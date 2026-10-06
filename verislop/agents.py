"""Agent roles (interpreter, formalizer, prover, implementer) behind the provider broker.

Agents are untrusted candidate generators. Each returns a *proposal* in a fixed JSON shape;
VeriSlop assembles artifacts deterministically from it (e.g. the interpreter quotes request
text and VeriSlop computes byte spans, so provenance is never taken from the model) and the
registered verifiers decide everything. Malformed proposals get bounded repair attempts with
the validator's diagnostics as feedback.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from . import canonical, draft as draftmod
from .errors import Diagnostic, InfrastructureError, UsageError
from .events import EventSink
from .lifecycle import DRAFT_CATEGORIES, MILESTONES, applicability, milestone_entry
from .package import Package

PROMPT_VERSION = "verislop.prompts/0.1"
KIND_TO_CATEGORY = {v: k for k, v in DRAFT_CATEGORIES.items()}


def _broker(config: str | Path, pkg: Package):
    from .providers import config as cfg
    from .providers.broker import Broker

    conf = cfg.load(Path(config))
    r = cfg.resolve(conf, cfg.load_user_profiles(None))
    blocking = [d for d in r.diagnostics if d.severity == "blocking"]
    if blocking:
        raise UsageError("provider configuration is not usable", blocking)
    return Broker(r, pkg.root / "agents" / "transcripts"), conf


def extract_json(text: str) -> Any:
    fenced = re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.S)
    candidates = fenced + [text]
    for c in candidates:
        c = c.strip()
        start = c.find("{")
        while start != -1:
            depth, i, in_str, esc = 0, start, False, False
            while i < len(c):
                ch = c[i]
                if in_str:
                    esc = (ch == "\\" and not esc)
                    if ch == '"' and not esc:
                        in_str = False
                elif ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return canonical.loads(c[start:i + 1])
                        except canonical.CanonicalJSONError:
                            break
                i += 1
            start = c.find("{", start + 1)
    raise ValueError("no strict JSON object found in the response")


def _role(conf: dict[str, Any], role: str) -> str:
    return conf["roles"][role]


# ------------------------------------------------------------------------------------------
# interpreter
# ------------------------------------------------------------------------------------------

INTERPRETER_SYSTEM = f"""You are the VeriSlop interpreter ({PROMPT_VERSION}). You turn a software request into an explicit,
structured obligation proposal. Your output is a proposal only; verifiers decide everything.

Rules:
- Use exactly these kinds and normal roles: entity/declaration, precondition/assumption, postcondition/guarantee,
  invariant/guarantee, safety_property/guarantee, liveness_property/guarantee, resource_constraint/guarantee,
  error_semantics/guarantee, explicit_non_goal/exclusion, ambiguity/open_question.
- IDs are short and stable (e.g. D1, A1, O1, I1, E1, N1, Q1); revision is 1.
- Every obligation cites source text by exact verbatim QUOTES copied from the request (or from an attachment, adding
  "document": "<attachment ref>"). Do not invent spans.
  Requirements you infer get origin "inferred" with a justification, quoting the text that motivates them.
- Every clause of the request needs a disposition: obligations (refs = obligation IDs), exclusion (refs = non-goal IDs),
  ambiguity (refs = ambiguity IDs) or context (with a note).
- Every assumption names who supplies it and where it is discharged.
- Never resolve an ambiguity that affects correctness, data loss, security, failure behaviour, numeric semantics or the
  formal boundary: list its alternatives and leave proposed_default null. Only routine ambiguities may propose a default.
