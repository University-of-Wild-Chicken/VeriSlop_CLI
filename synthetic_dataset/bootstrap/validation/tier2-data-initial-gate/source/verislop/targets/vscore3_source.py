"""VSCore 0.3 host proposals, closed canonical JSON and Lean literals.

This frontend is not a trusted parser or checker. Certificates must independently prove
``VSCore3.parseSource deliveredBytes = .ok program`` and replay Lean admission.
The optional surface frontend emits delivered JSON; it does not certify the .vsc text.
"""
from __future__ import annotations

import json
import re
from collections import deque
from typing import Any

from . import vscore_source as old

LANGUAGE = "vscore/0.3"
PROFILE = "data-pipeline/0.3"
SourceError = old.SourceError
MAX_SOURCE_BYTES = old.MAX_SOURCE_BYTES
MAX_NAT_DIGITS = old.MAX_NAT_DIGITS
MAX_SAFE_INTEGER = old.MAX_SAFE_INTEGER
MAX_DECLARATIONS = 1024
MAX_NODES = 65536
FEATURES = ("base", "nominalData", "option", "list", "acyclicCalls", "listFold", "natFold", "int", "string", "pureList")
BIN_OPS = old.BIN_OPS
UNARY_OPS = ("int_neg", "nat_to_int", "int_to_nat", "list_length", "list_range", "list_reverse", "list_sort", "list_unique")
parse_json = old.parse_json
lean_string = old.lean_string
lean_list = old.lean_list


def _shape(j: Any, keys: list[str], where: str) -> dict:
    if not isinstance(j, dict) or list(j) != sorted(keys):
        raise SourceError(f"{where}: unexpected or missing fields")
    return j


def _array(j: Any, where: str) -> list:
    if not isinstance(j, list):
        raise SourceError(f"{where}: expected an array")
    return j


def decode_ty(j: Any, depth: int = 0) -> Any:
    if depth > 256:
        raise SourceError("type nesting exceeds decode budget")
    if isinstance(j, str) and j in ("nat", "int", "bool", "string", "unit"):
        return j
    if isinstance(j, dict) and len(j) == 1:
        tag = next(iter(j))
        if tag in ("enum", "record", "variant"):
            return (tag, old._ident(j[tag]))
        if tag in ("option", "list"):
            return (tag, decode_ty(j[tag], depth + 1))
        if tag == "result":
            r = _shape(j[tag], ["error", "ok"], "result type")
            return (tag, decode_ty(r["error"], depth + 1), decode_ty(r["ok"], depth + 1))
    raise SourceError("invalid type")


_SHAPES = {**old._SHAPES,
    "int": ["tag", "value"], "string": ["tag", "value"],
    **{tag: ["tag", "value"] for tag in UNARY_OPS},
    "int_fdiv": ["left", "right", "tag"],
    "list_get": ["index", "tag", "value"], "list_append": ["left", "right", "tag"],
    "record": ["fields", "record", "tag"], "project": ["field", "tag", "value"],
    "variant": ["args", "ctor", "tag", "variant"],
    "match_variant": ["branches", "scrutinee", "tag"],
    "none": ["element_type", "tag"], "some": ["tag", "value"],
    "match_option": ["none", "scrutinee", "some", "tag"],
    "nil": ["element_type", "tag"], "cons": ["head", "tag", "tail"],
    "match_list": ["cons", "nil", "scrutinee", "tag"],
    "call": ["args", "helper", "tag"],
    "list_fold": ["initial", "source", "step", "tag"],
    "nat_fold": ["initial", "source", "step", "tag"],
}


def _int_literal(value: Any) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]*|-[1-9][0-9]*", value):
        raise SourceError("int: expected a canonical signed decimal string")
    if len(value.removeprefix("-")) > MAX_NAT_DIGITS:
        raise SourceError("int literal exceeds digit budget")
    return int(value)


def _codepoints(value: Any) -> tuple[int, ...]:
    points = _array(value, "string codepoints")
    if len(points) > MAX_NODES:
        raise SourceError("string literal exceeds scalar budget")
    out = []
    for point in points:
        if not isinstance(point, old._Num):
            raise SourceError("string: codepoint must be a canonical integer")
        n = int(point)
        if n > 0x10FFFF or 0xD800 <= n <= 0xDFFF:
            raise SourceError("string: codepoint is not a Unicode scalar")
        out.append(n)
    return tuple(out)


