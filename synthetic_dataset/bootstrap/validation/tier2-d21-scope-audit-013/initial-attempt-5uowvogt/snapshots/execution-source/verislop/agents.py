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

from . import canonical, draft as draftmod, schemas
from .errors import Diagnostic, InfrastructureError, UsageError
from .events import EventSink
from .lifecycle import DRAFT_CATEGORIES, MILESTONES, applicability, milestone_entry
from .package import Package

PROMPT_VERSION = "verislop.prompts/0.8"
CAPABILITY_VERSION = "verislop.formalizer-capability-gap/0.1"
CAPABILITY_MARKER = b"-- formalizer capability gap (untrusted report)\n"
KIND_TO_CATEGORY = {v: k for k, v in DRAFT_CATEGORIES.items()}


def _source_policy_context(pkg: Package) -> dict | None:
    from . import source_policy

    return source_policy.context(pkg)


def _source_policy_prompt(policy: dict) -> str:
    return ("\nREQUIRED SOURCE FACETS (frozen specification constraint; not accepted IR or proof evidence):\n"
            + json.dumps(policy, ensure_ascii=False, indent=1)
            + "\nRetain every policy obligation ID as a required guarantee with its complete requested behavior. "
              "Each row fixes the canonical file, entry, arity and closed source properties for that ID. "
              "value_required=true requires the complete functional value proposition as well as the source facets; "
              "a mathematical existence result, True, reflexive equality or an unrelated entry cannot replace them. "
              "Do not convert these requirements into assumptions, declarations, exclusions or optional guarantees. "
              "The policy supplies no algorithm, candidate source, expected output, accepted statement or lifecycle state.")


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
    """Parse the first outer response object; never promote a malformed object's child."""
    fenced = re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.S)
    for candidate in fenced + [text]:
        candidate = candidate.strip()
        start = candidate.find("{")
        if start == -1:
            continue
        depth, in_string, escaped = 0, False, False
        for index in range(start, len(candidate)):
            char = candidate[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return canonical.loads(candidate[start:index + 1])
                    except canonical.CanonicalJSONError as exc:
                        raise ValueError(f"invalid outer JSON object: {exc}") from None
        raise ValueError("unterminated outer JSON object in the response")
    raise ValueError("no strict JSON object found in the response")


def _role(conf: dict[str, Any], role: str) -> str:
    return conf["roles"][role]


def recorded_call(broker, pkg: Package, agent: str, instance: str, system: str, user: str, purpose: str):
    """Retain exact role context before calling the provider, including failed calls."""
    from . import agent_memory
    if hasattr(broker, "validate_prompt"):
        broker.validate_prompt(agent, system, user)
    snapshot = agent_memory.checkpoint(pkg, f"agent/{purpose}/input", {
        "system.txt": system.encode("utf-8"), "user.txt": user.encode("utf-8")},
        metadata={"agent": agent, "instance": instance, "prompt_version": PROMPT_VERSION})
    try:
        completion = broker.call(agent, instance, system, user, purpose)
    except Exception as exc:
        agent_memory.capture_context(pkg, f"agent/{purpose}/failure", {
            "input_snapshot": snapshot["snapshot_ref"], "error_type": type(exc).__name__, "error": str(exc)})
        raise
    agent_memory.checkpoint(pkg, f"agent/{purpose}/response", {"response.txt": completion.text.encode("utf-8")},
                            metadata={"input_snapshot": snapshot["snapshot_ref"], "agent": agent, "instance": instance})
    return completion


# ------------------------------------------------------------------------------------------
# interpreter
# ------------------------------------------------------------------------------------------

INTERPRETER_KIND_ROLES = [
    {"kind": kind, "role": role} for kind, role in (
        ("entity", "declaration"), ("precondition", "assumption"), ("postcondition", "guarantee"),
        ("invariant", "guarantee"), ("safety_property", "guarantee"), ("liveness_property", "guarantee"),
        ("resource_constraint", "guarantee"), ("error_semantics", "guarantee"),
        ("explicit_non_goal", "exclusion"), ("ambiguity", "open_question"))
]

# Complete proposal examples, not inferred requirements for an actual user request.
_ASSUMPTION_REQUEST = "The caller supplies a positive natural input. Return that input unchanged."
_ASSUMPTION_EXAMPLE = {
    "obligations": [
        {"id": "D1", "kind": "entity", "role": "declaration", "statement": "The input and output are natural numbers.",
         "required": True, "scope": ["input and output"], "dependencies": [],
         "acceptance_criteria": ["input and output have the natural-number domain"],
         "sources": [{"clause_id": "C1", "origin": "explicit", "interpretation": "input domain"}]},
        {"id": "A1", "kind": "precondition", "role": "assumption", "statement": "The caller supplies an input greater than zero.",
         "required": True, "scope": ["caller input"], "dependencies": [{"id": "D1", "relation": "uses_definition"}],
         "acceptance_criteria": ["input > 0"],
         "sources": [{"clause_id": "C1", "origin": "explicit", "interpretation": "explicit caller precondition"}]},
        {"id": "O1", "kind": "postcondition", "role": "guarantee", "statement": "Under the stated caller precondition, the output equals the input.",
         "required": True, "scope": ["inputs satisfying A1"], "dependencies": [{"id": "A1", "relation": "assumes"}, {"id": "D1", "relation": "uses_definition"}],
         "acceptance_criteria": ["input > 0 implies output = input"],
         "sources": [{"clause_id": "C2", "origin": "explicit", "interpretation": "identity behavior"}]}],
    "category_review": {cat: ({"entities": "natural input and output", "preconditions": "explicit positive-input caller assumption",
                               "postconditions": "identity under that assumption"}.get(cat, "none stated")) for cat in DRAFT_CATEGORIES},
    "clauses": [{"clause_id": "C1", "disposition": "obligations", "refs": ["D1", "A1"], "note": ""},
                {"clause_id": "C2", "disposition": "obligations", "refs": ["O1"], "note": ""}],
    "assumptions": [{"id": "A1", "supplied_by": "caller", "discharged_at": "function invocation, by the caller satisfying input > 0"}],
    "ambiguities": [], "selected_defaults": []}


def _interpreter_wire_schema() -> dict[str, Any]:
    """Describe proposal fields using the same schemas that validate assembled artifacts."""
    reg = schemas.registry()
    obligation, _ = reg.resolve(schemas.IDS["obligation"], schemas.IDS["obligation"])
    interpretation, _ = reg.resolve(schemas.IDS["interpretation"], schemas.IDS["interpretation"])
    ledger_fields = interpretation["properties"]
    ambiguity = ledger_fields["ambiguities"]["items"]
    # Resolution/provenance are supervisor-derived; the generator proposes only a default ID.
    ambiguity_proposal = {"type": "object", "additionalProperties": False,
                          "properties": {k: v for k, v in ambiguity["properties"].items() if k != "resolution"},
                          "required": [k for k in ambiguity["required"] if k != "resolution"] + ["proposed_default"]}
    ambiguity_proposal["properties"]["proposed_default"] = {"type": ["string", "null"]}
    default = ledger_fields["selected_defaults"]["items"]
    return {"kind_and_role_are_separate_fields": INTERPRETER_KIND_ROLES,
            "obligation_fields": ["id", "kind", "role", "statement", "required", "scope", "dependencies", "acceptance_criteria", "sources"],
            "request_source_item": {"clause_id": "<current request manifest ID>", "origin": "explicit or inferred",
                                    "interpretation": "<authored meaning of this citation>"},
            "request_clause_item": {"clause_id": "<current request manifest ID>", "disposition": "obligations/exclusion/ambiguity/context",
                                    "refs": ["<authored existing obligation ID>"], "note": "<required for context>"},
            "citation_rules": "Prefer clause_id only. quote is optional with an ID, but if present must equal the exact manifest quote. "
                              "IDs identify only the current request; attachments require document and a verbatim quote without clause_id. "
                              "Legacy quote-only citations remain exact substrings; never unescape model text.",
            "dependencies_item": obligation["$defs"]["dependency"],
            "assumptions_item": ledger_fields["assumptions"]["items"],
            "ambiguities_item": ambiguity_proposal,
            "selected_defaults_item": {"type": "object", "additionalProperties": False,
                                       "properties": {k: v for k, v in default["properties"].items() if k != "provenance"},
                                       "required": [k for k in default["required"] if k != "provenance"]}}


INTERPRETER_SYSTEM = f"""You are the VeriSlop interpreter ({PROMPT_VERSION}). You turn a software request into an explicit,
structured obligation proposal. Your output is a proposal only; verifiers decide everything.

Rules:
- kind and role are TWO SEPARATE JSON fields. Use these literal pairs:
  {json.dumps(INTERPRETER_KIND_ROLES, separators=(',', ':'))}
  For example, write "kind":"entity","role":"declaration". No kind or role contains a slash.
- IDs are short and stable (e.g. D1, A1, O1, I1, E1, N1, Q1); revision is 1.
- Every obligation cites request source text using "clause_id":"<current request manifest ID>". Prefer ID-only
  citations; the supervisor reconstructs the exact UTF-8 source span. An optional quote must match the manifest
  EXACTLY; a wrong or double-escaped quote is rejected, never unescaped. Do not invent byte spans or IDs.
  Attachments instead require "document":"<attachment ref>" and a verbatim "quote", without a request clause_id.
  Legacy quote-only citations are allowed. Inferred requirements use origin "inferred" and justify the cited text.
- Every clause of the request needs a disposition: obligations (refs = obligation IDs), exclusion (refs = non-goal IDs),
  ambiguity (refs = ambiguity IDs) or context (with a note).
- The user message supplies a deterministic REQUEST CLAUSE MANIFEST. Include every manifest clause exactly once in
  clauses, copying its clause_id and omitting quote. Clauses are source coverage, not automatically separate obligations.
  Clause IDs refer only to THIS request; a document field with an ID, if included, must equal the current request ref.
  Do not mark behavior, input/output requirements, edge cases or examples as mere context to avoid specifying them.
- Distinguish supervisor instructions about this verification run from requested implementation behavior by
  their subject and provenance. Instructions about this run's proof, staged checking, review, endpoint selection,
  contract registry maintenance or trust configuration are workflow context: cover their request clauses in the
  ledger as context with explanatory notes. They do not add program guarantees or establish their satisfaction.
  Supervisor-supplied program source policies still prescribe requirements of the delivered implementation.
  A user-requested verifier, artifact checker, audit log or metadata-processing program still has software
  requirements, even when it uses the same terminology. Preserve its source properties, functional safety,
  invariants, branches, examples and complete input/output domains as obligations with source citations.
  Never use this distinction to delete, downgrade or hide an unsupported user software requirement.
- dependencies is an array of objects {{"id":"<existing obligation ID>","relation":"<allowed relation>"}}, never strings.
  Every dependency target must appear in your obligations array; never copy a sample ID that you did not declare.
  Use [] when independent. assumes may name only an assumption record; uses_definition names a declaration;
  uses_proof names a guarantee; blocked_by names an ambiguity. No self-dependencies.
- Every assumption has BOTH an obligation with "kind":"precondition","role":"assumption" and an assumptions entry naming who supplies it and
  where it is discharged. Use assumptions: [] when none are stated. Do not invent preconditions for convenience,
  restrict the requested domain to easy cases, or convert required validation/error handling into a caller assumption.
- Every ambiguity has BOTH an obligation with "kind":"ambiguity","role":"open_question" and an ambiguities entry with the same ID.
  Use ambiguities: [] when the request already specifies the behavior. Input flexibility is not itself an ambiguity.
- Each assumptions entry has exactly id, supplied_by, discharged_at (all nonempty strings). Each ambiguities entry
  has id, alternatives (at least two objects with id and description), affected_obligations (existing IDs), impact
  (an array of correctness, data_loss, security, failure_behavior, numeric_semantics, formal_boundary or routine),
  and proposed_default (an offered alternative ID, or null). The supervisor creates resolution and provenance.
  Example entry: {{"id":"Q1","alternatives":[{{"id":"floor","description":"round downward"}},
  {{"id":"nearest","description":"round to the nearest integer"}}],"affected_obligations":["O1"],
  "impact":["numeric_semantics"],"proposed_default":null}}. Declare Q1 separately with
  "kind":"ambiguity","role":"open_question", source citations and all obligation fields; do not copy example IDs.
- Never resolve an ambiguity that affects correctness, data loss, security, failure behaviour, numeric semantics or the
  formal boundary: list its alternatives and leave proposed_default null. Only routine ambiguities may propose a default.
- Do not claim any lifecycle state. Do not write code.
Return ONLY one JSON object. This complete example is for the separate request "Return each natural input unchanged."
(use the ACTUAL request, manifest clause IDs and your own obligation IDs instead):
{{"obligations":[{{"id":"O1","kind":"postcondition","role":"guarantee","statement":"The returned natural equals its input.","required":true,
   "scope":["all natural inputs"],"dependencies":[],"acceptance_criteria":["output = input for every natural input"],
   "sources":[{{"clause_id":"C1","origin":"explicit","interpretation":"identity behavior"}}]}}],
 "category_review":{{"entities":"one natural input and output","preconditions":"none","postconditions":"identity",
   "invariants":"none stated","safety_properties":"none stated","liveness_properties":"none stated",
   "resource_constraints":"none stated","error_semantics":"none stated","explicit_non_goals":"none stated","ambiguities":"none"}},
 "clauses":[{{"clause_id":"C1","disposition":"obligations","refs":["O1"],"note":""}}],
 "assumptions":[], "ambiguities":[],
 "selected_defaults":[]}}
This second COMPLETE example is only for the separate request {json.dumps(_ASSUMPTION_REQUEST)}. It illustrates
the declaration and explicit assumption records AND their matching supplier entry. It does not add an assumption
to requests that lack one:
{json.dumps(_ASSUMPTION_EXAMPLE, ensure_ascii=False, separators=(',', ':'))}
Dependency relations: assumes, uses_definition, uses_proof, requires_witness, refines, requires_bridge, blocked_by."""


def _request_clauses(prompt: bytes) -> list[dict[str, Any]]:
    """Expose the same mechanical segments the coverage verifier actually checks."""
    from .segment import segments

    return [{"clause_id": f"C{i}", "quote": prompt[a:b].decode("utf-8"),
             "start_byte": a, "end_byte": b}
            for i, (a, b) in enumerate(segments(prompt), 1)]


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


def _request_citation(citation: dict, manifest: dict, ref: str) -> tuple[tuple[int, int] | None, str | None]:
    """Resolve an ID only in the current supervisor-owned request manifest."""
    cid = citation["clause_id"]
    expected = manifest.get(cid) if isinstance(cid, str) else None
    if expected is None:
        return None, f"clause {cid!r}: ID does not match the request clause manifest"
    if "document" in citation and citation["document"] != ref:
        return None, f"clause {cid!r}: request clause IDs cannot cite another document"
    if "quote" in citation and citation["quote"] != expected["quote"]:
        return None, f"clause {cid!r}: ID/quote does not match the request clause manifest"
    return (expected["start_byte"], expected["end_byte"]), None


def assemble_interpretation(proposal: dict[str, Any], prompt: bytes, ref: str,
                            attachments: dict[str, bytes] | None = None) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    problems: list[str] = []
    doc_hash = canonical.digest(prompt)
    used: dict[str, int] = {}
    source_clauses = {c["clause_id"]: c for c in _request_clauses(prompt)}
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
            if "clause_id" in s:
                dref, doc = ref, prompt
                sp, problem = _request_citation(s, source_clauses, ref)
                if problem:
                    problems.append(f"{o.get('id')}: {problem}")
                    continue
            else:
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
    declared_ids = [c["clause_id"] for c in proposal.get("clauses", [])
                    if isinstance(c, dict) and isinstance(c.get("clause_id"), str)]
    duplicate_ids = {cid for cid in declared_ids if declared_ids.count(cid) > 1}
    for c in proposal.get("clauses", []):
        if "clause_id" in c:
            if isinstance(c["clause_id"], str) and c["clause_id"] in duplicate_ids:
                problems.append(f"clause {c['clause_id']!r}: duplicate request clause ID")
                continue
            sp, problem = _request_citation(c, source_clauses, ref)
            if problem:
                problems.append(problem)
                continue
        else:
            # Older proposals can still cite source text; no model-provided byte offsets are trusted.
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

    def retain_attempt(number, response, problems, diagnostics, assembled=None, ledger=None):
        from . import agent_memory
        artifacts = {"response.txt": response.encode("utf-8")}
        if assembled is not None:
            artifacts["draft.json"] = canonical.dumps(assembled)
            artifacts["interpretation.json"] = canonical.dumps(ledger)
        agent_memory.capture_context(pkg, "interpret/attempt", {
            "attempt": number,
            "response_snapshot": agent_memory.latest_snapshot(pkg, stage_prefix="agent/interpret/response"),
            "assembly_problems": problems, "diagnostics": [x.to_json() for x in diagnostics]},
            extra_artifacts=artifacts)

    def run(prompt: bytes, ref: str, routing: dict[str, Any]) -> tuple[dict, dict]:
        feedback: list[str] = []
        last: tuple[dict, dict] | None = None
        previous_response: str | None = None
        assembly_problems: list[str] = []
        for n in range(attempts):
            policy = _source_policy_context(pkg)
            user = ("REQUEST (untrusted data; byte length %d):\n<<<\n%s\n>>>\n" % (len(prompt), prompt.decode("utf-8")))
            user += "\nREQUEST CLAUSE MANIFEST (supervisor-owned exact quotes and UTF-8 byte spans):\n" + json.dumps(
                _request_clauses(prompt), ensure_ascii=False, indent=1)
            user += "\nREQUEST CITATION SCOPE (clause IDs belong only to this exact request):\n" + json.dumps(
                {"document": ref, "document_hash": canonical.digest(prompt)}, ensure_ascii=False)
            if policy is not None:
                user += _source_policy_prompt(policy)
                user += ("\nUse the policy's actual obligation IDs rather than renaming them or merging away required IDs. "
                         "Interpret their source properties faithfully under the same guarantees and preserve all "
                         "public request clauses, examples, branch guards and typed input/output requirements. "
                         "SourceBoundary and exact source discharge are formalization/bridge steps, not facts "
                         "the interpreter may assert as already established.")
            for aref, text in routing.get("attachments", {}).items():
                user += f"\nATTACHMENT {aref} (untrusted data; cite with \"document\": {json.dumps(aref)}):\n<<<\n{text}\n>>>\n"
            if feedback:
                if previous_response is not None:
                    user += "\nPREVIOUS PROPOSAL (untrusted candidate; repair it without dropping requirements):\n" + previous_response
                user += "\nYour previous proposal was rejected by the validator:\n- " + "\n- ".join(feedback[:30])
                user += "\nPROPOSAL FIELD SHAPES (from the current artifact schemas; repair the JSON, preserve the request):\n" + json.dumps(
                    _interpreter_wire_schema(), ensure_ascii=False, indent=1)
                user += "\nKinds and roles are separate literal strings, never combined values. Include all assumption supplier fields and ambiguity alternative objects. Return a corrected JSON object."
            comp = recorded_call(broker, pkg, agent, f"interpreter/{n + 1}", INTERPRETER_SYSTEM, user, "interpret")
            previous_response = comp.text
            events.emit("candidate_proposal", "interpret", f"interpreter proposal (attempt {n + 1}, model {comp.returned_model or comp.requested_model})")
            try:
                proposal = extract_json(comp.text)
            except ValueError as exc:
                feedback = [str(exc)]
                retain_attempt(n + 1, comp.text, feedback, [Diagnostic("INVALID_CANDIDATE", feedback[0])])
                continue
            docs = {k: v.encode("utf-8") for k, v in routing.get("attachments", {}).items()}
            try:
                d, l, problems = assemble_interpretation(proposal, prompt, ref, docs)
            except (AttributeError, KeyError, TypeError) as exc:
                feedback = [f"malformed interpretation proposal: {exc}; use the exact JSON object/array shapes in the instructions"]
                retain_attempt(n + 1, comp.text, feedback, [Diagnostic("INVALID_CANDIDATE", feedback[0])])
                continue
            diags = draftmod.validate_draft(d, prompt, ref, docs)
            ldiags, _ = draftmod.validate_ledger(l, d, prompt, ref)
            feedback = problems + [x.message for x in diags + ldiags]
            assembly_problems = problems
            retain_attempt(n + 1, comp.text, problems, diags + ldiags, d, l)
            last = (d, l)
            if not feedback:
                return d, l
        if last is None:
            raise InfrastructureError("the interpreter produced no parseable proposal within its attempt budget",
                                      [Diagnostic("BUDGET_EXHAUSTED", "interpreter attempts exhausted")])
        if assembly_problems:
            from .errors import BlockedError
            raise BlockedError("the interpreter exhausted its bounded citation correction attempts",
                               [Diagnostic("INVALID_CANDIDATE", problem) for problem in assembly_problems])
        return last

    return run


# ------------------------------------------------------------------------------------------
# formalizer
# ------------------------------------------------------------------------------------------

FORMALIZER_SYSTEM = f"""You are the VeriSlop formalizer ({PROMPT_VERSION}). You propose a Lean 4 (v4.34.1) formal contract
for frozen interpreted obligations. Your output is a proposal; it is elaborated, kernel-replayed and checked.

Lean conventions:
- Start with `import Std` only (Init/Std/Lean are the only allowed import roots). No `axiom`, no `sorry` in definitions.
- Put everything in one namespace. Model domains with Nat, Int, Bool, Unit, String, `List A`, fixed-field
  nonrecursive monomorphic structures, nullary inductive enumerations, and `Except E A` for results.
  Define a concrete total reference function. JSON object APIs use a Lean structure with exactly the specified
  keys and a `solve (data : Input) : Output` entry point; lists and strings retain their actual values.
  Preserve exact field names. Write every structure field declaration and record-construction field name with a quoted identifier using guillemets,
  e.g. `«field_name» : String`; the quotation preserves the key and handles Lean keywords such as `prefix`.
- Those are the executable contract profile's sorts, not permission to erase the requested data model. Nat is
  unbounded nonnegative arithmetic with truncated subtraction; Int is signed exact arithmetic. Neither stands for
  arbitrary JSON or an unrelated data type. Do not replace a graph/collection operation with a Nat identity function, reduce the input
  domain to public examples, or silently remove requirements to fit the profile. Dynamic JSON, recursive/dependent
  records, arbitrary products, custom sorting and unsupported operations still require further admission. Faithful terms outside the profile
  remain opaque Lean terms and cannot obtain TESTED through the current generated-test bridge.
- Each guarantee is one `theorem` whose statement uses only: ∀/∃ over those types, →, ∧, ∨, ¬, ↔, =, <, ≤, +, -, *,
  numerals, constructors, record fields, String append/length/isEmpty, Nat-to-Int conversion, Int.toNat,
  Int.fdiv (floor division; zero divisor returns zero),
  List literals/append/reverse/length/map/filter/sum/foldl/range/get?Internal,
  scalar List.mergeSort with decide(≤), scalar List.eraseDups with builtin equality,
  Option constructors/getD/isSome and Bool cond,
  and calls of your definitions. Use builtin List functions, ordinary explicit lambda parameters for map/filter,
  and `decide` of quantifier-free comparisons/equality/connectives for Bool predicates. No custom typeclass
  instances, arbitrary polymorphism or imported third-party semantics. State theorems with `sorry` proofs (`:= by sorry`).
  State complete observable behavior as equalities against these fixed primitives, including each output field,
  order and multiplicity. A reflexive implementation equality or agreement between two unconstrained functions
  does not specify behavior. Keep an input record as one argument; do not secretly turn solve(data) into several
  target arguments or change Python lists/dictionaries to tuples. Bind input/output record types in declarations.
  Inlining the reference pipeline or using local let bindings avoids unnecessary separately implemented helpers.
- Preserve every specified branch condition inside the theorem. A requirement "if C then P" is C → P (with any
  explicitly permitted assumptions before C), not an unconditional P. Required branch guards are not new caller
  preconditions: keep them local to their matching guarantee instead of inventing a global assumption. Do not assert
  both success and error for all inputs when the request specifies them for different branches.
- For a success/error result use Lean's builtin `Except E A` exactly. Error enumerations may have nullary constructors;
  do not substitute a custom payload-bearing inductive Result, Option, product, structure or dependent type and claim
  it uses the executable Result bridge. Successful values and errors must retain their actual accepted sorts.
- An interpreted assumption is a Prop-valued `def` over its actual supported domain, used as an explicit hypothesis
  only by guarantees with an `assumes` dependency on that ID. Do not invent assumptions or strengthen hypotheses beyond
  the frozen interpretation. No-assumption requests need no assumption predicate and no internal non-vacuity obligation.
- For assumptions used by required guarantees, add derived non-vacuity theorems as existentials (or conjunctions of
  existentials) explicitly mentioning their predicates, with witnesses_for naming ONLY actual assumption IDs.
  Witness satisfiability of those predicates. Require both success and error witnesses only when the interpreted
  specification actually requires reachable success/error branches under those same assumptions; never manufacture
  an error branch for an infallible function. The prover must subsequently produce concrete witnesses.
- Lean 4 match expressions use `match value with | ctor => ...`; do not add Lean 3's `end` to a match expression.
- Parenthesize the whole function application before selecting a result field: `(f record).field`.
  Parenthesize the whole mapped-list expression before a following field operation: `(xs.map (fun x => x)).sum`.
  A List.length is Nat; an Int count uses its exact standard Nat-to-Int cast. For a foldl use the ordered builtin
  with two explicit lambda binders and a typed initial accumulator; its return sort equals the accumulator sort.
- The BINDING MANIFEST in the user message lists the actual immutable IDs and required binding shapes. Use exactly
  those active IDs, once each. Never copy unrelated example IDs. Fully qualify each declaration in your own namespace.
  Exclusions/open questions have only an obligation key, no theorem/predicate/declarations key. Blocked IDs have no binding.
- When given a previous candidate and checker diagnostics, repair that candidate, preserving its faithful domain,
  reference behavior and all frozen obligations. A syntax/proof failure is not permission to weaken the statement,
  change an assumption, fabricate a new guarantee or replace the reference with a placeholder.
- The supervisor adds its own obligation registry. Do not generate or copy a `VeriSlop.Registry` namespace or a
  `-- BEGIN VERISLOP REGISTRY` / `-- END VERISLOP REGISTRY` block; omit that generated block if present in prior context.
Return ONLY one JSON object:
{{"lean_source": "<entire Contract.lean>",
 "formalization": {{"schema_version":"0.1","artifact_kind":"formalization_candidate","profile_id":"<id>.v0_1",
   "lean_toolchain":"leanprover/lean4:v4.34.1","lean_file":"Contract.lean",
   "bindings": [], "internal_obligations": []}}}}
Populate bindings from the actual BINDING MANIFEST; the empty arrays above illustrate shape, not permission to omit IDs.
If needed, each internal obligation has exactly: id (fresh ID), kind "non_vacuity", theorem (qualified Lean name),
witnesses_for (nonempty array of existing assumption IDs), description (nonempty explanation).
Bind every non-blocked obligation exactly once: guarantees to theorems, assumptions to predicates, declarations to
declarations, exclusions and open questions with no Lean binding.
When the user context supplies a frozen required-source policy, each affected guarantee must contain the actual
registered `VeriSlop.Source.Contract` facet for a `VeriSlop.Source.SourceDefinition` bound to the exact typed endpoint.
Use the supplied pinned SourceBoundary prelude byte-for-byte before your own namespace; no substitute definitions.
Its closed requirements use `SourceRequirement.entry FILE ENTRY ARITY`, `typedTotal`, `deterministic`,
`inputPreserved`, `noExternalIO`, `noFloatingPoint`, `pureData` and `restrictedRuntimeOnly` as prescribed per ID.
For a value-required guarantee state `(complete_value_proposition) ∧ VeriSlop.Source.Contract Delivery` and provide
an exact value projection theorem whose proof is `by exact original_guarantee.1`. Its formalization binding has
`source_requirements:["fully.qualified.Delivery"]` and `value_projection:"fully.qualified.projection"` in addition
to the original theorem and obligation ID. Source-only bindings retain the Contract theorem and source_requirements
without inventing a value projection. Keep the original complete theorem as the bound guarantee. These facets prove
an abstract checking rule; they do not assert observed source facts. Native Python facets use a separate boundary
and cannot replace or share one theorem with source facets. Math-only existence/equality proxies omit required
entry, purity and floating-point constraints and will be rejected."""


TYPED_FORMALIZER_SYSTEM = f"""You are the VeriSlop formalizer ({PROMPT_VERSION}). Propose the exact contract for
the frozen interpreted obligations as an UNTRUSTED typed AST. A generic compiler renders Lean; Lean elaboration,
kernel replay, exact statement checking, proof search, acceptance and reconstruction still follow. Do not write
Lean punctuation into an AST string. Return ONLY a complete JSON object, without fences or commentary.

Envelope (listed keys required; native_requirements and source_requirements are optional; dictionaries keyed by ASCII identifier names):
{{"encoding":"verislop.formalizer-ast/0.1",
 "records":{{"RecordName":{{"fields":[{{"name":"field_name","sort":"Int"}}]}}}},
 "symbols":{{"function_name":{{"args":["Int"],"result":"Int","body":TERM}}}},
 "predicates":{{"predicate_name":{{"args":["Int"],"formula":FORMULA}}}},
 "theorems":{{"theorem_name":{{"formula":CLOSED_FORMULA}}}},
 "obligations":{{"actual_frozen_id":BINDING}},
 "witness_obligations":{{"fresh_id":{{"theorem":"theorem_name","witnesses_for":["actual_assumption_id"],"description":"why satisfiable"}}}}}}
These names illustrate shape only; choose your declarations and use ONLY actual frozen obligation IDs. Empty
records/predicates/witness_obligations are allowed when unnecessary. Definitions must be concrete, total and
acyclic. Record types must be monomorphic, nonrecursive, with 1..64 fields in their specified order. Preserve
the request's exact keys and actual types. A JSON-object API uses solve with ONE Input-record argument and its
actual Output record; neither caller fields nor resulting collections may disappear into an unrelated Nat model.
Symbols and predicates have arguments in application order. Their bodies use de Bruijn indices: var index 0
is the LAST argument, index 1 the previous argument. A nested binder pushes old indices up by one.

Sort is "Nat", "Int", "Bool", "Unit", "String", {{"list":SORT}}, {{"record":"RecordName"}}, or
{{"result":{{"error":SORT,"ok":SORT}}}} or {{"option":SORT}}. Nat is nonnegative with truncated subtraction; Int is exact signed;
String preserves Unicode scalar text exactly. No arbitrary JSON, hidden coercion, recursive/dependent records,
custom sorting, parsing or unsupported operation. If a faithful model is outside this frontend, report the gap;
never remove requirements or narrow to examples. The raw Lean proposal envelope is also supported for a domain
outside this frontend, but it has exactly the same strict proof and executable-DSL acceptance gates.

TERM grammar (objects have exactly the listed keys):
- {{"tag":"var","index":0}}; {{"tag":"nat","value":"0"}}; {{"tag":"int","value":"-1"}};
  {{"tag":"bool","value":true}}; {{"tag":"unit"}}; {{"tag":"string","value":"literal text"}}.
  Numeric literals are canonical decimal STRINGS (no leading zeros or -0).
- {{"tag":OP,"left":TERM,"right":TERM}}, OP is add/sub/mul for Nat, int_add/int_sub/int_mul/int_fdiv for Int,
  string_append for String, bool_and/bool_or for Bool, or bool_eq for matching scalar sorts.
- int_fdiv is mathematical floor division toward negative infinity; a zero divisor returns Int zero.
- {{"tag":OP,"value":TERM}}, OP is int_neg, nat_to_int (exact Nat→Int), int_to_nat (max(value,0)), bool_not, string_length (Nat),
  string_is_empty (Bool), list_length (Nat), list_reverse, or list_sum (Nat/Int lists).
- {{"tag":"record","sort":"RecordName","fields":[TERM,...]}}: fields follow the declared order.
- {{"tag":"field","sort":"RecordName","field":"field_name","value":TERM}}.
- {{"tag":"list","element_sort":SORT,"items":[TERM,...]}};
  {{"tag":"list_cons","head":TERM,"tail":TERM}}; {{"tag":"list_append","left":TERM,"right":TERM}}.
- {{"tag":"list_range","stop":NAT_TERM}} yields exactly the Nat list [0,...,stop-1], empty for zero.
- {{"tag":"list_get","value":LIST_TERM,"index":NAT_TERM}} returns Option of the element sort,
  none for an out-of-range index. Immediate Option/Unit payload restrictions apply.
- {{"tag":"list_sort","value":LIST_TERM}} admits List Nat/Int/String with fixed ascending scalar order.
- {{"tag":"list_unique","value":LIST_TERM}} admits List Nat/Int/String/Bool and preserves first occurrences.
  Neither term takes a candidate comparator or equality function. Strings use Unicode scalar lexicographic order.
- {{"tag":OP,"value":TERM,"function":{{"sort":ELEMENT_SORT,"body":TERM}}}}, OP list_map/list_filter.
  Lambda var index 0 is the element, index 1 the previously innermost variable. Filter returns Bool.
- {{"tag":"list_foldl","value":TERM,"initial":TERM,"function":{{"accumulator_sort":SORT,
  "element_sort":SORT,"body":TERM}}}}. Fold body index0 is element, index1 accumulator, index2 the
  previous innermost variable; body returns the accumulator sort, visits in order, empty returns initial.
- {{"tag":"decide","formula":FORMULA}}: quantifier-free scalar formula to Bool.
- {{"tag":"call","symbol":"function_name","args":[TERM,...]}}.
- {{"tag":"ok","error_sort":SORT,"value":TERM}} or {{"tag":"error","ok_sort":SORT,"value":TERM}}.
- {{"tag":"none","element_sort":SORT}}; {{"tag":"some","value":TERM}};
  {{"tag":"option_get_or","value":TERM,"default":TERM}};
  {{"tag":"option_is_some","value":TERM}} returns Bool. An Option wire value is None or the raw
  payload value; immediate Option-of-Option and Option Unit are prohibited to keep that representation injective.
- {{"tag":"ite","condition":BOOL_TERM,"then":TERM,"else":TERM}}: branches have exactly the same sort;
  only the selected branch is evaluated. Use an explicit Some branch when returning an optional payload.

FORMULA grammar:
- {{"tag":"true"}} / {{"tag":"false"}};
  {{"tag":REL,"left":TERM,"right":TERM}} for eq (matching sorts), lt/le (matching Nat/Int/String).
- {{"tag":"holds","term":BOOL_TERM}}; {{"tag":"not","body":FORMULA}};
  {{"tag":CONNECTIVE,"left":FORMULA,"right":FORMULA}} for and/or/implies/iff.
- {{"tag":QUANTIFIER,"sort":SORT,"body":FORMULA}} for forall/exists. Each binder pushes old indices
  up by one. Theorem formulas must be CLOSED; quantify every input variable explicitly.
- {{"tag":"predicate","predicate":"predicate_name","args":[TERM,...]}} explicitly references an
  assumption predicate. Such calls are a frontend construct; accepted Lean is later unfolded into the fixed DSL.

BINDING follows each actual frozen role: guarantee={{"theorem":"theorem_name"}},
assumption={{"predicate":"predicate_name"}}, declaration={{"declarations":[{{"kind":"record","name":"RecordName"}},
{{"kind":"symbol","name":"function_name"}}]}} (kind may also be predicate), exclusion/open_question={{}}.
Bind EACH active frozen ID once; do not bind blocked IDs. Several guarantee IDs may explicitly bind the same
complete theorem when that theorem covers all their observable requirements. The compiler does not infer coverage.

State complete observable behavior against fixed primitive expressions, including branch guards, output fields,
order, multiplicity and actual text. A solve(input)=solve(input) tautology, True, or equality between two
independently implemented helper functions cannot constrain the implementation. Inline the primitive expression
on the reference side to avoid extra unconstrained implementation symbols. Do not invent caller assumptions;
use interpreted assumptions only where the dependency permits them. Used assumptions require existential
non-vacuity theorems mentioning their actual predicate and concrete witnesses from subsequent proof search.
No proofs are supplied in this AST: theorem holes are generated mechanically and must later be proved.
Python native requirements are also supported as required facets of the SAME frozen guarantees; do not turn
them into assumptions, declarations, exclusions or optional claims. Optional top-level native_requirements is
{{"BoundaryName":{{"symbol":"actual_local_symbol","requirements":[NATIVE_REQUIREMENT,...]}}}}.
NATIVE_REQUIREMENT is {{"tag":"entry","file":"requested.py","qualname":"requested_function","arity":1}}
or exactly {{"tag":TAG}} for pure_json, standard_runtime_only, no_external_io, input_preserved, deterministic,
no_floating_point. Use no_floating_point for explicit bans on intermediate floating-point computation; integer
result equations alone do not discharge such a source requirement.
Use the actual requested relative file/name/arity, not these illustrative parameters. The symbol must be your
actual typed data function; all constructors/parameters are closed, with no receipts, source observations or PASS.
A theorem row may be {{"native":["BoundaryName"]}} for a source-only guarantee or
{{"formula":CLOSED_FORMULA,"native":["BoundaryName",...]}} for both value and source requirements.
Both forms produce real proof holes: the native rule proves checker transfer and nonvacuous admission in the
registered structural fact model. Actual Python conformance is checked separately against generated source.
Mixed rows require BOTH the original value proposition and every native facet; the compiler emits an exact
kernel-checked value projection. Do not invent a value equality to stand in for entry/layout/purity/no-I/O claims.
Keep JSON interface/functional output semantics in the typed input/output profile and value facet when requested.
The initial native checker admits closed acyclic pure JSON Python using registered len/sum/list/range and local
fresh-owned containers, with no imports or external I/O. It does not establish universal Python termination,
physical memory/time limits or every standard-library import. Preserve such unsupported requirements explicitly.
For an explicitly revised VSCore 0.3 restricted-source delivery, use the separate optional source_requirements map:
{{"SourceName":{{"symbol":"actual_local_symbol","requirements":[SOURCE_REQUIREMENT,...]}}}}.
SOURCE_REQUIREMENT is {{"tag":"entry","file":"program.vscore.json","entry":"actual_vscore_entry","arity":1}}
or exactly {{"tag":TAG}} for typed_total, deterministic, input_preserved, no_external_io, no_floating_point,
pure_data, restricted_runtime_only. Entry arity equals the accepted function signature; the entry name is a valid
VSCore identifier bound to that endpoint. No Python path, qualname, unknown parameter, observed fact or PASS is allowed.
Use theorem rows {{"source":["SourceName",...]}} or {{"formula":CLOSED_FORMULA,"source":["SourceName",...]}}.
Keep each source guarantee required under its actual frozen ID. Mixed source rows retain the COMPLETE value and
source proposition; the compiler emits a value projection depending on that original theorem. Never combine native
and source references in one theorem. They use independent algebras, namespaces and accepted package encodings.
The SourceBoundary Contract rule proves abstract checking soundness and model inhabitation. It does not establish
facts about delivered source. The exact VSCore3 bridge separately proves admitted typed-entry totality, deterministic
evaluation, unchanged input observations and empty effect traces in restricted-source semantics. Host interpreters,
compilers, operating systems, physical resources and independent TESTED campaigns are outside this source boundary.
Never replace source requirements with True or reflexive value equations, or change retained Python delivery claims
without an explicit revised request. Use the supervisor-selected boundary in the user context.
Repair rejected proposals using the checker feedback, retaining the frozen IDs and every requirement. Never
claim acceptance yourself, weaken a contract to get through a gate, or repeat a rejected unchanged proposal.
"""

CAPABILITY_REPORT_INSTRUCTIONS = """
If no faithful executable representation can be proposed, use ONLY this alternate JSON envelope:
{"encoding":"verislop.formalizer-capability-gap/0.1","obligation_ids":["actual active ID",...],
 "gaps":[{"obligation_ids":["actual affected ID",...],"feature":"specific missing operation/sort",
 "reason":"precise observable requirement that cannot be represented",
 "attempted_representations":["faithful supported representation considered and its concrete limitation"]}]}.
All keys are required; no extras. Retain EVERY active frozen ID exactly once in obligation_ids; gap refs
are nonempty subsets. Consider supported total folds, conditional expressions and admitted exact wire
representations before reporting a gap. An alternative must preserve all actual input/output types and
observable requirements; it cannot add caller assumptions, remove nulls/order, or replace the task with examples.
A report is untrusted search feedback, not proof of impossibility and not an accepted artifact. The existing
bounded critic/author loop seeks a changed faithful complete contract before reporting an explicit block.
When repairing a gap, propose a supported complete contract if possible; otherwise retain the precise gap
and explain the attempted alternate representation. Do not return a made-up status or arbitrary report envelope.
"""
FORMALIZER_SYSTEM += CAPABILITY_REPORT_INSTRUCTIONS
TYPED_FORMALIZER_SYSTEM += CAPABILITY_REPORT_INSTRUCTIONS


def _binding_manifest(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tell generators which existing IDs they must bind without inventing Lean names."""
    key_by_role = {"guarantee": "theorem", "assumption": "predicate", "declaration": "declarations",
                   "exclusion": None, "open_question": None}
    manifest = []
    for rec in records:
        blocked = rec.get("blocked_by", [])
        key = key_by_role[rec["role"]]
        shape: dict[str, Any] = {"obligation": rec["id"]}
        if key is not None:
            shape[key] = ["<qualified Lean declaration>"] if key == "declarations" else "<qualified Lean declaration>"
        manifest.append({"obligation": rec["id"], "role": rec["role"], "required": rec["required"],
                         "blocked_by": blocked, "binding": None if blocked else shape,
                         "allowed_assumptions": [d["id"] for d in rec["dependencies"] if d["relation"] == "assumes"]})
    return manifest


def validate_capability_report(obj: Any, records: list[dict[str, Any]]) -> dict:
    """A model's gap report is typed feedback, never an accepted contract."""
    if (not isinstance(obj, dict) or set(obj) != {"encoding", "obligation_ids", "gaps"}
            or obj.get("encoding") != CAPABILITY_VERSION):
        raise ValueError("use the exact formalizer capability-gap envelope")
    active = {r["id"] for r in records if not r.get("blocked_by")}
    ids = obj["obligation_ids"]
    if (not isinstance(ids, list) or not all(isinstance(i, str) for i in ids)
            or len(ids) != len(set(ids)) or set(ids) != active):
        raise ValueError("capability report must retain every active frozen obligation ID exactly once")
    gaps = obj["gaps"]
    if not isinstance(gaps, list) or not 1 <= len(gaps) <= 32:
        raise ValueError("capability gaps must be an array of 1..32 reports")
    def bounded(value, maximum):
        return isinstance(value, str) and 1 <= len(value) <= maximum and bool(value.strip())
    for gap in gaps:
        if not isinstance(gap, dict) or set(gap) != {"obligation_ids", "feature", "reason", "attempted_representations"}:
            raise ValueError("each capability gap must use the exact gap fields")
        refs, alternatives = gap["obligation_ids"], gap["attempted_representations"]
        if (not isinstance(refs, list) or not refs or not all(isinstance(i, str) for i in refs)
                or len(refs) != len(set(refs)) or not set(refs) <= active):
            raise ValueError("capability gap references must name actual active frozen obligations")
        if not bounded(gap["feature"], 256) or not bounded(gap["reason"], 4096):
            raise ValueError("capability feature/reason must be bounded nonempty strings")
        if (not isinstance(alternatives, list) or not 1 <= len(alternatives) <= 8
                or not all(bounded(value, 4096) for value in alternatives)):
            raise ValueError("record 1..8 bounded faithful alternate representations considered")
    return obj


def restore_formalizer_response(pkg: Package, candidate: dict) -> dict | None:
    """Validate pinned raw bytes before using retained context in another role."""
    from . import agent_memory
    from .errors import BlockedError
    if "raw_response" not in candidate and "raw_response_snapshot" not in candidate:
        return None
    text, ref = candidate.get("raw_response"), candidate.get("raw_response_snapshot")
    if not isinstance(text, str) or not isinstance(ref, dict):
        raise BlockedError("unbound formalizer response", [Diagnostic("STALE_OR_UNBOUND_EVIDENCE", "raw response lacks exact text or snapshot")])
    # latest_snapshot validates the entire current chain, including stale heads.
    agent_memory.latest_snapshot(pkg)
    restored = agent_memory.restore(pkg, ref)
    if restored.get("response.txt") != text.encode("utf-8"):
        raise BlockedError("changed formalizer response", [Diagnostic("STALE_OR_UNBOUND_EVIDENCE", "raw formalizer response differs from its pinned memory bytes")])
    return {"text": text, "snapshot_ref": ref}


def assemble_formalization_response(text: str, records: list[dict[str, Any]], response_ref: str):
    """Deterministic proposal assembly; raises for rejected untrusted responses."""
    obj = extract_json(text)
    if isinstance(obj, dict) and obj.get("encoding") == CAPABILITY_VERSION:
        return CAPABILITY_MARKER, {"capability_report": validate_capability_report(obj, records)}, None
    if isinstance(obj, dict) and obj.get("encoding") == "verislop.formalizer-ast/0.1":
        from .formal_frontend import compile_response
        compiled = compile_response(text.encode("utf-8"), records, "generated.v0_2", response_ref=response_ref)
        return compiled.source, compiled.formalization, compiled
    return obj["lean_source"].encode("utf-8"), obj["formalization"], None


def formalizer_agent(config: str | Path, pkg: Package, events: EventSink) -> Callable[[dict[str, Any]], tuple[bytes, dict]]:
    broker, conf = _broker(config, pkg)
    agent = _role(conf, "formalizer")
    unparseable_response: str | None = None

    def run(ctx: dict[str, Any]) -> tuple[bytes, dict]:
        nonlocal unparseable_response
        prior = ctx.get("previous_candidate") or {}
        retained_response = restore_formalizer_response(pkg, prior)
        if retained_response is not None:
            unparseable_response = retained_response["text"]
        if (unparseable_response is None and prior.get("lean_source")
                == "-- unparseable formalizer response\n"):
            from . import agent_memory
            retained = agent_memory.latest_snapshot(pkg, stage_prefix="agent/formalize/response")
            if retained:
                unparseable_response = agent_memory.restore(pkg, retained)["response.txt"].decode("utf-8")
        run.last_origin = None
        run.last_compiled = None
        run.last_response = None
        records = [{k: r[k] for k in ("id", "kind", "role", "statement", "required", "dependencies", "acceptance_criteria", "blocked_by")}
                   for r in ctx["records"]]
        user = "FROZEN INTERPRETED OBLIGATIONS (data):\n" + json.dumps(records, indent=1, ensure_ascii=False)
        user += "\nBINDING MANIFEST (supervisor-owned IDs and role constraints):\n" + json.dumps(
            _binding_manifest(records), ensure_ascii=False, indent=1)
        user += "\nASSUMPTION SUPPLIERS:\n" + json.dumps(ctx["ledger"].get("assumptions", []), ensure_ascii=False)
        requested = ctx.get("requested", pkg.meta().get("requested", {}))
        user += "\nREQUESTED ASSURANCE AND IMPLEMENTATION BOUNDARY (supervisor-selected, not changeable by the proposal):\n" + json.dumps(
            requested, ensure_ascii=False, indent=1)
        source_typed = (requested.get("target") == "vscore" and requested.get("tier") == 2
                        and requested.get("backend_version") == "0.3"
                        and requested.get("endpoint") in (None, "restricted_source"))
        if (requested.get("target") in (None, "python")
                and (requested.get("require_state") in ("TESTED", "END_TO_END_VERIFIED")
                     or requested.get("endpoint") == "test_campaign")):
            user += ("\nThis request requires executable downstream obligations. The current Python generated-test bridge admits "
                     "the stated Nat/Int/Bool/Unit/String/List/fixed-record/nullary-enumeration/Except/Option sorts and registered "
                     "arithmetic/list/record formulas. It does not admit arbitrary JSON semantics. Opaque Lean "
                     "acceptance cannot satisfy this requested assurance. Preserve the actual specification and report "
                     "a faithful unsupported domain rather than replacing it with a vacuous supported model.")
        if (requested.get("target") in (None, "python") and requested.get("tier") in (None, 0, 1)
                and (requested.get("require_state") == "TESTED" or requested.get("endpoint") == "test_campaign")):
            user += ("\nCAMPAIGN QUANTIFIER SHAPE (representation constraint, not a weaker specification): "
                     "Structured campaigns sample only a leading forall prefix. A residual forall or exists over "
                     "Nat/Int/String/List or another non-finite sort, including one inside a conjunction or "
                     "implication, is not executable reference-preflight evidence. Finite Bool/Unit/enumeration "
                     "and finite composite quantifiers and explicit range quantifiers remain admitted. State "
                     "faithfully equivalent pointwise formulas beneath leading universal binders where "
                     "equivalence holds for the requested domain. Preserve all examples, guards, obligations "
                     "and dependencies; moving a closed conjunct under a binder can require an inhabited domain. "
                     "Never replace an existential by a universal, bound an infinite requirement, or drop a "
                     "claim to fit the test language. Propose your own complete replacement and let the ordinary "
                     "Lean, denotation and critic checks evaluate it.")
        python_typed = (requested.get("target") in (None, "python") and requested.get("tier") in (None, 0)
                        and (requested.get("require_state") == "TESTED" or requested.get("endpoint") == "test_campaign"))
        typed = python_typed or source_typed
        source_policy = _source_policy_context(pkg)
        if source_policy is not None:
            user += _source_policy_prompt(source_policy)
            user += ("\nEvery policy row is checked against the kernel-elaborated theorem before proof generation, "
                     "and again after acceptance and in closure. Missing source facets, changed entry/arity or "
                     "omitted IDs must be repaired under the same specification. Use an actual typed endpoint "
                     "and the real SourceBoundary Contract conjunction; math-only proxies do not meet the policy. "
                     "Native Python requirements do not discharge this source policy.")
            if typed:
                user += ("\nPOLICY AUTHORING WIRE: source_requirements is a map from local definition IDs to "
                         '{"symbol":"actual_local_function","requirements":[{"tag":"entry","file":"program.vscore.json",'
                         '"entry":"exact_policy_entry","arity":0},{"tag":"typed_total"}]} (use the actual policy arity '
                         "and every policy property, not the illustrative values). Property constructors are exactly "
                         '{"tag":TAG}, with TAG one of typed_total, deterministic, input_preserved, no_external_io, '
                         "no_floating_point, pure_data, restricted_runtime_only. Each obligations[OID] binds its "
                         'theorem local ID; that theorems row has {"source":["source_definition_local_ID"]}, '
                         'plus "formula":CLOSED_FORMULA whenever value_required=true. Keep the full formula. '
                         "The compiler emits the exact Contract conjunct and value projection depending on the "
                         "original theorem. Do not author Lean code or fact observations inside this AST.")
            else:
                from . import source_contract

                user += ("\nRAW LEAN SOURCE POLICY: Include the exact pinned prelude below, then declare your "
                         "typed endpoint and SourceDefinition whose endpoint field is that function and whose "
                         "requirements are the policy's exact entry constructor and closed properties. Each "
                         "required original theorem contains VeriSlop.Source.Contract of the bound definition; "
                         "value_required=true also retains the complete value conjunct and a projection of that "
                         "original theorem. Bind the definition via source_requirements in the matching "
                         "formalization.bindings row and the "
                         "projection via value_projection. No native facet or mathematical proxy substitutes "
                         "for this conjunction.\nPINNED SOURCEBOUNDARY PRELUDE (copy exactly, including its import):\n"
                         + source_contract.library_source().decode("utf-8"))
        if typed:
            user += ("\nPrefer the typed AST envelope. In that envelope bindings use LOCAL declaration IDs, not the "
                     "qualified Lean-name placeholders in the manifest; the compiler qualifies them. No supervisor "
                     "registry or Lean proof/source strings belong inside the typed proposal.")
        if python_typed:
            user += ("\nNATIVE BOUNDARY FACETS: The typed envelope accepts optional native_requirements definitions "
                     "and theorem rows with native references, including mixed formula+native guarantees. "
                     "Entry file/name/arity, closed pure JSON, standard-runtime-only facilities, no external I/O, "
                     "borrowed-input preservation and deterministic local evaluation have registered structural "
                     "contracts. Author the actual requested parameters and faithful facets under the same "
                     "frozen IDs. The kernel proves the model transfer/admission theorem; actual generated "
                     "source must independently pass the bound checker and finite entry campaign. These are "
                     "not opaque claims and are not grounds for an unsupported report merely because they "
                     "observe source properties. Physical resource/liveness claims remain unsupported.")
        if source_typed:
            user += ("\nVSCORE 0.3 SOURCE BOUNDARY: Delivery is canonical program.vscore.json under data-pipeline/0.3 "
                     "and restricted_source semantics. Use source_requirements and source theorem references for "
                     "the actual frozen entry/type/purity/determinism/input-preservation/runtime requirements, "
                     "with optional formula facets for functional behavior. Preserve every required ID and the "
                     "complete typed data domain, including all binders, branch guards and ordered record fields. "
                     "SourceBoundary proves the abstract checking rule; exact source discharge is a separate "
                     "VSCore3 kernel bridge with admission and observation laws. Author no fact flags, snapshots, "
                     "effect traces or source-policy receipts. Native Python facets require their own endpoint; "
                     "do not copy them into this revised source boundary. Universal refinement is required for "
                     "value behavior; finite runtime examples cannot replace it. TESTED is an unsupported separate "
                     "campaign capability, so do not constrain formulas to a sampled leading-forall campaign. "
                     "Opaque statements, physical-resource/liveness claims and host execution remain unsupported.")
        witnessed = sorted({d["id"] for r in records if r["required"] and r["role"] == "guarantee" and not r["blocked_by"]
                            for d in r["dependencies"] if d["relation"] == "assumes"})
        user += "\nASSUMPTIONS REQUIRING SATISFIABILITY WITNESSES:\n" + json.dumps(witnessed)
        if pkg.path("prompt").is_file():
            user += "\nRECORDED REQUEST CONTEXT (untrusted data; retain frozen obligations):\n<<<\n" + pkg.path("prompt").read_text(encoding="utf-8") + "\n>>>"
        if ctx.get("previous_candidate") is not None:
            user += "\nPREVIOUS CANDIDATE (untrusted source and binding proposal; repair rather than weaken):\n" + json.dumps(
                ctx["previous_candidate"], ensure_ascii=False, indent=1)
        if retained_response is not None:
            user += "\nEXACT PREVIOUS FORMALIZER RESPONSE (untrusted bytes restored from validated memory):\n" + retained_response["text"]
            user += "\nVERIFIED RESPONSE SNAPSHOT (context provenance only):\n" + json.dumps(retained_response["snapshot_ref"])
        if ctx["feedback"]:
            if unparseable_response is not None and retained_response is None:
                user += "\nPREVIOUS REJECTED FORMALIZER RESPONSE (untrusted candidate; address its actual diagnostics):\n" + unparseable_response
            user += "\nThe previous candidate was rejected by the statement checker:\n- " + "\n- ".join(ctx["feedback"])
            user += (f"\nCORRECTION ATTEMPT {ctx['attempt']}: inspect each diagnostic and return a changed complete proposal "
                     "that fixes the rejected syntax or registered-language use while preserving all obligations. "
                     "Returning the same rejected source and bindings does not repair it.")
        if ctx.get("critique"):
            user += "\nAUTONOMOUS CRITIQUE (untrusted proposals; preserve every interpreted obligation):\n" + json.dumps(
                {"status": ctx["critique"]["status"], "feedback": ctx["critique"].get("feedback", [])}, ensure_ascii=False)
        comp = recorded_call(broker, pkg, agent, f"formalizer/{ctx['attempt']}",
                           TYPED_FORMALIZER_SYSTEM if typed else FORMALIZER_SYSTEM, user, "formalize")
        from . import agent_memory
        response_ref = agent_memory.latest_snapshot(pkg, stage_prefix="agent/formalize/response")
        run.last_response = {"text": comp.text, "snapshot_ref": response_ref}
        try:
            source, form, compiled = assemble_formalization_response(
                comp.text, ctx["records"], getattr(comp, "request_id", None) or "captured-provider-response")
            if compiled is not None:
                run.last_compiled = compiled
                run.last_origin = {"proposal": compiled.proposal, "receipt": compiled.receipt}
            unparseable_response = None
            return source, form
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            unparseable_response = comp.text
            return b"-- unparseable formalizer response\n", {"error": f"unparseable formalizer response: {exc}"}

    run.last_origin = None
    run.last_compiled = None
    run.last_response = None
    return run


# ------------------------------------------------------------------------------------------
# prover
# ------------------------------------------------------------------------------------------

PROVER_SYSTEM = f"""You are a VeriSlop proof agent ({PROMPT_VERSION}) working in a sandbox on a FROZEN Lean 4 (v4.34.1) challenge.
Replace every `sorry` with a proof. You MUST NOT change any theorem statement, definition, instance, import, or the
generated `VeriSlop.Registry` block: any change is detected and rejected. Do not use `sorry`, `native_decide`,
`axiom`, `implemented_by` or `extern`. Existential (non-vacuity) proofs must use explicit witnesses, e.g.
`exact ⟨1, 0, by decide, rfl⟩` or `refine ⟨1, 0, ?_⟩; simp [defs]`. Useful tactics: `grind [defs]`, `simp [defs]`,
`unfold defs at h; split at h`, `omega`, `decide`. For closed computations involving well-founded library
functions (such as sorting) and record-valued equalities, `cbv <;> simp_all <;> done` produces a normal kernel-checked
proof without requiring record DecidableEq. A failed `rfl` or `decide` attempt is not evidence that a statement is false.
For existential witnesses over the structured data profile, supply actual typed record constructors with all fields,
lists and Unicode string literals. Quote field names with guillemets. A Nat placeholder cannot inhabit a record.
Return ONLY one JSON object: {{"lean_source":"<complete Lean source>"}}.
The lean_source string must contain the complete Lean file, with JSON-escaped newlines and quotes;
do not wrap the file in a Markdown code block. Preserve all definitions, namespace boundaries and the generated
registry byte-for-byte; return the complete file rather than a list of replacement theorems. When a previous attempt
is supplied, use its exact diagnostics to repair its proofs. A successful incomplete baseline is not evidence that
the previous proposal compiled. Do not discard the current Lean failures or alter a frozen statement to fix them."""


def assemble_proof_response(response: str) -> str:
    """Deterministically preserve the supported JSON/fenced/legacy proof envelope."""
    text = response.strip()
    json_fence = re.fullmatch(r"```(?:json)?\s*\n(.*?)```\s*", text, re.S)
    for candidate in ([json_fence.group(1)] if json_fence else []) + [text]:
        try:
            obj = canonical.loads(candidate.strip())
        except canonical.CanonicalJSONError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("lean_source"), str) and obj["lean_source"].strip():
            return obj["lean_source"]
        return response
    if text.startswith(("{", "[")) or text.startswith("```json"):
        return response
    fences = re.findall(r"```lean\s*\n(.*?)```", response, re.S)
    return fences[-1] if fences else response


def prover_agent(config: str | Path, pkg: Package, events: EventSink) -> Callable[[dict[str, Any]], str]:
    broker, conf = _broker(config, pkg)
    agent = _role(conf, "prover")

    def run(ctx: dict[str, Any]) -> str:
        user = "CURRENT FILE:\n```lean\n" + ctx["best"] + "\n```\n"
        if ctx.get("previous_candidate") is not None:
            user += "\nPREVIOUS PROOF ATTEMPT (exact untrusted submitted source; repair proofs without changing the frozen contract):\n" + json.dumps(
                {"lean_source": ctx["previous_candidate"], "result": ctx.get("previous_result")}, ensure_ascii=False, indent=1)
            user += "\nThe CURRENT FILE is the best baseline; the PREVIOUS PROOF ATTEMPT is the latest evaluated proposal. Its failures must be addressed even if the baseline elaborates with unresolved sorry proofs.\n"
        if ctx["errors"]:
            user += "LEAN ERRORS (latest attempt, not merely the best baseline):\n" + "\n".join(ctx["errors"]) + "\n"
        if ctx.get("critique"):
            user += "\nAUTONOMOUS PROOF CRITIQUE (untrusted correction advice; frozen statements cannot change):\n" + json.dumps(
                {"status": ctx["critique"]["status"], "feedback": ctx["critique"].get("feedback", [])}, ensure_ascii=False)
        comp = recorded_call(broker, pkg, agent, f"prover/{ctx['attempt']}", PROVER_SYSTEM, user, "prove")
        return assemble_proof_response(comp.text)

    return run


# ------------------------------------------------------------------------------------------
# implementer
# ------------------------------------------------------------------------------------------

IMPLEMENTER_SYSTEM = f"""You are a VeriSlop implementation agent ({PROMPT_VERSION}). Implement the accepted contract in Python
using the fixed python-v0_1 profile: Nat -> int >= 0; Bool -> bool; Unit -> None; an enumeration constructor -> its
name as str; Result(E, A) -> the 2-tuple ("ok", a) or ("error", e). Functions must be total, pure and deterministic,
take exactly the declared positional arguments, and must not raise. Use only the standard library.
The accepted formula_package ASTs and full semantic profile are authoritative; rendered display strings are commentary.
Preserve quantifier order, branch guards, accepted assumptions and the exact Nat/Result semantics. Only use obligation
IDs present in the accepted IR context for bindings; never copy a sample ID that is absent from that artifact.
Each bindings[].symbol must be an EXACT key in the supplied Python binding manifest, which may differ from its Lean
declaration name. Bind each required key exactly once, using a unique plain top-level function of the declared arity.
For the registered concrete target_case reviewer, write plain top-level pure functions without annotations, defaults,
decorators, imports, reflection, I/O or nested functions. Keep helpers in the same admitted pure syntax and declare them.
Calls may target only plain top-level functions defined in the delivered file, with positional arguments; builtin calls
such as max, min, abs and int are outside that replay profile. For Nat subtraction use truncated subtraction, for example
`left - right if right <= left else 0`, rather than negative integers.
Return ONLY one JSON object:
{{"files": {{"module_name.py": "<source>"}},
 "bindings": {{"schema_version":"0.1","artifact_kind":"implementation_bindings","target":"python",
   "serialization_profile":"python-v0_1","bindings":[{{"binding_id":"B-sym","symbol":"<profile symbol>",
   "object":{{"file":"module_name.py","qualname":"<function>"}},"obligations":["O1"]}}],"helpers":[]}}}}
Every public top-level function must be bound to a symbol or declared in helpers with a reason."""


IMPLEMENTER_SYSTEM_V2 = f"""You are a VeriSlop implementation agent ({PROMPT_VERSION}). Implement the accepted contract in
Python using the frozen python-v0_2 serialization profile. Nat is an exact nonnegative int (not bool), with truncated
subtraction. Int is an exact signed arbitrary-precision int (not bool), with ordinary signed subtraction. Bool is bool;
Unit is None; String is a Unicode scalar str; List A is an actual Python list of A; a fixed-field Record is an actual
Python dict with exactly its accepted field names and recursively typed values. An enum is its constructor name as
str; Result(E,A) is the 2-tuple ("ok", a) or ("error", e). Option A is None for none or the ordinary raw
Python representation of A for some; never use a tagged tuple for an Option. Do not convert lists into tuples or flatten a record argument
into multiple arguments. Preserve field values, sequence order, duplicates, empty values and exact Unicode text.
The accepted formula_package ASTs and full semantic profile are authoritative; display strings are commentary.
Functions must be total, pure and deterministic on their typed domain, take exactly the declared positional arguments,
and must not raise. Preserve quantifier order, branch guards and accepted assumptions. Use only obligation IDs from
the accepted IR. Bind each required EXACT key in the Python binding manifest once to a unique top-level function of
the declared arity; symbol keys can differ from Lean names. No annotations, defaults, decorators, imports, classes,
reflection, I/O, globals or nested functions. Helpers must also be plain top-level functions and declared in helpers.
The concrete reviewer admits ordinary arithmetic, comparison, conditionals, literal lists/dicts, subscripts/slices,
list comprehensions, local for loops, local assignments and augmented assignments, break and continue. Calls may
target delivered top-level functions or the pure builtins len, sum, list and range, with positional arguments only.
One-argument append and subscript writes require a proven freshly allocated list/dict root. Arguments and their
indexed or iterated children are borrowed, including nested children of shallow copies; do not mutate them.
Track aliases conservatively across branches and loops; helper parameters are borrowed. Do not mutate active
iterables or shadow builtin/helper call names. Duplicate top-level names and recursive helpers are rejected.
Other attribute calls and other builtins are unsupported. Follow exact native entry filenames/qualnames in the
binding manifest when native_entry_required is true; the supervisor will not rename your captured proposal.
The native no_floating_point policy covers intermediate operations too: avoid `/`, floating literals, and powers
without a closed nonnegative integer literal exponent. Use exact integer division and admitted integer loops.
Modulo requires a proven integer left operand under that policy; string formatting through `%` can introduce
floating-point conversions and is rejected. The same rules apply to augmented assignments and helper bodies.
Membership operators in/not in are outside this replay subset; use explicit loops and scalar equality instead.
Implement primitive expressions as defined by the supplied AST, including Int operations, list filter/map/length/sum/foldl,
record construction/fields, Boolean predicates and String concatenation. Do not replace the contract with examples,
use guessed field names, impose machine-width arithmetic or drop a required binding.
The nat_to_int operation preserves its nonnegative integer value exactly. A list_foldl starts at initial and visits
elements from left to right. Its function body uses de Bruijn index 0 for the element, index 1 for the accumulator,
and indices 2 and above for captured outer variables. The empty fold returns initial; preserve order for every sort.
The ite term evaluates only its selected branch. option_get_or selects the raw optional payload or its default;
option_is_some tests against None. Preserve these exact null semantics in every record and list field.
list_range(stop) corresponds to list(range(stop)). int_to_nat(value) returns value if nonnegative, otherwise zero.
int_fdiv(left,right) returns left // right when right is nonzero and zero otherwise; do not raise on zero.
list_get(xs,index) returns xs[index] when index is in range, otherwise None. Keep Some zero or an empty list intact.
list_sort is ascending scalar sorting; implement it with admitted loops/comparisons because sorted/list.sort are
outside this replay subset. list_unique preserves the first occurrence, comparing scalar values in encounter order.
Return ONLY one JSON object:
{{"files": {{"module_name.py": "<source>"}},
 "bindings": {{"schema_version":"0.1","artifact_kind":"implementation_bindings","target":"python",
   "serialization_profile":"python-v0_2","bindings":[{{"binding_id":"B-sym","symbol":"<profile symbol>",
   "object":{{"file":"module_name.py","qualname":"<function>"}},"obligations":["<accepted guarantee ID>"]}}],"helpers":[]}}}}
Every public top-level function must be bound to a symbol or declared in helpers with a reason."""


def _accepted_implementation_formulas(pkg: Package, ctx: dict[str, Any]) -> dict[str, Any]:
    """Read hash-bound packages reconstructed from the accepted environment, never a draft."""
    from .backends import admission
    from . import contract_values, dsl

    profile = dsl.Profile.from_json(ctx["profile"])
    formulas = {}
    for oid, rec in sorted(ctx["ir"]["obligations"].items()):
        package = admission.formula_package(pkg, rec)
        if package is None:
            raise UsageError("accepted expression packages are missing or changed",
                             [Diagnostic("INPUT_MUTATION", f"{oid}: accepted formula_ref no longer binds its expression bytes", obligations=[oid])])
        formal = rec["formal"]
        statement = ctx["statements"].get(oid)
        if formal["representation"] in ("contract_dsl", "contract_facets", "source_facets"):
            if statement is None or statement.get("formula_package") != package:
                raise UsageError("checked statement and accepted expression package disagree",
                                 [Diagnostic("IR_REIFICATION_MISMATCH", f"{oid}: implementation context differs from its accepted formula package", obligations=[oid])])
            value = contract_values.value_package(package)
            if value is not None:
                dsl.check_package(value, profile)
        formulas[oid] = {"id": rec["id"], "revision": rec["revision"], "kind": rec["kind"], "role": rec["role"],
                         "required": rec["required"], "dependencies": rec["dependencies"],
                         "formal": formal, "formula_package": package,
                         "display": statement.get("display") if statement else None}
    return formulas


def _python_prompt_formulas(statements: dict[str, Any]) -> dict[str, Any]:
    """Lossless content-addressed transport of already checked accepted packages."""
    packages, obligations = {}, {}
    for oid, statement in sorted(statements.items()):
        row = dict(statement)
        package = row.pop("formula_package")
        reference = canonical.digest_json(package)
        packages[reference] = package
        row["formula_package_ref"] = reference
        obligations[oid] = row
    return {"encoding": "verislop.implementation-formulas/0.1",
            "obligations": obligations, "formula_packages": packages}


def _python_binding_manifest(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Exact target keys and permitted claim coverage from checked semantic closures."""
    from .materialize import symbols_for

    from . import native_contract
    layouts = {}
    for statement in ctx["statements"].values():
        for facet in native_contract.native_facets(statement.get("formula_package", {})):
            for requirement in facet["requirements"]:
                if requirement["tag"] == "entry":
                    object_ = {"file": requirement["file"], "qualname": requirement["qualname"]}
                    previous = layouts.setdefault(facet["symbol"], object_)
                    if previous != object_:
                        raise UsageError("accepted native entry requirements conflict", [Diagnostic(
                            "STATEMENT_MISMATCH", "one accepted symbol has incompatible native entry layouts")])
    manifest = []
    for symbol, spec in sorted(ctx["profile"]["symbols"].items()):
        covered = sorted(oid for oid, rec in ctx["ir"]["obligations"].items()
                         if applicability(rec)["LINKED"][0]
                         and symbol in symbols_for(oid, ctx["ir"], ctx["profile"], ctx["statements"]))
        manifest.append({"symbol": symbol, "lean_decl": spec["lean_decl"], "arity": len(spec["args"]),
                         "args": spec["args"], "result": spec["result"], "allowed_obligations": covered,
                         "required": any(ctx["ir"]["obligations"][oid]["required"] for oid in covered),
                         "object": layouts.get(symbol, {"file": "<delivered .py path>", "qualname": "<plain top-level function>"}),
                         "native_entry_required": symbol in layouts})
    return manifest


def _python_proposal(obj: Any, ctx: dict[str, Any], manifest: list[dict[str, Any]]) -> tuple[dict[str, bytes], Any, list[Diagnostic]]:
    """Read-only schema, source inventory and shared binding checks; no milestones."""
    from . import fsutil, link, schemas
    from .targets import python_target

    if not isinstance(obj, dict) or set(obj) != {"files", "bindings"}:
        return {}, None, [Diagnostic("INVALID_CANDIDATE", "implementation proposal must contain exactly files and bindings")]
    proposed_files = obj["files"]
    proposal = obj["bindings"]
    if (not isinstance(proposed_files, dict) or not proposed_files or
            not all(isinstance(path, str) and isinstance(source, str) for path, source in proposed_files.items())):
        return {}, proposal, [Diagnostic("INVALID_CANDIDATE", "files must be a nonempty mapping of relative .py paths to UTF-8 source strings")]
    files = {}
    diags = schemas.require_valid("implementation-bindings", proposal, "binding proposal")
    for path, source in proposed_files.items():
        try:
            if "\x00" in path:
                raise ValueError("NUL is not permitted in an implementation path")
            path.encode("utf-8")
            fsutil.check_relpath(path)
            if not path.endswith(".py"):
                raise ValueError("implementation agent source files must end in .py")
            files[path] = source.encode("utf-8")
        except (UsageError, ValueError) as exc:
            diags.append(Diagnostic("INVALID_CANDIDATE", f"implementation file {path!r}: {exc}"))
    # Reject impossible or ambiguous file trees before any temporary source write.
    # These are untrusted proposal defects, not mutations of accepted artifacts.
    folded = {}
    for path in files:
        key = path.casefold()
        if key in folded:
            diags.append(Diagnostic("INVALID_CANDIDATE", f"case-insensitive implementation path collision: {folded[key]!r} vs {path!r}"))
        else:
            folded[key] = path
    for path in files:
        parts = path.split("/")
        for length in range(1, len(parts)):
            prefix = "/".join(parts[:length]).casefold()
            if prefix in folded:
                diags.append(Diagnostic("INVALID_CANDIDATE", f"implementation file {folded[prefix]!r} is also a parent directory of {path!r}"))
    if diags:
        return files, proposal, diags
    with fsutil.temporary_directory(prefix="verislop-implementation-proposal-") as directory:
        root = Path(directory)
        for path, source in files.items():
            fsutil.atomic_write(root / path, source)
        inventory = python_target.inventory(root)
        diags.extend(Diagnostic("CANDIDATE_BUILD_FAILURE", f"syntax error: {error}") for error in inventory.errors)
        diags.extend(link.structural_proposal_diagnostics(
            proposal, ctx["profile"], inventory, {row["symbol"]: row["allowed_obligations"] for row in manifest}))
    from . import native_source
    checked = native_source.check_sources(files, ctx["ir"], ctx["profile"], bindings=proposal,
                                          statements=ctx["statements"])
    diags.extend(native_source.diagnostics(checked))
    bound = {binding["symbol"] for binding in proposal["bindings"]}
    for row in manifest:
        if row["required"] and row["symbol"] not in bound:
            diags.append(Diagnostic("UNMAPPED_IMPLEMENTATION_OBJECT", f"no binding for required profile symbol {row['symbol']}",
                                    obligations=row["allowed_obligations"]))
    return files, proposal, diags


def implementer_agent(config: str | Path, pkg: Package, events: EventSink, *, attempts: int = 3, proof_attempts: int = 3) -> Callable[[dict[str, Any]], tuple[dict[str, bytes], dict]]:
    broker, conf = _broker(config, pkg)
    agent = _role(conf, "implementer")

    def run(ctx: dict[str, Any]) -> tuple[dict[str, bytes], dict]:
        if ctx["parameters"].get("target") == "vscore":
            return _vscore_implementation(broker, conf, pkg, events, ctx, attempts, proof_attempts)
        statements = _accepted_implementation_formulas(pkg, ctx)
        manifest = _python_binding_manifest(ctx)
        provenance = {k: v for k, v in ctx["ir"].items() if k != "obligations"}
        provenance["accepted_ir_sha256"] = canonical.digest_json(ctx["ir"])
        transport = _python_prompt_formulas(statements)
        def encode(value):
            return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        user = ("ACCEPTED IR PROVENANCE (artifact-derived, supervisor-checked):\n" + encode(provenance)
                + "\nACCEPTED SEMANTIC PROFILE (authoritative sorts and symbols to implement):\n" + encode(ctx["profile"])
                + "\nACCEPTED FORMULAS (authoritative formula_package ASTs; display is commentary):\n" + encode(transport)
                + "\nFORMULA TABLE RULE: Every obligations entry retains its accepted metadata. Its formula_package_ref "
                  "names the exact formula_packages entry; substitute that whole package to recover formula_package. "
                  "Several obligations may refer to the same package. Preserve every obligation and all binders/guards; "
                  "this is lossless transport, not a change to the accepted contract.\n"
                + "\nPYTHON BINDING MANIFEST (exact symbol keys, arities and permitted obligation IDs):\n" + encode(manifest)
                + "\nFROZEN IMPLEMENTATION PARAMETERS:\n" + encode(ctx["parameters"]))
        feedback = ""
        diagnostics = []
        system = (IMPLEMENTER_SYSTEM_V2 if ctx["parameters"].get("serialization_profile") == "python-v0_2"
                  else IMPLEMENTER_SYSTEM)
        call_cap = conf.get("review", {}).get("budgets", {}).get("max_calls_per_instance", 3)
        for number in range(1, min(3, max(1, attempts), call_cap) + 1):
            # Broker failures and accepted-artifact binding errors are not model protocol defects.
            comp = recorded_call(broker, pkg, agent, "implementer/1", system, user + feedback, "generate")
            try:
                obj = extract_json(comp.text)
            except ValueError as exc:
                diagnostics = [Diagnostic("INVALID_CANDIDATE", f"unparseable implementer proposal: {exc}")]
            else:
                files, proposal, diagnostics = _python_proposal(obj, ctx, manifest)
                if not diagnostics:
                    return files, proposal
            events.emit("diagnostic", "generate", f"implementation proposal attempt {number} needs correction",
                        details={"diagnostics": [d.to_json() for d in diagnostics]})
            feedback = ("\nPREVIOUS IMPLEMENTATION PROPOSAL (exact untrusted response, including files and bindings):\n"
                        + comp.text + "\nIMPLEMENTATION PROPOSAL VALIDATOR DIAGNOSTICS:\n"
                        + json.dumps([d.to_json() for d in diagnostics], indent=1)
                        + "\nReturn a corrected complete proposal for the SAME accepted contract and binding manifest. "
                          "Preserve all formulas, assumptions, guarantee IDs and frozen parameters; no silent key substitution "
                          "or weaker contract. These checks inspect structure only; downstream verifiers decide milestones.")
        raise UsageError("the implementer exhausted its bounded proposal correction attempts", diagnostics)

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


VSCORE3_IMPLEMENTER_SYSTEM = f"""You are a VeriSlop VSCore implementation agent ({PROMPT_VERSION}). Propose a total pure
vscore/0.3 program, profile data-pipeline/0.3, and a one-to-one accepted-symbol relation for the exact accepted contract.
The delivered endpoint is program.vscore.json under restricted_source and vscore-semantics/0.3.
Use only the supplied canonical source grammar: unbounded Nat and Int, Bool, Unit, Unicode scalar String,
accepted enumerations, ordered nominal records/variants, Result, Option, List, acyclic helpers and finite folds.
Int arithmetic is exact; int_fdiv uses total Lean Int.fdiv, including zero and negative divisors.
String literals are arrays of Unicode scalar codepoints; signed Int literals are canonical decimal strings.
List indexing returns Option. Scalar sort uses the fixed ascending Nat/Int/String ordering; unique preserves
first occurrences. No general recursion, state, I/O, floating point or machine-width arithmetic is available.
Every entry binds exactly one accepted function and must discharge its exact generated source obligations.
Value behavior additionally requires universal total refinement for every used endpoint. Source-only endpoints
absent from every value predicate need the exact operational source laws, without an arbitrary reference-body
equality. Unrelated additional bound entries still require refinement. Follow the generated inventory exactly.
Preserve accepted type identity, record field order, all assumptions and every required obligation ID.
The supervisor owns the exact adapters, source_fn functions, raw encoding laws, evaluator equations and goals.
The helper relation has exactly schema_version="0.3", format="verislop.vscore-relation/0.3",
template="vscore.reference_refinement/0.3", source_slot="vscore-source", proof_slot="vscore-proof",
and bindings=[{{"symbol": <accepted symbol>, "entry": <program entry>}}, ...]. Use these literal slot IDs;
slots are not filenames or theorem names. Sort bindings by unique symbol and use unique entries.
Do not reinterpret retained Python delivery requirements or weaken the accepted contract.
Return ONLY a JSON object with exactly:
{{"program": <source program object>, "relation": <relation descriptor object>, "proof_source": <optional Lean proof text>}}
The supervisor encodes canonical source/relation bytes and derives the Lean goal. Omit proof_source if you have
no proof. Never supply a goal/proposition hash, accepted IR, evidence, lifecycle state or an imported contract.
The optional proof imports VeriSlopBridgeGoal and declares VeriSlopBridgeProof.edge : VeriSlopBridgeGoal.EdgeProp.
Your proposals have no acceptance authority; the registered kernel checks decide every result."""

VSCORE3_PROVER_SYSTEM = f"""You are a VeriSlop VSCore proof agent ({PROMPT_VERSION}). Propose one Lean 4 proof module for
the verifier-generated exact VSCore 0.3 goal, fixed canonical source and accepted reference below.
The endpoint is restricted_source under vscore-semantics/0.3. Import VeriSlopBridgeGoal and prove theorem
VeriSlopBridgeProof.edge : VeriSlopBridgeGoal.EdgeProp. Follow the exact generated goal and helper theorems.
Refines_<symbol> is universal equality of the intrinsically compiled source_fn_<symbol> and accepted function.
Prove only the generated refinement inventory: an endpoint used solely by source facets has operational laws
without arbitrary reference-body equality; value-used endpoints and unrelated bound extras retain refinement.
The goal also binds exact parse/typing, typed adapter inverses, raw decode-after-encode/injectivity, admitted-input
coverage, raw evaluator correspondence and transfer of every required accepted guarantee under all binders.
Source facets also require exact admitted-entry/observation laws and checking transfer through the accepted
SourceBoundary Contract theorem. The supervisor derives every fact from source admission and semantics; never
supply fact flags, traces, snapshots or source-policy assertions. Follow the source-only or mixed goal as generated.
Do not change source, relation, adapters, goal, accepted reference, domain types, assumptions or definitions.
No sorry, axiom, native_decide, implemented_by, extern or additional imported modules outside pinned policy.
The supervisor supplies a closed proof_support catalog of kernel-proved universal transport lemmas.
Choose its lemmas explicitly in rw/simp only; identity maps and Bool/Prop guards need their own normalization.
Compiler-produced dependent casts can require with_unfolding_all around a small change, rfl or exact step.
Do not unfold the whole compiler into every goal. Inspect source_fn_*, Refines_* and edge_of_refines first.
For closed decidable witness preconditions, decide +kernel is available. Broad cbv can expose compiler casts.
Return ONLY the complete proof module in one ```lean code block. A failed attempt receives bounded checker
diagnostics with a compact entry for every reported error and a bound full-error artifact reference;
no response assigns an evidence outcome or lifecycle state."""


def _vscore_components(parameters: dict[str, Any]) -> dict[str, Any]:
    """Dispatch only the selected backend/version; proposals cannot choose their checker."""
    backend, version = parameters.get("backend"), parameters.get("backend_version")
    if backend == "verislop.backend.vscore/0.1" and version in (None, "0.1"):
        # Existing 0.1 contexts predate the explicit frozen version field.
        from .bridges import vscore_checker
        from .targets import vscore_source, vscore_target
        return {"source": vscore_source, "target": vscore_target, "checker": vscore_checker,
                "source_schema": "vscore-source", "relation_schema": "vscore-relation",
                "implementer_system": VSCORE_IMPLEMENTER_SYSTEM, "prover_system": VSCORE_PROVER_SYSTEM}
    if backend == "verislop.backend.vscore/0.3" and version == "0.3":
        from .bridges import vscore3_checker
        from .targets import vscore3_source, vscore3_target
        return {"source": vscore3_source, "target": vscore3_target, "checker": vscore3_checker,
                "source_schema": "vscore-source-v3", "relation_schema": "vscore-relation-v3",
                "implementer_system": VSCORE3_IMPLEMENTER_SYSTEM, "prover_system": VSCORE3_PROVER_SYSTEM}
    raise UsageError("no registered VSCore agent target was selected", [Diagnostic(
        "UNSUPPORTED_CAPABILITY", "VSCore implementer needs an exact frozen registered backend and backend_version")])


def _proof_text(text: str) -> str:
    matches = re.findall(r"```lean\s*\n(.*?)```", text, re.S)
    return matches[-1] if matches else text


def _vscore_context(pkg: Package, ctx: dict[str, Any]) -> dict[str, Any]:
    """Supply exact accepted packages/reference and supervisor-owned language limits."""
    from . import schemas
    from .backends import admission, registry
    components = _vscore_components(ctx["parameters"])
    vscore_source, vscore_target = components["source"], components["target"]

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
            "source_grammar": canonical.load_file(schemas.schema_dir() / (components["source_schema"] + ".schema.json")),
            "relation_format": canonical.load_file(schemas.schema_dir() / (components["relation_schema"] + ".schema.json")),
            "relation_helper_slots": {"source_slot": components["checker"].SLOTS["source"],
                                      "proof_slot": components["checker"].SLOTS["proof"],
                                      "binding_order": "sorted unique accepted symbols; unique source entries"},
            "feature_limits": {"source_bytes": vscore_source.MAX_SOURCE_BYTES, "proof_bytes": vscore_target.MAX_PROOF_BYTES,
                               "bindings": vscore_target.MAX_BINDINGS,
                               "excluded_surfaces": (registry.by_id(ctx["parameters"]["backend"], 2) or {}).get(
                                   "excluded_surfaces", registry.VSCORE_EXCLUDED)},
            "accepted_reference": {"path": reference["path"], "sha256": reference["sha256"],
                                   "lean_source": reference_bytes.decode("utf-8")},
            "lean_toolchain": certificate["toolchain"]["pin"]}


def _vscore_failure_record(exc: Exception, source: bytes | None, relation: bytes | None,
                           proof: bytes | None) -> dict:
    """Complete diagnostics bound to the current proposal, including protocol failures."""
    ds = getattr(exc, "diagnostics", None)
    return {"format": "verislop.vscore-agent-diagnostics/1", "passed": False,
            "source_hash": canonical.digest(source) if source is not None else None,
            "relation_hash": canonical.digest(relation) if relation is not None else None,
            "proof_hash": canonical.digest(proof) if proof is not None else None,
            "diagnostics": [d.to_json() for d in ds] if ds else [Diagnostic("INVALID_CANDIDATE", str(exc)).to_json()]}


def _vscore_failure_feedback(record: dict, path: str) -> dict:
    """One bounded excerpt per error; all complete messages live in the bound artifact."""
    rows = []
    for diagnostic in record["diagnostics"]:
        details = diagnostic.get("details", {})
        errors = details.get("errors") or [diagnostic["message"]]
        for error in errors:
            message = str(error)
            rows.append({"number": len(rows) + 1, "code": diagnostic["code"],
                         "module": details.get("module"), "message_excerpt": message[:384],
                         "message_hash": canonical.digest(message.encode()),
                         "omitted_chars": max(0, len(message) - 384)})
    return {"error_count": len(rows), "errors": rows, "message_excerpt_max_chars": 384,
            "compacted": any(row["omitted_chars"] for row in rows),
            "source_hash": record["source_hash"], "relation_hash": record["relation_hash"],
            "proof_hash": record["proof_hash"],
            "response_artifact": record.get("response_artifact"),
            "full_diagnostics": {"path": path, "sha256": canonical.digest_json(record)}}


def _vscore_implementation(broker, conf: dict, pkg: Package, events: EventSink, ctx: dict,
                           attempts: int, proof_attempts: int) -> tuple[dict[str, bytes], dict]:
    """Bounded source/proof search before selection; every source and proof attempt is retained."""
    from . import fsutil, schemas
    components = _vscore_components(ctx["parameters"])
    vscore_checker, vscore_target = components["checker"], components["target"]

    if not 1 <= attempts <= 10 or not 0 <= proof_attempts <= 10:
        raise UsageError("VSCore search budgets require 1..10 source attempts and 0..10 proof attempts")
    fixed = _vscore_context(pkg, ctx)
    implementer = _role(conf, "implementer")
    prover = conf["roles"].get("prover")
    feedback: dict = {}
    fallback: dict[str, bytes] | None = None
    root = pkg.root / "agents" / "vscore-attempts"
    root.mkdir(parents=True, exist_ok=True)
    first = 1
    while (root / f"source-{first}").exists():
        first += 1

    def retain(stage: Path, data: dict[str, bytes]) -> None:
        for name, value in data.items():
            fsutil.write_once(stage / name, value)

    def diagnostics(stage: Path, label: str, exc: Exception, source: bytes | None,
                    relation: bytes | None, proof: bytes | None = None,
                    response_path: Path | None = None) -> dict:
        record = _vscore_failure_record(exc, source, relation, proof)
        response_path = response_path or stage / "response.txt"
        record["response_artifact"] = {"path": str(response_path.relative_to(pkg.root)),
                                       "sha256": canonical.digest(response_path.read_bytes())}
        path = stage / f"diagnostics/{label}.json"
        fsutil.write_json(path, record, once=True)
        return _vscore_failure_feedback(record, str(path.relative_to(pkg.root)))

    def checked(stage: Path, source: bytes, relation: bytes, proof: bytes | None, label: str):
        try:
            spec, build, info = vscore_checker.preview(pkg, source, relation, proof=proof)
            fsutil.write_json(stage / f"checks/{label}.json",
                              {"proof_checked": proof is not None, "passed": True,
                               "proposition_hash": info["proposition_hash"], "source_hash": canonical.digest(source),
                               "relation_hash": canonical.digest(relation),
                               "proof_hash": canonical.digest(proof) if proof is not None else None}, once=True)
            return spec, build, info
        except vscore_checker.EdgeFailure as exc:
            fsutil.write_json(stage / f"checks/{label}.json",
                              {"proof_checked": proof is not None, "passed": False,
                               "diagnostics": [d.to_json() for d in exc.diagnostics],
                               "source_hash": canonical.digest(source), "relation_hash": canonical.digest(relation),
                               "proof_hash": canonical.digest(proof) if proof is not None else None}, once=True)
            if any(d.severity == "infrastructure" for d in exc.diagnostics):
                raise InfrastructureError("VSCore preview infrastructure failed", exc.diagnostics) from exc
            raise

    for offset in range(attempts):
        number = first + offset
        stage = root / f"source-{number}"
        user = "FIXED ACCEPTED CONTRACT AND TARGET (data):\n" + json.dumps(fixed, ensure_ascii=False)
        if feedback:
            user += "\nCHECKER ERROR INVENTORY FROM THE PREVIOUS ATTEMPT (excerpts; full artifact referenced):\n" + json.dumps(feedback, ensure_ascii=False)
        comp = recorded_call(broker, pkg, implementer, f"implementer/vscore/{number}", components["implementer_system"], user, "generate")
        events.emit("candidate_proposal", "generate", f"VSCore source proposal (attempt {number})")
        fsutil.write_once(stage / "response.txt", comp.text.encode("utf-8"))
        source, relation = None, None
        try:
            proposed = extract_json(comp.text)
            if not isinstance(proposed, dict) or not {"program", "relation"} <= set(proposed) or set(proposed) - {"program", "relation", "proof_source"}:
                raise ValueError("VSCore proposal must contain only program, relation and optional proof_source")
            if not isinstance(proposed["program"], dict) or not isinstance(proposed["relation"], dict):
                raise ValueError("program and relation must be JSON objects")
            source, relation = canonical.dumps(proposed["program"]), canonical.dumps(proposed["relation"])
            retain(stage, {"program.vscore.json": source, "relation.json": relation})
            issues = schemas.validate(components["source_schema"], proposed["program"])
            if issues:
                raise vscore_checker.EdgeFailure([Diagnostic("INVALID_CANDIDATE",
                    f"{components['source_schema']}: {issue}") for issue in issues])
            vscore_target.load_relation(relation)
            if "proof_source" in proposed and not isinstance(proposed["proof_source"], str):
                raise ValueError("proof_source must be Lean text")
            retain(stage, {"program.vscore.json": source, "relation.json": relation})
            spec, _, info = checked(stage, source, relation, None, "source")
            retain(stage, {"VeriSlopBridgeGoal.lean": spec.text.encode(), "model.json": info["model"], "profile.json": info["profile"]})
        except (ValueError, TypeError, KeyError, vscore_target.BridgeInvalid, vscore_checker.EdgeFailure) as exc:
            feedback = diagnostics(stage, "source", exc, source, relation)
            fsutil.write_json(stage / "source-diagnostics.json", feedback, once=True)
            continue
        proof = proposed.get("proof_source", "import VeriSlopBridgeGoal\nnamespace VeriSlopBridgeProof\ntheorem edge : VeriSlopBridgeGoal.EdgeProp := by sorry\nend VeriSlopBridgeProof\n").encode("utf-8")
        proof_feedback: dict = {}
        last_bounded_proof = proof if len(proof) <= vscore_target.MAX_PROOF_BYTES else b"import VeriSlopBridgeGoal\nnamespace VeriSlopBridgeProof\ntheorem edge : VeriSlopBridgeGoal.EdgeProp := by sorry\nend VeriSlopBridgeProof\n"
        if "proof_source" in proposed:
            retain(stage, {"proofs/initial.lean": proof})
            try:
                if len(proof) > vscore_target.MAX_PROOF_BYTES:
                    raise ValueError("initial proof exceeds the registered proof size budget")
                checked(stage, source, relation, proof, "initial-proof")
                return {"program.vscore.json": source, "relation.json": relation, "Proof.lean": proof}, {}
            except (ValueError, vscore_checker.EdgeFailure) as exc:
                proof_feedback = diagnostics(stage, "initial-proof", exc, source, relation, proof)
        prover_context = {"parameters": fixed["parameters"], "source_hash": canonical.digest(source),
                          "source": proposed["program"], "relation": proposed["relation"],
                          "generated_goal": spec.text, "accepted_reference": fixed["accepted_reference"],
                          "accepted_packages": fixed["accepted_packages"], "accepted_profile": fixed["accepted_profile"],
                          "lean_toolchain": fixed["lean_toolchain"],
                          "verifier_library": {name: data.decode("utf-8") for name, data in vscore_target.library_sources().items()}}
        if fixed["parameters"].get("backend_version") == "0.3" and hasattr(spec, "refinement_symbols"):
            prover_context["refinement_symbols"] = sorted(spec.refinement_symbols)
        if fixed["parameters"].get("backend_version") == "0.3":
            prover_context["proof_support"] = vscore_target.proof_support_catalog()
        prover_context["relation_hash"] = canonical.digest(relation)
        prover_context["goal_hash"] = canonical.digest(spec.text.encode())
        for proof_number in range(1, proof_attempts + 1 if prover else 1):
            prover_context["proof_hash"] = canonical.digest(proof)
            user = "FIXED VSCORE PROOF CONTEXT (data):\n" + json.dumps(prover_context, ensure_ascii=False)
            user += "\nCURRENT CANDIDATE PROOF:\n```lean\n" + proof.decode("utf-8") + "\n```\n"
            if proof_feedback:
                user += "\nCHECKER ERROR INVENTORY (excerpts; full artifact referenced):\n" + json.dumps(proof_feedback, ensure_ascii=False)
            comp = recorded_call(broker, pkg, prover, f"prover/vscore/{number}/{proof_number}", components["prover_system"], user, "generate")
            proof = _proof_text(comp.text).encode("utf-8")
            if len(proof) <= vscore_target.MAX_PROOF_BYTES:
                last_bounded_proof = proof
            response_path = stage / f"responses/proof-{proof_number}.txt"
            retain(stage, {f"proofs/{proof_number}.lean": proof,
                           f"responses/proof-{proof_number}.txt": comp.text.encode("utf-8")})
            events.emit("candidate_proposal", "generate", f"VSCore proof proposal (source {number}, proof {proof_number})")
            try:
                if len(proof) > vscore_target.MAX_PROOF_BYTES:
                    raise ValueError("proof exceeds the registered proof size budget")
                checked(stage, source, relation, proof, f"proof-{proof_number}")
                return {"program.vscore.json": source, "relation.json": relation, "Proof.lean": proof}, {}
            except (ValueError, vscore_checker.EdgeFailure) as exc:
                proof_feedback = diagnostics(stage, f"proof-{proof_number}", exc, source, relation, proof, response_path)
        # A failed proof search leaves a concrete source candidate for IMPLEMENTED/LINKED.
        fallback = {"program.vscore.json": source, "relation.json": relation, "Proof.lean": last_bounded_proof}
        if not proof_feedback:
            proof_feedback = diagnostics(stage, "no-proof", ValueError("no configured prover established the exact refinement theorem"),
                                         source, relation, last_bounded_proof)
        feedback = proof_feedback
        fsutil.write_json(stage / "proof-diagnostics.json", {"diagnostics": feedback, "proof_search_exhausted": True}, once=True)
    if fallback is not None:
        events.emit("progress", "generate", "bounded VSCore proof search exhausted; source candidate remains available for materialization")
        return fallback, {}
    raise UsageError("VSCore implementer produced no well-formed source within its bounded search budget",
                     [Diagnostic("BUDGET_EXHAUSTED", "VSCore source attempts exhausted", details={"diagnostics": feedback})])
