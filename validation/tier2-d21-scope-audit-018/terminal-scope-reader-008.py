#!/usr/bin/env python3
"""Finite D21 stage018 terminal audit; registration preparation does not execute it.

The first task read requires explicit root terminal authorization and a complete
stopped-actor/sealed-inventory binding. Only the fresh stage018 run is authority.
This reader never calls an author, repairs a package, or assigns a lifecycle.
Its temporary verification builds are the qualified published-checker rebuild
route, expanded to retain the actual declaration AST and process observations.
Natural-language correspondence remains explicit interpretation trust, bound to
the finite original clauses and real accepted AST, separately from kernel facts.
"""
from __future__ import annotations

import argparse
import base64
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

HERE = Path(__file__).absolute().parent
REPO = HERE.parent.parent
PROJECT = REPO / "synthetic_dataset/bootstrap/stages/tier2-source-facets-018/project"
COHORT = PROJECT.parent / "run"
DRIVER = REPO / "validation/tier2-native-live-driver-018"
AUDIT_ID = "tier2-d21-scope-audit-018"
FORMAT = "verislop.d21-terminal-scope-binding/8"
PRE_FORMAT = "verislop.d21-retained-pre-route-authorization/8"
RETAINED_RECORD_FORMAT = "verislop.stage018-retained-validation/8"
PRE_SCHEMA_NAME = "retained-pre-route-authorization-schema-008.json"
FINAL_SCHEMA_NAME = "terminal-scope-reader-binding-schema-008.json"
SOURCE_ROOT = "sha256:d8a0820c0194b7ed864a7377218012aa4c9489e007a18d221ec80ec0696289a8"
QUALIFICATION_ROOT = "sha256:5fc3b19939b89a1923535fb59e6e75a5153cc227e04d21376f09f6ba80af5def"
HELPER_SHA = "5ebc62b212e202e29715079f664ddd198f7bbfd087906ebcdfddb86ce6957524"
PRE_BINDING = HERE / "pre-generation-actual-001/binding.json"
PRE_BINDING_SHA = "503aa3e32a9f950705672d5b59409c96ed096a2b157ae93730c91e791d485268"
PRE_RECEIPT = DRIVER / "pre-generation/binding-actual-process-receipt.json"
PRE_RECEIPT_SHA = "4cd8c71b9648860373d854580df4cf7aaaaec720c4ecbe968e05fcd54598f052"
QUAL_REPORT = REPO / "validation/tier2-support-018-qualification-002/final-reconciliation/report.json"
QUAL_REPORT_SHA = "4368d9182ad259381db3709feec09d5e5ecb56edf0d33dfd10404d745b6a48b7"
ENGINEERING = QUAL_REPORT.parent / "engineering-record.json"
ENGINEERING_SHA = "31ff343872f7603984b9b37780171aab7fe8cbc499b3f59c9fabdce10d8556d5"
INDEPENDENT_REPORT = REPO / "validation/tier2-support-018-independent-audit-002/actual-001/report.json"
INDEPENDENT_REPORT_SHA = "8024bebbc25196f864f01d4b3d95882f9e96f6186dec0cc2485192ef6835a189"
IDS = ("D1", "A1", "O1", "O2", "O3", "O4", "O5", "O6", "O7", "I1", "S1")
GUARANTEES = ("O1", "O2", "O3", "O4", "O5", "O6", "O7", "I1", "S1")
STATES = {"VERIFIED", "BLOCKED", "INFRASTRUCTURE_FAILURE"}
SPEC_NAME = "terminal-scope-reader-specification-008.json"
REG_NAME = "terminal-scope-reader-registration-008.json"
ROUTE_NAME = "retained-validation-route-008.py"
PYTHON = "/home/augustus/anaconda3/bin/python"
PRE_COMMON_FIELDS = ("authorization", "stage", "project", "cohort", "preregistration_input_root_hash",
                     "registered_files", "actor_stop", "cohort_seal", "orchestration_seal",
                     "generation_started_at_utc", "source_root", "qualification_input_root", "terminal_nonce")
PRE_FIELDS = {*PRE_COMMON_FIELDS, "format", "authorized_at_utc"}
SUBMIT_CODE = "import sys,json;from pathlib import Path;from synthetic_dataset.tools import bootstrap_tier2 as b;print(json.dumps(b.submit_response(Path(sys.argv[1]),json.loads(Path(sys.argv[2]).read_text())),sort_keys=True))"
FINAL_SCHEMA = PRE_SCHEMA = None
TRANSPORT_FIELD_REQUIREMENTS = {
    "required": ["format", "stage", "source_root", "controller_count", "requests"],
    "requests_required": ["request_id", "author_agent_id", "literal_final", "literal_final_origin", "submissions"],
    "literal_final_origin_required": ["record", "json_pointer"],
    "submission_required": ["envelope", "literal_final_pointer", "observed_exit_code", "process_evidence",
                            "metadata_only_correction", "changed_json_pointers"],
    "process_evidence_required": {"completed_process_receipt": ["kind", "record"],
                                  "tool_invocation_result": ["kind", "result"]},
    "process_evidence_optional": {"completed_process_receipt": [], "tool_invocation_result": ["invocation"]},
    "completed_process_required": ["returncode", "argv", "cwd", "timed_out", "envelope_path", "envelope_sha256"],
    "tool_submission_required": ["native_response_publication"],
    "tool_invocation_required": ["tool_name", "arguments"],
    "registered_tool_invocation_required": ["invocation_reference", "tool_result_reference", "exact_tool_invocation"],
    "tool_result_required": ["exit_code"],
}
METADATA_REQUIRED = {'aggregate': ['backend_version', 'complete', 'endpoint', 'excluded', 'format', 'fresh_agents', 'fresh_calls', 'hidden_cases_loaded', 'language', 'model_identity_attested', 'oracle_calls', 'original_python_assurance_relabelled', 'protocol_sha256', 'request_set_root', 'rows', 'selected_tasks', 'source_root', 'stage', 'status', 'tier', 'transport_errors', 'trust', 'verified_tasks'], 'native_audit': ['all_required_e2e', 'all_required_guarantees', 'builds', 'closure_root', 'determinism', 'issues', 'mechanical_claims', 'mechanical_result', 'mechanical_status', 'per_obligation_outcomes', 'release_status', 'required_e2e_passed', 'required_guarantees', 'required_non_vacuity_witnesses', 'required_obligations', 'status'], 'origin_audit': ['agents', 'issues', 'milestone_authority', 'missing_native_prompts', 'model_identity_attested', 'packages', 'provider_calls', 'responses', 'status', 'transport_errors'], 'pre_generation_binding': ['actual_qualification_process_receipts', 'audit_id', 'binding_status', 'bootstrap_verify_inputs', 'cohort', 'controller_inputs', 'engineering_native_chain', 'engineering_record', 'engineering_registered_required_claim_count', 'engineering_validator', 'format', 'generation_started', 'identity', 'input_files', 'input_root', 'lifecycle_state_assigned', 'model_calls', 'native_driver', 'next_action', 'only_allowed_derived_id', 'optional_TESTED', 'original_required_ids', 'pending_request_invocations', 'preregistration_input_root_hash', 'preregistration_sha256', 'probe_object_canonical_sha256', 'project', 'project_snapshot_sha256', 'protocol_sha256', 'public_input_root_hash', 'public_probe_executions', 'qualification_claim_ids', 'qualification_claim_status', 'qualification_closure_id', 'qualification_input_root', 'qualification_report', 'qualification_report_schema_sha256', 'qualification_source_root', 'request_set_root', 'scope', 'source_files', 'source_freeze', 'source_root', 'task_artifact_reads', 'task_builds', 'task_verifiers', 'terminal_audit_status', 'tokens'], 'preregistration': ['format', 'generation_started', 'input_root', 'protocol_sha256', 'request_set_root', 'source_root'], 'protocol': ['backend_version', 'carrier_format', 'configuration_sha256', 'contract_repair_rounds', 'endpoint', 'endpoint_profiles_path', 'endpoint_profiles_sha256', 'excluded', 'fork_turns', 'format', 'fresh_agent_per_request', 'generation_started', 'hidden_cases_loaded', 'independent_clean_builds', 'input_files', 'input_root', 'input_tokens', 'language', 'max_calls_per_instance', 'max_calls_per_task', 'model_generation_deadline', 'model_identity_attested', 'native_cli_required', 'output_tokens', 'pair_order', 'policy', 'positive_candidate_arguments', 'profile', 'project_path', 'proof_search_deadline', 'python_grader_invoked', 'relay_mode', 'request_set_root', 'requested_model', 'require_state', 'review_tier_deadline', 'runtime_campaign_requested', 'semantics', 'source_files', 'source_root', 'specifications', 'stage', 'target', 'task_oracle_invoked', 'task_order', 'tasks', 'tier', 'transport', 'trust'], 'protocol_task': ['id', 'metadata_path', 'original_request_sha256', 'revised_prompt_path', 'revised_request_ref', 'revised_request_sha256', 'revision_path', 'source_policy_classification', 'source_policy_path', 'source_policy_sha256'], 'task_result': ['arm', 'artifact_path', 'cli_diagnostics', 'cli_stages', 'cli_status', 'cli_stopped_at', 'delivery_revision', 'endpoint', 'format', 'hidden_cases_loaded', 'issues', 'language', 'mechanical_status', 'model_identity_attested', 'native', 'native_terminal_status', 'oracle_calls', 'origin_audit', 'original_request_sha256', 'package', 'primary_worker_error', 'python_runtime_campaign', 'release_status', 'request_set_root', 'revised_request_sha256', 'scope', 'source_policy_path', 'source_policy_sha256', 'source_root', 'startup_failure', 'status', 'strict_cli_success', 'successful_task', 'task', 'tier', 'usage', 'worker_exit_code', 'worker_outputs', 'worker_receipt']}
METADATA_FORMAT = "verislop.tier2-data-bootstrap/0.1"
SCHEMA_KEYWORDS = {"$schema", "title", "type", "required", "properties", "additionalProperties",
                   "const", "pattern", "format", "anyOf", "items"}


class Block(Exception):
    pass


def need(ok, code, message):
    if not ok:
        raise Block(code + ": " + message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def plain_hash(value):
    need(isinstance(value, str), "BINDING_INVALID", "hash is not text")
    out = value.removeprefix("sha256:")
    need(len(out) == 64 and all(c in "0123456789abcdef" for c in out), "BINDING_INVALID", "invalid SHA256")
    return out


def utc(value):
    need(isinstance(value, str), "BINDING_INVALID", "timestamp missing")
    return datetime.fromisoformat(value.replace(" UTC", "+00:00").replace("Z", "+00:00"))


def strict_path(value):
    p = Path(value)
    need(p.is_absolute() and p.resolve() == p and not p.is_symlink(), "INPUT_MUTATION", "indirect path: " + str(p))
    return p


def pointer(value, selector):
    need(isinstance(selector, str) and (selector == "" or selector.startswith("/")), "BINDING_INVALID", "invalid JSON pointer")
    for part in selector.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        try:
            value = value[int(part)] if isinstance(value, list) else value[part]
        except (KeyError, ValueError, IndexError, TypeError) as exc:
            raise Block("EVIDENCE_MISSING: " + selector) from exc
    return value


def duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        need(key not in obj, "BINDING_INVALID", "duplicate key " + key)
        obj[key] = value
    return obj


def schema_definition(schema):
    """Reject unsupported constraints; validate the entire registered dialect."""
    need(type(schema) is dict and set(schema) <= SCHEMA_KEYWORDS,
         "BINDING_INVALID", "unsupported or malformed registered binding schema")
    if "$schema" in schema:
        need(schema["$schema"] == "https://json-schema.org/draft/2020-12/schema",
             "BINDING_INVALID", "unregistered schema dialect")
    if "title" in schema:
        need(type(schema["title"]) is str, "BINDING_INVALID", "schema title type")
    if "type" in schema:
        need(type(schema["type"]) is str and schema["type"] in {"object", "array", "string", "null"},
             "BINDING_INVALID", "unsupported schema type")
    if "required" in schema:
        required = schema["required"]
        need(type(required) is list and all(type(k) is str for k in required) and len(set(required)) == len(required),
             "BINDING_INVALID", "malformed schema required keys")
    if "additionalProperties" in schema:
        need(type(schema["additionalProperties"]) is bool, "BINDING_INVALID", "unsupported additionalProperties schema")
    if "properties" in schema:
        need(type(schema["properties"]) is dict and all(type(k) is str for k in schema["properties"]),
             "BINDING_INVALID", "malformed schema properties")
        for child in schema["properties"].values():
            schema_definition(child)
    if "pattern" in schema:
        need(type(schema["pattern"]) is str, "BINDING_INVALID", "malformed schema pattern")
        try:
            re.compile(schema["pattern"])
        except re.error as exc:
            raise Block("BINDING_INVALID: malformed schema pattern") from exc
    if "format" in schema:
        need(schema["format"] == "date-time", "BINDING_INVALID", "unsupported schema format")
    if "anyOf" in schema:
        need(type(schema["anyOf"]) is list and bool(schema["anyOf"]), "BINDING_INVALID", "malformed schema alternatives")
        for child in schema["anyOf"]:
            schema_definition(child)
    if "items" in schema:
        schema_definition(schema["items"])


def validate_schema(value, schema, location="binding"):
    """Implement every constraint in the finite registered final/pre schemas."""
    expected_type = schema.get("type")
    if expected_type is not None:
        good = {"object":type(value) is dict, "array":type(value) is list,
                "string":type(value) is str, "null":value is None}[expected_type]
        need(good, "BINDING_INVALID", location + " type differs")
    if "const" in schema:
        need(type(value) is type(schema["const"]) and value == schema["const"],
             "BINDING_INVALID", location + " registered constant differs")
    if "anyOf" in schema:
        accepted = False
        for alternative in schema["anyOf"]:
            try:
                validate_schema(value, alternative, location)
                accepted = True
                break
            except Block:
                pass
        need(accepted, "BINDING_INVALID", location + " does not match any registered alternative")
    if type(value) is dict:
        need(all(k in value for k in schema.get("required", [])), "BINDING_INVALID", location + " required key missing")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            need(set(value) <= set(properties), "HASH_CYCLE_OR_UNREGISTERED_INPUT", location + " unregistered nested key")
        for key in set(value) & set(properties):
            validate_schema(value[key], properties[key], location + "/" + key)
    if type(value) is list and "items" in schema:
        for index, child in enumerate(value):
            validate_schema(child, schema["items"], location + "/" + str(index))
    if type(value) is str and "pattern" in schema:
        pattern = schema["pattern"]
        match = re.fullmatch(pattern, value) if pattern.startswith("^") and pattern.endswith("$") else re.search(pattern, value)
        need(match is not None, "BINDING_INVALID", location + " pattern differs")
    if type(value) is str and "format" in schema:
        need(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})", value) is not None,
             "BINDING_INVALID", location + " requires timezone-aware RFC3339 date-time")
        try:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            need(stamp.tzinfo is not None and stamp.utcoffset() is not None,
                 "BINDING_INVALID", location + " timestamp has no timezone")
        except ValueError as exc:
            raise Block("BINDING_INVALID: invalid date-time " + location) from exc
    return value


