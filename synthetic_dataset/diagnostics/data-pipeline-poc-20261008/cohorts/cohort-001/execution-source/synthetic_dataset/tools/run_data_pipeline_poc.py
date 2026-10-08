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

from verislop import canonical, fsutil
from verislop.agents import extract_json
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
    forbidden = {"--candidate", "--interpret-candidate", "--formalize-candidate", "--proof-candidate", "--implementation", "--bindings", "--draft", "--ledger"}
    if forbidden.intersection(argv):
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, type=Path, help="New, nonexistent cohort directory")
    args = parser.parse_args(argv)
    cohort = args.cohort.absolute()
    if cohort.exists():
        raise ValueError("Cohort is write-once; preserve prior attempts under their existing IDs")
    prereg = check_preregistration()
    frozen = source_inputs()
    cohort.mkdir(parents=True)
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
    env = {**os.environ, "VERISLOP_CONFIG_HOME": str(profiles.parent)}
    summary = []
    for task in TASKS:
        check_preregistration()
        if source_inputs() != frozen:
            missing = [{"task": name, "status": "BLOCKED", "reason": "INPUT_MUTATION before generation"}
                       for name in TASKS if name not in {row["task"] for row in summary}]
            write_once(cohort / "SUMMARY.json", {"status": "BLOCKED", "runtime_root": canonical.digest_json(frozen),
                       "preregistration_root": prereg["root"], "tasks": [*summary, *missing], "total_tasks": len(TASKS),
                       "verified_tasks": 0, "blocking_reason": "INPUT_MUTATION: cohort invalidated; no prior result is promoted"})
            return 2
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
        with (task_root / "stdout.json").open("xb") as stdout, (task_root / "stderr.log").open("xb") as stderr:
            process = subprocess.run(command, cwd=REPO, env=env, stdout=stdout, stderr=stderr, check=False)
        package = task_root / "runs" / run_id
        # Native repairs can create child run packages; all are retained and audited.
        packages = [Package(path) for path in sorted((task_root / "runs").glob("*")) if (path / "package.json").is_file()]
        try:
            native = canonical.load_file(task_root / "stdout.json")
        except (ValueError, OSError) as exc:
            native = {"status": "INFRASTRUCTURE_FAILURE", "diagnostics": [{"message": f"No parseable native CLI result: {exc}"}]}
        final_ref = native.get("summary", {}).get("active_package") or native.get("summary", {}).get("package") or native.get("artifacts", {}).get("package")
        if final_ref:
            package = Path(final_ref)
            if not package.is_absolute():
                package = REPO / package
        elif packages:
            package = packages[-1].root
        audits = [{"package": str(pkg.root), **origin_audit(pkg, command, frozen)} for pkg in packages]
        write_once(task_root / "origin-audit.json", audits)
        oracle = run_check(package, task) if (package / "package.json").is_file() else {"status": "BLOCKED", "diagnostics": ["No generated package"]}
        write_once(task_root / "independent-oracle.json", oracle)
        status = (oracle["status"] if audits and all(row["status"] == "PASS" for row in audits) and source_inputs() == frozen else "BLOCKED")
        if native.get("status") == "INFRASTRUCTURE_FAILURE" and oracle["status"] != "VERIFIED" and source_inputs() == frozen:
            status = "INFRASTRUCTURE_FAILURE"
        row = {"task": task, "status": status, "cli_exit": process.returncode, "package": str(package),
               "native_status": native.get("status"), "independent_cases_passed": oracle.get("passed_cases", 0),
               "independent_cases": oracle.get("distinct_cases", 160), "observations": oracle.get("observations", 0),
               "provider_calls": sum(a["provider_calls"] for a in audits), "origin_audit_passed": bool(audits) and all(a["status"] == "PASS" for a in audits)}
        write_once(task_root / "result.json", row)
        summary.append(row)
        print(canonical.dumps(row).decode(), flush=True)
    verified = sum(row["status"] == "VERIFIED" for row in summary)
    write_once(cohort / "SUMMARY.json", {"status": "VERIFIED" if verified == len(TASKS) else "INFRASTRUCTURE_FAILURE" if any(row["status"] == "INFRASTRUCTURE_FAILURE" for row in summary) else "BLOCKED",
               "runtime_root": canonical.digest_json(frozen), "preregistration_root": prereg["root"], "tasks": summary,
               "verified_tasks": verified, "total_tasks": len(TASKS), "completed_at_utc": datetime.now(timezone.utc).isoformat(),
               "assurance": "Tier 0 TESTED only, plus finite independent request cases and recorded-origin audit"})
    return 0 if verified == len(TASKS) else 2


if __name__ == "__main__":
    raise SystemExit(main())
