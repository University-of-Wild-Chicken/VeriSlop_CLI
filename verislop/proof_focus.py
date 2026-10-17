"""Native-diagnostic proof proposal focus and lossless prompt deduplication.

These are search conveniences, never acceptance or proof evidence. All native
observations originate in the ordinary whole-module evaluation; no model output
is consulted to identify unresolved declarations.
"""
from __future__ import annotations

import copy
import json
from typing import Any

from . import canonical, proof_fragments

FOCUS_FORMAT = "verislop.proof-focus/0.1"
CONTEXT_FORMAT = "verislop.proof-prompt-context/0.1"
SOURCE_PATHS = (("current_file",), ("previous_attempt", "lean_source"),
                ("previous_attempt", "raw_response"), ("retained_rejection", "candidate"), ("retained_rejection", "raw_response"))


def _mapped_names(baseline: str, declarations: list, allowed: set[str], positions: list) -> set[str] | None:
    # Lean v4.34.1 FileMap.toPosition increments a column once per Unicode
    # character (Lean/Data/Position.lean), matching Python string offsets.
    # Python splitlines also treats U+0085/U+2028/U+2029 as line breaks;
    # Lean FileMap.ofString counts only literal LF, including inside strings.
    lines = baseline.split("\n")
    starts, offset = [], 0
    for line in lines:
        starts.append(offset)
        offset += len(line) + 1
    unresolved: set[str] = set()
    for pos in positions:
        if (not isinstance(pos, dict) or set(pos) != {"line", "column"}
                or type(pos["line"]) is not int or type(pos["column"]) is not int
                or not 1 <= pos["line"] <= len(lines)
                or not 0 <= pos["column"] < len(lines[pos["line"] - 1])):
            return None
        offset = starts[pos["line"] - 1] + pos["column"]
        matches = [t.name for t in declarations if t.start <= offset < t.body_end]
        if len(matches) != 1 or matches[0] not in allowed:
            return None
        unresolved.add(matches[0])
    return unresolved


def select(frozen: str, baseline: str, evaluation: dict | None,
           toolchain_identity: dict | None, policy: dict) -> dict | None:
    """Conservatively select original holes from a bound native compilation.

    `evaluation` is produced by prove.evaluate in the current process. Retained
    baselines are re-evaluated before reaching this function. A serialized
    descriptor is not a substitute for this native compilation.
    """
    try:
        original = proof_fragments._frozen_declarations(frozen)
    except proof_fragments.FragmentError:
        # General full-file proof jobs may use syntax outside the optional
        # fragment protocol. Do not restrict or reinterpret those jobs here.
        return None
    holes = [t for t in original if t.hole]
    all_names = [t.name for t in holes]
    result = {"format": FOCUS_FORMAT, "frozen_sha256": canonical.digest(frozen.encode()),
              "baseline_sha256": canonical.digest(baseline.encode()), "names": all_names,
              "basis": "conservative", "reason": "native observation unavailable",
              "native_sha256": None, "native_observation": None}

    def fallback(reason: str) -> dict:
        result["reason"] = reason
        return result

    if not isinstance(evaluation, dict) or evaluation.get("ok") is not True:
        return fallback("baseline has no successful native evaluation")
    native = evaluation.get("native_diagnostics")
    if (not isinstance(native, dict) or toolchain_identity is None
            or set(native) != {"source_sha256", "policy_sha256", "toolchain", "sorry_positions"}
            or native["source_sha256"] != result["baseline_sha256"]
            or native["policy_sha256"] != canonical.digest_json(policy)
            or native["toolchain"] != toolchain_identity):
        return fallback("native observation binding is missing or stale")
    positions = native["sorry_positions"]
    if (not isinstance(positions, list) or not positions
            or type(evaluation.get("sorries")) is not int
            or len(positions) != evaluation["sorries"] or evaluation.get("errors") != []):
        return fallback("native warning positions are missing or inconsistent")
    try:
        previous = proof_fragments.declarations(baseline)
        allowed = set(all_names)
        if ([(t.name, t.header) for t in previous] != [(t.name, t.header) for t in original]
                or proof_fragments._masked(baseline, previous, allowed)
                != proof_fragments._masked(frozen, original, allowed)):
            return fallback("baseline does not preserve the frozen scaffold")
    except proof_fragments.FragmentError:
        return fallback("baseline declaration positions are unsupported")
    unresolved = _mapped_names(baseline, previous, allowed, positions)
    if unresolved is None:
        return fallback("native warning does not map uniquely inside an original hole")
    result.update(names=[name for name in all_names if name in unresolved],
                  basis="native_sorry_positions", reason="successful exact-baseline native compilation",
                  native_sha256=canonical.digest_json(native), native_observation=copy.deepcopy(native))
    return result