def install_binding_schemas(final, pre):
    global FINAL_SCHEMA, PRE_SCHEMA
    schema_definition(final)
    schema_definition(pre)
    need(set(pre.get("required", [])) == PRE_FIELDS and
         set(final.get("required", [])) == {*PRE_COMMON_FIELDS, "format", "transport_trace", "scope_interpretation",
             "retained_validations", "public_probe_observations", "pre_route_authorization", "terminal_authorized_at_utc"},
         "BINDING_INVALID", "registered final/pre schema membership differs")
    FINAL_SCHEMA, PRE_SCHEMA = final, pre


def ref_identity(record):
    need(type(record) is dict and set(record) == {"path", "sha256"} and type(record["path"]) is str and record["path"].startswith("/"),
         "HASH_CYCLE_OR_UNREGISTERED_INPUT", "reference is not a closed absolute path/hash object")
    return record["path"], plain_hash(record["sha256"])


def same_ref(first, second):
    return ref_identity(first) == ref_identity(second)


def registered_identity(record):
    need(type(record) is dict and set(record) == {"terminal-scope-reader-008.py", SPEC_NAME, REG_NAME, ROUTE_NAME},
         "VERIFIER_MISMATCH", "registered verifier map keys differ")
    return {key:plain_hash(value) for key, value in record.items()}


def retained_process_argv_identity(argv):
    need(type(argv) is list and all(type(v) is str for v in argv) and
         argv.count("--pre-route-authorization-sha256") == 1,
         "VERIFIER_MISMATCH", "actual retained argv lacks the unique registered authorization SHA flag")
    normalized = list(argv)
    index = normalized.index("--pre-route-authorization-sha256") + 1
    need(index < len(normalized), "VERIFIER_MISMATCH", "retained authorization digest argument missing")
    normalized[index] = "sha256:" + plain_hash(normalized[index])
    return normalized


def qualification_definition(specification):
    # This authorization chain is ROOT002; owned reader version changes never
    # rename qualification artifacts or transfer authority from another root.
    authorized = {
        "root002_report": {"path":str(REPO / "validation/tier2-support-018-qualification-002/final-reconciliation/report.json"),
                           "sha256":"4368d9182ad259381db3709feec09d5e5ecb56edf0d33dfd10404d745b6a48b7"},
        "engineering_record": {"path":str(REPO / "validation/tier2-support-018-qualification-002/final-reconciliation/engineering-record.json"),
                               "sha256":"31ff343872f7603984b9b37780171aab7fe8cbc499b3f59c9fabdce10d8556d5"},
        "independent_report": {"path":str(REPO / "validation/tier2-support-018-independent-audit-002/actual-001/report.json"),
                               "sha256":"8024bebbc25196f864f01d4b3d95882f9e96f6186dec0cc2485192ef6835a189"}}
    constants = {"root002_report":{"path":str(QUAL_REPORT), "sha256":QUAL_REPORT_SHA},
                 "engineering_record":{"path":str(ENGINEERING), "sha256":ENGINEERING_SHA},
                 "independent_report":{"path":str(INDEPENDENT_REPORT), "sha256":INDEPENDENT_REPORT_SHA}}
    need(specification.get("current_source_root") == SOURCE_ROOT and
         specification.get("current_qualification_input_root") == QUALIFICATION_ROOT,
         "STALE_OR_UNBOUND_EVIDENCE", "registered qualified source/input constants differ")
    for key, reference in authorized.items():
        need(same_ref(constants[key], reference) and same_ref(specification["qualification"][key], reference),
             "STALE_OR_UNBOUND_EVIDENCE", "ROOT002 registered path/hash authority differs: " + key)
    return authorized


def validate_pre_route(pre):
    """A closed frozen-input authority; no future outputs can enter its hash."""
    need(PRE_SCHEMA is not None, "VERIFIER_MISMATCH", "registered pre-route schema has not been authenticated")
    validate_schema(pre, PRE_SCHEMA, "pre-route")
    need(isinstance(pre, dict) and set(pre) == PRE_FIELDS and pre.get("format") == PRE_FORMAT,
         "HASH_CYCLE_OR_UNREGISTERED_INPUT", "pre-route authority is not the closed frozen-input schema")
    need(pre["authorization"] == "root-explicit-terminal-after-all-authors-controller-stopped" and
         pre["stage"] == "tier2-source-facets-018" and pre["project"] == str(PROJECT) and pre["cohort"] == str(COHORT) and
         pre["source_root"] == SOURCE_ROOT and pre["qualification_input_root"] == QUALIFICATION_ROOT and
         pre["preregistration_input_root_hash"] == "a8febb88f2615e49738194d1380f7441ab42e5bd808adc40bd20fbb57bbb7366",
         "STALE_OR_UNBOUND_EVIDENCE", "pre-route current source/qualification/public/stage roots differ")
    need(isinstance(pre["terminal_nonce"], str) and pre["terminal_nonce"] == plain_hash(pre["terminal_nonce"]),
         "BINDING_INVALID", "current terminal nonce must be64 lowercase hex characters")
    need(set(pre["registered_files"]) == {"terminal-scope-reader-008.py",SPEC_NAME,REG_NAME,ROUTE_NAME},
         "VERIFIER_MISMATCH", "pre-route registered verifier identities differ")
    need(utc(pre["generation_started_at_utc"]) <= utc(pre["authorized_at_utc"]) <= datetime.now(timezone.utc),
         "STALE_OR_UNBOUND_EVIDENCE", "pre-route authorization chronology is invalid")
    return pre


def authenticate_pre_route(final, pre):
    need(FINAL_SCHEMA is not None, "VERIFIER_MISMATCH", "registered final schema has not been authenticated")
    validate_schema(final, FINAL_SCHEMA, "final")
    validate_pre_route(pre)
    references = {"actor_stop", "cohort_seal", "orchestration_seal"}
    need(final.get("format") == FORMAT and all(
         same_ref(final[field], pre[field]) if field in references else
         registered_identity(final[field]) == registered_identity(pre[field]) if field == "registered_files" else
         final[field] == pre[field] for field in PRE_COMMON_FIELDS),
         "STALE_OR_UNBOUND_EVIDENCE", "final/pre-route common roots/actors/seals/verifiers/current nonce differ")
    need(utc(pre["authorized_at_utc"]) <= utc(final["terminal_authorized_at_utc"]) <= datetime.now(timezone.utc),
         "STALE_OR_UNBOUND_EVIDENCE", "final authorization predates pre-route authority or is in the future")
    return pre


def authenticate_route_interval(process, pre, final):
    authenticate_pre_route(final,pre)
    need(utc(pre["authorized_at_utc"]) <= utc(process["started_at_utc"]) <= utc(process["ended_at_utc"]) <= utc(final["terminal_authorized_at_utc"]),
         "STALE_OR_UNBOUND_EVIDENCE", "actual route interval is outside pre-route/final authorization chronology")


def authenticate_transport_correction(prior, envelope, attempt):
    need(type(prior) is dict and type(envelope) is dict, "STALE_OR_UNBOUND_EVIDENCE", "metadata correction lacks its actual prior envelope")
    allowed = ("/transport", "/relay_mode")
    changed_keys = {key for key in set(prior) | set(envelope) if
                    key not in prior or key not in envelope or prior[key] != envelope[key]}
    need(bool(changed_keys) and changed_keys <= {"transport", "relay_mode"},
         "STALE_OR_UNBOUND_EVIDENCE", "metadata correction changed no field or a non-transport field")
    actual = [selector for selector in allowed if selector[1:] in changed_keys]
    need(attempt.get("changed_json_pointers") == actual and envelope.get("transport") == "collaboration" and
         envelope.get("relay_mode") == "file",
         "STALE_OR_UNBOUND_EVIDENCE", "claimed correction differs from exact allowed actual diff/frozen values")
    return {"actual_changed_json_pointers":actual,"every_other_field_unchanged":True}


def authenticate_transport_transition(prior, envelope, attempt):
    need(type(attempt.get("metadata_only_correction")) is bool,
         "STALE_OR_UNBOUND_EVIDENCE", "transport correction flag is not boolean")
    if prior is None or (prior == envelope and attempt["metadata_only_correction"] is False):
        need(attempt["metadata_only_correction"] is False and attempt.get("changed_json_pointers") == [],
             "STALE_OR_UNBOUND_EVIDENCE", "initial/unchanged submission claims a fictitious metadata correction")
        return {"actual_changed_json_pointers":[],"initial_submission":prior is None}
    need(attempt["metadata_only_correction"] is True,
         "STALE_OR_UNBOUND_EVIDENCE", "actual submission diff cannot be hidden by an unset correction flag")
    return authenticate_transport_correction(prior,envelope,attempt)


def authenticate_literal_final_origin(original, raw, selector):
    need(type(original) is dict and set(original) == {"format", "text"} and
         original["format"] == "verislop.literal-final/1" and selector == "/text" and type(original["text"]) is str,
         "STALE_OR_UNBOUND_EVIDENCE", "literal FINAL origin lacks exact controller JSON/text identity")
    need(original["text"].encode("utf-8", errors="strict") == raw,
         "STALE_OR_UNBOUND_EVIDENCE", "raw literal FINAL copy differs from exact original controller text")
    return raw


def transport_field_identity(policy, registered_policy=None):
    """The normative lists are authenticated inputs, not ignored annotations."""
    need(type(policy) is dict and all(policy.get(key) == value for key, value in TRANSPORT_FIELD_REQUIREMENTS.items()),
         "VERIFIER_MISMATCH", "SOURCE/SPEC transport field lists differ")
    if registered_policy is not None:
        need(type(registered_policy) is dict and registered_policy == policy,
             "VERIFIER_MISMATCH", "SPEC/registration transport representation differs")
    return TRANSPORT_FIELD_REQUIREMENTS


def transport_required(value, fields, location):
    need(type(value) is dict and set(fields) <= set(value),
         "STALE_OR_UNBOUND_EVIDENCE", location + " lacks registered mandatory fields")


def validate_transport_structure(trace, policy):
    """Admission of an honest missing-evidence row never authenticates it."""
    fields = transport_field_identity(policy)
    transport_required(trace, fields["required"], "transport trace")
    need(type(trace["requests"]) is list and bool(trace["requests"]),
         "STALE_OR_UNBOUND_EVIDENCE", "transport trace request inventory is not a nonempty list")
    for row in trace["requests"]:
        transport_required(row, fields["requests_required"], "transport request")
        need(type(row["request_id"]) is str and type(row["author_agent_id"]) is str,
             "STALE_OR_UNBOUND_EVIDENCE", "transport request/author identity type differs")
        ref_identity(row["literal_final"])
        origin = row["literal_final_origin"]
        transport_required(origin, fields["literal_final_origin_required"], "literal FINAL origin")
        need(set(origin) == set(fields["literal_final_origin_required"]) and origin["json_pointer"] == "/text",
             "STALE_OR_UNBOUND_EVIDENCE", "literal FINAL origin shape/pointer differs")
        ref_identity(origin["record"])
        need(type(row["submissions"]) is list and bool(row["submissions"]),
             "STALE_OR_UNBOUND_EVIDENCE", "transport submission inventory is not a nonempty list")
        for attempt in row["submissions"]:
            transport_required(attempt, fields["submission_required"], "transport submission")
            ref_identity(attempt["envelope"])
            need(type(attempt["literal_final_pointer"]) is str and attempt["literal_final_pointer"].startswith("/") and
                 type(attempt["observed_exit_code"]) is int and type(attempt["metadata_only_correction"]) is bool and
                 type(attempt["changed_json_pointers"]) is list and all(type(v) is str for v in attempt["changed_json_pointers"]),
                 "STALE_OR_UNBOUND_EVIDENCE", "transport submission field types differ")
            evidence = attempt["process_evidence"]
            need(type(evidence) is dict and evidence.get("kind") in fields["process_evidence_required"],
                 "UNRESOLVED_TRANSPORT_PROCESS_IDENTITY", "unknown actual submission evidence alternative")
            kind = evidence["kind"]
            required = fields["process_evidence_required"][kind]
            optional = fields["process_evidence_optional"][kind]
            transport_required(evidence, required, "submission evidence")
            need(set(evidence) <= set(required + optional),
                 "UNRESOLVED_TRANSPORT_PROCESS_IDENTITY", "submission evidence mixes unregistered representation fields")
            if kind == "completed_process_receipt":
                ref_identity(evidence["record"])
            else:
                ref_identity(evidence["result"])
                if evidence.get("invocation") is not None:
                    ref_identity(evidence["invocation"])
                transport_required(attempt, fields["tool_submission_required"], "rejected tool submission")
                need(type(attempt["native_response_publication"]) is bool,
                     "UNRESOLVED_TRANSPORT_PROCESS_IDENTITY", "tool publication observation is not boolean")
    return trace


