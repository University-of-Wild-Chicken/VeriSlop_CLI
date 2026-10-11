"""Pure public structural criticism and same-author evidence validation.

This module does not open files, launch agents, read carriers, or evaluate answers.
Source-bound callers supply retained bytes. Structural completion is not acceptance.
"""
import hashlib
import json
import re

FORMAT = "verislop.support023-single-fresh-author-evidence/1"
CRITIQUE_FORMAT = "verislop.support023-public-final-critique/1"
POLICY = {"max_corrective_followups": 32, "max_author_turns": 33,
          "ancillary_fresh_author_calls_meaning": "fresh_spawn_count",
          "inference_timeout": None, "retrieval_timeout": None, "review_timeout": None}
ROOT_KEYS = ("markers", "field_roots", "field_eof", "field_chars")
FIELD_KEYS = ("/system", "/user")
SAFE_INTEGER = 2**53 - 1
FEEDBACK_PREFIX = (
    "REGISTERED SAME-AUTHOR STRUCTURAL CORRECTION — support023/1\n"
    "Your preceding literal FINAL contradicts the frozen public success schema. "
    "The counterexamples below concern only that output's structure; they disclose no evaluator answer.\n"
)
FEEDBACK_SUFFIX = (
    "\nContinue this SAME author session using the original full frozen seed and only its registered recipes. "
    "If the accepted cursor was lost, use the fixed CHECKPOINT recipe to recover your own accepted availability state. "
    "Explicitly continue NEXT and CONFIRM through both /system and /user EOFs; use HASH only after both confirmed EOFs. "
    "Then author a new complete literal FINAL; do not copy this critique into FINAL. "
    "No new author, replacement sampling, additional agents, automatic VIEW loop, expected-value oracle, "
    "or hard inference/retrieval/review deadline is authorized. Every earlier literal remains evidence. "
    "Structural completion gives no semantic acceptance, proof, TESTED, or lifecycle authority.\n"
)


class ContinuationError(ValueError):
    pass


def need(condition, rule):
    if not condition:
        raise ContinuationError(rule)


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8", "strict")


def strict_parse(raw):
    need(type(raw) is bytes, "LITERAL_NOT_BYTES")
    text = raw.decode("utf-8", "strict")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    def invalid(value):
        raise ContinuationError("FLOAT_OR_NONFINITE_JSON_NUMBER")
    def integer(value):
        result = int(value)
        need(abs(result) <= SAFE_INTEGER, "UNSAFE_JSON_INTEGER")
        return result
    value = json.loads(text, object_pairs_hook=unique, parse_float=invalid,
                       parse_constant=invalid, parse_int=integer)
    def scalars(item):
        if type(item) is str:
            item.encode("utf-8", "strict")
        elif type(item) is list:
            for child in item:
                scalars(child)
        elif type(item) is dict:
            for key, child in item.items():
                scalars(key); scalars(child)
    scalars(value)
    return value


def pointer(key):
    return "/" + key.replace("~", "~0").replace("/", "~1")


