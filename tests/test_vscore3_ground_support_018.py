"""Finite controls for ground observation provenance and diagnostic transport."""
from __future__ import annotations

import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from verislop import canonical, dsl, review, review_counterexamples as supervisor
from verislop.exprjson import const, app
from verislop.targets import vscore3_replay as replay, vscore3_target as target


class GroundSupportControls(unittest.TestCase):
    def attempt(self, errors=None, timed_out=False):
        result = SimpleNamespace(errors=errors or [], ok=False, timed_out=timed_out,
            sorry_positions=[], process_evidence={"returncode": 1, "stdout": {"byte_count": 0, "sha256": canonical.digest(b"")},
                "stderr": {"byte_count": 0, "sha256": canonical.digest(b"")}})
        return replay._attempt(result, b"independent generic proof proposal", False, 1)

    def test_utf8_row_and_whole_wire_bounds(self):
        attempt = self.attempt(["🙂" * 300 for _ in range(10)])
        self.assertEqual(attempt["available_rows"], 10)
        self.assertEqual(attempt["retained_rows"], 8)
        self.assertEqual(attempt["available_utf8_bytes"], 12000)
        self.assertEqual(attempt["retained_utf8_bytes"], 4096)
        self.assertTrue(attempt["truncated"])
        self.assertTrue(all(attempt["row_truncated"]))
        for row in attempt["errors"]:
            self.assertEqual(len(row.encode()), 512)
            self.assertNotIn("�", row)
        self.assertLessEqual(len(canonical.dumps([attempt, attempt])), replay.DIAGNOSTIC_WIRE_BYTES)

    def test_escaped_control_rows_obey_encoded_wire_cap(self):
        first = self.attempt(["\x00" * 512] * 8)
        second = self.attempt(["\n\"\\" * 171] * 8)
        self.assertLessEqual(len(canonical.dumps([first, second])), replay.DIAGNOSTIC_WIRE_BYTES)
        self.assertEqual(first["available_rows"], 8)
        self.assertEqual(first["available_utf8_bytes"], 4096)
        self.assertTrue(first["truncated"])
        self.assertLess(first["retained_rows"], 8)
        self.assertIn("proof_attempts=", str(replay.Unsupported("unresolved", [first, second])))

    def test_failed_attempt_survives_real_supervisor_receipt_path(self):
        attempt = self.attempt(["failed to synthesize Decidable for an unrelated admitted residual"])
        failure = replay.Unsupported("closed residual unresolved", [attempt])
        reader = SimpleNamespace(close=lambda: None, recheck=lambda: None)
        inputs = SimpleNamespace(hashes={}, reader=reader)
        proposal = {"kind": "target_case", "obligation_id": "GENERIC", "assignment": [{"int": "-2"}]}
        with patch.object(supervisor, "_Inputs", return_value=inputs), \
             patch.object(supervisor, "bound_roots", return_value={}), \
             patch.object(supervisor, "_context_claims", return_value=({}, {})), \
             patch.object(supervisor, "_target", side_effect=failure):
            receipt = supervisor.replay(SimpleNamespace(), "release", proposal, timeout_seconds=30)
        self.assertEqual(receipt["status"], "UNSUPPORTED")
        self.assertIsNone(receipt["observed"])
        retained = canonical.loads(receipt["diagnostics"][0].split("; proof_attempts=", 1)[1].encode())
        self.assertEqual(retained, [attempt])

    def dependencies(self, name):
        spec = SimpleNamespace(obligations=[SimpleNamespace(lean_symbol="VeriSlopContract.guarantee")])
        rows = {
            replay.THEOREM: {"kind": "theorem", "type": const("True"), "value_constants": [["VeriSlopReviewProbe", "wrapper"]]},
            "VeriSlopReviewProbe.wrapper": {"kind": "theorem", "type": const("True"), "value_constants": [name.split(".")]},
            name: {"kind": "theorem", "type": const("True"), "value_constants": [["True", "intro"]]}}
        return spec, rows

    def test_guarantee_oracle_rejected_through_wrapper(self):
        spec, rows = self.dependencies("VeriSlopContract.guarantee")
        with self.assertRaisesRegex(replay.Unsupported, "guarantee oracle"):
            replay._proof_dependencies(spec, rows, replay.THEOREM, {target.CONTRACT_MODULE, replay.MODULE})

    def test_refinement_transfer_and_candidate_proof_oracles_rejected(self):
        names = [target.GOAL_MODULE + ".Refines_transform", target.GOAL_MODULE + ".transfer_GENERIC",
                 target.GOAL_MODULE + ".Transfer_GENERIC", target.GOAL_MODULE + ".edge_of_refines",
                 target.PROOF_MODULE + ".borrowedProof"]
        for name in names:
            with self.subTest(name=name):
                spec, rows = self.dependencies(name)
                with self.assertRaisesRegex(replay.Unsupported, "guarantee oracle"):
                    replay._proof_dependencies(spec, rows, replay.THEOREM, {target.GOAL_MODULE, replay.MODULE})

    def test_definition_wrapper_is_traversed(self):
        spec, rows = self.dependencies("VeriSlopContract.guarantee")
        rows["VeriSlopReviewProbe.wrapper"] = {"kind": "definition", "type": const("True"),
            "value": const("VeriSlopContract.guarantee")}
        with self.assertRaises(replay.Unsupported):
            replay._proof_dependencies(spec, rows, replay.THEOREM, {target.CONTRACT_MODULE, replay.MODULE})

    def test_flat_quoted_oracle_leaf_uses_exact_name_components(self):
        from verislop.exprjson import name_str
        spec = SimpleNamespace(obligations=[SimpleNamespace(lean_symbol="VeriSlopContract.guarantee")])
        for leaf in ("Transfer_G.filter", "Refines_G-keep", "transfer_G:normal"):
            name = name_str([target.GOAL_MODULE, leaf])
            rows = {replay.THEOREM: {"kind": "theorem", "type": const("True"),
                    "value_constants": [[target.GOAL_MODULE, leaf]]},
                    name: {"kind": "theorem", "type": const("True"), "value_constants": [["True", "intro"]]}}
            with self.subTest(leaf=leaf), self.assertRaises(replay.Unsupported):
                replay._proof_dependencies(spec, rows, replay.THEOREM, {target.GOAL_MODULE, replay.MODULE})

    def test_missing_staged_dependency_rejected(self):
        spec, rows = self.dependencies("VeriSlopReviewProbe.missing")
        rows.pop("VeriSlopReviewProbe.missing")
        with self.assertRaisesRegex(replay.Unsupported, "staged declaration export"):
            replay._proof_dependencies(spec, rows, replay.THEOREM, {replay.MODULE})

    def test_pinned_toolchain_leaf_recorded_without_oracle(self):
        spec, rows = self.dependencies("True.intro")
        rows.pop("True.intro")
        audit = replay._proof_dependencies(spec, rows, replay.THEOREM, {replay.MODULE})
        self.assertIn("True.intro", audit["precontract_leaves"])
        self.assertEqual(audit["forbidden_dependencies"], [])

    def test_unbounded_residual_is_still_rejected(self):
        formula = {"tag": "forall", "sort": "Int", "body": {"tag": "true"}}
        with self.assertRaisesRegex(supervisor._ReplayUnsupported, "unbounded residual"):
            supervisor._decidable(formula)

    def test_assignment_arity_stays_strict(self):
        formula = {"tag": "forall", "sort": "Int", "body": {"tag": "true"}}
        with self.assertRaisesRegex(replay.Unsupported, "assignment arity"):
            replay.ground(SimpleNamespace(), formula, [1, 2])

    def test_wrong_wire_sort_rejected(self):
        profile = dsl.Profile.from_json({"profile_id": "unrelated-control", "dsl": dsl.ENCODING_V2})
        with self.assertRaises((supervisor._ReplayUnsupported, dsl.DSLError, ValueError)):
            supervisor._decode({"str": "x"}, "Int", profile)

    def test_closed_record_shape_rejected(self):
        profile = dsl.Profile.from_json({"profile_id": "unrelated-control", "dsl": dsl.ENCODING_V2,
            "records": {"Box": {"fields": [{"name": "item", "sort": "Int"}]}}})
        for value, sort in [({"dict": {}}, {"record": "Box"}),
                            ({"dict": {"item": {"int": "2"}, "extra": {"int": "3"}}}, {"record": "Box"})]:
            with self.subTest(value=value):
                with self.assertRaises((supervisor._ReplayUnsupported, dsl.DSLError, ValueError)):
                    supervisor._decode(value, sort, profile)

    def test_deadline_exhaustion_remains_unresolved(self):
        with self.assertRaises(dsl.BudgetExceeded):
            replay.remaining(time.monotonic() - 1)
        attempt = self.attempt(["elaboration timed out"], timed_out=True)
        failure = replay.Unsupported("ground proof exceeded the replay deadline", [attempt])
        self.assertIn('"timed_out":true', str(failure))

    def test_unsupported_probe_keeps_unanimity_incomplete(self):
        ballot = {"reported_verdict": "ACCEPT", "verdict": "ACCEPT", "findings": []}
        review._apply_replay_results(ballot, [{"status": "UNSUPPORTED"}], ["GENERIC"])
        self.assertEqual(ballot["verdict"], "ABSTAIN")
        tally = review.tally_tier({"consensus": {"mode": "unanimous"}}, ["slot"], {"slot": ballot}, [])
        self.assertEqual(tally["result"], "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
