"""Frozen collection/name qualification; no task inputs or model calls."""
from datetime import datetime, timezone
from pathlib import Path
import os
import difflib
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
GATE = Path(__file__).resolve().parent
if Path.cwd() != ROOT:
    raise RuntimeError("Run this qualification in the exact workspace root")
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
from verislop import canonical

MODULES = [
    "tests.test_vscore3_proof_support",
    "tests.test_vscore3_name_identity",
    "tests.test_vscore3_readable",
    "tests.test_vscore3_readable_cli",
    "tests.test_vscore3_workflow_unit",
    "tests.test_vscore3_closure_dispatch",
    "tests.test_bootstrap_tier2",
    "tests.test_vscore3_collection_bridge",
]
prior_gate = ROOT / "validation/tier2-native-boundary-gate-017"
prior_result = bootstrap.load(prior_gate / "run-result.json")
prior_freeze = bootstrap.load(prior_gate / "source-freeze.json")
prior_qualification = bootstrap.load(prior_gate / "qualification-inputs.json")
prior_tests = bootstrap.load(prior_gate / "test-sources.json")
if (canonical.digest_file(prior_gate / "source-freeze.json") != prior_qualification["engineering_freeze_hash"]
        or prior_tests != prior_result["test_sources"]
        or any(prior_qualification["source_hashes"].get(name) != sha for name, sha in prior_tests.items())
        or prior_qualification["source_root"] != prior_freeze["source_root"]
        or prior_result["source_root_before"] != prior_freeze["source_root"]
        or prior_result["source_root_after"] != prior_freeze["source_root"]
        or canonical.digest_json(prior_freeze["source_files"]) != prior_freeze["source_root"]):
    raise RuntimeError("The bound original failed qualification preimages or source roots differ")
if (prior_result["status"] != "FAIL" or not prior_result["source_unchanged"]
        or not prior_result["qualification_inputs_unchanged"]
        or bootstrap.source_inventory() != prior_freeze["source_files"]):
    raise RuntimeError("The prior failed qualification or unchanged production boundary differs")
repair_dir = ROOT / "validation/tier2-proof-support-017-collection-design/development-repair-001"
old_test = (repair_dir / "original-tests.py").read_bytes()
old_test_hash = canonical.digest(old_test)
if (old_test_hash != prior_result["test_sources"]["tests/test_vscore3_collection_bridge.py"]
        or old_test_hash != prior_qualification["source_hashes"]["tests/test_vscore3_collection_bridge.py"]):
    raise RuntimeError("The repair original is not the exact gate017 frozen collection test")
current_test = (ROOT / "tests/test_vscore3_collection_bridge.py").read_bytes()
expected_test = old_test
REPAIR_TRANSFORMS = [('"readable_diagnostics": info["readable_candidate_artifacts"]}', '"readable_diagnostics": {path: data for path, data in info["readable_candidate_artifacts"].items()\n                                                 if path != readable.SELECTION_PATH}}'), ('readable_diagnostics=wrong_info["readable_candidate_artifacts"])', 'readable_diagnostics={path: data for path, data in wrong_info["readable_candidate_artifacts"].items()\n                                             if path != readable.SELECTION_PATH})'), ('readable_diagnostics=info["readable_candidate_artifacts"])', 'readable_diagnostics=selected_options["readable_diagnostics"])')]
for before, after in REPAIR_TRANSFORMS:
    if expected_test.count(before.encode()) != 1:
        raise RuntimeError("The original frozen test differs from an exact authorized repair site")
    expected_test = expected_test.replace(before.encode(), after.encode(), 1)
if current_test != expected_test or (repair_dir / "repaired-tests.py").read_bytes() != current_test:
    raise RuntimeError("The collection fixture repair contains an unauthorized byte change")
repair_diff = "".join(difflib.unified_diff(old_test.decode().splitlines(keepends=True),
                                        current_test.decode().splitlines(keepends=True),
                                        fromfile="original-tests.py", tofile="tests/test_vscore3_collection_bridge.py"))
repair_observations = {"old_test_sha256": canonical.digest(old_test),
                      "new_test_sha256": canonical.digest(current_test),
                      "authorized_replacements": len(REPAIR_TRANSFORMS),
                      "diff_sha256": canonical.digest(repair_diff.encode())}
repair_receipt = bootstrap.load(GATE / "repair-diff-receipt.json")
if (repair_receipt.get("format") != "verislop.exact-collection-harness-repair/1"
        or repair_receipt.get("observations") != repair_observations):
    raise RuntimeError("The bound repair receipt disagrees with actual exact old/new test bytes")

freeze = bootstrap.freeze_engineering(GATE / "source-freeze.json")
test_hashes = {p.relative_to(ROOT).as_posix(): canonical.digest_file(p)
               for p in sorted((ROOT / "tests").rglob("*.py"))}
prior_tests = bootstrap.load(prior_gate / "test-sources.json")
changed_tests = sorted(name for name in set(prior_tests) | set(test_hashes)
                       if prior_tests.get(name) != test_hashes.get(name))
if changed_tests != ["tests/test_vscore3_collection_bridge.py"]:
    raise RuntimeError("The authorized collection diagnostic-map repair is not the exact test change")
bootstrap.write_once(GATE / "test-sources.json", test_hashes)
all_hashes = {**freeze["source_files"], **test_hashes,
              Path(__file__).relative_to(ROOT).as_posix(): canonical.digest_file(Path(__file__)),
              (GATE / "qualification-specification.json").relative_to(ROOT).as_posix():
                  canonical.digest_file(GATE / "qualification-specification.json")}
