"""Run registered current-root phases serially; record actual process facts."""
import argparse
import datetime
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
from verislop import canonical

SECTIONS = {"core": (0, 4), "additional-pre": (4, 6), "additional-post": (6, 8)}


def gate_path(raw):
    gate = Path(raw).absolute()
    if (gate.resolve() != gate or gate.parent != ROOT / "validation" or
            not gate.name.startswith("tier2-support-019-qualification-") or
            gate.is_symlink() or not gate.is_dir()):
        raise ValueError("Expected canonical registered current qualification root")
    return gate


def guard(hashes, external, frozen, spec):
    for name, expected in {**hashes, **external}.items():
        path = ROOT / name
        if (not path.is_file() or path.is_symlink() or path.resolve() != path.absolute() or
                canonical.digest_file(path) != expected):
            raise ValueError("Frozen phase input changed: " + name)
    tests = {p.relative_to(ROOT).as_posix(): canonical.digest_file(p)
             for p in sorted((ROOT / "tests").rglob("*.py"))}
    sources = bootstrap.source_inventory()
    if (sources != frozen["source_files"] or canonical.digest_json(sources) != spec["source_root"] or
            tests != spec["test_sources"]):
        raise ValueError("Complete current production/test inventory changed between phases")


def identity(path):
    if not path.is_file() or path.is_symlink() or path.resolve() != path.absolute():
        raise ValueError("Not a canonical regular evidence file: " + str(path))
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "byte_count": len(raw), "sha256": canonical.digest(raw)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-root", required=True)
    parser.add_argument("--section", choices=SECTIONS, required=True)
    args = parser.parse_args()
    gate = gate_path(args.qualification_root)
    spec = bootstrap.load(gate / "qualification-specification.json")
    manifest = bootstrap.load(gate / "qualification-inputs.json")
    frozen = bootstrap.load(gate / "source-freeze.json")
    hashes = manifest["source_hashes"]
    external = {p.relative_to(ROOT).as_posix(): canonical.digest_file(p)
                for p in (gate / "qualification-inputs.json", gate / "preregistration.json")}
    if hashes.get(Path(__file__).relative_to(ROOT).as_posix()) != canonical.digest_file(Path(__file__)):
        raise ValueError("Actual phase launcher is not frozen")
    guard(hashes, external, frozen, spec)
    phases = spec["execution_phases"] + spec["additional_processes"]
    start, stop = SECTIONS[args.section]
    expected = ("registered-suite", "carrier-fixtures", "unicode-kernel", "ground-kernel",
                "equality-original44-new11-grouped", "carrier-pure-controls",
                "current-root-reconciliation", "independent-predicate-reader")
    if tuple(p["id"] for p in phases) != expected:
        raise ValueError("Original and added phase order differs")
    for previous in phases[:start]:
        receipt = bootstrap.load(gate / (previous["id"] + "-actual-process-receipt.json"))
        if (receipt["argv"] != previous["argv"] or receipt["registered_environment"] != previous["environment"] or
                type(receipt["returncode"]) is not int or receipt["returncode"] != previous["accepted_exit_code"] or
                receipt["source_root"] != spec["source_root"] or receipt["input_root"] != manifest["input_root"]):
            raise ValueError("Earlier registered section is incomplete")
        for stream in ("stdout", "stderr"):
            if identity(ROOT / receipt[stream]["path"]) != receipt[stream]:
                raise ValueError("Earlier raw log changed")
    invocation = "phase-launcher-invocation.json" if args.section == "core" else args.section + "-launcher-invocation.json"
    bootstrap.write_once(gate / invocation, {
        "format": "verislop.support018-phase-launcher-invocation/1", "pid": os.getpid(),
        "argv": sys.argv, "cwd": str(ROOT), "input_root": manifest["input_root"],
        "source_root": spec["source_root"], "phases": phases[start:stop],
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "inference_timeout": None, "model_calls": 0, "task_inputs": False})
    for phase in phases[start:stop]:
        guard(hashes, external, frozen, spec)
        receipt_path = gate / (phase["id"] + "-actual-process-receipt.json")
        stdout_path, stderr_path = (gate / (phase["id"] + "." + stream + ".log") for stream in ("stdout", "stderr"))
        if any(p.exists() for p in (receipt_path, stdout_path, stderr_path)):
            raise ValueError("Phase evidence already exists: " + phase["id"])
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        env = dict(os.environ); env.update(phase["environment"])
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            child = subprocess.Popen(phase["argv"], cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                     stdout=stdout, stderr=stderr)
            bootstrap.write_once(gate / (phase["id"] + "-started.json"), {
                "argv": phase["argv"], "pid": child.pid, "launcher_pid": os.getpid(),
                "started_utc": started, "source_root": spec["source_root"], "input_root": manifest["input_root"]})
            code = child.wait()
        bootstrap.write_once(receipt_path, {
            "format": "verislop.support018-actual-process-receipt/1", "id": phase["id"],
            "argv": phase["argv"], "cwd": str(ROOT), "pid": child.pid,
            "registered_environment": phase["environment"], "returncode": code, "timed_out": False, "timeout_seconds": None,
            "started_utc": started, "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "stdout": identity(stdout_path), "stderr": identity(stderr_path),
            "input_root": manifest["input_root"], "source_root": spec["source_root"],
            "process_status_scope": "Direct actual Python verifier process; no invented descendant status",
            "peak_memory": None, "cpu_time": None})
        guard(hashes, external, frozen, spec)
        print(phase["id"], code, flush=True)
        if code != phase["accepted_exit_code"]:
            return code if code > 0 else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
