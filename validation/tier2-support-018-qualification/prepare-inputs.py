"""Materialize exact final registration before any qualification execution."""
import argparse
import datetime
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
from verislop import canonical, leanbridge, policy


def load_module(name, path):
    definition = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--amendment", required=True, type=Path)
    args = parser.parse_args()
    for name in ("source-freeze.json", "qualification-specification.json", "qualification-inputs.json",
                 "preregistration.json", "verification-source-manifest.json", "final-identity-preflight.json"):
        if (HERE / name).exists():
            raise ValueError("Final registration already exists: " + name)
    amendment = args.amendment.absolute()
    if not amendment.is_relative_to(ROOT) or amendment.is_symlink():
        raise ValueError("Final prospective amendment must be a regular repository input")
    gate = load_module("support018_final_gate", HERE / "gate.py")
    preflight = gate.preflight({"test_modules": list(gate.MODULE_FLOOR)})
    bootstrap.write_once(HERE / "final-identity-preflight.json", preflight)
    source_freeze = bootstrap.freeze_engineering(HERE / "source-freeze.json")
    if source_freeze["source_files"] != preflight["source_files"]:
        raise ValueError("Source changed after final identity collection")
    ground = load_module("support018_ground_registry", ROOT /
                         "validation/tier2-ground-replay-support-018-design/qualification.py")
    extra = set(ground.relevant_paths())
    for directory, names in (
        ("validation/tier2-carrier-view-support-018-design",
         ("SPECIFICATION.md", "evidence-plan.json", "execution-plan.json")),
        ("validation/tier2-carrier-view-support-018-implementation", ("verify_carrier_views.py",)),
        ("validation/tier2-unicode-literal-support-018",
         ("verify.py", "spec.json", "fixtures.json", "negative-plan.json", "verifier-plan.json")),
        ("validation/tier2-unicode-literal-support-018/ledger-extension-001",
         ("design.json", "registration.json", "mock_shape_checks.py", "prior/verify.py")),
        ("validation/tier2-support-018-qualification-plan",
         ("qualification-plan.json", "channel-check-protocol-v2.json", "plan-binding-v2-amendment.json",
          "scripts/verify-channel-records-v2.py")),
    ):
        extra.update(ROOT / directory / name for name in names)
    extra.add(amendment)
    reconciliation = ROOT / "validation/tier2-support-018-qualification-plan/final-reconciliation-001"
    if not (reconciliation / "finalizer-registration.json").is_file():
        raise ValueError("Final reconciliation registration is not ready")
    extra.update(path for path in reconciliation.iterdir() if path.is_file())
    extra.update(path for path in (reconciliation / "repair-001").iterdir() if path.is_file())
    extra.update(HERE / name for name in ("gate.py", "execute-phases.py", "prepare-inputs.py",
                 "channel-orchestrator.js", "driver-specification-before-implementation.json",
                 "phase-launcher-registration.json", "source-freeze.json", "final-identity-preflight.json"))
    extra.update(path for path in (HERE / "channel-actual").iterdir() if path.is_file())
    original_channel = ROOT / "validation/tier2-carrier-view-support-018-implementation/channel-001"
    extra.update(original_channel / name for name in ("own-carrier.json", "commands.json"))
    names = (set(preflight["source_files"]) | set(preflight["test_sources"])
             | set(preflight["required_collection_inputs"])
             | {path.relative_to(ROOT).as_posix() for path in extra})
    hashes = {name: canonical.digest_file(gate.relative_file(name)) for name in sorted(names)}
    bootstrap.write_once(HERE / "verification-source-manifest.json", {"files": hashes})
    phases = [
        {"id": "registered-suite", "argv": [sys.executable, str(HERE / "gate.py"), "run"],
         "accepted_exit_code": 0, "required_report": (HERE / "run-result.json").relative_to(ROOT).as_posix()},
        {"id": "carrier-fixtures", "argv": [sys.executable, str(ROOT /
            "validation/tier2-carrier-view-support-018-implementation/verify_carrier_views.py"),
            "--manifest", str(HERE / "verification-source-manifest.json"),
            "--output", str(HERE / "carrier-fixtures")], "accepted_exit_code": 0},
        {"id": "unicode-kernel", "argv": [sys.executable, str(ROOT /
            "validation/tier2-unicode-literal-support-018/verify.py"), "--run-id", "qualification-018"],
            "accepted_exit_code": 0},
        {"id": "ground-kernel", "argv": [sys.executable, str(ROOT /
            "validation/tier2-ground-replay-support-018-design/qualification.py"),
            "--output", str(HERE / "ground-kernel"), "--source-freeze", source_freeze["source_root"],
            "--source-manifest", str(HERE / "verification-source-manifest.json")], "accepted_exit_code": 0},
    ]
    for phase in phases:
        phase["environment"] = {"PYTHONPATH": str(ROOT)}
    spec = {
        "format": "verislop.support018-unified-qualification/1", "closure_id": "support018-final-current-root-001",
        "source_root": source_freeze["source_root"], "test_modules": preflight["test_modules"],
        "registered_test_ids": preflight["test_ids"], "registered_test_count": preflight["test_count"],
        "test_sources": preflight["test_sources"], "required_collection_inputs": preflight["required_collection_inputs"],
        "execution_phases": phases, "claims_plan": args.amendment.as_posix(),
        "claims_plan_sha256": canonical.digest_file(amendment), "model_calls": 0, "task_inputs": False,
        "prior_pass_inheritance": False, "inference_timeout": None,
        "toolchain": leanbridge.resolve_toolchain().identity(), "kernel_tool_hash": leanbridge.kernel_tool_hash(),
        "policy_hash": policy.policy_hash(policy.get("strict")),
        "final_report_rule": "Every exact registered predicate needs actual new evidence; process exits alone are insufficient",
        "finalizer_registration": (reconciliation / "finalizer-registration.json").relative_to(ROOT).as_posix(),
        "post_phase_order": ["actual-channel-capture", "actual-channel-comparison", "final-reconciliation"],
    }
    bootstrap.write_once(HERE / "qualification-specification.json", spec)
    for path in (HERE / "qualification-specification.json", HERE / "verification-source-manifest.json"):
        hashes[path.relative_to(ROOT).as_posix()] = canonical.digest_file(path)
    hashes = dict(sorted(hashes.items()))
    bootstrap.write_once(HERE / "qualification-inputs.json", {
        "format": "verislop.support018-qualification-inputs/1", "source_root": source_freeze["source_root"],
        "source_hashes": hashes, "input_root": canonical.digest_json(hashes),
    })
    bootstrap.write_once(HERE / "preregistration.json", {
        "format": "verislop.support018-qualification-preregistration/1", "generation_started": False,
        "driver_sha256": canonical.digest_file(HERE / "gate.py"),
        "spec_sha256": canonical.digest_file(HERE / "qualification-specification.json"),
        "input_manifest_sha256": canonical.digest_file(HERE / "qualification-inputs.json"),
        "source_freeze_sha256": canonical.digest_file(HERE / "source-freeze.json"),
        "source_root": source_freeze["source_root"], "input_root": canonical.digest_json(hashes),
        "registered_test_count": preflight["test_count"], "execution_phases": phases,
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    gate.check_hashes(hashes)
    if (bootstrap.source_inventory() != source_freeze["source_files"]
            or gate.test_sources() != preflight["test_sources"]):
        raise ValueError("Source/test changed while finalizing registration")
    print({"source_root": source_freeze["source_root"], "input_root": canonical.digest_json(hashes),
           "test_count": preflight["test_count"], "input_count": len(hashes), "execution_started": False}, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
