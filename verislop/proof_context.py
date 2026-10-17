"""Exact, restorable model-facing library selection; never verifier input rewriting."""
from __future__ import annotations

from typing import Any

from . import agent_memory, canonical
from .errors import blocked
from .targets import vscore3_target

FORMAT = "verislop.vscore-proof-library-context/0.1"
SOURCE_REF = "verifier-library.json"
INLINE_MODULES = ("VSCore3.Typed", "VSCore3.Transport")
AUTHORITY = "Retained proof-author context only; no proof, acceptance or milestone authority."
_REFERENCE_KEYS = {"encoding", "snapshot_ref", "source_ref", "sha256", "library_sha256",
                   "lean_toolchain", "module_inventory", "inline_modules", "omitted_modules", "authority"}


def _fail(message: str) -> None:
    raise blocked("STALE_OR_UNBOUND_EVIDENCE", "VSCore proof library context: " + message)


def _library(value: Any) -> dict[str, str]:
    if (not isinstance(value, dict) or set(value) != set(vscore3_target.LIB_MODULES)
            or any(not isinstance(text, str) for text in value.values())):
        _fail("expected the exact complete registered text module inventory")
    try:
        for text in value.values():
            text.encode("utf-8", "strict")
    except UnicodeError:
        _fail("module text is not valid UTF-8")
    return value


def _pin(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("missing Lean toolchain binding")
    return value


def _inventory(library: dict[str, str]) -> list[dict]:
    return [{"module": name, "sha256": canonical.digest(library[name].encode("utf-8")),
             "size": len(library[name].encode("utf-8"))} for name in sorted(library)]


def _omitted() -> list[str]:
    return sorted(set(vscore3_target.LIB_MODULES) - set(INLINE_MODULES))


def restore_verifier_library(pkg: Any, reference: dict) -> dict[str, str]:
    """Restore the exact historical library; never substitute current source bytes."""
    if (not isinstance(reference, dict) or set(reference) != _REFERENCE_KEYS
            or reference.get("encoding") != FORMAT or reference.get("source_ref") != SOURCE_REF
            or reference.get("inline_modules") != list(INLINE_MODULES)
            or reference.get("omitted_modules") != _omitted()
            or reference.get("authority") != AUTHORITY):
        _fail("malformed library reference")
    pin = _pin(reference["lean_toolchain"])
    agent_memory.latest_snapshot(pkg)  # A broken current journal cannot be bypassed by an old ref.
    restored = agent_memory.restore(pkg, reference["snapshot_ref"])
    if set(restored) != {SOURCE_REF}:
        _fail("retained library artifact inventory differs")
    raw = restored[SOURCE_REF]
    if canonical.digest(raw) != reference["sha256"]:
        _fail("retained library bytes differ")
    payload = canonical.loads(raw)
    if (not isinstance(payload, dict) or set(payload) != {"lean_toolchain", "modules"}
            or payload["lean_toolchain"] != pin):
        _fail("retained library toolchain differs")
    library = _library(payload["modules"])
    if (canonical.digest_json(library) != reference["library_sha256"]
            or _inventory(library) != reference["module_inventory"]):
        _fail("retained library module inventory differs")
    return library


def project_vscore_prompt(pkg: Any, data: dict) -> dict:
    """Select exact API modules once per source candidate, before proof retries.

    The caller binds its routing identity to the ORIGINAL full library mapping.
    Only the prompt is projected; every other context field and input object is
    preserved. Legacy VSCore packets are returned unchanged without storage.
    """
    if data.get("parameters", {}).get("backend_version") != "0.3":
        return data
    if "verifier_library_reference" in data:
        _fail("library context is already projected")
    library = _library(data.get("verifier_library"))
    pin = _pin(data.get("lean_toolchain"))
    current = {name: source.decode("utf-8") for name, source in vscore3_target.library_sources().items()}
    if library != current:
        _fail("supplied library differs from the current registered compiler inputs")
    raw = canonical.dumps({"lean_toolchain": pin, "modules": library})
    library_hash = canonical.digest_json(library)
    snapshot = agent_memory.checkpoint(pkg, "prover/vscore/library-context", {SOURCE_REF: raw},
        metadata={"encoding": FORMAT, "sha256": canonical.digest(raw),
                  "library_sha256": library_hash, "lean_toolchain": pin, "authority": AUTHORITY})
    reference = {"encoding": FORMAT, "snapshot_ref": snapshot["snapshot_ref"],
                 "source_ref": SOURCE_REF, "sha256": canonical.digest(raw),
                 "library_sha256": library_hash, "lean_toolchain": pin,
                 "module_inventory": _inventory(library), "inline_modules": list(INLINE_MODULES),
                 "omitted_modules": _omitted(), "authority": AUTHORITY}
    retained = restore_verifier_library(pkg, reference)
    return {**data, "verifier_library": {name: retained[name] for name in INLINE_MODULES},
            "verifier_library_reference": reference}
