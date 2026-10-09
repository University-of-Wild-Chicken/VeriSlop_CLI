"""Authoritative `report.json` and the terminal rendering derived from it (specification §10.4).

The default rendering shows tier, obligation state, proof boundary and remaining trust
together, and never an unqualified application-correctness badge.
"""

from __future__ import annotations

from typing import Any

from . import SCHEMA_VERSION, __version__, canonical
from .errors import Diagnostic
from .lifecycle import MILESTONES
from .package import Package
from .verifiers import TRUST, verifier_hash

TCB = [TRUST[k] for k in ("axioms", "lean", "kernel_tool", "reifier", "orchestration", "sandbox", "os", "nl")]

def _qualified(terminal: str, params: dict[str, Any], diags: list[Diagnostic]) -> str:
    tier = params.get("tier")
    if terminal == "VERIFIED":
        if tier == 0:
            return "VERIFIED closure; implementation assurance: TESTED (Tier 0)"
        if tier == 1:
            tested = params.get("require_tests")
            return "VERIFIED closure; implementation assurance: runtime-monitored (detection)" + (" + TESTED" if tested else "") + " (Tier 1)"
        if tier == 2:
            return "VERIFIED closure; END_TO_END_VERIFIED [restricted_source; " + params.get("language", "vscore/0.1") + "]"
        return f"VERIFIED closure (Tier {tier})"
    blocking = sorted({d.code for d in diags if d.severity == "blocking"})
    infra = sorted({d.code for d in diags if d.severity == "infrastructure"})
    if terminal == "INFRASTRUCTURE_FAILURE":
        return f"INFRASTRUCTURE_FAILURE ({', '.join(infra)}); no verification success" + (f"; claim failures also observed: {', '.join(blocking)}" if blocking else "")
    return f"BLOCKED ({', '.join(blocking)}); no verification success"