def decode_expr(j: Any, depth: int = 0) -> Any:
    if depth > 256:
        raise SourceError("expression nesting exceeds decode budget")
    if not isinstance(j, dict) or not isinstance(j.get("tag"), str):
        raise SourceError("expression requires a string tag")
    tag = j["tag"]
    if tag not in _SHAPES:
        raise SourceError(f"unsupported expression tag {tag}")
    _shape(j, _SHAPES[tag], tag)
    sub = lambda k: decode_expr(j[k], depth + 1)
    typ = lambda k: decode_ty(j[k], depth + 1)
    args = lambda k: [decode_expr(x, depth + 1) for x in _array(j[k], k)]
    if tag == "var":
        if not isinstance(j["index"], old._Num):
            raise SourceError("var: index must be a canonical integer")
        return (tag, int(j["index"]))
    if tag == "nat":
        return (tag, old._nat_literal(j["value"]))
    if tag == "int":
        return (tag, _int_literal(j["value"]))
    if tag == "string":
        return (tag, _codepoints(j["value"]))
    if tag in UNARY_OPS:
        return (tag, sub("value"))
    if tag in ("int_fdiv", "list_append"):
        return (tag, sub("left"), sub("right"))
    if tag == "list_get":
        return (tag, sub("value"), sub("index"))
    if tag == "bool":
        if not isinstance(j["value"], bool):
            raise SourceError("bool: value must be true or false")
        return (tag, j["value"])
    if tag == "unit":
        return (tag,)
    if tag == "enum":
        return (tag, old._ident(j["enum"]), old._ident(j["ctor"]))
    if tag in BIN_OPS:
        return ("bin", tag, sub("left"), sub("right"))
    if tag == "not":
        return (tag, sub("value"))
    if tag == "if":
        return ("ite", sub("cond"), sub("then"), sub("else"))
    if tag == "let":
        return (tag, sub("value"), sub("body"))
    if tag == "ok":
        return (tag, typ("error_type"), sub("value"))
    if tag == "error":
        return (tag, typ("ok_type"), sub("value"))
    if tag == "match_result":
        return ("match", sub("scrutinee"), sub("ok"), sub("error"))
    if tag == "record":
        fields = []
        for f in _array(j["fields"], "fields"):
            _shape(f, ["id", "value"], "record field")
            fields.append((old._ident(f["id"]), decode_expr(f["value"], depth + 1)))
        return (tag, old._ident(j["record"]), fields)
    if tag == "project":
        return (tag, sub("value"), old._ident(j["field"]))
    if tag == "variant":
        return (tag, old._ident(j["variant"]), old._ident(j["ctor"]), args("args"))
    if tag == "match_variant":
        branches = []
        for b in _array(j["branches"], "branches"):
            _shape(b, ["body", "ctor"], "variant branch")
            branches.append((old._ident(b["ctor"]), decode_expr(b["body"], depth + 1)))
        return (tag, sub("scrutinee"), branches)
    if tag in ("none", "nil"):
        return (tag, typ("element_type"))
    if tag == "some":
        return (tag, sub("value"))
    if tag == "match_option":
        return (tag, sub("scrutinee"), sub("none"), sub("some"))
    if tag == "cons":
        return (tag, sub("head"), sub("tail"))
    if tag == "match_list":
        return (tag, sub("scrutinee"), sub("nil"), sub("cons"))
    if tag == "call":
        return (tag, old._ident(j["helper"]), args("args"))
    return (tag, sub("source"), sub("initial"), sub("step"))


