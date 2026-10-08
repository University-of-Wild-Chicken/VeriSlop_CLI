"""Reification between accepted Lean expressions and the contract DSL.

* `derive_profile` reads the module's declarations and registers finite enumerations, data
  symbols and Prop-valued predicate definitions mechanically.
* `reify_formula` reconstructs a DSL formula from an elaborated theorem type. Prop-valued
  predicate definitions registered in the profile are unfolded by bounded delta/beta
  reduction (the only registered reduction). Anything outside the fragment fails closed and
  the statement stays an opaque `lean_expr`.
* `denote_formula` builds the Lean expression a DSL formula denotes; the kernel tool then checks
  that it type checks and is definitionally equal to the accepted theorem type.

The reifier never emits range quantifiers: `∀ n, lo ≤ n → n < hi → p` is reified in its general
form. Choosing a bounded formula is an explicit formalization decision, not a rewrite.
"""

from __future__ import annotations

from typing import Any

from . import canonical
from .dsl import ID_RE, Profile, DSLError, ENCODING, ENCODING_V2, type_formula
from .exprjson import (
    Expr, app, beta, bvar, const, has_loose_bvar, head, head_const, lam, name_str, pi, parse_name, instantiate1,
)

LEVEL_ZERO = 0
LEVEL_ONE = 1


class Unsupported(Exception):
    pass


# ------------------------------------------------------------------------------------------
# profile derivation
# ------------------------------------------------------------------------------------------

def _pi_telescope(t: Expr) -> tuple[list[Expr], Expr]:
    doms: list[Expr] = []
    while "pi" in t:
        b = t["pi"]
        if b["bi"] != "default" or has_loose_bvar(b["body"], 0):
            raise Unsupported("dependent or implicit binder")
        doms.append(b["type"])
        t = b["body"]
        t = _lower_closed(t)
    return doms, t


def _lower_closed(e: Expr) -> Expr:
    from .exprjson import _map_bvars

    return _map_bvars(e, lambda i, d: {"bvar": i - 1} if i > d else {"bvar": i})


def _sort_of_type(t: Expr, enums_by_decl: dict[str, str], records_by_decl: dict[str, str] | None = None) -> Any:
    n, args = head_const(t)
    if n is None:
        raise Unsupported("type is not a constant application")
    if not args:
        if n in ("Nat", "Int", "Bool", "String", "Unit"):
            return n
        if n == "PUnit" and t["levels"] == [LEVEL_ONE]:
            return "Unit"
        if n in enums_by_decl:
            return {"enum": enums_by_decl[n]}
        if n in (records_by_decl or {}):
            return {"record": records_by_decl[n]}
    if n == "List" and len(args) == 1 and head(t)[0]["levels"] == [LEVEL_ZERO]:
        return {"list": _sort_of_type(args[0], enums_by_decl, records_by_decl)}
    if n == "Except" and len(args) == 2 and head(t)[0]["levels"] == [LEVEL_ZERO, LEVEL_ZERO]:
        return {"result": {"error": _sort_of_type(args[0], enums_by_decl, records_by_decl),
                           "ok": _sort_of_type(args[1], enums_by_decl, records_by_decl)}}
    raise Unsupported(f"type {n} is outside the admitted contract sorts")


def _record_fields(n: str, c: dict, decls: dict) -> tuple[str, list[tuple[str, Expr, str]]]:
    ind = c["inductive"]
    if (c.get("safety") != "safe" or c["level_params"] or c["type"] != {"sort": 1}
            or ind["num_params"] or ind["num_indices"] or ind["is_rec"] or ind["num_nested"]
            or len(ind["all"]) != 1 or len(ind["ctors"]) != 1):
        raise Unsupported("record must be a monomorphic nonrecursive single-constructor Type")
    ctor = name_str(ind["ctors"][0])
    info = decls.get(ctor, {})
    if info.get("kind") != "constructor" or info.get("level_params") or info.get("safety") != "safe":
        raise Unsupported("record constructor unavailable")
    meta = info["constructor"]
    if meta["num_params"] or meta["cidx"] or name_str(meta["induct"]) != n:
        raise Unsupported("record constructor metadata mismatch")
    fields = []
    t = info["type"]
    while "pi" in t:
        b = t["pi"]
        if b["bi"] != "default" or has_loose_bvar(b["body"], 0) or len(b["name"]) != 1:
            raise Unsupported("dependent, proof, implicit or unnamed record field")
        name = name_str(b["name"])
        if not ID_RE.fullmatch(name) or "." in name:
            raise Unsupported("record field name outside the admitted syntax")
        proj_name = n + "." + name
        proj = decls.get(proj_name, {})
        try:
            doms, cod = _pi_telescope(proj["type"])
            val = proj["value"]["lam"]
        except (KeyError, Unsupported):
            raise Unsupported("record field lacks a checked projection") from None
        if (proj.get("kind") != "definition" or proj.get("safety") != "safe" or proj.get("level_params")
                or doms != [const(n)] or cod != b["type"] or val["type"] != const(n)
                or val["bi"] != "default"
                or val["body"] != {"proj": {"struct": parse_name(n), "idx": len(fields), "expr": bvar(0)}}):
            raise Unsupported("record projection does not select its constructor field")
        fields.append((name, b["type"], proj_name))
        t = _lower_closed(b["body"])
    if t != const(n) or len(fields) != meta["num_fields"] or not 1 <= len(fields) <= 64:
        raise Unsupported("record constructor field inventory mismatch")
    return ctor, fields


