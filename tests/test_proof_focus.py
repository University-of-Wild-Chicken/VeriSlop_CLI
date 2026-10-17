"""Authored engineering fixtures, not live model success evidence."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verislop import agents, canonical, leanbridge, proof_focus, proof_fragments, prove
from verislop.events import EventSink
from verislop.package import Package
from verislop.providers.adapters import Completion
from verislop.providers.broker import Broker
import test_small_prover_routing as routing_fixture


POLICY = {"build_timeout_seconds": 30, "memory_mb": 2048, "require_network_isolation": True}
FROZEN = ("import Std\nnamespace Focus\ntheorem preexisting : True := by trivial\n"
          + "".join(f"theorem «留存_{i}» (n : Nat) : n = n := by sorry\n" for i in range(8))
          + "theorem pending_a : True := by sorry\ntheorem pending_b : True := by sorry\nend Focus\n")
BASELINE = FROZEN.replace("by sorry", "by first | rfl | sorry")
FRAGMENT = "theorem pending_a : True := by trivial\ntheorem pending_b : True := by trivial"


class NativeProofFocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tc = leanbridge.resolve_toolchain()
        cls.result = prove.evaluate(cls.tc, POLICY, BASELINE)

    def selection(self, *, frozen=FROZEN, baseline=BASELINE, result=None, identity=None, policy=None):
        return proof_focus.select(frozen, baseline, self.result if result is None else result,
            self.tc.identity() if identity is None else identity, POLICY if policy is None else policy)

    def test_native_positions_select_two_not_ten_lexical_fallback_sorries(self):
        self.assertEqual(10, len(prove.sorry_sites(BASELINE)))
        self.assertTrue(self.result["ok"], self.result)
        self.assertEqual(2, self.result["sorries"])
        selected = self.selection()
        self.assertEqual("native_sorry_positions", selected["basis"])
        self.assertEqual(["pending_a", "pending_b"], selected["names"])
        self.assertEqual(selected["names"], proof_focus.focused_names(selected, FROZEN, BASELINE))
        self.assertEqual(2, len(proof_fragments.expected_headers(FROZEN, selected["names"])))

    def test_focused_fragments_preserve_solved_bodies_and_compile_whole_module(self):
        names = self.selection()["names"]
        first = proof_fragments.assemble(FRAGMENT.splitlines()[0], FROZEN, BASELINE, selected_names=names)
        self.assertIn("theorem pending_b : True := by first | rfl | sorry", first)
        complete = proof_fragments.assemble(FRAGMENT.splitlines()[1], FROZEN, first, selected_names=names)
        before = {t.name: BASELINE[t.body_start:t.body_end] for t in proof_fragments.declarations(BASELINE)}
        after = {t.name: complete[t.body_start:t.body_end] for t in proof_fragments.declarations(complete)}
        for name in set(before) - set(names):
            self.assertEqual(before[name], after[name])
        outcome = prove.evaluate(self.tc, POLICY, complete)
        self.assertTrue(outcome["complete"], outcome)
        self.assertEqual([], outcome["native_diagnostics"]["sorry_positions"])
        proof_fragments.validate_focused_candidate(complete, FROZEN, BASELINE, names)

    def test_invalid_selected_proof_still_fails_native_whole_module_compilation(self):
        source = proof_fragments.assemble(FRAGMENT.replace("by trivial", "by exact missing_focus_proof", 1),
                                          FROZEN, BASELINE, selected_names=self.selection()["names"])
        result = prove.evaluate(self.tc, POLICY, source)
        self.assertFalse(result["ok"])
        self.assertTrue(any("missing_focus_proof" in error for error in result["errors"]))

    def test_both_protocols_reject_changes_outside_selected_bodies(self):
        names = self.selection()["names"]
        with self.assertRaises(proof_fragments.FragmentError):
            proof_fragments.assemble("theorem «留存_0» (n : Nat) : n = n := by rfl", FROZEN, BASELINE,
                                     selected_names=names)
        completed = proof_fragments.assemble(FRAGMENT, FROZEN, BASELINE, selected_names=names)
        for changed in (completed.replace("by first | rfl | sorry", "by simp", 1),
                        completed.replace("theorem preexisting : True", "theorem preexisting : False"),
                        completed.replace("namespace Focus", "namespace Altered")):
            with self.subTest(changed=changed[:80]), self.assertRaises(proof_fragments.FragmentError):
                proof_fragments.validate_focused_candidate(changed, FROZEN, BASELINE, names)

    def test_missing_stale_and_ambiguous_native_observations_are_conservative(self):
        cases = []
        for change in (
                lambda e: e.pop("native_diagnostics"),
                lambda e: e.update(ok=False),
                lambda e: e.update(errors=["a failure"]),
                lambda e: e.update(sorries=10),
                lambda e: e["native_diagnostics"].update(source_sha256="sha256:stale"),
                lambda e: e["native_diagnostics"].update(policy_sha256="sha256:stale"),
                lambda e: e["native_diagnostics"].update(toolchain={}),
                lambda e: e["native_diagnostics"].update(sorry_positions=[]),
                lambda e: e["native_diagnostics"]["sorry_positions"][0].update(column=100000),
                lambda e: e["native_diagnostics"]["sorry_positions"][0].update(line=True),
                lambda e: e["native_diagnostics"]["sorry_positions"][0].update(line=3)):
            altered = copy.deepcopy(self.result)
            change(altered)
            cases.append(altered)
        for result in cases:
            with self.subTest(result=result):
                focus = self.selection(result=result)
                self.assertEqual("conservative", focus["basis"])
                self.assertEqual(10, len(focus["names"]))
                self.assertIsNone(proof_focus.focused_names(focus, FROZEN, BASELINE))
        stale = self.selection(baseline=BASELINE + "-- changed\n")
        self.assertEqual("conservative", stale["basis"])

    def test_focus_is_bound_to_exact_baseline_and_original_names(self):
        descriptor = self.selection()
        for frozen, baseline in ((FROZEN + "\n", BASELINE), (FROZEN, BASELINE + "\n")):
            with self.assertRaises(proof_fragments.FragmentError):
                proof_focus.focused_names(descriptor, frozen, baseline)
        for names in ([], ["pending_a", "pending_a"], ["unknown"], ["pending_b", "pending_a"]):
            changed = {**descriptor, "names": names}
            with self.subTest(names=names), self.assertRaises(proof_fragments.FragmentError):
                proof_focus.focused_names(changed, FROZEN, BASELINE)
        for change in ({"names": ["«留存_0»"]}, {"native_sha256": "not a digest"}, {"basis": []}):
            with self.subTest(change=change), self.assertRaises(proof_fragments.FragmentError):
                proof_focus.focused_names({**descriptor, **change}, FROZEN, BASELINE)

    def test_unsupported_full_file_layout_keeps_legacy_mode(self):
        unsupported = 'import Std\n@[simp] theorem foo : True := by sorry\n'
        self.assertIsNone(proof_focus.select(unsupported, unsupported, None, None, POLICY))
        self.assertIsNone(proof_focus.focused_names(None, unsupported, unsupported))

    def test_native_unicode_line_separators_are_not_lean_newlines(self):
        for separator in ("\u0085", "\u2028", "\u2029"):
            frozen = ('import Std\ndef marker : String := "x' + separator + 'y"\n'
                      'theorem solved_a : 0 = 0 := by sorry\n'
                      'theorem solved_b : 1 = 1 := by sorry\n'
                      'theorem pending : True := by sorry\n')
            baseline = frozen.replace("by sorry", "by rfl", 2)
            result = prove.evaluate(self.tc, POLICY, baseline)
            self.assertTrue(result["ok"], result)
            with self.subTest(separator=repr(separator)):
                self.assertEqual(["pending"], proof_focus.select(frozen, baseline, result, self.tc.identity(), POLICY)["names"])

    def test_comment_or_indent_positions_do_not_map_to_theorem(self):
        source = 'import Std\n  theorem a : True := by sorry -- trailing comment\ntheorem b : True := by sorry\n'
        result = prove.evaluate(self.tc, POLICY, source)
        self.assertTrue(result["ok"], result)
        for column in (0, 43):
            changed = copy.deepcopy(result)
            changed["native_diagnostics"]["sorry_positions"][0] = {"line": 2, "column": column}
            selected = proof_focus.select(source, source, changed, self.tc.identity(), POLICY)
            with self.subTest(column=column):
                self.assertEqual("conservative", selected["basis"])

    def test_focused_full_file_system_scopes_sorry_prohibition_to_selected_bodies(self):
        self.assertNotIn("Replace every `sorry`", agents.FOCUSED_PROVER_SYSTEM)
        self.assertNotIn("Do not use `sorry`", agents.FOCUSED_PROVER_SYSTEM)
        self.assertIn("Preserve every other proof body byte-for-byte", agents.FOCUSED_PROVER_SYSTEM)
        self.assertIn("unused `sorry` tactic alternatives", agents.FOCUSED_PROVER_SYSTEM)
        self.assertIn("Do not introduce `sorry` in selected proof bodies", agents.FOCUSED_PROVER_SYSTEM)

    def test_full_file_dispatch_enforces_focus_without_rewriting_model_response(self):
        selected = self.selection()["names"]
        complete = proof_fragments.assemble(FRAGMENT, FROZEN, BASELINE, selected_names=selected)
        changed = complete.replace("by first | rfl | sorry", "by simp", 1)
        for proposal, accepted in ((complete, True), (changed, False)):
            comp = Completion(json.dumps({"lean_source": proposal}), "model", "model", None, 1, 1)
            with patch.object(agents, "recorded_call", return_value=comp):
                args = (None, {"agents": {"sol": {}}}, None, None, "sol", "test", "system", "user",
                        "prove", FROZEN, BASELINE, agents.assemble_proof_response)
                if accepted:
                    actual, raw = agents._proof_completion(*args, selected_names=selected)
                    self.assertEqual(proposal, actual)
                    self.assertEqual(comp.text, raw)
                else:
                    with self.assertRaises(proof_fragments.FragmentError) as caught:
                        agents._proof_completion(*args, selected_names=selected)
                    self.assertEqual(comp.text, caught.exception.response)


class ExactProofContextTests(unittest.TestCase):
    def data(self):
        baseline = "import Std\n-- é e\u0301 😀 中\n" * 30
        candidate = baseline + "theorem retained : True := by trivial\n"
        errors = ["例:42: no theorem 😀", "actual second diagnostic", ""]
        return {"current_file": baseline,
                "previous_attempt": {"lean_source": candidate,
                    "result": {"errors": errors, "ok": False, "raw_metadata": {"exact_content_ref": ["unrelated"]}}},
                "retained_rejection": {"candidate": candidate, "raw_response": candidate, "diagnostics": errors},
                "errors": errors, "critique": {"status": "REPAIR", "feedback": ["keep the concrete failure"]},
                "focus": None}

    def test_duplicate_sources_restore_exact_unicode_and_every_diagnostic(self):
        original = self.data()
        before = copy.deepcopy(original)
        projected = proof_focus.project_context(original)
        self.assertEqual(before, original)
        self.assertEqual(original, proof_focus.restore_context(projected))
        context = projected["context"]
        self.assertEqual(original["previous_attempt"]["lean_source"], context["previous_attempt"]["lean_source"])
        for field in ("candidate", "raw_response"):
            self.assertEqual(["previous_attempt", "lean_source"], context["retained_rejection"][field]["exact_content_ref"])
        self.assertLess(len(canonical.dumps(projected)), len(canonical.dumps(original)))
        rendered = proof_focus.render_context(projected)
        for diagnostic in original["errors"]:
            self.assertIn(diagnostic, rendered)
        self.assertIn("EXACT RETAINED PROOF REJECTION", rendered)
        self.assertIn("Nothing was summarized".lower(), rendered.lower())

    def test_best_previous_and_raw_response_dedup_without_losing_distinct_raw_bytes(self):
        data = self.data()
        data["previous_attempt"]["lean_source"] = data["current_file"]
        data["retained_rejection"]["candidate"] = data["current_file"]
        data["retained_rejection"]["raw_response"] = "```lean\n" + data["current_file"] + "```"
        projected = proof_focus.project_context(data)
        self.assertEqual(["current_file"], projected["context"]["previous_attempt"]["lean_source"]["exact_content_ref"])
        self.assertIsInstance(projected["context"]["retained_rejection"]["raw_response"], str)
        self.assertEqual(data, proof_focus.restore_context(projected))

    def test_empty_and_normalization_distinct_strings_preserved(self):
        data = self.data()
        data["current_file"] = ""
        data["previous_attempt"]["lean_source"] = ""
        data["retained_rejection"].update(candidate="é", raw_response="e\u0301")
        projected = proof_focus.project_context(data)
        self.assertEqual("é", projected["context"]["retained_rejection"]["candidate"])
        self.assertEqual("e\u0301", projected["context"]["retained_rejection"]["raw_response"])
        self.assertEqual(data, proof_focus.restore_context(projected))

    def test_unknown_forward_indirect_and_stale_references_fail_closed(self):
        original = proof_focus.project_context(self.data())
        for update in ({"exact_content_ref": ["retained_rejection", "raw_response"]},
                       {"exact_content_ref": ["missing"]}, {"exact_content_ref": [1]},
                       {"sha256": "sha256:stale"}, {"utf8_bytes": 0}, {"utf8_bytes": True}):
            changed = copy.deepcopy(original)
            changed["context"]["retained_rejection"]["candidate"].update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                proof_focus.restore_context(changed)
        changed = copy.deepcopy(original)
        changed["context"]["retained_rejection"]["raw_response"]["exact_content_ref"] = ["retained_rejection", "candidate"]
        with self.assertRaises(ValueError):
            proof_focus.restore_context(changed)
        changed = copy.deepcopy(original)
        changed["context"]["errors"].pop()
        with self.assertRaises(ValueError):
            proof_focus.restore_context(changed)

    def test_renderer_rejects_unknown_fields_instead_of_losing_metadata(self):
        data = self.data()
        data["unique_new_diagnostic"] = "must never disappear"
        projected = proof_focus.project_context(data)
        self.assertEqual(data, proof_focus.restore_context(projected))
        with self.assertRaises(ValueError):
            proof_focus.render_context(projected)


class ProofFocusWorkflowTests(unittest.TestCase):
    inputs = routing_fixture.SmallProverRoutingTests.inputs

    def setUp(self):
        routing_fixture.SmallProverRoutingTests.setUp(self)

    def test_native_evaluation_flows_through_routed_role_and_exact_retained_context(self):
        from verislop import agent_memory
        frozen = FROZEN + routing_fixture.REGISTRY
        baseline = BASELINE + routing_fixture.REGISTRY
        (self.challenge / "Contract.lean").write_text(frozen)
        self.policy = POLICY
        self.cfg.write_text(json.dumps(self.conf))
        calls = []

        def completion(broker, agent, instance, system, user, purpose):
            calls.append((agent, system, user))
            return Completion(FRAGMENT, broker.model_for(agent), broker.model_for(agent), None, 1, 1)

        # The authored baseline models unused portfolio fallbacks; its native
        # compiler observation and the entire dispatch/assembly path are real.
        with self.inputs(real_lean=True), patch.object(prove, "apply_portfolio", return_value=baseline), \
             patch.object(Broker, "call", new=completion):
            role = agents.prover_agent(self.cfg, self.pkg, self.events)
            result = prove.run(self.pkg, self.events, agent=role, portfolio=True, max_attempts=1, budget_seconds=0)
        self.assertEqual("PASS", result.status, result.to_json())
        self.assertEqual(1, len(calls))
        headers = calls[0][2].split("EXACT FROZEN THEOREM HEADERS", 1)[1].split("FOCUSED PROOF DISPATCH", 1)[0]
        self.assertIn("pending_a", headers)
        self.assertIn("pending_b", headers)
        self.assertNotIn("留存", headers)
        retained = agent_memory.latest_snapshot(self.pkg, stage_prefix="proof-context/projection")
        projection = canonical.loads(agent_memory.restore(self.pkg, retained)["payload.json"])
        original = proof_focus.restore_context(projection)
        self.assertEqual(baseline, original["current_file"])
        self.assertEqual(baseline, original["previous_attempt"]["lean_source"])
        self.assertEqual(["pending_a", "pending_b"], original["focus"]["names"])
        candidate = (self.pkg.path("contract") / "proofs/candidate.lean").read_text()
        self.assertEqual(8, len(prove.sorry_sites(candidate)))
        self.assertEqual(frozen, (self.challenge / "Contract.lean").read_text())
        self.assertFalse(self.pkg.path("accepted").exists())


if __name__ == "__main__":
    unittest.main()
