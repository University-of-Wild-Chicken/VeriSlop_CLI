"""Exact generic closure inventories and nullable support; no compiler or models."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from verislop import canonical, fsutil
from verislop.backends import vscore, vscore3, vscore_closure, vscore3_closure
from verislop.bridges.manifest import InvalidPackage
from verislop.package import Package


def outputs(support=None):
    return {slot: support if slot == "readable_support" else {"generic": slot}
            for slot in vscore3_closure.COMPARISON_SLOTS}


class ClosureOutputComparisonTests(unittest.TestCase):
    def compare(self, a, b):
        return vscore3_closure._compare_outputs(a, b)

    def test_present_legacy_null_support_compares_equal(self):
        a = outputs()
        self.assertEqual(self.compare(a, copy.deepcopy(a)), [])

    def test_selected_complete_support_compares_equal(self):
        support = {"descriptor": {"mode": "CHECKED"},
                   "artifacts": {"readable/base-kernel-export.json": canonical.digest(b"generic baseline")}}
        a = outputs(support)
        self.assertEqual(self.compare(a, copy.deepcopy(a)), [])

    def test_missing_nullable_support_fails_even_when_both_omit_it(self):
        for omitted in ("A", "B", "both"):
            with self.subTest(omitted=omitted):
                a, b = outputs(), outputs()
                if omitted in ("A", "both"):
                    del a["readable_support"]
                if omitted in ("B", "both"):
                    del b["readable_support"]
                self.assertEqual([m["output"] for m in self.compare(a, b)], ["readable_support"])

    def test_every_older_slot_rejects_equal_null_and_omission(self):
        for slot in vscore_closure.COMPARISON_SLOTS:
            for mutation in ("null", "missing"):
                with self.subTest(slot=slot, mutation=mutation):
                    a, b = outputs(), outputs()
                    if mutation == "null":
                        a[slot] = b[slot] = None
                    else:
                        del a[slot]
                        del b[slot]
                    self.assertEqual([m["output"] for m in self.compare(a, b)], [slot])

    def test_null_and_selected_support_differ_in_both_directions(self):
        selected = outputs({"descriptor": {"mode": "CHECKED"}, "artifacts": {}})
        for a, b in ((outputs(), selected), (selected, outputs())):
            self.assertEqual([m["output"] for m in self.compare(a, b)], ["readable_support"])

    def test_changed_support_artifact_bytes_fail(self):
        a = outputs({"descriptor": {"mode": "CHECKED"}, "artifacts": {
            "readable/base-kernel-export.json": canonical.digest(b"generic baseline")}})
        b = copy.deepcopy(a)
        b["readable_support"]["artifacts"]["readable/base-kernel-export.json"] = canonical.digest(b"changed baseline")
        self.assertEqual([m["output"] for m in self.compare(a, b)], ["readable_support"])

    def test_extra_output_rejected_even_when_both_builds_agree(self):
        for side in ("A", "B", "both"):
            with self.subTest(side=side):
                a, b = outputs(), outputs()
                if side in ("A", "both"):
                    a["undeclared"] = {"generic": "extra"}
                if side in ("B", "both"):
                    b["undeclared"] = {"generic": "extra"}
                self.assertEqual([m["output"] for m in self.compare(a, b)], ["undeclared"])


class FrozenClosureInventoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="generic-closure-dispatch-")
        self.addCleanup(temporary.cleanup)
        self.pkg = Package(Path(temporary.name) / "package")
        self.ir = {"obligations": {}, "contract_input_root": canonical.digest(b"generic contract")}
        self.acceptance = {"artifacts": {"profile": {"path": "accepted/profile.json"}}}
        self.params = {"bridge_id": "generic"}
        self.plan = {"edges": [{"claim_id": "generic-edge"}], "claims": []}
        for path, obj in {"claims.json": {"claims": [], "obligations": []},
                          "accepted/accepted-ir.json": self.ir,
                          "accepted/acceptance.json": self.acceptance,
                          "accepted/profile.json": {}, "interpretation.json": {},
                          "bridges/generic/plan.json": self.plan}.items():
            fsutil.atomic_write(self.pkg.root / path, canonical.dumps(obj))

    def inventory(self):
        return vscore3.implementation_claims(self.pkg, self.ir,
            canonical.digest_file(self.pkg.root / "accepted/accepted-ir.json"),
            canonical.digest_file(self.pkg.root / "accepted/acceptance.json"),
            self.params, {}, {}, self.plan)

    def test_registries_select_exact_versioned_predicate(self):
        self.assertEqual(vscore3.FINAL_CLAIMS, vscore3_closure.FINAL_PREDICATES)
        self.assertEqual(vscore3.FINAL_CLAIMS["CLOSURE:determinism"], "closure-determinism/0.3")
        self.assertEqual(vscore.FINAL_CLAIMS["CLOSURE:determinism"], "closure-determinism/0.2")
        self.assertEqual(vscore_closure.FINAL_PREDICATES["CLOSURE:determinism"], "closure-determinism/0.2")

    def test_supervisor_inventory_reconstructs_versioned_terminal_claim(self):
        inventory = self.inventory()
        fsutil.atomic_write(self.pkg.root / "closure/implementation-claims.json", canonical.dumps(inventory))
        claims = vscore3_closure._claims(self.pkg)
        terminal = next(c for c in claims if c["claim_id"] == "CLOSURE:determinism")
        self.assertEqual(terminal["result_predicate"], "closure-determinism/0.3")
        self.assertEqual(terminal["pass_predicate"], "closure-determinism/0.3")
        self.assertTrue(terminal["required"])
        self.assertEqual(terminal["verifier"], "verislop.closure")

    def test_candidate_cannot_downgrade_frozen_terminal_predicate(self):
        inventory = self.inventory()
        terminal = next(c for c in inventory["claims"] if c["claim_id"] == "CLOSURE:determinism")
        terminal["result_predicate"] = terminal["pass_predicate"] = "closure-determinism/0.2"
        fsutil.atomic_write(self.pkg.root / "closure/implementation-claims.json", canonical.dumps(inventory))
        with self.assertRaises(InvalidPackage) as rejected:
            vscore3_closure._claims(self.pkg)
        self.assertEqual(rejected.exception.code, "CLAIM_MUTATION")


if __name__ == "__main__":
    unittest.main()
