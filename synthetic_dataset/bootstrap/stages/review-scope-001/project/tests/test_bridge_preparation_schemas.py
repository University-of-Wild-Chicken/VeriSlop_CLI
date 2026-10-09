"""Preparation proposals cannot supply accepted identities or verification outcomes.

The output-shaped fixture below is synthetic; schema validity does not establish
that a supervisor executed an import or checker. Runtime tests cover provenance.
"""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from verislop import canonical, schemas


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "bridge-proposal"
PROPOSAL_SCHEMA = "urn:verislop:schema:bridge-proposal:0.1"
CERTIFICATE_SCHEMA = "urn:verislop:schema:bridge-preparation-certificate:0.1"


def proposal_fixture() -> dict:
    return canonical.load_file(EXAMPLE / "proposal.json")


def preparation_certificate_fixture() -> dict:
    """An output-shaped record, explicitly not evidence of a real preparation."""
    digest = lambda label: canonical.digest(label.encode())
    return {
        "schema_version": "0.1", "format": "verislop.bridge-preparation-certificate/0.1",
        "bridge_id": "bounded-increment-metadata",
        "plan_hash": digest("synthetic plan"), "artifacts_hash": digest("synthetic manifest"),
        "accepted_ir_hash": digest("synthetic IR"),
        "acceptance_certificate_hash": digest("synthetic acceptance certificate"),
        "checker": {"verifier_id": "verislop.bridge-envelope-checker", "verifier_hash": digest("synthetic checker")},
        "evidence": {"path": "evidence/ev-fixture.json", "sha256": digest("synthetic evidence")},
        "contract_import": {
            "source_contract_root": digest("synthetic source contract root"),
            "source_ir_hash": digest("synthetic source IR"),
            "source_certificate_hash": digest("synthetic source certificate"),
            "receipt_sha256": digest("synthetic import receipt"),
        },
        "pending_semantic_claims": ["BRIDGE:bounded-increment:refinement"],
        "structural_acceptance": True, "semantic_acceptance": False,
        "assigns_end_to_end_verified": False,
    }


