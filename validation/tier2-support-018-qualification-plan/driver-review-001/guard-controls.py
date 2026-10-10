"""Finite driver guard harness with mock identities/results, no actual tests."""
from __future__ import annotations

import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest

BASE = Path(__file__).resolve().parent


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_once(path, value):
    with path.open("xb") as stream:
        stream.write(encode(value))


class Identity:
    def __init__(self, name):
        self.name = name

    def id(self):
        return self.name


def execute_control(name, original, planning):
    root = BASE / "scratch" / name
    gate = root / "qualification"
    gate.mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "generic.py").write_text("# unrelated guard-only source\n")
    (root / "tests/test_generic.py").write_text("# no executable fixture or test\n")
    (gate / "gate.py").write_bytes(original)
    canonical = SimpleNamespace(digest_file=lambda path: digest(Path(path).read_bytes()),
        digest_json=lambda value: digest(encode(value)))
    namespace = {"__file__": str(gate / "gate.py"), "ROOT": root, "GATE": gate,
        "Path": Path, "unittest": unittest, "os": os, "sys": sys,
        "datetime": datetime, "time": time, "canonical": canonical}
    tree = ast.parse(original)
    selected = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(gate / "gate.py"), "exec"), namespace)
    collection = ("tests.test_vscore3_collection_bridge.CollectionRegisteredTier2Tests."
                  "test_actual_frozen_collection_closure_and_retained_release_probe")
    namespace["COLLECTION_ID"] = collection
    modules = [row["module"] for row in planning["modules"]]
    ids = [identity for row in planning["modules"] for identity in row["ast_declared_test_ids"]]
    if name in ("COLLECTION-ONLY", "SKIP-MARKER"):
        modules = ["tests.test_vscore3_collection_bridge"]
        ids = [collection]
    if name == "EMPTY-SUITE":
        modules, ids = [], []
    if name == "DUPLICATE-IDENTITY":
        ids = [collection, collection]
    source_map = {"generic.py": canonical.digest_file(root / "generic.py")}
    test_map = {"tests/test_generic.py": canonical.digest_file(root / "tests/test_generic.py")}
    source_root = canonical.digest_json(source_map)
    frozen_source_map = source_map if name != "FAKE-FROZEN-SOURCE" else {"generic.py": "sha256:" + "0" * 64}
    frozen_root = canonical.digest_json(frozen_source_map)
    spec = {"source_root": frozen_root, "test_sources": test_map,
        "test_modules": modules, "registered_test_ids": ids, "registered_test_count": len(ids),
        "required_collection_inputs": ["generic.py", "tests/test_generic.py"]}
    write_once(gate / "qualification-specification.json", spec)
    write_once(gate / "source-freeze.json", {"source_files": frozen_source_map, "source_root": frozen_root})
    names = ["generic.py", "tests/test_generic.py", "qualification/gate.py",
             "qualification/qualification-specification.json", "qualification/source-freeze.json"]
    if name == "UNBOUND-DRIVER-MUTATION":
        names.remove("qualification/gate.py")
    if name == "SOURCE-FREEZE-MUTATION":
        names.remove("qualification/source-freeze.json")
    hashes = {path: canonical.digest_file(root / path) for path in names}
    if name == "WRONG-REGISTERED-HASH":
        hashes["generic.py"] = "sha256:" + "0" * 64
    write_once(gate / "qualification-inputs.json", {"source_hashes": hashes, "source_root": frozen_root})
    write_once(gate / "preregistration.json", {
        "driver_sha256": canonical.digest_file(gate / "gate.py"),
        "spec_sha256": canonical.digest_file(gate / "qualification-specification.json"),
        "input_manifest_sha256": canonical.digest_file(gate / "qualification-inputs.json"),
        "source_freeze_sha256": canonical.digest_file(gate / "source-freeze.json"),
        "input_root": canonical.digest_json(hashes), "source_root": frozen_root})
    before_external = {path.name: canonical.digest_file(path) for path in gate.iterdir() if path.is_file()}
    namespace["bootstrap"] = SimpleNamespace(load=lambda path: json.loads(Path(path).read_bytes()),
        source_inventory=lambda: {"generic.py": canonical.digest_file(root / "generic.py")},
        write_once=write_once)
    namespace["importlib"] = SimpleNamespace(import_module=lambda name: SimpleNamespace(
        qualification_source_files=lambda: ["generic.py", "tests/test_generic.py"]))
    identities = [Identity(identity) for identity in ids]
    if name == "SKIP-MARKER":
        identities[0].__unittest_skip__ = True

    class Loader:
        errors = []

        def loadTestsFromNames(self, names):
            return identities

    class Runner:
        def __init__(self, **kwargs):
            pass

        def run(self, suite):
            if name == "INPUT-MANIFEST-MUTATION":
                value = json.loads((gate / "qualification-inputs.json").read_bytes())
                value["task_inputs"] = True
                (gate / "qualification-inputs.json").write_bytes(encode(value))
            if name == "PREREGISTRATION-MUTATION":
                value = json.loads((gate / "preregistration.json").read_bytes())
                value["unbound_legacy_PASS"] = True
                (gate / "preregistration.json").write_bytes(encode(value))
            if name == "SOURCE-FREEZE-MUTATION":
                value = json.loads((gate / "source-freeze.json").read_bytes())
                value["unbound_generation_started"] = True
                (gate / "source-freeze.json").write_bytes(encode(value))
            if name == "UNBOUND-DRIVER-MUTATION":
                (gate / "gate.py").write_text("# substituted legacy PASS driver\n")
            if name == "SOURCE-MUTATION":
                (root / "generic.py").write_text("# mutated unrelated guard-only source\n")
            observed_ids = ids[:-1] if name == "INCOMPLETE-RESULT" else ids
            return SimpleNamespace(started_ids=observed_ids, testsRun=len(observed_ids),
                observations=[{"test_id": identity, "status": "PASS"} for identity in observed_ids],
                wasSuccessful=lambda: True, failures=[], errors=[], skipped=[],
                expectedFailures=[], unexpectedSuccesses=[])

    namespace["unittest"] = SimpleNamespace(TestSuite=list, TestLoader=Loader, TextTestRunner=Runner)
    if name == "LEGACY-PASS-ONLY":
        write_once(gate / "run-result.json", {"status": "PASS", "legacy": True})
    try:
        if name in ("COLLECTION-ONLY", "EMPTY-SUITE", "DUPLICATE-IDENTITY", "SKIP-MARKER"):
            _, selected_ids = namespace["collect"](spec)
            disposition = {"guard": "ACCEPT", "collected_count": len(selected_ids),
                "missing_planned_modules": sorted(set(row["module"] for row in planning["modules"]) - set(modules))}
        else:
            exit_code = namespace["run"](spec)
            result = json.loads((gate / "run-result.json").read_bytes())
            disposition = {"guard": "ACCEPT" if exit_code == 0 else "REJECT", "exit_code": exit_code,
                "record_status": result["status"], "record_qualification_inputs_unchanged": result["qualification_inputs_unchanged"]}
    except Exception as exc:
        disposition = {"guard": "REJECT", "exception_type": type(exc).__name__, "diagnostic": str(exc)}
    after_external = {path.name: canonical.digest_file(path) for path in gate.iterdir() if path.is_file()}
    changed = [name for name, old in before_external.items() if after_external.get(name) != old]
    return {"id": name, "disposition": disposition, "changed_external_binding_files": changed,
        "actual_tests_executed": 0, "mock_result_is_not_qualification_evidence": True}


