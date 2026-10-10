"""Supervisor-owned, binder-preserving Tier 2 bridge for VSCore 0.3.

The source function is obtained from the intrinsically checked entry, not from a
candidate relation or an independent interpreter. The accepted DSL is denoted
again with those functions, including beneath all binders. Raw representation
laws and the exact evaluator equation are part of the edge proposition.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import canonical, source_contract
from ..dsl import DSLError, Profile, type_formula
from ..exprjson import Expr, app, bvar, const, lam, name_str, parse_name, pi
from ..reify import _Denoter
from . import vscore_target as old
from . import vscore3_source as src

TEMPLATE = "vscore.reference_refinement/0.3"
LANGUAGE = "vscore/0.3"
SEMANTICS = "vscore-semantics/0.3"
RELATION_FORMAT = "verislop.vscore-relation/0.3"
MODEL_FORMAT = "verislop.vscore-model/0.3"
PROFILE_FORMAT = "verislop.vscore-profile/0.3"
IR_FORMAT = "verislop.vscore-implementation-ir/0.3"
PROPOSITION_FORMAT = "verislop.vscore-proposition/0.3"
ENDPOINT = old.ENDPOINT
SOURCE_ROLE, PROOF_ROLE = old.SOURCE_ROLE, old.PROOF_ROLE
MAX_SOURCE_BYTES, MAX_PROOF_BYTES, MAX_BINDINGS = old.MAX_SOURCE_BYTES, old.MAX_PROOF_BYTES, old.MAX_BINDINGS
CONTRACT_MODULE, GOAL_MODULE, PROOF_MODULE = old.CONTRACT_MODULE, old.GOAL_MODULE, old.PROOF_MODULE
EDGE_THEOREM, EDGE_PROP = old.EDGE_THEOREM, old.EDGE_PROP
LIB_ROOT = old.LIB_ROOT
LIB_MODULES = ("VSCore.Syntax", "VSCore.Decode", "VSCore3.Syntax", "VSCore3.Equality",
               "VSCore3.Decode", "VSCore3.Typed", "VSCore3.Typing", "VSCore3.Semantics",
               "VSCore3.Proofs", "VSCore3.Transport", "VSCore3.SourceFacts", "VSCore3")
BridgeInvalid, BridgeUnsupported = old.BridgeInvalid, old.BridgeUnsupported
Printer, same_expr, lean_name, lean_component = old.Printer, old.same_expr, old.lean_name, old.lean_component
gname, gconst, module_path = old.gname, old.gconst, old.module_path
decl_index = old.decl_index


def library_sources() -> dict[str, bytes]:
    return {m: (LIB_ROOT / module_path(m)).read_bytes() for m in LIB_MODULES}


def proof_support_catalog() -> dict:
    """Closed universal lemma signatures, independently elaborated in generic tests."""
    signatures = {
        "apply_ite": "∀ {α : Sort u} {β : Sort v} (f : α → β) (p : Prop) [Decidable p] (x y : α), "
                     "f (if p then x else y) = if p then f x else f y",
        "apply_bool_ite": "∀ {α : Sort u} {β : Sort v} (f : α → β) (b : Bool) (x y : α), "
                          "f (if b then x else y) = if b then f x else f y",
        "ite_decide": "∀ {α : Sort u} (p : Prop) [Decidable p] (x y : α), "
                      "(if decide p then x else y) = if p then x else y",
        "map_identity": "∀ {α : Type u} (xs : List α), xs.map (fun x => x) = xs",
        "int_ofNat_eq_cast": "∀ (n : Nat), Int.ofNat n = (n : Int)",
        "int_ofNat_add": "∀ (m n : Nat), Int.ofNat (m + n) = Int.ofNat m + Int.ofNat n",
    }
    return {"module": "VSCore3.Transport", "source_hash": canonical.digest((LIB_ROOT / module_path("VSCore3.Transport")).read_bytes()),
            "universes": ["u", "v"], "global_simp_rules": False,
            "lemmas": [{"name": "VSCore3.ProofSupport." + name, "signature": signature}
                       for name, signature in signatures.items()]}


def load_relation(data: bytes) -> dict:
    try:
        rel = canonical.loads(data)
    except Exception as exc:
        raise BridgeInvalid(f"noncanonical relation: {exc}") from None
    keys = {"schema_version", "format", "template", "source_slot", "proof_slot", "bindings"}
    if not isinstance(rel, dict) or set(rel) != keys or rel["schema_version"] != "0.3" or \
            rel["format"] != RELATION_FORMAT or rel["template"] != TEMPLATE:
        raise BridgeInvalid("not an exact VSCore 0.3 relation descriptor")
    if any(not isinstance(rel[k], str) or not rel[k] for k in ("source_slot", "proof_slot")):
        raise BridgeInvalid("relation artifact slots must be nonempty strings")
    bindings = rel["bindings"]
    if not isinstance(bindings, list) or not 1 <= len(bindings) <= MAX_BINDINGS or any(
        not isinstance(b, dict) or set(b) != {"symbol", "entry"} or any(
            not isinstance(b[k], str) or not b[k] for k in ("symbol", "entry")) for b in bindings
    ):
        raise BridgeInvalid("invalid relation bindings")
    syms, entries = ([b[k] for b in bindings] for k in ("symbol", "entry"))
    if syms != sorted(set(syms)) or len(entries) != len(set(entries)):
        raise BridgeInvalid("bindings must be sorted and one-to-one", "AMBIGUOUS_CORRESPONDENCE")
    return rel


def model_descriptor(pin: str) -> dict:
    return {"schema_version": "0.3", "format": MODEL_FORMAT, "language": LANGUAGE, "semantics": SEMANTICS,
            "lean_toolchain": pin,
            "library": [{"module": m, "sha256": canonical.digest(b)} for m, b in library_sources().items()],
            "evaluation": "intrinsically typed total pure Lean functions; unbounded Nat/Int, Int.fdiv, "
                          "Unicode scalar String, immutable algebraic data; admission budgets are not runtime fuel"}


def profile_descriptor(accepted_profile: dict, accepted_profile_hash: str) -> dict:
    # Retain the complete accepted inventories, including constructor/projection
    # hashes. Shape is never inferred from a candidate's purported type registry.
    return {"schema_version": "0.3", "format": PROFILE_FORMAT, "language": LANGUAGE,
            "accepted_profile": accepted_profile["profile_id"], "accepted_profile_hash": accepted_profile_hash,
            "enums": accepted_profile.get("enums", {}), "records": accepted_profile.get("records", {}),
            "symbols": accepted_profile.get("symbols", {}),
            "representation": "exact nominal IDs and ordered canonical product layouts; typed inverse and "
                              "decode-after-encode laws; no bounds or input-domain narrowing"}


def sort_ty(sort: Any) -> Any:
    if isinstance(sort, str) and sort in {"Nat", "Int", "Bool", "String", "Unit"}:
        return sort.lower()
    if isinstance(sort, dict) and len(sort) == 1:
        tag = next(iter(sort))
        if tag in {"list", "option"}:
            return (tag, sort_ty(sort[tag]))
        if tag in {"record", "enum"}:
            return (tag, sort[tag])
        if tag == "result":
            return ("result", sort_ty(sort[tag]["error"]), sort_ty(sort[tag]["ok"]))
    raise BridgeUnsupported(f"unsupported accepted carrier {sort!r}")


def _product(items: list[str]) -> str:
    tail = ".unit"
    for item in reversed(items):
        tail = f"(.product {item} {tail})"
    return tail


def shape(sort: Any, profile: Profile) -> str:
    if isinstance(sort, str):
        sort_ty(sort)
        return "." + sort.lower()
    tag = next(iter(sort))
    if tag in {"list", "option"}:
        return f"(.{tag} {shape(sort[tag], profile)})"
    if tag == "result":
        return f"(.result {shape(sort[tag]['error'], profile)} {shape(sort[tag]['ok'], profile)})"
    if tag == "record":
        r = profile.records[sort[tag]]
        names = "[" + ", ".join(src.lean_string(f["name"]) for f in r["fields"]) + "]"
        payload = _product([shape(f["sort"], profile) for f in r["fields"]])
        return f"(.record {src.lean_string(sort[tag])} {names} {payload})"
    if tag == "enum":
        names = "[" + ", ".join(src.lean_string(c) for c in profile.enums[sort[tag]]["constructors"]) + "]"
        return f"(.enum {src.lean_string(sort[tag])} {names})"
    raise BridgeUnsupported(f"unsupported shape {sort!r}")


@dataclass
class AdapterSpec:
    name: str
    sort: Any
    ty: Any
    lean_type: Expr
    shape: str
    definition: str


SymbolSpec = old.SymbolSpec


@dataclass
class ObligationSpec:
    oid: str
    lean_symbol: str
    formula: dict | None
    statement_hash: str
    symbols: list[str]
    source_facets: list[dict] = field(default_factory=list)


@dataclass
class GoalSpec:
    source_bytes: bytes
    program: dict
    signatures: list[dict]
    enums: list
    adapters: list[AdapterSpec]
    symbols: list[SymbolSpec]
    obligations: list[ObligationSpec]
    profile: Profile
    expected: dict[str, dict[str, Expr]] = field(default_factory=dict)
    text: str = ""
    base_text: str = ""
    readable_selection: bytes | None = None
    readable_view: Any = None
    readable_correspondence: bytes = b""

    @property
    def refinement_symbols(self) -> set[str]:
        value_symbols = set().union(*(_formula_symbols(o.formula) for o in self.obligations))
        source_symbols = {r["symbol"] for o in self.obligations for r in o.source_facets}
        # A source-only requirement constrains operational behavior, not an
        # otherwise unconstrained endpoint's mathematical reference body.
        return {s.symbol for s in self.symbols} - (source_symbols - value_symbols)


class _Adapters:
    def __init__(self, profile: Profile):
        self.profile = profile
        self.order: list[AdapterSpec] = []
        self.cache: dict[bytes, AdapterSpec] = {}
        self.denoter = _Denoter(profile)

    def get(self, sort: Any) -> AdapterSpec:
        key = canonical.dumps({"sort": sort})
        if key in self.cache:
            return self.cache[key]
        if isinstance(sort, str):
            body = "VSCore3." + sort.lower() + "Adapter"
        elif "list" in sort or "option" in sort:
            tag = next(iter(sort))
            elem = self.get(sort[tag])
            body = f"VSCore3.{tag}Adapter {elem.name}"
        elif "result" in sort:
            err, ok = (self.get(sort["result"][k]) for k in ("error", "ok"))
            body = f"VSCore3.resultAdapter {err.name} {ok.name}"
        elif "enum" in sort:
            enum = self.profile.enums[sort["enum"]]
            names, ctors = enum["constructors"], enum["lean_constructors"]
            if not names or len(names) != len(ctors):
                raise BridgeInvalid("accepted enumeration has no exact constructor inventory", "STATEMENT_MISMATCH")
            cases = " ".join("| " + lean_name(parse_name(c)) + " => ⟨" + src.lean_string(n) +
                             ", by decide +kernel⟩" for n, c in zip(names, ctors))
            inv = "@" + lean_name(parse_name(ctors[-1]))
            for n, c in reversed(list(zip(names[:-1], ctors[:-1]))):
                inv = "if x.val = " + src.lean_string(n) + " then @" + lean_name(parse_name(c)) + " else " + inv
            body = ("{ to := fun x => match x with " + cases + "\n"
                    "    inv := fun x => " + inv + "\n"
                    "    from_to := by intro x; cases x <;> rfl\n"
                    "    to_from := by intro x; rcases x with ⟨x, h⟩; "
                    "simp only [List.mem_cons, List.not_mem_nil, or_false] at h; "
                    "rcases h with " + " | ".join("rfl" for _ in names) + "; all_goals rfl }")
        elif "record" in sort:
            r = self.profile.records[sort["record"]]
            fields = [(f, self.get(f["sort"])) for f in r["fields"]]
            to = "()"
            for f, a in reversed(fields):
                projection = f.get("lean_projection", f.get("projection"))
                if not isinstance(projection, str):
                    raise BridgeInvalid("accepted record lacks a projection name", "STATEMENT_MISMATCH")
                to = f"({a.name}.to (@{lean_name(parse_name(projection))} x), {to})"
            ctor = r.get("lean_constructor", r.get("constructor"))
            if not isinstance(ctor, str):
                raise BridgeInvalid("accepted record lacks its constructor", "STATEMENT_MISMATCH")
            args = []
            for i, (_, a) in enumerate(fields):
                args.append(f"({a.name}.inv (x{'.2' * i}.1))")
            component = ", ".join(a.name + ".from_to" for _, a in fields)
            inverse = ", ".join(a.name + ".to_from" for _, a in fields)
            body = ("{ to := fun x => " + to + "\n"
                    "    inv := fun x => @" + lean_name(parse_name(ctor)) + " " + " ".join(args) + "\n"
                    "    from_to := by intro x; cases x; simp [" + component + "]\n"
                    "    to_from := by intro x; " + " ".join("rcases x with ⟨x" + str(i) + ", x⟩;" for i in range(len(fields))) +
                    " cases x; simp [" + inverse + "] }")
        else:
            raise BridgeUnsupported("0.3 has no adapter for the accepted sort " + repr(sort))
        item = AdapterSpec(f"adapter_{len(self.order)}", sort, sort_ty(sort), self.denoter.sort(sort),
                           shape(sort, self.profile), body)
        self.order.append(item)
        self.cache[key] = item
        return item


class _SourceDenoter(_Denoter):
    """Only function interpretation changes; normal denotation handles all binders."""
    def __init__(self, profile: Profile, symbols: dict[str, SymbolSpec]):
        super().__init__(profile)
        self.symbols = symbols

    def term(self, term: dict, ctx: list[tuple]) -> tuple[Expr, Any]:
        if term.get("tag") == "call" and term["symbol"] in self.symbols:
            s = self.symbols[term["symbol"]]
            return app(gconst("source_fn_" + s.symbol), *(self.term(a, ctx)[0] for a in term["args"])), s.result_sort
        return super().term(term, ctx)


def transfer_expr(formula: dict, profile: Profile, symbols: dict[str, SymbolSpec]) -> Expr:
    return _SourceDenoter(profile, symbols).formula(formula, [])


def _endpoint_type(symbol: SymbolSpec, denoter: _Denoter) -> Expr:
    out = denoter.sort(symbol.result_sort)
    for sort in reversed(symbol.arg_sorts):
        out = pi("x", denoter.sort(sort), out)
    return out


def _source_transfer(row: dict, denoter: _Denoter, symbols: dict[str, SymbolSpec]) -> Expr:
    requirements = app(const(source_contract.NS + ".SourceDefinition.requirements"),
                       _endpoint_type(symbols[row["symbol"]], denoter), const(row["definition"]))
    return app(const(source_contract.NS + ".HoldsBoundary"), requirements,
               gconst("sourceFacts_" + row["symbol"]))


def _obligation_transfer(ob: ObligationSpec, profile: Profile, symbols: dict[str, SymbolSpec]) -> Expr:
    parts = ([transfer_expr(ob.formula, profile, symbols)] if ob.formula is not None else [])
    parts += [_source_transfer(row, _Denoter(profile), symbols) for row in ob.source_facets]
    return old.and_chain(parts)


def _refines(symbol: SymbolSpec, denoter: _Denoter) -> Expr:
    args = [bvar(symbol.arity - i - 1) for i in range(symbol.arity)]
    out = old.eq_expr(denoter.sort(symbol.result_sort), app(gconst("source_fn_" + symbol.symbol), *args),
                      app(const(symbol.lean_decl), *args))
    for sort in reversed(symbol.arg_sorts):
        out = pi("x", denoter.sort(sort), out)
    return out


def _edge(spec: GoalSpec) -> Expr:
    # Each supervisor theorem is named as a proposition; its exact definition is
    # frozen in the derived module and proposition dependency closure.
    props = [gconst("SourceParses"), gconst("SourceChecks")]
    for s in spec.symbols:
        props += [gconst("InputsCover_" + s.symbol), gconst("RawEval_" + s.symbol)]
        if s.symbol in spec.refinement_symbols:
            props.append(gconst("Refines_" + s.symbol))
        if any(row["symbol"] == s.symbol for ob in spec.obligations for row in ob.source_facets):
            props.append(gconst("SourceAdequate_" + s.symbol))
    props += [gconst("Transfer_" + ob.oid) for ob in spec.obligations]
    return old.and_chain(props)


def build_goal(source: bytes, relation: dict, accepted_profile: dict, obligations: dict[str, dict]) -> GoalSpec:
    if len(source) > MAX_SOURCE_BYTES:
        raise BridgeUnsupported("source exceeds frozen bridge admission budget")
    try:
        profile = Profile.from_json(accepted_profile)
        program = src.parse_source(source)
        signatures = src.check_program({k: e["constructors"] for k, e in profile.enums.items()}, program)
    except (DSLError, src.SourceError, KeyError, TypeError) as exc:
        raise BridgeInvalid(f"source/profile rejected: {exc}") from None
    entries = {e["id"]: e for e in program["entries"]}
    if {b["entry"] for b in relation["bindings"]} != set(entries):
        raise BridgeInvalid("every entry must have exactly one accepted binding", "UNMAPPED_IMPLEMENTATION_OBJECT")
    declarations = {d["id"]: d for d in program["declarations"]}
    adapters, symbols = _Adapters(profile), []
    for b in relation["bindings"]:
        decl = profile.symbols.get(b["symbol"])
        if decl is None or decl.get("level_params"):
            raise BridgeUnsupported("binding requires an accepted monomorphic function")
        entry = entries[b["entry"]]
        if entry["params"] != [sort_ty(s) for s in decl["args"]] or entry["result"] != sort_ty(decl["result"]):
            raise BridgeInvalid("entry signature differs from accepted function", "STATEMENT_MISMATCH")
        aa, ra = [adapters.get(s).name for s in decl["args"]], adapters.get(decl["result"]).name
        symbols.append(SymbolSpec(b["symbol"], b["entry"], decl["lean_decl"], decl["args"], decl["result"], aa, ra))
    for a in adapters.order:
        if isinstance(a.sort, dict) and "record" in a.sort:
            rid = a.sort["record"]
            want = [(f["name"], sort_ty(f["sort"])) for f in profile.records[rid]["fields"]]
            got = declarations.get(rid)
            if got is None or got.get("tag") != "record" or got.get("fields") != want:
                raise BridgeInvalid(f"record {rid} differs from exact accepted nominal layout", "STATEMENT_MISMATCH")
    by_symbol, obs = {s.symbol: s for s in symbols}, []
    for oid, rec in sorted(obligations.items()):
        formula, facets = rec.get("formula"), rec.get("source_facets", [])
        if formula is not None:
            try:
                type_formula(formula, [], profile)
            except DSLError as exc:
                raise BridgeInvalid(f"{oid}: {exc}", "STATEMENT_MISMATCH") from None
        used: set[str] = set()
        stack = [formula]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if x.get("tag") == "call":
                    used.add(x["symbol"])
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)
        if used - by_symbol.keys():
            raise BridgeInvalid(f"{oid}: unbound function", "UNMAPPED_IMPLEMENTATION_OBJECT")
        for row in facets:
            if row.get("symbol") not in by_symbol:
                raise BridgeInvalid(f"{oid}: unbound source endpoint", "UNMAPPED_IMPLEMENTATION_OBJECT")
            sym = by_symbol[row["symbol"]]
            if row.get("lean_decl") != sym.lean_decl or row.get("model_version") != source_contract.MODEL_VERSION or \
                    row.get("model_source_hash") != source_contract.model_source_hash():
                raise BridgeInvalid(f"{oid}: source facet endpoint/model differs from the accepted contract", "STATEMENT_MISMATCH")
            try:
                source_contract.validate_requirements(row["requirements"], arity=sym.arity)
            except (source_contract.SourceError, KeyError) as exc:
                raise BridgeInvalid(f"{oid}: invalid source requirements: {exc}", "STATEMENT_MISMATCH") from None
            for requirement in row["requirements"]:
                if requirement["tag"] == "entry" and requirement["entry"] != sym.entry:
                    raise BridgeInvalid(f"{oid}: source entry differs from its exact binding", "STATEMENT_MISMATCH")
            used.add(sym.symbol)
        if not used:
            raise BridgeUnsupported(f"{oid}: no implementation symbol")
        obs.append(ObligationSpec(oid, rec["lean_symbol"], formula, rec["statement_hash"], sorted(used), facets))
    if not obs:
        raise BridgeInvalid("edge covers no accepted obligations", "ORPHAN_CLAIM")
    enums = [(eid, list(e["constructors"]), e["lean_decl"], list(e["lean_constructors"])) for eid, e in sorted(profile.enums.items())]
    spec = GoalSpec(source, program, signatures, enums, adapters.order, symbols, obs, profile)
    denoter = _Denoter(profile)
    for s in symbols:
        spec.expected["Refines_" + s.symbol] = {"type": {"sort": 0}, "value": _refines(s, denoter)}
        if any(row["symbol"] == s.symbol for ob in obs for row in ob.source_facets):
            spec.expected["SourceAdequate_" + s.symbol] = {"type": {"sort": 0}, "value": app(
                const("VSCore3.SourceFactsAdequate"), gconst("profile"), gconst("rawProgram"),
                {"lit": {"str": s.entry}}, gconst("checkedProgram"), gconst("entry_" + s.symbol))}
    for ob in obs:
        spec.expected["Transfer_" + ob.oid] = {"type": {"sort": 0}, "value": _obligation_transfer(ob, profile, by_symbol)}
    spec.expected["EdgeProp"] = {"type": {"sort": 0}, "value": _edge(spec)}
    spec.text = render_goal(spec)
    spec.base_text = spec.text
    return spec


def statement_mismatches(spec: GoalSpec, decls: dict[str, dict]) -> list[str]:
    bad = []
    for component, want in sorted(spec.expected.items()):
        name = name_str(gname(component))
        got = decls.get(name)
        if (got is None or got.get("kind") != want.get("kind", "definition") or got.get("level_params")
                or not same_expr(got.get("type", {}), want["type"])
                or ("value" in want and not same_expr(got.get("value", {}), want["value"]))):
            bad.append(name)
    return bad


def proposition_hash(decls: dict[str, dict], pin: str) -> tuple[str, dict[str, str]]:
    from ..exprjson import closure, decl_hash
    if EDGE_PROP not in decls:
        raise BridgeInvalid("no replayed edge proposition", "STATEMENT_MISMATCH")
    hashes = {n: decl_hash(decls[n]) for n in sorted(closure({EDGE_PROP}, decls))}
    return canonical.digest_json({"format": PROPOSITION_FORMAT, "lean_toolchain": pin,
                                  "proposition": old._strip_names(const(EDGE_PROP)), "closure": hashes}), hashes


def reexport(spec: GoalSpec, decls: dict[str, dict]) -> dict:
    from .vscore3_check import _Reify
    r = _Reify()
    source = bytes(r.list((old._value(decls, "sourceBytes"), None), const("Nat"), r.nat))
    program = r.program((old._value(decls, "rawProgram"), None))
    sigs = r.list((old._value(decls, "signatures"), None), const("VSCore3.EntrySig"), r.signature)
    registry = r.profile((old._value(decls, "profile"), None))
    if source != spec.source_bytes or program != spec.program or sigs != spec.signatures or \
            registry != [[eid, cs] for eid, cs, _, _ in spec.enums]:
        raise BridgeInvalid("replayed artifact differs from frozen source/profile", "IR_REIFICATION_MISMATCH")
    return {"program": src.program_json(program), "signatures": [
        {"id": s["id"], "params": [src.ty_json(t) for t in s["params"]], "result": src.ty_json(s["result"])} for s in sigs],
        "enums": [{"id": eid, "constructors": cs} for eid, cs in registry],
        "bindings": [{"symbol": s.symbol, "entry": s.entry, "lean_decl": s.lean_decl,
                      "args": s.arg_sorts, "result": s.result_sort} for s in spec.symbols]}


def render_goal(spec: GoalSpec) -> str:
    """Render exact source, intrinsic entries, adapters and universal transfer.

    Implemented separately below the derivation so generated statements are easy
    to inspect and cannot be supplied by proof authors.
    """
    return _render_goal(spec)


def _render_goal(spec: GoalSpec) -> str:
    p, denoter = Printer(), _Denoter(spec.profile)
    adapters = {a.name: a for a in spec.adapters}
    out = ["import VSCore3"]
    if any(ob.source_facets for ob in spec.obligations):
        out.append("import VSCore3.SourceFacts")
    out += ["import VeriSlopContract", "",
           "set_option maxRecDepth 100000", "set_option maxHeartbeats 20000000", "",
           "namespace " + GOAL_MODULE, "",
           old._doc(f"Supervisor goal {TEMPLATE}; exact delivered bytes {canonical.digest(spec.source_bytes)}."),
           "def sourceBytes : List Nat := [" + ", ".join(map(str, spec.source_bytes)) + "]",
           "def rawProgram : VSCore3.Program := " + src.lean_program(spec.program),
           "def profile : VSCore3.Profile := { enums := [" + ", ".join(
               "(" + src.lean_string(eid) + ", [" + ", ".join(src.lean_string(c) for c in cs) + "])"
               for eid, cs, _, _ in spec.enums) + "] }",
           "def signatures : List VSCore3.EntrySig := " + src.lean_signatures(spec.signatures),
           "def SourceParses : Prop := VSCore3.parseSource sourceBytes = .ok rawProgram",
           "theorem source_parses : SourceParses := by rfl",
           "def SourceChecks : Prop := VSCore3.checkProgram profile rawProgram = .ok signatures",
           "theorem source_checks : SourceChecks := VSCore3.checkProgram_of_check (by decide +kernel)",
           "def checkedProgram : VSCore3.CheckedProgram := (VSCore3.compileProgram profile rawProgram).toOption.getD",
           "  { declarations := [], helpers := [], entries := [], signatures := [] }",
           "theorem compiled_ok : VSCore3.compileProgram profile rawProgram = .ok checkedProgram := by with_unfolding_all rfl", ""]
    for a in spec.adapters:
        out += [old._doc("Exact accepted carrier " + canonical.dumps(a.sort).decode() + "."),
                f"def {a.name} : VSCore3.Adapter {a.shape} {p.term(a.lean_type)} :=",
                "  " + a.definition,
                f"def {a.name}_raw : VSCore3.RawLaws {a.shape} := {_raw_laws(a.sort, spec.profile)}",
                f"theorem {a.name}_decode_encode (x : {p.term(a.lean_type)}) :",
                f"    VSCore3.decode {a.shape} ({a.name}.encode x) = some ({a.name}.to x) :=",
                f"  {a.name}.decode_encode {a.name}_raw x", ""]
    for s in spec.symbols:
        symbol, entry = lean_component(s.symbol), src.lean_string(s.entry)
        sourcefn, ref = lean_component("source_fn_" + s.symbol), lean_component("Refines_" + s.symbol)
        ename = lean_component("entry_" + s.symbol)
        xs = [f"x__{i}" for i in range(s.arity)]
        arg_binders = " ".join(f"({x} : {p.term(denoter.sort(sort))})" for x, sort in zip(xs, s.arg_sorts))
        env = "()"
        for x, a in reversed(list(zip(xs, s.arg_adapters))):
            env = f"({a}.to {x}, {env})"
        enc_args = "[" + ", ".join(f"{a}.encode {x}" for a, x in zip(s.arg_adapters, xs)) + "]"
        shapes = "[" + ", ".join(adapters[a].shape for a in s.arg_adapters) + "]"
        result_shape = adapters[s.result_adapter].shape
        # Repackage the exact found entry with explicit canonical signature fields.
        # The proof below checks equality to the admitted function; the shell lets
        # later elaboration use the signature without reducing the whole checker.
        out += [f"abbrev {ename} : VSCore3.CompiledFunction :=",
                f"  {{ id := {entry}, params := {shapes}, result := {result_shape},",
                f"    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram {entry}).getD",
                "      { id := \"_missing\", params := [], result := .unit, run := fun _ => () }).run }",
                f"theorem find_{symbol} : VSCore3.findEntry checkedProgram {entry} = some {ename} := by with_unfolding_all rfl",
                f"def {sourcefn} {arg_binders} : {p.term(denoter.sort(s.result_sort))} := by",
                f"  with_unfolding_all exact {s.result_adapter}.inv ({ename}.run {env})",
                f"def {ref} : Prop := {p.term(spec.expected['Refines_' + s.symbol]['value'])}",
                f"def RawEval_{symbol} : Prop := " + (f"∀ {arg_binders}," if xs else ""),
                f"  VSCore3.evalEntry profile rawProgram {entry} {enc_args} =",
                f"    .ok ({s.result_adapter}.encode ({sourcefn} {' '.join(xs)}))",
                f"theorem raw_eval_{symbol} : RawEval_{symbol} := by"]
        if xs:
            out.append("  intro " + " ".join(xs))
        out += [f"  have hd : VSCore3.decodeEnv {ename}.params {enc_args} = some {env} := by",
                f"    change VSCore3.decodeEnv {shapes} {enc_args} = some {env}",
                "    simp only [VSCore3.decodeEnv, " + ", ".join(a + "_decode_encode" for a in s.arg_adapters) +
                (", " if s.arg_adapters else "") + "bind, Option.bind, pure]",
                f"  change VSCore3.evalEntry profile rawProgram {entry} {enc_args} = _",
                f"  simp only [VSCore3.evalEntry, compiled_ok, find_{symbol}, VSCore3.evalCheckedEntry, hd]",
                f"  simp only [{sourcefn}, VSCore3.Adapter.encode]",
                f"  change Except.ok (VSCore3.encode {result_shape} ({ename}.run {env})) =",
                f"    Except.ok (VSCore3.encode {result_shape} ({s.result_adapter}.to ({s.result_adapter}.inv ({ename}.run {env}))))",
                f"  rw [{s.result_adapter}.to_from]",
                f"def InputsCover_{symbol} : Prop := ∀ args, VSCore3.ArgsTyped {ename} args → " +
                ("∃ " + " ".join(f"({x} : {p.term(denoter.sort(sort))})" for x, sort in zip(xs, s.arg_sorts)) + ", " if xs else "") +
                f"args = {enc_args}",
                f"theorem inputs_cover_{symbol} : InputsCover_{symbol} := by",
                "  intro args h",
                "  obtain ⟨env, hd⟩ := h",
                f"  change VSCore3.decodeEnv {shapes} args = some env at hd",
                "  have he := VSCore3.encodeEnv_decodeEnv " + shapes + " " + _param_laws(s.arg_sorts, spec.profile) + " args env hd"]
        for i in range(s.arity):
            out.append(f"  rcases env with ⟨v__{i}, env⟩")
        out.append("  cases env")
        actuals = [f"{a}.inv v__{i}" for i, a in enumerate(s.arg_adapters)]
        if xs:
            out.append("  refine ⟨" + ", ".join(actuals) + ", ?_⟩")
        out += ["  simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode" +
                "".join(", " + a + ".to_from" for a in s.arg_adapters) + "] using he.symm", ""]
        if any(row["symbol"] == s.symbol for ob in spec.obligations for row in ob.source_facets):
            out += _render_source_facts(s, spec.profile, adapters)
    for ob in spec.obligations:
        tr = lean_component("Transfer_" + ob.oid)
        hyps = " ".join(f"(h_{lean_component(s)} : {lean_component('Refines_' + s)})" for s in sorted(_formula_symbols(ob.formula)))
        out += [old._doc(f"Accepted obligation {ob.oid}, theorem {ob.lean_symbol}, hash {ob.statement_hash}."),
                f"def {tr} : Prop := {p.term(spec.expected['Transfer_' + ob.oid]['value'])}",
                f"theorem {lean_component('transfer_' + ob.oid)} {hyps} : {tr} := by"]
        if ob.source_facets:
            out.append(f"  have haccepted := @{lean_name(parse_name(ob.lean_symbol))}")
        value_symbols = _formula_symbols(ob.formula)
        for s in sorted(value_symbols):
            sym = next(x for x in spec.symbols if x.symbol == s)
            sourcefn = lean_component("source_fn_" + s)
            eqname = lean_component("eq_" + s)
            out.append(f"  have {eqname} : {sourcefn} = @{lean_name(parse_name(sym.lean_decl))} := by")
            if sym.arity:
                out.append("    " + "; ".join("apply funext; intro x__" + str(i) for i in range(sym.arity)))
                out.append("    exact h_" + lean_component(s) + " " + " ".join("x__" + str(i) for i in range(sym.arity)))
            else:
                out.append("    exact h_" + lean_component(s))
        components = []
        if ob.formula is not None:
            reference = p.term(denoter.formula(ob.formula, []))
            source_value = p.term(transfer_expr(ob.formula, spec.profile, {s.symbol: s for s in spec.symbols}))
            out += [f"  have htransfer : ({source_value}) = ({reference}) := by"]
            out.append("    rw [" + ", ".join(lean_component("eq_" + s) for s in sorted(value_symbols)) + "]"
                       if value_symbols else "    rfl")
            proof = "haccepted.1" if ob.source_facets else "@" + lean_name(parse_name(ob.lean_symbol))
            out += [f"  have hvalue : ({source_value}) := htransfer.symm ▸ ({proof})"]
            components.append("hvalue")
        for i, row in enumerate(ob.source_facets):
            proof = "haccepted" + (".2" if ob.formula is not None else "") + ".2" * i
            if i < len(ob.source_facets) - 1:
                proof += ".1"
            source_prop = p.term(_source_transfer(row, denoter, {s.symbol: s for s in spec.symbols}))
            out += [f"  have hsource_{i} : ({source_prop}) := by",
                    f"    apply ({proof}).1 sourceFacts_{lean_component(row['symbol'])}",
                    "    with_unfolding_all rfl"]
            components.append("hsource_" + str(i))
        out += ["  exact " + (components[0] if len(components) == 1 else "⟨" + ", ".join(components) + "⟩"), ""]
    refines = " ".join(f"(h_{lean_component(s.symbol)} : {lean_component('Refines_' + s.symbol)})" for s in spec.symbols
                       if s.symbol in spec.refinement_symbols)
    parts = ["source_parses", "source_checks"]
    for s in spec.symbols:
        parts += ["inputs_cover_" + lean_component(s.symbol), "raw_eval_" + lean_component(s.symbol)]
        if s.symbol in spec.refinement_symbols:
            parts.append("h_" + lean_component(s.symbol))
        if any(row["symbol"] == s.symbol for ob in spec.obligations for row in ob.source_facets):
            parts.append("source_adequate_" + lean_component(s.symbol))
    for ob in spec.obligations:
        parts.append(lean_component("transfer_" + ob.oid) + " " + " ".join("h_" + lean_component(s) for s in sorted(_formula_symbols(ob.formula))))
    out += ["def EdgeProp : Prop := " + p.term(spec.expected["EdgeProp"]["value"]),
            f"theorem edge_of_refines {refines} : EdgeProp :=", "  ⟨" + ", ".join(parts) + "⟩",
            "", "end " + GOAL_MODULE, ""]
    # Compiler-produced runs contain checked dependent casts. Give the supervisor
    # equations the same full transparency used by the admission proof; no host
    # evaluation or axioms enter the generated proof terms.
    rendered, full_transparency = [], False
    for line in out:
        if line.startswith("theorem raw_eval_") or line.startswith("theorem inputs_cover_"):
            rendered.extend((line, "  with_unfolding_all"))
            full_transparency = True
            continue
        if full_transparency and line and not line.startswith(" "):
            full_transparency = False
        rendered.append("  " + line if full_transparency and line else line)
    return "\n".join(rendered)


def _formula_symbols(formula: dict | None) -> set[str]:
    result, stack = set(), [formula]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("tag") == "call":
                result.add(node["symbol"])
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return result


def enrich_readable(spec: GoalSpec) -> GoalSpec:
    """Append an untrusted source-only proposal; run_build must kernel-check it."""
    import copy
    from . import vscore3_readable as R
    result = copy.deepcopy(spec)
    result.base_text = spec.base_text or spec.text
    view = R.render(spec.source_bytes, {eid: cs for eid, cs, _, _ in spec.enums}, spec.program)
    out = ["namespace " + GOAL_MODULE + ".Readable"]
    for row in view.functions:
        n = row["name"]
        rn = R.NAMESPACE + "." + n
        lookup = (f"checkedProgram.helpers.find? (fun h => h.id == {src.lean_string(row['source_id'])})"
                  if row["role"] == "helper" else f"VSCore3.findEntry checkedProgram {src.lean_string(row['source_id'])}")
        out += [f"abbrev {n}_compiled : VSCore3.CompiledFunction :=",
                f"  {{ id := {src.lean_string(row['source_id'])}, params := {rn}_params, result := {rn}_result,",
                f"    run := by with_unfolding_all exact (({lookup}).getD",
                '      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }',
                f"theorem lookup_{n} : ({lookup}) = some {n}_compiled := by with_unfolding_all rfl",
                f"theorem signature_{n} : {n}_compiled.params = {rn}_params ∧ {n}_compiled.result = {rn}_result := by exact ⟨rfl, rfl⟩",
                f"def RunEquals_{n} : Prop := VSCore3.ReadableRunEquals {n}_compiled {rn}_params {rn}_result {rn}_run",
                f"theorem runEquals_{n} : RunEquals_{n} := by",
                "  with_unfolding_all",
                "    refine ⟨rfl, rfl, ?_⟩",
                "    intro env",
                "    rfl"]
        goal_name = "Readable.RunEquals_" + n
        result.expected[goal_name] = {"type": {"sort": 0}, "value": app(const("VSCore3.ReadableRunEquals"),
            gconst("Readable." + n + "_compiled"), const(rn + "_params"), const(rn + "_result"), const(rn + "_run"))}
        result.expected["Readable.runEquals_" + n] = {"kind": "theorem", "type": gconst(goal_name)}
    p, denoter = Printer(), _Denoter(spec.profile)
    for sym in spec.symbols:
        n = next(r["name"] for r in view.functions if r["role"] == "entry" and r["source_id"] == sym.entry)
        xs = [f"x__{i}" for i in range(sym.arity)]
        binders = " ".join(f"({x} : {p.term(denoter.sort(t))})" for x, t in zip(xs, sym.arg_sorts))
        env = R._tuple([f"{a}.to {x}" for a, x in zip(sym.arg_adapters, xs)])
        fn = "readable_fn_" + lean_component(sym.symbol)
        out += [f"def {fn} {binders} : {p.term(denoter.sort(sym.result_sort))} := by",
                f"  with_unfolding_all exact {sym.result_adapter}.inv ({R.NAMESPACE}.{n}_run {env})",
                f"theorem source_eq_{lean_component(sym.symbol)} {binders} : source_fn_{lean_component(sym.symbol)} {' '.join(xs)} = {fn} {' '.join(xs)} := by with_unfolding_all rfl",
                f"theorem raw_eval_{lean_component(sym.symbol)} {binders} :",
                f"  VSCore3.evalEntry profile rawProgram {src.lean_string(sym.entry)} [" + ", ".join(f"{a}.encode {x}" for a,x in zip(sym.arg_adapters,xs)) + "] =",
                f"    .ok ({sym.result_adapter}.encode ({fn} {' '.join(xs)})) := by",
                f"  rw [← source_eq_{lean_component(sym.symbol)} {' '.join(xs)}]",
                f"  exact {GOAL_MODULE}.raw_eval_{lean_component(sym.symbol)} {' '.join(xs)}"]
    out.append("end " + GOAL_MODULE + ".Readable")
    correspondence = ("\n".join(out) + "\n").encode()
    if len(correspondence) > R.BUDGETS["correspondence_bytes"]:
        raise R.Unavailable("OUTPUT_BUDGET", "readable correspondence byte budget exceeded")
    result.readable_view, result.readable_correspondence = view, correspondence
    result.text = result.base_text + "\n" + view.block.decode() + "\n" + correspondence.decode()
    return result


def _render_source_facts(s: SymbolSpec, profile: Profile, adapters: dict[str, AdapterSpec]) -> list[str]:
    symbol = lean_component(s.symbol)
    entry = src.lean_string(s.entry)
    name = "sourceFacts_" + symbol
    out = [f"def {name} : VeriSlop.Source.ModuleFacts :=",
           f"  let m := VSCore3.exactSourceFacts profile rawProgram {entry}",
           "  { entries := m.entries.map (fun e => ⟨e.file, e.id, e.arity⟩),",
           "    uniqueEntries := m.uniqueEntries, typedTotal := m.typedTotal, deterministic := m.deterministic,",
           "    inputPreserved := m.inputPreserved, noExternalIO := m.noExternalIO,",
           "    noFloatingPoint := m.noFloatingPoint, pureData := m.pureData,",
           "    restrictedRuntimeOnly := m.restrictedRuntimeOnly }",
           f"def SourceAdequate_{symbol} : Prop :=",
           f"  VSCore3.SourceFactsAdequate profile rawProgram {entry} checkedProgram entry_{symbol}",
           f"theorem source_adequate_{symbol} : SourceAdequate_{symbol} := by",
           "  with_unfolding_all",
           f"    exact VSCore3.exactSourceFacts_adequate compiled_ok find_{symbol}",
           "      " + _param_laws(s.arg_sorts, profile),
           "      " + s.result_adapter + "_raw", ""]
    return out


def _raw_laws(sort: Any, profile: Profile) -> str:
    if isinstance(sort, str):
        return "VSCore3." + sort.lower() + "RawLaws"
    tag = next(iter(sort))
    if tag in {"list", "option"}:
        return f"(VSCore3.{tag}RawLaws {_raw_laws(sort[tag], profile)})"
    if tag == "result":
        return f"(VSCore3.resultRawLaws {_raw_laws(sort[tag]['error'], profile)} {_raw_laws(sort[tag]['ok'], profile)})"
    if tag == "record":
        fs = profile.records[sort[tag]]["fields"]
        law, layout = "VSCore3.unitRawLaws", "VSCore3.RecordLayout.nil"
        for f in reversed(fs):
            law = f"(VSCore3.productRawLaws {_raw_laws(f['sort'], profile)} {law})"
            layout = f"(VSCore3.RecordLayout.cons {src.lean_string(f['name'])} {layout})"
        return f"(VSCore3.recordRawLaws {src.lean_string(sort[tag])} {layout} {law})"
    if tag == "enum":
        return "(VSCore3.enumRawLaws " + src.lean_string(sort[tag]) + " [" + ", ".join(
            src.lean_string(c) for c in profile.enums[sort[tag]]["constructors"]) + "])"
    raise BridgeUnsupported("no raw laws for " + repr(sort))


def _param_laws(sorts: list, profile: Profile) -> str:
    if not sorts:
        return "(by intro t h; simp at h)"
    branches = " | ".join("rfl" for _ in sorts)
    proofs = "\n".join("    · exact " + _raw_laws(sort, profile) for sort in sorts)
    return "(by\n    intro t h\n    simp only [List.mem_cons, List.not_mem_nil, or_false] at h\n    rcases h with " + branches + "\n" + proofs + ")"
