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
from dataclasses import dataclass, field
from itertools import product
from typing import Any, Callable, Iterable

from . import canonical

ENCODING = "verislop.contract-dsl/0.1"
ENCODING_V2 = "verislop.contract-dsl/0.2"
OPAQUE_ENCODING = "verislop.lean-export-ref/0.1"
ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
NAT_RE = re.compile(r"^(0|[1-9][0-9]*)$")
INT_RE = re.compile(r"^(0|-?[1-9][0-9]*)$")
MAX_INDEX = 2147483647

LIMITS = {"max_bytes": 1 << 20, "max_depth": 256, "max_nodes": 100_000}

NAT_OPS = ("add", "sub", "mul")
INT_OPS = ("int_add", "int_sub", "int_mul")
V2_TAGS = {"int", "string", *INT_OPS, "int_neg", "nat_to_int", "record", "field", "list", "list_cons",
           "list_length", "list_append", "list_reverse", "list_map", "list_filter", "list_sum", "list_foldl",
           "decide", "bool_and", "bool_or", "bool_not", "bool_eq", "string_append", "string_length", "string_is_empty",
           "none", "some", "option_get_or", "option_is_some", "ite", "list_range", "int_fdiv", "int_to_nat",
           "list_get", "list_sort", "list_unique"}
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


def check_sort(s: Any, profile: "Profile", depth: int = 0) -> None:
    if depth > LIMITS["max_depth"]:
        raise DSLError("sort nesting limit exceeded")
    if s in ("Nat", "Bool", "Unit"):
        return
    if s in ("Int", "String") and profile.encoding == ENCODING_V2:
        return
    if isinstance(s, dict) and set(s) == {"list"} and profile.encoding == ENCODING_V2:
        check_sort(s["list"], profile, depth + 1)
        return
    if isinstance(s, dict) and set(s) == {"option"} and profile.encoding == ENCODING_V2:
        check_sort(s["option"], profile, depth + 1)
        if s["option"] == "Unit" or isinstance(s["option"], dict) and "option" in s["option"]:
            raise DSLError("option payload cannot be Unit or another option: Python None would conflate constructors")
        return
    if isinstance(s, dict) and set(s) == {"record"} and profile.encoding == ENCODING_V2:
        if not isinstance(s["record"], str) or s["record"] not in profile.records:
            raise DSLError(f"unknown record {s['record']!r}")
        return
    if isinstance(s, dict) and set(s) == {"enum"}:
        if s["enum"] not in profile.enums:
            raise DSLError(f"unknown enumeration {s['enum']!r}")
        return
    if isinstance(s, dict) and set(s) == {"result"}:
        r = s["result"]
        if not isinstance(r, dict) or set(r) != {"error", "ok"}:
            raise DSLError("result sort must have exactly error and ok")
        check_sort(r["error"], profile, depth + 1)
        check_sort(r["ok"], profile, depth + 1)
        return
    raise DSLError(f"invalid sort {s!r}")


def sort_eq(a: Sort, b: Sort) -> bool:
    return canonical.dumps(a) == canonical.dumps(b)


def is_finite(s: Sort, profile: "Profile | None" = None) -> bool:
    if s in ("Bool", "Unit"):
        return True
    if s in ("Nat", "Int", "String"):
        return False
    if "list" in s:
        return False
    if "option" in s:
        return is_finite(s["option"], profile)
    if "record" in s:
        return profile is not None and all(is_finite(f["sort"], profile) for f in profile.records[s["record"]]["fields"])
    if "enum" in s:
        return True
    return is_finite(s["result"]["error"], profile) and is_finite(s["result"]["ok"], profile)


def sort_str(s: Sort) -> str:
    if isinstance(s, str):
        return s
    if "enum" in s:
        return s["enum"]
    if "record" in s:
        return s["record"]
    if "list" in s:
        return f"List({sort_str(s['list'])})"
    if "option" in s:
        return f"Option({sort_str(s['option'])})"
    return f"Result({sort_str(s['result']['error'])}, {sort_str(s['result']['ok'])})"


