"""Authenticated display engineering fixtures, not native acceptance evidence."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verislop import agent_memory, author_reference as view, canonical, contract, exprjson, surface_context
from verislop.errors import BlockedError
from verislop.package import Package


def fixture(pkg, fixed, *, operative=False, unusual=False, duplicate=False, preamble="", commented=False):
    """Construct unrelated typed-export fixture data; no Lean or model acceptance."""
    def lit(value): return {"lit": {"str": value}}
    def apply(name, *args): return exprjson.app(exprjson.const(name), *args)
    def sequence(values):
        result = apply("List.nil", exprjson.const("Unit"))
        for value in reversed(values):
            result = apply("List.cons", exprjson.const("Unit"), value, result)
        return result
    records = [{"id": oid, "revision": 1, "kind": "entity", "role": "declaration",
        "statement": "unrelated display fixture é " + oid, "required": True, "source_refs": [],
        "scope": ["fixture"], "dependencies": [], "acceptance_criteria": ["retain exact metadata"],
        "bindings": ["Fixture.one", "Fixture.two"]} for oid in ("Z9", "A1")]
    def entry(row):
        return apply("VeriSlop.Registry.Entry.mk", lit(row["id"]), {"lit": {"nat": "1"}},
            lit(row["kind"]), lit(row["role"]), lit(row["statement"]), exprjson.const("Bool.true"),
            sequence([]), sequence([lit(x) for x in row["scope"]]), sequence([]),
            sequence([lit(x) for x in row["acceptance_criteria"]]), sequence([lit(x) for x in row["bindings"]]))
    constants = [{"name": exprjson.parse_name("VeriSlop.Registry.entries"), "kind": "definition",
                  "type": exprjson.const("List"), "value": sequence([entry(row) for row in records])}]
    if operative == "proof":
        constants.append({"name": ["Fixture", "proof"], "kind": "theorem", "type": exprjson.const("True"),
                          "value_constants": [exprjson.parse_name("VeriSlop.Registry.entries")]})
    elif operative:
        constants.append({"name": ["Fixture", "operative"], "kind": "definition",
                          "type": exprjson.const("Nat"), "value": exprjson.const("VeriSlop.Registry.entries")})
    environment = {"constants": constants, "lean_githash": "fixture-git", "import": {"ok": True}, "replay": {"ok": True}}
    envraw = canonical.dumps(environment)
    generated = contract.registry_lean(records, {r["id"]: r["bindings"] for r in records})
    if unusual:
        generated = generated.replace("Typed obligation metadata", "Typed  obligation metadata")
    source = ("import Std\n\n" + preamble + generated + (generated if duplicate else "") + "\ndef unrelated : Nat := 0\n").encode()
    if commented:
        source = ("/-\n" + generated + "-/\nimport Std\n" + generated.replace("Typed obligation metadata", "Typed  obligation metadata") + "\ndef unrelated : Nat := 0\n").encode()
    source_ref = {"path": "accepted/source/" + canonical.sha256_hex(source) + ".lean", "sha256": canonical.digest(source)}
    env_ref = {"path": "accepted/environment/" + canonical.sha256_hex(envraw) + ".json", "sha256": canonical.digest(envraw)}
    certificate = {"artifact_kind": "acceptance_certificate", "gate": "accepted_and_proved",
        "contract_input_root": "fixture-root", "toolchain": {"pin": fixed["lean_toolchain"], "githash": "fixture-git"},
        "artifacts": {"source": source_ref, "environment_export": env_ref}}
    certraw = canonical.dumps(certificate)
    certpath = "accepted/certificates/" + canonical.sha256_hex(certraw) + ".json"
    for path, data in ((source_ref["path"], source), (env_ref["path"], envraw), (certpath, certraw)):
        location = pkg.root / path
        location.parent.mkdir(parents=True, exist_ok=True)
        location.write_bytes(data)
    obligations = {r["id"]: {k: copy.deepcopy(v) for k,v in r.items() if k != "bindings"} for r in records}
    # Intentional exported dependency difference must remain preserved, not rejected.
    obligations["A1"]["dependencies"] = [{"id": "Z9", "relation": "uses_definition"}]
    fixed["accepted_ir"] = {"acceptance_certificate_ref": certpath, "accepted_environment_hash": env_ref["sha256"],
        "contract_input_root": "fixture-root", "lean_toolchain": fixed["lean_toolchain"], "obligations": obligations}
    fixed["accepted_reference"] = {**source_ref, "lean_source": source.decode()}
    return records


class AuthorReferenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="verislop-author-reference-")
        self.addCleanup(temp.cleanup)
        self.pkg = Package(Path(temp.name) / "pkg")
        self.pkg.ensure("unrelated-display-fixture")
        self.fixed = {"parameters": {"backend": "verislop.backend.vscore/0.3", "backend_version": "0.3"},
                      "source_grammar": {}, "lean_toolchain": "fixture-pin", "accepted_profile": {}}
        self.records = fixture(self.pkg, self.fixed)

    def test_complete_records_and_exact_segments_historically_restore(self):
        original = copy.deepcopy(self.fixed)
        selected = surface_context.project_fixed_context(self.pkg, self.fixed)
        display = selected["accepted_reference"]["lean_source_display"]
        self.assertNotIn("lean_source", selected["accepted_reference"])
        self.assertEqual(self.records, display["registry_metadata"]["ordered_entries"])
        self.assertEqual([], display["registry_metadata"]["ordered_entries"][1]["dependencies"])
        self.assertTrue(self.fixed["accepted_ir"]["obligations"]["A1"]["dependencies"])
        regenerated = contract.registry_lean(self.records, {r["id"]: r["bindings"] for r in self.records})
        self.assertEqual(original["accepted_reference"]["lean_source"],
                         display["before_registry"] + regenerated + display["after_registry"])
        self.assertEqual(original, self.fixed)
        with patch.object(Path, "read_bytes", side_effect=AssertionError("ambient filesystem read")):
            self.assertEqual(original, surface_context.restore_fixed_context(self.pkg, selected))

    def test_changed_display_fields_records_and_native_bindings_reject(self):
        selected = surface_context.project_fixed_context(self.pkg, self.fixed)
        changes = [lambda d: d["accepted_reference"]["lean_source_display"].update(before_registry="different"),
            lambda d: d["accepted_reference"]["lean_source_display"].update(after_registry="different"),
            lambda d: d["accepted_reference"]["lean_source_display"]["registry_metadata"]["ordered_entries"].reverse(),
            lambda d: d["accepted_reference"]["lean_source_display"]["registry_metadata"]["ordered_entries"][0]["bindings"].reverse(),
            lambda d: d["accepted_reference"]["lean_source_display"]["retained_registry"].update(start_byte=True),
            lambda d: d["accepted_reference"].update(sha256="sha256:stale")]
        for mutate in changes:
            changed = copy.deepcopy(selected)
            mutate(changed)
            with self.subTest(changed=changed), self.assertRaises(BlockedError):
                surface_context.restore_fixed_context(self.pkg, changed)

    def test_bound_source_environment_toolchain_and_metadata_mismatch_fail_closed(self):
        mutations = [lambda f: f["accepted_reference"].update(sha256="sha256:bad"),
            lambda f: f["accepted_ir"].update(accepted_environment_hash="sha256:bad"),
            lambda f: f["accepted_ir"].update(lean_toolchain="other"),
            lambda f: f["accepted_ir"].update(contract_input_root="other"),
            lambda f: f["accepted_ir"]["obligations"]["A1"].update(statement="changed"),
            lambda f: f["accepted_ir"]["obligations"]["A1"].update(revision=True)]
        for mutate in mutations:
            changed = copy.deepcopy(self.fixed)
            mutate(changed)
            with self.subTest(fixed=changed), self.assertRaises(BlockedError):
                view.capture_artifacts(self.pkg, changed)

    def test_valid_operative_nonstandard_and_repeated_registry_keep_full_source(self):
        for options in ({"operative": True}, {"operative": "proof"}, {"unusual": True}, {"duplicate": True},
                        {"preamble": "def inserted : Nat := 0\n"}, {"commented": True}):
            fixture(self.pkg, self.fixed, **options)
            selected = surface_context.project_fixed_context(self.pkg, self.fixed)
            reference = selected["accepted_reference"]
            self.assertEqual(self.fixed["accepted_reference"]["lean_source"], reference["lean_source"])
            self.assertEqual("full_source", reference["lean_source_display"]["mode"])
            self.assertTrue(reference["lean_source_display"]["reason"])
            self.assertEqual(self.fixed, surface_context.restore_fixed_context(self.pkg, selected))

    def test_coherent_receipt_cannot_replace_registry_with_functional_source_span(self):
        artifacts = view.capture_artifacts(self.pkg, self.fixed)
        receipt = canonical.loads(artifacts[view.VIEW])
        source = self.fixed["accepted_reference"]["lean_source"].encode()
        start = receipt["span"]["end_byte"]
        artifacts[view.REGISTRY] = source[start:]
        receipt["span"] = {"start_byte": start, "end_byte": len(source), "sha256": canonical.digest(source[start:])}
        artifacts[view.VIEW] = canonical.dumps(receipt)
        with self.assertRaises(BlockedError):
            view.project_reference(self.fixed, artifacts)

    def test_historical_restore_rejects_changed_retained_environment(self):
        selected = surface_context.project_fixed_context(self.pkg, self.fixed)
        ref = selected[surface_context.REFERENCE_KEY]["snapshot_ref"]
        manifest = canonical.load_file(self.pkg.root / ref["path"])
        blob = next(row["blob_ref"] for row in manifest["artifacts"] if row["source_ref"] == view.ENV)
        path = self.pkg.root / blob["path"]
        path.chmod(0o600)
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(BlockedError):
            surface_context.restore_fixed_context(self.pkg, selected)

    def test_legacy_surface_snapshot_still_restores_without_new_reference_artifacts(self):
        root = Path(surface_context.__file__).resolve().parents[1]
        grammar = (root / surface_context.GRAMMAR_PATH).read_bytes()
        compiler = canonical.dumps({p: (root / p).read_text() for p in surface_context.COMPILER_PATHS})
        raw = canonical.dumps(self.fixed)
        binding = {"format": surface_context.LEGACY_FORMAT, "fixed_sha256": canonical.digest(raw),
            "grammar_sha256": canonical.digest(grammar), "compiler_sha256": canonical.digest(compiler),
            "lean_toolchain": self.fixed["lean_toolchain"], "authority": surface_context.AUTHORITY}
        snapshot = agent_memory.checkpoint(self.pkg, "legacy-fixture", {"fixed-context.json": raw,
            surface_context.GRAMMAR_PATH: grammar, "compiler-sources.json": compiler})
        reference = {**binding, "snapshot_ref": snapshot["snapshot_ref"]}
        selected = copy.deepcopy(self.fixed)
        selected["source_grammar"] = {"format": "ebnf", "path": surface_context.GRAMMAR_PATH,
            "sha256": canonical.digest(grammar), "text": grammar.decode()}
        selected[surface_context.REFERENCE_KEY] = reference
        self.assertEqual(self.fixed, surface_context.restore_fixed_context(self.pkg, selected))

    def test_environment_retention_boundary_preserves_full_source_without_ignoring_corruption(self):
        def resize_environment(size):
            cert = canonical.load_file(self.pkg.root / self.fixed["accepted_ir"]["acceptance_certificate_ref"])
            env = canonical.load_file(self.pkg.root / cert["artifacts"]["environment_export"]["path"])
            env["fixture_padding"] = ""
            env["fixture_padding"] = "x" * (size - len(canonical.dumps(env)))
            raw = canonical.dumps(env)
            self.assertEqual(size, len(raw))
            ref = {"path": "accepted/environment/" + canonical.sha256_hex(raw) + ".json", "sha256": canonical.digest(raw)}
            (self.pkg.root / ref["path"]).write_bytes(raw)
            cert["artifacts"]["environment_export"] = ref
            cert_raw = canonical.dumps(cert)
            certpath = "accepted/certificates/" + canonical.sha256_hex(cert_raw) + ".json"
            (self.pkg.root / certpath).write_bytes(cert_raw)
            self.fixed["accepted_ir"].update(acceptance_certificate_ref=certpath, accepted_environment_hash=ref["sha256"])
            return self.pkg.root / ref["path"]
        resize_environment(agent_memory.MAX_ARTIFACT_BYTES)
        self.assertEqual(view.ARTIFACTS, set(view.capture_artifacts(self.pkg, self.fixed)))
        path = resize_environment(agent_memory.MAX_ARTIFACT_BYTES + 1)
        selected = surface_context.project_fixed_context(self.pkg, self.fixed)
        self.assertEqual(self.fixed["accepted_reference"], selected["accepted_reference"])
        ref = selected[surface_context.REFERENCE_KEY]["snapshot_ref"]
        artifacts = agent_memory.restore(self.pkg, ref)
        self.assertNotIn(view.ENV, artifacts)
        receipt = canonical.loads(artifacts[view.VIEW])
        self.assertEqual("full_source_retention_limit", receipt["mode"])
        self.assertEqual(agent_memory.MAX_ARTIFACT_BYTES + 1, receipt["observed_artifacts"][view.ENV]["size"])
        self.assertFalse(receipt["environment_retained"])
        with patch.object(Path, "read_bytes", side_effect=AssertionError("ambient read")):
            self.assertEqual(self.fixed, surface_context.restore_fixed_context(self.pkg, selected))
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(BlockedError):
            view.capture_artifacts(self.pkg, self.fixed)
        path.unlink()
        with self.assertRaises(BlockedError):
            view.capture_artifacts(self.pkg, self.fixed)

    def test_total_checkpoint_retention_budget_has_explicit_full_source_fallback(self):
        artifacts = view.capture_artifacts(self.pkg, self.fixed, retention_reserved_bytes=agent_memory.MAX_CHECKPOINT_BYTES)
        self.assertEqual({view.VIEW}, set(artifacts))
        self.assertEqual(self.fixed["accepted_reference"], view.project_reference(self.fixed, artifacts))


if __name__ == "__main__":
    unittest.main()
