"""The specification's acceptance scenarios (§13), exercised end to end with the real Lean toolchain.

Run from the repository root:  python3 -m unittest discover -s tests -v
A shared base package is built once (full pipeline, VERIFIED); mutation scenarios work on copies.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import unittest
from pathlib import Path

from helpers import (EX, TempDir, build, codes, copy_pkg, formalization_variant, impl_variant, json_variant, run_cli,
                     stage, writable)
from verislop import canonical

TMP: TempDir = None  # type: ignore[assignment]  # set in setUpModule
BASE: Path = None  # type: ignore[assignment]


def setUpModule() -> None:
    global TMP, BASE
    TMP = TempDir()
    BASE = TMP.path / "base"
    res = build(BASE, "verify")
    assert res["verify"][0] == 0, res["verify"]


def tearDownModule() -> None:
    TMP.cleanup()


def view(pkg: Path) -> dict:
    run_cli("status", "--package", str(pkg))
    return canonical.load_file(pkg / "obligation-view.json")["obligations"]


def report(pkg: Path) -> dict:
    return canonical.load_file(pkg / "report.json")


BOUNDED = (EX / "lean" / "BoundedIncrement.lean").read_text()
# The fixture without its illustrative metadata section (so signature edits still elaborate).
BOUNDED_CORE = BOUNDED.split("inductive ObligationKind where")[0] + "end VeriSlop.BoundedIncrement\n"


class S01Routing(unittest.TestCase):
    def test_draft_has_all_ten_categories_before_generation(self):
        d = canonical.load_file(BASE / "draft.json")
        for cat in ("entities", "preconditions", "postconditions", "invariants", "safety_properties", "liveness_properties",
                    "resource_constraints", "error_semantics", "explicit_non_goals", "ambiguities"):
            self.assertIsInstance(d[cat], list, cat)
        empty = TMP.path / "s01-empty"
        empty.mkdir()
        code, _, _ = run_cli("generate", "--package", str(empty), "--candidate", str(EX / "python"))
        self.assertEqual(code, 64)  # no interpretation, no accepted IR: generation cannot start

    def test_non_software_is_not_applicable_not_success(self):
        p = TMP.path / "s01-poem"
        p.mkdir()
        prompt = TMP.path / "poem.txt"
        prompt.write_text("Write a poem and a short story about my travel itinerary.")
        code, res = stage(p, "interpret", "--prompt-file", str(prompt), "--non-interactive")
        self.assertEqual(code, 2)
        self.assertIn("NOT_APPLICABLE_ROUTING", codes(res))

    def test_uncertain_never_bypasses_and_forced_mode_overrides_classifier(self):
        p = TMP.path / "s01-uncertain"
        p.mkdir()
        prompt = TMP.path / "vague.txt"
        prompt.write_text("Make it better.")
        code, res = stage(p, "interpret", "--prompt-file", str(prompt), "--non-interactive")
        self.assertEqual(code, 2)
        self.assertIn("INTERPRETATION_UNRESOLVED", codes(res))
        code, res, _ = run_cli("classify", "--prompt-file", str(prompt), "--mode", "software")
        self.assertEqual(res["summary"]["routing_result"], "OBLIGATION_PIPELINE")


    def test_attachments_are_immutable_citable_documents(self):
        notes = TMP.path / "notes.md"
        notes.write_text("Callers are internal services; limit never exceeds 4096.")
        ref = notes.as_posix()
        blob = notes.read_bytes()

        def cite(d, digest):
            d["entities"][0]["source_refs"].append({"document_ref": ref, "document_hash": digest, "start_byte": 0,
                                                    "end_byte": len(blob), "origin": "explicit", "interpretation": "deployment note"})
            return d

        good = json_variant(TMP.path, EX / "draft.json", "s01-att-good.json", lambda d: cite(d, canonical.digest(blob)))
        p = TMP.path / "s01-att"
        p.mkdir()
        code, res = stage(p, "interpret", "--prompt-file", str(EX / "request.txt"), "--request-ref", "examples/request.txt",
                          "--attachment", str(notes), "--repository-revision", "abc123", "--candidate", str(good),
                          "--ledger", str(EX / "interpretation.json"), "--non-interactive")
        self.assertEqual(code, 0, res)
        req = canonical.load_file(p / "request" / "request.json")
        self.assertEqual(req["repository_revision"], "abc123")
        self.assertEqual(req["attachments"][0]["sha256"], canonical.digest(blob))
        bad = json_variant(TMP.path, EX / "draft.json", "s01-att-bad.json", lambda d: cite(d, "sha256:" + "0" * 64))
        p2 = TMP.path / "s01-att-bad"
        p2.mkdir()
        code, res = stage(p2, "interpret", "--prompt-file", str(EX / "request.txt"), "--request-ref", "examples/request.txt",
                          "--attachment", str(notes), "--candidate", str(bad), "--ledger", str(EX / "interpretation.json"),
                          "--non-interactive")
        self.assertEqual(code, 2)
        self.assertIn("INPUT_MUTATION", codes(res))


class S02Ambiguity(unittest.TestCase):
    def test_ambiguity_blocks_dependent_guarantee_only(self):
        q = {"id": "Q1", "revision": 1, "kind": "ambiguity", "role": "open_question",
             "statement": "Should the limit itself be a valid success output?", "required": False,
             "source_refs": [{"document_ref": "examples/request.txt", "document_hash": "sha256:2213797320bd7e3039f08522754c441e3654d5e0f00918aa837ae0cdd15cfe1c",
                              "start_byte": 156, "end_byte": 186, "origin": "explicit", "interpretation": "error boundary"}],
             "scope": ["mathematical Nat reference model"], "dependencies": [], "acceptance_criteria": ["Resolve before formalizing E1."],
             "state": "INTERPRETED", "lifecycle": json.loads(json.dumps(canonical.load_file(EX / "draft.json")["explicit_non_goals"][0]["lifecycle"]))}

        def edit_draft(d):
            d["ambiguities"].append(q)
            return d

        def edit_ledger(l):
            l["clauses"].append({"start_byte": 156, "end_byte": 186, "disposition": "ambiguity", "refs": ["Q1"]})
            l["ambiguities"].append({"id": "Q1", "alternatives": [{"id": "error", "description": "limit is an error"},
                                                                   {"id": "success", "description": "limit succeeds"}],
                                     "affected_obligations": ["E1"], "impact": ["failure_behavior"],
                                     "resolution": {"status": "unresolved", "selected": None, "provenance": {"kind": "none", "detail": "open"}}})
            return l

        draft = json_variant(TMP.path, EX / "draft.json", "s02-draft.json", edit_draft)
        ledger = json_variant(TMP.path, EX / "interpretation.json", "s02-ledger.json", edit_ledger)
        form = formalization_variant(TMP.path, "s02-form", form_edit=lambda f: {
            **f, "bindings": [b for b in f["bindings"] if b["obligation"] != "E1"] + [{"obligation": "Q1"}]})
        pkg = TMP.path / "s02"
        res = build(pkg, "verify", draft=draft, ledger=ledger, formalization=form)
        self.assertIn("INTERPRETATION_UNRESOLVED", codes(res["interpret"][1]))
        self.assertEqual(res["formalize"][0], 2)  # frozen, with E1 reported as blocked
        self.assertTrue((pkg / "contract" / "challenge" / "challenge.json").is_file())
        v = view(pkg)
        self.assertEqual(v["O17"]["lifecycle"]["PROVED"]["outcome"], "PASS")  # independent proof work continued
        self.assertEqual(v["I2"]["lifecycle"]["PROVED"]["outcome"], "PASS")
        self.assertEqual(v["E1"]["lifecycle"]["FORMALIZED"]["outcome"], "PENDING")
        self.assertIn("blocked by unresolved ambiguity Q1", v["E1"]["lifecycle"]["FORMALIZED"]["reason"])
        self.assertEqual(v["Q1"]["lifecycle"]["PROVED"]["outcome"], "NOT_APPLICABLE")  # scenario 19 for open questions
        self.assertEqual(report(pkg)["terminal_status"], "BLOCKED")
        self.assertIn("INTERPRETATION_UNRESOLVED", {d["code"] for d in report(pkg)["blocking_reasons"]})


def prove_accept(name: str, lean_source: str, portfolio: bool = True) -> tuple[Path, dict]:
    pkg = copy_pkg(BASE, TMP.path / name)
    cand = TMP.path / f"{name}.lean"
    cand.write_text(lean_source)
    args = ["--candidate", str(cand)] + ([] if portfolio else ["--no-portfolio"])
    stage(pkg, "prove", *args)
    code, res = stage(pkg, "accept")
    return pkg, res


class S03StatementIdentity(unittest.TestCase):
    def test_changed_definition_rejected(self):
        src = (EX / "formalization" / "Contract.lean").read_text().replace("input ≤ limit", "input < limit + 1")
        _, res = prove_accept("s03-def", src)
        self.assertIn("STATEMENT_MISMATCH", codes(res))
        self.assertEqual(res["summary"]["gate"], "blocked")
        self.assertEqual(res["summary"]["obligations"]["E1"]["typechecked"], "FAIL")

    def test_weakened_theorem_rejected(self):
        src = BOUNDED_CORE.replace("(h : increment limit input = .ok output) : output = input + 1 := by",
                                   "(hsmall : input < 10) (h : increment limit input = .ok output) : output = input + 1 := by")
        self.assertNotEqual(src, BOUNDED_CORE)
        _, res = prove_accept("s03-weak", src)
        self.assertIn("STATEMENT_MISMATCH", codes(res))
        self.assertEqual(res["summary"]["obligations"]["O17"]["proved"], "FAIL")


class S04Axioms(unittest.TestCase):
    def test_sorry_fails_acceptance(self):
        _, res = prove_accept("s04-sorry", (EX / "formalization" / "Contract.lean").read_text(), portfolio=False)
        self.assertIn("PROOF_UNRESOLVED", codes(res))
        self.assertEqual(res["summary"]["obligations"]["O17"]["proved"], "FAIL")
        self.assertEqual(res["summary"]["obligations"]["O17"]["typechecked"], "PASS")

    def test_hidden_unauthorized_axiom_fails(self):
        src = BOUNDED.replace("/-- O17: every successful result is exactly one more than the input. -/",
                              "axiom cheat : False\n\ntheorem helper_lemma (n : Nat) : n = n := cheat.elim\n\n"
                              "/-- O17: every successful result is exactly one more than the input. -/")
        src = src.replace("""    (h : increment limit input = .ok output) : output = input + 1 := by
  unfold increment at h""", """    (h : increment limit input = .ok output) : output = input + 1 := by
  have _ := helper_lemma 0
  unfold increment at h""")
        _, res = prove_accept("s04-axiom", src, portfolio=False)
        self.assertIn("INADMISSIBLE_AXIOM", codes(res))
        self.assertEqual(res["summary"]["obligations"]["O17"]["proved"], "FAIL")
        self.assertIn("VeriSlop.BoundedIncrement.cheat", res["summary"]["obligations"]["O17"]["axioms"])

    def test_native_evaluation_axiom_fails_and_blocks_dependent_witness(self):
        src = BOUNDED.replace("exact ⟨1, 0, 1, by unfold validInput; decide, rfl⟩", "exact ⟨1, 0, 1, by unfold validInput; native_decide, rfl⟩")
        self.assertNotEqual(src, BOUNDED)
        _, res = prove_accept("s04-native", src, portfolio=False)
        self.assertIn("INADMISSIBLE_AXIOM", codes(res))
        obl = res["summary"]["obligations"]
        self.assertEqual(obl["W1"]["proved"], "FAIL")
        self.assertEqual(obl["E1"]["proved"], "FAIL")       # its witness obligation is not accepted
        self.assertIn("MISSING_WITNESS", obl["E1"]["codes"])


class S05FalsePrecondition(unittest.TestCase):
    def test_false_precondition_gets_no_witness(self):
        form = formalization_variant(TMP.path, "s05-form", lean_edit=lambda s: s.replace("input ≤ limit", "input < 0"))
        pkg = TMP.path / "s05"
        res = build(pkg, "accept", formalization=form)
        acc = res["accept"][1]["summary"]["obligations"]
        self.assertEqual(acc["W1"]["proved"], "FAIL")
        self.assertEqual(acc["E1"]["proved"], "FAIL")       # vacuously provable, but its precondition has no witness
        self.assertIn("MISSING_WITNESS", acc["E1"]["codes"])
        self.assertEqual(res["accept"][1]["summary"]["gate"], "blocked")


class S06S07ExportIntegrity(unittest.TestCase):
    def test_draft_mutation_cannot_change_reexport_and_artifact_mutation_invalidates(self):
        pkg = copy_pkg(BASE, TMP.path / "s06")
        before = (pkg / "accepted" / "accepted-ir.json").read_bytes()
        writable(pkg / "draft.json")
        d = canonical.load_file(pkg / "draft.json")
        d["postconditions"][0]["statement"] = "Every successful output equals input + 2."
        (pkg / "draft.json").write_text(json.dumps(d))
        code, res = stage(pkg, "export")
        self.assertEqual(code, 0, res)
        self.assertTrue(res["summary"]["byte_identical_to_previous"])
        self.assertEqual((pkg / "accepted" / "accepted-ir.json").read_bytes(), before)
        (pkg / "draft.json").unlink()
        code, res = stage(pkg, "export")
        self.assertEqual(code, 0)
        self.assertEqual((pkg / "accepted" / "accepted-ir.json").read_bytes(), before)
        cert = canonical.load_file(pkg / "accepted" / "acceptance.json")
        olean = pkg / cert["artifacts"]["olean"]["path"]
        writable(olean)
        data = bytearray(olean.read_bytes())
        data[-1] ^= 0xFF
        olean.write_bytes(bytes(data))
        code, res = stage(pkg, "export")
        self.assertEqual(code, 2)
        self.assertIn("INPUT_MUTATION", codes(res))

    def test_reification_checks_recorded(self):
        ir = canonical.load_file(BASE / "accepted" / "accepted-ir.json")
        self.assertEqual(ir["obligations"]["O17"]["formal"]["representation"], "contract_dsl")
        evs = [json.loads(p.read_text()) for p in (BASE / "evidence").glob("ev-*.json")]
        reified = [e for e in evs if e["claim_id"].startswith("REIFIED:O17")]
        self.assertTrue(reified)
        raw = json.loads((BASE / reified[-1]["raw_result_ref"]).read_text())
        self.assertEqual(raw["check"]["denotation_defeq"], {"defeq": True, "ok": True, "typechecks": True})
        self.assertTrue(raw["check"]["round_trip"])
        pkgref = ir["obligations"]["O17"]["formal"]["formula_ref"].rsplit("@", 1)[1].split(":")[1]
        package = canonical.load_file(BASE / "accepted" / "expressions" / f"{pkgref}.json")
        doc = json.loads((EX.parent / "docs" / "contract-ir.md").read_text().split("```json")[1].split("```")[0])
        self.assertEqual(package["formula"], doc["formula"])  # matches the specification's O17 package exactly


class S08Opaque(unittest.TestCase):
    def test_opaque_statement_gets_no_fabricated_oracle(self):
        o18 = json.loads(json.dumps(canonical.load_file(EX / "draft.json")["postconditions"][0]))
        o18.update({"id": "O18", "statement": "A successful output, read as an integer, equals input + 1."})

        def edit_draft(d):
            d["postconditions"].append(o18)
            return d

        def edit_ledger(l):
            l["clauses"][2]["refs"] = ["O17", "O18"]
            return l

        thm = ("\ntheorem success_as_int (limit input output : Nat) (h : increment limit input = .ok output) :\n"
               "    (output : Int) = (input : Int) + 1 := by\n  sorry\n\nend VeriSlop.BoundedIncrement")
        form = formalization_variant(TMP.path, "s08-form",
                                     lean_edit=lambda s: s.replace("\nend VeriSlop.BoundedIncrement", thm),
                                     form_edit=lambda f: {**f, "bindings": f["bindings"] + [{"obligation": "O18", "theorem": "VeriSlop.BoundedIncrement.success_as_int"}]})
        proof = TMP.path / "s08-proof.lean"
        proof.write_text(BOUNDED.replace("\ninductive ObligationKind where",
                                         "\ntheorem success_as_int (limit input output : Nat) (h : increment limit input = .ok output) :\n"
                                         "    (output : Int) = (input : Int) + 1 := by\n  have := success_is_successor limit input output h\n  omega\n"
                                         "\ninductive ObligationKind where"))
        pkg = TMP.path / "s08"
        res = build(pkg, "verify", draft=json_variant(TMP.path, EX / "draft.json", "s08-draft.json", edit_draft),
                    ledger=json_variant(TMP.path, EX / "interpretation.json", "s08-ledger.json", edit_ledger),
                    formalization=form, proof=proof)
        self.assertEqual(res["accept"][0], 0, res["accept"])
        ir = canonical.load_file(pkg / "accepted" / "accepted-ir.json")
        self.assertEqual(ir["obligations"]["O18"]["formal"]["representation"], "lean_expr")
        v = view(pkg)
        self.assertEqual(v["O18"]["lifecycle"]["PROVED"]["outcome"], "PASS")
        self.assertEqual(v["O18"]["lifecycle"]["TESTED"]["outcome"], "UNSUPPORTED")
        self.assertIn("UNSUPPORTED_SEMANTICS", codes(res["test"][1]))
        self.assertEqual(report(pkg)["terminal_status"], "BLOCKED")


class S09MetadataAuthority(unittest.TestCase):
    def test_registry_status_string_has_no_authority(self):
        src = BOUNDED + '\ndef VeriSlop.Registry.status : String := "PROVED"\n'
        _, res = prove_accept("s09", src, portfolio=False)
        self.assertIn("CLAIM_MUTATION", codes(res))
        self.assertEqual(res["summary"]["gate"], "blocked")


class S10ChangedTarget(unittest.TestCase):
    def test_changed_target_invalidates_implementation_evidence_only(self):
        pkg = copy_pkg(BASE, TMP.path / "s10")
        f = pkg / "implementation" / "bounded_increment.py"
        writable(f)
        f.write_text(f.read_text() + "\n# edited after testing\n")
        v = view(pkg)
        life = v["O17"]["lifecycle"]
        self.assertEqual(life["PROVED"]["outcome"], "PASS")
        for m in ("IMPLEMENTED", "LINKED", "TESTED"):
            self.assertEqual(life[m]["outcome"], "STALE", m)
        code, res = stage(pkg, "verify")
        self.assertEqual(code, 2)
        self.assertIn("STALE_OR_UNBOUND_EVIDENCE", codes(res))


class S11CampaignAdequacy(unittest.TestCase):
    def test_zero_effective_cases_fail(self):
        impl = impl_variant(TMP.path, "s11-impl", "def increment(limit, input):\n    return ('error', 'limitReached')\n")
        pkg = TMP.path / "s11"
        res = build(pkg, "test", impl=impl)
        summ = res["test"][1]["summary"]["obligations"]
        self.assertEqual(summ["O17"]["codes"], ["EMPTY_TEST_CAMPAIGN"])
        self.assertEqual(summ["O17"]["counts"]["effective"], 0)
        self.assertIn("TEST_FAILURE", summ["E1"]["codes"])

    def test_binding_outside_the_artifact_cannot_be_tested(self):
        bindings = json.loads((EX / "python" / "bindings.json").read_text())
        bindings["bindings"][0]["object"]["file"] = "../reference/bounded_increment.py"
        impl = impl_variant(TMP.path, "s11-ref", (EX / "python" / "bounded_increment.py").read_text(), bindings)
        pkg = TMP.path / "s11-ref-pkg"
        res = build(pkg, "test", impl=impl)
        self.assertIn("UNMAPPED_IMPLEMENTATION_OBJECT", codes(res["link"][1]))
        v = view(pkg)
        self.assertNotEqual(v["O17"]["lifecycle"]["TESTED"]["outcome"], "PASS")


class S12Tier1(unittest.TestCase):
    def test_tier1_is_detection_and_never_e2e(self):
        pkg = TMP.path / "s12"
        res = build(pkg, "verify", tier="1")
        self.assertEqual(res["verify"][0], 0, res["verify"])
        placement = canonical.load_file(pkg / "bridges" / "tier1" / "placement.json")
        self.assertTrue(placement["violation_behavior"].startswith("detection"))
        self.assertTrue(placement["bypassable"])
        self.assertIn("detection", report(pkg)["qualified_result"])
        self.assertEqual(view(pkg)["O17"]["lifecycle"]["END_TO_END_VERIFIED"]["outcome"], "UNSUPPORTED")


class S13S14Endpoints(unittest.TestCase):
    def test_requested_endpoints_beyond_tier_are_blocked(self):
        for extra in (["--endpoint", "native-binary"], ["--endpoint", "restricted-source"], ["--require-state", "END_TO_END_VERIFIED"]):
            pkg = copy_pkg(BASE, TMP.path / "s14")
            code, res = stage(pkg, "verify", *extra)
            self.assertEqual(code, 2, extra)
            self.assertIn("UNSUPPORTED_CAPABILITY", codes(res))
            self.assertNotEqual(report(pkg)["terminal_status"], "VERIFIED")

    def test_unsupported_tiers_give_capability_diagnostics(self):
        for tier in ("2", "3", "4"):
            pkg = copy_pkg(BASE, TMP.path / f"s13-{tier}")
            for p in ("closure", "implementation", "bridges", "tests"):
                if (pkg / p).exists():
                    writable(pkg / p)
                    import shutil
                    shutil.rmtree(pkg / p)
            code, res = stage(pkg, "generate", "--candidate", str(EX / "python"), "--tier", tier)
            self.assertEqual(code, 2)
            self.assertIn("UNSUPPORTED_CAPABILITY", codes(res))


class S15Profiles(unittest.TestCase):
    CASES = {
        "list-not-tuple": "def increment(limit, input):\n    return ['ok', input + 1] if input < limit else ('error', 'limitReached')\n",
        "overflow": "def increment(limit, input):\n    if input >= 2**64 - 1:\n        raise OverflowError('u64')\n    return ('ok', input + 1) if input < limit else ('error', 'limitReached')\n",
        "error-state": "def increment(limit, input):\n    return ('ok', input + 1) if input < limit else ('error', 'LimitReached')\n",
    }

    def test_profile_mismatches_are_caught(self):
        for name, src in self.CASES.items():
            pkg = TMP.path / f"s15-{name}"
            res = build(pkg, "test", impl=impl_variant(TMP.path, f"s15-{name}-impl", src))
            self.assertEqual(res["test"][0], 2, name)
            self.assertIn("TEST_FAILURE", codes(res["test"][1]), name)

    def test_cancellation_is_an_incomplete_run(self):
        import verislop.testing as t

        original = t.run

        def interrupted(*a, **k):
            raise KeyboardInterrupt

        t.run = interrupted
        try:
            code, _, _ = run_cli("run", "--prompt-file", str(EX / "request.txt"), "--request-ref", "examples/request.txt",
                                 "--runs-dir", str(TMP.path / "s15-runs"),
                                 "--run-id", "run-cancel", "--draft-candidate", str(EX / "draft.json"),
                                 "--ledger-candidate", str(EX / "interpretation.json"),
                                 "--formalization-candidate", str(EX / "formalization"),
                                 "--implementation-candidate", str(EX / "python"), "--non-interactive")
        finally:
            t.run = original
        self.assertEqual(code, 130)
        rep = report(TMP.path / "s15-runs" / "run-cancel")
        self.assertEqual(rep["terminal_status"], "BLOCKED")
        self.assertIn("INTERRUPTED", rep["qualified_result"])


class S16Liveness(unittest.TestCase):
    def test_finite_campaign_cannot_discharge_liveness_or_resources(self):
        from verislop import dsl, testing
        from verislop.contract import frozen_json
        from verislop.package import Package

        pkg = Package(BASE)
        ir = canonical.load_file(BASE / "accepted" / "accepted-ir.json")
        claims = canonical.load_file(BASE / "closure" / "implementation-claims.json")
        link = canonical.load_file(BASE / "bridges" / "link.json")
        cfg = canonical.load_file(BASE / "tests" / "campaign.json")
        ir["obligations"]["O17"]["kind"] = "liveness_property"
        ir["obligations"]["I2"]["kind"] = "resource_constraint"
        out = testing.execute(BASE / "implementation", link, claims, ir, dsl.Profile.from_json(frozen_json(pkg, "profile.json")),
                              cfg, BASE / "accepted" / "expressions", {})
        self.assertEqual(out["obligations"]["O17"]["outcome"], "UNSUPPORTED")
        self.assertEqual(out["obligations"]["I2"]["outcome"], "UNSUPPORTED")
        self.assertEqual(out["obligations"]["E1"]["outcome"], "PASS")


class S17Closure(unittest.TestCase):
    def test_nondeterministic_target_blocks(self):
        src = ("_n = [0]\n\ndef increment(limit, input):\n    _n[0] += 1\n    if input < limit:\n"
               "        return ('ok', input + 1 + (_n[0] % 2))\n    return ('error', 'limitReached')\n")
        pkg = TMP.path / "s17-nd"
        res = build(pkg, "test", impl=impl_variant(TMP.path, "s17-nd-impl", src))
        self.assertIn("NONDETERMINISM", codes(res["test"][1]))

    def test_orphan_claim_blocks(self):
        pkg = copy_pkg(BASE, TMP.path / "s17-orphan")
        p = pkg / "closure" / "implementation-claims.json"
        writable(p)
        c = canonical.load_file(p)
        c["claims"].append({"claim_id": "PUBLIC:fastest", "obligation": None, "milestone": None, "required": True, "applicable": True,
                            "verifier": "marketing.department", "pass_predicate": "trust us", "severity": "blocking", "reason": "x"})
        p.write_bytes(canonical.dumps(c))
        code, res = stage(pkg, "verify")
        self.assertEqual(code, 2)
        self.assertIn("ORPHAN_CLAIM", codes(res))


class S18InfrastructureFailure(unittest.TestCase):
    def test_crashed_checker_is_infrastructure_failure_and_keeps_evidence(self):
        pkg = copy_pkg(BASE, TMP.path / "s18")
        before = sorted(p.name for p in (pkg / "evidence").glob("ev-*.json"))
        from verislop import leanbridge

        leanbridge._identity.cache_clear()
        code, res, _ = run_cli("verify", "--package", str(pkg), env={"VERISLOP_LEAN_PREFIX": str(TMP.path / "no-such-toolchain")})
        leanbridge._identity.cache_clear()
        self.assertEqual(code, 3)
        rep = report(pkg)
        self.assertEqual(rep["terminal_status"], "INFRASTRUCTURE_FAILURE")
        self.assertNotIn("VERIFIED closure", rep["qualified_result"])
        after = sorted(p.name for p in (pkg / "evidence").glob("ev-*.json"))
        self.assertTrue(set(before) <= set(after))


class S19NoFabricatedProofs(unittest.TestCase):
    def test_non_guarantees_never_get_proof_milestones(self):
        v = view(BASE)
        for oid in ("D1", "A3", "N1"):
            self.assertEqual(v[oid]["lifecycle"]["PROVED"]["outcome"], "NOT_APPLICABLE", oid)
        self.assertEqual(v["N1"]["lifecycle"]["TESTED"]["outcome"], "NOT_APPLICABLE")


class S20Report(unittest.TestCase):
    def test_report_states_endpoint_roots_assumptions_trust_coverage(self):
        rep = report(BASE)
        self.assertEqual(rep["terminal_status"], "VERIFIED")
        self.assertEqual(rep["qualified_result"], "VERIFIED closure; implementation assurance: TESTED (Tier 0)")
        self.assertEqual(rep["tier"]["endpoint"], "test_campaign")
        self.assertFalse(rep["endpoint"]["end_to_end_eligible"])
        self.assertTrue(rep["roots"]["closure_input_root"].startswith("sha256:"))
        self.assertEqual(rep["hypotheses"]["E1"], ["A3"])
        self.assertTrue(rep["surfaces"]["trusted"])
        self.assertTrue(all(p["outcome"] == "PASS" for p in rep["provenance"]))
        self.assertEqual(len(rep["builds"]), 2)
        self.assertEqual(rep["determinism"]["mismatches"], [])
        for oid in ("O17", "I2", "E1"):
            self.assertTrue(rep["obligations"][oid]["end_to_end"].startswith("UNSUPPORTED"))


if __name__ == "__main__":
    unittest.main()
