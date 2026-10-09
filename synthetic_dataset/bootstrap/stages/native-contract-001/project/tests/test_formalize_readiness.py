"""Pre-freeze executable readiness, including real Lean reification of conditional values."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from verislop import agents, canonical, contract, formalize, fsutil, interpret
from verislop.events import EventSink
from verislop.package import Package


REQUEST = b"Implement absolute_difference(left, right) over natural numbers, returning left-right when right<=left and right-left otherwise."
CONDITIONAL = "absolute_difference left right = (if right <= left then left - right else right - left)"
BRANCHES = "(right <= left → absolute_difference left right = left - right) ∧ (¬ (right <= left) → absolute_difference left right = right - left)"


def source(statement):
    # The extra theorem proves the two representations equivalent in Lean itself.
    return ("import Std\nnamespace Aligned\n"
            "def absolute_difference (left right : Nat) : Nat :=\n"
            "  if right <= left then left - right else right - left\n"
            f"theorem result (left right : Nat) : {statement} := by sorry\n"
            f"theorem branch_shape_equivalent (left right : Nat) : ({CONDITIONAL}) <-> ({BRANCHES}) := by\n"
            "  by_cases h : right <= left <;> simp [h]\n"
            "end Aligned\n").encode()


FORM = {"schema_version": "0.1", "artifact_kind": "formalization_candidate", "profile_id": "aligned.v0_1",
        "lean_toolchain": "leanprover/lean4:v4.34.1", "lean_file": "Contract.lean",
        "bindings": [{"obligation": "D1", "declarations": ["Aligned.absolute_difference"]},
                     {"obligation": "O2", "theorem": "Aligned.result"}], "internal_obligations": []}
REQUESTED = {"tier": 0, "target": "python", "endpoint": "test_campaign", "require_state": "TESTED"}


class FormalizeReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(Path(self.tmp.name) / "package")
        self.pkg.ensure("formalize-readiness")
        self.events = EventSink(self.pkg.run_id, self.pkg.root, quiet=True)
        self.addCleanup(self.events.close)

    def record_interpretation(self):
        obligations = []
        for oid, kind, role, statement, deps in (
                ("D1", "entity", "declaration", "absolute_difference takes two Nat values and returns a Nat.", []),
                ("O2", "postcondition", "guarantee", REQUEST.decode(), [{"id": "D1", "relation": "uses_definition"}])):
            obligations.append({"id": oid, "kind": kind, "role": role, "statement": statement,
                                "required": True, "scope": ["all natural inputs"], "dependencies": deps,
                                "acceptance_criteria": ["Bind the exact declaration or proposition in Lean."],
                                "sources": [{"quote": REQUEST.decode(), "origin": "explicit", "interpretation": "exact domain and branches"}]})
        proposal = {"obligations": obligations,
                    "category_review": {k: "reviewed" for k in agents.DRAFT_CATEGORIES},
                    "clauses": [{"quote": REQUEST.decode(), "disposition": "obligations", "refs": ["D1", "O2"]}],
                    "assumptions": [], "ambiguities": [], "selected_defaults": []}
        path = Path(self.tmp.name) / "request.txt"
        path.write_bytes(REQUEST)

        def interpreter(prompt, ref, routing):
            draft, ledger, problems = agents.assemble_interpretation(proposal, prompt, ref)
            self.assertEqual([], problems)
            return draft, ledger

        result = interpret.run(self.pkg, self.events, path, mode="software", request_ref="request.txt", agent=interpreter)
        self.assertEqual("PASS", result.status, [d.to_json() for d in result.diagnostics])

    def test_inline_conditional_is_repaired_before_freeze_with_exact_context(self):
        self.record_interpretation()
        self.pkg.set_meta("requested", REQUESTED)
        contexts = []

        def proposer(ctx):
            contexts.append(copy.deepcopy(ctx))
            return source(CONDITIONAL if len(contexts) == 1 else BRANCHES), copy.deepcopy(FORM)

        result = formalize.run(self.pkg, self.events, agent=proposer, max_attempts=2)
        self.assertEqual("PASS", result.status, [d.to_json() for d in result.diagnostics])
        self.assertEqual(2, len(contexts))
        self.assertEqual({"lean_source": source(CONDITIONAL).decode(), "formalization": FORM}, contexts[1]["previous_candidate"])
        self.assertTrue(any("O2" in text and "term constant ite is not registered" in text for text in contexts[1]["feedback"]))
        self.assertTrue(any("Do not weaken, remove" in text for text in contexts[1]["feedback"]))
        statement = contract.frozen_json(self.pkg, "statements.json")["statements"]["O2"]
        self.assertEqual("contract_dsl", statement["representation"])
        self.assertEqual("and", statement["formula_package"]["formula"]["body"]["body"]["tag"])
        self.assertEqual(source(BRANCHES), (self.pkg.path("contract") / "candidate/proposal.lean").read_bytes())

    def test_exhausted_readiness_repairs_do_not_freeze_opaque_campaign_contract(self):
        self.record_interpretation()
        self.pkg.set_meta("requested", REQUESTED)
        calls = []

        def proposer(ctx):
            calls.append(ctx)
            return source(CONDITIONAL), copy.deepcopy(FORM)

        result = formalize.run(self.pkg, self.events, agent=proposer, max_attempts=1)
        self.assertEqual("BLOCKED", result.status)
        self.assertEqual(1, len(calls))
        self.assertFalse((contract.challenge_dir(self.pkg) / "challenge.json").exists())
        self.assertEqual(["O2"], result.diagnostics[-1].obligations)
        self.assertEqual("term constant ite is not registered in the semantic profile", result.diagnostics[-1].details["opaque_reason"])

    def test_explicit_opaque_candidate_remains_admissible_with_tested_request(self):
        self.record_interpretation()
        self.pkg.set_meta("requested", REQUESTED)
        candidate = Path(self.tmp.name) / "candidate"
        fsutil.atomic_write(candidate / "Contract.lean", source(CONDITIONAL))
        fsutil.write_json(candidate / "formalization.json", FORM)
        result = formalize.run(self.pkg, self.events, candidate=candidate)
        self.assertEqual("PASS", result.status, [d.to_json() for d in result.diagnostics])
        self.assertEqual("lean_expr", contract.frozen_json(self.pkg, "statements.json")["statements"]["O2"]["representation"])

    def test_readiness_respects_scope_and_actual_test_applicability(self):
        guarantee = {"id": "O2", "role": "guarantee", "kind": "postcondition", "required": True, "blocked_by": []}
        statement = {"representation": "lean_expr", "opaque_reason": "term constant ite is not registered",
                     "semantic_closure": {"Aligned.absolute_difference": "sha256:checked"}}
        analysis = contract.Analysis({"symbols": {"difference": {"lean_decl": "Aligned.absolute_difference"}}},
                                     {"O2": statement}, [], [], [])
        self.assertEqual(1, len(formalize.executable_readiness([guarantee], analysis, REQUESTED)))
        self.assertEqual(1, len(formalize.executable_readiness([guarantee], analysis, {"tier": 0})))
        self.assertEqual(1, len(formalize.executable_readiness([guarantee], analysis,
                                                           {"tier": None, "target": None, "endpoint": None, "require_state": None})))
        for request in ({}, {"tier": 2, "target": "vscore", "require_state": "END_TO_END_VERIFIED"},
                        {"tier": 1, "target": "python", "endpoint": "instrumented_runtime", "require_state": "PROVED"}):
            self.assertEqual([], formalize.executable_readiness([guarantee], analysis, request))
        for change in ({"required": False}, {"blocked_by": ["Q1"]}, {"kind": "non_vacuity"}, {"role": "declaration"}):
            self.assertEqual([], formalize.executable_readiness([{**guarantee, **change}], analysis, REQUESTED))
        no_symbol = contract.Analysis({"symbols": {}}, {"O2": statement}, [], [], [])
        missing = formalize.executable_readiness([guarantee], no_symbol, REQUESTED)
        self.assertTrue(missing[0].details["missing_implementation_symbol"])

    def test_true_or_reflexive_input_guarantee_cannot_freeze_a_test_campaign(self):
        guarantee = {"id": "O2", "role": "guarantee", "kind": "postcondition", "required": True, "blocked_by": []}
        for semantic_closure in ({}, {"Nat": "sha256:checked"}):
            analysis = contract.Analysis({"symbols": {"difference": {"lean_decl": "Aligned.absolute_difference"}}},
                                         {"O2": {"representation": "contract_dsl", "semantic_closure": semantic_closure}},
                                         [], [], [])
            diagnostics = formalize.executable_readiness([guarantee], analysis, REQUESTED)
            self.assertEqual(1, len(diagnostics))
            self.assertEqual(["O2"], diagnostics[0].obligations)
            self.assertTrue(diagnostics[0].details["missing_implementation_symbol"])

    def test_reflexive_output_guarantee_is_rejected_but_model_equation_is_preserved(self):
        self.record_interpretation()
        self.pkg.set_meta("requested", REQUESTED)
        result = formalize.run(self.pkg, self.events, agent=lambda ctx: (
            source("absolute_difference left right = absolute_difference left right"), copy.deepcopy(FORM)),
            max_attempts=1)
        self.assertEqual("BLOCKED", result.status)
        self.assertTrue(any(d.details.get("structurally_trivial_guarantee") for d in result.diagnostics))
        self.assertFalse((contract.challenge_dir(self.pkg) / "challenge.json").exists())
        # Syntactic comparison does not unfold a function into its reference body.
        self.assertFalse(formalize._structurally_trivial({"tag": "eq", "left": {"tag": "call", "symbol": "solve", "args": []},
                                                        "right": {"tag": "nat", "value": "0"}}))


if __name__ == "__main__":
    unittest.main()
