"""Run the registered unrelated equality controls against installed source.

This producer records observations. Independent readers decide qualification.
No model calls, task inputs, output resampling, or outer process deadline.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXPECTED_SOURCE = "sha256:e539b2c7ab0c6aa2295dad45dc361481240106c678cc0aefbe08eeff6e7b6828"


def digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-root", type=Path, required=True)
    args = parser.parse_args()
    gate = args.qualification_root.absolute()
    if (gate.resolve() != gate or gate.parent != ROOT / "validation"
            or not gate.name.startswith("tier2-support-019-qualification-")):
        raise ValueError("Expected canonical current qualification root")
    sys.path.insert(0, str(ROOT))
    from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
    from verislop import canonical
    frozen = bootstrap.load(gate / "qualification-inputs.json")
    hashes = frozen["source_hashes"]
    def guard():
        for name, expected in hashes.items():
            path = ROOT / name
            if (not path.is_file() or path.is_symlink() or path.resolve() != path.absolute()
                    or digest(path) != expected):
                raise ValueError("Frozen input changed: " + name)
        if canonical.digest_json(bootstrap.source_inventory()) != frozen["source_root"]:
            raise ValueError("Current source inventory changed")
        if digest(ROOT / "verislop/contract_refutation.py") != EXPECTED_SOURCE:
            raise ValueError("Reviewed equality implementation is not installed")
        for name in ("verify_equality.py", "test_candidate_019.py", "test_additional_controls_019.py",
                     "test_revision002_private_and_binding.py", "contract_refutation_candidate.py",
                     "fixture_only_analysis_guard_mutant.py"):
            if hashes.get((HERE / name).relative_to(ROOT).as_posix()) != digest(HERE / name):
                raise ValueError("Equality producer input omitted: " + name)
    guard()
    output = gate / "equality"
    output.mkdir()
    processes, reports = [], {}
    for label, source, env_key in (
            ("original-main", "test_candidate_019.py", "EQUALITY019_RUN"),
            ("original-additional", "test_additional_controls_019.py", "EQUALITY019_ADD_RUN"),
            ("private-binding", "test_revision002_private_and_binding.py", "EQUALITY019_PRIVATE_RUN")):
        argv = [sys.executable, str(HERE / source)]
        environment = dict(os.environ)
        environment.pop("EQUALITY019_CASES", None)
        environment.pop("EQUALITY019_CONTROL", None)
        environment[env_key] = str(output / label)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        start = datetime.now(timezone.utc).isoformat()
        tick = time.monotonic_ns()
        stdout, stderr = output / (label + ".stdout.log"), output / (label + ".stderr.log")
        with stdout.open("xb") as out, stderr.open("xb") as err:
            child = subprocess.Popen(argv, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
                                     stdout=out, stderr=err)
            write(output / (label + ".invocation.json"), {
                "argv": argv, "cwd": str(ROOT), "pid": child.pid, "launcher_pid": os.getpid(),
                "started_utc": start, "timeout_seconds": None,
                "environment_overrides": {env_key: environment[env_key], "PYTHONDONTWRITEBYTECODE": "1"},
                "removed_environment_keys": ["EQUALITY019_CASES", "EQUALITY019_CONTROL"],
                "source_root": frozen["source_root"], "input_root": frozen["input_root"]})
            returncode = child.wait()
        receipt = {"argv": argv, "cwd": str(ROOT), "pid": child.pid, "launcher_pid": os.getpid(),
                   "returncode": returncode, "started_utc": start,
                   "completed_utc": datetime.now(timezone.utc).isoformat(),
                   "elapsed_nanoseconds": time.monotonic_ns() - tick,
                   "timed_out": False, "timeout_seconds": None,
                   "source_root": frozen["source_root"], "input_root": frozen["input_root"],
                   "stdout": {"path": stdout.relative_to(ROOT).as_posix(), "sha256": digest(stdout)},
                   "stderr": {"path": stderr.relative_to(ROOT).as_posix(), "sha256": digest(stderr)}}
        write(output / (label + ".process.json"), receipt)
        processes.append(receipt)
        result_path = output / label / "results.json"
        if result_path.is_file():
            reports[label] = {"path": result_path.relative_to(ROOT).as_posix(), "sha256": digest(result_path)}
        if returncode != 0:
            break
    guard()
    files = {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}
    record = {"format": "verislop.support019-equality-observations/1", "status": "OBSERVED",
              "source_root": frozen["source_root"], "input_root": frozen["input_root"],
              "installed_source_sha256": EXPECTED_SOURCE, "processes": processes,
              "reports": reports, "files": files, "models_called": 0, "task_inputs": False,
              "qualification_authority": False}
    write(output / "equality-result.json", record)
    return 0 if len(processes) == 3 and all(p["returncode"] == 0 for p in processes) else 2


if __name__ == "__main__":
    raise SystemExit(main())
