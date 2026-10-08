"""Contract expression DSL, version 0.1 (docs/contract-ir.md).

Typed first-order formulas over Nat, Bool, Unit, finite enumerations and explicit results,
closed under de Bruijn binding. This module implements:

* exact JSON node shapes, typing judgments and registered parse limits;
* canonical encoding and the per-value round trip ``decode(encode(q)) == q``;
* a three-valued evaluator used by test campaigns and runtime monitors. Sampling a quantifier
  over Nat never makes a universal formula *true*; only definite counterexamples are reported
  as failures and exhaustion yields UNKNOWN.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from . import canonical

ENCODING = "verislop.contract-dsl/0.1"
OPAQUE_ENCODING = "verislop.lean-export-ref/0.1"
ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
NAT_RE = re.compile(r"^(0|[1-9][0-9]*)$")
MAX_INDEX = 2147483647

LIMITS = {"max_bytes": 1 << 20, "max_depth": 256, "max_nodes": 100_000}

NAT_OPS = ("add", "sub", "mul")
RELATIONS = ("eq", "lt", "le")
CONNECTIVES = ("and", "or", "implies", "iff")
QUANTIFIERS = ("forall", "exists")
RANGE_QUANTIFIERS = ("forall_range", "exists_range")


class DSLError(ValueError):
    pass


# ------------------------------------------------------------------------------------------
# sorts and the profile registry
# ------------------------------------------------------------------------------------------

Sort = Any  # "Nat" | "Bool" | "Unit" | {"enum": id} | {"result": {"error": S, "ok": S}}


def check_sort(s: Any, profile: "Profile") -> None:
    if s in ("Nat", "Bool", "Unit"):
        return
    if isinstance(s, dict) and set(s) == {"enum"}:
        if s["enum"] not in profile.enums:
            raise DSLError(f"unknown enumeration {s['enum']!r}")
        return
    if isinstance(s, dict) and set(s) == {"result"}:
        r = s["result"]
        if not isinstance(r, dict) or set(r) != {"error", "ok"}:
            raise DSLError("result sort must have exactly error and ok")
        check_sort(r["error"], profile)
        check_sort(r["ok"], profile)
        return
    raise DSLError(f"invalid sort {s!r}")


def sort_eq(a: Sort, b: Sort) -> bool:
    return canonical.dumps(a) == canonical.dumps(b)


def is_finite(s: Sort) -> bool:
    if s in ("Bool", "Unit"):
        return True
    if s == "Nat":
        return False
    if "enum" in s:
        return True
    return is_finite(s["result"]["error"]) and is_finite(s["result"]["ok"])


def sort_str(s: Sort) -> str:
    if isinstance(s, str):
        return s
    if "enum" in s:
        return s["enum"]
    return f"Result({sort_str(s['result']['error'])}, {sort_str(s['result']['ok'])})"


@dataclass
class Profile:
    profile_id: str
    enums: dict[str, dict[str, Any]]
    symbols: dict[str, dict[str, Any]]
    predicates: dict[str, dict[str, Any]]
    raw: dict[str, Any]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Profile":
        p = cls(data["profile_id"], data.get("enums", {}), data.get("symbols", {}), data.get("predicates", {}), data)
        for eid, e in p.enums.items():
            if not ID_RE.match(eid):
                raise DSLError(f"invalid enumeration ID {eid!r}")
            ctors = e["constructors"]
            if not ctors or len(set(ctors)) != len(ctors) or not all(ID_RE.match(c) for c in ctors):
                raise DSLError(f"enumeration {eid} needs a nonempty list of unique constructor IDs")
        for sid, s in p.symbols.items():
            if not ID_RE.match(sid):
                raise DSLError(f"invalid symbol ID {sid!r}")
            for a in s["args"]:
                check_sort(a, p)
            check_sort(s["result"], p)
        return p

    def hash(self) -> str:
        return canonical.digest_json(self.raw)


# ------------------------------------------------------------------------------------------
# typing
# ------------------------------------------------------------------------------------------

class _Budget:
    def __init__(self) -> None:
        self.nodes = 0

    def tick(self, depth: int) -> None:
        self.nodes += 1
        if self.nodes > LIMITS["max_nodes"]:
            raise DSLError("node-count limit exceeded")
        if depth > LIMITS["max_depth"]:
            raise DSLError("nesting limit exceeded")


def _fields(node: Any, expected: set[str], what: str) -> None:
    if not isinstance(node, dict):
        raise DSLError(f"{what} must be an object")
    if set(node) != expected:
        raise DSLError(f"{what} {node.get('tag', '?')!r} must have exactly fields {sorted(expected)}, got {sorted(node)}")


def type_term(t: Any, ctx: list[Sort], profile: Profile, budget: _Budget | None = None, depth: int = 0) -> Sort:
    budget = budget or _Budget()
    budget.tick(depth)
    if not isinstance(t, dict) or "tag" not in t:
        raise DSLError("term must be an object with a tag")
    tag = t["tag"]
    if tag == "var":
        _fields(t, {"tag", "index"}, "term")
        i = t["index"]
        if not isinstance(i, int) or isinstance(i, bool) or not (0 <= i <= MAX_INDEX):
            raise DSLError("variable index must be an integer in [0, 2147483647]")
        if i >= len(ctx):
            raise DSLError(f"variable index {i} is out of range (context depth {len(ctx)})")
        return ctx[i]
    if tag == "nat":
        _fields(t, {"tag", "value"}, "term")
        if not isinstance(t["value"], str) or not NAT_RE.match(t["value"]):
            raise DSLError("nat value must be a canonical unsigned decimal string")
        return "Nat"
    if tag == "bool":
        _fields(t, {"tag", "value"}, "term")
        if not isinstance(t["value"], bool):
            raise DSLError("bool value must be a JSON Boolean")
        return "Bool"
    if tag == "unit":
        _fields(t, {"tag"}, "term")
        return "Unit"
    if tag == "enum":
        _fields(t, {"tag", "sort", "constructor"}, "term")
        e = profile.enums.get(t["sort"])
        if e is None:
            raise DSLError(f"unknown enumeration {t['sort']!r}")
        if t["constructor"] not in e["constructors"]:
            raise DSLError(f"{t['constructor']!r} is not a constructor of {t['sort']}")
        return {"enum": t["sort"]}
    if tag in NAT_OPS:
        _fields(t, {"tag", "left", "right"}, "term")
        for side in ("left", "right"):
            if type_term(t[side], ctx, profile, budget, depth + 1) != "Nat":
                raise DSLError(f"{tag} operands must be Nat")
        return "Nat"
    if tag == "call":
        _fields(t, {"tag", "symbol", "args"}, "term")
        sym = profile.symbols.get(t["symbol"])
        if sym is None:
            raise DSLError(f"unknown symbol {t['symbol']!r}")
        if not isinstance(t["args"], list) or len(t["args"]) != len(sym["args"]):
            raise DSLError(f"{t['symbol']} expects {len(sym['args'])} arguments")
        for a, s in zip(t["args"], sym["args"]):
            if not sort_eq(type_term(a, ctx, profile, budget, depth + 1), s):
                raise DSLError(f"argument sort mismatch in call to {t['symbol']} (no coercions)")
        return sym["result"]
    if tag == "ok":
        _fields(t, {"tag", "error_sort", "value"}, "term")
        check_sort(t["error_sort"], profile)
        return {"result": {"error": t["error_sort"], "ok": type_term(t["value"], ctx, profile, budget, depth + 1)}}
    if tag == "error":
        _fields(t, {"tag", "ok_sort", "value"}, "term")
        check_sort(t["ok_sort"], profile)
        return {"result": {"error": type_term(t["value"], ctx, profile, budget, depth + 1), "ok": t["ok_sort"]}}
    raise DSLError(f"unknown term tag {tag!r}")


def type_formula(p: Any, ctx: list[Sort], profile: Profile, budget: _Budget | None = None, depth: int = 0) -> None:
    budget = budget or _Budget()
    budget.tick(depth)
    if not isinstance(p, dict) or "tag" not in p:
        raise DSLError("formula must be an object with a tag")
    tag = p["tag"]
    if tag in ("true", "false"):
        _fields(p, {"tag"}, "formula")
    elif tag in RELATIONS:
        _fields(p, {"tag", "left", "right"}, "formula")
        a = type_term(p["left"], ctx, profile, budget, depth + 1)
        b = type_term(p["right"], ctx, profile, budget, depth + 1)
        if tag == "eq":
            if not sort_eq(a, b):
                raise DSLError("eq requires equal operand sorts")
        elif a != "Nat" or b != "Nat":
            raise DSLError(f"{tag} requires Nat operands")
    elif tag == "holds":
        _fields(p, {"tag", "term"}, "formula")
        if type_term(p["term"], ctx, profile, budget, depth + 1) != "Bool":
            raise DSLError("holds requires a Bool term")
    elif tag == "not":
        _fields(p, {"tag", "body"}, "formula")
        type_formula(p["body"], ctx, profile, budget, depth + 1)
    elif tag in CONNECTIVES:
        _fields(p, {"tag", "left", "right"}, "formula")
        type_formula(p["left"], ctx, profile, budget, depth + 1)
        type_formula(p["right"], ctx, profile, budget, depth + 1)
    elif tag in QUANTIFIERS:
        _fields(p, {"tag", "sort", "body"}, "formula")
        check_sort(p["sort"], profile)
        type_formula(p["body"], [p["sort"]] + ctx, profile, budget, depth + 1)
    elif tag in RANGE_QUANTIFIERS:
        _fields(p, {"tag", "lower", "upper", "body"}, "formula")
        for side in ("lower", "upper"):
            if type_term(p[side], ctx, profile, budget, depth + 1) != "Nat":
                raise DSLError(f"{tag} bounds must be Nat terms of the outer context")
        type_formula(p["body"], ["Nat"] + ctx, profile, budget, depth + 1)
    else:
        raise DSLError(f"unknown formula tag {tag!r}")


def make_package(formula: dict[str, Any], profile_id: str) -> dict[str, Any]:
    return {"encoding": ENCODING, "semantic_profile": profile_id, "formula": formula}


def check_package(pkg: Any, profile: Profile) -> None:
    _fields(pkg, {"encoding", "semantic_profile", "formula"}, "formula package")
    if pkg["encoding"] != ENCODING:
        raise DSLError(f"unsupported encoding {pkg['encoding']!r}")
    if pkg["semantic_profile"] != profile.profile_id:
        raise DSLError("formula package names a different semantic profile")
    type_formula(pkg["formula"], [], profile)


def encode(pkg: dict[str, Any]) -> bytes:
    return canonical.dumps(pkg)


def decode(data: bytes, profile: Profile) -> dict[str, Any]:
    if len(data) > LIMITS["max_bytes"]:
        raise DSLError("byte limit exceeded")
    pkg = canonical.loads(data)
    check_package(pkg, profile)
    return pkg


def round_trip_ok(pkg: dict[str, Any], profile: Profile) -> bool:
    data = encode(pkg)
    return encode(decode(data, profile)) == data and decode(data, profile) == pkg


def calls(p: Any) -> set[str]:
    out: set[str] = set()
    stack = [p]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            if x.get("tag") == "call":
                out.add(x["symbol"])
            stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
        elif isinstance(x, list):
            stack.extend(x)
    return out


def prefix(p: dict[str, Any]) -> tuple[list[Sort], dict[str, Any]]:
    """Split a leading run of universal quantifiers off a formula."""
    sorts: list[Sort] = []
    while p["tag"] == "forall":
        sorts.append(p["sort"])
        p = p["body"]
    return sorts, p


def is_existential_shape(p: dict[str, Any]) -> bool:
    if p["tag"] in ("exists", "exists_range"):
        return True
    if p["tag"] == "and":
        return is_existential_shape(p["left"]) and is_existential_shape(p["right"])
    return False


def render(p: Any, names: list[str] | None = None) -> str:
    """Human display; never used for identity."""
    names = names or []

    def fresh() -> str:
        return f"x{len(names)}"

    def term(t: dict[str, Any], ns: list[str]) -> str:
        tag = t["tag"]
        if tag == "var":
            return ns[t["index"]] if t["index"] < len(ns) else f"#{t['index']}"
        if tag == "nat":
            return t["value"]
        if tag == "bool":
            return "true" if t["value"] else "false"
        if tag == "unit":
            return "()"
        if tag == "enum":
            return f"{t['sort']}.{t['constructor']}"
        if tag in NAT_OPS:
            op = {"add": "+", "sub": "-", "mul": "*"}[tag]
            return f"({term(t['left'], ns)} {op} {term(t['right'], ns)})"
        if tag == "call":
            return f"{t['symbol']}({', '.join(term(a, ns) for a in t['args'])})"
        return f"{tag}({term(t['value'], ns)})"

    def form(q: dict[str, Any], ns: list[str]) -> str:
        tag = q["tag"]
        if tag in ("true", "false"):
            return tag
        if tag in RELATIONS:
            op = {"eq": "=", "lt": "<", "le": "≤"}[tag]
            return f"{term(q['left'], ns)} {op} {term(q['right'], ns)}"
        if tag == "holds":
            return f"{term(q['term'], ns)} = true"
        if tag == "not":
            return f"¬({form(q['body'], ns)})"
        if tag in CONNECTIVES:
            op = {"and": "∧", "or": "∨", "implies": "→", "iff": "↔"}[tag]
            return f"({form(q['left'], ns)} {op} {form(q['right'], ns)})"
        if tag in QUANTIFIERS:
            v = f"x{len(ns)}"
            sym = "∀" if tag == "forall" else "∃"
            return f"{sym} {v} : {sort_str(q['sort'])}, {form(q['body'], [v] + ns)}"
        v = f"x{len(ns)}"
        sym = "∀" if tag == "forall_range" else "∃"
        return f"{sym} {v} ∈ [{term(q['lower'], ns)}, {term(q['upper'], ns)}), {form(q['body'], [v] + ns)}"

    return form(p, names)


# ------------------------------------------------------------------------------------------
# values and evaluation
# ------------------------------------------------------------------------------------------

UNIT = ("unit",)


def ok(v: Any) -> tuple:
    return ("ok", v)


def err(v: Any) -> tuple:
    return ("error", v)


def enum_v(eid: str, ctor: str) -> tuple:
    return ("enum", eid, ctor)


def finite_values(s: Sort, profile: Profile) -> list[Any]:
    if s == "Bool":
        return [False, True]
    if s == "Unit":
        return [UNIT]
    if "enum" in s:
        return [enum_v(s["enum"], c) for c in profile.enums[s["enum"]]["constructors"]]
    r = s["result"]
    return [err(v) for v in finite_values(r["error"], profile)] + [ok(v) for v in finite_values(r["ok"], profile)]


def value_has_sort(v: Any, s: Sort, profile: Profile) -> bool:
    if s == "Nat":
        return type(v) is int and v >= 0
    if s == "Bool":
        return type(v) is bool
    if s == "Unit":
        return v == UNIT
    if "enum" in s:
        return isinstance(v, tuple) and len(v) == 3 and v[0] == "enum" and v[1] == s["enum"] and v[2] in profile.enums[s["enum"]]["constructors"]
    r = s["result"]
    if isinstance(v, tuple) and len(v) == 2 and v[0] == "ok":
        return value_has_sort(v[1], r["ok"], profile)
    if isinstance(v, tuple) and len(v) == 2 and v[0] == "error":
        return value_has_sort(v[1], r["error"], profile)
    return False


class TargetFault(Exception):
    """A bound implementation raised, timed out, or returned a value outside the profile."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind  # exception | malformed | timeout
        self.detail = detail