def decode_program(j: Any) -> dict:
    _shape(j, ["declarations", "entries", "helpers", "language", "profile"], "program")
    if j["language"] != LANGUAGE or j["profile"] != PROFILE:
        raise SourceError("unsupported language or profile")
    declarations = []
    for d in _array(j["declarations"], "declarations"):
        if not isinstance(d, dict):
            raise SourceError("declaration must be an object")
        tag = d.get("tag")
        if tag == "record":
            _shape(d, ["fields", "id", "tag"], "record declaration")
            fields = []
            for f in _array(d["fields"], "record fields"):
                _shape(f, ["id", "type"], "field declaration")
                fields.append((old._ident(f["id"]), decode_ty(f["type"])))
            declarations.append({"tag": tag, "id": old._ident(d["id"]), "fields": fields})
        elif tag == "variant":
            _shape(d, ["constructors", "id", "tag"], "variant declaration")
            constructors = []
            for c in _array(d["constructors"], "constructors"):
                _shape(c, ["id", "params"], "constructor declaration")
                constructors.append((old._ident(c["id"]), [decode_ty(t) for t in _array(c["params"], "payload types")]))
            declarations.append({"tag": tag, "id": old._ident(d["id"]), "constructors": constructors})
        else:
            raise SourceError("unsupported declaration tag")
    functions = {}
    for group in ("helpers", "entries"):
        functions[group] = []
        for f in _array(j[group], group):
            _shape(f, ["body", "id", "params", "result"], "function")
            functions[group].append({"id": old._ident(f["id"]),
                "params": [decode_ty(t) for t in _array(f["params"], "parameters")],
                "result": decode_ty(f["result"]), "body": decode_expr(f["body"])})
    return {"language": LANGUAGE, "profile": PROFILE, "declarations": declarations, **functions}


def parse_source(data: bytes) -> dict:
    try:
        return decode_program(parse_json(data))
    except RecursionError:
        raise SourceError("source nesting exceeds the supported depth") from None


def _unique(ids: list[str], where: str) -> None:
    if len(set(ids)) != len(ids):
        raise SourceError(f"duplicate {where} IDs")


def _nominal_refs(t: Any) -> set[str]:
    if isinstance(t, str) or t[0] == "enum":
        return set()
    if t[0] in ("record", "variant"):
        return {t[1]}
    return set().union(*(_nominal_refs(x) for x in t[1:]))


def _acyclic(graph: dict[str, set[str]], where: str) -> None:
    # Kahn's algorithm avoids dependence on Python's recursion depth.
    incoming = {k: 0 for k in graph}
    dependants: dict[str, set[str]] = {k: set() for k in graph}
    for caller, refs in graph.items():
        for target in refs:
            if target not in graph:
                raise SourceError(f"unknown {where} dependency {target}")
            incoming[caller] += 1
            dependants[target].add(caller)
    ready = deque(k for k, n in incoming.items() if n == 0)
    done = 0
    while ready:
        target = ready.popleft()
        done += 1
        for caller in dependants[target]:
            incoming[caller] -= 1
            if incoming[caller] == 0:
                ready.append(caller)
    if done != len(graph):
        raise SourceError(f"cyclic {where} dependencies")


def _validate_enums(enums: dict[str, list[str]]) -> None:
    if not isinstance(enums, dict):
        raise SourceError("accepted enumeration registry must be an object")
    for identifier, constructors in enums.items():
        old._ident(identifier)
        if not isinstance(constructors, list) or not constructors:
            raise SourceError("accepted enumeration needs a nonempty constructor array")
        for constructor in constructors:
            old._ident(constructor)
        _unique(constructors, "enumeration constructor")


def _registry(enums: dict[str, list[str]], prog: dict) -> tuple[dict, dict]:
    _validate_enums(enums)
    declarations = prog["declarations"]
    _unique([d["id"] for d in declarations] + list(enums), "type")
    decls = {d["id"]: d for d in declarations}
    helpers = {f["id"]: f for f in prog["helpers"]}
    return decls, helpers


def _wf(enums: dict, declarations: dict, t: Any) -> bool:
    if isinstance(t, str):
        return t in ("nat", "int", "bool", "string", "unit")
    if not isinstance(t, tuple) or not t:
        return False
    if t[0] == "enum":
        return len(t) == 2 and t[1] in enums
    if t[0] in ("record", "variant"):
        return len(t) == 2 and t[1] in declarations and declarations[t[1]]["tag"] == t[0]
    if t[0] in ("option", "list"):
        return len(t) == 2 and _wf(enums, declarations, t[1])
    if t[0] == "result":
        return len(t) == 3 and all(_wf(enums, declarations, x) for x in t[1:])
    return False


def _children(e: Any) -> list:
    tag = e[0]
    if tag in ("var", "nat", "int", "string", "bool", "unit", "enum", "none", "nil"):
        return []
    if tag == "bin":
        return [e[2], e[3]]
    if tag in ("not", "some", "project"):
        return [e[1]]
    if tag in ("ok", "error"):
        return [e[2]]
    if tag == "record":
        return [x for _, x in e[2]]
    if tag in ("variant", "call"):
        return e[3] if tag == "variant" else e[2]
    if tag == "match_variant":
        return [e[1]] + [x for _, x in e[2]]
    return list(e[1:])


