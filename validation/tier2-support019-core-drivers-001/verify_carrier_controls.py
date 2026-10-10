"""Observe every fresh generic carrier/capture pure control at the current root."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXPECTED = "sha256:9930beff878848b05c8d69245fff12c1388f14254b6630504b36748c4c294366"
TEMPLATES = (
    ("support019_carrier_pure", "validation/tier2-carrier-context-support-019-implementation-002/test_candidate.py", "CandidateTests"),
    ("support019_capture_pure", "validation/tier2-carrier-context-support-019-implementation-002/capture-amendment-002/test_capture_controls.py", "CaptureControls"),
)


def digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started_ids, self.observations = [], []

    def startTest(self, test):
        self.started_ids.append(test.id())
        super().startTest(test)

    def addSuccess(self, test):
        self.observations.append({"test_id": test.id(), "status": "PASS"})
        super().addSuccess(test)

    def addFailure(self, test, error):
        self.observations.append({"test_id": test.id(), "status": "FAIL"})
        super().addFailure(test, error)

    def addError(self, test, error):
        self.observations.append({"test_id": test.id(), "status": "ERROR"})
        super().addError(test, error)

    def addSkip(self, test, reason):
        self.observations.append({"test_id": test.id(), "status": "SKIP"})
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, error):
        self.observations.append({"test_id": test.id(), "status": "EXPECTED_FAILURE"})
        super().addExpectedFailure(test, error)

    def addUnexpectedSuccess(self, test):
        self.observations.append({"test_id": test.id(), "status": "UNEXPECTED_SUCCESS"})
        super().addUnexpectedSuccess(test)

    def addSubTest(self, test, subtest, error):
        if error is not None:
            self.observations.append({"test_id": test.id(), "status": "SUBTEST_FAILURE"})
        super().addSubTest(test, subtest, error)


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
    def guard():
        for name, expected in frozen["source_hashes"].items():
            path = ROOT / name
            if (not path.is_file() or path.is_symlink() or path.resolve() != path.absolute()
                    or digest(path) != expected):
                raise ValueError("Frozen input changed: " + name)
        if canonical.digest_json(bootstrap.source_inventory()) != frozen["source_root"]:
            raise ValueError("Current source inventory changed")
        for name in ("synthetic_dataset/tools/bootstrap_tier2_carrier_view.py",
                     "validation/tier2-carrier-context-support-019-implementation-002/bootstrap_tier2_carrier_view.py"):
            if frozen["source_hashes"].get(name) != EXPECTED or digest(ROOT / name) != EXPECTED:
                raise ValueError("Reviewed production/candidate carrier binding mismatch")
        for name in [str(Path(__file__).relative_to(ROOT))] + [row[1] for row in TEMPLATES]:
            if frozen["source_hashes"].get(name) != digest(ROOT / name):
                raise ValueError("Carrier control source omitted: " + name)
    guard()
    suites, expected_ids = [], []
    loader = unittest.TestLoader()
    for module_name, source, class_name in TEMPLATES:
        spec = importlib.util.spec_from_file_location(module_name, ROOT / source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        suite = loader.loadTestsFromTestCase(getattr(module, class_name))
        ids = [test.id() for test in suite]
        if len(ids) != 15 or len(set(ids)) != 15:
            raise ValueError("Registered carrier/capture15 floor changed")
        suites.append(suite)
        expected_ids.extend(ids)
    if loader.errors or len(expected_ids) != len(set(expected_ids)):
        raise ValueError("Loader errors or duplicate pure control identities")
    start = datetime.now(timezone.utc).isoformat()
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2, failfast=True,
                                    resultclass=Result).run(unittest.TestSuite(suites))
    guard()
    accepted = (result.wasSuccessful() and result.testsRun == len(expected_ids)
                and result.started_ids == expected_ids
                and result.observations == [{"test_id": oid, "status": "PASS"} for oid in expected_ids]
                and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses)
    record = {"format": "verislop.support019-carrier-pure-observations/1", "status": "OBSERVED",
              "source_root": frozen["source_root"], "input_root": frozen["input_root"],
              "installed_source_sha256": EXPECTED, "registered_test_ids": expected_ids,
              "started_ids": result.started_ids, "cases": result.observations,
              "tests_run": result.testsRun, "failures": len(result.failures),
              "errors": len(result.errors), "skipped": len(result.skipped),
              "expected_failures": len(result.expectedFailures), "unexpected_successes": len(result.unexpectedSuccesses),
              "started_utc": start, "completed_utc": datetime.now(timezone.utc).isoformat(),
              "models_called": 0, "task_inputs": False, "qualification_authority": False}
    output = gate / "carrier-pure-result.json"
    with output.open("x") as stream:
        json.dump(record, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    return 0 if accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
