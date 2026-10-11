"""Observe every fresh generic carrier/capture pure control at the current root."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import ast
import base64
from contextlib import ExitStack
from functools import wraps
import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXPECTED = "sha256:774081ab079b0bb9086479782d065c9e4b91c372ecce765c248b533c1c2b666a"
TEMPLATES = (
    ("support019_carrier_pure", "validation/tier2-carrier-context-support-019-implementation-002/test_candidate.py", "CandidateTests"),
    ("support019_capture_pure", "validation/tier2-carrier-context-support-019-implementation-002/capture-amendment-002/test_capture_controls.py", "CaptureControls"),
)
SCHEMA_PATH = HERE / "WITNESS_SCHEMA.json"


def digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(value):
    """Snapshot known JSON/byte values without file reads or lossy coercion."""
    if isinstance(value, bytes):
        return {"encoding": "base64", "data": base64.b64encode(value).decode("ascii"),
                "sha256": "sha256:" + hashlib.sha256(value).hexdigest(), "byte_count": len(value)}
    if value is None or type(value) in (str, int, float, bool):
        return value
    if isinstance(value, Path):
        return {"encoding": "path", "value": str(value)}
    if isinstance(value, (tuple, list)):
        return [encoded(item) for item in value]
    if isinstance(value, dict) and all(type(key) is str for key in value):
        return {key: encoded(item) for key, item in value.items()}
    return {"encoding": "unavailable", "python_type": type(value).__module__ + "." + type(value).__qualname__}


class SemanticWitnesses:
    """Observe original calls in memory; only final sidecar publication writes."""
    def __init__(self, gate, frozen, schema):
        self.gate, self.frozen, self.schema = gate, frozen, schema
        self.case_id, self.active, self.frames = None, [], []
        self.references, self.raw_sources, self.source_pairs = {}, {}, []

    def source_ref(self, path):
        path = Path(path).absolute()
        relative = str(path.relative_to(ROOT))
        if relative not in self.references:
            if path.is_symlink() or path.resolve() != path:
                raise ValueError("Witness source must be canonical and direct: " + relative)
            raw = path.read_bytes()
            sha256 = "sha256:" + hashlib.sha256(raw).hexdigest()
            if self.frozen["source_hashes"].get(relative) != sha256:
                raise ValueError("Witness source omitted or changed: " + relative)
            self.raw_sources[relative] = raw
            self.references[relative] = {"path": relative,
                "sha256": sha256, "byte_count": len(raw)}
        return self.references[relative]

    def pair(self, role, module, symbols):
        reference = self.source_ref(module.__file__)
        source = self.raw_sources[reference["path"]].decode("utf-8")
        tree, fragments = ast.parse(source), []
        for symbol in symbols:
            if symbol == "READER_SOURCE":
                node = next(node for node in tree.body if isinstance(node, ast.Assign)
                            and any(isinstance(target, ast.Name) and target.id == symbol for target in node.targets))
                raw = ast.literal_eval(node.value).encode("utf-8")
                kind = "constant_bytes"
            else:
                node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == symbol)
                raw, kind = ast.get_source_segment(source, node).encode("utf-8"), "function_ast_bytes"
            fragments.append({"symbol": symbol, "kind": kind, "value": encoded(raw)})
        self.source_pairs.append({"role": role, "source_ref": reference, "fragments": fragments})

    def observe(self, original, kind, role, reference, symbol, args, kwargs):
        if self.case_id is None:
            return original(*args, **kwargs)
        sequence = len(self.frames) + 1
        frame = {"sequence": sequence, "case_id": self.case_id,
            "parent_sequence": self.active[-1] if self.active else None,
            "kind": kind, "role": role, "source_ref": reference, "symbol": symbol,
            "arguments": {"positional": encoded(args), "keyword": encoded(kwargs)},
            "returned_type": None, "returned_value": None, "exception": None}
        self.frames.append(frame)
        self.active.append(sequence)
        try:
            actual = original(*args, **kwargs)
        except BaseException as error:
            frame["exception"] = {"python_type": type(error).__module__ + "." + type(error).__qualname__,
                "arguments": encoded(error.args), "returncode": getattr(error, "returncode", None),
                "stdout": encoded(getattr(error, "stdout", None)),
                "stderr": encoded(getattr(error, "stderr", None)), "argv": encoded(getattr(error, "cmd", None))}
            raise
        else:
            frame["returned_type"] = type(actual).__module__ + "." + type(actual).__qualname__
            if kind == "subprocess":
                frame["returned_value"] = {"argv": encoded(actual.args), "cwd": encoded(kwargs.get("cwd")),
                    "returncode": actual.returncode, "stdout": encoded(actual.stdout), "stderr": encoded(actual.stderr)}
            else:
                frame["returned_value"] = encoded(actual)
            return actual
        finally:
            self.active.pop()

    def wrapper(self, original, kind, role, reference, symbol):
        @wraps(original)
        def delegated(*args, **kwargs):
            return self.observe(original, kind, role, reference, symbol, args, kwargs)
        return delegated

    def install(self, stack, module, source, class_name):
        reference = self.source_ref(ROOT / source)
        alias = "candidate" if class_name == "CandidateTests" else "capture"
        runner_name = "node_templates" if alias == "candidate" else "inert_node"
        stack.enter_context(patch.object(module, runner_name,
            self.wrapper(getattr(module, runner_name), runner_name, alias + "." + runner_name,
                         reference, runner_name)))
        test_class = getattr(module, class_name)
        original_setup = test_class.setUp
        reader_reference = self.source_ref(module.candidate.__file__)
        @wraps(original_setup)
        def observed_setup(instance):
            original_setup(instance)
            for name in ("carrier", "read"):
                original = getattr(instance, name, None)
                if callable(original):
                    origin = reader_reference if name == "read" else reference
                    symbol = "READER_SOURCE::carrier_view" if name == "read" else class_name + ".carrier"
                    setattr(instance, name, self.wrapper(original, name, alias + "." + name, origin, symbol))
        stack.enter_context(patch.object(test_class, "setUp", observed_setup))
        for name in ("candidate", "previous", "original"):
            target = getattr(module, name, None)
            if target is None:
                continue
            target_ref = self.source_ref(target.__file__)
            functions = self.schema["source_functions"]
            self.pair(alias + "." + name, target, ["READER_SOURCE"] + functions)
            for function in functions:
                stack.enter_context(patch.object(target, function,
                    self.wrapper(getattr(target, function), "source_function", name + "." + function,
                                 target_ref, function)))
        if hasattr(module, "factory"):
            factory = module.factory
            factory_ref = self.source_ref(factory.__file__)
            functions = self.schema["factory_source_functions"]
            self.pair("capture_factory", factory, functions)
            for function in functions:
                stack.enter_context(patch.object(factory, function,
                    self.wrapper(getattr(factory, function), "source_function", "capture_factory." + function,
                                 factory_ref, function)))

    def publish(self, expected_ids):
        cases = []
        for contract in self.schema["case_contracts"]:
            reference = self.source_ref(ROOT / contract["source"])
            source = self.raw_sources[reference["path"]].decode("utf-8")
            method = contract["exact_symbol"].split(".")[-1]
            node = next(node for node in ast.walk(ast.parse(source))
                        if isinstance(node, ast.FunctionDef) and node.name == method)
            selected = [frame for frame in self.frames if frame["case_id"] == contract["case_id"]]
            role_index = {}
            for frame in selected:
                role_index.setdefault(frame["role"], []).append(frame["sequence"])
            cases.append({"case_id": contract["case_id"], "source_ref": reference,
                "exact_symbol": contract["exact_symbol"], "source_only": contract["source_only"],
                "required_roles": contract["required_roles"], "independent_predicates": contract["independent_predicates"],
                "source_only_obligations": contract["source_only_obligations"],
                "frame_sequences": [frame["sequence"] for frame in selected], "role_index": role_index,
                "case_ast": encoded(ast.get_source_segment(source, node).encode("utf-8"))})
        producer_ref, schema_ref = self.source_ref(__file__), self.source_ref(SCHEMA_PATH)
        sidecar = {"format": self.schema["sidecar_format"], "source_root": self.frozen["source_root"],
            "input_root": self.frozen["input_root"], "installed_source_sha256": EXPECTED,
            "producer": producer_ref, "schema": schema_ref,
            "source_refs": [self.references[key] for key in sorted(self.references)],
            "source_pairs": self.source_pairs, "registered_test_ids": expected_ids,
            "cases": cases, "frames": self.frames, "models_called": 0, "task_inputs": False,
            "qualification_authority": False}
        raw = (json.dumps(sidecar, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
        output = self.gate / self.schema["sidecar_path"]
        with output.open("xb") as stream:
            stream.write(raw)
        return {"path": str(output.relative_to(ROOT)),
                "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(), "byte_count": len(raw)}


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started_ids, self.observations = [], []

    def startTest(self, test):
        self.witnesses.case_id = test.id()
        self.started_ids.append(test.id())
        super().startTest(test)

    def stopTest(self, test):
        super().stopTest(test)
        self.witnesses.case_id = None

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
                     "validation/tier2-carrier-context-support-019-implementation-004/bootstrap_tier2_carrier_view.py"):
            if frozen["source_hashes"].get(name) != EXPECTED or digest(ROOT / name) != EXPECTED:
                raise ValueError("Reviewed production/candidate carrier binding mismatch")
        for name in [str(Path(__file__).relative_to(ROOT)), str(SCHEMA_PATH.relative_to(ROOT))] + [row[1] for row in TEMPLATES]:
            if frozen["source_hashes"].get(name) != digest(ROOT / name):
                raise ValueError("Carrier control source omitted: " + name)
    guard()
    # Preserve the original30 witness semantics while binding current legacy APIs.
    installed_source = (ROOT / "synthetic_dataset/tools/bootstrap_tier2_carrier_view.py").read_text()
    historical_source = (ROOT / "validation/tier2-carrier-context-support-019-implementation-002/bootstrap_tier2_carrier_view.py").read_text()
    legacy_symbols = {"inline_source", "inline_command", "inline_prefix", "own_session_key",
                      "_closed_view", "initial_session_template", "next_session_template"}
    def legacy_ast(source):
        return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(source).body
                if isinstance(node, ast.FunctionDef) and node.name in legacy_symbols}
    if legacy_ast(installed_source) != legacy_ast(historical_source):
        raise ValueError("CURRENT_LEGACY_CARRIER_AST_CHANGED")
    def reader_literal(source):
        return next(ast.literal_eval(node.value) for node in ast.parse(source).body
                    if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "READER_SOURCE"
                                                           for target in node.targets))
    if reader_literal(installed_source) != reader_literal(historical_source):
        raise ValueError("CURRENT_LEGACY_CARRIER_READER_CHANGED")
    schema = json.loads(SCHEMA_PATH.read_text())
    witnesses = SemanticWitnesses(gate, frozen, schema)
    modules = []
    suites, expected_ids = [], []
    loader = unittest.TestLoader()
    for module_name, source, class_name in TEMPLATES:
        spec = importlib.util.spec_from_file_location(module_name, ROOT / source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        modules.append((module, source, class_name))
        suite = loader.loadTestsFromTestCase(getattr(module, class_name))
        ids = [test.id() for test in suite]
        if len(ids) != 15 or len(set(ids)) != 15:
            raise ValueError("Registered carrier/capture15 floor changed")
        suites.append(suite)
        expected_ids.extend(ids)
    if loader.errors or len(expected_ids) != len(set(expected_ids)):
        raise ValueError("Loader errors or duplicate pure control identities")
    if [case["case_id"] for case in schema["case_contracts"]] != expected_ids:
        raise ValueError("Witness contracts do not preserve the exact registered30 identities")
    # Preload source-only generic specifications; no wrapper performs file I/O.
    for relative in (
        "validation/tier2-carrier-context-support-019-implementation-002/prepare_unrelated_fixture.py",
        "validation/tier2-carrier-context-support-019-implementation-002/prepared-qualification-protocol.json",
        "validation/tier2-carrier-context-support-019-implementation-002/hash-manifest.json",
        "validation/tier2-carrier-context-support-019-implementation-002/capture-amendment-001/hash-manifest.json",
        "validation/tier2-carrier-context-support-019-implementation-002/capture-amendment-002/registration.json",
    ):
        reference = witnesses.source_ref(ROOT / relative)
        witnesses.source_pairs.append({"role": "source_only_generic_input", "source_ref": reference,
            "fragments": [{"symbol": "FILE_BYTES", "kind": "constant_bytes",
                           "value": encoded(witnesses.raw_sources[relative])}]})
    start = datetime.now(timezone.utc).isoformat()
    def result_factory(*positional, **keyword):
        value = Result(*positional, **keyword)
        value.witnesses = witnesses
        return value
    with ExitStack() as stack:
        for module, source, class_name in modules:
            witnesses.install(stack, module, source, class_name)
        original_run = subprocess.run
        stack.enter_context(patch.object(subprocess, "run", witnesses.wrapper(original_run, "subprocess",
            "runtime.subprocess.run", witnesses.source_ref(__file__), "subprocess.run")))
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2, failfast=True,
                                        resultclass=result_factory).run(unittest.TestSuite(suites))
    guard()
    semantic_witnesses_ref = witnesses.publish(expected_ids)
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
    record["semantic_witnesses_ref"] = semantic_witnesses_ref
    output = gate / "carrier-pure-result.json"
    with output.open("x") as stream:
        json.dump(record, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    return 0 if accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
