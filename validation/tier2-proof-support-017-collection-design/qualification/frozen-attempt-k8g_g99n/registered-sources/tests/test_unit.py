"""Unit tests: canonical JSON, schema validator, DSL, segmentation, classification, consensus."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import unittest

import helpers  # noqa: F401  (sets sys.path)
from verislop import canonical, classify, dsl, draft as draftmod, lifecycle, schemas, segment
from verislop.jsonschema_lite import Registry, SchemaError
from verislop.review import parse_ballot, tally_tier

PROFILE = dsl.Profile.from_json({
    "profile_id": "t.v0_1",
    "enums": {"E": {"lean_decl": "T.E", "constructors": ["a", "b"], "lean_constructors": ["T.E.a", "T.E.b"]}},
    "symbols": {"f": {"lean_decl": "T.f", "args": ["Nat", "Nat"], "result": {"result": {"error": {"enum": "E"}, "ok": "Nat"}}}},
    "predicates": {},
})


class CanonicalTests(unittest.TestCase):
    def test_rejects_duplicates_floats_nonfinite_surrogates_bigints(self):
        for bad in (b'{"a":1,"a":2}', b'{"a":1.5}', b'{"a":NaN}', b'{"a":"\\ud800"}', b'{"a":9007199254740993}', b"\xef\xbb\xbf{}"):
            with self.assertRaises(canonical.CanonicalJSONError, msg=bad):
                canonical.loads(bad)

    def test_jcs_ordering_and_escaping(self):
        self.assertEqual(canonical.dumps({"b": 1, "a": [True, None, "x\n\u0001é"]}),
                         '{"a":[true,null,"x\\n\\u0001é"],"b":1}'.encode())
        # keys sorted by UTF-16 code units
        self.assertEqual(canonical.dumps({"\U0001F600": 1, "￿": 2}).decode(), '{"\U0001F600":1,"￿":2}')


class SchemaTests(unittest.TestCase):
    def test_unknown_keyword_fails_closed(self):
        reg = Registry()
        with self.assertRaises(SchemaError):
            reg.add({"$id": "urn:x", "type": "object", "unevaluatedProperties": False})

    def test_example_draft_validates(self):
        self.assertEqual(schemas.validate("draft", canonical.load_file(helpers.EX / "draft.json")), [])
        self.assertEqual(schemas.validate("review-config", canonical.load_file(helpers.EX / "review-config.json")), [])

    def test_bool_is_not_integer(self):
        issues = schemas.validate("evidence", {"exit_code": True})
        self.assertTrue(any("exit_code" in str(i) for i in issues))

    def test_duplicate_array_has_bounded_diagnostics(self):
        reg = Registry()
        reg.add({"$id": "urn:unique", "type": "array", "uniqueItems": True})
        issues = reg.validate(["same"] * 20000, "urn:unique")
        self.assertEqual(len(issues), 1)
        self.assertIn("not unique", str(issues[0]))

    def test_array_uniqueness_preserves_json_types_and_object_equality(self):
        reg = Registry()
        reg.add({"$id": "urn:unique", "type": "array", "uniqueItems": True})
        self.assertEqual(reg.validate([True, 1, 1.0, "1", None], "urn:unique"), [])
        self.assertTrue(reg.validate([{"a": [1], "b": False}, {"b": False, "a": [1]}], "urn:unique"))


class DSLTests(unittest.TestCase):
    O17 = json.loads((helpers.REPO / "docs" / "contract-ir.md").read_text().split("```json")[1].split("```")[0])["formula"]

    def test_doc_example_typechecks_with_profile(self):
        prof = dsl.Profile.from_json({"profile_id": "bounded-increment-nat.v0_1",
                                      "enums": {"IncrementError": {"lean_decl": "X", "constructors": ["limitReached"], "lean_constructors": ["X.limitReached"]}},
                                      "symbols": {"increment": {"lean_decl": "Y", "args": ["Nat", "Nat"], "result": {"result": {"error": {"enum": "IncrementError"}, "ok": "Nat"}}}},
                                      "predicates": {}})
        pkg = dsl.make_package(self.O17, prof.profile_id)
        dsl.check_package(pkg, prof)
        self.assertTrue(dsl.round_trip_ok(pkg, prof))

    def test_typing_errors(self):
        bad = [
            {"tag": "var", "index": 0},                                            # free variable
            {"tag": "lt", "left": {"tag": "bool", "value": True}, "right": {"tag": "nat", "value": "1"}},
            {"tag": "eq", "left": {"tag": "nat", "value": "01"}, "right": {"tag": "nat", "value": "1"}},
            {"tag": "eq", "left": {"tag": "call", "symbol": "f", "args": [{"tag": "nat", "value": "1"}]}, "right": {"tag": "nat", "value": "1"}},
            {"tag": "true", "extra": 1},
        ]
        for f in bad:
            with self.assertRaises(dsl.DSLError, msg=f):
                dsl.type_formula(f, [], PROFILE)

    def test_range_bounds_see_outer_context_only(self):
        f = {"tag": "forall", "sort": "Nat", "body": {"tag": "forall_range", "lower": {"tag": "nat", "value": "0"},
             "upper": {"tag": "var", "index": 0}, "body": {"tag": "le", "left": {"tag": "var", "index": 0}, "right": {"tag": "var", "index": 1}}}}
        dsl.type_formula(f, [], PROFILE)
        f_bad = {"tag": "forall_range", "lower": {"tag": "nat", "value": "0"}, "upper": {"tag": "var", "index": 0}, "body": {"tag": "true"}}
        with self.assertRaises(dsl.DSLError):
            dsl.type_formula(f_bad, [], PROFILE)

    def test_sampling_never_proves_universal_and_exhaustion_is_unknown(self):
        ev = dsl.Evaluator(PROFILE, {}, lambda body, env: [0, 1, 2])
        forall_nat = {"tag": "forall", "sort": "Nat", "body": {"tag": "le", "left": {"tag": "nat", "value": "0"}, "right": {"tag": "var", "index": 0}}}
        t = ev.formula(forall_nat, [])
        self.assertTrue(t.value is True and not t.exact)
        exists_nat = {"tag": "exists", "sort": "Nat", "body": {"tag": "eq", "left": {"tag": "var", "index": 0}, "right": {"tag": "nat", "value": "99"}}}
        self.assertIsNone(ev.formula(exists_nat, []).value)  # not found among samples: UNKNOWN, never FALSE
        big = {"tag": "forall_range", "lower": {"tag": "nat", "value": "0"}, "upper": {"tag": "nat", "value": "100000"}, "body": {"tag": "true"}}
        self.assertIsNone(ev.formula(big, []).value)
        finite = {"tag": "forall", "sort": "Bool", "body": {"tag": "or", "left": {"tag": "holds", "term": {"tag": "var", "index": 0}},
                                                           "right": {"tag": "not", "body": {"tag": "holds", "term": {"tag": "var", "index": 0}}}}}
        self.assertEqual(ev.formula(finite, []), dsl.T_EXACT)

    def test_target_value_outside_profile_is_a_fault(self):
        ev = dsl.Evaluator(PROFILE, {"f": lambda args: ["ok", 1]}, lambda b, e: [])
        with self.assertRaises(dsl.TargetFault):
            ev.term({"tag": "call", "symbol": "f", "args": [{"tag": "nat", "value": "1"}, {"tag": "nat", "value": "2"}]}, [])


class SegmentClassifyTests(unittest.TestCase):
    def test_segments_and_coverage(self):
        data = (helpers.EX / "request.txt").read_bytes()
        segs = segment.segments(data)
        self.assertEqual(len(segs), 7)
        self.assertEqual(segment.uncovered(data, [(0, len(data))]), [])
        self.assertEqual(len(segment.uncovered(data, [(0, 118)])), 5)

    def test_routing(self):
        sw = classify.classify((helpers.EX / "request.txt").read_bytes(), "r")
        self.assertEqual(sw["decision"], "SOFTWARE")
        non = classify.classify(b"Write a poem and a short story about my travel itinerary.", "r")
        self.assertEqual(non["routing_result"], "NOT_APPLICABLE")
        unsure = classify.classify(b"Make it better.", "r")
        self.assertEqual(unsure["decision"], "UNCERTAIN")
        forced = classify.forced_software(b"Make it better.", "r")
        self.assertEqual(forced["routing_result"], "OBLIGATION_PIPELINE")
        self.assertFalse(sw["confidence_is_evidence"])


class LifecycleTests(unittest.TestCase):
    def test_display_state_and_applicability(self):
        life = {m: lifecycle.milestone_entry("PENDING", "x") for m in lifecycle.MILESTONES}
        life["TESTED"] = lifecycle.milestone_entry("PASS", "t", ["e"], ["s"])
        self.assertEqual(lifecycle.derive_state(life), "TESTED")  # presentation order, even with PROVED pending
        for role in ("declaration", "assumption", "exclusion", "open_question"):
            app = lifecycle.applicability({"id": "X", "role": role, "kind": "entity"})
            self.assertFalse(app["PROVED"][0], role)

    def test_candidate_cannot_claim_proved(self):
        d = canonical.load_file(helpers.EX / "draft.json")
        d["postconditions"][0]["state"] = "PROVED"
        d["postconditions"][0]["lifecycle"]["PROVED"] = {"outcome": "PASS", "evidence_refs": ["x"], "reason": "trust me", "scope": ["all"]}
        diags = draftmod.validate_draft(d, (helpers.EX / "request.txt").read_bytes(), "examples/request.txt")
        self.assertIn("STALE_OR_UNBOUND_EVIDENCE", {x.code for x in diags})


class ConsensusTests(unittest.TestCase):
    TIER = {"id": "R0", "reviewers": [{"agent": "a", "count": 3, "focus": "f"}],
            "consensus": {"mode": "unanimous", "require_all_responses": True, "max_soft_rejects": 0, "max_abstentions": 0, "blocking_findings_veto": True}}
    MEMBERS = ["R0/a#1", "R0/a#2", "R0/a#3"]

    def ballot(self, verdict, blocking=()):
        return {"verdict": verdict, "unresolved_blocking_findings": list(blocking)}

    def test_unanimity_missing_reject_abstain(self):
        all_ok = {m: self.ballot("ACCEPT") for m in self.MEMBERS}
        self.assertEqual(tally_tier(self.TIER, self.MEMBERS, all_ok, [])["result"], "TIER_ACCEPTED")
        missing = dict(list(all_ok.items())[:2])
        self.assertEqual(tally_tier(self.TIER, self.MEMBERS, missing, [])["result"], "INCOMPLETE")
        rej = {**all_ok, "R0/a#3": self.ballot("REJECT")}
        self.assertEqual(tally_tier(self.TIER, self.MEMBERS, rej, [])["result"], "CHANGES_REQUESTED")
        abst = {**all_ok, "R0/a#3": self.ballot("ABSTAIN")}
        self.assertEqual(tally_tier(self.TIER, self.MEMBERS, abst, [])["result"], "INCOMPLETE")

    def test_mechanical_failure_vetoes_unanimous_accept(self):
        all_ok = {m: self.ballot("ACCEPT") for m in self.MEMBERS}
        self.assertEqual(tally_tier(self.TIER, self.MEMBERS, all_ok, ["TESTED:O17@1"])["result"], "CHANGES_REQUESTED")

    def test_quorum(self):
        tier = {**self.TIER, "reviewers": [{"agent": "a", "count": 4, "focus": "f"}],
                "consensus": {"mode": "quorum", "min_accepts": 3, "require_all_responses": True, "max_soft_rejects": 1,
                              "max_abstentions": 0, "blocking_findings_veto": True}}
        members = [f"R0/a#{i}" for i in range(1, 5)]
        b = {m: self.ballot("ACCEPT") for m in members[:3]}
        b[members[3]] = self.ballot("REJECT")
        self.assertEqual(tally_tier(tier, members, b, [])["result"], "TIER_ACCEPTED")
        b[members[3]] = self.ballot("REJECT", ["F1"])
        self.assertEqual(tally_tier(tier, members, b, [])["result"], "CHANGES_REQUESTED")
        del b[members[3]]
        self.assertEqual(tally_tier(tier, members, b, [])["result"], "INCOMPLETE")  # missing never shrinks the denominator

    def test_ballot_validation(self):
        scope = ["O1", "O2"]
        self.assertIsNone(parse_ballot({"verdict": "MAYBE"}, scope)[0])
        self.assertIsNone(parse_ballot({"verdict": "ACCEPT", "reviewed_obligations": ["O1"]}, scope)[0])  # subset cannot accept
        self.assertIsNone(parse_ballot({"verdict": "ACCEPT", "reviewed_obligations": scope,
                                        "findings": [{"severity": "blocking", "statement": "x"}]}, scope)[0])
        ok, err = parse_ballot({"verdict": "ACCEPT", "reviewed_obligations": scope, "findings": [],
            "search": {"method": "probe the recorded interpretation claim", "attempted_cases": 1,
                       "probes": [{"kind": "mechanical_failure", "claim_id": "INTERPRETATION:request"}],
                       "conclusion": "NO_COUNTEREXAMPLE_FOUND"}}, scope)
        self.assertIsNotNone(ok, err)


class HttpTests(unittest.TestCase):
    def test_redirects_are_refused(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        from verislop.providers.http import ProviderError, request

        class R(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                self.send_response(302)
                self.send_header("Location", "http://evil.example/steal")
                self.end_headers()

        srv = ThreadingHTTPServer(("127.0.0.1", 0), R)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with self.assertRaises(ProviderError):
                request("POST", f"http://127.0.0.1:{srv.server_address[1]}/v1", "/chat/completions", {"Authorization": "Bearer s"}, {}, 5)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
