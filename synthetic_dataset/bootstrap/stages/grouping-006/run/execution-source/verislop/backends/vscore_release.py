"""Release finalization after an immutable, current VSCore mechanical execution.

Review gates can block release or fail operationally; they never modify the checked
mechanical snapshot or its atomically published end-to-end evidence.
"""
from __future__ import annotations

from pathlib import Path

from .. import canonical, fsutil, report, review, review_projection, schemas, view
from ..errors import Diagnostic, UsageError, VeriSlopError
from ..bridges.manifest import InvalidPackage
from ..stage import StageResult
from . import vscore_closure


def finalize(pkg, events, snapshot: dict, *, config: Path | None = None,
             endpoint: str | None = None, require_state: str | None = None) -> StageResult:
    if not isinstance(snapshot, dict) or "mechanical_result_path" not in snapshot or schemas.validate(
            "mechanical-result", {k: v for k, v in snapshot.items() if k != "mechanical_result_path"}):
        result = StageResult("verify", "BLOCKED", "a validated mechanical snapshot is required before release finalization")
        result.diagnostics = [Diagnostic("VERIFIER_NOT_RUN", "no valid current mechanical snapshot is available")]
        result.summary = {"mechanical_status": "BLOCKED", "release_status": "BLOCKED", "terminal_status": "BLOCKED"}
        return result
    diags = [Diagnostic.from_json(d) for d in snapshot["diagnostics"]]
    mechanical = snapshot["mechanical_status"]
    mechanical_current = False
    release = "NOT_REQUIRED"
    gate = {"configured": False, "checkpoints": {}, "diagnostics": []}
    projected = None
    try:
        current = vscore_closure.mechanical_snapshot(pkg)
        if current != snapshot:
            raise UsageError("mechanical inputs/publication changed before release finalization",
                             [Diagnostic("INPUT_MUTATION", "current execution differs from the mechanically checked snapshot")])
        frozen_diags = vscore_closure.validate_frozen(pkg)
        if frozen_diags:
            raise UsageError("frozen closure changed before finalization", frozen_diags)
        mechanical_current = True
        stored = pkg.path("closure") / "review-config.json"
        if config is not None:
            from ..providers import config as pcfg
            conf = pcfg.load(Path(config))
            fsutil.atomic_write(stored, canonical.dumps(conf), readonly=True)
            config = stored
        elif stored.is_file():
            config = stored
        projected = review_projection.build(pkg, snapshot)
        if config is not None:
            gate = review.gate(pkg, Path(config))
            diags.extend(gate["diagnostics"])
            release = ("INFRASTRUCTURE_FAILURE" if any(d.severity == "infrastructure" for d in gate["diagnostics"])
                       else "BLOCKED" if gate["diagnostics"] else "ACCEPTED")
    except (InvalidPackage, VeriSlopError, OSError, ValueError, KeyError) as exc:
        errors = getattr(exc, "diagnostics", None) or [Diagnostic(
            getattr(exc, "code", "STALE_OR_UNBOUND_EVIDENCE"), str(exc))]
        diags.extend(errors)
        release = "INFRASTRUCTURE_FAILURE" if any(d.severity == "infrastructure" for d in errors) else "BLOCKED"
    if mechanical_current:
        # This check also runs after a review/config/projection failure, which by itself
        # leaves the mechanically checked fact true. Input mutation invalidates currency.
        try:
            final_diags = vscore_closure.validate_frozen(pkg)
            if final_diags:
                raise UsageError("frozen inputs changed during release finalization", final_diags)
            if vscore_closure.mechanical_snapshot(pkg) != snapshot:
                raise InvalidPackage("current mechanical publication changed during release finalization", "INPUT_MUTATION")
        except (InvalidPackage, VeriSlopError, OSError, ValueError, KeyError) as exc:
            mechanical_current = False
            diags.extend(getattr(exc, "diagnostics", None) or [Diagnostic(getattr(exc, "code", "INPUT_MUTATION"), str(exc))])
    if not mechanical_current:
        mechanical = "INFRASTRUCTURE_FAILURE" if any(d.severity == "infrastructure" for d in diags) else "BLOCKED"
    terminal = ("INFRASTRUCTURE_FAILURE" if "INFRASTRUCTURE_FAILURE" in (mechanical, release) else
                "VERIFIED" if mechanical == "VERIFIED" and release in ("ACCEPTED", "NOT_REQUIRED") else "BLOCKED")
    overlay = view.derive(pkg)
    params = snapshot["parameters"]
    rep = report.build(pkg, overlay, terminal, diags, snapshot["builds"], snapshot["determinism"], params,
                       endpoint, require_state or params.get("require_state"), snapshot["closure_root"],
                       snapshot["provenance"], {**gate, "diagnostics": [d.to_json() for d in gate["diagnostics"]]},
                       canonical.digest_file(pkg.path("accepted_ir")) if pkg.path("accepted_ir").is_file() else None)
    rep.update({"mechanical_status": mechanical, "release_status": release, "closure_id": snapshot["closure_id"],
                "mechanical_result": snapshot["mechanical_result_path"],
                "freshness": "current execution revalidated" if mechanical_current else "recorded_execution_only"})
    rep["endpoint"]["established"] = "restricted_source" if mechanical == "VERIFIED" else None
    if not mechanical_current:
        rep["endpoint"]["statement"] = "restricted_source is not established by a current mechanical execution"
    if mechanical == "VERIFIED":
        rep["qualified_result"] = "VERIFIED closure; END_TO_END_VERIFIED [restricted_source; vscore/0.1]"
        if release not in ("ACCEPTED", "NOT_REQUIRED"):
            rep["qualified_result"] += "; release " + release.lower()
    if projected:
        rep["review_projection"] = {"hash": projected["projection_hash"], "normalizer_registry_hash": projected["normalizer_registry_hash"],
                                    "current_raw_inventory_hash": projected["raw_inventory_hash"],
                                    "reuse": gate.get("projection_reuse", {})}
        rep["execution_inventory_hash"] = projected["raw_inventory_hash"]
        rep["review_target"] = gate.get("review_target")
    issues = schemas.validate("run-report-v2", rep)
    if issues:
        raise ValueError(f"invalid Tier 2 report: {issues[0]}")
    fsutil.write_json(pkg.path("report"), rep)
    view.write(pkg)
    result = StageResult("verify", "PASS" if terminal == "VERIFIED" else terminal,
                         "finite restricted_source mechanics and independently configured release review")
    result.diagnostics = diags
    result.artifacts = {"report": pkg.rel(pkg.path("report")), "mechanical_result": snapshot["mechanical_result_path"]}
    result.summary = {"mechanical_status": mechanical, "release_status": release, "terminal_status": terminal,
                      "closure_root": snapshot["closure_root"], "mechanical_result": snapshot["mechanical_result_path"]}
    result.lines = report.render_lines(rep)
    events.emit("stage_finished", "verify", f"mechanical {mechanical}; release {release}; terminal {terminal}")
    return result