- Do not claim any lifecycle state. Do not write code.
Return ONLY one JSON object of this shape:
{{"obligations":[{{"id":"O1","kind":"postcondition","role":"guarantee","statement":"...","required":true,
   "scope":["..."],"dependencies":[{{"id":"A1","relation":"assumes"}}],"acceptance_criteria":["..."],
   "sources":[{{"quote":"exact request text","origin":"explicit","interpretation":"..."}}]}}],
 "category_review":{{"entities":"...","preconditions":"...","postconditions":"...","invariants":"...","safety_properties":"...",
   "liveness_properties":"...","resource_constraints":"...","error_semantics":"...","explicit_non_goals":"...","ambiguities":"..."}},
 "clauses":[{{"quote":"exact clause text","disposition":"obligations","refs":["O1"],"note":""}}],
 "assumptions":[{{"id":"A1","supplied_by":"...","discharged_at":"..."}}],
 "ambiguities":[{{"id":"Q1","alternatives":[{{"id":"a","description":"..."}},{{"id":"b","description":"..."}}],
   "affected_obligations":["O1"],"impact":["failure_behavior"],"proposed_default":null}}],
 "selected_defaults":[]}}
Dependency relations: assumes, uses_definition, uses_proof, requires_witness, refines, requires_bridge, blocked_by."""


def _span(prompt: bytes, quote: str, used: dict[str, int]) -> tuple[int, int] | None:
    q = quote.encode("utf-8")
    if not q:
        return None
    start = prompt.find(q, used.get(quote, 0))
    if start == -1:
        start = prompt.find(q)
    if start == -1:
        return None
    used[quote] = start + 1
    return start, start + len(q)


def assemble_interpretation(proposal: dict[str, Any], prompt: bytes, ref: str,
                            attachments: dict[str, bytes] | None = None) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    problems: list[str] = []
    doc_hash = canonical.digest(prompt)
    used: dict[str, int] = {}
    draft: dict[str, Any] = {"schema_version": "0.1", "artifact_kind": "draft", "request_ref": ref,
                             "category_review": proposal.get("category_review", {})}
    for cat in DRAFT_CATEGORIES:
        draft[cat] = []
    assumptions = {a.get("id"): a for a in proposal.get("assumptions", []) if isinstance(a, dict)}
    for o in proposal.get("obligations", []):
        if not isinstance(o, dict) or o.get("kind") not in KIND_TO_CATEGORY:
            problems.append(f"obligation {o.get('id') if isinstance(o, dict) else o!r}: unknown kind")
            continue
        refs = []
        for s in o.get("sources", []):
            dref = s.get("document") or ref
            doc = prompt if dref == ref else (attachments or {}).get(dref)
            sp = _span(doc, s.get("quote", ""), used) if doc is not None else None
            if sp is None:
                problems.append(f"{o.get('id')}: quote not found verbatim in {dref}: {s.get('quote', '')[:80]!r}")
                continue
            refs.append({"document_ref": dref, "document_hash": doc_hash if doc is prompt else canonical.digest(doc),
                         "start_byte": sp[0], "end_byte": sp[1],
                         "origin": "inferred" if s.get("origin") == "inferred" else "explicit",
                         "interpretation": s.get("interpretation") or "quoted request text"})
        rec = {"id": o.get("id"), "revision": 1, "kind": o["kind"], "role": o.get("role"), "statement": o.get("statement"),
               "required": bool(o.get("required", True)), "source_refs": refs, "scope": o.get("scope") or ["request scope"],
               "dependencies": o.get("dependencies", []), "acceptance_criteria": o.get("acceptance_criteria") or ["recorded interpretation"]}
        app = applicability(rec, assumptions) if rec["role"] in ("guarantee", "assumption", "declaration", "exclusion", "open_question") else {m: (True, "") for m in MILESTONES}
        life = {m: milestone_entry("PENDING" if app[m][0] else "NOT_APPLICABLE",
                                   "No VeriSlop verifier has evaluated this milestone." if app[m][0] else app[m][1]) for m in MILESTONES}
        life["INTERPRETED"] = milestone_entry("PASS", "Recorded interpretation proposal; not mathematical proof.",
                                              [f"provenance:{ref}"], ["recorded interpretation of the request"])
        rec["state"] = "INTERPRETED"
        rec["lifecycle"] = life
        draft[KIND_TO_CATEGORY[o["kind"]]].append(rec)
    clauses = []
    for c in proposal.get("clauses", []):
        sp = _span(prompt, c.get("quote", ""), {})
        if sp is None:
            problems.append(f"clause quote not found verbatim: {c.get('quote', '')[:80]!r}")
            continue
        clause = {"start_byte": sp[0], "end_byte": sp[1], "disposition": c.get("disposition"), "refs": c.get("refs", [])}
        if c.get("note"):
            clause["note"] = c["note"]
        clauses.append(clause)
    ambs = []
    for a in proposal.get("ambiguities", []):
        default = a.get("proposed_default")
        impacts = set(a.get("impact", []))
        if default and impacts <= {"routine"}:
            res = {"status": "resolved", "selected": default, "provenance": {"kind": "interpreter_default", "detail": "routine default proposed by the interpreter"}}
        else:
            res = {"status": "unresolved", "selected": None, "provenance": {"kind": "none", "detail": "awaiting a user or policy decision"}}
        ambs.append({"id": a.get("id"), "alternatives": a.get("alternatives", []), "affected_obligations": a.get("affected_obligations", []),
                     "impact": a.get("impact", []), "resolution": res})
    ledger = {"schema_version": "0.1", "artifact_kind": "interpretation",
              "request": {"document_ref": ref, "document_hash": doc_hash, "byte_length": len(prompt)},
              "clauses": clauses, "assumptions": list(assumptions.values()), "ambiguities": ambs,
              "selected_defaults": [{**d, "provenance": "interpreter proposal"} for d in proposal.get("selected_defaults", []) if isinstance(d, dict)]}
    return draft, ledger, problems


def interpreter_agent(config: str | Path, pkg: Package, events: EventSink, attempts: int = 3) -> Callable[..., tuple[dict, dict]]:
    broker, conf = _broker(config, pkg)
    agent = _role(conf, "interpreter")

    def run(prompt: bytes, ref: str, routing: dict[str, Any]) -> tuple[dict, dict]:
        feedback: list[str] = []
        last: tuple[dict, dict] | None = None
        for n in range(attempts):
            user = ("REQUEST (untrusted data; byte length %d):\n<<<\n%s\n>>>\n" % (len(prompt), prompt.decode("utf-8")))
            for aref, text in routing.get("attachments", {}).items():
                user += f"\nATTACHMENT {aref} (untrusted data; cite with \"document\": {json.dumps(aref)}):\n<<<\n{text}\n>>>\n"
            if feedback:
                user += "\nYour previous proposal was rejected by the validator:\n- " + "\n- ".join(feedback[:30]) + "\nReturn a corrected JSON object."
            comp = broker.call(agent, f"interpreter/{n + 1}", INTERPRETER_SYSTEM, user, "interpret")
            events.emit("candidate_proposal", "interpret", f"interpreter proposal (attempt {n + 1}, model {comp.returned_model or comp.requested_model})")
            try:
                proposal = extract_json(comp.text)
            except ValueError as exc:
                feedback = [str(exc)]
                continue
            docs = {k: v.encode("utf-8") for k, v in routing.get("attachments", {}).items()}
            d, l, problems = assemble_interpretation(proposal, prompt, ref, docs)
            diags = draftmod.validate_draft(d, prompt, ref, docs)
            ldiags, _ = draftmod.validate_ledger(l, d, prompt, ref)
            feedback = problems + [x.message for x in diags + ldiags]
            last = (d, l)
            if not feedback:
                return d, l
        if last is None:
            raise InfrastructureError("the interpreter produced no parseable proposal within its attempt budget",
                                      [Diagnostic("BUDGET_EXHAUSTED", "interpreter attempts exhausted")])
        return last

    return run


# ------------------------------------------------------------------------------------------
# formalizer
# ------------------------------------------------------------------------------------------

FORMALIZER_SYSTEM = f"""You are the VeriSlop formalizer ({PROMPT_VERSION}). You propose a Lean 4 (v4.34.1) formal contract
for frozen interpreted obligations. Your output is a proposal; it is elaborated, kernel-replayed and checked.

