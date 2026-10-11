"""Closed reported-failure syntax only; no success, provenance or cause authority."""
import hashlib
import json
import re

MAX_SAFE_INTEGER = 2**53 - 1
SUCCESS_KEYS = {"markers", "field_roots", "field_eof", "field_chars"}
STAGES = {"FIRST_INVENTORY", "NEXT_SYSTEM", "NEXT_USER", "CONFIRM", "HASH", "CHECKPOINT", "FINAL_ASSEMBLY", "UNKNOWN"}
SOURCES = {"NESTED_ACTUAL_RESULT", "OUTER_ACTUAL_RESPONSE", "PURE_EXCEPTION_RESPONSE", "OWN_VISIBLE_PROTOCOL_STATE"}


class DiagnosticSchemaError(ValueError):
    """A reported diagnostic fails this evidence-only closed schema."""


def _need(condition, code):
    if not condition:
        raise DiagnosticSchemaError(code)


def _keys(value, expected, code):
    _need(type(value) is dict and set(value) == set(expected), code)


def _string(value, code, *, nonempty=False):
    _need(type(value) is str and (not nonempty or bool(value)), code)
    try:
        value.encode("utf-8", "strict")
    except UnicodeError as error:
        raise DiagnosticSchemaError("INVALID_UNICODE") from error


def _integer(value, code, *, low=0, high=MAX_SAFE_INTEGER):
    _need(type(value) is int and low <= value <= high, code)


def _enum(value, permitted, code):
    _need(type(value) is str and value in permitted, code)


def _nullable_string(value, code, *, nonempty=False):
    if value is not None:
        _string(value, code, nonempty=nonempty)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _need(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _number(_value):
    raise DiagnosticSchemaError("UNSUPPORTED_JSON_NUMBER")


def _parsed_integer(value):
    _need(len(value.lstrip("-")) <= 16, "UNSAFE_JSON_INTEGER")
    number = int(value)
    _need(abs(number) <= MAX_SAFE_INTEGER, "UNSAFE_JSON_INTEGER")
    return number


def _unicode(value):
    if type(value) is str:
        _string(value, "INVALID_STRING")
    elif type(value) is list:
        for item in value:
            _unicode(item)
    elif type(value) is dict:
        for key, item in value.items():
            _string(key, "INVALID_KEY")
            _unicode(item)


def _load(raw):
    _need(type(raw) in (bytes, str), "INVALID_RAW_TYPE")
    try:
        data = raw if type(raw) is bytes else raw.encode("utf-8", "strict")
        text = data.decode("utf-8", "strict")
    except UnicodeError as error:
        raise DiagnosticSchemaError("INVALID_UTF8") from error
    _need(not text.startswith("\ufeff"), "UNSUPPORTED_JSON_BOM")
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_float=_number,
                           parse_constant=_number, parse_int=_parsed_integer)
        _unicode(value)
    except json.JSONDecodeError as error:
        raise DiagnosticSchemaError("MALFORMED_JSON") from error
    except RecursionError as error:
        raise DiagnosticSchemaError("UNSUPPORTED_JSON_STRUCTURE") from error
    return value, data


def _hash(value, code):
    _need(type(value) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None, code)


def _reference(value):
    _keys(value, {"path", "sha256", "byte_count"}, "INVALID_EXPOSED_REFERENCE")
    _string(value["path"], "INVALID_EXPOSED_REFERENCE", nonempty=True)
    _hash(value["sha256"], "INVALID_EXPOSED_REFERENCE")
    _integer(value["byte_count"], "INVALID_EXPOSED_REFERENCE")
    return value["path"], value["sha256"], value["byte_count"]


def _allowlist(references):
    _need(type(references) in (list, tuple), "INVALID_REFERENCE_ALLOWLIST")
    result = set()
    for reference in references:
        identity = _reference(reference)
        _need(identity not in result, "DUPLICATE_REFERENCE_ALLOWLIST")
        result.add(identity)
    return result


def _view(value):
    _need(type(value) is dict, "INVALID_CLOSED_VIEW")
    operation = value.get("operation")
    _enum(operation, {"inventory", "field"}, "INVALID_VIEW_OPERATION")
    expected = {"operation", "output_cap_bytes", "metadata_reserve_bytes"}
    if operation == "field":
        expected |= {"selector", "start_char"}
    _keys(value, expected, "INVALID_CLOSED_VIEW")
    _integer(value["output_cap_bytes"], "INVALID_VIEW_CAP", low=-MAX_SAFE_INTEGER)
    _integer(value["metadata_reserve_bytes"], "INVALID_VIEW_RESERVE", low=-MAX_SAFE_INTEGER)
    if operation == "field":
        _enum(value["selector"], {"/system", "/user"}, "INVALID_VIEW_SELECTOR")
        _integer(value["start_char"], "INVALID_VIEW_CURSOR", low=-MAX_SAFE_INTEGER)


