"""One native strict-CLI attempt for each preregistered task, with immutable receipts.

No candidate flags, model-generation deadlines, answer injection or hidden-test feedback.
All failures are retained. A source mutation blocks the cohort rather than rescoring it.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

from verislop import canonical, fsutil, recovery
from verislop.agents import extract_json
from verislop.errors import VeriSlopError
from verislop.package import Package
from synthetic_dataset.tools.check_data_pipeline_poc import PROTOCOL, REPO, check_preregistration, run_check
from synthetic_dataset.tools.data_pipeline_oracle import TASKS


def source_inputs() -> dict[str, str]:
    paths = {REPO / "pyproject.toml", REPO / "lean-toolchain"}
    paths.update((REPO / "verislop").rglob("*.py"))
    paths.update((REPO / "verislop/lean").rglob("*.lean"))
    paths.update((REPO / "formal").rglob("*.lean"))
    paths.update((REPO / "schemas").glob("*.json"))
    paths.update((REPO / "policies").glob("*.json"))
    paths.update(REPO / "synthetic_dataset/tools" / name for name in
                 ("run_data_pipeline_poc.py", "check_data_pipeline_poc.py", "data_pipeline_oracle.py", "check_reservation_poc.py"))
    return {path.relative_to(REPO).as_posix(): canonical.digest_file(path) for path in sorted(paths) if path.is_file()}


def write_once(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical.dumps(data))


def origin_audit(pkg: Package, argv: list[str], frozen_inputs: dict[str, str]) -> dict[str, Any]:
    issues, transcript_rows = [], []
    forbidden = {"--candidate", "--interpret-candidate", "--formalize-candidate", "--proof-candidate", "--implementation", "--bindings", "--draft", "--ledger",
                 "--draft-candidate", "--ledger-candidate", "--formalization-candidate", "--implementation-candidate", "--bindings-candidate"}
    options = {arg.split("=", 1)[0] for arg in argv}
    if forbidden.intersection(options) or any(arg.startswith("--bridge-") for arg in options):
        issues.append("Supplied positive artifact argument")
    if source_inputs() != frozen_inputs:
        issues.append("INPUT_MUTATION: frozen runtime or verifier changed")
    installed = canonical.load_file(PROTOCOL / "qwen-config.json")["agents"]["author"]
    expected_digest = installed["model_identity"]["model_digest_sha256"]
    calls = []
    for path in sorted(pkg.root.rglob("transcripts/*.json")):
        entry = canonical.load_file(path)
        calls.append(entry)
        transcript_rows.append({"path": path.relative_to(pkg.root).as_posix(), "hash": canonical.digest_file(path),
                                "purpose": entry.get("purpose"), "error": entry.get("error")})
        if entry.get("system_sha256") != canonical.digest(entry.get("system", "").encode()) or entry.get("user_sha256") != canonical.digest(entry.get("user", "").encode()):
            issues.append("Transcript prompt digest mismatch")
        if entry.get("response") is not None and (entry.get("requested_model") != installed["model_ref"]
                or entry.get("returned_model") != installed["model_ref"] or entry.get("model_digest_sha256") != expected_digest):
            issues.append("Model identity mismatch")
        if any(marker in entry.get("user", "") for marker in ("expected_wire", "data-pipeline-request-oracle", "withheld/", "PREREGISTRATION.json")):
            issues.append("Withheld evaluation material in an outbound model prompt")
    if not calls:
        issues.append("No native provider transcript")
    proposal = pkg.path("contract") / "candidate" / "proposal.lean"
    if proposal.is_file():
        sources = []
        for entry in calls:
            try:
                obj = extract_json(entry.get("response") or "")
                if isinstance(obj, dict) and isinstance(obj.get("lean_source"), str):
                    sources.append(obj["lean_source"].encode())
            except ValueError:
                pass
        if proposal.read_bytes() not in sources:
            issues.append("Formalization proposal bytes have no exact native response origin")
    implemented = fsutil.manifest_tree(pkg.path("implementation"), "implementation") if pkg.path("implementation").is_dir() else []
    matches = []
    if implemented:
        actual = {path.relative_to(pkg.path("implementation")).as_posix(): path.read_bytes()
                  for path in pkg.path("implementation").rglob("*") if path.is_file()}
        for row, entry in zip(transcript_rows, calls):
            try:
                obj = extract_json(entry.get("response") or "")
                if isinstance(obj, dict) and isinstance(obj.get("files"), dict) and all(isinstance(v, str) for v in obj["files"].values()):
                    if actual == {key: value.encode() for key, value in obj["files"].items()}:
                        matches.append(row["path"])
            except ValueError:
                pass
        if not matches:
            issues.append("Implementation bytes have no exact complete native proposal origin")
    attempts = pkg.path("contract") / "proofs" / "attempts.jsonl"
    if attempts.is_file():
        for line in attempts.read_bytes().splitlines():
            record = canonical.loads(line)
            if record.get("generator") == "candidate_file":
                issues.append("Proof source supplied manually")
    return {"status": "PASS" if not issues else "BLOCK", "issues": sorted(set(issues)),
            "transcripts": transcript_rows, "provider_calls": len(calls), "native_implementation_origins": matches,
            "runtime_root": canonical.digest_json(frozen_inputs), "scope": "Recorded origin and frozen-byte checks; privileged host and transcript fidelity are trusted"}


def active_package(task_root: Path, task: str, native: dict[str, Any], packages: list[Package]) -> Path:
    """A CLI reference must name this invocation's exact validated native repair chain."""
    runs = task_root / "runs"
    run_id = task.lower()
    root = Package(runs / run_id, resolve_root=False)
    if root.root.is_symlink() or root.root.resolve() != root.root or not root.exists() or root.run_id != run_id:
        raise ValueError("Missing or mismatched current-task native root package")
    selected, rounds, _ = recovery.resolve_active(root)
    expected = {root.root} | {runs.absolute() / row["package"] for row in rounds}
    actual = {pkg.root for pkg in packages}
    if actual != expected or any(pkg.root.is_symlink() or pkg.root.resolve() != pkg.root for pkg in packages):
        raise ValueError("Native package inventory differs from this invocation's validated repair lineage")
    refs = [native.get("summary", {}).get(key) for key in ("active_package", "package")]
    refs.append(native.get("artifacts", {}).get("package"))
    refs = [ref for ref in refs if ref is not None]
    if not refs or any(not isinstance(ref, str) or not ref for ref in refs):
        raise ValueError("Native CLI result has no exact active package reference")
    for ref in refs:
        path = Path(ref)
        path = path.absolute() if path.is_absolute() else (REPO / path).absolute()
        if path != selected.root or path not in actual:
            raise ValueError("Native active package is outside the current task's audited repair lineage")
    return selected.root


