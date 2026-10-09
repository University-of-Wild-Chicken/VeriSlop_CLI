"""Actual target-process evidence for source-bound native Tier 0 facets."""
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from verislop import canonical, dsl, native_testing, sandbox, testing
from verislop.targets.python_target import Harness


@unittest.skipUnless(sandbox.filesystem_isolation_available() and sandbox.network_isolation_available(),
                     "filesystem/network namespaces unavailable")
class NativeRuntime(unittest.TestCase):
    def harness(self, source):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "solution.py").write_text(source)
        harness = Harness(root, {"solution.py": canonical.digest_file(root / "solution.py")},
                          {"probe": ("solution.py", "solve")}, per_call_timeout=.1)
        self.addCleanup(harness.close)
        return harness

    def profile(self, args=None, result="Bool"):
        return dsl.Profile.from_json({"dsl": dsl.ENCODING_V2, "profile_id": "native-fixture", "enums": {},
            "records": {}, "predicates": {}, "symbols": {"probe": {"lean_decl": "Fixture.probe",
            "args": ["Bool"] if args is None else args, "result": result}}})

    def run_native(self, source, profile=None):
        profile = profile or self.profile()
        harness = self.harness(source)
        result = native_testing.execute([{"symbol": "probe"}], profile, {"obligations": {}}, {},
            harness, testing.campaign_config(91, 2, 100, profile), 19, {})
        return result, harness

    def test_native_only_requires_actual_repeated_calls_even_with_no_value_formula(self):
        result, harness = self.run_native("def solve(x):\n return x\n")
        self.assertEqual("PASS", result["outcome"], result)
        self.assertEqual(4, harness.calls)
        row = result["detail"]["native_runtime"]["probe"]
        self.assertEqual(2, row["counts"]["effective"])
        self.assertTrue(row["domain"]["exact_completion"])
        self.assertEqual(2, len(row["observation_hashes"]))

    def test_frame_is_observed_inside_process_for_nested_borrowed_write(self):
        harness = self.harness("def solve(x):\n x[0]['v'] = 8\n return True\n")
        encoded = [{"list": [{"dict": {"v": {"int": "7"}}}]}]
        response = harness.call("probe", encoded, observe=True)
        self.assertEqual(encoded, response["observation"]["before"]["values"])
        self.assertNotEqual(response["observation"]["before"], response["observation"]["after"])
        self.assertEqual(encoded, [{"list": [{"dict": {"v": {"int": "7"}}}]}], "host transport is unchanged")

    def test_runtime_rejects_actual_input_write(self):
        profile = self.profile([{"list": "Bool"}])
        result, _ = self.run_native("def solve(x):\n x.append(True)\n return True\n", profile)
        self.assertEqual("FAIL", result["outcome"], result)
        self.assertIn("TEST_FAILURE", result["codes"])
        self.assertIn("changed an input", str(result))

    def test_repeat_compares_actual_outcomes(self):
        result, _ = self.run_native("state = []\ndef solve(x):\n state.append(x)\n return len(state) % 2 == 0\n")
        self.assertEqual(["NONDETERMINISM"], result["codes"], result)

    def test_timeout_cannot_become_effective_or_reuse_channel(self):
        result, harness = self.run_native("def solve(x):\n while True:\n  pass\n")
        self.assertEqual("FAIL", result["outcome"], result)
        self.assertEqual(0, result["detail"]["counts"]["effective"])
        self.assertIn("TEST_INCOMPLETE", result["codes"])
        self.assertTrue(harness.closed)

    def test_modeled_failure_retains_frame_and_repeat_evidence(self):
        result, harness = self.run_native("def solve(x):\n raise ValueError('invalid')\n")
        self.assertEqual("PASS", result["outcome"], result)
        self.assertEqual(4, harness.calls)

    def test_non_json_output_is_concrete_failure(self):
        result, _ = self.run_native("def solve(x):\n return object()\n")
        self.assertIn("TEST_FAILURE", result["codes"], result)

    def preflight(self, bodies, profile=None):
        profile = profile or self.profile()
        harness = self.harness("def solve(x):\n return True\n")
        result = native_testing.execute([{"symbol": "probe"}], profile,
            {"accepted_environment_hash": "sha256:fixture", "obligations": {}}, {}, harness,
            testing.campaign_config(91, 2, 100, profile), 19, bodies)
        return result, harness

    def test_missing_reference_cannot_enter_target_or_become_counterexample(self):
        result, harness = self.preflight({})
        self.assertEqual(0, harness.calls)
        self.assertEqual(0, result["detail"]["counts"]["effective"])
        self.assertEqual(2, result["detail"]["counts"]["indeterminate"])
        self.assertIn("TEST_INCOMPLETE", result["codes"])
        self.assertNotIn("TEST_FAILURE", result["codes"])
        self.assertEqual([], result["detail"]["native_runtime"]["probe"]["counterexamples"])

    def test_reference_work_budget_selects_no_target_calls(self):
        profile = self.profile(result="Nat")
        bodies = {"probe": {"tag": "list_length", "value": {"tag": "list_range",
            "stop": {"tag": "nat", "value": "1000000000000"}}}}
        result, harness = self.preflight(bodies, profile)
        self.assertEqual(0, harness.calls)
        self.assertEqual(0, result["detail"]["counts"]["effective"])
        self.assertIn("TEST_INCOMPLETE", result["codes"])
        self.assertIn("list_range exceeds", str(result))

    def test_reference_result_is_discarded_and_actual_calls_supply_evidence(self):
        result, harness = self.preflight({"probe": {"tag": "bool", "value": False}})
        self.assertEqual("PASS", result["outcome"], result)
        self.assertEqual(4, harness.calls)
        receipt = result["detail"]["native_runtime"]["probe"]
        self.assertFalse(receipt["reference_preflight"]["reference_result_used_as_test_evidence"])
        self.assertEqual(2, receipt["counts"]["effective"])

    def test_pure_reference_fault_is_incomplete_without_software_counterexample(self):
        with patch.object(dsl.Evaluator, "term", side_effect=dsl.TargetFault("malformed", "reference fault")):
            result, harness = self.preflight({"probe": {"tag": "bool", "value": True}})
        self.assertEqual(0, harness.calls)
        self.assertEqual(0, result["detail"]["counts"]["failures"])
        self.assertIn("TEST_INCOMPLETE", result["codes"])
        self.assertEqual([], result["detail"]["native_runtime"]["probe"]["counterexamples"])