def main():
    freeze_raw = (BASE / "input-freeze.json").read_bytes()
    freeze = json.loads(freeze_raw)
    for name, expected in freeze["files"].items():
        if digest((BASE / name).read_bytes()) != expected:
            raise RuntimeError("INPUT_MUTATION: " + name)
    original = (BASE / "registered-inputs/gate-reviewed.py").read_bytes()
    planning = json.loads((BASE / "registered-inputs/test-planning-inventory.json").read_bytes())
    controls = json.loads((BASE / "controls.json").read_bytes())
    results = [execute_control(control["id"], original, planning) for control in controls]
    for row, control in zip(results, controls):
        row["expected_guard"] = control["expected_guard"]
        row["matches_expected_counterexample_or_rejection"] = row["disposition"]["guard"] == control["expected_guard"]
    report = {"format": "verislop.support018-driver-guard-review/1",
        "reviewed_driver_sha256": digest(original), "input_freeze_sha256": digest(freeze_raw),
        "input_root_hash": freeze["input_root_hash"], "results": results,
        "actual_tests_executed": 0, "fixture_builds": 0, "model_calls": 0, "task_inputs": False,
        "testqualification_PASS_asserted": False,
        "guard_counterexamples_executed": len(results)}
    write_once(BASE / "guard-results.json", report)
    print(json.dumps(report, sort_keys=True))
    return 0 if all(row["matches_expected_counterexample_or_rejection"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
