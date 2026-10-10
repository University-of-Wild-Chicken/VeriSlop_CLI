"""Frozen support transport boundaries; fresh fixtures, no Lean or model execution.

Qualification/schema tests live with the readable checker. Here the qualification
service is isolated to test consumers losing or substituting its exact byte map.
"""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from verislop import canonical, fsutil, policy, review_projection
from verislop.backends import vscore3 as backend, vscore3_closure as closure
from verislop.bridges import vscore3_checker as checker
from verislop.bridges import vscore3_readable_support as readable_support
from verislop.bridges.manifest import InvalidPackage, PackageReader
from verislop.events import EventSink
from verislop.package import Package
from verislop.stage import StageResult


SELECTION = "support/readable/selection.json"
DIAGNOSTIC = "support/readable/diagnostics/qualification.json"
MANIFEST = "readable/manifest.json"


def metadata_fixture(selection, read_bytes):
    """Isolated qualification boundary with independent byte/hash validation."""
    value = canonical.loads(selection)
    result = {SELECTION: selection}
    for ref in value["diagnostic_inputs"]:
        artifact = ref["artifact"]
        data = read_bytes(artifact["path"])
        if (canonical.digest(data), len(data)) != (artifact["sha256"], artifact["size"]):
            raise InvalidPackage("fixture diagnostic changed", "INPUT_MUTATION")
        result[artifact["path"]] = data
    return result


def artifact_refs_fixture(descriptor, read_bytes):
    manifest = read_bytes(descriptor["manifest"]["path"])
    if canonical.digest(manifest) != descriptor["manifest"]["sha256"]:
        raise InvalidPackage("fixture manifest changed", "INPUT_MUTATION")
    refs = {descriptor["manifest"]["path"]: canonical.digest(manifest)}
    for path, expected in canonical.loads(manifest)["artifacts"].items():
        data = read_bytes(path)
        if canonical.digest(data) != expected:
            raise InvalidPackage("fixture support byte changed", "INPUT_MUTATION")
        refs[path] = expected
    return refs


def selected_fixture(mode="CHECKED", diagnostic=b"generic qualification diagnostic"):
    selection = canonical.dumps({"selected_mode": mode,
        "status": "CHECKED" if mode == "CHECKED" else "UNSUPPORTED",
        "diagnostic_inputs": [{"slot_id": "generic-diagnostic", "role": "readable_diagnostic",
            "artifact": {"path": DIAGNOSTIC, "sha256": canonical.digest(diagnostic), "size": len(diagnostic)}}]})
    return {SELECTION: selection, DIAGNOSTIC: diagnostic}


def support_fixture(mode="CHECKED"):
    artifacts = selected_fixture(mode)
    artifacts[MANIFEST] = canonical.dumps({"artifacts": {
        path: canonical.digest(data) for path, data in sorted(artifacts.items())}})
    descriptor = {"version": "generic-fixture", "mode": mode,
        "status": "CHECKED" if mode == "CHECKED" else "UNSUPPORTED",
        "selection": {"slot_id": "vscore-readable-selection", "sha256": canonical.digest(artifacts[SELECTION])},
        "manifest": {"path": MANIFEST, "sha256": canonical.digest(artifacts[MANIFEST])},
        "support_inventory_hash": canonical.digest(b"generic inventory"),
        "support_module_parts_hash": canonical.digest(b"generic modules"),
        "selected_goal_hash": canonical.digest(b"generic selected goal")}
    return descriptor, artifacts


