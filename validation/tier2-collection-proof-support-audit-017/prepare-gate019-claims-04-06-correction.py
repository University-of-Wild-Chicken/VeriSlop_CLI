"""Correct representation-only reader comparisons against frozen production rules."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from datetime import datetime, timezone
import json
import hashlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from verislop import canonical
from verislop.exprjson import canon, name_str, semantic_refs

AUDIT = Path(__file__).resolve().parent
CAPTURE = ROOT / "validation/tier2-proof-support-017-collection-design/qualification/frozen-attempt-egfasmab"
ANNEX = CAPTURE.parent / "retained-check-c7wcbpdr"
GATE = ROOT / "validation/tier2-native-boundary-gate-019"
PKG = CAPTURE / "package"
EDGE = next((PKG / "bridges/implementation/semantic").iterdir())
sha = lambda p: "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda p: json.loads(p.read_bytes())
draft_path = AUDIT / "gate019-prepared-observations-04-06.json"
draft = load(draft_path)
manifest = load(GATE / "qualification-inputs.json")
assert sha(draft_path) == "sha256:5b3d6ccffd2091c3601f4a8c84a5ff10748b7534f505fa53f3af8002112889ca"
assert len(draft["new_concrete_or_reader_gaps"]) == 12
assert all(sha(ROOT / n) == h for n, h in draft["evidence_bindings"].items())
assert all(sha(ROOT / n) == h for n, h in manifest["source_hashes"].items())
assert all(sha(CAPTURE / n) == h for n, h in load(CAPTURE / "capture.json")["files"].items())

def frontend_bool_eq_to_accepted_decide(value):
    # This is exactly the frozen frontend bool_eq rule: decide of propositional Eq.
    # Preserve every operand, binder, nominal sort and all other fields.
    if isinstance(value, list):
        return [frontend_bool_eq_to_accepted_decide(x) for x in value]
    if not isinstance(value, dict):
        return value
    if value.get("tag") == "bool_eq":
        assert set(value) == {"tag", "left", "right"}
        return {"tag": "decide", "formula": {"tag": "eq",
                "left": frontend_bool_eq_to_accepted_decide(value["left"]),
                "right": frontend_bool_eq_to_accepted_decide(value["right"])}}
    return {k: frontend_bool_eq_to_accepted_decide(v) for k, v in value.items()}

corrections = []
accepted = load(PKG / "accepted/accepted-ir.json")
response = load(PKG / "formalizer-response.json")
for oid, theorem in [("G.filter", "law_filter"), ("G:fold", "law_fold"), ("G-equality", "law_equality")]:
    ref = accepted["obligations"][oid]["formal"]["formula_ref"]
    actual = load(PKG / "accepted/expressions" / (ref.rsplit("@", 1)[1][7:] + ".json"))["formula"]
    expected = frontend_bool_eq_to_accepted_decide(response["theorems"][theorem]["formula"])
    assert actual == expected
    corrections.append({"replaces_check": oid + " reconstructed accepted formula equals frozen frontend",
                        "correction": "Compare exact accepted canonical decide(Eq) representation of frozen bool_eq syntax; preserve all operands/binders/sorts.",
                        "actual_canonical_formula_sha256": canonical.digest_json(actual),
                        "expected_canonical_formula_sha256": canonical.digest_json(expected), "match": True})
exports = load(EDGE / "readable/kernel-export.json")
inventory = load(EDGE / "readable/compiled-inventory.json")
for row in inventory:
    name = row["run_equals_theorem"]
    definition = name.replace(".runEquals_", ".RunEquals_")
    assert semantic_refs(exports[name]) == {definition}
    actual = canonical.digest_json(canon(exports[definition]["value"], []))
    assert actual == row["run_equals_type_hash"]
    corrections.append({"replaces_check": name + " exact type hash",
                        "correction": "The actual theorem type is the exact named RunEquals proposition; compiled inventory binds canonical exported value of that proposition definition, as specified by frozen production.",
                        "theorem_type_constant": definition, "actual_sha256": actual,
                        "expected_sha256": row["run_equals_type_hash"], "match": True})
replacement_names = {x["replaces_check"] for x in corrections}
assert replacement_names == {x["check"] for x in draft["new_concrete_or_reader_gaps"]}
unchanged_checks = [x for x in draft["comparisons"] if x["check"] not in replacement_names]
assert len(unchanged_checks) == 336 and all(x["match"] for x in unchanged_checks)
equalities = load(EDGE / "readable/equalities.json")
assert all(canonical.digest_json(canon(exports[x["name"]]["type"], [])) == x["type_hash"] for x in equalities)
records = [load(p) for p in sorted((EDGE / "readable/kernel-records").glob("*.json"))]
assert len(records) == len(exports) == 105
assert all(row == exports[name_str(row["name"])] for row in records)
assert all(row["safety"] == "safe" and not row["unresolved_constants"] for row in records)
bound_sources = ["verislop/formal_frontend.py", "verislop/bridges/vscore3_readable_support.py", "verislop/exprjson.py"]
assert all(sha(ROOT / n) == manifest["source_hashes"][n] for n in bound_sources)
report = {"format": "verislop.collection-support-pending-preparation-reader-correction/1",
          "audit_id": "tier2-collection-proof-support-audit-017", "qualification_attempt": "gate019",
          "prepared_at_utc": datetime.now(timezone.utc).isoformat(), "overall": "PENDING",
          "qualification_authority": False, "claims_discharged": [],
          "claim_status": {"AUD017-04-GENERATED-PACKAGE": "UNDISCHARGED", "AUD017-05-SEMANTIC-BRIDGE": "UNDISCHARGED", "AUD017-06-CLOSURE-AND-PORTABILITY": "UNDISCHARGED"},
          "tests_executed_by_reviewer": 0, "lean_builds_by_reviewer": 0, "model_calls_by_reviewer": 0,
          "fixture_generation_by_reviewer": False, "gate_terminal_result_read": False,
          "initial_draft_path": draft_path.relative_to(ROOT).as_posix(), "initial_draft_sha256": sha(draft_path),
          "initial_reader_results_preserved": True, "reader_sha256": sha(Path(__file__)),
          "frozen_production_rule_bindings": {n: sha(ROOT / n) for n in bound_sources},
          "frontend_rule": "verislop/formal_frontend.py:333: bool_eq lowers to fixed Decidable.decide of operand equality.",
          "compiled_inventory_rule": "verislop/bridges/vscore3_readable_support.py:174: run_equals_type_hash hashes canon(exported RunEquals proposition definition value, []).",
          "corrections": corrections, "unchanged_matching_comparisons": 336,
          "corrected_matching_comparisons": 12, "total_prepared_comparisons": 348,
          "all_corrected_prepared_comparisons_match": True, "registered_acceptance_predicates_changed": False,
          "additional_existing_metadata_reconciliation": {"all37_actual_equalities_type_hashes_match_canonical_exports": True,
                                                         "all105_kernel_records_equal_actual_export_rows": True,
                                                         "all105_kernel_records_safe_no_unresolved_constants": True},
          "all1340_capture_hashes_and415_current_inputs_unchanged": True,
          "new_concrete_target_gaps": [],
          "limitations": ["This corrects representation errors in the read-only reader, not the target, evidence, controls or registered predicates.",
                          "The original348 draft and two failed reader process observations remain immutable.",
                          "All seven claims still require the completed98 gate, actual process receipt, final engineering provenance and complete finite audit.",
                          "Optional wrong-source ground replay remains UNRESOLVED_REPLAY_BOUNDARY/qualification false; actual universal wrong-source proof rejection remains separate."]}
out = AUDIT / "gate019-prepared-observations-04-06-correction-001.json"
with out.open("xb") as f:
    f.write(canonical.dumps(report))
out.chmod(0o444)
print(out.relative_to(ROOT).as_posix(), sha(out))
print("unchanged comparisons", 336, "corrected representations", 12, "all match", True, "status PENDING")