def _confirmation(value):
    _keys(value, {"chunk_id", "outer_output_intact"}, "INVALID_CLOSED_CONFIRMATION")
    _string(value["chunk_id"], "INVALID_CONFIRMATION_CHUNK", nonempty=True)
    _need(type(value["outer_output_intact"]) is bool, "INVALID_CONFIRMATION_FLAG")


def _operation(value):
    if value is None:
        return
    _keys(value, {"chunk_id", "selector", "start_char", "output_cap_bytes", "metadata_reserve_bytes"}, "INVALID_OWN_OPERATION")
    _nullable_string(value["chunk_id"], "INVALID_OWN_CHUNK", nonempty=True)
    if value["selector"] is not None:
        _enum(value["selector"], {"/system", "/user"}, "INVALID_OWN_SELECTOR")
    if value["start_char"] is not None:
        _integer(value["start_char"], "INVALID_OWN_CURSOR", low=-MAX_SAFE_INTEGER)
    if value["output_cap_bytes"] is not None:
        _integer(value["output_cap_bytes"], "INVALID_OWN_CAP", low=-MAX_SAFE_INTEGER)
    if value["metadata_reserve_bytes"] is not None:
        _integer(value["metadata_reserve_bytes"], "INVALID_OWN_RESERVE", low=-MAX_SAFE_INTEGER)


def _observation(value, allowlist):
    _need(type(value) is dict, "INVALID_OBSERVATION")
    kind = value.get("kind")
    _enum(kind, {"literal", "reference", "unavailable"}, "INVALID_OBSERVATION_KIND")
    if kind == "unavailable":
        _keys(value, {"kind", "reason"}, "INVALID_OBSERVATION")
        _enum(value["reason"], {"NOT_EXPOSED", "NOT_RETAINED"}, "INVALID_UNAVAILABLE_REASON")
        return
    _keys(value, {"kind", "source", "scope", "text" if kind == "literal" else "reference"}, "INVALID_OBSERVATION")
    _enum(value["source"], SOURCES, "INVALID_OBSERVATION_SOURCE")
    _enum(value["scope"], {"complete", "visible_fragment"}, "INVALID_OBSERVATION_SCOPE")
    if kind == "literal":
        _string(value["text"], "INVALID_OBSERVATION_TEXT")
    else:
        _need(_reference(value["reference"]) in allowlist, "REFERENCE_NOT_EXPOSED_ALLOWLIST_MEMBER")


def _reproduction(value):
    _keys(value, {"template", "view", "confirmation", "own_input_literal", "expected_observed_error_literal", "availability"}, "INVALID_REPRODUCTION")
    _enum(value["template"], {"FIRST", "NEXT", "CONFIRM", "HASH", "CHECKPOINT", "FINAL_SCHEMA", "UNAVAILABLE"}, "INVALID_REPRODUCTION_TEMPLATE")
    if value["view"] is not None:
        _view(value["view"])
    if value["confirmation"] is not None:
        _confirmation(value["confirmation"])
    _nullable_string(value["own_input_literal"], "INVALID_REPRODUCTION_INPUT")
    _nullable_string(value["expected_observed_error_literal"], "INVALID_REPRODUCTION_ERROR")
    _enum(value["availability"], {"PROVIDED", "UNAVAILABLE"}, "INVALID_REPRODUCTION_AVAILABILITY")
    if value["availability"] == "PROVIDED":
        _need(value["template"] != "UNAVAILABLE", "PROVIDED_TEMPLATE_UNAVAILABLE")
        _string(value["expected_observed_error_literal"], "PROVIDED_ERROR_UNAVAILABLE", nonempty=True)
        template = value["template"]
        if template in ("FIRST", "NEXT"):
            _need(value["view"] is not None and value["view"]["operation"] ==
                  ("inventory" if template == "FIRST" else "field"), "PROVIDED_VIEW_TEMPLATE_MISMATCH")
            _need(value["confirmation"] is None, "PROVIDED_IRRELEVANT_CONFIRMATION")
        else:
            _need(value["view"] is None, "PROVIDED_IRRELEVANT_VIEW")
            _string(value["own_input_literal"], "PROVIDED_OWN_INPUT_UNAVAILABLE", nonempty=True)
            if template == "CONFIRM":
                _need(value["confirmation"] is not None, "PROVIDED_CONFIRMATION_UNAVAILABLE")
            else:
                _need(value["confirmation"] is None, "PROVIDED_IRRELEVANT_CONFIRMATION")


