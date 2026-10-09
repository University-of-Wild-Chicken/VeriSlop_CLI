"""Authored generic fixtures for all native Tier 0 gates; no live corpus answers."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verislop import (accept, agents, canonical, closure, contract, export, formal_frontend,
                      formalize, fsutil, generate, interpret, link, native_source, prove,
                      review_counterexamples, testing)
from verislop.events import EventSink
from verislop.package import Package
from tests.test_bootstrap_native_contract import proposal
from tests.test_agent_alignment import CapturingBroker


class NativePipeline(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pkg = Package(Path(self.temp.name) / "package")
        self.pkg.ensure("native-engineering-fixture")
        self.pkg.set_meta("requested", {"tier": 0, "target": "python", "endpoint": "test_campaign", "require_state": "TESTED"})
        self.events = EventSink(self.pkg.run_id, self.pkg.root, quiet=True)
        self.addCleanup(self.events.close)
        request = b'Implement pure bump(data) in worker.py: a record has one signed value field; return value plus one. Use only standard runtime facilities and no external I/O.'
        path = Path(self.temp.name) / "request.txt"
        path.write_bytes(request)
        draft = {"obligations": [{"id": oid, "kind": kind, "role": role, "statement": statement,
            "required": True, "scope": ["all admitted inputs"], "dependencies": [], "acceptance_criteria": [statement],
            "sources": [{"quote": request.decode(), "origin": "explicit", "interpretation": statement}]}
            for oid, kind, role, statement in (("D1", "entity", "declaration", "Signed record input and signed result"),
                ("O1", "postcondition", "guarantee", "Pure worker.py bump returns value plus one"),
                ("R1", "resource_constraint", "guarantee", "Standard runtime only and no external I/O"))],
            "category_review": {key: "reviewed" for key in agents.DRAFT_CATEGORIES},
            "clauses": [{"quote": request.decode(), "disposition": "obligations", "refs": ["D1", "O1", "R1"]}],
            "assumptions": [], "ambiguities": [], "selected_defaults": []}
        def interpreter(raw, ref, routing):
            a, b, problems = agents.assemble_interpretation(draft, raw, ref)
            self.assertEqual([], problems)
            return a, b
        self.pass_(interpret.run(self.pkg, self.events, path, mode="software", request_ref="request.txt", agent=interpreter))
        obj = proposal()
        obj["theorems"]["runtime"] = {"native": ["Boundary"]}
        obj["obligations"]["R1"] = {"theorem": "runtime"}
        draft, ledger, _ = formalize.require_interpretation(self.pkg)
        compiled = formal_frontend.compile_response(canonical.dumps(obj), formalize._records(draft, ledger, None), "fixture")
        self.pass_(formalize.run(self.pkg, self.events, agent=lambda _: (compiled.source, compiled.formalization), max_attempts=1))
        def proof(ctx):
            text = ctx["challenge"]
            text = text.replace(":= by sorry", ":= by exact ⟨by intros; rfl, VeriSlop.Native.contract_sound _⟩", 1)
            return text.replace(":= by sorry", ":= by exact VeriSlop.Native.contract_sound _")
        self.pass_(prove.run(self.pkg, self.events, portfolio=False, agent=proof, budget_seconds=0, max_attempts=1))
        self.pass_(accept.run(self.pkg, self.events))
        self.pass_(export.run(self.pkg, self.events))

    def pass_(self, result):
        self.assertEqual("PASS", result.status, [d.to_json() for d in result.diagnostics])

    def candidate(self, source='def bump(data):\n return data["value"] + 1\n', file="worker.py"):
        root = Path(self.temp.name) / "candidate"
        fsutil.atomic_write(root / file, source.encode())
        bindings = {"schema_version": "0.1", "artifact_kind": "implementation_bindings", "target": "python",
            "serialization_profile": "python-v0_2", "helpers": [], "bindings": [{"binding_id": "B1", "symbol": "bump",
            "object": {"file": file, "qualname": "bump"}, "obligations": ["O1", "R1"]}]}
        fsutil.write_json(root / "bindings.json", bindings)
        return root

    def test_mixed_and_native_only_resource_reach_tested_and_two_clean_builds(self):
        self.pass_(generate.run(self.pkg, self.events, candidate=self.candidate(), tier=0, target="python", require_state="TESTED"))
        self.pass_(link.run(self.pkg, self.events))
        self.pass_(testing.run(self.pkg, self.events, seed=45, cases=24))
        self.pass_(closure.run(self.pkg, self.events))
        report = canonical.load_file(self.pkg.path("report"))
        self.assertEqual("VERIFIED", report["terminal_status"])
        for oid in ("O1", "R1"):
            self.assertEqual("PASS", report["obligations"][oid]["outcomes"]["TESTED"])
            self.assertNotEqual("PASS", report["obligations"][oid]["outcomes"]["END_TO_END_VERIFIED"])
        results = canonical.load_file(self.pkg.path("tests") / "results.json")["obligations"]
        self.assertGreaterEqual(results["R1"]["counts"]["effective"], 20)
        probe = {"kind": "source_violation", "obligation_id": "R1", "file": "worker.py", "ast_path": "/body/0", "rule": "BORROWED_WRITE"}
        receipt = review_counterexamples.replay(self.pkg, "release", probe)
        self.assertEqual("NOT_REPRODUCED", receipt["status"], receipt["diagnostics"])
        actual = {"kind": "target_case", "obligation_id": "O1", "assignment": [{"dict": {"value": {"int": "-7"}}}]}
        receipt = review_counterexamples.replay(self.pkg, "release", actual)
        self.assertEqual("NOT_REPRODUCED", receipt["status"], receipt["diagnostics"])

    def test_borrowed_write_is_exact_source_counterexample_and_never_materializes(self):
        candidate = self.candidate('def bump(data):\n data["value"] += 1\n return data["value"]\n')
        result = generate.run(self.pkg, self.events, candidate=candidate, tier=0, target="python", require_state="TESTED")
        self.assertEqual("BLOCKED", result.status)
        ir = canonical.load_file(self.pkg.path("accepted_ir"))
        profile = contract.frozen_json(self.pkg, "profile.json")
        receipt = native_source.for_package(self.pkg, ir, profile,
            bindings=canonical.load_file(self.pkg.path("bridges") / "bindings.json"))
        diagnostic = receipt["obligations"]["R1"]["diagnostics"][0]
        probe = {"kind": "source_violation", "obligation_id": "R1", "file": diagnostic["file"],
                 "ast_path": diagnostic["ast_path"], "rule": diagnostic["code"]}
        replay = review_counterexamples.replay(self.pkg, "implementation", probe)
        self.assertEqual("CONFIRMED", replay["status"], replay["diagnostics"])
        changed = {**probe, "ast_path": "/wrong/site"}
        self.assertEqual("NOT_REPRODUCED", review_counterexamples.replay(self.pkg, "implementation", changed)["status"])

    def test_agent_repairs_exact_layout_and_ownership_diagnostics_before_staging(self):
        good = 'def bump(data):\n return data["value"] + 1\n'
        def response(file, source):
            return canonical.dumps({"files": {file: source}, "bindings": {
                "schema_version": "0.1", "artifact_kind": "implementation_bindings", "target": "python",
                "serialization_profile": "python-v0_2", "helpers": [], "bindings": [{"binding_id": "B1", "symbol": "bump",
                "object": {"file": file, "qualname": "bump"}, "obligations": ["O1", "R1"]}]}}).decode()
        responses = [response("wrong.py", good),
                     response("worker.py", 'def bump(data):\n data["value"] += 1\n return data["value"]\n'),
                     response("worker.py", good)]
        broker = CapturingBroker(responses)
        with patch.object(agents, "_broker", return_value=(broker, {"roles": {"implementer": "author"}})):
            self.pass_(generate.run(self.pkg, self.events, tier=0, target="python", require_state="TESTED",
                                   agent=agents.implementer_agent("unused", self.pkg, self.events)))
        self.assertEqual(3, len(broker.calls))
        self.assertIn("ENTRY_MISMATCH", broker.calls[1]["user"])
        self.assertIn(responses[0], broker.calls[1]["user"])
        self.assertIn("BORROWED_WRITE", broker.calls[2]["user"])
        self.assertIn(responses[1], broker.calls[2]["user"])
        self.assertEqual(good.encode(), (self.pkg.path("implementation") / "worker.py").read_bytes())
        self.assertFalse((self.pkg.path("implementation") / "wrong.py").exists())


class SourceProposalSyntax(unittest.TestCase):
    def test_source_probes_are_closed_bounded_and_have_no_invented_observations(self):
        obj = {"kind": "source_violation", "obligation_id": "R1", "file": "solution.py", "ast_path": "/body/0/body/0", "rule": "BORROWED_WRITE"}
        self.assertEqual([], review_counterexamples.validate_proposal(obj))
        self.assertTrue(review_counterexamples.validate_proposal({**obj, "status": "CONFIRMED"}))
        self.assertTrue(review_counterexamples.validate_proposal({**obj, "rule": "probably unsafe"}))
