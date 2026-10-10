"""Host-side VSCore 0.1 source handling: proposal parser, proposal type checker and Lean literals.

Nothing here is authoritative. `parse_source` mirrors the normative Lean decoder
(`lean/VSCore/Decode.lean`) so that the supervisor can *propose* the decoded program and give
early diagnostics; acceptance requires the kernel-checked equation
`VSCore.parseSource sourceBytes = .ok rawProgram`. Likewise `check_program` proposes the entry
signatures that `VSCore.checkProgram` must reproduce in the kernel. A disagreement between the
host and the kernel is a blocking failure, never a reason to trust either side alone.

AST shapes (plain Python data, mirroring `VSCore.Syntax`):

    Ty    : "nat" | "bool" | "unit" | ("enum", id) | ("result", error_ty, ok_ty)
    Expr  : ("var", i) | ("nat", n) | ("bool", b) | ("unit",) | ("enum", id, ctor)
          | ("bin", op, lhs, rhs) | ("not", e) | ("ite", c, t, e) | ("let", v, b)
          | ("ok", error_ty, e) | ("error", ok_ty, e) | ("match", scrutinee, on_ok, on_error)
    Entry : {"id", "params", "result", "body"};  Program : {"language", "entries"}
"""

from __future__ import annotations

import re
from typing import Any

LANGUAGE = "vscore/0.1"
MAX_SAFE_INTEGER = 9007199254740991
_MAX_SAFE_INTEGER_BYTES = str(MAX_SAFE_INTEGER).encode("ascii")
MAX_SOURCE_BYTES = 1 << 20
MAX_NAT_DIGITS = 1024
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*\Z")
BIN_OPS = ("add", "sub", "mul", "lt", "le", "eq", "and", "or")


class SourceError(ValueError):
    """The source is rejected (malformed, non-canonical, unsupported or ill typed)."""


# ------------------------------------------------------------------------------------------
# canonical JSON subset (mirrors parseValue / parseMembers / parseElems)
# ------------------------------------------------------------------------------------------

def _str_byte(b: int) -> bool:
    return 32 <= b <= 126 and b not in (34, 92)


class _Parser:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def peek(self) -> int | None:
        return self.data[self.pos] if self.pos < len(self.data) else None

    def string(self) -> str:
        start = self.pos
        while True:
            b = self.peek()
            if b is None:
                raise SourceError("unterminated string")
            if b == 34:
                self.pos += 1
                return self.data[start:self.pos - 1].decode("ascii")
            if not _str_byte(b):
                raise SourceError("string contains an escape, control or non-ASCII byte")
            self.pos += 1

    def value(self, depth: int) -> Any:
        if depth > 256:
            raise SourceError("JSON nesting exceeds the supported depth")
        b = self.peek()
        if b is None:
            raise SourceError("unexpected end of input")
        self.pos += 1
        if b == 34:
            return self.string()
        if b == 123:
            if self.peek() == 125:
                self.pos += 1
                return {}
            return self.members(depth)
        if b == 91:
            if self.peek() == 93:
                self.pos += 1
                return []
            return self.elems(depth)
        if b == 116:
            if self.data[self.pos:self.pos + 3] == b"rue":
                self.pos += 3
                return True
            raise SourceError("invalid literal")
        if b == 102:
            if self.data[self.pos:self.pos + 4] == b"alse":
                self.pos += 4
                return False
            raise SourceError("invalid literal")
        if b == 48:
            nxt = self.peek()
            if nxt is not None and 48 <= nxt <= 57:
                raise SourceError("non-canonical integer (leading zero)")
            return _Num(0)
        if 49 <= b <= 57:
            start = self.pos - 1
            while (c := self.peek()) is not None and 48 <= c <= 57:
                self.pos += 1
            digits = self.data[start:self.pos]
            # Canonical positive decimals have no leading zeros, so length and
            # lexical order establish the bound before Python converts them.
            if (len(digits) > len(_MAX_SAFE_INTEGER_BYTES) or
                    (len(digits) == len(_MAX_SAFE_INTEGER_BYTES) and digits > _MAX_SAFE_INTEGER_BYTES)):
                raise SourceError("integer exceeds 2^53 - 1")
            return _Num(int(digits))
        raise SourceError("unexpected byte (whitespace, null, sign, or non-JSON)")

    def members(self, depth: int) -> dict:
        out: dict[str, Any] = {}
        prev: bytes | None = None
        while True:
            if self.peek() != 34:
                raise SourceError("expected an object key")
            self.pos += 1
            key = self.string()
            raw = key.encode("ascii")
            if prev is not None and not prev < raw:
                raise SourceError("object keys are not strictly sorted")
            if prev is None and not raw:
                raise SourceError("empty object key")
            if self.peek() != 58:
                raise SourceError("expected ':'")
            self.pos += 1
            out[key] = self.value(depth + 1)
            prev = raw
            b = self.peek()
            self.pos += 1
            if b == 44:
                continue
            if b == 125:
                return out
            raise SourceError("expected ',' or '}'")

    def elems(self, depth: int) -> list:
        out = []
        while True:
            out.append(self.value(depth + 1))
            b = self.peek()
            self.pos += 1
            if b == 44:
                continue
            if b == 93:
                return out
            raise SourceError("expected ',' or ']'")


