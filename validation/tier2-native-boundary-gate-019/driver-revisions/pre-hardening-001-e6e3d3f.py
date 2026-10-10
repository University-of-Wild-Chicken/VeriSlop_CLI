"""Spec-first gate019; complete frozen-input preflight, no task/model inputs.

--preflight-only imports and counts the registered suite but executes no test,
creates no fixture, invokes no Lean build and publishes no qualification files.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import difflib
import hashlib
import importlib
import inspect
import json
import os
import sys
import time
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
GATE = Path(__file__).resolve().parent
PRIOR_GATE = ROOT / "validation/tier2-native-boundary-gate-018"
SPEC_PATH = GATE / "qualification-specification.json"
FREEZE_ENV = "VERISLOP_COLLECTION_QUALIFICATION_FREEZE"
EXPECTED_TESTS = 98
EXPECTED_SOURCE_ROOT = "sha256:c0225d21274f4c4819800e3f136f49e68c9762eb0322860438e57d43e179db49"
EXPECTED_TEST_ROOT = "sha256:abb6b4ff9f34e028618d3fc2f9064f8d7da3e6bad985dac1c1a60ed988fd89f3"
EXPECTED_PRIOR_INPUT_HASH = "sha256:f8dd26148a088ee76607c495b1bd0256a7dedccf131c064e8d201ccdbc8e917a"
MODULES = [
    "tests.test_vscore3_collection_bridge",
    "tests.test_vscore3_proof_support",
    "tests.test_vscore3_name_identity",
    "tests.test_vscore3_readable",
    "tests.test_vscore3_readable_cli",
    "tests.test_vscore3_workflow_unit",
    "tests.test_vscore3_closure_dispatch",
    "tests.test_bootstrap_tier2",
]
OUTPUT_NAMES = ("source-freeze.json", "test-sources.json", "qualification-inputs.json",
                "invocation.json", "run-result.json")


def regular_bytes(path):
    if path.is_symlink() or not path.is_file() or path.resolve() != path.absolute():
        raise RuntimeError("Missing, nonregular or indirect qualification input: " + str(path))
    return path.read_bytes()


def file_hash(path):
    return "sha256:" + hashlib.sha256(regular_bytes(path)).hexdigest()


def read_json(path):
    return json.loads(regular_bytes(path))


def checked_relative(name):
    path = Path(name)
    if not isinstance(name, str) or path.is_absolute() or path.as_posix() != name or ".." in path.parts:
        raise RuntimeError("Invalid qualification input path")
    return ROOT / path


def assert_hashes(hashes):
    for name, expected in sorted(hashes.items()):
        if file_hash(checked_relative(name)) != expected:
            raise RuntimeError("Qualification input differs from its immutable anchor: " + name)


def leaf_tests(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from leaf_tests(test)
        else:
            yield test


def assert_no_registered_skips(tests):
    for test in tests:
        method = getattr(test, test._testMethodName)
        if (getattr(test, "__unittest_skip__", False)
                or getattr(type(test), "__unittest_skip__", False)
                or getattr(method, "__unittest_skip__", False)):
            raise RuntimeError("Registered qualification test is already marked skipped: " + test.id())


def preserve_original_gate018_predicates():
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
    repair_receipt = bootstrap.load(PRIOR_GATE / "repair-diff-receipt.json")
    if (repair_receipt.get("format") != "verislop.exact-collection-harness-repair/1"
            or repair_receipt.get("observations") != repair_observations):
        raise RuntimeError("The bound repair receipt disagrees with actual exact old/new test bytes")


def preflight():
    if Path.cwd() != ROOT:
        raise RuntimeError("Run this qualification in the exact workspace root")
    specification = read_json(SPEC_PATH)
    prior_path = PRIOR_GATE / "qualification-inputs.json"
    if file_hash(prior_path) != EXPECTED_PRIOR_INPUT_HASH:
        raise RuntimeError("The immutable gate018 manifest bytes differ")
    prior = read_json(prior_path)
    original_hashes = prior["source_hashes"]
    anchor = specification["immutable_gate018_manifest"]
    if (len(original_hashes) != 397 or anchor["input_count"] != 397
            or anchor["path"] != prior_path.relative_to(ROOT).as_posix()
            or anchor["sha256"] != EXPECTED_PRIOR_INPUT_HASH
            or prior["source_root"] != EXPECTED_SOURCE_ROOT
            or anchor["source_root"] != EXPECTED_SOURCE_ROOT
            or prior["test_root"] != EXPECTED_TEST_ROOT
            or anchor["test_root"] != EXPECTED_TEST_ROOT
            or prior["qualification_attempt"] != "gate018"
            or prior["prior_pass_inheritance"] is not False
            or prior["task_inputs"] is not False or prior["model_calls"] != 0):
        raise RuntimeError("The immutable gate018 input/root/attempt registration differs")
    # Bind the exact source-list implementation and its dependencies before importing it.
    assert_hashes(original_hashes)
    fixed_hashes = specification["fixed_additional_input_hashes"]
    assert_hashes(fixed_hashes)
    if fixed_hashes.get(prior_path.relative_to(ROOT).as_posix()) != EXPECTED_PRIOR_INPUT_HASH:
        raise RuntimeError("The specification does not bind the exact original gate018 manifest")
    for name in specification["independent_preregistration_artifacts"]:
        regular_bytes(checked_relative(name))

    sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
    global bootstrap, canonical
    from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
    from verislop import canonical

    prior_freeze = bootstrap.load(PRIOR_GATE / "source-freeze.json")
    prior_tests = bootstrap.load(PRIOR_GATE / "test-sources.json")
    prior_result = bootstrap.load(PRIOR_GATE / "run-result.json")
    prior_invocation = bootstrap.load(PRIOR_GATE / "invocation.json")
    prior_process = bootstrap.load(PRIOR_GATE / "actual-process-receipt.json")
    prior_release = bootstrap.load(PRIOR_GATE / "qualification-hold-release.json")
    if (canonical.digest_file(PRIOR_GATE / "source-freeze.json") != prior["engineering_freeze_hash"]
            or canonical.digest_json(prior_freeze["source_files"]) != EXPECTED_SOURCE_ROOT
            or prior_freeze["source_root"] != EXPECTED_SOURCE_ROOT
            or len(prior_freeze["source_files"]) != 241 or anchor["source_count"] != 241
            or canonical.digest_json(prior_tests) != EXPECTED_TEST_ROOT
            or len(prior_tests) != anchor["test_count"]
            or prior_tests != prior_result["test_sources"]
            or any(original_hashes.get(name) != sha for name, sha in prior_tests.items())
            or any(original_hashes.get(name) != sha for name, sha in prior_freeze["source_files"].items())
            or prior_result["source_root_before"] != EXPECTED_SOURCE_ROOT
            or prior_result["source_root_after"] != EXPECTED_SOURCE_ROOT
            or prior_result["status"] != "FAIL" or prior_result["tests_run"] != EXPECTED_TESTS
            or prior_result["registered_test_count"] != EXPECTED_TESTS
            or prior_result["expected_test_count"] != EXPECTED_TESTS
            or prior_result["failures"] != 1 or prior_result["errors"] != 0
            or prior_result["skipped"] != 0 or prior_result["expected_failures"] != 0
            or prior_result["unexpected_successes"] != 0
            or prior_result["source_unchanged"] is not True
            or prior_result["qualification_inputs_unchanged"] is not True
            or prior_result["fresh_model_calls"] != 0
            or prior_result["prior_pass_inheritance"] is not False
            or prior_result["qualification_attempt"] != "gate018"
            or prior_invocation["qualification_inputs_hash"] != EXPECTED_PRIOR_INPUT_HASH
            or prior_invocation["driver_script_sha256"] != file_hash(PRIOR_GATE / "gate.py")
            or prior_invocation["source_root"] != EXPECTED_SOURCE_ROOT
            or prior_invocation["test_modules"] != prior_result["test_modules"]
            or prior_invocation["fresh_task_model_calls"] != 0
            or prior_invocation["task_inputs_supplied"] is not False
            or prior_process["actual_returncode"] != 2 or prior_process["model_calls"] != 0
            or "sha256:" + prior_process["logs"]["run-result.json"]["sha256"] != file_hash(PRIOR_GATE / "run-result.json")
            or prior_release["actual_driver_process_stopped"] is not True
            or prior_release["actual_process_receipt_sha256"] != file_hash(PRIOR_GATE / "actual-process-receipt.json")
            or prior_release["all_frozen_inputs_unchanged"] is not True
            or prior_release["gate018_status"] != "FAIL"
            or prior_release["qualification_authority"] is not False
            or prior_release["prior_pass_inheritance"] is not False
            or prior_release["fresh_task_generation_started"] is not False
            or prior_release["source_root"] != EXPECTED_SOURCE_ROOT
            or prior_release["qualification_inputs_sha256"] != EXPECTED_PRIOR_INPUT_HASH
            or prior_release["run_result_sha256"] != file_hash(PRIOR_GATE / "run-result.json")
            or sorted(prior_release["observed_missing_inputs"]) != sorted([
                "validation/tier2-native-boundary-gate-017/gate.py",
                "validation/tier2-native-boundary-gate-017/qualification-specification.json"])):
        raise RuntimeError("The immutable gate018 failed-result/invocation/process/release bindings differ")
    preserve_original_gate018_predicates()
    current_sources = bootstrap.source_inventory()
    test_hashes = {p.relative_to(ROOT).as_posix(): file_hash(p)
                   for p in sorted((ROOT / "tests").rglob("*.py"))}
    if current_sources != prior_freeze["source_files"] or test_hashes != prior_tests:
        raise RuntimeError("Production/source/test file names or hashes differ from gate018")
    current_names = [Path(__file__).relative_to(ROOT).as_posix(), SPEC_PATH.relative_to(ROOT).as_posix()]
    if specification["current_driver_and_specification"] != current_names:
        raise RuntimeError("The current driver/specification names differ from the preregistered specification")
    all_hashes = {**original_hashes, **fixed_hashes}
    for name in current_names + specification["independent_preregistration_artifacts"]:
        all_hashes[name] = file_hash(checked_relative(name))
    selected_names = sorted(all_hashes)
    if (selected_names != specification["selected_input_names"]
            or len(selected_names) != specification["selected_input_count"]
            or len(selected_names) != 411):
        raise RuntimeError("The exact selected qualification input set differs from preregistration")
    assert_hashes(all_hashes)

    # The collection class reads this variable at import time: set it BEFORE loading any test.
    os.environ[FREEZE_ENV] = str(GATE / "qualification-inputs.json")
    os.environ["VERISLOP_COLLECTION_DEVELOPMENT_EVIDENCE"] = str(GATE / "actual-gate-evidence")
    collection = importlib.import_module("tests.test_vscore3_collection_bridge")
    implementation = specification["required_source_implementation"]
    required_names = collection.qualification_source_files()
    if (implementation["module"] != collection.__name__
            or implementation["function"] != "qualification_source_files"
            or implementation["module_path"] != "tests/test_vscore3_collection_bridge.py"
            or implementation["module_sha256"] != all_hashes[implementation["module_path"]]
            or canonical.digest(inspect.getsource(collection.qualification_source_files).encode()) != implementation["function_source_sha256"]
            or required_names != implementation["required_names"]
            or len(required_names) != implementation["required_count"]
            or len(required_names) != 180 or set(required_names) - set(all_hashes)):
        raise RuntimeError("The bound actual collection-required source implementation/subset differs")
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames(MODULES)
    tests = list(leaf_tests(suite))
    test_ids = [test.id() for test in tests]
    registered = specification["registered_suite"]
    if (loader.errors or suite.countTestCases() != EXPECTED_TESTS
            or len(test_ids) != EXPECTED_TESTS or len(set(test_ids)) != EXPECTED_TESTS
            or registered["test_modules"] != MODULES
            or registered["registered_test_ids"] != test_ids
            or registered["registered_test_count"] != EXPECTED_TESTS
            or registered["unique_test_count"] != EXPECTED_TESTS
            or registered["expected_test_count"] != EXPECTED_TESTS
            or registered["failfast"] is not True
            or registered["collection_module_first"] is not True
            or registered["prior_pass_inheritance"] is not False
            or any(registered[key] != 0 for key in ("errors_allowed", "failures_allowed", "skips_allowed", "expected_failures_allowed", "unexpected_successes_allowed"))
            or sorted(MODULES) != sorted(prior_result["test_modules"])):
        raise RuntimeError("The exact 98-unique-test suite identities/module set/order differ")
    assert_no_registered_skips(tests)
    plan = bootstrap.load(ROOT / "validation/tier2-collection-proof-support-audit-017/plan.json")
    if len(plan["claims"]) != 7 or specification["audit_claims"] != plan["claims"]:
        raise RuntimeError("The original seven independent audit claim predicates differ")
    prereg_path = ROOT / "validation/tier2-collection-proof-support-audit-017/gate019-driver-preregistration.json"
    prereg = bootstrap.load(prereg_path)
    if (prereg.get("driver_script_sha256") != all_hashes[current_names[0]]
            or prereg.get("qualification_specification_sha256") != all_hashes[current_names[1]]
            or prereg.get("test_modules") != MODULES
            or prereg.get("registered_test_ids") != test_ids
            or prereg.get("registered_test_count") != EXPECTED_TESTS
            or prereg.get("expected_test_count") != EXPECTED_TESTS
            or prereg.get("failfast") is not True
            or prereg.get("collection_module_first") is not True
            or prereg.get("prior_pass_inheritance") is not False):
        raise RuntimeError("Independent preregistration does not bind the actual final driver/specification and exact ordered suite")
    assert_hashes(all_hashes)
    if bootstrap.source_inventory() != current_sources:
        raise RuntimeError("Production/source inputs changed during nonexecuting preflight")
    report = {
        "format": "verislop.gate019-nonexecuting-preflight/1", "status": "PREFLIGHT_PASS",
        "qualification_authority": False, "qualification_attempt": "gate019",
        "source_root": EXPECTED_SOURCE_ROOT, "source_count": len(current_sources),
        "test_root": canonical.digest_json(test_hashes), "test_source_count": len(test_hashes),
        "source_hashes": all_hashes, "selected_input_count": len(all_hashes),
        "selected_input_root": canonical.digest_json(all_hashes),
        "required_source_names": required_names, "required_source_count": len(required_names),
        "required_source_implementation": implementation,
        "test_modules": MODULES, "registered_test_ids": test_ids,
        "registered_test_count": len(test_ids), "unique_test_count": len(set(test_ids)),
        "expected_test_count": EXPECTED_TESTS, "failfast": True, "collection_module_first": True,
        "registered_skip_flags": 0, "model_calls": 0, "tests_executed": 0,
        "fixture_generation": False, "lean_builds": False, "qualification_files_published": False,
        "prior_pass_inheritance": False, "audit_claim_count": len(plan["claims"]),
    }
    return report, suite, current_sources, test_hashes, collection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true", help="Verify exact inputs and suite without executing tests or publishing qualification files")
    args = parser.parse_args()
    report, suite, source_files, test_hashes, collection = preflight()
    if args.preflight_only:
        print(canonical.dumps(report).decode())
        return 0
    if any((GATE / name).exists() for name in OUTPUT_NAMES):
        raise RuntimeError("This write-once gate019 attempt already has qualification outputs")
    all_hashes = report["source_hashes"]
    assert_hashes(all_hashes)
    freeze = bootstrap.freeze_engineering(GATE / "source-freeze.json")
    if freeze["source_files"] != source_files or freeze["source_root"] != EXPECTED_SOURCE_ROOT:
        raise RuntimeError("Production/source changed before the actual qualification freeze")
    bootstrap.write_once(GATE / "test-sources.json", test_hashes)
    qualification = {
        "format": "verislop.collection-qualification-input-freeze/1", "source_hashes": all_hashes,
        "source_root": freeze["source_root"], "test_root": canonical.digest_json(test_hashes),
        "engineering_freeze_hash": file_hash(GATE / "source-freeze.json"),
        "task_inputs": False, "model_calls": 0, "prior_failed_attempt": "gate018",
        "earlier_failed_attempts": ["gate017", "gate018"], "prior_pass_inheritance": False,
        "qualification_attempt": "gate019", "selected_input_count": len(all_hashes),
        "selected_input_root": canonical.digest_json(all_hashes),
        "required_source_names": report["required_source_names"], "required_source_count": 180,
        "required_source_implementation": report["required_source_implementation"],
        "test_modules": MODULES, "registered_test_ids": report["registered_test_ids"],
        "registered_test_count": EXPECTED_TESTS, "unique_test_count": EXPECTED_TESTS,
        "expected_test_count": EXPECTED_TESTS, "failfast": True, "collection_module_first": True,
    }
    bootstrap.write_once(GATE / "qualification-inputs.json", qualification)
    collection.require_frozen_sources(GATE / "qualification-inputs.json")
    assert_no_registered_skips(list(leaf_tests(suite)))
    bootstrap.write_once(GATE / "invocation.json", {
        "format": "verislop.tier2-native-engineering-invocation/0.1",
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "source_root": freeze["source_root"],
        "test_modules": MODULES, "registered_test_ids": report["registered_test_ids"],
        "registered_test_count": EXPECTED_TESTS, "unique_test_count": EXPECTED_TESTS,
        "expected_test_count": EXPECTED_TESTS, "failfast": True, "collection_module_first": True,
        "fresh_task_model_calls": 0, "task_inputs_supplied": False,
        "qualification_inputs_hash": file_hash(GATE / "qualification-inputs.json"),
        "driver_script_sha256": file_hash(Path(__file__)),
        "qualification_specification_sha256": file_hash(SPEC_PATH),
        "prior_pass_inheritance": False, "qualification_attempt": "gate019",
    })
    qualification_hash = file_hash(GATE / "qualification-inputs.json")
    assert_hashes(all_hashes)
    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    after = bootstrap.source_inventory()
    input_hashes_after = {name: file_hash(ROOT / name) for name in all_hashes}
    source_unchanged = after == source_files
    inputs_unchanged = (input_hashes_after == all_hashes
                        and file_hash(GATE / "source-freeze.json") == qualification["engineering_freeze_hash"]
                        and file_hash(GATE / "test-sources.json") == canonical.digest_json(test_hashes)
                        and file_hash(GATE / "qualification-inputs.json") == qualification_hash)
    passed = (result.wasSuccessful() and result.testsRun == EXPECTED_TESTS
              and not result.failures and not result.errors and not result.skipped
              and not result.expectedFailures and not result.unexpectedSuccesses
              and source_unchanged and inputs_unchanged)
    bootstrap.write_once(GATE / "run-result.json", {
        "format": "verislop.tier2-native-engineering-gate/0.1", "status": "PASS" if passed else "FAIL",
        "tests_run": result.testsRun, "registered_test_count": EXPECTED_TESTS,
        "unique_test_count": EXPECTED_TESTS, "expected_test_count": EXPECTED_TESTS,
        "expected_failures": len(result.expectedFailures), "unexpected_successes": len(result.unexpectedSuccesses),
        "errors": len(result.errors), "failures": len(result.failures), "skipped": len(result.skipped),
        "duration_seconds": str(time.monotonic() - started), "test_modules": MODULES,
        "registered_test_ids": report["registered_test_ids"], "test_sources": test_hashes,
        "source_root_before": freeze["source_root"], "source_root_after": canonical.digest_json(after),
        "source_unchanged": source_unchanged, "qualification_inputs_unchanged": inputs_unchanged,
        "fresh_model_calls": 0, "prior_pass_inheritance": False, "qualification_attempt": "gate019",
        "failfast": True, "collection_module_first": True,
        "scope": "generic universal adapter/collection support, exact punctuated obligation names, actual helper/capture source refinements, registered two-build closure and retained release probes; no task answers",
    })
    return 0 if passed else 2


if __name__ == "__main__":
    sys.exit(main())