class ReadableConsumers(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="verislop-readable-consumers-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.pkg = Package(self.root / "run")
        self.pkg.ensure("generic-readable-consumer")
        self.events = EventSink(self.pkg.run_id, quiet=True)
        self.addCleanup(self.events.close)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in (("READABLE_SELECTION_PATH", SELECTION),
                            ("READABLE_SELECTION_SLOT", "vscore-readable-selection"),
                            ("readable_candidate_metadata", metadata_fixture),
                            ("readable_artifact_refs", artifact_refs_fixture)):
            self.stack.enter_context(patch.object(checker, name, value, create=True))

    def test_candidate_reader_preserves_declared_bytes_and_rejects_mutation(self):
        candidate = self.root / "candidate"
        metadata = selected_fixture("BASE")
        for name, data in metadata.items():
            fsutil.atomic_write(candidate / name, data)
        reader = PackageReader(candidate)
        try:
            selection, result = backend._candidate_readable_metadata(reader)
            self.assertEqual((selection, result), (metadata[SELECTION], metadata))
            fsutil.atomic_write(candidate / DIAGNOSTIC, b"changed diagnostic")
            with self.assertRaises(InvalidPackage):
                reader.recheck()
        finally:
            reader.close()
        reader = PackageReader(candidate)
        try:
            with self.assertRaises(InvalidPackage):
                backend._candidate_readable_metadata(reader)
        finally:
            reader.close()

    def test_missing_selection_is_legacy_and_symlink_selection_is_rejected(self):
        candidate = self.root / "candidate"
        candidate.mkdir()
        reader = PackageReader(candidate)
        try:
            self.assertEqual(backend._candidate_readable_metadata(reader), (None, {}))
        finally:
            reader.close()
        fsutil.atomic_write(self.root / "outside.json", selected_fixture()[SELECTION])
        (candidate / SELECTION).parent.mkdir(parents=True)
        (candidate / SELECTION).symlink_to(self.root / "outside.json")
        reader = PackageReader(candidate)
        try:
            with self.assertRaises(InvalidPackage):
                backend._candidate_readable_metadata(reader)
        finally:
            reader.close()

    def setup_generate(self, metadata, *, replay_mutation=None, package_mutation=None, frozen=False):
        fsutil.write_json(self.pkg.path("interpretation"), {})
        fsutil.write_json(self.pkg.root / "acceptance.json", {})
        self.params = {"require_state": "END_TO_END_VERIFIED", "require_tests": False,
                       "bridge_id": "implementation"}
        self.source = b"generic source bytes"
        self.relation = b"generic relation bytes"
        self.proof = b"generic proof bytes"
        self.candidate = self.root / "candidate"
        for name, data in {backend.SOURCE_FILE: self.source, "relation.json": self.relation,
                           "Proof.lean": self.proof, **metadata}.items():
            fsutil.atomic_write(self.candidate / name, data)
        self.ctx = SimpleNamespace(inputs={"source": ("source", self.source),
            "relation": ("relation", self.relation), "proof_source": ("proof", self.proof)},
            readable_selection=metadata.get(SELECTION),
            readable_diagnostics={path: data for path, data in metadata.items() if path != SELECTION},
            plan={"acceptance_certificate": {}}, bridge_id="implementation")
        self.preview_calls = []
        self.prepared_maps = []

        def preview(_pkg, source, relation, proof=None, **options):
            self.preview_calls.append((source, relation, proof, options))
            info = {"readable_selection": metadata.get(SELECTION), "readable_candidate_artifacts": dict(metadata)}
            if replay_mutation:
                replay_mutation(info)
            return None, None, info

        def files(_bid, info, source, relation, proof):
            result = {backend.SOURCE_FILE: source, "relation.json": relation, "Proof.lean": proof,
                      "proposal.json": canonical.dumps({"format": "generic-proposal"}),
                      **info["readable_candidate_artifacts"]}
            if package_mutation:
                package_mutation(result)
            return result

        def prepare(_pkg, _events, _proposal, stage, **_kwargs):
            self.prepared_maps.append({name: (stage / name).read_bytes() for name in fsutil.list_files(stage)})
            return StageResult("prepare", "PASS", "generic fixture")

        patches = [patch.object(backend.C, "frozen_json", return_value={}),
            patch.object(backend.admission, "features", return_value=({}, [])),
            patch.object(backend.admission, "admit", return_value=("admitted", [], [])),
            patch.object(backend, "_scope_context", return_value=self.ctx),
            patch.object(backend, "selection_record", return_value={"bridge_id": "implementation"}),
            patch.object(backend, "selection", return_value={"bridge_id": "implementation"}),
            patch.object(backend, "implementation_claims", return_value={"parameters": self.params, "claims": []}),
            patch.object(backend, "_binding_proposal", return_value={}), patch.object(backend, "_schema"),
            patch.object(backend, "_materialize", return_value=[]), patch.object(backend, "roots", return_value={}),
            patch.object(backend.registry, "select", return_value={}), patch("verislop.view.write"),
            patch.object(checker, "preview", side_effect=preview),
            patch.object(checker, "candidate_files", side_effect=files),
            patch.object(backend.prepare, "run", side_effect=prepare)]
        for item in patches:
            self.stack.enter_context(item)
        if frozen:
            fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json",
                              {"parameters": self.params, "claims": []})

    def generate(self, *, agent=False):
        kwargs = ({"agent": lambda _ctx: ({backend.SOURCE_FILE: self.source, "relation.json": self.relation,
            "Proof.lean": self.proof, **selected_fixture("BASE")}, None)} if agent else {"candidate": self.candidate})
        return backend.generate(self.pkg, self.events, {"acceptance_certificate_ref": "acceptance.json"},
                                canonical.digest(b"generic ir"), {}, self.params, **kwargs)

    def test_explicit_candidate_and_agent_preserve_base_diagnostics_without_reselection(self):
        for via_agent in (False, True):
            with self.subTest(via_agent=via_agent):
                # Each route gets its own package so the second call cannot use a frozen run.
                self.pkg = Package(self.root / ("agent" if via_agent else "explicit"))
                self.pkg.ensure("generic-readable-route")
                metadata = selected_fixture("BASE")
                with ExitStack() as route:
                    old = self.stack
                    self.stack = route
                    self.setup_generate(metadata)
                    result = self.generate(agent=via_agent)
                    self.stack = old
                self.assertEqual(result.status, "PASS", result.diagnostics)
                self.assertEqual(self.preview_calls, [(self.source, self.relation, None, {
                    "readable_selection": metadata[SELECTION], "select_readable": False,
                    "readable_diagnostics": {DIAGNOSTIC: metadata[DIAGNOSTIC]}})])
                self.assertTrue(all(self.prepared_maps[0][name] == data for name, data in metadata.items()))

    def test_checked_candidate_replay_preserves_exact_metadata_and_proof_is_not_checked(self):
        metadata = selected_fixture()
        self.setup_generate(metadata)
        result = self.generate()
        self.assertEqual(result.status, "PASS", result.diagnostics)
        self.assertIsNone(self.preview_calls[0][2])
        self.assertEqual(self.prepared_maps[0]["Proof.lean"], self.proof)
        self.assertEqual({path: self.prepared_maps[0][path] for path in metadata}, metadata)

    def test_legacy_candidate_uses_unchanged_preview_call(self):
        self.setup_generate({})
        result = self.generate()
        self.assertEqual(result.status, "PASS", result.diagnostics)
        self.assertEqual(self.preview_calls, [(self.source, self.relation, None, {})])

    def test_replay_downgrade_fails_before_preparation(self):
        self.setup_generate(selected_fixture(), replay_mutation=lambda info: info.update(
            readable_selection=None, readable_candidate_artifacts={}))
        result = self.generate()
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.diagnostics[0].code, "INPUT_MUTATION")
        self.assertEqual(self.prepared_maps, [])

    def test_replay_cannot_substitute_only_frozen_diagnostic_bytes(self):
        self.setup_generate(selected_fixture("BASE"), replay_mutation=lambda info:
                            info["readable_candidate_artifacts"].update({DIAGNOSTIC: b"replacement"}))
        result = self.generate()
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.diagnostics[0].code, "INPUT_MUTATION")
        self.assertEqual(self.prepared_maps, [])

    def test_prepared_context_cannot_drop_selected_support(self):
        self.setup_generate(selected_fixture())
        self.ctx.readable_selection = None
        self.ctx.readable_diagnostics = {}
        result = self.generate()
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.diagnostics[0].code, "INPUT_MUTATION")
        self.assertEqual(len(self.prepared_maps), 1)
        self.assertFalse((self.pkg.path("closure") / "implementation-claims.json").exists())

    def test_candidate_packaging_cannot_drop_frozen_diagnostics(self):
        self.setup_generate(selected_fixture("BASE"), package_mutation=lambda files: files.pop(DIAGNOSTIC))
        result = self.generate()
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.diagnostics[0].code, "INPUT_MUTATION")
        self.assertEqual(self.prepared_maps, [])

    def test_frozen_rerun_cannot_replace_valid_selection_and_diagnostic_pair(self):
        original = selected_fixture("BASE")
        self.setup_generate(original, frozen=True)
        changed = selected_fixture("BASE", b"different but internally valid diagnostic")
        for name, data in changed.items():
            fsutil.atomic_write(self.candidate / name, data)
        result = self.generate()
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.diagnostics[0].code, "CLAIM_MUTATION")
        self.assertEqual(self.preview_calls, [])

    def test_materialization_and_link_reject_dropped_checked_support(self):
        descriptor, artifacts = support_fixture()
        ctx = SimpleNamespace(readable_selection=artifacts[SELECTION],
            acceptance={"toolchain": {"pin": "generic"}}, edge={"expected_proposition_hash": "generic"})
        spec = SimpleNamespace(text="generic selected goal")
        build = SimpleNamespace(readable_support=None)
        fsutil.write_json(self.pkg.path("implementation") / backend.INVENTORY_FILE, {})
        with patch.object(backend, "selection", return_value={"bridge_id": "generic", "covered": []}), \
             patch.object(backend, "_scope_context", return_value=ctx), \
             patch.object(backend, "_frozen_json", return_value={"claims": []}), \
             patch.object(backend, "_schema"), patch.object(checker, "derive_goal", return_value=spec), \
             patch.object(checker, "run_build", return_value=build, create=True) as replay, \
             patch.object(backend.leanbridge, "resolve_toolchain", return_value=None):
            with self.assertRaises(checker.EdgeFailure) as rejected:
                backend._materialize(self.pkg, self.events, ctx, {"claims": []})
            self.assertEqual(rejected.exception.diagnostics[0].code, "INPUT_MUTATION")
            result = backend.link(self.pkg, self.events)
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.diagnostics[0].code, "INPUT_MUTATION")
        self.assertEqual([call.kwargs for call in replay.call_args_list],
                         [{"with_proof": False}, {"with_proof": False}])

    def test_frozen_support_guard_rejects_goal_mode_and_selection_substitution(self):
        descriptor, artifacts = support_fixture()
        ctx = SimpleNamespace(readable_selection=artifacts[SELECTION])
        spec = SimpleNamespace(text="generic selected goal")
        backend._require_selected_readable(ctx, spec, SimpleNamespace(readable_support=descriptor))
        for changed in ({**descriptor, "mode": "BASE"},
                        {**descriptor, "selection": {"slot_id": "vscore-readable-selection", "sha256": canonical.digest(b"other")}},
                        {**descriptor, "selected_goal_hash": canonical.digest(b"other goal")}):
            with self.subTest(changed=changed), self.assertRaises(checker.EdgeFailure):
                backend._require_selected_readable(ctx, spec, SimpleNamespace(readable_support=changed))
        with self.assertRaises(checker.EdgeFailure):
            backend._require_selected_readable(SimpleNamespace(readable_selection=None), spec,
                                               SimpleNamespace(readable_support=descriptor))

    def test_support_projection_is_complete_and_ignores_process_timing(self):
        descriptor, artifacts = support_fixture()
        build = SimpleNamespace(readable_support=descriptor, readable_artifacts=artifacts,
                                process_evidence={"elapsed_seconds": "1.0"})
        observed = closure._readable_output(build)
        self.assertEqual(observed, {"descriptor": descriptor,
            "artifacts": {path: canonical.digest(data) for path, data in artifacts.items()}})
        build.process_evidence = {"elapsed_seconds": "2.0"}
        self.assertEqual(closure._readable_output(build), observed)
        build.readable_artifacts = {**artifacts, "readable/unlisted.json": b"unlisted"}
        with self.assertRaises(InvalidPackage):
            closure._readable_output(build)
        with self.assertRaises(InvalidPackage):
            closure._readable_output(SimpleNamespace(readable_support=None, readable_artifacts=artifacts))

    def retained_support(self):
        descriptor, artifacts = support_fixture("BASE")
        prefix = "builds/A/"
        for path, data in artifacts.items():
            fsutil.atomic_write(self.root / (prefix + "semantic/" + path), data)
        reader = PackageReader(self.root)
        self.addCleanup(reader.close)
        observed = closure._readable_output(SimpleNamespace(readable_support=descriptor, readable_artifacts=artifacts))
        expected = {prefix + "semantic/" + path for path in artifacts}
        return reader, prefix, expected, {"readable_support": descriptor}, observed

    def test_retained_support_requires_complete_execution_membership(self):
        reader, prefix, expected, envelope, observed = self.retained_support()
        closure._validate_retained_readable(reader, prefix, expected, envelope, observed)
        with self.assertRaises(InvalidPackage) as rejected:
            closure._validate_retained_readable(reader, prefix, expected - {prefix + "semantic/" + DIAGNOSTIC},
                                                envelope, observed)
        self.assertEqual(rejected.exception.code, "ORPHAN_CLAIM")

    def test_retained_support_cannot_disagree_with_envelope_or_omit_manifest_ref(self):
        reader, prefix, expected, envelope, observed = self.retained_support()
        with self.assertRaises(InvalidPackage):
            closure._validate_retained_readable(reader, prefix, expected, {}, observed)
        with self.assertRaises(InvalidPackage):
            closure._validate_retained_readable(reader, prefix, expected, envelope, None)
        dropped = {**observed, "artifacts": {path: digest for path, digest in observed["artifacts"].items() if path != MANIFEST}}
        with self.assertRaises(InvalidPackage):
            closure._validate_retained_readable(reader, prefix, expected, envelope, dropped)

    def test_retained_support_checks_bytes_independent_of_outer_inventory(self):
        reader, prefix, expected, envelope, observed = self.retained_support()
        fsutil.atomic_write(self.root / (prefix + "semantic/" + DIAGNOSTIC), b"mutated retained diagnostic")
        with self.assertRaises(InvalidPackage):
            closure._validate_retained_readable(reader, prefix, expected, envelope, observed)

    def test_support_closure_projection_survives_registered_normalizer(self):
        descriptor, artifacts = support_fixture()
        support = closure._readable_output(SimpleNamespace(readable_support=descriptor, readable_artifacts=artifacts))
        outputs = {name: None for name in closure.COMPARISON_SLOTS}
        outputs["readable_support"] = support
        row = {"build": "A", "ok": True, "errors": [], "closure_root": "generic-root", "producer": {},
               "outputs": outputs, "execution": {"wall_ms": 91}}
        projected = review_projection._builds([row], [])[0]
        self.assertEqual(projected["outputs"]["readable_support"], support)
        self.assertNotIn("execution", projected)

    def setup_clean_build(self, mode="CHECKED"):
        """Isolate kernel qualification while exercising closure's byte replay."""
        descriptor, artifacts = support_fixture(mode)
        source = b"generic replay source"
        spec = SimpleNamespace(text="generic selected goal", source_bytes=source)

        @dataclass
        class Context:
            contract_module: bytes
            accepted_ir: dict
            acceptance: dict
            readable_selection: bytes
            edge: dict

        digest = canonical.digest(b"generic checked proposition")
        certificate = {"artifacts": {"olean": {"path": "contract.olean", "sha256": canonical.digest(b"contract")}},
                       "obligations": {}, "toolchain": {"pin": "generic"}}
        ctx = Context(b"old contract", {}, certificate, artifacts[SELECTION], {"expected_proposition_hash": digest})
        imported = SimpleNamespace(certificate=certificate, files={"contract.olean": b"contract", "ir.json": b"{}"},
                                   ir={}, ir_path="ir.json", replay_receipt={"generic": "replayed"})
        build = SimpleNamespace(readable_support=descriptor, readable_artifacts=artifacts,
            process_evidence={"elapsed_seconds": "1.0"}, proposition_hash=digest,
            observation={"generic": "deterministic semantic build"}, modules={})
        fresh = {checker.CERTIFICATE: canonical.dumps({"accepted_modules": [], "readable_support": descriptor}),
                 checker.IR_FILE: b"{}", "goal/VeriSlopBridgeGoal.lean": spec.text.encode(),
                 "builds/A.json": b"{}", "builds/B.json": b"{}", **artifacts}
        selection = {"bridge_id": "generic", "edge_id": "generic-edge",
                     "build_policy": {"total_timeout_seconds": 60}}
        accepted = self.pkg.root / "bridges" / "generic" / checker.SEMANTIC_DIR / checker.edge_key("generic-edge")
        for path, data in fresh.items():
            fsutil.atomic_write(accepted / path, data)
        fsutil.atomic_write(self.pkg.path("implementation") / backend.SOURCE_FILE, source)
        for item in (patch.object(closure, "import_contract", return_value=imported),
                     patch.object(closure, "_check_preparation"),
                     patch.object(checker, "load_context", return_value=ctx),
                     patch.object(checker, "derive_goal", return_value=spec),
                     patch.object(checker, "run_build", return_value=build, create=True),
                     patch.object(checker, "outputs", return_value=fresh),
                     patch.object(checker, "_certificate_descriptor", side_effect=lambda value: value),
                     patch.object(closure.leanbridge, "resolve_toolchain", return_value=None),
                     patch.object(backend, "materialization_inventory", return_value={"generic": "inventory"}),
                     patch.object(backend, "checked_link", return_value=({"generic": "link"}, [])),
                     patch.object(closure, "_json", return_value={"inventory": {"generic": "inventory"}}),
                     patch.object(closure, "_nonfinal", return_value=([], []))):
            self.stack.enter_context(item)
        return build, fresh, selection, accepted

    def test_clean_closure_replays_exact_support_and_ignores_fresh_process_timing(self):
        build, _fresh, selection, _accepted = self.setup_clean_build()
        a = closure._clean_build(self.pkg, "A", selection, [], {"closure_root": "generic-root"}, {})
        build.process_evidence = {"elapsed_seconds": "different fresh timing"}
        b = closure._clean_build(self.pkg, "B", selection, [], {"closure_root": "generic-root"}, {})
        self.assertEqual(a["outputs"], b["outputs"])
        self.assertEqual(set(a["outputs"]), set(closure.COMPARISON_SLOTS))
        for path, data in build.readable_artifacts.items():
            self.assertEqual(a.artifacts["semantic/" + path], data)
        self.assertEqual(a["outputs"]["readable_support"]["descriptor"], build.readable_support)

    def test_clean_closure_preserves_unavailable_base_diagnostic_bytes(self):
        build, _fresh, selection, _accepted = self.setup_clean_build("BASE")
        result = closure._clean_build(self.pkg, "A", selection, [], {"closure_root": "generic-root"}, {})
        self.assertEqual(result["outputs"]["readable_support"]["descriptor"]["mode"], "BASE")
        self.assertEqual(result.artifacts["semantic/" + DIAGNOSTIC], build.readable_artifacts[DIAGNOSTIC])

    def test_clean_closure_rejects_mutated_frozen_support_and_dropped_build_selection(self):
        build, _fresh, selection, accepted = self.setup_clean_build()
        fsutil.atomic_write(accepted / DIAGNOSTIC, b"changed frozen diagnostic")
        with self.assertRaises(InvalidPackage):
            closure._clean_build(self.pkg, "A", selection, [], {"closure_root": "generic-root"}, {})
        build.readable_support = None
        with self.assertRaises(checker.EdgeFailure) as rejected:
            closure._clean_build(self.pkg, "B", selection, [], {"closure_root": "generic-root"}, {})
        self.assertEqual(rejected.exception.diagnostics[0].code, "INPUT_MUTATION")

    def test_clean_closure_rejects_support_certificate_without_selected_build(self):
        build, _fresh, selection, _accepted = self.setup_clean_build()
        build.readable_support = None
        build.readable_artifacts = {}
        # Simulate a loader dropping the selection and an outputs producer inventing
        # support. The cross-check still rejects it without relying on either service.
        with patch.object(backend, "_require_selected_readable"):
            with self.assertRaises(InvalidPackage) as rejected:
                closure._clean_build(self.pkg, "A", selection, [], {"closure_root": "generic-root"}, {})
        self.assertEqual(rejected.exception.code, "STATEMENT_MISMATCH")


