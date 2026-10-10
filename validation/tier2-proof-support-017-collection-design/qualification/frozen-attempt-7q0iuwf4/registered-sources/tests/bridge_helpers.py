"""Synthetic, structurally valid bridge packages for schema/envelope tests.

Every digest identifies real fixture bytes, but the acceptance/proof/evidence metadata below
is fabricated test data. A package passing these shape/binding checks is NOT a Lean proof;
the runtime must still refuse semantic acceptance without a registered relation checker.
"""

from __future__ import annotations

from pathlib import Path

from verislop import canonical

PLAN_PATH = "plan.json"
ARTIFACTS_PATH = "artifacts.json"
CERTIFICATE_PATH = "edge.json"
CHECKER_ID = "verislop.bridge-envelope-checker"
CLAIM_ID = "BRIDGE:O17:equivalence@1"


def write_json(root: Path, path: str, value: dict) -> bytes:
    data = canonical.dumps(value)
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return data


def semantic_edge_root(plan_hash: str, artifacts_hash: str, edge: dict) -> str:
    return canonical.digest_json({
        "format": "verislop.semantic-edge-root/0.1",
        "plan_hash": plan_hash, "artifacts_hash": artifacts_hash, "edge": edge,
    })


def make_bridge_fixture(root: Path) -> tuple[dict, dict, dict]:
    """Write plan.json, artifacts.json, edge.json plus referenced files; return their objects."""
    root.mkdir(parents=True, exist_ok=True)
    files: dict[str, tuple[str, str, str, bytes]] = {}

    def artifact(slot: str, role: str, node: str, path: str, data: bytes) -> str:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files[slot] = role, node, path, data
        return canonical.digest(data)

    def jartifact(slot: str, role: str, node: str, path: str, value: dict) -> str:
        return artifact(slot, role, node, path, canonical.dumps(value))

    statement_hash = jartifact("statements", "statements", "contract", "artifacts/statements.json",
                               {"fixture_proposition": "output = input + 1"})
    environment_hash = jartifact("environment_export", "environment_export", "contract", "artifacts/environment.json",
                                 {"fixture": "synthetic accepted environment"})
    contract_root = canonical.digest(b"synthetic-contract-inputs")
    reference_hash = artifact("contract_model", "model", "contract", "artifacts/Reference.lean",
                              b"-- Synthetic reference model, not accepted by Lean.\n")
    source_model_hash = artifact("source_model", "model", "source", "artifacts/SourceSemantics.lean",
                                 b"-- Synthetic source semantics, not accepted by Lean.\n")
    profile_hash = jartifact("contract_profile", "profile", "contract", "artifacts/contract-profile.json",
                             {"id": "fixture-contract/0.1", "numeric_semantics": "mathematical Nat"})
    source_profile_hash = jartifact("source_profile", "profile", "source", "artifacts/source-profile.json",
                                    {"id": "fixture-source/0.1", "effects": "none"})
    jartifact("source", "source", "source", "artifacts/program.vscore.json",
              {"format": "fixture-source/0.1", "body": "input + 1"})
    relation_hash = artifact("relation", "relation", "source", "artifacts/Relation.lean",
                             b"-- Synthetic extensional-equivalence relation.\n")
    module_hash = artifact("proof_module", "proof_module", "source", "artifacts/Proof.olean",
                           b"Synthetic fixture bytes; deliberately not a checked Lean module.\n")
    inventory = {
        "schema_version": "0.1", "format": "verislop.bridge-proof-inventory/0.1",
        "module_slot": "proof_module", "module_hash": module_hash,
        "theorems": [{"symbol": "Fixture.bridge", "type_hash": statement_hash, "axioms": []}],
    }
    inventory_hash = jartifact("proof_inventory", "proof_inventory", "source", "artifacts/proof-inventory.json", inventory)

    cert = {
        "schema_version": "0.1", "artifact_kind": "acceptance_certificate",
        "contract_input_root": contract_root, "gate": "accepted_and_proved",
        "policy": {"id": "strict", "hash": canonical.digest(b"fixture-policy"), "allowed_axioms": []},
        "toolchain": {"pin": "leanprover/lean4:v4.34.1", "version": "4.34.1", "githash": "fixture-only",
                      "lean_binary_sha256": canonical.digest(b"fixture-toolchain")},
        "olean_closure": canonical.digest(b"fixture-import-closure"),
        "checkers": {"fixture-kernel": canonical.digest(b"fixture-checker")}, "sandbox": {},
        "artifacts": {
            "source": {"path": "artifacts/Reference.lean", "sha256": reference_hash},
            "olean": {"path": "artifacts/Proof.olean", "sha256": module_hash},
            "environment_export": {"path": "artifacts/environment.json", "sha256": environment_hash},
            "profile": {"path": "artifacts/contract-profile.json", "sha256": profile_hash},
            "statements": {"path": "artifacts/statements.json", "sha256": statement_hash},
        },
        "obligations": {"O17": {
            "revision": 1, "kind": "postcondition", "role": "guarantee", "representation": "contract_dsl",
            "lean_symbol": "Fixture.O17", "statement_hash": statement_hash, "typechecked": "PASS", "proved": "PASS",
            "axioms": [], "codes": [], "uses_proof": [], "witnesses": [],
        }},
        "diagnostics": [],
    }
    acceptance_hash = jartifact("acceptance_certificate", "acceptance_certificate", "contract", "artifacts/acceptance.json", cert)
    ir = {
        "schema_version": "0.1", "artifact_kind": "accepted_semantic_ir",
        "contract_input_root": contract_root, "accepted_environment_hash": environment_hash,
        "acceptance_certificate_ref": "artifacts/acceptance.json",
        "exporter_id": "fixture-reifier", "exporter_hash": canonical.digest(b"fixture-reifier"),
        "lean_toolchain": "leanprover/lean4:v4.34.1", "semantic_profile": "fixture-contract/0.1",
        "obligations": {"O17": {
            "id": "O17", "revision": 1, "kind": "postcondition", "role": "guarantee",
            "statement": "Synthetic fixture: successful output equals input plus one.", "required": True,
            "source_refs": [{"document_ref": "fixture-request.txt", "document_hash": canonical.digest(b"fixture-request"),
                             "start_byte": 0, "end_byte": 15, "origin": "explicit", "interpretation": "fixture only"}],
            "scope": ["restricted-source semantics"], "dependencies": [],
            "acceptance_criteria": ["exact source equivalence"],
            "formal": {
                "lean_symbol": "Fixture.O17", "representation": "contract_dsl", "formula_ref": "fixture-formula.json",
                "statement_hash": statement_hash, "semantic_closure_hash": canonical.digest(b"fixture-semantic-closure"),
                "hypotheses": [], "axioms": [], "reification_evidence_ref": "evidence:fixture-reification",
            },
        }},
    }
    ir_hash = jartifact("accepted_ir", "accepted_ir", "contract", "artifacts/accepted-ir.json", ir)
    contract_model = {"id": "contract_model", "sha256": reference_hash}
    source_model = {"id": "source_model", "sha256": source_model_hash}
    contract_profile = {"id": "contract_profile", "sha256": profile_hash}
    source_profile = {"id": "source_profile", "sha256": source_profile_hash}
    edge = {
        "edge_id": "reference-to-source", "claim_id": CLAIM_ID,
        "source_node": "contract", "target_node": "source",
        "model_refs": [contract_model, source_model], "profile_refs": [contract_profile, source_profile],
        "relation": {"id": "relation", "sha256": relation_hash}, "expected_proposition_hash": statement_hash,
    }
    plan = {
        "schema_version": "0.1", "format": "verislop.bridge-plan/0.1", "bridge_id": "fixture-bridge",
        "tier": 2, "endpoint": "restricted_source", "accepted_ir": ir_hash, "acceptance_certificate": acceptance_hash,
        "nodes": [
            {"node_id": "contract", "kind": "accepted_contract",
             "artifact_slots": sorted(slot for slot, (_, node, _, _) in files.items() if node == "contract"),
             "model_ref": contract_model, "profile_ref": contract_profile},
            {"node_id": "source", "kind": "restricted_source",
             "artifact_slots": sorted(slot for slot, (_, node, _, _) in files.items() if node == "source"),
             "model_ref": source_model, "profile_ref": source_profile},
        ],
        "artifact_slots": [{"slot_id": slot, "role": role, "node_id": node}
                           for slot, (role, node, _, _) in sorted(files.items())],
        "claims": [{"claim_id": CLAIM_ID, "verifier_id": CHECKER_ID, "root_kind": "semantic_edge",
                    "result_predicate": "bridge-semantic-edge/0.1", "premises": []}],
        "obligations": [{"id": "O17", "revision": 1, "accepted_statement_hash": statement_hash, "required_claims": [CLAIM_ID]}],
        "edges": [edge], "reproducible_slots": ["source", "proof_inventory"],
        "declared_trust": [{"id": "fixture-checker", "kind": "checker", "description": "Synthetic metadata only; no proof checker ran."}],
    }
    plan_hash = canonical.digest(write_json(root, PLAN_PATH, plan))
    manifest = {
        "schema_version": "0.1", "format": "verislop.bridge-artifacts/0.1", "bridge_id": plan["bridge_id"],
        "plan_hash": plan_hash,
        "artifacts": [{"slot_id": slot, "role": role, "path": path, "size": len(data), "sha256": canonical.digest(data)}
                      for slot, (role, _, path, data) in sorted(files.items())],
    }
    artifacts_hash = canonical.digest(write_json(root, ARTIFACTS_PATH, manifest))
    input_root = semantic_edge_root(plan_hash, artifacts_hash, edge)
    # These are deliberately forged, fully hash-consistent evidence records. The
    # negative semantic-acceptance tests must not turn matching metadata into a proof.
    from verislop.verifiers import VERIFIERS, verifier_hash
    checker_hash = verifier_hash(CHECKER_ID) if CHECKER_ID in VERIFIERS else canonical.digest(b"unregistered-fixture-checker")
    raw_path = "evidence/raw/fixture.json"
    raw = {
        "claim_id": CLAIM_ID, "sequence": 1, "recorded_at": "2026-10-06T00:00:00Z",
        "edge_id": edge["edge_id"], "plan_hash": plan_hash, "artifacts_hash": artifacts_hash,
        "binding_root": "semantic_edge",
        "result_predicate": "bridge-semantic-edge/0.1", "proposition_hash": statement_hash,
        "proof_inventory_hash": inventory_hash, "proof_module_hash": module_hash, "proof_symbol": "Fixture.bridge",
    }
    raw_hash = canonical.digest(write_json(root, raw_path, raw))
    evidence_body = {
        "schema_version": "0.1", "closure_id": "fixture-only", "claim_id": CLAIM_ID,
        "input_root_hash": input_root, "verifier_id": CHECKER_ID, "verifier_hash": checker_hash,
        "execution_environment": {"fixture": "synthetic; no checker executed"}, "invocation": ["fixture-only"],
        "raw_result_ref": raw_path, "raw_result_hash": raw_hash, "exit_code": 0, "status": "PASS",
        "scope": ["synthetic metadata; not proof"], "trusted_dependencies": [],
    }
    evidence_id = "ev-" + canonical.sha256_hex(canonical.dumps(evidence_body))[:32]
    evidence_path = f"evidence/{evidence_id}.json"
    evidence_hash = canonical.digest(write_json(root, evidence_path, {"evidence_id": evidence_id, **evidence_body}))
    certificate = {
        "schema_version": "0.1", "format": "verislop.semantic-edge-certificate/0.1",
        "certificate_id": "fixture-edge-certificate", "bridge_id": plan["bridge_id"],
        "plan_hash": plan_hash, "artifacts_hash": artifacts_hash,
        "edge_id": edge["edge_id"], "claim_id": CLAIM_ID, "source_node": "contract", "target_node": "source",
        "model_refs": edge["model_refs"], "profile_refs": edge["profile_refs"], "relation": edge["relation"],
        "proposition_hash": statement_hash, "premise_claims": [],
        "checker": {"verifier_id": CHECKER_ID, "verifier_hash": checker_hash},
        "proof": {"module_slot": "proof_module", "symbol": "Fixture.bridge", "type_hash": statement_hash,
                  "inventory_slot": "proof_inventory"},
        "evidence": {"path": evidence_path, "sha256": evidence_hash},
    }
    write_json(root, CERTIFICATE_PATH, certificate)
    return plan, manifest, certificate
