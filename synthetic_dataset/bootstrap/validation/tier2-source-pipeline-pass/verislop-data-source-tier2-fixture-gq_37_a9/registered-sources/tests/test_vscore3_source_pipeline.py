"""Fresh unrelated record/value/source fixture through the registered 0.3 path."""
from __future__ import annotations

import tempfile
import copy
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from verislop import accept, agents, canonical, closure, export, formal_frontend, formalize, fsutil, generate, interpret, link, prove, schemas, source_contract, view, verifiers
from verislop.backends import registry, vscore3, vscore3_closure
from verislop.bridges import prepare, vscore3_checker
from verislop.evidence import validated_execution
from verislop.events import EventSink
from verislop.package import Package
from verislop.targets import vscore3_source

REQUEST = (b"Deliver a VSCore 0.3 pure source implementation. Packet has amount:Int, words:List String and extra:Option Int. "
           b"shift subtracts three from every mathematical integer. solve returns Packet.amount minus three. "
           b"Mapping shift over any integer list equals mapping subtraction of three. Deliver solve in program.vscore.json "
           b"with typed total evaluation, deterministic results, preserved inputs, no external I/O or floating point, "
           b"pure data and the restricted runtime. These source requirements are independently required and also part "
           b"of the value guarantee. This is a restricted source contract.")
VARIABLE = {"tag": "var", "index": 0}
ARITHMETIC = {"tag": "int_add", "left": VARIABLE, "right": {"tag": "int", "value": "-3"}}
SOLVE = {"tag": "int_add", "left": {"tag": "field", "sort": "Packet", "field": "amount", "value": VARIABLE},
         "right": {"tag": "int", "value": "-3"}}
AST = {
    "encoding": formal_frontend.VERSION,
    "records": {"Packet": {"fields": [{"name": "amount", "sort": "Int"},
        {"name": "words", "sort": {"list": "String"}}, {"name": "extra", "sort": {"option": "Int"}}]}},
    "symbols": {"shift": {"args": ["Int"], "result": "Int", "body": ARITHMETIC},
                "solve": {"args": [{"record": "Packet"}], "result": "Int", "body": SOLVE}},
    "predicates": {},
    "theorems": {
        "result": {"formula": {"tag": "forall", "sort": {"record": "Packet"}, "body": {"tag": "eq",
            "left": {"tag": "call", "symbol": "solve", "args": [VARIABLE]}, "right": SOLVE}}},
        "binder": {"formula": {"tag": "forall", "sort": {"list": "Int"}, "body": {"tag": "eq",
            "left": {"tag": "list_map", "value": VARIABLE, "function": {"sort": "Int", "body": {
                "tag": "call", "symbol": "shift", "args": [VARIABLE]}}},
            "right": {"tag": "list_map", "value": VARIABLE, "function": {"sort": "Int", "body": ARITHMETIC}}}}}},
    "obligations": {"D1": {"declarations": [{"kind": "record", "name": "Packet"},
        {"kind": "symbol", "name": "shift"}, {"kind": "symbol", "name": "solve"}]},
        "O1": {"theorem": "result"}, "O2": {"theorem": "binder"}},
    "witness_obligations": {},
}
AST["source_requirements"] = {"Delivery": {"symbol": "solve", "requirements": [
    {"tag": "entry", "file": "program.vscore.json", "entry": "solve", "arity": 1},
    *({"tag": tag} for tag in ("typed_total", "deterministic", "input_preserved", "no_external_io",
                              "no_floating_point", "pure_data", "restricted_runtime_only"))]}}
AST["theorems"]["result"]["source"] = ["Delivery"]
AST["theorems"]["source_only"] = {"source": ["Delivery"]}
AST["obligations"]["S1"] = {"theorem": "source_only"}
SURFACE = '''program "vscore/0.3" profile "data-pipeline/0.3";
record Packet { amount:Int; words:List(String); extra:Option(Int); }
entry shift(x:Int)->Int{x+int(-3)}
entry solve(p:Record(Packet))->Int{p.amount+int(-3)}
'''
RELATION = {"schema_version": "0.3", "format": "verislop.vscore-relation/0.3",
    "template": "vscore.reference_refinement/0.3", "source_slot": "vscore-source", "proof_slot": "vscore-proof",
    "bindings": [{"symbol": "shift", "entry": "shift"}, {"symbol": "solve", "entry": "solve"}]}
PROOF = b'''import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  all_goals intro x; with_unfolding_all rfl
end VeriSlopBridgeProof
'''


