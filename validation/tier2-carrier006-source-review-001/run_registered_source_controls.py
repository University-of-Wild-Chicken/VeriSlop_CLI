"""Run only the registered independent source controls, preserving observations."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def identity(path):
    raw = path.read_bytes()
    return {"sha256": "sha256:" + hashlib.sha256(raw).hexdigest(), "byte_count": len(raw)}


def main():
    registration_path = HERE / "registration-before-control-execution.json"
    registration_raw = registration_path.read_bytes()
    registration = json.loads(registration_raw)
    before = {name: identity(ROOT / name) for name in registration["source_guards"]}
    if not before or before != registration["source_guards"]:
        raise RuntimeError("REGISTERED_SOURCE_GUARD_MISMATCH")
    process = subprocess.Popen(registration["argv"], cwd=registration["cwd"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    (HERE / "independent-controls.stdout.log").write_bytes(stdout)
    (HERE / "independent-controls.stderr.log").write_bytes(stderr)
    after = {name: identity(ROOT / name) for name in registration["source_guards"]}
    record = {"format": "verislop.independent-source-control-actual-process/1",
              "scope": "SOURCE_ONLY_NO_RUNTIME_QUALIFICATION_OR_ACTIVATION",
              "runner_pid": os.getpid(), "pid": process.pid,
              "argv": registration["argv"], "cwd": registration["cwd"],
              "integer_returncode": process.returncode,
              "registration": {"path": registration_path.relative_to(ROOT).as_posix(),
                               **identity(registration_path)},
              "before": before, "after": after,
              "nonempty_guards_unchanged": bool(before) and before == after,
              "stdout": {"path": (HERE / "independent-controls.stdout.log").relative_to(ROOT).as_posix(),
                         **identity(HERE / "independent-controls.stdout.log")},
              "stderr": {"path": (HERE / "independent-controls.stderr.log").relative_to(ROOT).as_posix(),
                         **identity(HERE / "independent-controls.stderr.log")},
              "model_calls": 0, "VIEW_calls": 0, "Lean_calls": 0,
              "qualification_calls": 0, "native_calls": 0, "task_calls": 0,
              "qualification_authority": False, "activation_authority": False}
    (HERE / "independent-controls-actual-receipt.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"pid": process.pid, "integer_returncode": process.returncode,
                      "guard_count": len(before), "nonempty_guards_unchanged": record["nonempty_guards_unchanged"]}))
    print(stdout.decode("utf-8", "strict"), end="")
    print(stderr.decode("utf-8", "strict"), end="")
    if process.returncode or before != after:
        raise SystemExit(process.returncode or 1)


if __name__ == "__main__":
    main()
