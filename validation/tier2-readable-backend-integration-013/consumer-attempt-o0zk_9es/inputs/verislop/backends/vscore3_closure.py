"""Finite, frozen closure of the delivered VSCore restricted-source endpoint.

The supervisor freezes the claim graph and input membership before either fresh
execution. Existing certificates are comparison inputs, never execution substitutes.
Terminal records are staged in private storage and published with the immutable
mechanical result in one no-clobber directory operation.
"""
from __future__ import annotations

import secrets
import signal
import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

from .. import canonical, contract, fsutil, leanbridge, schemas
from ..claimcheck import evaluate_claim
from ..errors import Diagnostic, VeriSlopError
from ..evidence import Evidence, EvidenceStore
from ..events import EventSink
from ..lifecycle import applicability, claim_id
from ..package import Package
from ..stage import StageResult, status_from
from ..verifiers import CORE, PKG, VERIFIERS, registry_snapshot, verifier_hash
from ..bridges import prepare, vscore3_checker as checker
from ..bridges.check import _evidence, semantic_edge_root
from ..bridges.import_contract import import_contract
from ..bridges.manifest import InvalidPackage, PackageReader
from ..bridges.publish import publish_into
from ..targets import vscore3_target as target

VERIFIER = "verislop.closure"
FINAL_PREDICATES = {
    "CLOSURE:clean-builds": "closure-clean-builds/0.2",
    "CLOSURE:determinism": "closure-determinism/0.2",
    "CLOSURE:provenance": "closure-provenance/0.2",
    "CLOSURE:endpoint": "closure-endpoint/0.2",
}
COMPARISON_SLOTS = (
    "contract_receipt", "contract_artifacts", "contract_obligations", "accepted_ir",
    "semantic_build", "goal", "semantic_certificate", "implementation_ir",
    "module_parts", "materialization_inventory", "link_record", "nonfinal_outcomes",
    "provenance_graph", "readable_support",
)
EXCLUDED = [
    "host interpreter, Lean code generation, VM, compiler, linker, loader and native executable",
    "operating-system services, I/O, concurrency and fairness",
    "general mutable state, unrestricted recursion and entry-to-entry calls",
    "physical resources, machine-width arithmetic and constant-time behavior",
    "unlisted claims and future revisions",
]


def _fail(code: str, message: str, claims: list[str] | None = None) -> InvalidPackage:
    error = InvalidPackage(message, code)
    error.claims = claims or []
    return error


def _selection(pkg: Package) -> dict:
    from . import vscore3 as vscore

    return vscore.selection(pkg)


def _json(pkg: Package, path: str) -> dict:
    reader = PackageReader(pkg.root)
    try:
        value, _ = reader.json(path)
        reader.recheck()
        return value
    finally:
        reader.close()


def _claims(pkg: Package) -> list[dict]:
    """Expand inventories, preserving every required internal claim."""
    contract_claims = _json(pkg, "claims.json")
    implementation = _json(pkg, "closure/implementation-claims.json")
    # Reconstruct the supervisor inventory before trusting its frozen predicates,
    # requiredness or premise edges. Candidate-edited claim records cannot waive
    # a declaration, bridge check or accepted proof.
    from . import vscore3 as vscore

    ir = _json(pkg, "accepted/accepted-ir.json")
    cert = _json(pkg, "accepted/acceptance.json")
    profile = _json(pkg, cert["artifacts"]["profile"]["path"])
    bridge_plan = _json(pkg, "bridges/" + implementation["parameters"]["bridge_id"] + "/plan.json")
    reconstructed = vscore.implementation_claims(pkg, ir, result_hash(pkg.root / "accepted/accepted-ir.json"),
        result_hash(pkg.root / "accepted/acceptance.json"), implementation["parameters"], profile,
        _json(pkg, "interpretation.json"), bridge_plan)
    if implementation != reconstructed:
        raise _fail("CLAIM_MUTATION", "frozen claim graph differs from the supervisor's complete accepted-contract inventory")
    result: list[dict] = []
    derived = {r["id"] for r in contract_claims["obligations"] if r["origin"] == "derived"}
    defaults = {"INTERPRETED": "interpretation_root", "FORMALIZED": "contract_input_root",
                "TYPECHECKED": "contract_input_root", "PROVED": "contract_input_root"}
    contract_ids = {c["claim_id"] for c in contract_claims["claims"]}
    inherited_ids = {c["claim_id"] for c in implementation["claims"]
                     if c.get("milestone") in defaults}
    if contract_ids != inherited_ids:
        raise _fail("ORPHAN_CLAIM", "implementation inventory omits or invents contract claims")
    for record in implementation["claims"]:
        item = dict(record)
        item.setdefault("root_kind", defaults.get(item.get("milestone"), "closure_root"))
        if item.get("milestone") == "INTERPRETED" and item.get("obligation") in derived:
            item["root_kind"] = "contract_input_root"
        item.setdefault("result_predicate", "milestone-pass/0.1")
        item.setdefault("premises", [])
        item.setdefault("scope", ["frozen contract claim"])
        item.setdefault("trusted_dependencies", VERIFIERS.get(item.get("verifier"), {}).get("trusted", []))
        item.setdefault("revision", None)
        item.setdefault("accepted_statement_hash", None)
        result.append(item)
    result.append({"claim_id": "INTERPRETATION:request", "obligation": None, "milestone": None,
                   "revision": None, "accepted_statement_hash": None, "required": True, "applicable": True,
                   "verifier": "verislop.interpretation-recorder", "root_kind": "interpretation_root",
                   "result_predicate": "interpretation-coverage/0.1", "premises": [],
                   "scope": ["complete frozen source-clause interpretation coverage"],
                   "trusted_dependencies": ["accepted-contract-policy"]})
    for oid, rec in sorted(ir["obligations"].items()):
        result.append({"claim_id": f"REIFIED:{oid}@{rec['revision']}", "obligation": None, "milestone": None,
                       "revision": None, "accepted_statement_hash": rec["formal"]["statement_hash"],
                       "required": rec["required"], "applicable": True, "verifier": "verislop.reifier",
                       "root_kind": "acceptance_certificate", "result_predicate": "milestone-pass/0.1",
                       "premises": [claim_id("TYPECHECKED", oid, rec["revision"])],
                       "scope": ["accepted artifact-to-IR correspondence"],
                       "trusted_dependencies": ["accepted-contract-policy"]})
    ids = [c["claim_id"] for c in result]
    if len(ids) != len(set(ids)):
        raise _fail("ORPHAN_CLAIM", "closure has duplicate frozen claim identities")
    by_id = {c["claim_id"]: c for c in result}
    for claim in result:
        if claim.get("verifier", claim.get("verifier_id")) not in VERIFIERS:
            raise _fail("ORPHAN_CLAIM", f"unregistered verifier for {claim['claim_id']}")
        if not set(claim["premises"]).issubset(by_id):
            raise _fail("ORPHAN_CLAIM", f"undeclared premise of {claim['claim_id']}")
    waiting = set(by_id)
    passed: set[str] = set()
    while waiting:
        ready = {cid for cid in waiting if set(by_id[cid]["premises"]).issubset(passed)}
        if not ready:
            raise _fail("ORPHAN_CLAIM", "closure claim premise graph contains a cycle")
        waiting -= ready
        passed |= ready
    for cid, predicate in FINAL_PREDICATES.items():
        item = by_id.get(cid)
        if not item or (item.get("verifier") != VERIFIER or item.get("obligation") is not None or
                        item.get("milestone") is not None or not item.get("required") or
                        not item.get("applicable") or item["root_kind"] != "closure_root" or
                        item["result_predicate"] != predicate):
            raise _fail("ORPHAN_CLAIM", f"missing or invalid terminal claim {cid}")
    return sorted(result, key=lambda c: c["claim_id"])