@dataclass
class Profile:
    profile_id: str
    enums: dict[str, dict[str, Any]]
    symbols: dict[str, dict[str, Any]]
    predicates: dict[str, dict[str, Any]]
    raw: dict[str, Any]
    records: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def encoding(self) -> str:
        return self.raw.get("dsl", ENCODING)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Profile":
        p = cls(data["profile_id"], data.get("enums", {}), data.get("symbols", {}), data.get("predicates", {}), data,
                data.get("records", {}))
        if p.encoding not in (ENCODING, ENCODING_V2):
            raise DSLError(f"unsupported profile encoding {p.encoding!r}")
        if p.records and p.encoding != ENCODING_V2:
            raise DSLError("records require contract DSL 0.2")
        for eid, e in p.enums.items():
            if not ID_RE.match(eid):
                raise DSLError(f"invalid enumeration ID {eid!r}")
            ctors = e["constructors"]
            if not ctors or len(set(ctors)) != len(ctors) or not all(ID_RE.match(c) for c in ctors):
                raise DSLError(f"enumeration {eid} needs a nonempty list of unique constructor IDs")
        for rid, r in p.records.items():
            if not ID_RE.fullmatch(rid):
                raise DSLError(f"invalid record ID {rid!r}")
            fs = r.get("fields")
            if not isinstance(fs, list) or not 1 <= len(fs) <= 64:
                raise DSLError(f"record {rid} needs 1 to 64 fields")
            names = [f.get("name") for f in fs if isinstance(f, dict)]
            if len(names) != len(fs) or any(not isinstance(n, str) or not ID_RE.fullmatch(n) for n in names) or len(set(names)) != len(names):
                raise DSLError(f"record {rid} needs unique named fields")
            for f in fs:
                check_sort(f["sort"], p)
        def referenced_records(s):
            if isinstance(s, dict):
                if "record" in s:
                    return {s["record"]}
                if "list" in s:
                    return referenced_records(s["list"])
                if "option" in s:
                    return referenced_records(s["option"])
                if "result" in s:
                    return referenced_records(s["result"]["error"]) | referenced_records(s["result"]["ok"])
            return set()
        done = set()
        def acyclic(rid, visiting):
            if rid in done:
                return
            if len(visiting) > LIMITS["max_depth"]:
                raise DSLError("record nesting limit exceeded")
            if rid in visiting:
                raise DSLError("recursive record sorts are unsupported")
            for f in p.records[rid]["fields"]:
                for child in referenced_records(f["sort"]):
                    acyclic(child, visiting | {rid})
            done.add(rid)
        for rid in p.records:
            acyclic(rid, set())
        for sid, s in p.symbols.items():
            if not ID_RE.match(sid):
                raise DSLError(f"invalid symbol ID {sid!r}")
            for a in s["args"]:
                check_sort(a, p)
            check_sort(s["result"], p)
        for pred in p.predicates.values():
            for a in pred["args"]:
                check_sort(a, p)
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
    if tag in V2_TAGS and profile.encoding != ENCODING_V2:
        raise DSLError(f"{tag} requires contract DSL 0.2")
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
    if tag == "int":
        _fields(t, {"tag", "value"}, "term")
        if not isinstance(t["value"], str) or not INT_RE.fullmatch(t["value"]):
            raise DSLError("int value must be a canonical signed decimal string")
        return "Int"
    if tag == "string":
        _fields(t, {"tag", "value"}, "term")
        if not isinstance(t["value"], str) or any(0xD800 <= ord(c) <= 0xDFFF for c in t["value"]):
            raise DSLError("string value must contain Unicode scalar values")
        return "String"
    if tag == "unit":
        _fields(t, {"tag"}, "term")
        return "Unit"
    if tag == "none":
        _fields(t, {"tag", "element_sort"}, "term")
        result = {"option": t["element_sort"]}
        check_sort(result, profile)
        return result
    if tag == "some":
        _fields(t, {"tag", "value"}, "term")
        result = {"option": type_term(t["value"], ctx, profile, budget, depth + 1)}
        check_sort(result, profile)
        return result
    if tag in ("option_get_or", "option_is_some"):
        _fields(t, {"tag", "value", "default"} if tag == "option_get_or" else {"tag", "value"}, "term")
        s = type_term(t["value"], ctx, profile, budget, depth + 1)
        if not isinstance(s, dict) or set(s) != {"option"}:
            raise DSLError(f"{tag} requires an option")
        if tag == "option_is_some":
            return "Bool"
        if not sort_eq(type_term(t["default"], ctx, profile, budget, depth + 1), s["option"]):
            raise DSLError("option_get_or default sort differs from its option payload")
        return s["option"]
    if tag == "ite":
        _fields(t, {"tag", "condition", "then", "else"}, "term")
        if type_term(t["condition"], ctx, profile, budget, depth + 1) != "Bool":
            raise DSLError("ite condition must be Bool")
        a = type_term(t["then"], ctx, profile, budget, depth + 1)
        b = type_term(t["else"], ctx, profile, budget, depth + 1)
        if not sort_eq(a, b):
            raise DSLError("ite branch sorts must be equal")
        return a
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
    if tag == "int_fdiv":
        _fields(t, {"tag", "left", "right"}, "term")
        if any(type_term(t[side], ctx, profile, budget, depth + 1) != "Int" for side in ("left", "right")):
            raise DSLError("int_fdiv operands must be Int")
        return "Int"
    if tag in INT_OPS or tag in ("string_append", "bool_and", "bool_or", "bool_eq"):
        _fields(t, {"tag", "left", "right"}, "term")
        a = type_term(t["left"], ctx, profile, budget, depth + 1)
        b = type_term(t["right"], ctx, profile, budget, depth + 1)
        wanted = "Int" if tag in INT_OPS else "String" if tag == "string_append" else "Bool"
        if tag == "bool_eq":
            if not sort_eq(a, b) or a not in ("Nat", "Int", "String", "Bool", "Unit"):
                raise DSLError("bool_eq requires equal primitive scalar sorts")
            return "Bool"
        if a != wanted or b != wanted:
            raise DSLError(f"{tag} operands must be {wanted}")
        return wanted
    if tag in ("int_neg", "bool_not"):
        _fields(t, {"tag", "value"}, "term")
        wanted = "Int" if tag == "int_neg" else "Bool"
        if type_term(t["value"], ctx, profile, budget, depth + 1) != wanted:
            raise DSLError(f"{tag} operand must be {wanted}")
        return wanted
    if tag == "nat_to_int":
        _fields(t, {"tag", "value"}, "term")
        if type_term(t["value"], ctx, profile, budget, depth + 1) != "Nat":
            raise DSLError("nat_to_int operand must be Nat")
        return "Int"
    if tag == "int_to_nat":
        _fields(t, {"tag", "value"}, "term")
        if type_term(t["value"], ctx, profile, budget, depth + 1) != "Int":
            raise DSLError("int_to_nat operand must be Int")
        return "Nat"
    if tag == "list_range":
        _fields(t, {"tag", "stop"}, "term")
        if type_term(t["stop"], ctx, profile, budget, depth + 1) != "Nat":
            raise DSLError("list_range stop must be Nat")
        return {"list": "Nat"}
    if tag in ("string_length", "string_is_empty"):
        _fields(t, {"tag", "value"}, "term")
        if type_term(t["value"], ctx, profile, budget, depth + 1) != "String":
            raise DSLError(f"{tag} requires a String")
        return "Nat" if tag == "string_length" else "Bool"
    if tag == "record":
        _fields(t, {"tag", "sort", "fields"}, "term")
        check_sort({"record": t["sort"]}, profile)
        fs = profile.records[t["sort"]]["fields"]
        if not isinstance(t["fields"], list) or len(t["fields"]) != len(fs):
            raise DSLError("record constructor field count mismatch")
        for value, f in zip(t["fields"], fs):
            if not sort_eq(type_term(value, ctx, profile, budget, depth + 1), f["sort"]):
                raise DSLError(f"record field {f['name']} sort mismatch")
        return {"record": t["sort"]}
    if tag == "field":
        _fields(t, {"tag", "sort", "field", "value"}, "term")
        check_sort({"record": t["sort"]}, profile)
        if not sort_eq(type_term(t["value"], ctx, profile, budget, depth + 1), {"record": t["sort"]}):
            raise DSLError("projection record sort mismatch")
        fs = [f for f in profile.records[t["sort"]]["fields"] if f["name"] == t["field"]]
        if len(fs) != 1:
            raise DSLError(f"unknown record field {t['field']!r}")
        return fs[0]["sort"]
    if tag == "list":
        _fields(t, {"tag", "element_sort", "items"}, "term")
        check_sort(t["element_sort"], profile)
        if not isinstance(t["items"], list):
            raise DSLError("list items must be an array")
        for value in t["items"]:
            if not sort_eq(type_term(value, ctx, profile, budget, depth + 1), t["element_sort"]):
                raise DSLError("list element sort mismatch")
        return {"list": t["element_sort"]}
    if tag in ("list_cons", "list_append"):
        _fields(t, {"tag", "head", "tail"} if tag == "list_cons" else {"tag", "left", "right"}, "term")
        a = type_term(t["head" if tag == "list_cons" else "left"], ctx, profile, budget, depth + 1)
        b = type_term(t["tail" if tag == "list_cons" else "right"], ctx, profile, budget, depth + 1)
        if not isinstance(b, dict) or set(b) != {"list"} or not sort_eq(a, b["list"] if tag == "list_cons" else b):
            raise DSLError(f"{tag} list sort mismatch")
        return b
    if tag in ("list_get", "list_sort", "list_unique"):
        _fields(t, {"tag", "value", "index"} if tag == "list_get" else {"tag", "value"}, "term")
        s = type_term(t["value"], ctx, profile, budget, depth + 1)
        if not isinstance(s, dict) or set(s) != {"list"}:
            raise DSLError(f"{tag} requires a list")
        if tag == "list_get":
            if type_term(t["index"], ctx, profile, budget, depth + 1) != "Nat":
                raise DSLError("list_get index must be Nat")
            result = {"option": s["list"]}
            check_sort(result, profile)
            return result
        admitted = ("Nat", "Int", "String") if tag == "list_sort" else ("Nat", "Int", "String", "Bool")
        if s["list"] not in admitted:
            raise DSLError(f"{tag} requires elements in {admitted}")
        return s
    if tag in ("list_length", "list_reverse", "list_sum", "list_map", "list_filter"):
        _fields(t, {"tag", "value", "function"} if tag in ("list_map", "list_filter") else {"tag", "value"}, "term")
        s = type_term(t["value"], ctx, profile, budget, depth + 1)
        if not isinstance(s, dict) or set(s) != {"list"}:
            raise DSLError(f"{tag} requires a list")
        if tag == "list_length":
            return "Nat"
        if tag == "list_reverse":
            return s
        if tag == "list_sum":
            if s["list"] not in ("Nat", "Int"):
                raise DSLError("list_sum requires Nat or Int elements")
            return s["list"]
        fn = t["function"]
        _fields(fn, {"sort", "body"}, "lambda")
        if not sort_eq(fn["sort"], s["list"]):
            raise DSLError("lambda binder sort differs from list element sort")
        result = type_term(fn["body"], [fn["sort"]] + ctx, profile, budget, depth + 1)
        if tag == "list_filter":
            if result != "Bool":
                raise DSLError("list_filter lambda must return Bool")
            return s
        return {"list": result}
    if tag == "list_foldl":
        _fields(t, {"tag", "value", "initial", "function"}, "term")
        s = type_term(t["value"], ctx, profile, budget, depth + 1)
        if not isinstance(s, dict) or set(s) != {"list"}:
            raise DSLError("list_foldl requires a list")
        initial = type_term(t["initial"], ctx, profile, budget, depth + 1)
        fn = t["function"]
        _fields(fn, {"accumulator_sort", "element_sort", "body"}, "fold lambda")
        check_sort(fn["accumulator_sort"], profile)
        check_sort(fn["element_sort"], profile)
        if not sort_eq(fn["accumulator_sort"], initial) or not sort_eq(fn["element_sort"], s["list"]):
            raise DSLError("fold lambda binder sorts differ from accumulator or list element sort")
        result = type_term(fn["body"], [fn["element_sort"], fn["accumulator_sort"]] + ctx,
                           profile, budget, depth + 1)
        if not sort_eq(result, initial):
            raise DSLError("list_foldl lambda must return the accumulator sort")
        return initial
    if tag == "decide":
        _fields(t, {"tag", "formula"}, "term")
        type_formula(t["formula"], ctx, profile, budget, depth + 1)
        if not decidable_shape(t["formula"], ctx, profile, budget, depth + 1):
            raise DSLError("decide requires a quantifier-free formula over primitive scalar sorts")
        return "Bool"
    if tag == "call":
        _fields(t, {"tag", "symbol", "args"}, "term")
        sym = profile.symbols.get(t["symbol"])
        if sym is None:
            raise DSLError(f"unknown symbol {t['symbol']!r}")
        check_sort(sym["result"], profile)
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
        elif a not in ("Nat", "Int", "String") or a != b:
            raise DSLError(f"{tag} requires matching Nat, Int or String operands")
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