def _short(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def derive_profile(profile_id: str, decls: dict[str, dict[str, Any]], decl_hashes: dict[str, str],
                   roots: set[str]) -> tuple[dict[str, Any], list[str]]:
    """Register module declarations reachable from obligation statements and bound declarations.

    Returns (profile JSON, notes). Auxiliary declarations that no statement reaches are not
    registered, so they cannot influence the profile hash.
    """
    from .exprjson import closure

    all_decls = decls
    reach = closure(roots, decls)
    decls = {n: c for n, c in decls.items() if n in reach and not any(str(x).startswith("_") for x in n.split("."))}
    notes: list[str] = []
    enums: dict[str, dict[str, Any]] = {}
    enum_decl: dict[str, str] = {}
    candidates_enum = []
    candidates_record = {}
    for n, c in decls.items():
        if c["kind"] != "inductive" or c["level_params"]:
            continue
        ind = c["inductive"]
        if ind["num_params"] or ind["num_indices"] or ind["is_rec"] or len(ind["all"]) != 1 or not ind["ctors"]:
            continue
        ctors = [name_str(x) for x in ind["ctors"]]
        if all(decls.get(k, {}).get("type") == const(n) for k in ctors):
            candidates_enum.append((n, ctors))
        else:
            try:
                candidates_record[n] = _record_fields(n, c, all_decls)
            except Unsupported as exc:
                notes.append(f"record {n} not registered: {exc}")
    short_counts: dict[str, int] = {}
    defs = [(n, c) for n, c in decls.items() if c["kind"] == "definition" and c["safety"] == "safe" and not c["level_params"]]
    for n in [x[0] for x in candidates_enum] + list(candidates_record) + [d[0] for d in defs]:
        short_counts[_short(n)] = short_counts.get(_short(n), 0) + 1

    def ident(n: str) -> str | None:
        s = _short(n)
        cand = s if short_counts.get(s, 0) == 1 else n
        return cand if ID_RE.match(cand) else None

    for n, ctors in candidates_enum:
        eid = ident(n)
        cids = [_short(k) for k in ctors]
        if eid is None or not all(ID_RE.match(x) for x in cids):
            notes.append(f"enumeration {n} has identifiers outside the DSL ID syntax; not registered")
            continue
        enums[eid] = {"lean_decl": n, "constructors": cids, "lean_constructors": ctors, "decl_hash": decl_hashes[n]}
        enum_decl[n] = eid
    records = {}
    record_decl = {}
    pending = dict(candidates_record)
    while pending:
        progress = False
        for n, (ctor, fs) in list(pending.items()):
            rid = ident(n)
            if rid is None:
                del pending[n]
                continue
            try:
                fields = [{"name": name, "sort": _sort_of_type(t, enum_decl, record_decl),
                           "lean_projection": proj, "projection_hash": decl_hashes[proj]} for name, t, proj in fs]
            except Unsupported:
                continue
            records[rid] = {"lean_decl": n, "lean_constructor": ctor, "decl_hash": decl_hashes[n],
                            "constructor_hash": decl_hashes[ctor], "fields": fields}
            record_decl[n] = rid
            del pending[n]
            progress = True
        if not progress:
            notes.extend(f"record {n} has unsupported or recursive field sorts; not registered" for n in sorted(pending))
            break
    projections = {f["lean_projection"] for r in records.values() for f in r["fields"]}
    symbols: dict[str, dict[str, Any]] = {}
    predicates: dict[str, dict[str, Any]] = {}
    for n, c in defs:
        if n in projections:
            continue
        try:
            doms, cod = _pi_telescope(c["type"])
            arg_sorts = [_sort_of_type(d, enum_decl, record_decl) for d in doms]
        except Unsupported:
            continue
        sid = ident(n)
        if sid is None:
            notes.append(f"definition {n} has an identifier outside the DSL ID syntax; not registered")
            continue
        if cod == {"sort": 0}:
            predicates[sid] = {"lean_decl": n, "args": arg_sorts, "decl_hash": decl_hashes[n]}
            continue
        try:
            res = _sort_of_type(cod, enum_decl, record_decl)
        except Unsupported:
            continue
        symbols[sid] = {"lean_decl": n, "args": arg_sorts, "result": res, "level_params": [], "decl_hash": decl_hashes[n]}
    def extended(s):
        return s in ("Int", "String") or isinstance(s, dict) and ("list" in s or "record" in s or
            "result" in s and (extended(s["result"]["error"]) or extended(s["result"]["ok"])))
    from .exprjson import constants
    extended_constants = {"Int", "String", "List", "List.nil", "List.cons", "List.length", "List.map",
                          "List.filter", "List.sum", "List.foldl", "List.append", "List.reverse", "String.append", "String.length", "String.isEmpty",
                          "Decidable.decide", "BEq.beq", "bne", "Bool.and", "Bool.or", "Bool.not"}
    data_type_used = any(constants(c["type"]) & extended_constants for c in decls.values())
    version = ENCODING_V2 if records or data_type_used or any(extended(s) for d in symbols.values() for s in [*d["args"], d["result"]]) else ENCODING
    profile = {
        "profile_id": profile_id,
        "dsl": version,
        "numeric_semantics": "Nat denotes Lean's arbitrary-precision natural numbers; sub is truncated subtraction; no machine width",
        "result_semantics": "Result(E, A) denotes Except E A; the error sort is the first parameter",
        "evaluation_semantics": "pure total functions; no I/O, mutation, concurrency or nondeterminism",
        "enums": dict(sorted(enums.items())),
        "symbols": dict(sorted(symbols.items())),
        "predicates": dict(sorted(predicates.items())),
    }
    if version == ENCODING_V2:
        profile["records"] = dict(sorted(records.items()))
        profile["numeric_semantics"] += "; Int denotes arbitrary-precision signed integers with exact add/sub/mul/neg"
        profile["data_semantics"] = "String is a sequence of Unicode scalar values; lists preserve order and duplicates; records have fixed ordered fields"
    return profile, notes


# ------------------------------------------------------------------------------------------
# Expr -> DSL
# ------------------------------------------------------------------------------------------

class _Reifier:
    def __init__(self, profile: Profile, decls: dict[str, dict[str, Any]], fuel: int = 64) -> None:
        self.p = profile
        self.decls = decls
        self.fuel = fuel
        self.enum_by_decl = {e["lean_decl"]: k for k, e in profile.enums.items()}
        self.record_by_decl = {r["lean_decl"]: k for k, r in profile.records.items()}
        self.record_ctor = {r["lean_constructor"]: k for k, r in profile.records.items()}
        self.projections = {f["lean_projection"]: (k, f["name"]) for k, r in profile.records.items() for f in r["fields"]}
        self.ctor_by_decl = {}
        for k, e in profile.enums.items():
            for short, full in zip(e["constructors"], e["lean_constructors"]):
                self.ctor_by_decl[full] = (k, short)
        self.sym_by_decl = {s["lean_decl"]: k for k, s in profile.symbols.items()}
        self.pred_by_decl = {s["lean_decl"]: k for k, s in profile.predicates.items()}
        self.unfolded: set[str] = set()

    def sort(self, t: Expr) -> Any:
        return _sort_of_type(t, self.enum_by_decl, self.record_by_decl)

    def try_sort(self, t: Expr) -> Any:
        try:
            return self.sort(t)
        except Unsupported:
            return None

    @staticmethod
    def var(i: int, ctx: list[tuple]) -> dict[str, Any]:
        if i >= len(ctx):
            raise Unsupported("loose bound variable")
        if ctx[i][0] != "var":
            raise Unsupported("statement uses a hypothesis as a term (dependent arrow)")
        k = sum(1 for e in ctx[:i] if e[0] == "var")
        return {"tag": "var", "index": k}

    def term(self, e: Expr, ctx: list[tuple]) -> dict[str, Any]:
        if "let" in e:
            if self.fuel <= 0:
                raise Unsupported("let reduction fuel exhausted")
            self.fuel -= 1
            b = e["let"]
            return self.term(instantiate1(b["body"], b["value"]), ctx)
        if "bvar" in e:
            return self.var(e["bvar"], ctx)
        if "lit" in e and "nat" in e["lit"]:
            return {"tag": "nat", "value": e["lit"]["nat"]}
        if "lit" in e and "str" in e["lit"]:
            return {"tag": "string", "value": e["lit"]["str"]}
        if "proj" in e:
            proj = e["proj"]
            rid = self.record_by_decl.get(name_str(proj["struct"]))
            if rid is None or not 0 <= proj["idx"] < len(self.p.records[rid]["fields"]):
                raise Unsupported("projection of an unregistered record")
            return {"tag": "field", "sort": rid, "field": self.p.records[rid]["fields"][proj["idx"]]["name"],
                    "value": self.term(proj["expr"], ctx)}
        n, args = head_const(e)
        if n is None:
            raise Unsupported("term head is not a constant")
        if n == "OfNat.ofNat" and len(args) == 3 and self.try_sort(args[0]) in ("Nat", "Int") and "lit" in args[1]:
            sort = self.sort(args[0])
            inst_n, inst_args = head_const(args[2])
            if inst_n == ("instOfNatNat" if sort == "Nat" else "instOfNat") and inst_args == [args[1]]:
                return {"tag": "nat" if sort == "Nat" else "int", "value": args[1]["lit"]["nat"]}
            raise Unsupported("numeral with a non-standard OfNat instance")
        if n == "Nat.cast" and len(args) == 3 and self.try_sort(args[0]) == "Int":
            # Propose the fixed builtin conversion. The candidate NatCast instance is not
            # trusted: kernel defeq against Int.ofNat must validate its actual semantics.
            return {"tag": "nat_to_int", "value": self.term(args[2], ctx)}
        if n in ("Int.ofNat", "Int.negSucc") and len(args) == 1:
            term = self.term(args[0], ctx)
            if n == "Int.ofNat" and term["tag"] != "nat":
                return {"tag": "nat_to_int", "value": term}
            if term["tag"] != "nat":
                raise Unsupported("nonliteral Int.negSucc")
            k = int(term["value"])
            return {"tag": "int", "value": str(k if n == "Int.ofNat" else -k - 1)}
        if n == "Nat.zero" and not args:
            return {"tag": "nat", "value": "0"}
        if n in ("HAdd.hAdd", "HSub.hSub", "HMul.hMul") and len(args) == 6:
            s = self.try_sort(args[0])
            if s not in ("Nat", "Int") or not all(self.try_sort(a) == s for a in args[:3]):
                raise Unsupported(f"{n} outside matching Nat or Int sorts")
            tag = {"HAdd.hAdd": "add", "HSub.hSub": "sub", "HMul.hMul": "mul"}[n]
            if s == "Int":
                tag = "int_" + tag
            return {"tag": tag, "left": self.term(args[4], ctx), "right": self.term(args[5], ctx)}
        if n in ("Nat.add", "Nat.sub", "Nat.mul") and len(args) == 2:
            tag = n.split(".")[1]
            return {"tag": tag, "left": self.term(args[0], ctx), "right": self.term(args[1], ctx)}
        if n in ("Int.add", "Int.sub", "Int.mul") and len(args) == 2:
            return {"tag": "int_" + n.split(".")[1], "left": self.term(args[0], ctx), "right": self.term(args[1], ctx)}
        if n == "Int.neg" and len(args) == 1 or n == "Neg.neg" and len(args) == 3 and self.try_sort(args[0]) == "Int":
            v = self.term(args[-1], ctx)
            return {"tag": "int", "value": str(-int(v["value"]))} if v["tag"] == "int" else {"tag": "int_neg", "value": v}
        if n in ("Bool.and", "Bool.or") and len(args) == 2:
            return {"tag": "bool_" + n.split(".")[1], "left": self.term(args[0], ctx), "right": self.term(args[1], ctx)}
        if n == "Bool.not" and len(args) == 1:
            return {"tag": "bool_not", "value": self.term(args[0], ctx)}
        if n in ("BEq.beq", "bne") and len(args) == 4:
            if self.sort(args[0]) not in ("Nat", "Int", "Bool", "String", "Unit"):
                raise Unsupported("Boolean equality of a nonprimitive sort")
            eq = {"tag": "bool_eq", "left": self.term(args[2], ctx), "right": self.term(args[3], ctx)}
            return eq if n == "BEq.beq" else {"tag": "bool_not", "value": eq}
        if n == "Decidable.decide" and len(args) == 2:
            return {"tag": "decide", "formula": self.formula(args[0], ctx)}
        if n == "HAppend.hAppend" and len(args) == 6:
            s = self.sort(args[0])
            if not all(self.sort(a) == s for a in args[:3]) or not (s == "String" or isinstance(s, dict) and "list" in s):
                raise Unsupported("append outside String or equal list sorts")
            return {"tag": "string_append" if s == "String" else "list_append",
                    "left": self.term(args[4], ctx), "right": self.term(args[5], ctx)}
        if n == "String.append" and len(args) == 2:
            return {"tag": "string_append", "left": self.term(args[0], ctx), "right": self.term(args[1], ctx)}
        if n in ("String.length", "String.isEmpty") and len(args) == 1:
            return {"tag": "string_length" if n == "String.length" else "string_is_empty", "value": self.term(args[0], ctx)}
        if n == "List.nil" and len(args) == 1:
            return {"tag": "list", "element_sort": self.sort(args[0]), "items": []}
        if n == "List.cons" and len(args) == 3:
            s = self.sort(args[0])
            tail = self.term(args[2], ctx)
            item = self.term(args[1], ctx)
            if tail["tag"] == "list" and tail["element_sort"] == s:
                return {**tail, "items": [item, *tail["items"]]}
            return {"tag": "list_cons", "head": item, "tail": tail}
        if n in ("List.length", "List.reverse") and len(args) == 2:
            self.sort(args[0])
            return {"tag": "list_length" if n == "List.length" else "list_reverse", "value": self.term(args[1], ctx)}
        if n == "List.append" and len(args) == 3:
            self.sort(args[0])
            return {"tag": "list_append", "left": self.term(args[1], ctx), "right": self.term(args[2], ctx)}
        if n == "List.sum" and len(args) == 4:
            if self.sort(args[0]) not in ("Nat", "Int"):
                raise Unsupported("sum outside Nat or Int")
            return {"tag": "list_sum", "value": self.term(args[3], ctx)}
        if n in ("List.map", "List.filter") and len(args) == (4 if n == "List.map" else 3):
            s = self.sort(args[0])
            fn = args[-2].get("lam")
            if fn is None or fn["bi"] != "default" or self.sort(fn["type"]) != s:
                raise Unsupported("map/filter requires an explicit typed lambda")
            body = self.term(fn["body"], [("var", s)] + ctx)
            return {"tag": "list_map" if n == "List.map" else "list_filter",
                    "value": self.term(args[-1], ctx), "function": {"sort": s, "body": body}}
        if n == "List.foldl" and len(args) == 5:
            acc, elem = self.sort(args[0]), self.sort(args[1])
            outer = args[2].get("lam")
            inner = outer["body"].get("lam") if outer else None
            if (outer is None or inner is None or outer["bi"] != "default" or inner["bi"] != "default"
                    or self.sort(outer["type"]) != acc or self.sort(inner["type"]) != elem):
                raise Unsupported("foldl requires an explicit typed two-binder lambda")
            body = self.term(inner["body"], [("var", elem), ("var", acc)] + ctx)
            return {"tag": "list_foldl", "value": self.term(args[4], ctx), "initial": self.term(args[3], ctx),
                    "function": {"accumulator_sort": acc, "element_sort": elem, "body": body}}
        if n in self.projections and len(args) == 1:
            rid, field = self.projections[n]
            return {"tag": "field", "sort": rid, "field": field, "value": self.term(args[0], ctx)}
        if n in self.record_ctor:
            rid = self.record_ctor[n]
            if len(args) != len(self.p.records[rid]["fields"]):
                raise Unsupported("partial record constructor")
            return {"tag": "record", "sort": rid, "fields": [self.term(a, ctx) for a in args]}
        if n in ("Bool.true", "Bool.false") and not args:
            return {"tag": "bool", "value": n == "Bool.true"}
        if n in ("Unit.unit",) and not args:
            return {"tag": "unit"}
        if n == "PUnit.unit" and not args and head(e)[0]["levels"] == [LEVEL_ONE]:
            return {"tag": "unit"}
        if n in self.ctor_by_decl and not args:
            eid, c = self.ctor_by_decl[n]
            return {"tag": "enum", "sort": eid, "constructor": c}
        if n in ("Except.ok", "Except.error") and len(args) == 3 and head(e)[0]["levels"] == [LEVEL_ZERO, LEVEL_ZERO]:
            es, os_ = self.sort(args[0]), self.sort(args[1])
            if n == "Except.ok":
                return {"tag": "ok", "error_sort": es, "value": self.term(args[2], ctx)}
            return {"tag": "error", "ok_sort": os_, "value": self.term(args[2], ctx)}
        if n in self.sym_by_decl:
            sid = self.sym_by_decl[n]
            if len(args) != len(self.p.symbols[sid]["args"]):
                raise Unsupported(f"partial application of {n}")
            return {"tag": "call", "symbol": sid, "args": [self.term(a, ctx) for a in args]}
        raise Unsupported(f"term constant {n} is not registered in the semantic profile")

    def formula(self, e: Expr, ctx: list[tuple]) -> dict[str, Any]:
        if "pi" in e:
            b = e["pi"]
            if b["bi"] != "default":
                raise Unsupported("implicit or instance binder in a statement")
            s = self.try_sort(b["type"])
            if s is not None:
                return {"tag": "forall", "sort": s, "body": self.formula(b["body"], [("var", s)] + ctx)}
            if has_loose_bvar(b["body"], 0):
                raise Unsupported("dependent arrow over a proposition")
            return {"tag": "implies", "left": self.formula(b["type"], ctx),
                    "right": self.formula(b["body"], [("proof",)] + ctx)}
        n, args = head_const(e)
        if n is None:
            raise Unsupported("formula head is not a constant")
        if n == "True" and not args:
            return {"tag": "true"}
        if n == "False" and not args:
            return {"tag": "false"}
        if n in ("And", "Or", "Iff") and len(args) == 2:
            return {"tag": n.lower(), "left": self.formula(args[0], ctx), "right": self.formula(args[1], ctx)}
        if n == "Not" and len(args) == 1:
            return {"tag": "not", "body": self.formula(args[0], ctx)}
        if n == "Eq" and len(args) == 3:
            s = self.sort(args[0])
            if s == "Bool" and head_const(args[2]) == ("Bool.true", []):
                return {"tag": "holds", "term": self.term(args[1], ctx)}
            return {"tag": "eq", "left": self.term(args[1], ctx), "right": self.term(args[2], ctx)}
        if n == "Ne" and len(args) == 3:
            self.sort(args[0])
            return {"tag": "not", "body": {"tag": "eq", "left": self.term(args[1], ctx), "right": self.term(args[2], ctx)}}
        if n in ("LT.lt", "LE.le", "GT.gt", "GE.ge") and len(args) == 4:
            if self.try_sort(args[0]) not in ("Nat", "Int"):
                raise Unsupported(f"{n} outside Nat or Int")
            a, b = self.term(args[2], ctx), self.term(args[3], ctx)
            if n in ("GT.gt", "GE.ge"):
                a, b = b, a
            return {"tag": "lt" if n in ("LT.lt", "GT.gt") else "le", "left": a, "right": b}
        if n == "Exists" and len(args) == 2 and "lam" in args[1]:
            s = self.sort(args[0])
            return {"tag": "exists", "sort": s, "body": self.formula(args[1]["lam"]["body"], [("var", s)] + ctx)}
        if n in self.pred_by_decl:
            if self.fuel <= 0:
                raise Unsupported("predicate unfolding fuel exhausted")
            self.fuel -= 1
            decl = self.decls[n]
            body = beta(decl["value"], args)
            if body is None or len(args) != len(self.p.predicates[self.pred_by_decl[n]]["args"]):
                raise Unsupported(f"predicate {n} is not a lambda telescope of its arity")
            self.unfolded.add(n)
            return self.formula(body, ctx)
        raise Unsupported(f"proposition constant {n} is not in the DSL fragment or the profile")


def reify_formula(type_expr: Expr, profile: Profile, decls: dict[str, dict[str, Any]]) -> tuple[dict[str, Any] | None, str, set[str]]:
    """Returns (formula or None, reason, unfolded predicate declarations)."""
    r = _Reifier(profile, decls)
    try:
        f = r.formula(type_expr, [])
        type_formula(f, [], profile)
    except (Unsupported, DSLError) as exc:
        return None, str(exc), set()
    return f, "reified into " + profile.encoding, r.unfolded


def predicate_constants(type_expr: Expr, profile: Profile) -> set[str]:
    """Registered predicate declarations mentioned (before unfolding) in a theorem type."""
    from .exprjson import constants

    preds = {p["lean_decl"] for p in profile.predicates.values()}
    return constants(type_expr) & preds


# ------------------------------------------------------------------------------------------
# DSL -> Expr (denotation)
# ------------------------------------------------------------------------------------------

class _Denoter:
    def __init__(self, profile: Profile) -> None:
        self.p = profile

    def sort(self, s: Any) -> Expr:
        if s in ("Nat", "Int", "Bool", "String", "Unit"):
            return const(s)
        if "enum" in s:
            return const(self.p.enums[s["enum"]]["lean_decl"])
        if "record" in s:
            return const(self.p.records[s["record"]]["lean_decl"])
        if "list" in s:
            return app(const("List", [0]), self.sort(s["list"]))
        r = s["result"]
        return app(const("Except", [LEVEL_ZERO, LEVEL_ZERO]), self.sort(r["error"]), self.sort(r["ok"]))

    @staticmethod
    def var(i: int, ctx: list[tuple]) -> tuple[Expr, Any]:
        seen = 0
        for j, entry in enumerate(ctx):
            if entry[0] == "var":
                if seen == i:
                    return bvar(j), entry[1]
                seen += 1
        raise DSLError("variable out of range")

    def nat(self, n: str) -> Expr:
        return app(const("OfNat.ofNat", [LEVEL_ZERO]), const("Nat"), {"lit": {"nat": n}},
                   app(const("instOfNatNat"), {"lit": {"nat": n}}))

    @staticmethod
    def equality_instance(s: Any) -> Expr:
        names = {"Nat": "instDecidableEqNat", "Int": "Int.instDecidableEq", "Bool": "instDecidableEqBool",
                 "String": "instDecidableEqString", "Unit": "instDecidableEqPUnit"}
        if not isinstance(s, str) or s not in names:
            raise DSLError("decidable equality outside primitive scalar sorts")
        return const(names[s], [1] if s == "Unit" else [])

    def decision(self, p: dict[str, Any], ctx: list[tuple]) -> Expr:
        tag = p["tag"]
        if tag in ("true", "false"):
            return const("instDecidableTrue" if tag == "true" else "instDecidableFalse")
        if tag in ("eq", "lt", "le"):
            a, s = self.term(p["left"], ctx)
            b, _ = self.term(p["right"], ctx)
            if tag == "eq":
                return app(self.equality_instance(s), a, b)
            if s not in ("Nat", "Int"):
                raise DSLError("decidable order outside Nat or Int")
            return app(const(s + (".decLt" if tag == "lt" else ".decLe")), a, b)
        if tag == "holds":
            a, _ = self.term(p["term"], ctx)
            return app(self.equality_instance("Bool"), a, const("Bool.true"))
        if tag == "not":
            return app(const("instDecidableNot"), self.formula(p["body"], ctx), self.decision(p["body"], ctx))
        if tag in ("and", "or", "iff", "implies"):
            a, b = self.formula(p["left"], ctx), self.formula(p["right"], ctx)
            name = {"and": "instDecidableAnd", "or": "instDecidableOr", "iff": "instDecidableIff",
                    "implies": "instDecidableForall"}[tag]
            return app(const(name), a, b, self.decision(p["left"], ctx), self.decision(p["right"], ctx))
        raise DSLError("unsupported decidable formula")

    def term(self, t: dict[str, Any], ctx: list[tuple]) -> tuple[Expr, Any]:
        tag = t["tag"]
        if tag == "var":
            return self.var(t["index"], ctx)
        if tag == "nat":
            return self.nat(t["value"]), "Nat"
        if tag == "int":
            v = int(t["value"])
            return app(const("Int.ofNat" if v >= 0 else "Int.negSucc"), {"lit": {"nat": str(v if v >= 0 else -v - 1)}}), "Int"
        if tag == "string":
            return {"lit": {"str": t["value"]}}, "String"
        if tag == "bool":
            return const("Bool.true" if t["value"] else "Bool.false"), "Bool"
        if tag == "unit":
            return const("Unit.unit"), "Unit"
        if tag == "enum":
            e = self.p.enums[t["sort"]]
            return const(e["lean_constructors"][e["constructors"].index(t["constructor"])]), {"enum": t["sort"]}
        if tag in ("add", "sub", "mul"):
            cls, inst, base = {"add": ("HAdd.hAdd", "instHAdd", "instAddNat"),
                               "sub": ("HSub.hSub", "instHSub", "instSubNat"),
                               "mul": ("HMul.hMul", "instHMul", "instMulNat")}[tag]
            nat = const("Nat")
            a, _ = self.term(t["left"], ctx)
            b, _ = self.term(t["right"], ctx)
            return app(const(cls, [0, 0, 0]), nat, nat, nat, app(const(inst, [0]), nat, const(base)), a, b), "Nat"
        if tag in ("int_add", "int_sub", "int_mul"):
            op = tag[4:]
            cls = {"add": "HAdd.hAdd", "sub": "HSub.hSub", "mul": "HMul.hMul"}[op]
            inst = {"add": "instHAdd", "sub": "instHSub", "mul": "instHMul"}[op]
            ty = const("Int")
            a, _ = self.term(t["left"], ctx)
            b, _ = self.term(t["right"], ctx)
            return app(const(cls, [0, 0, 0]), ty, ty, ty, app(const(inst, [0]), ty, const("Int.inst" + op.title())), a, b), "Int"
        if tag == "int_neg":
            v, _ = self.term(t["value"], ctx)
            return app(const("Int.neg"), v), "Int"
        if tag == "nat_to_int":
            v, _ = self.term(t["value"], ctx)
            return app(const("Int.ofNat"), v), "Int"
        if tag in ("string_length", "string_is_empty"):
            v, _ = self.term(t["value"], ctx)
            return app(const("String.length" if tag == "string_length" else "String.isEmpty"), v), "Nat" if tag == "string_length" else "Bool"
        if tag in ("bool_and", "bool_or", "bool_eq", "string_append", "list_append"):
            a, s = self.term(t["left"], ctx)
            b, _ = self.term(t["right"], ctx)
            if tag in ("bool_and", "bool_or"):
                return app(const("Bool.and" if tag == "bool_and" else "Bool.or"), a, b), "Bool"
            if tag == "bool_eq":
                inst = app(const("instBEqOfDecidableEq", [0]), self.sort(s), self.equality_instance(s))
                return app(const("BEq.beq", [0]), self.sort(s), inst, a, b), "Bool"
            if tag == "string_append":
                return app(const("String.append"), a, b), "String"
            return app(const("List.append", [0]), self.sort(s["list"]), a, b), s
        if tag == "bool_not":
            v, _ = self.term(t["value"], ctx)
            return app(const("Bool.not"), v), "Bool"
        if tag == "decide":
            p = self.formula(t["formula"], ctx)
            return app(const("Decidable.decide"), p, self.decision(t["formula"], ctx)), "Bool"
        if tag == "record":
            r = self.p.records[t["sort"]]
            return app(const(r["lean_constructor"]), *(self.term(v, ctx)[0] for v in t["fields"])), {"record": t["sort"]}
        if tag == "field":
            r = self.p.records[t["sort"]]
            f = next(f for f in r["fields"] if f["name"] == t["field"])
            v, _ = self.term(t["value"], ctx)
            return app(const(f["lean_projection"]), v), f["sort"]
        if tag == "list":
            ty = self.sort(t["element_sort"])
            value = app(const("List.nil", [0]), ty)
            for x in reversed(t["items"]):
                value = app(const("List.cons", [0]), ty, self.term(x, ctx)[0], value)
            return value, {"list": t["element_sort"]}
        if tag == "list_cons":
            x, s = self.term(t["head"], ctx)
            xs, _ = self.term(t["tail"], ctx)
            return app(const("List.cons", [0]), self.sort(s), x, xs), {"list": s}
        if tag in ("list_length", "list_reverse", "list_sum", "list_map", "list_filter"):
            xs, s = self.term(t["value"], ctx)
            elem = s["list"]
            ty = self.sort(elem)
            if tag == "list_length":
                return app(const("List.length", [0]), ty, xs), "Nat"
            if tag == "list_reverse":
                return app(const("List.reverse", [0]), ty, xs), s
            if tag == "list_sum":
                add = const("instAddNat" if elem == "Nat" else "Int.instAdd")
                of_nat = app(const("instOfNatNat" if elem == "Nat" else "instOfNat"), {"lit": {"nat": "0"}})
                zero = app(const("Zero.ofOfNat0", [0]), ty, of_nat)
                return app(const("List.sum", [0]), ty, add, zero, xs), elem
            fn = t["function"]
            body, result = self.term(fn["body"], [("var", fn["sort"])] + ctx)
            function = lam("x", ty, body)
            if tag == "list_map":
                return app(const("List.map", [0, 0]), ty, self.sort(result), function, xs), {"list": result}
            return app(const("List.filter", [0]), ty, function, xs), s
        if tag == "list_foldl":
            values, _ = self.term(t["value"], ctx)
            initial, acc = self.term(t["initial"], ctx)
            fn = t["function"]
            elem = fn["element_sort"]
            body, _ = self.term(fn["body"], [("var", elem), ("var", acc)] + ctx)
            function = lam("acc", self.sort(acc), lam("x", self.sort(elem), body))
            return app(const("List.foldl", [0, 0]), self.sort(acc), self.sort(elem), function, initial, values), acc
        if tag == "call":
            sym = self.p.symbols[t["symbol"]]
            args = [self.term(a, ctx)[0] for a in t["args"]]
            return app(const(sym["lean_decl"]), *args), sym["result"]
        if tag == "ok":
            v, s = self.term(t["value"], ctx)
            res = {"result": {"error": t["error_sort"], "ok": s}}
            return app(const("Except.ok", [0, 0]), self.sort(t["error_sort"]), self.sort(s), v), res
        if tag == "error":
            v, s = self.term(t["value"], ctx)
            res = {"result": {"error": s, "ok": t["ok_sort"]}}
            return app(const("Except.error", [0, 0]), self.sort(s), self.sort(t["ok_sort"]), v), res
        raise DSLError(tag)

    def formula(self, p: dict[str, Any], ctx: list[tuple]) -> Expr:
        tag = p["tag"]
        nat = const("Nat")
        if tag == "true":
            return const("True")
        if tag == "false":
            return const("False")
        if tag == "eq":
            a, s = self.term(p["left"], ctx)
            b, _ = self.term(p["right"], ctx)
            return app(const("Eq", [LEVEL_ONE]), self.sort(s), a, b)
        if tag in ("lt", "le"):
            a, s = self.term(p["left"], ctx)
            b, _ = self.term(p["right"], ctx)
            cls = "LT.lt" if tag == "lt" else "LE.le"
            inst = ("instLTNat" if tag == "lt" else "instLENat") if s == "Nat" else ("Int.instLTInt" if tag == "lt" else "Int.instLEInt")
            return app(const(cls, [0]), self.sort(s), const(inst), a, b)
        if tag == "holds":
            a, _ = self.term(p["term"], ctx)
            return app(const("Eq", [LEVEL_ONE]), const("Bool"), a, const("Bool.true"))
        if tag == "not":
            return app(const("Not"), self.formula(p["body"], ctx))
        if tag in ("and", "or", "iff"):
            return app(const({"and": "And", "or": "Or", "iff": "Iff"}[tag]),
                       self.formula(p["left"], ctx), self.formula(p["right"], ctx))
        if tag == "implies":
            return pi("h", self.formula(p["left"], ctx), self.formula(p["right"], [("proof",)] + ctx))
        if tag == "forall":
            return pi("x", self.sort(p["sort"]), self.formula(p["body"], [("var", p["sort"])] + ctx))
        if tag == "exists":
            t = self.sort(p["sort"])
            return app(const("Exists", [LEVEL_ONE]), t, lam("x", t, self.formula(p["body"], [("var", p["sort"])] + ctx)))
        if tag == "forall_range":
            lo, _ = self.term(p["lower"], [("proof",)] + ctx)
            hi, _ = self.term(p["upper"], [("proof",), ("proof",)] + ctx)
            body = self.formula(p["body"], [("proof",), ("proof",), ("var", "Nat")] + ctx)
            le = app(const("LE.le", [0]), nat, const("instLENat"), lo, bvar(0))
            lt = app(const("LT.lt", [0]), nat, const("instLTNat"), bvar(1), hi)
            return pi("n", nat, pi("h", le, pi("h", lt, body)))
        if tag == "exists_range":
            lo, _ = self.term(p["lower"], [("proof",)] + ctx)
            hi, _ = self.term(p["upper"], [("proof",)] + ctx)
            body = self.formula(p["body"], [("var", "Nat")] + ctx)
            le = app(const("LE.le", [0]), nat, const("instLENat"), lo, bvar(0))
            lt = app(const("LT.lt", [0]), nat, const("instLTNat"), bvar(0), hi)
            return app(const("Exists", [LEVEL_ONE]), nat,
                       lam("n", nat, app(const("And"), le, app(const("And"), lt, body))))
        raise DSLError(tag)


def denote_formula(formula: dict[str, Any], profile: Profile) -> Expr:
    return _Denoter(profile).formula(formula, [])


def statement_hash(*, encoding: str, profile_id: str, profile_hash: str, toolchain: str,
                   payload: Any, referenced: dict[str, str]) -> str:
    return canonical.digest_json({
        "schema_version": "0.1",
        "encoding": encoding,
        "semantic_profile": profile_id,
        "profile_registry_hash": profile_hash,
        "lean_toolchain": toolchain,
        "payload": payload,
        "referenced_definitions": dict(sorted(referenced.items())),
    })
