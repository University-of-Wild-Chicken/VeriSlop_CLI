import copy
import json
from pathlib import Path
import tempfile
import unittest

from synthetic_dataset.tools.compare_runs import (
    ARMS, GATES, AuditFailure, active_package, audit_cases, audit_usage, digest,
    encode, exact, inside, inventory, markdown, metrics, paired_ids,
    paired_outcomes, render_viewer, strict_success,
)


class ComparisonTests(unittest.TestCase):
    def test_exact_json_keeps_boolean_and_large_integer_distinctions(self):
        self.assertFalse(exact(True, 1))
        self.assertFalse(exact(2**128, 2**128 + 1))
        self.assertTrue(exact({"a": 2**128, "b": None}, {"b": None, "a": 2**128}))

    def test_grades_recomputed_from_observation(self):
        cases = [{"id": "X-public", "visibility": "public", "expected": True},
                 {"id": "X-hidden", "visibility": "hidden", "expected": 2**128}]
        row = {"task_id": "X", "public_results": [{"id": "X-public", "observed": 1, "status": "FAIL"}],
               "held_out_results": [{"id": "X-hidden", "observed": 2**128, "status": "PASS"}],
               "public_passed": 0, "public_total": 1, "hidden_passed": 1, "hidden_total": 1}
        self.assertFalse(audit_cases(row, cases))
        row["public_results"][0]["status"] = "PASS"
        with self.assertRaises(AuditFailure):
            audit_cases(row, cases)

    def test_repaired_package_selected_and_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "arm"
            directory.mkdir()
            self.assertEqual(active_package(directory, {"summary": {"active_package": "package-repair-02"}}), directory / "package-repair-02")
            for path in ("../package", "package-copy", "/tmp/package"):
                with self.assertRaises(AuditFailure):
                    active_package(directory, {"summary": {"active_package": path}})

    def test_strict_gate_requires_proved_linked_tested_active_report(self):
        pipeline = {"status": "PASS"}
        stages = [{"stage": gate, "status": "PASS"} for gate in GATES]
        report = {"terminal_status": "VERIFIED", "tier": {"requested": 0, "target": "python", "endpoint": "test_campaign", "require_state": "TESTED"},
                  "obligations": {"O1": {"required": True, "required_milestones": ["PROVED", "TESTED"], "outcomes": {"PROVED": "PASS", "TESTED": "PASS"}}}}
        self.assertTrue(strict_success(pipeline, report, 0, stages))
        for field in ("PROVED", "TESTED"):
            defective = copy.deepcopy(report)
            defective["obligations"]["O1"]["outcomes"][field] = "BLOCKED"
            self.assertFalse(strict_success(pipeline, defective, 0, stages))
        self.assertFalse(strict_success(pipeline, report, 0, stages[:-1]))
        self.assertFalse(strict_success(pipeline, report, 2, stages))
        self.assertFalse(strict_success(pipeline, report, 0, stages, True))

    def test_inventory_rejects_missing_changed_and_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a").write_bytes(b"a")
            self.assertEqual(inventory(root, {"a": digest(b"a")}, "test"), 1)
            with self.assertRaises(AuditFailure):
                inventory(root, {"a": digest(b"b")}, "test")
            with self.assertRaises(AuditFailure):
                inside(root, "../a")
            (root / "linked").symlink_to(root / "a")
            with self.assertRaises(AuditFailure):
                inside(root, "linked")

    def test_pairs_do_not_count_unfinished_tasks(self):
        rows = [{"task_id": "A", "arm": "raw", "successful_task": True},
                {"task_id": "A", "arm": "verislop", "successful_task": False},
                {"task_id": "B", "arm": "raw", "successful_task": True}]
        self.assertEqual(paired_ids(rows), {"A"})
        self.assertEqual(paired_outcomes(rows), {"both_success": 0, "raw_only": 1, "verislop_only": 0, "neither_success": 0})

    def test_simulated_tokens_remain_unknown(self):
        row = {"task_id": "A", "arm": "raw", "successful_task": True, "artifact_present": True,
               "hidden_passed": 1, "hidden_total": 1, "public_passed": 1, "public_total": 1,
               "generation_seconds": 1, "usage": {"calls": 1, "input_tokens": None, "output_tokens": None},
               "workflow_status": "ARTIFACT", "last_model_purpose": "raw-coding"}
        self.assertIsNone(metrics([row])["raw"]["output_tokens"])

    def test_disconnected_native_call_does_not_hide_unknown_usage(self):
        row = {"arm": "verislop", "successful_task": False, "artifact_present": False,
               "hidden_passed": 0, "hidden_total": 1, "public_passed": 0, "public_total": 1,
               "generation_seconds": 1, "usage": {"calls": 2, "responses": 1,
               "input_tokens": 100, "output_tokens": 20, "unknown_usage_calls": 1},
               "workflow_status": "INFRASTRUCTURE_FAILURE", "last_model_purpose": "formalize"}
        result = metrics([row])["verislop"]
        self.assertEqual(result["unknown_usage_calls"], 1)
        self.assertEqual(result["output_tokens"], 20)

    def test_viewer_embeds_payload_without_script_injection(self):
        template = '<script id="benchmark-data" type="application/json">{}</script>'
        document = {"text": "</script>", "integer": 2**128}
        rendered = render_viewer(template, document)
        self.assertEqual(rendered.count("</script>"), 1)
        self.assertIn(str(2**128), rendered)
        payload = rendered.split(">", 1)[1].rsplit("</script>", 1)[0]
        self.assertEqual(json.loads(payload), document)

    def test_native_alignment_control_independently_qualifies(self):
        root = Path(__file__).resolve().parents[1]
        package = root / ".verislop/alignment/native-qwen/runs/difference-v6"
        if not (package / "report.json").exists():
            self.skipTest("Native alignment evidence is not present in this checkout")
        output = root / ".verislop/alignment/native-qwen/difference-v6-console.log"
        pipeline = json.loads(output.read_bytes())
        report = json.loads((package / "report.json").read_bytes())
        self.assertTrue(strict_success(pipeline, report, 0, pipeline["summary"]["stages"]))


if __name__ == "__main__":
    unittest.main()
