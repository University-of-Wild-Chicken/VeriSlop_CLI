"""Prepared only: materialize an unrelated fixture after root review/freeze.

This program makes no model/tool-channel calls and performs no qualification.
It does not read any task/native/artifact input.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from synthetic_dataset.tools import bootstrap_tier2_runtime_integration as runtime_integration


HERE = Path(__file__).resolve().parent
# Legacy carrier source and the compact deployment are explicit registered CLI inputs.

ATOM = 'Aé🙂e\u0301\u2028\x00\t\r\n\\"/'
MARKERS = (
    "UNRELATED_019_005_START",
    "UNRELATED_019_005_MIDDLE_A",
    "UNRELATED_019_005_MIDDLE_B",
    "UNRELATED_019_005_FINAL_TAIL",
)
SYSTEM = 'This is a finite unrelated transport fixture. Inspect the complete original system field and complete original user field through explicit EOF. Return only one syntactically valid JSON object with keys markers, field_roots, field_eof and field_chars. markers is the ordered list of every distinct complete marker label beginning UNRELATED_019_005_ in the user field, excluding adjacent whitespace or Unicode scalars. field_roots maps /system and /user to sha256: followed by the SHA-256 hex digest of each complete reconstructed decoded field encoded as strict UTF-8. field_eof maps those selectors to the observed explicit EOF boolean. field_chars maps those selectors to the exact decoded Unicode code point count. Compute from your own original field views in memory only. Preserve the requested literal JSON response. This fixture grants no semantic, proof, review or lifecycle authority. If a concrete observed protocol failure prevents completion, this fixture SYSTEM explicitly permits the following self-contained diagnostic branch. It is evidence only, unsuccessful, and grants zero claim authority. Preserve only actual observed partial fields, never invent roots, EOF, markers or errors. When the gate-fixture SYSTEM permits diagnostic failure, return the four ordinary fields with only your actual available partial values and exactly one additional failure object. Its exact keys are format, trust, stage, operation, observation, reproduction, self_critique. Set format="verislop.author-observed-failure/0.1" and trust="UNATTESTED". Stage is one of FIRST_INVENTORY, NEXT_SYSTEM, NEXT_USER, CONFIRM, HASH, FINAL_ASSEMBLY, UNKNOWN; it describes your reported attempt, never attested execution. Do not infer a stopped operation from incomplete EOF alone. Unknown observations use UNKNOWN/null rather than invented cursors or causes.\noperation is null or exactly {chunk_id,selector,start_char,output_cap_bytes,metadata_reserve_bytes}, with each value nullable when unavailable. A present chunk_id is a nonempty actually observed string; selector is /system or /user; start_char counts decoded Unicode code points and is an exact nonnegative safe integer; present cap/reserve retain the existing integer bounds and reserve<cap. observation is exactly {kind:"literal",source,text,scope} or {kind:"reference",source,reference,scope} or {kind:"unavailable",reason}. source is NESTED_ACTUAL_RESULT, OUTER_ACTUAL_RESPONSE, PURE_EXCEPTION_RESPONSE or OWN_VISIBLE_PROTOCOL_STATE. text is the exact already visible error/output or smallest sufficient exact observed fragment; scope is complete or visible_fragment, without promoting a fragment to complete. reference is exactly {path,sha256,byte_count} for an already exposed ref, never a future file/hash or hidden ID. Unavailable reason is NOT_EXPOSED or NOT_RETAINED.\nreproduction is exactly {template,view,confirmation,own_input_literal,expected_observed_error_literal,availability}. template is FIRST, NEXT, CONFIRM, HASH, FINAL_SCHEMA or UNAVAILABLE. view and confirmation are the unchanged closed VIEW/CONFIRM or null. The two literals are exact already observed own data/error or null; availability is PROVIDED or UNAVAILABLE. Supply the smallest available concrete fixed-template operation/input for the reported check, without claiming global minimality or inventing a synthetic checkpoint. self_critique is exactly {violated_check,own_attempted_retry,observed_retry_error_literal,recovery}. Its check/error literals are exact observed strings or null, retry is a permitted closed VIEW/CONFIRM or null, and recovery is RECOVERABLE_ALLOWED_VALUES, FIXED_SOURCE_BLOCKED or UNAVAILABLE. All strings/integers/bools retain their actual types; these literals are data, not executable code.\n CLOSED REPRODUCTION CONSISTENCY: PROVIDED requires a non-UNAVAILABLE template and nonempty exact expected observed error. FIRST requires inventory VIEW; NEXT requires field VIEW; both have null confirmation. CONFIRM requires its exact confirmation, null VIEW and nonempty exact own input. HASH/FINAL_SCHEMA require null VIEW/confirmation and nonempty exact own input. Unavailable necessary inputs mean availability=UNAVAILABLE; partial known data cannot claim executable sufficiency. UNKNOWN stage or unavailable observation means stage UNKNOWN, operation null, critique check/retry/error null, recovery UNAVAILABLE and reproduction availability UNAVAILABLE. Never infer missing details. These closed shape relations establish no actual observation, execution, historical cause or success. Partial-result markers is an ordered list of nonempty strings; field_roots is a subset of /system and /user with strict sha256: plus 64 lowercase hexadecimal digests; field_eof contains both selectors with exact booleans; field_chars contains both selectors with nonnegative exact safe integers. Every string must encode as strict UTF-8; reject duplicate keys, a BOM, floats, nonfinite values and integers beyond JavaScript safe integer range. The exact failure grammar here governs only this unrelated fixture; permitted compact runtime operations and recovery remain those in the fixed outer protocol. A diagnostic response never satisfies successful completion.'


def pack(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def fixture(markers=MARKERS, system=SYSTEM):
    user = (markers[0] + "\n" + ATOM * 11000
            + "\n" + markers[1] + "\n" + ATOM * 11000
            + "\n" + markers[2] + "\n" + ATOM * 11000
            + "\n" + markers[3] + "🙂\t ")
    if len(user) < 400000:
        raise ValueError("UNRELATED_FIXTURE_TOO_SMALL")
    return system, user


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-reviewed-frozen-manifest", type=Path, required=True)
    parser.add_argument("--root-authorized-materialization", action="store_true", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--legacy-carrier-file", type=Path, required=True)
    parser.add_argument("--runtime-deployment-root", type=Path, required=True)
    parser.add_argument("--fixture-registration", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if not output.is_relative_to(HERE) or output == HERE or output.exists():
        raise ValueError("NEW_OWN_VALIDATION_OUTPUT_DIRECTORY_REQUIRED")
    frozen = json.loads(args.root_reviewed_frozen_manifest.read_text())
    candidate_path = args.legacy_carrier_file.absolute()
    registration = json.loads(args.fixture_registration.read_text())
    if set(registration) != {"legacy_revision", "fixture_revision", "marker_prefix", "request_id", "empty_request_id"} or not all(type(v) is str and v for v in registration.values()):
        raise ValueError("EXACT_FRESH_FIXTURE_REGISTRATION_REQUIRED")
    if not registration["marker_prefix"].endswith("_") or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789" for c in registration["marker_prefix"]):
        raise ValueError("FRESH_MARKER_PREFIX_INVALID")
    markers = tuple(registration["marker_prefix"] + suffix for suffix in ("START", "MIDDLE_A", "MIDDLE_B", "FINAL_TAIL"))
    system_text = SYSTEM.replace("UNRELATED_019_005_", registration["marker_prefix"])
    deployment = args.runtime_deployment_root.absolute()
    runtime_registration = runtime_integration.delivery_registration(deployment)
    if runtime_registration is None or frozen.get("runtime_registration") != runtime_registration:
        raise ValueError("ROOT_REVIEWED_RUNTIME_REGISTRATION_REQUIRED")
    runtime_descriptor = runtime_integration.load_registration(deployment)
    candidate_sha = digest(candidate_path.read_bytes())
    if (frozen.get("status") != "ROOT_REVIEWED_FROZEN_CANDIDATE"
            or frozen.get("revision") != registration["legacy_revision"]
            or frozen.get("activation_authority") is not False
            or frozen.get("candidate_sha256") != candidate_sha):
        raise ValueError("ROOT_REVIEWED_CANDIDATE_FREEZE_REQUIRED")
    spec = importlib.util.spec_from_file_location("unrelated_frozen_carrier_candidate", candidate_path)
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    system, user = fixture(markers, system_text)
    request = {"format": "verislop.unrelated-carrier-smoke-request/2",
               "request_id": registration["request_id"], "system": system, "user": user}
    request_raw = pack(request)
    carrier = {"format": "verislop.collaboration-carrier/0.1",
               "request_id": request["request_id"], "request_sha256": digest(request_raw),
               "system": system, "user": user}
    carrier_raw = pack(carrier)
    output.mkdir()
    carrier_path = output / "own-unrelated-carrier.json"
    carrier_path.write_bytes(carrier_raw)
    reference = {"path": str(carrier_path), "sha256": digest(carrier_raw),
                 "request_sha256": carrier["request_sha256"]}
    expected = {"markers": list(markers),
                "field_roots": {"/system": digest(system.encode()), "/user": digest(user.encode())},
                "field_eof": {"/system": True, "/user": True},
                "field_chars": {"/system": len(system), "/user": len(user)}}
    (output / "original-unrelated-request.json").write_bytes(request_raw)
    (output / "reference.json").write_bytes(pack(reference))
    (output / "fixture-only-expected.json").write_bytes(pack(expected))
    session_directory = output / "runtime020-own-sessions"
    session_directory.mkdir(mode=0o700)
    (output / "fresh-author-exact-message.txt").write_text(runtime_integration.compact_message(
        deployment, runtime_descriptor, reference, str(session_directory)))
    (output / "first-functions-exec.js").write_text(candidate.initial_session_template(reference))
    (output / "next-functions-exec.js").write_text(candidate.next_session_template(reference))
    empty_request = {"format": "verislop.unrelated-carrier-smoke-request/2",
                     "request_id": registration["empty_request_id"], "system": "", "user": ""}
    empty_request_raw = pack(empty_request)
    empty_carrier = {"format": "verislop.collaboration-carrier/0.1",
                     "request_id": empty_request["request_id"], "request_sha256": digest(empty_request_raw),
                     "system": "", "user": ""}
    empty_carrier_raw = pack(empty_carrier)
    empty_path = output / "own-unrelated-empty-carrier.json"
    empty_path.write_bytes(empty_carrier_raw)
    empty_reference = {"path": str(empty_path), "sha256": digest(empty_carrier_raw),
                       "request_sha256": empty_carrier["request_sha256"]}
    (output / "original-unrelated-empty-request.json").write_bytes(empty_request_raw)
    (output / "empty-reference.json").write_bytes(pack(empty_reference))
    (output / "empty-first-functions-exec.js").write_text(candidate.initial_session_template(empty_reference))
    (output / "empty-next-system-functions-exec.js").write_text(candidate.next_session_template(empty_reference))
    (output / "empty-next-user-functions-exec.js").write_text(candidate.next_session_template(empty_reference, {
        "operation": "field", "selector": "/user", "start_char": 0,
        "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048,
    }))
    (output / "preexecution-registration.json").write_bytes(pack({
        "format": "verislop.unrelated-carrier-context-registration/2",
        "revision": registration["fixture_revision"],
        "runtime_registration": runtime_registration,
        "runtime_source_files": runtime_descriptor["source_files"],
        "fixture_registration_sha256": digest(args.fixture_registration.read_bytes()),
        "status": "PREPARED_NOT_EXECUTED",
        "candidate_sha256": candidate_sha,
        "root_reviewed_frozen_manifest_sha256": digest(args.root_reviewed_frozen_manifest.read_bytes()),
        "reference": reference,
        "empty_reference": empty_reference,
        "expected_empty_field_roots": {"/system": digest(b""), "/user": digest(b"")},
        "expected_empty_field_chars": {"/system": 0, "/user": 0},
        "expected_empty_field_eof": {"/system": True, "/user": True},
        "fixture_user_chars": len(user),
        "fixture_user_utf8_bytes": len(user.encode()),
        "markers": list(markers),
        "expected_field_roots": expected["field_roots"],
        "expected_reply_sha256": digest(pack(expected)),
        "fixture_expected_is_evaluator_only": True,
        "fresh_author_model": "gpt-6.1-sol",
        "fresh_author_fork_turns": "none",
        "fresh_author_exact_count": 1,
        "fresh_author_case": "FA002-001",
        "actual_channel_cases": ["AC002-001", "AC002-002", "AC002-003", "AC002-004"],
        "previous001_reused": False,
        "author_inspection_assertion_status": "UNATTESTED",
        "actual_channel_executions": [],
        "model_calls": [],
        "activation_authority": False,
    }))


if __name__ == "__main__":
    main()
