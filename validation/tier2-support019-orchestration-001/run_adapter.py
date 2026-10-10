"""Expand registered runtime hash slots and record the actual adapter child."""
import argparse
import datetime
import os
from pathlib import Path
import subprocess
import sys
from execute_phases import ROOT, bootstrap, canonical, gate_path, guard, identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-root", required=True)
    parser.add_argument("--kind", choices=("reconcile", "reader"), required=True)
    args = parser.parse_args()
    gate = gate_path(args.qualification_root)
    spec = bootstrap.load(gate / "qualification-specification.json")
    manifest = bootstrap.load(gate / "qualification-inputs.json")
    frozen = bootstrap.load(gate / "source-freeze.json")
    external = {p.relative_to(ROOT).as_posix(): canonical.digest_file(p)
                for p in (gate / "qualification-inputs.json", gate / "preregistration.json")}
    guard(manifest["source_hashes"], external, frozen, spec)
    if manifest["source_hashes"].get(Path(__file__).relative_to(ROOT).as_posix()) != canonical.digest_file(Path(__file__)):
        raise ValueError("Adapter wrapper is not frozen")
    config = spec["adapters"]
    index_hashes = {}
    for key in ("equality", "carrier", "author", "pure"):
        path = ROOT / config["additional_evidence_paths"][key]
        identity(path)
        if not path.is_relative_to(gate):
            raise ValueError("Ancillary evidence is not in the current root")
        index_hashes[key + "_index_sha256"] = canonical.digest_file(path)
    registration_path = ROOT / config["adapter_wrapper_registrations"][args.kind]
    registration_identity = identity(registration_path)
    if manifest["source_hashes"].get(registration_identity["path"]) != registration_identity["sha256"]:
        raise ValueError("Adapter child registration is not frozen")
    registration = bootstrap.load(registration_path)
    bindings = {"python": sys.executable, "qualification_root": str(gate),
                "verifier": str(ROOT / registration["verifier"]["path"]),
                "final_report": str(gate / "final-reconciliation/report.json"),
                "finalizer_receipt": str(gate / "reconcile-child-process-receipt.json"),
                "output": str(gate / "independent-audit"), **index_hashes}
    if (registration["closure_id"] != spec["closure_id"] or
            registration["verifier"]["sha256"] != manifest["source_hashes"][registration["verifier"]["path"]]):
        raise ValueError("Adapter registration is not current")
    argv = [part.format(**bindings) for part in registration["invocation"]["argv_template"]]
    if argv[:2] != [sys.executable, bindings["verifier"]]:
        raise ValueError("Adapter command does not name its registered verifier")
    stdout_path, stderr_path = (gate / (args.kind + "-child." + stream + ".log") for stream in ("stdout", "stderr"))
    receipt_path = gate / (args.kind + "-child-process-receipt.json")
    if any(p.exists() for p in (stdout_path, stderr_path, receipt_path)):
        raise ValueError("Adapter child evidence already exists")
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        child = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        bootstrap.write_once(gate / (args.kind + "-child-started.json"), {
            "argv": argv, "pid": child.pid, "launcher_pid": os.getpid(), "started_utc": started,
            "source_root": spec["source_root"], "input_root": manifest["input_root"], "runtime_bindings": bindings})
        code = child.wait()
    receipt = {"format": "verislop.support019-actual-process-receipt/1", "id": args.kind + "-child",
               "argv": argv, "cwd": str(ROOT), "pid": child.pid, "launcher_pid": os.getpid(),
               "registered_environment": {}, "returncode": code, "timed_out": False,
               "started_utc": started, "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "source_root": spec["source_root"], "input_root": manifest["input_root"],
               "stdout": identity(stdout_path), "stderr": identity(stderr_path), "runtime_bindings": bindings}
    bootstrap.write_once(receipt_path, receipt)
    guard(manifest["source_hashes"], external, frozen, spec)
    sys.stdout.buffer.write(stdout_path.read_bytes()); sys.stdout.buffer.flush()
    sys.stderr.buffer.write(stderr_path.read_bytes()); sys.stderr.buffer.flush()
    return code if code >= 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
