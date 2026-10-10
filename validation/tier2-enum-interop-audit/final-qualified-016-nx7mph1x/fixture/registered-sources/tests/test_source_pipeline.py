"""Fresh source-only and mixed contracts cross the ordinary accepted-kernel pipeline."""
from __future__ import annotations

import copy
import os
import stat
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from verislop import accept, agents, canonical, contract, export, formalize, fsutil, interpret, policy, prove, source_contract
from verislop.backends import admission
from verislop.events import EventSink
from verislop.exprjson import name_str
from verislop.package import Package
from tests.test_source_frontend import frozen_records, source_proposal


SOURCE_REQUEST = ("Deliver plus with arity one in program.vscore.json as total typed pure data under VSCore 0.3. "
                  "Its restricted-source evaluation is deterministic, preserves its input, has no external I/O "
                  "or floating point, and uses only the restricted source runtime.")
VALUE_REQUEST = "For every mathematical signed Int x, plus(x) returns x + 2 and retains all those source guarantees."
REQUEST = (SOURCE_REQUEST + "\n" + VALUE_REQUEST).encode()


def accepted_fixture(root: Path):
    """Mock only the source author; interpretation, proofs, acceptance and export are real."""
    pkg = Package(root / "package")
    pkg.ensure("fresh-source-acceptance-pipeline")
    pkg.set_meta("requested", {"tier": 2, "target": "vscore", "endpoint": "restricted_source",
                              "backend_version": "0.3", "require_state": "END_TO_END_VERIFIED"})
    events = EventSink(pkg.run_id, pkg.root, quiet=True)
    results = {}

    def passed(name, result):
        results[name] = result.to_json()
        if result.status != "PASS":
            raise AssertionError((name, [d.to_json() for d in result.diagnostics]))

    try:
        prompt = root / "request.txt"
        prompt.write_bytes(REQUEST)
        records = frozen_records() + [{**frozen_records()[0], "id": "G2"}]
        records[0].update(kind="safety_property", statement=SOURCE_REQUEST)
        records[1].update(statement=VALUE_REQUEST)
        interpretation = {"obligations": [{**row, "scope": ["all typed signed integer inputs"],
            "sources": [{"quote": row["statement"], "origin": "explicit", "interpretation": "exact restricted-source guarantee"}]}
            for row in records], "category_review": {k: "reviewed" for k in agents.DRAFT_CATEGORIES},
            "clauses": [{"quote": row["statement"], "disposition": "obligations", "refs": [row["id"]]} for row in records],
            "assumptions": [], "ambiguities": [], "selected_defaults": []}

        def interpreter(data, ref, _routing):
            draft, ledger, problems = agents.assemble_interpretation(interpretation, data, ref)
            if problems:
                raise AssertionError(problems)
            return draft, ledger

        passed("interpret", interpret.run(pkg, events, prompt, mode="software", request_ref="fresh-request.txt", agent=interpreter))
        proposal = source_proposal()
        proposal["theorems"]["ValueSpec"] = source_proposal(mixed=True)["theorems"]["Spec"]
        proposal["obligations"]["G2"] = {"theorem": "ValueSpec"}
        response = canonical.dumps(proposal).decode()
        broker = SimpleNamespace(call=lambda *_args: SimpleNamespace(text=response, request_id="fresh-source-fixture"))
        with patch.object(agents, "_broker", return_value=(broker, {"roles": {"formalizer": "author"}})):
            author = agents.formalizer_agent("unused", pkg, events)
            passed("formalize", formalize.run(pkg, events, agent=author, max_attempts=1))
        check = canonical.load_file(pkg.path("contract") / "candidate/statement-check.json")
        if not check["frontend_defeq"] or not all(row["result"].get("defeq") for row in check["frontend_defeq"]):
            raise AssertionError(check)
        proof = (pkg.path("contract") / "candidate/proposal.lean").read_text()
        if proof.count(":= by sorry") != 2:
            raise AssertionError("fresh fixture must have exactly its two original theorem holes")
        proof = proof.replace(":= by sorry", ":= by exact VeriSlop.Source.contract_sound _", 1)
        proof = proof.replace(":= by sorry", ":= by exact ⟨by intros; rfl, VeriSlop.Source.contract_sound _⟩", 1)
        proof_path = root / "fresh-proof.lean"
        proof_path.write_text(proof)
        passed("prove", prove.run(pkg, events, candidate=proof_path, portfolio=False, budget_seconds=0))
        passed("accept", accept.run(pkg, events))
        passed("export", export.run(pkg, events))
        fsutil.write_json(root / "stage-results.json", results)
        return pkg, results
    finally:
        events.close()


@contextmanager
def changed_bytes(path: Path, data: bytes):
    original, mode = path.read_bytes(), stat.S_IMODE(path.stat().st_mode)
    os.chmod(path, mode | stat.S_IWUSR)
    path.write_bytes(data)
    try:
        yield
    finally:
        path.write_bytes(original)
        os.chmod(path, mode)


class SourceAcceptancePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="verislop-source-pipeline-")
        cls.root = Path(cls.tmp.name)
        cls.addClassCleanup(cls.cleanup)
        cls.pkg, cls.stages = accepted_fixture(cls.root)
        cls.ir_bytes = cls.pkg.path("accepted_ir").read_bytes()
        cls.ir = canonical.loads(cls.ir_bytes)
        cls.cert_path = cls.pkg.path("accepted") / "acceptance.json"
        cls.cert = canonical.load_file(cls.cert_path)

    @classmethod
    def cleanup(cls):
        if cls.root.exists():
            fsutil.make_writable_tree(cls.root)
        cls.tmp.cleanup()

    def events(self):
        sink = EventSink(self.pkg.run_id, quiet=True)
        self.addCleanup(sink.close)
        return sink

    def test_complete_original_ids_and_source_only_endpoint_survive_accepted_reconstruction(self):
        self.assertEqual(set(self.ir["obligations"]), {"G1", "G2"})
        self.assertEqual(self.cert["gate"], "accepted_and_proved")
        self.assertTrue(all(result["status"] == "PASS" for result in self.stages.values()))
        environment = canonical.load_file(self.pkg.root / self.cert["artifacts"]["environment_export"]["path"])
        env = contract.Env.from_export(environment, policy.get("strict"), "fresh accepted source")
        self.assertEqual(env.diagnostics, [])
        for oid, rec in self.ir["obligations"].items():
            self.assertTrue(rec["required"])
            self.assertEqual(rec["formal"]["representation"], "source_facets")
            self.assertEqual(rec["formal"]["statement_hash"], self.cert["obligations"][oid]["statement_hash"])
            package = admission.formula_package(self.pkg, rec)
            self.assertEqual(package["encoding"], source_contract.ENCODING)
            self.assertEqual(source_contract.symbols(package), {"plus"})
            facet = package["source"][0]
            self.assertEqual(facet["requirements"], source_proposal()["source_requirements"]["Delivery"]["requirements"])
            self.assertEqual(facet["definition"], "VeriSlopAST.Delivery")
            self.assertEqual(facet["definition_hash"], env.hashes[facet["definition"]])
            self.assertEqual(facet["lean_decl"], "VeriSlopAST.plus")
            self.assertEqual(facet["decl_hash"], env.hashes[facet["lean_decl"]])
            self.assertEqual(facet["model_version"], source_contract.MODEL_VERSION)
            self.assertEqual(facet["model_source_hash"], source_contract.model_source_hash())
            if oid == "G1":
                self.assertIsNone(package["value"])
                self.assertIsNone(package["value_projection"])
            else:
                projection = package["value_projection"]
                self.assertEqual(projection["source_theorem"], "VeriSlopAST.ValueSpec")
                self.assertEqual(projection["decl_hash"], env.hashes[projection["lean_symbol"]])
                self.assertIn(projection["source_theorem"], {name_str(n) for n in env.decls[projection["lean_symbol"]]["value_constants"]})
        profile = canonical.load_file(self.pkg.root / self.cert["artifacts"]["profile"]["path"])
        self.assertEqual(set(profile["symbols"]), {"plus"})
        _, _, _, diagnostics = export.verified_ir(self.pkg)
        self.assertEqual(diagnostics, [])

    def test_author_json_mutation_after_acceptance_has_no_semantic_authority(self):
        path = self.pkg.path("contract") / "candidate/typed-proposal.json"
        altered = canonical.load_file(path)
        altered["source_requirements"]["Delivery"]["requirements"][0]["file"] = "forged.py"
        altered["symbols"]["plus"]["body"]["right"]["value"] = "99"
        with changed_bytes(path, canonical.dumps(altered)):
            result = export.run(self.pkg, self.events())
            self.assertEqual(result.status, "PASS", [d.to_json() for d in result.diagnostics])
            self.assertTrue(result.summary["byte_identical_to_previous"])
            self.assertEqual(self.pkg.path("accepted_ir").read_bytes(), self.ir_bytes)
            self.assertEqual(admission.formula_package(self.pkg, self.ir["obligations"]["G1"])["source"][0]["requirements"][0]["file"],
                             "program.vscore.json")

    def test_mutated_accepted_source_and_frozen_model_bytes_invalidate_currency(self):
        accepted_source = self.pkg.root / self.cert["artifacts"]["source"]["path"]
        frozen_source = contract.challenge_dir(self.pkg) / "Contract.lean"
        model = frozen_source.read_bytes()
        self.assertIn(b"| .typedTotal => m.typedTotal", model)
        for path, altered in ((accepted_source, accepted_source.read_bytes() + b"\n-- mutated accepted source\n"),
                              (frozen_source, model.replace(b"| .typedTotal => m.typedTotal", b"| .typedTotal => false", 1))):
            with self.subTest(path=str(path)), changed_bytes(path, altered):
                _, _, _, diagnostics = export.verified_ir(self.pkg)
                self.assertIn("INPUT_MUTATION", {d.code for d in diagnostics})
        _, _, _, diagnostics = export.verified_ir(self.pkg)
        self.assertEqual(diagnostics, [])


if __name__ == "__main__":
    unittest.main()
