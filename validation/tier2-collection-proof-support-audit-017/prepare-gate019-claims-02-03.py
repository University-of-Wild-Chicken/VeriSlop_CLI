"""Read-only preparation from the designated current gate019 catalog/name evidence.

This reader compiles nothing, executes no qualification suite, and assigns no
claim PASS or final closure state. Its output remains PENDING until the whole
registered gate and fresh collection package are available for the final audit.
"""
import sys
sys.dont_write_bytecode = True
from datetime import datetime, timezone
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from verislop import canonical, leanbridge, verifiers
from verislop.exprjson import name_str, parse_name
from verislop.targets import vscore3_target as target

AUDIT = Path(__file__).resolve().parent
GATE = ROOT / "validation/tier2-native-boundary-gate-019"
CATALOG = GATE / "actual-gate-evidence/catalog"
NAMES = ROOT / "validation/tier2-proof-support-017-name-design/kernel-names-dxoxuqbp"
EXPECTED_FREEZE = "sha256:b2879c5b19be1d63a72dacfa472839eb5ea5900ad572fbd8fa4a9bcfccc01de4"
EXPECTED_DRIVER = "sha256:a6e8cac21eadd002fa57a9c1d722fc836246b21a753d1fe78ba657f8cf53e1e7"

comparisons = []
evidence_hashes = {}


def compare(condition, description):
    comparisons.append({"comparison": description, "matches": bool(condition)})


def load(path):
    evidence_hashes[path.relative_to(ROOT).as_posix()] = canonical.digest_file(path)
    return canonical.load_file(path)


def parts_identity(directory, module, *, flat=False):
    stem = module if flat else leanbridge.module_relpath(module)
    parts = {suffix: canonical.digest_file(directory / (stem + suffix))
             for suffix in leanbridge.MODULE_SUFFIXES
             if (directory / (stem + suffix)).is_file()}
    return canonical.digest_json(parts)


plan = load(AUDIT / "plan.json")
qualification = load(GATE / "qualification-inputs.json")
freeze = load(GATE / "source-freeze.json")
invocation = load(GATE / "invocation.json")
preregistration = load(AUDIT / "gate019-driver-preregistration.json")
compare(evidence_hashes[(GATE / "qualification-inputs.json").relative_to(ROOT).as_posix()] == EXPECTED_FREEZE,
        "The exact root-designated gate019 input manifest is used")
compare(invocation["qualification_inputs_hash"] == EXPECTED_FREEZE,
        "Registered invocation binds the root-designated input manifest")
compare(invocation["driver_script_sha256"] == EXPECTED_DRIVER == canonical.digest_file(GATE / "gate.py")
        == preregistration["driver_script_sha256"], "Invocation, preregistration and current driver identities match")
compare(qualification["engineering_freeze_hash"] == canonical.digest_file(GATE / "source-freeze.json"),
        "Qualified source-freeze bytes match the manifest engineering-freeze hash")
compare(canonical.digest_json(freeze["source_files"]) == freeze["source_root"]
        == qualification["source_root"] == invocation["source_root"], "Production source roots reconcile canonically")
input_mismatches = [path for path, sha in qualification["source_hashes"].items()
                    if not (ROOT / path).is_file() or canonical.digest_file(ROOT / path) != sha]
compare(not input_mismatches, "All 415 frozen verification input preimages match the current checkout")
compare(len(qualification["source_hashes"]) == 415 and len(freeze["source_files"]) == 241,
        "Exact current input and production inventory counts match the registered attempt")
required_registered = {"verislop/" + rel for spec in verifiers.VERIFIERS.values()
                       for rel in verifiers.CORE + spec["sources"]}
required_registered |= {"schemas/" + rel for spec in verifiers.VERIFIERS.values() for rel in spec["schemas"]}
compare(required_registered <= qualification["source_hashes"].keys(),
        "Current registered production and schema dependencies are covered by the frozen manifest")
compare(invocation["test_modules"] == preregistration["test_modules"],
        "Invocation retains all eight preregistered modules")
compare(canonical.digest_json(plan["claims"]) == preregistration["original_claims_sha256"],
        "All seven original claim records remain unchanged")

catalog = target.proof_support_catalog()
expected_names = ["VSCore3.ProofSupport." + name for name in plan["claims"][1]["names"]]
compare([r["name"] for r in catalog["lemmas"]] == expected_names,
        "Actual current authoring catalog contains exactly the eleven registered names")
transport_path = ROOT / "verislop/lean/VSCore3/Transport.lean"
compare(catalog["source_hash"] == canonical.digest_file(transport_path)
        == qualification["source_hashes"][transport_path.relative_to(ROOT).as_posix()],
        "Catalog binds exact current frozen transport source")