def _roots(pkg: Package, selection: dict, root: str | None) -> dict:
    result = {**pkg.roots(), "closure_root": root,
              "contract_candidate_root": pkg.meta().get("contract_candidate_root"),
              "acceptance_certificate": result_hash(pkg.root / "accepted/acceptance.json")}
    bundle = pkg.root / "bridges" / selection["bridge_id"]
    plan = canonical.load_file(bundle / "plan.json")
    edge = next(e for e in plan["edges"] if e["edge_id"] == selection["edge_id"])
    result.update({"bridge_plan": canonical.digest_file(bundle / "plan.json"),
                   "bridge_artifacts": canonical.digest_file(bundle / "artifacts.json"),
                   "semantic_edge": semantic_edge_root(result_hash(bundle / "plan.json"),
                                                        result_hash(bundle / "artifacts.json"), edge)})
    return result


def result_hash(path: Path) -> str:
    return canonical.digest(path.read_bytes())


def _selected_evidence(pkg: Package, selection: dict, claims: list[dict], roots: dict) -> dict[str, Evidence]:
    """Only the assigned latest current record becomes a manifest input."""
    pool = list(pkg.evidence.load())
    internal_pool: dict[str, list[Evidence]] = {}
    bundle = pkg.root / "bridges" / selection["bridge_id"]
    reader = PackageReader(bundle)
    try:
        prep, _ = reader.json("preparation-certificate.json")
        structural = _evidence(reader, prep["evidence"])
        internal_pool["bridge_artifacts"] = [structural]
        rel = f"semantic/{checker.edge_key(selection['edge_id'])}"
        cert, _ = reader.json(f"{rel}/{checker.CERTIFICATE}")
        semantic_reader = PackageReader(bundle / rel)
        try:
            semantic = _evidence(semantic_reader, cert["evidence"])
            internal_pool["semantic_edge"] = [semantic]
            semantic_reader.recheck()
        finally:
            semantic_reader.close()
        reader.recheck()
    finally:
        reader.close()
    accepted, pending, diagnostics = checker.verify_published(pkg, selection["bridge_id"], rebuild=False)
    if diagnostics or pending or len(accepted) != 1:
        raise checker.EdgeFailure(diagnostics or [Diagnostic("VERIFIER_NOT_RUN", "selected semantic certificate is absent")])
    selected: dict[str, Evidence] = {}
    for claim in claims:
        if _terminal(claim):
            continue
        checked = evaluate_claim(claim, internal_pool.get(claim["root_kind"], pool), roots, claim["root_kind"])
        if checked.evidence:
            selected[claim["claim_id"]] = checked.evidence
    return selected


def _terminal(claim: dict) -> bool:
    return claim["claim_id"] in FINAL_PREDICATES or claim.get("milestone") == "END_TO_END_VERIFIED"


def _evidence_bytes(pkg: Package, selection: dict, ev: Evidence) -> tuple[bytes, bytes]:
    bundle = pkg.root / "bridges" / selection["bridge_id"]
    bases = (pkg.root, bundle, bundle / checker.SEMANTIC_DIR / checker.edge_key(selection["edge_id"]))
    for base in bases:
        rel = "evidence/" + ev.id + ".json"
        if (base / rel).is_file():
            reader = PackageReader(base)
            try:
                record = reader.read(rel, keep=True).data
                raw = reader.read(ev.record["raw_result_ref"], keep=True).data
                if canonical.loads(record) != ev.record or canonical.digest(raw) != ev.record["raw_result_hash"]:
                    raise _fail("STALE_OR_UNBOUND_EVIDENCE", "consumed evidence changed during execution")
                reader.recheck()
                return record, raw
            finally:
                reader.close()
    raise _fail("STALE_OR_UNBOUND_EVIDENCE", "selected evidence has no exact retained input record")


def _input_paths(pkg: Package, selection: dict, claims: list[dict], selected: dict[str, Evidence]) -> dict[str, str]:
    paths: dict[str, str] = {}
    from .. import source_policy
    if source_policy.context(pkg) is not None:
        paths[source_policy.PATH] = "frozen-input"
    for rel in ("claims.json", "request/prompt.txt", "request/request.json", "draft.json", "interpretation.json",
                "closure/selection.json", "closure/implementation-claims.json", "bridges/bindings.json",
                "bridges/link.json", "closure/plan.json", "closure/tcb.json",
                "closure/verifiers.json", "closure/schemas.json", "closure/runtime.json"):
        paths[rel] = "frozen-input"
    for directory in ("contract/challenge", "accepted", "implementation", "bridges/" + selection["bridge_id"],
                      "request/attachments"):
        if (pkg.root / directory).is_dir():
            for rel in fsutil.list_files(pkg.root / directory):
                paths[directory + "/" + rel] = "frozen-input"
    for rel in ("contract/proofs/candidate.lean", "tests/campaign.json"):
        if (pkg.root / rel).is_file():
            paths[rel] = "frozen-input"
    # Include exact evidence actually consumed. Bridge evidence is already inside
    # the selected bundle; ordinary assigned records live at the package root.
    for evidence in selected.values():
        rel = "evidence/" + evidence.id + ".json"
        if (pkg.root / rel).is_file():
            paths[rel] = "consumed-evidence"
            paths[evidence.record["raw_result_ref"]] = "consumed-evidence"
    return dict(sorted(paths.items()))


def _manifest(pkg: Package, paths: dict[str, str], closure_id: str) -> dict:
    reader = PackageReader(pkg.root)
    try:
        entries = []
        for path, role in sorted(paths.items()):
            snap = reader.read(path)
            entries.append({"path": path, "role": role, "size": snap.size, "sha256": snap.sha256})
        reader.recheck()
        return {"schema_version": "0.2", "format": "verislop.closure-manifest/0.2",
                "closure_id": closure_id, "entries": entries}
    finally:
        reader.close()


def _runtime_snapshot(ids: list[str]) -> dict:
    files = set(CORE)
    schema_names = set()
    for vid in ids:
        files.update(VERIFIERS[vid]["sources"])
        schema_names.update(VERIFIERS[vid]["schemas"])
    return {"sources": [{"path": rel, "sha256": canonical.digest_file(PKG / rel)} for rel in sorted(files)],
            "schemas": [{"path": rel, "sha256": canonical.digest_file(schemas.schema_dir() / rel)}
                        for rel in sorted(schema_names)]}


def _tcb(cert: dict) -> dict:
    _check_toolchain_binary(cert)
    return {"format": "verislop.tcb/0.2", "toolchain": cert["toolchain"],
            "standard_library_closure": cert["olean_closure"], "allowed_axioms": cert["policy"]["allowed_axioms"],
            "verified": ["VSCore normative parsing, typing, evaluation and representation adapters"],
            "trusted_ids": ["lean-kernel", "accepted-contract-policy"],
            "trusted": ["pinned Lean kernel and standard library", "kernel replay and expression export tools",
                        "supervisor codecs, orchestration and SHA-256", "sandbox, operating system and hardware",
                        "recorded natural-language interpretation"]}


def _check_toolchain_binary(cert: dict) -> None:
    """The process-local toolchain identity cache is never a live file check."""
    tc = leanbridge.resolve_toolchain(cert["toolchain"]["pin"])
    if canonical.digest_file(tc.lean) != cert["toolchain"]["lean_binary_sha256"]:
        raise _fail("UNDECLARED_DEPENDENCY", "actual pinned Lean executable differs from the accepted toolchain identity")


