#!/usr/bin/env python3
"""Finite comparison of retained actual exec_command returns; never run a viewer.

This checker verifies syntactic channel availability under the declared
orchestration trust. It cannot attest LLM consumption or semantic review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


FIELDS = {
    "format", "status", "carrier_path", "carrier_raw_bytes", "carrier_sha256",
    "request_sha256", "request_id", "char_unit", "byte_unit",
    "output_cap_bytes", "metadata_reserve_bytes", "operation", "selector",
    "field_chars", "field_utf8_bytes", "start_char", "end_char",
    "start_utf8_byte", "end_utf8_byte", "content_chars", "content_utf8_bytes",
    "content", "next_char", "field_eof",
}


class Block(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise Block(code)


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def wire(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8", "strict")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def parse(data):
    try:
        return json.loads(data.decode("utf-8", "strict"),
                          object_pairs_hook=unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(Block("NONFINITE_JSON")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Block("INVALID_RECEIVED_JSON") from exc


def regular(root, name, expected):
    require(isinstance(name, str), "INVALID_ARTIFACT_PATH")
    relative = Path(name)
    require(not relative.is_absolute() and relative.as_posix() == name
            and ".." not in relative.parts, "INVALID_ARTIFACT_PATH")
    path = root / relative
    require(path.is_file() and not path.is_symlink()
            and path.resolve() == path.absolute(), "MISSING_OR_INDIRECT_ARTIFACT")
    data = path.read_bytes()
    require(sha(data) == expected, "STALE_OR_UNBOUND_EVIDENCE")
    return data


def integer(value, code):
    require(type(value) is int and value >= 0, code)
    return value


def expected_record(case, carrier_raw):
    carrier = parse(carrier_raw)
    require(type(carrier) is dict, "INVALID_SYNTHETIC_CARRIER")
    selector = case["selector"]
    require(selector in ("/system", "/user"), "INVALID_SELECTOR")
    text = carrier.get(selector[1:])
    require(type(text) is str, "INVALID_FIXTURE_FIELD")
    encoded = text.encode("utf-8", "strict")
    start = integer(case["start_char"], "INVALID_START_CURSOR")
    require(start <= len(text), "INVALID_START_CURSOR")
    cap = integer(case["output_cap_bytes"], "INVALID_CAP")
    reserve = integer(case["metadata_reserve_bytes"], "INVALID_RESERVE")
    require(cap > reserve > 0, "INVALID_CAP_RESERVE")
    require(sha(carrier_raw) == case["expected_carrier_sha256"], "CARRIER_IDENTITY_MISMATCH")
    require(carrier.get("request_sha256") == case["expected_request_sha256"], "REQUEST_METADATA_MISMATCH")
    require(type(carrier.get("request_id")) is str, "INVALID_REQUEST_ID")
    prefix_bytes = len(text[:start].encode("utf-8", "strict"))

    def record(end):
        content = text[start:end]
        return {
            "format": "verislop.exact-carrier-view/0.1", "status": "ok",
            "carrier_path": case["literal_carrier_path"],
            "carrier_raw_bytes": len(carrier_raw), "carrier_sha256": sha(carrier_raw),
            "request_sha256": carrier["request_sha256"], "request_id": carrier["request_id"],
            "char_unit": "decoded_unicode_code_points", "byte_unit": "decoded_field_utf8",
            "output_cap_bytes": cap, "metadata_reserve_bytes": reserve,
            "operation": "field", "selector": selector,
            "field_chars": len(text), "field_utf8_bytes": len(encoded),
            "start_char": start, "end_char": end, "start_utf8_byte": prefix_bytes,
            "end_utf8_byte": prefix_bytes + len(content.encode("utf-8", "strict")),
            "content_chars": len(content), "content_utf8_bytes": len(content.encode("utf-8", "strict")),
            "content": content, "next_char": end, "field_eof": end == len(text),
        }

    def fits(end):
        value = record(end)
        metadata = dict(value, content="")
        token = json.dumps(value["content"], sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"), allow_nan=False).encode("utf-8", "strict")
        return (len(wire(metadata)) <= reserve
                and len(token) <= cap - reserve and len(wire(value)) <= cap)

    # The exact final endpoint has a one-byte shorter EOF header. It can fit
    # when an earlier non-final header does not, so test it before assuming
    # the remaining non-final predicates are monotone.
    if fits(len(text)):
        return record(len(text)), text
    require(fits(start), "METADATA_RESERVE_EXCEEDED")
    low, high = start, max(start, len(text) - 1)
    while low < high:
        middle = (low + high + 1) // 2
        if fits(middle):
            low = middle
        else:
            high = middle - 1
    require(low > start or start == len(text), "NO_CHARACTER_FITS")
    return record(low), text


def evaluate(args):
    root = args.capture_root.absolute()
    index_raw = regular(root, args.index, args.index_sha256)
    index = parse(index_raw)
    case_plan = parse(regular(root, args.frozen_case_plan, args.frozen_case_plan_sha256))
    require(case_plan.get("format") == "verislop.carrier-channel-case-plan/1", "CASE_PLAN_SCHEMA_MISMATCH")
    require(index.get("format") == "verislop.carrier-channel-capture/1", "CAPTURE_SCHEMA_MISMATCH")
    for key, expected in (("closure_id", args.closure_id),
                          ("input_root_hash", args.input_root_hash),
                          ("source_root_hash", args.source_root_hash),
                          ("producer_implementation_hash", args.producer_hash),
                          ("channel_orchestrator_hash", args.orchestrator_hash)):
        require(index.get(key) == expected, "STALE_OR_UNBOUND_EVIDENCE")
    require(index.get("execution_channel") == "functions.tools.exec_command", "WRONG_CHANNEL")
    require(index.get("forwarding_contract") == "text(entire_actual_tool_result)", "MISSING_FORWARD_CONTRACT")
    cases = index.get("cases")
    require(type(cases) is list and cases, "CHANNEL_NOT_TESTED")
    require(len(cases) <= 64, "UNREGISTERED_CHANNEL_CASE_COUNT")
    require(len({case["id"] for case in cases}) == len(cases), "DUPLICATE_CASE_ID")
    frozen_cases = case_plan.get("cases")
    require(type(frozen_cases) is list and len(frozen_cases) == len(cases), "CASE_REGISTRATION_MISMATCH")
    require([case["id"] for case in cases] == [case["id"] for case in frozen_cases], "CASE_REGISTRATION_MISMATCH")
    for actual_case, frozen_case in zip(cases, frozen_cases):
        require(all(actual_case.get(key) == value for key, value in frozen_case.items()), "CASE_PLAN_MUTATION")
    expected_ids = case_plan.get("required_case_ids")
    require(type(expected_ids) is list and set(expected_ids) <= {case["id"] for case in cases}, "CONTROL_NOT_RUN")
    results, completed, truncations = [], {}, {}
    for case in cases:
        require(case.get("exit_code_expected") == 0, "UNDECLARED_EXIT_MAPPING")
        require(case.get("expected_delivery") in ("intact", "truncated"), "UNREGISTERED_DISPOSITION")
        carrier_raw = regular(root, case["carrier_ref"], case["carrier_ref_sha256"])
        expected, original = expected_record(case, carrier_raw)
        emitted = regular(root, case["expected_stdout_ref"], case["expected_stdout_sha256"])
        require(emitted == wire(expected), "EMITTED_RECORD_MISMATCH")
        actual_raw = regular(root, case["actual_tool_result_ref"], case["actual_tool_result_sha256"])
        actual = parse(actual_raw)
        require(type(actual) is dict and actual.get("exit_code") == 0
                and actual.get("session_id") is None, "CHANNEL_PROCESS_INCOMPLETE")
        require(type(actual.get("output")) is str, "MISSING_ACTUAL_OUTPUT")
        require(case.get("forwarded_tool_result_sha256") == sha(actual_raw), "FORWARDED_RESULT_MISMATCH")
        received = actual["output"].encode("utf-8", "strict")
        is_intact = received == emitted
        if case["expected_delivery"] == "truncated":
            require(case["max_output_tokens"] == 100, "LOW_BUDGET_CONTROL_MISMATCH")
            require(case["output_cap_bytes"] == 8192 and case["metadata_reserve_bytes"] == 2048,
                    "LOW_BUDGET_CONTROL_MISMATCH")
            require(not is_intact, "TRUNCATION_CONTROL_NOT_DETECTED")
            # Output inequality could instead be corruption or another failure.
            # Use the retained structured tool truncation evidence when it is
            # supplied; never promote an arbitrary mismatch to a clip control.
            explicit_flags = [actual[key] for key in ("output_truncated", "truncated")
                              if key in actual]
            require(all(type(value) is bool for value in explicit_flags), "INVALID_TOOL_TRUNCATION_FLAG")
            require(not explicit_flags or all(explicit_flags), "TOOL_DID_NOT_REPORT_TRUNCATION")
            count = actual.get("original_token_count")
            if count is not None:
                require(type(count) is int and count >= 0, "INVALID_TOOL_ORIGINAL_TOKEN_COUNT")
                require(count > case["max_output_tokens"], "TOOL_DID_NOT_REPORT_TRUNCATION")
            require(bool(explicit_flags) or count is not None, "MISSING_EXPLICIT_TOOL_TRUNCATION_EVIDENCE")
            require(case.get("accepted_next_char") is None, "TRUNCATED_ADVANCEMENT")
            require(case.get("retry_case_id") is not None, "MISSING_SAME_START_RETRY")
            truncations[case["id"]] = case
            results.append({"case_id": case["id"], "status": "PASS", "delivery": "truncated",
                            "actual_tool_result_sha256": sha(actual_raw), "received_bytes": len(received),
                            "tool_original_token_count": count, "tool_truncation_flags": explicit_flags})
            continue
        require(case["max_output_tokens"] == 16384, "INTACT_BUDGET_MISMATCH")
        require(is_intact, "CHANNEL_BYTES_DIFFER_FROM_EMISSION")
        parsed = parse(received)
        require(set(parsed) == FIELDS and parsed == expected, "RECEIVED_RECORD_MISMATCH")
        require(received == wire(parsed), "NONCANONICAL_RESPONSE_WIRE")
        require(case.get("accepted_next_char") == expected["next_char"], "CURSOR_ACCEPTANCE_MISMATCH")
        key = (case["expected_carrier_sha256"], case["selector"])
        completed.setdefault(key, {"original": original, "intervals": []})["intervals"].append(
            (expected["start_char"], expected["end_char"], expected["content"], expected["field_eof"]))
        metadata = len(wire(dict(expected, content="")))
        token = len(json.dumps(expected["content"], ensure_ascii=False,
                               separators=(",", ":"), allow_nan=False).encode("utf-8", "strict"))
        results.append({"case_id": case["id"], "status": "PASS", "delivery": "intact",
                        "response_wire_bytes": len(received), "metadata_wire_bytes": metadata,
                        "content_json_token_bytes": token, "actual_tool_result_sha256": sha(actual_raw)})
    by_id = {case["id"]: case for case in cases}
    for prior in truncations.values():
        retry = by_id.get(prior["retry_case_id"])
        require(retry is not None and retry["expected_delivery"] == "intact", "MISSING_SAME_START_RETRY")
        for field in ("expected_carrier_sha256", "expected_request_sha256", "literal_carrier_path", "selector", "start_char"):
            require(retry[field] == prior[field], "RETRY_SNAPSHOT_OR_CURSOR_CHANGED")
        require(retry["output_cap_bytes"] == 4096 and retry["metadata_reserve_bytes"] == 2048
                and retry["max_output_tokens"] == 16384, "RETRY_BOUND_MISMATCH")
    required_fields = case_plan.get("required_complete_fields")
    require(type(required_fields) is list, "MISSING_RECONSTRUCTION_REGISTRATION")
    reconstructions = []
    for row in required_fields:
        key = (row["carrier_sha256"], row["selector"])
        require(key in completed, "MISSING_COMPLETE_FIELD")
        value = completed[key]
        original, intervals = value["original"], sorted(value["intervals"])
        cursor, reconstructed, eof = 0, "", False
        for start, end, content, final in intervals:
            require(start <= cursor, "RECONSTRUCTION_GAP")
            require(content == original[start:end], "RECONSTRUCTION_MISMATCH")
            if end > cursor:
                reconstructed += content[cursor-start:]
                cursor = end
            eof = eof or (final and end == len(original))
        require(cursor == len(original) and reconstructed == original and eof,
                "MISSING_TAIL_OR_EMPTY_EOF")
        reconstructions.append({"carrier_sha256": key[0], "selector": key[1],
                                "field_chars": len(original),
                                "field_utf8_sha256": sha(original.encode("utf-8", "strict"))})
    require(truncations, "CONTROL_NOT_RUN")
    return {"cases": results, "complete_fields": reconstructions,
            "truncation_controls": len(truncations), "llm_consumption_attested": False,
            "accept_or_lifecycle_authority": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", type=Path, required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--index-sha256", required=True)
    parser.add_argument("--frozen-case-plan", required=True)
    parser.add_argument("--frozen-case-plan-sha256", required=True)
    parser.add_argument("--closure-id", required=True)
    parser.add_argument("--input-root-hash", required=True)
    parser.add_argument("--source-root-hash", required=True)
    parser.add_argument("--producer-hash", required=True)
    parser.add_argument("--orchestrator-hash", required=True)
    args = parser.parse_args()
    envelope = {"schema_version": "1.0", "closure_id": args.closure_id,
                "claim_id": "Q018-06", "input_root_hash": args.input_root_hash,
                "source_root_hash": args.source_root_hash, "verifier_id": "V018-CHANNEL-RECORDS",
                "verifier_hash": sha(Path(__file__).read_bytes()),
                "execution_environment": {"python": sys.version, "platform": sys.platform},
                "raw_result_ref": args.index, "raw_result_hash": args.index_sha256}
    try:
        envelope.update(status="PASS", exit_code=0, raw_result=evaluate(args))
    except (Block, KeyError, TypeError, UnicodeError) as exc:
        envelope.update(status="BLOCK", exit_code=1,
                        raw_result={"blocking_code": str(exc) or type(exc).__name__})
    except (OSError, RuntimeError) as exc:
        envelope.update(status="INFRASTRUCTURE_FAILURE", exit_code=2,
                        raw_result={"infrastructure_error": str(exc)})
    print(json.dumps(envelope, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return envelope["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
