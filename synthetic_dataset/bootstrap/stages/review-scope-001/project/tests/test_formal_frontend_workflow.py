"""Authored frontend fixtures cross real Lean/TESTED gates; not native PoC scores."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from verislop import accept, agents, canonical, closure, contract, export, formal_frontend, formalize, fsutil, generate, interpret, link, prove, testing
from verislop.events import EventSink
from verislop.package import Package
from synthetic_dataset.tools.run_data_pipeline_poc import artifact_origin_audit, task_status


REQUEST = b"Implement bump(data) on a record with one signed value field, returning exactly that value plus one."
VARIABLE = {"tag": "var", "index": 0}
BODY = {"tag": "int_add", "left": {"tag": "field", "sort": "Input", "field": "value", "value": VARIABLE},
        "right": {"tag": "int", "value": "1"}}
AST = {"encoding": formal_frontend.VERSION, "records": {"Input": {"fields": [{"name": "value", "sort": "Int"}]}},
       "symbols": {"bump": {"args": [{"record": "Input"}], "result": "Int", "body": BODY}},
       "predicates": {}, "theorems": {"result": {"formula": {"tag": "forall", "sort": {"record": "Input"},
           "body": {"tag": "eq", "left": {"tag": "call", "symbol": "bump", "args": [VARIABLE]}, "right": BODY}}}},
       "obligations": {"D1": {"declarations": [{"kind": "record", "name": "Input"}, {"kind": "symbol", "name": "bump"}]},
                       "O1": {"theorem": "result"}}, "witness_obligations": {}}


class FrontendWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(Path(self.tmp.name) / "package")
        self.pkg.ensure("authored-frontend-workflow")
        self.pkg.set_meta("requested", {"tier": 0, "target": "python", "endpoint": "test_campaign", "require_state": "TESTED"})
        self.events = EventSink(self.pkg.run_id, self.pkg.root, quiet=True)
        self.addCleanup(self.events.close)
        prompt = Path(self.tmp.name) / "request.txt"
        prompt.write_bytes(REQUEST)
        proposal = {"obligations": [{"id": oid, "kind": kind, "role": role, "statement": REQUEST.decode(),
            "required": True, "scope": ["all admitted inputs"], "dependencies": [],
            "acceptance_criteria": ["Exact type and observable value"],
            "sources": [{"quote": REQUEST.decode(), "origin": "explicit", "interpretation": "record and exact signed addition"}]}
            for oid, kind, role in (("D1", "entity", "declaration"), ("O1", "postcondition", "guarantee"))],
            "category_review": {k: "reviewed" for k in agents.DRAFT_CATEGORIES},
            "clauses": [{"quote": REQUEST.decode(), "disposition": "obligations", "refs": ["D1", "O1"]}],
            "assumptions": [], "ambiguities": [], "selected_defaults": []}
        def interpreter(data, ref, routing):
            draft, ledger, problems = agents.assemble_interpretation(proposal, data, ref)
            self.assertEqual([], problems)
            return draft, ledger
        self.assert_pass(interpret.run(self.pkg, self.events, prompt, mode="software", request_ref="request.txt", agent=interpreter))

    def assert_pass(self, result):
        self.assertEqual("PASS", result.status, [d.to_json() for d in result.diagnostics])

    def test_exact_agent_ast_crosses_kernel_proofs_reconstruction_and_real_campaign(self):
        raw = canonical.dumps(AST).decode()
        broker = SimpleNamespace(call=lambda *args: SimpleNamespace(text=raw, request_id="authored-fixture"))
        with patch.object(agents, "_broker", return_value=(broker, {"roles": {"formalizer": "author"}})):
            proposer = agents.formalizer_agent("unused", self.pkg, self.events)
            self.assert_pass(formalize.run(self.pkg, self.events, agent=proposer, max_attempts=1))
        check = canonical.load_file(self.pkg.path("contract") / "candidate/statement-check.json")
        self.assertTrue(check["frontend_defeq"])
        self.assertTrue(all(row["result"]["defeq"] for row in check["frontend_defeq"]))
        self.assert_pass(prove.run(self.pkg, self.events, budget_seconds=0))
        self.assert_pass(accept.run(self.pkg, self.events))
        self.assert_pass(export.run(self.pkg, self.events))
        source = 'def bump(data):\n    return data["value"] + 1\n'
        candidate = Path(self.tmp.name) / "implementation"
        fsutil.atomic_write(candidate / "main.py", source.encode())
        fsutil.write_json(candidate / "bindings.json", {"schema_version": "0.1", "artifact_kind": "implementation_bindings", "target": "python",
            "serialization_profile": "python-v0_2", "helpers": [], "bindings": [{"binding_id": "B1", "symbol": "bump",
                "object": {"file": "main.py", "qualname": "bump"}, "obligations": ["O1"]}]})
        self.assert_pass(generate.run(self.pkg, self.events, candidate=candidate, tier=0, target="python", require_state="TESTED"))
        self.assert_pass(link.run(self.pkg, self.events))
        self.assert_pass(testing.run(self.pkg, self.events, seed=71, cases=24))
        self.assert_pass(closure.run(self.pkg, self.events))
        report = canonical.load_file(self.pkg.path("report"))
        self.assertEqual("VERIFIED", report["terminal_status"])
        self.assertEqual("PASS", report["obligations"]["O1"]["outcomes"]["TESTED"])
        self.assertNotEqual("PASS", report["obligations"]["O1"]["outcomes"]["END_TO_END_VERIFIED"])
        calls = [{"purpose": "formalize", "response": raw},
            {"purpose": "generate", "response": canonical.dumps({"files": {"main.py": source},
                "bindings": canonical.load_file(self.pkg.path("bridges") / "bindings.json")}).decode()}]
        audit = artifact_origin_audit(self.pkg, calls)
        self.assertEqual([], audit["issues"], audit)
        self.assertEqual("generic-typed-AST-compiler", audit["formalization_origins"][0]["assembly"])
        binding_path = self.pkg.path("bridges") / "bindings.json"
        changed = canonical.load_file(binding_path)
        changed["bindings"][0]["binding_id"] = "hand-edited"
        fsutil.write_json(binding_path, changed)
        self.assertIn("Implementation bytes have no exact complete native proposal origin",
                      artifact_origin_audit(self.pkg, calls)["issues"])

    def test_faithfully_rejected_placeholder_does_not_veto_a_later_success(self):
        raw = "not JSON"
        draft, ledger, _ = formalize.require_interpretation(self.pkg)
        records = formalize._records(draft, ledger, None)
        with self.assertRaises(ValueError) as failure:
            agents.assemble_formalization_response(raw, records, "captured-provider-response")
        candidate = self.pkg.path("contract") / "candidate"
        fsutil.atomic_write(candidate / "proposal.lean", b"-- unparseable formalizer response\n")
        fsutil.write_json(candidate / "formalization.json", {"error": f"unparseable formalizer response: {failure.exception}"})
        audit = artifact_origin_audit(self.pkg, [{"purpose": "formalize", "response": raw}])
        self.assertEqual([], audit["issues"], audit)
        self.assertFalse(audit["formalization_origins"][0]["positive_artifact"])
        self.assertEqual("VERIFIED", task_status({"status": "PASS"}, 0, {"status": "VERIFIED"},
            [{"status": "PASS"}, {"status": "PASS"}], bound=True, unchanged=True))
        fsutil.write_json(candidate / "formalization.json", {"error": "manually changed diagnostic"})
        self.assertTrue(artifact_origin_audit(self.pkg, [{"purpose": "formalize", "response": raw}])["issues"])

    def test_exact_native_invalid_manifest_is_a_rejection_not_origin_failure(self):
        source, form = "def invalid_candidate : Nat := 0\n", {"bindings": []}
        candidate = self.pkg.path("contract") / "candidate"
        fsutil.atomic_write(candidate / "proposal.lean", source.encode())
        fsutil.write_json(candidate / "formalization.json", form)
        audit = artifact_origin_audit(self.pkg, [{"purpose": "formalize", "response": canonical.dumps({
            "lean_source": source, "formalization": form}).decode()}])
        self.assertEqual([], audit["issues"], audit)
        self.assertFalse((contract.challenge_dir(self.pkg) / "challenge.json").exists())

    def test_miscompiled_primitive_fails_real_kernel_fidelity_before_freeze(self):
        draft, ledger, _ = formalize.require_interpretation(self.pkg)
        records = formalize._records(draft, ledger, None)
        compiled = formal_frontend.compile_response(canonical.dumps(AST), records, "generated.v0_2")
        broken = copy.copy(compiled)
        broken.source = compiled.source.replace(b"_root_.Int.add", b"_root_.Int.sub")
        def proposer(ctx):
            return broken.source, broken.formalization
        proposer.last_compiled = broken
        result = formalize.run(self.pkg, self.events, agent=proposer, max_attempts=1)
        self.assertEqual("BLOCKED", result.status)
        self.assertTrue(any(d.code == "IR_REIFICATION_MISMATCH" for d in result.diagnostics), [d.to_json() for d in result.diagnostics])
        self.assertFalse((contract.challenge_dir(self.pkg) / "challenge.json").exists())