def freeze(pkg: Package) -> list[Diagnostic]:
    """Freeze once after semantic acceptance; never repair an existing snapshot."""
    try:
        selection = _selection(pkg)
        claims = _claims(pkg)
        existing = pkg.root / "closure/plan.json"
        if existing.is_file() and (pkg.root / "closure/manifest.json").is_file():
            return validate_frozen(pkg)
        # Validate all required pre-existing certificate evidence before writing
        # any closure snapshot. An interrupted freeze can finish the exact same
        # immutable plan; it cannot replace a previously frozen manifest.
        selected = _selected_evidence(pkg, selection, claims, _roots(pkg, selection, None))
        closure_id = (_json(pkg, "closure/plan.json")["closure_id"] if existing.is_file()
                      else pkg.run_id + "-closure-" + secrets.token_hex(12))
        ids = sorted({c.get("verifier", c.get("verifier_id")) for c in claims} | {VERIFIER})
        cert = _json(pkg, "accepted/acceptance.json")
        tcb = _tcb(cert)
        snapshots = {"tcb.json": tcb, "verifiers.json": registry_snapshot(),
                     "schemas.json": schemas.all_schema_hashes(), "runtime.json": _runtime_snapshot(ids)}
        for name, value in snapshots.items():
            fsutil.write_json(pkg.root / "closure" / name, value, once=True)
        refs = [{"path": path, "sha256": result_hash(pkg.root / path)}
                for path in ("claims.json", "closure/implementation-claims.json")]
        plan = {"schema_version": "0.2", "format": "verislop.closure-plan/0.2", "closure_id": closure_id,
                "backend": selection["backend"], "endpoint": target.ENDPOINT,
                "selection": {"path": "closure/selection.json", "sha256": result_hash(pkg.root / "closure/selection.json")},
                "claim_inventories": refs, "claim_ids": [c["claim_id"] for c in claims],
                "premise_graph": [{"claim_id": c["claim_id"], "premises": c["premises"]} for c in claims],
                "public_claims": [{"claim_id": c["claim_id"], "obligation": c.get("obligation"),
                                   "scope": c["scope"]} for c in claims if c["required"] and c["applicable"]],
                "test_policy": selection["test_policy"], "build_policy": selection["build_policy"],
                "reproducible_outputs": [{"slot": slot, "producer": VERIFIER, "format": "canonical-json/0.1"}
                                         for slot in COMPARISON_SLOTS],
                "permitted_nondeterministic_fields": ["/execution/attempt_id", "/execution/started_at",
                    "/execution/finished_at", "/execution/wall_ms", "/execution/work_directory",
                    "/evidence/evidence_id", "/evidence/raw_result_ref", "/evidence/raw_result_hash",
                    "/raw/sequence", "/raw/recorded_at"],
                "verifiers": [{"id": vid, "sha256": verifier_hash(vid)} for vid in ids],
                "schemas": [{"id": name, "sha256": digest} for name, digest in sorted(schemas.all_schema_hashes().items())],
                "tcb": {"path": "closure/tcb.json", "sha256": result_hash(pkg.root / "closure/tcb.json")}}
        fsutil.write_json(existing, plan, once=True)
        manifest = _manifest(pkg, _input_paths(pkg, selection, claims, selected), closure_id)
        for name, value in (("closure-plan-v3", plan), ("closure-manifest", manifest)):
            issues = schemas.validate(name, value)
            if issues:
                raise _fail("INVALID_CANDIDATE", f"{name}: {issues[0]}")
        fsutil.write_json(pkg.root / "closure/manifest.json", manifest, once=True)
        return validate_frozen(pkg)
    except (checker.EdgeFailure, InvalidPackage, VeriSlopError, OSError, KeyError, ValueError) as exc:
        return _diagnostics(exc)


freeze_closure = freeze


def _diagnostics(exc: Exception) -> list[Diagnostic]:
    if isinstance(exc, (checker.EdgeFailure, VeriSlopError)) and exc.diagnostics:
        return exc.diagnostics
    return [Diagnostic(getattr(exc, "code", "VERIFIER_FAILURE"), str(exc),
                       severity="infrastructure" if isinstance(exc, OSError) else "blocking",
                       claims=getattr(exc, "claims", []))]


def validate_frozen(pkg: Package) -> list[Diagnostic]:
    try:
        selection = _selection(pkg)
        claims = _claims(pkg)
        plan = _json(pkg, "closure/plan.json")
        manifest = _json(pkg, "closure/manifest.json")
        for name, value in (("closure-plan-v3", plan), ("closure-manifest", manifest)):
            issues = schemas.validate(name, value)
            if issues:
                raise _fail("INPUT_MUTATION", f"{name}: {issues[0]}")
        if plan["closure_id"] != manifest["closure_id"]:
            raise _fail("INPUT_MUTATION", "closure plan and manifest identify different closures")
        tcb = _json(pkg, "closure/tcb.json")
        if tcb != _tcb(_json(pkg, "accepted/acceptance.json")):
            raise _fail("UNDECLARED_DEPENDENCY", "TCB differs from the registered accepted dependency boundary")
        if any(not set(c["trusted_dependencies"]).issubset(tcb["trusted_ids"]) for c in claims):
            raise _fail("UNDECLARED_DEPENDENCY", "a required claim uses an undeclared trusted dependency")
        if (plan["backend"] != selection["backend"] or plan["endpoint"] != target.ENDPOINT or
                plan["test_policy"] != selection["test_policy"] or plan["build_policy"] != selection["build_policy"] or
                plan["public_claims"] != [{"claim_id": c["claim_id"], "obligation": c.get("obligation"),
                                          "scope": c["scope"]} for c in claims if c["required"] and c["applicable"]] or
                plan["claim_ids"] != [c["claim_id"] for c in claims] or
                plan["premise_graph"] != [{"claim_id": c["claim_id"], "premises": c["premises"]} for c in claims] or
                plan["reproducible_outputs"] != [{"slot": slot, "producer": VERIFIER, "format": "canonical-json/0.1"}
                                                for slot in COMPARISON_SLOTS]):
            raise _fail("CLAIM_MUTATION", "closure plan no longer matches its frozen supervisor graph/recipe")
        ids = sorted({c.get("verifier", c.get("verifier_id")) for c in claims} | {VERIFIER})
        if (plan["verifiers"] != [{"id": vid, "sha256": verifier_hash(vid)} for vid in ids] or
                _json(pkg, "closure/verifiers.json") != registry_snapshot() or
                _json(pkg, "closure/schemas.json") != schemas.all_schema_hashes() or
                _json(pkg, "closure/runtime.json") != _runtime_snapshot(ids)):
            raise _fail("STALE_OR_UNBOUND_EVIDENCE", "registered verifier/schema/runtime dependency changed after freeze")
        selected = _selected_evidence(pkg, selection, claims, _roots(pkg, selection, None))
        fresh = _manifest(pkg, _input_paths(pkg, selection, claims, selected), plan["closure_id"])
        if fresh != manifest:
            raise _fail("INPUT_MUTATION", "closure input membership or exact bytes changed after freeze")
        if (plan["selection"]["sha256"] != result_hash(pkg.root / plan["selection"]["path"]) or
                plan["tcb"]["sha256"] != result_hash(pkg.root / plan["tcb"]["path"]) or
                any(ref["sha256"] != result_hash(pkg.root / ref["path"]) for ref in plan["claim_inventories"])):
            raise _fail("INPUT_MUTATION", "closure plan input reference changed")
        return []
    except (checker.EdgeFailure, InvalidPackage, VeriSlopError, OSError, KeyError, ValueError) as exc:
        return _diagnostics(exc)


def closure_manifest(pkg: Package) -> dict | None:
    path = pkg.root / "closure/manifest.json"
    return _json(pkg, "closure/manifest.json") if path.is_file() else None


