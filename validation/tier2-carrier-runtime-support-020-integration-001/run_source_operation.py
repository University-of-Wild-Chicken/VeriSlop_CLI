"""Finite registered candidate-source operation, with no outer time limit."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def guards(spec):
    actual = {}
    for name, expected in spec["guards"].items():
        path = ROOT / name
        assert path.is_file() and not path.is_symlink() and path.resolve() == path.absolute()
        actual[name] = sha(path.read_bytes())
        assert actual[name] == expected, "SOURCE_GUARD_CHANGED: " + name
    return actual


def main():
    registration = Path(sys.argv[1]).absolute()
    assert registration.parent == HERE
    spec = json.loads(registration.read_bytes())
    assert spec["format"] == "verislop.support020-source-operation/1"
    command = spec["command"]
    assert command[:3] == ["/usr/bin/python3.12", "-I", "-B"] and len(command) == 4
    assert Path(command[3]).parent == HERE
    before = guards(spec)
    output = HERE / spec["output_directory"]
    assert output.parent == HERE and not output.exists()
    output.mkdir()
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    assert type(process.returncode) is int
    (output / "stdout.log").write_bytes(stdout)
    (output / "stderr.log").write_bytes(stderr)
    after = guards(spec)
    receipt = {"format": "verislop.support020-source-process-receipt/1",
        "registration": {"path": registration.relative_to(ROOT).as_posix(), "sha256": sha(registration.read_bytes())},
        "wrapper_pid": os.getpid(), "pid": process.pid, "integer_exit_status": process.returncode,
        "command": command, "before_guards": before, "after_guards": after,
        "all_guards_unchanged": before == after, "outer_timeout": None,
        "stdout": {"path": (output / "stdout.log").relative_to(ROOT).as_posix(), "sha256": sha(stdout)},
        "stderr": {"path": (output / "stderr.log").relative_to(ROOT).as_posix(), "sha256": sha(stderr)},
        "scope": "SOURCE_ONLY_CANDIDATE_NO_QUALIFICATION"}
    (output / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"pid": process.pid, "wrapper_pid": os.getpid(), "integer_exit_status": process.returncode,
                      "guard_count": len(before), "all_guards_unchanged": before == after,
                      "receipt": (output / "receipt.json").relative_to(ROOT).as_posix()}))
    raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
