"""Frozen current-root regression runner; no model or task input.

Preflight collects identities only. Run requires a finalized immutable registry,
the exact input manifest, source freeze and separately bound preregistration.
The caller records actual process completion independently of this report.
"""
from __future__ import annotations

import argparse
import datetime
import importlib
import json
import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
GATE = Path(__file__).resolve().parent
COLLECTION_ID = ("tests.test_vscore3_collection_bridge.CollectionRegisteredTier2Tests."
                 "test_actual_frozen_collection_closure_and_retained_release_probe")
sys.path.insert(0, str(ROOT))
from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
from verislop import canonical


def test_sources():
    return {p.relative_to(ROOT).as_posix(): canonical.digest_file(p)
            for p in sorted((ROOT / "tests").rglob("*.py"))}


def leaf_tests(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from leaf_tests(test)
        else:
            yield test


def relative_file(name):
    p = Path(name)
    if (p.is_absolute() or ".." in p.parts or p.as_posix() != name
            or not (ROOT / p).is_file() or (ROOT / p).is_symlink()
            or (ROOT / p).resolve() != (ROOT / p).absolute()):
        raise ValueError("Missing or indirect registered input: " + name)
    return ROOT / p


def check_hashes(hashes):
    for name, expected in hashes.items():
        if canonical.digest_file(relative_file(name)) != expected:
            raise ValueError("Frozen qualification input changed: " + name)


def collect(spec):
    # Collection's opt-in is evaluated at import, before setUp or test execution.
    os.environ["VERISLOP_COLLECTION_QUALIFICATION_FREEZE"] = str(GATE / "qualification-inputs.json")
    os.environ["VERISLOP_COLLECTION_DEVELOPMENT_EVIDENCE"] = str(GATE / "actual-gate-evidence")
    for key, value in spec.get("test_environment", {}).items():
        if not key.startswith("VERISLOP_"):
            raise ValueError("Unregistered test environment name")
        os.environ[key] = value
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames(spec["test_modules"])
    ids = [test.id() for test in leaf_tests(suite)]
    if (loader.errors or len(ids) != len(set(ids)) or COLLECTION_ID not in ids
            or not spec["test_modules"] or len(spec["test_modules"]) != len(set(spec["test_modules"]))):
        raise ValueError({"loader_errors": loader.errors, "duplicate_ids": len(ids)-len(set(ids))})
    return suite, ids


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.observations = []
        self.started_ids = []

    def startTest(self, test):
        self.started_ids.append(test.id())
        super().startTest(test)

    def note(self, test, status):
        self.observations.append({"test_id": test.id(), "status": status})

    def addSuccess(self, test):
        self.note(test, "PASS"); super().addSuccess(test)

    def addFailure(self, test, err):
        self.note(test, "FAIL"); super().addFailure(test, err)

    def addError(self, test, err):
        self.note(test, "ERROR"); super().addError(test, err)

    def addSkip(self, test, reason):
        self.note(test, "SKIP"); super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self.note(test, "EXPECTED_FAILURE"); super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self.note(test, "UNEXPECTED_SUCCESS"); super().addUnexpectedSuccess(test)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.note(test, "SUBTEST_FAILURE")
        super().addSubTest(test, subtest, err)


def preflight(spec):
    before = bootstrap.source_inventory(), test_sources()
    suite, ids = collect(spec)
    after = bootstrap.source_inventory(), test_sources()
    if before != after:
        raise ValueError("Identity collection changed source/test files")
    required = importlib.import_module("tests.test_vscore3_collection_bridge").qualification_source_files()
    return {"format": "verislop.support018-suite-preflight/1", "test_ids": ids,
            "test_count": len(ids), "test_modules": spec["test_modules"],
            "source_files": before[0], "source_root": canonical.digest_json(before[0]),
            "test_sources": before[1], "required_collection_inputs": required,
            "tests_executed": 0, "model_calls": 0, "task_inputs": False}


def run(spec):
    inputs = bootstrap.load(GATE / "qualification-inputs.json")
    prereg = bootstrap.load(GATE / "preregistration.json")
    frozen = bootstrap.load(GATE / "source-freeze.json")
    hashes = inputs["source_hashes"]
    if (prereg["driver_sha256"] != canonical.digest_file(Path(__file__))
            or prereg["spec_sha256"] != canonical.digest_file(GATE / "qualification-specification.json")
            or prereg["input_manifest_sha256"] != canonical.digest_file(GATE / "qualification-inputs.json")
            or prereg["source_freeze_sha256"] != canonical.digest_file(GATE / "source-freeze.json")
            or prereg["input_root"] != canonical.digest_json(hashes)
            or prereg["source_root"] != frozen["source_root"]
            or spec["source_root"] != frozen["source_root"]
            or inputs["source_root"] != frozen["source_root"]):
        raise ValueError("Qualification preregistration differs from exact current driver/spec/input/freeze")
    check_hashes(hashes)
    sources_before, tests_before = bootstrap.source_inventory(), test_sources()
    if (sources_before != frozen["source_files"] or canonical.digest_json(sources_before) != frozen["source_root"]
            or tests_before != spec["test_sources"] or set(sources_before) - set(hashes)
            or set(tests_before) - set(hashes)):
        raise ValueError("Complete current source/test inventory not bound")
    suite, ids = collect(spec)
    if ids != spec["registered_test_ids"] or len(ids) != spec["registered_test_count"]:
        raise ValueError("Actual test identities/count/order differ from registration")
    required = importlib.import_module("tests.test_vscore3_collection_bridge").qualification_source_files()
    if required != spec["required_collection_inputs"] or set(required) - set(hashes):
        raise ValueError("Actual collection-required input inventory not bound")
    bootstrap.write_once(GATE / "invocation.json", {
        "format": "verislop.support018-suite-invocation/1", "source_root": frozen["source_root"],
        "input_root": canonical.digest_json(hashes), "driver_sha256": canonical.digest_file(Path(__file__)),
        "registered_test_ids": ids, "test_modules": spec["test_modules"],
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model_calls": 0, "task_inputs": False, "prior_pass_inheritance": False})
    started = time.monotonic()
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2, failfast=True,
                                    resultclass=RecordedResult).run(suite)
    sources_after, tests_after = bootstrap.source_inventory(), test_sources()
    check_hashes(hashes)
    exact = (result.started_ids == ids and result.testsRun == len(ids)
             and result.observations == [{"test_id": oid, "status": "PASS"} for oid in ids]
             and sources_before == sources_after and tests_before == tests_after)
    accepted = (result.wasSuccessful() and exact and not result.skipped
                and not result.expectedFailures and not result.unexpectedSuccesses)
    record = {"format": "verislop.support018-suite-result/1", "status": "PASS" if accepted else "FAIL",
              "registered_test_count": len(ids), "registered_test_ids": ids,
              "tests_run": result.testsRun, "started_ids": result.started_ids,
              "test_observations": result.observations, "failures": len(result.failures),
              "errors": len(result.errors), "skipped": len(result.skipped),
              "expected_failures": len(result.expectedFailures),
              "unexpected_successes": len(result.unexpectedSuccesses),
              "elapsed_milliseconds": int((time.monotonic()-started)*1000),
              "source_root_before": canonical.digest_json(sources_before),
              "source_root_after": canonical.digest_json(sources_after),
              "source_unchanged": sources_before == sources_after,
              "tests_unchanged": tests_before == tests_after,
              "qualification_inputs_unchanged": True, "input_root": canonical.digest_json(hashes),
              "model_calls": 0, "task_inputs": False, "prior_pass_inheritance": False}
    bootstrap.write_once(GATE / "run-result.json", record)
    return 0 if accepted else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "run"))
    parser.add_argument("--spec", type=Path, default=GATE / "qualification-specification.json")
    args = parser.parse_args()
    spec = bootstrap.load(args.spec)
    if args.action == "preflight":
        print(json.dumps(preflight(spec), sort_keys=True), flush=True)
        return 0
    if args.spec.resolve() != (GATE / "qualification-specification.json").resolve():
        raise ValueError("Run requires exact finalized qualification specification")
    return run(spec)


if __name__ == "__main__":
    raise SystemExit(main())