def _walk(e: Any):
    pending = [(e, 0)]
    nodes = 0
    while pending:
        x, depth = pending.pop()
        nodes += 1
        if nodes > MAX_NODES or depth > 256:
            raise SourceError("expression exceeds the supported node or depth budget")
        yield x
        pending.extend((child, depth + 1) for child in reversed(_children(x)))


def type_of(enums: dict, declarations: dict, helpers: dict, ctx: list, e: Any) -> Any:
    """Proposal type inference. `declarations` and `helpers` must be checked registries."""
    tag = e[0]
    infer = lambda x, gamma=ctx: type_of(enums, declarations, helpers, gamma, x)
    wf = lambda t: _wf(enums, declarations, t)
    if tag == "var":
        if type(e[1]) is not int or e[1] < 0 or e[1] >= len(ctx):
            raise SourceError("unbound variable index")
        return ctx[e[1]]
    if tag in ("nat", "int", "string", "bool", "unit"):
        return tag
    if tag == "enum":
        if e[1] not in enums or e[2] not in enums[e[1]]:
            raise SourceError("unknown enumeration or constructor")
        return ("enum", e[1])
    if tag == "bin":
        op, left, right = e[1], infer(e[2]), infer(e[3])
        if left != right:
            raise SourceError("binary operand types differ")
        if op == "eq":
            return "bool"
        if op in ("add", "sub", "mul") and left in ("nat", "int"):
            return left
        if op in ("lt", "le") and left in ("nat", "int", "string"):
            return "bool"
        if op in ("and", "or") and left == "bool":
            return "bool"
        raise SourceError(f"{op}: unsupported operand type {left}")
    if tag in ("int_fdiv", "int_neg", "nat_to_int", "int_to_nat"):
        expected = "nat" if tag == "nat_to_int" else "int"
        if any(infer(x) != expected for x in e[1:]):
            raise SourceError(f"{tag}: operands must have {expected} type")
        return "nat" if tag == "int_to_nat" else "int"
    if tag == "list_range":
        if infer(e[1]) != "nat":
            raise SourceError("list_range: bound must have Nat type")
        return ("list", "nat")
    if tag in ("list_length", "list_reverse", "list_sort", "list_unique", "list_get", "list_append"):
        typ = infer(e[1])
        if not isinstance(typ, tuple) or typ[0] != "list":
            raise SourceError(f"{tag}: operand must have List type")
        if tag == "list_length":
            return "nat"
        if tag == "list_get":
            if infer(e[2]) != "nat":
                raise SourceError("list_get: index must have Nat type")
            return ("option", typ[1])
        if tag == "list_append" and infer(e[2]) != typ:
            raise SourceError("list_append: element types differ")
        if tag == "list_sort" and typ[1] not in ("nat", "int", "string"):
            raise SourceError("list_sort: only Nat, Int and String scalar sorts are supported")
        if tag == "list_unique" and typ[1] not in ("nat", "int", "string", "bool"):
            raise SourceError("list_unique: only primitive scalar sorts are supported")
        return typ
    if tag == "not":
        if infer(e[1]) != "bool":
            raise SourceError("not: operand must be bool")
        return "bool"
    if tag == "ite":
        cond, yes, no = (infer(x) for x in e[1:])
        if cond != "bool" or yes != no:
            raise SourceError("if: invalid condition or differing branch types")
        return yes
    if tag == "let":
        return infer(e[2], [infer(e[1])] + ctx)
    if tag in ("ok", "error"):
        if not wf(e[1]):
            raise SourceError(f"{tag}: ill-formed annotated type")
        t = infer(e[2])
        return ("result", e[1], t) if tag == "ok" else ("result", t, e[1])
    if tag == "match":
        t = infer(e[1])
        if not isinstance(t, tuple) or t[0] != "result":
            raise SourceError("match_result: scrutinee must have Result type")
        a, b = infer(e[2], [t[2]] + ctx), infer(e[3], [t[1]] + ctx)
    elif tag == "record":
        d = declarations.get(e[1])
        if not d or d["tag"] != "record":
            raise SourceError("unknown record type")
        if [k for k, _ in e[2]] != [k for k, _ in d["fields"]]:
            raise SourceError("record fields must be complete and in declaration order")
        for (_, value), (_, expected) in zip(e[2], d["fields"]):
            if infer(value) != expected:
                raise SourceError("record field type differs from declaration")
        return (tag, e[1])
    elif tag == "project":
        t = infer(e[1])
        if not isinstance(t, tuple) or t[0] != "record":
            raise SourceError("project: receiver must have Record type")
        for name, ft in declarations[t[1]]["fields"]:
            if name == e[2]:
                return ft
        raise SourceError("unknown record field")
    elif tag == "variant":
        d = declarations.get(e[1])
        if not d or d["tag"] != "variant":
            raise SourceError("unknown variant type")
        ct = next((types for name, types in d["constructors"] if name == e[2]), None)
        if ct is None:
            raise SourceError("unknown variant constructor")
        if [infer(x) for x in e[3]] != ct:
            raise SourceError("variant payload arity or types differ")
        return (tag, e[1])
    elif tag == "match_variant":
        t = infer(e[1])
        if not isinstance(t, tuple) or t[0] != "variant":
            raise SourceError("match_variant: scrutinee must have Variant type")
        ct = declarations[t[1]]["constructors"]
        if [name for name, _ in e[2]] != [name for name, _ in ct]:
            raise SourceError("variant branches must be exhaustive and in declaration order")
        types = [infer(body, list(reversed(params)) + ctx) for (_, body), (_, params) in zip(e[2], ct)]
        if not types or any(t != types[0] for t in types):
            raise SourceError("variant branch types differ or variant is empty")
        return types[0]
    elif tag in ("none", "nil"):
        if not wf(e[1]):
            raise SourceError(f"{tag}: ill-formed element type")
        return ("option" if tag == "none" else "list", e[1])
    elif tag == "some":
        return ("option", infer(e[1]))
    elif tag == "cons":
        h, t = infer(e[1]), infer(e[2])
        if t != ("list", h):
            raise SourceError("cons: tail must be a homogeneous List")
        return t
    elif tag in ("match_option", "match_list"):
        t = infer(e[1])
        expected = "option" if tag == "match_option" else "list"
        if not isinstance(t, tuple) or t[0] != expected:
            raise SourceError(f"{tag}: wrong scrutinee type")
        a = infer(e[2])
        branch_ctx = [t[1]] + ctx if expected == "option" else [t, t[1]] + ctx
        b = infer(e[3], branch_ctx)
    elif tag == "call":
        f = helpers.get(e[1])
        if f is None:
            raise SourceError("call target must be a declared helper, not an entry")
        if [infer(x) for x in e[2]] != f["params"]:
            raise SourceError("call argument arity or types differ")
        return f["result"]
    elif tag in ("list_fold", "nat_fold"):
        s, initial = infer(e[1]), infer(e[2])
        if tag == "list_fold":
            if not isinstance(s, tuple) or s[0] != "list":
                raise SourceError("list_fold: source must have List type")
            gamma = [s[1], initial] + ctx
        else:
            if s != "nat":
                raise SourceError("nat_fold: source must have Nat type")
            gamma = [initial, "nat"] + ctx
        if infer(e[3], gamma) != initial:
            raise SourceError("fold step must preserve accumulator type")
        return initial
    else:
        raise SourceError(f"unknown expression {tag}")
    if a != b:
        raise SourceError(f"{tag}: branch types differ")
    return a


