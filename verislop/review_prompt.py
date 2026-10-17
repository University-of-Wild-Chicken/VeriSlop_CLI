"""Bound display-only projection of an already checked VSCore 0.3 release packet.

The complete packet remains the native review target and verifier input. This
module neither reads files nor checks mechanical outcomes; it binds the few
omitted display values to the caller's retained packet for exact restoration.
"""
from __future__ import annotations

from typing import Any

from . import canonical

LEGACY_FORMAT = "verislop.vscore-release-review-view/0.1"
FORMAT = "verislop.vscore-release-review-view/0.2"
CONTEXT_REFERENCE_FORMAT = "verislop.review-view-value-ref/0.1"
REFERENCE_FORMAT = "verislop.review-packet-value-ref/0.1"
PACKET_REF = "packet.json"
AUTHORITY = (
    "Model display only; no proof, acceptance, milestone or release authority. "
    "The complete retained packet remains the native review target and verifier input."
)
LEGACY_OMITTED_DETAIL = (
    "Only mechanical_snapshot.execution_inventory and each "
    "mechanical_snapshot.builds[i].outputs are retained by exact reference rather "
    "than displayed inline. Registered native verifiers check this mechanical "
    "detail. The reviewer must not claim to have inspected referenced detail; "
    "it can challenge current mechanical claims using the unchanged independently "
    "replayed probes. All other packet fields, scope and review policy remain exact."
)


def _backend(value: Any) -> bool:
    return (isinstance(value, dict) and value.get("target") == "vscore"
            and value.get("backend_version") == "0.3"
            and value.get("id") == "verislop.backend.vscore/0.3")


def _snapshot(packet: Any) -> dict:
    if not isinstance(packet, dict) or packet.get("checkpoint") != "release":
        raise ValueError("review display projection requires a VSCore 0.3 release packet")
    vscore = packet.get("vscore")
    selection = vscore.get("selection") if isinstance(vscore, dict) else None
    backend = selection.get("backend") if isinstance(selection, dict) else None
    snapshot = packet.get("mechanical_snapshot")
    if (not _backend(backend) or not isinstance(snapshot, dict)
            or not _backend(snapshot.get("backend"))):
        raise ValueError("review display projection requires VSCore 0.3 backend bindings")
    if (not isinstance(snapshot.get("execution_inventory"), list)
            or not isinstance(snapshot.get("builds"), list)
            or any(not isinstance(build, dict) or "outputs" not in build
                   for build in snapshot["builds"])):
        raise ValueError("review display projection requires the complete mechanical detail fields")
    return snapshot


def _reference(value: Any, pointer: str) -> dict:
    raw = canonical.dumps(value)
    return {"format": REFERENCE_FORMAT, "packet_ref": PACKET_REF,
            "pointer": pointer, "sha256": canonical.digest(raw), "utf8_bytes": len(raw)}


def _project_legacy(packet: dict) -> dict:
    """Return a deterministic display view without mutating the full packet.

    This deliberately rejects earlier checkpoints and backend versions. Only
    the closed paths below are replaced: similarly named fields or literal
    reference-shaped objects elsewhere are ordinary retained packet data.
    """
    _snapshot(packet)
    raw = canonical.dumps(packet)
    projected = canonical.loads(raw)
    snapshot = projected["mechanical_snapshot"]
    snapshot["execution_inventory"] = _reference(
        snapshot["execution_inventory"], "/mechanical_snapshot/execution_inventory")
    for index, build in enumerate(snapshot["builds"]):
        build["outputs"] = _reference(build["outputs"],
                                      f"/mechanical_snapshot/builds/{index}/outputs")
    return {"format": LEGACY_FORMAT, "packet_ref": PACKET_REF,
            "packet_sha256": canonical.digest(raw), "packet_utf8_bytes": len(raw),
            "authority": AUTHORITY, "omitted_detail": LEGACY_OMITTED_DETAIL, "packet": projected}



OMITTED_DETAIL = (
    "The generated native vscore.goal, opaque evidence ID list, execution inventory, "
    "build output maps, claim input roots/evidence references and provenance evidence "
    "references are retained by exact packet references rather than displayed inline. "
    "Every claim ID, outcome, required flag, premise, reason, root kind and verifier "
    "remains visible, along with complete accepted Lean and implementation source, "
    "scope and concrete probe policy. Registered native verifiers check the referenced "
    "detail. The reviewer must not claim to have inspected referenced detail; it can "
    "challenge current claims using the unchanged independently replayed probes."
)
CLAIM_FIELDS = {"claim_id", "outcome", "required", "premises", "reason", "root_kind", "verifier",
                "input_root", "evidence_refs"}