class BudgetExceeded(Exception):
    pass


@dataclass(frozen=True)
class Truth:
    value: bool | None  # None = UNKNOWN
    exact: bool         # False when a Nat quantifier was approximated by samples

    def __str__(self) -> str:
        v = {True: "TRUE", False: "FALSE", None: "UNKNOWN"}[self.value]
        return v if self.exact or self.value is None else v + "(sampled)"


T_EXACT = Truth(True, True)
F_EXACT = Truth(False, True)
UNKNOWN = Truth(None, False)


def t_not(a: Truth) -> Truth:
    return a if a.value is None else Truth(not a.value, a.exact)


def t_and(a: Truth, b: Truth) -> Truth:
    if a.value is False or b.value is False:
        exact = (a.value is False and a.exact) or (b.value is False and b.exact)
        return Truth(False, exact)
    if a.value is True and b.value is True:
        return Truth(True, a.exact and b.exact)
    return UNKNOWN


def t_or(a: Truth, b: Truth) -> Truth:
    return t_not(t_and(t_not(a), t_not(b)))


def t_iff(a: Truth, b: Truth) -> Truth:
    if a.value is None or b.value is None:
        return UNKNOWN
    return Truth(a.value == b.value, a.exact and b.exact)


NatCandidates = Callable[[dict[str, Any], list[Any]], Iterable[int]]