compare(not catalog["global_simp_rules"]
        and not re.search(r"@\[[^\]]*\bsimp\b|attribute\s+\[simp\]", transport_path.read_text()),
        "Catalog metadata and transport source introduce no global simp registrations")
inventories = load(CATALOG / "inventories.json")
expected_axioms = {
    "apply_ite": ["propext"], "apply_bool_ite": [], "ite_decide": ["propext"],
    "map_identity": ["Quot.sound", "propext"], "int_ofNat_eq_cast": [], "int_ofNat_add": [],
    "to_eq_iff": [], "decide_to_eq": ["propext"], "map_transport": ["propext"],
    "filter_transport": ["propext"], "foldl_transport": ["propext"],
}
catalog_rows = {}
catalog_controls = {}
for build in ("A", "B"):
    kernel = load(CATALOG / build / "kernel.json")
    compare(kernel["import"]["ok"] and kernel["replay"]["ok"], f"Catalog {build} actual kernel import/replay succeeds")
    compare(all(name[-1] == "_unsafe_rec" for name in kernel["replay"]["not_replayed_unsafe_or_partial"]),
            f"Catalog {build} replay skips only declared runtime compiler auxiliaries")
    rows = {name_str(c["name"]): c for c in kernel["constants"]}
    compare(sorted(n for n in rows if n.startswith("VSCore3.ProofSupport.")) == sorted(expected_names),
            f"Catalog {build} actual ProofSupport export inventory has exactly eleven declarations")
    actual_inventory = {module: parts_identity(CATALOG / build / "modules", module, flat=True)
                        for module in inventories[build]}
    compare(actual_inventory == inventories[build], f"Catalog {build} retained module parts match recorded deterministic inventory")
    catalog_rows[build] = []
    for index, advertised in enumerate(catalog["lemmas"]):
        name = advertised["name"]
        actual, alias = rows[name], rows[f"GenericProofSupport.signature_{index}"]
        short = name.rsplit(".", 1)[1]
        axioms = sorted(name_str(n) for n in actual["axioms"])
        compare(actual["kind"] == "theorem" and actual["safety"] == "safe"
                and actual["module"] == ["VSCore3", "Transport"] and not actual["unresolved_constants"],
                f"Catalog {build} {short} is an exact safe resolved kernel theorem in Transport")
        compare(target.same_expr(actual["type"], alias["type"])
                and actual["level_params"] == alias["level_params"]
                and name in {name_str(n) for n in alias["value_constants"]},
                f"Catalog {build} {short} actual type matches independently elaborated advertised signature")
        compare(axioms == expected_axioms[short], f"Catalog {build} {short} exact actual axiom closure matches preregistration")
        catalog_rows[build].append({"name": actual["name"], "kind": actual["kind"], "safety": actual["safety"],
            "module": actual["module"], "level_params": actual["level_params"], "axioms": actual["axioms"],
            "type_sha256": canonical.digest_json(actual["type"]), "theorem_body_exported": False,
            "value_constants": actual["value_constants"], "unresolved_constants": actual["unresolved_constants"]})
    for module in inventories[build]:
        compile_record = load(CATALOG / build / (module + ".compile.json"))
        compare(compile_record["returncode"] == 0 and "declaration uses `sorry`" not in compile_record["stdout"] + compile_record["stderr"],
                f"Catalog {build} {module} actual compilation succeeds without sorry")
        source = (CATALOG / "GenericProofSupport.lean").read_bytes() if module == "GenericProofSupport" else target.library_sources()[module]
        compare(compile_record["source_hash"] == canonical.digest(source), f"Catalog {build} {module} compiled source hash matches exact input")
    for control in ("BadUniversal", "BadCollectionAgreement"):
        rejected = load(CATALOG / build / (control + ".compile.json"))
        compare(rejected["returncode"] != 0 and "error:" in rejected["stdout"] + rejected["stderr"]
                and "declaration uses `sorry`" not in rejected["stdout"] + rejected["stderr"],
                f"Catalog {build} {control} is rejected with actual Lean diagnostics")
        catalog_controls[f"{build}/{control}"] = rejected
    for example in ("map_nat_to_int", "fold_nat_to_int"):
        actual = rows["GenericProofSupport." + example]
        compare(actual["kind"] == "theorem" and actual["safety"] == "safe" and not actual["unresolved_constants"],
                f"Catalog {build} {example} is a safe universal different-carrier instantiation")
