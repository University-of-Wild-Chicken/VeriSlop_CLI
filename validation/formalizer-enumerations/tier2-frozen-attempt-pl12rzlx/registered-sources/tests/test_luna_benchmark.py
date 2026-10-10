"""Independent scoring and evidence regressions for the agent-mediated experiment."""
from __future__ import annotations

import json
import signal
import subprocess
import sys
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from synthetic_dataset.build_dataset import ROOT, digest, encode
from synthetic_dataset.tools import luna_benchmark as bench
from synthetic_dataset.tools import luna_worker as worker


class LunaBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="verislop-luna-benchmark-test-")
        self.addCleanup(self.temporary.cleanup)
        self.out = Path(self.temporary.name)
        self.manifest = {"tasks": 100, "dataset_root": "sha256:fixture"}
        self.protocol = {"task_order": ["G03"], "source_hashes": {}, "harness_calls": 32}

    def row(self, task="G03", arm="raw", success=True):
        return {"task_id": task, "arm": arm, "category": "graph_algorithms",
                "successful_task": success, "artifact_present": True,
                "hidden_passed": 8 if success else 7, "hidden_total": 8,
                "public_passed": 2, "public_total": 2,
                "workflow_status": "ARTIFACT" if arm == "raw" else "PASS",
                "last_model_purpose": "raw-coding" if arm == "raw" else "review",
                "generation_seconds": 1.25,
                "artifact_path": f"artifacts/{task}/{arm}",
                "usage": {"calls": 1, "responses": 1, "output_bytes": 4,
                          "input_tokens": None, "output_tokens": None,
                          "unknown_usage_calls": 1}}

    def pending(self, task="G03", arm="raw"):
        directory = self.out / f"artifacts/{task}/{arm}"
        worker.atomic_json(self.out / "active-arm.json", {
            "phase": "generation", "task_id": task, "arm": arm,
            "artifact_path": directory.relative_to(self.out).as_posix()})
        path = directory / "request-0001.json"
        request = {"request_id": "0001", "requested_model": worker.MODEL,
                   "transport": "collaboration", "system": "Exact system", "user": "Exact user"}
        worker.atomic_json(path, request)
        envelope = {"request_id": "0001", "request_sha256": digest(path.read_bytes()),
                    "requested_model": worker.MODEL, "transport": "collaboration",
                    "agent_task_id": "/root/fresh_luna_fixture", "text": "exact é final\n",
                    "model_override": worker.MODEL, "fork_turns": "none",
                    "spawn_message_sha256": digest(bench.agent_message(request).encode("utf-8"))}
        return directory, path, envelope

    def evidence(self, task="G03", arm="raw", agent_id="/root/fresh_luna_fixture"):
        directory, request_path, envelope = self.pending(task, arm)
        envelope["agent_task_id"] = agent_id
        response_path = directory / "response-0001.json"
        worker.atomic_json(response_path, envelope)
        text_bytes = envelope["text"].encode("utf-8")
        worker.atomic_json(directory / "response-receipt-0001.json", {
            "request_id": "0001", "request_sha256": digest(request_path.read_bytes()),
            "response_sha256": digest(response_path.read_bytes()),
            "text_sha256": digest(text_bytes), "output_bytes": len(text_bytes),
            "agent_task_id": agent_id, "requested_model": worker.MODEL,
            "returned_model": None, "input_tokens": None, "output_tokens": None,
            "model_identity_attested": False})
        row = self.row(task, arm)
        row["usage"]["output_bytes"] = len(text_bytes)
        configuration = worker.configuration()
        worker.atomic_json(self.out / "config.json", configuration)
        self.protocol["config_hash"] = digest(encode(configuration))
        profiles = self.out / "provider-home/endpoint-profiles.json"
        worker.atomic_json(profiles, worker.endpoint_profiles())
        self.protocol["endpoint_profiles_hash"] = digest(profiles.read_bytes())
        return row, response_path

    def audit(self, rows):
        worker.atomic_json(self.out / "protocol.json", self.protocol)
        with patch.object(bench, "verify_dataset", return_value=self.manifest), \
                patch.object(bench, "score_integrity_errors", return_value=[]):
            return bench.audit(self.out, self.manifest, self.protocol, rows)

    def scored_row(self, arm="raw", missing=False):
        task = next(json.loads(line) for line in (ROOT / "tasks.jsonl").read_text().splitlines()
                    if json.loads(line)["id"] == "G03")
        cases = json.loads((ROOT / task["cases_path"]).read_bytes())
        scores = [{"id": c["id"], "status": "FAIL", "reason": "missing unambiguous solve(data) artifact"}
                  if missing else {"id": c["id"], "status": "PASS", "expected": c["expected"],
                                   "observed": c["expected"]} for c in cases]
        row = self.row(arm=arm, success=not missing)
        row.update(title=task["title"], category=task["category"],
                   artifact_present=not missing, entry_file=None if missing else "solution.py",
                   artifact_error=None, source_hashes={}, worker_exit_code=0, timed_out=False,
                   held_out_results=[s for s, c in zip(scores, cases) if c["visibility"] == "hidden"],
                   public_results=[s for s, c in zip(scores, cases) if c["visibility"] == "public"])
        row["hidden_total"] = len(row["held_out_results"])
        row["public_total"] = len(row["public_results"])
        row["hidden_passed"] = 0 if missing else row["hidden_total"]
        row["public_passed"] = 0 if missing else row["public_total"]
        directory = self.out / row["artifact_path"]
        if missing:
            row["workflow_status"] = "ERROR" if arm == "raw" else "BLOCKED"
        else:
            candidate = directory / ("artifact" if arm == "raw" else "package/implementation") / "solution.py"
            candidate.parent.mkdir(parents=True)
            source = b"def solve(data): return data\n"
            candidate.write_bytes(source)
            row["source_hashes"] = {"solution.py": digest(source)}
        self.save_score(row)
        return row

    def save_score(self, row):
        directory = self.out / row["artifact_path"]
        if row["arm"] == "verislop":
            row.setdefault("active_package", str((directory / "package").relative_to(self.out)))
            row.setdefault("cli_report", row["active_package"] + "/report.json")
            row.setdefault("strict_cli_success", row["workflow_status"] == "PASS")
            task = next(json.loads(line) for line in (ROOT / "tasks.jsonl").read_text().splitlines()
                        if json.loads(line)["id"] == row["task_id"])
            worker.atomic_json(directory / "cli-invocation.json", {
                "argv": worker.cli_argv(ROOT / task["prompt_path"], directory, self.out / "config.json")})
            stages = self.strict_stages(row["workflow_status"])
            worker.atomic_json(self.out / row["cli_report"], self.strict_report(row["workflow_status"]))
            (directory / "stdout.txt").write_bytes(encode({"status": row["workflow_status"], "summary": {
                "active_package": str((self.out / row["active_package"]).resolve()), "stages": stages}}))
        worker.atomic_json(directory / "score.json", row)

    @staticmethod
    def strict_stages(status="PASS"):
        return [{"stage": gate, "status": status} for gate in (
            "formalize", "prove", "accept", "export", "review:formal_contract",
            "generate", "link", "test", "review:release")]

    @staticmethod
    def strict_report(status="PASS"):
        return {"terminal_status": "VERIFIED" if status == "PASS" else "BLOCKED",
                "tier": {"requested": 0, "target": "python", "endpoint": "test_campaign", "require_state": "TESTED"},
                "blocking_reasons": [], "infrastructure_errors": [],
                "obligations": {"O1": {"required": True, "required_milestones": ["TESTED"],
                                        "outcomes": {"TESTED": status}}}}

    def test_nullable_token_metrics_remain_unknown_and_selected_pairs_complete(self):
        rows = [self.row()]
        summary = bench.summarize(rows, self.manifest, self.protocol)
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["complete_pairs"], 0)
        rows.append(self.row(arm="verislop", success=False))
        summary = bench.summarize(rows, self.manifest, self.protocol)
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["selected_tasks"], 1)
        self.assertEqual(summary["paired"]["raw_only"], 1)
        for arm in summary["arms"].values():
            self.assertIsNone(arm["input_tokens"])
            self.assertIsNone(arm["output_tokens"])
            self.assertFalse(arm["token_usage_available"])
            self.assertEqual(arm["unknown_usage_calls"], arm["model_calls"])

    def test_duplicate_task_arm_score_is_rejected(self):
        with self.assertRaises(ValueError):
            bench.summarize([self.row(), self.row()], self.manifest, self.protocol)

    def test_unselected_task_cannot_satisfy_selected_completion(self):
        with self.assertRaises(ValueError):
            bench.summarize([self.row("A01"), self.row("A01", "verislop")], self.manifest, self.protocol)

    def test_unknown_arm_and_duplicate_selected_task_are_rejected(self):
        with self.assertRaises(ValueError):
            bench.summarize([self.row(arm="unexpected")], self.manifest, self.protocol)
        with self.assertRaises(ValueError):
            bench.summarize([], self.manifest, {**self.protocol, "task_order": ["G03", "G03"]})

    def test_publish_preserves_exact_final_and_binds_model_context_and_request(self):
        directory, path, envelope = self.pending()
        result = bench.publish_response(self.out, envelope)
        self.assertEqual(result["output_bytes"], len(envelope["text"].encode("utf-8")))
        saved = json.loads((directory / "response-0001.json").read_bytes())
        self.assertEqual(saved["text"], envelope["text"])
        self.assertEqual(saved["request_sha256"], digest(path.read_bytes()))
        self.assertIsNone(bench.pending_request(self.out))
        with self.assertRaises(ValueError):
            bench.publish_response(self.out, envelope)

    def test_publish_rejects_wrong_or_missing_binding_and_model_context(self):
        directory, _, envelope = self.pending()
        for key, value in (("request_id", "0002"), ("request_sha256", "sha256:wrong"),
                           ("requested_model", "wrong-model"), ("model_override", "wrong-model"),
                           ("fork_turns", "all"), ("spawn_message_sha256", "sha256:wrong")):
            with self.subTest(key=key):
                with self.assertRaises(Exception):
                    bench.publish_response(self.out, {**envelope, key: value})
                self.assertFalse((directory / "response-0001.json").exists())
        for key in ("request_id", "request_sha256"):
            with self.subTest(missing=key):
                unbound = {k: v for k, v in envelope.items() if k != key}
                with self.assertRaises(Exception):
                    bench.publish_response(self.out, unbound)

    def test_fresh_agent_reuse_is_rejected_across_tasks_and_arms(self):
        previous = self.out / "artifacts/A01/verislop/response-receipt-0001.json"
        worker.atomic_json(previous, {"agent_task_id": "/root/fresh_luna_fixture"})
        directory, _, envelope = self.pending()
        with self.assertRaises(ValueError):
            bench.publish_response(self.out, envelope)
        self.assertFalse((directory / "response-0001.json").exists())

    def test_blocked_cli_is_unsuccessful_even_when_every_candidate_case_passes(self):
        task = json.loads((ROOT / "tasks.jsonl").read_text().splitlines()[0])
        cases = json.loads((ROOT / task["cases_path"]).read_bytes())
        scores = [{"id": c["id"], "status": "PASS", "expected": c["expected"],
                   "observed": c["expected"]} for c in cases]
        process = SimpleNamespace(returncode=0, communicate=Mock(return_value=(b'{"status":"BLOCKED"}', b"")))
        args = SimpleNamespace(harness_calls=32, case_seconds=1)
        with patch.object(bench.subprocess, "Popen", return_value=process), \
                patch.object(bench, "artifact_files", return_value=({"solution.py": b"def solve(data): return data\n"}, "solution.py")), \
                patch.object(bench, "grade", return_value=(scores, {"network_namespace": True})):
            row = bench.run_arm(task, "verislop", 0, self.out, args)
        process.communicate.assert_called_once_with()
        self.assertEqual(row["hidden_passed"], row["hidden_total"])
        self.assertEqual(row["public_passed"], row["public_total"])
        self.assertFalse(row["successful_task"])
        self.assertEqual(row["workflow_status"], "BLOCKED")
        self.assertFalse(row["timed_out"])

    def test_recovered_package_is_scored_instead_of_failed_parent(self):
        task = json.loads((ROOT / "tasks.jsonl").read_text().splitlines()[0])
        cases = json.loads((ROOT / task["cases_path"]).read_bytes())
        scores = [{"id": c["id"], "status": "PASS", "expected": c["expected"],
                   "observed": c["expected"]} for c in cases]
        directory = self.out / "artifacts" / task["id"] / "verislop"
        child = directory / "package-repair-01"
        source = b"def solve(data): return data\n"
        recovery = {"consumed_rounds": 1, "max_rounds": 2}
        pipeline = {"status": "PASS", "summary": {"active_package": str(child),
                    "stages": self.strict_stages(), "recovery": recovery}}

        def completed_worker(*_args, **_kwargs):
            worker.atomic_json(directory / "package/report.json", self.strict_report("BLOCKED"))
            parent_code = directory / "package/implementation/solution.py"
            parent_code.parent.mkdir()
            parent_code.write_bytes(b"def solve(data): return None\n")
            worker.atomic_json(child / "report.json", self.strict_report())
            candidate = child / "implementation/solution.py"
            candidate.parent.mkdir()
            candidate.write_bytes(source)
            worker.atomic_json(directory / "cli-invocation.json", {
                "argv": worker.cli_argv(ROOT / task["prompt_path"], directory, self.out / "config.json")})
            return SimpleNamespace(returncode=0, communicate=Mock(return_value=(encode(pipeline), b"")))

        args = SimpleNamespace(harness_calls=32, case_seconds=1)
        with patch.object(bench.subprocess, "Popen", side_effect=completed_worker), \
                patch.object(bench, "grade", return_value=(scores, {})):
            row = bench.run_arm(task, "verislop", 0, self.out, args)
        self.assertTrue(row["successful_task"])
        self.assertTrue(row["strict_cli_success"])
        self.assertEqual(row["active_package"], str(child.relative_to(self.out)))
        self.assertEqual(row["cli_report"], str((child / "report.json").relative_to(self.out)))
        self.assertEqual(row["source_hashes"], {"solution.py": digest(source)})
        self.assertEqual(row["recovery"], recovery)
        self.assertEqual(bench.score_integrity_errors(row, self.out), [])

    def test_pipeline_pass_without_required_report_is_not_a_success(self):
        task = json.loads((ROOT / "tasks.jsonl").read_text().splitlines()[0])
        cases = json.loads((ROOT / task["cases_path"]).read_bytes())
        scores = [{"id": c["id"], "status": "PASS", "expected": c["expected"],
                   "observed": c["expected"]} for c in cases]
        pipeline = {"status": "PASS", "summary": {"stages": self.strict_stages()}}
        process = SimpleNamespace(returncode=0, communicate=Mock(return_value=(encode(pipeline), b"")))
        args = SimpleNamespace(harness_calls=32, case_seconds=1)
        with patch.object(bench.subprocess, "Popen", return_value=process), \
                patch.object(bench, "artifact_files", return_value=({"solution.py": b"def solve(data): return data\n"}, "solution.py")), \
                patch.object(bench, "grade", return_value=(scores, {})):
            row = bench.run_arm(task, "verislop", 0, self.out, args)
        self.assertEqual(row["workflow_status"], "PASS")
        self.assertFalse(row["strict_cli_success"])
        self.assertFalse(row["successful_task"])

    def test_driver_stop_preserves_partial_manifest_without_unfinished_score(self):
        out = self.out / "stopped-run"
        with patch.object(bench, "run_arm", side_effect=KeyboardInterrupt("user stop")), \
                patch.object(bench, "source_inventory", return_value={}), \
                patch("verislop.verifiers.host_environment", return_value={}), \
                patch("verislop.verifiers.registry_snapshot", return_value={}):
            status = bench.main(["--out", str(out), "--limit", "1"])
        self.assertEqual(status, 130)
        summary = json.loads((out / "summary.json").read_bytes())
        manifest = json.loads((out / "run-manifest.json").read_bytes())
        self.assertEqual(summary["status"], "USER_STOPPED")
        self.assertEqual(summary["complete_pairs"], 0)
        self.assertFalse(summary["complete"])
        self.assertFalse(manifest["complete"])
        self.assertFalse((out / "results.jsonl").exists())
        for rel, expected in manifest["files"].items():
            self.assertEqual(digest((out / rel).read_bytes()), expected)

    def test_interrupted_arm_cancels_worker_without_fabricating_score(self):
        task = json.loads((ROOT / "tasks.jsonl").read_text().splitlines()[0])
        process = SimpleNamespace(communicate=Mock(side_effect=KeyboardInterrupt("user stop")))
        args = SimpleNamespace(harness_calls=32, case_seconds=1)
        with patch.object(bench.subprocess, "Popen", return_value=process) as spawned, \
                patch.object(bench, "stop_worker", return_value=(b"retained stdout", b"retained stderr")) as stopped, \
                patch.object(bench, "grade") as graded:
            with self.assertRaises(KeyboardInterrupt):
                bench.run_arm(task, "verislop", 0, self.out, args)
        stopped.assert_called_once_with(process)
        graded.assert_not_called()
        self.assertTrue(spawned.call_args.kwargs["start_new_session"])
        directory = self.out / "artifacts" / task["id"] / "verislop"
        self.assertEqual((directory / "stdout.txt").read_bytes(), b"retained stdout")
        self.assertEqual((directory / "stderr.txt").read_bytes(), b"retained stderr")
        self.assertFalse((directory / "score.json").exists())

    def test_stop_worker_cancels_and_reaps_real_child_session(self):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        self.addCleanup(lambda: proc.kill() if proc.poll() is None else None)
        self.assertEqual(bench.stop_worker(proc), (b"", b""))
        self.assertEqual(proc.returncode, -signal.SIGTERM)

    def test_cleanup_deadline_only_escalates_an_explicit_cancellation(self):
        proc = SimpleNamespace(pid=17, communicate=Mock(side_effect=[
            subprocess.TimeoutExpired("fixture", 5), (b"out", b"err")]))
        with patch.object(bench.os, "killpg") as killed:
            self.assertEqual(bench.stop_worker(proc), (b"out", b"err"))
        self.assertEqual(killed.call_args_list[0].args, (17, signal.SIGTERM))
        self.assertEqual(killed.call_args_list[1].args, (17, signal.SIGKILL))
        self.assertEqual(proc.communicate.call_args_list[0].kwargs, {"timeout": 5})
        self.assertEqual(proc.communicate.call_args_list[1].kwargs, {})

    def test_audit_accepts_honest_bound_evidence_and_rejects_changed_captured_bytes(self):
        row, response_path = self.evidence()
        result = self.audit([row])
        self.assertTrue(result["valid"])
        self.assertEqual(result["fresh_agents"], 1)
        self.assertFalse(result["provider_model_identity_attested"])
        response_path.write_bytes(response_path.read_bytes() + b"\n")
        result = self.audit([row])
        self.assertFalse(result["valid"])
        self.assertTrue(any("receipt does not match exact response bytes" in e for e in result["response_integrity_errors"]))

    def test_audit_rejects_invented_tokens_and_reused_agent_ids(self):
        first, _ = self.evidence()
        second, _ = self.evidence(arm="verislop")
        second["usage"]["output_tokens"] = 20
        result = self.audit([first, second])
        self.assertFalse(result["valid"])
        errors = result["response_integrity_errors"]
        self.assertTrue(any("agent reused" in e for e in errors))
        self.assertTrue(any("invented token usage" in e for e in errors))

    def test_audit_rejects_changed_execution_source_snapshot(self):
        row, _ = self.evidence()
        repo = self.out / "fixture-repo"
        repo.mkdir()
        source = repo / "driver.py"
        source.write_text("original source\n")
        self.protocol["source_hashes"] = {"driver.py": digest(source.read_bytes())}
        snapshot = self.out / "execution-source/driver.py"
        snapshot.parent.mkdir()
        snapshot.write_text("altered source\n")
        with patch.object(bench, "REPO", repo):
            result = self.audit([row])
        self.assertFalse(result["valid"])
        self.assertEqual(result["source_mutations"], ["execution-source/driver.py"])

    def test_score_audit_accepts_consistent_observations_and_missing_artifact_failures(self):
        row = self.scored_row()
        self.assertEqual(bench.score_integrity_errors(row, self.out), [])
        missing = self.scored_row(arm="verislop", missing=True)
        self.assertEqual(bench.score_integrity_errors(missing, self.out), [])

    def test_score_audit_rejects_false_pass_and_inflated_case_counts(self):
        row = self.scored_row()
        row["held_out_results"][0]["observed"] = {"wrong": "output"}
        self.save_score(row)
        self.assertTrue(bench.score_integrity_errors(row, self.out))
        row["held_out_results"][0]["observed"] = row["held_out_results"][0]["expected"]
        row["hidden_passed"] = 999
        self.save_score(row)
        self.assertTrue(bench.score_integrity_errors(row, self.out))

    def test_score_audit_rejects_blocked_success_and_nonzero_worker_exit(self):
        row = self.scored_row(arm="verislop")
        row["workflow_status"] = "BLOCKED"
        self.save_score(row)
        self.assertTrue(bench.score_integrity_errors(row, self.out))
        row["workflow_status"] = "PASS"
        row["worker_exit_code"] = 2
        self.save_score(row)
        self.assertTrue(bench.score_integrity_errors(row, self.out))

    def test_score_audit_rejects_changed_frozen_expected_values_and_case_identity(self):
        row = self.scored_row()
        row["held_out_results"][0]["expected"] = "altered oracle"
        row["held_out_results"][0]["observed"] = "altered oracle"
        self.save_score(row)
        self.assertTrue(bench.score_integrity_errors(row, self.out))
        row["held_out_results"][0]["id"] = row["held_out_results"][1]["id"]
        self.save_score(row)
        self.assertTrue(bench.score_integrity_errors(row, self.out))

    def test_score_audit_rejects_artifact_byte_mutation_and_detached_score_file(self):
        row = self.scored_row()
        candidate = self.out / row["artifact_path"] / "artifact/solution.py"
        candidate.write_text("def solve(data): return None\n")
        self.assertTrue(bench.score_integrity_errors(row, self.out))
        candidate.write_bytes(b"def solve(data): return data\n")
        saved = json.loads((self.out / row["artifact_path"] / "score.json").read_bytes())
        saved["hidden_passed"] = 999
        self.save_score(saved)
        self.assertTrue(bench.score_integrity_errors(row, self.out))


if __name__ == "__main__":
    unittest.main()