def accepted_fixture(root: Path) -> Package:
    """Author this fixture's request, interpretation and reference from fresh constants."""
    pkg = Package(root / "package")
    pkg.ensure("data-source-tier2-fixture")
    pkg.set_meta("requested", {"tier": 2, "target": "vscore", "endpoint": "restricted_source",
                               "backend_version": "0.3", "require_state": "END_TO_END_VERIFIED"})
    prompt = root / "request.txt"
    prompt.write_bytes(REQUEST)
    proposal = {"obligations": [{"id": oid, "kind": kind, "role": role, "statement": REQUEST.decode(),
        "required": True, "scope": ["all mathematical inputs under VSCore 0.3 semantics"], "dependencies": [],
        "acceptance_criteria": ["Exact accepted types and universal function equality"],
        "sources": [{"quote": REQUEST.decode(), "origin": "explicit", "interpretation": "the pure source record and integer function contract"}]}
        for oid, kind, role in (("D1", "entity", "declaration"), ("O1", "postcondition", "guarantee"),
                               ("O2", "invariant", "guarantee"), ("S1", "safety_property", "guarantee"))],
        "category_review": {k: "reviewed for the finite pure source fixture" for k in agents.DRAFT_CATEGORIES},
        "clauses": [{"quote": REQUEST.decode(), "disposition": "obligations", "refs": ["D1", "O1", "O2", "S1"]}],
        "assumptions": [], "ambiguities": [], "selected_defaults": []}
    events = EventSink(pkg.run_id, pkg.root, quiet=True)
    try:
        def interpreter(data, ref, routing):
            draft, ledger, problems = agents.assemble_interpretation(proposal, data, ref)
            if problems:
                raise AssertionError(problems)
            return draft, ledger
        stages = [interpret.run(pkg, events, prompt, mode="software", request_ref="request.txt", agent=interpreter)]
        raw = canonical.dumps(AST).decode()
        broker = SimpleNamespace(call=lambda *args: SimpleNamespace(text=raw, request_id="fresh-tier2-fixture"))
        with patch.object(agents, "_broker", return_value=(broker, {"roles": {"formalizer": "fixture-author"}})):
            stages.append(formalize.run(pkg, events, agent=agents.formalizer_agent("unused", pkg, events), max_attempts=1))
        for result in stages:
            if result.status != "PASS":
                raise AssertionError([d.to_json() for d in result.diagnostics])
        candidate = root / "contract-proof.lean"
        challenge = (pkg.path("contract") / "challenge/Contract.lean").read_text()
        tactics = {"binder": "intros; rfl", "result": "exact ⟨by intros; rfl, VeriSlop.Source.contract_sound _⟩",
                   "source_only": "exact VeriSlop.Source.contract_sound _"}
        authored = challenge
        for offset in reversed(prove.sorry_sites(challenge)):
            name = prove._short(prove.enclosing_decl(challenge, offset))
            authored = authored[:offset] + tactics[name] + authored[offset + 5:]
        candidate.write_text(authored)
        for operation in (prove.run, accept.run, export.run):
            result = operation(pkg, events, **({"budget_seconds": 0, "candidate": candidate, "portfolio": False} if operation is prove.run else {}))
            if result.status != "PASS":
                raise AssertionError([d.to_json() for d in result.diagnostics])
        return pkg
    finally:
        events.close()