def closure_input_root(pkg: Package) -> str | None:
    # Avoid calling pkg.roots here: this function is itself a Package root provider.
    if not (pkg.root / "closure/plan.json").is_file() or not (pkg.root / "closure/manifest.json").is_file():
        return None
    try:
        plan = _json(pkg, "closure/plan.json")
        manifest = _json(pkg, "closure/manifest.json")
        if schemas.validate("closure-plan-v3", plan) or schemas.validate("closure-manifest", manifest):
            return None
        selection = _selection(pkg)
        claims = _claims(pkg)
        paths = _input_paths(pkg, selection, claims, {})
        # Consumed evidence is frozen by exact record identity. Newly generated
        # outputs do not join the input manifest, while membership in every
        # declared input directory must still match on a status/view read.
        paths.update({row["path"]: row["role"] for row in manifest["entries"]
                      if row["role"] == "consumed-evidence"})
        if [(row["path"], row["role"]) for row in manifest["entries"]] != sorted(paths.items()):
            return None
        ids = sorted({c.get("verifier", c.get("verifier_id")) for c in claims} | {VERIFIER})
        if (_json(pkg, "closure/runtime.json") != _runtime_snapshot(ids) or
                _json(pkg, "closure/tcb.json") != _tcb(_json(pkg, "accepted/acceptance.json")) or
                _json(pkg, "closure/schemas.json") != schemas.all_schema_hashes()):
            return None
        reader = PackageReader(pkg.root)
        try:
            for entry in manifest["entries"]:
                snap = reader.read(entry["path"])
                if (snap.sha256, snap.size) != (entry["sha256"], entry["size"]):
                    return None
            reader.recheck()
        finally:
            reader.close()
        return canonical.digest_json({"format": "verislop.closure-root/0.2", "closure_id": plan["closure_id"],
            "plan_hash": result_hash(pkg.root / "closure/plan.json"),
            "manifest_hash": result_hash(pkg.root / "closure/manifest.json"),
            "verifier_registry_hash": result_hash(pkg.root / "closure/verifiers.json"),
            "schema_registry_hash": result_hash(pkg.root / "closure/schemas.json"),
            "tcb_hash": result_hash(pkg.root / "closure/tcb.json")})
    except (checker.EdgeFailure, InvalidPackage, VeriSlopError, OSError, KeyError, ValueError):
        return None


def _nonfinal(pkg: Package, selection: dict, claims: list[dict], roots: dict,
              selected: dict[str, Evidence]) -> tuple[list[dict], list[Diagnostic]]:
    result, diags = [], []
    by_id: dict[str, dict] = {}
    waiting = {c["claim_id"]: c for c in claims if not _terminal(c)}
    while waiting:
        ready = [c for c in waiting.values() if all(p in by_id for p in c["premises"])]
        if not ready:
            raise _fail("ORPHAN_CLAIM", "non-final claim depends on a terminal or missing claim")
        for claim in ready:
            cid = claim["claim_id"]
            if not claim["applicable"]:
                outcome, reason, evidence = "NOT_APPLICABLE", claim.get("reason", "inapplicable"), None
            else:
                assessment = evaluate_claim(claim, [selected[cid]] if cid in selected else [], roots, claim["root_kind"])
                outcome, reason, evidence = assessment.outcome, assessment.reason, assessment.evidence
                if outcome == "PASS" and evidence is not None:
                    milestone = claim.get("milestone")
                    if milestone == "IMPLEMENTED":
                        expected = result_hash(pkg.root / "implementation/materialization.json")
                        if (evidence.result.get("inventory_hash") != expected or
                                evidence.result.get("source_hash") != result_hash(pkg.root / "implementation/program.vscore.json")):
                            outcome, reason = "FAIL", "materializer evidence does not identify the exact checked source and inventory"
                    elif milestone == "LINKED":
                        if evidence.result.get("link_record_hash") != result_hash(pkg.root / "bridges/link.json"):
                            outcome, reason = "FAIL", "linker evidence does not identify the exact checked correspondence record"
                if any(by_id[p]["outcome"] != "PASS" for p in claim["premises"]):
                    outcome, reason = "FAIL", "a frozen prerequisite did not pass"
                if claim["required"] and outcome != "PASS":
                    diags.extend(assessment.diagnostics or [Diagnostic("VERIFIER_NOT_RUN", f"{cid}: {reason}", claims=[cid])])
            item = {"claim_id": cid, "outcome": outcome, "required": claim["required"],
                    "verifier": claim.get("verifier", claim.get("verifier_id")), "root_kind": claim["root_kind"],
                    "input_root": roots.get(claim["root_kind"]), "premises": claim["premises"],
                    "evidence_refs": ["evidence:" + evidence.id] if evidence else [], "reason": reason}
            item["required"] = bool(claim["required"] and claim["applicable"])
            by_id[cid] = item
            result.append(item)
            del waiting[cid]
    return sorted(result, key=lambda x: x["claim_id"]), diags


@contextmanager
def _wall_bound(seconds: int):
    if threading.current_thread() is not threading.main_thread():
        raise _fail("VERIFIER_FAILURE", "bounded clean builds require the supervisor main thread")
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    def expired(_signal, _frame):
        raise _fail("CLEAN_BUILD_FAILURE", "complete clean build exceeded its frozen total wall-clock bound")
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)


def clean_build(pkg: Package, label: str, selection: dict, claims: list[dict], roots: dict,
                selected: dict[str, Evidence]) -> dict:
    with _wall_bound(selection["build_policy"]["total_timeout_seconds"]):
        return _clean_build(pkg, label, selection, claims, roots, selected)


