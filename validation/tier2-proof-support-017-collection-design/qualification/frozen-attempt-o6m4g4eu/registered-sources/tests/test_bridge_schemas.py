"""Bridge envelope structure tests; valid shape does not establish semantic truth."""

from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bridge_helpers import ARTIFACTS_PATH, CERTIFICATE_PATH, PLAN_PATH, make_bridge_fixture
from verislop import canonical, schemas
from verislop.jsonschema_lite import Registry


class BridgeSchemas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-bridge-schema-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan, self.artifacts, self.certificate = make_bridge_fixture(self.root)

    def assert_valid(self, schema, value):
        self.assertEqual(schemas.validate(schema, value), [])

    def assert_invalid(self, schema, value):
        self.assertTrue(schemas.validate(schema, value), (schema, value))

    def test_fixtures_validate_with_lite_registry(self):
        for schema, value in (("bridge-plan", self.plan), ("bridge-artifacts", self.artifacts),
                              ("semantic-edge-certificate", self.certificate)):
            with self.subTest(schema=schema):
                self.assert_valid(schema, value)
        self.assert_valid("accepted-ir", canonical.load_file(self.root / "artifacts/accepted-ir.json"))
        self.assert_valid("acceptance-certificate", canonical.load_file(self.root / "artifacts/acceptance.json"))
        self.assert_valid("evidence", canonical.load_file(self.root / self.certificate["evidence"]["path"]))

    def test_fixtures_bind_real_bytes_not_placeholder_hashes(self):
        self.assertEqual(self.artifacts["plan_hash"], canonical.digest_file(self.root / PLAN_PATH))
        self.assertEqual(self.certificate["plan_hash"], canonical.digest_file(self.root / PLAN_PATH))
        self.assertEqual(self.certificate["artifacts_hash"], canonical.digest_file(self.root / ARTIFACTS_PATH))
        for entry in self.artifacts["artifacts"]:
            with self.subTest(slot=entry["slot_id"]):
                data = (self.root / entry["path"]).read_bytes()
                self.assertEqual(entry["sha256"], canonical.digest(data))
                self.assertEqual(entry["size"], len(data))
        self.assertEqual(canonical.load_file(self.root / CERTIFICATE_PATH), self.certificate)

    def test_all_tier_endpoint_pairs_and_cross_tier_rejection(self):
        admitted = {2: {"restricted_source"}, 3: {"proof_bearing_source", "extracted_language"},
                    4: {"machine_code_region", "native_binary"}}
        for tier in admitted:
            for endpoint in set().union(*admitted.values()):
                value = {**self.plan, "tier": tier, "endpoint": endpoint}
                with self.subTest(tier=tier, endpoint=endpoint):
                    (self.assert_valid if endpoint in admitted[tier] else self.assert_invalid)("bridge-plan", value)
        for tier in (0, 1, 5, True, "2", 2.0):
            with self.subTest(invalid_tier=tier):
                self.assert_invalid("bridge-plan", {**self.plan, "tier": tier})

    def test_every_top_level_field_is_required(self):
        for schema, original in (("bridge-plan", self.plan), ("bridge-artifacts", self.artifacts),
                                 ("semantic-edge-certificate", self.certificate)):
            for key in original:
                with self.subTest(schema=schema, missing=key):
                    value = copy.deepcopy(original)
                    del value[key]
                    self.assert_invalid(schema, value)

    def test_lifecycle_and_success_fields_rejected(self):
        for schema, original in (("bridge-plan", self.plan), ("bridge-artifacts", self.artifacts),
                                 ("semantic-edge-certificate", self.certificate)):
            for field in ("status", "state", "success", "proved", "lifecycle", "exit_code"):
                with self.subTest(schema=schema, field=field):
                    self.assert_invalid(schema, {**original, field: "PASS"})

    def test_unknown_nested_fields_rejected(self):
        plan_paths = [
            ("nodes", 0), ("nodes", 0, "model_ref"), ("nodes", 0, "profile_ref"),
            ("artifact_slots", 0), ("claims", 0), ("obligations", 0), ("edges", 0),
            ("edges", 0, "relation"), ("edges", 0, "model_refs", 0), ("declared_trust", 0),
        ]
        for schema, original, paths in (
            ("bridge-plan", self.plan, plan_paths),
            ("bridge-artifacts", self.artifacts, [("artifacts", 0)]),
            ("semantic-edge-certificate", self.certificate, [("proof",), ("checker",), ("evidence",), ("relation",)]),
        ):
            for path in paths:
                with self.subTest(schema=schema, path=path):
                    value = copy.deepcopy(original)
                    item = value
                    for part in path:
                        item = item[part]
                    item["success"] = True
                    self.assert_invalid(schema, value)

    def test_semantic_claim_requires_edge_root_and_reserved_predicate(self):
        for root_kind in ("bridge_plan", "bridge_artifacts", "contract_input_root", "unknown"):
            value = copy.deepcopy(self.plan)
            value["claims"][0]["root_kind"] = root_kind
            self.assert_invalid("bridge-plan", value)
        value = copy.deepcopy(self.plan)
        value["claims"][0]["result_predicate"] = "bridge-structural/0.1"
        self.assert_invalid("bridge-plan", value)
        for root_kind in ("bridge_plan", "bridge_artifacts"):
            value["claims"][0]["root_kind"] = root_kind
            self.assert_valid("bridge-plan", value)
        value["claims"][0]["result_predicate"] = "trust-the-agent"
        self.assert_invalid("bridge-plan", value)

    def test_explicit_premise_lists_and_coverage_are_required(self):
        value = copy.deepcopy(self.plan)
        del value["claims"][0]["premises"]
        self.assert_invalid("bridge-plan", value)
        value = copy.deepcopy(self.plan)
        value["obligations"][0]["required_claims"] = []
        self.assert_invalid("bridge-plan", value)
        value = copy.deepcopy(self.plan)
        value["claims"][0]["premises"] = ["P1", "P1"]
        self.assert_invalid("bridge-plan", value)
        value = copy.deepcopy(self.certificate)
        value["premise_claims"] = ["P1", "P1"]
        self.assert_invalid("semantic-edge-certificate", value)

    def test_invalid_revisions_sizes_and_malformed_hashes_rejected(self):
        for revision in (0, -1, True, "1"):
            value = copy.deepcopy(self.plan)
            value["obligations"][0]["revision"] = revision
            self.assert_invalid("bridge-plan", value)
        for size in (-1, True, "1", 1.5):
            value = copy.deepcopy(self.artifacts)
            value["artifacts"][0]["size"] = size
            self.assert_invalid("bridge-artifacts", value)
        for digest in ("", "sha256:abc", "sha512:" + "0" * 64, "sha256:" + "G" * 64,
                       "sha256:" + "0" * 64 + "\n"):
            self.assert_invalid("bridge-plan", {**self.plan, "accepted_ir": digest})
            self.assert_invalid("semantic-edge-certificate", {**self.certificate, "proposition_hash": digest})

    def test_unsafe_artifact_and_evidence_paths_rejected(self):
        invalid_paths = ("", "/outside", "../outside", "./file", "dir/../file", "dir/./file",
                         "dir//file", "dir/", "dir\\file", "C:/file", "https://host/file", "file\n", "file\0")
        for path in invalid_paths:
            with self.subTest(path=repr(path)):
                artifacts = copy.deepcopy(self.artifacts)
                artifacts["artifacts"][0]["path"] = path
                self.assert_invalid("bridge-artifacts", artifacts)
                certificate = copy.deepcopy(self.certificate)
                certificate["evidence"]["path"] = path
                self.assert_invalid("semantic-edge-certificate", certificate)

    def test_missing_exact_edge_identity_or_proof_binding_rejected(self):
        for parent in ("proof", "checker", "evidence"):
            for key in self.certificate[parent]:
                with self.subTest(parent=parent, key=key):
                    value = copy.deepcopy(self.certificate)
                    del value[parent][key]
                    self.assert_invalid("semantic-edge-certificate", value)
        for key in self.plan["edges"][0]:
            value = copy.deepcopy(self.plan)
            del value["edges"][0][key]
            self.assert_invalid("bridge-plan", value)

    def test_proof_inventory_definition_is_closed_and_validates(self):
        reg = Registry()
        for path in schemas.schema_dir().glob("*.schema.json"):
            reg.add(canonical.load_file(path))
        inventory_id = "urn:verislop:test:bridge-proof-inventory"
        reg.add({"$id": inventory_id, "$ref": "urn:verislop:schema:semantic-edge-certificate:0.1#/$defs/proof_inventory"})
        inventory = canonical.load_file(self.root / "artifacts/proof-inventory.json")
        self.assertEqual(reg.validate(inventory, inventory_id), [])
        for field in ("success", "state", "proved"):
            self.assertTrue(reg.validate({**inventory, field: True}, inventory_id))
        value = copy.deepcopy(inventory)
        value["theorems"][0]["status"] = "PROVED"
        self.assertTrue(reg.validate(value, inventory_id))
        value = copy.deepcopy(inventory)
        del value["theorems"][0]["type_hash"]
        self.assertTrue(reg.validate(value, inventory_id))

    def test_exact_versions_required(self):
        for schema, original in (("bridge-plan", self.plan), ("bridge-artifacts", self.artifacts),
                                 ("semantic-edge-certificate", self.certificate)):
            self.assert_invalid(schema, {**original, "schema_version": "0.2"})
            self.assert_invalid(schema, {**original, "format": original["format"].replace("/0.1", "/0.2")})


if __name__ == "__main__":
    unittest.main()