class RegisteredVSCore3SourcePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="verislop-data-source-tier2-fixture-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.pkg = accepted_fixture(cls.root)
        cls.events = EventSink(cls.pkg.run_id, cls.pkg.root, quiet=True)
        cls.addClassCleanup(cls.events.close)
        cls.candidate = cls.root / "candidate"
        fsutil.atomic_write(cls.candidate / "program.vscore.json", vscore3_source.compile_surface(SURFACE))
        fsutil.write_json(cls.candidate / "relation.json", RELATION)
        fsutil.atomic_write(cls.candidate / "Proof.lean", PROOF)
        for operation, kwargs in ((generate.run, {"tier": 2, "target": "vscore", "backend_version": "0.3", "candidate": cls.candidate}),
                                  (link.run, {})):
            result = operation(cls.pkg, cls.events, **kwargs)
            if result.status != "PASS":
                raise AssertionError([d.to_json() for d in result.diagnostics])
        checked = vscore3_checker.accept(cls.pkg, "implementation", cls.events)
        if checked.status != "PASS":
            raise AssertionError([d.to_json() for d in checked.diagnostics])
        result = closure.run(cls.pkg, cls.events)
        if result.status != "PASS":
            raise AssertionError([d.to_json() for d in result.diagnostics])

        # Preserve actual observations and every module part before test cleanup.
        destination = Path(__file__).resolve().parents[1] / "synthetic_dataset/bootstrap/validation/tier2-source-pipeline-pass" / cls.root.name
        destination.mkdir(parents=True, exist_ok=False)
        shutil.copytree(cls.pkg.root, destination / "package")
        shutil.copytree(cls.candidate, destination / "candidate")
        sources = sorted({"verislop/" + rel for spec in verifiers.VERIFIERS.values() for rel in verifiers.CORE + spec["sources"]}
                         | {"schemas/" + name for spec in verifiers.VERIFIERS.values() for name in spec["schemas"]}
                         | {"tests/test_vscore3_source_pipeline.py"})
        repo = Path(__file__).resolve().parents[1]
        source_hashes = {}
        for rel in sources:
            data = (repo / rel).read_bytes()
            fsutil.atomic_write(destination / "registered-sources" / rel, data)
            source_hashes[rel] = canonical.digest(data)
        files = {str(path.relative_to(destination)): canonical.digest_file(path) for path in sorted(destination.rglob("*")) if path.is_file()}
        fsutil.write_json(destination / "capture.json", {"format": "verislop.tier2-source-pipeline-capture/0.1",
            "test": "tests.test_vscore3_source_pipeline", "captured_before_test_temp_cleanup": True,
            "historical_source_root": str(cls.root), "mechanical_status": "VERIFIED", "files": files,
            "source_hashes": source_hashes, "source_root": canonical.digest_json(source_hashes)})
        print("SOURCE_PIPELINE_CAPTURE", destination, flush=True)

    def test_complete_claim_graph_and_distinct_registered_version(self):
        report = canonical.load_file(self.pkg.path("report"))
        self.assertEqual([], schemas.validate("run-report-v3", report))
        self.assertEqual("VERIFIED", report["terminal_status"])
        self.assertEqual("VERIFIED", report["mechanical_status"])
        self.assertEqual(registry.VSCORE3_ID, report["backend"])
        self.assertEqual("vscore/0.3", report["language"])
        self.assertIn("END_TO_END_VERIFIED [restricted_source; vscore/0.3]", report["qualified_result"])
        for oid in ("O1", "O2", "S1"):
            self.assertEqual("PASS", report["obligations"][oid]["outcomes"]["END_TO_END_VERIFIED"])
            self.assertEqual("PENDING", report["obligations"][oid]["outcomes"]["TESTED"])
        ir = canonical.load_file(self.pkg.path("accepted_ir"))
        self.assertEqual("source_facets", ir["obligations"]["O1"]["formal"]["representation"])
        self.assertEqual("source_facets", ir["obligations"]["S1"]["formal"]["representation"])
        self.assertEqual("contract_dsl", ir["obligations"]["O2"]["formal"]["representation"])
        for oid in ("O1", "S1"):
            package = vscore3.admission.formula_package(self.pkg, ir["obligations"][oid])
            self.assertEqual({"solve"}, source_contract.symbols(package))
            self.assertEqual(8, len(source_contract.source_facets(package)[0]["requirements"]))
            self.assertEqual(package["value"] is None, oid == "S1")
        selected = vscore3.selection(self.pkg)
        self.assertEqual(["O1", "O2", "S1"], [r["id"] for r in selected["covered"]])
        materialized = canonical.load_file(self.pkg.path("implementation") / "materialization.json")
        self.assertFalse(materialized["proof_checked"])
        linked = canonical.load_file(self.pkg.path("bridges") / "link.json")
        self.assertIn("accepted_record", {o["kind"] for d in linked["declarations"] for o in d["objects"]})
        self.assertTrue(all(report["obligations"]["D1"]["outcomes"][m] == "PASS" for m in ("IMPLEMENTED", "LINKED")))
        self.assertTrue(prepare.verify_preparation(self.pkg, "implementation", semantic="rebuild").summary["semantic_acceptance"])

    def test_current_execution_revalidates_and_source_mutation_invalidates(self):
        snapshot = vscore3_closure.mechanical_snapshot(self.pkg)
        self.assertIsNotNone(snapshot)
        execution = self.pkg.root / snapshot["mechanical_result_path"]
        self.assertEqual("VERIFIED", validated_execution(execution.parent)["mechanical_status"])
        child_root = self.root / "changed"
        import shutil
        shutil.copytree(self.pkg.root, child_root)
        child = Package(child_root)
        fsutil.atomic_write(child.path("implementation") / "program.vscore.json",
                            (child.path("implementation") / "program.vscore.json").read_bytes() + b"\n")
        with self.assertRaises(vscore3_closure.InvalidPackage):
            vscore3_closure.mechanical_snapshot(child)
        overlay = view.derive(child)
        self.assertNotEqual("PASS", overlay["obligations"]["O1"]["lifecycle"]["END_TO_END_VERIFIED"]["outcome"])


if __name__ == "__main__":
    unittest.main()