def _clean_build(pkg: Package, label: str, selection: dict, claims: list[dict], roots: dict,
                selected: dict[str, Evidence]) -> dict:
    """One complete from-source contract and semantic build; no accepted module reuse."""
    from . import vscore3 as vscore

    started = time.monotonic()
    imported = import_contract(pkg.root)
    _check_preparation(pkg, selection, imported)
    ctx = checker.load_context(pkg.root / "bridges" / selection["bridge_id"], selection["bridge_id"], selection["edge_id"])
    # import_contract executed acceptance and re-export in a fresh private package
    # and compared every byte. Feed that current replay's exact module into the
    # fresh VSCore build, rather than the stored module selected by load_context.
    module_ref = imported.certificate["artifacts"]["olean"]["path"]
    ctx = replace(ctx, contract_module=imported.files[module_ref], accepted_ir=imported.ir,
                  acceptance=imported.certificate)
    spec = checker.derive_goal(ctx)
    tc = leanbridge.resolve_toolchain(ctx.acceptance["toolchain"]["pin"])
    build = checker.run_build(tc, ctx, spec)
    vscore._require_selected_readable(ctx, spec, build)
    readable = _readable_output(build)
    if build.proposition_hash != ctx.edge["expected_proposition_hash"]:
        raise _fail("STATEMENT_MISMATCH", "fresh build proved a different derived proposition")
    with fsutil.temporary_directory(prefix="verislop-closure-certificate-") as temporary:
        fresh = checker.outputs(ctx, spec, build, build, pkg.run_id, Path(temporary))
    accepted_dir = pkg.root / "bridges" / selection["bridge_id"] / checker.SEMANTIC_DIR / checker.edge_key(selection["edge_id"])
    stored_certificate = canonical.load_file(accepted_dir / checker.CERTIFICATE)
    fresh_certificate = canonical.loads(fresh[checker.CERTIFICATE])
    if checker._certificate_descriptor(stored_certificate) != checker._certificate_descriptor(fresh_certificate):
        raise _fail("NONDETERMINISM", "fresh execution differs from complete pre-existing semantic certificate")
    if fresh_certificate.get("readable_support") != (readable["descriptor"] if readable is not None else None):
        raise _fail("STATEMENT_MISMATCH", "fresh support descriptor differs from its checked build")
    if readable is not None:
        stored_refs = checker.readable_artifact_refs(readable["descriptor"],
                                                     lambda path: (accepted_dir / path).read_bytes())
        if stored_refs != readable["artifacts"]:
            raise _fail("NONDETERMINISM", "fresh readable artifact membership differs from frozen support")
    for path in (checker.IR_FILE, "goal/VeriSlopBridgeGoal.lean", "builds/A.json", "builds/B.json",
                 *(entry["path"] for entry in stored_certificate["accepted_modules"]),
                 *(sorted(readable["artifacts"]) if readable is not None else [])):
        if fresh[path] != (accepted_dir / path).read_bytes():
            raise _fail("NONDETERMINISM", f"fresh execution differs from pre-existing {path}")
    inventory = vscore.materialization_inventory(ctx, spec, build)
    stored_inventory = _json(pkg, "implementation/materialization.json")
    # The backend's materialization record may wrap its checked inventory.
    expected_inventory = stored_inventory.get("inventory", stored_inventory)
    if inventory != expected_inventory:
        raise _fail("IR_REIFICATION_MISMATCH", "fresh materialization/type/adapter inventory differs from the frozen output")
    link, link_diags = vscore.checked_link(pkg)
    if link_diags or link is None:
        raise checker.EdgeFailure(link_diags or [Diagnostic("UNMAPPED_IMPLEMENTATION_OBJECT", "no checked link")])
    outcomes, diags = _nonfinal(pkg, selection, claims, roots, selected)
    if diags:
        raise checker.EdgeFailure(diags)
    if (pkg.root / "implementation/program.vscore.json").read_bytes() != spec.source_bytes:
        raise _fail("INPUT_MUTATION", "delivered source is not the selected semantic source")
    elapsed = time.monotonic() - started
    if elapsed > selection["build_policy"]["total_timeout_seconds"]:
        raise _fail("CLEAN_BUILD_FAILURE", f"build {label} exceeded its frozen total wall-clock limit")
    outputs = {
        "contract_receipt": imported.replay_receipt,
        "contract_artifacts": imported.certificate["artifacts"],
        "contract_obligations": imported.certificate["obligations"],
        "accepted_ir": canonical.digest(imported.files[imported.ir_path]),
        "semantic_build": build.observation,
        "goal": canonical.digest(spec.text.encode()),
        "semantic_certificate": checker._certificate_descriptor(fresh_certificate),
        "implementation_ir": canonical.digest(fresh[checker.IR_FILE]),
        "module_parts": {m: {suffix: canonical.digest(data) for suffix, data in sorted(parts.items())}
                         for m, parts in sorted(build.modules.items())},
        "materialization_inventory": inventory, "link_record": link,
        "nonfinal_outcomes": [{k: v for k, v in entry.items() if k not in ("evidence_refs", "reason")}
                              for entry in outcomes],
        "provenance_graph": [{"claim_id": c["claim_id"], "premises": c["premises"],
                              "verifier": c.get("verifier", c.get("verifier_id")), "root_kind": c["root_kind"],
                              "input_root": roots.get(c["root_kind"]), "scope": c["scope"],
                              "trusted_dependencies": c["trusted_dependencies"]}
                             for c in claims if not _terminal(c) and c["required"]],
        "readable_support": readable,
    }
    artifacts = {"goal/VeriSlopBridgeGoal.lean": spec.text.encode(), "implementation-ir.json": fresh[checker.IR_FILE]}
    artifacts.update({"semantic/" + path: data for path, data in fresh.items()})
    for module, parts in build.modules.items():
        for suffix, data in parts.items():
            artifacts["modules/" + leanbridge.module_relpath(module) + suffix] = data
    for role, reference in imported.certificate["artifacts"].items():
        artifacts["contract/" + role] = imported.files[reference["path"]]
    result = BuildObservation({"build": label, "ok": True, "errors": [], "closure_root": roots["closure_root"],
            "producer": {"verifier_id": VERIFIER, "verifier_hash": verifier_hash(VERIFIER)},
            "outputs": outputs, "execution": {"wall_ms": int(elapsed * 1000)}})
    result.artifacts = artifacts
    return result


class BuildObservation(dict):
    """JSON observation with private bytes retained until atomic publication."""
    artifacts: dict[str, bytes]


def _readable_output(build: checker.Build) -> dict | None:
    """Complete deterministic support projection; process telemetry is separate."""
    descriptor = getattr(build, "readable_support", None)
    artifacts = getattr(build, "readable_artifacts", {})
    if descriptor is None:
        if artifacts:
            raise _fail("ORPHAN_CLAIM", "legacy build contains unselected readable artifacts")
        return None
    refs = checker.readable_artifact_refs(descriptor, artifacts.__getitem__)
    if refs != {path: canonical.digest(data) for path, data in sorted(artifacts.items())}:
        raise _fail("ORPHAN_CLAIM", "checked readable artifact inventory differs from its complete manifest")
    return {"descriptor": descriptor, "artifacts": refs}


def _validate_retained_readable(reader: PackageReader, prefix: str, expected: set[str],
                                envelope: dict, readable: dict | None) -> None:
    """Bind every support byte to both the semantic envelope and execution inventory."""
    if readable is None:
        if envelope.get("readable_support") is not None:
            raise _fail("STATEMENT_MISMATCH", "retained support is missing from the clean build observation")
        return
    if envelope.get("readable_support") != readable["descriptor"]:
        raise _fail("STATEMENT_MISMATCH", "retained support descriptor differs from the semantic envelope")
    support_refs = checker.readable_artifact_refs(
        readable["descriptor"], lambda path: reader.read(prefix + "semantic/" + path, keep=True).data)
    if support_refs != readable["artifacts"]:
        raise _fail("ORPHAN_CLAIM", "retained support artifact inventory differs from its complete manifest")
    for path, digest in support_refs.items():
        full_path = prefix + "semantic/" + path
        if full_path not in expected or reader.read(full_path).sha256 != digest:
            raise _fail("ORPHAN_CLAIM", "retained readable artifacts omit or change " + full_path)


def _check_preparation(pkg: Package, selection: dict, imported) -> None:
    """Reconstruct every structural descriptor from this build's fresh import."""
    bundle = pkg.root / "bridges" / selection["bridge_id"]
    reader = PackageReader(bundle)
    try:
        proposal, proposal_snap = reader.json("proposal.json")
        candidates = {a["path"]: reader.read("candidate-inputs/" + a["path"], keep=True).data
                      for a in proposal["artifacts"]}
        fresh, plan, _ = prepare._assemble(imported, proposal, proposal_snap.data, candidates)
        for path in ("plan.json", "artifacts.json"):
            if fresh[path] != reader.read(path, keep=True).data:
                raise _fail("INPUT_MUTATION", "selected structural bridge differs from the current source replay")
        cert, _ = reader.json(prepare.CERTIFICATE)
        receipt, receipt_snap = reader.json(prepare.RECEIPT)
        identity = prepare._import_identity(imported)
        if (receipt != imported.replay_receipt or receipt_snap.sha256 != identity["receipt_sha256"] or
                cert["contract_import"] != identity or cert["bridge_id"] != selection["bridge_id"] or
                cert["plan_hash"] != selection["plan_hash"] or cert["artifacts_hash"] != selection["artifacts_hash"] or
                cert["accepted_ir_hash"] != plan["accepted_ir"] or
                cert["acceptance_certificate_hash"] != plan["acceptance_certificate"] or
                cert["checker"] != {"verifier_id": prepare.VERIFIER, "verifier_hash": verifier_hash(prepare.VERIFIER)}):
            raise _fail("STALE_OR_UNBOUND_EVIDENCE", "complete preparation certificate differs from the fresh checked bridge")
        evidence = _evidence(reader, cert["evidence"])
        expected = {"plan_hash": selection["plan_hash"], "artifacts_hash": selection["artifacts_hash"],
                    "bridge_id": selection["bridge_id"], "contract_import": identity,
                    "assigns_end_to_end_verified": False, "pending_semantic_claims": [selection["edge_claim_id"]]}
        if (cert["pending_semantic_claims"] != expected["pending_semantic_claims"] or
                any(evidence.result.get(k) != v for k, v in expected.items())):
            raise _fail("STALE_OR_UNBOUND_EVIDENCE", "structural evidence is not bound to its complete preparation result")
        reader.recheck()
    finally:
        reader.close()