def build(pkg: Package, view: dict[str, Any], terminal: str, diags: list[Diagnostic], builds: list[dict[str, Any]],
          determinism: dict[str, Any], params: dict[str, Any], requested_ep: str | None, req_state: str | None,
          closure_root: str | None, provenance: list[dict[str, Any]], review: dict[str, Any], ir_hash: str | None,
          bridge_preparations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    cert_p = pkg.path("accepted") / "acceptance.json"
    cert = canonical.load_file(cert_p) if cert_p.is_file() else None
    impl_claims_p = pkg.path("closure") / "implementation-claims.json"
    impl_claims = canonical.load_file(impl_claims_p) if impl_claims_p.is_file() else {"claims": []}
    claims = canonical.load_file(pkg.path("claims"))["claims"] if pkg.path("claims").is_file() else []
    required: dict[str, list[str]] = {}
    for c in claims + impl_claims["claims"]:
        if c["required"] and c["obligation"]:
            required.setdefault(c["obligation"], []).append(c["milestone"])
    tests: dict[str, Any] = {}
    for c in impl_claims["claims"]:
        if c["milestone"] == "TESTED" and c["applicable"]:
            evs = [e for e in pkg.evidence.for_claim(c["claim_id"]) if e.valid]
            if evs:
                tests[c["obligation"]] = evs[-1].result
    requested = pkg.meta().get("requested", {})
    if not isinstance(requested, dict):
        requested = {}
    tier = params.get("tier", requested.get("tier"))
    if tier == 2 and params.get("target", requested.get("target")) == "vscore":
        from .backends.registry import select
        frozen_params = impl_claims.get("parameters", {})
        version = frozen_params.get("backend_version", params.get("backend_version", requested.get("backend_version")))
        descriptor = select(2, "vscore", "restricted_source", version)
        if descriptor:
            # Early pipeline exits have request parameters but no materialized source.
            # Report the exact selected version without assigning any new assurance.
            params = {**params, "backend": descriptor["id"], "language": descriptor["language"],
                      "semantics": descriptor["semantics"], "backend_version": descriptor["backend_version"]}
    obligations: dict[str, Any] = {}
    counts: dict[str, Any] = {"obligations": 0, "required_obligations": 0, "milestones": {m: {} for m in MILESTONES}}
    axioms: dict[str, Any] = {}
    hypotheses: dict[str, Any] = {}
    for oid, rec in sorted(view["obligations"].items()):
        life = rec["lifecycle"]
        counts["obligations"] += 1
        counts["required_obligations"] += int(rec["required"])
        for m in MILESTONES:
            o = life[m]["outcome"]
            counts["milestones"][m][o] = counts["milestones"][m].get(o, 0) + 1
        formal = rec.get("formal") or {}
        proved = life["PROVED"]["outcome"]
        if rec["role"] == "guarantee":
            boundary = (f"PROVED {proved}: Lean reference-model theorem {formal.get('lean_symbol', '?')} "
                        f"(axioms: {', '.join(formal.get('axioms', [])) or 'none'}; hypotheses: {', '.join(formal.get('hypotheses', [])) or 'none'}); "
                        "proves the model, not the implementation")
            axioms[oid] = formal.get("axioms", [])
            hypotheses[oid] = formal.get("hypotheses", [])
        else:
            boundary = f"{rec['role']}: no proposition proved ({life['PROVED']['reason']})"
        t = tests.get(oid)
        if life["TESTED"]["outcome"] == "PASS" and t:
            assurance = (f"TESTED (Tier {tier} campaign seed {t.get('seed')}, {t.get('counts', {}).get('effective')} effective cases; "
                         "finite sampling, not proof)")
        elif life["IMPLEMENTED"]["outcome"] == "NOT_APPLICABLE":
            assurance = "no implementation claim (" + life["IMPLEMENTED"]["reason"] + ")"
        else:
            assurance = f"IMPLEMENTED {life['IMPLEMENTED']['outcome']}, LINKED {life['LINKED']['outcome']}, TESTED {life['TESTED']['outcome']}"
        e2e = life["END_TO_END_VERIFIED"]
        blocking = sorted({d.code for d in diags if oid in d.obligations and d.severity != "warning"})
        obligations[oid] = {
            "role": rec["role"], "kind": rec["kind"], "revision": rec["revision"], "required": rec["required"],
            "state": rec["state"], "outcomes": {m: life[m]["outcome"] for m in MILESTONES},
            "required_milestones": sorted(set(required.get(oid, [])), key=MILESTONES.index),
            "proof_boundary": boundary,
            "implementation_assurance": assurance,
            "weakest_required_bridge": (f"Tier {tier} ({params.get('endpoint')})" if life["IMPLEMENTED"]["outcome"] != "NOT_APPLICABLE" and tier is not None else "none"),
            "end_to_end": f"{e2e['outcome']}: {e2e['reason']}",
            "blocking": blocking,
        }
    trusted: set[str] = set(TCB)
    for e in pkg.evidence.load():
        if e.valid and e.verifier_current:
            trusted.update(e.record["trusted_dependencies"])
    excluded = []
    if pkg.path("claims").is_file():
        for r in canonical.load_file(pkg.path("claims"))["obligations"]:
            if r["role"] == "exclusion":
                excluded.append(f"{r['id']}: {r['statement']}")
    excluded += [
        "machine-code, compiler, runtime and hardware behaviour (no Tier 4 claim)",
        "behaviour on inputs outside the serialization profile",
        "physical time, memory and resource bounds unless stated as obligations",
    ]
    verified = []
    if cert:
        verified += ["Lean kernel replay of every declaration of the accepted module",
                     "statement and definition identity against the frozen challenge",
                     "transitive axiom audit per theorem from the replayed environment",
                     "DSL denotation definitional equality and round trip for reified statements",
                     "concrete non-vacuity witnesses read from accepted proof terms"]
    if ir_hash:
        verified.append(f"accepted IR {ir_hash} reconstructed from the certified environment")
    if any(b.get("ok") for b in builds):
        verified.append("two isolated clean builds compared for declared reproducible outputs")
    if tests:
        verified.append("Tier 0 target campaign executed on hash-verified implementation bytes")
    witnesses = {oid: o["witnesses"] for oid, o in (cert or {}).get("obligations", {}).items() if o.get("witnesses")}
    link_p = pkg.path("bridges") / "link.json"
    mappings = canonical.load_file(link_p)["bindings"] if link_p.is_file() else []
    req = canonical.load_file(pkg.path("request")) if pkg.path("request").is_file() else {}
    routing = canonical.load_file(pkg.path("routing")) if pkg.path("routing").is_file() else {}
    roots = {**pkg.roots(), "closure_input_root": closure_root, "accepted_ir": ir_hash,
             "certificate": canonical.digest(cert_p.read_bytes()) if cert_p.is_file() else None}
    record = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "run_report",
        "run_id": pkg.run_id,
        "terminal_status": terminal,
        "qualified_result": _qualified(terminal, params, diags),
        "generated_by": {"verifier": "verislop.closure", "verifier_hash": verifier_hash("verislop.closure"), "verislop_version": __version__},
        "request": {"request_ref": req.get("request_ref"), "document_hash": req.get("document_hash"),
                    "routing": {k: routing.get(k) for k in ("decision", "routing_result", "classifier")}},
        "roots": roots,
        "tier": {"requested": tier, "endpoint": params.get("endpoint"), "requested_endpoint": requested_ep,
                 "target": params.get("target", requested.get("target")), "require_state": req_state,
                 "tier_default_applied": bool(params.get("tier_default_applied", False))},
        "counts": counts,
        "obligations": obligations,
        "endpoint": {"established": params.get("endpoint"), "requested": requested_ep,
                     "end_to_end_eligible": False,
                     "statement": ("No END_TO_END_VERIFIED claim: Tiers 0 and 1 are ineligible; the endpoint is the recorded test campaign or monitored runtime."
                                   if tier in (0, 1) else
                                   "No END_TO_END_VERIFIED claim: Tier 2 semantic edges can be accepted, but pipeline integration and endpoint closure are not implemented."
                                   if tier == 2 else
                                   "No END_TO_END_VERIFIED claim: semantic bridge backends for Tiers 3 and 4 are unsupported; structural preparation establishes no implementation endpoint.")},
        "mappings": mappings,
        "witnesses": witnesses,
        "builds": builds,
        "determinism": determinism,
        "provenance": provenance,
        "axioms": axioms,
        "hypotheses": hypotheses,
        "surfaces": {"verified": verified, "trusted": sorted(trusted), "excluded": excluded},
        "review": review,
        "bridge_preparations": bridge_preparations or [],
        "blocking_reasons": [d.to_json() for d in diags if d.severity == "blocking"],
        "infrastructure_errors": [d.to_json() for d in diags if d.severity == "infrastructure"],
        "warnings": [d.to_json() for d in diags if d.severity == "warning"],
        "artifacts": {k: v for k, v in {
            "report": pkg.rel(pkg.path("report")), "obligation_view": pkg.rel(pkg.path("view")),
            "accepted_ir": pkg.rel(pkg.path("accepted_ir")) if pkg.path("accepted_ir").is_file() else None,
            "certificate": pkg.rel(cert_p) if cert_p.is_file() else None,
            "implementation": pkg.rel(pkg.path("implementation")) if pkg.path("implementation").is_dir() else None,
            "evidence": "evidence/",
        }.items() if v},
    }
    if tier == 2 and params.get("target", requested.get("target")) == "vscore":
        language = params.get("language", "vscore/0.1")
        semantics = params.get("semantics", "vscore-semantics/0.1")
        required_guarantees = [o for o in obligations.values() if o["required"] and o["role"] == "guarantee"
                               and o["outcomes"]["END_TO_END_VERIFIED"] != "NOT_APPLICABLE"]
        established = bool(required_guarantees) and all(o["outcomes"]["END_TO_END_VERIFIED"] == "PASS" for o in required_guarantees)
        record.update({"schema_version": "0.2", "format": "verislop.run-report/0.2",
                       "backend": params.get("backend", "verislop.backend.vscore/0.1"),
                       "language": language, "semantics": semantics, "closure_id": None,
                       "mechanical_result": None,
                       "mechanical_status": "VERIFIED" if established else "INFRASTRUCTURE_FAILURE" if terminal == "INFRASTRUCTURE_FAILURE" else "BLOCKED",
                       "release_status": "NOT_REQUIRED" if not review.get("configured") else "ACCEPTED" if terminal == "VERIFIED" else "BLOCKED"})
        record["endpoint"] = {"requested": requested_ep, "established": "restricted_source" if established else None,
                              "end_to_end_eligible": True,
                              "statement": f"END_TO_END_VERIFIED [restricted_source; {language}]: exact source under the normative Lean semantics"
                              if established else "restricted_source endpoint not established by complete mechanical closure"}
        from .backends.registry import VSCORE_EXCLUDED, select
        descriptor = select(2, "vscore", "restricted_source", params.get("backend_version"))
        excluded = descriptor["excluded_surfaces"] if descriptor else VSCORE_EXCLUDED

        record["surfaces"]["excluded"] = sorted(set(record["surfaces"]["excluded"] + excluded))
        if established:
            record["surfaces"]["verified"].append("total reference refinement and transported required guarantees for the exact delivered VSCore source")
            for obligation in required_guarantees:
                obligation["implementation_assurance"] += f"; proved correspondence at restricted_source; {language}"
    return record


