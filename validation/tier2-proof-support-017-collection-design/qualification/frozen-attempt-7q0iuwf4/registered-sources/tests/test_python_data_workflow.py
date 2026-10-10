"""Kernel-accepted data contracts drive Python linkage, TESTED and exact reviewer replay.

The contracts and implementations here are explicit verification fixtures, not native model
outputs. No provider calls or simulated proof/accepted-IR boundaries are used in these tests.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import TempDir
from test_data_contract_core import SOURCE
from verislop import accept, agents, canonical, closure, contract, dsl, export, formalize, fsutil, generate, interpret, link, prove, review, review_counterexamples as rc, testing, view
from verislop.events import EventSink
from verislop.package import Package
from verislop.targets import python_target as pt


REQUEST = ("Implement numericSolve on values, minimum and factor: filter signed integers at least minimum, multiply by factor, preserve order and duplicates, and return values, total and count. "
           "Implement rowsSolve on rows and threshold: keep enabled records whose signed amount is at least threshold, preserve Unicode tags and amounts in order, and return rows, total and count. "
           "Implement labelsSolve on labels and prefix: remove only empty strings, prepend prefix preserving Unicode, duplicates and order, and return labels and count.").encode()
PYTHON = '''def numericSolve(data):
    values = [x * data["factor"] for x in data["values"] if x >= data["minimum"]]
    return {"values": values, "total": sum(values), "count": len(values)}

def rowsSolve(data):
    rows = [{"tag": r["tag"], "amount": r["amount"]} for r in data["rows"] if r["enabled"] and r["amount"] >= data["threshold"]]
    return {"rows": rows, "total": sum([r["amount"] for r in rows]), "count": len(rows)}

def labelsSolve(data):
    labels = [data["prefix"] + s for s in data["labels"] if s != ""]
    return {"labels": labels, "count": len(labels)}
'''
NAMES = ["numericSolve", "rowsSolve", "labelsSolve"]
THEOREMS = ["numeric_contract", "rows_contract", "labels_contract"]


class PythonDataWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.base = cls.tmp.path / "accepted-data"
        cls.pkg = Package(cls.base)
        cls.pkg.ensure("accepted-data-workflow")
        events = EventSink(cls.pkg.run_id, cls.pkg.root, quiet=True)
        try:
            prompt = cls.tmp.path / "request.txt"
            prompt.write_bytes(REQUEST)
            clauses = agents._request_clauses(REQUEST)
            obligations = [{"id": "D1", "kind": "entity", "role": "declaration", "statement": "Three total record-input and record-output data operations.",
                "required": True, "scope": ["all admitted inputs"], "dependencies": [], "acceptance_criteria": ["Bind the three reference functions."],
                "sources": [{"quote": c["quote"], "origin": "explicit", "interpretation": "record fields and function identity"} for c in clauses]}]
            for i, c in enumerate(clauses, 1):
                obligations.append({"id": f"O{i}", "kind": "postcondition", "role": "guarantee", "statement": c["quote"], "required": True,
                    "scope": ["all admitted inputs"], "dependencies": [{"id": "D1", "relation": "uses_definition"}],
                    "acceptance_criteria": ["Exact record output equals the specified filtered and mapped values, totals and counts."],
                    "sources": [{"quote": c["quote"], "origin": "explicit", "interpretation": "complete observable behavior"}]})
            proposal = {"obligations": obligations, "category_review": {k: "reviewed" for k in agents.DRAFT_CATEGORIES},
                "clauses": [{"clause_id": c["clause_id"], "quote": c["quote"], "disposition": "obligations", "refs": ["D1", f"O{i}"]} for i, c in enumerate(clauses, 1)],
                "assumptions": [], "ambiguities": [], "selected_defaults": []}

            def interpreter(prompt_bytes, ref, routing):
                draft, ledger, problems = agents.assemble_interpretation(proposal, prompt_bytes, ref)
                if problems:
                    raise AssertionError(problems)
                return draft, ledger

            cls.assert_pass(interpret.run(cls.pkg, events, prompt, mode="software", request_ref="request.txt", agent=interpreter))
            formdir = cls.tmp.path / "formalization"
            fsutil.atomic_write(formdir / "Contract.lean", SOURCE.encode())
            fsutil.write_json(formdir / "formalization.json", {"schema_version": "0.1", "artifact_kind": "formalization_candidate",
                "profile_id": "data-workflow.v0_2", "lean_toolchain": "leanprover/lean4:v4.34.1", "lean_file": "Contract.lean",
                "bindings": [{"obligation": "D1", "declarations": ["DataCore." + n for n in NAMES]}] +
                            [{"obligation": f"O{i}", "theorem": "DataCore." + n} for i, n in enumerate(THEOREMS, 1)], "internal_obligations": []})
            cls.assert_pass(formalize.run(cls.pkg, events, candidate=formdir))
            cls.assert_pass(prove.run(cls.pkg, events, budget_seconds=0))
            cls.assert_pass(accept.run(cls.pkg, events))
            cls.assert_pass(export.run(cls.pkg, events))
        finally:
            events.close()

    @classmethod
    def assert_pass(cls, result):
        if result.status != "PASS":
            raise AssertionError((result.command, result.status, [d.to_json() for d in result.diagnostics]))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.location = self.tmp.path / self._testMethodName
        self.pkg = Package(self.location)
        self.pkg.ensure(self._testMethodName)
        # Copy the frozen, accepted inputs and their registered evidence to a fresh package.
        # Package-relative evidence roots stay identical; implementation candidates are new.
        fsutil.remove_tree(self.location)
        import shutil
        shutil.copytree(self.base, self.location, symlinks=True)
        self.pkg = Package(self.location, resolve_root=False)
        self.events = EventSink(self.pkg.run_id, self.pkg.root, quiet=True)
        self.addCleanup(self.events.close)

    def deliver(self, source=PYTHON, tier=0):
        impl = self.tmp.path / (self._testMethodName + "-candidate")
        fsutil.atomic_write(impl / "data_pipeline.py", source.encode())
        fsutil.write_json(impl / "bindings.json", {"schema_version": "0.1", "artifact_kind": "implementation_bindings", "target": "python",
            "serialization_profile": pt.PROFILE_ID_V2, "helpers": [], "bindings": [{"binding_id": "B-" + name, "symbol": name,
            "object": {"file": "data_pipeline.py", "qualname": name}, "obligations": [f"O{i}"]} for i, name in enumerate(NAMES, 1)]})
        result = generate.run(self.pkg, self.events, candidate=impl, tier=tier, target="python", require_state="TESTED")
        if tier == 0:
            self.assert_pass(result)
            self.assert_pass(link.run(self.pkg, self.events))
        return result

    def test_accepted_record_artifacts_drive_real_tested_campaign_and_concrete_reviewer_inputs(self):
        self.deliver()
        result = testing.run(self.pkg, self.events, seed=43, cases=32)
        self.assert_pass(result)
        obligations = view.derive(self.pkg)["obligations"]
        for oid in ("O1", "O2", "O3"):
            self.assertEqual("contract_dsl", obligations[oid]["formal"]["representation"])
            self.assertEqual("PASS", obligations[oid]["lifecycle"]["PROVED"]["outcome"])
            self.assertEqual("PASS", obligations[oid]["lifecycle"]["TESTED"]["outcome"])
            self.assertEqual(32, result.summary["obligations"][oid]["counts"]["effective"])
            self.assertNotEqual("PASS", obligations[oid]["lifecycle"]["END_TO_END_VERIFIED"]["outcome"])
        profile = dsl.Profile.from_json(contract.frozen_json(self.pkg, "profile.json"))
        value = dsl.record_v("NumericIn", [(-7, -2, -2, 0, 3), -2, -3])
        proposal = {"kind": "target_case", "obligation_id": "O1", "assignment": [pt.encode_arg(value, {"record": "NumericIn"}, profile)]}
        receipt = rc.replay(self.pkg, "implementation", proposal)
        self.assertEqual("NOT_REPRODUCED", receipt["status"], receipt)
        packet = review.build_packet(self.pkg, "implementation")
        self.assertEqual(pt.PROFILE_ID_V2, packet["counterexample_policy"]["target_case_binders"]["serialization_profile"])
        self.assertEqual({"values", "minimum", "factor"}, set(packet["counterexample_policy"]["target_case_binders"]["obligations"]["O1"]["assignment_example"][0]["dict"]))
        self.assert_pass(closure.run(self.pkg, self.events))
        report = canonical.load_file(self.pkg.path("report"))
        self.assertEqual("VERIFIED", report["terminal_status"])
        self.assertFalse(report["endpoint"]["end_to_end_eligible"])
        for oid in ("O1", "O2", "O3"):
            self.assertEqual("PASS", report["obligations"][oid]["outcomes"]["TESTED"])
            self.assertNotEqual("PASS", report["obligations"][oid]["outcomes"]["END_TO_END_VERIFIED"])

    def test_real_accepted_numeric_contract_rejects_wrong_total_with_confirmed_counterexample(self):
        mutant = PYTHON.replace('"total": sum(values)', '"total": sum(values) + 1')
        self.deliver(mutant)
        result = testing.run(self.pkg, self.events, seed=43, cases=24)
        self.assertEqual("BLOCKED", result.status)
        self.assertIn("TEST_FAILURE", [d.code for d in result.diagnostics])
        self.assertEqual("FAIL", result.summary["obligations"]["O1"]["outcome"])
        profile = dsl.Profile.from_json(contract.frozen_json(self.pkg, "profile.json"))
        value = dsl.record_v("NumericIn", [(-2, -2, 3), -2, -3])
        receipt = rc.replay(self.pkg, "implementation", {"kind": "target_case", "obligation_id": "O1",
                            "assignment": [pt.encode_arg(value, {"record": "NumericIn"}, profile)]})
        self.assertEqual("CONFIRMED", receipt["status"], receipt)
        self.assertFalse(receipt["observed"]["predicate"])

    def test_tier1_does_not_silently_claim_structured_runtime_monitor_semantics(self):
        result = self.deliver(tier=1)
        self.assertEqual("BLOCKED", result.status)
        self.assertIn("UNSUPPORTED_CAPABILITY", [d.code for d in result.diagnostics])
        self.assertFalse((self.pkg.path("implementation") / "data_pipeline.py").is_file())

    def test_artifact_origin_reconstructs_bindings_challenge_proof_and_complete_files(self):
        # Synthetic transcript-shaped fixtures exercise reconstruction only; they
        # are not authenticated provider calls and cannot count as a native PoC.
        from synthetic_dataset.tools.run_data_pipeline_poc import artifact_origin_audit
        self.deliver()
        form = canonical.load_file(self.pkg.path("contract") / "candidate/formalization.json")
        calls = [{"purpose": "formalize", "response": canonical.dumps({"lean_source": SOURCE, "formalization": form}).decode()},
                 {"purpose": "generate", "response": canonical.dumps({"files": {"data_pipeline.py": PYTHON},
                     "bindings": canonical.load_file(self.pkg.path("bridges") / "bindings.json")}).decode()}]
        audit = artifact_origin_audit(self.pkg, calls)
        self.assertEqual([], audit["issues"], audit)
        self.assertTrue(audit["proof_origins"])
        changed = copy.deepcopy(calls)
        bad_form = {**form, "profile_id": "a.different.profile"}
        changed[0]["response"] = canonical.dumps({"lean_source": SOURCE, "formalization": bad_form}).decode()
        self.assertTrue(artifact_origin_audit(self.pkg, changed)["issues"])
        extra = self.pkg.path("implementation") / "injected.py"
        extra.write_text("def injected(x):\n    return x\n")
        self.assertIn("Implementation bytes have no exact complete native proposal origin",
                      artifact_origin_audit(self.pkg, calls)["issues"])


if __name__ == "__main__":
    unittest.main()