def _endpoint(pkg: Package, selection: dict, claims: list[dict]) -> list[Diagnostic]:
    from . import vscore3 as vscore

    diags: list[Diagnostic] = []
    accepted = _json(pkg, "accepted/accepted-ir.json")
    required = {oid for oid, rec in accepted["obligations"].items()
                if rec["required"] and rec["role"] == "guarantee" and applicability(rec)["END_TO_END_VERIFIED"][0]}
    covered = {rec["id"] for rec in selection["covered"]}
    e2e = {c["obligation"] for c in claims if c.get("milestone") == "END_TO_END_VERIFIED" and c["applicable"] and c["required"]}
    if required != covered or e2e != required:
        diags.append(Diagnostic("ORPHAN_CLAIM", "selection and E2E graph must cover exactly the required implementation guarantees"))
    if selection["backend"].get("endpoint") != target.ENDPOINT or selection["test_policy"]["require_tests"]:
        diags.append(Diagnostic("UNSUPPORTED_CAPABILITY", "closure supports exactly restricted_source without a required campaign"))
    if fsutil.list_files(pkg.root / "implementation") != ["materialization.json", "program.vscore.json"]:
        diags.append(Diagnostic("SCOPE_LEAK", "implementation contains undeclared executable/source artifacts"))
    _, link_diags = vscore.checked_link(pkg)
    diags.extend(link_diags)
    return diags


def _record_summary(claim: dict, evidence: Evidence, roots: dict) -> dict:
    return {"claim_id": claim["claim_id"], "outcome": "PASS" if evidence.status == "PASS" else "FAIL",
            "required": claim["required"], "verifier": claim.get("verifier", claim.get("verifier_id")),
            "root_kind": claim["root_kind"], "input_root": roots.get(claim["root_kind"]),
            "premises": claim["premises"], "evidence_refs": ["evidence:" + evidence.id],
            "reason": evidence.result.get("reason", "registered closure execution")}


def validate_execution(directory: Path, *, expected_root: str | None = None,
                       frozen_claims: list[dict] | None = None, expected_roots: dict | None = None) -> dict:
    """Validate exact publication membership and evidence before exposing a result."""
    reader = PackageReader(directory)
    try:
        result, _ = reader.json("mechanical-result.json")
        issues = schemas.validate("mechanical-result-v3", result)
        if issues:
            raise _fail("INPUT_MUTATION", f"mechanical result: {issues[0]}")
        if expected_root is not None and result["closure_root"] != expected_root:
            raise _fail("STALE_OR_UNBOUND_EVIDENCE", "mechanical execution is bound to a different closure root")
        inventory_paths = [row["path"] for row in result["execution_inventory"]]
        if inventory_paths != sorted(set(inventory_paths)):
            raise _fail("INPUT_MUTATION", "mechanical execution inventory paths must be unique and sorted")
        claim_ids = [item["claim_id"] for item in result["claims"]]
        if claim_ids != sorted(set(claim_ids)):
            raise _fail("ORPHAN_CLAIM", "mechanical outcome claim IDs must be unique and sorted")
        expected = {"mechanical-result.json"} | set(inventory_paths)
        if set(fsutil.list_files(directory)) != expected:
            raise _fail("INPUT_MUTATION", "mechanical execution inventory does not cover its exact files")
        for row in result["execution_inventory"]:
            snap = reader.read(row["path"])
            if (snap.size, snap.sha256) != (row["size"], row["sha256"]):
                raise _fail("INPUT_MUTATION", f"mechanical execution artifact {row['path']} changed")
        store = EvidenceStore(directory, result["closure_id"])
        records = {ev.claim_id: ev for ev in store.load()}
        frozen = {c["claim_id"]: c for c in (frozen_claims or [])}
        if frozen_claims is not None:
            expected_claims = {c["claim_id"] for c in frozen_claims}
            if {c["claim_id"] for c in result["claims"]} != expected_claims:
                raise _fail("ORPHAN_CLAIM", "mechanical result omits or invents frozen claims")
        for item in result["claims"]:
            if frozen_claims is not None:
                claim = frozen[item["claim_id"]]
                if (item["required"] != bool(claim["required"] and claim["applicable"]) or
                        item["verifier"] != claim.get("verifier", claim.get("verifier_id")) or
                        item["root_kind"] != claim["root_kind"] or item["premises"] != claim["premises"] or
                        (expected_roots is not None and item["input_root"] != expected_roots.get(claim["root_kind"]))):
                    raise _fail("ORPHAN_CLAIM", "mechanical outcome changes frozen requiredness, issuer, root or premises")
            if item["claim_id"] in FINAL_PREDICATES or item["claim_id"].startswith("END_TO_END_VERIFIED:"):
                if not item["required"] and not item["evidence_refs"]:
                    if item["outcome"] not in ("PENDING", "NOT_APPLICABLE"):
                        raise _fail("STALE_OR_UNBOUND_EVIDENCE", "unselected E2E claim has an invented outcome")
                    continue
                ev = records.get(item["claim_id"])
                if (not ev or not ev.valid or ev.record["input_root_hash"] != result["closure_root"] or
                        ev.record["verifier_id"] != VERIFIER or ev.record["verifier_hash"] != verifier_hash(VERIFIER) or
                        ev.record["closure_id"] != result["closure_id"] or
                        item["evidence_refs"] != ["evidence:" + ev.id]):
                    raise _fail("STALE_OR_UNBOUND_EVIDENCE", "terminal execution evidence is missing or unbound")
                if item["outcome"] == "PASS" and (ev.status != "PASS" or ev.record["exit_code"] != 0):
                    raise _fail("STALE_OR_UNBOUND_EVIDENCE", "terminal PASS differs from actual execution status")
                if frozen_claims is not None:
                    claim = frozen[item["claim_id"]]
                    assessed = evaluate_claim(claim, [ev], {"closure_root": result["closure_root"]}, "closure_root")
                    if assessed.outcome != item["outcome"] or claim["premises"] != item["premises"]:
                        raise _fail("STALE_OR_UNBOUND_EVIDENCE", "terminal typed result differs from frozen predicate/prerequisites")
                if (item["claim_id"].startswith("END_TO_END_VERIFIED:") and ev.status == "PASS" and
                        result["mechanical_status"] != "VERIFIED"):
                    raise _fail("STALE_OR_UNBOUND_EVIDENCE", "unverified execution contains E2E PASS")
                if item["claim_id"] in FINAL_PREDICATES:
                    nonfinal = [c for c in result["claims"] if c["claim_id"] not in FINAL_PREDICATES
                                and not c["claim_id"].startswith("END_TO_END_VERIFIED:")]
                    if (ev.result.get("builds") != result["builds"] or
                            ev.result.get("determinism") != result["determinism"] or
                            ev.result.get("nonfinal_claims") != nonfinal):
                        raise _fail("STALE_OR_UNBOUND_EVIDENCE", "terminal evidence differs from the retained checked observations")
        if result["mechanical_status"] == "VERIFIED":
            if (any(c["required"] and c["outcome"] != "PASS" for c in result["claims"]) or
                    result["diagnostics"] or len(result["builds"]) != 2 or
                    not all(b["ok"] for b in result["builds"]) or result["determinism"]["mismatches"] or
                    result["dependencies"]["undeclared"]):
                raise _fail("STALE_OR_UNBOUND_EVIDENCE", "VERIFIED result contradicts its mechanical outputs")
            if result["determinism"]["compared"] != list(COMPARISON_SLOTS):
                raise _fail("ORPHAN_CLAIM", "complete deterministic comparison projection is absent")
            if [b["build"] for b in result["builds"]] != ["A", "B"]:
                raise _fail("ORPHAN_CLAIM", "two independent labeled build observations are required")
            for build in result["builds"]:
                label, outputs = build["build"], build["outputs"]
                if (build["closure_root"] != result["closure_root"] or
                        build["producer"] != {"verifier_id": VERIFIER, "verifier_hash": verifier_hash(VERIFIER)}):
                    raise _fail("STALE_OR_UNBOUND_EVIDENCE", "clean build producer or input root differs from its registered execution")
                if set(outputs["module_parts"]) != set(target.library_sources()) | {
                        target.CONTRACT_MODULE, target.GOAL_MODULE, target.PROOF_MODULE}:
                    raise _fail("UNDECLARED_DEPENDENCY", "complete compiled module inventory is absent or contains undeclared modules")
                if outputs["semantic_build"]["modules"] != {
                        module: canonical.digest_json(parts) for module, parts in sorted(outputs["module_parts"].items())}:
                    raise _fail("IR_REIFICATION_MISMATCH", "retained module parts differ from the complete checked compilation inventory")
                prefix = "builds/" + label + "/"
                if set(outputs) != set(COMPARISON_SLOTS):
                    raise _fail("ORPHAN_CLAIM", "clean build omits a required output observation")
                if reader.json("builds/" + label + ".json")[0] != build:
                    raise _fail("INPUT_MUTATION", "build result differs from its retained exact observation")
                refs = {prefix + "goal/VeriSlopBridgeGoal.lean": outputs["goal"],
                        prefix + "implementation-ir.json": outputs["implementation_ir"]}
                for module, parts in outputs["module_parts"].items():
                    for suffix, digest in parts.items():
                        refs[prefix + "modules/" + leanbridge.module_relpath(module) + suffix] = digest
                refs.update({prefix + "contract/" + role: reference["sha256"]
                             for role, reference in outputs["contract_artifacts"].items()})
                for path, digest in refs.items():
                    if path not in expected or reader.read(path).sha256 != digest:
                        raise _fail("ORPHAN_CLAIM", "retained build artifacts omit or change " + path)
                envelope = reader.json(prefix + "semantic/certificate.json")[0]
                if checker._certificate_descriptor(envelope) != outputs["semantic_certificate"]:
                    raise _fail("STATEMENT_MISMATCH", "retained semantic envelope differs from its complete checked payload")
                _validate_retained_readable(reader, prefix, expected, envelope, outputs["readable_support"])
            if result["builds"][0]["outputs"] != result["builds"][1]["outputs"]:
                raise _fail("NONDETERMINISM", "retained complete clean-build outputs disagree")
            for item in result["claims"]:
                if item["claim_id"] in FINAL_PREDICATES or item["claim_id"].startswith("END_TO_END_VERIFIED:"):
                    continue
                for reference in item["evidence_refs"]:
                    eid = reference.removeprefix("evidence:")
                    record = reader.json("consumed/" + eid + "/record.json")[0]
                    raw = reader.read("consumed/" + eid + "/raw.json", keep=True)
                    body = {k: v for k, v in record.items() if k != "evidence_id"}
                    if (record["evidence_id"] != eid or "ev-" + canonical.sha256_hex(canonical.dumps(body))[:32] != eid or
                            raw.sha256 != record["raw_result_hash"] or record["claim_id"] != item["claim_id"]):
                        raise _fail("STALE_OR_UNBOUND_EVIDENCE", "retained consumed evidence is not bound to its projected claim")
        reader.recheck()
        return result
    finally:
        reader.close()