def render_lines(rep: dict[str, Any]) -> list[str]:
    t = rep["tier"]
    lines = [
        f"RESULT: {rep['qualified_result']}",
        f"tier: {t['requested']} -> endpoint {t['endpoint']} (target {t['target']})"
        + (" [Tier 0 default applied: test evidence only]" if t["tier_default_applied"] else ""),
        "obligations (state is a display projection; see outcomes):",
    ]
    sym = {"PASS": "✓", "FAIL": "✗", "PENDING": "·", "STALE": "s", "UNSUPPORTED": "u", "NOT_APPLICABLE": "–"}
    lines.append("         " + " ".join(m[:4] for m in MILESTONES) + "   (✓ pass ✗ fail · pending s stale u unsupported – n/a)")
    for oid, o in rep["obligations"].items():
        outs = "    ".join(sym[v] for v in o["outcomes"].values())
        lines.append(f"  {oid:<6} {outs}    {o['role']}, state {o['state']}")
        lines.append(f"         proof boundary: {o['proof_boundary']}")
        if o["implementation_assurance"] and not o["implementation_assurance"].startswith("no implementation"):
            lines.append(f"         implementation: {o['implementation_assurance']}")
        if o["blocking"]:
            lines.append(f"         blocking: {', '.join(o['blocking'])}")
    det = rep["determinism"]
    lines.append(f"clean builds: {len(rep['builds'])}; reproducible outputs compared: {', '.join(det.get('compared', [])) or 'none'}; "
                 f"mismatches: {len(det.get('mismatches', []))}")
    lines.append(f"end-to-end: {rep['endpoint']['statement']}")
    for preparation in rep.get("bridge_preparations", []):
        accepted = preparation.get("semantic_certificates") or []
        if accepted:
            covered = sorted({o for c in accepted for o in c.get("obligations", [])})
            pending = preparation.get("pending_semantic_claims") or []
            lines.append(f"bridge {preparation.get('bridge_id', '?')}: {preparation.get('status', 'BLOCKED')}; "
                         f"{len(accepted)} semantic edge(s) accepted by registered checkers "
                         f"(obligations {', '.join(covered)}; {len(pending)} pending); not END_TO_END_VERIFIED")
        else:
            lines.append(f"bridge preparation {preparation.get('bridge_id', '?')}: {preparation.get('status', 'BLOCKED')}; "
                         "structure and accepted-contract replay only; no implementation semantics established")
    lines.append("remaining trust (TCB):")
    lines.extend(f"  - {x}" for x in rep["surfaces"]["trusted"][:12])
    if len(rep["surfaces"]["trusted"]) > 12:
        lines.append(f"  … {len(rep['surfaces']['trusted']) - 12} more in report.json")
    lines.append("excluded: " + "; ".join(rep["surfaces"]["excluded"][:3]))
    return lines