class BridgePreparationSchemas(unittest.TestCase):
    def setUp(self):
        self.proposal = proposal_fixture()
        self.certificate = preparation_certificate_fixture()

    def assert_valid(self, schema, value):
        self.assertEqual(schemas.registry().validate(value, schema), [])

    def assert_invalid(self, schema, value):
        self.assertTrue(schemas.registry().validate(value, schema), (schema, value))

    def test_example_and_output_shape_validate(self):
        self.assert_valid(PROPOSAL_SCHEMA, self.proposal)
        self.assert_valid(CERTIFICATE_SCHEMA, self.certificate)

    def test_example_has_real_candidate_files_and_unchecked_goal_bytes(self):
        by_slot = {item["slot_id"]: item for item in self.proposal["artifacts"]}
        for item in by_slot.values():
            path = EXAMPLE / item["path"]
            self.assertTrue(path.is_file())
            self.assertFalse(path.is_symlink())
            self.assertGreater(path.stat().st_size, 0)
        goal = EXAMPLE / by_slot["candidate-goal"]["path"]
        self.assertEqual(self.proposal["edges"][0]["expected_proposition_hash"], canonical.digest_file(goal))
        self.assertIn("not a Lean proposition or a proof", goal.read_text())

    def test_example_covers_only_actual_implementation_guarantees(self):
        draft = canonical.load_file(EXAMPLE.parent / "draft.json")
        guarantees = {r["id"] for values in draft.values() if isinstance(values, list)
                      for r in values if isinstance(r, dict) and r.get("role") == "guarantee" and r.get("required")}
        self.assertEqual(guarantees, {"E1", "I2", "O17"})
        self.assertEqual({item["id"] for item in self.proposal["obligations"]}, guarantees)
        self.assertNotIn("W1", {item["id"] for item in self.proposal["obligations"]})

    def test_exact_versions_and_all_required_top_level_fields(self):
        for schema, original in ((PROPOSAL_SCHEMA, self.proposal), (CERTIFICATE_SCHEMA, self.certificate)):
            for key in original:
                with self.subTest(schema=schema, missing=key):
                    changed = copy.deepcopy(original)
                    del changed[key]
                    self.assert_invalid(schema, changed)
            self.assert_invalid(schema, {**original, "schema_version": "0.2"})
            self.assert_invalid(schema, {**original, "format": original["format"].replace("/0.1", "/0.2")})

    def test_tier_endpoint_compatibility_is_enforced(self):
        pairs = {2: {"restricted_source"}, 3: {"proof_bearing_source", "extracted_language"},
                 4: {"machine_code_region", "native_binary"}}
        for tier, admitted in pairs.items():
            for endpoint in set().union(*pairs.values()):
                changed = {**self.proposal, "tier": tier, "endpoint": endpoint}
                with self.subTest(tier=tier, endpoint=endpoint):
                    (self.assert_valid if endpoint in admitted else self.assert_invalid)(PROPOSAL_SCHEMA, changed)
        for tier in (0, 1, 5, True, "2", 2.0):
            self.assert_invalid(PROPOSAL_SCHEMA, {**self.proposal, "tier": tier})

    def test_proposal_cannot_inject_supervisor_derived_fields(self):
        for key in ("accepted_ir", "acceptance_certificate", "claims", "checker", "status", "lifecycle", "success"):
            self.assert_invalid(PROPOSAL_SCHEMA, {**self.proposal, key: "untrusted"})
        fields = {
            "artifacts": ("sha256", "size", "status"),
            "obligations": ("revision", "accepted_statement_hash", "state"),
            "edges": ("verifier_id", "verifier_hash", "root_kind", "result_predicate", "semantic_acceptance"),
            "nodes": ("status", "proved"),
        }
        for parent, names in fields.items():
            for name in names:
                with self.subTest(parent=parent, name=name):
                    changed = copy.deepcopy(self.proposal)
                    changed[parent][0][name] = "untrusted"
                    self.assert_invalid(PROPOSAL_SCHEMA, changed)

    def test_reserved_contract_identity_cannot_be_supplied(self):
        mutations = [
            ("nodes", "node_id", "accepted-contract"), ("nodes", "kind", "accepted_contract"),
            ("artifacts", "node_id", "accepted-contract"),
            ("artifacts", "slot_id", "contract-model"), ("artifacts", "slot_id", "contract-profile"),
            ("artifacts", "role", "accepted_ir"), ("artifacts", "role", "acceptance_certificate"),
            ("artifacts", "role", "contract_import"),
        ]
        for parent, key, value in mutations:
            with self.subTest(parent=parent, key=key, value=value):
                changed = copy.deepcopy(self.proposal)
                changed[parent][0][key] = value
                self.assert_invalid(PROPOSAL_SCHEMA, changed)
        # Referencing the supervisor-injected source node is required and legal.
        self.assertEqual(self.proposal["edges"][0]["source_node"], "accepted-contract")

    def test_nested_fields_and_explicit_premises_are_required(self):
        for parent in ("nodes", "artifacts", "edges", "obligations", "declared_trust"):
            for key in self.proposal[parent][0]:
                changed = copy.deepcopy(self.proposal)
                del changed[parent][0][key]
                self.assert_invalid(PROPOSAL_SCHEMA, changed)
        for parent in ("checker", "evidence", "contract_import"):
            for key in self.certificate[parent]:
                changed = copy.deepcopy(self.certificate)
                del changed[parent][key]
                self.assert_invalid(CERTIFICATE_SCHEMA, changed)

    def test_nonempty_coverage_and_duplicate_lists(self):
        for field in ("nodes", "artifacts", "edges", "obligations", "reproducible_slots"):
            self.assert_invalid(PROPOSAL_SCHEMA, {**self.proposal, field: []})
            original = self.proposal[field]
            self.assert_invalid(PROPOSAL_SCHEMA, {**self.proposal, field: [original[0], original[0]]})
        changed = copy.deepcopy(self.proposal)
        changed["obligations"][0]["required_claims"] = []
        self.assert_invalid(PROPOSAL_SCHEMA, changed)
        changed = copy.deepcopy(self.proposal)
        changed["edges"][0]["premises"] = ["CLAIM:one", "CLAIM:one"]
        self.assert_invalid(PROPOSAL_SCHEMA, changed)
        self.assert_invalid(CERTIFICATE_SCHEMA, {**self.certificate, "pending_semantic_claims": []})
        pending = self.certificate["pending_semantic_claims"][0]
        self.assert_invalid(CERTIFICATE_SCHEMA, {**self.certificate, "pending_semantic_claims": [pending, pending]})

    def test_unsafe_artifact_and_evidence_paths_rejected(self):
        for path in ("", "/outside", "../outside", "./file", "dir/../file", "dir/./file", "dir//file",
                     "dir/", "dir\\file", "C:/file", "https://host/file", "file\n", "file\0"):
            with self.subTest(path=repr(path)):
                proposal = copy.deepcopy(self.proposal)
                proposal["artifacts"][0]["path"] = path
                self.assert_invalid(PROPOSAL_SCHEMA, proposal)
                certificate = copy.deepcopy(self.certificate)
                certificate["evidence"]["path"] = path
                self.assert_invalid(CERTIFICATE_SCHEMA, certificate)

    def test_malformed_goal_and_certificate_hashes_rejected(self):
        for digest in ("", "sha256:abc", "sha512:" + "0" * 64, "sha256:" + "A" * 64,
                       "sha256:" + "0" * 64 + "\n"):
            proposal = copy.deepcopy(self.proposal)
            proposal["edges"][0]["expected_proposition_hash"] = digest
            self.assert_invalid(PROPOSAL_SCHEMA, proposal)
            for key in ("plan_hash", "artifacts_hash", "accepted_ir_hash", "acceptance_certificate_hash"):
                self.assert_invalid(CERTIFICATE_SCHEMA, {**self.certificate, key: digest})
            for key in self.certificate["contract_import"]:
                certificate = copy.deepcopy(self.certificate)
                certificate["contract_import"][key] = digest
                self.assert_invalid(CERTIFICATE_SCHEMA, certificate)

    def test_preparation_output_cannot_claim_semantics_or_lifecycle(self):
        for key, values in (("structural_acceptance", (False, 1, "true")),
                            ("semantic_acceptance", (True, 0, "false")),
                            ("assigns_end_to_end_verified", (True, 0, "false"))):
            for value in values:
                self.assert_invalid(CERTIFICATE_SCHEMA, {**self.certificate, key: value})
        for key in ("state", "lifecycle", "proved", "accepted_semantic_certificates", "success"):
            self.assert_invalid(CERTIFICATE_SCHEMA, {**self.certificate, key: "PASS"})
        for parent in ("checker", "evidence", "contract_import"):
            changed = copy.deepcopy(self.certificate)
            changed[parent]["success"] = True
            self.assert_invalid(CERTIFICATE_SCHEMA, changed)


if __name__ == "__main__":
    unittest.main()