class _Num(int):
    """A JSON number (kept distinct from Booleans and decimal strings)."""


def parse_json(data: bytes) -> Any:
    if len(data) > MAX_SOURCE_BYTES:
        raise SourceError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
    p = _Parser(data)
    v = p.value(0)
    if p.pos != len(data):
        raise SourceError("trailing bytes after the JSON value")
    return v


# ------------------------------------------------------------------------------------------
# closed-schema decoder (mirrors decodeTy / decodeExpr / decodeEntry / decodeProgram)
# ------------------------------------------------------------------------------------------

def _ident(j: Any) -> str:
    if not isinstance(j, str):
        raise SourceError("expected an identifier string")
    if len(j) > 128 or not IDENT.match(j):
        raise SourceError("invalid identifier")
    return j


def _nat_literal(s: Any) -> int:
    if not isinstance(s, str):
        raise SourceError("nat: value must be a decimal string")
    if not (s == "0" or re.fullmatch(r"[1-9][0-9]*", s)) or len(s) > MAX_NAT_DIGITS:
        raise SourceError("natural literal must be a canonical decimal string")
    return int(s)


def decode_ty(j: Any, depth: int = 0) -> Any:
    if depth > 256:
        raise SourceError("type nesting exceeds decode budget")
    if j in ("nat", "bool", "unit") and isinstance(j, str):
        return j
    if isinstance(j, dict) and list(j) == ["enum"]:
        return ("enum", _ident(j["enum"]))
    if isinstance(j, dict) and list(j) == ["result"] and isinstance(j["result"], dict) and list(j["result"]) == ["error", "ok"]:
        return ("result", decode_ty(j["result"]["error"], depth + 1), decode_ty(j["result"]["ok"], depth + 1))
    raise SourceError("invalid type")


_SHAPES = {
    "var": ["index", "tag"], "nat": ["tag", "value"], "bool": ["tag", "value"], "unit": ["tag"],
    "enum": ["ctor", "enum", "tag"], "not": ["tag", "value"], "if": ["cond", "else", "tag", "then"],
    "let": ["body", "tag", "value"], "ok": ["error_type", "tag", "value"], "error": ["ok_type", "tag", "value"],
    "match_result": ["error", "ok", "scrutinee", "tag"], **{op: ["left", "right", "tag"] for op in BIN_OPS},
}


