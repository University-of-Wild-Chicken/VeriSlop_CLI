"""Execute one explicitly registered process, retaining actual facts and guards."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import time

ROOT = Path(__file__).absolute().parents[2]


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def ref(path):
    assert path.is_file() and not path.is_symlink() and path.resolve() == path.absolute()
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(raw), "byte_count": len(raw)}


def guard(files):
    assert type(files) is dict and files
    actual = {name: ref(ROOT / name) for name in files}
    assert actual == files
    return actual


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", required=True)
    args = parser.parse_args()
    registration_path = (ROOT / args.registration).absolute()
    registration_identity = ref(registration_path)
    registration = json.loads(registration_path.read_bytes())
    assert registration["timeout_seconds"] is None
    assert type(registration["accepted_exit_code"]) is int and registration["accepted_exit_code"] == 0
    argv, cwd, environment = registration["argv"], registration["cwd"], registration["environment"]
    assert type(argv) is list and argv and all(type(value) is str for value in argv)
    assert cwd == str(ROOT) and type(environment) is dict
    output = (ROOT / registration["output_directory"]).absolute()
    assert output.resolve() == output and output.is_relative_to(ROOT / "validation")
    output.mkdir(exist_ok=False)
    before = guard(registration["source_guards"])
    stdout_path, stderr_path = output / "stdout.log", output / "stderr.log"
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t = time.monotonic()
    env = dict(os.environ)
    env.update(environment)
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr)
        write(output / "started.json", {"argv": argv, "cwd": cwd, "pid": process.pid,
                                         "started_utc": started, "registration": registration_identity})
        code = process.wait()
    after = {name: ref(ROOT / name) for name in before}
    receipt = {"format": "verislop.support019-registered-actual-process-receipt/1",
               "registration": registration_identity, "argv": argv, "cwd": cwd,
               "registered_environment": environment, "pid": process.pid, "returncode": code,
               "started_utc": started, "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "wall_seconds": time.monotonic() - t, "timeout_seconds": None, "timed_out": False,
               "stdout": ref(stdout_path), "stderr": ref(stderr_path), "before": before, "after": after,
               "frozen_inputs_unchanged": before == after,
               "qualification_authority": False, "activation_authority": False,
               "task_TESTED_authority": False, "scope": registration["scope"],
               "peak_memory": None, "cpu_time": None}
    write(output / "actual-process-receipt.json", receipt)
    assert ref(registration_path) == registration_identity
    assert before == after and before
    print(json.dumps({"returncode": code, "actual_pid": process.pid,
                      "receipt": ref(output / "actual-process-receipt.json"),
                      "stdout": receipt["stdout"], "stderr": receipt["stderr"],
                      "scope": receipt["scope"]}, sort_keys=True), flush=True)
    return code if code >= 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
