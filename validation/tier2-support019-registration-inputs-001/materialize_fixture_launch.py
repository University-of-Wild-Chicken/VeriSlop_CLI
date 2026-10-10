"""Record fresh unrelated fixture materialization only; no test/model/view."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False); stream.write("\n")


def main():
    registration = json.loads((HERE / "fixture-materialization-registration.json").read_text())
    if sha(Path(registration["argv"][1])) != registration["source_sha256"] or registration["cwd"] != str(ROOT):
        raise ValueError("Fixture source registration differs")
    directory = HERE / "fixture-materialization-actual-001"
    directory.mkdir()
    started = datetime.now(timezone.utc).isoformat(); tick = time.monotonic_ns()
    stdout, stderr = directory / "stdout.log", directory / "stderr.log"
    with stdout.open("xb") as out, stderr.open("xb") as err:
        child = subprocess.Popen(registration["argv"], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=err)
        write(directory / "invocation.json", {"argv": registration["argv"], "cwd": str(ROOT),
              "pid": child.pid, "launcher_pid": os.getpid(), "started_utc": started,
              "source_sha256": registration["source_sha256"], "timeout_seconds": None})
        code = child.wait()
    write(directory / "actual-process-receipt.json", {"argv": registration["argv"], "cwd": str(ROOT),
          "pid": child.pid, "launcher_pid": os.getpid(), "returncode": code, "timed_out": False,
          "started_utc": started, "completed_utc": datetime.now(timezone.utc).isoformat(),
          "elapsed_nanoseconds": time.monotonic_ns() - tick,
          "stdout": {"path": stdout.relative_to(ROOT).as_posix(), "sha256": sha(stdout), "byte_count": stdout.stat().st_size},
          "stderr": {"path": stderr.relative_to(ROOT).as_posix(), "sha256": sha(stderr), "byte_count": stderr.stat().st_size},
          "models": 0, "VIEW_calls": 0, "task_inputs": False, "qualification_authority": False})
    print(json.dumps({"returncode": code, "materialization_only": True, "models": 0, "VIEW_calls": 0}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
