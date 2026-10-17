"""Exact accepted-name authoring convenience; canonical checker semantics stay fixed."""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import agent_memory, canonical, dsl, export, fsutil
from .bridges.manifest import InvalidPackage, PackageReader
from .errors import Diagnostic, blocked
from .targets import vscore3_target as target

FORMAT = "verislop.relation-authoring/0.1"
AUTHORITY_FORMAT = "verislop.relation-authoring-authority/0.1"
AUTHORITY = "Untrusted authoring name normalization only; no proof, linkage, TESTED, refinement or acceptance authority."
AUTH_FILES = {"accepted-ir.json", "acceptance-certificate.json", "accepted-profile.json", "binding.json"}


class NormalizationError(ValueError):
    def __init__(self, diagnostics: list[Diagnostic]):
        super().__init__("; ".join(d.message for d in diagnostics))
        self.diagnostics = diagnostics
        self.relation_input_kind = "raw_authoring_relation"


def _fail(message: str):
    raise blocked("STALE_OR_UNBOUND_EVIDENCE", "relation authoring: " + message)


def identity() -> dict:
    root = Path(__file__).resolve().parent
    return {"format": FORMAT, "implementation": {name: canonical.digest((root / name).read_bytes())
        for name in ("relation_authoring.py", "agents.py", "targets/vscore3_target.py", "dsl.py", "canonical.py")}}


def _ref(path: str, data: bytes) -> dict:
    return {"path": path, "sha256": canonical.digest(data), "size": len(data)}


def _accepted_bytes(pkg, fixed: dict | None = None) -> dict[str, bytes]:
    """Use existing evidence verification, then bind exact stable artifact reads."""
    ir, ir_hash, cert, diagnostics = export.verified_ir(pkg)
    if diagnostics or ir is None or cert is None:
        raise blocked("STALE_OR_UNBOUND_EVIDENCE", "relation authoring requires verified accepted IR",
                      details={"diagnostics": [d.to_json() for d in diagnostics]})
    reader = PackageReader(pkg.root)
    try:
        ir_art = reader.read(pkg.path("accepted_ir"), keep=True)
        cert_art = reader.read(ir["acceptance_certificate_ref"], keep=True)
        profile_ref = cert["artifacts"]["profile"]
        profile_art = reader.read(profile_ref["path"], keep=True)
        profile = canonical.loads(profile_art.data)
        if (ir_art.sha256 != ir_hash or canonical.dumps(canonical.loads(ir_art.data)) != canonical.dumps(ir)
                or canonical.dumps(canonical.loads(cert_art.data)) != canonical.dumps(cert)
                or Path(cert_art.path).name != cert_art.sha256[7:] + ".json"
                or cert.get("artifact_kind") != "acceptance_certificate" or cert.get("gate") != "accepted_and_proved"
                or ir["contract_input_root"] != cert["contract_input_root"]
                or ir["lean_toolchain"] != cert["toolchain"]["pin"]
                or profile_art.sha256 != profile_ref["sha256"]):
            _fail("accepted IR/certificate/profile artifact identity differs")
        if fixed is not None and (canonical.dumps(fixed["accepted_ir"]) != canonical.dumps(ir)
                or canonical.dumps(fixed["accepted_profile"]) != canonical.dumps(profile)
                or fixed["lean_toolchain"] != cert["toolchain"]["pin"]):
            _fail("fixed context is not the authenticated accepted IR/profile/toolchain")
        binding = {"format": AUTHORITY_FORMAT, "authority": AUTHORITY, "normalizer": identity(),
            "contract_input_root": ir["contract_input_root"], "lean_toolchain": ir["lean_toolchain"],
            "ir": _ref(ir_art.path, ir_art.data), "certificate": _ref(cert_art.path, cert_art.data),
            "profile": _ref(profile_art.path, profile_art.data)}
        reader.recheck()
        return {"accepted-ir.json": ir_art.data, "acceptance-certificate.json": cert_art.data,
                "accepted-profile.json": profile_art.data, "binding.json": canonical.dumps(binding)}
    except (InvalidPackage, KeyError, TypeError, ValueError, AttributeError) as exc:
        _fail("malformed or changed accepted artifacts: " + str(exc))
    finally:
        reader.close()