def task_status(native: dict[str, Any], cli_exit: int | None, oracle: dict[str, Any],
                audits: list[dict[str, Any]], *, bound: bool, unchanged: bool) -> str:
    if not unchanged:
        return "BLOCKED"
    if (bound and native.get("status") == "PASS" and cli_exit == 0 and oracle.get("status") == "VERIFIED"
            and audits and all(row.get("status") == "PASS" for row in audits)):
        return "VERIFIED"
    if native.get("status") == "INFRASTRUCTURE_FAILURE" or (bound and oracle.get("status") == "INFRASTRUCTURE_FAILURE"):
        return "INFRASTRUCTURE_FAILURE"
    return "BLOCKED"


def _seal(cohort: Path, rows: list[dict[str, Any]], frozen: dict[str, str] | None,
          prereg: dict[str, Any] | None, *, reason: str | None = None) -> int:
    by_task = {row["task"]: row for row in rows}
    summary = []
    for task in TASKS:
        if task in by_task:
            row = dict(by_task[task])
            if reason:
                row.update(retained_result_status=row["status"], status="BLOCKED", cohort_blocking_reason=reason)
        else:
            row = {"task": task, "status": "BLOCKED", "reason": reason or "Task did not produce a result",
                   "cli_exit": None, "native_status": None, "package": None,
                   "independent_cases_passed": 0, "independent_cases": 160, "observations": 0,
                   "provider_calls": 0, "origin_audit_passed": False}
            write_once(cohort / task / "result.json", row)
        summary.append(row)
    verified = sum(row["status"] == "VERIFIED" for row in summary)
    status = ("BLOCKED" if reason else "VERIFIED" if verified == len(TASKS) else
              "INFRASTRUCTURE_FAILURE" if any(row["status"] == "INFRASTRUCTURE_FAILURE" for row in summary) else "BLOCKED")
    write_once(cohort / "SUMMARY.json", {"status": status,
        "runtime_root": canonical.digest_json(frozen) if frozen is not None else None,
        "preregistration_root": prereg.get("root") if prereg else None, "tasks": summary,
        "verified_tasks": verified, "total_tasks": len(TASKS), "blocking_reason": reason,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "assurance": "Tier 0 TESTED only, plus finite independent request cases and recorded-origin audit"})
    return 0 if verified == len(TASKS) else 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, type=Path, help="New, nonexistent cohort directory")
    args = parser.parse_args(argv)
    cohort = args.cohort.absolute()
    if cohort.exists() or cohort.is_symlink():
        raise ValueError("Cohort is write-once; preserve prior attempts under their existing IDs")
    cohort.mkdir(parents=True)
    prereg, frozen, summary = None, None, []
    caught = (VeriSlopError, OSError, ValueError, KeyError, TypeError, AttributeError)
    try:
        prereg = check_preregistration()
        frozen = source_inputs()
        for rel in frozen:
            target = cohort / "execution-source" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((REPO / rel).read_bytes())
        write_once(cohort / "source-freeze.json", {"format": "verislop.data-pipeline-source-freeze/0.1",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(), "files": frozen,
            "root": canonical.digest_json(frozen), "preregistration_root": prereg["root"], "tasks": list(TASKS)})
        profiles = cohort / "config-home" / "endpoint-profiles.json"
        profiles.parent.mkdir()
        profiles.write_bytes((PROTOCOL / "endpoint-profiles.json").read_bytes())
    except caught as exc:
        return _seal(cohort, summary, frozen, prereg, reason=f"Pre-generation input failure: {exc}")
    env = {**os.environ, "VERISLOP_CONFIG_HOME": str(profiles.parent)}
    for task in TASKS:
        try:
            if check_preregistration()["root"] != prereg["root"] or source_inputs() != frozen:
                raise ValueError("INPUT_MUTATION: frozen preregistration, runtime or verifier changed")
        except caught as exc:
            return _seal(cohort, summary, frozen, prereg, reason=str(exc))
        task_root = cohort / task
        task_root.mkdir()
        run_id = task.lower()
        command = [sys.executable, "-m", "verislop", "run", "--prompt-file", str(PROTOCOL / f"{task}.txt"),
                   "--request-ref", f"data-pipelines/{task}.txt", "--config", str(PROTOCOL / "qwen-config.json"),
                   "--mode", "software", "--tier", "0", "--target", "python", "--endpoint", "test_campaign",
                   "--require-state", "TESTED", "--require-tests", "--non-interactive", "--budget-seconds", "0",
                   "--repair-rounds", "2", "--seed", "20261008", "--cases", "32", "--run-id", run_id,
                   "--runs-dir", str(task_root / "runs"), "--json"]
        write_once(task_root / "invocation.json", {"argv": command, "cwd": str(REPO),
                   "environment_override": {"VERISLOP_CONFIG_HOME": str(profiles.parent)}, "runtime_root": canonical.digest_json(frozen),
                   "started_at_utc": datetime.now(timezone.utc).isoformat(), "candidate_inputs": []})
        print(f"START {task}", flush=True)
        cli_exit, package, audits = None, None, []
        diagnostics = []
        native = {"status": "INFRASTRUCTURE_FAILURE"}
        oracle = {"status": "BLOCKED", "diagnostics": ["No current native package selected"]}
        bound = False
        try:
            with (task_root / "stdout.json").open("xb") as stdout, (task_root / "stderr.log").open("xb") as stderr:
                process = subprocess.run(command, cwd=REPO, env=env, stdout=stdout, stderr=stderr, check=False)
                cli_exit = process.returncode
            native = canonical.load_file(task_root / "stdout.json")
            if (not isinstance(native, dict) or native.get("status") not in ("PASS", "BLOCKED", "INFRASTRUCTURE_FAILURE")
                    or not isinstance(native.get("summary", {}), dict) or not isinstance(native.get("artifacts", {}), dict)):
                raise ValueError("Native CLI result has no valid stage status")
        except caught as exc:
            native = {"status": "INFRASTRUCTURE_FAILURE", "diagnostics": [{"message": f"Native launch/result failure: {exc}"}]}
            diagnostics.append(f"Native launch/result failure: {exc}")
        try:
            packages = [Package(path, resolve_root=False) for path in sorted((task_root / "runs").glob("*")) if (path / "package.json").is_file()]
            for pkg in packages:
                try:
                    audit = origin_audit(pkg, command, frozen)
                except caught as exc:
                    audit = {"status": "BLOCK", "issues": [str(exc)], "provider_calls": 0}
                audits.append({"package": str(pkg.root), **audit})
            package = active_package(task_root, task, native, packages)
            bound = True
            oracle = run_check(package, task)
        except caught as exc:
            diagnostics.append(f"Current native package/oracle binding failure: {exc}")
        write_once(task_root / "origin-audit.json", audits)
        write_once(task_root / "independent-oracle.json", oracle)
        try:
            unchanged = source_inputs() == frozen and check_preregistration()["root"] == prereg["root"]
        except caught as exc:
            diagnostics.append(f"Frozen input recheck failed: {exc}")
            unchanged = False
        status = task_status(native, cli_exit, oracle, audits, bound=bound, unchanged=unchanged)
        row = {"task": task, "status": status, "cli_exit": cli_exit, "package": str(package) if package else None,
               "native_status": native.get("status"), "independent_cases_passed": oracle.get("passed_cases", 0),
               "independent_cases": 160, "independent_cases_loaded": oracle.get("distinct_cases", 0), "observations": oracle.get("observations", 0),
               "provider_calls": sum(a["provider_calls"] for a in audits), "origin_audit_passed": bool(audits) and all(a["status"] == "PASS" for a in audits),
               "active_package_bound": bound, "diagnostics": diagnostics}
        write_once(task_root / "result.json", row)
        summary.append(row)
        print(canonical.dumps(row).decode(), flush=True)
        if not unchanged:
            return _seal(cohort, summary, frozen, prereg, reason="INPUT_MUTATION: cohort invalidated; no prior result is promoted")
    return _seal(cohort, summary, frozen, prereg)


if __name__ == "__main__":
    raise SystemExit(main())