def _check_program(enums: dict, prog: dict, allowed_features: tuple | list) -> list[dict]:
    if prog["language"] != LANGUAGE or prog["profile"] != PROFILE:
        raise SourceError("unsupported language or profile")
    if not prog["entries"]:
        raise SourceError("a program needs at least one entry")
    if sum(len(prog[k]) for k in ("declarations", "helpers", "entries")) > MAX_DECLARATIONS:
        raise SourceError("program exceeds the declaration budget")
    decls, helpers = _registry(enums, prog)
    _unique([f["id"] for f in prog["helpers"] + prog["entries"]], "function")
    graph = {}
    for d in prog["declarations"]:
        if d["tag"] == "record":
            _unique([name for name, _ in d["fields"]], "record field")
            types = [t for _, t in d["fields"]]
        else:
            if not d["constructors"]:
                raise SourceError("a variant needs at least one constructor")
            _unique([name for name, _ in d["constructors"]], "variant constructor")
            types = [t for _, ts in d["constructors"] for t in ts]
        if not all(_wf(enums, decls, t) for t in types):
            raise SourceError("ill-formed declaration type")
        graph[d["id"]] = set().union(*(_nominal_refs(t) for t in types))
    _acyclic(graph, "nominal type")
    call_graph = {f["id"]: set() for f in prog["helpers"]}
    signatures = []
    for group in ("helpers", "entries"):
        for f in prog[group]:
            if not all(_wf(enums, decls, t) for t in f["params"] + [f["result"]]):
                raise SourceError(f"function {f['id']}: ill-formed signature")
            for x in _walk(f["body"]):
                if x[0] == "call":
                    if x[1] not in helpers:
                        raise SourceError("call target must be a declared helper, not an entry")
                    if group == "helpers":
                        call_graph[f["id"]].add(x[1])
            inferred = type_of(enums, decls, helpers, list(reversed(f["params"])), f["body"])
            if inferred != f["result"]:
                raise SourceError(f"function {f['id']}: body type differs from declared result")
            if group == "entries":
                signatures.append({k: f[k] for k in ("id", "params", "result")})
    _acyclic(call_graph, "helper call")
    missing = set(required_features(prog)) - set(allowed_features)
    if missing:
        raise SourceError("unsupported required features: " + ", ".join(sorted(missing)))
    return signatures


