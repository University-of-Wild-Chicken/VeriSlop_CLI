#!/usr/bin/env python3
"""Reconcile only newly registered support018 evidence; no builds or models.

The specification was written before this implementation. This program is an
artifact admission checker, not a test runner or an authority for consumption,
semantic acceptance, TESTED, universal correctness, or historical PASS reuse.
"""
from __future__ import annotations

import argparse
import ast
import base64
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DEFAULT_GATE = ROOT / "validation/tier2-support-018-qualification"
SPEC = HERE / "specification.json"
SCHEMA = HERE / "report-schema.json"
COLLECTION_ID = ("tests.test_vscore3_collection_bridge.CollectionRegisteredTier2Tests."
                 "test_actual_frozen_collection_closure_and_retained_release_probe")
PHASE_IDS = ["registered-suite", "carrier-fixtures", "unicode-kernel", "ground-kernel"]
MODULE_FLOOR = ["tests.test_vscore3_collection_bridge", "tests.test_vscore3_proof_support",
                "tests.test_vscore3_name_identity", "tests.test_vscore3_readable",
                "tests.test_vscore3_readable_cli", "tests.test_vscore3_workflow_unit",
                "tests.test_vscore3_closure_dispatch", "tests.test_bootstrap_tier2",
                "tests.test_vscore3_review_replay", "tests.test_review_counterexamples",
                "tests.test_provider_unbounded_timeout", "tests.test_run_unbounded_budget",
                "tests.test_tier2_carrier_views", "tests.test_vscore3_ground_support_018",
                "tests.test_unicode_lean_literals_018"]
GROUPS = {
    "Q018-01": ["guards", "phases"], "Q018-02": ["guards", "phases", "suite"],
    "Q018-03": ["guards", "phases", "suite", "unicode"],
    "Q018-04": ["guards", "phases", "suite", "carrier"],
    "Q018-05": ["guards", "phases", "suite", "carrier"],
    "Q018-06": ["guards", "phases", "channel"],
    "Q018-07": ["guards", "phases", "suite", "carrier"],
    "Q018-08": ["guards", "phases", "suite", "carrier", "ground"],
    "Q018-09": ["guards", "phases", "ground"],
    "Q018-10": ["guards", "phases", "ground", "unicode"],
    "Q018-11": ["guards", "phases", "ground"],
    "Q018-12": ["guards", "phases", "ground", "suite"],
    "Q018-13": ["guards", "phases", "ground"],
    "Q018-14": ["guards", "phases", "carrier", "ground", "unicode"],
    "Q018-15": ["guards", "phases", "suite", "collection"],
    "Q018-16": ["guards", "phases", "suite", "collection"],
    "Q018-17": ["guards", "phases", "suite", "collection"],
    "Q018-18": ["guards", "phases", "suite", "carrier", "channel", "unicode", "ground", "collection"],
}


class Block(ValueError):
    pass


def need(condition, code):
    if not condition:
        raise Block(code)


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def same_hash(actual, expected):
    return (isinstance(actual, str) and isinstance(expected, str)
            and actual.removeprefix("sha256:") == expected.removeprefix("sha256:")
            and re.fullmatch(r"[0-9a-f]{64}", expected.removeprefix("sha256:")) is not None)


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "DUPLICATE_JSON_KEY:" + key)
        result[key] = value
    return result