class Evaluator:
    """Evaluate formulas with bound symbol implementations.

    `nat_candidates(body, env)` supplies sampled values for quantifiers over Nat. A universal
    over sampled values is at best TRUE(sampled); an existential without a found witness is
    UNKNOWN, never FALSE. Range quantifiers are enumerated exactly up to `range_limit`.
    """

    def __init__(self, profile: Profile, symbols: dict[str, Callable[[list[Any]], Any]],
                 nat_candidates: NatCandidates, step_budget: int = 200_000, range_limit: int = 4096) -> None:
        self.profile = profile
        self.symbols = symbols
        self.nat_candidates = nat_candidates
        self.steps = step_budget
        self.range_limit = range_limit

    def _tick(self) -> None:
        self.steps -= 1
        if self.steps < 0:
            raise BudgetExceeded("evaluation step budget exhausted")

    def term(self, t: dict[str, Any], env: list[Any]) -> Any:
        self._tick()
        tag = t["tag"]
        if tag == "var":
            return env[t["index"]]
        if tag == "nat":
            return int(t["value"])
        if tag == "bool":
            return t["value"]
        if tag == "unit":
            return UNIT
        if tag == "enum":
            return enum_v(t["sort"], t["constructor"])
        if tag in NAT_OPS:
            a, b = self.term(t["left"], env), self.term(t["right"], env)
            return a + b if tag == "add" else (max(0, a - b) if tag == "sub" else a * b)
        if tag == "call":
            args = [self.term(a, env) for a in t["args"]]
            fn = self.symbols.get(t["symbol"])
            if fn is None:
                raise BudgetExceeded(f"symbol {t['symbol']} has no executable binding")
            result = fn(args)
            if not value_has_sort(result, self.profile.symbols[t["symbol"]]["result"], self.profile):
                raise TargetFault("malformed", f"{t['symbol']}{tuple(args)} returned {result!r}, outside sort {sort_str(self.profile.symbols[t['symbol']]['result'])}")
            return result
        if tag == "ok":
            return ok(self.term(t["value"], env))
        if tag == "error":
            return err(self.term(t["value"], env))
        raise DSLError(tag)

    def formula(self, p: dict[str, Any], env: list[Any]) -> Truth:
        self._tick()
        tag = p["tag"]
        if tag == "true":
            return T_EXACT
        if tag == "false":
            return F_EXACT
        if tag in RELATIONS:
            a, b = self.term(p["left"], env), self.term(p["right"], env)
            v = a == b if tag == "eq" else (a < b if tag == "lt" else a <= b)
            return T_EXACT if v else F_EXACT
        if tag == "holds":
            return T_EXACT if self.term(p["term"], env) is True else F_EXACT
        if tag == "not":
            return t_not(self.formula(p["body"], env))
        if tag == "and":
            a = self.formula(p["left"], env)
            if a.value is False and a.exact:
                return a
            return t_and(a, self.formula(p["right"], env))
        if tag == "or":
            a = self.formula(p["left"], env)
            if a.value is True and a.exact:
                return a
            return t_or(a, self.formula(p["right"], env))
        if tag == "implies":
            a = self.formula(p["left"], env)
            if a.value is False and a.exact:
                return T_EXACT
            return t_or(t_not(a), self.formula(p["right"], env))
        if tag == "iff":
            return t_iff(self.formula(p["left"], env), self.formula(p["right"], env))
        if tag in QUANTIFIERS:
            universal = tag == "forall"
            s = p["sort"]
            if is_finite(s):
                values, exact = finite_values(s, self.profile), True
            else:
                values, exact = self._sampled(s, p["body"], env), False
            return self._quantify(universal, p["body"], env, values, exact)
        if tag in RANGE_QUANTIFIERS:
            lo, hi = self.term(p["lower"], env), self.term(p["upper"], env)
            if hi - lo > self.range_limit:
                return UNKNOWN
            return self._quantify(tag == "forall_range", p["body"], env, range(lo, max(lo, hi)), True)
        raise DSLError(tag)

    def _sampled(self, s: Sort, body: dict[str, Any], env: list[Any]) -> list[Any]:
        if s == "Nat":
            return list(dict.fromkeys(self.nat_candidates(body, env)))
        r = s["result"]
        out: list[Any] = []
        for side, wrap in (("error", err), ("ok", ok)):
            sub = r[side]
            vals = finite_values(sub, self.profile) if is_finite(sub) else self._sampled(sub, body, env)
            out.extend(wrap(v) for v in vals)
        return out

    def _quantify(self, universal: bool, body: dict[str, Any], env: list[Any], values: Iterable[Any], exact: bool) -> Truth:
        acc = Truth(True, exact) if universal else Truth(False, exact)
        unknown = False
        for v in values:
            r = self.formula(body, [v] + env)
            if universal:
                if r.value is False:
                    return Truth(False, r.exact)
                if r.value is None:
                    unknown = True
                elif not r.exact:
                    acc = Truth(True, False)
            else:
                if r.value is True:
                    return Truth(True, r.exact)
                if r.value is None:
                    unknown = True
        if unknown:
            return UNKNOWN
        if not universal and not exact:
            return UNKNOWN  # no witness among samples proves nothing
        return acc


