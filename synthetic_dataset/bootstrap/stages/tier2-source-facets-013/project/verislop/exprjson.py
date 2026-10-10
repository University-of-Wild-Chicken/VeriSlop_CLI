"""Helpers over the kernel tool's Expr JSON (de Bruijn indices, flattened applications).

Identity hashes drop binder display names (alpha-normalisation via de Bruijn indices), keep
binder infos (implicit/instance arguments are semantic), and replace universe parameter names
by their position in the declaration.
"""

from __future__ import annotations

import re
from typing import Any

from . import canonical

_IDENT = re.compile(r"^[A-Za-z_À-￿][A-Za-z0-9_'!?À-￿]*$")

Expr = dict[str, Any]


def name_str(comps: list) -> str:
    parts = []
    for c in comps:
        if isinstance(c, int):
            parts.append(str(c))
        elif _IDENT.match(c):
            parts.append(c)
        else:
            parts.append("«" + c + "»")
    return ".".join(parts)


def parse_name(text: str) -> list:
    comps: list = []
    cur = ""
    i = 0
    escaped = False
    while i < len(text):
        ch = text[i]
        if ch == "«":
            j = text.find("»", i + 1)
            if j == -1:
                raise ValueError(f"unterminated « in name {text!r}")
            cur += text[i + 1 : j]
            escaped = True
            i = j + 1
            continue
        if ch == ".":
            comps.append(_component(cur, escaped))
            cur, escaped = "", False
        else:
            cur += ch
        i += 1
    comps.append(_component(cur, escaped))
    if any(c == "" for c in comps):
        raise ValueError(f"invalid Lean name {text!r}")
    return comps


def _component(text: str, escaped: bool) -> Any:
    if not escaped and text.isdigit():
        return int(text)
    return text


def const(name: str, levels: list | None = None) -> Expr:
    return {"const": parse_name(name), "levels": levels or []}


def app(fn: Expr, *args: Expr) -> Expr:
    if not args:
        return fn
    if "app" in fn:
        return {"app": fn["app"] + list(args)}
    return {"app": [fn, *args]}


def bvar(i: int) -> Expr:
    return {"bvar": i}


def pi(name: str, type_: Expr, body: Expr, bi: str = "default") -> Expr:
    return {"pi": {"name": [name], "bi": bi, "type": type_, "body": body}}


def lam(name: str, type_: Expr, body: Expr, bi: str = "default") -> Expr:
    return {"lam": {"name": [name], "bi": bi, "type": type_, "body": body}}


def nat_lit(n: int) -> Expr:
    return {"lit": {"nat": str(n)}}


def head(e: Expr) -> tuple[Expr, list[Expr]]:
    if "app" in e:
        return e["app"][0], e["app"][1:]
    return e, []


def const_name(e: Expr) -> str | None:
    return name_str(e["const"]) if "const" in e else None


def head_const(e: Expr) -> tuple[str | None, list[Expr]]:
    fn, args = head(e)
    return const_name(fn), args


def constants(e: Any, acc: set[str] | None = None) -> set[str]:
    acc = set() if acc is None else acc
    stack = [e]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            if "const" in x:
                acc.add(name_str(x["const"]))
                continue
            stack.extend(v for k, v in x.items() if k != "name")
        elif isinstance(x, list):
            stack.extend(x)
    return acc


def _map_bvars(e: Expr, f, depth: int = 0) -> Expr:
    if "bvar" in e:
        return f(e["bvar"], depth)
    if "app" in e:
        return {"app": [_map_bvars(x, f, depth) for x in e["app"]]}
    for key in ("lam", "pi"):
        if key in e:
            b = e[key]
            return {key: {**b, "type": _map_bvars(b["type"], f, depth), "body": _map_bvars(b["body"], f, depth + 1)}}
    if "let" in e:
        b = e["let"]
        return {"let": {**b, "type": _map_bvars(b["type"], f, depth), "value": _map_bvars(b["value"], f, depth),
                        "body": _map_bvars(b["body"], f, depth + 1)}}
    if "proj" in e:
        p = e["proj"]
        return {"proj": {**p, "expr": _map_bvars(p["expr"], f, depth)}}
    return e


