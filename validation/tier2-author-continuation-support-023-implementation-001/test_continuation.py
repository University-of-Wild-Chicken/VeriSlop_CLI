"""Finite, wholly synthetic source controls; NEVER evidence of an actual agent run.

Registered design: tier2-author-continuation-support-023-design/
SPECIFICATION_BEFORE_IMPLEMENTATION.json. No model, runtime, carrier, Lean,
qualification, task payload, evaluator expectation, or frozen input is executed.
All virtual refs below are SYNTHETIC_SOURCE_CONTROL_NO_ACTUAL_AGENT artifacts.
"""

import copy
import hashlib
import json
import unittest

from continuation_contract import critique, render_feedback, validate_turn_ledger


SYNTHETIC_SOURCE_CONTROL_NO_ACTUAL_AGENT = True
SEED = b"SYNTHETIC public frozen seed; no actual author is invoked."
TARGET = "/root/public023_author"
GUARDS = {"SYNTHETIC_SOURCE_CONTROL_NO_ACTUAL_AGENT/frozen.txt":
          "sha256:" + "c" * 64}
POLICY = {
    "max_corrective_followups": 32,
    "max_author_turns": 33,
    "ancillary_fresh_author_calls_meaning": "fresh_spawn_count",
    "inference_timeout": None,
    "retrieval_timeout": None,
    "review_timeout": None,
}