def check_program(enums: dict[str, list[str]], prog: dict, allowed_features: tuple | list = FEATURES) -> list[dict]:
    """Propose Lean admission and externally visible signatures, preserving entry order."""
    try:
        return _check_program(enums, prog, allowed_features)
    except RecursionError:
        raise SourceError("program nesting exceeds the supported depth") from None


def required_features(prog: dict) -> list[str]:
    found = {"base"}
    def typ(t):
        if isinstance(t, str):
            if t in ("int", "string"):
                found.add(t)
            return
        if t[0] in ("record", "variant"):
            found.add("nominalData")
        if t[0] in ("option", "list"):
            found.add(t[0])
            typ(t[1])
        elif t[0] == "result":
            typ(t[1]); typ(t[2])
    for d in prog["declarations"]:
        found.add("nominalData")
        for t in ([t for _, t in d["fields"]] if d["tag"] == "record" else [t for _, ts in d["constructors"] for t in ts]):
            typ(t)
    for f in prog["helpers"] + prog["entries"]:
        for t in f["params"] + [f["result"]]:
            typ(t)
        for e in _walk(f["body"]):
            tag = e[0]
            if tag == "int" or tag in ("int_fdiv", "int_neg", "nat_to_int", "int_to_nat"):
                found.add("int")
            if tag == "string":
                found.add("string")
            if tag.startswith("list_") and tag not in ("list_fold",):
                found.update(("list", "pureList"))
            if tag == "list_get":
                found.add("option")
            if tag in ("record", "project", "variant", "match_variant"):
                found.add("nominalData")
            if tag in ("none", "some", "match_option"):
                found.add("option")
            if tag in ("nil", "cons", "match_list", "list_fold"):
                found.add("list")
            if tag == "call":
                found.add("acyclicCalls")
            if tag == "list_fold":
                found.add("listFold")
            if tag == "nat_fold":
                found.add("natFold")
            if tag in ("none", "nil", "ok", "error"):
                typ(e[1])
    return [f for f in FEATURES if f in found]


def ty_json(t: Any) -> Any:
    if isinstance(t, str):
        return t
    if t[0] == "result":
        return {"result": {"error": ty_json(t[1]), "ok": ty_json(t[2])}}
    return {t[0]: ty_json(t[1]) if t[0] in ("option", "list") else t[1]}