def decode_expr(j: Any, depth: int = 0) -> Any:
    if depth > 256:
        raise SourceError("expression nesting exceeds decode budget")
    if not isinstance(j, dict):
        raise SourceError("expression must be an object")
    tag = j.get("tag")
    if not isinstance(tag, str):
        raise SourceError("expression object needs a string tag")
    if tag not in _SHAPES:
        raise SourceError(f"unsupported expression tag {tag}")
    if list(j) != _SHAPES[tag]:
        raise SourceError(f"{tag}: unexpected or missing fields")
    sub = lambda k: decode_expr(j[k], depth + 1)  # noqa: E731
    if tag == "var":
        if not isinstance(j["index"], _Num):
            raise SourceError("var: index must be a canonical integer")
        return ("var", int(j["index"]))
    if tag == "nat":
        return ("nat", _nat_literal(j["value"]))
    if tag == "bool":
        if not isinstance(j["value"], bool):
            raise SourceError("bool: value must be true or false")
        return ("bool", j["value"])
    if tag == "unit":
        return ("unit",)
    if tag == "enum":
        return ("enum", _ident(j["enum"]), _ident(j["ctor"]))
    if tag == "not":
        return ("not", sub("value"))
    if tag == "if":
        return ("ite", sub("cond"), sub("then"), sub("else"))
    if tag == "let":
        return ("let", sub("value"), sub("body"))
    if tag == "ok":
        return ("ok", decode_ty(j["error_type"], depth + 1), sub("value"))
    if tag == "error":
        return ("error", decode_ty(j["ok_type"], depth + 1), sub("value"))
    if tag == "match_result":
        return ("match", sub("scrutinee"), sub("ok"), sub("error"))
    return ("bin", tag, sub("left"), sub("right"))


def decode_program(j: Any) -> dict:
    if not isinstance(j, dict):
        raise SourceError("program must be an object")
    if list(j) != ["entries", "language"]:
        raise SourceError("program: unexpected or missing fields")
    if not isinstance(j["language"], str) or not isinstance(j["entries"], list):
        raise SourceError("program: language string and entries array are required")
    if j["language"] != LANGUAGE:
        raise SourceError("unsupported language version")
    entries = []
    for e in j["entries"]:
        if not isinstance(e, dict):
            raise SourceError("entry must be an object")
        if list(e) != ["body", "id", "params", "result"]:
            raise SourceError("entry: unexpected or missing fields")
        if not isinstance(e["params"], list):
            raise SourceError("entry: id, params (array), result and body are required")
        entries.append({"id": _ident(e["id"]), "params": [decode_ty(t) for t in e["params"]],
                        "result": decode_ty(e["result"]), "body": decode_expr(e["body"])})
    return {"language": j["language"], "entries": entries}


def parse_source(data: bytes) -> dict:
    """Proposed `VSCore.parseSource` result; raises SourceError where the Lean decoder errors."""
    return decode_program(parse_json(data))


# ------------------------------------------------------------------------------------------
# proposal type checker (mirrors VSCore.Typing)
# ------------------------------------------------------------------------------------------

def _wf(enums: dict[str, list[str]], t: Any) -> bool:
    if t in ("nat", "bool", "unit"):
        return True
    if t[0] == "enum":
        return t[1] in enums
    return _wf(enums, t[1]) and _wf(enums, t[2])


def _bin_type(op: str, a: Any, b: Any) -> Any:
    if op in ("add", "sub", "mul") and a == b == "nat":
        return "nat"
    if op in ("lt", "le") and a == b == "nat":
        return "bool"
    if op in ("and", "or") and a == b == "bool":
        return "bool"
    if op == "eq":
        if a == b:
            return "bool"
        raise SourceError("eq: operand types differ")
    raise SourceError("operator applied to operands of the wrong type")


def type_of(enums: dict[str, list[str]], ctx: list[Any], e: Any) -> Any:
    tag = e[0]
    if tag == "var":
        if e[1] >= len(ctx):
            raise SourceError("unbound variable index")
        return ctx[e[1]]
    if tag in ("nat", "bool", "unit"):
        return tag
    if tag == "enum":
        if e[1] not in enums:
            raise SourceError("unknown enumeration")
        if e[2] not in enums[e[1]]:
            raise SourceError("unknown enumeration constructor")
        return ("enum", e[1])
    if tag == "bin":
        return _bin_type(e[1], type_of(enums, ctx, e[2]), type_of(enums, ctx, e[3]))
    if tag == "not":
        if type_of(enums, ctx, e[1]) != "bool":
            raise SourceError("not: operand must be bool")
        return "bool"
    if tag == "ite":
        c, t, f = (type_of(enums, ctx, x) for x in e[1:])
        if c != "bool":
            raise SourceError("if: condition must be bool")
        if t != f:
            raise SourceError("if: branch types differ")
        return t
    if tag == "let":
        return type_of(enums, [type_of(enums, ctx, e[1])] + ctx, e[2])
    if tag == "ok":
        if not _wf(enums, e[1]):
            raise SourceError("ok: ill-formed error type")
        return ("result", e[1], type_of(enums, ctx, e[2]))
    if tag == "error":
        if not _wf(enums, e[1]):
            raise SourceError("error: ill-formed ok type")
        return ("result", type_of(enums, ctx, e[2]), e[1])
    if tag == "match":
        s = type_of(enums, ctx, e[1])
        if not (isinstance(s, tuple) and s[0] == "result"):
            raise SourceError("match_result: scrutinee must have a result type")
        t1 = type_of(enums, [s[2]] + ctx, e[2])
        t2 = type_of(enums, [s[1]] + ctx, e[3])
        if t1 != t2:
            raise SourceError("match_result: branch types differ")
        return t1
    raise SourceError(f"unknown expression {tag}")


