"""Read-only current-capture comparisons; no test, Lean, model or qualification run."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from datetime import datetime, timezone
import base64
import hashlib
import json
import stat

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from verislop import canonical
from verislop.exprjson import name_str, parse_name, semantic_refs

AUDIT = Path(__file__).resolve().parent
CAPTURE = ROOT / "validation/tier2-proof-support-017-collection-design/qualification/frozen-attempt-egfasmab"
ANNEX = CAPTURE.parent / "retained-check-c7wcbpdr"
GATE = ROOT / "validation/tier2-native-boundary-gate-019"
PKG = CAPTURE / "package"
EDGE = next((PKG / "bridges/implementation/semantic").iterdir())
checks = []
bindings = {}

def digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

def load(path):
    bindings[path.relative_to(ROOT).as_posix()] = digest(path)
    return json.loads(path.read_bytes())

def compact(value):
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, (dict, list)) and len(value) > 16:
        return {"count": len(value), "canonical_sha256": canonical.digest_json(value)}
    return value

def check(claim, label, actual, expected):
    checks.append({"claim": claim, "check": label, "actual": compact(actual),
                   "expected": compact(expected), "match": actual == expected})

def deps(roots, declarations):
    seen, pending = set(), list(roots)
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        row = declarations.get(name)
        if row is not None:
            pending.extend(semantic_refs(row))
            pending.extend(name_str(n) for n in row.get("value_constants", []))
    return seen

def pi_count(expression):
    count = 0
    while isinstance(expression, dict) and "pi" in expression:
        count += 1
        expression = expression["pi"]["body"]
    return count

def stream_checks(label, process):
    check("05", label + " available", process.get("availability"), "available")
    record = process["record"]
    for stream in ("stdout", "stderr"):
        row = record[stream]
        payload = base64.b64decode(row["content_b64"])
        check("05", label + " " + stream + " bytes", len(payload), row["byte_count"])
        check("05", label + " " + stream + " digest", canonical.digest(payload), row["sha256"])
    return record

manifest = load(GATE / "qualification-inputs.json")
capture = load(CAPTURE / "capture.json")
annex = load(ANNEX / "result.json")
check("04", "new exact frozen manifest", digest(GATE / "qualification-inputs.json"),
      "sha256:b2879c5b19be1d63a72dacfa472839eb5ea5900ad572fbd8fa4a9bcfccc01de4")
check("04", "capture copied exact415 source mapping", capture["source_hashes"], manifest["source_hashes"])
check("04", "capture source root is full415 input root", capture["source_root"], manifest["selected_input_root"])
check("04", "captured source freeze digest", digest(CAPTURE / "source-freeze.json"), capture["source_freeze_hash"])
check("04", "capture binds gate019 manifest", capture["source_freeze_hash"], digest(GATE / "qualification-inputs.json"))
all_files = {str(p.relative_to(CAPTURE)): digest(p) for p in sorted(CAPTURE.rglob("*")) if p.is_file() and p.name != "capture.json"}
check("04", "complete1340 retained file inventory", all_files, capture["files"])
check("04", "retained registered415 exact preimages", {n: digest(CAPTURE / "registered-sources" / n) for n in manifest["source_hashes"]}, manifest["source_hashes"])
check("04", "all415 current input hashes still match", {n: digest(ROOT / n) for n in manifest["source_hashes"]}, manifest["source_hashes"])
check("04", "immutable captured files", [str(p.relative_to(CAPTURE)) for p in CAPTURE.rglob("*") if p.is_file() and stat.S_IMODE(p.stat().st_mode) != 0o444], [])
check("04", "no symlinked capture files", [str(p.relative_to(CAPTURE)) for p in CAPTURE.rglob("*") if p.is_symlink()], [])
check("04", "capture model calls", capture["model_calls"], 0)
check("04", "capture deliberately not final qualification", capture["qualification"], False)
check("04", "capture reached retained-validation prerequisite", capture["stage_status"], "BUILT_PENDING_RETAINED")

stages = load(CAPTURE / "contract-stage-results.json")
check("04", "actual contract stages", [(x["command"], x["status"]) for x in stages],
      [("interpret", "PASS"), ("formalize", "PASS"), ("prove", "PASS"), ("accept", "PASS"), ("export", "PASS")])
certificate = load(PKG / "accepted/acceptance.json")
accepted = load(PKG / "accepted/accepted-ir.json")
response = load(PKG / "formalizer-response.json")
frozen = load(PKG / "formalizer-frozen.json")
origin = load(PKG / "contract/candidate/compiler-origin.json")
statement = load(PKG / "contract/candidate/statement-check.json")
profile = load(PKG / certificate["artifacts"]["profile"]["path"])
check("04", "frontend captured response binding", origin["captured_response_hash"], digest(PKG / "formalizer-response.json"))
check("04", "frontend frozen record binding", origin["frozen_records_hash"], digest(PKG / "formalizer-frozen.json"))
check("04", "frontend actual compilation", statement["compile"]["ok"], True)
check("04", "frontend diagnostics", statement["diagnostics"], [])
check("04", "actual statement and frontend denotation audits", [x["result"] for x in statement["defeq"] + statement["frontend_defeq"]], [{"defeq": True, "ok": True, "typechecks": True}] * 20)
check("04", "eight accepted obligation identities", sorted(accepted["obligations"]), sorted(["D1", "A1", "G-map", "G.filter", "G:fold", "G-equality", "S:delivery.only", "W1"]))
for oid, row in certificate["obligations"].items():
    check("04", oid + " typechecked", row["typechecked"], "PASS")
    check("04", oid + " proof status", row["proved"], "NOT_APPLICABLE" if oid in ("D1", "A1") else "PASS")
    check("04", oid + " no diagnostics", row["codes"], [])
check("04", "Shade all three alternatives", profile["enums"]["Shade"]["constructors"], ["light", "dark", "neutral"])
check("04", "fixed canonical Shade equality", profile["enums"]["Shade"]["decidable_eq"]["lean_decl"], "VeriSlopAST.instDecidableEqShade")
check("04", "no candidate equality override", "candidate_decidable_eq" in profile["enums"]["Shade"], False)
check("04", "Parcel exact nominal fields", [(x["name"], x["sort"]) for x in profile["records"]["Parcel"]["fields"]], [("shade", {"enum": "Shade"}), ("n", "Nat")])
check("04", "Envelope exact nominal fields", [(x["name"], x["sort"]) for x in profile["records"]["Envelope"]["fields"]], [("parcel", {"record": "Parcel"}), ("active", "Bool")])
witness = stages[3]["summary"]["obligations"]["W1"]
check("04", "constructive witness accepted", witness["proved"], "PASS")
check("04", "retained constructive zero/light/inactive witness exists", certificate["obligations"]["W1"].get("witnesses") is not None, True)
for oid, theorem in [("G-map", "law_shift"), ("G.filter", "law_filter"), ("G:fold", "law_fold"), ("G-equality", "law_equality"), ("S:delivery.only", "source_delivery")]:
    row = accepted["obligations"][oid]["formal"]
    expression = load(PKG / "accepted/expressions" / (row["formula_ref"].rsplit("@", 1)[1][7:] + ".json"))
    if oid in ("G-map", "S:delivery.only"):
        actual_formula = expression["value"]["formula"] if expression["value"] is not None else None
        check("04", oid + " actual source facet entry", expression["source"][0]["symbol"], "shiftEnvelopes" if oid == "G-map" else "inspectEnvelope")
        check("04", oid + " Mixed/value scope", expression["value"] is not None, oid == "G-map")
    else:
        actual_formula = expression["formula"]
    check("04", oid + " reconstructed accepted formula equals frozen frontend", actual_formula, response["theorems"][theorem].get("formula"))

source = load(CAPTURE / "program.vscore.json")
admission = load(CAPTURE / "source-admission-result.json")
wrong_admission = load(CAPTURE / "wrong-source-admission-result.json")
entries = {x["id"]: x for x in source["entries"]}
helpers = {x["id"]: x for x in source["helpers"]}
check("05", "source admission", admission["status"], "PASS")
check("05", "type-correct wrong source admission", wrong_admission["status"], "PASS")
check("05", "exact four retained helpers", sorted(helpers), sorted(["shiftParcel", "shiftEnvelope", "keepEnvelope", "totalStep"]))
check("05", "helper heterogeneous declared order", helpers["shiftEnvelope"]["params"], ["nat", {"record": "Envelope"}])
check("05", "helper-to-helper call retained", helpers["shiftEnvelope"]["body"]["fields"][0]["value"]["helper"], "shiftParcel")
check("05", "map captured increment and lambda variable order", entries["shiftEnvelopes"]["body"], {"tag": "list_map", "value": {"tag": "var", "index": 1}, "body": {"tag": "call", "helper": "shiftEnvelope", "args": [{"tag": "var", "index": 1}, {"tag": "var", "index": 0}]}})
check("05", "filter captured Parcel and lambda variable order", entries["keepParcel"]["body"], {"tag": "list_filter", "value": {"tag": "var", "index": 1}, "body": {"tag": "call", "helper": "keepEnvelope", "args": [{"tag": "var", "index": 1}, {"tag": "var", "index": 0}]}})
check("05", "fold captured Shade, arbitrary initial, ordered step", entries["shadeTotal"]["body"], {"tag": "list_fold", "source": {"tag": "var", "index": 2}, "initial": {"tag": "var", "index": 1}, "step": {"tag": "call", "helper": "totalStep", "args": [{"tag": "var", "index": 2}, {"tag": "var", "index": 1}, {"tag": "var", "index": 0}]}})
check("05", "source-only body stays independent", entries["inspectEnvelope"]["body"], {"tag": "nat", "value": "0"})
for path in (CAPTURE / "candidate/program.vscore.json", PKG / "implementation/program.vscore.json", CAPTURE / "previews/positive/program.vscore.json"):
    check("05", "exact delivered bytes " + path.relative_to(CAPTURE).as_posix(), digest(path), digest(CAPTURE / "program.vscore.json"))

declarations = load(CAPTURE / "previews/positive/declarations.json")
observation = load(CAPTURE / "previews/positive/observation.json")
semantic = load(EDGE / "certificate.json")
readable = load(EDGE / "readable/manifest.json")
base = load(EDGE / "readable/base-kernel-export.json")
typed = load(EDGE / "readable/typed-ir.json")
support_exports = load(EDGE / "readable/kernel-export.json")
inventory = load(EDGE / "readable/compiled-inventory.json")
check("05", "actual CHECKED readable status", (readable["selected_mode"], readable["status"]), ("CHECKED", "CHECKED"))
check("05", "CHECKED helper/entry correspondence inventory", (sum(x["role"] == "helper" for x in inventory), sum(x["role"] == "entry" for x in inventory)), (4, 5))
check("05", "typed readable source helper identities", sorted(x["source_id"] for x in typed["functions"] if x["role"] == "helper"), sorted(helpers))
check("05", "original EdgeProp body unchanged under CHECKED selection", declarations["VeriSlopBridgeGoal.EdgeProp"]["value"], base["VeriSlopBridgeGoal.EdgeProp"]["value"])
check("05", "base/original proposition identity", readable["base_proposition_hash"], semantic["proposition_hash"])
check("05", "replayed/original proposition identity", readable["replayed_proposition_hash"], semantic["proposition_hash"])
check("05", "kernel support replay receipt", load(EDGE / "readable/kernel-receipt.json")["replayed"], True)
for row in readable["artifacts"]:
    artifact = row["artifact"]
    check("05", "readable artifact " + artifact["path"], digest(EDGE / artifact["path"]), artifact["sha256"])
for row in inventory:
    for key in ("lookup_theorem", "signature_theorem", "run_equals_theorem"):
        exported = support_exports[row[key]]
        check("05", row[key] + " actual safe theorem", (exported["kind"], exported["safety"], exported["unresolved_constants"]), ("theorem", "safe", []))
    check("05", row["run_equals_theorem"] + " exact type hash", canonical.digest_json(support_exports[row["run_equals_theorem"]]["type"]), row["run_equals_type_hash"])
edge_dependencies = deps(["VeriSlopBridgeProof.edge"], declarations)
laws = ["VSCore3.ProofSupport." + x for x in ("to_eq_iff", "decide_to_eq", "map_transport", "filter_transport", "foldl_transport")]
check("05", "actual combined source proof depends on all five laws", sorted(set(laws) - edge_dependencies), [])
edge_refs = semantic_refs(declarations["VeriSlopBridgeGoal.EdgeProp"])
check("05", "source-only arbitrary reference equality absent from EdgeProp", "VeriSlopBridgeGoal.Refines_inspectEnvelope" in edge_refs, False)
check("05", "source-only operational adequacy retained", "VeriSlopBridgeGoal.SourceAdequate_inspectEnvelope" in edge_refs, True)
for symbol, proof_name, arity in [("shiftEnvelopes", "ref_map", 2), ("keepParcel", "ref_filter", 2), ("shadeTotal", "ref_fold", 3), ("sameShade", "ref_equality", 2)]:
    definition = declarations["VeriSlopBridgeGoal.Refines_" + symbol]
    check("05", symbol + " universal kernel binder arity", pi_count(definition["value"]), arity)
    row = declarations["VeriSlopBridgeProof." + proof_name]
    check("05", proof_name + " actual safe refinement theorem", (row["kind"], row["safety"], row["unresolved_constants"]), ("theorem", "safe", []))
    check("05", proof_name + " correct original refinement type", semantic_refs(row), {"VeriSlopBridgeGoal.Refines_" + symbol})
for symbol in entries:
    for prefix in ("inputs_cover_", "raw_eval_"):
        name = "VeriSlopBridgeGoal." + prefix + symbol
        row = declarations[name]
        check("05", name + " actual safe theorem", (row["kind"], row["safety"], row["unresolved_constants"]), ("theorem", "safe", []))
        check("05", name + " in accepted edge proof closure", name in edge_dependencies, True)
for obligation in semantic["obligations"]:
    oid, name = obligation["id"], obligation["transfer_theorem"]
    check("05", oid + " literal transfer name components", parse_name(name), ["VeriSlopBridgeGoal", "transfer_" + oid])
    row = declarations[name]
    check("05", oid + " safe actual transfer theorem", (row["kind"], row["safety"], row["unresolved_constants"]), ("theorem", "safe", []))
    check("05", oid + " depends on original accepted theorem", obligation["accepted_theorem"] in deps([name], declarations), True)
    check("05", oid + " exact accepted statement hash", obligation["accepted_statement_hash"], accepted["obligations"][oid]["formal"]["statement_hash"])
for name in ("direct-conversion-baseline", "semantically-wrong-source"):
    failure = load(CAPTURE / "previews" / name / "failure.json")
    diagnostic = failure["diagnostics"][0]
    check("05", name + " actual rejection", diagnostic["code"], "CANDIDATE_BUILD_FAILURE")
    check("05", name + " actual Lean rfl error", any("Tactic `rfl` failed" in x for x in diagnostic["details"]["errors"]), True)
    process = stream_checks(name, diagnostic["details"]["process_evidence"])
    check("05", name + " actual compiler nonzero", process["returncode"] != 0, True)
    check("05", name + " exact attempted proof module", process["input"]["module_source_sha256"], digest(CAPTURE / "previews" / name / "Proof.lean"))
tamper = load(CAPTURE / "previews/tampered-readable-selection/failure.json")
check("05", "selection tampering actual production rejection", tamper["diagnostics"][0]["code"], "INPUT_MUTATION")
wrong_ground = load(CAPTURE / "concrete-wrong-source-control.json")
check("05", "optional ground replay honestly remains unresolved", wrong_ground["status"], "UNRESOLVED_REPLAY_BOUNDARY")
check("05", "optional ground replay never qualified", wrong_ground["qualification"], False)

implementation_stages = load(CAPTURE / "implementation-stage-results.json")
check("06", "actual registered workflow stages", [(x["command"], x["status"]) for x in implementation_stages], [("generate", "PASS"), ("link", "PASS"), ("bridge accept", "PASS"), ("verify", "PASS")])
check("06", "actual semantic bridge accepted", semantic["semantic_acceptance"], True)
check("06", "semantic bridge does not assign end-to-end itself", semantic["assigns_end_to_end_verified"], False)
snapshot = load(CAPTURE / "mechanical-snapshot.json")
retained = load(ANNEX / "retained-mechanical-snapshot.json")
check("06", "registered current mechanical status", snapshot["mechanical_status"], "VERIFIED")
check("06", "registered restricted source endpoint", snapshot["endpoint"], "restricted_source")
check("06", "actual isolated A/B build identities", [(x["build"], x["ok"], x["errors"]) for x in snapshot["builds"]], [("A", True, []), ("B", True, [])])
check("06", "all deterministic A/B outputs equal", snapshot["builds"][0]["outputs"], snapshot["builds"][1]["outputs"])
check("06", "no semantic mismatch masked by exclusions", snapshot["determinism"]["excluded_nondeterministic_fields"], ["/execution/wall_ms"])
check("06", "no determinism mismatches", snapshot["determinism"]["mismatches"], [])
check("06", "retained snapshot equals original exactly", retained, snapshot)
execution = PKG / Path(snapshot["mechanical_result_path"]).parent
check("06", "all432 actual execution inventory hash/size bindings", [(x["path"], digest(execution / x["path"]), (execution / x["path"]).stat().st_size) for x in snapshot["execution_inventory"]], [(x["path"], x["sha256"], x["size"]) for x in snapshot["execution_inventory"]])
for build in snapshot["builds"]:
    output = build["outputs"]
    check("06", build["build"] + " contract replayed", output["contract_receipt"]["accepted_contract_replayed"], True)
    check("06", build["build"] + " CHECKED descriptor", output["readable_support"]["descriptor"]["mode"], "CHECKED")
    check("06", build["build"] + " exact proposition", output["semantic_build"]["proposition_hash"], semantic["proposition_hash"])
    check("06", build["build"] + " all module compilations okay", all(x["ok"] and not x["errors"] and x["sorries"] == 0 for x in output["semantic_build"]["compiles"].values()), True)
    check("06", build["build"] + " actual filesystem isolation", (output["semantic_build"]["isolation"]["filesystem_read_isolation"], output["semantic_build"]["isolation"]["filesystem_write_isolation"]), (True, True))
    check("06", build["build"] + " preview same actual module/proposition inventory", (output["semantic_build"]["modules"], output["semantic_build"]["proposition_hash"]), (observation["modules"], observation["proposition_hash"]))
for path in (CAPTURE / "release-probe.json", ANNEX / "retained-release-probe.json"):
    probe = load(path)
    check("06", path.name + " actual release execution", (probe["checkpoint"], probe["status"], probe["expected"]["outcome"], probe["observed"]["outcome"]), ("release", "NOT_REPRODUCED", "PASS", "PASS"))
    check("06", path.name + " all753 concrete package input hashes", {n: digest(PKG / n) for n in probe["input_bindings"] if n != "binding:roots"}, {n: h for n, h in probe["input_bindings"].items() if n != "binding:roots"})
    check("06", path.name + " exact semantic claim", probe["claim"]["claim_id"], semantic["claim_id"])
check("06", "retained annex exact attempt", annex["attempt"], CAPTURE.relative_to(ROOT).as_posix())
check("06", "retained annex exact capture hash", annex["capture_hash"], digest(CAPTURE / "capture.json"))
check("06", "retained annex actual qualification observation", annex["qualification"], True)
check("06", "retained annex original temp removal recorded", annex["original_temporary_root_removed"], True)
check("06", "actual original fresh temp root absent", Path("/tmp/fresh-shade-collection-tier2-kc5w7faq").exists(), False)
check("06", "retained annex no error/model calls", (annex["error"], annex["model_calls"]), (None, 0))
check("06", "all415 inputs still unchanged after this preparation", {n: digest(ROOT / n) for n in manifest["source_hashes"]}, manifest["source_hashes"])

gaps = [x for x in checks if not x["match"]]
report = {"format": "verislop.collection-support-pending-preparation/1", "audit_id": "tier2-collection-proof-support-audit-017",
          "qualification_attempt": "gate019", "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
          "overall": "PENDING", "qualification_authority": False,
          "claim_status": {"AUD017-04-GENERATED-PACKAGE": "UNDISCHARGED", "AUD017-05-SEMANTIC-BRIDGE": "UNDISCHARGED", "AUD017-06-CLOSURE-AND-PORTABILITY": "UNDISCHARGED"},
          "tests_executed_by_reviewer": 0, "lean_builds_by_reviewer": 0, "model_calls_by_reviewer": 0,
          "fixture_generation_by_reviewer": False, "gate_terminal_result_read": False,
          "captured_package": CAPTURE.relative_to(ROOT).as_posix(), "retained_annex": ANNEX.relative_to(ROOT).as_posix(),
          "reader_sha256": digest(Path(__file__)), "evidence_bindings": bindings,
          "frozen_input_manifest_sha256": digest(GATE / "qualification-inputs.json"),
          "selected_input_root": manifest["selected_input_root"], "selected_input_count": 415,
          "comparison_count": len(checks), "all_prepared_comparisons_match": not gaps,
          "comparisons": checks, "new_concrete_or_reader_gaps": gaps,
          "optional_wrong_source_ground_replay": wrong_ground,
          "limitations": ["No claim discharge or qualification authority until the complete98 gate, actual final process receipt, final engineering record and whole seven-claim audit.",
                          "All new evidence comes only from the two root-designated fresh gate019 captures; no task artifacts or historical qualification package was inspected.",
                          "The optional wrong-source ground probe is Unsupported/UNRESOLVED, not proved false; the required actual universal proof rejection is retained separately.",
                          "Correct release probes are recorded mechanical_failure replays of the registered semantic claim, not independent ground-value kernel FALSE/TRUE claims.",
                          "Initial exploratory readers encountered list/dict and integer/count schema errors; they did not execute tests, Lean or qualification and did not alter evidence."]}
out = AUDIT / "gate019-prepared-observations-04-06.json"
with out.open("xb") as f:
    f.write(canonical.dumps(report))
out.chmod(0o444)
print(str(out.relative_to(ROOT)), digest(out))
print("comparisons", len(checks), "match", not gaps, "gaps", [(x["check"], x["actual"], x["expected"]) for x in gaps], "status PENDING")
