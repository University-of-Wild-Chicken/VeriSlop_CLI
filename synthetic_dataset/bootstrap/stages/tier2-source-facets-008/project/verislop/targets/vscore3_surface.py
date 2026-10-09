"""Untrusted ASCII authoring frontend for grammar/vscore-0.3.ebnf.

Named local scopes elaborate to de Bruijn indices. The output, rather than this text,
is the delivered canonical JSON endpoint checked by the normative Lean decoder.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import vscore3_source as core
from .vscore_source import IDENT, _nat_literal

_KEYWORDS = set("program profile record variant fn entry Nat Int Bool String Unit Enum Record Variant Result Option List let if then else match ok error none some nil cons not true false unit enum list int string call fold fdiv ofNat toNat length range get append reverse sort unique map filter sum".split())
_PUNCT = ("->", "=>", "<=", "==", "&&", "||", ";", "{", "}", "(", ")", "[", "]", ":", ",", ".", "=", "+", "-", "*", "<")


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    offset: int


def tokenize(text: str) -> list[Token]:
    try:
        data = text.encode("ascii")
    except UnicodeEncodeError:
        raise core.SourceError("surface source must be ASCII") from None
    if len(data) > core.MAX_SOURCE_BYTES:
        raise core.SourceError("surface source exceeds the byte budget")
    out = []
    i = 0
    while i < len(text):
        start = i
        ch = text[i]
        if ch in " \t\r\n":
            i += 1
            continue
        if text.startswith("//", i):
            i += 2
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue
        quoted = text.startswith('@"', i)
        if quoted or ch == '"':
            i += 2 if quoted else 1
            content = i
            while i < len(text) and text[i] != '"':
                if not (32 <= ord(text[i]) <= 126) or text[i] == "\\":
                    raise core.SourceError(f"invalid quoted token at byte {start}")
                i += 1
            if i == len(text):
                raise core.SourceError(f"unterminated quoted token at byte {start}")
            value = text[content:i]
            i += 1
            if quoted and (len(value) > 128 or not IDENT.fullmatch(value)):
                raise core.SourceError(f"invalid quoted identifier at byte {start}")
            out.append(Token("name" if quoted else "string", value, start))
        elif ch.isascii() and (ch.isalpha() or ch == "_"):
            i += 1
            while i < len(text) and (text[i].isascii() and (text[i].isalnum() or text[i] == "_")):
                i += 1
            value = text[start:i]
            if len(value) > 128:
                raise core.SourceError(f"identifier exceeds 128 bytes at byte {start}")
            out.append(Token("keyword" if value in _KEYWORDS else "name", value, start))
        elif ch.isdigit():
            i += 1
            while i < len(text) and text[i].isdigit():
                i += 1
            value = text[start:i]
            _nat_literal(value)
            out.append(Token("nat", value, start))
        else:
            p = next((p for p in _PUNCT if text.startswith(p, i)), None)
            if p is None:
                raise core.SourceError(f"unexpected character at byte {i}")
            i += len(p)
            out.append(Token("punct", p, start))
        if len(out) > core.MAX_NODES * 8:
            raise core.SourceError("surface source exceeds the token budget")
    out.append(Token("eof", "", len(text)))
    return out


class Parser:
    def __init__(self, text: str):
        self.tokens = tokenize(text)
        self.pos = 0
        self.depth = 0
        self.nodes = 0

    def peek(self, value: str) -> bool:
        token = self.tokens[self.pos]
        return token.kind in ("keyword", "punct") and token.text == value

    def take(self, value: str) -> bool:
        if self.peek(value):
            self.pos += 1
            return True
        return False

    def expect(self, value: str) -> None:
        if not self.take(value):
            raise core.SourceError(f"expected {value!r} at byte {self.tokens[self.pos].offset}")

    def name(self) -> str:
        t = self.tokens[self.pos]
        if t.kind != "name":
            raise core.SourceError(f"expected a name at byte {t.offset}; reserved words require @ quotation")
        self.pos += 1
        return t.text

    def string(self, expected: str) -> None:
        t = self.tokens[self.pos]
        if t.kind != "string" or t.text != expected:
            raise core.SourceError(f"expected quoted {expected!r} at byte {t.offset}")
        self.pos += 1

    def typ(self) -> Any:
        self.depth += 1
        try:
            if self.depth > 256:
                raise core.SourceError("surface nesting exceeds the depth budget")
            for keyword, tag in (("Nat", "nat"), ("Int", "int"), ("Bool", "bool"), ("String", "string"), ("Unit", "unit")):
                if self.take(keyword):
                    return tag
            for keyword, tag in (("Enum", "enum"), ("Record", "record"), ("Variant", "variant")):
                if self.take(keyword):
                    self.expect("(")
                    name = self.name()
                    self.expect(")")
                    return (tag, name)
            for keyword, tag in (("Result", "result"), ("Option", "option"), ("List", "list")):
                if self.take(keyword):
                    self.expect("(")
                    a = self.typ()
                    if tag == "result":
                        self.expect(",")
                        b = self.typ()
                        t = (tag, a, b)
                    else:
                        t = (tag, a)
                    self.expect(")")
                    return t
            raise core.SourceError(f"expected a type at byte {self.tokens[self.pos].offset}")
        finally:
            self.depth -= 1

    def types(self) -> list:
        out = [self.typ()]
        while self.take(","):
            out.append(self.typ())
        return out

    def program(self) -> dict:
        self.expect("program")
        self.string(core.LANGUAGE)
        self.expect("profile")
        self.string(core.PROFILE)
        self.expect(";")
        declarations = []
        while self.peek("record") or self.peek("variant"):
            tag = "record" if self.take("record") else "variant"
            if tag == "variant":
                self.expect("variant")
            ident = self.name()
            self.expect("{")
            members = []
            while not self.take("}"):
                name = self.name()
                if tag == "record":
                    self.expect(":")
                    value = self.typ()
                else:
                    value = []
                    if self.take("("):
                        value = self.types()
                        self.expect(")")
                self.expect(";")
                members.append((name, value))
            declarations.append({"tag": tag, "id": ident, "fields" if tag == "record" else "constructors": members})
        helpers, entries = [], []
        while self.take("fn"):
            helpers.append(self.function())
        while self.take("entry"):
            entries.append(self.function())
        if self.tokens[self.pos].kind != "eof":
            raise core.SourceError(f"unexpected token at byte {self.tokens[self.pos].offset}; declarations must precede helpers and entries")
        if not entries:
            raise core.SourceError("a surface program needs at least one entry")
        return {"language": core.LANGUAGE, "profile": core.PROFILE, "declarations": declarations, "helpers": helpers, "entries": entries}

    def function(self) -> dict:
        ident = self.name()
        self.expect("(")
        params, names = [], []
        if not self.take(")"):
            while True:
                names.append(self.name())
                self.expect(":")
                params.append(self.typ())
                if self.take(")"):
                    break
                self.expect(",")
        core._unique(names, "parameter")
        self.expect("->")
        result = self.typ()
        self.expect("{")
        body = self.expr()
        self.expect("}")
        return {"id": ident, "params": params, "result": result, "body": body, "_names": names}

    def expr(self) -> Any:
        self.depth += 1
        self.nodes += 1
        try:
            if self.depth > 256 or self.nodes > core.MAX_NODES:
                raise core.SourceError("surface expression exceeds node or depth budget")
            if self.take("let"):
                n = self.name()
                self.expect("=")
                value = self.expr()
                self.expect(";")
                return ("let_named", n, value, self.expr())
            if self.take("if"):
                cond = self.expr()
                self.expect("then")
                yes = self.expr()
                self.expect("else")
                return ("ite", cond, yes, self.expr())
            if self.take("match"):
                value = self.expr()
                self.expect("{")
                branches = []
                while not self.take("}"):
                    p = self.pattern()
                    self.expect("=>")
                    body = self.expr()
                    self.expect(";")
                    branches.append((p, body))
                if not branches:
                    raise core.SourceError("a match needs at least one branch")
                return ("match_named", value, branches)
            return self.or_expr()
        finally:
            self.depth -= 1

    def pattern(self) -> tuple:
        for tag in ("ok", "error", "some"):
            if self.take(tag):
                self.expect("(")
                n = self.name()
                self.expect(")")
                return (tag, [n])
        for tag in ("none", "nil"):
            if self.take(tag):
                return (tag, [])
        if self.take("cons"):
            self.expect("(")
            a = self.name()
            self.expect(",")
            b = self.name()
            self.expect(")")
            core._unique([a, b], "pattern binder")
            return ("cons", [a, b])
        if self.take("variant"):
            nominal = self.name()
            self.expect(".")
            ctor = self.name()
            self.expect("(")
            names = []
            if not self.take(")"):
                names.append(self.name())
                while self.take(","):
                    names.append(self.name())
                self.expect(")")
            core._unique(names, "pattern binder")
            return ("variant", nominal, ctor, names)
        raise core.SourceError(f"expected a pattern at byte {self.tokens[self.pos].offset}")

    def binary(self, inner, ops: dict[str, str], repeat: bool = True):
        e = inner()
        while True:
            op = next((token for token in ops if self.peek(token)), None)
            if op is None:
                return e
            self.expect(op)
            e = ("bin", ops[op], e, inner())
            if not repeat:
                return e

    def or_expr(self):
        return self.binary(self.and_expr, {"||": "or"})

    def and_expr(self):
        return self.binary(self.eq_expr, {"&&": "and"})

    def eq_expr(self):
        return self.binary(self.cmp_expr, {"==": "eq"}, False)

    def cmp_expr(self):
        return self.binary(self.add_expr, {"<": "lt", "<=": "le"}, False)

    def add_expr(self):
        return self.binary(self.mul_expr, {"+": "add", "-": "sub"})

    def mul_expr(self):
        return self.binary(self.unary, {"*": "mul"})

    def unary(self):
        if self.take("not"):
            # unary recursion must observe the same budget as parentheses and folds.
            self.depth += 1
            try:
                if self.depth > 256:
                    raise core.SourceError("surface nesting exceeds the depth budget")
                return ("not", self.unary())
            finally:
                self.depth -= 1
        if self.take("-"):
            self.depth += 1
            try:
                if self.depth > 256:
                    raise core.SourceError("surface nesting exceeds the depth budget")
                token = self.tokens[self.pos]
                if token.kind == "nat":
                    self.pos += 1
                    return ("int", core._int_literal("-" + token.text))
                return ("int_neg", self.unary())
            finally:
                self.depth -= 1
        e = self.primary()
        while self.take("."):
            e = ("project", e, self.name())
        return e

    def args(self) -> list:
        out = []
        if not self.take(")"):
            out.append(self.expr())
            while self.take(","):
                out.append(self.expr())
            self.expect(")")
        return out

    def primary(self):
        t = self.tokens[self.pos]
        if t.kind == "name":
            return ("name", self.name())
        if t.kind == "nat":
            self.pos += 1
            return ("nat", _nat_literal(t.text))
        if t.kind == "string":
            self.pos += 1
            return ("string", tuple(ord(c) for c in t.text))
        if self.take("int"):
            self.expect("(")
            sign = "-" if self.take("-") else ""
            token = self.tokens[self.pos]
            if token.kind != "nat":
                raise core.SourceError("int literal requires a signed decimal literal")
            self.pos += 1
            self.expect(")")
            return ("int", core._int_literal(sign + token.text))
        if self.take("string"):
            self.expect("(")
            points = []
            if not self.take(")"):
                while True:
                    token = self.tokens[self.pos]
                    if token.kind != "nat":
                        raise core.SourceError("string literal requires Unicode scalar integers")
                    self.pos += 1
                    point = _nat_literal(token.text)
                    if point > 0x10FFFF or 0xD800 <= point <= 0xDFFF:
                        raise core.SourceError("string literal contains a non-scalar codepoint")
                    points.append(point)
                    if self.take(")"):
                        break
                    self.expect(",")
            return ("string", tuple(points))
        for tag in ("true", "false"):
            if self.take(tag):
                return ("bool", tag == "true")
        if self.take("unit"):
            return ("unit",)
        if self.take("("):
            e = self.expr()
            self.expect(")")
            return e
        if self.take("enum"):
            self.expect("(")
            ident = self.name()
            self.expect(",")
            ctor = self.name()
            self.expect(")")
            return ("enum", ident, ctor)
        for tag in ("ok", "error", "none", "nil", "list"):
            if self.take(tag):
                self.expect("[")
                ty = self.typ()
                self.expect("]")
                if tag in ("none", "nil"):
                    return (tag, ty)
                self.expect("(")
                if tag == "list":
                    return ("list_literal", ty, self.args())
                v = self.expr()
                self.expect(")")
                return (tag, ty, v)
        if self.take("some"):
            self.expect("(")
            value = self.expr()
            self.expect(")")
            return ("some", value)
        if self.take("cons"):
            self.expect("(")
            head = self.expr()
            self.expect(",")
            tail = self.expr()
            self.expect(")")
            return ("cons", head, tail)
        if self.take("record"):
            ident = self.name()
            self.expect("{")
            fields = []
            if not self.take("}"):
                while True:
                    name = self.name()
                    self.expect("=")
                    fields.append((name, self.expr()))
                    if self.take("}"):
                        break
                    self.expect(",")
            return ("record", ident, fields)
        if self.take("variant"):
            ident = self.name()
            self.expect(".")
            ctor = self.name()
            self.expect("(")
            return ("variant", ident, ctor, self.args())
        if self.take("call"):
            ident = self.name()
            self.expect("(")
            return ("call", ident, self.args())
        if self.take("Int"):
            self.expect(".")
            tag = next((tag for name, tag in (("fdiv", "int_fdiv"), ("ofNat", "nat_to_int"), ("toNat", "int_to_nat")) if self.take(name)), None)
            if tag is None:
                raise core.SourceError("unknown Int operation")
            self.expect("(")
            args = self.args()
            if len(args) != (2 if tag == "int_fdiv" else 1):
                raise core.SourceError(f"{tag}: wrong arity")
            return (tag, *args)
        for built, tag in (("List", "list_fold_named"), ("Nat", "nat_fold_named")):
            if self.take(built):
                self.expect(".")
                if built == "List" and (self.peek("map") or self.peek("filter")):
                    op = "list_map_named" if self.take("map") else "list_filter_named"
                    if op == "list_filter_named":
                        self.expect("filter")
                    self.expect("(")
                    source = self.expr()
                    self.expect(";")
                    binder = self.name()
                    self.expect("=>")
                    body = self.expr()
                    self.expect(")")
                    return (op, source, binder, body)
                if built == "List" and not self.peek("fold"):
                    op = next((op for name, op in (("length", "list_length"), ("range", "list_range"), ("get", "list_get"),
                              ("append", "list_append"), ("reverse", "list_reverse"), ("sort", "list_sort"),
                              ("unique", "list_unique"), ("sum", "list_sum")) if self.take(name)), None)
                    if op is None:
                        raise core.SourceError("unknown List operation")
                    self.expect("(")
                    args = self.args()
                    if len(args) != (2 if op in ("list_get", "list_append") else 1):
                        raise core.SourceError(f"{op}: wrong arity")
                    return (op, *args)
                self.expect("fold")
                self.expect("(")
                source = self.expr()
                self.expect(",")
                initial = self.expr()
                self.expect(";")
                a = self.name()
                self.expect(",")
                b = self.name()
                core._unique([a, b], "fold binder")
                self.expect("=>")
                step = self.expr()
                self.expect(")")
                return (tag, source, initial, [a, b], step)
        raise core.SourceError(f"expected an expression at byte {t.offset}")


def _elab(enums: dict, decls: dict, helpers: dict, ctx: list[tuple[str, Any]], raw: tuple, depth: int = 0) -> tuple:
    if depth > 256:
        raise core.SourceError("elaboration exceeds depth budget")
    tag = raw[0]
    elab = lambda x, gamma=ctx: _elab(enums, decls, helpers, gamma, x, depth + 1)
    infer = lambda x: core.type_of(enums, decls, helpers, [t for _, t in ctx], x)
    if tag in ("int", "string"):
        return raw
    if tag in (*core.UNARY_OPS, "int_fdiv", "list_get", "list_append"):
        return (tag, *(elab(x) for x in raw[1:]))
    if tag == "name":
        for i, (n, _) in enumerate(ctx):
            if n == raw[1]:
                return ("var", i)
        raise core.SourceError(f"unbound local name {raw[1]}")
    if tag == "let_named":
        v = elab(raw[2])
        return ("let", v, elab(raw[3], [(raw[1], infer(v))] + ctx))
    if tag == "list_literal":
        values = [elab(x) for x in raw[2]]
        if any(infer(x) != raw[1] for x in values):
            raise core.SourceError("list literal element type differs from annotation")
        result = ("nil", raw[1])
        for value in reversed(values):
            result = ("cons", value, result)
        return result
    if tag in ("list_map_named", "list_filter_named"):
        source = elab(raw[1])
        st = infer(source)
        if not isinstance(st, tuple) or st[0] != "list":
            raise core.SourceError("List.map/filter source must have List type")
        return (tag.removesuffix("_named"), source, elab(raw[3], [(raw[2], st[1])] + ctx))
    if tag in ("list_fold_named", "nat_fold_named"):
        source, initial = elab(raw[1]), elab(raw[2])
        st, it = infer(source), infer(initial)
        if tag == "list_fold_named":
            if not isinstance(st, tuple) or st[0] != "list":
                raise core.SourceError("List.fold source must have List type")
            types = [it, st[1]]
        else:
            if st != "nat":
                raise core.SourceError("Nat.fold source must have Nat type")
            types = ["nat", it]
        bound = list(reversed(list(zip(raw[3], types)))) + ctx
        return (tag.removesuffix("_named"), source, initial, elab(raw[4], bound))
    if tag == "match_named":
        source = elab(raw[1])
        st = infer(source)
        if not isinstance(st, tuple) or st[0] not in ("result", "option", "list", "variant"):
            raise core.SourceError("match requires Result, Option, List or Variant")
        branches = raw[2]
        if st[0] == "variant":
            ct = decls[st[1]]["constructors"]
            if len(branches) != len(ct):
                raise core.SourceError("variant match must be exhaustive")
            resolved = []
            for (pattern, body), (ctor, types) in zip(branches, ct):
                if pattern[:3] != ("variant", st[1], ctor) or len(pattern[3]) != len(types):
                    raise core.SourceError("variant match identity, branch order or binder arity differs")
                bound = list(reversed(list(zip(pattern[3], types)))) + ctx
                resolved.append((ctor, elab(body, bound)))
            return ("match_variant", source, resolved)
        expected = {"result": ["ok", "error"], "option": ["none", "some"], "list": ["nil", "cons"]}[st[0]]
        if [p[0] for p, _ in branches] != expected:
            raise core.SourceError("builtin match branch order or exhaustiveness differs")
        types = {"result": [[st[2]], [st[1]]] if st[0] == "result" else [],
                 "option": [[], [st[1]]], "list": [[], [st[1], st]]}[st[0]]
        bodies = []
        for (p, body), ts in zip(branches, types):
            if len(p) != 2 or len(p[1]) != len(ts):
                raise core.SourceError("match pattern binder arity differs")
            bound = list(reversed(list(zip(p[1], ts)))) + ctx
            bodies.append(elab(body, bound))
        return ({"result": "match", "option": "match_option", "list": "match_list"}[st[0]], source, *bodies)
    if tag in ("var", "nat", "bool", "unit", "enum", "none", "nil"):
        return raw
    if tag == "bin":
        return (tag, raw[1], elab(raw[2]), elab(raw[3]))
    if tag in ("not", "some"):
        return (tag, elab(raw[1]))
    if tag in ("ok", "error"):
        return (tag, raw[1], elab(raw[2]))
    if tag == "record":
        return (tag, raw[1], [(n, elab(x)) for n, x in raw[2]])
    if tag == "project":
        return (tag, elab(raw[1]), raw[2])
    if tag == "variant":
        return (tag, raw[1], raw[2], [elab(x) for x in raw[3]])
    if tag == "call":
        return (tag, raw[1], [elab(x) for x in raw[2]])
    return (tag, *(elab(x) for x in raw[1:]))


def parse_surface(text: str, enums: dict[str, list[str]] | None = None) -> dict:
    enums = {} if enums is None else enums
    try:
        prog = Parser(text).program()
        decls, helpers = core._registry(enums, prog)
        # Match elaboration consults nominal payload declarations. Reject unknown or
        # wrong-kind references before inspecting bodies, rather than allowing a KeyError.
        for d in prog["declarations"]:
            types = ([t for _, t in d["fields"]] if d["tag"] == "record" else
                     [t for _, ts in d["constructors"] for t in ts])
            if not all(core._wf(enums, decls, t) for t in types):
                raise core.SourceError("ill-formed declaration type")
        for f in prog["helpers"] + prog["entries"]:
            if not all(core._wf(enums, decls, t) for t in f["params"] + [f["result"]]):
                raise core.SourceError(f"function {f['id']}: ill-formed signature")
        for f in prog["helpers"] + prog["entries"]:
            names = f.pop("_names")
            ctx = list(reversed(list(zip(names, f["params"]))))
            f["body"] = _elab(enums, decls, helpers, ctx, f["body"])
        core.check_program(enums, prog)
        # The closed byte decoder is part of authoring validation as well.
        core.source_bytes(prog)
        return prog
    except RecursionError:
        raise core.SourceError("surface nesting exceeds the supported depth") from None
