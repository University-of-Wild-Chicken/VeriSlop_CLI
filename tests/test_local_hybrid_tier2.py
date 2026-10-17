"""Project request binding and concrete terminal rejection units.

Mocked mechanical snapshots below test harness decisions, not Lean assurance;
test_vscore3_source_pipeline separately exercises retained kernel evidence.
"""
from contextlib import nullcontext
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_bootstrap_tier2 as fixtures
from synthetic_dataset.tools import bootstrap_tier2, local_hybrid_tier2 as project, run_local_hybrid as hybrid
from verislop import canonical, cli, fsutil, interpret, run as native_run, review
from verislop.backends import vscore3_closure
from verislop.package import Package


class ProjectRequestBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.out = Path(temporary.name)
        self.task = hybrid.PROJECT_TASKS[0]
        self.protocol = {"trial_mode": "tier2-project", "tasks": [self.task]}
        self.invoked = hybrid.cli_argv(self.out, self.task, self.protocol)
        self.directory = self.out / "tasks" / self.task
        hybrid.once(self.directory / "invocation.json", {"argv": self.invoked, "positive_candidate_arguments": []})
        self.pkg = Package(self.directory / "runs" / self.task.lower())
        self.pkg.ensure(self.task.lower())
        parameters = native_run._params_from_args(cli.build_parser().parse_args(self.invoked))
        self.pkg.set_meta("run_parameters", parameters)
        self.prompt = self.out / "prompts" / f"{self.task}.txt"
        fsutil.atomic_write(self.prompt, b"Exact public component requirements.")
        interpret.stage_request(self.pkg, self.prompt, f"project-bootstrap/{self.task}.txt", "software")
        self.verify = patch.object(hybrid, "verify_inputs", return_value=self.protocol)
        self.verify.start()
        self.addCleanup(self.verify.stop)

    def test_same_request_and_native_invocation_bind(self):
        project.request_binding(self.out, self.task, self.pkg)

    def test_valid_other_prompt_cannot_borrow_project_success(self):
        changed = b"A different easier component."
        fsutil.atomic_write(self.pkg.path("prompt"), changed)
        request = canonical.load_file(self.pkg.path("request"))
        request.update(document_hash=canonical.digest(changed), byte_length=len(changed))
        fsutil.write_json(self.pkg.path("request"), request)
        with patch.object(bootstrap_tier2, "native_audit", return_value={"status": "PASS"}) as native:
            result = project.native_gate(self.out, self.task, self.pkg, {}, {}, 0)
        self.assertEqual("BLOCK", result["status"])
        self.assertTrue(any("exact frozen project prompt" in issue for issue in result["issues"]))
        native.assert_not_called()

    def test_external_candidate_and_different_invocation_block(self):
        parameters = self.pkg.meta()["run_parameters"]
        self.pkg.set_meta("run_parameters", {**parameters, "proof_candidate": "/some/positive-proof.lean"})
        with self.assertRaisesRegex(ValueError, "run parameters"):
            project.request_binding(self.out, self.task, self.pkg)
        self.pkg.set_meta("run_parameters", parameters)
        fsutil.write_json(self.directory / "invocation.json", {"argv": self.invoked + ["--proof-candidate", "/some/proof"],
                                                               "positive_candidate_arguments": []})
        with self.assertRaisesRegex(ValueError, "invocation differs"):
            project.request_binding(self.out, self.task, self.pkg)

    def test_request_metadata_and_task_membership_are_bound(self):
        request = canonical.load_file(self.pkg.path("request"))
        for change in ({"attachments": [{"path": "extra"}]}, {"request_ref": "other"}, {"mode": "auto"}):
            with self.subTest(change=change):
                fsutil.write_json(self.pkg.path("request"), {**request, **change})
                with self.assertRaisesRegex(ValueError, "exact frozen project prompt"):
                    project.request_binding(self.out, self.task, self.pkg)
        with self.assertRaisesRegex(ValueError, "outside the frozen"):
            project.request_binding(self.out, hybrid.PROJECT_TASKS[1], self.pkg)


