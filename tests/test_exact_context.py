"""Exact model-context engineering checks; no live model or success candidates."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from relation_authoring_fixture import mock_relation_authority

from verislop import agent_memory, agents, canonical, exact_context
from verislop.errors import Diagnostic, UsageError
from verislop.events import EventSink
from verislop.package import Package


class ExactContextTests(unittest.TestCase):
    def sample(self):
        shared = {"formula": {"tag": "forall", "sort": "Nat", "body": {"tag": "true"}},
                  "hash": "sha256:" + "abcdef0123456789" * 4}
        literal = ('é e\u0301 😀 中\x00\nEND EXACT STRING 0\nEXACT STRING 1 99 UTF8 BYTES\n' * 20)
        return {"first": shared, "again": copy.deepcopy(shared), "proof": literal,
                "proof_again": literal, "scalar_types": [True, 1, False, 0, None, ""],
                "unrelated_metadata": {"any": "unique diagnostic must survive"}}

    def test_exact_nested_values_and_literal_bytes_restore(self):
        original = self.sample()
        before = copy.deepcopy(original)
        document = exact_context.project_context(original)
        self.assertEqual(original, before)
        self.assertTrue(document["definitions"])
        self.assertTrue(document["strings"])
        message = exact_context.render_context(document)
        restored = exact_context.restore_prompt(message)
        self.assertEqual(original, restored)
        self.assertEqual(document, exact_context.parse_context(message))
        self.assertIs(type(restored["scalar_types"][0]), bool)
        self.assertIs(type(restored["scalar_types"][1]), int)
        restored["again"]["formula"]["sort"] = "changed"
        self.assertEqual("Nat", restored["first"]["formula"]["sort"])
        self.assertEqual(before, original)

    def test_reserved_marker_objects_are_literal_not_protocol(self):
        data = {"values": [{"$r": 0}, {"$r": True}, {"$text": "not an id"},
            {"$literal": {"$r": 3}}, {"$r": 1, "extra": "original"},
            {"$literal": [{"$text": 5}]}, {"$text": 1, "$r": 2}],
            "repeated": [{"$r": "literal reserved marker"}] * 4}
        projected = exact_context.project_context(data)
        self.assertEqual(data, exact_context.restore_prompt(exact_context.render_context(projected)))

    def test_canonical_projection_is_deterministic_and_array_order_is_preserved(self):
        a = {"b": ["z", "a", "z"], "a": self.sample()}
        b = {"a": self.sample(), "b": ["z", "a", "z"]}
        self.assertEqual(exact_context.render_context(exact_context.project_context(a)),
                         exact_context.render_context(exact_context.project_context(b)))
        self.assertEqual(["z", "a", "z"], exact_context.restore_context(exact_context.project_context(a))["b"])

    def test_corrupt_envelopes_and_reference_graphs_are_rejected(self):
        original = exact_context.project_context(self.sample())
        changes = [lambda d: d.update(extra=1), lambda d: d.update(format="future"),
            lambda d: d.update(original_sha256="sha256:stale"),
            lambda d: d.update(original_utf8_bytes=True),
            lambda d: d["definitions"].update({"unknown": {}}),
            lambda d: d.update(context={"$r": 9999}),
            lambda d: d.update(context={"$r": True}),
            lambda d: d.update(context={"$r": 0, "extra": 1}),
            lambda d: d["definitions"].update({"0": {"$r": 0}}),
            lambda d: d["strings"][0].update(text=d["strings"][0]["text"] + "changed"),
            lambda d: d["strings"][0].update(utf8_bytes=True),
            lambda d: d["strings"][0].update(sha256="sha256:stale")]
        for mutate in changes:
            document = copy.deepcopy(original)
            mutate(document)
            with self.subTest(document=document), self.assertRaises(ValueError):
                exact_context.restore_context(document)

    def test_byte_frames_reject_missing_truncated_changed_and_trailing_content(self):
        document = exact_context.project_context(self.sample())
        message = exact_context.render_context(document)
        bad = [message + "trailing", message[:-1], message.replace("EXACT STRING 0 ", "EXACT STRING 7 ", 1),
               message.split("EXACT STRING 0 ", 1)[0], message.replace("é e", "é X", 1)]
        for changed in bad:
            with self.subTest(changed=changed[-80:]), self.assertRaises(ValueError):
                exact_context.restore_prompt(changed)
        # A duplicated header member cannot be hidden by ordinary JSON parsing.
        line = message.splitlines()[1]
        changed = message.replace(line, line[:-1] + ',"format":"duplicate"}', 1)
        with self.assertRaises(ValueError):
            exact_context.restore_prompt(changed)

    def test_unknown_metadata_never_disappears_and_empty_context_is_valid(self):
        for data in ({}, {"diagnostics": {"unknown": ["", "😀", {"$text": 0}]}}, self.sample()):
            self.assertEqual(data, exact_context.restore_prompt(
                exact_context.render_context(exact_context.project_context(data))))


class ImplementationContextTests(unittest.TestCase):
    def run_rejected_sources(self, *, version):
        root = Path(self.tmp.name)
        pkg = Package(root / version)
        pkg.ensure("implementation-context-fixture")
        params = {"backend": "verislop.backend.vscore/" + version, "backend_version": version}
        fixed = {"parameters": params, "accepted_reference": {"lean_source": "-- exact reference\n" * 40},
                 "accepted_packages": {"unknown": {"must": "remain intact"}},
                 "accepted_profile": {}, "lean_toolchain": "fixture-pin"}
        before = copy.deepcopy(fixed)
        responses = [json.dumps({"program": {"language": "invalid", "specific_prior_entry": "retain exactly"},
                                 "relation": {}}), '{ malformed JSON with exact bytes\n"retained": true']
        events = EventSink(pkg.run_id, quiet=True)
        calls = []

        def completion(*args):
            calls.append({"system": args[4], "user": args[5]})
            return SimpleNamespace(text=responses[len(calls) - 1])
        try:
            with patch.object(agents, "_vscore_context", return_value=fixed), \
                    patch.object(agents, "recorded_call", side_effect=completion):
                with self.assertRaises(UsageError):
                    agents._vscore_implementation(None, {"roles": {"implementer": "fixture"}}, pkg, events,
                        {"parameters": params}, attempts=2, proof_attempts=0)
        finally:
            events.close()
        self.assertEqual(before, fixed)
        self.assertEqual(2, len(calls))
        return pkg, fixed, responses, calls

    def setUp(self):
        self.addCleanup(mock_relation_authority().close)
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-exact-context-test-")
        self.addCleanup(self.tmp.cleanup)

    def test_03_actual_dispatch_retains_fixed_contract_and_exact_rejected_source(self):
        pkg, fixed, responses, calls = self.run_rejected_sources(version="0.3")
        first, second = [exact_context.restore_prompt(call["user"]) for call in calls]
        self.assertEqual({"fixed_context": fixed, "previous_response": None, "previous_diagnostics": {},
                          "previous_diagnostic_record": None}, first)
        self.assertEqual(fixed, second["fixed_context"])
        self.assertEqual(responses[0], second["previous_response"])
        self.assertGreater(second["previous_diagnostics"]["error_count"], 0)
        self.assertEqual(second["previous_diagnostic_record"], canonical.load_file(
            pkg.root / second["previous_diagnostics"]["full_diagnostics"]["path"]))
        self.assertIn("SOURCE CORRECTION", calls[1]["system"])
        saved = agent_memory.latest_snapshot(pkg, stage_prefix="implementer/vscore/context/2")
        self.assertEqual(second, canonical.loads(agent_memory.restore(pkg, saved)["context.json"]))
        for number, response in enumerate(responses, 1):
            self.assertEqual(response, (pkg.root / f"agents/vscore-attempts/source-{number}/response.txt").read_text())

    def test_01_keeps_existing_request_protocol(self):
        pkg, fixed, _, calls = self.run_rejected_sources(version="0.1")
        prefix = "FIXED ACCEPTED CONTRACT AND TARGET (data):\n"
        self.assertEqual(fixed, json.loads(calls[0]["user"].removeprefix(prefix)))
        self.assertIn("CHECKER ERROR INVENTORY", calls[1]["user"])
        self.assertNotIn(exact_context.PREFIX, calls[0]["user"])
        self.assertIsNone(agent_memory.latest_snapshot(pkg, stage_prefix="implementer/vscore/context/"))

    def test_failed_bridge_proof_keeps_source_response_and_full_diagnostic_record_distinct(self):
        from tests.test_vscore3_workflow_unit import VSCore3WorkflowUnits
        from verislop.bridges import vscore3_checker
        fixture = VSCore3WorkflowUnits()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        source = fixture.source()
        source_response = json.dumps({"program": canonical.loads(source), "relation": fixture.relation})
        rejected_proof = "fixture distinct rejected bridge proof"
        responses = iter([source_response, rejected_proof, '{"program":{},"relation":{}}'])
        tail = "UNIQUE_REQUIRED_DIAGNOSTIC_TAIL_é_😀"
        diagnostic = Diagnostic("KERNEL_REJECTION", "x" * 500 + tail,
                                details={"unique_metadata": "METADATA_NOT_IN_MESSAGE"})

        def preview(_pkg, _source, _relation, proof=None, **kwargs):
            if proof is not None:
                raise vscore3_checker.EdgeFailure([diagnostic])
            return SimpleNamespace(text="fixture generated goal"), None, fixture.info

        with patch.object(agents, "_vscore_context", return_value=fixture.fixed_context()), \
                patch.object(agents, "_role", return_value="implementer"), \
                patch.object(agents, "recorded_call", side_effect=lambda *args: SimpleNamespace(text=next(responses))) as calls, \
                patch.object(vscore3_checker, "preview", side_effect=preview):
            files, _ = agents._vscore_implementation(None, {"roles": {"prover": "prover"}}, fixture.pkg,
                fixture.events, {"parameters": fixture.params}, attempts=2, proof_attempts=1)
        self.assertEqual(rejected_proof.encode(), files["Proof.lean"])
        self.assertEqual(3, calls.call_count)
        retry = exact_context.restore_prompt(calls.call_args_list[2].args[5])
        self.assertEqual(source_response, retry["previous_response"])
        self.assertNotEqual(rejected_proof, retry["previous_response"])
        record = retry["previous_diagnostic_record"]
        self.assertEqual(record, canonical.load_file(fixture.pkg.root /
            retry["previous_diagnostics"]["full_diagnostics"]["path"]))
        self.assertEqual(canonical.digest(rejected_proof.encode()), record["proof_hash"])
        self.assertIn(tail, record["diagnostics"][0]["message"])
        self.assertEqual("METADATA_NOT_IN_MESSAGE", record["diagnostics"][0]["details"]["unique_metadata"])
        self.assertNotIn(tail, retry["previous_diagnostics"]["errors"][0]["message_excerpt"])


if __name__ == "__main__":
    unittest.main()