def expr_json(e: Any) -> dict:
    tag = e[0]
    enc = expr_json
    if tag == "int":
        return {"tag": tag, "value": str(e[1])}
    if tag == "string":
        return {"tag": tag, "value": list(e[1])}
    if tag in UNARY_OPS:
        return {"tag": tag, "value": enc(e[1])}
    if tag in ("int_fdiv", "list_append"):
        return {"left": enc(e[1]), "right": enc(e[2]), "tag": tag}
    if tag == "list_get":
        return {"index": enc(e[2]), "tag": tag, "value": enc(e[1])}
    if tag == "record":
        return {"fields": [{"id": k, "value": enc(v)} for k, v in e[2]], "record": e[1], "tag": tag}
    if tag == "project":
        return {"field": e[2], "tag": tag, "value": enc(e[1])}
    if tag == "variant":
        return {"args": [enc(x) for x in e[3]], "ctor": e[2], "tag": tag, "variant": e[1]}
    if tag == "match_variant":
        return {"branches": [{"body": enc(b), "ctor": c} for c, b in e[2]], "scrutinee": enc(e[1]), "tag": tag}
    if tag in ("none", "nil"):
        return {"element_type": ty_json(e[1]), "tag": tag}
    if tag == "some":
        return {"tag": tag, "value": enc(e[1])}
    if tag == "cons":
        return {"head": enc(e[1]), "tag": tag, "tail": enc(e[2])}
    if tag in ("match_option", "match_list"):
        a, b = ("none", "some") if tag == "match_option" else ("nil", "cons")
        return {a: enc(e[2]), b: enc(e[3]), "scrutinee": enc(e[1]), "tag": tag}
    if tag == "call":
        return {"args": [enc(x) for x in e[2]], "helper": e[1], "tag": tag}
    if tag in ("list_fold", "nat_fold"):
        return {"initial": enc(e[2]), "source": enc(e[1]), "step": enc(e[3]), "tag": tag}
    if tag in ("ok", "error"):
        return {"error_type" if tag == "ok" else "ok_type": ty_json(e[1]), "tag": tag, "value": enc(e[2])}
    # Scalar constructor shapes are the unchanged 0.1 wire fragment.
    if tag == "bin":
        return {"left": enc(e[2]), "right": enc(e[3]), "tag": e[1]}
    if tag == "not":
        return {"tag": tag, "value": enc(e[1])}
    if tag == "ite":
        return {"cond": enc(e[1]), "else": enc(e[3]), "tag": "if", "then": enc(e[2])}
    if tag == "let":
        return {"body": enc(e[2]), "tag": tag, "value": enc(e[1])}
    if tag == "match":
        return {"error": enc(e[3]), "ok": enc(e[2]), "scrutinee": enc(e[1]), "tag": "match_result"}
    return old.expr_json(e)


def program_json(prog: dict) -> dict:
    declarations = []
    for d in prog["declarations"]:
        if d["tag"] == "record":
            declarations.append({"fields": [{"id": k, "type": ty_json(t)} for k, t in d["fields"]], "id": d["id"], "tag": "record"})
        else:
            declarations.append({"constructors": [{"id": k, "params": [ty_json(t) for t in ts]} for k, ts in d["constructors"]], "id": d["id"], "tag": "variant"})
    def functions(group):
        return [{"body": expr_json(f["body"]), "id": f["id"], "params": [ty_json(t) for t in f["params"]], "result": ty_json(f["result"])} for f in prog[group]]
    return {"declarations": declarations, "entries": functions("entries"), "helpers": functions("helpers"), "language": prog["language"], "profile": prog["profile"]}