def check_program(enums: dict[str, list[str]], prog: dict) -> list[dict]:
    """Proposed `VSCore.checkProgram` signatures (one per entry, in program order)."""
    if prog["language"] != LANGUAGE:
        raise SourceError("unsupported language version")
    if not prog["entries"]:
        raise SourceError("a program needs at least one entry")
    ids = [e["id"] for e in prog["entries"]]
    if len(set(ids)) != len(ids):
        raise SourceError("duplicate entry IDs")
    sigs = []
    for e in prog["entries"]:
        if not all(_wf(enums, t) for t in e["params"]):
            raise SourceError(f"entry {e['id']}: ill-formed parameter type")
        if not _wf(enums, e["result"]):
            raise SourceError(f"entry {e['id']}: ill-formed result type")
        try:
            t = type_of(enums, list(reversed(e["params"])), e["body"])
        except SourceError as exc:
            raise SourceError(f"entry {e['id']}: {exc}") from None
        except RecursionError:
            raise SourceError(f"entry {e['id']}: expression nesting exceeds the supported depth") from None
        if t != e["result"]:
            raise SourceError(f"entry {e['id']}: body type differs from the declared result type")
        sigs.append({"id": e["id"], "params": e["params"], "result": e["result"]})
    return sigs


# ------------------------------------------------------------------------------------------
# Lean literals (verifier-generated goal text) and canonical JSON (implementation IR)
# ------------------------------------------------------------------------------------------

def lean_string(s: str) -> str:
    """Render a Lean literal without changing its Unicode scalar text.

    Lean has fixed-width ``\\xNN`` and ``\\uNNNN`` escapes. Supplementary
    scalars must be emitted directly; UTF-16 surrogate escapes are not scalars.
    This is a term printer, independent of the restricted source JSON grammar.
    """
    escapes = {'"': '\\"', '\\': '\\\\', '\n': '\\n', '\r': '\\r', '\t': '\\t'}
    out = []
    for c in s:
        n = ord(c)
        if 0xD800 <= n <= 0xDFFF:
            raise SourceError("string literal contains an invalid Unicode surrogate")
        if c in escapes:
            out.append(escapes[c])
        elif n < 0x20 or 0x7F <= n <= 0x9F:
            out.append(f"\\x{n:02x}")
        elif 0xA0 <= n <= 0xFFFF:
            out.append(f"\\u{n:04x}")
        else:
            out.append(c)
    return '"' + ''.join(out) + '"'


def lean_ty(t: Any) -> str:
    if t in ("nat", "bool", "unit"):
        return f"VSCore.Ty.{t}"
    if t[0] == "enum":
        return f"(VSCore.Ty.enum {lean_string(t[1])})"
    return f"(VSCore.Ty.result {lean_ty(t[1])} {lean_ty(t[2])})"