def _critique(value):
    _keys(value, {"violated_check", "own_attempted_retry", "observed_retry_error_literal", "recovery"}, "INVALID_SELF_CRITIQUE")
    _nullable_string(value["violated_check"], "INVALID_CRITIQUE_CHECK")
    _nullable_string(value["observed_retry_error_literal"], "INVALID_CRITIQUE_ERROR")
    retry = value["own_attempted_retry"]
    if retry is not None:
        _need(type(retry) is dict, "INVALID_CRITIQUE_RETRY")
        if set(retry) == {"chunk_id", "outer_output_intact"}:
            _confirmation(retry)
        else:
            _view(retry)
    _enum(value["recovery"], {"RECOVERABLE_ALLOWED_VALUES", "FIXED_SOURCE_BLOCKED", "UNAVAILABLE"}, "INVALID_CRITIQUE_RECOVERY")


def _partial_result(value):
    _need(type(value["markers"]) is list, "INVALID_PARTIAL_MARKERS")
    for marker in value["markers"]:
        _string(marker, "INVALID_PARTIAL_MARKER", nonempty=True)
    roots = value["field_roots"]
    _need(type(roots) is dict and set(roots) <= {"/system", "/user"}, "INVALID_PARTIAL_ROOTS")
    for digest in roots.values():
        _hash(digest, "INVALID_PARTIAL_ROOT")
    _keys(value["field_eof"], {"/system", "/user"}, "INVALID_PARTIAL_EOF")
    _keys(value["field_chars"], {"/system", "/user"}, "INVALID_PARTIAL_TOTALS")
    for selector in ("/system", "/user"):
        _need(type(value["field_eof"][selector]) is bool, "INVALID_PARTIAL_EOF_FLAG")
        _integer(value["field_chars"][selector], "INVALID_PARTIAL_TOTAL")


def parse_failure(raw, *, fixture_failure_allowed=False, exposed_references=()):
    """Validate reported shape/membership only, preserving literal hash and distrust.

    The caller must authenticate actual fixture permission and exposed-reference
    provenance. This pure parser cannot establish either observation or cause.
    """
    _need(type(fixture_failure_allowed) is bool, "INVALID_FIXTURE_PERMISSION_TYPE")
    _need(fixture_failure_allowed, "FIXTURE_FAILURE_BRANCH_NOT_AUTHORIZED")
    value, data = _load(raw)
    _keys(value, SUCCESS_KEYS | {"failure"}, "NOT_CLOSED_DIAGNOSTIC_FAILURE_BRANCH")
    _partial_result(value)
    failure = value["failure"]
    _keys(failure, {"format", "trust", "stage", "operation", "observation", "reproduction", "self_critique"}, "INVALID_FAILURE_OBJECT")
    _need(failure["format"] == "verislop.author-observed-failure/0.1", "INVALID_FAILURE_FORMAT")
    _need(failure["trust"] == "UNATTESTED", "FAILURE_AUTHORITY_OVERCLAIM")
    _enum(failure["stage"], STAGES, "INVALID_FAILURE_STAGE")
    _operation(failure["operation"])
    _observation(failure["observation"], _allowlist(exposed_references))
    _reproduction(failure["reproduction"])
    _critique(failure["self_critique"])
    if failure["stage"] == "UNKNOWN" or failure["observation"]["kind"] == "unavailable":
        critique = failure["self_critique"]
        _need(failure["stage"] == "UNKNOWN" and failure["operation"] is None
              and critique["violated_check"] is None and critique["own_attempted_retry"] is None
              and critique["observed_retry_error_literal"] is None and critique["recovery"] == "UNAVAILABLE"
              and failure["reproduction"]["availability"] == "UNAVAILABLE", "UNKNOWN_FAILURE_INVENTED_DETAILS")
    return {"format": "verislop.author-observed-failure-evidence/0.1",
            "trust": "UNATTESTED", "success": False,
            "qualification_claims_discharged": [], "historical_cause": "UNAVAILABLE",
            "literal_final_sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
            "report": value}