@dataclass(frozen=True)
class AcceptedNames:
    snapshot_ref: dict
    binding: dict
    profile: dict


def prepare(pkg, fixed: dict) -> AcceptedNames:
    artifacts = _accepted_bytes(pkg, fixed)
    binding = canonical.loads(artifacts["binding.json"])
    stage = "relation-authority/" + canonical.digest_json(binding)[7:]
    ref = agent_memory.latest_snapshot(pkg, stage_prefix=stage)
    if ref is None:
        ref = agent_memory.checkpoint(pkg, stage, artifacts, metadata={"authority": AUTHORITY})["snapshot_ref"]
    elif agent_memory.restore(pkg, ref) != artifacts:
        _fail("retained authority snapshot differs from authenticated artifacts")
    return AcceptedNames(ref, binding, canonical.loads(artifacts["accepted-profile.json"]))


def restore_authority(pkg, reference: dict, *, expected: AcceptedNames | None = None) -> AcceptedNames:
    artifacts = agent_memory.restore(pkg, reference)
    if set(artifacts) != AUTH_FILES or artifacts != _accepted_bytes(pkg):
        _fail("retained authority differs from current verified acceptance binding")
    binding = canonical.loads(artifacts["binding.json"])
    result = AcceptedNames(reference, binding, canonical.loads(artifacts["accepted-profile.json"]))
    if expected is not None and (canonical.dumps(result.binding) != canonical.dumps(expected.binding)
            or canonical.dumps(result.profile) != canonical.dumps(expected.profile)
            or result.snapshot_ref != expected.snapshot_ref):
        _fail("retained normalization uses a different accepted profile")
    return result


def _diagnostic(code: str, reason: str, message: str, **details) -> Diagnostic:
    return Diagnostic(code, message, details={"stage": "relation_authoring", "reason": reason,
        "relation_input_kind": "raw_authoring_relation", **details})


def _table(profile: dict) -> dict:
    try:
        symbols = profile["symbols"]
        if not isinstance(symbols, dict):
            raise ValueError("accepted symbols must be an object")
        for sid, row in symbols.items():
            if (not isinstance(sid, str) or not sid or not isinstance(row, dict)
                    or not {"lean_decl", "args", "result", "level_params", "decl_hash"} <= set(row)
                    or not isinstance(row["lean_decl"], str) or not row["lean_decl"]
                    or not isinstance(row["args"], list) or not isinstance(row["level_params"], list)
                    or any(not isinstance(p, str) or not p for p in row["level_params"])
                    or not isinstance(row["decl_hash"], str) or len(row["decl_hash"]) != 71
                    or not row["decl_hash"].startswith("sha256:")
                    or any(c not in "0123456789abcdef" for c in row["decl_hash"][7:])):
                raise ValueError(f"malformed accepted symbol metadata for {sid!r}")
        dsl.Profile.from_json(profile)
        return symbols
    except (KeyError, TypeError, ValueError, AttributeError, dsl.DSLError) as exc:
        raise NormalizationError([_diagnostic("INVALID_CANDIDATE", "malformed_accepted_metadata", str(exc))]) from None


def _matches(symbols: dict, query: str) -> list[dict]:
    return [{"id": sid, "lean_decl": row["lean_decl"],
             "match_modes": (["profile_id"] if sid == query else []) + (["lean_decl"] if row["lean_decl"] == query else [])}
            for sid, row in sorted(symbols.items()) if sid == query or row["lean_decl"] == query]


