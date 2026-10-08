"""`verislop accept`: the Lean acceptance boundary (specification §6).

Successful compilation of a candidate is never sufficient. The acceptance service:

1. verifies the frozen challenge inputs, policy and verifier hashes (pinned at freeze);
2. stages the exact challenge and proof-candidate bytes and elaborates both in the sandbox;
3. replays every candidate declaration through the kernel in a separate trusted process;
4. requires identical statements, referenced definitions, instances and registry metadata;
5. audits transitive axioms per theorem (sorry, native evaluation, unknown axioms rejected)
   from the replayed environment, never from data stored in candidate `.olean` files;
6. checks constructive witnesses, coverage, interpretation decisions and DSL denotations;
7. writes an immutable, content-addressed acceptance certificate and TYPECHECKED/PROVED evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION, canonical, contract, dsl, fsutil, leanbridge, policy as policymod, schemas
from .errors import Diagnostic
from .events import EventSink
from .exprjson import head_const, name_str
from .lifecycle import claim_id
from .package import Package
from .stage import StageResult, status_from
from .verifiers import verifier_hash

VERIFIER = "verislop.lean-acceptance"


def decode_witness_value(e: dict[str, Any], sort: Any, profile: dsl.Profile) -> Any:
    if sort == "Nat":
        if "lit" in e and "nat" in e["lit"]:
            return int(e["lit"]["nat"])
        n, args = head_const(e)
        if n == "Nat.zero" and not args:
            return 0
        if n == "Nat.succ" and len(args) == 1:
            return decode_witness_value(args[0], "Nat", profile) + 1
        raise ValueError("witness is not a Nat literal")
    n, args = head_const(e)
    if sort == "Bool" and n in ("Bool.true", "Bool.false") and not args:
        return n == "Bool.true"
    if sort == "Unit" and n in ("Unit.unit", "PUnit.unit") and not args:
        return dsl.UNIT
    if isinstance(sort, dict) and "enum" in sort:
        en = profile.enums[sort["enum"]]
        if n in en["lean_constructors"] and not args:
            return dsl.enum_v(sort["enum"], en["constructors"][en["lean_constructors"].index(n)])
    if isinstance(sort, dict) and "result" in sort and n in ("Except.ok", "Except.error") and len(args) == 3:
        side = "ok" if n == "Except.ok" else "error"
        return (side, decode_witness_value(args[2], sort["result"][side], profile))
    raise ValueError(f"witness value does not decode at sort {dsl.sort_str(sort)}")


def match_witnesses(formula: dict[str, Any], shape: dict[str, Any], profile: dsl.Profile) -> list[list[Any]]:
    """Check the extracted proof shape against the existential formula; return witness tuples."""
    if formula["tag"] == "and":
        if "and" not in shape:
            raise ValueError("proof of a conjunction is not an And.intro after head normalisation")
        return match_witnesses(formula["left"], shape["and"][0], profile) + match_witnesses(formula["right"], shape["and"][1], profile)
    values: list[Any] = []
    f, s = formula, shape
    while f["tag"] == "exists":
        if "exists" not in s:
            raise ValueError("existential proof is not a concrete Exists.intro (non-constructive or opaque)")
        values.append(decode_witness_value(s["exists"]["witness"], f["sort"], profile))
        f, s = f["body"], s["exists"]["rest"]
    return [values]


def _jsonable(v: Any) -> Any:
    if isinstance(v, tuple):
        return {"tuple": [_jsonable(x) for x in v]}
    return v


def kernel_request(form: dict[str, Any], active: list[dict[str, Any]]) -> dict[str, Any]:
    """The exact kernel-tool request whose response is the certified environment export."""
    from .exprjson import parse_name

    names = contract.binding_names(form)
    witness_thms = [names[r["id"]][0] for r in active if r["kind"] == "non_vacuity"]
    return {"export": True, "axioms": True, "witnesses": [parse_name(n) for n in witness_thms]}


def run(pkg: Package, events: EventSink, *, contract: Path | None = None, policy_name: str = "strict") -> StageResult:
    from . import contract as C

    if contract is not None:
        pkg.set_path("contract", contract)
    events.emit("stage_started", "accept", "isolated acceptance of the proof candidate")
    result = StageResult("accept", "PASS", "every required obligation TYPECHECKED and PROVED under the frozen policy")
    ch, fdiags = C.load_frozen(pkg)
    if fdiags:
        result.diagnostics.extend(fdiags)
        result.status = "BLOCKED"
        return result
    chdir = C.challenge_dir(pkg)
    pol = C.frozen_json(pkg, "policy.json")
    form = C.frozen_json(pkg, "formalization.json")
    frozen_profile = C.frozen_json(pkg, "profile.json")
    frozen_st = C.frozen_json(pkg, "statements.json")
    frozen_verifiers = C.frozen_json(pkg, "verifiers.json")
    claims = canonical.load_file(pkg.path("claims"))
    records = claims["obligations"]
    root = ch["contract_input_root"]
    requested = policymod.get(policy_name)
    if requested["id"] != pol["id"]:
        result.diagnostics.append(Diagnostic(
            "CLAIM_MUTATION", f"the challenge was frozen under {pol['id']}; accepting under {requested['id']} would change "
            "the trust policy, which requires a new candidate in a new run"))
    current = {"kernel_tool": leanbridge.kernel_tool_hash(), VERIFIER: verifier_hash(VERIFIER),
               "verislop.reifier": verifier_hash("verislop.reifier"),
               "verislop.formal-statement-checker": verifier_hash("verislop.formal-statement-checker")}
    for k, v in current.items():
        if frozen_verifiers.get(k) != v:
            result.diagnostics.append(Diagnostic(
                "STALE_OR_UNBOUND_EVIDENCE", f"verifier {k} changed since the challenge was frozen; a verifier change requires a new run"))
    cand_path = pkg.path("contract") / "proofs" / "candidate.lean"
    if not cand_path.is_file():
        result.diagnostics.append(Diagnostic("VERIFIER_NOT_RUN", "no proof candidate; run `verislop prove` first"))
    if result.diagnostics:
        result.status = status_from(result.diagnostics)
        return result

    tc = leanbridge.resolve_toolchain((chdir / "lean-toolchain").read_text())
    challenge_src = (chdir / "Contract.lean").read_bytes()
    solution_src = cand_path.read_bytes()
    active = [r for r in records if not r["blocked_by"]]
    diags: list[Diagnostic] = []
    kopts = dict(timeout=pol["kernel_timeout_seconds"], memory_mb=pol["memory_mb"],
                 require_network_isolation=pol["require_network_isolation"])
    with fsutil.temporary_directory(prefix="verislop-accept-") as tmp:
        tmpd = Path(tmp)
        # -- re-derive the challenge (determinism of the statement checker) --------------------------
        events.emit("progress", "accept", "re-elaborating the frozen challenge in an isolated stage")
        cc = leanbridge.compile_module(tc, challenge_src, tmpd / "challenge", timeout=pol["build_timeout_seconds"],
                                       memory_mb=pol["memory_mb"], require_network_isolation=pol["require_network_isolation"])
        if not cc.ok:
            diags.append(Diagnostic("NONDETERMINISM", "the frozen challenge no longer elaborates: " + "; ".join(cc.errors[:3])))
        else:
            cexp = leanbridge.run_kernel_tool(tc, cc.olean, {"export": True, "axioms": True}, **kopts)
            cenv = C.Env.from_export(cexp, pol, "challenge")
            if cenv.hashes != frozen_st["declaration_hashes"]:
                diags.append(Diagnostic("NONDETERMINISM", "re-elaborating the frozen challenge produced different declarations"))
        # -- the proof candidate ------------------------------------------------------------------------
        events.emit("progress", "accept", "elaborating the proof candidate in the sandbox")
        sc = leanbridge.compile_module(tc, solution_src, tmpd / "solution", timeout=pol["build_timeout_seconds"],
                                       memory_mb=pol["memory_mb"], require_network_isolation=pol["require_network_isolation"])
        sandbox_obs = sc.isolation
        if not sc.ok:
            diags.append(Diagnostic("CANDIDATE_BUILD_FAILURE", "the proof candidate does not elaborate: " + "; ".join(sc.errors[:3]),
                                    obligations=[r["id"] for r in active]))
            senv = None
        else:
            events.emit("progress", "accept", "kernel replay, export, axiom walk and witness extraction")
            sexp = leanbridge.run_kernel_tool(tc, sc.olean, kernel_request(form, active), **kopts)
            senv = C.Env.from_export(sexp, pol, "proof candidate")
            olean_bytes = sc.olean.read_bytes()
            diags.extend(senv.diagnostics)

    obligations: dict[str, dict[str, Any]] = {}
    statements_frozen = frozen_st["statements"]
    witnesses: dict[str, Any] = {}
    if senv is not None and not any(d.code == "KERNEL_REJECTION" for d in senv.diagnostics):
        closure_id, cdiags = leanbridge.olean_closure_identity(tc, sexp["import"]["modules"])
        diags.extend(cdiags)
        if closure_id != frozen_st["olean_closure"]:
            diags.append(Diagnostic("UNDECLARED_DEPENDENCY", "the proof candidate imports a different toolchain module closure than the frozen challenge"))
        # Statement identity: every declaration the frozen statements depend on, plus the registry.
        must_match = {n for st in statements_frozen.values() for n in st["semantic_closure"]}
        must_match |= {n for n in frozen_st["declaration_hashes"] if n.startswith(C.REGISTRY_NS + ".")}
        changed: set[str] = set()
        for n in sorted(must_match):
            want = frozen_st["declaration_hashes"].get(n)
            got = senv.hashes.get(n)
            if got != want:
                changed.add(n)
                affected = [oid for oid, st in statements_frozen.items() if n in st["semantic_closure"]] or [r["id"] for r in active]
                code = "CLAIM_MUTATION" if n.startswith(C.REGISTRY_NS + ".") else "STATEMENT_MISMATCH"
                diags.append(Diagnostic(code, f"declaration {n} differs from the frozen challenge ({'missing' if got is None else 'changed'})", obligations=affected))
        for n in sorted(senv.decls):
            if n.startswith(C.REGISTRY_NS + ".") and n not in frozen_st["declaration_hashes"]:
                diags.append(Diagnostic("CLAIM_MUTATION", f"the proof candidate adds {n} to the reserved registry namespace; "
                                        "registry metadata is generated at freeze and carries no authority", obligations=[r["id"] for r in active]))
        analysis = C.analyze(senv, records, form, pol, form["lean_toolchain"].strip(), "proof candidate")
        diags.extend(d for d in analysis.diagnostics if d.severity != "warning")
        if analysis.profile is not None and canonical.dumps(analysis.profile) != canonical.dumps(frozen_profile):
            diags.append(Diagnostic("STATEMENT_MISMATCH", "the semantic profile derived from the proof candidate differs from the frozen profile"))
        for oid, st in analysis.statements.items():
            if st["statement_hash"] != statements_frozen.get(oid, {}).get("statement_hash"):
                diags.append(Diagnostic("STATEMENT_MISMATCH", f"{oid}: accepted statement differs from the frozen challenge", obligations=[oid]))
        if analysis.defeq_requests:
            with fsutil.temporary_directory(prefix="verislop-accept-olean-") as tmp2:
                op = Path(tmp2) / "VeriSlopContract.olean"
                op.write_bytes(olean_bytes)
                resp = leanbridge.run_kernel_tool(tc, op, {"defeq": analysis.defeq_requests}, **kopts)
            diags.extend(C.defeq_diagnostics(resp, "proof candidate"))
        profile = dsl.Profile.from_json(frozen_profile)
        # Witnesses
        wres = {name_str(w["theorem"]): w for w in sexp.get("witnesses", [])}
        thm_of = {oid: st.get("lean_symbol") for oid, st in statements_frozen.items()}
        for r in active:
            if r["kind"] != "non_vacuity":
                continue
            st = statements_frozen[r["id"]]
            w = wres.get(thm_of[r["id"]])
            try:
                if not w or not w.get("ok"):
                    raise ValueError((w or {}).get("error", "no witness extraction result"))
                tuples = match_witnesses(st["formula_package"]["formula"], w["shape"], profile)
                witnesses[r["id"]] = [[_jsonable(v) for v in t] for t in tuples]
            except ValueError as exc:
                diags.append(Diagnostic("MISSING_WITNESS", f"{r['id']}: no concrete checked witness: {exc}", obligations=[r["id"]]))
        # Per-obligation outcomes
        theorem_obl = {st["lean_symbol"]: oid for oid, st in statements_frozen.items() if st["role"] == "guarantee"}
        module_decls = senv.decls
        blocking_by_obl: dict[str, list[str]] = {}
        for d in diags:
            if d.severity in ("blocking", "infrastructure"):
                for oid in d.obligations:
                    blocking_by_obl.setdefault(oid, []).append(d.code)
        global_block = [d.code for d in diags if d.severity in ("blocking", "infrastructure") and not d.obligations]
        # Witness obligations first: a guarantee's witness requirement needs an accepted (PROVED) witness.
        for r in sorted(active, key=lambda x: 0 if x["kind"] == "non_vacuity" else 1):
            oid = r["id"]
            st = statements_frozen[oid]
            codes = sorted(set(blocking_by_obl.get(oid, []) + global_block))
            # A well-typed declaration with an inadmissible proof still TYPECHECKS; PROVED fails.
            typechecked = "FAIL" if any(c in codes for c in ("STATEMENT_MISMATCH", "CLAIM_MUTATION", "KERNEL_REJECTION",
                                                           "IR_REIFICATION_MISMATCH", "UNDECLARED_DEPENDENCY", "NONDETERMINISM",
                                                           "UNSUPPORTED_SEMANTICS")) else "PASS"
            axioms: list[str] = []
            uses: list[str] = []
            proved = "NOT_APPLICABLE"
            if r["role"] == "guarantee":
                thm = st["lean_symbol"]
                c = module_decls.get(thm)
                axioms = [name_str(a) for a in c.get("axioms", [])] if c else []
                for ax in axioms:
                    kind = policymod.classify_axiom(ax, pol)
                    if kind == "sorry":
                        codes.append("PROOF_UNRESOLVED")
                        diags.append(Diagnostic("PROOF_UNRESOLVED", f"{oid}: {thm} depends on sorryAx", obligations=[oid]))
                    elif kind in ("native", "unauthorized"):
                        codes.append("INADMISSIBLE_AXIOM")
                        diags.append(Diagnostic("INADMISSIBLE_AXIOM", f"{oid}: {thm} depends on {'native-evaluation' if kind == 'native' else 'unauthorized'} axiom {ax}", obligations=[oid]))
                if c and c.get("unresolved_constants"):
                    codes.append("KERNEL_REJECTION")
                # uses_proof: obligation theorems reachable from the proof term through module lemmas
                seen: set[str] = set()
                stack = [name_str(x) for x in (c or {}).get("value_constants", [])]
                while stack:
                    n = stack.pop()
                    if n in seen or n not in module_decls:
                        continue
                    seen.add(n)
                    if n in theorem_obl and theorem_obl[n] != oid:
                        uses.append(theorem_obl[n])
                    dc = module_decls[n]
                    stack += [name_str(x) for x in dc.get("value_constants", [])]
                if pol["require_witnesses"]:
                    for h in st["hypotheses"]:
                        covering = [i["id"] for i in form["internal_obligations"] if h in i["witnesses_for"]]
                        if not any(w in witnesses and obligations.get(w, {}).get("proved") == "PASS" for w in covering):
                            codes.append("MISSING_WITNESS")
                            diags.append(Diagnostic("MISSING_WITNESS", f"{oid}: assumption {h} has no accepted concrete witness", obligations=[oid]))
                codes = sorted(set(codes))
                proved = "PASS" if typechecked == "PASS" and not codes else "FAIL"
            obligations[oid] = {
                "revision": r["revision"], "kind": r["kind"], "role": r["role"],
                "representation": st["representation"], "lean_symbol": st.get("lean_symbol"),
                "statement_hash": st["statement_hash"], "typechecked": typechecked, "proved": proved,
                "axioms": axioms, "codes": sorted(set(codes)), "uses_proof": sorted(set(uses)),
                "witnesses": witnesses.get(oid),
            }
    else:
        for r in active:
            obligations[r["id"]] = {
                "revision": r["revision"], "kind": r["kind"], "role": r["role"], "representation": "none",
                "lean_symbol": None, "statement_hash": statements_frozen.get(r["id"], {}).get("statement_hash"),
                "typechecked": "FAIL", "proved": "FAIL" if r["role"] == "guarantee" else "NOT_APPLICABLE",
                "axioms": [], "codes": sorted({d.code for d in diags if d.severity == "blocking"}), "uses_proof": [], "witnesses": None,
            }
        olean_bytes = b""
        sexp = {"import": {}, "replay": {}}

    for r in records:
        if r["blocked_by"]:
            diags.append(Diagnostic("INTERPRETATION_UNRESOLVED", f"{r['id']} is blocked by {', '.join(r['blocked_by'])} and was not accepted", obligations=[r["id"]]))
            obligations[r["id"]] = {
                "revision": r["revision"], "kind": r["kind"], "role": r["role"], "representation": "none",
                "lean_symbol": None, "statement_hash": None, "typechecked": "PENDING",
                "proved": "PENDING" if r["role"] == "guarantee" else "NOT_APPLICABLE",
                "axioms": [], "codes": ["INTERPRETATION_UNRESOLVED"], "uses_proof": [], "witnesses": None}

    # ---- immutable, content-addressed accepted artifacts and certificate -------------------------------
    acc = pkg.path("accepted")
    def store(kind: str, data: bytes, ext: str) -> dict[str, str]:
        h = canonical.digest(data)
        rel = f"{pkg.rel(acc)}/{kind}/{h.split(':')[1]}.{ext}"
        fsutil.write_once(pkg.root / rel, data)
        return {"path": rel, "sha256": h}

    artifacts = {
        "source": store("source", solution_src, "lean"),
        "olean": store("olean", olean_bytes, "olean"),
        "environment_export": store("environment", canonical.dumps(sexp), "json"),
        "profile": store("profile", canonical.dumps(frozen_profile), "json"),
        "statements": store("statements", canonical.dumps(frozen_st), "json"),
    }
    required_ok = all(
        (o["typechecked"] == "PASS") and (o["proved"] in ("PASS", "NOT_APPLICABLE"))
        for oid, o in obligations.items() if next(r for r in records if r["id"] == oid)["required"])
    gate = ("accepted_and_proved" if pol["gate"] == "accepted_and_proved" else "typechecked_exploratory") if required_ok else "blocked"
    cert = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "acceptance_certificate",
        "contract_input_root": root,
        "gate": gate,
        "policy": {"id": pol["id"], "hash": policymod.policy_hash(pol), "allowed_axioms": pol["allowed_axioms"]},
        "toolchain": tc.identity(),
        "olean_closure": frozen_st["olean_closure"],
        "checkers": current,
        "sandbox": sandbox_obs,
        "artifacts": artifacts,
        "obligations": obligations,
        "diagnostics": [d.to_json() for d in diags],
    }
    issues = schemas.validate("acceptance-certificate", cert)
    if issues:
        raise RuntimeError(f"internal certificate failed schema validation: {issues[0]}")
    cert_bytes = canonical.dumps(cert)
    cert_ref = store("certificates", cert_bytes, "json")
    fsutil.atomic_write(acc / "acceptance.json", cert_bytes)
    result.artifacts.update({"certificate": pkg.rel(acc / "acceptance.json"), "certificate_immutable": cert_ref["path"]})

    for r in active:
        o = obligations[r["id"]]
        for milestone, outcome in (("TYPECHECKED", o["typechecked"]), ("PROVED", o["proved"])):
            if outcome == "NOT_APPLICABLE":
                continue
            ev = pkg.evidence.record(
                claim_id=claim_id(milestone, r["id"], r["revision"]), verifier_id=VERIFIER,
                status="PASS" if outcome == "PASS" else "BLOCK",
                scope=[f"contract input root {root}", f"certificate {cert_ref['sha256']}",
                       "reference-model theorem (Lean); not an implementation theorem" if milestone == "PROVED" else "kernel-replayed declaration matching the frozen challenge"],
                input_root=root,
                result={"milestone_outcome": outcome, "codes": o["codes"], "certificate": cert_ref["path"],
                        "certificate_hash": cert_ref["sha256"], "axioms": o["axioms"], "statement_hash": o["statement_hash"],
                        "binding_root": "contract_input_root", "policy": pol["id"]},
                invocation=["verislop", "accept", "--policy", policy_name],
                environment={"lean_toolchain": tc.pin})
            events.emit("verifier_decision", "accept", f"{r['id']} {milestone} {outcome}", obligation_id=r["id"],
                        milestone=milestone, outcome=outcome, evidence_ref=f"evidence:{ev.id}")
    result.diagnostics.extend(diags)
    if gate == "blocked" and not any(d.severity in ("blocking", "infrastructure") for d in diags):
        result.diagnostics.append(Diagnostic("PROOF_UNRESOLVED", "required obligations are not accepted"))
    if gate == "typechecked_exploratory":
        result.diagnostics.append(Diagnostic("UNSUPPORTED_CAPABILITY", "exploratory policy: the contract is not labelled accepted-and-proved", severity="warning"))
    result.status = status_from(result.diagnostics)
    result.summary = {"gate": gate, "certificate_hash": cert_ref["sha256"], "contract_input_root": root,
                      "obligations": {k: {"typechecked": v["typechecked"], "proved": v["proved"], "axioms": v["axioms"],
                                          "codes": v["codes"]} for k, v in obligations.items()}}
    for oid, o in obligations.items():
        ax = ", ".join(o["axioms"]) or "none"
        result.lines.append(f"{oid}: TYPECHECKED {o['typechecked']}, PROVED {o['proved']} (axioms: {ax})" + (f" witnesses {o['witnesses']}" if o["witnesses"] else ""))
    return result
