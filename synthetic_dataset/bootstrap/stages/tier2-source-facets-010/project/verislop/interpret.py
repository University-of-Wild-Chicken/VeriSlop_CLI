"""`verislop interpret`: route the request and record an explicit interpretation.

The interpreter (an LLM agent or any other candidate source) proposes; this module validates
the proposal against the exact request bytes, records the interpretation ledger, computes
which guarantees are blocked by unresolved ambiguities, and writes INTERPRETED evidence. The
draft is emitted before any implementation generation and is never downstream authority.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

from . import SCHEMA_VERSION, canonical, classify, draft as draftmod, fsutil
from .errors import Diagnostic, UsageError
from .events import EventSink
from .lifecycle import claim_id
from .package import Package
from .stage import StageResult, status_from

VERIFIER = "verislop.interpretation-recorder"


def stage_request(pkg: Package, prompt_file: Path, request_ref: str | None, mode: str,
                  attachments: list[Path] | None = None, repository_revision: str | None = None) -> tuple[bytes, str]:
    """Copy the exact prompt (and immutable attachment) bytes into the package."""
    data = Path(prompt_file).read_bytes()
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        raise UsageError("the prompt must be UTF-8 text") from None
    ref = request_ref or Path(prompt_file).as_posix()
    existing = pkg.path("prompt")
    if existing.is_file() and existing.read_bytes() != data:
        raise UsageError(
            f"package {pkg.root} already holds a different request; start a new run package",
            [Diagnostic("INPUT_MUTATION", "request bytes differ from the package's frozen request")],
        )
    fsutil.write_once(existing, data)
    staged = []
    for a in attachments or []:
        blob = Path(a).read_bytes()
        h = canonical.digest(blob)
        rel = f"request/attachments/{h.split(':')[1][:16]}-{Path(a).name}"
        fsutil.write_once(pkg.root / rel, blob)
        staged.append({"ref": Path(a).as_posix(), "path": rel, "sha256": h, "byte_length": len(blob)})
    request = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "request",
        "request_ref": ref,
        "document_hash": canonical.digest(data),
        "byte_length": len(data),
        "mode": mode,
        "attachments": staged,
        "repository_revision": repository_revision,
    }
    req_path = pkg.path("request")
    if req_path.is_file():
        prev = canonical.load_file(req_path)
        if prev.get("request_ref") != ref:
            raise UsageError(f"package request_ref is {prev.get('request_ref')!r}; pass --request-ref to match")
        if staged and prev.get("attachments") and prev["attachments"] != staged:
            raise UsageError("package attachments differ from the frozen request; start a new run package")
        request = {**prev, "mode": mode, "attachments": prev.get("attachments") or staged,
                   "repository_revision": prev.get("repository_revision") or repository_revision}
    fsutil.write_json(req_path, request, pretty=True)
    return data, ref


def attachment_documents(pkg: Package) -> dict[str, bytes]:
    """Attachment ref -> exact staged bytes (citable by source refs)."""
    req = canonical.load_file(pkg.path("request")) if pkg.path("request").is_file() else {}
    return {a["ref"]: (pkg.root / a["path"]).read_bytes() for a in req.get("attachments", [])}


def route(pkg: Package, prompt: bytes, ref: str, mode: str, resolve_routing: str | None) -> dict[str, Any]:
    routing = classify.forced_software(prompt, ref) if mode == "software" else classify.classify(prompt, ref)
    if routing["decision"] == "UNCERTAIN" and resolve_routing:
        routing["resolution"] = {"selected": resolve_routing, "provenance": "user: --resolve routing=" + resolve_routing}
        routing["routing_result"] = "OBLIGATION_PIPELINE" if resolve_routing == "software" else "NOT_APPLICABLE"
    fsutil.write_json(pkg.path("routing"), routing, pretty=True)
    return routing


def _interactive_resolve(ledger: dict[str, Any], blocked: dict[str, list[str]]) -> dict[str, str]:
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        return {}
    chosen: dict[str, str] = {}
    pending = sorted({a for ids in blocked.values() for a in ids})
    for aid in pending:
        amb = next(a for a in ledger["ambiguities"] if a["id"] == aid)
        sys.stderr.write(f"\nAmbiguity {aid} (impact: {', '.join(amb['impact'])}) affects {', '.join(amb['affected_obligations'])}\n")
        for alt in amb["alternatives"]:
            sys.stderr.write(f"  [{alt['id']}] {alt['description']}\n")
        sys.stderr.write("Choose an alternative (empty leaves it unresolved): ")
        sys.stderr.flush()
        answer = sys.stdin.readline().strip()
        if answer in [alt["id"] for alt in amb["alternatives"]]:
            chosen[aid] = answer
    return chosen


def run(
    pkg: Package,
    events: EventSink,
    prompt_file: Path,
    *,
    mode: str = "auto",
    request_ref: str | None = None,
    candidate: Path | None = None,
    ledger_path: Path | None = None,
    resolutions: dict[str, str] | None = None,
    interactive: bool = False,
    draft_out: Path | None = None,
    agent: Callable[[bytes, str, dict], tuple[dict, dict]] | None = None,
    attachments: list[Path] | None = None,
    repository_revision: str | None = None,
) -> StageResult:
    resolutions = dict(resolutions or {})
    events.emit("stage_started", "interpret", "routing and interpreting the request")
    prompt, ref = stage_request(pkg, prompt_file, request_ref, mode, attachments, repository_revision)
    docs = attachment_documents(pkg)
    routing = route(pkg, prompt, ref, mode, resolutions.pop("routing", None))
    result = StageResult("interpret", "PASS", "interpretation recorded with no unresolved blocking ambiguity")
    result.artifacts["routing"] = pkg.rel(pkg.path("routing"))
    result.summary["routing"] = {k: routing[k] for k in ("decision", "routing_result", "reason")}
    events.emit("verifier_decision", "classify", f"routing decision {routing['decision']} -> {routing['routing_result']}")
    if routing["routing_result"] == "NOT_APPLICABLE":
        result.diagnostics.append(Diagnostic(
            "NOT_APPLICABLE_ROUTING",
            "the request was routed NOT_APPLICABLE (non-software); no obligations were interpreted and nothing was verified"))
        result.status = "BLOCKED"
        result.lines.append("routing: NOT_APPLICABLE — this is not a verification success; use --mode software to force the pipeline")
        return result
    if routing["routing_result"] == "AMBIGUOUS":
        result.diagnostics.append(Diagnostic(
            "INTERPRETATION_UNRESOLVED",
            "the classifier is UNCERTAIN whether this is software work; verification is not bypassed",
            details={"ambiguity": "routing", "alternatives": ["software", "non_software"],
                     "resolve_with": ["--mode software", "--resolve routing=software", "--resolve routing=non_software"]}))
        result.status = "BLOCKED"
        return result

    # -- obtain the candidate ------------------------------------------------------------------
    if candidate is not None:
        try:
            draft = canonical.load_file(candidate)
        except Exception as exc:  # noqa: BLE001
            raise UsageError(f"cannot read candidate draft {candidate}: {exc}") from None
        if ledger_path is None:
            result.diagnostics.append(Diagnostic(
                "INVALID_CANDIDATE",
                "a candidate draft must be accompanied by an interpretation ledger (--ledger) with clause dispositions"))
            result.status = "BLOCKED"
            return result
        ledger = canonical.load_file(ledger_path)
        source = {"kind": "candidate_file", "draft": str(candidate), "ledger": str(ledger_path)}
    elif agent is not None:
        draft, ledger = agent(prompt, ref, {**routing, "attachments": {k: v.decode("utf-8", "replace") for k, v in docs.items()}})
        source = {"kind": "agent", "role": "interpreter"}
    else:
        raise UsageError(
            "no interpreter available: configure an `interpreter` role with --config, or pass a candidate "
            "draft with --candidate and --ledger"
        )
    events.emit("candidate_proposal", "interpret", "received interpretation candidate", details=source)

    if resolutions and isinstance(ledger, dict) and isinstance(ledger.get("ambiguities"), list):
        result.diagnostics.extend(draftmod.apply_resolutions(ledger, resolutions, "user: --resolve on the command line"))

    # -- validate ----------------------------------------------------------------------------------
    diags = draftmod.validate_draft(draft, prompt, ref, docs)
    coverage: dict[str, Any] = {}
    if not any(d.code in ("INVALID_CANDIDATE",) and "schema" in d.message for d in diags):
        ldiags, coverage = draftmod.validate_ledger(ledger, draft, prompt, ref) if isinstance(draft, dict) else ([], {})
        diags.extend(ldiags)
    else:
        ldiags = []

    structural = [d for d in diags if d.code != "UNCOVERED_SOURCE_CLAUSE"]
    blocked: dict[str, list[str]] = {}
    if not structural:
        blocked = draftmod.blocked_obligations(draft, ledger)
        if blocked and interactive:
            chosen = _interactive_resolve(ledger, blocked)
            if chosen:
                draftmod.apply_resolutions(ledger, chosen, "user: interactive prompt")
                blocked = draftmod.blocked_obligations(draft, ledger)

    # -- write artifacts (the draft is the first deliverable; it is a proposal) ----------------------
    out = pkg.set_path("draft", draft_out) if draft_out else pkg.path("draft")
    if isinstance(draft, dict):
        fsutil.write_json(out, draft, pretty=True)
        result.artifacts["draft"] = pkg.rel(out)
    if isinstance(ledger, dict):
        fsutil.write_json(pkg.path("interpretation"), ledger, pretty=True)
        result.artifacts["interpretation"] = pkg.rel(pkg.path("interpretation"))

    root = pkg.interpretation_root() or canonical.digest(prompt)
    store = pkg.evidence
    invocation = ["verislop", "interpret"]
    request_ok = not structural
    store.record(
        claim_id="INTERPRETATION:request",
        verifier_id=VERIFIER,
        status="PASS" if request_ok and not ldiags_uncovered(diags) else "BLOCK",
        scope=[f"request {canonical.digest(prompt)}", "interpretation provenance; not mathematical proof"],
        input_root=root,
        result={
            "milestone_outcome": "PASS" if request_ok else "FAIL",
            "diagnostics": [d.to_json() for d in diags],
            "coverage": coverage,
            "blocked_guarantees": blocked,
            "routing": routing["decision"],
            "candidate_source": source,
        },
        invocation=invocation,
    )
    if request_ok:
        ledger_assumptions = {a["id"]: a for a in ledger["assumptions"]}
        for rec in draftmod.obligations(draft):
            ev = store.record(
                claim_id=claim_id("INTERPRETED", rec["id"], rec["revision"]),
                verifier_id=VERIFIER,
                status="PASS",
                scope=["recorded interpretation of the request; not proof of intent"] + rec["scope"],
                input_root=root,
                result={
                    "milestone_outcome": "PASS",
                    "reason": "explicit interpretation recorded with provenance, schema and coverage checks",
                    "record_digest": canonical.digest_json(rec),
                    "blocked_by": blocked.get(rec["id"], []),
                    "assumption_supplier": ledger_assumptions.get(rec["id"]),
                },
                invocation=invocation,
            )
            events.emit("verifier_decision", "interpret", f"{rec['id']} INTERPRETED", obligation_id=rec["id"],
                        milestone="INTERPRETED", outcome="PASS", evidence_ref=f"evidence:{ev.id}")

    for oid, ambs in blocked.items():
        amb_details = [a for a in ledger["ambiguities"] if a["id"] in ambs]
        diags.append(Diagnostic(
            "INTERPRETATION_UNRESOLVED",
            f"{oid} is blocked by unresolved ambiguity {', '.join(ambs)}; independent obligations may continue",
            obligations=[oid],
            details={"ambiguities": amb_details, "resolve_with": [f"--resolve {a}=<alternative>" for a in ambs]}))
    result.diagnostics.extend(diags)
    result.status = status_from(result.diagnostics)
    result.summary.update({
        "obligations": len(draftmod.obligations(draft)) if isinstance(draft, dict) else 0,
        "blocked_guarantees": blocked,
        "uncovered_segments": len(coverage.get("uncovered_segments", [])),
        "interpretation_root": root,
    })
    return result


def ldiags_uncovered(diags: list[Diagnostic]) -> bool:
    return any(d.code == "UNCOVERED_SOURCE_CLAUSE" for d in diags)