def metadata_field_identity(policy, registered, inventory):
    need(type(policy) is dict and type(registered) is dict and registered == policy and
         policy.get("required_keys") == METADATA_REQUIRED and type(inventory) is dict and
         inventory.get("required_keys") == METADATA_REQUIRED and inventory.get("source_root") == SOURCE_ROOT and
         policy.get("frozen_producer_constructors") == inventory.get("registered_producer_constructors"),
         "METADATA_INTERFACE_MISMATCH", "SOURCE/SPEC/registration/frozen producer metadata inventories differ")
    return METADATA_REQUIRED


def metadata_record(interface, value):
    need(interface in METADATA_REQUIRED and type(value) is dict and set(value) == set(METADATA_REQUIRED[interface]),
         "METADATA_INTERFACE_MISMATCH", "missing/mixed metadata fields for " + interface)
    return value


def validate_protocol_metadata(protocol, pre):
    metadata_record("protocol", protocol)
    need(type(protocol["tasks"]) is list and bool(protocol["tasks"]),
         "METADATA_INTERFACE_MISMATCH", "protocol task metadata is not a nonempty list")
    for task in protocol["tasks"]:
        metadata_record("protocol_task", task)
    need(protocol["format"] == METADATA_FORMAT and protocol["source_root"] == SOURCE_ROOT and
         protocol["input_root"] == pre["input_root"] and protocol["request_set_root"] == pre["request_set_root"] and
         protocol["stage"] == "tier2-source-facets-018" and [task["id"] for task in protocol["tasks"]] == ["D21"] and
         all(protocol[field] is False for field in ("hidden_cases_loaded", "task_oracle_invoked",
                                                    "python_grader_invoked", "runtime_campaign_requested")),
         "SCOPE_LEAK", "original domain/protocol/task inventory or no-oracle/no-python/no-runtime constraints differ")
    return protocol


def validate_task_result_metadata(result):
    metadata_record("task_result", result)
    metadata_record("native_audit", result["native"])
    metadata_record("origin_audit", result["origin_audit"])
    need(result["format"] == METADATA_FORMAT and result["task"] == "D21" and result["arm"] == "verislop" and
         result["source_root"] == SOURCE_ROOT and result["endpoint"] == "restricted_source" and
         type(result["tier"]) is int and result["tier"] == 2 and result["hidden_cases_loaded"] is False and
         type(result["oracle_calls"]) is int and result["oracle_calls"] == 0 and
         result["python_runtime_campaign"] is False and result["model_identity_attested"] is False,
         "SCOPE_LEAK", "per-task no-oracle/no-runtime/source endpoint assurance differs")
    return result


def validate_aggregate_metadata(aggregate):
    # The current audit consumes task_result. This separate registered shape is
    # exercised only by unrelated controls, never used as a task-row substitute.
    metadata_record("aggregate", aggregate)
    need(type(aggregate["rows"]) is list and bool(aggregate["rows"]),
         "METADATA_INTERFACE_MISMATCH", "aggregate has no actual task-row metadata")
    for row in aggregate["rows"]:
        validate_task_result_metadata(row)
    need(aggregate["format"] == METADATA_FORMAT and aggregate["source_root"] == SOURCE_ROOT and
         aggregate["endpoint"] == "restricted_source" and type(aggregate["tier"]) is int and aggregate["tier"] == 2 and
         type(aggregate["oracle_calls"]) is int and aggregate["oracle_calls"] == 0 and
         aggregate["hidden_cases_loaded"] is False and aggregate["model_identity_attested"] is False and
         aggregate["original_python_assurance_relabelled"] is False,
         "SCOPE_LEAK", "aggregate assurance differs; missing row runtime field cannot default false")
    return aggregate


def authenticate_transport_evidence(attempt, result, invocation=None, registered=None):
    """Actual tool exit_code is never promoted to a fabricated process record."""
    expected = attempt.get("observed_exit_code")
    need(type(expected) is int, "STALE_OR_UNBOUND_EVIDENCE", "submission lacks actual numeric observed exit code")
    evidence = attempt.get("process_evidence", {})
    if evidence.get("kind") == "completed_process_receipt":
        transport_required(result, TRANSPORT_FIELD_REQUIREMENTS["completed_process_required"], "actual completed process receipt")
        need(type(result) is dict and type(result.get("returncode")) is int and result["returncode"] == expected and
             result.get("argv") == [PYTHON, "-c", SUBMIT_CODE, str(COHORT), attempt["envelope"]["path"]] and
             result.get("cwd") == str(PROJECT) and result.get("timed_out") is False and
             result.get("envelope_path") == attempt["envelope"]["path"] and
             plain_hash(result.get("envelope_sha256")) == plain_hash(attempt["envelope"]["sha256"]),
             "STALE_OR_UNBOUND_EVIDENCE", "completed native submission process identity/actual numeric result differs")
        return {"representation":"completed_process_receipt","actual_process_returncode":result["returncode"],
                "actual_process_receipt":result}
    need(evidence.get("kind") == "tool_invocation_result", "UNRESOLVED_TRANSPORT_PROCESS_IDENTITY", "unregistered submission evidence representation")
    need(type(invocation) is dict and type(registered) is dict,
         "UNRESOLVED_TRANSPORT_PROCESS_IDENTITY", "exact archived rejected tool invocation/registration is absent")
    transport_required(invocation, TRANSPORT_FIELD_REQUIREMENTS["tool_invocation_required"], "archived rejected tool invocation")
    transport_required(registered, TRANSPORT_FIELD_REQUIREMENTS["registered_tool_invocation_required"], "registered rejected tool identity")
    need(set(registered) == {"invocation_reference", "tool_result_reference", "exact_tool_invocation"} and
         same_ref(evidence.get("invocation"), registered["invocation_reference"]) and
         same_ref(evidence.get("result"), registered["tool_result_reference"]) and
         invocation == registered["exact_tool_invocation"] and
         invocation.get("tool_name") == "functions.exec/tools.exec_command" and type(invocation.get("arguments")) is dict,
         "UNRESOLVED_TRANSPORT_PROCESS_IDENTITY", "archived rejected invocation is not the exact prospectively registered tool call")
    transport_required(result, TRANSPORT_FIELD_REQUIREMENTS["tool_result_required"], "original rejected tool result")
    need(type(result) is dict and type(result.get("exit_code")) is int and result["exit_code"] == expected and expected != 0 and
         attempt.get("native_response_publication") is False,
         "UNRESOLVED_TRANSPORT_PROCESS_IDENTITY", "tool result is not an actual rejected numeric result before publication")
    need(not ({"argv", "pid", "returncode", "started_at_utc", "ended_at_utc", "timed_out"} & set(result)),
         "UNRESOLVED_TRANSPORT_PROCESS_IDENTITY", "tool result mixes fabricated process facts into its evidence representation")
    return {"representation":"tool_invocation_result","observed_tool_exit_code":result["exit_code"],
            "exact_tool_invocation":invocation,"actual_tool_result":result,
            "actual_process_returncode":None,"actual_process_argv":None,"actual_process_pid":None,
            "process_runtime_facts":None}


class Reads:
    def __init__(self):
        self.rows = []
        self.busy = False
        self.enable_hook = False
        self.first = {}
        self.mutations = []
        self.finalized = False
        self.temporary_roots = {}
        self.verification_sources = set()
        self.archive_root = None
        self.open_aliases = {}
        self.temporary_creator_code = None

    def _bound(self, p, data, purpose):
        digest = "sha256:" + sha(data)
        key = str(p)
        row = {"path": key, "sha256": digest, "size_bytes": len(data), "purpose": purpose,
               "lifetime": "bound", "first_read_sha256": self.first.get(key, digest)}
        self.rows.append(row)
        if key in self.first and self.first[key] != digest:
            self.mutations.append({"path": key, "first": self.first[key], "later": digest})
            raise Block("INPUT_MUTATION: a previously read path changed: " + key)
        self.first.setdefault(key, digest)

    def _observe(self, p, data, purpose, *, force_bound=False):
        # A pre-existing bound input can never become a generated temporary.
        roots = [root for root in self.temporary_roots if p.is_relative_to(root)]
        if force_bound or not roots or str(p) in self.first:
            self._bound(p, data, purpose)
            return
        need(self.archive_root is not None, "EVIDENCE_MISSING", "temporary-read archive is unavailable")
        root = max(roots, key=lambda value: len(str(value)))
        index = sum(row.get("lifetime") == "ephemeral" for row in self.rows)
        archive = self.archive_root / f"{index:08d}-{sha(data)}.bin"
        archive.parent.mkdir(parents=True, exist_ok=True)
        with archive.open("xb") as f:
            f.write(data)
        self.rows.append({"path": str(p), "sha256": "sha256:" + sha(data), "size_bytes": len(data),
                          "purpose": purpose, "lifetime": "ephemeral", "archive_path": str(archive),
                          "temporary_creation": self.temporary_roots[root]})
        self._bound(archive, data, "lossless archive of an actual generated verification read")

    def raw(self, path, expected=None, purpose="terminal bound input"):
        need(not self.finalized, "INPUT_MUTATION", "a bound read was attempted after completion freeze")
        p = strict_path(str(path))
        need(p.is_file(), "EVIDENCE_MISSING", str(p))
        self.busy = True
        try:
            data = p.read_bytes()
        finally:
            self.busy = False
        self.busy = True
        try:
            self._observe(p, data, purpose, force_bound=True)
        finally:
            self.busy = False
        if expected is not None:
            if sha(data) != plain_hash(expected):
                self.mutations.append({"path":str(p), "expected":expected, "actual":"sha256:"+sha(data)})
                raise Block("INPUT_MUTATION: expected digest differs: " + str(p))
        return data

    def finalize(self):
        self.enable_hook = False
        # Reopen every first-read bound input independently, including external
        # references and archive copies. No sealed-root whitelist can omit one.
        initial = dict(self.first)
        failures = []
        for opened, actual in self.open_aliases.items():
            if str(Path(opened).resolve()) != actual:
                failures.append("verifier input path alias changed: " + opened)
        for path, digest in sorted(initial.items()):
            try:
                self.raw(path, digest, "independent final reread of every first-read bound file")
            except Exception as exc:
                failures.append(type(exc).__name__ + ": " + str(exc))
        if self.first != initial:
            failures.append("completion unexpectedly added an input")
        self.finalized = True
        self.final_summary = {"bound_file_count":len(initial), "first_read_file_hashes":initial,
                "ephemeral_read_count":sum(r.get("lifetime") == "ephemeral" for r in self.rows),
                "temporary_roots":list(self.temporary_roots.values()),"mutations":self.mutations,"final_failures":failures}
        need(not failures and not self.mutations, "INPUT_MUTATION", "bound completion check failed: " + str(failures or self.mutations))
        return self.final_summary

    def obj(self, path, expected=None, purpose="terminal bound JSON input"):
        try:
            return json.loads(self.raw(path, expected, purpose), object_pairs_hook=duplicate_keys)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise Block("BINDING_INVALID: malformed JSON " + str(path)) from exc

    def artifact(self, record, purpose):
        need(isinstance(record, dict) and {"path", "sha256"} <= set(record), "BINDING_INVALID", purpose)
        return self.obj(record["path"], record["sha256"], purpose)

    def hook(self, event, args):
        # Observe verifier Python reads without monkeypatching registered code.
        # Native subprocess inputs/outputs are separately retained in actual
        # compiler receipts and complete module inventories, not invented here.
        if not self.enable_hook or self.busy:
            return
        if event == "tempfile.mkdtemp" and args:
            root = Path(os.fsdecode(args[0])).absolute()
            # Observe actual creation in registered production source. Merely
            # living in /tmp, or having a familiar prefix, grants no exemption.
            frame, callers, actual_creator = sys._getframe(1), [], False
            while frame is not None:
                name = str(Path(frame.f_code.co_filename).absolute())
                actual_creator = actual_creator or frame.f_code is self.temporary_creator_code
                if name in self.verification_sources or name == str(HERE / "terminal-scope-reader-008.py"):
                    callers.append({"path":name,"function":frame.f_code.co_name})
                frame = frame.f_back
            if actual_creator and not root.exists() and not root.is_relative_to(REPO) and any(c["path"] == str(PROJECT / "verislop/fsutil.py") and
                                         c["function"] == "temporary_directory" for c in callers):
                need(not any(Path(path).is_relative_to(root) for path in self.first),
                     "INPUT_MUTATION", "a bound input was reclassified as temporary")
                self.temporary_roots[root] = {"root":str(root),"event":"tempfile.mkdtemp",
                    "registered_callers":callers,"created_at_utc":datetime.now(timezone.utc).isoformat(),
                    "provenance":"new verification temporary; never original or retained authority"}
            return
        if event != "open" or not args or not isinstance(args[0], (str, bytes)):
            return
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else 0
        if isinstance(mode, str) and any(c in mode for c in "wax+"):
            return
        if isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
            return
        self.busy = True
        try:
            opened = Path(os.fsdecode(args[0])).absolute()
            p = opened.resolve()
            if p.is_file():
                if not any(opened.is_relative_to(root) for root in self.temporary_roots):
                    old = self.open_aliases.setdefault(str(opened), str(p))
                    if old != str(p):
                        self.mutations.append({"opened_path":str(opened),"first_target":old,"later_target":str(p)})
                        raise Block("INPUT_MUTATION: a verifier input alias changed: " + str(opened))
                data = p.read_bytes()
                self._observe(p, data, "actual qualified-verifier Python read")
        finally:
            self.busy = False


