"""Restorable surface-authoring view; never checker or prover input rewriting."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from . import agent_memory, canonical, author_reference
from .errors import blocked

FORMAT = "verislop.vscore-surface-authoring-context/0.2"
LEGACY_FORMAT = "verislop.vscore-surface-authoring-context/0.1"
GRAMMAR_PATH = "grammar/vscore-0.3.ebnf"
COMPILER_PATHS = ("verislop/targets/vscore3_source.py", "verislop/targets/vscore3_surface.py",
                  "verislop/targets/vscore_source.py")
AUTHORITY = ("Authoring input only. The host surface compiler is a trusted translation; "
             "only canonical program.vscore.json is certified by the unchanged native checks.")
REFERENCE_KEY = "surface_authoring_reference"
_ARTIFACTS = {"fixed-context.json", GRAMMAR_PATH, "compiler-sources.json"}
_KEYS = {"format", "snapshot_ref", "fixed_sha256", "grammar_sha256", "compiler_sha256",
         "lean_toolchain", "authority"}


def _fail(message: str) -> None:
    raise blocked("STALE_OR_UNBOUND_EVIDENCE", "VSCore surface authoring context: " + message)


def _fixed(value: Any) -> dict:
    if (not isinstance(value, dict) or REFERENCE_KEY in value or "source_grammar" not in value
            or value.get("parameters", {}).get("backend") != "verislop.backend.vscore/0.3"
            or value.get("parameters", {}).get("backend_version") != "0.3"
            or not isinstance(value.get("lean_toolchain"), str) or not value["lean_toolchain"].strip()):
        _fail("expected an original VSCore 0.3 context with grammar and toolchain")
    return value


def _view(fixed: dict, grammar: bytes, reference: dict, artifacts: dict) -> dict:
    selected = copy.deepcopy(fixed)
    selected["source_grammar"] = {"format": "ebnf", "path": GRAMMAR_PATH,
                                  "sha256": canonical.digest(grammar), "text": grammar.decode("utf-8")}
    selected[REFERENCE_KEY] = copy.deepcopy(reference)
    if reference["format"] == FORMAT:
        selected["accepted_reference"] = author_reference.project_reference(fixed,
            {key: artifacts[key] for key in author_reference.ARTIFACTS if key in artifacts})
    return selected


def restore_fixed_context(pkg: Any, selected: dict) -> dict:
    """Authenticate a historical view using retained bytes, never current source files."""
    reference = selected.get(REFERENCE_KEY) if isinstance(selected, dict) else None
    if (not isinstance(reference, dict) or set(reference) != _KEYS
            or reference.get("format") not in (FORMAT, LEGACY_FORMAT) or reference.get("authority") != AUTHORITY):
        _fail("malformed historical reference")
    agent_memory.latest_snapshot(pkg)
    artifacts = agent_memory.restore(pkg, reference["snapshot_ref"])
    extra = set(artifacts) - _ARTIFACTS
    expected_extras = (author_reference.ARTIFACTS, {author_reference.VIEW}) if reference["format"] == FORMAT else (set(),)
    if not _ARTIFACTS <= set(artifacts) or extra not in expected_extras:
        _fail("retained artifact inventory differs")
    for path, key in (("fixed-context.json", "fixed_sha256"), (GRAMMAR_PATH, "grammar_sha256"),
                      ("compiler-sources.json", "compiler_sha256")):
        if canonical.digest(artifacts[path]) != reference[key]:
            _fail("retained artifact binding differs: " + path)
    try:
        fixed = _fixed(canonical.loads(artifacts["fixed-context.json"]))
        compiler = canonical.loads(artifacts["compiler-sources.json"])
        if (not isinstance(compiler, dict) or set(compiler) != set(COMPILER_PATHS)
                or any(not isinstance(value, str) for value in compiler.values())):
            _fail("retained compiler inventory differs")
        if (fixed["lean_toolchain"] != reference["lean_toolchain"]
                or canonical.dumps(_view(fixed, artifacts[GRAMMAR_PATH], reference, artifacts)) != canonical.dumps(selected)):
            _fail("selected view or toolchain differs from its retained context")
    except (ValueError, UnicodeError, TypeError) as exc:
        _fail("invalid retained context encoding: " + str(exc))
    return fixed


def project_fixed_context(pkg: Any, fixed: dict) -> dict:
    """Retain once before retries; substitute only the exact registered EBNF grammar."""
    _fixed(fixed)
    root = Path(__file__).resolve().parent.parent
    grammar = (root / GRAMMAR_PATH).read_bytes()
    compiler = {path: (root / path).read_bytes().decode("utf-8") for path in COMPILER_PATHS}
    raw = canonical.dumps(fixed)
    compiler_raw = canonical.dumps(compiler)
    bindings = {"format": FORMAT, "fixed_sha256": canonical.digest(raw),
                "grammar_sha256": canonical.digest(grammar), "compiler_sha256": canonical.digest(compiler_raw),
                "lean_toolchain": fixed["lean_toolchain"], "authority": AUTHORITY}
    artifacts = {"fixed-context.json": raw, GRAMMAR_PATH: grammar, "compiler-sources.json": compiler_raw}
    artifacts.update(author_reference.capture_artifacts(pkg, fixed, retention_reserved_bytes=sum(map(len, artifacts.values()))))
    receipt = canonical.loads(artifacts[author_reference.VIEW])
    snapshot = agent_memory.checkpoint(pkg, "implementer/vscore/surface-authoring", artifacts,
        metadata={**bindings, "reference_display": {"mode": receipt["mode"], "reason": receipt["reason"],
                                                   "receipt_sha256": canonical.digest(artifacts[author_reference.VIEW])}})
    selected = _view(fixed, grammar, {**bindings, "snapshot_ref": snapshot["snapshot_ref"]}, artifacts)
    if canonical.dumps(restore_fixed_context(pkg, selected)) != raw:
        _fail("original fixed context did not restore exactly")
    return selected


def accepted_enums(fixed: dict) -> dict[str, list[str]]:
    """Use accepted constructor identities verbatim, including order and opaque IDs."""
    profile = fixed.get("accepted_profile")
    if not isinstance(profile, dict) or not isinstance(profile.get("enums", {}), dict):
        _fail("accepted enumeration inventory is malformed")
    result = {}
    for name, descriptor in profile.get("enums", {}).items():
        if (not isinstance(descriptor, dict) or not isinstance(descriptor.get("constructors"), list)
                or any(not isinstance(value, str) for value in descriptor["constructors"])):
            _fail("accepted enumeration constructor inventory is malformed")
        result[name] = list(descriptor["constructors"])
    return result