def decidable_shape(p: dict[str, Any], ctx: list[Sort], profile: Profile,
                    budget: _Budget | None = None, depth: int = 0) -> bool:
    budget = budget or _Budget()
    budget.tick(depth)
    tag = p["tag"]
    if tag in ("true", "false", "holds"):
        return True
    if tag in RELATIONS:
        return type_term(p["left"], ctx, profile, budget, depth + 1) in ("Nat", "Int", "Bool", "String", "Unit")
    if tag == "not":
        return decidable_shape(p["body"], ctx, profile, budget, depth + 1)
    if tag in CONNECTIVES:
        return (decidable_shape(p["left"], ctx, profile, budget, depth + 1)
                and decidable_shape(p["right"], ctx, profile, budget, depth + 1))
    return False


def make_package(formula: dict[str, Any], profile_id: str, *, encoding: str = ENCODING) -> dict[str, Any]:
    return {"encoding": encoding, "semantic_profile": profile_id, "formula": formula}


def check_package(pkg: Any, profile: Profile) -> None:
    _fields(pkg, {"encoding", "semantic_profile", "formula"}, "formula package")
    if pkg["encoding"] not in (ENCODING, ENCODING_V2):
        raise DSLError(f"unsupported encoding {pkg['encoding']!r}")
    if pkg["semantic_profile"] != profile.profile_id:
        raise DSLError("formula package names a different semantic profile")
    selected = profile
    if pkg["encoding"] == ENCODING and profile.encoding == ENCODING_V2:
        # A v0.1 package cannot smuggle v0.2 nodes or sorts through a newer registry.
        raw = {**profile.raw, "dsl": ENCODING, "records": {}}
        selected = Profile(profile.profile_id, profile.enums, profile.symbols, profile.predicates, raw)
    type_formula(pkg["formula"], [], selected)


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
        if tag == "int":
            return t["value"]
        if tag == "string":
            return repr(t["value"])
        if tag == "bool":
            return "true" if t["value"] else "false"
        if tag == "unit":
            return "()"
        if tag == "none":
            return f"none : {sort_str(t['element_sort'])}"
        if tag == "ite":
            return f"if {term(t['condition'], ns)} then {term(t['then'], ns)} else {term(t['else'], ns)}"
        if tag == "option_get_or":
            return f"getD({term(t['value'], ns)}, {term(t['default'], ns)})"
        if tag == "list_range":
            return f"range({term(t['stop'], ns)})"
        if tag == "list_get":
            return f"{term(t['value'], ns)}[{term(t['index'], ns)}]?"
        if tag == "int_fdiv":
            return f"fdiv({term(t['left'], ns)}, {term(t['right'], ns)})"
        if tag == "enum":
            return f"{t['sort']}.{t['constructor']}"
        if tag in NAT_OPS:
            op = {"add": "+", "sub": "-", "mul": "*"}[tag]
            return f"({term(t['left'], ns)} {op} {term(t['right'], ns)})"
        if tag in INT_OPS or tag in ("bool_and", "bool_or", "bool_eq", "string_append", "list_append"):
            op = {"int_add": "+", "int_sub": "-", "int_mul": "*", "bool_and": "&&", "bool_or": "||",
                  "bool_eq": "==", "string_append": "++", "list_append": "++"}[tag]
            return f"({term(t['left'], ns)} {op} {term(t['right'], ns)})"
        if tag == "record":
            return f"{t['sort']}({', '.join(term(x, ns) for x in t['fields'])})"
        if tag == "field":
            return f"{term(t['value'], ns)}.{t['field']}"
        if tag == "list":
            return "[" + ", ".join(term(x, ns) for x in t["items"]) + "]"
        if tag == "list_cons":
            return f"({term(t['head'], ns)} :: {term(t['tail'], ns)})"
        if tag in ("list_map", "list_filter"):
            v = f"x{len(ns)}"
            return f"{tag}({term(t['value'], ns)}, fun {v} => {term(t['function']['body'], [v] + ns)})"
        if tag == "list_foldl":
            acc, elem = f"x{len(ns)}", f"x{len(ns) + 1}"
            body = term(t["function"]["body"], [elem, acc] + ns)
            return f"list_foldl({term(t['value'], ns)}, {term(t['initial'], ns)}, fun {acc} {elem} => {body})"
        if tag == "decide":
            return f"decide({form(t['formula'], ns)})"
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


