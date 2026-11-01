"""HTTP and process regression tests for the local workbench.

The child-process fixtures below only write handwritten JSON bookkeeping. They
never call a model, Lean, a verifier, or the actual software-generation pipeline.
Native report labels in these fixtures test display fidelity, not assurance.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import quote, urlsplit

from verislop import cli, web


REPO = Path(__file__).resolve().parents[1]
REAL_POPEN = subprocess.Popen


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="verislop-workbench-test-")
        self.workspace = Path(self.temp.name)
        self.app = web.Workbench(self.workspace)
        self.server = web.make_server(self.app, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = "http://127.0.0.1:" + str(self.server.server_address[1])
        self.addCleanup(self.cleanup)
        code, meta = self.request("GET", "/api/meta")
        self.assertEqual(code, 200, meta)
        self.token = meta["token"]

    def cleanup(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.app.close()
        self.temp.cleanup()

    def request(self, method, route, body=None, *, token=True, headers=None):
        supplied = dict(headers or {})
        if body is not None:
            supplied.setdefault("Content-Type", "application/json")
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        if method == "POST" and token:
            supplied.setdefault("X-VeriSlop-Token", self.token)
            supplied.setdefault("Origin", self.origin)
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        try:
            conn.request(method, route, body=body, headers=supplied)
            response = conn.getresponse()
            content = response.read()
            if "application/json" in response.getheader("Content-Type", ""):
                content = json.loads(content)
            return response.status, content
        finally:
            conn.close()

    def write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def package(self, name="recorded", *, report=True):
        package = self.workspace / "retained" / name
        self.write_json(package / "package.json", {
            "schema_version": "0.1", "artifact_kind": "run_package", "run_id": name,
            "created_at": "2026-10-31T12:00:00Z", "artifacts": {},
            "run_parameters": {"tier": 2, "target": "vscore", "endpoint": "restricted_source"},
        })
        (package / "request").mkdir()
        (package / "request/prompt.txt").write_text("Preserve duplicate Unicode labels exactly.\n", encoding="utf-8")
        if report:
            self.write_json(package / "report.json", {
                "terminal_status": "BLOCKED", "mechanical_status": "VERIFIED", "release_status": "BLOCKED",
                "tier": {"requested": 2, "target": "vscore", "endpoint": "restricted_source"},
                "qualified_result": "Recorded source closure; release review blocked",
                "obligations": {"O1": {"kind": "postcondition", "role": "guarantee", "required": True,
                    "state": "PROVED", "outcomes": {"PROVED": "PASS", "IMPLEMENTED": "PENDING", "TESTED": "PENDING"},
                    "proof_boundary": "Lean reference model only", "blocking": ["release review"]}},
            })
        self.write_json(package / "accepted/accepted-ir.json", {
            "obligations": {"O1": {"statement": "Preserve duplicate occurrences", "lean_symbol": "Fixture.preserve"}}
        })
        (package / "events.jsonl").write_text(json.dumps({"seq": 1, "type": "verifier_decision", "phase": "prove",
            "message": "recorded proof gate", "time": "2026-10-31T12:00:02Z", "outcome": "PASS"}) + "\n", encoding="utf-8")
        return package

    def open_package(self, package):
        code, run = self.request("POST", "/api/runs/open", {"path": str(package)})
        self.assertEqual(code, 200, run)
        self.assertIn("id", run)
        return run

    def snapshot(self, root):
        return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob("*") if p.is_file()}

    def finish(self, ident, *, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            code, detail = self.request("GET", "/api/runs/" + ident)
            self.assertEqual(code, 200, detail)
            if detail["run"]["process_status"] not in {"RUNNING", "STARTING", "CANCELLING", "STOPPING"}:
                return detail
            time.sleep(0.02)
        self.fail("handwritten child did not finish within test bound")

    def fake_process(self, commands, *, script="print('{}')", on_spawn=None):
        def spawn(command, **kwargs):
            commands.append((list(command), dict(kwargs)))
            if on_spawn is not None:
                on_spawn(command)
            return REAL_POPEN([sys.executable, "-c", script], **kwargs)
        return patch.object(web.subprocess, "Popen", side_effect=spawn)

    def config(self, tier):
        conf = json.loads((REPO / "examples/local-hybrid-config.json").read_text())
        conf["bridge_tier"] = tier
        conf["endpoint"] = {0: "test_campaign", 1: "instrumented_runtime", 2: "restricted_source"}[tier]
        path = self.workspace / "models.json"
        self.write_json(path, conf)
        return path

    def save_request(self, **changes):
        data = {"prompt": "Preserve duplicate Unicode labels exactly.\n", "config": "", "tier": 0,
                "budget_seconds": 0, "repair_rounds": 2, **changes}
        status, saved = self.request("POST", "/api/requests", data)
        self.assertEqual(status, 201, saved)
        return saved

    def test_request_save_read_edit_are_exact_persistent_and_do_not_spawn(self):
        prompt = "  Preserve decomposed e\u0301 and é separately.\n" + "x" * 450 + "\n  "
        with patch.object(web.subprocess, "Popen") as spawn:
            saved = self.save_request(prompt=prompt)
            status, full = self.request("GET", "/api/requests/" + saved["id"])
            self.assertEqual(status, 200, full)
            self.assertEqual(full["prompt"], prompt)
            self.assertEqual(full["config"], "")
            self.assertIsNone(full["last_run_id"])
            status, listed = self.request("GET", "/api/requests")
            self.assertEqual(status, 200, listed)
            self.assertEqual(len(listed["requests"]), 1)
            self.assertEqual(listed["requests"][0]["prompt"], prompt[:400])
            replacement = {"prompt": "  Keep the exact trailing newline.\n", "config": "future-models.json",
                           "tier": 1, "budget_seconds": 120, "repair_rounds": 3}
            status, edited = self.request("POST", "/api/requests/" + saved["id"], replacement)
            self.assertEqual(status, 200, edited)
            for key, value in replacement.items():
                self.assertEqual(edited[key], value)
            self.assertEqual(edited["id"], saved["id"])
            self.assertEqual(edited["created_at"], saved["created_at"])
            self.app.close()
            another = web.Workbench(self.workspace)
            try:
                restored = another.get_request(saved["id"])
                self.assertEqual(restored, edited)
            finally:
                another.close()
        spawn.assert_not_called()

    def test_request_payload_boundaries_and_request_routes_do_not_escape(self):
        normal = {"prompt": "Implement sorting.", "config": "", "tier": 0,
                  "budget_seconds": 0, "repair_rounds": 2}
        with patch.object(web.subprocess, "Popen") as spawn:
            for change in ({"prompt": " \n "}, {"prompt": None}, {"prompt": "é" * 32001},
                           {"tier": 3}, {"tier": True}, {"config": {}}, {"config": "bad\x00path"},
                           {"config": "x" * 4097}, {"budget_seconds": -1}, {"repair_rounds": 9}):
                with self.subTest(change={k: type(v).__name__ for k, v in change.items()}):
                    status, result = self.request("POST", "/api/requests", {**normal, **change})
                    self.assertGreaterEqual(status, 400, result)
            status, result = self.request("POST", "/api/requests", normal, token=False)
            self.assertGreaterEqual(status, 400, result)
            saved = self.save_request(prompt="é" * 32000)
            self.assertEqual(len(saved["prompt"].encode()), 64000)
            # JSON expands each control character to six bytes. The HTTP and
            # persisted-document limits must still admit the advertised 64 KiB
            # UTF-8 prompt limit without trimming or truncation.
            escaped_prompt = "x" + "\x01" * 63999
            escaped = self.save_request(prompt=escaped_prompt, config="\x01" * 4096)
            status, expanded = self.request("GET", "/api/requests/" + escaped["id"])
            self.assertEqual(status, 200, expanded)
            self.assertEqual(expanded["prompt"], escaped_prompt)
            self.assertEqual(expanded["config"], "\x01" * 4096)
            for route in ("/api/requests/../registry.json", "/api/requests/%2e%2e%2fregistry.json",
                          "/api/requests/not-a-saved-request"):
                status, result = self.request("GET", route)
                self.assertGreaterEqual(status, 400, result)
            status, result = self.request("POST", "/api/requests/" + saved["id"], {**normal, "prompt": ""})
            self.assertGreaterEqual(status, 400, result)
            status, full = self.request("GET", "/api/requests/" + saved["id"])
            self.assertEqual(status, 200, full)
            self.assertEqual(full["prompt"], "é" * 32000)
        spawn.assert_not_called()

    def test_request_launch_freezes_prompt_and_links_owned_run(self):
        config = self.config(0)
        prompt = "Implement an exact Unicode label pipeline.\n  Keep trailing spaces.  "
        saved = self.save_request(prompt=prompt, config=str(config))
        commands = []
        linked_before_spawn = []
        with self.fake_process(commands, script="import time; time.sleep(0.2); print('{}')",
                on_spawn=lambda _: linked_before_spawn.append(self.app.get_request(saved["id"])["last_run_id"])):
            status, run = self.request("POST", "/api/requests/" + saved["id"] + "/launch", {})
            self.assertEqual(status, 201, run)
            self.assertEqual(linked_before_spawn, [run["id"]])
            args = cli.build_parser().parse_args(commands[0][0][commands[0][0].index("run"):])
            self.assertEqual(Path(args.prompt_file).read_text(), prompt)
            self.assertEqual(args.config, str(config))
            snapshot = Path(args.prompt_file).parent / "request.json"
            frozen_request = snapshot.read_bytes()
            edited_prompt = "A future revision must not rewrite the already-started run."
            status, edited = self.request("POST", "/api/requests/" + saved["id"], {
                "prompt": edited_prompt, "config": str(config), "tier": 0, "budget_seconds": 0, "repair_rounds": 2})
            self.assertEqual(status, 200, edited)
            self.assertEqual(edited["last_run_id"], run["id"])
            self.assertEqual(Path(args.prompt_file).read_text(), prompt)
            self.assertEqual(snapshot.read_bytes(), frozen_request)
            status, detail = self.request("GET", "/api/runs/" + run["id"])
            self.assertEqual(status, 200, detail)
            self.assertEqual(detail["prompt"], prompt)
            self.finish(run["id"])
        status, current = self.request("GET", "/api/requests/" + saved["id"])
        self.assertEqual(status, 200, current)
        self.assertEqual(current["prompt"], edited_prompt)
        self.assertEqual(current["last_run_id"], run["id"])

    def test_failed_request_launch_preserves_saved_draft(self):
        with patch.object(web.subprocess, "Popen") as spawn:
            # A draft's configuration is opaque until explicit launch, so it
            # can be saved before a model configuration exists. Launch still
            # rejects missing or outside-workspace configuration paths.
            for config in ("", "missing-config.json", "../outside.json"):
                with self.subTest(config=config):
                    saved = self.save_request(config=config)
                    route = "/api/requests/" + saved["id"]
                    for body in ({}, {"prompt": "unrecorded replacement"}):
                        status, result = self.request("POST", route + "/launch", body)
                        self.assertGreaterEqual(status, 400, result)
                    status, current = self.request("GET", route)
                    self.assertEqual(status, 200, current)
                    self.assertEqual(current, saved)
        spawn.assert_not_called()

    def test_request_link_persistence_failure_never_starts_process(self):
        saved = self.save_request(config=str(self.config(0)))
        with patch.object(self.app, "_write_request", side_effect=OSError("fixture persistence failure")), \
                patch.object(web.subprocess, "Popen") as spawn:
            status, failure = self.request("POST", "/api/requests/" + saved["id"] + "/launch", {})
        self.assertEqual(status, 500, failure)
        spawn.assert_not_called()
        status, current = self.request("GET", "/api/requests/" + saved["id"])
        self.assertEqual(status, 200, current)
        self.assertEqual(current, saved)
        status, catalog = self.request("GET", "/api/runs")
        self.assertEqual(status, 200, catalog)
        self.assertEqual(len(catalog["runs"]), 1)
        run = catalog["runs"][0]
        self.assertEqual(run["status"], "INFRASTRUCTURE_FAILURE")
        self.assertFalse(run["owned"])
        status, detail = self.request("GET", "/api/runs/" + run["id"])
        self.assertEqual(status, 200, detail)
        self.assertEqual(detail["run"]["status"], "INFRASTRUCTURE_FAILURE")

    def test_meta_and_list_do_not_launch_any_process(self):
        with patch.object(web.subprocess, "Popen") as spawn:
            status, meta = self.request("GET", "/api/meta")
            listed, result = self.request("GET", "/api/runs")
        spawn.assert_not_called()
        self.assertEqual((status, listed), (200, 200))
        self.assertEqual(result, {"runs": []})
        self.assertEqual(meta["workspace"], str(self.workspace))
        self.assertEqual({row["id"] for row in meta["tiers"]}, {0, 1, 2})
        self.assertTrue(meta["example_prompt"].strip())

    def test_inspection_preserves_recorded_outcomes_and_package_bytes(self):
        package = self.package()
        before = self.snapshot(package)
        with patch.object(web.subprocess, "Popen") as spawn:
            run = self.open_package(package)
            code, detail = self.request("GET", "/api/runs/" + run["id"])
        spawn.assert_not_called()
        self.assertEqual(code, 200, detail)
        self.assertEqual(detail["run"]["status"], "BLOCKED")
        self.assertEqual(detail["run"]["mechanical_status"], "VERIFIED")
        self.assertEqual(detail["run"]["release_status"], "BLOCKED")
        self.assertFalse(detail["run"]["owned"])
        self.assertEqual(detail["obligations"][0]["outcomes"]["TESTED"], "PENDING")
        self.assertEqual(detail["events"][0]["message"], "recorded proof gate")
        self.assertIn("report.json", {row["path"] for row in detail["artifacts"]})
        self.assertEqual(before, self.snapshot(package))

    def test_partial_report_and_event_tail_are_inspectable_without_success(self):
        package = self.package(report=False)
        (package / "report.json").write_text('{"terminal_status":', encoding="utf-8")
        with (package / "events.jsonl").open("a") as stream:
            stream.write('{"seq":2')
        run = self.open_package(package)
        code, detail = self.request("GET", "/api/runs/" + run["id"])
        self.assertEqual(code, 200, detail)
        self.assertNotEqual(detail["run"]["status"], "VERIFIED")
        self.assertEqual(len(detail["events"]), 1)
        self.assertTrue(detail["warnings"])
        (package / "report.json").write_text(
            '{"terminal_status":"BLOCKED","terminal_status":"VERIFIED"}')
        code, detail = self.request("GET", "/api/runs/" + run["id"])
        self.assertEqual(code, 200, detail)
        self.assertIsNone(detail["report"])
        self.assertNotEqual(detail["run"]["status"], "VERIFIED")
        self.assertTrue(any("report.json" in warning for warning in detail["warnings"]))

    def test_requested_endpoint_and_state_are_recorded_values_not_guesses(self):
        package = self.package(report=False)
        meta_path = package / "package.json"
        meta = json.loads(meta_path.read_text())
        meta.pop("run_parameters")
        meta["requested"] = {"tier": 3, "target": "native", "endpoint": "native_binary",
                             "require_state": "END_TO_END_VERIFIED"}
        self.write_json(meta_path, meta)
        run = self.open_package(package)
        self.assertEqual((run["tier"], run["target"], run["endpoint"], run["require_state"]),
                         (3, "native", "native_binary", "END_TO_END_VERIFIED"))

        # A report's exact selected scope takes precedence over request metadata.
        self.write_json(package / "report.json", {"terminal_status": "BLOCKED", "tier": {
            "requested": 1, "target": "python", "endpoint": "instrumented_runtime", "require_state": "TESTED"}})
        code, detail = self.request("GET", "/api/runs/" + run["id"])
        self.assertEqual(code, 200, detail)
        selected = detail["run"]
        self.assertEqual((selected["tier"], selected["endpoint"], selected["require_state"]),
                         (1, "instrumented_runtime", "TESTED"))

        # No requested value may be fabricated from a tier when metadata is absent.
        (package / "report.json").unlink()
        meta.pop("requested")
        self.write_json(meta_path, meta)
        code, detail = self.request("GET", "/api/runs/" + run["id"])
        self.assertEqual(code, 200, detail)
        self.assertIsNone(detail["run"]["require_state"])
        self.assertIsNone(detail["run"]["endpoint"])

    def test_artifact_preview_is_confined_and_bounded(self):
        package = self.package()
        (package / "implementation").mkdir()
        (package / "implementation/solve.py").write_text("def solve(x): return x\n")
        (package / "implementation/large.txt").write_text("x" * (2 * 1024 * 1024))
        run = self.open_package(package)
        prefix = "/api/runs/" + run["id"] + "/artifact?path="
        code, preview = self.request("GET", prefix + "implementation/solve.py")
        self.assertEqual(code, 200, preview)
        self.assertIn("def solve", preview["content"])
        self.assertFalse(preview["truncated"])
        code, preview = self.request("GET", prefix + "implementation/large.txt")
        self.assertEqual(code, 200, preview)
        self.assertTrue(preview["truncated"])
        self.assertLess(len(preview["content"]), preview["size"])
        for path in ("../../models.json", str(self.workspace / "models.json")):
            code, result = self.request("GET", prefix + quote(path, safe=""))
            self.assertGreaterEqual(code, 400, result)

    def test_open_paths_reject_escape_and_symlink(self):
        package = self.package()
        link = self.workspace / "linked"
        link.symlink_to(package, target_is_directory=True)
        for path in (str(self.workspace.parent), "../outside", str(link)):
            code, result = self.request("POST", "/api/runs/open", {"path": path})
            self.assertGreaterEqual(code, 400, result)
            self.assertIn("error", result)

    def test_http_origin_host_and_token_boundaries(self):
        package = self.package()
        body = {"path": str(package)}
        code, result = self.request("POST", "/api/runs/open", body, token=False)
        self.assertGreaterEqual(code, 400, result)
        for method, path, value, headers in (
            ("POST", "/api/runs/open", body, {"X-VeriSlop-Token": "wrong"}),
            ("POST", "/api/runs/open", body, {"X-VeriSlop-Token": "é"}),
            ("POST", "/api/runs/open", body, {"Origin": "http://foreign.example"}),
            ("GET", "/api/meta", None, {"Origin": "http://foreign.example"}),
            ("GET", "/api/meta", None, {"Host": "foreign.example"}),
        ):
            with self.subTest(method=method, headers=headers):
                code, result = self.request(method, path, value, headers=headers)
                self.assertGreaterEqual(code, 400, result)
        code, result = self.request("POST", "/api/runs/open", body)
        self.assertEqual(code, 200, result)

    def test_example_launch_uses_exact_candidates_and_no_provider_config(self):
        commands = []
        with self.fake_process(commands):
            code, run = self.request("POST", "/api/runs", {"mode": "example", "tier": 0,
                "prompt": "An unrelated injected replacement", "budget_seconds": 0, "repair_rounds": 0})
            self.assertIn(code, (200, 201, 202), run)
            detail = self.finish(run["id"])
        command, kwargs = commands[0]
        args = cli.build_parser().parse_args(command[command.index("run"):])
        self.assertEqual(args.tier, 0)
        self.assertEqual(args.target, "python")
        self.assertEqual(args.budget_seconds, 0)
        self.assertTrue(args.non_interactive)
        self.assertTrue(args.require_tests)
        self.assertNotIn("--config", command)
        self.assertEqual(Path(args.prompt_file).read_bytes(), (REPO / "examples/request.txt").read_bytes())
        self.assertEqual(Path(args.implementation_candidate), REPO / "examples/python")
        self.assertFalse(kwargs.get("shell", False))
        self.assertTrue(kwargs["start_new_session"])
        self.assertNotEqual(detail["run"]["status"], "VERIFIED")

    def test_agent_launch_preserves_supported_tier_and_exact_prompt(self):
        prompt = "Keep labels with quotes ' and $() literally.\nDo not deduplicate."
        for tier in (0, 1, 2):
            with self.subTest(tier=tier):
                config = self.config(tier)
                commands = []
                with self.fake_process(commands):
                    code, run = self.request("POST", "/api/runs", {"mode": "agents", "tier": tier,
                        "prompt": prompt, "config": str(config), "budget_seconds": 0, "repair_rounds": 2})
                    self.assertIn(code, (200, 201, 202), run)
                    self.finish(run["id"])
                command = commands[0][0]
                args = cli.build_parser().parse_args(command[command.index("run"):])
                self.assertEqual(args.tier, tier)
                self.assertEqual(Path(args.prompt_file).read_text(), prompt)
                self.assertEqual(args.config, str(config))
                self.assertEqual(args.repair_rounds, 2)
                if tier == 2:
                    self.assertEqual((args.target, args.backend_version, args.endpoint, args.require_state),
                                     ("vscore", "0.3", "restricted_source", "END_TO_END_VERIFIED"))
                    self.assertTrue(args.no_tests)
                else:
                    self.assertEqual(args.target, "python")
                    self.assertEqual(args.require_state, "TESTED")
                    self.assertTrue(args.require_tests)

    def test_invalid_launch_is_rejected_before_spawn(self):
        config = str(self.config(0))
        normal = {"mode": "agents", "prompt": "Implement sorting", "config": config, "tier": 0,
                  "budget_seconds": 0, "repair_rounds": 2}
        with patch.object(web.subprocess, "Popen") as spawn:
            for change in ({"tier": 3}, {"tier": True}, {"prompt": ""}, {"config": "missing.json"},
                           {"budget_seconds": -1}, {"repair_rounds": 9}, {"mode": "arbitrary"}):
                with self.subTest(change=change):
                    code, result = self.request("POST", "/api/runs", {**normal, **change})
                    self.assertGreaterEqual(code, 400, result)
        spawn.assert_not_called()

    def test_only_owned_live_process_is_cancellable_and_single_run_admission(self):
        imported = self.open_package(self.package())
        code, result = self.request("POST", "/api/runs/" + imported["id"] + "/cancel", {})
        self.assertGreaterEqual(code, 400, result)
        commands = []
        with self.fake_process(commands, script="import time; print('ready', flush=True); time.sleep(30)"):
            code, run = self.request("POST", "/api/runs", {"mode": "example", "tier": 0})
            self.assertIn(code, (200, 201, 202), run)
            code, result = self.request("POST", "/api/runs", {"mode": "example", "tier": 0})
            self.assertEqual(code, 409, result)
            code, result = self.request("POST", "/api/runs/" + run["id"] + "/cancel", {})
            self.assertIn(code, (200, 202), result)
            detail = self.finish(run["id"])
        self.assertEqual(len(commands), 1)
        self.assertNotEqual(detail["run"]["process_status"], "RUNNING")
        self.assertNotEqual(detail["run"]["status"], "VERIFIED")

    def test_registration_survives_restart_without_claiming_process_ownership(self):
        run = self.open_package(self.package())
        registry = self.workspace / ".verislop/workbench/registry.json"
        saved = json.loads(registry.read_text())
        saved["runs"][0].update(process_status="RUNNING", owned=True)
        self.write_json(registry, saved)
        self.app.close()
        another = web.Workbench(self.workspace)
        try:
            detail = another.detail(run["id"])
            self.assertEqual(detail["run"]["run_id"], "recorded")
            self.assertFalse(detail["run"]["owned"])
            self.assertEqual(detail["run"]["process_status"], "INTERRUPTED")
        finally:
            another.close()

    def test_completed_run_follows_exact_named_recovery_package(self):
        recorded_commands = []

        def spawn(command, **kwargs):
            args = cli.build_parser().parse_args(command[command.index("run"):])
            active = Path(args.runs_dir) / (args.run_id + "-repair-01")
            recorded_commands.append((args, active))
            # A handwritten child imitates only the ordinary run-result envelope.
            # The retained report is deliberately BLOCKED, never a proof result.
            script = (
                "import json\nfrom pathlib import Path\n"
                f"p=Path({str(active)!r})\np.mkdir(parents=True)\n"
                "(p/'package.json').write_text(json.dumps({'run_id':p.name,'artifacts':{}}))\n"
                "(p/'report.json').write_text(json.dumps({'terminal_status':'BLOCKED','obligations':{}}))\n"
                "print(json.dumps({'summary':{'active_package':str(p)}}))\n"
            )
            return REAL_POPEN([sys.executable, "-c", script], **kwargs)

        with patch.object(web.subprocess, "Popen", side_effect=spawn):
            code, run = self.request("POST", "/api/runs", {"mode": "example", "tier": 0})
            self.assertIn(code, (200, 201, 202), run)
            detail = self.finish(run["id"])
        self.assertEqual(detail["run"]["path"], str(recorded_commands[0][1].relative_to(self.workspace)))
        self.assertEqual(detail["run"]["status"], "BLOCKED")
        self.assertEqual(detail["report"]["terminal_status"], "BLOCKED")
        self.assertEqual(detail["run"]["id"], run["id"])
        code, catalog = self.request("GET", "/api/runs")
        self.assertEqual(code, 200, catalog)
        self.assertEqual(len(catalog["runs"]), 1, "Recovery package must not duplicate its owning run")

    def test_cli_start_failure_remains_inspectable_as_infrastructure_failure(self):
        with patch.object(web.subprocess, "Popen", side_effect=OSError("fixture failed to spawn")):
            code, result = self.request("POST", "/api/runs", {"mode": "example", "tier": 0})
        self.assertEqual(code, 500, result)
        code, result = self.request("GET", "/api/runs")
        self.assertEqual(code, 200, result)
        self.assertEqual(len(result["runs"]), 1)
        run = result["runs"][0]
        self.assertEqual(run["status"], "INFRASTRUCTURE_FAILURE")
        self.assertFalse(run["owned"])
        self.assertNotEqual(run["process_status"], "RUNNING")

    def test_nonfinite_json_cannot_produce_success_or_spawn(self):
        package = self.package()
        (package / "report.json").write_text('{"terminal_status":"VERIFIED","value":NaN}')
        run = self.open_package(package)
        code, detail = self.request("GET", "/api/runs/" + run["id"])
        self.assertEqual(code, 200, detail)
        self.assertIsNone(detail["report"])
        self.assertNotEqual(detail["run"]["status"], "VERIFIED")
        self.assertTrue(any("report.json" in row for row in detail["warnings"]))
        with patch.object(web.subprocess, "Popen") as spawn:
            code, result = self.request("POST", "/api/runs", {"mode": "example", "budget_seconds": float("nan")})
        self.assertEqual(code, 400, result)
        spawn.assert_not_called()

    def test_cli_ui_forwards_local_server_arguments(self):
        with patch.object(web, "main", return_value=2) as serve:
            result = cli.main(["ui", "--workspace", "workspace with spaces", "--runs-dir", "runs",
                               "--host", "localhost", "--port", "9123"])
        self.assertEqual(result, 2)
        serve.assert_called_once_with(["--workspace", "workspace with spaces", "--host", "localhost",
                                       "--port", "9123", "--runs-dir", "runs"])

    def test_static_assets_are_served_with_content_types_and_csp(self):
        for path, types in (("/", {"text/html"}), ("/app.js", {"application/javascript", "text/javascript"}),
                            ("/styles.css", {"text/css"})):
            with self.subTest(path=path):
                conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
                try:
                    conn.request("GET", path)
                    response = conn.getresponse()
                    body = response.read()
                    self.assertEqual(response.status, 200, body)
                    self.assertIn(response.getheader("Content-Type").split(";")[0], types)
                    self.assertIn("script-src 'self'", response.getheader("Content-Security-Policy"))
                    self.assertIn("frame-ancestors 'none'", response.getheader("Content-Security-Policy"))
                    self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
                    self.assertTrue(body)
                    if path == "/":
                        self.assertIn(b"VeriSlop", body)
                finally:
                    conn.close()

    def test_server_rejects_nonloopback_bind(self):
        for host in ("0.0.0.0", "192.0.2.1"):
            with self.subTest(host=host), self.assertRaises(web.APIError):
                web.make_server(self.app, host=host, port=0)

    def test_workspace_has_one_controller_and_lock_is_released_on_close(self):
        with self.assertRaises(web.APIError):
            web.Workbench(self.workspace)
        self.app.close()
        replacement = web.Workbench(self.workspace)
        try:
            self.assertEqual(replacement.workspace, self.workspace)
        finally:
            replacement.close()

    def test_invalid_registry_is_preserved_and_failed_start_releases_owner_lock(self):
        self.app.close()
        registry = self.workspace / ".verislop/workbench/registry.json"
        for invalid in ({"version": 99, "runs": []}, {"version": 1, "runs": "retain these bytes"}):
            with self.subTest(invalid=invalid):
                self.write_json(registry, invalid)
                original = registry.read_bytes()
                with self.assertRaises(web.APIError):
                    web.Workbench(self.workspace)
                self.assertEqual(registry.read_bytes(), original)
                self.write_json(registry, {"version": 1, "runs": []})
                replacement = web.Workbench(self.workspace)
                try:
                    self.assertEqual(replacement.list_runs(), {"runs": []})
                finally:
                    replacement.close()

    def test_cancel_still_stops_owned_child_when_registry_persistence_fails(self):
        commands = []
        pids = []

        def spawn(command, **kwargs):
            commands.append(command)
            child = REAL_POPEN([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
            pids.append(child.pid)
            return child

        with patch.object(web.subprocess, "Popen", side_effect=spawn):
            status, run = self.request("POST", "/api/runs", {"mode": "example", "tier": 0})
            self.assertEqual(status, 201, run)
            with patch.object(self.app, "_save", side_effect=OSError("fixture registry unavailable")):
                status, result = self.request("POST", "/api/runs/" + run["id"] + "/cancel", {})
                self.assertEqual(status, 200, result)
                detail = self.finish(run["id"])
        self.assertEqual(len(commands), 1)
        self.assertNotEqual(detail["run"]["status"], "VERIFIED")
        self.assertFalse(detail["run"]["owned"])
        with self.assertRaises(ProcessLookupError):
            os.kill(pids[0], 0)

    def test_configuration_metadata_excludes_credentials_and_model_details(self):
        path = self.config(0)
        conf = json.loads(path.read_text())
        marker = "not-for-browser-fixture-model-secret"
        credential_ref = "env:NOT_FOR_BROWSER_FIXTURE_CREDENTIAL"
        conf["agents"][next(iter(conf["agents"]))]["model_ref"] = marker
        conf["providers"][next(iter(conf["providers"]))]["credential_ref"] = credential_ref
        self.write_json(self.workspace / "verislop.json", conf)
        with patch.object(web.subprocess, "Popen") as spawn:
            status, meta = self.request("GET", "/api/meta")
        self.assertEqual(status, 200, meta)
        spawn.assert_not_called()
        encoded = json.dumps(meta)
        self.assertNotIn(marker, encoded)
        self.assertNotIn(credential_ref, encoded)
        self.assertIn("verislop.json", meta["configs"])
        detail = next(row for row in meta["config_details"] if row["path"] == "verislop.json")
        self.assertTrue(detail["valid"])
        self.assertEqual(detail["tier"], 0)

    def test_missing_example_fixture_is_rejected_before_spawn(self):
        absent = self.workspace / "missing-example-fixtures"
        with patch.object(web, "EXAMPLES", absent), patch.object(web.subprocess, "Popen") as spawn:
            status, result = self.request("POST", "/api/runs", {"mode": "example", "tier": 0})
        self.assertGreaterEqual(status, 400, result)
        spawn.assert_not_called()

    def test_sigterm_server_stops_owned_child_and_preserves_unrelated_process(self):
        workspace = self.workspace / "signal-server"
        workspace.mkdir()
        pid_file = workspace / "controlled-child.pid"
        child_code = ("import os,time\nfrom pathlib import Path\n"
                      f"Path({str(pid_file)!r}).write_text(str(os.getpid()))\ntime.sleep(60)\n")
        # The server is real, but its Popen seam launches only this sleeping
        # fixture. It cannot execute the CLI, a model, or Lean.
        server_code = (
            "import sys\nfrom verislop import web\n"
            "real_popen=web.subprocess.Popen\n"
            "def controlled_child(command, **kwargs):\n"
            f" return real_popen([sys.executable,'-c',{child_code!r}],**kwargs)\n"
            "web.subprocess.Popen=controlled_child\n"
            f"raise SystemExit(web.main(['--workspace',{str(workspace)!r},'--port','0']))\n"
        )
        unrelated = REAL_POPEN([sys.executable, "-c", "import time; time.sleep(60)"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        server = None
        child_pid = None
        try:
            server = REAL_POPEN([sys.executable, "-B", "-u", "-c", server_code], cwd=REPO,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            with selectors.DefaultSelector() as selector:
                selector.register(server.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=5), "server failed to publish its local URL")
                first = server.stdout.readline().strip()
            self.assertTrue(first.startswith("VeriSlop Workbench: http://127.0.0.1:"), first)
            origin = first.split(": ", 1)[1]
            port = urlsplit(origin).port

            def call(method, path, payload=None, token=None):
                headers = {}
                body = None
                if payload is not None:
                    body = json.dumps(payload).encode()
                    headers = {"Content-Type": "application/json", "Origin": origin,
                               "X-VeriSlop-Token": token}
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                try:
                    connection.request(method, path, body=body, headers=headers)
                    response = connection.getresponse()
                    return response.status, json.loads(response.read())
                finally:
                    connection.close()

            status, meta = call("GET", "/api/meta")
            self.assertEqual(status, 200, meta)
            status, run = call("POST", "/api/runs", {"mode": "example", "tier": 0}, meta["token"])
            self.assertEqual(status, 201, run)
            deadline = time.monotonic() + 5
            while not pid_file.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(pid_file.exists(), "controlled child never started")
            child_pid = int(pid_file.read_text())
            os.kill(child_pid, 0)
            server.send_signal(signal.SIGTERM)
            self.assertEqual(server.wait(timeout=8), 0)
            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)
            self.assertIsNone(unrelated.poll(), "shutdown must not signal another process")
        finally:
            if server is not None:
                if server.poll() is None:
                    server.terminate()
                    try:
                        server.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=3)
                server.stdout.close()
                server.stderr.close()
            if child_pid is not None:
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            unrelated.terminate()
            unrelated.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
