"""`verislop link`: deterministic structural binding (LINKED).

A binding record connects one implementation object (file, qualified name, exact source hash)
to one accepted profile symbol (Lean declaration and its declaration hash) and the obligations
whose accepted statements depend on that symbol. Coverage is computed mechanically from the
accepted semantic closure; the candidate's own obligation lists are only checked against it.
Missing or competing bindings block; public objects nobody accounted for are reported.
A structural link resolves identity and coverage; it does not prove semantic equivalence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION, canonical, contract as C, fsutil
from .errors import Diagnostic
from .events import EventSink
from .export import verified_ir
from .lifecycle import claim_id
from .materialize import symbols_for
from .package import Package
from .stage import StageResult, status_from
from .targets import python_target as pt

VERIFIER = "verislop.python-linker"


def run(pkg: Package, events: EventSink, *, ir: Path | None = None, implementation: Path | None = None) -> StageResult:
    events.emit("stage_started", "link", "structural binding of implementation objects")
    result = StageResult("link", "PASS", "every required obligation has a unique structural binding")
    if ir is not None:
        pkg.set_path("accepted_ir", ir)
    if implementation is not None:
        pkg.set_path("implementation", implementation)
    irj, ir_hash, cert, diags = verified_ir(pkg)
    claims_path = pkg.path("closure") / "implementation-claims.json"
    bpath = pkg.path("bridges") / "bindings.json"
    if not claims_path.is_file() or not bpath.is_file():
        diags.append(Diagnostic("VERIFIER_NOT_RUN", "no implementation claims/binding proposal; run `verislop generate` first"))
    if diags:
        result.diagnostics = diags
        result.status = status_from(diags)
        return result
    assert irj is not None
    claims = canonical.load_file(claims_path)
    proposal = canonical.load_file(bpath)
    profile = C.frozen_json(pkg, "profile.json")
    statements = C.frozen_json(pkg, "statements.json")["statements"]
    frozen_hashes = C.frozen_json(pkg, "statements.json")["declaration_hashes"]
    impl = pkg.path("implementation")
    inv = pt.inventory(impl)
    from . import view

    current = view.derive(pkg)["obligations"]

    # -- validate the proposal ---------------------------------------------------------------------
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    by_object: dict[tuple[str, str], list[str]] = {}
    for b in proposal["bindings"]:
        by_symbol.setdefault(b["symbol"], []).append(b)
        by_object.setdefault((b["object"]["file"], b["object"]["qualname"]), []).append(b["binding_id"])
    for sym, bs in by_symbol.items():
        if sym not in profile["symbols"]:
            diags.append(Diagnostic("UNMAPPED_IMPLEMENTATION_OBJECT", f"binding to unknown profile symbol {sym}"))
        if len(bs) > 1:
            diags.append(Diagnostic("AMBIGUOUS_CORRESPONDENCE", f"symbol {sym} has competing bindings {[b['binding_id'] for b in bs]}"))
    for obj, ids in by_object.items():
        if len(ids) > 1:
            diags.append(Diagnostic("AMBIGUOUS_CORRESPONDENCE", f"object {obj[0]}:{obj[1]} appears in several bindings {ids}"))
    helpers = {(h["file"], h["qualname"]) for h in proposal.get("helpers", [])}
    for o in inv.objects:
        key = (o["file"], o["qualname"])
        if o["public"] and key not in by_object and key not in helpers:
            diags.append(Diagnostic("UNMAPPED_IMPLEMENTATION_OBJECT",
                                    f"public object {o['file']}:{o['qualname']} is neither bound nor declared a helper"))

    records: list[dict[str, Any]] = []
    for b in proposal["bindings"]:
        sym = profile["symbols"].get(b["symbol"])
        obj = inv.find(b["object"]["file"], b["object"]["qualname"])
        problems = []
        if obj is None:
            problems.append("implementation object does not exist")
        elif obj["kind"] != "function":
            problems.append(f"object is a {obj['kind']}, not a function")
        elif sym is not None:
            arity = len(sym["args"])
            if obj["varargs"] or obj["kwonly_required"] or not (obj["positional"] - obj["defaults"] <= arity <= obj["positional"]):
                problems.append(f"signature does not accept exactly {arity} positional argument(s)")
            if obj["decorated"]:
                problems.append("decorated functions are not bound structurally in v0.1")
        linkable = {c["obligation"] for c in claims["claims"] if c["milestone"] == "LINKED" and c["applicable"]}
        covered = sorted(oid for oid in irj["obligations"]
                         if oid in linkable and sym and b["symbol"] in symbols_for(oid, irj, profile, statements))
        claimed = set(b["obligations"])
        leak = sorted(claimed - set(covered))
        if leak:
            diags.append(Diagnostic("SCOPE_LEAK", f"binding {b['binding_id']} claims {', '.join(leak)}, whose accepted statements do not depend on {b['symbol']}"))
        for p in problems:
            diags.append(Diagnostic("UNMAPPED_IMPLEMENTATION_OBJECT", f"binding {b['binding_id']}: {p}"))
        if sym is None or obj is None or problems:
            continue
        records.append({
            "binding_id": b["binding_id"],
            "symbol": b["symbol"],
            "formal_declaration": {"lean_decl": sym["lean_decl"], "decl_hash": frozen_hashes[sym["lean_decl"]],
                                   "args": sym["args"], "result": sym["result"]},
            "implementation_object": {"file": obj["file"], "qualname": obj["qualname"], "source_hash": obj["source_hash"],
                                      "file_hash": inv.files[obj["file"]], "lineno": obj["lineno"]},
            "obligations": covered,
            "serialization_profile": pt.PROFILE_ID,
        })
    link = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "link_record",
        "accepted_ir": ir_hash,
        "implementation_root": pkg.implementation_root(),
        "serialization_profile": pt.PROFILE_DOC,
        "bindings": sorted(records, key=lambda r: r["binding_id"]),
        "correspondence": "structural identity and coverage only; semantic correspondence is not established at this tier",
    }
    fsutil.write_json(pkg.path("bridges") / "link.json", link, pretty=True)
    root = pkg.link_root()
    bound_syms = {r["symbol"]: r for r in records}
    required = [c for c in claims["claims"] if c["milestone"] == "LINKED" and c["applicable"]]
    for c in required:
        oid = c["obligation"]
        rec = irj["obligations"][oid]
        syms = symbols_for(oid, irj, profile, statements)
        missing = [s for s in syms if s not in bound_syms]
        pre = current.get(oid, {}).get("lifecycle", {})
        prereq = [m for m in ("TYPECHECKED", "IMPLEMENTED") if pre.get(m, {}).get("outcome") != "PASS"]
        global_block = [d for d in diags if d.code in ("AMBIGUOUS_CORRESPONDENCE",) or (d.code == "UNMAPPED_IMPLEMENTATION_OBJECT")]
        ok = not missing and not prereq and not global_block
        codes = (["UNMAPPED_IMPLEMENTATION_OBJECT"] if missing else []) + [d.code for d in global_block]
        if prereq:
            codes.append("VERIFIER_NOT_RUN")
        ev = pkg.evidence.record(
            claim_id=claim_id("LINKED", oid, rec["revision"]), verifier_id=VERIFIER, status="PASS" if ok else "BLOCK",
            scope=[f"link root {root}", "structural identity and coverage; not semantic equivalence"],
            input_root=root or "sha256:" + "0" * 64,
            result={"milestone_outcome": "PASS" if ok else "FAIL", "symbols": syms,
                    "bindings": [bound_syms[s]["binding_id"] for s in syms if s in bound_syms],
                    "missing_symbols": missing, "prerequisites_not_passed": prereq, "codes": sorted(set(codes))},
            invocation=["verislop", "link"])
        events.emit("verifier_decision", "link", f"{oid} LINKED {'PASS' if ok else 'FAIL'}", obligation_id=oid,
                    milestone="LINKED", outcome="PASS" if ok else "FAIL", evidence_ref=f"evidence:{ev.id}")
        if missing:
            diags.append(Diagnostic("UNMAPPED_IMPLEMENTATION_OBJECT", f"{oid}: no binding for symbol(s) {', '.join(missing)}", obligations=[oid]))
        if prereq:
            diags.append(Diagnostic("VERIFIER_NOT_RUN", f"{oid}: LINKED requires {', '.join(prereq)} to pass first", obligations=[oid]))
    view.write(pkg)
    result.diagnostics = diags
    result.status = status_from(diags)
    result.artifacts["link"] = pkg.rel(pkg.path("bridges") / "link.json")
    result.summary = {"link_root": root, "bindings": [{"symbol": r["symbol"], "object": f"{r['implementation_object']['file']}:{r['implementation_object']['qualname']}",
                                                      "obligations": r["obligations"]} for r in records]}
    for r in records:
        result.lines.append(f"{r['symbol']} <- {r['implementation_object']['file']}:{r['implementation_object']['qualname']} covers {', '.join(r['obligations'])}")
    return result
