"""Frozen predicate inventory controls; these tests execute no Lean builds."""
import copy
import tempfile
import unittest
from pathlib import Path

from verislop.claimcheck import evaluate_claim
from verislop.evidence import EvidenceStore
from verislop.verifiers import verifier_hash

LEGACY = ("contract_receipt", "contract_artifacts", "contract_obligations", "accepted_ir",
          "semantic_build", "goal", "semantic_certificate", "implementation_ir",
          "module_parts", "materialization_inventory", "link_record", "nonfinal_outcomes",
          "provenance_graph")
CURRENT = LEGACY + ("readable_support",)
ROOT = "sha256:" + "7" * 64
ISSUER = "verislop.closure"


class ClosurePredicateDispatchTests(unittest.TestCase):
    def payload(self, version):
        slots = CURRENT if version == "0.3" else LEGACY
        outputs = {slot: ROOT for slot in slots}
        if version == "0.3":
            outputs["readable_support"] = None
        return {"format": "closure-determinism/" + version, "milestone_outcome": "PASS",
                "binding_root": "closure_root", "predicate_satisfied": True,
                "determinism": {"mismatches": [], "compared": list(slots)},
                "builds": [{"build": label, "ok": True, "outputs": copy.deepcopy(outputs),
                            "producer": {"verifier_id": ISSUER, "verifier_hash": verifier_hash(ISSUER)}}
                           for label in ("A", "B")]}

    def check(self, version, result):
        claim = {"claim_id": "CLOSURE:determinism", "verifier": ISSUER,
                 "root_kind": "closure_root", "result_predicate": "closure-determinism/" + version}
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(Path(tmp), "dispatch-fixture")
            evidence = store.record(claim_id=claim["claim_id"], verifier_id=ISSUER,
                                    status="PASS", scope=["pure evidence dispatch control"],
                                    input_root=ROOT, result=result, invocation=["dispatch-control"])
            return evaluate_claim(claim, [evidence], {"closure_root": ROOT}, "closure_root")

    def test_each_frozen_version_accepts_only_its_exact_inventory(self):
        for version in ("0.2", "0.3"):
            with self.subTest(version=version):
                self.assertEqual(self.check(version, self.payload(version)).outcome, "PASS")

    def test_both_cross_version_results_fail(self):
        for version, other in (("0.2", "0.3"), ("0.3", "0.2")):
            with self.subTest(version=version):
                result = self.payload(other)
                result["format"] = "closure-determinism/" + version
                self.assertEqual(self.check(version, result).outcome, "FAIL")

    def test_raw_format_and_backend_cannot_override_frozen_predicate(self):
        result = self.payload("0.3")
        result.update(backend="verislop.backend.vscore/0.1")
        self.assertEqual(self.check("0.2", result).outcome, "FAIL")
        result["format"] = "closure-determinism/0.2"
        self.assertEqual(self.check("0.3", result).outcome, "FAIL")
        self.assertEqual(self.check("9", result).outcome, "UNSUPPORTED")

    def test_missing_extra_malformed_or_wrong_null_outputs_fail(self):
        for mutation in ("missing_support", "extra", "null_goal", "non_object", "one_build"):
            with self.subTest(mutation=mutation):
                result = self.payload("0.3")
                outputs = result["builds"][1]["outputs"]
                if mutation == "missing_support":
                    del outputs["readable_support"]
                elif mutation == "extra":
                    outputs["unregistered"] = ROOT
                elif mutation == "null_goal":
                    outputs["goal"] = None
                elif mutation == "non_object":
                    result["builds"][1]["outputs"] = None
                else:
                    result["builds"].pop()
                self.assertEqual(self.check("0.3", result).outcome, "FAIL")


if __name__ == "__main__":
    unittest.main()