def critique(raw):
    need(type(raw) is bytes, "LITERAL_NOT_BYTES")
    witnesses = []
    def fail(where, rule, observed, required):
        witnesses.append({"pointer": where, "rule": rule, "observed": observed, "required": required})
    try:
        value = strict_parse(raw)
    except UnicodeError:
        fail("", "INVALID_UNICODE_SCALAR_OR_UTF8", "INVALID_ENCODING", "STRICT_UTF8_UNICODE_SCALARS")
    except json.JSONDecodeError as error:
        fail("", "MALFORMED_JSON", {"line": error.lineno, "column": error.colno}, "ONE_JSON_VALUE")
    except (ContinuationError, ValueError, RecursionError) as error:
        rule = str(error) if isinstance(error, ContinuationError) else "JSON_PARSE_LIMIT"
        fail("", rule, "REJECTED_LITERAL", "STRICT_PUBLIC_JSON")
    else:
        if type(value) is not dict:
            fail("", "ROOT_NOT_OBJECT", type(value).__name__, "OBJECT")
        else:
            for key in ROOT_KEYS:
                if key not in value:
                    fail(pointer(key), "REQUIRED_KEY_MISSING", "MISSING", "PRESENT")
            if set(value) - set(ROOT_KEYS):
                # Do not copy caller-controlled extra key text into feedback.
                fail("/failure" if "failure" in value else "", "EXTRA_ROOT_KEYS", "EXTRA_KEYS_PRESENT", list(ROOT_KEYS))
            if "markers" in value:
                markers = value["markers"]
                if type(markers) is not list:
                    fail("/markers", "MARKERS_NOT_LIST", type(markers).__name__, "UNIQUE_SCALAR_STRING_LIST")
                else:
                    seen = set()
                    for index, marker in enumerate(markers):
                        if type(marker) is not str:
                            fail("/markers/" + str(index), "MARKER_NOT_STRING", type(marker).__name__, "SCALAR_STRING")
                        elif marker in seen:
                            fail("/markers/" + str(index), "DUPLICATE_MARKER", "DUPLICATE_STRING", "UNIQUE_STRING")
                        else:
                            seen.add(marker)
            for kind in ("field_roots", "field_eof", "field_chars"):
                if kind not in value:
                    continue
                fields = value[kind]
                if type(fields) is not dict:
                    fail(pointer(kind), "FIELD_MAP_NOT_OBJECT", type(fields).__name__, list(FIELD_KEYS))
                    continue
                if set(fields) - set(FIELD_KEYS):
                    fail(pointer(kind), "EXTRA_FIELD_KEYS", "EXTRA_KEYS_PRESENT", list(FIELD_KEYS))
                for key in FIELD_KEYS:
                    where = pointer(kind) + pointer(key)
                    if key not in fields:
                        fail(where, "REQUIRED_FIELD_KEY_MISSING", "MISSING", "PRESENT")
                        continue
                    field = fields[key]
                    if kind == "field_roots" and (type(field) is not str or re.fullmatch(r"sha256:[0-9a-f]{64}", field) is None):
                        fail(where, "NONCANONICAL_SHA256", type(field).__name__, "sha256:LOWERCASE_64_HEX")
                    elif kind == "field_eof" and field is not True:
                        fail(where, "EXPLICIT_EOF_NOT_TRUE", False if field is False else type(field).__name__, True)
                    elif kind == "field_chars" and (type(field) is not int or not 0 <= field <= SAFE_INTEGER):
                        fail(where, "NONNEGATIVE_SAFE_INTEGER_REQUIRED", type(field).__name__, "INTEGER_0_TO_9007199254740991_EXCLUDING_BOOL")
    return {"format": CRITIQUE_FORMAT, "literal_final_sha256": sha(raw),
            "structurally_complete": not witnesses, "counterexamples": witnesses,
            "acceptance_authority": False}


def render_feedback(raw):
    report = critique(raw)
    need(not report["structurally_complete"], "NO_COUNTEREXAMPLE_FOR_COMPLETE_LITERAL")
    return FEEDBACK_PREFIX.encode("utf-8") + wire(report) + FEEDBACK_SUFFIX.encode("utf-8")


