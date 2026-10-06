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


def implementer_agent(config: str | Path, pkg: Package, events: EventSink) -> Callable[[dict[str, Any]], tuple[dict[str, bytes], dict]]:
    broker, conf = _broker(config, pkg)
    agent = _role(conf, "implementer")

    def run(ctx: dict[str, Any]) -> tuple[dict[str, bytes], dict]:
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
