"""Request policy gates actual unrelated kernel-reconstructed source facets."""
from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verislop import canonical, contract, export, fsutil, recovery, source_policy
from verislop.errors import Diagnostic, UsageError
from verislop.events import EventSink
from verislop.package import Package
from verislop.stage import StageResult
from tests import test_source_pipeline as fixture


def policy():
    return {"schema_version": "0.1", "format": source_policy.FORMAT, "obligations": {
        oid: {"file": "program.vscore.json", "entry": "plus", "arity": 1,
              "properties": ["typed_total", "deterministic", "input_preserved", "no_external_io",
                             "no_floating_point", "pure_data", "restricted_runtime_only"],
              "value_required": oid == "G2"} for oid in ("G1", "G2")}}


def stage(root):
    pkg = Package(root / "package")
    pkg.ensure("fresh-source-policy-fixture")
    path = root / "policy-input.json"
    fsutil.write_json(path, policy())
    source_policy.stage(pkg, path)
    return pkg


class SourcePolicyUnits(unittest.TestCase):
    def test_closed_schema_has_no_algorithm_answers_or_host_paths(self):
        for edit in (lambda p: p["obligations"]["G1"].update(algorithm="answer"),
                     lambda p: p["obligations"]["G1"].update(file="solution.py"),
                     lambda p: p["obligations"]["G1"].update(properties=["no_external_io", "no_external_io"]),
                     lambda p: p["obligations"]["G1"].update(properties=["host_verified"]),
                     lambda p: p["obligations"]["G1"].update(arity=True)):
            value = policy()
            edit(value)
            self.assertTrue(source_policy.validate(value))
        self.assertEqual(source_policy.validate(policy()), [])

    def test_original_path_has_no_authority_after_exact_request_freeze(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pkg = stage(root)
            (root / "policy-input.json").unlink()
            self.assertEqual(source_policy.context(pkg), policy())
            altered = policy()
            altered["obligations"]["G1"]["entry"] = "other"
            other = root / "other.json"
            fsutil.write_json(other, altered)
            with self.assertRaises(UsageError):
                source_policy.stage(pkg, other)
            self.assertEqual(source_policy.context(pkg), policy())

    def test_missing_ids_value_endpoints_and_source_properties_are_specific_repairs(self):
        records = [{"id": oid, "role": "guarantee", "required": True, "blocked_by": []} for oid in ("G1", "G2")]
        source = {"symbol": "plus", "requirements": [{"tag": "entry", "file": "program.vscore.json", "entry": "plus", "arity": 1},
                   *({"tag": t} for t in policy()["obligations"]["G1"]["properties"])]}
        statements = {oid: {"representation": "source_facets", "formula_package": {
            "encoding": source_policy.source_contract.ENCODING,
            "source": [source], "value": {"formula": {"tag": "eq", "left": {"tag": "call", "symbol": "plus", "args": []},
                                                       "right": {"tag": "call", "symbol": "plus", "args": []}}} if oid == "G2" else None}}
            for oid in ("G1", "G2")}
        self.assertEqual(source_policy.check(policy(), statements, records), [])
        for edit in (lambda p: p.pop("G1"), lambda p: p["G2"].update(representation="contract_dsl"),
                     lambda p: p["G2"]["formula_package"].update(value=None),
                     lambda p: p["G1"]["formula_package"]["source"][0]["requirements"].pop(),
                     lambda p: p["G2"]["formula_package"].update(value={"formula": {"tag": "true"}})):
            bad = copy.deepcopy(statements)
            edit(bad)
            diagnostics = source_policy.check(policy(), bad, records)
            self.assertTrue(diagnostics)
            self.assertTrue(all(d.code == source_policy.CODE and d.details["repairable"] for d in diagnostics))
        self.assertIn(source_policy.CODE, recovery.REPAIRABLE_CODES)


class SourcePolicyKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="verislop-source-policy-kernel-")
        cls.root = Path(cls.tmp.name)
        cls.addClassCleanup(cls.cleanup)
        positive = cls.root / "positive"
        positive.mkdir()
        stage(positive)
        cls.pkg, cls.stages = fixture.accepted_fixture(positive)

    @classmethod
    def cleanup(cls):
        destination = Path(__file__).resolve().parents[1] / "synthetic_dataset/bootstrap/validation/tier2-source-policy-kernel" / cls.root.name
        shutil.copytree(cls.root, destination, symlinks=True)
        files = {p.relative_to(destination).as_posix(): canonical.digest_file(p) for p in sorted(destination.rglob("*")) if p.is_file()}
        fsutil.write_json(destination / "capture.json", {"format": "verislop.source-policy-kernel-capture/0.1",
            "files": files, "files_root": canonical.digest_json(files), "historical_source_root": str(cls.root),
            "scope": "unrelated accepted positive and rejected pre-proof constructor policy fixtures"})
        fsutil.make_writable_tree(cls.root)
        cls.tmp.cleanup()

    def test_positive_policy_is_checked_against_accepted_constructors_not_author_json(self):
        self.assertTrue(all(r["status"] == "PASS" for r in self.stages.values()))
        ir, _, _, diagnostics = export.verified_ir(self.pkg)
        self.assertEqual(diagnostics, [])
        self.assertEqual(source_policy.context(self.pkg), policy())
        candidate = self.pkg.path("contract") / "candidate/typed-proposal.json"
        changed = canonical.load_file(candidate)
        changed["source_requirements"]["Delivery"]["requirements"][0]["entry"] = "forged"
        with fixture.changed_bytes(candidate, canonical.dumps(changed)):
            _, _, _, diagnostics = export.verified_ir(self.pkg)
            self.assertEqual(diagnostics, [])
        self.assertEqual({r["formal"]["representation"] for r in ir["obligations"].values()}, {"source_facets"})

    def test_actual_import_replays_policy_bytes_and_reference(self):
        from verislop.bridges.import_contract import import_contract, BridgeImportError
        imported = import_contract(self.pkg.root)
        self.assertEqual(imported.files[source_policy.PATH], (self.pkg.root / source_policy.PATH).read_bytes())
        self.assertEqual(imported.ir["obligations"].keys(), {"G1", "G2"})
        altered = policy()
        altered["obligations"]["G1"]["entry"] = "other"
        with fixture.changed_bytes(self.pkg.root / source_policy.PATH, canonical.dumps(altered)), self.assertRaises(BridgeImportError):
            import_contract(self.pkg.root)

    def test_actual_strict_recovery_preserves_policy_and_interpretation(self):
        diagnostic = Diagnostic(source_policy.CODE, "fresh unrelated fixture requires its declared source endpoint")
        failure = StageResult("run", "BLOCKED", "source policy needs a new contract proposal",
            diagnostics=[diagnostic], summary={"stopped_at": "formalize",
                "failed_stage_diagnostics": [diagnostic.to_json()]})
        events = EventSink(self.pkg.run_id, self.pkg.root, quiet=True)
        try:
            child, _, _ = recovery.create(self.pkg, self.pkg,
                {"config": "unused-provider-config", "repair_rounds": 1}, failure, 1, events)
        finally:
            events.close()
        self.assertEqual(policy(), source_policy.context(child))
        self.assertEqual(self.pkg.meta()["source_policy"], child.meta()["source_policy"])
        self.assertEqual(self.pkg.interpretation_root(), child.interpretation_root())
        self.assertEqual((self.pkg.root / source_policy.PATH).read_bytes(),
                         (child.root / source_policy.PATH).read_bytes())
        lineage = canonical.load_file(child.root / "recovery-lineage.json")
        self.assertIn(source_policy.PATH, {row["path"] for row in lineage["copied_inputs"]["entries"]})
        self.assertFalse(child.path("accepted_ir").exists())

    def negative(self, name, edit):
        root = self.root / name
        root.mkdir()
        pkg = stage(root)
        original = fixture.source_proposal
        def proposal(*args, **kwargs):
            value = original(*args, **kwargs)
            edit(value, kwargs.get("mixed", False))
            return value
        with patch.object(fixture, "source_proposal", side_effect=proposal), self.assertRaises(AssertionError) as error:
            fixture.accepted_fixture(root)
        self.assertIn(source_policy.CODE, str(error.exception))
        self.assertFalse((pkg.path("contract") / "challenge/challenge.json").exists())
        self.assertFalse((pkg.path("contract") / "proofs/candidate.lean").exists())
        self.assertFalse(pkg.path("accepted_ir").exists())
        checked = canonical.load_file(pkg.path("contract") / "candidate/statement-check.json")
        self.assertIn(source_policy.CODE, {d["code"] for d in checked["diagnostics"]})

    def test_plain_functional_equation_cannot_replace_named_entry_and_effect_facets(self):
        def edit(value, mixed):
            if mixed:
                value["theorems"]["Spec"].pop("source")
        self.negative("plain-math", edit)

    def test_alternate_source_entry_cannot_satisfy_public_named_delivery(self):
        self.negative("other-entry", lambda value, _mixed:
                      value["source_requirements"]["Delivery"]["requirements"][0].update(entry="floor_kernel"))

    def test_policy_mutation_and_removal_invalidate_frozen_and_accepted_inputs(self):
        path = self.pkg.root / source_policy.PATH
        altered = policy()
        altered["obligations"]["G1"]["entry"] = "other"
        with fixture.changed_bytes(path, canonical.dumps(altered)):
            _, diagnostics = contract.load_frozen(self.pkg)
            self.assertIn("INPUT_MUTATION", {d.code for d in diagnostics})
            _, _, _, diagnostics = export.verified_ir(self.pkg)
            self.assertIn("INPUT_MUTATION", {d.code for d in diagnostics})
        original = path.read_bytes()
        reference = self.pkg.meta()["source_policy"]
        path.unlink()
        self.pkg.meta().pop("source_policy")
        try:
            _, diagnostics = contract.load_frozen(self.pkg)
            self.assertIn("INPUT_MUTATION", {d.code for d in diagnostics})
        finally:
            path.write_bytes(original)
            self.pkg.set_meta("source_policy", reference)


if __name__ == "__main__":
    unittest.main()