def focused_names(descriptor: dict | None, frozen: str, baseline: str) -> list[str] | None:
    """Validate the internal dispatch binding; return only a strict focus."""
    if descriptor is None:
        return None
    if (not isinstance(descriptor, dict) or set(descriptor) != {
            "format", "frozen_sha256", "baseline_sha256", "names", "basis", "reason", "native_sha256", "native_observation"}
            or descriptor["format"] != FOCUS_FORMAT
            or descriptor["frozen_sha256"] != canonical.digest(frozen.encode())
            or descriptor["baseline_sha256"] != canonical.digest(baseline.encode())):
        raise proof_fragments.FragmentError("proof focus is stale or malformed")
    all_names = [t.name for t in proof_fragments._frozen_declarations(frozen) if t.hole]
    names = descriptor["names"]
    if (not isinstance(names, list) or any(not isinstance(n, str) for n in names)
            or names != [name for name in all_names if name in names]
            or not isinstance(descriptor["basis"], str)
            or descriptor["basis"] not in {"conservative", "native_sorry_positions"}):
        raise proof_fragments.FragmentError("proof focus contains invalid theorem names or basis")
    if descriptor["basis"] == "conservative":
        if names != all_names or descriptor["native_sha256"] is not None or descriptor["native_observation"] is not None:
            raise proof_fragments.FragmentError("conservative proof focus must retain every original hole")
        return None
    native = descriptor["native_observation"]
    if (not isinstance(native, dict) or not names
            or set(native) != {"source_sha256", "policy_sha256", "toolchain", "sorry_positions"}
            or descriptor["native_sha256"] != canonical.digest_json(native)
            or native["source_sha256"] != descriptor["baseline_sha256"]
            or not isinstance(native["sorry_positions"], list) or not native["sorry_positions"]):
        raise proof_fragments.FragmentError("native proof focus has no bound unresolved declarations")
    mapped = _mapped_names(baseline, proof_fragments.declarations(baseline), set(all_names), native["sorry_positions"])
    if mapped is None or names != [name for name in all_names if name in mapped]:
        raise proof_fragments.FragmentError("proof focus names differ from the bound native warning locations")
    return names if names != all_names else None


def _location(data: dict, path: tuple[str, ...]) -> tuple[dict, str] | None:
    current = data
    for part in path[:-1]:
        if current.get(part) is None:
            return None
        current = current[part]
        if not isinstance(current, dict):
            raise ValueError("proof context source parent must be an object")
    if path[-1] not in current:
        return None
    return current, path[-1]


def project_context(data: dict[str, Any]) -> dict:
    """Reference exact duplicate source strings at four explicitly named paths."""
    context = copy.deepcopy(data)
    first: dict[str, tuple[tuple[str, ...], str]] = {}
    for path in SOURCE_PATHS:
        location = _location(context, path)
        if location is None:
            continue
        parent, key = location
        value = parent[key]
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError("proof context source must be an exact string")
        digest = canonical.digest(value.encode())
        if digest in first:
            original_path, original = first[digest]
            if value != original:
                raise ValueError("proof context content digest collision")
            parent[key] = {"exact_content_ref": list(original_path), "sha256": digest,
                           "utf8_bytes": len(value.encode())}
        else:
            first[digest] = (path, value)
    envelope = {"format": CONTEXT_FORMAT, "original_sha256": canonical.digest_json(data), "context": context}
    if restore_context(envelope) != data:
        raise ValueError("proof context projection did not restore exactly")
    return envelope


