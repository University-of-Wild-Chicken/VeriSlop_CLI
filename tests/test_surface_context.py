"""Surface authoring engineering fixtures; no live model qualification."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from relation_authoring_fixture import mock_relation_authority

from verislop import agent_memory, agents, canonical, exact_context, schemas, surface_context
from verislop.bridges import vscore3_checker
from verislop.errors import BlockedError, Diagnostic, UsageError
from verislop.events import EventSink
from verislop.package import Package
from verislop.providers import config as provider_config
from verislop.targets import vscore3_source


class SurfaceContextTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock_relation_authority().close)
        self.temp = tempfile.TemporaryDirectory(prefix="verislop-surface-context-")
        self.addCleanup(self.temp.cleanup)
        self.pkg = Package(Path(self.temp.name) / "run")
        self.pkg.ensure("surface-authoring-engineering-fixture")
        self.events = EventSink(self.pkg.run_id, quiet=True)
        self.addCleanup(self.events.close)
        self.params = {"target": "vscore", "backend": "verislop.backend.vscore/0.3", "backend_version": "0.3"}
        self.fixed = {"parameters": self.params, "source_grammar": {"exact_original": "canonical source schema"},
            "lean_toolchain": "fixture-pin", "accepted_profile": {"enums": {
                "Opaque.Enum": {"constructors": ["z-last", "a-first"], "lean_decl": "Fixture.Enum"}}},
            "accepted_reference": {"lean_source": "-- exact fixture reference\n"},
            "accepted_packages": {}, "required_obligations": ["O9"], "unknown_fixed_metadata": ["é", True, 1]}
        from test_author_reference import fixture
        fixture(self.pkg, self.fixed)
        self.surface = ('// retain exact author bytes\nprogram "vscore/0.3" profile "data-pipeline/0.3";\n'
                        'entry same(x:Enum(@"Opaque.Enum"))->Enum(@"Opaque.Enum"){x}\n')
        self.relation = {"schema_version": "0.3", "format": "verislop.vscore-relation/0.3",
            "template": "vscore.reference_refinement/0.3", "source_slot": "vscore-source",
            "proof_slot": "vscore-proof", "bindings": [{"symbol": "same", "entry": "same"}]}

    def conf(self, mode="surface"):
        result = {"roles": {"implementer": "author"}, "agents": {"author": {}}}
        if mode is not None:
            result["agents"]["author"]["vscore_authoring_format"] = mode
        return result

    def rejected(self, responses, mode="surface", fixed=None, preview=None):
        calls = []
        def completion(*args):
            calls.append(args)
            return SimpleNamespace(text=responses[len(calls) - 1])
        with patch.object(agents, "_vscore_context", return_value=fixed or self.fixed), \
                patch.object(agents, "recorded_call", side_effect=completion), \
                patch.object(vscore3_checker, "preview", side_effect=preview or AssertionError("unexpected preview")) as checked:
            with self.assertRaises(UsageError):
                agents._vscore_implementation(None, self.conf(mode), self.pkg, self.events,
                    {"parameters": (fixed or self.fixed)["parameters"]}, attempts=len(responses), proof_attempts=0)
        return calls, checked

    def test_exact_view_restores_all_fields_without_ambient_sources(self):
        before = copy.deepcopy(self.fixed)
        view = surface_context.project_fixed_context(self.pkg, self.fixed)
        self.assertEqual(before, self.fixed)
        grammar = Path(surface_context.__file__).resolve().parent.parent / surface_context.GRAMMAR_PATH
        self.assertEqual(grammar.read_bytes(), view["source_grammar"]["text"].encode())
        for key in self.fixed:
            if key not in ("source_grammar", "accepted_reference"):
                self.assertEqual(self.fixed[key], view[key])
        with patch.object(Path, "read_bytes", side_effect=AssertionError("ambient read during historical restore")):
            self.assertEqual(self.fixed, surface_context.restore_fixed_context(self.pkg, view))
        view["unknown_fixed_metadata"][0] = "mutated"
        self.assertEqual("é", self.fixed["unknown_fixed_metadata"][0])

    def test_stale_reference_grammar_toolchain_and_semantic_fields_rejected(self):
        original = surface_context.project_fixed_context(self.pkg, self.fixed)
        changes = [lambda d: d.update(extra="unbound"),
            lambda d: d["source_grammar"].update(text="different grammar"),
            lambda d: d["accepted_profile"]["enums"]["Opaque.Enum"]["constructors"].reverse(),
            lambda d: d.update(required_obligations=[]),
            lambda d: d[surface_context.REFERENCE_KEY].update(extra=1),
            lambda d: d[surface_context.REFERENCE_KEY].update(lean_toolchain="stale"),
            lambda d: d[surface_context.REFERENCE_KEY].update(compiler_sha256="sha256:stale"),
            lambda d: d[surface_context.REFERENCE_KEY].update(fixed_sha256="sha256:stale"),
            lambda d: d[surface_context.REFERENCE_KEY].update(grammar_sha256="sha256:stale")]
        for change in changes:
            view = copy.deepcopy(original)
            change(view)
            with self.subTest(view=view), self.assertRaises(BlockedError):
                surface_context.restore_fixed_context(self.pkg, view)

    def test_changed_retained_compiler_blob_rejected(self):
        view = surface_context.project_fixed_context(self.pkg, self.fixed)
        reference = view[surface_context.REFERENCE_KEY]
        snapshot = canonical.load_file(self.pkg.root / reference["snapshot_ref"]["path"])
        row = next(x for x in snapshot["artifacts"] if x["source_ref"] == "compiler-sources.json")
        path = self.pkg.root / row["blob_ref"]["path"]
        path.chmod(0o600)
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(BlockedError):
            surface_context.restore_fixed_context(self.pkg, view)

    def test_real_parser_uses_exact_enums_and_preserves_checker_bytes(self):
        expected = vscore3_source.compile_surface(self.surface, {"Opaque.Enum": ["z-last", "a-first"]})
        raw = json.dumps({"program_source": self.surface, "relation": self.relation})
        rejected = vscore3_checker.EdgeFailure([Diagnostic("KERNEL_REJECTION", "fixture preview rejection")])
        with patch.object(vscore3_source, "compile_surface", wraps=vscore3_source.compile_surface) as compiler:
            calls, preview = self.rejected([raw], preview=rejected)
        compiler.assert_called_once_with(self.surface, {"Opaque.Enum": ["z-last", "a-first"]})
        self.assertEqual(expected, preview.call_args.args[1])
        self.assertEqual(canonical.dumps(self.relation), preview.call_args.args[2])
        stage = self.pkg.root / "agents/vscore-attempts/source-1"
        self.assertEqual(self.surface.encode(), (stage / "program.vsc").read_bytes())
        self.assertEqual(expected, (stage / "program.vscore.json").read_bytes())
        self.assertEqual(raw, (stage / "response.txt").read_text())
        self.assertIn('"program_source"', calls[0][4])
        self.assertNotIn('"program": <source program object>', calls[0][4])
        view = exact_context.restore_prompt(calls[0][5])["fixed_context"]
        self.assertEqual(self.fixed, surface_context.restore_fixed_context(self.pkg, view))

    def test_malformed_surface_repairs_with_exact_response_and_full_diagnostics_once_retained(self):
        raw = json.dumps({"program_source": self.surface.replace("{x}", "{unknown}"), "relation": self.relation})
        calls, preview = self.rejected([raw, raw])
        preview.assert_not_called()
        first, second = [exact_context.restore_prompt(call[5]) for call in calls]
        self.assertEqual(first["fixed_context"], second["fixed_context"])
        self.assertEqual(raw, second["previous_response"])
        full = canonical.load_file(self.pkg.root / second["previous_diagnostics"]["full_diagnostics"]["path"])
        self.assertEqual(full, second["previous_diagnostic_record"])
        self.assertIn("unknown", full["diagnostics"][0]["message"])
        snapshots = [canonical.load_file(p) for p in (self.pkg.root / "agents/memory/snapshots").glob("*.json")]
        self.assertEqual(1, sum(s["stage"] == "implementer/vscore/surface-authoring" for s in snapshots))

    def test_mixed_and_wrong_envelopes_are_not_reinterpreted(self):
        bad = [{"program": {}, "relation": self.relation},
               {"program_source": self.surface, "program": {}, "relation": self.relation},
               {"program_source": self.surface, "relation": self.relation, "extra": True},
               {"program_source": {}, "relation": self.relation},
               {"program_source": self.surface, "relation": []}]
        calls, preview = self.rejected([json.dumps(p) for p in bad])
        preview.assert_not_called()
        self.assertEqual(5, len(calls))
        self.assertEqual(self.surface.encode(), (self.pkg.root / "agents/vscore-attempts/source-2/program.vsc").read_bytes())
        self.assertFalse((self.pkg.root / "agents/vscore-attempts/source-2/program.vscore.json").exists())

    def test_default_and_explicit_canonical_keep_existing_system_and_context(self):
        for mode in (None, "canonical_json"):
            calls, _ = self.rejected([json.dumps({"program_source": self.surface, "relation": self.relation})], mode)
            self.assertEqual(agents.VSCORE3_IMPLEMENTER_SYSTEM, calls[0][4])
            self.assertEqual(self.fixed, exact_context.restore_prompt(calls[0][5])["fixed_context"])
        self.assertIsNone(agent_memory.latest_snapshot(self.pkg, stage_prefix="implementer/vscore/surface-authoring"))

    def test_unsupported_legacy_and_python_targets_fail_before_dispatch(self):
        legacy = {**self.fixed, "parameters": {"target": "vscore", "backend": "verislop.backend.vscore/0.1", "backend_version": "0.1"}}
        with patch.object(agents, "_vscore_context", return_value=legacy), patch.object(agents, "recorded_call") as call:
            with self.assertRaises(UsageError) as exc:
                agents._vscore_implementation(None, self.conf(), self.pkg, self.events,
                    {"parameters": legacy["parameters"]}, attempts=1, proof_attempts=0)
            self.assertEqual("UNSUPPORTED_CAPABILITY", exc.exception.diagnostics[0].code)
            call.assert_not_called()
        with patch.object(agents, "_broker", return_value=(None, self.conf())), patch.object(agents, "recorded_call") as call:
            run = agents.implementer_agent("unused", self.pkg, self.events)
            with self.assertRaises(UsageError) as exc:
                run({"parameters": {"target": "python"}})
            self.assertEqual("UNSUPPORTED_CAPABILITY", exc.exception.diagnostics[0].code)
            call.assert_not_called()

    def test_configuration_accepts_provider_independent_modes_and_rejects_unknown_values(self):
        conf = canonical.load_file(Path(__file__).resolve().parents[1] / "examples/local-hybrid-tier2-config.json")
        name = conf["roles"]["implementer"]
        for mode in (None, "canonical_json", "surface"):
            value = copy.deepcopy(conf)
            value["agents"][name].pop("vscore_authoring_format", None)
            if mode is not None:
                value["agents"][name]["vscore_authoring_format"] = mode
            self.assertEqual([], schemas.validate("review-config", value))
            result = provider_config.resolve(value, {})
            self.assertFalse(any("vscore_authoring_format" in d.message for d in result.diagnostics))
        for mode in ("future", None, [], 42):
            value = copy.deepcopy(conf)
            value["agents"][name]["vscore_authoring_format"] = mode
            self.assertTrue(schemas.validate("review-config", value))
            self.assertTrue(any("vscore_authoring_format" in d.message for d in provider_config.resolve(value, {}).diagnostics))


if __name__ == "__main__":
    unittest.main()
