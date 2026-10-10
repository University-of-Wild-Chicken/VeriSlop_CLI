"""Registered output/normalizer compatibility; no model or Lean execution."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from verislop import canonical, review_projection as projection
from verislop.bridges import vscore3_checker as checker
from verislop.bridges.check import _evidence
from verislop.bridges.manifest import InvalidPackage, PackageReader


class CompileProcessProjectionTests(unittest.TestCase):
    def publish(self, *, support=False):
        temp = tempfile.TemporaryDirectory(prefix="verislop-process-projection-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        inventory = {"Generic.Process": {"availability": "available", "record": {
            "format": "verislop.lean-compile-process/1", "elapsed_seconds": "1.25",
            "working_directory": "/generic/compile", "stdout": {"time": "must remain", "content_b64": ""}}}}
        build = checker.Build({}, {}, {checker.T.GOAL_MODULE: {".olean": b"generic goal module"},
                                      checker.T.PROOF_MODULE: {".olean": b"generic proof module"}},
                              canonical.digest(b"generic proposition"), {}, [], inventory)
        build.ir = {"program": {}, "signatures": [], "enums": [], "bindings": []}
        ctx = SimpleNamespace(bridge_id="generic", edge={"edge_id": "generic-edge"}, claim={"claim_id": "GENERIC"},
                              inputs={"source": ("source-slot", b"generic program")},
                              plan={"accepted_ir": {}, "acceptance_certificate": {}})
        spec = SimpleNamespace(text="generic goal", source_bytes=b"generic program")
        digest = canonical.digest(b"generic fixture binding")
        descriptor = {"bridge_id": "generic", "edge_id": "generic-edge", "plan_hash": digest,
                      "artifacts_hash": digest, "semantic_edge_root": digest, "template": checker.T.TEMPLATE,
                      "proposition_hash": build.proposition_hash, "theorem": {"symbol": "generic", "axioms": []},
                      "inputs": {}, "obligations": []}
        if support:
            descriptor["readable_support"] = {"fixture": "frozen source support", "time": "retain"}
        with patch.object(checker, "_schema"), patch.object(checker, "_semantic_descriptor", return_value=descriptor):
            files = checker.outputs(ctx, spec, build, build, "generic-run", root / "stage")
        publication = root / "publication"
        for name, data in files.items():
            path = publication / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        reader = PackageReader(publication)
        self.addCleanup(reader.close)
        cert = canonical.loads(files[checker.CERTIFICATE])
        ev = _evidence(reader, cert["evidence"])
        return ev, inventory

    def test_actual_output_raw_result_normalizes_and_retains_frozen_process_payload(self):
        evidence, inventory = self.publish()
        _, normalized = projection.normalize(evidence.record, evidence.result)
        self.assertEqual(normalized["raw"]["compile_process_evidence"], {
            "format": "verislop.vscore-compile-process-inventory/1", "builds": {"A": inventory, "B": inventory}})
        self.assertNotIn("recorded_at", normalized["raw"])
        self.assertNotIn("sequence", normalized["raw"])

    def test_legacy_and_closed_extensions_reject_unknown_producer_keys(self):
        evidence, _ = self.publish()
        legacy = {k: v for k, v in evidence.result.items() if k != "compile_process_evidence"}
        projection.normalize(evidence.record, legacy)
        extended = {**evidence.result, "readable_support": {"fixture": "preserved", "path": "semantic data"}}
        _, normalized = projection.normalize(evidence.record, extended)
        self.assertEqual(normalized["raw"]["readable_support"], extended["readable_support"])
        with self.assertRaises(InvalidPackage):
            projection.normalize(evidence.record, {**extended, "unregistered_field": 1})
        old_record = {**evidence.record, "verifier_id": "verislop.vscore-checker"}
        projection.normalize(old_record, legacy)
        with self.assertRaises(InvalidPackage):
            projection.normalize(old_record, evidence.result)

    def test_closed_build_output_extension_is_preserved_and_unknown_field_rejected(self):
        outputs = {name: None for name in projection.OUTPUT_FIELDS}
        support = {"descriptor": {"time": "semantic"}, "artifacts": {"readable/manifest.json": "fixture-digest"}}
        build = {"build": "A", "ok": True, "errors": [], "closure_root": "fixture-root", "producer": {},
                 "outputs": {**outputs, "readable_support": support}, "execution": {"wall_ms": 17}}
        metadata = []
        normalized = projection._builds([build], metadata)[0]
        self.assertEqual(normalized["outputs"]["readable_support"], support)
        self.assertNotIn("execution", normalized)
        projection._builds([{**build, "outputs": outputs}], [])
        with self.assertRaises(InvalidPackage):
            projection._builds([{**build, "outputs": {**build["outputs"], "unregistered_field": 0}}], [])
        self.assertEqual(projection.normalizer_registry()["output_alternatives"],
                         [sorted(fields) for fields in projection.OUTPUT_ALTERNATIVES])


if __name__ == "__main__":
    unittest.main()
