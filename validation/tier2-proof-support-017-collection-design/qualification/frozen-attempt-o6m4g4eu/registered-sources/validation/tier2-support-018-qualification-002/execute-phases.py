"""Record actual current qualification processes without model deadlines.

Every command and input is frozen before execution. This launcher records
numeric process completion and log bytes; it does not infer a verifier's result.
"""
from pathlib import Path
import datetime
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
from verislop import canonical


def guard(hashes, external, frozen, spec):
    for name, digest in {**hashes, **external}.items():
        path = ROOT / name
        if (not path.is_file() or path.is_symlink()
                or path.resolve() != path.absolute()
                or canonical.digest_file(path) != digest):
            raise ValueError("Frozen phase input changed: " + name)
    tests = {p.relative_to(ROOT).as_posix(): canonical.digest_file(p)
             for p in sorted((ROOT / "tests").rglob("*.py"))}
    sources = bootstrap.source_inventory()
    if (sources != frozen["source_files"]
            or canonical.digest_json(sources) != spec["source_root"]
            or tests != spec["test_sources"]):
        raise ValueError("Complete current production/test inventory changed between phases")


def main():
    spec = bootstrap.load(HERE / "qualification-specification.json")
    manifest = bootstrap.load(HERE / "qualification-inputs.json")
    frozen = bootstrap.load(HERE / "source-freeze.json")
    hashes = manifest["source_hashes"]
    external = {p.relative_to(ROOT).as_posix(): canonical.digest_file(p)
                for p in (HERE / "qualification-inputs.json", HERE / "preregistration.json")}
    if hashes.get(Path(__file__).relative_to(ROOT).as_posix()) != canonical.digest_file(Path(__file__)):
        raise ValueError("Actual phase launcher is not frozen")
    guard(hashes, external, frozen, spec)
    invocation = HERE / "phase-launcher-invocation.json"
    bootstrap.write_once(invocation, {
        "format": "verislop.support018-phase-launcher-invocation/1",
        "pid": os.getpid(), "argv": sys.argv, "cwd": str(ROOT),
        "input_root": canonical.digest_json(hashes),
        "source_root": spec["source_root"], "phases": spec["execution_phases"],
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "inference_timeout": None, "model_calls": 0, "task_inputs": False,
    })
    for phase in spec["execution_phases"]:
        guard(hashes, external, frozen, spec)
        receipt_path = HERE / (phase["id"] + "-actual-process-receipt.json")
        stdout_path = HERE / (phase["id"] + ".stdout.log")
        stderr_path = HERE / (phase["id"] + ".stderr.log")
        if receipt_path.exists() or stdout_path.exists() or stderr_path.exists():
            raise ValueError("Phase evidence already exists: " + phase["id"])
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        env = dict(os.environ)
        env.update(phase.get("environment", {}))
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            process = subprocess.Popen(phase["argv"], cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
            code = process.wait()
        receipt = {
            "format": "verislop.support018-actual-process-receipt/1", "id": phase["id"],
            "argv": phase["argv"], "cwd": str(ROOT), "pid": process.pid,
            "registered_environment": phase.get("environment", {}),
            "returncode": code, "timed_out": False,
            "started_utc": started,
            "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "stdout": {"path": stdout_path.relative_to(ROOT).as_posix(),
                       "byte_count": stdout_path.stat().st_size,
                       "sha256": canonical.digest_file(stdout_path)},
            "stderr": {"path": stderr_path.relative_to(ROOT).as_posix(),
                       "byte_count": stderr_path.stat().st_size,
                       "sha256": canonical.digest_file(stderr_path)},
            "input_root": canonical.digest_json(hashes), "source_root": spec["source_root"],
            "process_status_scope": "Direct actual Python verifier process; no invented descendant status",
            "peak_memory": None, "cpu_time": None,
        }
        bootstrap.write_once(receipt_path, receipt)
        guard(hashes, external, frozen, spec)
        print(phase["id"], code, flush=True)
        if code != phase["accepted_exit_code"]:
            return code if code > 0 else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