compare(inventories["A"] == inventories["B"] and catalog_rows["A"] == catalog_rows["B"],
        "Catalog A/B deterministic module inventories and exact catalog type/axiom/dependency records agree")

names_manifest = load(NAMES / "manifest.json")
name_artifact_mismatches = [relative for relative, sha in names_manifest["artifacts"].items()
                           if not (NAMES / relative).is_file() or canonical.digest_file(NAMES / relative) != sha]
compare(not name_artifact_mismatches, "All 380 retained current name-fixture artifact hashes match their completed manifest")
for path in (NAMES / "inputs").rglob("*"):
    if not path.is_file():
        continue
    relative = path.relative_to(NAMES / "inputs").as_posix()
    production = "verislop/lean/" + relative[len("library/"):] if relative.startswith("library/") else relative
    compare(production in qualification["source_hashes"] and canonical.digest_file(path) == qualification["source_hashes"][production],
            "Name fixture copied input equals frozen current " + production)
spec = target.build_goal((NAMES / "fixtures/program.vscore.json").read_bytes(),
    load(NAMES / "fixtures/relation.json"), load(NAMES / "fixtures/profile.json"), load(NAMES / "fixtures/obligations.json"))
compare(spec.text.encode() == (NAMES / "fixtures/VeriSlopBridgeGoal.lean").read_bytes(),
        "Name fixture generated goal reconstructs exactly from its actual input fixtures")
compare(spec.expected == load(NAMES / "fixtures/expected.json"), "Name fixture expected statements reconstruct exactly")
name_observations = {}
for build in ("A", "B"):
    observation = load(NAMES / ("build-" + build) / "observation.json")
    kernel = load(NAMES / ("build-" + build) / "kernel-0.json")
    compare(kernel["import"]["ok"] and kernel["replay"]["ok"], f"Names {build} actual kernel import/replay succeeds")
    compare(all(r["ok"] and not r["errors"] and r["sorries"] == 0 for r in observation["compiles"].values()),
            f"Names {build} actual compilation inventory is successful without sorry")
    compare({module: parts_identity(NAMES / ("build-" + build) / "modules", module)
             for module in observation["modules"]} == observation["modules"], f"Names {build} module-part hashes match actual retained bytes")
    compare(canonical.digest_json(kernel["constants"]) == observation["export_digest"], f"Names {build} recorded export digest matches actual constants")
    rows = {name_str(c["name"]): c for c in kernel["constants"]}
    goals = {n: c for n, c in rows.items() if c.get("module") == [target.GOAL_MODULE]}
    compare(not target.statement_mismatches(spec, goals), f"Names {build} actual generated declaration statements match exact supervisor expectations")
    compare(canonical.dumps(target.reexport(spec, goals)["program"]) == spec.source_bytes,
            f"Names {build} kernel re-export reconstructs the exact delivered source AST")
    descriptor = load(NAMES / "certificate-descriptor.json")
    for row in descriptor["obligations"]:
        for field, prefix in (("transfer", "Transfer_"), ("transfer_theorem", "transfer_")):
            exact = [target.GOAL_MODULE, prefix + row["id"]]
            compare(parse_name(row[field]) == exact == goals[row[field]]["name"]
                    and name_str(exact) == row[field], f"Names {build} {row['id']} {field} has exact exported components and canonical spelling")
        theorem = goals[row["transfer_theorem"]]
        compare(theorem["kind"] == "theorem" and parse_name(row["accepted_theorem"]) in theorem["value_constants"],
                f"Names {build} {row['id']} actual transfer depends on the exact original theorem components")
    compare(descriptor["statement_identity"] == sorted(name_str(target.expected_decl_name(n)) for n in spec.expected)
            and all(parse_name(n) == goals[n]["name"] for n in descriptor["statement_identity"]),
            f"Names {build} certificate statement_identity equals actual expected exports")
    name_observations[build] = observation
compare(name_observations["A"] == name_observations["B"], "Names A/B deterministic observations agree")
name_controls = {}
for case in ("missing", "near_name", "dependency", "namespace_dependency", "wrong_kind", "statement"):
    directory = NAMES / "compiled-negatives" / case
    result = load(directory / "result.json")
    kernel = load(directory / "kernel-0.json")
    review = load(directory / "review/result.json")
    review_kernel = load(directory / "review/kernel-0.json")
    compare(kernel["import"]["ok"] and kernel["replay"]["ok"]
            and review_kernel["import"]["ok"] and review_kernel["replay"]["ok"],
            f"Names {case} negative uses actual kernel-replayed declarations in checker and concrete review")
    compare(result[0]["code"] == "STATEMENT_MISMATCH" and review["status"] == "UNSUPPORTED"
            and ("source goal differs" if case == "statement" else "original accepted theorem") in review["reason"],
            f"Names {case} actual checker and concrete review reject the exact required identity defect")
    name_controls[case] = {"checker_diagnostics": [{k: v for k, v in r.items() if k != "details"} for r in result], "review": review}