def publish(path, value):
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    with path.open("xb") as f:
        f.write(data)
    return "sha256:" + sha(data)


def inventory(reads, root, purpose):
    root = strict_path(str(root))
    rows = {}
    for p in sorted(root.rglob("*")):
        need(not p.is_symlink(), "INPUT_MUTATION", "symlink in sealed inventory: " + str(p))
        if p.is_file():
            data = reads.raw(p, purpose=purpose)
            rows[p.relative_to(root).as_posix()] = {"sha256": "sha256:" + sha(data), "size_bytes": len(data)}
    return rows


def compile_record(envelope, *, accepted, name):
    """Unwrap the qualified compile_process_details shape, retaining failures."""
    need(isinstance(envelope, dict) and set(envelope) == {"availability", "record"} and
         envelope["availability"] == "available" and isinstance(envelope["record"], dict),
         "EVIDENCE_MISSING", "actual compiler process is unavailable: " + name)
    record = envelope["record"]
    need(record.get("format") == "verislop.lean-compile-process/1" and
         type(record.get("returncode")) is int and type(record.get("timed_out")) is bool and
         isinstance(record.get("requested_argv"), list) and bool(record["requested_argv"]) and
         isinstance(record.get("launcher_argv"), list) and bool(record["launcher_argv"]) and
         all(isinstance(v, str) and bool(v) for v in record["requested_argv"] + record["launcher_argv"]) and
         isinstance(record.get("working_directory"), str) and bool(record["working_directory"]),
         "EVIDENCE_MISSING", "actual compiler invocation is incomplete: " + name)
    if accepted:
        need(record["returncode"] == 0 and record["timed_out"] is False,
             "CLEAN_BUILD_FAILURE", "an accepted compilation failed: " + name)
    for stream in ("stdout", "stderr"):
        value = record.get(stream)
        need(isinstance(value, dict) and type(value.get("byte_count")) is int and value["byte_count"] >= 0,
             "EVIDENCE_MISSING", "compiler lossless log is missing: " + name)
        log = base64.b64decode(value["content_b64"], validate=True)
        need(len(log) == value["byte_count"] and sha(log) == plain_hash(value["sha256"]),
             "INPUT_MUTATION", "compiler lossless log digest differs: " + name)
    return {"availability":envelope["availability"], "record":record,
            "role":"accepted_compile" if accepted else "documented_optional_or_control_attempt"}


def documented_envelopes(value):
    """Find exact process receipts within already authenticated diagnostics."""
    if isinstance(value, dict):
        if set(value) == {"availability", "record"}:
            yield sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
        for child in value.values():
            yield from documented_envelopes(child)
    elif isinstance(value, list):
        for child in value:
            yield from documented_envelopes(child)


def public_probe_row(probe, row):
    need(row["id"] == probe["id"] and row["input"] == probe["input"] and
         row["expected_output"] == probe["expected_output"] and
         row["status"] in {"OBSERVED", "UNSUPPORTED", "ABSENT"},
         "PROBE_BYTE_MUTATION", "optional input/expected_output/status changed")
    if row["status"] == "OBSERVED":
        need(row["output"] == probe["expected_output"], "CONCRETE_COUNTEREXAMPLE",
             "frozen public output mismatch: " + probe["id"])


def retained_argv(mode, pre_route_path, pre_route_sha, record, output_file):
    return [PYTHON, str(HERE / ROUTE_NAME), "--mode", mode,
            "--pre-route-authorization", pre_route_path, "--pre-route-authorization-sha256", pre_route_sha,
            "--retained-root", record["retained_root"], "--original-root", record["original_root"],
            "--closure-root", record["closure_root"], "--claim-id", record["claim_id"],
            "--output-file", output_file]


def authenticate_retained_process(process, result, *, mode, expected_argv, record, removed_at, checker, native_claim):
    """Pure control boundary: a successful unrelated process is not evidence."""
    need(isinstance(native_claim, dict), "UNRESOLVED_REQUIRED_CLAIM", "registered required claim is absent")
    need(retained_process_argv_identity(process.get("argv")) == retained_process_argv_identity(expected_argv) and process.get("cwd") == str(PROJECT) and
         process.get("timeout_seconds", "missing") is None and
         type(process.get("returncode")) is int and process["returncode"] == 0 and process.get("timed_out") is False,
         "VERIFIER_MISMATCH", "retained process identity/cwd/budget/completed result differs")
    need(utc(removed_at) <= utc(process["started_at_utc"]) <= utc(process["ended_at_utc"]),
         "STALE_OR_UNBOUND_EVIDENCE", "retained process did not follow original-root removal")
    need(result.get("format") == "verislop.stage018-retained-route-result/8" and result.get("mode") == mode and
         result.get("source_root") == SOURCE_ROOT and result.get("closure_root") == record["closure_root"] and
         result.get("retained_root") == record["retained_root"] and result.get("original_root") == record["original_root"] and
         result.get("original_root_absent_before_reads") is True and result.get("claim_id") == record["claim_id"] and
         result.get("native_claim") == native_claim and native_claim.get("required") is True and native_claim.get("applicable") is True,
         "STALE_OR_UNBOUND_EVIDENCE", "retained result lacks the exact current required claim/root binding")
    need(same_ref(result.get("pre_route_authorization"), record["pre_route_authorization"]) and
         result.get("terminal_nonce") == record["terminal_nonce"] and
         plain_hash(result.get("bound_inputs", {}).get("first_read_file_hashes", {}).get(record["pre_route_authorization"]["path"])) == plain_hash(record["pre_route_authorization"]["sha256"]) and
         not ({"terminal_binding", "terminal_binding_sha256", "final_binding", "final_binding_sha256"} & set(result)),
         "HASH_CYCLE_OR_UNREGISTERED_INPUT", "retained result must bind only the current pre-route authority, never final binding")
    need(result.get("registered_route", {}).get("id") == "D21-SCOPE-RETAINED-018-008" and
         set(result["registered_route"]) == {"id", "sha256"} and
         plain_hash(result["registered_route"]["sha256"]) == plain_hash(record["route_sha256"]) and
         result.get("checker") == checker and result.get("status") == "PASS" and
         utc(process["started_at_utc"]) <= utc(result["started_at_utc"]) <= utc(result["ended_at_utc"]) <= utc(process["ended_at_utc"]),
         "VERIFIER_MISMATCH", "retained route/checker/result/actual chronology differs")
    if mode == "second-probe":
        probe = result.get("probe")
        need(isinstance(probe, dict) and probe.get("status") == "NOT_REPRODUCED" and
             probe.get("expected", {}).get("outcome") == "PASS" and probe.get("observed", {}).get("outcome") == "PASS" and
             probe.get("checker") == checker and probe.get("proposal") == {"kind":"mechanical_failure", "claim_id":record["claim_id"]} and
             probe.get("checkpoint") == "release" and probe.get("claim", {}).get("claim_id") == record["claim_id"] and
             probe.get("input_bindings") and probe["input_bindings"].get("binding:roots") and
             probe.get("expected", {}).get("root_kind") == native_claim["root_kind"] and
             probe.get("expected", {}).get("root") == result.get("roots", {}).get(native_claim["root_kind"]) and
             result.get("registered_internal_probe_timeout_seconds") == 5.0,
             "UNRESOLVED_REQUIRED_CLAIM", "retained second probe is absent/unbound/not PASS")
    return result


