"""Authored interpreter protocol coverage, without model or kernel qualification."""
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from unittest.mock import patch

from verislop import agent_memory, agents, canonical, draft, source_policy
from verislop.events import EventSink
from verislop.package import Package


class InterpreterWorkflowContextTests(unittest.TestCase):
    def test_requested_checker_obligations_and_supervisor_context_survive_native_interpreter_path(self):
        prompt = (
            "Implement a verifier that checks each supplied artifact's contract metadata against its declared "
            "metadata and returns every mismatch in input order.\n"
            "Maintain an audit log of every supplied record, including matching records and duplicate names.\n"
            "Input lists may be empty and contain arbitrary Unicode scalar names and mathematical integers.\n"
            "Supervisor workflow: the CLI must check this run's reconstructed facets before proof and at closure.\n"
            "Supervisor workflow: this run selects a restricted-source endpoint and trusts its pinned kernel.\n"
        ).encode("utf-8")
        manifest = agents._request_clauses(prompt)
        self.assertEqual(5, len(manifest))
        ids = ("O-check", "I-log", "D-input")
        kinds = ("postcondition", "invariant", "entity")
        roles = ("guarantee", "guarantee", "declaration")
        proposal = {"obligations": [
            {"id": oid, "kind": kind, "role": role, "required": True,
             "statement": clause["quote"], "scope": ["all supplied records"], "dependencies": [],
             "acceptance_criteria": ["complete requested behavior"],
             "sources": [{"clause_id": clause["clause_id"], "origin": "explicit",
                          "interpretation": "requested implementation behavior or complete input domain"}]}
            for oid, kind, role, clause in zip(ids, kinds, roles, manifest)],
            "clauses": [{"clause_id": clause["clause_id"], "disposition": "obligations", "refs": [oid]}
                        for oid, clause in zip(ids, manifest[:3])] +
                       [{"clause_id": clause["clause_id"], "disposition": "context", "refs": [],
                         "note": "Supervisor instructions for the verification run, without a program guarantee "
                                 "or a claim that the workflow has succeeded."} for clause in manifest[3:]],
            "assumptions": [], "ambiguities": [], "selected_defaults": [],
            "category_review": {category: "Reviewed the supplied checker request; no additional requirement."
                                for category in agents.DRAFT_CATEGORIES}}
        policy = {"schema_version": "0.1", "format": source_policy.FORMAT,
                  "obligations": {oid: {"file": "program.vscore.json", "entry": "solve", "arity": 1,
                      "properties": ["typed_total", "deterministic", "input_preserved", "no_external_io",
                                     "no_floating_point", "pure_data", "restricted_runtime_only"],
                      "value_required": True} for oid in ids[:2]}}
        calls = []
        class AuthoredBroker:
            def call(self, agent, instance, system, user, purpose):
                calls.append({"system": system, "user": user, "purpose": purpose})
                return SimpleNamespace(text=canonical.dumps(proposal).decode("utf-8"),
                                       requested_model="authored-no-model", returned_model=None)
        with tempfile.TemporaryDirectory(prefix="authored-interpreter-context-") as temporary:
            root = Path(temporary)
            pkg = Package(root / "package")
            pkg.ensure("authored-interpreter-context")
            policy_path = root / "required-source-policy.json"
            policy_path.write_bytes(canonical.dumps(policy))
            source_policy.stage(pkg, policy_path)
            events = EventSink(pkg.run_id, pkg.root, quiet=True)
            self.addCleanup(events.close)
            with patch.object(agents, "_broker", return_value=(AuthoredBroker(), {"roles": {"interpreter": "author"}})):
                interpreted, ledger = agents.interpreter_agent("unused", pkg, events, attempts=1)(
                    prompt, "public-artifact-checker", {})
            self.assertEqual(1, len(calls))
            self.assertEqual("interpret", calls[0]["purpose"])
            self.assertEqual(agents.INTERPRETER_SYSTEM, calls[0]["system"])
            self.assertIn(prompt.decode("utf-8"), calls[0]["user"])
            supplied_policy = json.JSONDecoder().raw_decode(calls[0]["user"].split(
                "REQUIRED SOURCE FACETS (frozen specification constraint; not accepted IR or proof evidence):\n", 1
            )[1].lstrip())[0]
            self.assertEqual(policy, supplied_policy)
            captured = agent_memory.restore(pkg, agent_memory.latest_snapshot(pkg, stage_prefix="agent/interpret/input"))
            self.assertEqual(calls[0]["system"].encode("utf-8"), captured["system.txt"])
            self.assertEqual(calls[0]["user"].encode("utf-8"), captured["user.txt"])
            records = {rec["id"]: rec for rec in draft.obligations(interpreted)}
            self.assertEqual(set(ids), set(records))
            for oid, kind, role, clause in zip(ids, kinds, roles, manifest):
                rec = records[oid]
                self.assertEqual((kind, role, True), (rec["kind"], rec["role"], rec["required"]))
                self.assertEqual(clause["quote"], rec["statement"])
                source = rec["source_refs"][0]
                self.assertEqual(clause["quote"].encode("utf-8"), prompt[source["start_byte"]:source["end_byte"]])
            self.assertEqual([], draft.validate_draft(interpreted, prompt, "public-artifact-checker"))
            diagnostics, coverage = draft.validate_ledger(ledger, interpreted, prompt, "public-artifact-checker")
            self.assertEqual([], diagnostics)
            self.assertEqual([], coverage["uncovered_segments"])
            contexts = [row for row in ledger["clauses"] if row["disposition"] == "context"]
            self.assertEqual(2, len(contexts))
            self.assertTrue(all(row["note"] and not row["refs"] for row in contexts))
            contexts[0].pop("note")
            self.assertIn("INVALID_CANDIDATE", {d.code for d in draft.validate_ledger(
                ledger, interpreted, prompt, "public-artifact-checker")[0]})


if __name__ == "__main__":
    unittest.main()