for index, oid in enumerate(("N-bump", "N.bump", "N:bump")):
    result = load(NAMES / f"probe-{index}/result.json")
    kernel = load(NAMES / f"probe-{index}/kernel-0.json")
    compare(result["obligation_id"] == oid and result["result"]["predicate"] is True
            and result["result"]["kernel_replay"] and kernel["import"]["ok"] and kernel["replay"]["ok"],
            f"Names concrete review positive {oid} binds an actual kernel-checked result")
readable_descriptor = load(NAMES / "readable/certificate-descriptor.json")
readable_kernel = load(NAMES / "readable/kernel-0.json")
readable_rows = {name_str(c["name"]): c for c in readable_kernel["constants"]}
reserved = [target.GOAL_MODULE, "Readable", "RunEquals_entry_0"]
compare(name_str(reserved) in readable_descriptor["statement_identity"]
        and readable_rows[name_str(reserved)]["name"] == reserved
        and name_str([target.GOAL_MODULE, "Transfer_N.bump"]) in readable_descriptor["statement_identity"],
        "Actual readable nested namespace stays distinct from literal dotted obligation leaves")

current_inputs_after = [path for path, sha in qualification["source_hashes"].items()
                        if not (ROOT / path).is_file() or canonical.digest_file(ROOT / path) != sha]
compare(not current_inputs_after, "Prepared read-only inspection changes none of the 415 frozen inputs")
catalog_artifact_hashes = {p.relative_to(CATALOG).as_posix(): canonical.digest_file(p)
                          for p in sorted(CATALOG.rglob("*")) if p.is_file()}
report = {
    "format": "verislop.collection-support-prepared-audit-observations/1",
    "audit_id": plan["audit_id"], "attempt_id": "gate019", "state": "PENDING",
    "qualification": False, "claim_discharge": False, "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
    "producer_sha256": canonical.digest_file(Path(__file__)),
    "prepared_claim_ids": ["AUD017-02-CATALOG", "AUD017-03-EXACT-NAMES"],
    "original_plan_sha256": canonical.digest_file(AUDIT / "plan.json"),
    "full_frozen_input_root": canonical.digest_json(qualification["source_hashes"]),
    "frozen_manifest_sha256": EXPECTED_FREEZE, "production_root": freeze["source_root"],
    "evidence_hashes": evidence_hashes, "comparisons": comparisons,
    "concrete_findings": [r for r in comparisons if not r["matches"]],
    "catalog": {"rows": catalog_rows, "actual_negative_diagnostics": catalog_controls,
        "artifact_hashes": catalog_artifact_hashes, "inventory": inventories,
        "warnings": "Independent signature wrapper compilation emits only unused named premise h linter warnings; actual safe theorem types retain the premise and match their independently elaborated signatures. No required claim is weakened by these warnings."},
    "names": {"root": NAMES.relative_to(ROOT).as_posix(), "manifest_sha256": canonical.digest_file(NAMES / "manifest.json"),
        "retained_artifact_count": len(names_manifest["artifacts"]), "artifact_mismatches": name_artifact_mismatches,
        "compiled_checker_and_review_negative_controls": name_controls, "observations": name_observations},
    "semantic_control_boundary": "A wrong-source optional ground replay reporting UNSUPPORTED/UNRESOLVED proves neither falsehood nor acceptance. The mandatory control remains actual semantic universal-proof/bridge rejection. Correct-package release and retained probes remain independently required.",
    "pending_required_evidence": ["whole gate019 actual completion/receipt and all 98 outcome counts", "final before/after frozen-input equality", "actual current engineering record and final complete seven-claim audit"],
    "interpretation": "These are prepared read-only comparisons from completed current catalog/name evidence. They assign no final claim PASS, closure state, qualification or native task authority. No incomplete collection package or task artifact was read."
}
destination = AUDIT / "gate019-prepared-observations-02-03.json"
if destination.exists():
    raise RuntimeError("Prepared observation is immutable; use a new artifact for a new preparation")
destination.write_bytes(canonical.dumps(report))
destination.chmod(0o444)
print({"path": destination.relative_to(ROOT).as_posix(), "sha256": canonical.digest_file(destination),
       "state": report["state"], "comparisons": len(comparisons), "concrete_findings": report["concrete_findings"]})