class Audit:
    def __init__(self, reads, binding, output):
        self.reads, self.binding, self.output = reads, binding, output
        self.memo = {}
        self.observations = {}
        self.bootstrap = self.canonical = self.pkg = None
        self.binding_ref = None
        self.pre_route_doc = None
        self.pre_route_ref = None

    def once(self, name, function):
        if name not in self.memo:
            try:
                self.memo[name] = (True, function())
            except Exception as exc:
                self.memo[name] = (False, exc)
        good, result = self.memo[name]
        if not good:
            raise result
        return result

    def stop_and_seal(self):
        b = self.binding
        if b.get("format") == PRE_FORMAT:
            self.pre_route_doc = validate_pre_route(b)
        else:
            self.pre_route_ref = b["pre_route_authorization"]
            self.pre_route_doc = self.reads.artifact(self.pre_route_ref, "closed immutable pre-route authorization; no future outputs")
            authenticate_pre_route(b,self.pre_route_doc)
            if self.binding_ref is not None:
                need(self.pre_route_ref["path"] != self.binding_ref["path"] and
                     plain_hash(self.pre_route_ref["sha256"]) != plain_hash(self.binding_ref["sha256"]),
                     "HASH_CYCLE_OR_UNREGISTERED_INPUT", "pre-route and final binding roles cannot share bytes or path")
        need(b["authorization"] == "root-explicit-terminal-after-all-authors-controller-stopped" and
             b["stage"] == "tier2-source-facets-018" and b["project"] == str(PROJECT) and b["cohort"] == str(COHORT),
             "ACTORS_NOT_STOPPED", "missing exact stage018 terminal authorization")
        stop = self.reads.artifact(b["actor_stop"], "root actual stopped-actors attestation; read before all task artifacts")
        need(stop["format"] == "verislop.stage018-actor-stop/1" and stop["stage"] == b["stage"] and
             stop["source_root"] == SOURCE_ROOT and stop["cohort"] == str(COHORT) and
             stop["controller"]["status"] == "STOPPED" and stop["controller"]["active_author_count"] == 0 and
             stop["controller"]["pending_native_requests"] == 0 and
             isinstance(stop["authors"], list) and bool(stop["authors"]) and
             all(a["status"] == "STOPPED" for a in stop["authors"]),
             "ACTORS_NOT_STOPPED", "not every controller/author has stopped")
        names = [a["agent_id"] for a in stop["authors"]]
        need(len(names) == len(set(names)), "ACTORS_NOT_STOPPED", "duplicate author identities")
        need(utc(stop["stopped_at_utc"]) <= datetime.now(timezone.utc), "ACTORS_NOT_STOPPED", "future stop attestation")
        need(utc(stop["stopped_at_utc"]) <= utc(self.pre_route_doc["authorized_at_utc"]),
             "ACTORS_NOT_STOPPED", "pre-route authorization predates actual actor stop")
        self.observations["actor_stop"] = {"sha256": b["actor_stop"]["sha256"], "controller": stop["controller"],
                                            "authors": stop["authors"], "stopped_at_utc": stop["stopped_at_utc"]}
        # Both manifests are read only after the attestation; their exact maps
        # cover fresh cohort and controller evidence, including failed attempts.
        seals = {}
        for key, root in (("cohort_seal", COHORT), ("orchestration_seal", DRIVER)):
            seal = self.reads.artifact(b[key], key)
            need(seal["format"] == "verislop.stage018-sealed-inventory/1" and seal["root"] == str(root) and
                 seal["stage"] == b["stage"] and seal["source_root"] == SOURCE_ROOT,
                 "RUN_NOT_SEALED", key + " root/stage mismatch")
            need(utc(seal["sealed_at_utc"]) >= utc(stop["stopped_at_utc"]), "RUN_NOT_SEALED", "seal predates actor stop")
            need(utc(seal["sealed_at_utc"]) <= utc(self.pre_route_doc["authorized_at_utc"]),
                 "RUN_NOT_SEALED", "pre-route authorization predates sealed inventory")
            actual = inventory(self.reads, root, "exact sealed fresh " + key + " bytes")
            need(actual == seal["files"], "RUN_NOT_SEALED", key + " does not cover exact current files")
            seals[key] = actual
        self.observations["sealed_inventory_roots"] = {k: sha(json.dumps(v, sort_keys=True, separators=(",", ":")).encode()) for k,v in seals.items()}
        self.observations["pre_route_authorization"] = {"reference":self.pre_route_ref,"terminal_nonce":self.pre_route_doc["terminal_nonce"],
            "authorized_at_utc":self.pre_route_doc["authorized_at_utc"],"authority":"same frozen inputs only; final-output hashes are prohibited"}
        return stop, seals

    def preparation(self):
        pre = self.reads.obj(PRE_BINDING, PRE_BINDING_SHA, "actual immutable preregistered pre-generation binding")
        receipt = self.reads.obj(PRE_RECEIPT, PRE_RECEIPT_SHA, "independently captured pre-generation actual process receipt")
        need(type(receipt["returncode"]) is int and receipt["returncode"] == 0 and receipt["timed_out"] is False and
             receipt["cwd"] == str(PROJECT) and plain_hash(receipt["output_files"]["binding.json"]) == PRE_BINDING_SHA,
             "PREREGISTRATION_LATE", "pre-generation binding actual receipt differs")
        need(pre["binding_status"] == "PASS" and pre["generation_started"] is False and pre["model_calls"] == 0 and
             pre["task_artifact_reads"] == [] and pre["task_builds"] == pre["task_verifiers"] == pre["public_probe_executions"] == 0 and
             pre["source_root"] == SOURCE_ROOT and pre["qualification_input_root"] == QUALIFICATION_ROOT,
             "PREREGISTRATION_LATE", "binding did not precede native generation")
        need(utc(receipt["ended_at_utc"]) < utc(self.binding["generation_started_at_utc"]),
             "PREREGISTRATION_LATE", "actual binding completion does not precede first native generation")
        helper = HERE / "bind-pre-generation-001.py"
        self.reads.raw(helper, HELPER_SHA, "immutable registered public-plan helper; definitions only")
        module_spec = importlib.util.spec_from_file_location("scope018_public_plan_helper", helper)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        module.freeze_plan(self.reads)
        need(pre["preregistration_input_root_hash"] == module.PLAN_ROOT and
             self.binding["preregistration_input_root_hash"] == module.PLAN_ROOT and
             pre["probe_object_canonical_sha256"] == module.PROBE_OBJECT_SHA,
             "CLAIM_MUTATION", "frozen scope/probe root differs")
        self.public_helper, self.pre = module, pre
        self.reads.verification_sources = {str(PROJECT / name) for name in pre["source_files"]}
        for name, digest in pre["source_files"].items():
            self.reads.raw(PROJECT / name, digest, "qualified project source before import")
            self.reads.raw(REPO / name, digest, "current generic workspace source before import")
        for name, digest in pre["input_files"].items():
            self.reads.raw(COHORT / name, digest, "unchanged preregistered public request/configuration")
        for item in [pre["native_driver"], *pre["controller_inputs"]]:
            self.reads.raw(item["path"], item["sha256"], "frozen native orchestration/controller input")
        self.reads.raw(COHORT / "protocol.json", pre["protocol_sha256"], "exact stage018 public protocol")
        self.reads.raw(COHORT / "preregistration.json", pre["preregistration_sha256"], "exact bootstrap preregistration")
        self.reads.raw(PROJECT / "TIER2-SNAPSHOT.json", pre["project_snapshot_sha256"], "exact qualified project snapshot")
        need(module.source_map_digest(pre["source_files"]) == SOURCE_ROOT, "INPUT_MUTATION", "complete source map root differs")
        need(Path.cwd().absolute() == PROJECT, "VERIFIER_MISMATCH", "audit must execute in the frozen project cwd")
        sys.path.insert(0, str(PROJECT))
        self.canonical = importlib.import_module("verislop.canonical")
        self.bootstrap = importlib.import_module("synthetic_dataset.tools.bootstrap_tier2")
        fsutil = importlib.import_module("verislop.fsutil")
        need(str(Path(fsutil.__file__).absolute()) in self.reads.verification_sources,
             "VERIFIER_MISMATCH", "temporary creator is outside the registered source map")
        self.reads.temporary_creator_code = fsutil.temporary_directory.__wrapped__.__code__
        for obj in (self.canonical, self.bootstrap):
            need(Path(obj.__file__).absolute().is_relative_to(PROJECT), "VERIFIER_MISMATCH", "module imported outside frozen project")
        need(self.bootstrap.source_inventory(REPO) == pre["source_files"],"INPUT_MUTATION","complete current generic source inventory differs")
        protocol = self.bootstrap.verify_inputs(COHORT)
        validate_protocol_metadata(protocol,pre)
        self.protocol = protocol
        return pre

    def qualification(self):
        self.once("preparation", self.preparation)
        q = self.reads.obj(QUAL_REPORT, QUAL_REPORT_SHA, "actual Q018 root002 final report")
        independent = self.reads.obj(INDEPENDENT_REPORT, INDEPENDENT_REPORT_SHA, "actual independent root002 audit")
        for o in (q, independent):
            need(o["status"] == "VERIFIED" and o["source_root"] == SOURCE_ROOT and o["input_root"] == QUALIFICATION_ROOT,
                 "STALE_OR_UNBOUND_EVIDENCE", "current whole-root qualification/audit differs")
            need([r["claim_id"] for r in o["claims"]] == [f"Q018-{n:02d}" for n in range(1,19)] and
                 all(r["status"] == "VERIFIED" for r in o["claims"]), "ORPHAN_CLAIM", "qualification is not actual18-of18")
        need(q["decision"]["manual_override_allowed"] is False and type(q["decision"]["exit_code"]) is int and
             q["decision"]["exit_code"] == 0 and independent["manual_override_allowed"] is False and
             type(independent["exit_code"]) is int and independent["exit_code"] == 0 and
             independent["infrastructure_errors"] == [], "QUALIFICATION_INCOMPLETE", "qualification/audit decision differs")
        engineering = self.reads.obj(ENGINEERING, ENGINEERING_SHA, "actual engineering chain; its own dynamic claim inventory")
        pre_spec = self.reads.obj(DRIVER / "pre-generation/binding-specification-001.json",
                    "f2ac3e8ae4a43db80152e8904cea33582400be6f8e3556a407f52a415e77e0b4",
                    "actual pre-generation argument specification; same authenticated generic chain")
        self.public_helper.qualification(self.reads,pre_spec,self.canonical,self.bootstrap)
        need(engineering["source_root"] == SOURCE_ROOT and engineering["status"] == "VERIFIED" and
             all(r["required"] is True and r["outcome"] == "PASS" for r in engineering["required_claim_observations"]),
             "QUALIFICATION_INCOMPLETE", "actual engineering collection closure differs")
        return {"qualification": QUAL_REPORT_SHA, "independent_audit": INDEPENDENT_REPORT_SHA,
                "engineering_record": ENGINEERING_SHA, "engineering_required_claim_count": len(engineering["required_claim_observations"])}

    def transport(self):
        self.once("stop_and_seal",self.stop_and_seal)
        self.once("preparation",self.preparation)
        trace = self.reads.artifact(self.binding["transport_trace"],"actual complete stage018 controller transport trace including rejected envelopes")
        transport_spec = self.reads.obj(HERE/SPEC_NAME,self.binding["registered_files"][SPEC_NAME])["transport_trace"]
        validate_transport_structure(trace,transport_spec)
        need(trace["format"] == "verislop.stage018-native-transport-trace/2" and trace["stage"] == "tier2-source-facets-018" and
             trace["source_root"] == SOURCE_ROOT and trace["controller_count"] == 1 and bool(trace["requests"]),
             "STALE_OR_UNBOUND_EVIDENCE","actual sole-controller transport trace missing")
        self.observations["native_transport_trace"] = {"path":self.binding["transport_trace"]["path"],
            "sha256":self.binding["transport_trace"]["sha256"],"retained_request_count":len(trace["requests"]),
            "authenticated_submission_evidence":[],"status":"INCOMPLETE_BEFORE_AUTHENTICATION",
            "authority":"actual transport only; no semantic or review ACCEPT inferred"}
        seen = set()
        agents = set()
        mailbox = COHORT / "artifacts/D21/verislop/mailbox"
        expected_ids = {p.stem.removeprefix("request-") for p in mailbox.glob("request-*.json")}
        stopped_authors = {r["agent_id"] for r in self.memo["stop_and_seal"][1][0]["authors"]}
        for row in trace["requests"]:
            need(row["request_id"] not in seen,"STALE_OR_UNBOUND_EVIDENCE","duplicate native request in actual transport trace")
            seen.add(row["request_id"])
            need(row["author_agent_id"] in stopped_authors and row["author_agent_id"] not in agents,
                 "STALE_OR_UNBOUND_EVIDENCE","fresh author uniqueness/stop identity differs")
            agents.add(row["author_agent_id"])
            final = self.reads.raw(row["literal_final"]["path"],row["literal_final"]["sha256"],"unchanged actual fresh author literal FINAL")
            origin = self.reads.artifact(row["literal_final_origin"]["record"],"exact original controller literal-FINAL JSON bytes")
            authenticate_literal_final_origin(origin,final,row["literal_final_origin"]["json_pointer"])
            need(bool(row["submissions"]),"STALE_OR_UNBOUND_EVIDENCE","author FINAL has no actual native submission")
            prior_envelope = None
            for index,attempt in enumerate(row["submissions"]):
                process = attempt["process_evidence"]
                invocation,registered = None,None
                if process["kind"] == "completed_process_receipt":
                    evidence = self.reads.artifact(process["record"],"actual full native submission process receipt")
                else:
                    evidence = self.reads.artifact(process["result"],"actual original rejected tool result; never fabricated process receipt")
                    if process.get("invocation") is not None:
                        invocation = self.reads.artifact(process["invocation"],"actual archived rejected tool invocation")
                    registered = transport_spec["registered_tool_invocations"].get(row["request_id"]+":"+str(index+1))
                actual_process = authenticate_transport_evidence(attempt,evidence,invocation,registered)
                self.observations["native_transport_trace"]["authenticated_submission_evidence"].append(
                    {"request_id":row["request_id"],"submission_index":index+1,"actual_evidence":actual_process})
                envelope = self.reads.artifact(attempt["envelope"],"exact submitted envelope; no answer resampling")
                literal = pointer(envelope,attempt["literal_final_pointer"])
                need(isinstance(literal,str) and literal.encode() == final,"STALE_OR_UNBOUND_EVIDENCE","native submitted answer differs from same author's literal FINAL")
                authenticate_transport_transition(prior_envelope,envelope,attempt)
                prior_envelope = envelope
            rid = row["request_id"]
            request_path = mailbox / ("request-"+rid+".json")
            request = self.reads.obj(request_path,purpose="actual frozen native request for transport origin")
            published = self.reads.obj(mailbox / ("response-"+rid+".json"),purpose="actual consumed native response envelope")
            pending = self.bootstrap._binding(COHORT,"D21",request_path,request,self.protocol,create=False)
            text,agent = self.bootstrap._check_envelope(published,pending)
            need(prior_envelope == published and text.encode() == final and agent == row["author_agent_id"] and
                 row["submissions"][-1]["observed_exit_code"] == 0,
                 "STALE_OR_UNBOUND_EVIDENCE","literal FINAL/author/current consumed native envelope differs")
        need(seen == expected_ids,"STALE_OR_UNBOUND_EVIDENCE","actual transport trace omits/adds native requests")
        self.observations["native_transport_trace"] = {"path":self.binding["transport_trace"]["path"],
            "sha256":self.binding["transport_trace"]["sha256"],"request_count":len(seen),
            "authenticated_submission_evidence":self.observations["native_transport_trace"]["authenticated_submission_evidence"],"status":"AUTHENTICATED_TRANSPORT_ONLY",
            "authority":"actual submission success is transport only; no semantic or review ACCEPT inferred"}
        return trace

    def native(self):
        self.once("preparation", self.preparation)
        task = self.protocol["tasks"][0]
        result = self.bootstrap.task_result(COHORT, task)
        validate_task_result_metadata(result)
        directory = COHORT / result["artifact_path"]
        pipeline = self.reads.obj(directory / "stdout.json", purpose="actual current native CLI publication")
        self.pkg = self.bootstrap.active_package(directory, pipeline)
        self.report = self.reads.obj(self.pkg.path("report"), purpose="current native report; not accepted without reconstruction")
        from verislop.backends import vscore3_closure as closure, vscore3 as backend
        from verislop.bridges import vscore3_checker as checker
        self.closure, self.backend, self.checker = closure, backend, checker
        self.snapshot = closure.mechanical_snapshot(self.pkg)
        need(self.snapshot is not None, "STALE_OR_UNBOUND_EVIDENCE", "native mechanical publication absent")
        self.selection = backend.selection(self.pkg)
        self.ctx = checker.load_context(self.pkg.root / "bridges" / self.selection["bridge_id"],
                                       self.selection["bridge_id"], self.selection["edge_id"])
        self.goal = checker.derive_goal(self.ctx)
        self.ir = self.ctx.accepted_ir
        self.observations["native_task_result"] = result
        return result

    def fresh_replay(self):
        self.once("native", self.native)
        from verislop import leanbridge, fsutil
        from verislop.targets import vscore3_target as target
        accepted, pending, diagnostics = self.checker.verify_published(self.pkg, self.selection["bridge_id"], rebuild=False)
        need(not diagnostics and not pending and len(accepted) == 1, "STALE_OR_UNBOUND_EVIDENCE", "retained semantic publication invalid")
        tc = leanbridge.resolve_toolchain(self.ctx.acceptance["toolchain"]["pin"])
        # This is the qualified verify_published(rebuild=True) route expanded
        # without modifying any registered function, policy, budget or input.
        # check_edge performs exactly two independently isolated checked builds.
        parent = self.output / "fresh-verification"
        parent.mkdir()
        try:
            spec, a, b = self.checker.check_edge(tc, self.ctx)
        except Exception as exc:
            diagnostics = [d.to_json() for d in getattr(exc,"diagnostics",[])]
            failure_hash = publish(parent / "actual-failure-diagnostics.json", diagnostics)
            self.observations["fresh_verification_failure"] = {"path":str(parent / "actual-failure-diagnostics.json"),
                  "sha256":failure_hash,"exception":type(exc).__name__,
                  "provenance":"actual temporary verification attempt; unchanged native inputs; no repair"}
            raise
        with fsutil.temporary_directory(prefix="scope018-verification-publication-") as temporary:
            fresh = self.checker.outputs(self.ctx, spec, a, b, AUDIT_ID, Path(temporary))
        accepted_dir = self.pkg.root / "bridges" / self.selection["bridge_id"] / self.checker.SEMANTIC_DIR / self.checker.edge_key(self.selection["edge_id"])
        stored = self.reads.obj(accepted_dir / self.checker.CERTIFICATE, purpose="retained semantic certificate at actual original provenance")
        cert = self.canonical.loads(fresh[self.checker.CERTIFICATE])
        need(self.checker._certificate_descriptor(stored) == self.checker._certificate_descriptor(cert),
             "NONDETERMINISM", "fresh verification does not reproduce complete stored semantic descriptor")
        paths = [self.checker.IR_FILE, "goal/VeriSlopBridgeGoal.lean", "builds/A.json", "builds/B.json",
                 *[m["path"] for m in stored["accepted_modules"]]]
        if "readable_support" in stored:
            paths.extend(self.checker.readable_artifact_refs(stored["readable_support"],
                                                          lambda p: self.reads.raw(accepted_dir / p)))
        for path in paths:
            need(fresh[path] == self.reads.raw(accepted_dir / path, purpose="exact stored artifact reproduced by fresh verification"),
                 "NONDETERMINISM", "fresh verification differs: " + path)
        artifacts = {}
        for name, data in sorted(fresh.items()):
            p = parent / "publication" / name
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("xb") as f:
                f.write(data)
            artifacts[p.relative_to(self.output).as_posix()] = "sha256:" + sha(data)
        for label, build in (("A", a), ("B", b)):
            artifacts["fresh-verification/" + label + "-declarations.json"] = publish(parent / (label + "-declarations.json"), build.decls)
            artifacts["fresh-verification/" + label + "-compiler-processes.json"] = publish(parent / (label + "-compiler-processes.json"), build.process_evidence)
            for module, parts in build.modules.items():
                for suffix, data in parts.items():
                    p = parent / label / "modules" / (leanbridge.module_relpath(module) + suffix)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    with p.open("xb") as f:
                        f.write(data)
                    artifacts[p.relative_to(self.output).as_posix()] = "sha256:" + sha(data)
        need(a.observation == b.observation, "NONDETERMINISM", "fresh A/B complete observations differ")
        self.fresh_spec, self.fresh_builds, self.fresh_decls = spec, (a,b), a.decls
        self.target = target
        self.observations["fresh_verification"] = {"route": "qualified verify_published rebuild route: check_edge/outputs/exact comparison",
             "provenance": "temporary independent scope verification; never substituted for original native closure or release roots",
             "actual_original_closure_root": self.snapshot["closure_root"], "original_semantic_edge_root": stored["semantic_edge_root"],
             "artifacts": artifacts, "builds": [a.observation,b.observation], "new_model_calls": 0,
             "new_public_probe_inputs": 0, "resource_budgets": self.ctx.policy}
        return artifacts

    def identities(self):
        self.once("native", self.native)
        expected = self.reads.obj(HERE / "original-public-metadata-projection.json")["records"]
        need(set(self.ir["obligations"]) in (set(IDS), set(IDS) | {"A1_nonvacuity"}), "OBLIGATION_DRIFT", "original IDs changed or extra obligations added")
        for original in expected:
            rec = self.ir["obligations"][original["id"]]
            need(all(rec[k] == original[k] for k in ("kind","role","required")), "OBLIGATION_DRIFT", original["id"])
            wanted = [{k: r[k] for k in ("document_ref","document_hash","start_byte","end_byte")} for r in original["source_refs"]]
            actual = [{k: r[k] for k in ("document_ref","document_hash","start_byte","end_byte")} for r in rec["source_refs"]]
            need(all(row in actual for row in wanted), "SOURCE_SPAN_MISMATCH", original["id"] + " original provenance absent")
        if "A1_nonvacuity" in self.ir["obligations"]:
            rec = self.ir["obligations"]["A1_nonvacuity"]
            need(rec["kind"] == "non_vacuity" and rec["required"] is True, "INVALID_DERIVED_OBLIGATION", "unexpected derived witness")
        need(sorted(r["id"] for r in self.selection["covered"]) == sorted(GUARANTEES), "ORPHAN_CLAIM", "selection is not original9 implementation guarantees")
        return {"original_ids": list(IDS), "implementation_guarantees": list(GUARANTEES)}

    def domain(self):
        self.once("identities", self.identities)
        need(len(self.goal.symbols) == 1, "REPRESENTATION_GAP", "one solve endpoint required")
        symbol = self.goal.symbols[0]
        need(symbol.entry == "solve" and symbol.arity == 1, "REPRESENTATION_GAP", "solve arity1 required")
        p = self.ctx.accepted_profile
        def record(sort):
            need(isinstance(sort,dict) and set(sort) == {"record"}, "REPRESENTATION_GAP", "record carrier required")
            return {f["name"]: f["sort"] for f in p["records"][sort["record"]]["fields"]}
        inp = record(symbol.arg_sorts[0])
        need(set(inp) == {"events","start","end","width","fill"} and all(inp[k] == "Int" for k in ("start","end","width")),
             "DOMAIN_NARROWING", "input shape or unbounded signed integer carriers changed")
        need(isinstance(inp["events"],dict) and set(inp["events"]) == {"list"}, "DOMAIN_NARROWING", "all finite event lists required")
        need(record(inp["events"]["list"]) == {"group":"String","time":"Int","value":{"option":"Int"}},
             "DOMAIN_NARROWING", "event carrier narrows scalar strings/signed integers/nulls")
        need(isinstance(inp["fill"],dict) and set(inp["fill"]) == {"enum"} and
             sorted(p["enums"][inp["fill"]["enum"]]["constructors"]) == ["none","previous"], "DOMAIN_NARROWING", "fill modes differ")
        need(isinstance(symbol.result_sort,dict) and set(symbol.result_sort) == {"list"}, "REPRESENTATION_GAP", "list result required")
        out = record(symbol.result_sort["list"])
        need(set(out) == {"group","start","count","value"} and out["group"] == "String" and out["start"] == "Int" and
             out["count"] in ("Nat","Int") and out["value"] == {"option":"Int"}, "REPRESENTATION_GAP", "output record domain changed")
        need([oid for oid,rec in self.ir["obligations"].items() if rec["role"] == "assumption"] == ["A1"],
             "UNDECLARED_ASSUMPTION", "assumptions exceed original caller A1")
        witness = self.once("correspondence", self.correspondence)
        need(witness["domain"]["premises"] == ["width > 0","start <= end"] and witness["domain"]["valid_input_exclusions"] == [] and
             witness["domain"]["integer_semantics"] == "unbounded mathematical signed Int" and
             witness["domain"]["strings"] == "arbitrary Unicode scalar String" and
             witness["domain"]["events"] == "all finite lists" and witness["domain"]["bucket_count"] == "all finite counts",
             "DOMAIN_NARROWING", "finite explicit domain interpretation does not cover original domain")
        need(bool(witness["domain"]["accepted_premise_references"]), "EVIDENCE_MISSING", "A1 accepted premise AST references absent")
        for ref in witness["domain"]["accepted_premise_references"]:
            self.resolve_correspondence_reference(ref)
        return {"input": inp, "output": out, "interpretation": witness["domain"]}

    def facets(self):
        self.once("identities", self.identities)
        from verislop import source_contract
        requested = self.reads.obj(COHORT / "requests/D21/source-policy.json", self.pre["input_files"]["requests/D21/source-policy.json"])
        need(self.reads.obj(self.pkg.root / "request/source-policy.json") == requested, "SOURCE_POLICY_MUTATION", "package source policy differs")
        for oid in GUARANTEES:
            rec = self.ctx.obligations[oid]
            need((rec["formula"] is not None) == oid.startswith("O") and bool(rec["source_facets"]), "FACET_MISMATCH", oid)
            if rec["formula"] is not None:
                residual = rec["formula"]
                while residual.get("tag") in {"forall","implies"}:
                    residual = residual["body"] if residual["tag"] == "forall" else residual["right"]
                need(residual.get("tag") != "true" and not (residual.get("tag") == "eq" and residual["left"] == residual["right"]),
                     "MISSING_REQUIREMENT","literal/reflexive value facet replaces functional scope: " + oid)
            rows = rec["source_facets"]
            need(len(rows) == 1, "FACET_MISMATCH", "one exact source endpoint row required: " + oid)
            properties = {r["tag"] for r in rows[0]["requirements"]}
            need(properties == {"entry", *self.public_helper.SOURCE_PROPERTIES}, "FACET_MISMATCH", "global source properties changed: " + oid)
            entry = next(r for r in rows[0]["requirements"] if r["tag"] == "entry")
            need(entry["entry"] == "solve" and entry["arity"] == 1 and rows[0]["model_source_hash"] == source_contract.model_source_hash(),
                 "FACET_MISMATCH", "entry or semantic source model changed")
        self.once("correspondence", self.correspondence)
        return {oid: "MIXED" if oid.startswith("O") else "SOURCE_ONLY" for oid in GUARANTEES}

    def resolve_correspondence_reference(self, ref):
        need(set(ref) == {"surface","selector","sha256"}, "AMBIGUOUS_CORRESPONDENCE", "closed actual AST reference required")
        surfaces = {"accepted_ir":self.ir, "accepted_profile":self.ctx.accepted_profile,
                    "accepted_formulas":self.ctx.obligations, "declarations":self.fresh_decls}
        need(ref["surface"] in surfaces, "AMBIGUOUS_CORRESPONDENCE", "foreign correspondence surface")
        value = pointer(surfaces[ref["surface"]], ref["selector"])
        need(plain_hash(self.canonical.digest_json(value)) == plain_hash(ref["sha256"]), "STATEMENT_MISMATCH", "actual correspondence AST hash differs")
        need(isinstance(value,(dict,list)) and value != {} and value != [],
             "MISSING_REQUIREMENT", "empty/literal correspondence reference")
        if ref["surface"] == "declarations":
            pieces = ref["selector"].split("/")[1:]
            need(bool(pieces),"STATEMENT_MISMATCH","whole declaration inventory cannot replace an exact AST reference")
            name = pieces[0].replace("~1","/").replace("~0","~")
            decl = self.fresh_decls[name]
            need(decl.get("module") in ([self.target.CONTRACT_MODULE],[self.target.GOAL_MODULE]) and
                 (len(pieces) == 1 or pieces[1] in {"type","value"}),
                 "STATEMENT_MISMATCH","correspondence must cite exact accepted/goal AST, not proof names or metadata")
        return value

    def correspondence(self):
        self.once("fresh_replay", self.fresh_replay)
        ref = self.binding["scope_interpretation"]
        need(ref is not None, "EVIDENCE_MISSING", "independent finite original-to-accepted correspondence matrix absent")
        need(strict_path(ref["path"]).is_relative_to(HERE), "SCOPE_LEAK", "interpretation record must be independent scope-audit evidence")
        matrix = self.reads.artifact(ref, "independent explicit interpretation; never kernel or authored PASS authority")
        need(matrix["format"] == "verislop.d21-finite-scope-interpretation/1" and matrix["audit_id"] == AUDIT_ID and
             matrix["original_requirements_sha256"] == "b76559ac9463a1f56be2ff38bb08940b4c2d74ef770573a5574d77450c4a1f0f" and
             matrix["accepted_ir_sha256"] == self.selection["accepted_ir_hash"] and matrix["closure_root"] == self.snapshot["closure_root"] and
             matrix["trust"] == "explicit natural-language-to-accepted-formula interpretation; no kernel theorem or LLM-only mechanical discharge",
             "AMBIGUOUS_CORRESPONDENCE", "interpretation has wrong scope/root/trust")
        originals = self.reads.obj(HERE / "original-public-requirements.json")["records"]
        expected = {}
        for rec in originals:
            expected[rec["id"] + ":statement"] = (rec["id"], rec["statement"])
            for i,text in enumerate(rec["acceptance_criteria"],1):
                expected[rec["id"] + f":criterion:{i:02d}"] = (rec["id"],text)
        rows = matrix["coverage"]
        need(len(rows) == len(expected) and {r["clause_id"] for r in rows} == set(expected), "MISSING_REQUIREMENT", "finite original statement/criteria coverage incomplete")
        for row in rows:
            oid,text = expected[row["clause_id"]]
            need(row["original_id"] == oid and plain_hash(row["original_text_sha256"]) == sha(text.encode()) and
                 row["accepted_id"] in (GUARANTEES if oid == "I1" else (oid,)) and
                 bool(row["references"]) and isinstance(row["explanation"],str) and bool(row["explanation"].strip()),
                 "MISSING_REQUIREMENT", row["clause_id"])
            need(any(r["surface"] == "declarations" for r in row["references"]), "STATEMENT_MISMATCH", "actual accepted/fresh declaration AST absent: " + row["clause_id"])
            if oid in GUARANTEES:
                need(any(r["surface"] == "accepted_formulas" and
                     r["selector"].split("/")[1:2] == [row["accepted_id"]] for r in row["references"]),
                     "MISSING_REQUIREMENT","exact own accepted facet/formula reference absent: " + row["clause_id"])
            for reference in row["references"]:
                self.resolve_correspondence_reference(reference)
            # The source-only revision does not carry original causal value I1.
            if oid == "I1":
                need(row["accepted_id"] == "O5" and self.ctx.obligations["O5"]["formula"] is not None,
                     "MISSING_REQUIREMENT", "full causal I1 must remain in Mixed O5")
        expected_deps = {rec["id"]:rec["dependencies"] for rec in originals}
        need(matrix["original_dependencies"] == expected_deps and matrix["undischarged_clauses"] == [] and
             matrix["new_requirements"] == [], "MISSING_REQUIREMENT", "original dependencies/clauses lost or new requirements introduced")
        self.observations["scope_interpretation"] = {"path":ref["path"],"sha256":ref["sha256"],"trust":matrix["trust"],"clause_count":len(rows)}
        return matrix

    def original_build_processes(self):
        self.once("native", self.native)
        need([b["build"] for b in self.snapshot["builds"]] == ["A","B"] and all(b["ok"] is True for b in self.snapshot["builds"]),
             "CLEAN_BUILD_FAILURE", "actual native closure A/B missing")
        execution = (self.pkg.root / self.snapshot["mechanical_result_path"]).parent
        workdirs, evidence = {}, {}
        for label in ("A","B"):
            root = execution / "builds" / label / "semantic"
            cert = self.reads.obj(root / self.checker.CERTIFICATE)
            record = self.reads.obj(root / cert["evidence"]["path"],cert["evidence"]["sha256"])
            raw = self.reads.obj(root / record["raw_result_ref"],record["raw_result_hash"])
            processes = raw["compile_process_evidence"]
            need(processes["format"] == "verislop.vscore-compile-process-inventory/1" and set(processes["builds"]) == {"A","B"},
                 "CLEAN_BUILD_FAILURE", "actual native compiler process inventory absent")
            # Each closure label contains the real one-build semantic output;
            # its internal duplicate A/B projection is not counted as two builds.
            actual = processes["builds"]["A"]
            need(actual == processes["builds"]["B"] and bool(actual), "CLEAN_BUILD_FAILURE", "closure semantic telemetry shape differs")
            workdirs[label] = set()
            documented = set()
            for data in self.ctx.readable_diagnostics.values():
                documented.update(documented_envelopes(self.canonical.loads(data)))
            readable = self.canonical.loads(self.ctx.readable_selection) if self.ctx.readable_selection else None
            rows, accepted_modules = {}, set()
            for name, envelope in actual.items():
                body = envelope.get("record") if isinstance(envelope, dict) else None
                succeeded = isinstance(body, dict) and type(body.get("returncode")) is int and body["returncode"] == 0 and body.get("timed_out") is False
                accepted = succeeded
                if not succeeded:
                    digest = sha(json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode())
                    need(name.startswith("SELECTED::") and readable is not None and readable["selected_mode"] == "BASE" and digest in documented,
                         "CLEAN_BUILD_FAILURE", "failed compile is not an authenticated optional/control history: " + name)
                row = compile_record(envelope, accepted=accepted, name=label+":"+name)
                need(row["record"].get("input", {}).get("module") == name.split("::")[-1],
                     "VERIFIER_MISMATCH", "compiler module name does not match actual receipt: " + name)
                rows[name] = row
                if accepted:
                    accepted_modules.add(name.split("::")[-1])
                    workdirs[label].add(row["record"]["working_directory"])
            from verislop.targets import vscore3_target as target
            need(target.GOAL_MODULE in accepted_modules and target.PROOF_MODULE in accepted_modules,
                 "CLEAN_BUILD_FAILURE", "successful actual goal/proof compilations are missing")
            evidence[label] = {"closure_root":self.snapshot["closure_root"],"processes":rows,
                               "raw_process_envelopes":actual,
                               "outputs":self.snapshot["builds"][0 if label=="A" else 1]["outputs"]}
        need(workdirs["A"].isdisjoint(workdirs["B"]), "CLEAN_BUILD_FAILURE", "native closure A/B reused working directories")
        need(self.snapshot["builds"][0]["outputs"] == self.snapshot["builds"][1]["outputs"] and self.snapshot["determinism"]["mismatches"] == [],
             "NONDETERMINISM", "native complete deterministic outputs differ")
        self.observations["original_native_build_processes"] = evidence
        return evidence

    def review(self):
        result = self.once("native", self.native)
        need(result["release_status"] == "ACCEPTED" and result["native"]["status"] == "PASS", "RELEASE_INCOMPLETE", "original native release is not accepted")
        need(self.report["review"]["configured"] is True and self.report["review"]["checkpoints"] ==
             {"formal_contract":"REVIEW_ACCEPTED","release":"REVIEW_ACCEPTED"}, "RELEASE_INCOMPLETE", "all configured original-ID gates must accept")
        certificates = {}
        for checkpoint in ("formal_contract","release"):
            candidates = []
            for p in sorted(self.pkg.path("reviews").glob("rc-*/consensus-certificate.json")):
                cert = self.reads.obj(p)
                if cert["checkpoint"] == checkpoint:
                    candidates.append((p,cert))
            need(bool(candidates), "RELEASE_INCOMPLETE", "checkpoint absent: " + checkpoint)
            p,cert = candidates[-1]
            need(cert["final"] == "REVIEW_ACCEPTED" and set(IDS) <= set(cert["scope"]), "RELEASE_INCOMPLETE", "original11 scope/checkpoint failed")
            for tier in cert["tiers"]:
                if tier["result"] == "NOT_REACHED":
                    continue
                need(tier["result"] == "TIER_ACCEPTED", "RELEASE_INCOMPLETE", "required review tier not accepted")
                for ballotref in tier["ballots"]:
                    ballot = self.reads.obj(self.pkg.root / ballotref["ballot_ref"],ballotref["ballot_hash"])
                    need(set(IDS) <= set(ballot["reviewed_obligations"]), "RELEASE_INCOMPLETE", "ballot omits original required IDs")
                    for ref in ballot["counterexample_receipts"]:
                        receipt = self.reads.obj(self.pkg.root / ref["receipt_ref"],ref["receipt_hash"])
                        if ballot["verdict"] == "ACCEPT":
                            need(receipt["status"] == "NOT_REPRODUCED", "RELEASE_INCOMPLETE", "unknown/unsupported/confirmed reviewer probe cannot accept")
            certificates[checkpoint] = {"path":str(p),"review_target_root":cert["review_target_root"],"scope":cert["scope"]}
        self.observations["original_reviews"] = certificates
        return certificates

    def probes(self):
        self.once("native", self.native)
        frozen = self.reads.obj(HERE / "public-probes.json")["probes"]
        ref = self.binding["public_probe_observations"]
        if ref is None:
            rows = [{"id":p["id"],"status":"ABSENT","observation":None} for p in frozen]
        else:
            o = self.reads.artifact(ref,"existing exact-nine optional observations only; no probe invocation")
            need(o["format"] == "verislop.d21-frozen-public-probe-observations/1" and o["closure_root"] == self.snapshot["closure_root"] and
                 o["probe_object_canonical_sha256"] == self.public_helper.PROBE_OBJECT_SHA and len(o["probes"]) == 9,
                 "PROBE_BYTE_MUTATION", "optional observations have wrong exact probe/root binding")
            rows = o["probes"]
            for p,row in zip(frozen,rows):
                public_probe_row(p, row)
                if row["status"] == "OBSERVED":
                    evidence = self.reads.artifact(row["receipt"],"actual registered reference/source public observation")
                    from verislop import schemas, verifiers, review_counterexamples
                    need(not schemas.validate("review-counterexample-receipt",evidence) and
                         evidence["checker"] == {"id":review_counterexamples.VERIFIER,
                           "sha256":verifiers.verifier_hash(review_counterexamples.VERIFIER)},
                         "UNSUPPORTED_OBSERVATION", "no registered source/reference output receipt; retain honest unsupported status")
                    need(evidence["closure_root"] == self.snapshot["closure_root"] and evidence["checker"] == row["checker"] and
                         evidence["wire_mapping"] == row["wire_mapping"] and evidence["input"] == p["input"] and
                         evidence["output"] == row["output"], "STALE_OR_UNBOUND_EVIDENCE", "optional observation not bound to real evaluator receipt")
        self.observations["optional_public_probes"] = rows
        return {"count":9,"invocations_by_this_reader":0,"observations":rows,"TESTED":"PENDING"}

    def retained(self):
        self.once("native", self.native)
        # Reconstruct the complete supervisor claim inventory, rather than
        # deciding applicability solely from filenames or authored booleans.
        claims = self.closure._claims(self.pkg)
        current_rows = {row["claim_id"]:row for row in self.snapshot["claims"]}
        need(set(current_rows) == {c["claim_id"] for c in claims} and
             all(not c["required"] or not c["applicable"] or current_rows[c["claim_id"]]["outcome"] == "PASS" for c in claims),
             "UNRESOLVED_REQUIRED_CLAIM", "registered native inventory has a missing/unresolved required claim")
        # Reserved retention/removal identities or predicates cannot be silently
        # treated as absent. Current qualified native generation registers none;
        # any actual emitted extension is preserved and demands real evidence.
        retention_claims = [c for c in claims if
            c["claim_id"].startswith(("RETAINED:","RETENTION:")) or
            any(word in str(c.get("result_predicate", "")).lower() for word in ("retained", "retention", "root-removal"))]
        emitted = []
        for p in self.pkg.root.rglob("*.json"):
            if "retained" in p.parts or p.name in {"retained-package.json","retention-manifest.json"}:
                emitted.append(str(p))
        records = self.binding["retained_validations"]
        discovery = {"native_claims":claims,"registered_retention_claims":retention_claims,"emitted_paths":emitted}
        if not emitted and not records and not retention_claims:
            return {"emitted":False,"conditional_requirement":"not applicable under exact reconstructed registered native inventory; no retained-removal claim/carrier emitted",
                    "actual_discovery":discovery}
        need(bool(records), "EVIDENCE_MISSING", "required/emitted retained claim has no actual post-removal validation")
        need(self.binding_ref is not None, "BINDING_INVALID", "actual terminal argument identity missing")
        route_hash = self.binding["registered_files"][ROUTE_NAME]
        self.reads.raw(HERE/ROUTE_NAME, route_hash, "exact registered retained process route source")
        from verislop import review_counterexamples, verifiers, schemas
        from verislop.package import Package
        checker_identity = {"id":review_counterexamples.VERIFIER,"sha256":verifiers.verifier_hash(review_counterexamples.VERIFIER)}
        required_retention = {c["claim_id"] for c in retention_claims if c["required"] and c["applicable"]}
        represented, checked = set(), []
        for ref in records:
            rec = self.reads.artifact(ref,"actual retained validation and repeated retained probe evidence")
            need(rec.get("format") == RETAINED_RECORD_FORMAT, "BINDING_INVALID", "unregistered retained record format")
            rec = {**rec,"route_sha256":"sha256:"+plain_hash(route_hash)}
            need(same_ref(rec.get("pre_route_authorization"), self.pre_route_ref) and rec.get("terminal_nonce") == self.binding["terminal_nonce"],
                 "STALE_OR_UNBOUND_EVIDENCE", "retained record differs from current pre-route authority/nonce")
            original = strict_path(rec["original_root"])
            retained = strict_path(rec["retained_root"])
            need(not original.exists() and original != retained and not retained.is_relative_to(original) and
                 retained.is_relative_to(COHORT) and rec["source_root"] == SOURCE_ROOT and
                 rec["closure_root"] == self.snapshot["closure_root"], "STALE_OR_UNBOUND_EVIDENCE", "retained root/provenance/removal differs")
            need(inventory(self.reads,retained,"retained exact bytes") == rec["files"], "INPUT_MUTATION", "retained exact bytes changed")
            removal = self.reads.artifact(rec["original_root_removal"], "actual host chronology of original-root absence")
            need(removal.get("format") == "verislop.stage018-root-removal-observation/1" and
                 removal.get("original_root") == str(original) and removal.get("source_root") == SOURCE_ROOT and
                 removal.get("original_root_absent") is True and
                 removal.get("authority") == "root actual host observation of original-root absence before registered validation and second probe",
                 "STALE_OR_UNBOUND_EVIDENCE", "missing actual host removal provenance")
            retained_pkg = Package(retained,resolve_root=False)
            accepted,pending,diagnostics = self.checker.verify_published(retained_pkg,"implementation",rebuild=False)
            need(bool(accepted) and pending == [] and diagnostics == [], "STALE_OR_UNBOUND_EVIDENCE", "retained published bridge admission failed")
            actual = self.closure.mechanical_snapshot(retained_pkg)
            need(actual == self.snapshot and actual["closure_root"] == rec["closure_root"] and actual["mechanical_status"] == "VERIFIED",
                 "STALE_OR_UNBOUND_EVIDENCE", "registered retained package revalidation failed after original root removal")
            retained_claims = self.closure._claims(retained_pkg)
            need(retained_claims == claims and self.backend.selection(retained_pkg)["edge_claim_id"] == rec["claim_id"],
                 "UNRESOLVED_REQUIRED_CLAIM", "retained selected claim/inventory differs")
            native_claim = next((c for c in claims if c["claim_id"] == rec["claim_id"]), None)
            need(native_claim is not None, "UNRESOLVED_REQUIRED_CLAIM", "required retained probe claim is absent")
            current_roots = self.closure._roots(retained_pkg,self.backend.selection(retained_pkg),actual["closure_root"])
            process_records, results = {}, {}
            for mode,key in (("validation","validation"),("second-probe","second_probe")):
                receipt = self.reads.artifact(rec[key+"_process"], "full actual registered retained " + mode + " process")
                result_ref = rec[key+"_result"]
                result = self.reads.artifact(result_ref, "actual registered retained " + mode + " result bytes")
                expected = retained_argv(mode,self.pre_route_ref["path"],self.pre_route_ref["sha256"],rec,result_ref["path"])
                authenticate_retained_process(receipt,result,mode=mode,expected_argv=expected,record=rec,
                    removed_at=removal["observed_at_utc"],checker=checker_identity,native_claim=native_claim)
                authenticate_route_interval(receipt,self.pre_route_doc,self.binding)
                need(self.binding_ref["path"] not in result["bound_inputs"]["first_read_file_hashes"],
                     "HASH_CYCLE_OR_UNREGISTERED_INPUT", "route chronology/inputs use final binding or precede authorization")
                need(result["mechanical_snapshot"] == actual and result["accepted"] == accepted and result["roots"] == current_roots and
                     plain_hash(receipt["output_files"][Path(result_ref["path"]).name]) == plain_hash(result_ref["sha256"]),
                     "STALE_OR_UNBOUND_EVIDENCE", "actual retained process result is not the complete current registered result")
                for stream in ("stdout","stderr"):
                    self.reads.raw(receipt[stream]["path"],receipt[stream]["sha256"],"actual retained process lossless "+stream)
                process_records[key],results[key] = receipt,result
            need(utc(process_records["validation"]["ended_at_utc"]) <= utc(process_records["second_probe"]["started_at_utc"]),
                 "STALE_OR_UNBOUND_EVIDENCE", "second probe does not follow actual retained validation")
            first = self.reads.artifact(rec["first_probe_observation"], "actual initial registered release mechanical probe")
            second = results["second_probe"]["probe"]
            current = review_counterexamples.replay(retained_pkg,"release",{"kind":"mechanical_failure","claim_id":rec["claim_id"]})
            need(not schemas.validate("review-counterexample-receipt",first) and
                 first == second == current and second["expected"]["root"] == current_roots[native_claim["root_kind"]],
                 "STALE_OR_UNBOUND_EVIDENCE", "first/second/current full retained probe/checker/claim/root/input bindings differ")
            represented.add(rec["claim_id"])
            checked.append({"record":rec,"actual_processes":process_records,"actual_results":results,"actual_current_probe":current})
        need(required_retention <= represented, "UNRESOLVED_REQUIRED_CLAIM", "required emitted retention claim omitted from actual validations")
        return {"emitted":True,"records":checked,"actual_discovery":discovery,
                "root_removal_chronology_trust":"actual host observation and registered route absence check before any retained read; full completed process evidence"}

    def evaluate(self, number):
        if number == 1:
            return self.once("stop_and_seal",self.stop_and_seal)[0]
        self.once("stop_and_seal",self.stop_and_seal)
        if number == 2:
            pre = self.once("preparation",self.preparation)
            self.once("transport",self.transport)
            return pre
        if number == 3:
            return self.once("qualification",self.qualification)
        result = self.once("native",self.native)
        if number == 4:
            revised = self.reads.raw(COHORT / "requests/D21/revised-prompt.txt",self.pre["input_files"]["requests/D21/revised-prompt.txt"])
            need(self.reads.raw(self.pkg.path("prompt")) == revised, "REQUEST_DRIFT", "package functional/delivery request differs")
            return {"original_prompt_sha256":self.public_helper.PUBLIC_PROMPT_SHA,"revised_prompt_sha256":sha(revised),"delivery_only_revision":True}
        if number == 5:
            return self.once("identities",self.identities)
        if number == 6:
            return self.once("domain",self.domain)
        if number == 7:
            return self.once("facets",self.facets)
        if number in (8,10,11,12,13,14,15):
            self.once("fresh_replay",self.fresh_replay)
            if number == 10:
                body = self.target.reexport(self.fresh_spec,self.fresh_decls)
                need(self.canonical.dumps(body["program"]) == self.ctx.inputs["source"][1], "IR_REIFICATION_MISMATCH", "fresh checked source re-export differs")
                link,diagnostics = self.backend.checked_link(self.pkg)
                need(link is not None and not diagnostics,"IR_REIFICATION_MISMATCH","independent current link reconstruction failed")
            if number == 11:
                self.once("domain",self.domain)
            if number == 12:
                need(self.fresh_spec.refinement_symbols == {s.symbol for s in self.fresh_spec.symbols}, "MISSING_REFINEMENT", "endpoint omitted universal delivered-source refinement")
            if number == 13:
                for ob in self.fresh_spec.obligations:
                    name = self.target.name_str(self.target.gname("transfer_" + ob.oid))
                    decl = self.fresh_decls.get(name)
                    need(decl is not None and decl["kind"] == "theorem" and self.target.references_theorem(decl,ob.lean_symbol),
                         "STATEMENT_MISMATCH", "exact own transfer/accepted dependency missing: " + ob.oid)
            if number == 14:
                self.once("facets",self.facets)
            return {"fresh_replay":self.observations["fresh_verification"],"exact_check":number}
        if number == 9:
            return self.once("correspondence",self.correspondence)
        if number == 16:
            claims = self.closure._claims(self.pkg)
            need([r["claim_id"] for r in claims] == [r["claim_id"] for r in self.snapshot["claims"]] and
                 all(not r["required"] or r["outcome"] == "PASS" for r in self.snapshot["claims"]), "ORPHAN_CLAIM", "current exact required graph has not passed")
            self.once("identities",self.identities)
            return {"claim_count":len(claims),"required_claims":sum(c["required"] for c in self.snapshot["claims"]),"actual_claims":self.snapshot["claims"]}
        if number == 17:
            return self.once("original_build_processes",self.original_build_processes)
        if number == 18:
            need(result["status"] == "VERIFIED" and result["strict_cli_success"] is True and result["worker_exit_code"] == 0 and
                 result["origin_audit"]["status"] == "PASS" and result["native"]["status"] == "PASS" and result["issues"] == [],
                 "STALE_OR_UNBOUND_EVIDENCE", "native/bootstrap/current closure/root/provenance do not reconcile")
            return result
        if number in (19,20):
            self.once("transport",self.transport)
            return self.once("review",self.review)
        if number == 21:
            return self.once("retained",self.retained)
        if number == 22:
            return self.once("probes",self.probes)
        if number == 23:
            for oid in GUARANTEES:
                need(result["native"]["per_obligation_outcomes"][oid]["TESTED"] == "PENDING", "SCOPE_LEAK", "optional TESTED changed")
            need(result["endpoint"] == "restricted_source" and result["tier"] == 2 and result["hidden_cases_loaded"] is False and
                 result["oracle_calls"] == 0 and result["python_runtime_campaign"] is False and result["model_identity_attested"] is False,
                 "SCOPE_LEAK", "scope/assurance changed")
            tcb = self.reads.obj(self.pkg.root / "closure/tcb.json")
            return {"actual_native_tcb":tcb,"interpretation_trust":"finite original-to-accepted correspondence is separately explicit",
                    "identity":"UNATTESTED","tokens":"unavailable","lifecycle_state_assigned":None,"excluded":["Python/CPython","extraction","compiler-machine correctness","native execution","resource guarantees","Tier3/4"]}
        if number == 24:
            _,seals = self.memo["stop_and_seal"][1]
            for key,root in (("cohort_seal",COHORT),("orchestration_seal",DRIVER)):
                need(inventory(self.reads,root,"final unchanged sealed inputs") == seals[key], "INPUT_MUTATION", "terminal input bytes changed: " + key)
            self.public_helper.freeze_plan(self.reads)
            for name,digest in self.pre["source_files"].items():
                self.reads.raw(PROJECT/name,digest,"final frozen verifier source comparison")
                self.reads.raw(REPO/name,digest,"final current generic root comparison")
            for name in ("terminal-scope-reader-008.py",SPEC_NAME,REG_NAME,ROUTE_NAME):
                self.reads.raw(HERE/name,self.binding["registered_files"][name],"final registered audit input comparison")
            reg = self.reads.obj(HERE/REG_NAME,self.binding["registered_files"][REG_NAME])
            self.reads.raw(HERE/"terminal-scope-reader-binding-schema-008.json",reg["binding_schema_sha256"],"final bound terminal argument schema")
            self.reads.raw(HERE/PRE_SCHEMA_NAME,reg["pre_route_schema_sha256"],"final bound closed pre-route schema")
            complete = self.reads.finalize()
            return {"all_bound_inputs_unchanged":True,"actual_completion":complete,"finite_checks":24,"fixed_optional_probes":9,"stop":True}
        raise Block("ORPHAN_CLAIM: unknown finite check")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal-binding",required=True)
    parser.add_argument("--terminal-binding-sha256",required=True)
    parser.add_argument("--output-dir",required=True)
    args = parser.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    sys.dont_write_bytecode = True
    reads = Reads()
    binding = reads.obj(args.terminal_binding,args.terminal_binding_sha256,"root explicit terminal binding")
    need(binding["format"] == FORMAT,"BINDING_INVALID","terminal binding format differs")
    output = strict_path(args.output_dir)
    need(output.parent == HERE and not output.exists(),"INPUT_MUTATION","output must be a new direct audit-directory child")
    registered = binding["registered_files"]
    need(set(registered) == {"terminal-scope-reader-008.py",SPEC_NAME,REG_NAME,ROUTE_NAME},"VERIFIER_MISMATCH","registered reader membership differs")
    for name,digest in registered.items():
        reads.raw(HERE/name,digest,"exact registered finite terminal reader/specification/registration")
    specification = reads.obj(HERE/SPEC_NAME)
    registration = reads.obj(HERE/REG_NAME)
    qualification_definition(specification)
    transport_field_identity(specification["transport_trace"],registration["transport_evidence_representation"])
    metadata_inventory = reads.obj(HERE/"terminal-metadata-interface-inventory-008.json",
        registration["metadata_interfaces"]["inventory"]["sha256"],"registered frozen producer/consumer metadata inventories")
    metadata_field_identity(specification["metadata_interfaces"],registration["metadata_interfaces"],metadata_inventory)
    need(plain_hash(registration["verifier_sha256"]) == plain_hash(registered["terminal-scope-reader-008.py"]) and
         plain_hash(registration["specification_sha256"]) == plain_hash(registered[SPEC_NAME]),"VERIFIER_MISMATCH","registration identity differs")
    install_binding_schemas(
        reads.obj(HERE/FINAL_SCHEMA_NAME,registration["binding_schema_sha256"],"bound terminal argument schema"),
        reads.obj(HERE/PRE_SCHEMA_NAME,registration["pre_route_schema_sha256"],"bound closed pre-route argument schema"))
    validate_schema(binding, FINAL_SCHEMA, "final")
    need(set(binding) == set(specification["terminal_binding_fields"]),"BINDING_INVALID","terminal binding field set differs")
    checks = reads.obj(HERE/"planned-evidence-checks.json","bf8b6e688722311b9d1d775d0874d6a4aaf49237476405085babece910c7d8fc")["checks"]
    need([c["id"] for c in checks] == [f"AUD-{n:02d}" for n in range(1,25)],"CLAIM_MUTATION","original check membership differs")
    output.mkdir()
    reads.archive_root = output / "ephemeral-verification-reads"
    audit = Audit(reads,binding,output)
    audit.binding_ref = {"path":str(strict_path(args.terminal_binding)),"sha256":"sha256:"+plain_hash(args.terminal_binding_sha256)}
    sys.addaudithook(reads.hook)
    reads.enable_hook = True
    rows = []
    for number,check in enumerate(checks,1):
        try:
            evidence = audit.evaluate(number)
            row = {**check,"status":"VERIFIED","actual_evidence":evidence,"blocking_reasons":[]}
        except Exception as exc:
            diagnostics = getattr(exc,"diagnostics",[])
            infrastructure = any(getattr(d,"severity",None) == "infrastructure" for d in diagnostics)
            expected = isinstance(exc,(Block,KeyError,ValueError,TypeError,IndexError)) or bool(diagnostics) or type(exc).__name__ in {
                "Block","InvalidPackage","DSLError","SourceError","BridgeInvalid","BridgeUnsupported","Unsupported"}
            state = "INFRASTRUCTURE_FAILURE" if infrastructure or not expected else "BLOCKED"
            row = {**check,"status":state,"actual_evidence":None,"blocking_reasons":[type(exc).__name__ + ": " + str(exc)]}
        rows.append(row)
    # AUD24 must close every actual input even if a prerequisite check blocked
    # its normal route. This never repairs or promotes a prerequisite outcome.
    if not reads.finalized:
        try:
            audit.observations["completion_bound_inputs"] = reads.finalize()
        except Exception as exc:
            audit.observations["completion_bound_inputs"] = getattr(reads,"final_summary",None)
            rows[-1]["status"] = "BLOCKED" if isinstance(exc,Block) else "INFRASTRUCTURE_FAILURE"
            rows[-1]["blocking_reasons"].append(type(exc).__name__ + ": " + str(exc))
    status = "VERIFIED" if all(r["status"] == "VERIFIED" for r in rows) else "INFRASTRUCTURE_FAILURE" if any(r["status"] == "INFRASTRUCTURE_FAILURE" for r in rows) else "BLOCKED"
    code = 0 if status == "VERIFIED" else 3 if status == "INFRASTRUCTURE_FAILURE" else 2
    report = {"format":"verislop.d21-terminal-scope-report/8","audit_id":AUDIT_ID,"status":status,
              "source_root":SOURCE_ROOT,"qualification_input_root":QUALIFICATION_ROOT,
              "preregistration_input_root_hash":binding["preregistration_input_root_hash"],
              "terminal_binding_sha256":"sha256:"+plain_hash(args.terminal_binding_sha256),
              "registered_files":registered,"checks":rows,"observations":audit.observations,
              "decision":{"exit_code":code,"manual_override_allowed":False,"exact_required_check_count":24},
              "scope":"original full-domain D21 delivery contract at Tier2 restricted_source",
              "identity":"UNATTESTED","tokens":"unavailable","lifecycle_state_assigned":None,
              "optional_TESTED":"PENDING","new_model_calls":0,"new_task_generation_or_repairs":0,
              "public_probe_invocations_by_reader":0,"stop_rule":"finite original24 evaluated; STOP"}
    report_hash = publish(output/"report.json",report)
    reads.enable_hook = False
    ledger_hash = publish(output/"read-ledger.json",{"format":"verislop.d21-terminal-read-ledger/1","audit_id":AUDIT_ID,"reads":reads.rows})
    publish(output/"invocation-observation.json",{"argv":sys.argv,"cwd":str(Path.cwd()),"pid":os.getpid(),
             "started_at_utc":started,"ended_at_utc":datetime.now(timezone.utc).isoformat(),
             "decision_exit_code":code,"actual_completed_process_returncode":None,
             "report_sha256":report_hash,"read_ledger_sha256":ledger_hash,
             "provenance":"caller independently captures actual completed numeric process returncode; this in-process record is not that receipt"})
    print(json.dumps({"status":status,"decision_exit_code":code,"report":str(output/"report.json"),"sha256":report_hash},sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