def wire(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8", "strict")


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def complete_value():
    # Deliberately arbitrary public shapes, never evaluator answers or roots.
    return {"markers": ["SYNTHETIC-only"],
            "field_roots": {"/system": "sha256:" + "a" * 64,
                            "/user": "sha256:" + "b" * 64},
            "field_eof": {"/system": True, "/user": True},
            "field_chars": {"/system": 1, "/user": 2}}


def incomplete_value():
    value = complete_value()
    value["field_roots"] = {}
    value["field_eof"]["/user"] = False
    value["failure"] = "SYNTHETIC incomplete result, no actual runtime error"
    return value


def build_ledger(finals):
    """Return index and virtual bytes only; creates NO actual metadata claim."""
    blobs = {}

    def add(name, raw):
        path = "SYNTHETIC_SOURCE_CONTROL_NO_ACTUAL_AGENT/" + name
        if path in blobs:
            raise AssertionError("synthetic fixture path reused")
        blobs[path] = raw
        return {"path": path, "sha256": sha(raw), "byte_count": len(raw)}

    seed_ref = add("seed.txt", SEED)
    spawn_ref = add("spawn-request.json", wire({
        "task_name": "public023_author", "model": "gpt-6.1-sol",
        "fork_turns": "none", "message": SEED.decode("utf-8")}))
    spawn_result_ref = add("spawn-result.json", wire({"task_name": TARGET}))
    turns, continuations, exposed = [], [], []
    for number, raw in enumerate(finals):
        final_ref = add("turn-%02d-final.txt" % number, raw)
        critique_ref = add("turn-%02d-critique.json" % number, wire(critique(raw)))
        response_ref = add("turn-%02d-exposed.txt" % number,
                           b"SYNTHETIC EXPOSED RESPONSE\n" + raw + b"\n")
        turns.append({"turn": number, "literal_final_ref": final_ref,
                      "critique_ref": critique_ref,
                      "exposed_responses_refs": [response_ref],
                      "guards_before": copy.deepcopy(GUARDS),
                      "guards_after": copy.deepcopy(GUARDS)})
        exposed.append(response_ref)
        if number:
            previous = finals[number - 1]
            feedback = (render_feedback(previous) if not critique(previous)["structurally_complete"]
                        else b"SYNTHETIC invalid continuation after structural success")
            feedback_ref = add("turn-%02d-feedback.txt" % number, feedback)
            request_ref = add("turn-%02d-followup-request.json" % number,
                              wire({"target": TARGET,
                                    "message": feedback.decode("utf-8", "strict")}))
            # Opaque synthetic native result bytes; no invented completion shape.
            result_ref = add("turn-%02d-followup-result.json" % number,
                             wire({"synthetic_source_control": number}))
            continuations.append({"turn": number, "target": TARGET,
                                  "previous_literal_sha256": sha(previous),
                                  "followup_request_ref": request_ref,
                                  "followup_result_ref": result_ref,
                                  "feedback_ref": feedback_ref})
    final_ref = turns[-1]["literal_final_ref"]
    is_complete = critique(finals[-1])["structurally_complete"]
    index = {
        "format": "verislop.support023-single-fresh-author-evidence/1",
        "spawn_count": 1, "requested_model": "gpt-6.1-sol", "fork_turns": "none",
        "model_identity": "UNATTESTED", "semantic_consumption": "UNATTESTED",
        "submitted_message_ref": seed_ref, "expected_literal_message_ref": seed_ref,
        "spawn_request_ref": spawn_ref, "spawn_result_ref": spawn_result_ref,
        "observed_author_requests": [{"spawn_request_ref": spawn_ref,
                                      "spawn_result_ref": spawn_result_ref,
                                      "agent_id": TARGET}],
        "author_agent_id": TARGET, "literal_final_ref": final_ref,
        "exposed_responses_refs": exposed,
        "evaluator_expectations_sent_to_author": False,
        "replacement_author_or_resampling": False,
        "continuation_policy": copy.deepcopy(POLICY),
        "observed_followups": len(continuations),
        "continuation_inventory": continuations,
        "author_turns": turns, "terminal_turn": len(turns) - 1,
        "continuation_status": "STRUCTURALLY_COMPLETE" if is_complete else "BUDGET_EXHAUSTED",
    }
    return index, blobs


def replace_artifact(ref, blobs, raw):
    """Rebind a synthetic ref so a semantic negative is not merely a bad hash."""
    blobs[ref["path"]] = raw
    ref["sha256"] = sha(raw)
    ref["byte_count"] = len(raw)


class ContinuationSourceControls(unittest.TestCase):
    def check(self, index, blobs, seed=SEED, guards=GUARDS):
        return validate_turn_ledger(index, lambda ref: blobs[ref["path"]], seed, guards)

    def reject_mutations(self, changes, finals=None):
        finals = finals or [wire(incomplete_value()), wire(complete_value())]
        for label, change in changes:
            with self.subTest(control=label):
                index, blobs = build_ledger(finals)
                change(index, blobs)
                with self.assertRaises(ValueError):
                    self.check(index, blobs)

    def test_01_incomplete_literal_has_concrete_schema_witnesses(self):
        raw = wire(incomplete_value())
        result = critique(raw)
        self.assertIs(result["structurally_complete"], False)
        self.assertIs(result["acceptance_authority"], False)
        self.assertEqual(result["literal_final_sha256"], sha(raw))
        witnesses = result["counterexamples"]
        self.assertTrue(witnesses)
        pointers = {entry["pointer"] for entry in witnesses}
        self.assertIn("/field_eof/~1user", pointers)
        self.assertTrue(any(pointer.startswith("/field_roots") for pointer in pointers))
        self.assertIn("/failure", pointers)
        self.assertTrue(all(type(entry["rule"]) is str and entry["rule"] for entry in witnesses))

    def test_02_strict_parse_rejects_malformed_duplicate_and_invalid_text(self):
        valid = wire(complete_value())
        cases = {
            "malformed": b"{", "trailing": valid + b"{}",
            "duplicate_root": valid[:-1] + b',"markers":[]}',
            "duplicate_nested": valid.replace(b'"/system":1', b'"/system":1,"/system":1'),
            "invalid_utf8": b'{"markers":["\xff"]}',
            "escaped_surrogate": valid.replace(b'SYNTHETIC-only', b'\\ud800'),
            "bom": b"\xef\xbb\xbf" + valid,
        }
        for name, raw in cases.items():
            with self.subTest(control=name):
                result = critique(raw)
                self.assertIs(result["structurally_complete"], False)
                self.assertTrue(result["counterexamples"])
                self.assertIs(result["acceptance_authority"], False)

    def test_03_exact_integer_boolean_and_json_number_rules(self):
        for value in (True, False, -1, 2 ** 53, 1.0):
            with self.subTest(field_chars=value):
                item = complete_value()
                item["field_chars"]["/user"] = value
                self.assertIs(critique(wire(item))["structurally_complete"], False)
        for value in (0, 1, "true", None):
            with self.subTest(field_eof=value):
                item = complete_value()
                item["field_eof"]["/user"] = value
                self.assertIs(critique(wire(item))["structurally_complete"], False)
        for token in (b"NaN", b"Infinity", b"-Infinity", b"1e0"):
            raw = wire(complete_value()).replace(b'"/user":2', b'"/user":' + token)
            self.assertIs(critique(raw)["structurally_complete"], False)

    def test_04_closed_schema_sha_and_marker_rules(self):
        bad = []
        item = complete_value(); item["extra"] = 1; bad.append(item)
        item = complete_value(); del item["markers"]; bad.append(item)
        item = complete_value(); item["field_chars"]["/other"] = 1; bad.append(item)
        for value in ("a" * 64, "sha256:" + "A" * 64, "sha256:" + "g" * 64,
                      "sha256:" + "a" * 63, 17):
            item = complete_value(); item["field_roots"]["/user"] = value; bad.append(item)
        for value in (["duplicate", "duplicate"], [True], [1], "string"):
            item = complete_value(); item["markers"] = value; bad.append(item)
        for number, item in enumerate(bad):
            with self.subTest(control=number):
                self.assertIs(critique(wire(item))["structurally_complete"], False)

    def test_05_complete_arbitrary_answers_have_no_evaluator_authority(self):
        item = complete_value()
        item["markers"] = ["", "λ🙂", "e\u0301"]
        item["field_chars"] = {"/system": 0, "/user": 2 ** 53 - 1}
        raw = wire(item)
        result = critique(raw)
        self.assertIs(result["structurally_complete"], True)
        self.assertIs(result["acceptance_authority"], False)
        self.assertEqual(result["counterexamples"], [])
        # Distinct wholly synthetic private-equality example: shape acceptance
        # cannot assert equality. No actual evaluator expectation is read here.
        unrelated_expected = complete_value()
        self.assertNotEqual(wire(item), wire(unrelated_expected))
        index, blobs = build_ledger([raw])
        self.assertIs(self.check(index, blobs)["acceptance_authority"], False)

    def test_06_feedback_is_deterministic_and_bound_to_preceding_literal(self):
        first = wire(incomplete_value())
        second = first + b"\n"
        feedback = render_feedback(first)
        self.assertIs(type(feedback), bytes)
        self.assertEqual(feedback, render_feedback(first))
        feedback.decode("utf-8", "strict")
        self.assertIn(sha(first).encode("ascii"), feedback)
        self.assertNotEqual(feedback, render_feedback(second))
        self.assertNotIn(SEED, feedback)
        for word in (b"CHECKPOINT", b"CONFIRM", b"HASH"):
            self.assertIn(word, feedback)

    def test_07_valid_single_correction_and_exact_exhaustion_ledgers(self):
        complete = wire(complete_value())
        incomplete = wire(incomplete_value())
        cases = (([complete], 0, "STRUCTURALLY_COMPLETE", True),
                 ([incomplete, complete], 1, "STRUCTURALLY_COMPLETE", True),
                 ([incomplete] * 33, 32, "BUDGET_EXHAUSTED", False))
        for finals, followups, status, success in cases:
            with self.subTest(turns=len(finals)):
                index, blobs = build_ledger(finals)
                result = self.check(index, blobs)
                self.assertEqual(result["observed_followups"], followups)
                self.assertEqual(result["terminal_turn"], len(finals) - 1)
                self.assertEqual(result["continuation_status"], status)
                self.assertIs(result["structurally_complete"], success)
                self.assertIs(result["acceptance_authority"], False)

    def test_08_single_exact_spawn_and_seed_binding(self):
        def spawn_change(index, blobs, key, value):
            ref = index["spawn_request_ref"]
            request = json.loads(blobs[ref["path"]])
            request[key] = value
            replace_artifact(ref, blobs, wire(request))
        self.reject_mutations([
            ("wrong_seed", lambda i, b: spawn_change(i, b, "message", "changed seed")),
            ("wrong_model", lambda i, b: spawn_change(i, b, "model", "other-model")),
            ("wrong_fork", lambda i, b: spawn_change(i, b, "fork_turns", "all")),
            ("spawn_count", lambda i, b: i.update(spawn_count=2)),
            ("bool_spawn_count", lambda i, b: i.update(spawn_count=True)),
            ("extra_spawn", lambda i, b: i["observed_author_requests"].append(copy.deepcopy(i["observed_author_requests"][0]))),
            ("resampling", lambda i, b: i.update(replacement_author_or_resampling=True)),
            ("expectations_sent", lambda i, b: i.update(evaluator_expectations_sent_to_author=True)),
            ("wrong_agent", lambda i, b: i.update(author_agent_id="/root/replacement_author")),
        ])

    def test_09_exact_same_target_and_derived_followup_message(self):
        def request_change(index, blobs, key, value):
            ref = index["continuation_inventory"][0]["followup_request_ref"]
            request = json.loads(blobs[ref["path"]])
            request[key] = value
            replace_artifact(ref, blobs, wire(request))
        self.reject_mutations([
            ("target_row", lambda i, b: i["continuation_inventory"][0].update(target="/root/replacement_author")),
            ("target_request", lambda i, b: request_change(i, b, "target", "/root/replacement_author")),
            ("message_request", lambda i, b: request_change(i, b, "message", "arbitrary hint")),
            ("extra_request_key", lambda i, b: request_change(i, b, "extra", "forbidden")),
            ("previous_hash", lambda i, b: i["continuation_inventory"][0].update(previous_literal_sha256="sha256:" + "f" * 64)),
            ("feedback_rebound", lambda i, b: replace_artifact(i["continuation_inventory"][0]["feedback_ref"], b, b"arbitrary hint")),
        ])

    def test_10_contiguous_exact_turn_and_followup_inventories(self):
        self.reject_mutations([
            ("turn_gap", lambda i, b: i["author_turns"][1].update(turn=2)),
            ("bool_turn", lambda i, b: i["author_turns"][1].update(turn=True)),
            ("followup_gap", lambda i, b: i["continuation_inventory"][0].update(turn=2)),
            ("omitted_followup", lambda i, b: i.update(continuation_inventory=[])),
            ("duplicate_followup", lambda i, b: i["continuation_inventory"].append(copy.deepcopy(i["continuation_inventory"][0]))),
            ("reordered_turns", lambda i, b: i["author_turns"].reverse()),
            ("wrong_count", lambda i, b: i.update(observed_followups=0)),
            ("bool_count", lambda i, b: i.update(observed_followups=True)),
            ("extra_turn_key", lambda i, b: i["author_turns"][0].update(extra=True)),
            ("extra_continuation_key", lambda i, b: i["continuation_inventory"][0].update(extra=True)),
        ])

    def test_11_all_artifact_bytes_literals_critic_and_guards_are_bound(self):
        def corrupt_critique(index, blobs):
            ref = index["author_turns"][0]["critique_ref"]
            document = json.loads(blobs[ref["path"]])
            document["acceptance_authority"] = True
            replace_artifact(ref, blobs, wire(document))
        self.reject_mutations([
            ("literal_hash", lambda i, b: i["author_turns"][0]["literal_final_ref"].update(sha256="sha256:" + "f" * 64)),
            ("literal_bytes", lambda i, b: b.update({i["author_turns"][0]["literal_final_ref"]["path"]: b"changed"})),
            ("bool_byte_count", lambda i, b: i["author_turns"][0]["literal_final_ref"].update(byte_count=True)),
            ("extra_ref_key", lambda i, b: i["author_turns"][0]["literal_final_ref"].update(extra="forbidden")),
            ("critic_authority", corrupt_critique),
            ("unexposed_literal", lambda i, b: replace_artifact(i["author_turns"][0]["exposed_responses_refs"][0], b, b"unrelated response")),
            ("aggregate_omitted", lambda i, b: i["exposed_responses_refs"].pop()),
            ("aggregate_reordered", lambda i, b: i["exposed_responses_refs"].reverse()),
            ("changed_before", lambda i, b: i["author_turns"][0].update(guards_before={})),
            ("changed_after", lambda i, b: i["author_turns"][1].update(guards_after={})),
        ])

    def test_12_budget_first_success_and_terminal_literal_selection(self):
        incomplete, complete = wire(incomplete_value()), wire(complete_value())
        for finals in ([incomplete], [incomplete] * 32, [incomplete] * 34,
                       [complete, complete], [complete, incomplete]):
            with self.subTest(invalid_turn_sequence=len(finals), first_complete=finals[0] == complete):
                index, blobs = build_ledger(finals)
                with self.assertRaises(ValueError):
                    self.check(index, blobs)
        self.reject_mutations([
            ("wrong_terminal_turn", lambda i, b: i.update(terminal_turn=0)),
            ("bool_terminal_turn", lambda i, b: i.update(terminal_turn=True)),
            ("wrong_terminal_literal", lambda i, b: i.update(literal_final_ref=i["author_turns"][0]["literal_final_ref"])),
            ("wrong_status", lambda i, b: i.update(continuation_status="BUDGET_EXHAUSTED")),
            ("budget_change", lambda i, b: i["continuation_policy"].update(max_corrective_followups=31)),
            ("deadline", lambda i, b: i["continuation_policy"].update(inference_timeout=60)),
            ("extra_policy_key", lambda i, b: i["continuation_policy"].update(extra=True)),
        ])


if __name__ == "__main__":
    unittest.main()