class ProjectGateUnits(unittest.TestCase):
    record = fixtures.Tier2NativeTerminalObservationUnits.record
    serialized_gate = fixtures.Tier2NativeTerminalObservationUnits.serialized_gate
    refresh_records = fixtures.Tier2NativeTerminalObservationUnits.refresh_records

    def setUp(self):
        fixtures.Tier2NativeTerminalObservationUnits.setUp(self)
        self.out = self.configuration.parent
        self.task = hybrid.PROJECT_TASKS[0]
        self.gate.update(checkpoints={"formal_contract": "REVIEW_ACCEPTED", "release": "REVIEW_ACCEPTED"}, diagnostics=[])
        self.snapshot.update(mechanical_status="VERIFIED", builds=[{"build": "A", "ok": True}, {"build": "B", "ok": True}])
        self.report.update(terminal_status="VERIFIED", mechanical_status="VERIFIED", release_status="ACCEPTED",
            tier={"requested": 2, "target": "vscore", "endpoint": "restricted_source",
                  "requested_endpoint": "restricted_source", "require_state": "END_TO_END_VERIFIED"},
            language="vscore/0.3", semantics="vscore-semantics/0.3", backend="verislop.backend.vscore/0.3",
            freshness="current execution revalidated", endpoint={"established": "restricted_source"},
            review=self.serialized_gate(), builds=copy.deepcopy(self.snapshot["builds"]))
        history = [{"stage": stage, "status": "PASS", "codes": [], "seconds": 0}
                   for stage in native_run._stages_for({"tier": 2, "target": "vscore", "config": str(self.configuration)})]
        self.pkg.set_meta("stage_history", history)
        self.pipeline = {"command": "run", "status": "PASS", "summary": {
            "package": str(self.pkg.root), "active_package": str(self.pkg.root), "stopped_at": None, "stages": history}}
        self.stack.enter_context(patch.object(project, "request_binding"))
        self.stack.enter_context(patch.object(project, "provider_context", return_value=nullcontext()))
        self.stack.enter_context(patch.object(review, "gate", side_effect=lambda *args: copy.deepcopy(self.gate)))

    def observe(self):
        return project.native_gate(self.out, self.task, self.pkg, self.report, self.pipeline, 0)

    def test_qualified_native_observation_passes_and_requires_current_mechanics(self):
        self.assertEqual("PASS", self.observe()["status"], self.observe())
        with patch.object(vscore3_closure, "mechanical_snapshot", side_effect=ValueError("retained artifact hash differs")):
            result = self.observe()
        self.assertEqual("BLOCK", result["status"])
        self.assertTrue(any("retained artifact hash differs" in issue for issue in result["issues"]))

    def test_endpoint_state_release_builds_and_determinism_cannot_be_removed(self):
        original = copy.deepcopy(self.report)
        changes = (lambda: self.report["endpoint"].update(established=None),
                   lambda: self.report["tier"].update(require_state="TESTED"),
                   lambda: self.report.update(release_status="NOT_REQUIRED"),
                   lambda: self.report.update(builds=self.report["builds"][:1]),
                   lambda: self.report["determinism"].update(mismatches=["artifact differs"]),
                   lambda: self.report["obligations"]["G"]["outcomes"].update(END_TO_END_VERIFIED="PENDING"),
                   lambda: self.report.update(obligations={}))
        for number, change in enumerate(changes):
            with self.subTest(change=number):
                self.report = copy.deepcopy(original)
                change()
                self.assertEqual("BLOCK", self.observe()["status"])

    def test_native_clean_build_failure_not_just_report_label_blocks(self):
        self.snapshot["builds"][0]["ok"] = False
        self.report["builds"] = copy.deepcopy(self.snapshot["builds"])
        self.assertEqual("BLOCK", self.observe()["status"])

    def test_only_provisional_unreviewed_verify_can_be_blocked(self):
        history = self.pkg.meta()["stage_history"]
        verify = next(row for row in history if row["stage"] == "verify")
        verify.update(status="BLOCKED", codes=["REVIEW_NOT_RUN"])
        self.pkg.set_meta("stage_history", history)
        self.pipeline["summary"]["stages"] = history
        self.assertEqual("PASS", self.observe()["status"])
        verify["codes"] = ["KERNEL_REJECTION"]
        self.pkg.set_meta("stage_history", history)
        self.assertEqual("BLOCK", self.observe()["status"])

    def test_missing_or_forged_history_does_not_fill_missing_native_stages(self):
        self.pipeline["summary"]["stages"] = []
        self.assertEqual("BLOCK", self.observe()["status"])
        self.pkg.set_meta("stage_history", [])
        self.assertEqual("BLOCK", self.observe()["status"])


if __name__ == "__main__":
    unittest.main()