def lean_expr(e: Any) -> str:
    tag = e[0]
    if tag == "var":
        return f"(VSCore.Expr.var {e[1]})"
    if tag == "nat":
        return f"(VSCore.Expr.nat {e[1]})"
    if tag == "bool":
        return f"(VSCore.Expr.bool {'true' if e[1] else 'false'})"
    if tag == "unit":
        return "VSCore.Expr.unit"
    if tag == "enum":
        return f"(VSCore.Expr.enum {lean_string(e[1])} {lean_string(e[2])})"
    if tag == "bin":
        return f"(VSCore.Expr.bin VSCore.BinOp.{e[1]} {lean_expr(e[2])} {lean_expr(e[3])})"
    if tag == "not":
        return f"(VSCore.Expr.not {lean_expr(e[1])})"
    if tag == "ite":
        return f"(VSCore.Expr.ite {lean_expr(e[1])} {lean_expr(e[2])} {lean_expr(e[3])})"
    if tag == "let":
        return f"(VSCore.Expr.letE {lean_expr(e[1])} {lean_expr(e[2])})"
    if tag == "ok":
        return f"(VSCore.Expr.ok {lean_ty(e[1])} {lean_expr(e[2])})"
    if tag == "error":
        return f"(VSCore.Expr.error {lean_ty(e[1])} {lean_expr(e[2])})"
    if tag == "match":
        return f"(VSCore.Expr.matchResult {lean_expr(e[1])} {lean_expr(e[2])} {lean_expr(e[3])})"
    raise SourceError(f"unknown expression {tag}")


def lean_list(items: list[str], indent: str = "  ") -> str:
    if not items:
        return "[]"
    return "[\n" + ",\n".join(indent + "  " + i for i in items) + "]"


def lean_program(prog: dict) -> str:
    entries = [
        "{ id := " + lean_string(e["id"]) + ",\n      params := [" + ", ".join(lean_ty(t) for t in e["params"])
        + "],\n      result := " + lean_ty(e["result"]) + ",\n      body := " + lean_expr(e["body"]) + " }"
        for e in prog["entries"]]
    return ("{ language := " + lean_string(prog["language"]) + ",\n    entries := [\n    "
            + ",\n    ".join(entries) + "] }")


def lean_signatures(sigs: list[dict]) -> str:
    return "[" + ",\n  ".join(
        "{ id := " + lean_string(s["id"]) + ", params := [" + ", ".join(lean_ty(t) for t in s["params"])
        + "], result := " + lean_ty(s["result"]) + " }" for s in sigs) + "]"


def ty_json(t: Any) -> Any:
    if t in ("nat", "bool", "unit"):
        return t
    if t[0] == "enum":
        return {"enum": t[1]}
    return {"result": {"error": ty_json(t[1]), "ok": ty_json(t[2])}}


def expr_json(e: Any) -> Any:
    """Canonical JSON of an expression; inverse of `decode_expr` (naturals as decimal strings)."""
    tag = e[0]
    if tag == "var":
        return {"index": e[1], "tag": "var"}
    if tag == "nat":
        return {"tag": "nat", "value": str(e[1])}
    if tag == "bool":
        return {"tag": "bool", "value": e[1]}
    if tag == "unit":
        return {"tag": "unit"}
    if tag == "enum":
        return {"ctor": e[2], "enum": e[1], "tag": "enum"}
    if tag == "bin":
        return {"left": expr_json(e[2]), "right": expr_json(e[3]), "tag": e[1]}
    if tag == "not":
        return {"tag": "not", "value": expr_json(e[1])}
    if tag == "ite":
        return {"cond": expr_json(e[1]), "else": expr_json(e[3]), "tag": "if", "then": expr_json(e[2])}
    if tag == "let":
        return {"body": expr_json(e[2]), "tag": "let", "value": expr_json(e[1])}
    if tag == "ok":
        return {"error_type": ty_json(e[1]), "tag": "ok", "value": expr_json(e[2])}
    if tag == "error":
        return {"ok_type": ty_json(e[1]), "tag": "error", "value": expr_json(e[2])}
    if tag == "match":
        return {"error": expr_json(e[3]), "ok": expr_json(e[2]), "scrutinee": expr_json(e[1]), "tag": "match_result"}
    raise SourceError(f"unknown expression {tag}")


def program_json(prog: dict) -> dict:
    return {"entries": [{"body": expr_json(e["body"]), "id": e["id"], "params": [ty_json(t) for t in e["params"]],
                         "result": ty_json(e["result"])} for e in prog["entries"]],
            "language": prog["language"]}
