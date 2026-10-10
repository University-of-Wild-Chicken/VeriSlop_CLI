"""Registered local fixture verifier; channel/build components stay unresolved."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = {}
    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes[test._testMethodName] = "PASS"
    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.outcomes[test._testMethodName] = "FAIL"
    def addError(self, test, error):
        super().addError(test, error)
        self.outcomes[test._testMethodName] = "ERROR"
    def addSubTest(self, test, subtest, error):
        super().addSubTest(test, subtest, error)
        if error is not None:
            self.outcomes[test._testMethodName] = "FAIL"


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    raw_manifest = args.manifest.read_bytes()
    manifest = json.loads(raw_manifest)
    mismatches = [path for path, expected in manifest["files"].items()
                  if digest((REPO / path).read_bytes()) != expected]
    if mismatches:
        report = {"local_status": "FAIL", "code": "INPUT_MUTATION", "paths": mismatches,
                  "engineering_input_root": digest(raw_manifest), "tests_run": 0}
        (args.output / "report.json").write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
        return 1
    spec = importlib.util.spec_from_file_location("unrelated_carrier_view_tests", REPO / "tests/test_tier2_carrier_views.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=RecordedResult).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(module.CarrierViewTests))
    (args.output / "unittest.log").write_text(stream.getvalue())
    checks = {}
    for claim, methods in module.CHECK_TESTS.items():
        passed = all(result.outcomes.get(method) == "PASS" for method in methods)
        unresolved = ("actual tool-channel probe not yet bound" if claim == "CV-004" else
                      "parent new-root two isolated builds/comparisons not yet bound" if claim == "CV-008" else None)
        checks[claim] = {"local_status": "PASS" if passed else "FAIL", "tests": methods,
                         "disposition": "UNRESOLVED" if passed and unresolved else "PASS" if passed else "FAIL",
                         "unresolved_reason": unresolved}
    controls = {}
    for index in range(1, 17):
        prefix = f"test_n{index:03d}_"
        methods = [name for name in result.outcomes if name.startswith(prefix)]
        controls[f"N-{index:03d}"] = {"tests": methods, "local_status": "PASS" if methods and all(result.outcomes[name] == "PASS" for name in methods) else "FAIL"}
    report = {"format": "verislop.carrier-view-local-evidence/0.1", "local_status": "PASS" if result.wasSuccessful() else "FAIL",
              "engineering_input_root": digest(raw_manifest), "manifest_sha256": digest(raw_manifest),
              "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "checks": checks, "negative_controls": controls, "test_outcomes": result.outcomes,
              "runtime": sys.version, "model_calls": 0, "native_runs": 0,
              "llm_consumption_attested": False, "semantic_acceptance_or_lifecycle_authority": False,
              "qualification_status": "UNRESOLVED_CHANNEL_AND_UNIFIED_NEW_ROOT_BUILDS"}
    (args.output / "report.json").write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print(json.dumps({"local_status": report["local_status"], "tests_run": result.testsRun, "report": str(args.output / "report.json")}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