def has_loose_bvar(e: Expr, k: int) -> bool:
    found = []

    def f(i: int, depth: int) -> Expr:
        if i == k + depth:
            found.append(True)
        return {"bvar": i}

    _map_bvars(e, f)
    return bool(found)


def loose_bvar_range(e: Expr) -> int:
    """1 + the largest loose bvar index (0 if closed)."""
    top = [0]

    def f(i: int, depth: int) -> Expr:
        if i >= depth:
            top[0] = max(top[0], i - depth + 1)
        return {"bvar": i}

    _map_bvars(e, f)
    return top[0]


def lift(e: Expr, n: int, cutoff: int = 0) -> Expr:
    if n == 0:
        return e
    return _map_bvars(e, lambda i, d: {"bvar": i + n} if i >= cutoff + d else {"bvar": i})


def instantiate1(body: Expr, arg: Expr) -> Expr:
    """Replace loose bvar 0 by arg and lower the other loose bvars (beta step)."""
    def f(i: int, depth: int) -> Expr:
        if i < depth:
            return {"bvar": i}
        if i == depth:
            return lift(arg, depth)
        return {"bvar": i - 1}

    return _map_bvars(body, f)


def beta(fn: Expr, args: list[Expr]) -> Expr | None:
    e = fn
    for a in args:
        if "lam" not in e:
            return None
        e = instantiate1(e["lam"]["body"], a)
    return e


# ------------------------------------------------------------------------------------------
# canonical identity
# ------------------------------------------------------------------------------------------

def canon(e: Any, level_params: list[str]) -> Any:
    if isinstance(e, list):
        return [canon(x, level_params) for x in e]
    if not isinstance(e, dict):
        return e
    if "param" in e and len(e) == 1:
        n = name_str(e["param"])
        return {"param_index": level_params.index(n)} if n in level_params else {"param": n}
    if "const" in e:
        return {"const": name_str(e["const"]), "levels": canon(e["levels"], level_params)}
    out = {}
    for k, v in e.items():
        if k == "name":
            continue
        out[k] = canon(v, level_params)
    return out


def decl_identity(c: dict[str, Any]) -> dict[str, Any]:
    lps = [name_str(n) for n in c.get("level_params", [])]
    ident: dict[str, Any] = {
        "kind": c["kind"],
        "safety": c.get("safety"),
        "num_level_params": len(lps),
        "type": canon(c["type"], lps),
    }
    if c["kind"] in ("definition", "opaque"):
        ident["value"] = canon(c["value"], lps)
    if c["kind"] == "inductive":
        ind = dict(c["inductive"])
        ind["all"] = [name_str(n) for n in ind["all"]]
        ind["ctors"] = [name_str(n) for n in ind["ctors"]]
        ident["inductive"] = ind
    if c["kind"] == "constructor":
        ctor = dict(c["constructor"])
        ctor["induct"] = name_str(ctor["induct"])
        ident["constructor"] = ctor
    return ident


def decl_hash(c: dict[str, Any]) -> str:
    """Theorems contribute their type only (proof irrelevance); definitions their value too."""
    return canonical.digest_json(decl_identity(c))


def semantic_refs(c: dict[str, Any]) -> set[str]:
    """Constants a declaration's *meaning* depends on (not proof terms of theorems)."""
    refs = constants(c["type"])
    if c["kind"] in ("definition", "opaque"):
        refs |= constants(c["value"])
    if c["kind"] == "inductive":
        refs |= {name_str(n) for n in c["inductive"]["ctors"]}
    if c["kind"] == "constructor":
        refs.add(name_str(c["constructor"]["induct"]))
    return refs


def closure(roots: set[str], decls: dict[str, dict[str, Any]]) -> set[str]:
    """Transitive semantic closure within the module's declarations."""
    seen: set[str] = set()
    stack = [r for r in roots if r in decls]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        for d in semantic_refs(decls[n]):
            if d in decls and d not in seen:
                stack.append(d)
    return seen