def record_v(rid: str, values: Iterable[Any]) -> tuple:
    return ("record", rid, tuple(values))


OPTION_NONE = ("none",)


def option_none_v() -> tuple:
    return OPTION_NONE


def option_some_v(value: Any) -> tuple:
    return ("some", value)


def finite_values(s: Sort, profile: Profile) -> list[Any]:
    if s == "Bool":
        return [False, True]
    if s == "Unit":
        return [UNIT]
    if not is_finite(s, profile):
        raise DSLError(f"sort {sort_str(s)} has no finite enumeration")
    if "enum" in s:
        return [enum_v(s["enum"], c) for c in profile.enums[s["enum"]]["constructors"]]
    if "option" in s:
        return [OPTION_NONE, *(option_some_v(v) for v in finite_values(s["option"], profile))]
    if "record" in s:
        fs = [finite_values(f["sort"], profile) for f in profile.records[s["record"]]["fields"]]
        size = 1
        for values in fs:
            size *= len(values)
            if size > 4096:
                raise BudgetExceeded("finite record enumeration exceeds 4096 values")
        return [record_v(s["record"], values) for values in product(*fs)]
    r = s["result"]
    return [err(v) for v in finite_values(r["error"], profile)] + [ok(v) for v in finite_values(r["ok"], profile)]


