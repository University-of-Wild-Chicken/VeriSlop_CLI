"""The gate consumes actual emitted strict reports; authored mocks are not PoCs."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import EX, MockLLM, TempDir, mock_config, run_cli, unanimous
from test_providers_review import Behaviour, SECRET
from verislop import canonical, schemas
from synthetic_dataset.tools import check_data_pipeline_poc as checker


class ActualReportQualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.mock = MockLLM(Behaviour(), SECRET)
        try:
            config, env = mock_config(cls.tmp.path, cls.mock.port, [unanimous("R0", "critic", 1)],
                                      checkpoints=["formal_contract", "release"])
            code, result, error = run_cli("run", "--prompt-file", str(EX / "request.txt"),
                "--request-ref", "examples/request.txt", "--tier", "0", "--target", "python",
                "--endpoint", "test_campaign", "--require-state", "TESTED", "--require-tests",
                "--budget-seconds", "0", "--config", str(config), "--non-interactive",
                "--runs-dir", str(cls.tmp.path / "runs"), "--run-id", "authored-accounting-regression", env=env)
            if code != 0:
                raise AssertionError((code, result, error[-2000:]))
            cls.report = canonical.load_file(cls.tmp.path / "runs/authored-accounting-regression/report.json")
            if schemas.validate("report", cls.report):
                raise AssertionError(schemas.validate("report", cls.report))
        except BaseException:
            cls.mock.close()
            cls.tmp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.mock.close()
        cls.tmp.cleanup()

    def test_actual_emitted_strict_report_is_eligible(self):
        self.assertIs(type(self.report["tier"]), dict)
        self.assertEqual("VERIFIED", self.report["terminal_status"])
        self.assertTrue(checker.native_tested_gate(self.report))

    def test_wrong_missing_or_legacy_tier_scopes_cannot_qualify(self):
        for tier in (0, False, True, None, [], "0", {}, {"requested": 0}):
            with self.subTest(tier=tier):
                report = copy.deepcopy(self.report)
                report["tier"] = tier
                self.assertFalse(checker.native_tested_gate(report))
        for key, bad in (("requested", 1), ("requested", False), ("requested", None),
                         ("requested", 0.0), ("target", "vscore"), ("require_state", "PROVED"),
                         ("endpoint", "restricted_source"), ("requested_endpoint", None)):
            with self.subTest(key=key, bad=bad):
                report = copy.deepcopy(self.report)
                report["tier"][key] = bad
                self.assertFalse(checker.native_tested_gate(report))

    def test_existing_native_gates_remain_required(self):
        report = copy.deepcopy(self.report)
        report["terminal_status"] = "BLOCKED"
        self.assertFalse(checker.native_tested_gate(report))
        report = copy.deepcopy(self.report)
        report["builds"][0]["ok"] = False
        self.assertFalse(checker.native_tested_gate(report))
        report = copy.deepcopy(self.report)
        report["determinism"]["mismatches"] = ["changed output"]
        self.assertFalse(checker.native_tested_gate(report))
        report = copy.deepcopy(self.report)
        report["review"]["checkpoints"]["release"] = "REVIEW_INCOMPLETE"
        self.assertFalse(checker.native_tested_gate(report))
        report = copy.deepcopy(self.report)
        tested = next(row for row in report["obligations"].values() if row["required"] and "TESTED" in row["required_milestones"])
        tested["outcomes"]["TESTED"] = "FAIL"
        self.assertFalse(checker.native_tested_gate(report))
        report = copy.deepcopy(self.report)
        report["obligations"] = {}
        self.assertFalse(checker.native_tested_gate(report))


if __name__ == "__main__":
    unittest.main()
