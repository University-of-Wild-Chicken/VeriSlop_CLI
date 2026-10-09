"""Semantic validation of the draft (a proposal) and of the interpretation ledger.

Structural validity comes from the JSON schemas. This module additionally checks provenance
(document hashes and byte spans against the exact request bytes), identity (unique IDs,
resolvable dependency edges), role/kind consistency, that the candidate claims no lifecycle
milestone beyond INTERPRETED, assumption suppliers, ambiguity decisions and mechanical clause
coverage.
"""

from __future__ import annotations

from typing import Any

from . import canonical, schemas
from .errors import Diagnostic
from .lifecycle import DRAFT_CATEGORIES, MILESTONES, applicability, derive_state
from .segment import SEGMENTER_ID, uncovered

BLOCKING_IMPACTS = {"correctness", "data_loss", "security", "failure_behavior", "numeric_semantics", "formal_boundary"}

# Strong role/kind pairings. Other combinations are permitted but reported.
REQUIRED_ROLE = {"explicit_non_goal": "exclusion", "ambiguity": "open_question"}
EXPECTED_ROLE = {"entity": "declaration", "precondition": "assumption"}


def obligations(draft: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for category in DRAFT_CATEGORIES:
        out.extend(draft.get(category, []))
    return out


def validate_draft(draft: Any, prompt: bytes, request_ref: str, attachments: dict[str, bytes] | None = None) -> list[Diagnostic]:
    diags: list[Diagnostic] = schemas.require_valid("draft", draft, "draft schema")
    if diags:
        return diags
    doc_hash = canonical.digest(prompt)
    if draft["request_ref"] != request_ref:
        diags.append(Diagnostic("INVALID_CANDIDATE", f"draft.request_ref {draft['request_ref']!r} does not name the request {request_ref!r}"))
    seen: dict[str, str] = {}
    records = obligations(draft)
    for rec in records:
        oid = rec["id"]
        if oid in seen:
            diags.append(Diagnostic("INVALID_CANDIDATE", f"duplicate obligation ID {oid}", obligations=[oid]))
        seen[oid] = rec["kind"]
    for rec in records:
        oid = rec["id"]
        kind, role = rec["kind"], rec["role"]
        if kind == "non_vacuity":
            diags.append(Diagnostic("INVALID_CANDIDATE", f"{oid}: non_vacuity obligations are added only by registered formalization rules", obligations=[oid]))
        if kind in REQUIRED_ROLE and role != REQUIRED_ROLE[kind]:
            diags.append(Diagnostic("INVALID_CANDIDATE", f"{oid}: kind {kind} requires role {REQUIRED_ROLE[kind]}", obligations=[oid]))
        if role in ("exclusion", "open_question") and kind not in ("explicit_non_goal", "ambiguity"):
            diags.append(Diagnostic("INVALID_CANDIDATE", f"{oid}: role {role} is reserved for non-goals and ambiguities", obligations=[oid]))
        for src in rec["source_refs"]:
            doc = prompt if src["document_ref"] == request_ref else (attachments or {}).get(src["document_ref"])
            if doc is None:
                diags.append(Diagnostic("INVALID_CANDIDATE", f"{oid}: source ref names {src['document_ref']!r}, which is neither the request nor an attachment", obligations=[oid]))
                continue
            if src["document_hash"] != (doc_hash if doc is prompt else canonical.digest(doc)):
                diags.append(Diagnostic("INPUT_MUTATION", f"{oid}: source ref hash does not match the cited document bytes", obligations=[oid]))
            if not (0 <= src["start_byte"] <= src["end_byte"] <= len(doc)):
                diags.append(Diagnostic("INVALID_CANDIDATE", f"{oid}: source span [{src['start_byte']}, {src['end_byte']}) is outside the request", obligations=[oid]))
            elif src["origin"] == "explicit" and src["start_byte"] == src["end_byte"]:
                diags.append(Diagnostic("INVALID_CANDIDATE", f"{oid}: an explicit source ref needs a non-empty span; mark inferred requirements as inferred", obligations=[oid]))
        for dep in rec["dependencies"]:
            if dep["id"] not in seen:
                diags.append(Diagnostic("INVALID_CANDIDATE", f"{oid}: dependency on unknown obligation {dep['id']}", obligations=[oid]))
            if dep["id"] == oid:
                diags.append(Diagnostic("INVALID_CANDIDATE", f"{oid}: self-dependency", obligations=[oid]))
            if dep["relation"] == "blocked_by" and seen.get(dep["id"]) != "ambiguity":
                diags.append(Diagnostic("INVALID_CANDIDATE", f"{oid}: blocked_by must reference an ambiguity record", obligations=[oid]))
        diags.extend(_check_candidate_lifecycle(rec))
    return diags


def _check_candidate_lifecycle(rec: dict[str, Any]) -> list[Diagnostic]:
    """A draft may only record INTERPRETED; anything stronger is unbound candidate metadata."""
    oid = rec["id"]
    diags: list[Diagnostic] = []
    life = rec["lifecycle"]
    if life["INTERPRETED"]["outcome"] != "PASS":
        diags.append(Diagnostic("INVALID_CANDIDATE", f"{oid}: a draft record exists only after a recorded interpretation (INTERPRETED must be PASS)", obligations=[oid]))
    app = applicability(rec)
    for m in MILESTONES[1:]:
        outcome = life[m]["outcome"]
        if outcome not in ("PENDING", "NOT_APPLICABLE"):
            diags.append(Diagnostic(
                "STALE_OR_UNBOUND_EVIDENCE",
                f"{oid}: candidate claims {m}={outcome}; lifecycle outcomes come only from registered verifier evidence",
                obligations=[oid]))
        if outcome == "NOT_APPLICABLE" and app[m][0] and rec["required"]:
            diags.append(Diagnostic(
                "INVALID_CANDIDATE",
                f"{oid}: required milestone {m} cannot be marked NOT_APPLICABLE for role {rec['role']}",
                obligations=[oid]))
    if rec["state"] != derive_state(life) or rec["state"] != "INTERPRETED":
        diags.append(Diagnostic(
            "STALE_OR_UNBOUND_EVIDENCE",
            f"{oid}: candidate metadata states {rec['state']!r}; a draft cannot carry a state beyond INTERPRETED",
            obligations=[oid]))
    return diags


def validate_ledger(ledger: Any, draft: dict[str, Any], prompt: bytes, request_ref: str) -> tuple[list[Diagnostic], dict[str, Any]]:
    """Returns diagnostics and the mechanical coverage report."""
    diags = schemas.require_valid("interpretation", ledger, "interpretation ledger schema")
    if diags:
        return diags, {}
    req = ledger["request"]
    if req["document_ref"] != request_ref or req["document_hash"] != canonical.digest(prompt) or req["byte_length"] != len(prompt):
        diags.append(Diagnostic("INPUT_MUTATION", "interpretation ledger is bound to different request bytes"))
    records = {r["id"]: r for r in obligations(draft)}
    spans: list[tuple[int, int]] = []
    for i, clause in enumerate(ledger["clauses"]):
        a, b = clause["start_byte"], clause["end_byte"]
        if not (0 <= a < b <= len(prompt)):
            diags.append(Diagnostic("INVALID_CANDIDATE", f"clause {i}: span [{a}, {b}) is not a non-empty span of the request"))
            continue
        spans.append((a, b))
        disp = clause["disposition"]
        if disp == "context":
            if not clause.get("note"):
                diags.append(Diagnostic("INVALID_CANDIDATE", f"clause {i}: explanatory context requires a note"))
            continue
        if not clause["refs"]:
            diags.append(Diagnostic("INVALID_CANDIDATE", f"clause {i}: disposition {disp} needs at least one reference"))
        for ref in clause["refs"]:
            rec = records.get(ref)
            if rec is None:
                diags.append(Diagnostic("INVALID_CANDIDATE", f"clause {i}: unknown obligation {ref}"))
            elif disp == "exclusion" and rec["role"] != "exclusion":
                diags.append(Diagnostic("INVALID_CANDIDATE", f"clause {i}: {ref} is not an exclusion"))
            elif disp == "ambiguity" and rec["role"] != "open_question":
                diags.append(Diagnostic("INVALID_CANDIDATE", f"clause {i}: {ref} is not an ambiguity record"))
            elif disp == "obligations" and rec["role"] in ("exclusion", "open_question"):
                diags.append(Diagnostic("INVALID_CANDIDATE", f"clause {i}: {ref} must use the {'exclusion' if rec['role'] == 'exclusion' else 'ambiguity'} disposition"))
    supplied = {a["id"]: a for a in ledger["assumptions"]}
    for oid, rec in records.items():
        if rec["role"] == "assumption" and oid not in supplied:
            diags.append(Diagnostic("INVALID_CANDIDATE", f"{oid}: an assumption must identify who supplies it and where it is discharged", obligations=[oid]))
    for aid in supplied:
        if aid not in records or records[aid]["role"] != "assumption":
            diags.append(Diagnostic("INVALID_CANDIDATE", f"ledger assumption {aid} does not name an assumption record"))
    amb_records = {oid for oid, r in records.items() if r["kind"] == "ambiguity"}
    amb_ledger = {a["id"]: a for a in ledger["ambiguities"]}
    for oid in amb_records - set(amb_ledger):
        diags.append(Diagnostic("INVALID_CANDIDATE", f"ambiguity {oid} has no alternatives/impact entry in the ledger", obligations=[oid]))
    for aid, amb in amb_ledger.items():
        if aid not in amb_records:
            diags.append(Diagnostic("INVALID_CANDIDATE", f"ledger ambiguity {aid} has no draft ambiguity record"))
        for ref in amb["affected_obligations"]:
            if ref not in records:
                diags.append(Diagnostic("INVALID_CANDIDATE", f"ambiguity {aid}: unknown affected obligation {ref}"))
        alt_ids = [alt["id"] for alt in amb["alternatives"]]
        if len(set(alt_ids)) != len(alt_ids):
            diags.append(Diagnostic("INVALID_CANDIDATE", f"ambiguity {aid}: duplicate alternative IDs"))
        res = amb["resolution"]
        if res["status"] == "resolved":
            if res["selected"] not in alt_ids:
                diags.append(Diagnostic("INVALID_CANDIDATE", f"ambiguity {aid}: selected alternative {res['selected']!r} is not offered"))
            if res["provenance"]["kind"] == "none":
                diags.append(Diagnostic("INVALID_CANDIDATE", f"ambiguity {aid}: a resolution needs provenance"))
        elif res["selected"] is not None:
            diags.append(Diagnostic("INVALID_CANDIDATE", f"ambiguity {aid}: unresolved ambiguity cannot select an alternative"))
    missing = uncovered(prompt, spans)
    coverage = {
        "segmenter": SEGMENTER_ID,
        "clauses": len(ledger["clauses"]),
        "uncovered_segments": [{"start_byte": a, "end_byte": b, "text": prompt[a:b].decode("utf-8")} for a, b in missing],
        "limitation": "accounts for recorded spans only; it cannot prove semantic completeness of the interpretation",
    }
    for a, b in missing:
        diags.append(Diagnostic(
            "UNCOVERED_SOURCE_CLAUSE",
            f"request clause [{a}, {b}) has no disposition: {prompt[a:b].decode('utf-8')[:80]!r}"))
    return diags, coverage


def effective_resolution(amb: dict[str, Any]) -> tuple[bool, str]:
    """(resolved, why). Interpreter defaults may settle only routine ambiguities."""
    res = amb["resolution"]
    if res["status"] != "resolved":
        return False, "unresolved"
    blocking = set(amb["impact"]) & BLOCKING_IMPACTS
    if res["provenance"]["kind"] == "interpreter_default" and blocking:
        return False, f"an agent default cannot resolve an ambiguity affecting {', '.join(sorted(blocking))}"
    return True, f"resolved by {res['provenance']['kind']}: {res['provenance']['detail']}"


def blocked_obligations(draft: dict[str, Any], ledger: dict[str, Any]) -> dict[str, list[str]]:
    """Obligation ID -> ambiguity IDs that block it (dependent guarantees only)."""
    records = {r["id"]: r for r in obligations(draft)}
    out: dict[str, list[str]] = {}
    for amb in ledger["ambiguities"]:
        resolved, _ = effective_resolution(amb)
        if resolved or not (set(amb["impact"]) & BLOCKING_IMPACTS):
            continue
        targets = set(amb["affected_obligations"])
        targets |= {oid for oid, r in records.items() if any(d["relation"] == "blocked_by" and d["id"] == amb["id"] for d in r["dependencies"])}
        for oid in targets:
            if records.get(oid, {}).get("role") == "guarantee":
                out.setdefault(oid, []).append(amb["id"])
    return {k: sorted(v) for k, v in sorted(out.items())}


def apply_resolutions(ledger: dict[str, Any], resolutions: dict[str, str], provenance: str) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    by_id = {a["id"]: a for a in ledger["ambiguities"]}
    for aid, choice in resolutions.items():
        amb = by_id.get(aid)
        if amb is None:
            diags.append(Diagnostic("INVALID_CANDIDATE", f"--resolve names unknown ambiguity {aid}"))
            continue
        if choice not in [alt["id"] for alt in amb["alternatives"]]:
            diags.append(Diagnostic("INVALID_CANDIDATE", f"--resolve {aid}={choice}: not an offered alternative"))
            continue
        amb["resolution"] = {"status": "resolved", "selected": choice,
                             "provenance": {"kind": "user", "detail": provenance}}
    return diags