def _normalize(raw: bytes, profile: dict) -> tuple[bytes | None, list[dict], list[Diagnostic]]:
    """Pure metadata computation, not acceptance authority; production uses prepare."""
    try:
        relation = target.load_relation(raw)
        if (relation["source_slot"], relation["proof_slot"]) != ("vscore-source", "vscore-proof"):
            raise target.BridgeInvalid("relation helper slots must be vscore-source and vscore-proof")
        symbols = _table(profile)
    except target.BridgeInvalid as exc:
        return None, [], [_diagnostic(exc.code, "invalid_descriptor", str(exc))]
    except NormalizationError as exc:
        return None, [], exc.diagnostics
    rows, diagnostics, mapped = [], [], []
    for index, binding in enumerate(relation["bindings"]):
        q = binding["symbol"]
        candidates = _matches(symbols, q)
        row = {"input_index": index, "submitted_symbol": q, "entry": binding["entry"],
               "candidates": candidates, "selected_id": None, "canonical_candidates": []}
        rows.append(row)
        detail = {"submitted_symbol": q, "entry": binding["entry"], "candidates": candidates}
        if not candidates:
            diagnostics.append(_diagnostic("UNMAPPED_IMPLEMENTATION_OBJECT", "unknown_symbol",
                f"relation symbol {q!r} has no exact accepted ID or lean_decl match", **detail))
            continue
        if len(candidates) != 1:
            diagnostics.append(_diagnostic("AMBIGUOUS_CORRESPONDENCE", "ambiguous_symbol",
                f"relation symbol {q!r} matches multiple accepted IDs", **detail))
            continue
        sid = candidates[0]["id"]
        canonical_candidates = _matches(symbols, sid)
        row["canonical_candidates"] = canonical_candidates
        if [item["id"] for item in canonical_candidates] != [sid]:
            diagnostics.append(_diagnostic("AMBIGUOUS_CORRESPONDENCE", "ambiguous_canonical_id",
                f"relation symbol {q!r} maps to {sid!r}, whose canonical spelling is ambiguous",
                **detail, canonical_id=sid, canonical_candidates=canonical_candidates))
            continue
        if symbols[sid]["level_params"]:
            diagnostics.append(_diagnostic("UNSUPPORTED_CAPABILITY", "unsupported_polymorphism",
                f"accepted function {sid!r} has nonempty universe parameters", **detail,
                level_params=symbols[sid]["level_params"]))
            continue
        row["selected_id"] = sid
        mapped.append({"symbol": sid, "entry": binding["entry"]})
    counts = {}
    for row in rows:
        if row["selected_id"] is not None:
            counts.setdefault(row["selected_id"], []).append(row["submitted_symbol"])
    for sid, names in sorted(counts.items()):
        if len(names) > 1:
            diagnostics.append(_diagnostic("AMBIGUOUS_CORRESPONDENCE", "normalization_collision",
                f"submitted relation names {names!r} resolve to the same accepted ID {sid!r}",
                canonical_id=sid, submitted_symbols=names, lean_decl=symbols[sid]["lean_decl"]))
    if diagnostics:
        return None, rows, diagnostics
    normalized = copy.deepcopy(relation)
    normalized["bindings"] = sorted(mapped, key=lambda b: b["symbol"])
    data = canonical.dumps(normalized)
    target.load_relation(data)
    return data, rows, []


def _receipt(authority: AcceptedNames, stage_ref: str, response: bytes, raw: bytes) -> tuple[dict, bytes | None]:
    from .agents import extract_json
    try:
        response_object = extract_json(response.decode("utf-8"))
        if not isinstance(response_object, dict) or "relation" not in response_object or canonical.dumps(response_object["relation"]) != raw:
            _fail("raw relation is not the exact decoded provider relation")
    except (ValueError, TypeError, UnicodeError) as exc:
        _fail("provider response/raw relation binding differs: " + str(exc))
    normalized, rows, diagnostics = _normalize(raw, authority.profile)
    receipt = {"format": FORMAT, "authority": AUTHORITY, "normalizer": identity(),
        "accepted_authority": authority.snapshot_ref, "accepted_binding": authority.binding,
        "response": _ref(stage_ref + "/response.txt", response),
        "raw_relation": _ref(stage_ref + "/relation.raw.json", raw),
        "normalized_relation": _ref(stage_ref + "/relation.json", normalized) if normalized is not None else None,
        "rows": rows, "input_order": [r["submitted_symbol"] for r in rows],
        "output_order": [r["symbol"] for r in canonical.loads(normalized)["bindings"]] if normalized is not None else None,
        "outcome": "normalized" if normalized is not None else "rejected",
        "diagnostics": [d.to_json() for d in diagnostics]}
    return receipt, normalized