def restore_context(envelope: dict) -> dict:
    if (not isinstance(envelope, dict) or set(envelope) != {"format", "original_sha256", "context"}
            or envelope["format"] != CONTEXT_FORMAT or not isinstance(envelope["context"], dict)):
        raise ValueError("invalid proof context envelope")
    context = copy.deepcopy(envelope["context"])
    originals: dict[tuple[str, ...], str] = {}
    for path in SOURCE_PATHS:
        location = _location(context, path)
        if location is None:
            continue
        parent, key = location
        value = parent[key]
        if value is None:
            continue
        if isinstance(value, str):
            originals[path] = value
            continue
        if (not isinstance(value, dict) or set(value) != {"exact_content_ref", "sha256", "utf8_bytes"}
                or not isinstance(value["exact_content_ref"], list)
                or any(not isinstance(part, str) for part in value["exact_content_ref"])):
            raise ValueError("invalid exact proof content reference")
        target = tuple(value["exact_content_ref"])
        if target not in originals:
            raise ValueError("proof content reference is unknown, forward, or indirect")
        original = originals[target]
        if (value["sha256"] != canonical.digest(original.encode())
                or type(value["utf8_bytes"]) is not int or value["utf8_bytes"] != len(original.encode())):
            raise ValueError("proof content reference binding mismatch")
        parent[key] = original
    if canonical.digest_json(context) != envelope["original_sha256"]:
        raise ValueError("restored proof context differs from the exact original")
    return context


def render_context(envelope: dict) -> str:
    """Keep existing prompt sections, with explicit references only for copies."""
    restore_context(envelope)
    data = envelope["context"]
    if set(data) - {"mechanical_retention"} != {"current_file", "previous_attempt", "errors", "critique", "focus", "retained_rejection"}:
        raise ValueError("proof prompt rendering requires the complete registered context fields")
    text = "CURRENT FILE:\n```lean\n" + data["current_file"] + "\n```\n"
    if data.get("previous_attempt") is not None:
        text += ("\nPREVIOUS PROOF ATTEMPT (exact untrusted submitted source; repair proofs without changing the frozen contract):\n"
                 + json.dumps(data["previous_attempt"], ensure_ascii=False, indent=1)
                 + "\nThe CURRENT FILE is the best baseline; the PREVIOUS PROOF ATTEMPT is the latest evaluated proposal. Its failures must be addressed even if the baseline elaborates with unresolved sorry proofs.\n")
    if data["errors"]:
        text += "LEAN ERRORS (latest attempt, not merely the best baseline):\n" + "\n".join(data["errors"]) + "\n"
    if data.get("critique") is not None:
        text += "\nAUTONOMOUS PROOF CRITIQUE (untrusted correction advice; frozen statements cannot change):\n" + json.dumps(data["critique"], ensure_ascii=False)
    if data.get("focus") is not None:
        text += "\nPROOF DISPATCH FOCUS (search guidance only; the entire module will be checked):\n" + json.dumps(data["focus"], ensure_ascii=False)
    if data.get("retained_rejection") is not None:
        text += ("\nEXACT RETAINED PROOF REJECTION (untrusted source/response with actual checker diagnostics; bound to this frozen job):\n"
                 + json.dumps(data["retained_rejection"], ensure_ascii=False)
                 + "\nRepair the proof body using these concrete errors. The frozen statements, definitions, imports, program and relation must not change.\n")
    if "mechanical_retention" in data:
        text += ("\nMECHANICAL PROOF RETENTION (search state only; the latest provider rejection remains unchanged):\n"
                 + json.dumps(data["mechanical_retention"], ensure_ascii=False))
    text += ("\nEXACT CONTENT REFERENCES: an object with exact_content_ref, sha256 and utf8_bytes replaces only an exact duplicate string. "
             "Its path names earlier inline content: current_file = CURRENT FILE; previous_attempt.lean_source = PREVIOUS PROOF ATTEMPT; "
             "retained_rejection = EXACT RETAINED PROOF REJECTION. Read that exact content at its first occurrence; nothing was summarized or truncated.\n"
             "RESTORED CONTEXT SHA256: " + envelope["original_sha256"] + "\n")
    return text