def source_bytes(prog: dict) -> bytes:
    """Encode a proposal as exact canonical delivered bytes, then recheck closed shape."""
    data = json.dumps(program_json(prog), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if parse_source(data) != prog:
        raise SourceError("program is not representable in the closed source format")
    return data


def lean_ty(t: Any) -> str:
    if isinstance(t, str):
        return f"VSCore3.Ty.{t}"
    if t[0] in ("enum", "record", "variant"):
        return f"(VSCore3.Ty.{t[0]} {lean_string(t[1])})"
    return f"(VSCore3.Ty.{t[0]} " + " ".join(lean_ty(x) for x in t[1:]) + ")"


def lean_expr(e: Any) -> str:
    tag = e[0]
    enc = lean_expr
    prefix = "VSCore3.Expr."
    if tag == "int":
        value = f"(Int.ofNat {e[1]})" if e[1] >= 0 else f"(Int.negSucc {-e[1] - 1})"
        return f"({prefix}int {value})"
    if tag == "string":
        return f"({prefix}string {lean_list([str(p) for p in e[1]])})"
    if tag in (*UNARY_OPS, "int_fdiv", "list_get", "list_append"):
        ctor = {"int_fdiv": "intFdiv", "int_neg": "intNeg", "nat_to_int": "natToInt", "int_to_nat": "intToNat",
                "list_length": "listLength", "list_range": "listRange", "list_reverse": "listReverse",
                "list_sort": "listSort", "list_unique": "listUnique", "list_get": "listGet", "list_append": "listAppend"}[tag]
        return f"({prefix}{ctor} " + " ".join(enc(x) for x in e[1:]) + ")"
    if tag in ("var", "nat"):
        return f"({prefix}{tag} {e[1]})"
    if tag == "bool":
        return f"({prefix}bool {'true' if e[1] else 'false'})"
    if tag == "unit":
        return prefix + "unit"
    if tag == "enum":
        return f"({prefix}enum {lean_string(e[1])} {lean_string(e[2])})"
    if tag == "bin":
        return f"({prefix}bin VSCore.BinOp.{e[1]} {enc(e[2])} {enc(e[3])})"
    if tag in ("not", "some"):
        return f"({prefix}{tag} {enc(e[1])})"
    if tag in ("ite", "let", "match", "match_option", "match_list", "list_fold", "nat_fold", "cons"):
        ctor = {"let": "letE", "match": "matchResult", "match_option": "matchOption", "match_list": "matchList", "list_fold": "listFold", "nat_fold": "natFold"}.get(tag, tag)
        return f"({prefix}{ctor} " + " ".join(enc(x) for x in e[1:]) + ")"
    if tag in ("ok", "error", "none", "nil"):
        return f"({prefix}{tag} {lean_ty(e[1])}" + (" " + enc(e[2]) if len(e) > 2 else "") + ")"
    if tag == "record":
        fields = "[" + ", ".join(f"({lean_string(k)}, {enc(v)})" for k, v in e[2]) + "]"
        return f"({prefix}record {lean_string(e[1])} {fields})"
    if tag == "project":
        return f"({prefix}project {enc(e[1])} {lean_string(e[2])})"
    if tag == "variant":
        return f"({prefix}variant {lean_string(e[1])} {lean_string(e[2])} [" + ", ".join(enc(x) for x in e[3]) + "])"
    if tag == "match_variant":
        branches = "[" + ", ".join(f"({lean_string(k)}, {enc(v)})" for k, v in e[2]) + "]"
        return f"({prefix}matchVariant {enc(e[1])} {branches})"
    if tag == "call":
        return f"({prefix}call {lean_string(e[1])} [" + ", ".join(enc(x) for x in e[2]) + "])"
    raise SourceError(f"unknown expression {tag}")


def lean_signature(f: dict) -> str:
    return "{ id := " + lean_string(f["id"]) + ", params := [" + ", ".join(lean_ty(t) for t in f["params"]) + "], result := " + lean_ty(f["result"]) + " }"


def lean_signatures(sigs: list[dict]) -> str:
    return "[" + ",\n  ".join(lean_signature(f) for f in sigs) + "]"


def lean_program(prog: dict) -> str:
    decls = []
    for d in prog["declarations"]:
        if d["tag"] == "record":
            members = "[" + ", ".join(f"({lean_string(k)}, {lean_ty(t)})" for k, t in d["fields"]) + "]"
        else:
            members = "[" + ", ".join(f"({lean_string(k)}, [" + ", ".join(lean_ty(t) for t in ts) + "])" for k, ts in d["constructors"]) + "]"
        decls.append(f"(VSCore3.DataDecl.{d['tag']} {lean_string(d['id'])} {members})")
    def functions(group):
        return "[" + ",\n".join("{ id := " + lean_string(f["id"]) + ", params := [" + ", ".join(lean_ty(t) for t in f["params"]) + "], result := " + lean_ty(f["result"]) + ", body := " + lean_expr(f["body"]) + " }" for f in prog[group]) + "]"
    return "{ language := " + lean_string(prog["language"]) + ", profile := " + lean_string(prog["profile"]) + ", declarations := [" + ", ".join(decls) + "], helpers := " + functions("helpers") + ", entries := " + functions("entries") + " }"


def parse_surface(text: str, enums: dict[str, list[str]] | None = None) -> dict:
    from .vscore3_surface import parse_surface as parse
    return parse(text, enums)


def compile_surface(text: str, enums: dict[str, list[str]] | None = None) -> bytes:
    return source_bytes(parse_surface(text, enums))