VISIBLE_CLAIM_FIELDS = ("claim_id", "outcome", "required", "premises", "reason", "root_kind", "verifier")
PROVENANCE_FIELDS = {"claim_id", "outcome", "reason", "verifier", "evidence"}
VISIBLE_PROVENANCE_FIELDS = ("claim_id", "outcome", "reason", "verifier")


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _claim_rows(packet: dict, snapshot: dict) -> None:
    """Validate the closed display shape, without assigning native outcomes."""
    from .lifecycle import OUTCOMES

    rows, provenance = snapshot.get("claims"), snapshot.get("provenance")
    required = packet.get("required_mechanical_claims")
    if not isinstance(rows, list) or not isinstance(provenance, list) or not isinstance(required, list):
        raise ValueError("release display requires complete claim/provenance tables")
    claims = {}
    for row in rows:
        if (not isinstance(row, dict) or set(row) != CLAIM_FIELDS
                or any(not isinstance(row[key], str) or not row[key]
                       for key in ("claim_id", "outcome", "root_kind", "verifier"))
                or row["outcome"] not in OUTCOMES or not isinstance(row["reason"], str)
                or type(row["required"]) is not bool
                or not _strings(row["premises"]) or not _strings(row["evidence_refs"])
                or not (row["input_root"] is None or isinstance(row["input_root"], str) and row["input_root"])
                or row["claim_id"] in claims):
            raise ValueError("release display has malformed or duplicate claim rows")
        claims[row["claim_id"]] = row
    if canonical.dumps(required) != canonical.dumps([row for row in rows if row["required"]]):
        raise ValueError("release display required claim inventory differs")
    seen = set()
    for row in provenance:
        if (not isinstance(row, dict) or set(row) != PROVENANCE_FIELDS
                or any(not isinstance(row[key], str) for key in VISIBLE_PROVENANCE_FIELDS)
                or not _strings(row["evidence"]) or row["claim_id"] in seen
                or row["claim_id"] not in claims):
            raise ValueError("release display has malformed or duplicate provenance rows")
        expected = {key: claims[row["claim_id"]][key] for key in VISIBLE_PROVENANCE_FIELDS}
        if canonical.dumps({key: row[key] for key in VISIBLE_PROVENANCE_FIELDS}) != canonical.dumps(expected):
            raise ValueError("release display provenance differs from its claim")
        seen.add(row["claim_id"])
    expected_provenance = [{**{key: row[key] for key in VISIBLE_PROVENANCE_FIELDS},
                            "evidence": row["evidence_refs"]} for row in rows if row["required"]]
    if canonical.dumps(provenance) != canonical.dumps(expected_provenance):
        raise ValueError("release display complete provenance inventory differs")


def project_packet(packet: dict) -> dict:
    """Project only closed mechanical-detail fields; retain all claim meanings."""
    snapshot = _snapshot(packet)
    _claim_rows(packet, snapshot)
    if (not isinstance(packet["vscore"].get("goal"), str)
            or not _strings(packet.get("evidence"))):
        raise ValueError("release display requires the complete generated goal and evidence inventory")
    for container, keys in ((packet, ("required_mechanical_claims_details_ref",)),
                            (snapshot, ("claims_details_ref", "provenance_details_ref"))):
        if any(key in container for key in keys):
            raise ValueError("release display input already contains reserved display fields")
    view = _project_legacy(packet)
    view["format"], view["omitted_detail"] = FORMAT, OMITTED_DETAIL
    projected = view["packet"]
    projected["vscore"]["goal"] = _reference(packet["vscore"]["goal"], "/vscore/goal")
    projected["evidence"] = _reference(packet["evidence"], "/evidence")
    for key, fields in (("claims", VISIBLE_CLAIM_FIELDS), ("provenance", VISIBLE_PROVENANCE_FIELDS)):
        projected["mechanical_snapshot"][key] = [{field: row[field] for field in fields} for row in snapshot[key]]
        projected["mechanical_snapshot"][key + "_details_ref"] = _reference(
            snapshot[key], "/mechanical_snapshot/" + key)
    projected["required_mechanical_claims"] = [
        {field: row[field] for field in VISIBLE_CLAIM_FIELDS} for row in packet["required_mechanical_claims"]]
    projected["required_mechanical_claims_details_ref"] = _reference(
        packet["required_mechanical_claims"], "/required_mechanical_claims")
    # Detach projected row children as well as the original full packet clone.
    return canonical.loads(canonical.dumps(view))


def restore_packet(view: dict, full_packet: dict) -> dict:
    """Restore against the caller's authenticated packet; never resolve a path."""
    raw = canonical.dumps(full_packet)
    if not isinstance(view, dict) or view.get("packet_sha256") != canonical.digest(raw):
        raise ValueError("review display full packet binding differs")
    if view.get("format") == LEGACY_FORMAT:
        expected = _project_legacy(full_packet)
    elif view.get("format") == FORMAT:
        expected = project_packet(full_packet)
    else:
        raise ValueError("unsupported review display version")
    if canonical.dumps(view) != canonical.dumps(expected):
        raise ValueError("review display view differs from its exact packet projection")
    return canonical.loads(raw)


def context_reference(view: dict, full_packet: dict) -> dict:
    """Bind the supervisor pointer to the exact fully inline display context."""
    restore_packet(view, full_packet)
    if view.get("format") != FORMAT:
        raise ValueError("supervisor display context pointer requires version 0.2")
    context = full_packet.get("review_context")
    policy = full_packet.get("counterexample_policy")
    if (not isinstance(context, dict) or not isinstance(policy, dict)
            or canonical.dumps(context) != canonical.dumps(policy.get("review_context"))
            or canonical.dumps(context) != canonical.dumps(view["packet"].get("review_context"))):
        raise ValueError("supervisor and displayed review contexts differ")
    raw = canonical.dumps(context)
    return {"format": CONTEXT_REFERENCE_FORMAT, "view_ref": "prompt-view.json",
            "view_sha256": canonical.digest_json(view), "pointer": "/packet/review_context",
            "sha256": canonical.digest(raw), "utf8_bytes": len(raw),
            "meaning": "Exact supervisor-selected context remains fully inline at this display pointer."}
