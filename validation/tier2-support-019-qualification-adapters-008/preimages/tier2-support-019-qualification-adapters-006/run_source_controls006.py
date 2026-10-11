"""Run registered unrelated development controls; no qualification execution."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def main():
    registration_path = HERE / "source-controls-registration-006.json"
    registration_bytes = registration_path.read_bytes()
    registration = json.loads(registration_bytes)
    if registration["execution_scope"] != "UNRELATED_SOURCE_DEVELOPMENT_ONLY" or registration["qualification_authority"] is not False:
        raise ValueError("source development boundary required")
    def observe():
        actual = {path: sha((ROOT / path).read_bytes()) for path in registration["source_hashes"]}
        if actual != registration["source_hashes"]:
            raise ValueError("source input hash mismatch")
        if registration_path.read_bytes() != registration_bytes:
            raise ValueError("registration mutation")
        return actual
    before = observe()
    environment = registration["environment"]
    argv = registration["argv"]
    if argv != [sys.executable, "-B", str(HERE / "test_author_reconstruction_source.py")]:
        raise ValueError("unregistered source control command")
    stdout_path = HERE / "source-controls-006.stdout.bin"
    stderr_path = HERE / "source-controls-006.stderr.bin"
    receipt_path = HERE / "source-controls-actual-receipt-006.json"
    if any(path.exists() for path in (stdout_path, stderr_path, receipt_path)):
        raise ValueError("source receipt overwrite prohibited")
    started = time.time()
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        process = subprocess.Popen(argv, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr)
        actual_pid = process.pid
        exit_code = process.wait()
    after = observe()
    receipt = {"format": "verislop.support019-source-development-receipt/1", "registration": {"path": str(registration_path.relative_to(ROOT)), "sha256": sha(registration_bytes)}, "execution_scope": "UNRELATED_SOURCE_DEVELOPMENT_ONLY", "qualification_authority": False, "runtime_claims_evaluated": 0, "actual_models": 0, "actual_VIEWs": 0, "actual_task_runs": 0, "actual_Lean_runs": 0, "actual_qualification_verifier_runs": 0, "argv": argv, "cwd": str(ROOT), "environment": environment, "actual_child_pid": actual_pid, "exit_code": exit_code, "duration_seconds": time.time() - started, "python_version": sys.version, "before": before, "after": after, "logs": {"stdout": {"path": str(stdout_path.relative_to(ROOT)), "sha256": sha(stdout_path.read_bytes()), "byte_count": stdout_path.stat().st_size}, "stderr": {"path": str(stderr_path.relative_to(ROOT)), "sha256": sha(stderr_path.read_bytes()), "byte_count": stderr_path.stat().st_size}}, "status": "SOURCE_CONTROLS_EXIT_ZERO" if type(exit_code) is int and exit_code == 0 else "SOURCE_CONTROLS_FAILED", "hidden_tool_envelope": "UNAVAILABLE", "semantic_consumption": "UNATTESTED"}
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"actual_child_pid": actual_pid, "exit_code": exit_code, "receipt": str(receipt_path.relative_to(ROOT)), "source_hash_count": len(before), "registered_test_count": registration["test_count"], "runtime_claims_evaluated": 0}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
