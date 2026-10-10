"""IMPLEMENTED: registered materialization/build check for Python candidates.

A concrete artifact exists for an obligation when every implementation symbol the obligation's
accepted statement depends on is proposed to be implemented by an existing top-level function
in the exact candidate bytes, and those bytes byte-compile in the sandbox. The record names the
source and object hashes and the entry-point inventory. The implementation may still be wrong.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import fsutil, native_source
from .errors import Diagnostic
from .events import EventSink
from .lifecycle import claim_id
from .package import Package
from .targets import python_target as pt

VERIFIER = "verislop.python-materializer"


def symbols_for(oid: str, ir: dict[str, Any], profile: dict[str, Any], frozen_statements: dict[str, Any]) -> list[str]:
    """Profile symbols an obligation depends on, from its accepted semantic closure."""
    closure = set(frozen_statements[oid]["semantic_closure"])
    symbols = {sid for sid, s in profile["symbols"].items() if s["lean_decl"] in closure}
    from . import native_contract
    package = frozen_statements[oid].get("formula_package", {})
    symbols.update(native_contract.symbols(package))
    return sorted(symbols)


def run(pkg: Package, events: EventSink, ir: dict[str, Any], profile: dict[str, Any], frozen_statements: dict[str, Any],
        claims: dict[str, Any], bindings: dict[str, Any]) -> list[Diagnostic]:
    impl = pkg.path("implementation")
    inv = pt.inventory(impl)
    diags: list[Diagnostic] = [Diagnostic("CANDIDATE_BUILD_FAILURE", f"syntax error: {e}") for e in inv.errors]
    source = native_source.for_package(pkg, ir, profile, bindings=bindings, statements=frozen_statements)
    diags.extend(native_source.diagnostics(source))
    if source["accepted"]:
        with fsutil.temporary_directory(prefix="verislop-materialize-") as tmp:
            bc = pt.byte_compile(impl, list(inv.files), Path(tmp))
    else:
        bc = {"ok": False, "errors": ["native source boundary admission did not pass"], "pyc": {}, "isolation": {}}
    if not bc["ok"]:
        diags.append(Diagnostic("CANDIDATE_BUILD_FAILURE", "byte compilation failed: " + "; ".join(bc["errors"][:3])))
    root = pkg.implementation_root()
    proposed = {b["symbol"]: b for b in bindings["bindings"]}
    required = {c["obligation"] for c in claims["claims"] if c["milestone"] == "IMPLEMENTED" and c["applicable"]}
    for oid in sorted(required):
        rec = ir["obligations"][oid]
        syms = symbols_for(oid, ir, profile, frozen_statements)
        problems = []
        objects = []
        for s in syms:
            b = proposed.get(s)
            if b is None:
                problems.append(f"no implementation object is proposed for symbol {s}")
                continue
            obj = inv.find(b["object"]["file"], b["object"]["qualname"])
            if obj is None:
                problems.append(f"{b['object']['file']}:{b['object']['qualname']} does not exist as a top-level object")
            elif obj["kind"] != "function":
                problems.append(f"{b['object']['qualname']} is a {obj['kind']}; python-v0_1 binds plain functions")
            else:
                objects.append(obj)
        ok = bc["ok"] and not inv.errors and not problems and source["accepted"]
        ev = pkg.evidence.record(
            claim_id=claim_id("IMPLEMENTED", oid, rec["revision"]), verifier_id=VERIFIER,
            status="PASS" if ok else "BLOCK",
            scope=[f"implementation root {root}", "artifact exists and byte-compiles; correctness not established"],
            input_root=root,
            result={"milestone_outcome": "PASS" if ok else "FAIL", "symbols": syms, "objects": objects,
                    "files": inv.files, "pyc": bc["pyc"], "problems": problems + bc["errors"],
                    "codes": [] if ok else ["CANDIDATE_BUILD_FAILURE"], "python": pt.python_identity(),
                    "entry_points": [o for o in inv.objects if o["public"]],
                    **({"native_source": source} if source["enabled"] else {})},
            invocation=["verislop", "generate"])
        events.emit("verifier_decision", "generate", f"{oid} IMPLEMENTED {'PASS' if ok else 'FAIL'}", obligation_id=oid,
                    milestone="IMPLEMENTED", outcome="PASS" if ok else "FAIL", evidence_ref=f"evidence:{ev.id}")
        for p in problems:
            diags.append(Diagnostic("CANDIDATE_BUILD_FAILURE", f"{oid}: {p}", obligations=[oid]))
    return diags
