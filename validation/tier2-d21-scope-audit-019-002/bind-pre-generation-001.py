#!/usr/bin/env python3
"""Read-only future binding; intentionally not invoked during preparation.

Invocation requires a root-supplied spec after the new whole-root qualification.
This binds public preparation inputs only. It never calls pending_request,
generation, a model, a build, a task verifier, or a public probe.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time

AUDIT_ID = "tier2-d21-scope-audit-019"
SPEC_FORMAT = "verislop.d21-pre-generation-binding-spec/1"
HERE = Path(__file__).absolute().parent
REPO = HERE.parent.parent
PROJECT = REPO / "synthetic_dataset/bootstrap/stages/tier2-source-facets-019/project"
COHORT = PROJECT.parent / "run"
DRIVER_ROOT = REPO / "validation/tier2-native-live-driver-019"
PLAN_ROOT = '64e246b31a78939aa6eb0aa5061ea5c3b0331fc07b492215ded16f22183168bb'
PLAN_MANIFEST_SHA = '60f157eaeea79eb01693ad1218c508a90def7d3bb711ab14176f9f4eb1920b90'
PROBE_OBJECT_SHA = "a1c8fc38bb8687b0512a89e3b29d8cd6673b1b75c8608116a6c583c267c5fe28"
PUBLIC_PROMPT_SHA = "1e1a8ccb008420489eab50ddfe73e1632b674ccb2202aeced608a233f7ac3296"
REPORT_SCHEMA = None
REPORT_SCHEMA_SHA = None
ORIGINAL_IDS = ("D1", "A1", "O1", "O2", "O3", "O4", "O5", "O6", "O7", "I1", "S1")
QUALIFICATION_IDS = tuple(f"Q018-{i:02d}" for i in range(1, 19)) + tuple(f"Q019-{i:02d}" for i in range(1, 10))
QUALIFICATION_ROOT = None
QUALIFICATION_CLOSURE = None
QUALIFICATION_SOURCE = None
QUALIFICATION_INPUT = None
QUALIFICATION_ADMISSION_VERIFIER = None
CURRENT_FRESH_PREFIXES = ()
SCHEMA_HELPER_SHA = '5d57a30a7cf89bc16251eb77459919aafdc101ac87b9f7eb9a751e0840393a69'
BINDING_SCHEMA_SHA = '25d09de89241ef495f2cd0cd6fa5bd4c598e2b58dcd0fc0b1a21a2238fd9bfd7'
ACTIVATION_SCHEMA_SHA = 'daabfef5b6133065e5de052a460a9bb4634be5d5cda045d3ec68187f0b1971fe'
SCHEMA_HELPER = None
NATIVE_FIXED_REFERENCES = {'native_driver': {'path': '/home/augustus/VeriSlop_CLI/validation/tier2-native-live-driver-019/driver.py', 'sha256': 'sha256:afeed7df381d443ad60051bc9e0a04ff84a9a82611a49b7373c9545468445830'}, 'native_driver_manifest': {'path': '/home/augustus/VeriSlop_CLI/validation/tier2-native-live-driver-019/hash-manifest.json', 'sha256': 'sha256:06f75555119779873187668c3a19fc32913cf990736f19e578787bd0b34be863'}, 'native_driver_seal': {'path': '/home/augustus/VeriSlop_CLI/validation/tier2-native-live-driver-019/SEAL.sha256', 'sha256': 'sha256:98c15d19006c80c39b4a957d261a18381713e500655fbc5bdf8cf40dfbd1a376'}, 'native_activation_amendment': {'path': '/home/augustus/VeriSlop_CLI/validation/tier2-native-live-driver019-activation-amendment-001/source-binding-amendment.json', 'sha256': 'sha256:df3918b1d2f64dccca03cb5a85496a10c449ec92c616b875da990e2559e56165'}}

SOURCE_PROPERTIES = ["typed_total", "deterministic", "input_preserved", "no_external_io",
                     "no_floating_point", "pure_data", "restricted_runtime_only"]
REQUIRED_REPORT_FIELDS = {"format", "closure_id", "status", "verifier_id", "verifier_sha256",
                          "specification_sha256", "source_root", "input_root", "claims", "guards",
                          "phase_receipts", "evidence", "dependencies", "scope", "decision"}
REQUIRED_CLAIM_FIELDS = {"claim_id", "registered_verifier", "original_statement",
                         "original_pass_condition", "status", "actual_predicates", "inputs",
                         "evidence", "trusted_dependencies", "blocking_reasons"}
DELIVERY_EDITS = (
    ("Implement solution.py with a pure solve(data) function. Input and output are JSON-compatible Python values. "
     "Use Python standard library only, no external I/O.",
     "Deliver program.vscore.json with one pure admitted typed entry named solve. Its typed input and result "
     "must represent the specified JSON input/output structure. Perform no external I/O."),
    ("Implement a pure deterministic Python 3 function solve(data) in solution.py. Use only the standard library, "
     "no external I/O. The function receives a JSON value and returns a JSON-serializable value. "
     "Preserve the specified input/output structure and exact ordering.",
     "Implement the solve entry as canonical vscore/0.3 source under normative Lean vscore-semantics/0.3 "
     "and the data-pipeline/0.3 serialization profile. Preserve the specified input/output structure and exact ordering. "
     "Admitted typed execution is total, pure and deterministic; input values are immutable, and the language has "
     "no external-effect constructors. Arithmetic uses unbounded mathematical integers without floating point. "
     "Strings contain Unicode scalar values and lexicographic order compares scalar codepoints. "
     "There are no additional input bounds or preconditions beyond the functional specification."),
    ("Public examples (additional held-out cases will be scored):",
     "Original public examples (preserved verbatim; universal refinement is required):"),
)


class Block(Exception):
    pass


def require(condition, code, detail):
    if not condition:
        raise Block(f"{code}: {detail}")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def source_map_digest(files):
    require(isinstance(files, dict) and bool(files), "INPUT_MUTATION", "generic source map is empty")
    for name, value in files.items():
        require(isinstance(name, str) and isinstance(value, str), "INPUT_MUTATION", "generic source map is invalid")
        hash_text(value)
    ordered = sorted(files, key=lambda name: name.encode("utf-16-be"))
    data = ("{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" +
                           json.dumps(files[k], ensure_ascii=False) for k in ordered) + "}").encode("utf-8")
    return "sha256:" + digest(data)


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "BINDING_INVALID", f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def hash_text(value):
    require(isinstance(value, str) and re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", value),
            "BINDING_INVALID", "expected an exact SHA256")
    return value.removeprefix("sha256:")


def path_text(value):
    require(isinstance(value, str), "BINDING_INVALID", "path must be a string")
    p = Path(value)
    require(p.is_absolute() and p == p.absolute() and p.resolve() == p,
            "INPUT_MUTATION", f"nonabsolute/indirect path: {p}")
    return p


def pointer(value, selector):
    require(isinstance(selector, str) and (selector == "" or selector.startswith("/")),
            "BINDING_INVALID", "JSON pointer is invalid")
    for segment in selector.split("/")[1:]:
        segment = segment.replace("~1", "/").replace("~0", "~")
        try:
            value = value[int(segment)] if isinstance(value, list) else value[segment]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise Block(f"EVIDENCE_MISSING: JSON pointer {selector}") from exc
    return value


class Reader:
    def __init__(self):
        self.reads = []

    def raw(self, path, expected=None, purpose="public binding input"):
        path = path_text(str(path))
        require(path.is_file() and not path.is_symlink(), "INPUT_MUTATION", str(path))
        data = path.read_bytes()
        actual = digest(data)
        self.reads.append({"path": str(path), "sha256": actual, "size_bytes": len(data), "purpose": purpose})
        if expected is not None:
            require(actual == hash_text(expected), "INPUT_MUTATION", f"hash mismatch: {path}")
        return data

    def obj(self, path, expected=None, purpose="public JSON binding input"):
        try:
            return load_schema_helper(self).strict_json(self.raw(path, expected, purpose))
        except (UnicodeError, ValueError) as exc:
            raise Block(f"BINDING_INVALID: malformed JSON at {path}: {exc}") from exc

    def artifact(self, record, purpose):
        require(isinstance(record, dict) and {"path", "sha256"} <= set(record),
                "BINDING_INVALID", purpose)
        return self.obj(path_text(record["path"]), record["sha256"], purpose)



def load_schema_helper(reader):
    global SCHEMA_HELPER
    path = HERE / "binding_schema.py"
    reader.raw(path, SCHEMA_HELPER_SHA, "exact registered generic closed-schema validator source")
    if SCHEMA_HELPER is None:
        module_spec = importlib.util.spec_from_file_location("_verislop_scope019_002_schema", path)
        require(module_spec is not None and module_spec.loader is not None, "BINDING_INVALID", "schema helper import unavailable")
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        SCHEMA_HELPER = module
    return SCHEMA_HELPER


def validate_binding_schema(reader, spec):
    helper = load_schema_helper(reader)
    raw = reader.raw(HERE / "pre-generation-binding-reader-schema-001.json", BINDING_SCHEMA_SHA,
                     "exact registered closed pre-generation schema before claims")
    schema = helper.strict_json(raw)
    helper.validate_closed_schema(schema, spec)
    require(hash_text(spec["reader_schema_sha256"]) == BINDING_SCHEMA_SHA,
            "BINDING_INVALID", "caller binding schema identity differs")


def authenticate_native_driver(reader, spec):
    helper = load_schema_helper(reader)
    for key, expected in NATIVE_FIXED_REFERENCES.items():
        helper.exact_driver_reference(spec[key], expected)
    driver = path_text(spec["native_driver"]["path"])
    require(driver == DRIVER_ROOT / "driver.py", "WRONG_DRIVER", "sole native driver must be exact sealed driver.py")
    manifest = reader.artifact(spec["native_driver_manifest"], "exact sealed native019 source manifest")
    seal = reader.raw(path_text(spec["native_driver_seal"]["path"]), spec["native_driver_seal"]["sha256"], "exact sealed native019 source seal")
    require(seal == (hash_text(spec["native_driver_manifest"]["sha256"]) + "  hash-manifest.json\n").encode(),
            "INPUT_MUTATION", "native019 manifest seal content differs")
    require(manifest["format"] == "verislop.native019-source-preparation-manifest/1" and manifest["activation_authority"] is False and
            {row["path"] for row in manifest["files"]} == {
                (DRIVER_ROOT / name).relative_to(REPO).as_posix() for name in
                ("driver.py", "orchestration-specification.json", "source-checks.json")},
            "INPUT_MUTATION", "sealed native019 source member inventory differs")
    require(len(manifest["files"]) == 3, "INPUT_MUTATION", "native019 source manifest has duplicate members")
    for item in manifest["files"]:
        relative = Path(item["path"])
        require(not relative.is_absolute() and relative.as_posix() == item["path"] and ".." not in relative.parts,
                "INPUT_MUTATION", "native source path differs")
        raw = reader.raw(REPO / relative, item["sha256"], "exact sealed native019 source member")
        require(type(item["byte_count"]) is int and item["byte_count"] == len(raw), "INPUT_MUTATION", "native source size differs")
    actual_driver = next(row for row in manifest["files"] if REPO / row["path"] == driver)
    require(hash_text(actual_driver["sha256"]) == hash_text(spec["native_driver"]["sha256"]),
            "INPUT_MUTATION", "native driver source identity differs from sealed member")
    reader.raw(driver, spec["native_driver"]["sha256"], "exact driver.py fixed source identity")
    amendment = reader.artifact(spec["native_activation_amendment"], "exact append-only source prerequisite amendment")
    require(amendment["format"] == "verislop.native019-prospective-activation-amendment/1" and
            amendment["activation_authority"] is False and amendment["driver_changed"] is False and
            amendment["prior_runtime_PASS_reused"] is False and amendment["status"] == "UNRESOLVED_SOURCE_PREPARATION_ONLY" and
            amendment["new_prospective_prerequisite"]["required_claims"] == 27 and
            amendment["new_prospective_prerequisite"]["required_independent_whole_status"] == "VERIFIED",
            "BINDING_INVALID", "append-only amendment narrows prerequisite or grants authority")
    require(amendment["new_prospective_prerequisite"]["root"] == Path(spec["qualification_root"]).relative_to(REPO).as_posix() and
            amendment["new_prospective_prerequisite"]["closure_id"] == spec["qualification_closure_id"],
            "STALE_OR_UNBOUND_EVIDENCE", "future actual qualification root differs from append-only amendment")
    return {key: spec[key] for key in NATIVE_FIXED_REFERENCES}


def authenticate_activation_binding(reader, spec):
    helper = load_schema_helper(reader)
    schema = helper.strict_json(reader.raw(HERE / "native-activation-binding-schema.json", ACTIVATION_SCHEMA_SHA,
                                          "exact closed actual activation prerequisite schema"))
    record_path = path_text(spec["native_activation_binding"]["path"])
    require(record_path.parent == path_text(spec["native_activation_amendment"]["path"]).parent and
            record_path != path_text(spec["native_activation_amendment"]["path"]),
            "BINDING_INVALID", "actual activation prerequisite record must be a separate append-only amendment child")
    binding = reader.artifact(spec["native_activation_binding"], "actual fresh qualification prerequisite binding; no activation grant")
    helper.validate_closed_schema(schema, binding)
    expected = {key: spec[key] for key in ("qualification_root", "qualification_closure_id", "qualification_report",
                "qualification_independent_report", "qualification_independent_admission", "qualification_admission_receipt",
                "engineering_record", "source_freeze", "native_driver", "native_driver_manifest", "native_driver_seal",
                "native_activation_amendment", "project", "cohort", "protocol_sha256", "preregistration_sha256", "project_snapshot_sha256")}
    expected.update({"source_root": QUALIFICATION_SOURCE, "input_root": QUALIFICATION_INPUT,
                     "qualification_claim_ids": list(QUALIFICATION_IDS), "scope_plan_root": PLAN_ROOT,
                     "scope_reader": {"path": str(Path(__file__).absolute()), "sha256": spec["reader_sha256"]}})
    helper.exact_activation_binding(binding, expected)
    completed = reader.artifact(spec["qualification_admission_receipt"], "actual admission completion chronology")
    stamps = [datetime.fromisoformat(value.replace("Z", "+00:00")) for value in
              (completed["completed_utc"], binding["created_at_utc"])]
    require(all(value.utcoffset() is not None and value.utcoffset().total_seconds() == 0 for value in stamps) and
            stamps[0] <= stamps[1], "STALE_OR_UNBOUND_EVIDENCE", "activation prerequisite binding predates actual fresh admission")
    return {"binding": spec["native_activation_binding"], "amendment": spec["native_activation_amendment"],
            "prerequisite_status": binding["status"], "activation_authority": False,
            "final_activation_requires_later_actual_binder_receipt": True}


def freeze_plan(reader):
    manifest = reader.obj(HERE / "FREEZE-MANIFEST.json", PLAN_MANIFEST_SHA, "immutable scope plan manifest")
    require(manifest["preregistration_input_root_hash"] == PLAN_ROOT,
            "CLAIM_MUTATION", "scope plan root differs")
    require(digest(canon(manifest["canonical_manifest"])) == PLAN_ROOT,
            "CLAIM_MUTATION", "canonical scope plan root differs")
    for item in manifest["canonical_manifest"]["files"]:
        p = REPO / item["path"]
        require(p.parent == HERE, "CLAIM_MUTATION", "plan file escaped audit directory")
        data = reader.raw(p, item["sha256"], "immutable scope plan input")
        require(len(data) == item["size_bytes"], "CLAIM_MUTATION", "plan size differs")
    probes = reader.obj(HERE / "public-probes.json")
    require(digest(canon(probes["probes"])) == PROBE_OBJECT_SHA and len(probes["probes"]) == 9,
            "PROBE_BYTE_MUTATION", "fixed nine public probes differ")
    checks = reader.obj(HERE / "planned-evidence-checks.json")
    require([row["id"] for row in checks["checks"]] == [f"AUD-{i:02d}" for i in range(1, 25)],
            "CLAIM_MUTATION", "fixed 24 scope checks differ")
    metadata = reader.obj(HERE / "original-public-metadata-projection.json")
    return manifest, metadata


def receipt(reader, record, report):
    data = reader.artifact(record, "actual qualified phase process receipt")
    observed = pointer(data, record["returncode_pointer"])
    require(type(observed) is int and observed == 0, "VERIFIER_FAILURE", "actual process returncode is not numeric zero")
    require(hash_text(pointer(report, record["report_sha256_pointer"])) == hash_text(record["sha256"]),
            "STALE_OR_UNBOUND_EVIDENCE", "actual process receipt is not authenticated by the current Q018 report")
    return {"path": record["path"], "sha256": record["sha256"], "returncode": observed}


def qualification(reader, spec, canonical, bootstrap):
    report = reader.artifact(spec["qualification_report"], "new whole-root Q018 final reconciliation report")
    require(hash_text(spec["qualification_report_schema_sha256"]) == REPORT_SCHEMA_SHA,
            "CLAIM_MUTATION", "prospectively fixed Q018 report schema hash differs")
    schema = reader.raw(REPORT_SCHEMA, REPORT_SCHEMA_SHA, "prospectively fixed Q018 report schema")
    require(REQUIRED_REPORT_FIELDS <= set(report) and
            report["format"] == "verislop.support019-final-reconciliation/1" and report["status"] == "VERIFIED",
            "QUALIFICATION_INCOMPLETE", "new Q018 final report is incomplete or not VERIFIED")
    require(report["decision"]["manual_override_allowed"] is False and
            type(report["decision"]["exit_code"]) is int and report["decision"]["exit_code"] == 0,
            "QUALIFICATION_INCOMPLETE", "Q018 decision is not immutable numeric zero")
    rows = report["claims"]
    require(isinstance(rows, list) and len(rows) == 27 and
            sorted(row.get("claim_id", "") for row in rows) == list(QUALIFICATION_IDS),
            "QUALIFICATION_INCOMPLETE", "exact original18 plus Q019-01..Q019-09 are required")
    for row in rows:
        require(REQUIRED_CLAIM_FIELDS <= set(row) and row["status"] == "VERIFIED" and
                row["blocking_reasons"] == [] and bool(row["actual_predicates"]) and
                bool(row["evidence"]) and bool(row["inputs"]),
                "QUALIFICATION_INCOMPLETE", f"missing actual Q018 evidence: {row.get('claim_id')}")
    require(report["closure_id"] == QUALIFICATION_CLOSURE and
            spec["expected_source_root"] == QUALIFICATION_SOURCE and
            spec["expected_qualification_input_root"] == QUALIFICATION_INPUT,
            "STALE_OR_UNBOUND_EVIDENCE", "exact freshly admitted current closure/source/input are required")
    require(report["source_root"] == spec["expected_source_root"] and
            report["input_root"] == spec["expected_qualification_input_root"],
            "STALE_OR_UNBOUND_EVIDENCE", "Q018 actual source/input root differs")
    require(hash_text(report["verifier_sha256"]) == hash_text(spec["qualification_verifier"]["sha256"]) and
            hash_text(report["specification_sha256"]) == hash_text(spec["qualification_specification"]["sha256"]),
            "VERIFIER_MISMATCH", "Q018 verifier/specification identity differs")
    reader.raw(path_text(spec["qualification_verifier"]["path"]), spec["qualification_verifier"]["sha256"], "registered final qualification verifier, not executed")
    reader.raw(path_text(spec["qualification_specification"]["path"]), spec["qualification_specification"]["sha256"], "fixed qualification specification")
    frozen = reader.artifact(spec["source_freeze"], "new engineering source freeze")
    engineering = reader.artifact(spec["engineering_record"], "new validated generic engineering record")
    require(frozen["format"] == "verislop.tier2-engineering-source-freeze/0.1" and
            frozen["generation_started"] is False and frozen["source_root"] == spec["expected_source_root"] and
            canonical.digest_json(frozen["source_files"]) == frozen["source_root"],
            "INPUT_MUTATION", "new engineering source freeze differs")
    require(engineering["format"] == "verislop.tier2-engineering-validation/0.1" and
            engineering["status"] == "VERIFIED" and engineering["source_root"] == frozen["source_root"] and
            engineering["source_freeze"] == spec["source_freeze"]["path"] and
            hash_text(engineering["source_freeze_sha256"]) == hash_text(spec["source_freeze"]["sha256"]) and
            engineering["fresh_model_calls"] == 0 and engineering["fixture_only"] is True and
            engineering["model_authoring_input"] is False,
            "QUALIFICATION_INCOMPLETE", "actual engineering/source-freeze linkage differs")
    require([b.get("build") for b in engineering["builds"]] == ["A", "B"] and
            all(b.get("ok") is True and b.get("errors") == [] for b in engineering["builds"]) and
            engineering["builds"][0]["outputs"] == engineering["builds"][1]["outputs"] and
            engineering["determinism"]["mismatches"] == [],
            "CLEAN_BUILD_FAILURE", "actual engineering A/B observations differ")
    required = engineering["required_claim_observations"]
    require(isinstance(required, list) and bool(required) and
            all(c.get("required") is True and c.get("outcome") == "PASS" for c in required),
            "QUALIFICATION_INCOMPLETE", "engineering required registered claims are not all PASS")
    # The engineering cardinality belongs to its own registered closure, never to Q018's 18 claims.
    # This exact qualified registered validator reconstructs the actual complete
    # native report/package/mechanical snapshot and compares the ENTIRE record.
    # It is read-only: its public contract performs no kernel rerun/model/build.
    # Package/report/result hashes retain their actual authenticated provenance;
    # no redundant synthetic snapshot or direct Q018 report fields are invented.
    require(canonical.digest_json(engineering["package_files"]) == engineering["package_files_root"] and
            engineering["package_files"].get(engineering["mechanical_result"]) == engineering["mechanical_result_sha256"],
            "STALE_OR_UNBOUND_EVIDENCE", "engineering native package/result inventory binding differs")
    bootstrap.verify_engineering_record(engineering)
    links = spec["qualification_links"]
    for item in links:
        require(pointer(report, item["report_pointer"]) == item["expected"],
                "STALE_OR_UNBOUND_EVIDENCE", f"qualification provenance link differs: {item['report_pointer']}")
    require({"engineering_record", "source_freeze"} <=
            {item["artifact"] for item in links}, "STALE_OR_UNBOUND_EVIDENCE", "qualification lacks engineering links")
    for item in links:
        artifact = spec[item["artifact"]]
        require(hash_text(item["expected"]) == hash_text(artifact["sha256"]),
                "STALE_OR_UNBOUND_EVIDENCE", "qualification link does not authenticate the supplied artifact")
    input_manifest = reader.artifact(spec["qualification_input_manifest"], "actual qualification input inventory")
    manifest_value = pointer(input_manifest, spec["qualification_input_manifest"]["canonical_pointer"])
    require(hash_text(canonical.digest_json(manifest_value)) == hash_text(report["input_root"]),
            "STALE_OR_UNBOUND_EVIDENCE", "qualification canonical input root differs")
    receipts = [receipt(reader, item, report) for item in spec["qualification_process_receipts"]]
    require(bool(receipts), "VERIFIER_NOT_RUN", "actual qualification process receipt is absent")
    return report, engineering, frozen, receipts, digest(schema)




def bind_current_root_metadata(reader, spec):
    global QUALIFICATION_ROOT, QUALIFICATION_CLOSURE, QUALIFICATION_SOURCE, QUALIFICATION_INPUT
    global REPORT_SCHEMA, REPORT_SCHEMA_SHA, QUALIFICATION_ADMISSION_VERIFIER
    QUALIFICATION_ROOT = path_text(spec["qualification_root"])
    require(QUALIFICATION_ROOT.parent == REPO / "validation" and
            re.fullmatch(r"tier2-support-019-qualification-[0-9]{3}", QUALIFICATION_ROOT.name),
            "BINDING_INVALID", "new canonical support019 qualification root required")
    QUALIFICATION_CLOSURE = spec["qualification_closure_id"]
    require(isinstance(QUALIFICATION_CLOSURE, str) and re.fullmatch(r"support019-final-current-root-[0-9]{3}", QUALIFICATION_CLOSURE),
            "BINDING_INVALID", "fresh registered support019 closure required")
    QUALIFICATION_SOURCE = spec["expected_source_root"]
    QUALIFICATION_INPUT = spec["expected_qualification_input_root"]
    require(all(isinstance(v, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", v) for v in
                (QUALIFICATION_SOURCE, QUALIFICATION_INPUT)), "BINDING_INVALID", "exact canonical actual source/input roots required")
    REPORT_SCHEMA = path_text(spec["qualification_report_schema"]["path"])
    REPORT_SCHEMA_SHA = hash_text(spec["qualification_report_schema"]["sha256"])
    require(hash_text(spec["qualification_report_schema_sha256"]) == REPORT_SCHEMA_SHA,
            "BINDING_INVALID", "actual registered report schema identity differs")
    QUALIFICATION_ADMISSION_VERIFIER = path_text(spec["qualification_admission_verifier"]["path"])
    schema = reader.artifact(spec["qualification_report_schema"], "future actual frozen all27 report schema")
    require(schema["format"] == "verislop.support019-adapter-report-schema/1" and
            schema["manual_override_allowed"] is False and schema["valid_states"] == ["VERIFIED", "BLOCKED", "INFRASTRUCTURE_FAILURE"] and
            set(schema["required"]) <= REQUIRED_REPORT_FIELDS | {"actual_predicate_groups"},
            "CLAIM_MUTATION", "future all27 schema decision or required fields differs")


def current_artifact(reader, record, purpose):
    path = path_text(record["path"])
    require(path.is_relative_to(QUALIFICATION_ROOT), "STALE_OR_UNBOUND_EVIDENCE", purpose + " outside current freshly bound qualification root")
    return reader.artifact(record, purpose)


def relative_observation(reader, item, purpose):
    require(isinstance(item, dict) and {"path", "sha256", "byte_count"} <= set(item), "BINDING_INVALID", purpose)
    name = Path(item["path"])
    require(not name.is_absolute() and name.as_posix() == item["path"] and ".." not in name.parts,
            "INPUT_MUTATION", purpose + " invalid relative path")
    path = REPO / name
    require(path.is_relative_to(QUALIFICATION_ROOT) or any(path.is_relative_to(REPO / p) for p in
            CURRENT_FRESH_PREFIXES), "STALE_OR_UNBOUND_EVIDENCE", purpose + " outside frozen fresh evidence prefixes")
    raw = reader.raw(path, item["sha256"], purpose)
    require(type(item["byte_count"]) is int and item["byte_count"] == len(raw), "INPUT_MUTATION", purpose + " byte count")
    return raw


def current_receipt(reader, record, report_record, argv, ident, environment, source_freeze):
    receipt = current_artifact(reader, record, "actual current completed direct verifier receipt")
    require(receipt["format"] in ("verislop.support018-actual-process-receipt/1", "verislop.support019-actual-process-receipt/1") and
            receipt["id"] == ident and receipt["argv"] == argv and receipt["cwd"] == str(REPO) and
            receipt["registered_environment"] == environment, "VERIFIER_MISMATCH", "exact actual registered process binding differs")
    require(type(receipt["pid"]) is int and receipt["pid"] > 0 and type(receipt["returncode"]) is int and
            receipt["returncode"] == 0 and receipt["timed_out"] is False and receipt["timeout_seconds"] is None,
            "VERIFIER_FAILURE", "actual direct process is not numeric zero or provenance/deadline differs")
    require(receipt["source_root"] == QUALIFICATION_SOURCE and receipt["input_root"] == QUALIFICATION_INPUT,
            "STALE_OR_UNBOUND_EVIDENCE", "actual direct process roots differ")
    stamps = [datetime.fromisoformat(value.replace("Z", "+00:00")) for value in
              (source_freeze["created_at_utc"], receipt["started_utc"], receipt["completed_utc"])]
    require(all(value.utcoffset() is not None and value.utcoffset().total_seconds() == 0 for value in stamps) and
            stamps[0] <= stamps[1] <= stamps[2], "STALE_OR_UNBOUND_EVIDENCE", "actual verifier chronology differs")
    for stream in ("stdout", "stderr"):
        relative_observation(reader, receipt[stream], "actual current direct verifier " + stream)
    if report_record is not None:
        identity = receipt["report"]
        require(REPO / identity["path"] == path_text(report_record["path"]) and
                hash_text(identity["sha256"]) == hash_text(report_record["sha256"]),
                "STALE_OR_UNBOUND_EVIDENCE", "actual direct process report binding differs")
        relative_observation(reader, identity, "actual process completed report")
    return receipt


def independent_qualification(reader, spec, final_report, canonical):
    global CURRENT_FRESH_PREFIXES
    manifest = reader.artifact(spec["qualification_input_manifest"], "exact current registered input manifest")
    require(path_text(spec["qualification_input_manifest"]["path"]) == QUALIFICATION_ROOT / "qualification-inputs.json" and
            spec["qualification_input_manifest"]["canonical_pointer"] == "/source_hashes" and
            manifest["source_root"] == QUALIFICATION_SOURCE and manifest["input_root"] == QUALIFICATION_INPUT and
            canonical.digest_json(manifest["source_hashes"]) == QUALIFICATION_INPUT, "INPUT_MUTATION", "exact current input root required")
    hashes = manifest["source_hashes"]
    for artifact_key in ("qualification_report_schema", "qualification_admission_verifier"):
        artifact = spec[artifact_key]
        artifact_path = path_text(artifact["path"])
        require(artifact_path.is_relative_to(REPO) and hashes.get(artifact_path.relative_to(REPO).as_posix()) is not None and
                hash_text(hashes[artifact_path.relative_to(REPO).as_posix()]) == hash_text(artifact["sha256"]),
                "VERIFIER_MISMATCH", "actual schema/admission verifier not in complete current frozen input map")
    for name, expected in sorted(hashes.items()):
        relative = Path(name)
        require(not relative.is_absolute() and relative.as_posix() == name and ".." not in relative.parts,
                "INPUT_MUTATION", "registered qualification path differs")
        reader.raw(REPO / relative, expected, "unchanged full frozen current qualification input bytes")
    qspec = reader.obj(QUALIFICATION_ROOT / "qualification-specification.json", hashes[(QUALIFICATION_ROOT / "qualification-specification.json").relative_to(REPO).as_posix()])
    frozen = reader.artifact(spec["source_freeze"], "exact current engineering freeze")
    require(path_text(spec["source_freeze"]["path"]) == QUALIFICATION_ROOT / "source-freeze.json" and
            path_text(spec["engineering_record"]["path"]) == QUALIFICATION_ROOT / "final-reconciliation/engineering-record.json" and
            path_text(spec["qualification_report"]["path"]) == QUALIFICATION_ROOT / "final-reconciliation/report.json" and
            qspec["closure_id"] == QUALIFICATION_CLOSURE and qspec["source_root"] == QUALIFICATION_SOURCE,
            "STALE_OR_UNBOUND_EVIDENCE", "exact current source/final/engineering paths required")
    prereg = reader.obj(QUALIFICATION_ROOT / "preregistration.json")
    require(set(prereg["external_bindings"]) == {"source-freeze.json", "qualification-specification.json", "qualification-inputs.json"} and
            prereg["input_root"] == QUALIFICATION_INPUT and prereg["source_root"] == QUALIFICATION_SOURCE and
            prereg["generation_started"] is False, "INPUT_MUTATION", "current preregistration bindings differ")
    for name, expected in prereg["external_bindings"].items():
        reader.raw(QUALIFICATION_ROOT / name, expected, "exact current externally bound preregistration input")
    CURRENT_FRESH_PREFIXES = qspec["fresh_evidence_prefixes"]
    require(isinstance(CURRENT_FRESH_PREFIXES, list) and CURRENT_FRESH_PREFIXES and
            all(isinstance(p, str) and not Path(p).is_absolute() and ".." not in Path(p).parts for p in CURRENT_FRESH_PREFIXES),
            "BINDING_INVALID", "current frozen fresh evidence prefix inventory differs")
    claims_path = REPO / qspec["adapters"]["claims_file"]
    claims = reader.obj(claims_path, hashes[claims_path.relative_to(REPO).as_posix()])
    expected_claims = claims["original_claims"] + claims["additional_claims"]
    require([c["id"] for c in expected_claims] == list(QUALIFICATION_IDS), "CLAIM_MUTATION", "all27 exact registered claims required")
    require([r["claim_id"] for r in final_report["claims"]] == list(QUALIFICATION_IDS), "CLAIM_MUTATION", "final report claim ordering differs")
    for original, row in zip(expected_claims, final_report["claims"]):
        require(row["original_statement"] == original["statement"] and row["original_pass_condition"] == original["pass_condition"] and
                row["trusted_dependencies"] == original["dependencies_trusted"] and row["registered_verifier"] == original["verifier"],
                "CLAIM_MUTATION", "final registered semantic claim differs")
    indexes = spec["qualification_ancillary_index_hashes"]
    require(set(indexes) == {"equality", "carrier", "author", "pure"}, "BINDING_INVALID", "four actual index identities required")
    for key, expected in indexes.items():
        reader.raw(REPO / qspec["adapters"]["additional_evidence_paths"][key], expected, "fresh actual ancillary index")
    reconcile_reg_path = REPO / qspec["adapters"]["adapter_wrapper_registrations"]["reconcile"]
    predicate_reg_path = REPO / qspec["adapters"]["adapter_wrapper_registrations"]["reader"]
    reconcile_reg = reader.obj(reconcile_reg_path, hashes[reconcile_reg_path.relative_to(REPO).as_posix()])
    predicate_reg = reader.obj(predicate_reg_path, hashes[predicate_reg_path.relative_to(REPO).as_posix()])
    for reg in (reconcile_reg, predicate_reg):
        require(reg["closure_id"] == QUALIFICATION_CLOSURE and
                hashes[reg["verifier"]["path"]] == reg["verifier"]["sha256"], "VERIFIER_MISMATCH", "registered current source verifier differs")
        reader.raw(REPO / reg["verifier"]["path"], reg["verifier"]["sha256"], "registered current verifier source; not executed")
    interpreter = qspec["execution_phases"][0]["argv"][0]
    bindings = {"python": interpreter, "qualification_root": str(QUALIFICATION_ROOT),
                "final_report": str(QUALIFICATION_ROOT / "final-reconciliation/report.json"),
                "finalizer_receipt": str(QUALIFICATION_ROOT / "reconcile-child-process-receipt.json"),
                "output": str(QUALIFICATION_ROOT / "independent-audit"),
                **{k + "_index_sha256": v for k, v in indexes.items()}}
    for key, reg, report_record in (("qualification_finalizer_receipt", reconcile_reg, spec["qualification_report"]),
                                    ("qualification_predicate_receipt", predicate_reg, spec["qualification_independent_report"])):
        binding = {**bindings, "verifier": str(REPO / reg["verifier"]["path"])}
        argv = [part.format(**binding) for part in reg["invocation"]["argv_template"]]
        expected_receipt = "reconcile-child-process-receipt.json" if key == "qualification_finalizer_receipt" else "reader-child-process-receipt.json"
        require(path_text(spec[key]["path"]) == QUALIFICATION_ROOT / expected_receipt,
                "STALE_OR_UNBOUND_EVIDENCE", "actual current child receipt path differs")
        current_receipt(reader, spec[key], report_record, argv, "reconcile-child" if key == "qualification_finalizer_receipt" else "reader-child", {}, frozen)
    independent = current_artifact(reader, spec["qualification_independent_report"], "fresh independently checked current all27 predicate report")
    require(path_text(spec["qualification_independent_report"]["path"]) == QUALIFICATION_ROOT / "independent-audit/report.json" and
            independent["format"] == "verislop.support019-independent-predicate-report/1" and independent["status"] == "VERIFIED" and
            independent["closure_id"] == QUALIFICATION_CLOSURE and independent["source_root"] == QUALIFICATION_SOURCE and
            independent["input_root"] == QUALIFICATION_INPUT and independent["decision"]["manual_override_allowed"] is False and
            type(independent["exit_code"]) is int and independent["exit_code"] == 0 and
            hash_text(independent["verifier_hash"]) == hash_text(predicate_reg["verifier"]["sha256"]) and
            [r["claim_id"] for r in independent["claims"]] == list(QUALIFICATION_IDS),
            "QUALIFICATION_INCOMPLETE", "fresh independent all27 predicate report differs")
    for original, row in zip(expected_claims, independent["claims"]):
        registered = qspec["independent_claim_checks"][original["id"]]
        require(row["status"] == "VERIFIED" and row["blocking_reasons"] == [] and row["raw_evidence_refs"] and
                row["original_statement"] == original["statement"] and row["original_pass_condition"] == original["pass_condition"] and
                row["trusted_dependencies"] == original["dependencies_trusted"] and row["checked_predicates"] == registered["required_predicate_names"] and
                row["verifier_id"] == registered["verifier_id"] and hash_text(row["verifier_hash"]) == hash_text(hashes[registered["verifier_path"]]) and
                row["closure_id"] == QUALIFICATION_CLOSURE and row["source_root"] == QUALIFICATION_SOURCE and row["input_root"] == QUALIFICATION_INPUT,
                "QUALIFICATION_INCOMPLETE", "actual independent claim predicates/roots/verifier/raw evidence differs")
        for item in row["raw_evidence_refs"]:
            relative_observation(reader, item, "actual independently checked predicate raw evidence")
    admission = current_artifact(reader, spec["qualification_independent_admission"], "actual independent complete current admission report")
    audit_path = QUALIFICATION_ADMISSION_VERIFIER
    require(audit_path.name == "audit_actual.py" and audit_path.is_relative_to(REPO / "validation") and
            hash_text(spec["qualification_admission_verifier"]["sha256"]) == hash_text(hashes[audit_path.relative_to(REPO).as_posix()]),
            "VERIFIER_MISMATCH", "whole-root admission verifier identity differs")
    require(admission["format"] == "verislop.support019-independent-admission-report/1" and admission["status"] == "VERIFIED" and
            admission["closure_id"] == QUALIFICATION_CLOSURE and admission["source_root"] == QUALIFICATION_SOURCE and admission["input_root"] == QUALIFICATION_INPUT and
            admission["claim_ids"] == list(QUALIFICATION_IDS) and admission["manual_override_allowed"] is False and
            admission["activation_authority"] is False and admission["blocking_reasons"] == [] and admission["infrastructure_errors"] == [] and
            hash_text(admission["verifier_hash"]) == hash_text(hashes[audit_path.relative_to(REPO).as_posix()]),
            "QUALIFICATION_INCOMPLETE", "actual whole27 independent admission missing/stale/blocked")
    reader.raw(audit_path, hashes[audit_path.relative_to(REPO).as_posix()], "registered independent admission verifier source; not executed")
    process_index = current_artifact(reader, spec["qualification_process_output_index"], "fresh actual registered process output index")
    require(path_text(spec["qualification_process_output_index"]["path"]) == REPO / qspec["actual_process_output_index_path"] and
            process_index["closure_id"] == QUALIFICATION_CLOSURE and process_index["source_root"] == QUALIFICATION_SOURCE and process_index["input_root"] == QUALIFICATION_INPUT,
            "STALE_OR_UNBOUND_EVIDENCE", "fresh actual process index path/roots differ")
    phase_names = [p["id"] for p in qspec["execution_phases"] + qspec["additional_processes"]]
    require(admission["actual_registered_processes"] == phase_names and set(process_index["processes"]) == set(phase_names),
            "QUALIFICATION_INCOMPLETE", "all8 registered actual phase outputs required")
    require(process_index["format"] == "verislop.support019-process-output-index/1" and
            hashes.get(process_index["producer_path"]) == process_index["producer_sha256"],
            "VERIFIER_MISMATCH", "current process index producer not frozen")
    previous_completion = datetime.fromisoformat(frozen["created_at_utc"].replace("Z", "+00:00"))
    for phase in qspec["execution_phases"] + qspec["additional_processes"]:
        bound = process_index["processes"][phase["id"]]
        require(set(bound["outputs"]) == set(phase["outputs"]), "QUALIFICATION_INCOMPLETE", "registered phase output inventory differs")
        item = bound["receipt"]
        relative_observation(reader, item, "actual registered phase receipt")
        process = current_receipt(reader, {"path": str(REPO / item["path"]), "sha256": item["sha256"]}, None,
                                  phase["argv"], phase["id"], phase["environment"], frozen)
        started = datetime.fromisoformat(process["started_utc"].replace("Z", "+00:00"))
        require(previous_completion <= started, "STALE_OR_UNBOUND_EVIDENCE", "actual registered phases not serialized")
        previous_completion = datetime.fromisoformat(process["completed_utc"].replace("Z", "+00:00"))
        for key, value in bound["outputs"].items():
            require(value["path"] == phase["outputs"][key], "STALE_OR_UNBOUND_EVIDENCE", "actual phase output substituted")
            relative_observation(reader, value, "actual registered phase output")
    for item in admission["evidence"].values():
        relative_observation(reader, item, "independent admission authenticated current evidence")
    output = path_text(spec["qualification_independent_admission"]["path"]).parent
    require(output.parent == QUALIFICATION_ROOT, "BINDING_INVALID", "admission output must be a fresh direct qualification child")
    argv = [interpreter, str(audit_path), "--qualification-root", QUALIFICATION_ROOT.relative_to(REPO).as_posix(),
            "--output", output.relative_to(REPO).as_posix(),
            "--process-output-index-sha256", spec["qualification_process_output_index"]["sha256"],
            "--channel-index-sha256", indexes["carrier"], "--author-index-sha256", indexes["author"]]
    current_receipt(reader, spec["qualification_admission_receipt"], spec["qualification_independent_admission"], argv,
                    "independent-admission", {}, frozen)
    return {"qualification_closure_id": QUALIFICATION_CLOSURE, "source_root": QUALIFICATION_SOURCE,
            "input_root": QUALIFICATION_INPUT, "claim_ids": list(QUALIFICATION_IDS), "registered_processes": phase_names,
            "independent_predicate_report": spec["qualification_independent_report"],
            "independent_admission_report": spec["qualification_independent_admission"],
            "independent_admission_receipt": spec["qualification_admission_receipt"],
            "model_identity": "UNATTESTED", "semantic_consumption": "UNATTESTED", "generation_authority": False}


def public_preparation(reader, spec, bootstrap, canonical, metadata, frozen):
    protocol = reader.obj(COHORT / "protocol.json", spec["protocol_sha256"], "new public protocol")
    prereg = reader.obj(COHORT / "preregistration.json", spec["preregistration_sha256"], "new public bootstrap preregistration")
    require(protocol["generation_started"] is False and prereg["generation_started"] is False,
            "PREREGISTRATION_LATE", "generation has started")
    require(not (COHORT / "artifacts").exists(), "PREREGISTRATION_LATE",
            "native task artifact directory exists; pre-generation binding cannot inspect it")
    require(protocol["project_path"] == str(PROJECT) and protocol["stage"] == spec["stage"] and
            protocol["task_order"] == ["D21"] and len(protocol["tasks"]) == 1 and
            protocol["tasks"][0]["id"] == "D21" and
            protocol["pair_order"] == [{"task": "D21", "arm": "verislop", "pair_index": 0}],
            "WRONG_STAGE", "only the fresh D21 stage019 cohort is admissible")
    require(protocol["source_root"] == spec["expected_source_root"] and
            protocol["source_files"] == frozen["source_files"] and
            canonical.digest_json(protocol["source_files"]) == protocol["source_root"],
            "INPUT_MUTATION", "project/protocol/current qualified source maps differ")
    snapshot = reader.obj(PROJECT / "TIER2-SNAPSHOT.json", spec["project_snapshot_sha256"], "new generic project snapshot")
    require(snapshot["source_root"] == protocol["source_root"] and snapshot["source_files"] == protocol["source_files"] and
            snapshot["cases_or_oracles_copied"] is False and snapshot["historical_snapshots_modified"] is False,
            "SCOPE_LEAK", "snapshot source map or exclusions differ")
    for excluded in ("synthetic_dataset/tasks", "synthetic_dataset/cases", "withheld", "artifacts", "solutions", "oracles"):
        require(not (PROJECT / excluded).exists(), "SCOPE_LEAK", f"excluded task/oracle tree is present: {excluded}")
    for name, expected in sorted(protocol["source_files"].items()):
        p = Path(name)
        require(not p.is_absolute() and p.as_posix() == name and ".." not in p.parts,
                "INPUT_MUTATION", "invalid generic source path")
        reader.raw(PROJECT / p, expected, "qualified generic project source")
        reader.raw(COHORT / "execution-source" / p, expected, "exact generic execution-source snapshot")
    required_public_inputs = {"config.json", "provider-home/endpoint-profiles.json", "engineering-validation.json",
                              "requests/D21/original-prompt.txt", "requests/D21/revised-prompt.txt",
                              "requests/D21/original-metadata.json", "requests/D21/delivery-revision.json",
                              "requests/D21/source-policy.json"}
    require(set(protocol["input_files"]) == required_public_inputs, "SCOPE_LEAK",
            "complete public input map differs from the fixed bootstrap schema; no cardinality cap is applied")
    for name, expected in sorted(protocol["input_files"].items()):
        reader.raw(COHORT / name, expected, "complete public cohort input inventory")
    fixed = {"tier": 2, "target": "vscore", "backend_version": "0.3", "language": "vscore/0.3",
             "semantics": "vscore-semantics/0.3", "profile": "data-pipeline/0.3", "endpoint": "restricted_source",
             "require_state": "END_TO_END_VERIFIED", "policy": "strict", "runtime_campaign_requested": False,
             "positive_candidate_arguments": [], "hidden_cases_loaded": False, "python_grader_invoked": False,
             "task_oracle_invoked": False, "independent_clean_builds": 2, "native_cli_required": True,
             "relay_mode": "file", "fork_turns": "none", "fresh_agent_per_request": True,
             "model_generation_deadline": None, "proof_search_deadline": None, "review_tier_deadline": None,
             "model_identity_attested": False, "input_tokens": None, "output_tokens": None}
    require(all(k in protocol and type(protocol[k]) is type(v) and protocol[k] == v for k, v in fixed.items()),
            "SCOPE_LEAK", "endpoint/domain/proof-input/no-campaign/timeout/identity policy changed")
    expected = [{**{k: row[k] for k in ("id", "kind", "role", "required")},
                 "source_spans": [{k: ref[k] for k in ("start_byte", "end_byte")} for ref in row["source_refs"]]}
                for row in metadata["records"]]
    original = reader.obj(COHORT / "requests/D21/original-metadata.json")
    identities = original["identities"]
    original_cohort = str(REPO / metadata["authority_path"].split("/artifacts/", 1)[0])
    require(original["original_cohort"] == original_cohort and
            hash_text(original["original_request_sha256"]) == PUBLIC_PROMPT_SHA and
            hash_text(original["metadata_hashes"]["artifacts/D21/verislop/package/draft.json"]) == metadata["authority_sha256"] and
            original["old_positive_candidate_bytes_read"] is False,
            "SOURCE_SPAN_MISMATCH", "original public metadata provenance differs")
    require(sorted(identities, key=lambda r: r["id"]) == sorted(expected, key=lambda r: r["id"]) and
            len(identities) == len(ORIGINAL_IDS) and all(row["required"] is True for row in identities),
            "OBLIGATION_DRIFT", "eleven original required identities/kinds/roles/spans differ")
    prompt = reader.raw(COHORT / "requests/D21/original-prompt.txt", PUBLIC_PROMPT_SHA, "exact original public prompt")
    revised = reader.raw(COHORT / "requests/D21/revised-prompt.txt", purpose="revised public delivery request")
    revision = reader.obj(COHORT / "requests/D21/delivery-revision.json")
    edits = revision["edits"]
    require(len(edits) == 3 and [(e["before"], e["after"]) for e in edits] == list(DELIVERY_EDITS),
            "REQUEST_DRIFT", "delivery edits exceed the fixed public revision")
    cursor = 0
    chunks = []
    for edit in edits:
        start, end = edit["original_start_byte"], edit["original_end_byte"]
        require(type(start) is int and type(end) is int and cursor <= start < end <= len(prompt) and
                prompt[start:end] == edit["before"].encode("utf-8"), "SOURCE_SPAN_MISMATCH", "delivery edit span differs")
        chunks.extend([prompt[cursor:start], edit["after"].encode("utf-8")])
        cursor = end
    chunks.append(prompt[cursor:])
    require(revised.startswith(b"".join(chunks)) and revision["functional_bytes_preserved"] is True and
            revision["old_delivery_assurance_relabelled"] is False,
            "REQUEST_DRIFT", "functional public bytes/domain/examples are not retained")
    recreated, mapping = bootstrap.revise_prompt(prompt, identities, operational_ids=("I1", "S1"))
    require(recreated == revised and mapping == revision, "REQUEST_DRIFT", "exact delivery-only mapping differs")
    policy = reader.obj(COHORT / "requests/D21/source-policy.json")
    expected_policy = {"schema_version": "0.1", "format": "verislop.required-source-facets/0.1",
                       "obligations": {name: {"file": "program.vscore.json", "entry": "solve", "arity": 1,
                                               "properties": SOURCE_PROPERTIES, "value_required": name not in ("I1", "S1")}
                                       for name in sorted(ORIGINAL_IDS) if name not in ("D1", "A1")}}
    require(policy == expected_policy and policy["obligations"]["O5"]["value_required"] is True,
            "FACET_MISMATCH", "exact Mixed O1-O7/source-only I1,S1 source policy differs")
    require(revision["source_policy_classification"] ==
            {"value_required_default": True, "source_only_operational_ids": ["I1", "S1"]},
            "FACET_MISMATCH", "causal I1 classification changed")
    # Full original causal/domain bytes remain in O5's functional request. Accepted
    # formal semantics are evaluated only by the later immutable AUD checks.
    actual = bootstrap.verify_inputs(COHORT)
    require(actual == protocol, "INPUT_MUTATION", "qualified bootstrap.verify_inputs result differs")
    require(prereg["protocol_sha256"] == canonical.digest_file(COHORT / "protocol.json") and
            all(prereg[k] == protocol[k] for k in ("source_root", "input_root", "request_set_root")),
            "INPUT_MUTATION", "exact preregistration roots differ")
    return protocol


def execute(reader, spec):
    validate_binding_schema(reader, spec)
    native_source = authenticate_native_driver(reader, spec)
    require(spec.get("format") == SPEC_FORMAT, "BINDING_INVALID", "wrong binding spec format")
    bind_current_root_metadata(reader, spec)
    require(path_text(spec["project"]) == PROJECT and path_text(spec["cohort"]) == COHORT and
            spec["stage"] == "tier2-source-facets-019", "WRONG_STAGE", "fresh exact stage019 paths are required")
    require(spec["authorization"] == "root-explicit-new-qualified-paths-before-generation" and
            spec["preregistration_input_root_hash"] == PLAN_ROOT,
            "BINDING_INVALID", "future root authorization or immutable plan root absent")
    reader.raw(Path(__file__).absolute(), spec["reader_sha256"], "root's exact frozen binding reader implementation")
    reader.raw(HERE / "pre-generation-binding-reader-schema-001.json", spec["reader_schema_sha256"], "frozen reader input schema")
    manifest, metadata = freeze_plan(reader)
    require(Path.cwd() == PROJECT, "WRONG_EXECUTION_ROOT", "reader must run in exact future project cwd")
    # Hash the new qualified source tree BEFORE importing its executable modules.
    prefreeze = reader.artifact(spec["source_freeze"], "root-authenticated pre-import source freeze")
    require(prefreeze["format"] == "verislop.tier2-engineering-source-freeze/0.1" and
            prefreeze["generation_started"] is False and prefreeze["source_root"] == spec["expected_source_root"] and
            source_map_digest(prefreeze["source_files"]) == prefreeze["source_root"],
            "INPUT_MUTATION", "pre-import qualified source root differs")
    for name, expected in sorted(prefreeze["source_files"].items()):
        relative = Path(name)
        require(not relative.is_absolute() and relative.as_posix() == name and ".." not in relative.parts,
                "INPUT_MUTATION", "invalid qualified source path")
        reader.raw(PROJECT / relative, expected, "exact qualified project bytes before import")
        reader.raw(REPO / relative, expected, "exact current generic workspace bytes before import")
    sys.dont_write_bytecode = True
    for name in tuple(sys.modules):
        require(not (name == "verislop" or name.startswith("verislop.") or
                     name == "synthetic_dataset" or name.startswith("synthetic_dataset.")),
                "WRONG_EXECUTION_ROOT", "bootstrap modules were imported before qualified-path selection")
    sys.path.insert(0, str(PROJECT))
    bootstrap = importlib.import_module("synthetic_dataset.tools.bootstrap_tier2")
    canonical = importlib.import_module("verislop.canonical")
    require(Path(bootstrap.__file__).resolve() == PROJECT / "synthetic_dataset/tools/bootstrap_tier2.py" and
            Path(canonical.__file__).resolve() == PROJECT / "verislop/canonical.py",
            "WRONG_EXECUTION_ROOT", "imports are not the exact qualified project copy")
    require(bootstrap.source_inventory(REPO) == prefreeze["source_files"],
            "INPUT_MUTATION", "complete current workspace generic inventory differs from qualified source freeze")
    report, engineering, frozen, receipts, schema_hash = qualification(reader, spec, canonical, bootstrap)
    independent = independent_qualification(reader, spec, report, canonical)
    protocol = public_preparation(reader, spec, bootstrap, canonical, metadata, frozen)
    require(canonical.digest_json(engineering) == protocol["input_files"]["engineering-validation.json"],
            "STALE_OR_UNBOUND_EVIDENCE", "cohort engineering record is not the exact newly qualified record")
    activation_binding = authenticate_activation_binding(reader, spec)
    controller_records = []
    for item in spec["controller_inputs"]:
        p = path_text(item["path"])
        require(p.is_relative_to(DRIVER_ROOT), "WRONG_STAGE", "controller public input escaped driver019")
        reader.raw(p, item["sha256"], "exact native019 public controller preregistration input")
        controller_records.append({"path": str(p), "sha256": item["sha256"]})
    require(bool(controller_records), "BINDING_INVALID", "native019 controller public input binding is absent")
    # Check bytes again to fail closed on an in-process mutation. No task artifacts
    # or historical packages are opened by this reader itself.
    for item in list(reader.reads):
        require(digest(Path(item["path"]).read_bytes()) == item["sha256"],
                "INPUT_MUTATION", f"input changed during binding: {item['path']}")
    return {"format": "verislop.d21-pre-generation-binding/1", "audit_id": AUDIT_ID,
            "binding_status": "PASS", "terminal_audit_status": None, "lifecycle_state_assigned": None,
            "preregistration_input_root_hash": PLAN_ROOT, "public_input_root_hash": manifest["public_input_root_hash"],
            "probe_object_canonical_sha256": PROBE_OBJECT_SHA, "qualification_report": spec["qualification_report"],
            "qualification_claim_ids": list(QUALIFICATION_IDS), "qualification_claim_status": "VERIFIED",
            "qualification_input_root": report["input_root"], "qualification_source_root": report["source_root"],
            "qualification_closure_id": report["closure_id"], "qualification_report_schema_sha256": schema_hash,
            "current_root_independent_admission": independent,
            "engineering_record": spec["engineering_record"], "source_freeze": spec["source_freeze"],
            "engineering_registered_required_claim_count": len(engineering["required_claim_observations"]),
            "engineering_validator": {"module": "synthetic_dataset.tools.bootstrap_tier2",
                                      "call": "verify_engineering_record(record: dict) -> None",
                                      "matched_entire_actual_registered_record": True,
                                      "project_copy": str(Path(bootstrap.__file__).resolve())},
            "engineering_native_chain": {key: engineering[key] for key in
                                         ("package", "package_files_root", "report_sha256", "mechanical_result",
                                          "mechanical_result_sha256", "closure_root", "closure_id")},
            "actual_qualification_process_receipts": receipts, "project": str(PROJECT), "cohort": str(COHORT),
            "protocol_sha256": spec["protocol_sha256"], "preregistration_sha256": spec["preregistration_sha256"],
            "project_snapshot_sha256": spec["project_snapshot_sha256"], "source_root": protocol["source_root"],
            "input_root": protocol["input_root"], "request_set_root": protocol["request_set_root"],
            "source_files": protocol["source_files"], "input_files": protocol["input_files"],
            "native_driver": spec["native_driver"], "native_source_package": native_source,
            "native_activation_prerequisites": activation_binding, "controller_inputs": controller_records,
            "bootstrap_verify_inputs": {"module": "synthetic_dataset.tools.bootstrap_tier2",
                                        "call": "verify_inputs(cohort: pathlib.Path) -> dict",
                                        "project_copy": str(Path(bootstrap.__file__).resolve()), "matched_protocol": True},
            "generation_started": False, "original_required_ids": list(ORIGINAL_IDS),
            "only_allowed_derived_id": "A1_nonvacuity", "identity": "UNATTESTED", "tokens": "unavailable",
            "optional_TESTED": "PENDING", "scope": "Tier2/restricted_source public pre-generation binding only",
            "task_artifact_reads": [], "pending_request_invocations": 0, "model_calls": 0,
            "task_builds": 0, "task_verifiers": 0, "public_probe_executions": 0,
            "next_action": "STOP; generation is a separate root decision; terminal audit waits for all authors/controller stopped"}


def publish_once(path, value):
    data = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding-spec", type=Path, required=True)
    parser.add_argument("--binding-spec-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    started_ns = time.monotonic_ns()
    reader = Reader()
    status, exit_code, error = "INFRASTRUCTURE_FAILURE", 2, None
    result = None
    try:
        spec = reader.obj(args.binding_spec.absolute(), args.binding_spec_sha256, "explicit root future execution binding spec")
        result = execute(reader, spec)
        status, exit_code = "PASS", 0
    except (Block, KeyError, IndexError, AttributeError, TypeError, ValueError) as exc:
        status, exit_code, error = "BLOCK", 1, f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        status, exit_code, error = "INFRASTRUCTURE_FAILURE", 2, f"{type(exc).__name__}: {exc}"
    output = args.output_dir.absolute()
    try:
        require(output.parent == HERE and not output.exists(), "BINDING_INVALID", "output must be a new direct child of stage019 audit directory")
        output.mkdir()
        receipt_value = {"format": "verislop.d21-binding-process-receipt/1", "audit_id": AUDIT_ID,
                         "argv": sys.argv, "cwd": str(Path.cwd()), "pid": os.getpid(),
                         "python": sys.executable, "python_version": sys.version,
                         "reader_path": str(Path(__file__).absolute()), "reader_sha256": digest(Path(__file__).read_bytes()),
                         "started_at_utc": started, "ended_at_utc": datetime.now(timezone.utc).isoformat(),
                         "elapsed_ns": time.monotonic_ns() - started_ns, "binding_status": status,
                         "actual_returncode": None, "intended_returncode": exit_code, "error": error,
                         "actual_completed_exit_authority": "root's independent subprocess receipt",
                         "root_independent_numeric_exit_receipt_required": True}
        publish_once(output / "process-receipt.json", receipt_value)
        publish_once(output / "read-ledger.json", {"format": "verislop.d21-binding-read-ledger/1",
                                                  "audit_id": AUDIT_ID, "reads": reader.reads,
                                                  "scope": "explicit reader reads; qualified bootstrap API internal reads belong to declared host/tooling trust"})
        if result is not None:
            publish_once(output / "binding.json", result)
        print(json.dumps({"binding_status": status, "intended_returncode": exit_code,
                          "output_dir": str(output), "error": error}, sort_keys=True))
    except Exception as exc:
        print(json.dumps({"binding_status": "INFRASTRUCTURE_FAILURE", "intended_returncode": 2,
                          "error": f"receipt publication failed: {type(exc).__name__}: {exc}"}, sort_keys=True))
        return 2
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