def parse(data):
    try:
        return json.loads(data.decode("utf-8", "strict"), object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(Block("NONFINITE_JSON")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Block("MALFORMED_JSON:" + str(exc)) from exc


def integer(value, code, minimum=0):
    need(type(value) is int and value >= minimum, code)
    return value


def utc_timestamp(value, code):
    need(isinstance(value, str) and re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?\+00:00", value), code)
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError as exc:
        raise Block(code) from exc
    need(parsed.utcoffset() == datetime.timedelta(0), code)
    return parsed


def write_once(path, value):
    data = (json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(data)


class Reconciliation:
    def __init__(self, gate):
        self.gate = gate
        self.output = gate / "final-reconciliation"
        self.evidence = {}
        self.results = {}
        self.phase_receipts = []
        self.hashes = {}
        self.external = {}
        self.toolchain_manifest = []
        self.registration = {}
        self.spec = {}
        self.freeze = {}
        self.plan = parse(SPEC.read_bytes())
        self.bootstrap = self.canonical = self.leanbridge = self.policy = None
        self.snapshot = None
        self.pkg = None

    def path(self, value, base=ROOT):
        need(isinstance(value, str) and value, "INVALID_PATH")
        rel = Path(value)
        need(not rel.is_absolute() and ".." not in rel.parts and rel.as_posix() == value,
             "NONCANONICAL_RELATIVE_PATH:" + value)
        path = base / rel
        need(path.is_file() and not path.is_symlink() and path.resolve() == path.absolute(),
             "MISSING_OR_INDIRECT_EVIDENCE:" + value)
        return path

    def read(self, path, expected=None):
        need(path.is_file() and not path.is_symlink() and path.resolve() == path.absolute(),
             "MISSING_OR_INDIRECT_EVIDENCE:" + str(path))
        data = path.read_bytes()
        digest = sha(data)
        previous = self.evidence.get(str(path))
        need(previous is None or previous == {"sha256": digest, "byte_count": len(data)},
             "EVIDENCE_CHANGED_BETWEEN_READS:" + str(path))
        if expected is not None:
            need(same_hash(digest, expected), "HASH_MISMATCH:" + str(path))
        if previous is None:
            self.evidence[str(path)] = {"sha256": digest, "byte_count": len(data)}
        return data

    def document(self, path, expected=None):
        return parse(self.read(path, expected))

    def registered(self, path):
        name = path.relative_to(ROOT).as_posix()
        need(name in self.hashes, "UNREGISTERED_VERIFIER_OR_INPUT:" + name)
        self.read(path, self.hashes[name])
        return path

    def module(self, name, path):
        self.registered(path)
        definition = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(definition)
        sys.modules[name] = module
        definition.loader.exec_module(module)
        return module

    def record_step(self, name, function):
        before = set(self.evidence)
        try:
            detail = function()
            self.results[name] = {"status": "VERIFIED", "actual_predicates": detail,
                                  "blocking_reasons": []}
        except (Block, AssertionError, ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
            self.results[name] = {"status": "BLOCKED", "actual_predicates": {},
                                  "blocking_reasons": [str(exc) or type(exc).__name__]}
        except Exception as exc:
            self.results[name] = {"status": "INFRASTRUCTURE_FAILURE", "actual_predicates": {},
                                  "blocking_reasons": [type(exc).__name__ + ": " + str(exc)]}
        self.results[name]["evidence"] = sorted(set(self.evidence) - before)

    def guard(self):
        for name, digest in {**self.hashes, **self.external}.items():
            self.read(self.path(name), digest)
        sources = self.bootstrap.source_inventory()
        tests = {p.relative_to(ROOT).as_posix(): sha(self.read(p))
                 for p in sorted((ROOT / "tests").rglob("*.py"))}
        need(sources == self.freeze["source_files"] and
             self.canonical.digest_json(sources) == self.freeze["source_root"], "CURRENT_SOURCE_ROOT_MUTATION")
        need(tests == self.spec["test_sources"], "COMPLETE_TEST_MAP_MUTATION")
        need(not (set(sources) | set(tests) | set(self.spec["required_collection_inputs"])) - set(self.hashes),
             "INCOMPLETE_REGISTERED_SOURCE_TEST_COLLECTION_MAP")
        environment = {"toolchain": self.leanbridge.resolve_toolchain().identity(),
                       "kernel_tool_hash": self.leanbridge.kernel_tool_hash(),
                       "policy_hash": self.policy.policy_hash(self.policy.get("strict"))}
        need(all(environment[key] == self.spec[key] for key in environment), "TOOLCHAIN_KERNEL_POLICY_MUTATION")
        for row in self.toolchain_manifest:
            p = Path(row["path"])
            need(p.is_absolute(), "UNICODE_TOOLCHAIN_MANIFEST_PATH_NOT_ABSOLUTE")
            data = self.read(p, row["sha256"])
            need(len(data) == integer(row["bytes"], "BAD_TOOLCHAIN_BYTE_COUNT"), "TOOLCHAIN_BYTE_COUNT_MISMATCH")
        return {"source_root": self.freeze["source_root"],
                "input_root": self.canonical.digest_json(self.hashes),
                "source_files": len(sources), "test_files": len(tests),
                "input_files": len(self.hashes), "external_bindings": self.external,
                "environment": environment, "unicode_manifest_files": len(self.toolchain_manifest)}

    def entry(self):
        need(sys.flags.optimize == 0, "ASSERTION_BASED_REGISTERED_VERIFIERS_DISABLED")
        inputs = self.document(self.gate / "qualification-inputs.json")
        self.hashes = inputs["source_hashes"]
        need(isinstance(self.hashes, dict) and self.hashes, "EMPTY_INPUT_MANIFEST")
        for name, digest in self.hashes.items():
            self.read(self.path(name), digest)
        self.external = {p.relative_to(ROOT).as_posix(): sha(self.read(p)) for p in
                         (self.gate / "qualification-inputs.json", self.gate / "preregistration.json")}
        for p in (Path(__file__), SPEC, SCHEMA, HERE / "schema-amendment-001.json",
                  HERE / "finalizer-registration.json", self.gate / "source-freeze.json",
                  self.gate / "qualification-specification.json", self.gate / "gate.py",
                  self.gate / "prepare-inputs.py", self.gate / "execute-phases.py"):
            self.registered(p)
        self.spec = self.document(self.gate / "qualification-specification.json")
        self.freeze = self.document(self.gate / "source-freeze.json")
        prereg = self.document(self.gate / "preregistration.json")
        self.registration = self.document(HERE / "finalizer-registration.json")
        reg = self.registration
        need(reg["format"] == "verislop.support018-finalizer-registration/1" and
             reg["closure_id"] == self.spec["closure_id"], "FINALIZER_REGISTRATION_MISMATCH")
        for key, path in (("verifier", Path(__file__)), ("specification", SPEC), ("report_schema", SCHEMA)):
            need(self.path(reg[key]["path"]) == path and
                 same_hash(reg[key]["sha256"], sha(self.read(path))), "FINALIZER_DECLARATION_MISMATCH:" + key)
        need(reg["invocation"]["output"] == "final-reconciliation" and
             reg["invocation"]["accepted_exit_code"] == 0, "FINALIZER_OUTPUT_OR_EXIT_MAPPING_CHANGED")
        expected_invocation = [sys.executable, str(Path(__file__)), "--qualification-root", str(self.gate)]
        need(reg["invocation"]["argv"] == expected_invocation, "FINALIZER_INVOCATION_NOT_EXACTLY_REGISTERED")
        for name in reg["producer_paths"]:
            self.registered(self.path(name))
        need([r["path"] for r in reg["repair_amendments"]] ==
             [(HERE / n).relative_to(ROOT).as_posix() for n in
              ("repair-amendment-001.json", "repair-amendment-002.json")], "RECONCILER_REPAIR_AMENDMENTS_NOT_REGISTERED")
        for reference in reg["repair_amendments"]:
            self.registered(self.path(reference["path"]))
            self.read(self.path(reference["path"]), reference["sha256"])
        for reference in (self.plan["original_plan"], self.plan["prospective_amendment"]):
            self.registered(self.path(reference["path"]))
            self.read(self.path(reference["path"]), reference["sha256"])
        original = self.document(self.path(self.plan["original_plan"]["path"]))
        need([{k: v for k, v in c.items() if k != "actual_reconciliation_predicates"}
              for c in self.plan["claims"]] == original["claims"], "ORIGINAL_CLAIM_PREDICATE_OR_SCOPE_WEAKENED")
        sys.path[:0] = [str(ROOT), str(ROOT / "tests"), str(ROOT / "validation/tier2-ground-replay-support-018-design")]
        from synthetic_dataset.tools import bootstrap_tier2
        from verislop import canonical, leanbridge, policy
        self.bootstrap, self.canonical = bootstrap_tier2, canonical
        self.leanbridge, self.policy = leanbridge, policy
        for key, path in (("driver_sha256", self.gate / "gate.py"),
                          ("spec_sha256", self.gate / "qualification-specification.json"),
                          ("input_manifest_sha256", self.gate / "qualification-inputs.json"),
                          ("source_freeze_sha256", self.gate / "source-freeze.json")):
            need(same_hash(prereg[key], sha(self.read(path))), "PREREGISTRATION_BINDING_MISMATCH:" + key)
        root = canonical.digest_json(self.hashes)
        need(prereg["input_root"] == inputs["input_root"] == root, "INPUT_ROOT_MISMATCH")
        need(prereg["source_root"] == inputs["source_root"] == self.freeze["source_root"] ==
             self.spec["source_root"], "SOURCE_ROOT_MISMATCH")
        need(self.freeze["generation_started"] is False and prereg["generation_started"] is False,
             "NOT_A_PREEXECUTION_FREEZE")
        need(self.spec["model_calls"] == 0 and self.spec["task_inputs"] is False and
             self.spec["prior_pass_inheritance"] is False and self.spec["inference_timeout"] is None,
             "AUTHORITY_OR_BUDGET_SCOPE_CHANGED")
        need(self.spec["claims_plan_sha256"] == sha(self.read(self.path(self.spec["claims_plan"]))),
             "ROOT_CLAIM_AMENDMENT_NOT_BOUND")
        need([p["id"] for p in self.spec["execution_phases"]] == PHASE_IDS == self.plan["phase_order"] and
             prereg["execution_phases"] == self.spec["execution_phases"], "PHASE_REGISTRATION_CHANGED")
        need([c["id"] for c in self.plan["claims"]] == list(GROUPS), "ORIGINAL_18_CLAIM_IDENTITY_CHANGED")
        unicode_manifest = ROOT / "validation/tier2-unicode-literal-support-018/runs/qualification-018/manifest.json"
        self.toolchain_manifest = self.document(unicode_manifest)["files"]
        need(isinstance(self.toolchain_manifest, list) and self.toolchain_manifest and
             len({r["path"] for r in self.toolchain_manifest}) == len(self.toolchain_manifest),
             "CURRENT_UNICODE_TOOLCHAIN_MANIFEST_MISSING_OR_DUPLICATE")
        return self.guard()

    def log_reference(self, row, base=ROOT, byte_key="byte_count"):
        path = self.path(row["path"], base)
        data = self.read(path, row["sha256"])
        need(len(data) == integer(row[byte_key], "LOG_BYTE_COUNT_NOT_INTEGER"), "LOG_BYTE_COUNT_MISMATCH")
        return data

    def compile_process(self, process, source, module, timeout_max=30, memory_mb=None):
        need(isinstance(process, dict) and process["format"] == self.leanbridge.COMPILE_PROCESS_FORMAT and
             process["input"]["module"] == module and
             same_hash(process["input"]["module_source_sha256"], sha(source)), "COMPILE_PROCESS_SOURCE_OR_SCHEMA_UNBOUND")
        need(type(process["returncode"]) is int and type(process["timed_out"]) is bool and
             isinstance(process["requested_argv"], list) and process["requested_argv"] and
             isinstance(process["launcher_argv"], list) and process["launcher_argv"] and
             process["sandbox_profile"], "COMPILE_PROCESS_ACTUAL_NUMERIC_OR_ISOLATION_EVIDENCE_MISSING")
        for stream in ("stdout", "stderr"):
            ref = process[stream]
            try:
                data = base64.b64decode(ref["content_b64"], validate=True)
            except (ValueError, TypeError) as exc:
                raise Block("COMPILE_PROCESS_RAW_OUTPUT_INVALID") from exc
            need(type(ref["byte_count"]) is int and ref["byte_count"] == len(data) and
                 same_hash(ref["sha256"], sha(data)), "COMPILE_PROCESS_RETAINED_BYTES_OR_HASH_MISMATCH")
        limits = process["requested_limits"]
        need(0 < float(limits["wall_timeout_seconds"]) <= timeout_max and
             type(limits["lean_heap_mb"]) is int and limits["lean_heap_mb"] > 0,
             "COMPILE_PROCESS_LIMITS_UNBOUND")
        if memory_mb is not None:
            need(limits["lean_heap_mb"] == memory_mb, "COMPILE_PROCESS_REGISTERED_MEMORY_LIMIT_CHANGED")
        return process

    def phases(self):
        invocation = self.document(self.gate / "phase-launcher-invocation.json")
        need(invocation["input_root"] == self.canonical.digest_json(self.hashes) and
             invocation["source_root"] == self.freeze["source_root"] and
             invocation["phases"] == self.spec["execution_phases"], "PHASE_LAUNCHER_STALE")
        need(invocation["model_calls"] == 0 and invocation["task_inputs"] is False and
             invocation["inference_timeout"] is None, "PHASE_SCOPE_CHANGED")
        frozen_at = utc_timestamp(self.freeze["created_at_utc"], "SOURCE_FREEZE_TIMESTAMP_NOT_UTC_ISO")
        prereg = self.document(self.gate / "preregistration.json")
        registered_at = utc_timestamp(prereg["created_utc"], "PREREGISTRATION_TIMESTAMP_NOT_UTC_ISO")
        launcher_at = utc_timestamp(invocation["started_utc"], "PHASE_LAUNCHER_TIMESTAMP_NOT_UTC_ISO")
        need(frozen_at <= registered_at <= launcher_at, "PREREGISTRATION_NOT_BEFORE_ACTUAL_LAUNCHER")
        previous_completed = launcher_at
        rows = []
        for phase in self.spec["execution_phases"]:
            row = self.document(self.gate / (phase["id"] + "-actual-process-receipt.json"))
            need(row["format"] == "verislop.support018-actual-process-receipt/1" and row["id"] == phase["id"],
                 "PHASE_RECEIPT_SCHEMA_OR_ID_MISMATCH")
            need(row["argv"] == phase["argv"] and row["cwd"] == str(ROOT), "ACTUAL_PHASE_COMMAND_MISMATCH")
            need(row["registered_environment"] == phase["environment"] == {"PYTHONPATH": str(ROOT)},
                 "ACTUAL_PHASE_REGISTERED_ENVIRONMENT_CHANGED")
            need(type(row["returncode"]) is int and row["returncode"] == phase["accepted_exit_code"] == 0 and
                 row["timed_out"] is False, "ACTUAL_PHASE_NOT_NUMERIC_SUCCESS:" + phase["id"])
            integer(row["pid"], "ACTUAL_PHASE_PID_MISSING", 1)
            need(row["input_root"] == self.canonical.digest_json(self.hashes) and
                 row["source_root"] == self.freeze["source_root"], "ACTUAL_PHASE_STALE:" + phase["id"])
            for stream in ("stdout", "stderr"):
                need(row[stream]["path"] == (self.gate / (phase["id"] + "." + stream + ".log")).relative_to(ROOT).as_posix(),
                     "PHASE_LOG_PATH_SUBSTITUTED")
                self.log_reference(row[stream])
            started = utc_timestamp(row["started_utc"], "ACTUAL_PHASE_START_TIMESTAMP_NOT_UTC_ISO")
            completed = utc_timestamp(row["completed_utc"], "ACTUAL_PHASE_END_TIMESTAMP_NOT_UTC_ISO")
            need(previous_completed <= started <= completed, "ACTUAL_PHASE_INTERVAL_NOT_REGISTERED_SERIAL_ORDER")
            previous_completed = completed
            rows.append(row)
        self.phase_receipts = rows
        return {"actual_numeric_receipts": len(rows), "registered_order": PHASE_IDS,
                "current_root_bound": True, "logs_rehashed": True,
                "serial_intervals_checked": True, "preregistration_before_launcher_before_phases": True}

    def require_suite_methods(self, methods):
        observed = self.suite_result["test_observations"]
        mapping = {r["test_id"]: r["status"] for r in observed}
        need(all(mapping.get(name) == "PASS" for name in methods), "MISSING_ACTUAL_METHOD_OUTCOME")

    def suite(self):
        result = self.document(self.gate / "run-result.json")
        invocation = self.document(self.gate / "invocation.json")
        ids = self.spec["registered_test_ids"]
        n = integer(self.spec["registered_test_count"], "UNREGISTERED_TEST_COUNT", 1)
        need(len(ids) == len(set(ids)) == n and COLLECTION_ID in ids, "REGISTERED_IDENTITIES_INCOMPLETE_OR_DUPLICATED")
        need(set(MODULE_FLOOR) <= set(self.spec["test_modules"]) and
             all(any(oid.startswith(module + ".") for oid in ids) for module in MODULE_FLOOR), "MANDATORY_MODULE_OR_ID_OMITTED")
        need(invocation["registered_test_ids"] == ids and invocation["test_modules"] == self.spec["test_modules"] and
             invocation["source_root"] == self.freeze["source_root"] and
             invocation["input_root"] == self.canonical.digest_json(self.hashes), "SUITE_INVOCATION_STALE")
        need(same_hash(invocation["driver_sha256"], sha(self.read(self.gate / "gate.py"))), "SUITE_DRIVER_NOT_CURRENT")
        need(result["registered_test_ids"] == result["started_ids"] == ids and
             result["registered_test_count"] == result["tests_run"] == n, "ACTUAL_SUITE_ORDER_OR_COUNT_MISMATCH")
        need(result["test_observations"] == [{"test_id": oid, "status": "PASS"} for oid in ids],
             "ACTUAL_SUITE_OUTCOMES_NOT_EXACT")
        for key in ("failures", "errors", "skipped", "expected_failures", "unexpected_successes"):
            need(type(result[key]) is int and result[key] == 0, "SUITE_NONZERO_OR_NONNUMERIC:" + key)
        root = self.freeze["source_root"]
        need(result["source_root_before"] == result["source_root_after"] == root and
             result["input_root"] == self.canonical.digest_json(self.hashes), "SUITE_ROOT_NOT_CURRENT")
        need(result["external_bindings_before"] == result["external_bindings_after"], "SUITE_EXTERNAL_BINDING_MUTATION")
        mandatory = [self.gate / name for name in ("gate.py", "qualification-specification.json", "qualification-inputs.json",
                                                  "source-freeze.json", "preregistration.json")]
        need(set(result["external_bindings_before"]) == {p.relative_to(ROOT).as_posix() for p in mandatory},
             "SUITE_EXTERNAL_BINDINGS_OMITTED")
        for name, digest in result["external_bindings_before"].items():
            self.read(self.path(name), digest)
        need(result["status"] == "PASS" and all(result[k] is True for k in
             ("source_unchanged", "tests_unchanged", "qualification_inputs_unchanged")), "SUITE_BINDING_GUARD_FAILED")
        for record in (invocation, result):
            need(record["model_calls"] == 0 and record["task_inputs"] is False and
                 record["prior_pass_inheritance"] is False, "SUITE_SCOPE_CHANGED")
        # Independently recollect registered identities, without running tests.
        driver = self.module("support018_final_registered_gate", self.gate / "gate.py")
        _, actual_ids = driver.collect(self.spec)
        need(actual_ids == ids, "CURRENT_LOADER_IDENTITY_OR_SKIP_GUARD_MISMATCH")
        self.suite_result = result
        return {"registered_count": n, "ordered_actual_count": len(result["started_ids"]),
                "mandatory_modules": MODULE_FLOOR, "collection_identity": COLLECTION_ID,
                "failure_error_skip_expected_unexpected_counts": [0, 0, 0, 0, 0],
                "actual_driver_identity_recollection": actual_ids}

    def carrier(self):
        report = self.document(self.gate / "carrier-fixtures/report.json")
        manifest_path = self.gate / "verification-source-manifest.json"
        self.registered(manifest_path)
        need(report["format"] == "verislop.carrier-view-local-evidence/0.1" and
             report["local_status"] == "PASS" and report["tests_run"] == 19 and
             report["failures"] == report["errors"] == 0, "CARRIER_LOCAL_ACTUAL_RUN_INCOMPLETE")
        need(same_hash(report["manifest_sha256"], sha(self.read(manifest_path))) and
             report["engineering_input_root"] == report["manifest_sha256"], "CARRIER_WRONG_CURRENT_INPUT_MANIFEST")
        registered = self.plan["carrier"]
        need(set(report["test_outcomes"]) == set(registered["methods"]) and
             all(value == "PASS" for value in report["test_outcomes"].values()), "CARRIER_19_EXACT_METHOD_RESULTS_MISSING")
        prefix = registered["class_prefix"]
        self.require_suite_methods([prefix + method for method in registered["methods"]])
        need(set(report["checks"]) == set(registered["mandatory_checks"]), "CARRIER_EIGHT_CHECKS_MISMATCH")
        for claim, methods in registered["check_test_map"].items():
            row = report["checks"][claim]
            need(row["tests"] == methods and row["local_status"] == "PASS", "CARRIER_CHECK_MAPPING_MISMATCH:" + claim)
            disposition = "UNRESOLVED" if claim in ("CV-004", "CV-008") else "PASS"
            need(row["disposition"] == disposition, "CARRIER_LOCAL_OVERCLAIM_OR_WRONG_DISPOSITION:" + claim)
        need(set(report["negative_controls"]) == set(registered["control_ids"]), "CARRIER_16_CONTROLS_MISSING")
        for index in range(1, 17):
            key = f"N-{index:03d}"
            methods = [m for m in registered["methods"] if m.startswith(f"test_n{index:03d}_")]
            row = report["negative_controls"][key]
            need(methods and row["tests"] == methods and row["local_status"] == "PASS", "CARRIER_NEGATIVE_MAPPING_MISMATCH:" + key)
        log = self.read(self.gate / "carrier-fixtures/unittest.log").decode("utf-8", "strict")
        need(re.search(r"Ran 19 tests in ", log) and re.search(r"\nOK\s*$", log) and
             not re.search(r"skipped|expected failure|unexpected success", log, re.I), "CARRIER_SKIP_OR_UNIT_LOG_MISMATCH")
        need(report["model_calls"] == report["native_runs"] == 0 and
             report["llm_consumption_attested"] is False and
             report["semantic_acceptance_or_lifecycle_authority"] is False, "CARRIER_LIFECYCLE_OVERCLAIM")
        return {"exact_checks": registered["check_test_map"], "actual_methods": registered["methods"],
                "exact_negative_mappings": report["negative_controls"],
                "scope": "Six frozen families; Unicode scalar repertoire only; nested linear fallback only",
                "CV004_discharge": "Requires separate actual channel group", "CV008_discharge": "Requires actual collection A/B group"}

    def channel(self):
        c = self.registration["channel"]
        fixed = "validation/tier2-support-018-qualification/channel-actual"
        need(c["capture_root"] == fixed and c["index"] == "capture-index.json" and
             c["case_plan"] == "channel-case-plan.json" and c["result"] == fixed + "/channel-result.json",
             "CHANNEL_REGISTERED_PATHS_CHANGED")
        root = ROOT / fixed
        case_path, index_path = root / c["case_plan"], root / c["index"]
        self.registered(case_path)
        plan = self.document(case_path, c["case_plan_sha256"])
        need(same_hash(c["case_plan_sha256"], "sha256:60b379805897bd8509145619071ed8ddfb0efe202c9f1d1e3506f940dacd59e5"),
             "CHANNEL_CASE_PLAN_CHANGED")
        index = self.document(index_path)
        need(len(plan["cases"]) == len(index["cases"]) == 3 and plan["required_complete_fields"] == [],
             "CHANNEL_SCOPE_NOT_EXACT_THREE_SLICES")
        for row, bounds in zip(plan["cases"], [(8192, 2048, 16384), (8192, 2048, 100), (4096, 2048, 16384)]):
            need((row["output_cap_bytes"], row["metadata_reserve_bytes"], row["max_output_tokens"]) == bounds and
                 row["selector"] == "/user" and row["start_char"] == 0, "CHANNEL_CASE_BUDGET_OR_SLICE_CHANGED")
        for key in ("comparator", "producer", "orchestrator"):
            self.registered(self.path(c[key]))
        bindings = {"python": sys.executable, "capture_root": str(root), "closure_id": self.spec["closure_id"],
                    "input_root_hash": self.canonical.digest_json(self.hashes), "source_root_hash": self.freeze["source_root"],
                    "index_sha256": sha(self.read(index_path)), "case_plan_sha256": sha(self.read(case_path)),
                    "producer_hash": sha(self.read(self.path(c["producer"]))),
                    "orchestrator_hash": sha(self.read(self.path(c["orchestrator"])))}
        argv = [part.format(**bindings) for part in c["argv_template"]]
        # Relative executable paths in the template are expanded deterministically.
        argv[1] = str(self.path(c["comparator"]))
        expected = [sys.executable, str(self.path(c["comparator"])), "--capture-root", str(root),
                    "--index", c["index"], "--index-sha256", bindings["index_sha256"],
                    "--frozen-case-plan", c["case_plan"], "--frozen-case-plan-sha256", bindings["case_plan_sha256"],
                    "--closure-id", bindings["closure_id"], "--input-root-hash", bindings["input_root_hash"],
                    "--source-root-hash", bindings["source_root_hash"], "--producer-hash", bindings["producer_hash"],
                    "--orchestrator-hash", bindings["orchestrator_hash"]]
        need(argv == expected, "CHANNEL_COMPARATOR_ARGV_TEMPLATE_CHANGED")
        receipt = self.document(self.path(c["comparator_receipt"]))
        need(receipt["argv"] == argv and type(receipt["returncode"]) is int and receipt["returncode"] == 0 and
             receipt["timed_out"] is False and receipt["source_root"] == bindings["source_root_hash"] and
             receipt["input_root"] == bindings["input_root_hash"], "CHANNEL_COMPARATOR_ACTUAL_PROCESS_NOT_CURRENT_SUCCESS")
        stdout = self.log_reference(receipt["stdout"])
        self.log_reference(receipt["stderr"])
        result = self.document(self.path(c["result"]))
        need(parse(stdout) == result, "CHANNEL_RESULT_DIFFERS_FROM_ACTUAL_COMPARATOR_STDOUT")
        comparator = self.module("support018_actual_channel_comparator", self.path(c["comparator"]))
        args = SimpleNamespace(capture_root=root, index=c["index"], index_sha256=bindings["index_sha256"],
            frozen_case_plan=c["case_plan"], frozen_case_plan_sha256=bindings["case_plan_sha256"],
            closure_id=bindings["closure_id"], input_root_hash=bindings["input_root_hash"],
            source_root_hash=bindings["source_root_hash"], producer_hash=bindings["producer_hash"],
            orchestrator_hash=bindings["orchestrator_hash"])
        actual = comparator.evaluate(args)
        need(result["status"] == "PASS" and result["exit_code"] == 0 and result["claim_id"] == "Q018-06" and
             result["raw_result"] == actual, "CHANNEL_COMPARATOR_RESULT_NOT_REPRODUCIBLE")
        for key in ("closure_id", "input_root_hash", "source_root_hash"):
            need(result[key] == bindings[key], "CHANNEL_RESULT_STALE:" + key)
        need(same_hash(result["verifier_hash"], sha(self.read(self.path(c["comparator"])))) and
             result["raw_result_ref"] == c["index"] and same_hash(result["raw_result_hash"], bindings["index_sha256"]),
             "CHANNEL_RESULT_VERIFIER_OR_INDEX_UNBOUND")
        for case in index["cases"]:
            for ref, hashkey in (("carrier_ref", "carrier_ref_sha256"), ("expected_stdout_ref", "expected_stdout_sha256"),
                                 ("actual_tool_result_ref", "actual_tool_result_sha256")):
                self.read(self.path(case[ref], root), case[hashkey])
        return {"exact_three_cases": actual["cases"], "explicit_truncation_controls": actual["truncation_controls"],
                "actual_comparator_argv": argv, "current_index_sha256": bindings["index_sha256"],
                "case_plan_sha256": bindings["case_plan_sha256"], "whole_channel_field_coverage_claim": False,
                "llm_consumption_attested": False, "accept_or_lifecycle_authority": False}

    def unicode(self):
        directory = ROOT / "validation/tier2-unicode-literal-support-018/runs/qualification-018"
        verifier = self.module("support018_current_unicode", ROOT / "validation/tier2-unicode-literal-support-018/verify.py")
        report = self.document(directory / "report.json")
        spec = self.document(self.registered(ROOT / "validation/tier2-unicode-literal-support-018/spec.json"))
        manifest = self.document(directory / "manifest.json")
        self.toolchain_manifest = manifest["files"]
        need(isinstance(self.toolchain_manifest, list) and self.toolchain_manifest and
             len({r["path"] for r in self.toolchain_manifest}) == len(self.toolchain_manifest), "UNICODE_MANIFEST_INCOMPLETE")
        for row in self.toolchain_manifest:
            data = self.read(Path(row["path"]), row["sha256"])
            need(len(data) == row["bytes"], "UNICODE_MANIFEST_BYTES_MISMATCH")
        input_root = verifier.digest(verifier.json_bytes(manifest))
        need(report["status"] == "VERIFIED" and report["input_root_hash"] == input_root and
             report["verifier_id"] == verifier.VERIFIER_ID and
             same_hash(report["verifier_hash"], sha(self.read(Path(verifier.__file__)))) and
             report["closure_id"] == spec["closure_id"] + "/qualification-018", "UNICODE_CURRENT_CLOSURE_OR_VERIFIER_UNBOUND")
        need(report["fixture_counts"] == {"positive": 182, "legacy": 95, "invalid_surrogate": 6, "lean_negative": 5},
             "UNICODE_FINITE_COUNTS_CHANGED")
        need(report["builds"] == {"required": 2, "passed": 2} and report["determinism"]["status"] == "PASS" and
             report["claims"]["statuses"] == {c: "PASS" for c in self.plan["unicode"]["claims"]}, "UNICODE_FIVE_CLAIMS_NOT_ACTUAL_PASS")
        registry = self.document(directory / "verifier-registry.json")
        need(same_hash(registry["implementation_sha256"], sha(self.read(Path(verifier.__file__)))) and
             registry["input_root_hash"] == input_root and registry["closure_id"] == report["closure_id"], "UNICODE_REGISTRY_STALE")
        phase = next(p for p in self.spec["execution_phases"] if p["id"] == "unicode-kernel")
        need(registry["argv"] == phase["argv"][1:], "UNICODE_ACTUAL_ARGV_NOT_REGISTERED")
        rows = self.document(directory / "correspondence-input.json")
        expected, rejected, legacy = verifier.host_checks(verifier.positive_fixtures(), verifier.invalid_fixtures())
        need(rows == expected and len(rows) == 182 and len(legacy) == 95 and len(rejected) == 6 and
             all(r["rejected_paths"] == 5 for r in rejected), "UNICODE_HOST_CORRESPONDENCE_NOT_EXACT")
        host = self.document(directory / "host-checks.json")
        need(host == {"invalid": rejected, "legacy_ids": legacy, "positive_count": 182}, "UNICODE_HOST_REJECTIONS_UNBOUND")
        tc = self.leanbridge.resolve_toolchain()
        need(report["execution_environment"]["toolchain"] == tc.identity(), "UNICODE_TOOLCHAIN_STALE")
        frozen_paths = {Path(r["path"]) for r in self.toolchain_manifest}
        rounds, inventories = [], []
        compiler_processes = []
        kernel_batches = []
        builds = self.document(directory / "builds.json")
        need([r["id"] for r in builds] == ["A", "B"], "UNICODE_TWO_ROUNDS_NOT_EXACT")
        batch_size = integer(spec["positive_batch_size"], "UNICODE_BATCH_SIZE_INVALID", 1)
        for label in ("A", "B"):
            mapped, inventory, artifacts = [], [], {}
            for offset in range(0, len(rows), batch_size):
                index = offset // batch_size
                tag = f"{label}-{index:02d}"
                compile_result = self.document(directory / ("build-" + tag + ".json"))
                source = self.read(directory / f"positive-{index:02d}.lean")
                compiler_processes.append(self.compile_process(compile_result["process_evidence"], source, self.leanbridge.MODULE,
                    spec["budget"]["compile_timeout_seconds"], spec["budget"]["memory_mb"]))
                need(compile_result["ok"] is True and compile_result["errors"] == [] and
                     compile_result["sorry_positions"] == [] and compile_result["timed_out"] is False and
                     type(compile_result["process_evidence"]["returncode"]) is int and
                     compile_result["process_evidence"]["returncode"] == 0, "UNICODE_ACTUAL_COMPILE_NOT_SUCCESS:" + tag)
                response = self.document(directory / ("kernel-" + tag + ".json"))
                actual = verifier.check_export(response, rows[offset:offset + batch_size], tc, frozen_paths)
                need(self.document(directory / ("correspondence-" + tag + ".json")) == actual, "UNICODE_KERNEL_CORRESPONDENCE_MISMATCH")
                mapped.extend(actual)
                inventory.append({"replay": response["replay"], "constants": response["constants"]})
                artifact_map = {p.name.removeprefix("build-" + tag + "-"): verifier.digest(self.read(p))
                                for p in sorted(directory.glob("build-" + tag + "-VeriSlopContract.olean*"))}
                need("VeriSlopContract.olean" in artifact_map, "UNICODE_COMPILED_ARTIFACT_MISSING")
                artifacts[str(index)] = {"source_sha256": verifier.digest(self.read(directory / f"positive-{index:02d}.lean")),
                                         "artifacts": artifact_map}
                kernel_batches.append({"tag": tag, "response": response, "artifacts": artifact_map,
                                       "compiler_process": compile_result["process_evidence"]})
            build = next(row for row in builds if row["id"] == label)
            need(build["artifacts"] == artifacts and build["inventory_sha256"] == verifier.digest(verifier.json_bytes(inventory)) and
                 build["correspondence_sha256"] == verifier.digest(verifier.json_bytes(mapped)) and len(mapped) == 182,
                 "UNICODE_ROUND_BINDING_MISMATCH:" + label)
            rounds.append(mapped)
            inventories.append(inventory)
        need(builds[0]["artifacts"] == builds[1]["artifacts"] and rounds[0] == rounds[1] and
             inventories[0] == inventories[1], "UNICODE_A_B_NONDETERMINISM")
        negatives = self.document(self.registered(ROOT / "validation/tier2-unicode-literal-support-018/negative-plan.json"))["lean_negative_sources"]
        summary = self.document(directory / "negative-summary.json")
        need(len(negatives) == len(summary) == 5 and [r["id"] for r in summary] == [r["id"] for r in negatives],
             "UNICODE_NEGATIVE_IDENTITIES_MISSING")
        for row, registered in zip(summary, negatives):
            raw = self.read(directory / (row["id"] + ".lean"))
            result = self.document(directory / (row["id"] + ".json"))
            compiler_processes.append(self.compile_process(result["process_evidence"], raw, self.leanbridge.MODULE,
                spec["budget"]["compile_timeout_seconds"], spec["budget"]["memory_mb"]))
            need(raw == registered["source"].encode("utf-8", "strict") and
                 row["source_sha256"] == verifier.digest(raw) and row["status"] == "PASS" and
                 result["ok"] is False and result["timed_out"] is False and result["errors"] and
                 result["sorry_positions"] == [] and type(result["process_evidence"]["returncode"]) is int and
                 result["process_evidence"]["returncode"] != 0 and row["returncode"] == result["process_evidence"]["returncode"] and
                 row["errors"] == result["errors"] and any(registered["expected_error_fragment"] in e for e in result["errors"]),
                 "UNICODE_NEGATIVE_NOT_ACTUAL_DECLARED_FAILURE:" + row["id"])
        processes = self.document(directory / "processes.json")
        need(processes, "UNICODE_ACTUAL_PROCESS_RECORDS_MISSING")
        for process_index, row in enumerate(processes):
            need(type(row["returncode"]) is int and row["timed_out"] is False and row["isolation"], "UNICODE_PROCESS_UNRESOLVED")
            need(row["stdout"]["path"] == f"process-{process_index:02d}.stdout" and
                 row["stderr"]["path"] == f"process-{process_index:02d}.stderr",
                 "UNICODE_ACTUAL_PROCESS_LOG_INDEX_MISMATCH")
            self.log_reference(row["stdout"], directory, "bytes")
            self.log_reference(row["stderr"], directory, "bytes")
        compiler_indices = []
        for process in compiler_processes:
            matching = [r for r in processes if r["argv"] == process["requested_argv"] and
                        r["cwd"] == process["working_directory"] and
                        r["returncode"] == process["returncode"] and
                        same_hash(r["stdout"]["sha256"], process["stdout"]["sha256"]) and
                        same_hash(r["stderr"]["sha256"], process["stderr"]["sha256"])]
            need(len(matching) == 1, "UNICODE_COMPILER_NOT_BOUND_TO_EXACT_ACTUAL_RETAINED_PROCESS_LOGS")
            compiler_indices.append(processes.index(matching[0]))
        need(compiler_indices == sorted(set(compiler_indices)), "UNICODE_COMPILER_LEDGER_NOT_DISTINCT_SERIAL_ORDER")
        actual_kernel_indices = [i for i, row in enumerate(processes) if "--run" in row["argv"]]
        expected_kernel_indices = []
        kernel_bindings = []
        for batch, compiler_index in zip(kernel_batches, compiler_indices[:len(kernel_batches)]):
            kernel_index = compiler_index + 1
            need(kernel_index < len(processes), "UNICODE_ACTUAL_KERNEL_PROCESS_MISSING:" + batch["tag"])
            kernel_bindings.append(self.unicode_kernel_row(directory, processes[kernel_index], batch, tc, spec))
            expected_kernel_indices.append(kernel_index)
        need(actual_kernel_indices == expected_kernel_indices and
             len(expected_kernel_indices) == 2 * ((182 + batch_size - 1) // batch_size),
             "UNICODE_TWO_ROUNDS_ACTUAL_KERNEL_LEDGER_NOT_EXACT")
        need(set(range(len(processes))) == set(compiler_indices) | set(expected_kernel_indices) and
             not set(compiler_indices) & set(expected_kernel_indices), "UNICODE_UNDECLARED_OR_UNCONSUMED_ACTUAL_PROCESS_ROW")
        unit = self.document(directory / "unit.json")
        need(unit["argv"] == [sys.executable, "-m", "unittest", "tests.test_unicode_lean_literals_018", "-v"] and
             type(unit["returncode"]) is int and unit["returncode"] == 0, "UNICODE_CURRENT_UNIT_PROCESS_NOT_SUCCESS")
        self.read(directory / "unit.stdout", unit["stdout_sha256"])
        self.read(directory / "unit.stderr", unit["stderr_sha256"])
        for claim in self.plan["unicode"]["claims"]:
            row = self.document(directory / (claim + ".json"))
            need(row["claim_id"] == claim and row["status"] == "PASS" and row["exit_code"] == 0 and
                 row["input_root_hash"] == input_root and row["closure_id"] == report["closure_id"] and
                 same_hash(row["verifier_hash"], sha(self.read(Path(verifier.__file__)))), "UNICODE_CLAIM_UNBOUND:" + claim)
            for artifact in row["raw_result"]["artifacts"]:
                self.read(self.path(artifact["path"], directory), artifact["sha256"])
        return {"actual_claims": self.plan["unicode"]["claims"], "two_kernel_rounds": [len(r) for r in rounds],
                "legacy": len(legacy), "six_surrogates_via_five_paths": rejected, "compiler_negatives": summary,
                "actual_kernel_batches": kernel_bindings,
                "deterministic_artifacts_and_exact_Expr_inventories": True, "universal_unicode_claim": False}

    def unicode_kernel_row(self, directory, row, batch, tc, spec):
        tag = batch["tag"]
        cwd = Path(row["cwd"])
        need(cwd.is_absolute() and ".." not in cwd.parts, "UNICODE_KERNEL_CWD_NOT_ABSOLUTE:" + tag)
        memory = spec["budget"]["memory_mb"]
        expected_argv = [str(tc.lean), "-j4", f"-M{memory}", "--run",
                         str(cwd / "VeriSlopKernel.lean"), "request.json", "response.json"]
        need(row["argv"] == expected_argv and type(row["returncode"]) is int and row["returncode"] == 0 and
             row["timed_out"] is False, "UNICODE_ACTUAL_KERNEL_COMMAND_OR_NUMERIC_RESULT_MISMATCH:" + tag)
        options = row["requested_options"]
        need(type(options["timeout"]) in (int, float, str) and
             float(options["timeout"]) == spec["budget"]["kernel_timeout_seconds"] and
             type(options["memory_mb"]) is int and options["memory_mb"] == memory + self.leanbridge.LEAN_AS_HEADROOM_MB and
             options["require_network_isolation"] is True and options["require_filesystem_isolation"] is True and
             options["read_only_paths"] == [str(tc.prefix)], "UNICODE_KERNEL_ACTUAL_OPTIONS_NOT_REGISTERED:" + tag)
        # Row identity is not inferred from a separately written export JSON.
        # The actual sandbox recorder must retain the request, response, copied
        # tool and hashes of the staged input module parts before temp cleanup.
        evidence = row["kernel_evidence"]
        need(set(evidence) == {"request", "response", "kernel_tool", "staged_module_parts"},
             "UNICODE_KERNEL_ACTUAL_ARTIFACT_SCHEMA_MISMATCH:" + tag)
        request_raw = self.log_reference(evidence["request"], directory, "bytes")
        response_raw = self.log_reference(evidence["response"], directory, "bytes")
        tool_raw = self.log_reference(evidence["kernel_tool"], directory, "bytes")
        need(tool_raw == self.read(self.leanbridge.KERNEL_TOOL), "UNICODE_EXECUTED_KERNEL_TOOL_BYTES_NOT_CURRENT:" + tag)
        request = parse(request_raw)
        expected_request = {"export": True, "axioms": True, "search_dir": str(cwd / "stage"),
                            "module": self.leanbridge.MODULE, "sysroot": str(tc.prefix)}
        need(self.canonical.dumps(request) == self.canonical.dumps(expected_request),
             "UNICODE_ACTUAL_KERNEL_REQUEST_NOT_EXACT:" + tag)
        parts = evidence["staged_module_parts"]
        need(parts["module"] == self.leanbridge.MODULE and set(parts["parts"]) == set(batch["artifacts"]) and
             all(same_hash(value, batch["artifacts"][name]) for name, value in parts["parts"].items()),
             "UNICODE_KERNEL_STAGED_INPUT_DIFFERS_FROM_EXACT_BATCH_COMPILE:" + tag)
        response = parse(response_raw)
        # Exactly the existing run_kernel_tool normalization, already declared
        # in the original Unicode verifier, is admitted here.
        for module in response.get("import", {}).get("modules", []):
            if module.get("name") == [self.leanbridge.MODULE]:
                module["olean"] = "<staged candidate module>"
        need(self.canonical.dumps(response) == self.canonical.dumps(batch["response"]),
             "UNICODE_ACTUAL_KERNEL_RESPONSE_NOT_RETAINED_BATCH_EXPORT:" + tag)
        self.log_reference(row["stdout"], directory, "bytes")
        self.log_reference(row["stderr"], directory, "bytes")
        return {"batch": tag, "actual_argv": row["argv"], "returncode": row["returncode"],
                "requested_options": options, "request_sha256": sha(request_raw),
                "response_sha256": sha(response_raw), "copied_kernel_tool_sha256": sha(tool_raw),
                "staged_module_parts": parts, "stdout": row["stdout"], "stderr": row["stderr"]}

    def ground(self):
        design = ROOT / "validation/tier2-ground-replay-support-018-design"
        directory = self.gate / "ground-kernel"
        verifier = self.module("support018_current_ground", design / "qualification.py")
        report = self.document(directory / "report.json")
        freeze = self.document(directory / "frozen-inputs.json")
        need(report["format"] == "verislop.ground-replay-qualification/1" and report["status"] == "VERIFIED" and
             report["caller_source_freeze"] == self.freeze["source_root"] == freeze["caller_source_freeze"] and
             report["input_root"] == freeze["file_map_hash"] == self.canonical.digest_json(freeze["files"]),
             "GROUND_CURRENT_ROOT_OR_FROZEN_MAP_MISMATCH")
        need(set(self.document(self.gate / "verification-source-manifest.json")["files"]) <= set(freeze["files"]),
             "GROUND_CALLER_INPUTS_OMITTED")
        for name, digest in freeze["files"].items():
            need(name in self.hashes and same_hash(digest, self.hashes[name]), "GROUND_UNREGISTERED_INPUT:" + name)
            self.read(self.path(name), digest)
        need(freeze["toolchain"] == self.spec["toolchain"] and freeze["kernel_tool_hash"] == self.spec["kernel_tool_hash"] and
             freeze["policy_hash"] == self.spec["policy_hash"] and report["inputs_unchanged"] is True and
             report["environment_unchanged"] is True and report["native_or_model_calls"] == 0 and
             report["forbidden_task_oracles_read"] is False, "GROUND_ENVIRONMENT_OR_SCOPE_NOT_CURRENT")
        registry = self.document(self.registered(design / "qualification-registration-013.json"))
        need(same_hash(registry["sha256"], sha(self.read(Path(verifier.__file__)))), "GROUND_HOOK_REGISTRATION_MISMATCH")
        recipe = self.document(self.registered(design / "recipe-001.json"), self.plan["ground"]["recipe_sha256"])
        need(verifier.replay.PROOF == report["recipe"] == recipe["proof"] and
             verifier.replay.STRATEGY == "kernel-ground-normalization/1" and recipe["strategy_id"] == "S-GR-001" and
             report["strategy"] == "S-GR-001" and report["optional_strategy"] == "S-GR-002_UNAVAILABLE",
             "GROUND_SELECTED_RECIPE_NOT_EXACT")
        need(recipe["options"] == {"maxHeartbeats": 2000000, "maxRecDepth": 100000, "smartUnfolding": False} and
             recipe["max_polarity_compilations"] == 2 and recipe["whole_probe_deadline_seconds"] == 30 and
             recipe["polarity_order"] == [False, True], "GROUND_LIMITS_RELAXED")
        need(verifier.replay.DIAGNOSTIC_ROWS == 8 and verifier.replay.DIAGNOSTIC_ROW_BYTES == 512 and
             verifier.replay.DIAGNOSTIC_WIRE_BYTES == 16384, "GROUND_DIAGNOSTIC_CONSTANTS_CHANGED")
        need([r["id"] for r in report["steps"]] == self.plan["ground"]["steps"] and
             all(type(r["rc"]) is int and r["rc"] == 0 for r in report["steps"]), "GROUND_REQUIRED_STEP_NOT_ACTUALLY_SUCCESSFUL")
        need(isinstance(report["evidence"], dict) and report["evidence"], "GROUND_RAW_EVIDENCE_MANIFEST_MISSING")
        for name, digest in report["evidence"].items():
            self.read(self.path(name, directory), digest)
        for row in report["steps"]:
            need(row["log"] == row["id"] + ".log" and row["log"] in report["evidence"], "GROUND_STEP_LOG_UNBOUND")
        projections = []
        for label, current in (("baseline", False), ("clean-001", True), ("clean-002", True)):
            outcomes = self.document(directory / label / "outcomes.json")
            pairs = [[row["fixture"], row["assignment"]] for row in outcomes]
            need(len(pairs) == 8 and len({tuple(p) for p in pairs}) == 8 and
                 set(map(tuple, pairs)) == set(map(tuple, self.plan["ground"]["case_pairs"])), "GROUND_EIGHT_CASES_NOT_EXACT:" + label)
            expected = self.plan["ground"]["expected_current" if current else "expected_baseline"]
            # The registered checker recomputes source AST/statements, defeq,
            # complete exports, dependencies, axiom policy and frontier bindings.
            projection = verifier.validate_fixtures(directory / label, expected, current=current)
            if current:
                need(len(projection) == 8, "GROUND_CURRENT_REQUIRED_RESULT_MISSING")
                projections.append(projection)
                for result in outcomes:
                    self.check_attempts(directory / label / result["fixture"] / ("assignment-%d" % result["assignment"]), result,
                                        verifier.replay)
                    assignment = directory / label / result["fixture"] / ("assignment-%d" % result["assignment"])
                    observed = result["observed"]
                    response = self.document(assignment / "kernel-response.json")
                    request = self.document(assignment / "kernel-request.json")
                    theorem_rows = [r for r in response["constants"] if r["name"] == [verifier.replay.MODULE, "result"]]
                    need(len(theorem_rows) == 1 and theorem_rows[0]["kind"] == "theorem" and
                         theorem_rows[0]["safety"] == "safe" and theorem_rows[0]["level_params"] == [] and
                         theorem_rows[0]["unresolved_constants"] == [] and theorem_rows[0]["module"] == [verifier.replay.MODULE],
                         "GROUND_EXACT_SAFE_THEOREM_BOUNDARY_MISSING")
                    need(len(response["defeq"]) == 1 and response["defeq"][0]["id"] == "ground-result" and
                         request["defeq"][0]["theorem"] == [verifier.replay.MODULE, "result"], "GROUND_SINGLE_EXACT_DEFEQ_NOT_BOUND")
                    staged = {verifier.name_str(r["name"]) for r in response["import"]["modules"] if r.get("staged")}
                    need(staged == set(observed["modules"]), "GROUND_ACTUAL_STAGED_MODULE_SET_DIFFERS")
                    toolchain_modules = [r for r in response["import"]["modules"] if not r.get("staged")]
                    need(all(r["name"] and str(r["name"][0]) in self.policy.get("strict")["allowed_import_roots"]
                         for r in toolchain_modules), "GROUND_UNREGISTERED_TOOLCHAIN_IMPORT_ROOT")
                    closure, issues = self.leanbridge.olean_closure_identity(self.leanbridge.resolve_toolchain(), toolchain_modules)
                    need(issues == [] and closure == observed["toolchain_olean_closure"] and
                         observed["toolchain"] == self.spec["toolchain"] and observed["kernel_tool_hash"] == self.spec["kernel_tool_hash"],
                         "GROUND_TOOLCHAIN_MODULE_BYTES_OR_CLOSURE_UNBOUND")
                    need(all(not name or name[-1] == "_unsafe_rec" for name in response["replay"].get("not_replayed_unsafe_or_partial", [])),
                         "GROUND_KERNEL_REPLAY_OMITTED_NONRUNTIME_DECLARATION")
        comparison = self.document(directory / "clean-comparison.json")
        need(projections[0] == projections[1] == comparison["exact_inventory"] and comparison["status"] == "VERIFIED" and
             comparison["clean_builds"] == 2 and comparison["inventory_hash"] == self.canonical.digest_json(projections[0]),
             "GROUND_TWO_CURRENT_CLEAN_INVENTORIES_DIFFER")
        units = self.document(directory / "units-results.json")
        expected_units = self.plan["ground"]["unit_ids"]
        need(units["registry"] == expected_units and units["executed"] == len(expected_units) == 15 and
             set(units["results"]) == set(expected_units) and all(r["status"] == "PASS" for r in units["results"].values()) and
             all(r["status"] == "PASS" for r in units["subtests"]) and units["success"] is True, "GROUND_EXACT_STRUCTURED_UNIT_RESULTS_MISSING")
        self.require_suite_methods(expected_units)
        actual_controls = verifier.verify_controls(directory)
        need(report["controls"] == actual_controls and [r["id"] for r in actual_controls] ==
             [r["id"] for r in self.plan["ground"]["negative_controls"]] and len(actual_controls) == 16,
             "GROUND_16_CONTROLS_NOT_EXACT")
        for row in actual_controls:
            need(row["status"] == "VERIFIED", "GROUND_CONTROL_NOT_VERIFIED:" + row["id"])
            self.read(self.path(row["evidence"], directory))
            if row["evidence"] == "units-results.json":
                need(row["executed_test_ids"] and all(t in expected_units and units["results"][t]["status"] == "PASS"
                     for t in row["executed_test_ids"]), "GROUND_CONTROL_HAS_NO_EXACT_UNIT_MAPPING:" + row["id"])
        failed = self.document(directory / "negative/compile-failure/result.json")
        need(failed["observed"] is None and failed["status"] == "UNSUPPORTED" and
             "; proof_attempts=" in failed["diagnostic"], "GROUND_FAILED_POLARITIES_NOT_RETAINED_UNSUPPORTED")
        failed_attempts = parse(failed["diagnostic"].split("; proof_attempts=", 1)[1].encode())
        self.failed_attempts(directory / "negative/compile-failure", failed_attempts, verifier.replay)
        guards = verifier.verify_verifier_guards(directory, self.plan["ground"]["expected_current"])
        need(self.document(directory / "verifier-guards.json") == guards and guards["status"] == "VERIFIED", "GROUND_OMISSION_GUARD_EVIDENCE_MISMATCH")
        actual_axioms = sorted({axiom for row in projections[0] for axiom in row["axioms"]})
        need(report["actual_axioms"] == actual_axioms and all(self.policy.classify_axiom(a, self.policy.get("strict")) == "allowed"
             for a in actual_axioms), "GROUND_AXIOM_POLICY_OR_INVENTORY_MISMATCH")
        claim_ids = ["C-GR-%03d" % i for i in range(1, 9)]
        need([r["id"] for r in report["claims"]] == claim_ids and all(r["status"] == "VERIFIED" for r in report["claims"]),
             "GROUND_REQUIRED_EIGHT_CLAIMS_UNRESOLVED")
        self.registered(design / "export-frontier-005-freeze.json")
        # No complete result may have a missing or differently bound declared
        # precontract leaf frontier: validate_fixtures recomputes it above.
        return {"current_exact_case_count": [len(p) for p in projections], "baseline_bounded_both_unsupported": True,
                "selected_recipe_sha256": self.plan["ground"]["recipe_sha256"],
                "actual_axioms": actual_axioms, "exact_controls": actual_controls,
                "actual_structured_unit_identities": expected_units, "frontier": "export-frontier-005",
                "deterministic_inventory_hash": comparison["inventory_hash"], "omission_guards": guards,
                "diagnostic_bounds": self.plan["ground"]["diagnostic_bounds"]}

    def failed_attempts(self, directory, attempts, replay):
        need(isinstance(attempts, list) and len(attempts) == 2 and
             [r["polarity"] for r in attempts] == [False, True] and
             all(type(r["polarity"]) is bool for r in attempts) and
             len(self.canonical.dumps(attempts)) <= 16384, "GROUND_FAILURE_TWO_POLARITY_WIRE_OR_ORDER_MISMATCH")
        compilation = [(p, self.document(p)) for p in sorted(directory.glob("compile-*.json"))]
        compilation = [(p, r) for p, r in compilation if r["module"] == replay.MODULE]
        need(len(compilation) == 2, "GROUND_FAILURE_ACTUAL_COMPILER_COUNT_MISMATCH")
        for index, (row, (path, record)) in enumerate(zip(attempts, compilation), 1):
            for key in ("attempt_index", "retained_rows", "available_rows", "retained_utf8_bytes", "available_utf8_bytes"):
                integer(row[key], "GROUND_FAILURE_LEDGER_NONINTEGER:" + key)
            for key in ("compiler_ok", "timed_out", "truncated", "sorry_positions_truncated"):
                need(type(row[key]) is bool, "GROUND_FAILURE_LEDGER_NONBOOLEAN:" + key)
            source = self.read(path.with_suffix(".lean"))
            process = self.compile_process(record["process"], source, replay.MODULE,
                                           memory_mb=self.policy.get("strict")["memory_mb"])
            need(record["ok"] is False and row["compiler_ok"] is False and
                 row["compiler_exit_code"] == process["returncode"] and row["timed_out"] == record["timed_out"] and
                 row["strategy_id"] == replay.STRATEGY and row["attempt_index"] == index and
                 same_hash(row["probe_source_hash"], sha(source)), "GROUND_FAILED_ATTEMPT_SOURCE_OR_PROCESS_BINDING_MISMATCH")
            errors = record["errors"]
            clipped = [e.encode("utf-8", "strict")[:512].decode("utf-8", "ignore") for e in errors[:8]]
            flags = [len(c.encode("utf-8")) != len(e.encode("utf-8")) for c, e in zip(clipped, errors[:8])]
            rows = row["errors"]
            n = len(rows)
            need(n <= 8 and rows == clipped[:n] and row["row_truncated"] == flags[:n] and
                 row["retained_rows"] == n and row["available_rows"] == len(errors) and
                 row["retained_utf8_bytes"] == sum(len(e.encode("utf-8")) for e in rows) and
                 row["available_utf8_bytes"] == sum(len(e.encode("utf-8")) for e in errors) and
                 len(self.canonical.dumps(row)) <= 8190, "GROUND_FAILED_DIAGNOSTIC_BOUND_OR_COUNT_MISMATCH")
            if n < len(clipped) or len(errors) > 8 or any(flags):
                need(row["truncated"] is True, "GROUND_FAILURE_DIAGNOSTIC_TRUNCATION_HIDDEN")
            need(row["underlying_process_output_truncated"] == process.get("output_truncated") and
                 row["process_output"] == {k: {f: process[k][f] for f in ("byte_count", "sha256")}
                                           for k in ("stdout", "stderr")}, "GROUND_FAILURE_PROCESS_OUTPUT_IDENTITY_CHANGED")

    def check_attempts(self, directory, result, replay):
        observed = result["observed"]
        attempts = observed["proof_attempts"]
        need(isinstance(attempts, list) and 1 <= len(attempts) <= 2 and
             len(self.canonical.dumps(attempts)) <= 16384, "GROUND_ATTEMPT_COUNT_OR_WIRE_BOUND_EXCEEDED")
        polarity = result["status"] == "NOT_REPRODUCED"
        need([r["polarity"] for r in attempts] == [False, True][:len(attempts)] and
             all(type(r["polarity"]) is bool for r in attempts) and
             attempts[-1]["polarity"] is polarity, "GROUND_ATTEMPT_ORDER_OR_FINAL_POLARITY_WRONG")
        # Exact field names are validated against the current production encoder;
        # unknown/missing fields block instead of using a diagnostics log fallback.
        compilation = [(path, self.document(path)) for path in sorted(directory.glob("compile-*.json"))]
        compilation = [(path, record) for path, record in compilation if record["module"] == replay.MODULE]
        need(len(compilation) == len(attempts), "GROUND_ACTUAL_COMPILE_ATTEMPT_LEDGER_MISMATCH")
        for index, (row, (path, record)) in enumerate(zip(attempts, compilation), 1):
            need(isinstance(row.get("errors"), list), "GROUND_DIAGNOSTIC_ROWS_FIELD_MISSING")
            rows = row["errors"]
            need(len(rows) <= 8 and all(isinstance(v, str) and len(v.encode("utf-8", "strict")) <= 512 for v in rows),
                 "GROUND_DIAGNOSTIC_PAYLOAD_BOUND_EXCEEDED")
            need(len(self.canonical.dumps(row)) <= 8190, "GROUND_PER_ATTEMPT_ENCODED_RESERVE_EXCEEDED")
            need(type(row["compiler_ok"]) is bool and type(row["truncated"]) is bool and
                 type(row["retained_rows"]) is int and row["retained_rows"] == len(rows), "GROUND_DIAGNOSTIC_COUNTS_OR_TYPES_INVALID")
            available = row["available_rows"]
            need(available is None or (type(available) is int and available >= len(rows)), "GROUND_AVAILABLE_COUNT_NOT_HONEST")
            source = self.read(path.with_suffix(".lean"))
            process = self.compile_process(record["process"], source, replay.MODULE)
            proxy = SimpleNamespace(ok=record["ok"], errors=record["errors"], process_evidence=record["process"],
                                    timed_out=record["timed_out"], sorry_positions=record["sorry_positions"])
            actual = replay._attempt(proxy, source, (False, True)[index - 1], index)
            need(self.canonical.dumps(row) == self.canonical.dumps(actual) and
                 row["strategy_id"] == "kernel-ground-normalization/1" and
                 same_hash(row["probe_source_hash"], sha(source)), "GROUND_ATTEMPT_NOT_ACTUAL_SOURCE_ENCODER_OR_PROCESS_RESULT")
            need(type(row["compiler_exit_code"]) is int and row["timed_out"] is False and
                 row["compiler_ok"] == (row["compiler_exit_code"] == 0), "GROUND_ATTEMPT_ACTUAL_RETURN_CODE_INVALID")
            need(record["timed_out"] == process["timed_out"] and
                 process["requested_limits"]["lean_heap_mb"] == self.policy.get("strict")["memory_mb"],
                 "GROUND_ACTUAL_REQUESTED_LIMITS_OR_TIMEOUT_CHANGED")
            if not row["compiler_ok"]:
                need(rows or row["truncated"] or available is None, "GROUND_FAILED_ATTEMPT_DIAGNOSTICS_MISSING")

    def collection(self):
        need(hasattr(self, "suite_result"), "CURRENT_COLLECTION_SUITE_NOT_VALIDATED")
        stdout = self.read(self.gate / "registered-suite.stdout.log").decode("utf-8", "strict")
        captures = re.findall(r"^COLLECTION_TIER2_FROZEN_ATTEMPT_CAPTURE (\S+)\s*$", stdout, re.M)
        annexes = re.findall(r"^COLLECTION_TIER2_RETAINED_CHECK_CAPTURE (\S+)\s*$", stdout, re.M)
        need(len(captures) == len(annexes) == 1, "FRESH_COLLECTION_PATHS_NOT_UNIQUE_IN_THIS_ROOT_STDOUT")
        collection_module = sys.modules.get("tests.test_vscore3_collection_bridge")
        need(collection_module is not None, "CURRENT_COLLECTION_MODULE_NOT_REGISTERED")
        expected_parent = collection_module.CAPTURE_ROOT
        need(expected_parent.is_relative_to(ROOT / "validation"), "COLLECTION_REGISTERED_CAPTURE_ROOT_OUTSIDE_VALIDATION")
        capture, annex = Path(captures[0]), Path(annexes[0])
        for path, prefix in ((capture, "frozen-attempt-"), (annex, "retained-check-")):
            need(path.is_absolute() and path.parent == expected_parent and path.name.startswith(prefix) and
                 path.is_dir() and not path.is_symlink() and path.resolve() == path.absolute(), "COLLECTION_CAPTURE_OUTSIDE_CURRENT_ROOT")
        receipt = self.document(capture / "capture.json")
        retained = self.document(annex / "result.json")
        need({p.name for p in annex.iterdir() if p.is_file()} ==
             {"result.json", "retained-release-probe.json", "retained-mechanical-snapshot.json"},
             "COLLECTION_RETAINED_ANNEX_FILES_NOT_EXACT")
        need(receipt["format"] == "verislop.fresh-collection-tier2-capture/1" and
             receipt["stage_status"] == "BUILT_PENDING_RETAINED" and receipt["qualification"] is False and
             receipt["model_calls"] == 0, "COLLECTION_INITIAL_CAPTURE_NOT_CURRENT_COMPLETED")
        need(receipt["source_hashes"] == self.hashes and receipt["source_root"] == self.canonical.digest_json(self.hashes) and
             same_hash(receipt["source_freeze_hash"], sha(self.read(self.gate / "qualification-inputs.json"))),
             "COLLECTION_CAPTURE_NOT_BOUND_TO_CURRENT_WHOLE_INPUT_MAP")
        self.read(capture / "source-freeze.json", sha(self.read(self.gate / "qualification-inputs.json")))
        actual_files = {p.relative_to(capture).as_posix() for p in capture.rglob("*") if p.is_file()}
        need(actual_files == set(receipt["files"]) | {"capture.json"}, "COLLECTION_CAPTURE_MANIFEST_NOT_COMPLETE")
        for name, digest in receipt["files"].items():
            self.read(self.path(name, capture), digest)
        for name, digest in self.hashes.items():
            self.read(self.path("registered-sources/" + name, capture), digest)
        need(retained["format"] == "verislop.fresh-collection-tier2-retained-check/1" and
             retained["attempt"] == capture.relative_to(ROOT).as_posix() and
             same_hash(retained["capture_hash"], sha(self.read(capture / "capture.json"))) and
             retained["qualification"] is True and retained["mechanical_status"] == "VERIFIED" and
             retained["original_temporary_root_removed"] is True and retained["error"] is None and
             retained["model_calls"] == 0 and retained["registered_actual_builds"] == "A,B" and
             retained["source_root"] == self.canonical.digest_json(self.hashes), "COLLECTION_RETAINED_CHECK_NOT_CURRENT_COMPLETE")
        self.require_suite_methods([COLLECTION_ID])
        from verislop.package import Package
        from verislop.backends import vscore3, vscore3_closure
        from verislop import review_counterexamples
        from verislop.bridges import vscore3_checker as checker
        pkg = Package(capture / "package")
        # These are actual registered retained validators, not booleans copied
        # from a report. No compiler or model is requested by these calls.
        accepted, pending, diagnostics = checker.verify_published(pkg, "implementation", rebuild=False)
        need(isinstance(accepted, list) and accepted and pending == [] and diagnostics == [],
             "CURRENT_RETAINED_BRIDGE_ADMISSION_FAILED")
        snapshot = vscore3_closure.mechanical_snapshot(pkg)
        need(snapshot is not None and snapshot["mechanical_status"] == "VERIFIED" and
             [b["build"] for b in snapshot["builds"]] == ["A", "B"] and
             all(b["ok"] and b["errors"] == [] for b in snapshot["builds"]) and
             snapshot["builds"][0]["outputs"] == snapshot["builds"][1]["outputs"] and
             snapshot["determinism"]["mismatches"] == [], "CURRENT_RETAINED_A_B_CLOSURE_REJECTED")
        need(self.document(capture / "mechanical-snapshot.json") == snapshot and
             self.document(annex / "retained-mechanical-snapshot.json") == snapshot, "RETAINED_SNAPSHOT_NOT_ACTUAL_CURRENT")
        claim = vscore3.selection(pkg)["edge_claim_id"]
        initial = self.document(capture / "release-probe.json")
        old_retained = self.document(annex / "retained-release-probe.json")
        current = review_counterexamples.replay(pkg, "release", {"kind": "mechanical_failure", "claim_id": claim})
        for probe in (initial, old_retained, current):
            need(probe["status"] == "NOT_REPRODUCED" and probe["expected"]["outcome"] == "PASS" and
                 probe["observed"]["outcome"] == "PASS", "CURRENT_OR_INITIAL_RELEASE_PROBE_UNRESOLVED")
        need(current == old_retained == initial, "RELEASE_PROBE_DETERMINISTIC_BINDING_MISMATCH")
        write_once(self.output / "actual-retained-release-probe.json", current)
        engineering = self.bootstrap.engineering_record(pkg.root, self.gate / "source-freeze.json")
        self.bootstrap.verify_engineering_record(engineering)
        need(engineering["source_root"] == self.freeze["source_root"] and engineering["builds"] == snapshot["builds"] and
             engineering["determinism"] == snapshot["determinism"] and engineering["fresh_model_calls"] == 0 and
             engineering["fixture_only"] is True and engineering["model_authoring_input"] is False, "ENGINEERING_RECORD_NOT_CURRENT_EXACT")
        write_once(self.output / "engineering-record.json", engineering)
        self.read(self.output / "engineering-record.json")
        self.read(self.output / "actual-retained-release-probe.json")
        self.snapshot, self.pkg = snapshot, pkg
        return {"capture": capture.relative_to(ROOT).as_posix(), "annex": annex.relative_to(ROOT).as_posix(),
                "collection_current_executed_id": COLLECTION_ID, "retained_bridge_actual_admission": True,
                "actual_AB_registered_validator": "vscore3_closure.mechanical_snapshot/validate_execution",
                "closure_root": snapshot["closure_root"], "actual_builds": snapshot["builds"],
                "determinism": snapshot["determinism"], "new_engineering_package_root": engineering["package_files_root"],
                "original_root_removal_evidence": "Exact current registered test self.assertFalse(root.exists()) plus annex; no model assertion",
                "initial_and_retained_and_new_release_probe_equal": True}

    def finish(self):
        # Recheck all evidence bytes, including runtime-generated manifests and
        # package publications. The final output files are the only new writes.
        old = dict(self.evidence)
        for name, row in old.items():
            self.read(Path(name), row["sha256"])
        if self.pkg is not None:
            engineering = self.document(self.output / "engineering-record.json")
            self.bootstrap.verify_engineering_record(engineering)
        after = self.guard()
        need(self.results["guards"]["actual_predicates"] == after, "ENTRY_EXIT_GUARD_PROJECTIONS_DIFFER")
        return after

    def run(self):
        need(not self.output.exists() and not self.output.is_symlink(), "FINALIZER_OUTPUT_ALREADY_EXISTS")
        self.output.mkdir()
        self.record_step("guards", self.entry)
        if self.results["guards"]["status"] == "VERIFIED":
            self.record_step("phases", self.phases)
            if self.results["phases"]["status"] == "VERIFIED":
                self.record_step("channel", self.channel)
            else:
                self.results["channel"] = {"status": "BLOCKED", "actual_predicates": {}, "evidence": [],
                                           "blocking_reasons": ["FOUR_ACTUAL_PHASES_NOT_COMPLETED_SUCCESSFULLY"]}
            methods = (("suite", self.suite), ("carrier", self.carrier),
                                 ("unicode", self.unicode), ("ground", self.ground),
                                 ("collection", self.collection))
            for name, method in methods:
                if self.results["phases"]["status"] == self.results["channel"]["status"] == "VERIFIED":
                    self.record_step(name, method)
                else:
                    self.results[name] = {"status": "BLOCKED", "actual_predicates": {}, "evidence": [],
                                          "blocking_reasons": ["ACTUAL_PHASES_AND_CURRENT_CHANNEL_COMPARATOR_NOT_COMPLETED_AND_VALIDATED"]}
            self.record_step("guards_after", self.finish)
            if self.results["guards_after"]["status"] != "VERIFIED":
                self.results["guards"]["status"] = self.results["guards_after"]["status"]
                self.results["guards"]["blocking_reasons"] += self.results["guards_after"]["blocking_reasons"]
        else:
            for name in ("phases", "suite", "carrier", "channel", "unicode", "ground", "collection"):
                self.results[name] = {"status": "BLOCKED", "actual_predicates": {}, "evidence": [],
                                      "blocking_reasons": ["CURRENT_ENTRY_BINDINGS_NOT_VALID"]}
        rows = []
        for claim in self.plan["claims"]:
            groups = [self.results[n] for n in GROUPS[claim["id"]]]
            status = ("BLOCKED" if any(g["status"] == "BLOCKED" for g in groups) else
                      "INFRASTRUCTURE_FAILURE" if any(g["status"] == "INFRASTRUCTURE_FAILURE" for g in groups) else "VERIFIED")
            if claim["id"] == "Q018-18" and any(c["status"] == "BLOCKED" for c in rows):
                status = "BLOCKED"
            elif claim["id"] == "Q018-18" and any(c["status"] == "INFRASTRUCTURE_FAILURE" for c in rows):
                status = "INFRASTRUCTURE_FAILURE"
            row = {"claim_id": claim["id"], "registered_verifier": claim["verifier"],
                   "reconciler_id": self.plan["verifier_id"], "reconciler_sha256": sha(Path(__file__).read_bytes()),
                   "original_statement": claim["statement"], "original_pass_condition": claim["pass_condition"],
                   "status": status, "actual_predicates": {n: self.results[n]["actual_predicates"] for n in GROUPS[claim["id"]]},
                   "inputs": {"source_root": self.freeze.get("source_root"),
                              "input_root": self.canonical.digest_json(self.hashes) if self.canonical else None,
                              "registered_files": self.hashes},
                   "evidence": sorted({e for g in groups for e in g["evidence"]}),
                   "trusted_dependencies": claim["dependencies_trusted"],
                   "blocking_reasons": [r for g in groups for r in g["blocking_reasons"]]}
            if claim["id"] == "Q018-18" and status != "VERIFIED":
                row["blocking_reasons"].append("REQUIRED_ORIGINAL_CLAIMS_NOT_ALL_VERIFIED")
            rows.append(row)
            write_once(self.output / (claim["id"] + ".json"), row)
        status = ("BLOCKED" if any(r["status"] == "BLOCKED" for r in rows) else
                  "INFRASTRUCTURE_FAILURE" if any(r["status"] == "INFRASTRUCTURE_FAILURE" for r in rows) else "VERIFIED")
        code = {"VERIFIED": 0, "BLOCKED": 1, "INFRASTRUCTURE_FAILURE": 2}[status]
        report = {"format": "verislop.support018-final-reconciliation/1", "closure_id": self.spec.get("closure_id"),
                  "status": status, "verifier_id": self.plan["verifier_id"], "verifier_sha256": sha(Path(__file__).read_bytes()),
                  "specification_sha256": sha(SPEC.read_bytes()), "report_schema_sha256": sha(SCHEMA.read_bytes()),
                  "source_root": self.freeze.get("source_root"),
                  "input_root": self.canonical.digest_json(self.hashes) if self.canonical else None,
                  "claims": rows, "guards": {k: v for k, v in self.results.items() if k.startswith("guards")},
                  "actual_predicate_groups": self.results, "phase_receipts": self.phase_receipts,
                  "evidence": self.evidence, "dependencies": {"trusted": self.plan["trusted_dependencies"], "undeclared": []},
                  "scope": {"finite_qualification_only": True, "excluded": self.plan["excluded_claims"],
                            "llm_consumption_attested": False, "semantic_acceptance_authority": False,
                            "production_task_inputs": False, "prior_pass_inheritance": False},
                  "decision": {"exit_code": code, "manual_override_allowed": False, "valid_states":
                               ["VERIFIED", "BLOCKED", "INFRASTRUCTURE_FAILURE"]}}
        need([r["claim_id"] for r in rows] == list(GROUPS) and len(rows) == 18, "REPORT_ORPHAN_CLAIM")
        write_once(self.output / "report.json", report)
        write_once(self.output / "provenance.json", [{"claim_id": r["claim_id"], "status": r["status"],
            "registered_verifier": r["registered_verifier"], "reconciler_sha256": r["reconciler_sha256"],
            "inputs": r["inputs"], "evidence": r["evidence"], "trusted_dependencies": r["trusted_dependencies"]} for r in rows])
        print(json.dumps({"status": status, "source_root": report["source_root"], "input_root": report["input_root"],
                          "report": str(self.output / "report.json"), "claim_count": 18}, sort_keys=True), flush=True)
        return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-root", type=Path, default=DEFAULT_GATE)
    args = parser.parse_args()
    gate = args.qualification_root.absolute()
    need(gate == DEFAULT_GATE and gate.is_dir() and not gate.is_symlink() and gate.resolve() == gate,
         "ONLY_THE_REGISTERED_NEW_SUPPORT018_ROOT_IS_ADMITTED")
    return Reconciliation(gate).run()


if __name__ == "__main__":
    raise SystemExit(main())
