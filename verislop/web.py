"""Local Workbench HTTP adapter. It observes artifacts; the CLI decides assurance.

Run with ``python -m verislop.web --workspace . --port 8765``. This server is
deliberately loopback-only and has no third-party runtime dependencies.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import threading
from urllib.parse import parse_qs, unquote, urlsplit

from . import __version__, fsutil
from .errors import VeriSlopError

REPO = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).with_name("web_assets")
EXAMPLES = Path(__file__).with_name("examples")
if not (EXAMPLES / "request.txt").is_file():
    EXAMPLES = REPO / "examples"
JSON_LIMIT = 4 * 1024 * 1024
PREVIEW_LIMIT = 256 * 1024
LOG_LIMIT = 64 * 1024
# A 64000-byte prompt may expand sixfold when JSON escapes control characters.
# Leave room for the bounded configuration path and request metadata as well.
BODY_LIMIT = 512 * 1024
MAX_RUNS = 200
MAX_REQUESTS = 200
REQUEST_LIMIT = 512 * 1024
MILESTONES = ("INTERPRETED", "FORMALIZED", "TYPECHECKED", "PROVED", "IMPLEMENTED",
              "LINKED", "TESTED", "END_TO_END_VERIFIED")
TIERS = [
    {"id": 0, "label": "Tier 0 · Tested Python", "target": "python", "endpoint": "test_campaign",
     "require_state": "TESTED", "description": "Finite property testing of the delivered Python implementation."},
    {"id": 1, "label": "Tier 1 · Runtime contracts", "target": "python", "endpoint": "instrumented_runtime",
     "require_state": "TESTED", "description": "Python runtime assertions and a finite test campaign."},
    {"id": 2, "label": "Tier 2 · Verified VSCore", "target": "vscore", "endpoint": "restricted_source",
     "require_state": "END_TO_END_VERIFIED", "description": "VSCore 0.3 source semantics; runtime testing is unavailable."},
]
TEXT_SUFFIXES = {".json", ".jsonl", ".lean", ".py", ".vsc", ".txt", ".md", ".toml", ".yaml",
                 ".yml", ".log", ".csv", ".html", ".js", ".css"}


class APIError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _confined(base: Path, value: str | Path) -> Path:
    """Validate lexical containment and reject symlinks before any file access."""
    if not isinstance(value, (str, Path)) or not str(value) or "\x00" in str(value):
        raise APIError("A nonempty local path is required.")
    candidate = Path(value)
    if ".." in candidate.parts:
        raise APIError("Parent traversal is not allowed.")
    candidate = candidate if candidate.is_absolute() else base / candidate
    try:
        parts = candidate.relative_to(base).parts
    except ValueError:
        raise APIError("Path must be inside this workspace.") from None
    current = base
    for part in parts:
        current /= part
        if current.is_symlink():
            raise APIError("Symbolic links are not supported for workbench paths.")
    if not candidate.resolve().is_relative_to(base.resolve()):
        raise APIError("Path must remain inside this workspace.")
    return candidate


def _read(path: Path, limit: int, *, tail: bool = False) -> tuple[bytes, int]:
    """Bounded descriptor read; no symlinks, devices, FIFOs or hardlinks."""
    fd = fsutil.open_regular_file(path, os.O_RDONLY)
    with os.fdopen(fd, "rb") as stream:
        size = os.fstat(stream.fileno()).st_size
        if tail and size > limit:
            stream.seek(size - limit)
        return stream.read(limit), size


def _object(value) -> dict:
    return value if isinstance(value, dict) else {}


def _json_loads(raw):
    def invalid_constant(value):
        raise ValueError(f"Nonfinite JSON value {value} is not supported")
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON object keys are not supported")
            result[key] = value
        return result
    try:
        return json.loads(raw, parse_constant=invalid_constant, object_pairs_hook=unique_keys)
    except RecursionError:
        raise ValueError("JSON nesting exceeds the supported depth") from None


class Workbench:
    """A small persistent catalog plus processes owned by this server session."""

    def __init__(self, workspace: Path, runs_dir: Path | None = None):
        self.workspace = Path(workspace).resolve()
        if not self.workspace.is_dir():
            raise APIError("Workspace must be an existing directory.")
        self.runs_dir = _confined(self.workspace, runs_dir or ".verislop/runs")
        self.state_dir = _confined(self.workspace, ".verislop/workbench")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir = _confined(self.state_dir, "jobs")
        self.jobs_dir.mkdir(exist_ok=True)
        self.requests_dir = _confined(self.state_dir, "requests")
        self.requests_dir.mkdir(exist_ok=True)
        self.registry_path = _confined(self.state_dir, "registry.json")
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.records: dict[str, dict] = {}
        self.processes: dict[str, subprocess.Popen] = {}
        self._watchers: list[threading.Thread] = []
        self.closed = False
        self._owner_fd: int | None = None
        owner_fd = fsutil.open_regular_file(_confined(self.state_dir, "server.lock"), os.O_RDWR | os.O_CREAT)
        try:
            fcntl.flock(owner_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(owner_fd)
            raise APIError("A workbench is already using this workspace. Stop its server or choose a different workspace.", 409) from None
        except BaseException:
            os.close(owner_fd)
            raise
        self._owner_fd = owner_fd
        if self.registry_path.exists():
            try:
                data, size = _read(self.registry_path, JSON_LIMIT)
                if size > JSON_LIMIT:
                    raise APIError("Workbench registry exceeds its read limit.")
                saved = _json_loads(data)
                if (not isinstance(saved, dict) or saved.get("version") != 1
                        or not isinstance(saved.get("runs"), list) or len(saved["runs"]) > MAX_RUNS):
                    raise ValueError("unsupported or invalid workbench registry")
                for row in saved["runs"]:
                    if (not isinstance(row, dict) or not isinstance(row.get("id"), str)
                            or len(row["id"]) != 20 or any(c not in "0123456789abcdef" for c in row["id"])
                            or row["id"] in self.records):
                        raise ValueError("invalid or duplicate workbench run identity")
                    self._package(row)
                    if row.get("process_status") in ("RUNNING", "CANCELLING"):
                        row["process_status"] = "INTERRUPTED"
                    self.records[row["id"]] = row
            except (OSError, ValueError, VeriSlopError, TypeError, KeyError, AttributeError):
                # Do not overwrite a malformed persisted registry on startup.
                self._release_owner()
                raise APIError("Cannot read the workbench registry; preserve it and use a clean workspace.") from None

    def _release_owner(self):
        if self._owner_fd is not None:
            fd, self._owner_fd = self._owner_fd, None
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def _save(self):
        fsutil.atomic_write(self.registry_path, json.dumps({"version": 1,
            "runs": list(self.records.values())[-MAX_RUNS:]}, ensure_ascii=False, indent=2).encode())

    def _package(self, record: dict) -> Path:
        return _confined(self.workspace, record["path"])

    def _id(self, path: Path) -> str:
        return hashlib.sha256(str(path.relative_to(self.workspace)).encode()).hexdigest()[:20]

    def _get(self, ident: str) -> dict:
        with self.lock:
            row = self.records.get(ident)
            if row is None:
                self._discover()
                row = self.records.get(ident)
            if row is None:
                raise APIError("Run not found.", 404)
            return dict(row)

    def _json(self, path: Path, warnings: list[str] | None = None) -> dict:
        try:
            if not path.exists():
                return {}
            raw, size = _read(path, JSON_LIMIT)
            if size > JSON_LIMIT:
                raise ValueError("larger than the 4 MiB preview limit")
            value = _json_loads(raw)
            if not isinstance(value, dict):
                raise ValueError("expected a JSON object")
            return value
        except (OSError, ValueError, VeriSlopError) as exc:
            if warnings is not None:
                warnings.append(f"{path.name} is unavailable or incomplete: {str(exc)[:200]}")
            return {}

    def _text(self, path: Path, limit: int = LOG_LIMIT, *, tail: bool = False) -> str:
        try:
            raw, size = _read(path, limit, tail=tail)
            text = raw.decode("utf-8", "replace")
            if size > limit:
                text = ("[… earlier content omitted …]\n" + text if tail else text + "\n[… preview truncated …]")
            return text
        except (OSError, ValueError, VeriSlopError):
            return ""

    def _artifact_path(self, package: Path, meta: dict, key: str, default: str) -> Path:
        value = _object(meta.get("artifacts")).get(key, default)
        if not isinstance(value, str):
            raise APIError("Invalid artifact path in package metadata.")
        return _confined(package, value)

    def _discover(self):
        if not self.runs_dir.is_dir():
            return
        # Deliberately one directory deep: historical validation trees can be huge.
        count = 0
        registered_paths = {row["path"] for row in self.records.values()}
        for path in self.runs_dir.iterdir():
            count += 1
            if count > 1000:
                break
            if path.is_symlink() or not path.is_dir() or not (path / "package.json").is_file():
                continue
            ident = self._id(path)
            if str(path.relative_to(self.workspace)) in registered_paths:
                continue
            if ident not in self.records:
                if len(self.records) >= MAX_RUNS:
                    break
                self.records[ident] = {"id": ident, "path": str(path.relative_to(self.workspace)),
                    "owned": False, "process_status": "NOT_OWNED"}

    def _events(self, package: Path) -> list[dict]:
        try:
            raw, size = _read(_confined(package, "events.jsonl"), PREVIEW_LIMIT, tail=True)
            lines = raw.splitlines()
            if size > PREVIEW_LIMIT:
                lines = lines[1:]
            events = []
            for line in lines[-400:]:
                try:
                    value = _json_loads(line)
                    if isinstance(value, dict):
                        events.append(value)
                except (ValueError, UnicodeDecodeError):
                    continue  # Polling can observe an unfinished final append.
            return events
        except (OSError, ValueError, VeriSlopError):
            return []

    def _summary(self, row: dict, report: dict | None = None, meta: dict | None = None) -> dict:
        package = self._package(row)
        meta = self._json(package / "package.json") if meta is None else meta
        if report is None:
            try:
                report = self._json(self._artifact_path(package, meta, "report", "report.json"))
            except APIError:
                report = {}
        params = _object(meta.get("run_parameters"))
        requested = _object(meta.get("requested"))
        tier_info = _object(report.get("tier"))
        def setting(name: str):
            values = (tier_info.get("requested" if name == "tier" else name),
                      params.get(name), requested.get(name), row.get(name))
            return next((value for value in values if value is not None), None)
        process_status = row.get("process_status", "NOT_OWNED")
        live = process_status in ("RUNNING", "CANCELLING") and row["id"] in self.processes
        status = (process_status if live else report.get("terminal_status") or row.get("result_status")
                  or ("INTERRUPTED" if process_status == "INTERRUPTED" else "NO_REPORT"))
        try:
            prompt = self._text(self._artifact_path(package, meta, "prompt", "request/prompt.txt"), 1000)
        except APIError:
            prompt = ""
        if not prompt and row.get("job"):
            prompt = self._text(_confined(self.jobs_dir, row["job"] + "/prompt.txt"), 1000)
        events = self._events(package)
        return {"id": row["id"], "run_id": meta.get("run_id", row.get("run_id", package.name)),
            "path": str(package.relative_to(self.workspace)), "created_at": meta.get("created_at", row.get("created_at")),
            "status": status, "process_status": process_status, "historical": not live,
            "tier": setting("tier"), "target": setting("target"),
            "require_state": setting("require_state"), "endpoint": setting("endpoint"),
            "prompt": prompt, "mechanical_status": report.get("mechanical_status"),
            "release_status": report.get("release_status"), "owned": row["id"] in self.processes,
            "phase": events[-1].get("phase", "") if events else "",
            "exit_code": row.get("exit_code"), "mode": row.get("mode", "imported")}

    def meta(self) -> dict:
        from .leanbridge import DEFAULT_TOOLCHAIN
        lean_prefix = Path(os.environ.get("VERISLOP_LEAN_PREFIX") or
            (Path(os.environ.get("ELAN_HOME", Path.home() / ".elan")) / "toolchains" /
             DEFAULT_TOOLCHAIN.replace("/", "--").replace(":", "---")))
        configs, config_details = [], []
        candidates = [self.workspace / "verislop.json"]
        examples = self.workspace / "examples"
        if examples.is_dir() and not examples.is_symlink():
            candidates.extend(sorted(examples.glob("*config*.json"))[:30])
        for p in candidates:
            if p.is_file() and not p.is_symlink():
                name = str(p.relative_to(self.workspace))
                configs.append(name)
                details = {"path": name, "valid": False}
                try:
                    from . import canonical, schemas
                    raw, size = _read(p, JSON_LIMIT)
                    if size > JSON_LIMIT:
                        raise ValueError("configuration exceeds preview limit")
                    conf = canonical.loads(raw)
                    if isinstance(conf, dict) and not schemas.validate("review-config", conf):
                        details.update(valid=True, tier=conf.get("bridge_tier"), endpoint=conf.get("endpoint"))
                except (OSError, ValueError, VeriSlopError):
                    pass
                config_details.append(details)
        return {"workspace": str(self.workspace), "runs_dir": str(self.runs_dir.relative_to(self.workspace)),
            "token": self.token, "version": __version__, "configs": configs, "config_details": config_details, "tiers": TIERS,
            "example_prompt": self._text(EXAMPLES / "request.txt"),
            "environment": {"python": sys.version.split()[0], "platform": sys.platform,
                "lean_toolchain": DEFAULT_TOOLCHAIN, "lean_installed": (lean_prefix / "bin/lean").is_file(),
                "bubblewrap_installed": shutil.which("bwrap") is not None,
                "note": "Availability only; the CLI checks actual prerequisites when a run starts."}}

    def list_runs(self) -> dict:
        with self.lock:
            self._discover()
            rows = [dict(row) for row in self.records.values()]
        summaries = []
        for row in rows:
            try:
                summaries.append(self._summary(row))
            except (OSError, ValueError, VeriSlopError):
                continue
        return {"runs": sorted(summaries, key=lambda r: r.get("created_at") or "", reverse=True)}

    @staticmethod
    def _request_values(data: dict) -> dict:
        """Validate an editable draft without resolving a model or configuration."""
        if not isinstance(data, dict):
            raise APIError("Request must be a JSON object.")
        prompt = data.get("prompt")
        try:
            valid_prompt = isinstance(prompt, str) and bool(prompt.strip()) and len(prompt.encode("utf-8")) <= 64000
        except UnicodeError:
            valid_prompt = False
        if not valid_prompt:
            raise APIError("Enter a software request of 1–64000 UTF-8 bytes.")
        config = data.get("config", "")
        if not isinstance(config, str) or len(config) > 4096 or "\x00" in config:
            raise APIError("Configuration must be a path of at most 4096 characters, or empty.")
        try:
            config.encode("utf-8")
        except UnicodeError:
            raise APIError("Configuration path must be valid UTF-8.") from None
        tier = data.get("tier", 0)
        if type(tier) is not int or tier not in (0, 1, 2):
            raise APIError("Only Tier 0, Tier 1 and Tier 2 are supported; no downgrade is performed.")
        budget = data.get("budget_seconds", 0)
        repairs = data.get("repair_rounds", 2)
        if type(budget) is not int or not 0 <= budget <= 604800:
            raise APIError("Proof budget must be 0 (no deadline) or an integer up to 604800 seconds.")
        if type(repairs) is not int or not 0 <= repairs <= 8:
            raise APIError("Repair rounds must be an integer between 0 and 8.")
        return {"prompt": prompt, "config": config, "tier": tier,
                "budget_seconds": budget, "repair_rounds": repairs}

    def _request_path(self, ident: str) -> Path:
        if (not isinstance(ident, str) or len(ident) != 28 or not ident.startswith("req-")
                or any(c not in "0123456789abcdef" for c in ident[4:])):
            raise APIError("Request not found.", 404)
        return _confined(self.workspace, self.requests_dir / (ident + ".json"))

    def _request_files(self) -> list[Path]:
        directory = _confined(self.workspace, self.requests_dir)
        files = []
        for count, path in enumerate(directory.iterdir()):
            if count >= 1000:
                raise APIError("Request directory exceeds its bounded catalog size.", 409)
            if path.name.startswith("req-") and path.suffix == ".json":
                files.append(path)
        if len(files) > MAX_REQUESTS:
            raise APIError("Request catalog exceeds its 200-request limit.", 409)
        return sorted(files)

    def _load_request(self, ident: str) -> dict:
        path = self._request_path(ident)
        if not path.exists():
            raise APIError("Request not found.", 404)
        try:
            raw, size = _read(path, REQUEST_LIMIT)
            if size > REQUEST_LIMIT:
                raise ValueError("saved request is too large")
            record = _json_loads(raw)
            values = self._request_values(record)
            if (record.get("id") != ident or record.get("version") != 1
                    or not isinstance(record.get("created_at"), str)
                    or not isinstance(record.get("updated_at"), str)
                    or (record.get("last_run_id") is not None and not isinstance(record["last_run_id"], str))):
                raise ValueError("invalid saved request metadata")
            return {"version": 1, "id": ident, **values, "created_at": record["created_at"],
                    "updated_at": record["updated_at"], "last_run_id": record.get("last_run_id")}
        except (OSError, ValueError, VeriSlopError):
            raise APIError("Saved request is incomplete or invalid; its existing bytes have been preserved.", 409) from None

    def _write_request(self, record: dict):
        path = self._request_path(record["id"])
        raw = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
        if len(raw) > REQUEST_LIMIT:
            raise APIError("Saved request exceeds its storage limit.")
        fsutil.atomic_write(path, raw)

    def list_requests(self) -> dict:
        with self.lock:
            records = [self._load_request(path.stem) for path in self._request_files()]
        rows = [{key: value for key, value in row.items()
                 if key in {"id", "created_at", "updated_at", "tier", "config", "last_run_id"}}
                | {"prompt": row["prompt"][:400]} for row in records]
        return {"requests": sorted(rows, key=lambda row: row["updated_at"], reverse=True)}

    def get_request(self, ident: str) -> dict:
        with self.lock:
            return self._load_request(ident)

    def save_request(self, data: dict, ident: str | None = None) -> dict:
        values = self._request_values(data)
        with self.lock:
            if self.closed:
                raise APIError("Workbench is shutting down.", 503)
            if ident is None:
                if len(self._request_files()) >= MAX_REQUESTS:
                    raise APIError("Request catalog is full (200 requests).", 409)
                while True:
                    ident = "req-" + secrets.token_hex(12)
                    if not self._request_path(ident).exists():
                        break
                created_at, last_run = _now(), None
            else:
                previous = self._load_request(ident)
                created_at, last_run = previous["created_at"], previous["last_run_id"]
            record = {"version": 1, "id": ident, **values, "created_at": created_at,
                      "updated_at": _now(), "last_run_id": last_run}
            self._write_request(record)
            return record

    def launch_request(self, ident: str) -> dict:
        # All draft edits and launches take this same mutex: an edit cannot
        # interleave the loaded snapshot, immutable prompt, and request/run link.
        with self.lock:
            snapshot = self._load_request(ident)
            if not snapshot["config"].strip():
                raise APIError("Add a provider configuration path to this saved request before launching it.")
            return self.launch({**snapshot, "mode": "agents"}, request_snapshot=snapshot)

    def open_run(self, data: dict) -> dict:
        package = _confined(self.workspace, data.get("path", ""))
        meta = self._json(_confined(package, "package.json"))
        if not meta or not isinstance(meta.get("run_id"), str):
            raise APIError("Select a run package containing a readable package.json and run_id.")
        ident = self._id(package)
        with self.lock:
            if self.closed:
                raise APIError("Workbench is shutting down.", 503)
            if ident not in self.records and len(self.records) >= MAX_RUNS:
                raise APIError("Workbench catalog is full; choose a separate workspace.", 409)
            row = self.records.setdefault(ident, {"id": ident,
                "path": str(package.relative_to(self.workspace)), "owned": False, "process_status": "NOT_OWNED"})
            self._save()
        return self._summary(row, meta=meta)

    def launch(self, data: dict, *, request_snapshot: dict | None = None) -> dict:
        mode = data.get("mode", "agents")
        if mode not in ("example", "agents"):
            raise APIError("Choose example or agents mode.")
        tier = data.get("tier", 0)
        if type(tier) is not int or tier not in (0, 1, 2):
            raise APIError("Only Tier 0, Tier 1 and Tier 2 are supported; no downgrade is performed.")
        if mode == "example" and tier != 0:
            raise APIError("The bundled Python example requires Tier 0.")
        budget = data.get("budget_seconds", 0)
        repairs = data.get("repair_rounds", 2)
        if type(budget) is not int or not 0 <= budget <= 604800:
            raise APIError("Proof budget must be 0 (no deadline) or an integer up to 604800 seconds.")
        if type(repairs) is not int or not 0 <= repairs <= 8:
            raise APIError("Repair rounds must be an integer between 0 and 8.")
        config = None
        if mode == "agents":
            prompt = data.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode()) > 64000:
                raise APIError("Enter a software request of 1–64000 UTF-8 bytes.")
            config = _confined(self.workspace, data.get("config", ""))
            try:
                raw, size = _read(config, JSON_LIMIT)
                if size > JSON_LIMIT:
                    raise ValueError("configuration too large")
                from .providers.config import load
                conf = load(config)
                if conf.get("bridge_tier") != tier:
                    raise APIError("Selected tier differs from bridge_tier in the provider configuration.")
                if conf.get("endpoint") and conf["endpoint"] != TIERS[tier]["endpoint"]:
                    raise APIError("Selected endpoint differs from the provider configuration.")
            except APIError:
                raise
            except (OSError, ValueError, VeriSlopError):
                raise APIError("Provider configuration is missing or invalid; check it with verislop providers check.") from None
        else:
            prompt = self._text(EXAMPLES / "request.txt")
            if not prompt:
                raise APIError("Bundled example is unavailable in this installation.")
            required = ("draft.json", "interpretation.json", "formalization/Contract.lean",
                        "formalization/formalization.json", "python/bounded_increment.py", "python/bindings.json")
            if not all((EXAMPLES / path).is_file() for path in required):
                raise APIError("Bundled example is incomplete; reinstall VeriSlop from a complete distribution.")
        with self.lock:
            if self.closed:
                raise APIError("Workbench is shutting down.", 503)
            if self.processes:
                raise APIError("A workbench run is already active. Wait for it or cancel it first.", 409)
            if len(self.records) >= MAX_RUNS:
                raise APIError("Workbench catalog is full; choose a separate workspace.", 409)
            run_id = "web-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + secrets.token_hex(3)
            package = _confined(self.runs_dir, run_id)
            ident = self._id(package)
            job = _confined(self.jobs_dir, ident)
            job.mkdir()
            prompt_path = job / "prompt.txt"
            fsutil.write_once(prompt_path, prompt.encode("utf-8"))
            if request_snapshot is not None:
                fsutil.write_once(job / "request.json", json.dumps(request_snapshot, ensure_ascii=False,
                                 indent=2).encode("utf-8"))
            selection = TIERS[tier]
            argv = [sys.executable, "-B", "-m", "verislop", "run", "--json", "--non-interactive",
                "--mode", "software", "--runs-dir", str(self.runs_dir), "--run-id", run_id,
                "--prompt-file", str(EXAMPLES / "request.txt" if mode == "example" else prompt_path),
                "--tier", str(tier), "--target", selection["target"], "--endpoint", selection["endpoint"],
                "--require-state", selection["require_state"], "--budget-seconds", str(budget),
                "--repair-rounds", str(repairs)]
            if tier == 2:
                argv.extend(["--backend-version", "0.3", "--no-tests"])
            else:
                argv.append("--require-tests")
            if mode == "example":
                argv.extend(["--request-ref", "examples/request.txt", "--draft-candidate", str(EXAMPLES / "draft.json"),
                    "--ledger-candidate", str(EXAMPLES / "interpretation.json"),
                    "--formalization-candidate", str(EXAMPLES / "formalization"),
                    "--implementation-candidate", str(EXAMPLES / "python")])
            else:
                argv.extend(["--config", str(config)])
            row = {"id": ident, "path": str(package.relative_to(self.workspace)), "run_id": run_id,
                "created_at": _now(), "owned": True, "process_status": "RUNNING", "job": ident,
                "command": argv, "mode": mode, "tier": tier, "target": selection["target"],
                "require_state": selection["require_state"], "endpoint": selection["endpoint"]}
            if request_snapshot is not None:
                row["request_id"] = request_snapshot["id"]
                row["request_updated_at"] = request_snapshot["updated_at"]
                row["request_snapshot_sha256"] = "sha256:" + hashlib.sha256((job / "request.json").read_bytes()).hexdigest()
            self.records[ident] = row
            try:
                self._save()
                if request_snapshot is not None:
                    # The request/run association must be durable before any
                    # potentially billable model process can start. A failed
                    # spawn may leave a link to an inspectable failed-start run.
                    self._write_request({**request_snapshot, "last_run_id": ident})
                with (job / "stdout.log").open("xb") as stdout, (job / "stderr.log").open("xb") as stderr:
                    env = dict(os.environ)
                    env["PYTHONPATH"] = str(REPO) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
                    process = subprocess.Popen(argv, cwd=self.workspace, env=env, stdin=subprocess.DEVNULL,
                        stdout=stdout, stderr=stderr, start_new_session=True)
                self.processes[ident] = process
            except (OSError, APIError, VeriSlopError) as exc:
                row.update(process_status="FINISHED", result_status="INFRASTRUCTURE_FAILURE", launch_error=str(exc))
                try:
                    self._save()
                except (OSError, ValueError, VeriSlopError):
                    pass  # Keep the in-memory failed-start record inspectable.
                raise APIError("Could not persist or start the CLI process. No process was started.", 500) from None
            watcher = threading.Thread(target=self._watch, args=(ident, process), daemon=True)
            self._watchers.append(watcher)
            watcher.start()
            return self._summary(row)

    def _watch(self, ident: str, process):
        code = process.wait()
        with self.lock:
            row = self.records[ident]
            cancelled = row.get("process_status") == "CANCELLING"
            row.update(exit_code=code, finished_at=_now(), process_status="CANCELLED" if cancelled else "FINISHED")
            row["result_status"] = ("INTERRUPTED" if cancelled or code in (-signal.SIGINT, 130) else
                "COMPLETED" if code == 0 else "BLOCKED" if code == 2 else
                "INFRASTRUCTURE_FAILURE" if code == 3 else "FAILED")
            result = self._json(_confined(self.jobs_dir, row["job"] + "/stdout.log"))
            active = _object(result.get("summary")).get("active_package")
            if isinstance(active, str):
                try:
                    package = _confined(self.runs_dir, active)
                    original = row["run_id"]
                    if package.name == original or package.name.startswith(original + "-repair-"):
                        if self._json(package / "package.json").get("run_id") == package.name:
                            row["original_path"] = row["path"]
                            row["path"] = str(package.relative_to(self.workspace))
                except (ValueError, OSError):
                    pass
            self.processes.pop(ident, None)
            try:
                self._save()
            except (OSError, ValueError, VeriSlopError):
                row["persistence_error"] = "Final process status could not be saved; the in-memory status is current."

    def cancel(self, ident: str) -> dict:
        with self.lock:
            row = self.records.get(ident)
            process = self.processes.get(ident)
            if row is None:
                raise APIError("Run not found.", 404)
            if process is None or process.poll() is not None:
                raise APIError("Only an active run started by this server can be cancelled.", 409)
            if row.get("process_status") != "CANCELLING":
                row["process_status"] = "CANCELLING"
                try:
                    self._save()
                except (OSError, ValueError, VeriSlopError):
                    row["persistence_error"] = "Cancellation was requested, but its bookkeeping could not be saved."
                self._signal(process, signal.SIGINT)
                threading.Thread(target=self._escalate, args=(process,), daemon=True).start()
            return self._summary(row)

    @staticmethod
    def _signal(process, sig):
        if process.poll() is None:
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass

    def _escalate(self, process):
        for seconds, sig in ((10, signal.SIGTERM), (3, signal.SIGKILL)):
            try:
                process.wait(timeout=seconds)
                return
            except subprocess.TimeoutExpired:
                self._signal(process, sig)

    def close(self):
        with self.lock:
            self.closed = True
            processes = list(self.processes.items())
        try:
            for ident, process in processes:
                try:
                    self.cancel(ident)
                except APIError:
                    pass
            for _, process in processes:
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self._signal(process, signal.SIGKILL)
                    process.wait(timeout=3)
            # Keep ownership until process monitors finish their final registry
            # writes, so a replacement server cannot race those writes.
            for watcher in self._watchers:
                if watcher is not threading.current_thread():
                    watcher.join(timeout=3)
        finally:
            self._release_owner()

    def _artifacts(self, package: Path) -> tuple[list[dict], bool]:
        items, scanned = [], 0
        if not package.is_dir():
            return items, False
        for directory, dirs, names in os.walk(package, followlinks=False):
            here = Path(directory)
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__"
                              and not (here / d).is_symlink())
            if len(here.relative_to(package).parts) >= 5:
                dirs[:] = []
            for name in sorted(names):
                scanned += 1
                if scanned > 2000 or len(items) >= 350:
                    return items, True
                path = here / name
                if name.startswith(".") or "config" in name.lower() or path.suffix not in TEXT_SUFFIXES:
                    continue
                try:
                    info = path.lstat()
                    if stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                        items.append({"path": path.relative_to(package).as_posix(), "size": info.st_size,
                                      "mtime_ns": str(info.st_mtime_ns)})
                except OSError:
                    continue
        priority = {"report.json": 0, "obligation-view.json": 1, "accepted/accepted-ir.json": 2,
                    "request/prompt.txt": 3, "events.jsonl": 4}
        return sorted(items, key=lambda r: (priority.get(r["path"], 5), r["path"])), False

    def detail(self, ident: str) -> dict:
        row = self._get(ident)
        package = self._package(row)
        warnings: list[str] = []
        if row.get("persistence_error"):
            warnings.append(row["persistence_error"])
        meta = self._json(package / "package.json", warnings)
        def document(key, default):
            try:
                return self._json(self._artifact_path(package, meta, key, default), warnings)
            except APIError as exc:
                warnings.append(str(exc))
                return {}
        report = document("report", "report.json")
        view = document("view", "obligation-view.json")
        accepted = document("accepted_ir", "accepted/accepted-ir.json")
        claim_doc = document("claims", "claims.json")
        statements = {}
        for doc in (claim_doc, accepted, view):
            obs = doc.get("obligations", {})
            if isinstance(obs, list):
                obs = {str(v.get("id", "")): v for v in obs if isinstance(v, dict)}
            if isinstance(obs, dict):
                for oid, value in obs.items():
                    if isinstance(value, dict):
                        statements[oid] = value
        recorded = _object(report.get("obligations")) or _object(view.get("obligations"))
        obligations = []
        for oid, value in recorded.items():
            if not isinstance(value, dict):
                continue
            fields = dict(value)
            fields["id"] = oid
            fields["statement"] = fields.get("statement") or statements.get(oid, {}).get("statement", "")
            outcomes = _object(fields.get("outcomes"))
            if not outcomes:
                outcomes = {m: v.get("outcome") for m, v in _object(fields.get("lifecycle")).items() if isinstance(v, dict)}
            fields["outcomes"] = outcomes
            obligations.append(fields)
        try:
            prompt = self._text(self._artifact_path(package, meta, "prompt", "request/prompt.txt"), PREVIEW_LIMIT)
        except APIError:
            prompt = ""
        stdout = stderr = ""
        if row.get("job"):
            job = _confined(self.jobs_dir, row["job"])
            stdout = self._text(job / "stdout.log", tail=True)
            stderr = self._text(job / "stderr.log", tail=True)
            if not prompt:
                prompt = self._text(job / "prompt.txt", PREVIEW_LIMIT)
        artifacts, truncated = self._artifacts(package)
        if truncated:
            warnings.append("Artifact index is bounded; use a relative artifact path to inspect additional files.")
        warnings.append("Recorded artifacts are historical observations. Opening this page does not reverify them.")
        return {"run": self._summary(row, report, meta), "report": report or None,
            "obligations": obligations, "events": self._events(package), "artifacts": artifacts,
            "prompt": prompt, "stdout": stdout, "stderr": stderr, "command": row.get("command", []), "warnings": warnings}

    def artifact(self, ident: str, value: str) -> dict:
        row = self._get(ident)
        package = self._package(row)
        path = _confined(package, value)
        if path.suffix not in TEXT_SUFFIXES or any(p.startswith(".") for p in path.relative_to(package).parts) or "config" in path.name.lower():
            raise APIError("Only source, report and evidence text artifacts can be previewed.", 415)
        try:
            data, size = _read(path, PREVIEW_LIMIT)
        except (OSError, ValueError, VeriSlopError):
            raise APIError("Artifact is missing or cannot be safely read.", 404) from None
        try:
            content = data.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            if size > len(data) and exc.end == len(data):
                content = data[:exc.start].decode("utf-8", "strict")
            else:
                raise APIError("This artifact is not UTF-8 text.", 415) from None
        return {"path": path.relative_to(package).as_posix(), "content": content,
                "truncated": size > len(data), "size": size}


def make_server(workbench: Workbench, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    if host not in ("127.0.0.1", "localhost"):
        raise APIError("Workbench can bind only to IPv4 loopback (127.0.0.1 or localhost).")
    if type(port) is not int or not 0 <= port <= 65535:
        raise APIError("Port must be an integer between 0 and 65535.")

    class Handler(BaseHTTPRequestHandler):
        server_version = "VeriSlopWorkbench/0.1"

        def log_message(self, _format, *args):
            pass

        def _same_origin(self):
            authority = self.headers.get("Host", "")
            expected = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.server.server_port == 80:
                expected.update({"127.0.0.1", "localhost"})
            if authority not in expected:
                raise APIError("Unexpected Host header.", 403)
            origin = self.headers.get("Origin")
            if origin is not None and origin != "http://" + authority:
                raise APIError("Only same-origin requests are accepted.", 403)
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                raise APIError("Cross-site requests are not accepted.", 403)

        def _send(self, status: int, body: bytes, content_type: str = "application/json; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, data):
            self._send(status, json.dumps(data, ensure_ascii=False).encode())

        def _route(self, mutate: bool = False):
            try:
                self._same_origin()
                url = urlsplit(self.path)
                path = unquote(url.path)
                if mutate:
                    if not secrets.compare_digest(self.headers.get("X-VeriSlop-Token", "").encode("utf-8"), workbench.token.encode("utf-8")):
                        raise APIError("Missing or invalid workbench request token.", 403)
                    if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                        raise APIError("Send an application/json request.", 415)
                    try:
                        size = int(self.headers.get("Content-Length", "0"))
                    except ValueError:
                        raise APIError("Invalid request size.") from None
                    if not 0 < size <= BODY_LIMIT or self.headers.get("Transfer-Encoding"):
                        raise APIError(f"Request body must be between 1 and {BODY_LIMIT} bytes.", 413)
                    self.connection.settimeout(5)
                    data = _json_loads(self.rfile.read(size))
                    if not isinstance(data, dict):
                        raise APIError("Request must be a JSON object.")
                    if path == "/api/runs":
                        return self._json(201, workbench.launch(data))
                    if path == "/api/runs/open":
                        return self._json(200, workbench.open_run(data))
                    if path == "/api/requests":
                        return self._json(201, workbench.save_request(data))
                    pieces = path.split("/")
                    if len(pieces) == 4 and pieces[1:3] == ["api", "requests"]:
                        return self._json(200, workbench.save_request(data, pieces[3]))
                    if len(pieces) == 5 and pieces[1:3] == ["api", "requests"] and pieces[4] == "launch":
                        if data:
                            raise APIError("Launch the saved request with an empty JSON object; edit it first to change its settings.")
                        return self._json(201, workbench.launch_request(pieces[3]))
                    if len(pieces) == 5 and pieces[1:3] == ["api", "runs"] and pieces[4] == "cancel":
                        return self._json(200, workbench.cancel(pieces[3]))
                    raise APIError("Route not found.", 404)
                if path == "/api/meta":
                    return self._json(200, workbench.meta())
                if path == "/api/runs":
                    return self._json(200, workbench.list_runs())
                if path == "/api/requests":
                    return self._json(200, workbench.list_requests())
                pieces = path.split("/")
                if len(pieces) == 4 and pieces[1:3] == ["api", "requests"]:
                    return self._json(200, workbench.get_request(pieces[3]))
                if len(pieces) == 4 and pieces[1:3] == ["api", "runs"]:
                    return self._json(200, workbench.detail(pieces[3]))
                if len(pieces) == 5 and pieces[1:3] == ["api", "runs"] and pieces[4] == "artifact":
                    values = parse_qs(url.query).get("path", [""])
                    return self._json(200, workbench.artifact(pieces[3], values[0]))
                if path.startswith("/api/"):
                    raise APIError("Route not found.", 404)
                asset = _confined(ASSETS, path.lstrip("/") or "index.html")
                if not asset.is_file() or asset.suffix not in (".html", ".js", ".css", ".svg", ".ico", ".woff2"):
                    raise APIError("Page not found.", 404)
                body, size = _read(asset, 4 * 1024 * 1024)
                if size > len(body):
                    raise APIError("Asset is too large.", 413)
                content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
                return self._send(200, body, content_type)
            except APIError as exc:
                self._json(exc.status, {"error": str(exc)})
            except (ValueError, UnicodeError):
                self._json(400, {"error": "Invalid request or incomplete JSON."})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except (OSError, VeriSlopError):
                self._json(500, {"error": "A local file or process is unavailable. Check the workspace and retry."})

        def do_GET(self):
            self._route()

        def do_HEAD(self):
            self._route()

        def do_POST(self):
            self._route(mutate=True)

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.workbench = workbench
    return server


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--runs-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    app = None
    previous_sigterm = None
    shutting_down = False

    def terminate(_signum, _frame):
        # SIGTERM's default exit would bypass finally and orphan the independent
        # CLI process group. Follow the same bounded cleanup as Ctrl-C instead.
        nonlocal shutting_down
        if not shutting_down:
            shutting_down = True
            raise KeyboardInterrupt

    try:
        app = Workbench(args.workspace, args.runs_dir)
        server = make_server(app, args.host, args.port)
        if threading.current_thread() is threading.main_thread():
            previous_sigterm = signal.signal(signal.SIGTERM, terminate)
        print(f"VeriSlop Workbench: http://127.0.0.1:{server.server_port}", flush=True)
        print(f"Workspace: {app.workspace}\nNo model calls occur until you launch a run.", flush=True)
        try:
            server.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    except (OSError, APIError, VeriSlopError) as exc:
        print(f"workbench: {exc}", file=sys.stderr)
        return 2
    finally:
        shutting_down = True
        try:
            if app is not None:
                app.close()
        finally:
            if previous_sigterm is not None:
                signal.signal(signal.SIGTERM, previous_sigterm)


if __name__ == "__main__":
    raise SystemExit(main())
