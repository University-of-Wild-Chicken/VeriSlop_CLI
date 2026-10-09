"""VSCore 0.1 bridge target (`restricted_source`): goal generation, transfer and re-export.

Everything that defines *what is proved* is derived here by the supervisor, never taken from a
candidate:

* the representation profile: the accepted contract's enumeration registry, reused through
  checked adapters (`VSCore.Transport`);
* the bridge goal module `VeriSlopBridgeGoal`: exact source bytes, the host-proposed program and
  signatures with kernel-checked parse/typing equations, adapters, one implementation relation
  `impl_<symbol>` per bound symbol, the refinement target `Refines_<symbol>` against the accepted
  reference function, input coverage `InputsCover_<symbol>`, and one mechanically derived
  transfer statement `Transfer_<obligation>` per covered accepted obligation;
* the expected kernel expressions of those statements, compared after replay with what Lean
  elaborated (statement identity);
* `implementation-ir.json`, reconstructed from the *replayed* goal declarations by bounded
  constructor reification, never from the host parse.

Transfer rule (`vscore.reference_refinement/0.1`): in the accepted DSL formula of an obligation,
every atomic formula containing calls `f(a…)` is replaced by
`∀ r, impl_f a… r → atom[r/f(a…)]` (innermost calls first). Given `Refines_f`, the implementation
relation is exactly the graph of the reference function, so the goal module itself proves
`Refines_f → Transfer_X` from the accepted theorem of `X`. The candidate only proves `Refines_f`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import canonical, schemas
from ..dsl import DSLError, Profile, type_formula
from ..exprjson import Expr, app, bvar, const, lam, loose_bvar_range, name_str, parse_name, pi
from ..reify import LEVEL_ONE, LEVEL_ZERO, _Denoter
from . import vscore_source as src

TEMPLATE = "vscore.reference_refinement/0.1"
LANGUAGE = src.LANGUAGE
SEMANTICS = "vscore-semantics/0.1"
RELATION_FORMAT = "verislop.vscore-relation/0.1"
MODEL_FORMAT = "verislop.vscore-model/0.1"
PROFILE_FORMAT = "verislop.vscore-profile/0.1"
IR_FORMAT = "verislop.vscore-implementation-ir/0.1"
PROPOSITION_FORMAT = "verislop.vscore-proposition/0.1"
ENDPOINT = "restricted_source"
SOURCE_ROLE = "source"
PROOF_ROLE = "proof_source"
# Frozen resource budgets: exceeding one is never acceptance.
MAX_SOURCE_BYTES = 16 * 1024
MAX_PROOF_BYTES = 1024 * 1024
MAX_BINDINGS = 64

LIB_ROOT = Path(__file__).resolve().parent.parent / "lean"
LIB_MODULES = ("VSCore.Syntax", "VSCore.Decode", "VSCore.Typing", "VSCore.Semantics", "VSCore.Transport", "VSCore")
CONTRACT_MODULE = "VeriSlopContract"
GOAL_MODULE = "VeriSlopBridgeGoal"
PROOF_MODULE = "VeriSlopBridgeProof"
EDGE_THEOREM = PROOF_MODULE + ".edge"
EDGE_PROP = GOAL_MODULE + ".EdgeProp"


class BridgeUnsupported(Exception):
    """The request is outside the registered template (reported as UNSUPPORTED_CAPABILITY)."""


class BridgeInvalid(Exception):
    """A candidate input is malformed or inconsistent with the frozen bridge."""

    def __init__(self, message: str, code: str = "INVALID_CANDIDATE"):
        super().__init__(message)
        self.code = code


def module_path(module: str) -> str:
    return module.replace(".", "/") + ".lean"


def library_sources() -> dict[str, bytes]:
    return {m: (LIB_ROOT / module_path(m)).read_bytes() for m in LIB_MODULES}


# ------------------------------------------------------------------------------------------
# descriptors: relation (candidate), model and profile (derived; candidate copies must match)
# ------------------------------------------------------------------------------------------

def load_relation(data: bytes) -> dict:
    try:
        rel = canonical.loads(data)
    except Exception as exc:  # noqa: BLE001
        raise BridgeInvalid(f"relation descriptor is not canonical JSON: {exc}") from None
    issues = schemas.validate("vscore-relation", rel)
    if issues:
        raise BridgeInvalid(f"vscore-relation: {issues[0]}")
    symbols = [b["symbol"] for b in rel["bindings"]]
    entries = [b["entry"] for b in rel["bindings"]]
    if len(set(symbols)) != len(symbols) or len(set(entries)) != len(entries):
        raise BridgeInvalid("relation bindings must be one-to-one between symbols and entries", "AMBIGUOUS_CORRESPONDENCE")
    if symbols != sorted(symbols):
        raise BridgeInvalid("relation bindings must be sorted by symbol")
    return rel


def model_descriptor(pin: str) -> dict:
    """The registered VSCore semantic model: exact library sources and toolchain."""
    return {"schema_version": "0.1", "format": MODEL_FORMAT, "language": LANGUAGE, "semantics": SEMANTICS,
            "lean_toolchain": pin,
            "library": [{"module": m, "sha256": canonical.digest(data)} for m, data in library_sources().items()],
            "evaluation": "big-step, structurally recursive, deterministic and total on checked programs; "
                          "mathematical natural numbers with truncated subtraction; no step or resource model"}


def profile_descriptor(accepted_profile: dict, accepted_profile_hash: str) -> dict:
    """The representation profile derived from the accepted contract registry."""
    enums = accepted_profile.get("enums", {})
    return {"schema_version": "0.1", "format": PROFILE_FORMAT, "language": LANGUAGE,
            "accepted_profile": accepted_profile["profile_id"], "accepted_profile_hash": accepted_profile_hash,
            "enums": [{"id": eid, "constructors": e["constructors"], "lean_decl": e["lean_decl"],
                       "lean_constructors": e["lean_constructors"]} for eid, e in sorted(enums.items())],
            "representation": {"Nat": "VSCore.Value.nat n (unbounded)", "Bool": "VSCore.Value.bool b",
                               "Unit": "VSCore.Value.unit",
                               "Enum": "VSCore.Value.enum id ctor (accepted registry names and order)",
                               "Result": "VSCore.Value.ok v | VSCore.Value.error e"},
            "adapters": "VSCore.Transport adapters with enc_typed, dec_enc, enc_dec and covers laws"}


# ------------------------------------------------------------------------------------------
# Lean names and the explicit term printer
# ------------------------------------------------------------------------------------------

_KEYWORDS = frozenset("""
at by calc deriving do else end example exists for forall from fun have if import in
inductive instance let local match mutual namespace noncomputable open partial private
protected rec return section show structure suffices then theorem unsafe universe variable
where with Prop Sort Type abbrev axiom class def macro syntax opaque attribute set_option
""".split())
_PLAIN = re.compile(r"[A-Za-z_][A-Za-z0-9_']*\Z")


def lean_component(c: Any) -> str:
    if isinstance(c, int):
        return str(c)
    if _PLAIN.match(c) and c not in _KEYWORDS:
        return c
    if "»" in c or "«" in c or not c or any(ord(ch) < 32 or ord(ch) > 126 for ch in c):
        raise BridgeUnsupported(f"identifier {c!r} cannot be rendered in a generated goal")
    return "«" + c + "»"


def lean_name(comps: list) -> str:
    return ".".join(lean_component(c) for c in comps)


def gname(component: str) -> list:
    return [GOAL_MODULE, component]


def gconst(component: str) -> Expr:
    return {"const": gname(component), "levels": []}


def _level(lv: Any) -> str:
    if isinstance(lv, int):
        return str(lv)
    raise BridgeUnsupported("generated goals use closed universe levels only")


class Printer:
    """Fully explicit Lean term syntax for an Expr: elaboration is the identity up to names."""

    def __init__(self) -> None:
        self.names: list[str] = []

    def binder(self, b: dict) -> str:
        base = b["name"][0] if b.get("name") and isinstance(b["name"][0], str) and _PLAIN.match(b["name"][0]) else "x"
        return f"{base}__{len(self.names)}"

    def term(self, e: Expr) -> str:
        if "bvar" in e:
            return self.names[-1 - e["bvar"]]
        if "const" in e:
            levels = e["levels"]
            suffix = ".{" + ", ".join(_level(lv) for lv in levels) + "}" if levels else ""
            return "@" + lean_name(e["const"]) + suffix
        if "app" in e:
            return "(" + " ".join(self.term(x) for x in e["app"]) + ")"
        if "pi" in e or "lam" in e:
            key = "pi" if "pi" in e else "lam"
            b = e[key]
            if b["bi"] != "default":
                raise BridgeUnsupported("generated goals use default binders only")
            name = self.binder(b)
            dom = self.term(b["type"])
            self.names.append(name)
            try:
                body = self.term(b["body"])
            finally:
                self.names.pop()
            return f"(∀ ({name} : {dom}), {body})" if key == "pi" else f"(fun ({name} : {dom}) => {body})"
        if "lit" in e:
            if "nat" in e["lit"]:
                return f"(nat_lit {int(e['lit']['nat'])})"
            return src.lean_string(e["lit"]["str"])
        if "sort" in e and e["sort"] == 0:
            return "Prop"
        raise BridgeUnsupported(f"expression node outside the goal printer: {sorted(e)}")

    def telescope(self, value: Expr, type_: Expr) -> tuple[list[str], str, str]:
        """Split `fun xs => body : ∀ xs, T` into Lean binders, result type and body."""
        binders = []
        while "lam" in value:
            lb, pb = value["lam"], type_.get("pi")
            if pb is None or lb["type"] != pb["type"]:
                raise BridgeUnsupported("definition value and type telescopes differ")
            name = self.binder(lb)
            binders.append(f"({name} : {self.term(lb['type'])})")
            self.names.append(name)
            value, type_ = lb["body"], pb["body"]
        out = binders, self.term(type_), self.term(value)
        self.names.clear()
        return out


def _strip_names(e: Any) -> Any:
    if isinstance(e, list):
        return [_strip_names(x) for x in e]
    if not isinstance(e, dict):
        return e
    return {k: _strip_names(v) for k, v in e.items() if k != "name"}


def same_expr(a: Expr, b: Expr) -> bool:
    """Kernel-expression identity up to binder display names (mdata is never exported)."""
    return _strip_names(a) == _strip_names(b)


# ------------------------------------------------------------------------------------------
# sorts, VSCore types and adapters
# ------------------------------------------------------------------------------------------

def sort_ty(s: Any) -> Any:
    if s == "Nat":
        return "nat"
    if s == "Bool":
        return "bool"
    if s == "Unit":
        return "unit"
    if isinstance(s, dict) and "enum" in s:
        return ("enum", s["enum"])
    if isinstance(s, dict) and "result" in s:
        return ("result", sort_ty(s["result"]["error"]), sort_ty(s["result"]["ok"]))
    raise BridgeUnsupported(f"sort {s!r} has no VSCore 0.1 representation")


def ty_expr(t: Any) -> Expr:
    if t in ("nat", "bool", "unit"):
        return const(f"VSCore.Ty.{t}")
    if t[0] == "enum":
        return app(const("VSCore.Ty.enum"), {"lit": {"str": t[1]}})
    return app(const("VSCore.Ty.result"), ty_expr(t[1]), ty_expr(t[2]))


def list_expr(elem_type: Expr, items: list[Expr]) -> Expr:
    out = app(const("List.nil", [LEVEL_ZERO]), elem_type)
    for item in reversed(items):
        out = app(const("List.cons", [LEVEL_ZERO]), elem_type, item, out)
    return out


VALUE = const("VSCore.Value")
EVAL_ERROR = const("VSCore.EvalError")
PROFILE = gconst("profile")


def eq_expr(type_: Expr, a: Expr, b: Expr) -> Expr:
    return app(const("Eq", [LEVEL_ONE]), type_, a, b)


def except_type(e: Expr, a: Expr) -> Expr:
    return app(const("Except", [LEVEL_ZERO, LEVEL_ZERO]), e, a)


def except_ok(e: Expr, a: Expr, v: Expr) -> Expr:
    return app(const("Except.ok", [LEVEL_ZERO, LEVEL_ZERO]), e, a, v)


def and_chain(props: list[Expr]) -> Expr:
    out = props[-1]
    for p in reversed(props[:-1]):
        out = app(const("And"), p, out)
    return out


@dataclass
class AdapterSpec:
    name: str          # goal-local declaration component
    sort: Any
    ty: Any
    lean_type: Expr
    definition: str    # Lean source of the definition body


@dataclass
class SymbolSpec:
    symbol: str
    entry: str
    lean_decl: str
    arg_sorts: list
    result_sort: Any
    arg_adapters: list[str]
    result_adapter: str

    @property
    def arity(self) -> int:
        return len(self.arg_sorts)


@dataclass
class ObligationSpec:
    oid: str
    lean_symbol: str
    formula: dict
    statement_hash: str
    symbols: list[str]


@dataclass
class GoalSpec:
    source_bytes: bytes
    program: dict
    signatures: list[dict]
    enums: list[tuple[str, list[str], str, list[str]]]  # id, constructors, lean_decl, lean_constructors
    adapters: list[AdapterSpec]
    symbols: list[SymbolSpec]
    obligations: list[ObligationSpec]
    profile: Profile
    expected: dict[str, dict[str, Expr]] = field(default_factory=dict)
    text: str = ""


class _Adapters:
    def __init__(self, profile: Profile, enum_index: dict[str, int]) -> None:
        self.profile = profile
        self.denoter = _Denoter(profile)
        self.enum_index = enum_index
        self.by_key: dict[bytes, AdapterSpec] = {}
        self.order: list[AdapterSpec] = []

    def get(self, sort: Any) -> AdapterSpec:
        key = canonical.dumps({"sort": sort})
        if key in self.by_key:
            return self.by_key[key]
        ty = sort_ty(sort)
        lean_type = self.denoter.sort(sort)
        if sort == "Nat":
            body = "VSCore.natAdapter profile"
        elif sort == "Bool":
            body = "VSCore.boolAdapter profile"
        elif sort == "Unit":
            body = "VSCore.unitAdapter profile"
        elif "enum" in sort:
            i = self.enum_index[sort["enum"]]
            e = self.profile.enums[sort["enum"]]
            ctors = ", ".join("@" + lean_name(parse_name(c)) for c in e["lean_constructors"])
            body = (f"VSCore.enumAdapter {src.lean_string(sort['enum'])} name_{i} [{ctors}]\n"
                    f"    (by intro a; cases a <;> simp)\n"
                    f"    (by intro a b h; cases a <;> cases b <;> simp_all [name_{i}])\n"
                    f"    (by decide +kernel)")
        else:
            err = self.get(sort["result"]["error"])
            ok = self.get(sort["result"]["ok"])
            body = f"VSCore.exceptAdapter {err.name} {ok.name} (by decide +kernel) (by decide +kernel)"
        spec = AdapterSpec(f"adapter_{len(self.order)}", sort, ty, lean_type, body)
        self.by_key[key] = spec
        self.order.append(spec)
        return spec


# ------------------------------------------------------------------------------------------
# transfer formulas
# ------------------------------------------------------------------------------------------

ATOMS = ("eq", "lt", "le", "holds")


def _calls_postorder(t: Any, out: list) -> None:
    if not isinstance(t, dict):
        return
    for key in ("left", "right", "value", "term"):
        if key in t and isinstance(t[key], dict):
            _calls_postorder(t[key], out)
    if t.get("tag") == "call":
        for a in t["args"]:
            _calls_postorder(a, out)
        out.append(t)


class _Transfer(_Denoter):
    """The DSL denotation with every call-containing atom replaced by its implementation reading."""

    def __init__(self, profile: Profile, symbols: dict[str, SymbolSpec]) -> None:
        super().__init__(profile)
        self.symbols = symbols

    def term(self, t: dict[str, Any], ctx: list[tuple]) -> tuple[Expr, Any]:
        if t["tag"] == "call":
            for j, entry in enumerate(ctx):
                if entry[0] == "res" and entry[1] is t:
                    return bvar(j), entry[2]
            raise BridgeUnsupported("call outside an atomic formula (for example in a range bound)")
        return super().term(t, ctx)

    def formula(self, p: dict[str, Any], ctx: list[tuple]) -> Expr:
        tag = p["tag"]
        if tag in ("forall_range", "exists_range"):
            found: list = []
            _calls_postorder(p["lower"], found)
            _calls_postorder(p["upper"], found)
            if found:
                raise BridgeUnsupported("calls inside range-quantifier bounds have no transfer rule")
            return super().formula(p, ctx)
        if tag not in ATOMS:
            return super().formula(p, ctx)
        found = []
        for key in ("left", "right", "term"):
            if key in p:
                _calls_postorder(p[key], found)
        return self._bind(found, 0, p, ctx)

    def _bind(self, calls: list, i: int, atom: dict, ctx: list[tuple]) -> Expr:
        if i == len(calls):
            return super().formula(atom, ctx)
        call = calls[i]
        sym = self.symbols.get(call["symbol"])
        if sym is None:
            raise BridgeUnsupported(f"symbol {call['symbol']} has no implementation binding")
        res_ctx = [("res", call, sym.result_sort)] + ctx
        args = [self.term(a, res_ctx)[0] for a in call["args"]]
        hyp = app(gconst("impl_" + sym.symbol), *args, bvar(0))
        body = self._bind(calls, i + 1, atom, [("proof",)] + res_ctx)
        return pi("r", self.sort(sym.result_sort), pi("h", hyp, body))


def transfer_expr(formula: dict, profile: Profile, symbols: dict[str, SymbolSpec]) -> Expr:
    return _Transfer(profile, symbols).formula(formula, [])


# ------------------------------------------------------------------------------------------
# expected statements
# ------------------------------------------------------------------------------------------

def _impl(sym: SymbolSpec, adapters: dict[str, AdapterSpec], denoter: _Denoter) -> tuple[Expr, Expr]:
    n = sym.arity
    res = adapters[sym.result_adapter]

    def enc(adapter: AdapterSpec, v: Expr) -> Expr:
        return app(const("VSCore.Adapter.enc"), PROFILE, adapter.lean_type, ty_expr(adapter.ty), gconst(adapter.name), v)

    # Under the binders x0 … x(n-1), r: argument i is bvar(n - i), the result is bvar(0).
    args = [enc(adapters[a], bvar(n - i)) for i, a in enumerate(sym.arg_adapters)]
    call = app(const("VSCore.evalEntry"), gconst("rawProgram"), {"lit": {"str": sym.entry}}, list_expr(VALUE, args))
    body = eq_expr(except_type(EVAL_ERROR, VALUE), call, except_ok(EVAL_ERROR, VALUE, enc(res, bvar(0))))
    value = lam("r", res.lean_type, body)
    type_ = pi("r", res.lean_type, {"sort": 0})
    for s in reversed(sym.arg_sorts):
        value = lam("x", denoter.sort(s), value)
        type_ = pi("x", denoter.sort(s), type_)
    return value, type_


def _refines(sym: SymbolSpec, denoter: _Denoter) -> Expr:
    n = sym.arity
    xs = [bvar(n - 1 - i) for i in range(n)]
    body = app(gconst("impl_" + sym.symbol), *xs, app(const(sym.lean_decl), *xs))
    for s in reversed(sym.arg_sorts):
        body = pi("x", denoter.sort(s), body)
    return body


def _inputs_cover(sym: SymbolSpec, adapters: dict[str, AdapterSpec]) -> Expr:
    n = sym.arity
    list_value = app(const("List", [LEVEL_ZERO]), VALUE)
    tys = list_expr(const("VSCore.Ty"), [ty_expr(sort_ty(s)) for s in sym.arg_sorts])
    # Context outside the existentials: [h, args]; inside k existentials, args is bvar(k + 1).
    encs = [app(const("VSCore.Adapter.enc"), PROFILE, adapters[a].lean_type, ty_expr(adapters[a].ty),
                gconst(adapters[a].name), bvar(n - 1 - i)) for i, a in enumerate(sym.arg_adapters)]
    body = eq_expr(list_value, bvar(n + 1), list_expr(VALUE, encs))
    for i in reversed(range(n)):
        t = adapters[sym.arg_adapters[i]].lean_type
        body = app(const("Exists", [LEVEL_ONE]), t, lam("x", t, body))
    typed = app(const("VSCore.ArgsTypedIn"), PROFILE, bvar(0), tys)
    return pi("args", list_value, pi("h", typed, body))


def _edge(spec: GoalSpec) -> Expr:
    program = const("VSCore.Program")
    sigs = app(const("List", [LEVEL_ZERO]), const("VSCore.EntrySig"))
    string = const("String")
    props = [
        eq_expr(except_type(string, program), app(const("VSCore.parseSource"), gconst("sourceBytes")),
                except_ok(string, program, gconst("rawProgram"))),
        eq_expr(except_type(string, sigs), app(const("VSCore.checkProgram"), PROFILE, gconst("rawProgram")),
                except_ok(string, sigs, gconst("signatures"))),
    ]
    for sym in spec.symbols:
        props += [gconst("InputsCover_" + sym.symbol), gconst("Refines_" + sym.symbol)]
    props += [gconst("Transfer_" + ob.oid) for ob in spec.obligations]
    return and_chain(props)


# ------------------------------------------------------------------------------------------
# goal construction
# ------------------------------------------------------------------------------------------

def build_goal(source: bytes, relation: dict, accepted_profile: dict, obligations: dict[str, dict]) -> GoalSpec:
    """Derive the complete goal from accepted inputs.

    `obligations` maps each covered obligation ID to {"formula", "lean_symbol", "statement_hash"},
    read from the accepted IR and its accepted formula packages.
    """
    if len(source) > MAX_SOURCE_BYTES:
        raise BridgeUnsupported(f"source exceeds the frozen {MAX_SOURCE_BYTES}-byte parse/proof budget")
    try:
        profile = Profile.from_json(accepted_profile)
    except (DSLError, KeyError, TypeError) as exc:
        raise BridgeInvalid(f"accepted profile cannot be loaded: {exc}", "STATEMENT_MISMATCH") from None
    enums_sorted = sorted(profile.enums.items())
    enum_index = {eid: i for i, (eid, _) in enumerate(enums_sorted)}
    enum_ctors = {eid: list(e["constructors"]) for eid, e in enums_sorted}
    for eid, e in enums_sorted:
        if len(e.get("lean_constructors", [])) != len(e["constructors"]):
            raise BridgeInvalid(f"accepted enumeration {eid} has an inconsistent constructor registry", "STATEMENT_MISMATCH")
        for c in e["constructors"]:
            src.lean_string(c)
        src.lean_string(eid)
    try:
        program = src.parse_source(source)
        signatures = src.check_program(enum_ctors, program)
    except src.SourceError as exc:
        raise BridgeInvalid(f"VSCore source rejected: {exc}") from None
    entries = {e["id"]: e for e in program["entries"]}
    bindings = relation["bindings"]
    if len(bindings) > MAX_BINDINGS:
        raise BridgeUnsupported("too many symbol bindings")
    if {b["entry"] for b in bindings} != set(entries):
        raise BridgeInvalid("every program entry must be bound to exactly one accepted symbol, and every binding "
                            "must name a program entry", "UNMAPPED_IMPLEMENTATION_OBJECT")
    adapters = _Adapters(profile, enum_index)
    symbols: list[SymbolSpec] = []
    for b in bindings:
        decl = profile.symbols.get(b["symbol"])
        if decl is None:
            raise BridgeInvalid(f"relation binds unknown accepted symbol {b['symbol']}", "UNMAPPED_IMPLEMENTATION_OBJECT")
        if decl.get("level_params"):
            raise BridgeUnsupported(f"universe-polymorphic symbol {b['symbol']}")
        entry = entries[b["entry"]]
        want_params = [sort_ty(s) for s in decl["args"]]
        want_result = sort_ty(decl["result"])
        if entry["params"] != want_params or entry["result"] != want_result:
            raise BridgeInvalid(f"entry {b['entry']} signature differs from the accepted signature of {b['symbol']}",
                                "STATEMENT_MISMATCH")
        arg_adapters = [adapters.get(s).name for s in decl["args"]]
        res_adapter = adapters.get(decl["result"]).name
        symbols.append(SymbolSpec(b["symbol"], b["entry"], decl["lean_decl"], list(decl["args"]), decl["result"],
                                  arg_adapters, res_adapter))
    by_symbol = {s.symbol: s for s in symbols}
    obs: list[ObligationSpec] = []
    for oid in sorted(obligations):
        rec = obligations[oid]
        formula = rec["formula"]
        try:
            type_formula(formula, [], profile)
        except DSLError as exc:
            raise BridgeInvalid(f"{oid}: accepted formula does not type check: {exc}", "STATEMENT_MISMATCH") from None
        found: list = []
        stack = [formula]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if x.get("tag") == "call":
                    found.append(x["symbol"])
                stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
            elif isinstance(x, list):
                stack.extend(x)
        used = sorted(set(found))
        if not used:
            raise BridgeUnsupported(f"{oid} mentions no implementation symbol; no transfer rule applies")
        missing = [s for s in used if s not in by_symbol]
        if missing:
            raise BridgeInvalid(f"{oid} uses symbols without an implementation binding: {', '.join(missing)}",
                                "UNMAPPED_IMPLEMENTATION_OBJECT")
        obs.append(ObligationSpec(oid, rec["lean_symbol"], formula, rec["statement_hash"], used))
    if not obs:
        raise BridgeInvalid("the edge covers no accepted obligation", "ORPHAN_CLAIM")
    spec = GoalSpec(source, program, signatures,
                    [(eid, list(e["constructors"]), e["lean_decl"], list(e["lean_constructors"])) for eid, e in enums_sorted],
                    adapters.order, symbols, obs, profile)
    _expected(spec)
    spec.text = render_goal(spec)
    return spec


def _expected(spec: GoalSpec) -> None:
    denoter = _Denoter(spec.profile)
    adapters = {a.name: a for a in spec.adapters}
    by_symbol = {s.symbol: s for s in spec.symbols}
    prop = {"sort": 0}
    for sym in spec.symbols:
        value, type_ = _impl(sym, adapters, denoter)
        spec.expected["impl_" + sym.symbol] = {"type": type_, "value": value}
        spec.expected["Refines_" + sym.symbol] = {"type": prop, "value": _refines(sym, denoter)}
        spec.expected["InputsCover_" + sym.symbol] = {"type": prop, "value": _inputs_cover(sym, adapters)}
    for ob in spec.obligations:
        spec.expected["Transfer_" + ob.oid] = {"type": prop, "value": transfer_expr(ob.formula, spec.profile, by_symbol)}
    spec.expected["EdgeProp"] = {"type": prop, "value": _edge(spec)}


def _doc(text: str) -> str:
    # Lean block comments nest, so neither opener nor closer may appear in generated text.
    safe = text.replace("/-", "/ -").replace("-/", "- /")
    return "/-- " + "".join(c if c.isprintable() else " " for c in safe) + " -/"


def render_goal(spec: GoalSpec) -> str:
    from ..dsl import render

    p = Printer()
    out = [
        "import VSCore",
        "import VeriSlopContract",
        "",
        "/-!",
        "# VeriSlop bridge goal (verifier-generated; candidates cannot change it)",
        "",
        f"Template `{TEMPLATE}`, language `{LANGUAGE}`, semantics `{SEMANTICS}`.",
        f"Source: {canonical.digest(spec.source_bytes)} ({len(spec.source_bytes)} bytes).",
        "",
        "A candidate proof module `VeriSlopBridgeProof` must import only this module (and",
        "toolchain modules) and prove `theorem edge : VeriSlopBridgeGoal.EdgeProp`, normally as",
        "`VeriSlopBridgeGoal.edge_of_refines` applied to proofs of every `Refines_<symbol>`.",
        "-/",
        "",
        "namespace VeriSlopBridgeGoal",
        "",
        _doc(f"Exact bytes of the frozen source artifact {canonical.digest(spec.source_bytes)}."),
        "def sourceBytes : List Nat := [" + ", ".join(str(b) for b in spec.source_bytes) + "]",
        "",
        _doc("Host-proposed decoding; its authority is only the kernel-checked `source_parses`."),
        "def rawProgram : VSCore.Program :=",
        "  " + src.lean_program(spec.program),
        "",
        _doc("The accepted contract's enumeration registry (IDs and constructor order)."),
        "def profile : VSCore.Profile := { enums := [" + ", ".join(
            "(" + src.lean_string(eid) + ", [" + ", ".join(src.lean_string(c) for c in ctors) + "])"
            for eid, ctors, _, _ in spec.enums) + "] }",
        "",
        "def signatures : List VSCore.EntrySig :=",
        "  " + src.lean_signatures(spec.signatures),
        "",
        "theorem source_parses : VSCore.parseSource sourceBytes = .ok rawProgram :=",
        "  VSCore.parseSource_of_check (by decide +kernel)",
        "",
        "theorem source_checks : VSCore.checkProgram profile rawProgram = .ok signatures :=",
        "  VSCore.checkProgram_of_check (by decide +kernel)",
        "",
    ]
    for i, (eid, ctors, decl, lean_ctors) in enumerate(spec.enums):
        out.append(_doc(f"Registered names of enumeration {eid} ({decl})."))
        out.append(f"def name_{i} : @{lean_name(parse_name(decl))} → String")
        for c, lc in zip(ctors, lean_ctors):
            out.append(f"  | @{lean_name(parse_name(lc))} => {src.lean_string(c)}")
        out.append("")
    for a in spec.adapters:
        out.append(_doc(f"Representation adapter for sort {canonical.dumps(a.sort).decode()}."))
        out.append(f"def {a.name} : VSCore.Adapter profile {p.term(a.lean_type)} {src.lean_ty(a.ty)} :=")
        out.append(f"  {a.definition}")
        out.append("")
    for sym in spec.symbols:
        s = sym.symbol
        impl, ref, cover = (lean_component(x + s) for x in ("impl_", "Refines_", "InputsCover_"))
        n = sym.arity
        xs = [f"x__{i}" for i in range(n)]
        exp = spec.expected
        binders, rtype, body = p.telescope(exp["impl_" + s]["value"], exp["impl_" + s]["type"])
        res_type = p.term(_Denoter(spec.profile).sort(sym.result_sort))
        out += [
            _doc(f"Implementation relation of accepted symbol `{s}` ({sym.lean_decl}) bound to entry "
                 f"{src.lean_string(sym.entry)}: the entry returns exactly the encoded result."),
            f"def {impl} {' '.join(binders)} : {rtype} :=", f"  {body}", "",
            _doc(f"Refinement target: entry {src.lean_string(sym.entry)} computes the accepted reference "
                 f"`{sym.lean_decl}` on every input."),
            f"def {ref} : Prop :=", f"  {p.term(exp['Refines_' + s]['value'])}", "",
            _doc(f"Every well-typed argument list of entry {src.lean_string(sym.entry)} encodes contract inputs."),
            f"def {cover} : Prop :=", f"  {p.term(exp['InputsCover_' + s]['value'])}", "",
            f"theorem {lean_component('inputs_cover_' + s)} : {cover} := by",
            "  intro args h",
        ]
        for i in range(n):
            out.append(f"  cases h with | cons h__{i} h =>")
        out.append("  cases h")
        if n:
            for i, a in enumerate(sym.arg_adapters):
                out.append(f"  obtain ⟨{xs[i]}, hx__{i}⟩ := {a}.represents h__{i}")
            out.append(f"  exact ⟨{', '.join(xs)}, by rw [{', '.join(f'hx__{i}' for i in range(n))}]⟩")
        else:
            out.append("  rfl")
        arg_binders = " ".join(f"({x} : {p.term(_Denoter(spec.profile).sort(t))})" for x, t in zip(xs, sym.arg_sorts))
        call = f"@{lean_name(parse_name(sym.lean_decl))} {' '.join(xs)}".rstrip()
        # Helper lemmas live apart from the public implementation definitions. In
        # particular, symbols `f` and `f_iff` must not both declare `impl_f_iff`.
        graph_iff = "Internal." + lean_component("impl_" + s + "_iff")
        forall_impl = "Internal." + lean_component("forall_impl_" + s)
        public_impl = "_root_." + GOAL_MODULE + "." + impl
        graph_ref = "_root_." + GOAL_MODULE + "." + graph_iff
        out += [
            "",
            f"theorem {graph_iff} (h : {ref}) {arg_binders} (r : {res_type}) :",
            f"    {public_impl} {' '.join(xs)} r ↔ r = {call} := by",
            f"  have hx : {public_impl} {' '.join(xs)} ({call}) := h {' '.join(xs)}",
            "  constructor",
            "  · intro hr",
            f"    unfold {public_impl} at hr hx",
            f"    exact (VSCore.Adapter.enc_eq_iff {sym.result_adapter}).mp (Except.ok.inj (hr.symm.trans hx))",
            "  · intro hr",
            "    cases hr",
            "    exact hx",
            "",
            f"theorem {forall_impl} (h : {ref}) {arg_binders} (P : {res_type} → Prop) :",
            f"    (∀ r, {public_impl} {' '.join(xs)} r → P r) ↔ P ({call}) := by",
            "  constructor",
            "  · intro hp",
            f"    exact hp ({call}) (h {' '.join(xs)})",
            "  · intro hp r hr",
            f"    have he := ({graph_ref} h {' '.join(xs)} r).mp hr",
            "    cases he",
            "    exact hp",
            "",
        ]
    for ob in spec.obligations:
        tr = lean_component("Transfer_" + ob.oid)
        hyps = " ".join(f"({lean_component('h_' + s)} : {lean_component('Refines_' + s)})" for s in ob.symbols)
        rules = ", ".join(f"Internal.{lean_component('forall_impl_' + s)} {lean_component('h_' + s)}"
                          for s in ob.symbols)
        reference = p.term(_Denoter(spec.profile).formula(ob.formula, []))
        out += [
            _doc(f"Implementation reading of accepted obligation {ob.oid} ({ob.lean_symbol}, "
                 f"statement {ob.statement_hash}): {render(ob.formula)}"),
            f"def {tr} : Prop :=", f"  {p.term(spec.expected['Transfer_' + ob.oid]['value'])}", "",
            f"theorem {lean_component('transfer_' + ob.oid)} {hyps} : {tr} := by",
            # Eliminate a complete call-result binder before simplifying its body.
            # This also works for Unit, whose equalities are definitionally true.
            # Compare with the explicit DSL denotation: an accepted theorem may
            # still name registered predicates that reification unfolded. Kernel
            # conversion handles those aliases at the final theorem application.
            f"  have htransfer : {tr} ↔ {reference} := by",
            f"    unfold {tr}",
            f"    simp only [{rules}]",
            f"  exact htransfer.mpr @{lean_name(parse_name(ob.lean_symbol))}",
            "",
        ]
    refines = " ".join(f"({lean_component('h_' + s.symbol)} : {lean_component('Refines_' + s.symbol)})"
                       for s in spec.symbols)
    parts = ["source_parses", "source_checks"]
    for s in spec.symbols:
        parts += [lean_component("inputs_cover_" + s.symbol), lean_component("h_" + s.symbol)]
    for ob in spec.obligations:
        parts.append(f"{lean_component('transfer_' + ob.oid)} " + " ".join(lean_component("h_" + s) for s in ob.symbols))
    out += [
        _doc("The edge proposition: exact parse and typing, input coverage, refinement and transfer of every "
             "covered accepted obligation."),
        f"def EdgeProp : Prop :=", f"  {p.term(spec.expected['EdgeProp']['value'])}", "",
        f"theorem edge_of_refines {refines} : EdgeProp :=",
        "  ⟨" + ", ".join(f"({x})" if " " in x else x for x in parts) + "⟩",
        "",
        "end VeriSlopBridgeGoal",
        "",
    ]
    return "\n".join(out)


# ------------------------------------------------------------------------------------------
# replayed-environment checks: statement identity, proposition hash, IR re-export
# ------------------------------------------------------------------------------------------

def decl_index(constants_: list[dict]) -> dict[str, dict]:
    return {name_str(c["name"]): c for c in constants_}


def statement_mismatches(spec: GoalSpec, decls: dict[str, dict]) -> list[str]:
    """Names whose replayed type/value differ from the supervisor-derived expressions."""
    bad = []
    for comp, want in sorted(spec.expected.items()):
        got = decls.get(name_str(gname(comp)))
        if (got is None or got.get("kind") != "definition" or got.get("level_params")
                or not same_expr(got.get("type", {}), want["type"]) or not same_expr(got.get("value", {}), want["value"])):
            bad.append(GOAL_MODULE + "." + comp)
    return bad


def proposition_hash(decls: dict[str, dict], pin: str) -> tuple[str, dict[str, str]]:
    """Digest of the edge proposition and the declarations its meaning depends on."""
    from ..exprjson import closure, decl_hash

    root = decls.get(EDGE_PROP)
    if root is None:
        raise BridgeInvalid("replayed goal has no EdgeProp declaration", "STATEMENT_MISMATCH")
    names = closure({EDGE_PROP}, decls)
    hashes = {n: decl_hash(decls[n]) for n in sorted(names)}
    digest = canonical.digest_json({"format": PROPOSITION_FORMAT, "lean_toolchain": pin,
                                    "proposition": _strip_names(const(EDGE_PROP)), "closure": hashes})
    return digest, hashes


class _Reify:
    """Bounded constructor reification of closed goal values.

    The only reduction is zeta (let) through an explicit environment, needed because Lean
    elaborates long list literals into let-bound binary splits. Anything else that is not a
    constructor application or literal fails closed.
    """

    def __init__(self, budget: int = 4_000_000) -> None:
        self.budget = budget

    def tick(self) -> None:
        self.budget -= 1
        if self.budget < 0:
            raise BridgeInvalid("implementation re-export exceeded its node budget", "IR_REIFICATION_MISMATCH")

    def whnf(self, e: Expr, env: tuple | None) -> tuple[Expr, tuple | None]:
        while True:
            self.tick()
            if "let" in e:
                env = ((e["let"]["value"], env), env)
                e = e["let"]["body"]
            elif "bvar" in e:
                cell, i = env, e["bvar"]
                while i and cell is not None:
                    cell, i = cell[1], i - 1
                if cell is None:
                    raise self.fail("closed")
                e, env = cell[0]
            else:
                return e, env

    def head(self, e: Expr, env: tuple | None, name: str, arity: int) -> list[tuple[Expr, tuple | None]] | None:
        e, env = self.whnf(e, env)
        fn, args = (e["app"][0], e["app"][1:]) if "app" in e else (e, [])
        if "const" in fn and name_str(fn["const"]) == name and len(args) == arity:
            return [(a, env) for a in args]
        return None

    def closed(self, x: tuple[Expr, tuple | None]) -> Expr:
        e, _ = self.whnf(*x)
        if loose_bvar_range(e):
            raise self.fail("closed")
        return e

    def fail(self, what: str) -> BridgeInvalid:
        return BridgeInvalid(f"accepted declaration is not a closed {what} constructor term", "IR_REIFICATION_MISMATCH")

    def nat(self, x: tuple[Expr, tuple | None]) -> int:
        e = self.closed(x)
        if "lit" in e and "nat" in e["lit"]:
            return int(e["lit"]["nat"])
        fn, args = (e["app"][0], e["app"][1:]) if "app" in e else (e, [])
        if fn == const("OfNat.ofNat", [LEVEL_ZERO]) and len(args) == 3 and args[0] == const("Nat") \
                and "lit" in args[1] and "nat" in args[1]["lit"] and args[2] == app(const("instOfNatNat"), args[1]):
            return int(args[1]["lit"]["nat"])
        raise self.fail("natural number")

    def string(self, x: tuple[Expr, tuple | None]) -> str:
        e = self.closed(x)
        if "lit" in e and "str" in e["lit"]:
            return e["lit"]["str"]
        raise self.fail("string literal")

    def list(self, x: tuple[Expr, tuple | None], elem_type: Expr, item) -> list:
        out = []
        while True:
            args = self.head(*x, "List.cons", 3)
            if args is not None and self.closed(args[0]) == elem_type:
                out.append(item(args[1]))
                x = args[2]
                continue
            args = self.head(*x, "List.nil", 1)
            if args is not None and self.closed(args[0]) == elem_type:
                return out
            raise self.fail("list")

    def bool(self, x: tuple[Expr, tuple | None]) -> bool:
        e = self.closed(x)
        if e == const("Bool.true"):
            return True
        if e == const("Bool.false"):
            return False
        raise self.fail("Boolean")

    def ty(self, x: tuple[Expr, tuple | None]) -> Any:
        e, env = self.whnf(*x)
        for t in ("nat", "bool", "unit"):
            if e == const(f"VSCore.Ty.{t}"):
                return t
        if (a := self.head(e, env, "VSCore.Ty.enum", 1)) is not None:
            return ("enum", self.string(a[0]))
        if (a := self.head(e, env, "VSCore.Ty.result", 2)) is not None:
            return ("result", self.ty(a[0]), self.ty(a[1]))
        raise self.fail("VSCore type")

    def expr(self, x: tuple[Expr, tuple | None]) -> Any:
        e, env = self.whnf(*x)
        if (a := self.head(e, env, "VSCore.Expr.var", 1)) is not None:
            return ("var", self.nat(a[0]))
        if (a := self.head(e, env, "VSCore.Expr.nat", 1)) is not None:
            return ("nat", self.nat(a[0]))
        if (a := self.head(e, env, "VSCore.Expr.bool", 1)) is not None:
            return ("bool", self.bool(a[0]))
        if e == const("VSCore.Expr.unit"):
            return ("unit",)
        if (a := self.head(e, env, "VSCore.Expr.enum", 2)) is not None:
            return ("enum", self.string(a[0]), self.string(a[1]))
        if (a := self.head(e, env, "VSCore.Expr.bin", 3)) is not None:
            opx = self.closed(a[0])
            op = next((o for o in src.BIN_OPS if opx == const(f"VSCore.BinOp.{o}")), None)
            if op is None:
                raise self.fail("binary operator")
            return ("bin", op, self.expr(a[1]), self.expr(a[2]))
        if (a := self.head(e, env, "VSCore.Expr.not", 1)) is not None:
            return ("not", self.expr(a[0]))
        if (a := self.head(e, env, "VSCore.Expr.ite", 3)) is not None:
            return ("ite", self.expr(a[0]), self.expr(a[1]), self.expr(a[2]))
        if (a := self.head(e, env, "VSCore.Expr.letE", 2)) is not None:
            return ("let", self.expr(a[0]), self.expr(a[1]))
        if (a := self.head(e, env, "VSCore.Expr.ok", 2)) is not None:
            return ("ok", self.ty(a[0]), self.expr(a[1]))
        if (a := self.head(e, env, "VSCore.Expr.error", 2)) is not None:
            return ("error", self.ty(a[0]), self.expr(a[1]))
        if (a := self.head(e, env, "VSCore.Expr.matchResult", 3)) is not None:
            return ("match", self.expr(a[0]), self.expr(a[1]), self.expr(a[2]))
        raise self.fail("VSCore expression")

    def program(self, x: tuple[Expr, tuple | None]) -> dict:
        a = self.head(*x, "VSCore.Program.mk", 2)
        if a is None:
            raise self.fail("program")

        def entry(y: tuple[Expr, tuple | None]) -> dict:
            f = self.head(*y, "VSCore.Entry.mk", 4)
            if f is None:
                raise self.fail("entry")
            return {"id": self.string(f[0]), "params": self.list(f[1], const("VSCore.Ty"), self.ty),
                    "result": self.ty(f[2]), "body": self.expr(f[3])}

        return {"language": self.string(a[0]), "entries": self.list(a[1], const("VSCore.Entry"), entry)}

    def signature(self, x: tuple[Expr, tuple | None]) -> dict:
        f = self.head(*x, "VSCore.EntrySig.mk", 3)
        if f is None:
            raise self.fail("entry signature")
        return {"id": self.string(f[0]), "params": self.list(f[1], const("VSCore.Ty"), self.ty), "result": self.ty(f[2])}

    def profile(self, x: tuple[Expr, tuple | None]) -> list:
        a = self.head(*x, "VSCore.Profile.mk", 1)
        if a is None:
            raise self.fail("profile")
        string = const("String")
        pair_t = app(const("Prod", [LEVEL_ZERO, LEVEL_ZERO]), string, app(const("List", [LEVEL_ZERO]), string))

        def pair(y: tuple[Expr, tuple | None]) -> list:
            f = self.head(*y, "Prod.mk", 4)
            if f is None:
                raise self.fail("registry entry")
            return [self.string(f[2]), self.list(f[3], string, self.string)]

        return self.list(a[0], pair_t, pair)


def _value(decls: dict[str, dict], comp: str) -> Expr:
    d = decls.get(name_str(gname(comp)))
    if d is None or d.get("kind") != "definition" or "value" not in d:
        raise BridgeInvalid(f"replayed goal lacks definition {comp}", "IR_REIFICATION_MISMATCH")
    return d["value"]


def reexport(spec: GoalSpec, decls: dict[str, dict]) -> dict:
    """Reconstruct the implementation IR from the replayed goal; bind it to the exact source bytes."""
    r = _Reify()
    source = bytes(r.list((_value(decls, "sourceBytes"), None), const("Nat"), r.nat))
    if source != spec.source_bytes:
        raise BridgeInvalid("accepted source-byte declaration differs from the frozen source artifact", "INPUT_MUTATION")
    program = r.program((_value(decls, "rawProgram"), None))
    sigs = r.list((_value(decls, "signatures"), None), const("VSCore.EntrySig"), r.signature)
    registry = r.profile((_value(decls, "profile"), None))
    if program != spec.program or sigs != spec.signatures:
        raise BridgeInvalid("accepted program declaration differs from the host proposal", "IR_REIFICATION_MISMATCH")
    if registry != [[eid, ctors] for eid, ctors, _, _ in spec.enums]:
        raise BridgeInvalid("accepted enumeration registry differs from the accepted contract profile",
                            "IR_REIFICATION_MISMATCH")
    return {"program": src.program_json(program),
            "signatures": [{"id": s["id"], "params": [src.ty_json(t) for t in s["params"]],
                            "result": src.ty_json(s["result"])} for s in sigs],
            "enums": [{"id": eid, "constructors": ctors} for eid, ctors in registry],
            "bindings": [{"symbol": s.symbol, "entry": s.entry, "lean_decl": s.lean_decl,
                          "args": s.arg_sorts, "result": s.result_sort} for s in spec.symbols]}