class ProductionReadableMetadata(unittest.TestCase):
    """Real closed schemas/helpers with a fresh unavailable BASE serialization."""
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="verislop-readable-production-metadata-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.diagnostic_path = "support/readable/diagnostics/0.json"
        diagnostic = canonical.dumps({"reported": "generic unsupported view", "complete": True})
        self.ctx = SimpleNamespace(inputs={"source": ("source", b"generic source"),
            "profile": ("profile", b"generic profile"), "relation": ("relation", b"generic relation")},
            accepted_profile={"profile_id": "generic-profile"},
            accepted_profile_hash=canonical.digest(b"generic accepted profile"),
            plan={}, accepted_ir={}, acceptance={"toolchain": {"pin": "generic-pin"}}, relation={},
            policy=policy.get("strict"), readable_diagnostics={self.diagnostic_path: diagnostic})
        self.spec = SimpleNamespace(source_bytes=b"generic source", text="generic unchanged base goal",
                                    base_text="generic unchanged base goal", enums=[], adapters=[])
        self.build = checker.Build({"toolchain_olean_closure": canonical.digest(b"generic toolchain closure")}, {}, {},
                                   canonical.digest(b"generic proposition"), {}, [])
        artifact = readable_support.ref(self.diagnostic_path, diagnostic)
        reason = {"code": "UNSUPPORTED_CONSTRUCTOR", "stage": "coverage", "source_path": None,
                  "message": "generic unavailable fixture", "reported_error_count": 1,
                  "diagnostic_artifact": artifact, "diagnostic_complete": True}
        record = readable_support.selection_record(self.ctx, self.spec, self.build,
            reasons=[reason], diagnostics=[{"slot_id": "vscore-readable-diagnostic-0",
                                            "role": "readable_diagnostic", "artifact": artifact}])
        self.selection = canonical.dumps(record)
        self.ctx.readable_selection = self.selection
        readable_support.attach(self.ctx, self.spec, self.build, self.build, self.selection)

    def test_real_selection_helper_and_backend_reader_preserve_full_base_metadata(self):
        expected = {SELECTION: self.selection, **self.ctx.readable_diagnostics}
        self.assertEqual(checker.readable_candidate_metadata(self.selection, expected.__getitem__), expected)
        for path, data in expected.items():
            fsutil.atomic_write(self.root / path, data)
        reader = PackageReader(self.root)
        try:
            self.assertEqual(backend._candidate_readable_metadata(reader), (self.selection, expected))
            self.assertEqual(backend._context_readable_metadata(self.ctx), expected)
            reader.recheck()
        finally:
            reader.close()

    def test_real_manifest_helper_binds_complete_support_and_retained_execution(self):
        output = closure._readable_output(self.build)
        self.assertEqual(output["artifacts"], {path: canonical.digest(data)
            for path, data in self.build.readable_artifacts.items()})
        backend._require_selected_readable(self.ctx, self.spec, self.build)
        prefix = "builds/A/"
        expected = set()
        for path, data in self.build.readable_artifacts.items():
            full_path = prefix + "semantic/" + path
            fsutil.atomic_write(self.root / full_path, data)
            expected.add(full_path)
        reader = PackageReader(self.root)
        try:
            closure._validate_retained_readable(reader, prefix, expected,
                                                {"readable_support": self.build.readable_support}, output)
            reader.recheck()
        finally:
            reader.close()

    def test_real_helpers_reject_redirected_diagnostic_slot_and_changed_bytes(self):
        metadata = {SELECTION: self.selection, **self.ctx.readable_diagnostics}
        changed = canonical.loads(self.selection)
        changed["diagnostic_inputs"][0]["slot_id"] = "other-slot"
        with self.assertRaises(checker.EdgeFailure):
            checker.readable_candidate_metadata(canonical.dumps(changed), metadata.__getitem__)
        metadata[self.diagnostic_path] = b"changed diagnostic"
        with self.assertRaises(checker.EdgeFailure):
            checker.readable_candidate_metadata(self.selection, metadata.__getitem__)
        files = {**self.build.readable_artifacts, self.diagnostic_path: b"changed diagnostic"}
        with self.assertRaises(checker.EdgeFailure):
            checker.readable_artifact_refs(self.build.readable_support, files.__getitem__)

    def test_real_manifest_cannot_omit_frozen_metadata_or_goal_inventory(self):
        for omitted in (SELECTION, self.diagnostic_path, "readable/base-goal.lean", "readable/selected-goal.lean"):
            with self.subTest(omitted=omitted):
                files = dict(self.build.readable_artifacts)
                manifest = canonical.loads(files[MANIFEST])
                manifest["artifacts"] = [row for row in manifest["artifacts"] if row["artifact"]["path"] != omitted]
                files[MANIFEST] = canonical.dumps(manifest)
                descriptor = {**self.build.readable_support, "manifest": {
                    "path": MANIFEST, "sha256": canonical.digest(files[MANIFEST])}}
                with self.assertRaises(checker.EdgeFailure):
                    checker.readable_artifact_refs(descriptor, files.__getitem__)

    def test_real_base_manifest_cannot_rebind_goal_bytes_without_frozen_goal_hash(self):
        for path in ("readable/base-goal.lean", "readable/selected-goal.lean"):
            with self.subTest(path=path):
                files = {**self.build.readable_artifacts, path: b"different goal bytes"}
                manifest = canonical.loads(files[MANIFEST])
                for row in manifest["artifacts"]:
                    if row["artifact"]["path"] == path:
                        row["artifact"] = readable_support.ref(path, files[path])
                files[MANIFEST] = canonical.dumps(manifest)
                descriptor = {**self.build.readable_support, "manifest": {
                    "path": MANIFEST, "sha256": canonical.digest(files[MANIFEST])}}
                with self.assertRaises(checker.EdgeFailure):
                    checker.readable_artifact_refs(descriptor, files.__getitem__)


if __name__ == "__main__":
    unittest.main()