Lean conventions:
- Start with `import Std` only (Init/Std/Lean are the only allowed import roots). No `axiom`, no `sorry` in definitions.
- Put everything in one namespace. Model domains with Nat, Bool, Unit, inductive enumerations (nullary constructors),
  and `Except E A` for results. Define a concrete, total, non-recursive-or-structurally-recursive reference function.
- Each guarantee is one `theorem` whose statement uses only: ∀/∃ over those types, →, ∧, ∨, ¬, ↔, =, <, ≤, +, -, *,
  numerals, constructors, and calls of your definitions. State theorems with `sorry` proofs (`:= by sorry`).
- Each precondition is a `def name (x y : Nat) : Prop := ...` predicate, used as an explicit hypothesis by the guarantees
  that assume it. Never strengthen hypotheses beyond the interpretation (that weakens a guarantee).
- Add one non-vacuity theorem: a conjunction of existentials showing that valid success and error cases exist under the
  preconditions, using the precondition predicates.
Return ONLY one JSON object:
{{"lean_source": "<entire Contract.lean>",
 "formalization": {{"schema_version":"0.1","artifact_kind":"formalization_candidate","profile_id":"<id>.v0_1",
   "lean_toolchain":"leanprover/lean4:v4.34.1","lean_file":"Contract.lean",
   "bindings":[{{"obligation":"D1","declarations":["Ns.Type","Ns.fn"]}},{{"obligation":"A1","predicate":"Ns.valid"}},
               {{"obligation":"O1","theorem":"Ns.thm"}},{{"obligation":"N1"}}],
   "internal_obligations":[{{"id":"W1","kind":"non_vacuity","theorem":"Ns.non_vacuity","witnesses_for":["A1"],
       "description":"valid success and error cases exist"}}]}}}}
