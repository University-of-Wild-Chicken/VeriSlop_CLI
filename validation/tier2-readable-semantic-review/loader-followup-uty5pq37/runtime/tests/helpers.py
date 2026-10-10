"""Shared helpers for the VeriSlop test suite (stdlib unittest; requires the pinned Lean toolchain)."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
EX = REPO / "examples"
sys.path.insert(0, str(REPO))

from verislop import cli, fsutil  # noqa: E402


def run_cli(*args: str, env: dict[str, str] | None = None, stdin: str | None = None) -> tuple[int, dict[str, Any] | None, str]:
    """Run `verislop` in-process with --json; returns (exit code, parsed JSON result, stderr)."""
    argv = list(args)
    if "--json" not in argv:
        argv.append("--json")
    if "--quiet" not in argv:
        argv.append("--quiet")
    out, err = io.StringIO(), io.StringIO()
    old_env = {}
    for k, v in (env or {}).items():
        old_env[k] = os.environ.get(k)
        os.environ[k] = v
    old_stdin = sys.stdin
    if stdin is not None:
        sys.stdin = io.StringIO(stdin)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(argv)
            except SystemExit as exc:
                code = int(exc.code or 0)
    finally:
        sys.stdin = old_stdin
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    text = out.getvalue()
    try:
        data = json.loads(text) if text.strip().startswith("{") else None
    except ValueError:
        data = None
    return code, data, err.getvalue() + ("" if data is not None else text)


def codes(result: dict[str, Any] | None) -> set[str]:
    return {d["code"] for d in (result or {}).get("diagnostics", [])}


def stage(pkg: Path, name: str, *extra: str) -> tuple[int, dict[str, Any] | None]:
    code, data, _ = run_cli(name, "--package", str(pkg), *extra)
    return code, data


def build(pkg: Path, upto: str = "verify", *, draft: Path = EX / "draft.json", ledger: Path = EX / "interpretation.json",
          formalization: Path = EX / "formalization", impl: Path = EX / "python", tier: str = "0",
          proof: Path | None = None) -> dict[str, tuple[int, Any]]:
    """Run the stages in order up to and including `upto`; returns {stage: (code, json)}."""
    if pkg.exists():
        fsutil.remove_tree(pkg)
    pkg.mkdir(parents=True)
    plan = [
        ("interpret", ["--prompt-file", str(EX / "request.txt"), "--request-ref", "examples/request.txt",
                       "--candidate", str(draft), "--ledger", str(ledger), "--non-interactive"]),
        ("formalize", ["--candidate", str(formalization)]),
        ("prove", ["--candidate", str(proof)] if proof else []),
        ("accept", []),
        ("export", []),
        ("generate", ["--candidate", str(impl), "--tier", tier]),
        ("link", []),
        ("test", []),
        ("verify", []),
    ]
    out: dict[str, tuple[int, Any]] = {}
    for name, extra in plan:
        out[name] = stage(pkg, name, *extra)
        if name == upto:
            break
    return out


def copy_pkg(src: Path, dst: Path) -> Path:
    if dst.exists():
        fsutil.remove_tree(dst)
    shutil.copytree(src, dst, symlinks=True)
    return dst


def writable(path: Path) -> None:
    fsutil.make_writable_tree(path) if path.is_dir() else os.chmod(path, 0o644)


def formalization_variant(tmp: Path, name: str, lean_edit: Callable[[str], str] | None = None,
                          form_edit: Callable[[dict], dict] | None = None) -> Path:
    d = tmp / name
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(EX / "formalization", d)
    if lean_edit:
        p = d / "Contract.lean"
        p.write_text(lean_edit(p.read_text()))
    if form_edit:
        p = d / "formalization.json"
        p.write_text(json.dumps(form_edit(json.loads(p.read_text())), indent=2))
    return d


def json_variant(tmp: Path, src: Path, name: str, edit: Callable[[dict], dict]) -> Path:
    data = json.loads(src.read_text())
    p = tmp / name
    p.write_text(json.dumps(edit(data), indent=2))
    return p


def impl_variant(tmp: Path, name: str, source: str, bindings: dict | None = None) -> Path:
    d = tmp / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    (d / "bounded_increment.py").write_text(source)
    (d / "bindings.json").write_text(json.dumps(bindings or json.loads((EX / "python" / "bindings.json").read_text())))
    return d


class TempDir:
    def __init__(self) -> None:
        self.path = Path(tempfile.mkdtemp(prefix="verislop-test-"))

    def cleanup(self) -> None:
        if self.path.exists():
            fsutil.make_writable_tree(self.path)
            shutil.rmtree(self.path, ignore_errors=True)


# ------------------------------------------------------------------------------------------
# loopback mock LLM (OpenAI-compatible chat completions)
# ------------------------------------------------------------------------------------------

class MockLLM:
    def __init__(self, handler: Callable[[str, str, str], str], secret: str = "test-secret-123") -> None:
        self.handler = handler
        self.secret = secret
        self.requests: list[dict[str, Any]] = []
        mock = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a: Any) -> None:  # silence
                pass

            def _auth(self) -> bool:
                return self.headers.get("Authorization") == f"Bearer {mock.secret}"

            def do_GET(self) -> None:  # noqa: N802
                if not self._auth():
                    self.send_response(401)
                    self.end_headers()
                    return
                body = json.dumps({"data": [{"id": "mock-model"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self) -> None:  # noqa: N802
                n = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(n))
                mock.requests.append({"headers": dict(self.headers), "body": req})
                if not self._auth():
                    self.send_response(401)
                    self.end_headers()
                    return
                system = req["messages"][0]["content"]
                user = req["messages"][1]["content"]
                text = mock.handler(system, user, req["model"])
                body = json.dumps({"id": f"mock-{len(mock.requests)}", "model": req["model"] + "-2026-10-01",
                                   "choices": [{"message": {"role": "assistant", "content": text}}],
                                   "usage": {"prompt_tokens": 10, "completion_tokens": 10}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def mock_config(tmp: Path, port: int, tiers: list[dict[str, Any]], checkpoints: list[str] | None = None,
                max_repair_rounds: int = 0) -> tuple[Path, dict[str, str]]:
    """Write verislop.json + endpoint profiles for the mock; returns (config path, env)."""
    home = tmp / "config-home"
    home.mkdir(parents=True, exist_ok=True)
    (home / "endpoint-profiles.json").write_text(json.dumps({
        "schema_version": "0.1", "artifact_kind": "endpoint_profiles",
        "profiles": {"mock-local": {"adapter": "openai_compatible", "base_url": f"http://127.0.0.1:{port}/v1",
                                    "auth_scheme": "bearer", "families": ["chat_completions"],
                                    "auth_check": "GET /models", "allow_insecure_loopback": True}}}))
    agents = {"author": {"provider": "mock", "model_ref": "env:VERISLOP_TEST_MODEL", "tool_profile": "candidate_writer", "max_output_tokens": 4000}}
    for t in tiers:
        for g in t["reviewers"]:
            agents.setdefault(g["agent"], {"provider": "mock", "model_ref": "mock-reviewer", "tool_profile": "review_readonly", "max_output_tokens": 2000})
    conf = {
        "schema_version": "0.1", "bridge_tier": 0, "endpoint": "test_campaign",
        "providers": {"mock": {"adapter": "openai_compatible", "api_family": "chat_completions", "endpoint_profile": "mock-local",
                               "credential_ref": "env:VERISLOP_TEST_KEY", "concurrency": 4, "request_timeout_seconds": 30}},
        "agents": agents,
        "roles": {"interpreter": "author", "formalizer": "author", "prover": "author", "implementer": "author", "repairer": "author"},
        "review": {"checkpoints": checkpoints or ["formal_contract", "release"], "restart_after_repair": "first_tier",
                   "budgets": {"max_repair_rounds": max_repair_rounds, "max_provider_retries": 1, "max_calls_per_instance": 4,
                               "max_total_tokens": 1000000, "max_wall_seconds_per_tier": 300},
                   "review_tiers": tiers},
        "release": {"require_mechanical_pass": True, "require_all_review_tiers": True, "require_requested_bridge_tier": True},
    }
    path = tmp / "verislop.json"
    path.write_text(json.dumps(conf, indent=2))
    env = {"VERISLOP_CONFIG_HOME": str(home), "VERISLOP_TEST_KEY": "test-secret-123", "VERISLOP_TEST_MODEL": "mock-author"}
    return path, env


def unanimous(tier_id: str, agent: str, count: int) -> dict[str, Any]:
    return {"id": tier_id, "reviewers": [{"agent": agent, "count": count, "focus": "general"}],
            "consensus": {"mode": "unanimous", "require_all_responses": True, "max_soft_rejects": 0, "max_abstentions": 0,
                          "blocking_findings_veto": True}}