def nat_hints(body: dict[str, Any], env: list[Any], ev: Evaluator) -> list[int]:
    """Values for the innermost Nat binder suggested by equalities and bounds in `body`.

    Looks for `eq(T, var0)`, `eq(T, ok(var0))`, `eq(T, error(var0))` (either orientation) and
    `le/lt` bounds whose other side does not mention var0, evaluating T in the outer context.
    Hint terms whose evaluation fails are ignored here; the campaign evaluates them again.
    """
    out: list[int] = []

    def mentions0(t: Any, depth: int) -> bool:
        if isinstance(t, dict):
            if t.get("tag") == "var":
                return t["index"] == depth
            return any(mentions0(v, depth) for k, v in t.items() if k != "tag")
        if isinstance(t, list):
            return any(mentions0(x, depth) for x in t)
        return False

    def lower(t: Any, depth: int) -> Any:
        # Remove the binders between the hint site and the quantifier being instantiated.
        if isinstance(t, dict):
            if t.get("tag") == "var":
                if t["index"] < depth:
                    raise ValueError("hint mentions an inner binder")
                return {"tag": "var", "index": t["index"] - depth - 1}
            return {k: lower(v, depth) for k, v in t.items()}
        if isinstance(t, list):
            return [lower(x, depth) for x in t]
        return t

    def value(t: Any, depth: int) -> Any:
        try:
            return ev.term(lower(t, depth), env)
        except (ValueError, TargetFault, BudgetExceeded, KeyError, IndexError):
            return None

    def visit(p: dict[str, Any], depth: int) -> None:
        tag = p["tag"]
        if tag in RELATIONS:
            for x, y in ((p["left"], p["right"]), (p["right"], p["left"])):
                target = None
                if x.get("tag") == "var" and x["index"] == depth:
                    target = "direct"
                elif x.get("tag") in ("ok", "error") and x["value"].get("tag") == "var" and x["value"]["index"] == depth:
                    target = x["tag"]
                if target and not mentions0(y, depth):
                    v = value(y, depth)
                    if target == "direct" and type(v) is int:
                        out.extend([v] if tag == "eq" else [v, max(0, v - 1), v + 1])
                    elif target != "direct" and isinstance(v, tuple) and v[0] == target and type(v[1]) is int:
                        out.append(v[1])
            return
        if tag == "not":
            visit(p["body"], depth)
        elif tag in CONNECTIVES:
            visit(p["left"], depth)
            visit(p["right"], depth)
        elif tag in QUANTIFIERS or tag in RANGE_QUANTIFIERS:
            visit(p["body"], depth + 1)

    visit(body, 0)
    return out