Bind every non-blocked obligation exactly once: guarantees to theorems, assumptions to predicates, declarations to
declarations, exclusions and open questions with no Lean binding."""


def formalizer_agent(config: str | Path, pkg: Package, events: EventSink) -> Callable[[dict[str, Any]], tuple[bytes, dict]]:
    broker, conf = _broker(config, pkg)
    agent = _role(conf, "formalizer")

    def run(ctx: dict[str, Any]) -> tuple[bytes, dict]:
        records = [{k: r[k] for k in ("id", "kind", "role", "statement", "required", "dependencies", "acceptance_criteria", "blocked_by")}
                   for r in ctx["records"]]
        user = "FROZEN INTERPRETED OBLIGATIONS (data):\n" + json.dumps(records, indent=1, ensure_ascii=False)
        user += "\nASSUMPTION SUPPLIERS:\n" + json.dumps(ctx["ledger"].get("assumptions", []), ensure_ascii=False)
        if ctx["feedback"]:
            user += "\nThe previous candidate was rejected by the statement checker:\n- " + "\n- ".join(ctx["feedback"][:30])
        comp = broker.call(agent, f"formalizer/{ctx['attempt']}", FORMALIZER_SYSTEM, user, "formalize")
        try:
            obj = extract_json(comp.text)
            return obj["lean_source"].encode("utf-8"), obj["formalization"]
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            return b"-- unparseable formalizer response\n", {"error": f"unparseable formalizer response: {exc}"}

    return run


# ------------------------------------------------------------------------------------------
# prover
# ------------------------------------------------------------------------------------------

PROVER_SYSTEM = f"""You are a VeriSlop proof agent ({PROMPT_VERSION}) working in a sandbox on a FROZEN Lean 4 (v4.34.1) challenge.
Replace every `sorry` with a proof. You MUST NOT change any theorem statement, definition, instance, import, or the
generated `VeriSlop.Registry` block: any change is detected and rejected. Do not use `sorry`, `native_decide`,
`axiom`, `implemented_by` or `extern`. Existential (non-vacuity) proofs must use explicit witnesses, e.g.
`exact ⟨1, 0, by decide, rfl⟩` or `refine ⟨1, 0, ?_⟩; simp [defs]`. Useful tactics: `grind [defs]`, `simp [defs]`,
`unfold defs at h; split at h`, `omega`, `decide`.
Return ONLY the complete Lean file in one ```lean code block."""


def prover_agent(config: str | Path, pkg: Package, events: EventSink) -> Callable[[dict[str, Any]], str]:
    broker, conf = _broker(config, pkg)
    agent = _role(conf, "prover")

    def run(ctx: dict[str, Any]) -> str:
        user = "CURRENT FILE:\n```lean\n" + ctx["best"] + "\n```\n"
        if ctx["errors"]:
            user += "LEAN ERRORS:\n" + "\n".join(ctx["errors"][:30]) + "\n"
        comp = broker.call(agent, f"prover/{ctx['attempt']}", PROVER_SYSTEM, user, "prove")
        m = re.findall(r"```lean\s*\n(.*?)```", comp.text, re.S)
        return m[-1] if m else comp.text

    return run


# ------------------------------------------------------------------------------------------
# implementer
# ------------------------------------------------------------------------------------------

IMPLEMENTER_SYSTEM = f"""You are a VeriSlop implementation agent ({PROMPT_VERSION}). Implement the accepted contract in Python
using the fixed python-v0_1 profile: Nat -> int >= 0; Bool -> bool; Unit -> None; an enumeration constructor -> its
name as str; Result(E, A) -> the 2-tuple ("ok", a) or ("error", e). Functions must be total, pure and deterministic,
take exactly the declared positional arguments, and must not raise. Use only the standard library.
The formulas are authoritative; prose statements are display only.
Return ONLY one JSON object:
{{"files": {{"module_name.py": "<source>"}},
 "bindings": {{"schema_version":"0.1","artifact_kind":"implementation_bindings","target":"python",
   "serialization_profile":"python-v0_1","bindings":[{{"binding_id":"B-sym","symbol":"<profile symbol>",
   "object":{{"file":"module_name.py","qualname":"<function>"}},"obligations":["O1"]}}],"helpers":[]}}}}
Every public top-level function must be bound to a symbol or declared in helpers with a reason."""


def implementer_agent(config: str | Path, pkg: Package, events: EventSink, *, attempts: int = 3, proof_attempts: int = 3) -> Callable[[dict[str, Any]], tuple[dict[str, bytes], dict]]:
    broker, conf = _broker(config, pkg)
    agent = _role(conf, "implementer")

    def run(ctx: dict[str, Any]) -> tuple[dict[str, bytes], dict]:
        if ctx["parameters"].get("target") == "vscore":
            if ctx["parameters"].get("backend") != "verislop.backend.vscore/0.1":
                raise UsageError("no registered VSCore agent target was selected", [Diagnostic("UNSUPPORTED_CAPABILITY", "VSCore implementer needs the frozen registered backend")])
            return _vscore_implementation(broker, conf, pkg, events, ctx, attempts, proof_attempts)
        statements = {oid: {"display": st.get("display"), "representation": st["representation"]} for oid, st in ctx["statements"].items()}
        user = ("ACCEPTED SEMANTIC PROFILE (symbols to implement):\n" + json.dumps(ctx["profile"]["symbols"], indent=1)
                + "\nENUMERATIONS:\n" + json.dumps(ctx["profile"]["enums"], indent=1)
                + "\nACCEPTED FORMULAS (authoritative):\n" + json.dumps(statements, indent=1, ensure_ascii=False)
                + f"\nTIER {ctx['parameters']['tier']} -> {ctx['parameters']['endpoint']}")
        comp = broker.call(agent, "implementer/1", IMPLEMENTER_SYSTEM, user, "generate")
        try:
            obj = extract_json(comp.text)
            files = {k: v.encode("utf-8") for k, v in obj["files"].items()}
            return files, obj["bindings"]
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise UsageError(f"the implementer returned an unparseable proposal: {exc}",
                             [Diagnostic("INVALID_CANDIDATE", f"unparseable implementer proposal: {exc}")]) from None

    return run


VSCORE_IMPLEMENTER_SYSTEM = f"""You are a VeriSlop VSCore implementation agent ({PROMPT_VERSION}). Propose a total pure
vscore/0.1 program and its one-to-one accepted-symbol relation for the exact accepted contract.
The delivered endpoint is restricted_source under vscore-semantics/0.1. Nat is mathematical and unbounded.
Use only the supplied source grammar: Nat, Bool, Unit, accepted finite enumerations, nested Result, expressions,
conditionals, let and Result matches. No loops, entry calls, helpers, state, I/O or machine-width arithmetic.
Every entry binds exactly one accepted function; every called symbol in the required formulas must be bound.
Every additional entry also needs total refinement. Preserve all accepted assumptions and do not narrow input types.
Return ONLY a JSON object with exactly:
{{"program": <source program object>, "relation": <relation descriptor object>, "proof_source": <optional Lean proof text>}}
The supervisor encodes exact canonical source/relation bytes and derives the Lean goal. Omit proof_source if you have
no proof. Never supply a goal/proposition hash, accepted IR, evidence, lifecycle state or an imported contract.
The optional proof imports VeriSlopBridgeGoal and declares VeriSlopBridgeProof.edge : VeriSlopBridgeGoal.EdgeProp.
Your proposals have no acceptance authority; the registered kernel checks decide every result."""

VSCORE_PROVER_SYSTEM = f"""You are a VeriSlop VSCore proof agent ({PROMPT_VERSION}). Propose one Lean 4 proof module for the
verifier-generated exact goal, fixed source and accepted reference below. The target is restricted_source.
Import VeriSlopBridgeGoal. Prove theorem VeriSlopBridgeProof.edge : VeriSlopBridgeGoal.EdgeProp, usually by applying
VeriSlopBridgeGoal.edge_of_refines to a total proof of each Refines_<symbol>. The goal includes exact parse/typing,
input coverage, total refinement for every bound entry and transfer of every required accepted guarantee.
Do not change source, bindings, goal, accepted reference, domain types, assumptions or imported definitions.
No sorry, axiom, native_decide, implemented_by, extern or additional imported modules outside pinned policy.
Return ONLY the complete proof module in one ```lean code block. A failed attempt receives bounded checker diagnostics;
no response assigns an evidence outcome or lifecycle state."""


def _proof_text(text: str) -> str:
    matches = re.findall(r"```lean\s*\n(.*?)```", text, re.S)
    return matches[-1] if matches else text


def _vscore_context(pkg: Package, ctx: dict[str, Any]) -> dict[str, Any]:
    """Supply exact accepted packages/reference and supervisor-owned language limits."""
    from . import schemas
    from .backends import admission, registry
    from .targets import vscore_source, vscore_target

    formulas = {}
    for oid, rec in sorted(ctx["ir"]["obligations"].items()):
        package = admission.formula_package(pkg, rec)
        if package is None:
            raise UsageError(f"accepted formula/metadata package {oid} is missing or changed",
                             [Diagnostic("INPUT_MUTATION", f"accepted expression package {oid} does not bind its bytes")])
        formulas[oid] = {"revision": rec["revision"], "statement_hash": rec["formal"]["statement_hash"],
                         "formula_ref": rec["formal"]["formula_ref"], "package": package}
    certificate = canonical.load_file(pkg.root / ctx["ir"]["acceptance_certificate_ref"])
    reference = certificate["artifacts"]["source"]
    reference_bytes = (pkg.root / reference["path"]).read_bytes()
    if canonical.digest(reference_bytes) != reference["sha256"]:
        raise UsageError("accepted reference bytes changed", [Diagnostic("INPUT_MUTATION", "accepted reference source no longer matches its certificate")])
    return {"accepted_ir": ctx["ir"], "accepted_packages": formulas, "accepted_profile": ctx["profile"],
            "parameters": ctx["parameters"], "required_obligations": ctx["required_obligations"],
            "source_grammar": canonical.load_file(schemas.schema_dir() / "vscore-source.schema.json"),
            "relation_format": canonical.load_file(schemas.schema_dir() / "vscore-relation.schema.json"),
            "feature_limits": {"source_bytes": vscore_source.MAX_SOURCE_BYTES, "proof_bytes": vscore_target.MAX_PROOF_BYTES,
                               "bindings": vscore_target.MAX_BINDINGS, "excluded_surfaces": registry.VSCORE_EXCLUDED},
            "accepted_reference": {"path": reference["path"], "sha256": reference["sha256"],
                                   "lean_source": reference_bytes.decode("utf-8")},
            "lean_toolchain": certificate["toolchain"]["pin"]}


def _vscore_implementation(broker, conf: dict, pkg: Package, events: EventSink, ctx: dict,
                           attempts: int, proof_attempts: int) -> tuple[dict[str, bytes], dict]:
    """Bounded source/proof search before selection; every source and proof attempt is retained."""
    from . import fsutil, schemas
    from .bridges import vscore_checker
    from .targets import vscore_target

    if not 1 <= attempts <= 10 or not 0 <= proof_attempts <= 10:
        raise UsageError("VSCore search budgets require 1..10 source attempts and 0..10 proof attempts")
    fixed = _vscore_context(pkg, ctx)
    implementer = _role(conf, "implementer")
    prover = conf["roles"].get("prover")
    feedback: list[str] = []
    fallback: dict[str, bytes] | None = None
    root = pkg.root / "agents" / "vscore-attempts"
    root.mkdir(parents=True, exist_ok=True)
    first = 1
    while (root / f"source-{first}").exists():
        first += 1

    def diagnostics(exc: Exception) -> list[str]:
        ds = getattr(exc, "diagnostics", None)
        return [d.message[:2000] for d in ds[:20]] if ds else [str(exc)[:2000]]

    def retain(stage: Path, data: dict[str, bytes]) -> None:
        for name, value in data.items():
            fsutil.write_once(stage / name, value)

    def checked(stage: Path, source: bytes, relation: bytes, proof: bytes | None, label: str):
        try:
            spec, build, info = vscore_checker.preview(pkg, source, relation, proof=proof)
            fsutil.write_json(stage / f"checks/{label}.json",
                              {"proof_checked": proof is not None, "passed": True,
                               "proposition_hash": info["proposition_hash"], "source_hash": canonical.digest(source)}, once=True)
            return spec, build, info
        except vscore_checker.EdgeFailure as exc:
            fsutil.write_json(stage / f"checks/{label}.json",
                              {"proof_checked": proof is not None, "passed": False,
                               "diagnostics": [d.to_json() for d in exc.diagnostics[:20]],
                               "source_hash": canonical.digest(source)}, once=True)
            if any(d.severity == "infrastructure" for d in exc.diagnostics):
                raise InfrastructureError("VSCore preview infrastructure failed", exc.diagnostics) from exc
            raise

    for offset in range(attempts):
        number = first + offset
        stage = root / f"source-{number}"
        user = "FIXED ACCEPTED CONTRACT AND TARGET (data):\n" + json.dumps(fixed, ensure_ascii=False)
        if feedback:
            user += "\nBOUNDED CHECKER DIAGNOSTICS FROM THE PREVIOUS ATTEMPT:\n- " + "\n- ".join(feedback[:20])
        comp = broker.call(implementer, f"implementer/vscore/{number}", VSCORE_IMPLEMENTER_SYSTEM, user, "generate")
        events.emit("candidate_proposal", "generate", f"VSCore source proposal (attempt {number})")
        fsutil.write_once(stage / "response.txt", comp.text.encode("utf-8"))
        try:
            proposed = extract_json(comp.text)
            if not isinstance(proposed, dict) or not {"program", "relation"} <= set(proposed) or set(proposed) - {"program", "relation", "proof_source"}:
                raise ValueError("VSCore proposal must contain only program, relation and optional proof_source")
            if not isinstance(proposed["program"], dict) or not isinstance(proposed["relation"], dict):
                raise ValueError("program and relation must be JSON objects")
            issues = schemas.validate("vscore-source", proposed["program"])
            if issues:
                raise ValueError(f"vscore-source: {issues[0]}")
            source, relation = canonical.dumps(proposed["program"]), canonical.dumps(proposed["relation"])
            vscore_target.load_relation(relation)
            if "proof_source" in proposed and not isinstance(proposed["proof_source"], str):
                raise ValueError("proof_source must be Lean text")
            retain(stage, {"program.vscore.json": source, "relation.json": relation})
            spec, _, info = checked(stage, source, relation, None, "source")
            retain(stage, {"VeriSlopBridgeGoal.lean": spec.text.encode(), "model.json": info["model"], "profile.json": info["profile"]})
        except (ValueError, TypeError, KeyError, vscore_target.BridgeInvalid, vscore_checker.EdgeFailure) as exc:
            feedback = diagnostics(exc)
            fsutil.write_json(stage / "source-diagnostics.json", {"diagnostics": feedback}, once=True)
            continue
        proof = proposed.get("proof_source", "import VeriSlopBridgeGoal\nnamespace VeriSlopBridgeProof\ntheorem edge : VeriSlopBridgeGoal.EdgeProp := by sorry\nend VeriSlopBridgeProof\n").encode("utf-8")
        proof_feedback: list[str] = []
        last_bounded_proof = proof if len(proof) <= vscore_target.MAX_PROOF_BYTES else b"import VeriSlopBridgeGoal\nnamespace VeriSlopBridgeProof\ntheorem edge : VeriSlopBridgeGoal.EdgeProp := by sorry\nend VeriSlopBridgeProof\n"
        if "proof_source" in proposed:
            retain(stage, {"proofs/initial.lean": proof})
            try:
                if len(proof) > vscore_target.MAX_PROOF_BYTES:
                    raise ValueError("initial proof exceeds the registered proof size budget")
                checked(stage, source, relation, proof, "initial-proof")
                return {"program.vscore.json": source, "relation.json": relation, "Proof.lean": proof}, {}
            except (ValueError, vscore_checker.EdgeFailure) as exc:
                proof_feedback = diagnostics(exc)
        prover_context = {"parameters": fixed["parameters"], "source_hash": canonical.digest(source),
                          "source": proposed["program"], "relation": proposed["relation"],
                          "generated_goal": spec.text, "accepted_reference": fixed["accepted_reference"],
                          "accepted_packages": fixed["accepted_packages"], "accepted_profile": fixed["accepted_profile"],
                          "lean_toolchain": fixed["lean_toolchain"],
                          "verifier_library": {name: data.decode("utf-8") for name, data in vscore_target.library_sources().items()}}
        for proof_number in range(1, proof_attempts + 1 if prover else 1):
            user = "FIXED VSCORE PROOF CONTEXT (data):\n" + json.dumps(prover_context, ensure_ascii=False)
            user += "\nCURRENT CANDIDATE PROOF:\n```lean\n" + proof.decode("utf-8") + "\n```\n"
            if proof_feedback:
                user += "\nBOUNDED CHECKER DIAGNOSTICS:\n- " + "\n- ".join(proof_feedback[:20])
            comp = broker.call(prover, f"prover/vscore/{number}/{proof_number}", VSCORE_PROVER_SYSTEM, user, "generate")
            proof = _proof_text(comp.text).encode("utf-8")
            if len(proof) <= vscore_target.MAX_PROOF_BYTES:
                last_bounded_proof = proof
            retain(stage, {f"proofs/{proof_number}.lean": proof})
            events.emit("candidate_proposal", "generate", f"VSCore proof proposal (source {number}, proof {proof_number})")
            try:
                if len(proof) > vscore_target.MAX_PROOF_BYTES:
                    raise ValueError("proof exceeds the registered proof size budget")
                checked(stage, source, relation, proof, f"proof-{proof_number}")
                return {"program.vscore.json": source, "relation.json": relation, "Proof.lean": proof}, {}
            except (ValueError, vscore_checker.EdgeFailure) as exc:
                proof_feedback = diagnostics(exc)
        # A failed proof search leaves a concrete source candidate for IMPLEMENTED/LINKED.
        fallback = {"program.vscore.json": source, "relation.json": relation, "Proof.lean": last_bounded_proof}
        feedback = proof_feedback or ["no configured prover established the exact refinement theorem"]
        fsutil.write_json(stage / "proof-diagnostics.json", {"diagnostics": feedback, "proof_search_exhausted": True}, once=True)
    if fallback is not None:
        events.emit("progress", "generate", "bounded VSCore proof search exhausted; source candidate remains available for materialization")
        return fallback, {}
    raise UsageError("VSCore implementer produced no well-formed source within its bounded search budget",
                     [Diagnostic("BUDGET_EXHAUSTED", "VSCore source attempts exhausted", details={"diagnostics": feedback})])
