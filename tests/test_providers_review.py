"""Provider broker, credentials, agent roles and hierarchical review (providers-and-review.md §9),
against a loopback mock of an OpenAI-compatible service. No real credentials or network are used."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import re
import unittest

from helpers import (EX, MockLLM, TempDir, build, codes, copy_pkg, impl_variant, mock_config, run_cli, unanimous,
                     writable)
from verislop import canonical

SECRET = "test-secret-123"

PROPOSAL = {
    "obligations": [
        {"id": "D1", "kind": "entity", "role": "declaration", "statement": "limit, input and outputs are Nat; failure is limitReached.",
         "required": True, "scope": ["mathematical Nat reference model"], "dependencies": [],
         "acceptance_criteria": ["Typecheck the domain declarations."],
         "sources": [{"quote": "Define a mathematical bounded increment over natural numbers.", "origin": "explicit", "interpretation": "domain"}]},
        {"id": "A3", "kind": "precondition", "role": "assumption", "statement": "The caller supplies input <= limit.", "required": True,
         "scope": ["mathematical Nat reference model"], "dependencies": [{"id": "D1", "relation": "uses_definition"}],
         "acceptance_criteria": ["Explicit hypothesis."],
         "sources": [{"quote": "The caller supplies limit and input with input <= limit.", "origin": "explicit", "interpretation": "caller domain"}]},
        {"id": "O17", "kind": "postcondition", "role": "guarantee", "statement": "Every successful output equals input + 1.", "required": True,
         "scope": ["mathematical Nat reference model"], "dependencies": [{"id": "D1", "relation": "uses_definition"}],
         "acceptance_criteria": ["Prove for the reference function."],
         "sources": [{"quote": "Return input + 1 when input < limit", "origin": "explicit", "interpretation": "success value"}]},
        {"id": "I2", "kind": "invariant", "role": "guarantee", "statement": "Every successful output is at most limit.", "required": True,
         "scope": ["mathematical Nat reference model"], "dependencies": [{"id": "D1", "relation": "uses_definition"}],
         "acceptance_criteria": ["Prove for the reference function."],
         "sources": [{"quote": "Every successful output must be at most limit.", "origin": "explicit", "interpretation": "bound"}]},
        {"id": "E1", "kind": "error_semantics", "role": "guarantee", "statement": "Under input <= limit, limitReached occurs iff input = limit.",
         "required": True, "scope": ["mathematical Nat reference model"],
         "dependencies": [{"id": "A3", "relation": "assumes"}, {"id": "D1", "relation": "uses_definition"}],
         "acceptance_criteria": ["Prove with the precondition as a hypothesis."],
         "sources": [{"quote": "otherwise return limitReached.", "origin": "explicit", "interpretation": "error case"}]},
        {"id": "N1", "kind": "explicit_non_goal", "role": "exclusion", "statement": "No target-language or machine-level claim.", "required": False,
         "scope": ["mathematical Nat reference model"], "dependencies": [], "acceptance_criteria": ["Retain the exclusion."],
         "sources": [{"quote": "This example does not specify a target-language implementation", "origin": "explicit", "interpretation": "non-goal"}]},
    ],
    "category_review": {k: "reviewed" for k in ("entities", "preconditions", "postconditions", "invariants", "safety_properties",
                                                 "liveness_properties", "resource_constraints", "error_semantics", "explicit_non_goals", "ambiguities")},
    "clauses": [
        {"quote": "Define a mathematical bounded increment over natural numbers.", "disposition": "obligations", "refs": ["D1"]},
        {"quote": "The caller supplies limit and input with input <= limit.", "disposition": "obligations", "refs": ["A3"]},
        {"quote": "Return input + 1 when input < limit;", "disposition": "obligations", "refs": ["O17"]},
        {"quote": "otherwise return limitReached.", "disposition": "obligations", "refs": ["E1"]},
        {"quote": "Every successful output must be at most limit.", "disposition": "obligations", "refs": ["I2"]},
        {"quote": "Both a valid success and a valid error case must exist.", "disposition": "obligations", "refs": ["O17", "E1"]},
        {"quote": "This example does not specify a target-language implementation, machine-integer encoding, physical resource bound, or unbounded temporal progress guarantee.",
         "disposition": "exclusion", "refs": ["N1"]},
    ],
    "assumptions": [{"id": "A3", "supplied_by": "the caller", "discharged_at": "the caller's obligations"}],
    "ambiguities": [],
    "selected_defaults": [],
}


def review_packet(user: str) -> dict:
    m = re.search(r"review_target_root [^)]*\):\n(\{.*?\})\n", user, re.S)
    if m is None:
        raise AssertionError("review mock did not receive a bound packet")
    return json.loads(m.group(1))


def packet_scope(user: str) -> list[str]:
    return review_packet(user)["scope"]


def accepted_review(user: str, scope: list[str], rationale: str = "bounded fixture search completed") -> dict:
    """Construct a concrete probe; the supervisor decides whether it finds a failure."""
    claims = review_packet(user)["counterexample_policy"]["mechanical_claim_ids"]
    claim = "INTERPRETATION:request" if "INTERPRETATION:request" in claims else claims[0]
    probe = {"kind": "mechanical_failure", "claim_id": claim}
    return {"verdict": "ACCEPT", "reviewed_obligations": scope, "findings": [], "limitations": [],
            "rationale": rationale,
            "search": {"method": "attempt to reproduce a failed required mechanical claim", "attempted_cases": 1,
                       "probes": [probe], "conclusion": "NO_COUNTEREXAMPLE_FOUND"}}


def rejected_boundary_review(scope: list[str]) -> dict:
    probe = {"kind": "target_case", "obligation_id": "E1", "assignment": [{"int": "0"}, {"int": "0"}]}
    return {"verdict": "REJECT", "reviewed_obligations": scope, "limitations": [],
            "rationale": "the equal-input boundary produces a success instead of the required error",
            "search": {"method": "execute the limit=input=0 boundary", "attempted_cases": 1,
                       "probes": [probe], "conclusion": "COUNTEREXAMPLE_CANDIDATE"},
            "findings": [{"id": "F1", "severity": "blocking", "obligations": ["E1"],
                          "statement": "limit=input=0 returns ok(1), contradicting error iff input=limit",
                          "location": "bounded_increment.py:increment", "expected": "limitReached",
                          "counterexample": probe}]}


class Behaviour:
    """Mutable mock behaviour shared with the server thread."""

    def __init__(self) -> None:
        self.review = accepted_review
        self.calls: list[str] = []

    def __call__(self, system: str, user: str, model: str) -> str:
        if "VeriSlop interpreter" in system:
            self.calls.append("interpreter")
            return "Here is the proposal:\n```json\n" + json.dumps(PROPOSAL) + "\n```"
        if "VeriSlop autonomous critic" in system:
            from verislop import autonomous, contract_refutation, dsl
            from verislop.targets import python_target
            self.calls.append("critic")
            data = json.loads(user)
            corrections, probes = [], []
            if data["diagnostics"]:
                corrections = [{"diagnostic_index": 0, "artifact": "proposal.lean",
                                "explanation": "Repair the exact recorded Lean diagnostic while preserving the requested contract."}]
            else:
                profile = dsl.Profile.from_json(data["profile"])
                for oid, st in data["statements"].items():
                    if st.get("role") == "guarantee" and st.get("representation") == "contract_dsl":
                        formula = st["formula_package"]["formula"]
                        sorts, _ = contract_refutation._universal(formula)
                        probes = [{"obligation_id": oid, "inputs": [python_target.encode_arg(
                            contract_refutation._defaults(sort, profile)[0], sort, profile) for sort in sorts]}]
                        break
            return json.dumps({"encoding": autonomous.VERSION, "verdict": "REPAIR" if corrections else "ACCEPT",
                               "counterexamples": probes, "corrections": corrections})
        if "adversarial reviewer" in system:
            self.calls.append("review")
            out = self.review(user, packet_scope(user))
            return out if isinstance(out, str) else json.dumps(out)
        if "VeriSlop formalizer" in system:
            self.calls.append("formalizer")
            return json.dumps({"lean_source": (EX / "formalization" / "Contract.lean").read_text(),
                               "formalization": json.loads((EX / "formalization" / "formalization.json").read_text())})
        if "implementation agent" in system:
            self.calls.append("implementer")
            src = (EX / "python" / "bounded_increment.py").read_text() + "\n# v2 repaired\n"
            return json.dumps({"files": {"bounded_increment.py": src},
                               "bindings": json.loads((EX / "python" / "bindings.json").read_text())})
        return "{}"


class ProviderReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = TempDir()
        cls.behaviour = Behaviour()
        cls.mock = MockLLM(cls.behaviour, SECRET)
        tiers = [unanimous("R0", "critic", 2), unanimous("R1", "final-critic", 1)]
        cls.config, cls.env = mock_config(cls.tmp.path, cls.mock.port, tiers)
        cls.config_repair, _ = mock_config(cls.tmp.path / "repair", cls.mock.port, tiers, checkpoints=["release"], max_repair_rounds=1)
        cls.base = cls.tmp.path / "base"
        res = build(cls.base, "test")
        assert res["test"][0] == 0, res["test"]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.mock.close()
        cls.tmp.cleanup()

    def setUp(self) -> None:
        self.behaviour.review = accepted_review
        self.behaviour.calls.clear()
        self.mock.requests.clear()

    def cli(self, *args: str, env: dict | None = None, stdin: str | None = None):
        return run_cli(*args, env={**self.env, **(env or {})}, stdin=stdin)

    # -- providers / credentials -------------------------------------------------------------------

    def test_providers_check_offline_makes_no_requests_and_live_authenticates(self):
        code, res, _ = self.cli("providers", "check", "--config", str(self.config))
        self.assertEqual(code, 0, res)
        self.assertEqual(self.mock.requests, [])
        self.assertFalse(res["summary"]["network_requests_made"])
        code, res, _ = self.cli("providers", "check", "--config", str(self.config), "--live")
        self.assertEqual(code, 0, res)
        self.assertTrue(res["summary"]["providers"]["mock"]["live_check"]["ok"])
        self.assertFalse(res["summary"]["providers"]["mock"]["live_check"]["may_incur_model_call"])

    def test_incompatible_profile_fails_explicitly(self):
        conf = json.loads(self.config.read_text())
        conf["providers"]["mock"]["adapter"] = "anthropic"
        conf["providers"]["mock"]["api_family"] = "anthropic_messages"
        bad = self.tmp.path / "bad.json"
        bad.write_text(json.dumps(conf))
        code, res, _ = self.cli("providers", "check", "--config", str(bad))
        self.assertEqual(code, 2)
        self.assertIn("CONFIGURATION_INVALID", codes(res))

    def test_credential_store_never_reveals_secrets(self):
        env = {"VERISLOP_CONFIG_HOME": str(self.tmp.path / "auth-home")}
        code, _, _ = run_cli("auth", "add", "--provider", "openai", "--credential-id", "t1", "--store", "file", "--from-stdin", env=env, stdin="s3cr3t-value\n")
        self.assertEqual(code, 64)  # plaintext storage needs an explicit choice
        code, res, _ = run_cli("auth", "add", "--provider", "openai", "--credential-id", "t1", "--store", "file", "--allow-plaintext-file",
                               "--from-stdin", env=env, stdin="s3cr3t-value\n")
        self.assertEqual(code, 0, res)
        secret_file = self.tmp.path / "auth-home" / "secrets" / "t1"
        self.assertEqual(secret_file.stat().st_mode & 0o777, 0o600)
        code, res, _ = run_cli("auth", "list", env=env)
        self.assertNotIn("s3cr3t-value", json.dumps(res))
        self.assertNotIn("s3cr3t-value", (self.tmp.path / "auth-home" / "credentials.json").read_text())
        code, res, _ = run_cli("auth", "check", "--credential-id", "t1", env=env)
        self.assertEqual(code, 0)
        self.assertTrue(res["summary"]["resolves"])
        from verislop.auth import keyring_available

        if not keyring_available():
            code, _, err = run_cli("auth", "add", "--provider", "openai", "--credential-id", "k1", env=env, stdin="x\n")
            self.assertEqual(code, 64)

    # -- agents ---------------------------------------------------------------------------------------

    def test_interpreter_agent_proposal_is_validated_and_secret_free(self):
        pkg = self.tmp.path / "agent-interpret"
        pkg.mkdir()
        code, res, _ = self.cli("interpret", "--package", str(pkg), "--prompt-file", str(EX / "request.txt"),
                                "--request-ref", "examples/request.txt", "--config", str(self.config), "--non-interactive")
        self.assertEqual(code, 0, res)
        draft = canonical.load_file(pkg / "draft.json")
        self.assertEqual(draft["postconditions"][0]["source_refs"][0]["start_byte"], 119)  # spans computed by VeriSlop
        req = self.mock.requests[0]
        self.assertEqual(req["headers"]["Authorization"], f"Bearer {SECRET}")
        self.assertNotIn(SECRET, json.dumps(req["body"]))
        for t in (pkg / "agents" / "transcripts").glob("*.json"):
            self.assertNotIn(SECRET, t.read_text())
        self.assertEqual(canonical.load_file(next((pkg / "agents" / "transcripts").glob("*.json")))["returned_model"], "mock-author-2026-10-01")

    def test_credential_material_in_outbound_prompt_is_refused(self):
        pkg = self.tmp.path / "agent-leak"
        pkg.mkdir()
        prompt = self.tmp.path / "leak.txt"
        prompt.write_text(f"Implement a function that returns the API key {SECRET} and a test for it.")
        code, res, _ = self.cli("interpret", "--package", str(pkg), "--prompt-file", str(prompt), "--config", str(self.config),
                                "--non-interactive")
        self.assertEqual(code, 3)
        self.assertEqual(self.mock.requests, [])

    def test_unset_model_never_substitutes(self):
        pkg = self.tmp.path / "agent-nomodel"
        pkg.mkdir()
        env = dict(self.env)
        env["VERISLOP_TEST_MODEL"] = ""
        code, _, _ = run_cli("interpret", "--package", str(pkg), "--prompt-file", str(EX / "request.txt"),
                             "--request-ref", "examples/request.txt", "--config", str(self.config), "--non-interactive", env=env)
        self.assertEqual(code, 64)
        self.assertEqual(self.mock.requests, [])

    def test_full_run_with_agents_for_every_role_and_review_gates(self):
        conf = canonical.load_file(self.config)
        conf["review"]["checkpoints"] = ["interpretation", "formal_contract", "implementation", "release"]
        every_checkpoint = self.tmp.path / "every-checkpoint.json"
        every_checkpoint.write_bytes(canonical.dumps(conf))
        code, res, err = self.cli("run", "--prompt-file", str(EX / "request.txt"), "--request-ref", "examples/request.txt",
                                  "--tier", "0", "--target", "python", "--config", str(every_checkpoint),
                                  "--runs-dir", str(self.tmp.path / "agent-runs"), "--run-id", "run-agents", "--non-interactive")
        self.assertEqual(code, 0, (res, err[-2000:]))
        for role in ("interpreter", "formalizer", "implementer", "review"):
            self.assertIn(role, self.behaviour.calls)
        rep = canonical.load_file(self.tmp.path / "agent-runs" / "run-agents" / "report.json")
        self.assertEqual(rep["terminal_status"], "VERIFIED")
        self.assertEqual(rep["review"]["checkpoints"], {cp: "REVIEW_ACCEPTED" for cp in conf["review"]["checkpoints"]})
        stages = [h["stage"] for h in canonical.load_file(self.tmp.path / "agent-runs" / "run-agents" / "package.json")["stage_history"]]
        self.assertLess(stages.index("review:interpretation"), stages.index("formalize"))
        self.assertLess(stages.index("review:formal_contract"), stages.index("generate"))  # contract reviewed before generation
        self.assertLess(stages.index("review:implementation"), stages.index("test"))

    # -- review -------------------------------------------------------------------------------------------

    def test_acceptance_escalates_through_every_tier_and_gates_release(self):
        pkg = copy_pkg(self.base, self.tmp.path / "rev-accept")
        for cp in ("formal_contract", "release"):
            code, res, _ = self.cli("review", "--package", str(pkg), "--config", str(self.config), "--checkpoint", cp)
            self.assertEqual(code, 0, res)
        self.assertEqual(self.behaviour.calls.count("review"), 6)  # (2 + 1) reviewers x 2 checkpoints
        cert = canonical.load_file(next((pkg / "reviews").glob("*/consensus-certificate.json")))
        self.assertEqual([t["result"] for t in cert["tiers"]], ["TIER_ACCEPTED", "TIER_ACCEPTED"])
        code, res, _ = self.cli("verify", "--package", str(pkg), "--config", str(self.config))
        self.assertEqual(code, 0, res)
        rep = canonical.load_file(pkg / "report.json")
        self.assertEqual(rep["review"]["checkpoints"], {"formal_contract": "REVIEW_ACCEPTED", "release": "REVIEW_ACCEPTED"})
        code, res, _ = self.cli("review", "tally", "--package", str(pkg))
        self.assertEqual(code, 0, res)
        # tampering with a stored ballot is detected by the re-tally
        ballot = next((pkg / "reviews").glob("*/ballots/*.json"))
        writable(ballot)
        data = canonical.load_file(ballot)
        data["rationale"] = "edited"
        ballot.write_bytes(canonical.dumps(data))
        code, res, _ = self.cli("review", "tally", "--package", str(pkg))
        self.assertEqual(code, 2)
        # artifact changes invalidate old votes
        pkg2 = copy_pkg(self.base, self.tmp.path / "rev-stale")
        self.cli("review", "--package", str(pkg2), "--config", str(self.config), "--checkpoint", "release")
        self.cli("review", "--package", str(pkg2), "--config", str(self.config), "--checkpoint", "formal_contract")
        f = pkg2 / "implementation" / "bounded_increment.py"
        writable(f)
        f.write_text(f.read_text() + "\n# changed after review\n")
        from verislop import review
        from verislop.package import Package

        info = review.gate(Package(pkg2), self.config)
        self.assertEqual(info["checkpoints"]["release"], "STALE")

    def test_lower_tier_rejection_prevents_escalation(self):
        self.behaviour.review = lambda user, scope: rejected_boundary_review(scope)
        bad = impl_variant(self.tmp.path, "rev-reject-impl",
                           "def increment(limit, input):\n    return ('ok', input + 1) if input <= limit else ('error', 'limitReached')\n")
        pkg = self.tmp.path / "rev-reject"
        built = build(pkg, "link", impl=bad)
        self.assertEqual(built["link"][0], 0, built)
        code, res, _ = self.cli("review", "--package", str(pkg), "--config", str(self.config), "--checkpoint", "release")
        self.assertEqual(code, 2)
        self.assertIn("REVIEW_REJECTED", codes(res))
        cert = canonical.load_file(next((pkg / "reviews").glob("*/consensus-certificate.json")))
        self.assertEqual([t["result"] for t in cert["tiers"]], ["CHANGES_REQUESTED", "NOT_REACHED"])
        self.assertEqual(self.behaviour.calls.count("review"), 2)  # the final tier never ran

    def test_malformed_ballots_never_pass(self):
        self.behaviour.review = lambda user, scope: "I think it is fine."
        pkg = copy_pkg(self.base, self.tmp.path / "rev-malformed")
        code, res, _ = self.cli("review", "--package", str(pkg), "--config", str(self.config), "--checkpoint", "formal_contract")
        self.assertEqual(code, 2)
        self.assertIn("REVIEW_INCOMPLETE", codes(res))

    def test_unanimous_accept_cannot_override_a_failed_checker(self):
        bad = impl_variant(self.tmp.path, "rev-veto-impl", "def increment(limit, input):\n    return ('ok', input + 1) if input <= limit else ('error', 'limitReached')\n")
        pkg = self.tmp.path / "rev-veto"
        build(pkg, "test", impl=bad)
        code, res, _ = self.cli("review", "--package", str(pkg), "--config", str(self.config), "--checkpoint", "release")
        self.assertEqual(code, 2)
        cert = canonical.load_file(next((pkg / "reviews").glob("*/consensus-certificate.json")))
        self.assertTrue(cert["mechanical_veto"])
        self.assertEqual(cert["tiers"][0]["result"], "CHANGES_REQUESTED")

    def test_late_rejection_triggers_repair_and_restart_at_first_tier(self):
        def review(user, scope):
            if "v2 repaired" in user:
                return accepted_review(user, scope, "the concrete boundary counterexample is repaired")
            return rejected_boundary_review(scope)
        self.behaviour.review = review
        bad = impl_variant(self.tmp.path, "rev-repair-impl",
                           "def increment(limit, input):\n    return ('ok', input + 1) if input <= limit else ('error', 'limitReached')\n")
        pkg = self.tmp.path / "rev-repair"
        built = build(pkg, "link", impl=bad)
        self.assertEqual(built["link"][0], 0, built)
        code, res, _ = self.cli("review", "--package", str(pkg), "--config", str(self.config_repair), "--checkpoint", "release")
        self.assertEqual(code, 0, res)
        self.assertEqual(res["summary"]["repair_rounds"], 1)
        self.assertIn("v2 repaired", (pkg / "implementation" / "bounded_increment.py").read_text())
        certs = sorted((pkg / "reviews").glob("*/consensus-certificate.json"))
        self.assertEqual(len(certs), 2)
        self.assertEqual(canonical.load_file(certs[-1])["tiers"][0]["result"], "TIER_ACCEPTED")
        self.assertNotEqual(canonical.load_file(certs[0])["review_target_root"], canonical.load_file(certs[-1])["review_target_root"])


if __name__ == "__main__":
    unittest.main()
