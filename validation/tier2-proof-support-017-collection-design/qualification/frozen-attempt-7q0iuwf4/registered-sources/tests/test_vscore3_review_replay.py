"""Fresh wrong-but-admitted source gets a concrete pinned-kernel review replay."""
from __future__ import annotations

import copy
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_source_pipeline import accepted_fixture, changed_bytes
from verislop import canonical, dsl, fsutil, generate, review, review_counterexamples as replay, schemas
from verislop.backends import registry
from verislop.events import EventSink
from verislop.exprjson import constants, loose_bvar_range
from verislop.targets import vscore3_replay as kernel, vscore3_source as source, vscore3_target as target


def wrong_program():
    var = {"tag": "var", "index": 0}
    def plus(n):
        return {"tag": "add", "left": var, "right": {"tag": "int", "value": str(n)}}
    return {"language": source.LANGUAGE, "profile": source.PROFILE, "declarations": [], "helpers": [],
        "entries": [{"id": "plus", "params": ["int"], "result": "int", "body": {
            "tag": "if", "cond": {"tag": "eq", "left": var, "right": {"tag": "int", "value": "0"}},
            "then": plus(2), "else": plus(3)}}]}


def relation():
    return {"schema_version": "0.3", "format": target.RELATION_FORMAT, "template": target.TEMPLATE,
        "source_slot": "vscore-source", "proof_slot": "vscore-proof", "bindings": [{"symbol": "plus", "entry": "plus"}]}


class ReplayConstructionTests(unittest.TestCase):
    def test_registered_review_budget_preserves_python_default_and_dispatches_exact_03(self):
        pkg = object()
        proposal = {"kind": "target_case", "obligation_id": "G2", "assignment": [{"int": "1"}]}
        for backend, budget in ((registry.VSCORE3_ID, 30), (registry.PYTHON_ID, None), (registry.VSCORE_ID, None)):
            with self.subTest(backend=backend), patch.object(registry, "frozen_backend", return_value=({"id": backend}, [])), \
                    patch.object(replay, "replay", return_value={}) as call:
                replay.replay_probe(pkg, "implementation", proposal)
                if budget is None:
                    call.assert_called_once_with(pkg, "implementation", proposal)
                else:
                    call.assert_called_once_with(pkg, "implementation", proposal, timeout_seconds=budget)

    def test_structured_grounding_keeps_calls_beneath_local_map_binders(self):
        from tests.test_vscore3_bridge import obligations, profile, program, relation as binder_relation
        spec = target.build_goal(canonical.dumps(program()), binder_relation(), profile(), obligations())
        grounded = kernel.ground(spec, obligations()["O2"]["formula"], [(1, -3)])
        names = constants(grounded)
        self.assertEqual(loose_bvar_range(grounded), 0)
        self.assertIn("VeriSlopBridgeGoal.source_fn_shift", names)
        self.assertNotIn("Fixture.shift", names)
        self.assertIn("List.map", names)

    def test_unbounded_residual_quantifiers_never_become_decidable_probes(self):
        formula = {"tag": "and", "left": {"tag": "true"}, "right": {
            "tag": "forall", "sort": "Int", "body": {"tag": "true"}}}
        with self.assertRaises(replay._ReplayUnsupported):
            replay._decidable(formula)


class VSCoreKernelReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="verislop-vscore3-review-")
        cls.root = Path(cls.tmp.name)
        cls.addClassCleanup(cls.cleanup)
        cls.pkg, cls.stages = accepted_fixture(cls.root)
        candidate = cls.root / "source-candidate"
        candidate.mkdir()
        fsutil.write_json(candidate / "program.vscore.json", wrong_program())
        fsutil.write_json(candidate / "relation.json", relation())
        # This proof is deliberately unusable. Source materialization and concrete
        # replay must not require a successful Refines proof or semantic acceptance.
        fsutil.atomic_write(candidate / "Proof.lean", b"import VeriSlopBridgeGoal\nnamespace VeriSlopBridgeProof\n"
            b"theorem edge : VeriSlopBridgeGoal.EdgeProp := by sorry\nend VeriSlopBridgeProof\n")
        events = EventSink(cls.pkg.run_id, quiet=True)
        try:
            result = generate.run(cls.pkg, events, candidate=candidate, tier=2, target="vscore", backend_version="0.3",
                                  endpoint="restricted_source", require_state="END_TO_END_VERIFIED", require_tests=False)
        finally:
            events.close()
        if result.status != "PASS":
            raise AssertionError([d.to_json() for d in result.diagnostics])
        cls.stages["generate"] = result.to_json()
        cls.receipts = []

    @classmethod
    def cleanup(cls):
        if cls.root.exists():
            fsutil.make_writable_tree(cls.root)
        cls.tmp.cleanup()

    def probe(self, assignment, oid="G2", *, timeout_seconds=30):
        proposal = {"kind": "target_case", "obligation_id": oid, "assignment": assignment}
        started = time.monotonic()
        result = replay.replay(self.pkg, "implementation", proposal, timeout_seconds=timeout_seconds)
        self.receipts.append({"receipt": result, "wall_seconds": format(time.monotonic() - started, ".6f")})
        self.assertEqual(schemas.validate("review-counterexample-receipt", result), [])
        return result

    def test_actual_wrong_valid_source_confirms_before_any_semantic_proof_acceptance(self):
        result = self.probe([{"int": "1"}])
        self.assertEqual(result["status"], "CONFIRMED", result)
        observed = result["observed"]
        self.assertFalse(observed["predicate"])
        self.assertTrue(observed["kernel_replay"])
        self.assertEqual(observed["result_theorem"], kernel.THEOREM)
        self.assertNotIn("sorryAx", observed["axioms"])
        self.assertIn(target.GOAL_MODULE, observed["modules"])
        self.assertNotIn(target.PROOF_MODULE, observed["modules"])
        self.assertIn("implementation/program.vscore.json", result["input_bindings"])
        self.assertIn("closure/selection.json", result["input_bindings"])
        self.assertEqual(result["claim"]["obligation_id"], "G2")
        self.assertEqual(result["expected"]["semantics"], target.SEMANTICS)
        self.assertFalse((self.pkg.path("bridges") / "implementation/semantic").exists())

    def test_matching_ground_case_is_not_reproduced(self):
        result = self.probe([{"int": "0"}])
        self.assertEqual(result["status"], "NOT_REPRODUCED", result)
        self.assertTrue(result["observed"]["predicate"])
        self.assertTrue(result["observed"]["kernel_replay"])

    def test_exhausted_explicit_deadline_leaves_the_probe_unresolved(self):
        result = self.probe([{"int": "1"}], timeout_seconds=0.001)
        self.assertEqual(result["status"], "UNSUPPORTED", result)
        self.assertTrue(any("deadline" in reason for reason in result["diagnostics"]))

    def test_source_only_and_wrong_sort_or_arity_are_unsupported(self):
        for oid, assignment in (("G1", []), ("G2", []), ("G2", [{"bool": True}]), ("unknown", [{"int": "1"}])):
            with self.subTest(oid=oid, assignment=assignment):
                self.assertEqual(self.probe(assignment, oid)["status"], "UNSUPPORTED")

    def test_changed_source_cannot_confirm_and_restoration_recovers_exact_binding(self):
        path = self.pkg.path("implementation") / "program.vscore.json"
        altered = copy.deepcopy(wrong_program())
        altered["entries"][0]["body"]["else"]["right"]["value"] = "20"
        with changed_bytes(path, canonical.dumps(altered)):
            self.assertEqual(self.probe([{"int": "1"}])["status"], "UNSUPPORTED")
        self.assertEqual(path.read_bytes(), canonical.dumps(wrong_program()))

    def test_reviewer_guidance_has_exact_value_binders_and_versioned_budget(self):
        policy = review._counterexample_policy(self.pkg, "implementation", ["G1", "G2"])
        self.assertEqual(policy["replay_limits"]["seconds_per_probe"], 30)
        self.assertIn("target_case", policy["proposals"])
        self.assertNotIn("source_violation", policy["proposals"])
        binders = policy["target_case_binders"]
        self.assertEqual(binders["serialization_profile"], "vscore3-kernel-assignment/0.1")
        self.assertEqual(binders["obligations"]["G1"]["status"], "unsupported")
        self.assertEqual(binders["obligations"]["G2"]["leading_universal_sorts"], ["Int"])
        self.assertEqual(binders["obligations"]["G2"]["status"], "supported")


if __name__ == "__main__":
    unittest.main()