for relative in ("validation/tier2-collection-proof-support-audit-017/plan.json",
                 "validation/tier2-collection-proof-support-audit-017/plan.md",
                 "validation/tier2-collection-proof-support-audit-017/initial-current-inputs.json",
                 "validation/tier2-collection-proof-support-audit-017/driver-preregistration.json",
                 "validation/tier2-native-boundary-gate-017/preregistration-correction.json",
                 "validation/tier2-native-boundary-gate-017/preregistration-correction-2.json",
                 "validation/tier2-native-boundary-gate-017/qualification-inputs.json",
                 "validation/tier2-native-boundary-gate-017/source-freeze.json",
                 "validation/tier2-native-boundary-gate-017/test-sources.json",
                 "validation/tier2-native-boundary-gate-017/run-result.json",
                 "validation/tier2-native-boundary-gate-017/actual-process-receipt.json",
                 "validation/tier2-native-boundary-gate-017/qualification-hold-release.json",
                 "validation/tier2-collection-proof-support-audit-017/gate017-failure-observations.json",
                 "validation/tier2-collection-proof-support-audit-017/gate018-amendment.json",
                 "validation/tier2-collection-proof-support-audit-017/gate018-prefreeze-binding.json",
                 "validation/tier2-proof-support-017-collection-design/development-repair-001/design-before-edit.json",
                 "validation/tier2-proof-support-017-collection-design/development-repair-001/original-tests.py",
                 "validation/tier2-proof-support-017-collection-design/development-repair-001/repaired-tests.py",
                 "validation/tier2-native-boundary-gate-018/repair-diff-receipt.json",
                 "validation/tier2-collection-proof-support-audit-017/gate018-driver-preregistration.json",
                 "validation/tier2-native-boundary-gate-018/driver-binding-correction.json",
                 "validation/tier2-native-boundary-gate-018/prefreeze-hardening.json",
                 "validation/tier2-native-boundary-gate-018/driver-revisions/pre-hardening-a5be32a.py",
                 "validation/tier2-collection-proof-support-audit-017/gate018-driver-prefreeze-observation-001.json",
                 "validation/tier2-collection-proof-support-audit-017/gate018-driver-prefreeze-observation-002.json",
                 "validation/tier2-native-boundary-gate-018/prefreeze-hardening-002.json",
                 "validation/tier2-native-boundary-gate-018/driver-revisions/pre-hardening-002-83f7057.py"):
    all_hashes[relative] = canonical.digest_file(ROOT / relative)
qualification = {"format": "verislop.collection-qualification-input-freeze/1",
                 "source_hashes": all_hashes, "source_root": freeze["source_root"],
                 "test_root": canonical.digest_json(test_hashes),
                 "engineering_freeze_hash": canonical.digest_file(GATE / "source-freeze.json"),
                 "task_inputs": False, "model_calls": 0, "prior_failed_attempt": "gate017",
                 "prior_pass_inheritance": False, "qualification_attempt": "gate018"}
bootstrap.write_once(GATE / "qualification-inputs.json", qualification)
os.environ["VERISLOP_COLLECTION_QUALIFICATION_FREEZE"] = str(GATE / "qualification-inputs.json")
os.environ["VERISLOP_COLLECTION_DEVELOPMENT_EVIDENCE"] = str(GATE / "actual-gate-evidence")
bootstrap.write_once(GATE / "invocation.json", {
    "format": "verislop.tier2-native-engineering-invocation/0.1",
    "started_at_utc": datetime.now(timezone.utc).isoformat(),
    "source_root": freeze["source_root"], "test_modules": MODULES,
    "fresh_task_model_calls": 0, "task_inputs_supplied": False,
    "qualification_inputs_hash": canonical.digest_file(GATE / "qualification-inputs.json"),
    "driver_script_sha256": canonical.digest_file(Path(__file__)),
})
started = time.monotonic()
EXPECTED_TESTS = 98
suite = unittest.defaultTestLoader.loadTestsFromNames(MODULES)
registered_test_count = suite.countTestCases()
if registered_test_count != EXPECTED_TESTS:
    raise RuntimeError("The exact 98-test registered suite differs before execution")
result = unittest.TextTestRunner(verbosity=2).run(suite)
after = bootstrap.source_inventory()
input_hashes_after = {name: canonical.digest_file(ROOT / name) for name in all_hashes}
unchanged = after == freeze["source_files"] and input_hashes_after == all_hashes
passed = (result.wasSuccessful() and result.testsRun == EXPECTED_TESTS
          and not result.skipped and not result.expectedFailures
          and not result.unexpectedSuccesses and unchanged)
bootstrap.write_once(GATE / "run-result.json", {
    "format": "verislop.tier2-native-engineering-gate/0.1",
    "status": "PASS" if passed else "FAIL",
    "tests_run": result.testsRun, "registered_test_count": registered_test_count,
    "expected_test_count": EXPECTED_TESTS, "expected_failures": len(result.expectedFailures),
    "unexpected_successes": len(result.unexpectedSuccesses), "errors": len(result.errors),
    "failures": len(result.failures), "skipped": len(result.skipped),
    "duration_seconds": str(time.monotonic() - started),
    "test_modules": MODULES, "test_sources": test_hashes,
    "source_root_before": freeze["source_root"],
    "source_root_after": canonical.digest_json(after),
    "source_unchanged": after == freeze["source_files"],
    "qualification_inputs_unchanged": input_hashes_after == all_hashes,
    "fresh_model_calls": 0, "prior_pass_inheritance": False, "qualification_attempt": "gate018",
    "scope": "generic universal adapter/collection support, exact punctuated obligation names, actual helper/capture source refinements, registered two-build closure and retained release probes; no task answers",
})
sys.exit(0 if passed else 2)