def validate_turn_ledger(index, read_raw, expected_seed, expected_guards):
    """Authenticate all retained turns against a frozen public continuation policy.

    The callback is an already restricted artifact reader, not an author/model call.
    No fixture expectations are accepted or computed by this function.
    """
    need(type(index) is dict and index.get("format") == FORMAT, "AUTHOR_FORMAT")
    need(type(expected_seed) is bytes, "EXPECTED_SEED_NOT_BYTES")
    need(type(expected_guards) is dict and bool(expected_guards), "EMPTY_FROZEN_GUARDS")
    need(all(type(key) is str and type(value) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", value)
             for key, value in expected_guards.items()), "INVALID_FROZEN_GUARDS")
    need(type(index.get("continuation_policy")) is dict and wire(index["continuation_policy"]) == wire(POLICY), "CONTINUATION_POLICY")
    need(type(index.get("spawn_count")) is int and index["spawn_count"] == 1, "EXTRA_SPAWN")
    need(index.get("requested_model") == "gpt-6.1-sol" and index.get("fork_turns") == "none", "AUTHOR_MODEL_FORK")
    need(index.get("replacement_author_or_resampling") is False and index.get("evaluator_expectations_sent_to_author") is False, "AUTHOR_CONTAMINATION")
    need(index.get("model_identity") == index.get("semantic_consumption") == "UNATTESTED", "AUTHOR_AUTHORITY")
    retained = {}
    def artifact(ref):
        need(type(ref) is dict and set(ref) == {"path", "sha256", "byte_count"}, "ARTIFACT_REF_KEYS")
        name = ref["path"]
        need(type(name) is str and bool(name) and not name.startswith("/") and all(part not in ("", ".", "..") for part in name.split("/")), "ARTIFACT_PATH")
        need(type(ref["sha256"]) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", ref["sha256"]) is not None, "ARTIFACT_HASH")
        need(type(ref["byte_count"]) is int and ref["byte_count"] >= 0, "ARTIFACT_SIZE")
        raw = read_raw(ref)
        need(type(raw) is bytes and len(raw) == ref["byte_count"] and sha(raw) == ref["sha256"], "ARTIFACT_CONTENT_MISMATCH")
        need(name not in retained or retained[name] == raw, "ARTIFACT_CHANGED")
        retained[name] = raw
        return raw
    seed = artifact(index["submitted_message_ref"])
    need(seed == expected_seed == artifact(index["expected_literal_message_ref"]), "CHANGED_SEED")
    spawn = strict_parse(artifact(index["spawn_request_ref"]))
    response = strict_parse(artifact(index["spawn_result_ref"]))
    need(type(spawn) is dict and set(spawn) == {"task_name", "model", "fork_turns", "message"}, "SPAWN_REQUEST_KEYS")
    need(type(response) is dict and set(response) == {"task_name"}, "SPAWN_RESPONSE_KEYS")
    target = response["task_name"]
    need(type(target) is str and re.fullmatch(r"/root(?:/[a-z0-9_]+)+", target) is not None,
         "SPAWN_TARGET")
    need(type(spawn["task_name"]) is str and re.fullmatch(r"[a-z0-9_]+", spawn["task_name"]) is not None
         and target.rsplit("/", 1)[1] == spawn["task_name"], "SPAWN_LEAF")
    need(spawn["model"] == "gpt-6.1-sol" and spawn["fork_turns"] == "none" and type(spawn["message"]) is str
         and spawn["message"].encode("utf-8", "strict") == seed, "SPAWN_SEED")
    inventory = index["observed_author_requests"]
    need(type(inventory) is list and len(inventory) == 1 and type(inventory[0]) is dict
         and set(inventory[0]) == {"spawn_request_ref", "spawn_result_ref", "agent_id"}, "SPAWN_INVENTORY")
    need(wire(inventory[0]["spawn_request_ref"]) == wire(index["spawn_request_ref"])
         and wire(inventory[0]["spawn_result_ref"]) == wire(index["spawn_result_ref"])
         and inventory[0]["agent_id"] == index["author_agent_id"] == target, "SPAWN_INVENTORY_BINDING")
    followups = index["continuation_inventory"]
    turns = index["author_turns"]
    count = index["observed_followups"]
    need(type(count) is int and 0 <= count <= POLICY["max_corrective_followups"], "FOLLOWUP_BUDGET")
    need(type(followups) is list and len(followups) == count and type(turns) is list and len(turns) == count + 1, "TURN_INVENTORY_LENGTH")
    need(type(index["terminal_turn"]) is int and index["terminal_turn"] == len(turns) - 1, "TERMINAL_SELECTION")
    all_responses = []
    literal_paths = set()
    request_paths = {index["spawn_request_ref"]["path"]}
    result_paths = {index["spawn_result_ref"]["path"]}
    prior_raw = None
    prior_complete = False
    for turn_number, turn in enumerate(turns):
        need(type(turn) is dict and set(turn) == {"turn", "literal_final_ref", "critique_ref", "exposed_responses_refs", "guards_before", "guards_after"}, "TURN_KEYS")
        need(type(turn["turn"]) is int and turn["turn"] == turn_number, "TURN_ORDER")
        need(type(turn["guards_before"]) is dict and type(turn["guards_after"]) is dict
             and wire(turn["guards_before"]) == wire(expected_guards) == wire(turn["guards_after"]), "TURN_GUARDS")
        if turn_number:
            need(not prior_complete, "FOLLOWUP_AFTER_STRUCTURAL_SUCCESS")
            row = followups[turn_number - 1]
            need(type(row) is dict and set(row) == {"turn", "target", "previous_literal_sha256", "followup_request_ref", "followup_result_ref", "feedback_ref"}, "FOLLOWUP_KEYS")
            need(type(row["turn"]) is int and row["turn"] == turn_number and row["target"] == target, "FOLLOWUP_TARGET_OR_ORDER")
            need(row["previous_literal_sha256"] == sha(prior_raw), "PREVIOUS_LITERAL_HASH")
            feedback = artifact(row["feedback_ref"])
            need(feedback == render_feedback(prior_raw), "ALTERED_FEEDBACK")
            request = strict_parse(artifact(row["followup_request_ref"]))
            need(type(request) is dict and set(request) == {"target", "message"}
                 and request["target"] == target and type(request["message"]) is str
                 and request["message"].encode("utf-8", "strict") == feedback, "FOLLOWUP_REQUEST")
            # Native acknowledgments are opaque actual retained bytes; no hidden agent/PID/status is fabricated.
            artifact(row["followup_result_ref"])
            need(row["followup_request_ref"]["path"] not in request_paths and row["followup_result_ref"]["path"] not in result_paths, "DUPLICATED_NATIVE_REQUEST_RESULT")
            request_paths.add(row["followup_request_ref"]["path"]); result_paths.add(row["followup_result_ref"]["path"])
        raw = artifact(turn["literal_final_ref"])
        need(turn["literal_final_ref"]["path"] not in literal_paths, "OVERWRITTEN_LITERAL")
        literal_paths.add(turn["literal_final_ref"]["path"])
        report = critique(raw)
        need(artifact(turn["critique_ref"]) == wire(report), "ALTERED_CRITIQUE")
        responses = turn["exposed_responses_refs"]
        need(type(responses) is list and bool(responses), "MISSING_TURN_RESPONSES")
        response_raw = [artifact(ref) for ref in responses]
        need(any(raw in item for item in response_raw), "LITERAL_NOT_IN_EXPOSED_RESPONSE")
        need(len({ref["path"] for ref in responses}) == len(responses), "DUPLICATED_TURN_RESPONSE")
        all_responses.extend(responses)
        prior_raw, prior_complete = raw, report["structurally_complete"]
    need(type(index["exposed_responses_refs"]) is list and wire(index["exposed_responses_refs"]) == wire(all_responses), "EXPOSED_RESPONSE_INVENTORY")
    need(len({ref["path"] for ref in all_responses}) == len(all_responses), "DUPLICATED_EXPOSED_RESPONSE")
    need(wire(index["literal_final_ref"]) == wire(turns[-1]["literal_final_ref"])
         and artifact(index["literal_final_ref"]) == prior_raw, "SELECTED_LITERAL_CHANGED")
    if prior_complete:
        need(index["continuation_status"] == "STRUCTURALLY_COMPLETE", "CONTINUATION_STATUS")
    else:
        need(count == POLICY["max_corrective_followups"] and index["continuation_status"] == "BUDGET_EXHAUSTED", "PREMATURE_TERMINATION")
    return {"continuation_status": index["continuation_status"], "structurally_complete": prior_complete,
            "observed_followups": count, "terminal_turn": index["terminal_turn"],
            "single_actual_spawn_target": target, "literal_final_sha256": sha(prior_raw),
            "acceptance_authority": False}
