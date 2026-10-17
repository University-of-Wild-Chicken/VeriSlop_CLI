"""Closed release display: exact meanings, historical restoration, and dispatch context."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from verislop import canonical, exact_context, review, review_prompt
import test_review_prompt as legacy_fixtures


def packet():
    result = legacy_fixtures.LegacyReviewPromptTests().packet()
    first = {"claim_id": "END_TO_END_VERIFIED:O1", "required": True, "outcome": "FAIL",
             "premises": ["LINKED:O1"], "reason": "concrete fixture failure é🙂",
             "root_kind": "closure_root", "verifier": "verislop.closure",
             "input_root": "sha256:" + "1" * 64, "evidence_refs": ["evidence:exact-first"]}
    second = {**first, "claim_id": "LINKED:O1", "required": False, "outcome": "PENDING",
              "premises": [], "reason": "optional pending fixture", "input_root": None, "evidence_refs": []}
    result["mechanical_snapshot"]["claims"] = [first, second]
    result["required_mechanical_claims"] = [deepcopy(first)]
    result["mechanical_snapshot"]["provenance"] = [
        {**{k: first[k] for k in review_prompt.VISIBLE_PROVENANCE_FIELDS}, "evidence": ["evidence:exact-first"]}]
    result["evidence"] = ["ev-opaque-fixture"]
    context = {"checkpoint": "release", "review_phase": "vscore_post_mechanical",
               "current_milestones": ["PROVED", "LINKED"], "outside_checkpoint_milestones": ["TESTED"],
               "current_required_claim_ids": [first["claim_id"]], "future_required_claim_ids": [],
               "claims": {first["claim_id"]: {"disposition": "CURRENT", "required": True}}}
    result["review_context"] = context
    result["counterexample_policy"].update(review_context=deepcopy(context),
        proposals={"mechanical_failure": {"kind": "mechanical_failure", "claim_id": first["claim_id"]},
                   "target_case": {"kind": "target_case", "obligation_id": "O1", "assignment": [{"int": "0"}]}},
        mechanical_claim_ids=[first["claim_id"]])
    return result


class ReleaseContextTests(unittest.TestCase):
    def test_closed_projection_restores_full_packet_and_all_visible_values(self):
        full = packet(); original = canonical.dumps(full)
        display = review_prompt.project_packet(full)
        self.assertEqual(review_prompt.FORMAT, display["format"])
        self.assertEqual(original, canonical.dumps(review_prompt.restore_packet(display, full)))
        p = display["packet"]
        for field in ("request", "scope", "obligations", "lean_accepted_source", "implementation",
                      "counterexample_policy", "review_context", "checked_link_inventory", "excluded_surfaces"):
            self.assertEqual(canonical.dumps(full[field]), canonical.dumps(p[field]))
        for old, new in zip(full["mechanical_snapshot"]["claims"], p["mechanical_snapshot"]["claims"]):
            self.assertEqual(set(review_prompt.VISIBLE_CLAIM_FIELDS), set(new))
            self.assertEqual({k: old[k] for k in review_prompt.VISIBLE_CLAIM_FIELDS}, new)
        self.assertEqual([True, False], [r["required"] for r in p["mechanical_snapshot"]["claims"]])
        self.assertEqual(["FAIL", "PENDING"], [r["outcome"] for r in p["mechanical_snapshot"]["claims"]])
        p["mechanical_snapshot"]["claims"][0]["premises"].clear()
        self.assertEqual(original, canonical.dumps(full))

    def test_references_are_batched_and_bind_every_replaced_value(self):
        full = packet(); p = review_prompt.project_packet(full)["packet"]
        pairs = [(p["vscore"]["goal"], full["vscore"]["goal"], "/vscore/goal"),
                 (p["evidence"], full["evidence"], "/evidence"),
                 (p["required_mechanical_claims_details_ref"], full["required_mechanical_claims"], "/required_mechanical_claims")]
        pairs += [(p["mechanical_snapshot"][key + "_details_ref"], full["mechanical_snapshot"][key],
                   "/mechanical_snapshot/" + key) for key in ("claims", "provenance")]
        for ref, value, pointer in pairs:
            self.assertEqual(review_prompt._reference(value, pointer), ref)
        for row in p["mechanical_snapshot"]["claims"]:
            self.assertFalse(any(key.endswith("_ref") for key in row))

    def test_unknown_missing_duplicate_and_mistyped_rows_fail_closed(self):
        changes = [lambda p: p["mechanical_snapshot"]["claims"][0].update(new_field="keep me"),
            lambda p: p["mechanical_snapshot"]["claims"][0].pop("input_root"),
            lambda p: p["mechanical_snapshot"]["claims"][0].update(required=1),
            lambda p: p["mechanical_snapshot"]["claims"][0].update(premises="wrong"),
            lambda p: p["mechanical_snapshot"]["claims"][0].update(outcome="UNKNOWN"),
            lambda p: p["mechanical_snapshot"]["claims"][0].update(evidence_refs=[True]),
            lambda p: p["mechanical_snapshot"]["claims"].append(deepcopy(p["mechanical_snapshot"]["claims"][0])),
            lambda p: p["required_mechanical_claims"].clear(),
            lambda p: p["mechanical_snapshot"]["provenance"][0].update(reason="different"),
            lambda p: p["mechanical_snapshot"]["provenance"][0].update(evidence=True),
            lambda p: p["mechanical_snapshot"]["provenance"][0].update(new_field=0),
            lambda p: p["mechanical_snapshot"]["provenance"].clear(),
            lambda p: p["mechanical_snapshot"]["provenance"][0].update(evidence=["different"]),
            lambda p: p["mechanical_snapshot"]["provenance"].append(deepcopy(p["mechanical_snapshot"]["provenance"][0])),
            lambda p: p.update(evidence="wrong"), lambda p: p["vscore"].update(goal=None),
            lambda p: p.update(required_mechanical_claims_details_ref={})]
        for change in changes:
            full = packet(); change(full)
            with self.subTest(change=change), self.assertRaises(ValueError):
                review_prompt.project_packet(full)

    def test_view_tampering_and_coherent_outer_hash_refresh_are_rejected(self):
        full = packet(); display = review_prompt.project_packet(full)
        paths = [("packet", "vscore", "goal"), ("packet", "evidence"),
                 ("packet", "mechanical_snapshot", "claims_details_ref"),
                 ("packet", "mechanical_snapshot", "provenance_details_ref"),
                 ("packet", "required_mechanical_claims_details_ref")]
        for path in paths:
            for key in ("pointer", "sha256", "utf8_bytes", "packet_ref", "format"):
                changed = deepcopy(display); row = changed
                for part in path: row = row[part]
                row[key] = "changed"
                with self.subTest(path=path, key=key), self.assertRaises(ValueError):
                    review_prompt.restore_packet(changed, full)
        for field in review_prompt.VISIBLE_CLAIM_FIELDS:
            changed = deepcopy(display)
            changed["packet"]["mechanical_snapshot"]["claims"][0][field] = "changed"
            with self.subTest(field=field), self.assertRaises(ValueError):
                review_prompt.restore_packet(changed, full)
        changed = deepcopy(full); changed["vscore"]["goal"] += "\n-- unique bytes"
        display["packet_sha256"] = canonical.digest_json(changed)
        display["packet_utf8_bytes"] = len(canonical.dumps(changed))
        with self.assertRaises(ValueError): review_prompt.restore_packet(display, changed)

    def test_supervisor_pointer_is_view_relative_and_preserves_original_milestones(self):
        full = packet(); view = review_prompt.project_packet(full)
        ref = review_prompt.context_reference(view, full)
        self.assertEqual("prompt-view.json", ref["view_ref"])
        self.assertEqual("/packet/review_context", ref["pointer"])
        self.assertEqual(canonical.digest_json(view), ref["view_sha256"])
        self.assertEqual(canonical.digest_json(full["review_context"]), ref["sha256"])
        self.assertNotIn("packet_ref", ref)
        raw = review._checkpoint_guidance("release", full["counterexample_policy"], context_ref=ref)
        guidance = json.JSONDecoder().raw_decode(raw.split("(supervisor-selected):\n", 1)[1])[0]
        self.assertEqual(ref, guidance["review_context"])
        self.assertEqual(["PROVED", "LINKED"], guidance["current_milestones"])
        self.assertEqual(["TESTED"], guidance["outside_checkpoint_milestones"])
        bad = deepcopy(full); bad["counterexample_policy"]["review_context"]["claims"] = {}
        with self.assertRaises(ValueError):
            review_prompt.context_reference(review_prompt.project_packet(bad), bad)

    def test_exact_codec_legacy_restore_and_literal_reference_payloads(self):
        full = packet(); literal = review_prompt._reference([True], "/not/a/display/path")
        full["unknown_data"] = {"claims_details_ref": literal, "$r": "literal é🙂"}
        view = review_prompt.project_packet(full)
        encoded = exact_context.render_context(exact_context.project_context(view))
        self.assertEqual(canonical.dumps(view), canonical.dumps(exact_context.restore_prompt(encoded)))
        self.assertEqual(full, review_prompt.restore_packet(exact_context.restore_prompt(encoded), full))
        old = legacy_fixtures.LegacyReviewPromptTests().packet()  # Deliberately lacks current row fields.
        legacy = review_prompt._project_legacy(old)
        self.assertEqual(review_prompt.LEGACY_FORMAT, legacy["format"])
        self.assertEqual(old, review_prompt.restore_packet(legacy, old))
        with self.assertRaises(ValueError): review_prompt.project_packet(old)

    def test_actual_system_variant_is_bound_and_legacy_rendering_unchanged(self):
        resolved = SimpleNamespace(profiles={"local": {"adapter": "mock"}})
        self.assertNotEqual(review.reviewer_configuration_hash({}, resolved),
            review.reviewer_configuration_hash({}, resolved, system=review.VSCORE3_RELEASE_SYSTEM))
        full = packet()
        with TemporaryDirectory() as folder:
            campaign = Path(folder)
            legacy = review._model_packet_text(full, campaign, bound_vscore_release=False)
            self.assertEqual(json.dumps(full, ensure_ascii=False), legacy)
            self.assertFalse((campaign / "prompt-view.json").exists())
            encoded = review._model_packet_text(full, campaign, bound_vscore_release=True)
            view = exact_context.restore_prompt(encoded)
            self.assertEqual(view, canonical.load_file(campaign / "prompt-view.json"))
            self.assertEqual(full, review_prompt.restore_packet(view, full))


class ReleaseDispatchTests(unittest.TestCase):
    def test_real_broker_recording_keeps_full_packet_and_exact_bad_ballot_feedback(self):
        from unittest.mock import patch
        from helpers import MockLLM, TempDir, mock_config, unanimous
        from test_providers_review import review_packet
        from verislop import review_projection
        from verislop.events import EventSink
        from verislop.package import Package
        from verislop.providers import config as pcfg

        full = packet()
        full["mechanical_snapshot"].update(closure_root="sha256:" + "2" * 64,
            mechanical_result_path="closure/executions/fixture/mechanical-result.json")
        original = canonical.dumps(full)
        rejected = '{"verdict":"ACCEPT","reviewed_obligations":["O1"],"rationale":"exact é🙂 raw response"}'
        requests = []
        def responder(system, user, model):
            requests.append((system, user, model))
            return rejected
        from contextlib import ExitStack
        with ExitStack() as cleanup:
            tmp = TempDir(); cleanup.callback(tmp.cleanup)
            transport = MockLLM(responder); cleanup.callback(transport.close)
            pkg = Package(tmp.path / "package"); pkg.ensure("release-display-host")
            path, env = mock_config(tmp.path, transport.port, [unanimous("R0", "reviewer", 1)], checkpoints=["release"])
            conf = canonical.load_file(path)
            conf["review"]["budgets"]["max_calls_per_instance"] = 2
            projected = {"projection_hash": "sha256:" + "3" * 64, "projection": {},
                         "raw_inventory": [], "raw_inventory_hash": canonical.digest_json([])}
            with patch.dict("os.environ", env):
                resolved = pcfg.resolve(conf, pcfg.load_user_profiles(None))
                events = EventSink(pkg.run_id, pkg.root, quiet=True)
                try:
                    with patch.object(review, "build_packet", return_value=full), \
                         patch.object(review, "target_components", return_value={}), \
                         patch("verislop.backends.registry.is_vscore", return_value=True), \
                         patch.object(review_projection, "build", return_value=projected), \
                         patch.object(review, "_mechanical_veto", return_value=["fixture-native-veto"]), \
                         patch("verislop.review_counterexamples.replay_probe") as replay:
                        cert, _ = review._campaign(pkg, events, conf, resolved, "release")
                finally: events.close()
            self.assertEqual(2, len(requests))
            replay.assert_not_called()  # Both raw proposals are invalid, never evidence.
            self.assertNotEqual("REVIEW_ACCEPTED", cert["final"])
            self.assertEqual(["fixture-native-veto"], cert["mechanical_veto"])
            self.assertEqual(original, canonical.dumps(full))
            first, second = requests
            self.assertEqual(review.VSCORE3_RELEASE_SYSTEM, first[0])
            self.assertEqual(first[0], second[0]); self.assertEqual(first[2], second[2])
            self.assertEqual(review_packet(first[1]), review_packet(second[1]))
            self.assertIn(rejected, second[1])
            self.assertIn("search must record method, attempted_cases, constructed probes and conclusion", second[1])
            folder = next(pkg.path("reviews").glob("rc-*"))
            self.assertEqual(original, canonical.dumps(canonical.load_file(folder / "packet.json")))
            view = canonical.load_file(folder / "prompt-view.json")
            self.assertEqual(original, canonical.dumps(review_prompt.restore_packet(view, full)))
            self.assertEqual(review.reviewer_configuration_hash(conf, resolved, system=first[0]),
                             cert["target_components"]["reviewer_configuration_hash"])
            self.assertEqual(rejected, (folder / "ballot-attempts/R0_reviewer#1/1.raw.txt").read_text())
            records = [canonical.load_file(path) for path in (folder / "transcripts").glob("*.json")]
            self.assertEqual(2, len(records))
            self.assertEqual({"review:release"}, {row["purpose"] for row in records})
            self.assertEqual({first[2]}, {row["requested_model"] for row in records})


if __name__ == "__main__": unittest.main()