def mechanical_snapshot(pkg: Package) -> dict | None:
    current = pkg.root / "closure/current.json"
    if not current.is_file():
        return None
    pointer = _json(pkg, "closure/current.json")
    rel = pointer["mechanical_result"]
    fsutil.check_relpath(rel)
    problems = validate_frozen(pkg)
    if problems:
        raise _fail("INPUT_MUTATION", problems[0].message)
    root = closure_input_root(pkg)
    result = validate_execution((pkg.root / rel).parent, expected_root=root, frozen_claims=_claims(pkg),
                                expected_roots=_roots(pkg, _selection(pkg), root))
    result["mechanical_result_path"] = rel
    return result


def run(pkg: Package, events: EventSink, *, endpoint: str | None = None,
        require_state: str | None = None, config: Path | None = None) -> StageResult:
    from . import vscore3_release as vscore_release

    events.emit("stage_started", "verify", "frozen VSCore closure: two complete source rebuilds")
    diags = freeze(pkg)
    builds: list[dict] = []
    determinism = {"compared": list(COMPARISON_SLOTS), "mismatches": [],
                   "excluded_nondeterministic_fields": ["/execution/wall_ms"]}
    try:
        selection = _selection(pkg)
        claims = _claims(pkg)
        params = _json(pkg, "closure/implementation-claims.json")["parameters"]
        root = closure_input_root(pkg)
        plan = _json(pkg, "closure/plan.json")
        roots = _roots(pkg, selection, root)
        selected = _selected_evidence(pkg, selection, claims, roots)
        nonfinal, provenance_diags = _nonfinal(pkg, selection, claims, roots, selected)
        diags.extend(provenance_diags)
        diags.extend(_endpoint(pkg, selection, claims))
        normalized_endpoint = endpoint.replace("-", "_") if endpoint else target.ENDPOINT
        if normalized_endpoint != target.ENDPOINT:
            diags.append(Diagnostic("UNSUPPORTED_CAPABILITY", "requested endpoint differs from the frozen restricted_source endpoint"))
        if require_state and require_state != params["require_state"]:
            diags.append(Diagnostic("CLAIM_MUTATION", "requested lifecycle requirement differs from the frozen closure policy"))
        if not root:
            diags.append(Diagnostic("INPUT_MUTATION", "current closure root is unavailable"))
        if not diags:
            # Copy the frozen source/evidence inputs into one read-only snapshot.
            # Both builds read this snapshot; each then executes fresh acceptance
            # and fresh VSCore compilation in independent temporary directories.
            with fsutil.temporary_directory(prefix="verislop-frozen-closure-") as temporary:
                snapshot_root = Path(temporary)
                manifest = _json(pkg, "closure/manifest.json")
                fsutil.copy_files(pkg.root, snapshot_root, [row["path"] for row in manifest["entries"]])
                snapshot_meta = {"schema_version": "0.1", "artifact_kind": "run_package", "run_id": pkg.run_id, "artifacts": {}}
                from .. import source_policy
                if source_policy.context(pkg) is not None:
                    snapshot_meta["source_policy"] = dict(pkg.meta()["source_policy"])
                fsutil.write_json(snapshot_root / "package.json", snapshot_meta)
                snapshot = Package(snapshot_root)
                snapshot_selected = _selected_evidence(snapshot, selection, claims, roots)
                fsutil.make_readonly_tree(snapshot_root)
                for label in ("A", "B"):
                    events.emit("progress", "verify", f"complete clean source build {label}")
                    try:
                        builds.append(clean_build(snapshot, label, selection, claims, roots, snapshot_selected))
                    except (checker.EdgeFailure, InvalidPackage, VeriSlopError, OSError, ValueError, KeyError) as exc:
                        errors = _diagnostics(exc)
                        diags.extend(errors)
                        diags.append(Diagnostic("CLEAN_BUILD_FAILURE", f"complete build {label} failed"))
                        builds.append({"build": label, "ok": False, "errors": [d.message for d in errors]})
            if len(builds) == 2 and all(b["ok"] for b in builds):
                for slot in COMPARISON_SLOTS:
                    a, b = builds[0]["outputs"].get(slot), builds[1]["outputs"].get(slot)
                    if a is None or b is None or canonical.dumps(a) != canonical.dumps(b):
                        determinism["mismatches"].append({"output": slot, "build_A": a, "build_B": b})
                        diags.append(Diagnostic("NONDETERMINISM", f"complete builds differ or omit required {slot}"))
        diags.extend(validate_frozen(pkg))
        final_ok = {
            "CLOSURE:clean-builds": len(builds) == 2 and all(b["ok"] for b in builds),
            "CLOSURE:determinism": len(builds) == 2 and all(b["ok"] for b in builds) and not determinism["mismatches"],
            "CLOSURE:provenance": not provenance_diags and not diags,
            "CLOSURE:endpoint": not diags,
        }
        status = {"PASS": "VERIFIED", "BLOCKED": "BLOCKED", "INFRASTRUCTURE_FAILURE": "INFRASTRUCTURE_FAILURE"}[status_from(diags)]
        attempt = "attempt-" + secrets.token_hex(12)
        by_id = {c["claim_id"]: c for c in claims}
        with fsutil.temporary_directory(prefix="verislop-terminal-") as temporary:
            stage = Path(temporary)
            store = EvidenceStore(stage, plan["closure_id"], sequence_base=len(pkg.evidence.load()))
            terminal = []
            for cid, ok in final_ok.items():
                claim = by_id[cid]
                ev = store.record(claim_id=cid, verifier_id=VERIFIER, status="PASS" if ok else "BLOCK",
                    scope=["restricted_source; vscore/0.3", f"closure root {root}"], input_root=root or "sha256:" + "0" * 64,
                    result={"format": FINAL_PREDICATES[cid], "milestone_outcome": "PASS" if ok else "FAIL",
                            "binding_root": "closure_root", "predicate_satisfied": ok, "builds": builds,
                            "determinism": determinism, "nonfinal_claims": nonfinal,
                            "required_claim_ids": [c["claim_id"] for c in claims if c["required"]],
                            "endpoint": target.ENDPOINT, "complete_required_coverage": not diags,
                            "declared_dependencies": True, "public_provenance_complete": not provenance_diags,
                            "output_plan_complete": True}, invocation=["verislop", "verify"])
                terminal.append(_record_summary(claim, ev, roots))
            outcomes = {c["claim_id"]: c["outcome"] for c in nonfinal + terminal}
            for claim in claims:
                if claim.get("milestone") != "END_TO_END_VERIFIED":
                    continue
                if not claim["applicable"] or not claim["required"]:
                    terminal.append({"claim_id": claim["claim_id"],
                        "outcome": "PENDING" if claim["applicable"] else "NOT_APPLICABLE", "required": False,
                        "verifier": claim["verifier"], "root_kind": claim["root_kind"],
                        "input_root": roots.get(claim["root_kind"]), "premises": claim["premises"],
                        "evidence_refs": [], "reason": claim["reason"]})
                    continue
                ok = status == "VERIFIED" and all(outcomes.get(p) == "PASS" for p in claim["premises"])
                ev = store.record(claim_id=claim["claim_id"], verifier_id=VERIFIER, status="PASS" if ok else "BLOCK",
                    scope=["restricted_source; vscore/0.3", f"closure root {root}"], input_root=root or "sha256:" + "0" * 64,
                    result={"format": "vscore-end-to-end/0.3", "milestone_outcome": "PASS" if ok else "FAIL",
                            "binding_root": "closure_root", "endpoint": target.ENDPOINT, "language": target.LANGUAGE,
                            "semantic_acceptance": ok, "complete_mechanical_closure": ok,
                            "obligation": claim["obligation"], "revision": claim.get("revision"),
                            "accepted_statement_hash": claim.get("accepted_statement_hash"),
                            "premises": [{"claim_id": p, "outcome": outcomes.get(p)} for p in claim["premises"]]},
                    invocation=["verislop", "verify"])
                terminal.append(_record_summary(claim, ev, roots))
            all_results = sorted(nonfinal + terminal, key=lambda c: c["claim_id"])
            for claim in claims:
                if claim["required"] and claim["applicable"] and not any(r["claim_id"] == claim["claim_id"] and r["outcome"] == "PASS" for r in all_results):
                    if status == "VERIFIED":
                        raise _fail("ORPHAN_CLAIM", "staged graph omits a required successful claim")
            for label, build in zip(("A", "B"), builds):
                fsutil.write_json(stage / "builds" / (label + ".json"), build, once=True)
                for path, data in getattr(build, "artifacts", {}).items():
                    fsutil.write_once(stage / "builds" / label / path, data)
            for evidence in selected.values():
                record, raw = _evidence_bytes(pkg, selection, evidence)
                fsutil.write_once(stage / "consumed" / evidence.id / "record.json", record)
                fsutil.write_once(stage / "consumed" / evidence.id / "raw.json", raw)
            inventory = [{"path": rel, "role": "mechanical-output", "size": (stage / rel).stat().st_size,
                          "sha256": result_hash(stage / rel)} for rel in fsutil.list_files(stage)]
            tcb = _json(pkg, "closure/tcb.json")
            result = {"schema_version": "0.2", "format": "verislop.mechanical-result/0.2", "closure_id": plan["closure_id"],
                "attempt_id": attempt, "closure_root": root or "sha256:" + "0" * 64, "mechanical_status": status,
                "backend": selection["backend"], "endpoint": target.ENDPOINT, "parameters": params,
                "claims": all_results, "builds": builds, "determinism": determinism,
                "provenance": [{"claim_id": c["claim_id"], "outcome": c["outcome"], "evidence": c["evidence_refs"],
                                "verifier": c["verifier"], "reason": c["reason"]} for c in all_results if c["required"]],
                "dependencies": {"verified": tcb["verified"], "trusted": tcb["trusted"], "undeclared": []},
                "boundary": {"verified_surface": ["exact delivered source bytes, normative Lean decoding, checked types, evaluator and transported required accepted properties"],
                             "trusted_surface": tcb["trusted"], "excluded_surface": EXCLUDED,
                             "interpretation": "VERIFIED applies only to the frozen finite restricted-source surface under the declared TCB."},
                "diagnostics": [d.to_json() for d in diags], "execution_inventory": inventory}
            fsutil.write_json(stage / "mechanical-result.json", result, once=True)
            validate_execution(stage, expected_root=root, frozen_claims=claims, expected_roots=roots)
            final_input_diags = validate_frozen(pkg)
            if final_input_diags or closure_input_root(pkg) != root:
                raise checker.EdgeFailure(final_input_diags or [Diagnostic("INPUT_MUTATION", "closure inputs changed before publication")])
            # No E2E record has been visible before this single atomic publication.
            publish_into(pkg.root, ["closure", "executions"], attempt,
                         {rel: (stage / rel).read_bytes() for rel in fsutil.list_files(stage)})
        result_path = f"closure/executions/{attempt}/mechanical-result.json"
        fsutil.write_json(pkg.root / "closure/current.json", {"mechanical_result": result_path})
        pkg.reset_evidence_cache()
        result["mechanical_result_path"] = result_path
        return vscore_release.finalize(pkg, events, result, config=config, endpoint=endpoint, require_state=require_state)
    except (checker.EdgeFailure, InvalidPackage, VeriSlopError, OSError, ValueError, KeyError) as exc:
        diags.extend(_diagnostics(exc))
        result = StageResult("verify", status_from(diags), "finite VSCore restricted-source closure")
        result.diagnostics = diags
        result.summary = {"mechanical_status": "INFRASTRUCTURE_FAILURE" if result.status == "INFRASTRUCTURE_FAILURE" else "BLOCKED",
                          "terminal_status": "INFRASTRUCTURE_FAILURE" if result.status == "INFRASTRUCTURE_FAILURE" else "BLOCKED",
                          "closure_root": closure_input_root(pkg)}
        return result
