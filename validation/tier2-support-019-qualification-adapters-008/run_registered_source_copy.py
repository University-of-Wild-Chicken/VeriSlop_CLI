"""Execute only the registered five-group source checker, retaining actual evidence."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def main():
    registration_path = HERE / "CONTROL_REGISTRATION_BEFORE_EXECUTION.json"
    registration = json.loads(registration_path.read_bytes())
    output = HERE / "source-copy-process-002"
    output.mkdir()
    before = {name: sha((ROOT / name).read_bytes()) for name in registration["guards"]}
    if not before or before != registration["guards"]:
        raise ValueError("REGISTERED_SOURCE_GUARD_MISMATCH")
    with (output / "stdout.log").open("wb") as stdout, (output / "stderr.log").open("wb") as stderr:
        process = subprocess.Popen(registration["command"], cwd=ROOT, stdout=stdout, stderr=stderr)
        status = process.wait()
    after = {name: sha((ROOT / name).read_bytes()) for name in registration["guards"]}
    receipt = {"format": "verislop.support020-adapters008-source-copy-process/1", "registration": {"path": registration_path.relative_to(ROOT).as_posix(), "sha256": sha(registration_path.read_bytes())}, "command": registration["command"], "cwd": str(ROOT), "pid": process.pid, "wrapper_pid": os.getpid(), "integer_exit_status": status, "outer_timeout": None, "before_guards": before, "after_guards": after, "all_guards_unchanged": before == after == registration["guards"], "qualification_authority": False}
    for name in ("stdout", "stderr"):
        path = output / (name + ".log")
        receipt[name] = {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path.read_bytes()), "byte_count": path.stat().st_size}
    (output / "actual-process-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"pid": process.pid, "wrapper_pid": os.getpid(), "integer_exit_status": status, "guard_count": len(before), "all_guards_unchanged": receipt["all_guards_unchanged"], "receipt": (output / "actual-process-receipt.json").relative_to(ROOT).as_posix()}), flush=True)
    if status != 0 or not receipt["all_guards_unchanged"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