def restore(pkg, document: dict, *, expected: AcceptedNames | None = None) -> tuple[dict, bytes | None]:
    """Authenticate authority and recompute full receipt; no receipt asserts a proof."""
    try:
        if not isinstance(document, dict) or set(document) != {"format", "receipt", "snapshot_ref"} or document["format"] != FORMAT:
            _fail("malformed normalization receipt envelope")
        artifacts = agent_memory.restore(pkg, document["snapshot_ref"])
        receipt = document["receipt"]
        if canonical.dumps(receipt) != artifacts["receipt.json"]:
            _fail("normalization receipt differs from retained bytes")
        authority = restore_authority(pkg, receipt["accepted_authority"], expected=expected)
        stage_ref = receipt["response"]["path"].removesuffix("/response.txt")
        fsutil.check_relpath(stage_ref)
        replay, normalized = _receipt(authority, stage_ref, artifacts["response.txt"], artifacts["relation.raw.json"])
        expected_files = {"receipt.json", "response.txt", "relation.raw.json"} | ({"relation.json"} if normalized is not None else set())
        if (set(artifacts) != expected_files or canonical.dumps(replay) != canonical.dumps(receipt)
                or normalized is not None and artifacts["relation.json"] != normalized):
            _fail("normalization replay differs from retained exact inputs/output")
        # Stage files are immutable authoring inputs, not mapping authority. Check
        # their exact correspondence when replaying the published attempt.
        reader = PackageReader(pkg.root)
        try:
            for name in ("response", "raw_relation"):
                ref = receipt[name]
                got = reader.read(ref["path"], keep=True)
                if got.sha256 != ref["sha256"] or got.size != ref["size"]:
                    _fail("published raw authoring artifact changed")
            normalized_ref = receipt["normalized_relation"]
            if normalized_ref is not None and os.path.lexists(pkg.root / normalized_ref["path"]):
                got = reader.read(normalized_ref["path"], keep=True)
                if got.sha256 != normalized_ref["sha256"] or got.size != normalized_ref["size"]:
                    _fail("published normalized relation changed")
            reader.recheck()
        finally:
            reader.close()
        return receipt, normalized
    except (InvalidPackage, KeyError, TypeError, ValueError, AttributeError) as exc:
        _fail("malformed or missing normalization artifact: " + str(exc))


def normalize_attempt(pkg, stage: Path, authority: AcceptedNames, response: bytes, raw: bytes) -> bytes:
    stage_ref = fsutil.check_relpath(str(stage.relative_to(pkg.root)))
    fsutil.write_once(stage / "response.txt", response)
    fsutil.write_once(stage / "relation.raw.json", raw)
    receipt_path = stage / "relation-normalization.json"
    if receipt_path.exists():
        document = canonical.loads(receipt_path.read_bytes())
        receipt, normalized = restore(pkg, document, expected=authority)
        if receipt["response"] != _ref(stage_ref + "/response.txt", response) or receipt["raw_relation"] != _ref(stage_ref + "/relation.raw.json", raw):
            _fail("completed normalization belongs to different authoring input")
    else:
        # Recheck retained authority before mapping, including in-memory profile
        # mutation and accepted evidence changed since prepare/model dispatch.
        authority = restore_authority(pkg, authority.snapshot_ref, expected=authority)
        receipt, normalized = _receipt(authority, stage_ref, response, raw)
        artifacts = {"response.txt": response, "relation.raw.json": raw, "receipt.json": canonical.dumps(receipt)}
        if normalized is not None:
            artifacts["relation.json"] = normalized
        snapshot = agent_memory.checkpoint(pkg, "relation-authoring/" + canonical.digest(stage_ref.encode())[7:],
            artifacts, metadata={"authority": AUTHORITY})
        document = {"format": FORMAT, "receipt": receipt, "snapshot_ref": snapshot["snapshot_ref"]}
        fsutil.write_json(receipt_path, document, once=True)
    if normalized is None:
        raise NormalizationError([Diagnostic.from_json(d) for d in receipt["diagnostics"]])
    fsutil.write_once(stage / "relation.json", normalized)
    return normalized
