"""Regression checks for concrete proposal/schema mismatches and retained repair context."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from verislop import agents, canonical, contract, draft, dsl, formalize, fsutil
from verislop.errors import Diagnostic, InfrastructureError, UsageError
from verislop.events import EventSink
from verislop.package import Package


EXAMPLE_REQUEST = b"Return each natural input unchanged."


def interpreter_example():
    # Exercise the JSON the real system prompt shows, rather than a separate test template.
    text = agents.INTERPRETER_SYSTEM
    return agents.extract_json(text[text.index('{"obligations"'):])


def candidate_form(ids):
    return {"schema_version": "0.1", "artifact_kind": "formalization_candidate", "profile_id": "aligned.v0_1",
            "lean_toolchain": "leanprover/lean4:v4.34.1", "lean_file": "Contract.lean",
            "bindings": [{"obligation": oid, "theorem": f"Aligned.t{i}"} for i, oid in enumerate(ids)],
            "internal_obligations": []}


class CapturingBroker:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def call(self, agent, instance, system, user, purpose):
        self.calls.append({"agent": agent, "instance": instance, "system": system, "user": user, "purpose": purpose})
        return SimpleNamespace(text=next(self.responses), requested_model="test-model", returned_model=None)


def section_json(user, marker):
    return json.JSONDecoder().raw_decode(user.split(marker, 1)[1].lstrip())[0]


class AgentAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(Path(self.tmp.name) / "package")
        self.pkg.ensure("agent-alignment")
        self.events = EventSink(self.pkg.run_id, self.pkg.root, quiet=True)
        self.addCleanup(self.events.close)
        self.conf = {"roles": {"interpreter": "author", "formalizer": "author", "implementer": "author"}}

    def test_typed_formalizer_is_compiled_with_exact_origin_and_retries_invalid_envelopes(self):
        from verislop import formal_frontend
        proposed = {"encoding": formal_frontend.VERSION, "records": {}, "predicates": {}, "witness_obligations": {},
                    "symbols": {"increment": {"args": ["Int"], "result": "Int", "body": {
                        "tag": "int_add", "left": {"tag": "var", "index": 0}, "right": {"tag": "int", "value": "1"}}}},
                    "theorems": {"result": {"formula": {"tag": "forall", "sort": "Int", "body": {"tag": "eq",
                        "left": {"tag": "call", "symbol": "increment", "args": [{"tag": "var", "index": 0}]},
                        "right": {"tag": "int_add", "left": {"tag": "var", "index": 0}, "right": {"tag": "int", "value": "1"}}}}}},
                    "obligations": {"D1": {"declarations": [{"kind": "symbol", "name": "increment"}]}, "O1": {"theorem": "result"}}}
        records = [{"id": oid, "kind": kind, "role": role, "statement": "typed fixture", "required": True,
                    "dependencies": [], "acceptance_criteria": [], "blocked_by": [], "origin": "interpreted"}
                   for oid, kind, role in (("D1", "entity", "declaration"), ("O1", "postcondition", "guarantee"))]
        text = canonical.dumps(proposed).decode()
        broker = CapturingBroker([text, "```json\n" + text + "\n```"])
        ctx = {"records": records, "ledger": {"assumptions": []}, "feedback": [], "attempt": 1,
               "requested": {"target": "python", "tier": 0, "require_state": "TESTED"}}
        with patch.object(agents, "_broker", return_value=(broker, self.conf)):
            proposer = agents.formalizer_agent("unused", self.pkg, self.events)
            source, form = proposer(ctx)
            self.assertIsNotNone(proposer.last_compiled)
            self.assertTrue(formal_frontend.replay_receipt(proposed, records, source, form,
                                                         proposer.last_origin["receipt"], captured_response=text.encode()))
            self.assertEqual(agents.TYPED_FORMALIZER_SYSTEM, broker.calls[0]["system"])
            bad_source, bad_form = proposer(ctx)
            self.assertIn("unparseable", bad_source.decode())
            self.assertIn("error", bad_form)
            self.assertIsNone(proposer.last_compiled)
            self.assertIsNone(proposer.last_origin)

    def test_actual_interpreter_prompt_example_has_no_dangling_ids(self):
        proposed = interpreter_example()
        d, ledger, problems = agents.assemble_interpretation(proposed, EXAMPLE_REQUEST, "request.txt")
        self.assertEqual([], problems)
        self.assertEqual([], draft.validate_draft(d, EXAMPLE_REQUEST, "request.txt"))
        diags, coverage = draft.validate_ledger(ledger, d, EXAMPLE_REQUEST, "request.txt")
        self.assertEqual([], diags)
        self.assertEqual([], coverage["uncovered_segments"])
        self.assertEqual([], proposed["assumptions"])
        self.assertEqual([], proposed["ambiguities"])

    def test_literal_kind_role_pairs_and_complete_assumption_example_validate(self):
        self.assertNotIn("entity/declaration", agents.INTERPRETER_SYSTEM)
        self.assertNotIn("precondition/assumption", agents.INTERPRETER_SYSTEM)
        self.assertNotIn("ambiguity/open_question", agents.INTERPRETER_SYSTEM)
        self.assertIn(json.dumps(agents.INTERPRETER_KIND_ROLES, separators=(',', ':')), agents.INTERPRETER_SYSTEM)
        text = agents.INTERPRETER_SYSTEM.split("This second COMPLETE example", 1)[1]
        proposed = agents.extract_json(text[text.index('{"obligations"'):])
        prompt = agents._ASSUMPTION_REQUEST.encode()
        d, ledger, problems = agents.assemble_interpretation(proposed, prompt, "request.txt")
        self.assertEqual([], problems)
        self.assertEqual([], draft.validate_draft(d, prompt, "request.txt"))
        self.assertEqual([], draft.validate_ledger(ledger, d, prompt, "request.txt")[0])
        self.assertEqual(["D1"], [r["id"] for r in d["entities"]])
        self.assertEqual(["A1"], [r["id"] for r in d["preconditions"]])
        self.assertEqual({"id", "supplied_by", "discharged_at"}, set(ledger["assumptions"][0]))

    def test_slash_kind_repair_receives_exact_literals_and_schema_shapes(self):
        bad = interpreter_example()
        bad["obligations"][0]["kind"] = "postcondition/guarantee"
        bad_text = json.dumps(bad)
        broker = CapturingBroker([bad_text, json.dumps(interpreter_example())])
        with patch.object(agents, "_broker", return_value=(broker, self.conf)):
            d, ledger = agents.interpreter_agent("unused", self.pkg, self.events, attempts=2)(EXAMPLE_REQUEST, "request.txt", {})
        self.assertEqual(2, len(broker.calls))
        user = broker.calls[1]["user"]
        self.assertIn(bad_text, user)
        self.assertIn("unknown kind", user)
        guidance = section_json(user, "PROPOSAL FIELD SHAPES (from the current artifact schemas; repair the JSON, preserve the request):")
        self.assertIn({"kind": "postcondition", "role": "guarantee"}, guidance["kind_and_role_are_separate_fields"])
        self.assertEqual(["id", "supplied_by", "discharged_at"], guidance["assumptions_item"]["required"])
        self.assertEqual(["id", "description"], guidance["ambiguities_item"]["properties"]["alternatives"]["items"]["required"])
        self.assertIn("proposed_default", guidance["ambiguities_item"]["required"])
        self.assertNotIn("resolution", guidance["ambiguities_item"]["properties"])
        self.assertEqual([], draft.validate_draft(d, EXAMPLE_REQUEST, "request.txt"))
        self.assertEqual([], draft.validate_ledger(ledger, d, EXAMPLE_REQUEST, "request.txt")[0])

    def test_missing_assumption_supplier_is_repaired_without_dropping_assumption(self):
        good = copy.deepcopy(agents._ASSUMPTION_EXAMPLE)
        bad = copy.deepcopy(good)
        del bad["assumptions"][0]["discharged_at"]
        bad_text = json.dumps(bad)
        broker = CapturingBroker([bad_text, json.dumps(good)])
        prompt = agents._ASSUMPTION_REQUEST.encode()
        with patch.object(agents, "_broker", return_value=(broker, self.conf)):
            d, ledger = agents.interpreter_agent("unused", self.pkg, self.events, attempts=2)(prompt, "request.txt", {})
        self.assertEqual(2, len(broker.calls))
        self.assertIn(bad_text, broker.calls[1]["user"])
        self.assertIn("discharged_at", broker.calls[1]["user"])
        self.assertEqual(["A1"], [r["id"] for r in d["preconditions"]])
        self.assertEqual(good["assumptions"], ledger["assumptions"])
        self.assertEqual([], draft.validate_ledger(ledger, d, prompt, "request.txt")[0])

    def test_published_ambiguity_entry_and_alternative_repair_remain_unresolved(self):
        # Use the exact entry shown in the real prompt, linked to actual proposal IDs.
        entry = agents.extract_json(agents.INTERPRETER_SYSTEM.split("Example entry: ", 1)[1])
        prompt = b"Return a rounded number."
        good = interpreter_example()
        for rec in good["obligations"]:
            rec["sources"][0]["quote"] = prompt.decode()
            rec["dependencies"] = [{"id": "Q1", "relation": "blocked_by"}]
        question = copy.deepcopy(good["obligations"][0])
        question.update(id="Q1", kind="ambiguity", role="open_question", statement="The rounding rule is unspecified.", dependencies=[])
        good["obligations"].append(question)
        good["clauses"][0].update(quote=prompt.decode(), disposition="ambiguity", refs=["Q1"])
        good["ambiguities"] = [entry]
        bad = copy.deepcopy(good)
        bad["ambiguities"][0]["alternatives"] = ["floor", "nearest"]
        broker = CapturingBroker([json.dumps(bad), json.dumps(good)])
        with patch.object(agents, "_broker", return_value=(broker, self.conf)):
            d, ledger = agents.interpreter_agent("unused", self.pkg, self.events, attempts=2)(prompt, "request.txt", {})
        self.assertEqual(2, len(broker.calls))
        self.assertIn("alternatives", broker.calls[1]["user"])
        self.assertEqual([], draft.validate_draft(d, prompt, "request.txt"))
        self.assertEqual([], draft.validate_ledger(ledger, d, prompt, "request.txt")[0])
        self.assertEqual("unresolved", ledger["ambiguities"][0]["resolution"]["status"])
        self.assertEqual({"O1": ["Q1"]}, draft.blocked_obligations(d, ledger))

    def test_manifest_covers_duplicate_utf8_clauses_without_trusting_offsets(self):
        prompt = "Return café. Return café.".encode()
        proposed = interpreter_example()
        proposed["obligations"][0]["sources"][0]["quote"] = "Return café."
        manifest = agents._request_clauses(prompt)
        self.assertEqual(["C1", "C2"], [c["clause_id"] for c in manifest])
        proposed["clauses"] = [{**c, "start_byte": 999, "end_byte": 1000,
                                 "disposition": "obligations", "refs": ["O1"]} for c in manifest]
        d, ledger, problems = agents.assemble_interpretation(proposed, prompt, "request.txt")
        self.assertEqual([], problems)
        self.assertEqual([(c["start_byte"], c["end_byte"]) for c in manifest],
                         [(c["start_byte"], c["end_byte"]) for c in ledger["clauses"]])
        self.assertEqual([], draft.validate_ledger(ledger, d, prompt, "request.txt")[0])

    def test_mismatched_manifest_quote_is_rejected_and_remains_uncovered(self):
        proposed = interpreter_example()
        for change in ({"clause_id": "C404"}, {"quote": "Invented requirement."}):
            with self.subTest(change=change):
                altered = copy.deepcopy(proposed)
                altered["clauses"][0].update(change)
                d, ledger, problems = agents.assemble_interpretation(altered, EXAMPLE_REQUEST, "request.txt")
                self.assertTrue(problems)
                self.assertIn("UNCOVERED_SOURCE_CLAUSE", {x.code for x in draft.validate_ledger(ledger, d, EXAMPLE_REQUEST, "request.txt")[0]})

    def test_unknown_dependency_is_not_silently_deleted_and_repair_sees_exact_proposal(self):
        bad = interpreter_example()
        bad["obligations"][0]["dependencies"] = [{"id": "A1", "relation": "assumes"}]
        good = interpreter_example()
        bad_text = json.dumps(bad)
        broker = CapturingBroker([bad_text, json.dumps(good)])
        with patch.object(agents, "_broker", return_value=(broker, self.conf)):
            run = agents.interpreter_agent("unused", self.pkg, self.events, attempts=2)
            d, ledger = run(EXAMPLE_REQUEST, "request.txt", {})
        self.assertEqual(2, len(broker.calls))
        repaired = broker.calls[1]["user"]
        self.assertIn(bad_text, repaired)
        self.assertIn("dependency on unknown obligation A1", repaired)
        self.assertEqual(agents._request_clauses(EXAMPLE_REQUEST), section_json(repaired, "REQUEST CLAUSE MANIFEST (supervisor-owned exact quotes and UTF-8 byte spans):"))
        self.assertEqual([], draft.validate_draft(d, EXAMPLE_REQUEST, "request.txt"))
        self.assertEqual([], draft.validate_ledger(ledger, d, EXAMPLE_REQUEST, "request.txt")[0])

    def test_string_dependencies_are_repaired_using_schema_diagnostics(self):
        bad = interpreter_example()
        bad["obligations"][0]["dependencies"] = ["A1"]
        broker = CapturingBroker([json.dumps(bad), json.dumps(interpreter_example())])
        with patch.object(agents, "_broker", return_value=(broker, self.conf)):
            d, _ = agents.interpreter_agent("unused", self.pkg, self.events, attempts=2)(EXAMPLE_REQUEST, "request.txt", {})
        self.assertEqual(2, len(broker.calls))
        self.assertIn("dependencies", broker.calls[1]["user"])
        self.assertEqual([], d["postconditions"][0]["dependencies"])

    def test_malformed_sources_do_not_crash_before_bounded_repair(self):
        bad = interpreter_example()
        bad["obligations"][0]["sources"] = ["not an object"]
        broker = CapturingBroker([json.dumps(bad), json.dumps(interpreter_example())])
        with patch.object(agents, "_broker", return_value=(broker, self.conf)):
            d, _ = agents.interpreter_agent("unused", self.pkg, self.events, attempts=2)(EXAMPLE_REQUEST, "request.txt", {})
        self.assertEqual(2, len(broker.calls))
        self.assertIn("malformed interpretation proposal", broker.calls[1]["user"])
        self.assertEqual("O1", d["postconditions"][0]["id"])

    def test_binding_manifest_uses_actual_ids_roles_and_blocked_constraints(self):
        def record(oid, role, blocked=None):
            return {"id": oid, "role": role, "required": True, "dependencies": [], "blocked_by": blocked or []}
        records = [record("Domain9", "declaration"), record("Input8", "assumption"), record("Guarantee17", "guarantee"),
                   record("Excluded4", "exclusion"), record("Question6", "open_question"), record("Blocked19", "guarantee", ["Question6"])]
        manifest = agents._binding_manifest(records)
        self.assertEqual([r["id"] for r in records], [r["obligation"] for r in manifest])
        self.assertEqual({"obligation", "declarations"}, set(manifest[0]["binding"]))
        self.assertEqual({"obligation", "predicate"}, set(manifest[1]["binding"]))
        self.assertEqual({"obligation", "theorem"}, set(manifest[2]["binding"]))
        self.assertEqual({"obligation": "Excluded4"}, manifest[3]["binding"])
        self.assertEqual({"obligation": "Question6"}, manifest[4]["binding"])
        self.assertIsNone(manifest[5]["binding"])
        self.assertNotIn('"obligation":"N1"', agents.FORMALIZER_SYSTEM)
        self.assertIn("No-assumption requests need no assumption predicate", agents.FORMALIZER_SYSTEM)
        self.assertIn("never manufacture", agents.FORMALIZER_SYSTEM)
        self.assertIn("Do not replace a graph/collection operation with a Nat identity function", agents.FORMALIZER_SYSTEM)
        self.assertIn('"if C then P" is C → P', agents.FORMALIZER_SYSTEM)
        self.assertIn("Required branch guards are not new caller", agents.FORMALIZER_SYSTEM)
        self.assertIn("For a success/error result use Lean's builtin `Except E A` exactly", agents.FORMALIZER_SYSTEM)

    def test_dynamic_manifest_candidate_passes_and_unknown_n1_still_fails(self):
        d, ledger, _ = agents.assemble_interpretation(interpreter_example(), EXAMPLE_REQUEST, "request.txt")
        records = contract.interpreted_records(d, {})
        form = candidate_form([r["id"] for r in records])
        self.assertEqual([], formalize.validate_candidate(form, records))
        form["bindings"].append({"obligation": "N1"})
        self.assertTrue(any("unknown obligation N1" in x.message for x in formalize.validate_candidate(form, records)))

    def test_formalizer_receives_exact_prior_source_manifest_and_request(self):
        d, ledger, _ = agents.assemble_interpretation(interpreter_example(), EXAMPLE_REQUEST, "request.txt")
        records = contract.interpreted_records(d, {})
        prior = {"lean_source": "import Std\nnamespace Preserved\ndef ref (n : Nat) := n + 1\nend Preserved\n",
                 "formalization": candidate_form(["O1"])}
        response = {"lean_source": prior["lean_source"], "formalization": prior["formalization"]}
        broker = CapturingBroker([json.dumps(response)])
        fsutil.atomic_write(self.pkg.path("prompt"), EXAMPLE_REQUEST)
        requested = {"tier": 0, "target": "python", "endpoint": "test_campaign", "require_state": "TESTED", "policy": "strict"}
        self.pkg.set_meta("requested", requested)
        with patch.object(agents, "_broker", return_value=(broker, self.conf)):
            got = agents.formalizer_agent("unused", self.pkg, self.events)({"records": records, "ledger": ledger,
                "feedback": ["unknown identifier Preserved.valid"], "attempt": 2, "previous_candidate": prior})
        self.assertEqual((prior["lean_source"].encode(), prior["formalization"]), got)
        user = broker.calls[0]["user"]
        self.assertEqual(prior, section_json(user, "PREVIOUS CANDIDATE (untrusted source and binding proposal; repair rather than weaken):"))
        self.assertEqual([], section_json(user, "ASSUMPTIONS REQUIRING SATISFIABILITY WITNESSES:"))
        self.assertIn(EXAMPLE_REQUEST.decode(), user)
        self.assertIn("unknown identifier Preserved.valid", user)
        self.assertEqual(requested, section_json(user, "REQUESTED ASSURANCE AND IMPLEMENTATION BOUNDARY (supervisor-selected, not changeable by the proposal):"))
        self.assertIn("Opaque Lean acceptance cannot satisfy this requested assurance", user)

    def test_unparseable_formalizer_response_is_visible_during_repair(self):
        d, ledger, _ = agents.assemble_interpretation(interpreter_example(), EXAMPLE_REQUEST, "request.txt")
        records = contract.interpreted_records(d, {})
        invalid = '{"lean_source":null,"formalization":{"bindings":[{"obligation":"O1"}]}}'
        good = {"lean_source": "import Std\n", "formalization": candidate_form(["O1"])}
        broker = CapturingBroker([invalid, json.dumps(good)])
        with patch.object(agents, "_broker", return_value=(broker, self.conf)):
            role = agents.formalizer_agent("unused", self.pkg, self.events)
            ctx = {"records": records, "ledger": ledger, "feedback": [], "attempt": 1}
            source, form = role(ctx)
            self.assertIn("error", form)
            got = role({**ctx, "feedback": ["formalization candidate is invalid"], "attempt": 2,
                        "previous_candidate": {"lean_source": source.decode(), "formalization": form}})
        self.assertIn(invalid, broker.calls[1]["user"])
        self.assertEqual((good["lean_source"].encode(), good["formalization"]), got)

    def test_formalize_repairs_receive_rejected_source_and_binding_without_rewriting(self):
        d, ledger, _ = agents.assemble_interpretation(interpreter_example(), EXAMPLE_REQUEST, "request.txt")
        form = candidate_form(["O1"])
        proposals = [b"import Std\ntheorem before : missing := by sorry\n", b"import Std\ntheorem after : stillMissing := by sorry\n"]
        contexts = []
        seed = {"lean_source": "old exact source", "formalization": {"old": "manifest"}}

        def generator(ctx):
            contexts.append(copy.deepcopy(ctx))
            return proposals[len(contexts) - 1], copy.deepcopy(form)

        def reject(*args):
            return {"diagnostics": [Diagnostic("CANDIDATE_BUILD_FAILURE", "unknown identifier missing")]}

        with patch.object(formalize, "require_interpretation", return_value=(d, ledger, [])), \
             patch.object(formalize.leanbridge, "resolve_toolchain", return_value=object()), \
             patch.object(formalize, "attempt", side_effect=reject):
            result = formalize.run(self.pkg, self.events, agent=generator, max_attempts=2,
                                   recovery_feedback=["prior proof search found counterexample"], previous_candidate=seed)
        self.assertEqual("BLOCKED", result.status)
        self.assertEqual(2, len(contexts))
        self.assertEqual(seed, contexts[0]["previous_candidate"])
        self.assertEqual(["prior proof search found counterexample"], contexts[0]["feedback"])
        self.assertEqual({"lean_source": proposals[0].decode(), "formalization": form}, contexts[1]["previous_candidate"])
        self.assertEqual(["unknown identifier missing"], contexts[1]["feedback"])
        self.assertEqual(proposals[1], (self.pkg.path("contract") / "candidate/proposal.lean").read_bytes())

    def test_recovery_parameters_do_not_mutate_an_already_frozen_challenge(self):
        d, ledger, _ = agents.assemble_interpretation(interpreter_example(), EXAMPLE_REQUEST, "request.txt")
        fsutil.write_json(contract.challenge_dir(self.pkg) / "challenge.json", {})
        fsutil.write_json(contract.challenge_dir(self.pkg) / "formalization.json", candidate_form(["O1"]))
        calls = []
        with patch.object(formalize, "require_interpretation", return_value=(d, ledger, [])), \
             patch.object(contract, "load_frozen", return_value=({}, [])):
            result = formalize.run(self.pkg, self.events, agent=lambda ctx: calls.append(ctx),
                                   recovery_feedback=["repair"], previous_candidate={"lean_source": "changed"})
        self.assertEqual("BLOCKED", result.status)
        self.assertEqual([], calls)
        self.assertIn("CLAIM_MUTATION", {d.code for d in result.diagnostics})

    def implementation_context(self):
        profile = {"profile_id": "aligned.v0_1", "enums": {}, "predicates": {},
                   "symbols": {"increment": {"lean_decl": "Aligned.increment", "args": ["Nat"], "result": "Nat"}}}
        var = {"tag": "var", "index": 0}
        formula = {"tag": "forall", "sort": "Nat", "body": {"tag": "eq",
                   "left": {"tag": "call", "symbol": "increment", "args": [var]},
                   "right": {"tag": "add", "left": var, "right": {"tag": "nat", "value": "1"}}}}
        package = dsl.make_package(formula, profile["profile_id"])
        digest = canonical.digest_json(package)
        path = self.pkg.path("accepted") / "expressions" / (digest.split(":", 1)[1] + ".json")
        fsutil.write_json(path, package)
        rec = {"id": "Guarantee17", "revision": 3, "kind": "postcondition", "role": "guarantee", "required": True,
               "dependencies": [], "formal": {"representation": "contract_dsl", "lean_symbol": "Aligned.successor",
               "formula_ref": f"artifact:accepted-expressions/Guarantee17@{digest}", "statement_hash": "sha256:checked"}}
        ctx = {"ir": {"schema_version": "0.1", "artifact_kind": "accepted_obligations",
                      "bound_to": {"acceptance_certificate_hash": "sha256:kernel-accepted"},
                      "obligations": {"Guarantee17": rec}}, "profile": profile,
               "statements": {"Guarantee17": {"representation": "contract_dsl", "formula_package": package,
                              "semantic_closure": {"Aligned.increment": "sha256:checked"},
                              "display": "misleading commentary: output = input - 1"}},
               "parameters": {"target": "python", "tier": 0, "endpoint": "test_campaign"}}
        return ctx, package, path

    def implementation_proposal(self, symbol="increment", source="def increment(n):\n    return n + 1\n"):
        return {"files": {"increment.py": source}, "bindings": {
            "schema_version": "0.1", "artifact_kind": "implementation_bindings", "target": "python",
            "serialization_profile": "python-v0_1", "bindings": [{"binding_id": "B-increment", "symbol": symbol,
                "object": {"file": "increment.py", "qualname": "increment"}, "obligations": ["Guarantee17"]}], "helpers": []}}

    def test_implementer_receives_hash_bound_accepted_ast_and_full_profile(self):
        ctx, package, _ = self.implementation_context()
        fsutil.write_json(self.pkg.path("draft"), {"statement": "POISON_ORIGINAL_DRAFT"})
        fsutil.atomic_write(self.pkg.path("prompt"), b"POISON_ORIGINAL_REQUEST")
        broker = CapturingBroker([json.dumps(self.implementation_proposal())])
        with patch.object(agents, "_broker", return_value=(broker, self.conf)):
            files, _ = agents.implementer_agent("unused", self.pkg, self.events)(ctx)
        user = broker.calls[0]["user"]
        supplied = section_json(user, "ACCEPTED FORMULAS (authoritative formula_package ASTs; display is commentary):")
        self.assertEqual(package, supplied["formula_packages"][supplied["obligations"]["Guarantee17"]["formula_package_ref"]])
        self.assertEqual(ctx["ir"]["obligations"]["Guarantee17"]["formal"], supplied["obligations"]["Guarantee17"]["formal"])
        self.assertEqual(3, supplied["obligations"]["Guarantee17"]["revision"])
        self.assertEqual(ctx["profile"], section_json(user, "ACCEPTED SEMANTIC PROFILE (authoritative sorts and symbols to implement):"))
        provenance = section_json(user, "ACCEPTED IR PROVENANCE (artifact-derived, supervisor-checked):")
        self.assertEqual(canonical.digest_json(ctx["ir"]), provenance["accepted_ir_sha256"])
        self.assertEqual(ctx["ir"]["bound_to"], provenance["bound_to"])
        self.assertNotIn("POISON_ORIGINAL", user)
        self.assertIn("without annotations, defaults", broker.calls[0]["system"])
        self.assertIn("builtin calls", broker.calls[0]["system"])
        self.assertIn("left - right if right <= left else 0", broker.calls[0]["system"])
        manifest = section_json(user, "PYTHON BINDING MANIFEST (exact symbol keys, arities and permitted obligation IDs):")
        self.assertEqual("increment", manifest[0]["symbol"])
        self.assertEqual("Aligned.increment", manifest[0]["lean_decl"])
        self.assertEqual(1, manifest[0]["arity"])
        self.assertEqual(["Guarantee17"], manifest[0]["allowed_obligations"])
        self.assertEqual(b"def increment(n):\n    return n + 1\n", files["increment.py"])

    def test_implementer_rejects_mutated_accepted_package_before_model_call(self):
        ctx, package, path = self.implementation_context()
        altered = copy.deepcopy(package)
        altered["formula"]["body"]["right"]["right"]["value"] = "2"
        fsutil.write_json(path, altered)
        broker = CapturingBroker([])
        with patch.object(agents, "_broker", return_value=(broker, self.conf)), self.assertRaises(UsageError) as raised:
            agents.implementer_agent("unused", self.pkg, self.events)(ctx)
        self.assertEqual("INPUT_MUTATION", raised.exception.diagnostics[0].code)
        self.assertEqual([], broker.calls)

    def test_implementer_rejects_context_formula_different_from_accepted_ast(self):
        ctx, _, _ = self.implementation_context()
        ctx["statements"]["Guarantee17"]["formula_package"] = dsl.make_package({"tag": "true"}, ctx["profile"]["profile_id"])
        broker = CapturingBroker([])
        with patch.object(agents, "_broker", return_value=(broker, self.conf)), self.assertRaises(UsageError) as raised:
            agents.implementer_agent("unused", self.pkg, self.events)(ctx)
        self.assertEqual("IR_REIFICATION_MISMATCH", raised.exception.diagnostics[0].code)
        self.assertEqual([], broker.calls)

    def test_implementer_repairs_qualified_lean_name_instead_of_substituting_it(self):
        ctx, _, _ = self.implementation_context()
        bad = self.implementation_proposal("Aligned.increment")
        good = self.implementation_proposal()
        raw_bad = json.dumps(bad, indent=2)
        broker = CapturingBroker([raw_bad, json.dumps(good)])
        before = self.pkg.evidence.load()
        with patch.object(agents, "_broker", return_value=(broker, self.conf)):
            files, bindings = agents.implementer_agent("unused", self.pkg, self.events)(ctx)
        self.assertEqual(2, len(broker.calls))
        repair = broker.calls[1]["user"]
        self.assertIn(raw_bad, repair)
        self.assertIn("binding to unknown profile symbol Aligned.increment", repair)
        self.assertIn("no binding for required profile symbol increment", repair)
        self.assertEqual(good["bindings"], bindings)
        self.assertEqual(good["files"]["increment.py"].encode(), files["increment.py"])
        self.assertEqual(before, self.pkg.evidence.load())
        self.assertFalse(self.pkg.path("implementation").exists())

    def test_implementer_repairs_json_then_binding_schema_with_exact_previous_response(self):
        ctx, _, _ = self.implementation_context()
        bad = self.implementation_proposal()
        del bad["bindings"]["serialization_profile"]
        raw_bad = json.dumps(bad)
        broker = CapturingBroker(["{unclosed proposal", raw_bad, json.dumps(self.implementation_proposal())])
        with patch.object(agents, "_broker", return_value=(broker, self.conf)):
            agents.implementer_agent("unused", self.pkg, self.events)(ctx)
        self.assertEqual(3, len(broker.calls))
        self.assertIn("{unclosed proposal", broker.calls[1]["user"])
        self.assertIn("unparseable implementer proposal", broker.calls[1]["user"])
        self.assertIn(raw_bad, broker.calls[2]["user"])
        self.assertIn("serialization_profile", broker.calls[2]["user"])

    def test_implementer_uses_shared_object_arity_and_scope_checks(self):
        ctx, _, _ = self.implementation_context()
        bad = self.implementation_proposal(source="def increment(left, right):\n    return left + right\n")
        bad["bindings"]["bindings"][0]["obligations"].append("Invented1")
        raw_bad = json.dumps(bad)
        broker = CapturingBroker([raw_bad, json.dumps(self.implementation_proposal())])
        with patch.object(agents, "_broker", return_value=(broker, self.conf)):
            agents.implementer_agent("unused", self.pkg, self.events)(ctx)
        self.assertEqual(2, len(broker.calls))
        self.assertIn("signature does not accept exactly 1 positional argument(s)", broker.calls[1]["user"])
        self.assertIn("claims Invented1", broker.calls[1]["user"])
        self.assertIn(raw_bad, broker.calls[1]["user"])

    def test_implementer_structural_failure_exhausts_finite_calls_without_fabricated_candidate(self):
        ctx, _, _ = self.implementation_context()
        bad = self.implementation_proposal("Aligned.increment")
        broker = CapturingBroker([json.dumps(bad)] * 3)
        with patch.object(agents, "_broker", return_value=(broker, self.conf)), self.assertRaises(UsageError) as raised:
            agents.implementer_agent("unused", self.pkg, self.events)(ctx)
        self.assertEqual(3, len(broker.calls))
        self.assertIn("UNMAPPED_IMPLEMENTATION_OBJECT", {d.code for d in raised.exception.diagnostics})
        self.assertFalse(self.pkg.path("implementation").exists())

    def test_implementer_honors_explicit_call_cap_and_does_not_retry_infrastructure(self):
        ctx, _, _ = self.implementation_context()
        conf = {**self.conf, "review": {"budgets": {"max_calls_per_instance": 1}}}
        broker = CapturingBroker(["not JSON"])
        with patch.object(agents, "_broker", return_value=(broker, conf)), self.assertRaises(UsageError):
            agents.implementer_agent("unused", self.pkg, self.events)(ctx)
        self.assertEqual(1, len(broker.calls))
        broker = CapturingBroker([])
        error = InfrastructureError("offline", [Diagnostic("PROVIDER_FAILURE", "offline", severity="infrastructure")])
        with patch.object(agents, "_broker", return_value=(broker, self.conf)), \
             patch.object(broker, "call", side_effect=error) as call, self.assertRaises(InfrastructureError):
            agents.implementer_agent("unused", self.pkg, self.events)(ctx)
        self.assertEqual(1, call.call_count)

    def assert_candidate_paths_are_repaired(self, extra_files):
        ctx, _, _ = self.implementation_context()
        good = self.implementation_proposal()
        bad = copy.deepcopy(good)
        bad["files"].update(extra_files)
        raw_bad = json.dumps(bad)
        broker = CapturingBroker([raw_bad, json.dumps(good)])
        conf = {**self.conf, "review": {"budgets": {"max_calls_per_instance": 2}}}
        original_conf = copy.deepcopy(conf)
        before = self.pkg.evidence.load()
        try:
            with patch.object(agents, "_broker", return_value=(broker, conf)):
                files, bindings = agents.implementer_agent("unused", self.pkg, self.events)(ctx)
        finally:
            self.assertEqual(before, self.pkg.evidence.load())
            self.assertEqual(original_conf, conf)
            self.assertFalse(self.pkg.path("implementation").exists())
        self.assertEqual(2, len(broker.calls), "the malformed path proposal must receive one bounded correction")
        self.assertEqual(["implementer/1", "implementer/1"], [call["instance"] for call in broker.calls])
        self.assertIn(raw_bad, broker.calls[1]["user"])
        diagnostics = section_json(broker.calls[1]["user"], "IMPLEMENTATION PROPOSAL VALIDATOR DIAGNOSTICS:")
        self.assertTrue(diagnostics)
        self.assertEqual({"INVALID_CANDIDATE"}, {diagnostic["code"] for diagnostic in diagnostics})
        self.assertEqual(good["bindings"], bindings)
        self.assertEqual({path: source.encode() for path, source in good["files"].items()}, files)

    def test_implementer_repairs_file_directory_prefix_collisions_in_both_orders(self):
        for paths in (("a.py", "a.py/b.py"), ("a.py/b.py", "a.py")):
            with self.subTest(paths=paths):
                self.assert_candidate_paths_are_repaired({path: "# candidate path fixture\n" for path in paths})

    def test_implementer_repairs_casefold_collision_in_unused_source_path(self):
        self.assert_candidate_paths_are_repaired({"INCREMENT.py": "# candidate path fixture\n"})

    def test_implementer_repairs_nul_in_unused_source_path(self):
        self.assert_candidate_paths_are_repaired({"bad\u0000.py": "# candidate path fixture\n"})


if __name__ == "__main__":
    unittest.main()
