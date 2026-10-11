"""Prepared only: materialize an unrelated fixture after root review/freeze.

This program makes no model/tool-channel calls and performs no qualification.
It does not read any task/native/artifact input.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CANDIDATE_PATH = HERE.parents[1] / "validation/tier2-carrier-context-support-019-implementation-004/bootstrap_tier2_carrier_view.py"

ATOM = 'Aé🙂e\u0301\u2028\x00\t\r\n\\"/'
MARKERS = (
    "UNRELATED_019_003_START",
    "UNRELATED_019_003_MIDDLE_A",
    "UNRELATED_019_003_MIDDLE_B",
    "UNRELATED_019_003_FINAL_TAIL",
)
SYSTEM = (
    "This is a finite unrelated transport fixture. Inspect the complete original system field and complete original "
    "user field through explicit EOF. Return only one syntactically valid JSON object with keys markers, field_roots, "
    "field_eof and field_chars. markers is the ordered list of every distinct complete marker label beginning "
    "UNRELATED_019_003_ in the user field, excluding adjacent whitespace or Unicode scalars. field_roots maps /system and "
    "/user to sha256: followed by the SHA-256 hex digest of each complete reconstructed decoded field encoded as strict "
    "UTF-8. field_eof maps those selectors to the observed explicit EOF boolean. field_chars maps those selectors to "
    "the exact decoded Unicode code point count. Compute from your own original field views in memory only. Preserve "
    "the requested literal JSON response. This fixture grants no semantic, proof, review or lifecycle authority."
)


def pack(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def fixture():
    user = (MARKERS[0] + "\n" + ATOM * 11000
            + "\n" + MARKERS[1] + "\n" + ATOM * 11000
            + "\n" + MARKERS[2] + "\n" + ATOM * 11000
            + "\n" + MARKERS[3] + "🙂\t ")
    if len(user) < 400000:
        raise ValueError("UNRELATED_FIXTURE_TOO_SMALL")
    return SYSTEM, user


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-reviewed-frozen-manifest", type=Path, required=True)
    parser.add_argument("--root-authorized-materialization", action="store_true", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if not output.is_relative_to(HERE) or output == HERE or output.exists():
        raise ValueError("NEW_OWN_VALIDATION_OUTPUT_DIRECTORY_REQUIRED")
    frozen = json.loads(args.root_reviewed_frozen_manifest.read_text())
    candidate_path = CANDIDATE_PATH
    candidate_sha = digest(candidate_path.read_bytes())
    if (frozen.get("status") != "ROOT_REVIEWED_FROZEN_CANDIDATE"
            or frozen.get("revision") != "004"
            or frozen.get("activation_authority") is not False
            or frozen.get("candidate_sha256") != candidate_sha):
        raise ValueError("ROOT_REVIEWED_CANDIDATE_FREEZE_REQUIRED")
    spec = importlib.util.spec_from_file_location("unrelated_frozen_carrier_candidate", candidate_path)
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    system, user = fixture()
    request = {"format": "verislop.unrelated-carrier-smoke-request/2",
               "request_id": "unrelated-carrier-context019-003-001", "system": system, "user": user}
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
    expected = {"markers": list(MARKERS),
                "field_roots": {"/system": digest(system.encode()), "/user": digest(user.encode())},
                "field_eof": {"/system": True, "/user": True},
                "field_chars": {"/system": len(system), "/user": len(user)}}
    (output / "original-unrelated-request.json").write_bytes(request_raw)
    (output / "reference.json").write_bytes(pack(reference))
    (output / "fixture-only-expected.json").write_bytes(pack(expected))
    (output / "fresh-author-exact-message.txt").write_text(candidate.agent_message(reference))
    (output / "first-functions-exec.js").write_text(candidate.initial_session_template(reference))
    (output / "next-functions-exec.js").write_text(candidate.next_session_template(reference))
    empty_request = {"format": "verislop.unrelated-carrier-smoke-request/2",
                     "request_id": "unrelated-carrier-context019-003-empty", "system": "", "user": ""}
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
        "revision": "004",
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
        "markers": list(MARKERS),
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