class NativeSampling(unittest.TestCase):
    def test_guards_must_be_common_and_target_free_and_hash_bound(self):
        profile = dsl.Profile.from_json({"dsl": dsl.ENCODING_V2, "profile_id": "guard-fixture", "enums": {},
            "records": {}, "predicates": {}, "symbols": {"probe": {"lean_decl": "Fixture.probe",
            "args": ["Nat"], "result": "Nat"}}})
        var = {"tag": "var", "index": 0}
        call = {"tag": "call", "symbol": "probe", "args": [var]}
        guard = {"tag": "gt", "left": var, "right": {"tag": "nat", "value": "0"}}
        formula = {"tag": "forall", "sort": "Nat", "body": {"tag": "implies", "left": guard,
            "right": {"tag": "eq", "left": call, "right": var}}}
        packages = {"O1": dsl.make_package(formula, profile.profile_id, encoding=profile.encoding)}
        ir = {"obligations": {"O1": {"required": True, "role": "guarantee"}}}
        plan = native_testing.sampling_plan("probe", profile, ir, packages)
        self.assertEqual([guard], plan["guards"])
        self.assertEqual(canonical.digest_json(packages["O1"]), plan["guard_sources"][0]["package"])
        packages["O2"] = dsl.make_package({"tag": "forall", "sort": "Nat", "body": formula["body"]["right"]},
                                           profile.profile_id, encoding=profile.encoding)
        ir["obligations"]["O2"] = ir["obligations"]["O1"]
        self.assertEqual([], native_testing.sampling_plan("probe", profile, ir, packages)["guards"])