def value_has_sort(v: Any, s: Sort, profile: Profile) -> bool:
    if s == "Nat":
        return type(v) is int and v >= 0
    if s == "Bool":
        return type(v) is bool
    if s == "Int":
        return type(v) is int
    if s == "String":
        return type(v) is str and not any(0xD800 <= ord(c) <= 0xDFFF for c in v)
    if s == "Unit":
        return v == UNIT
    if "option" in s:
        return (type(v) is tuple and (v == OPTION_NONE or
                len(v) == 2 and v[0] == "some" and value_has_sort(v[1], s["option"], profile)))
    if "list" in s:
        return type(v) is tuple and all(value_has_sort(x, s["list"], profile) for x in v)
    if "record" in s:
        fs = profile.records[s["record"]]["fields"]
        return (type(v) is tuple and len(v) == 3 and v[:2] == ("record", s["record"])
                and type(v[2]) is tuple and len(v[2]) == len(fs)
                and all(value_has_sort(x, f["sort"], profile) for x, f in zip(v[2], fs)))
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
                 nat_candidates: NatCandidates, step_budget: int = 200_000, range_limit: int = 4096,
                 *, sample_candidates: Callable[[Sort, dict[str, Any], list[Any]], Iterable[Any]] | None = None) -> None:
        self.profile = profile
        self.symbols = symbols
        self.nat_candidates = nat_candidates
        self.steps = step_budget
        self.range_limit = range_limit
        self.sample_candidates = sample_candidates

    def _tick(self) -> None:
        self.steps -= 1
        if self.steps < 0:
            raise BudgetExceeded("evaluation step budget exhausted")

    def _charge(self, count: int) -> None:
        if count > self.steps:
            raise BudgetExceeded("evaluation step budget exhausted")
        self.steps -= count

    def _sort_scalars(self, values: tuple) -> tuple:
        """Stable contiguous merge sort; charge traversal and each scalar comparison."""
        self._charge(len(values))
        if len(values) < 2:
            return values
        middle = (len(values) + 1) // 2
        left, right = self._sort_scalars(values[:middle]), self._sort_scalars(values[middle:])
        i, j, merged = 0, 0, []
        while i < len(left) and j < len(right):
            self._tick()
            if left[i] <= right[j]:
                merged.append(left[i])
                i += 1
            else:
                merged.append(right[j])
                j += 1
        merged.extend(left[i:])
        merged.extend(right[j:])
        return tuple(merged)

    def term(self, t: dict[str, Any], env: list[Any]) -> Any:
        self._tick()
        tag = t["tag"]
        if tag == "var":
            return env[t["index"]]
        if tag == "nat":
            return int(t["value"])
        if tag == "int":
            return int(t["value"])
        if tag == "string":
            return t["value"]
        if tag == "bool":
            return t["value"]
        if tag == "unit":
            return UNIT
        if tag == "none":
            return OPTION_NONE
        if tag == "some":
            return option_some_v(self.term(t["value"], env))
        if tag in ("option_get_or", "option_is_some"):
            value = self.term(t["value"], env)
            if tag == "option_is_some":
                return value != OPTION_NONE
            return self.term(t["default"], env) if value == OPTION_NONE else value[1]
        if tag == "ite":
            condition = self.term(t["condition"], env)
            return self.term(t["then"] if condition is True else t["else"], env)
        if tag == "int_fdiv":
            a, b = self.term(t["left"], env), self.term(t["right"], env)
            return a // b if b else 0
        if tag == "int_to_nat":
            return max(0, self.term(t["value"], env))
        if tag == "list_range":
            stop = self.term(t["stop"], env)
            if stop > self.range_limit:
                raise BudgetExceeded("list_range exceeds enumeration limit")
            if stop > self.steps:
                raise BudgetExceeded("list_range exceeds remaining evaluation step budget")
            self.steps -= stop
            return tuple(range(stop))
        if tag == "enum":
            return enum_v(t["sort"], t["constructor"])
        if tag in NAT_OPS:
            a, b = self.term(t["left"], env), self.term(t["right"], env)
            return a + b if tag == "add" else (max(0, a - b) if tag == "sub" else a * b)
        if tag in INT_OPS:
            a, b = self.term(t["left"], env), self.term(t["right"], env)
            return a + b if tag == "int_add" else a - b if tag == "int_sub" else a * b
        if tag == "int_neg":
            return -self.term(t["value"], env)
        if tag == "nat_to_int":
            # Both mathematical domains use exact Python integers; the checked Nat operand
            # is nonnegative. This operator does not coerce other host value types.
            return self.term(t["value"], env)
        if tag == "string_append":
            a, b = self.term(t["left"], env), self.term(t["right"], env)
            for _ in range(len(a) + len(b)):
                self._tick()
            return a + b
        if tag in ("string_length", "string_is_empty"):
            value = self.term(t["value"], env)
            self._tick()
            return len(value) if tag == "string_length" else value == ""
        if tag in ("bool_and", "bool_or", "bool_eq"):
            a = self.term(t["left"], env)
            if tag == "bool_and" and a is False:
                return False
            if tag == "bool_or" and a is True:
                return True
            b = self.term(t["right"], env)
            return b if tag in ("bool_and", "bool_or") else a == b
        if tag == "bool_not":
            return not self.term(t["value"], env)
        if tag == "decide":
            truth = self.formula(t["formula"], env)
            if truth.value is None or not truth.exact:
                raise BudgetExceeded("decide did not evaluate exactly")
            return truth.value
        if tag == "record":
            return record_v(t["sort"], (self.term(x, env) for x in t["fields"]))
        if tag == "field":
            v = self.term(t["value"], env)
            fields = self.profile.records[t["sort"]]["fields"]
            return v[2][next(i for i, f in enumerate(fields) if f["name"] == t["field"])]
        if tag == "list":
            return tuple(self.term(x, env) for x in t["items"])
        if tag == "list_cons":
            return (self.term(t["head"], env),) + self.term(t["tail"], env)
        if tag == "list_append":
            a, b = self.term(t["left"], env), self.term(t["right"], env)
            for _ in a:
                self._tick()
            return a + b
        if tag == "list_get":
            values, index = self.term(t["value"], env), self.term(t["index"], env)
            self._charge(min(index + 1, len(values)))
            return option_some_v(values[index]) if index < len(values) else OPTION_NONE
        if tag == "list_sort":
            return self._sort_scalars(self.term(t["value"], env))
        if tag == "list_unique":
            out = []
            for value in self.term(t["value"], env):
                self._tick()
                seen = False
                for previous in reversed(out):
                    self._tick()
                    if previous == value:
                        seen = True
                        break
                if not seen:
                    out.append(value)
            return tuple(out)
        if tag in ("list_length", "list_reverse", "list_map", "list_filter", "list_sum"):
            values = self.term(t["value"], env)
            if tag == "list_length":
                for _ in values:
                    self._tick()
                return len(values)
            if tag == "list_reverse":
                for _ in values:
                    self._tick()
                return tuple(reversed(values))
            if tag == "list_sum":
                result = 0
                for v in values:
                    self._tick()
                    result += v
                return result
            out = []
            for v in values:
                self._tick()
                result = self.term(t["function"]["body"], [v] + env)
                if tag == "list_map":
                    out.append(result)
                elif result is True:
                    out.append(v)
            return tuple(out)
        if tag == "list_foldl":
            values = self.term(t["value"], env)
            result = self.term(t["initial"], env)
            for value in values:
                self._tick()
                result = self.term(t["function"]["body"], [value, result] + env)
            return result
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
            if is_finite(s, self.profile):
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
        if self.sample_candidates is not None:
            values = list(dict.fromkeys(self.sample_candidates(s, body, env)))
            if not all(value_has_sort(v, s, self.profile) for v in values):
                raise DSLError("sample callback produced a value outside its requested sort")
            return values
        if s == "Nat":
            return list(dict.fromkeys(self.nat_candidates(body, env)))
        if s == "Int":
            ns = list(self.nat_candidates(body, env))
            return list(dict.fromkeys([0, *ns, *(-n for n in ns)]))
        if s == "String":
            return ["", "a", "λ", "🙂"]
        if "option" in s:
            sub = s["option"]
            values = finite_values(sub, self.profile) if is_finite(sub, self.profile) else self._sampled(sub, body, env)
            return [OPTION_NONE, *(option_some_v(v) for v in values)]
        if "list" in s:
            sub = s["list"]
            values = finite_values(sub, self.profile) if is_finite(sub, self.profile) else self._sampled(sub, body, env)
            return [(), *((v,) for v in values[:8]), tuple(values[:3])]
        if "record" in s:
            fs = self.profile.records[s["record"]]["fields"]
            values = [finite_values(f["sort"], self.profile) if is_finite(f["sort"], self.profile)
                      else self._sampled(f["sort"], body, env) for f in fs]
            if any(not xs for xs in values):
                return []
            return [record_v(s["record"], [xs[i % len(xs)] for xs in values]) for i in range(max(len(xs) for xs in values))]
        r = s["result"]
        out: list[Any] = []
        for side, wrap in (("error", err), ("ok", ok)):
            sub = r[side]
            vals = finite_values(sub, self.profile) if is_finite(sub, self.profile) else self._sampled(sub, body, env)
            out.extend(wrap(v) for v in vals)
        return out

    def _quantify(self, universal: bool, body: dict[str, Any], env: list[Any], values: Iterable[Any], exact: bool) -> Truth:
        acc = Truth(True, exact) if universal else Truth(False, exact)
        unknown = False
        for v in values:
            r = self.formula(body, [v] + env)
            if r.value is None or not r.exact:
                # A finite outer domain does not make an approximate inner result exact.
                # Keep looking: an exact witness/counterexample in another branch may still
                # settle the quantifier. Otherwise exhaustion is UNKNOWN.
                unknown = True
                continue
            if universal:
                if r.value is False:
                    return F_EXACT
            else:
                if r.value is True:
                    return T_EXACT
        if unknown:
            return UNKNOWN
        if universal and not exact and self.profile.encoding == ENCODING_V2:
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
