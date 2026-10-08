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
from .dsl import ID_RE, Profile, DSLError, type_formula
from .exprjson import (
    Expr, app, beta, bvar, const, has_loose_bvar, head, head_const, lam, name_str, pi,
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


def _sort_of_type(t: Expr, enums_by_decl: dict[str, str]) -> Any:
    n, args = head_const(t)
    if n is None:
        raise Unsupported("type is not a constant application")
    if not args:
        if n == "Nat":
            return "Nat"
        if n == "Bool":
            return "Bool"
        if n == "Unit":
            return "Unit"
        if n == "PUnit" and t["levels"] == [LEVEL_ONE]:
            return "Unit"
        if n in enums_by_decl:
            return {"enum": enums_by_decl[n]}
    if n == "Except" and len(args) == 2 and head(t)[0]["levels"] == [LEVEL_ZERO, LEVEL_ZERO]:
        return {"result": {"error": _sort_of_type(args[0], enums_by_decl), "ok": _sort_of_type(args[1], enums_by_decl)}}
    raise Unsupported(f"type {n} is outside the DSL v0.1 sorts")


def _short(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def derive_profile(profile_id: str, decls: dict[str, dict[str, Any]], decl_hashes: dict[str, str],
                   roots: set[str]) -> tuple[dict[str, Any], list[str]]:
    """Register module declarations reachable from obligation statements and bound declarations.

    Returns (profile JSON, notes). Auxiliary declarations that no statement reaches are not
    registered, so they cannot influence the profile hash.
    """
    from .exprjson import closure

    reach = closure(roots, decls)
    decls = {n: c for n, c in decls.items() if n in reach and not any(str(x).startswith("_") for x in n.split("."))}
    notes: list[str] = []
    enums: dict[str, dict[str, Any]] = {}
    enum_decl: dict[str, str] = {}
    candidates_enum = []
    for n, c in decls.items():
        if c["kind"] != "inductive" or c["level_params"]:
            continue
        ind = c["inductive"]
        if ind["num_params"] or ind["num_indices"] or ind["is_rec"] or len(ind["all"]) != 1 or not ind["ctors"]:
            continue
        ctors = [name_str(x) for x in ind["ctors"]]
        if not all(decls.get(k, {}).get("type") == const(n) for k in ctors):
            continue  # not all constructors nullary
        candidates_enum.append((n, ctors))
    short_counts: dict[str, int] = {}
    defs = [(n, c) for n, c in decls.items() if c["kind"] == "definition" and c["safety"] == "safe" and not c["level_params"]]
    for n in [x[0] for x in candidates_enum] + [d[0] for d in defs]:
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
    symbols: dict[str, dict[str, Any]] = {}
    predicates: dict[str, dict[str, Any]] = {}
    for n, c in defs:
        try:
            doms, cod = _pi_telescope(c["type"])
            arg_sorts = [_sort_of_type(d, enum_decl) for d in doms]
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
            res = _sort_of_type(cod, enum_decl)
        except Unsupported:
            continue
        symbols[sid] = {"lean_decl": n, "args": arg_sorts, "result": res, "level_params": [], "decl_hash": decl_hashes[n]}
    profile = {
        "profile_id": profile_id,
        "dsl": "verislop.contract-dsl/0.1",
        "numeric_semantics": "Nat denotes Lean's arbitrary-precision natural numbers; sub is truncated subtraction; no machine width",
        "result_semantics": "Result(E, A) denotes Except E A; the error sort is the first parameter",
        "evaluation_semantics": "pure total functions; no I/O, mutation, concurrency or nondeterminism",
        "enums": dict(sorted(enums.items())),
        "symbols": dict(sorted(symbols.items())),
        "predicates": dict(sorted(predicates.items())),
    }
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
        self.ctor_by_decl = {}
        for k, e in profile.enums.items():
            for short, full in zip(e["constructors"], e["lean_constructors"]):
                self.ctor_by_decl[full] = (k, short)
        self.sym_by_decl = {s["lean_decl"]: k for k, s in profile.symbols.items()}
        self.pred_by_decl = {s["lean_decl"]: k for k, s in profile.predicates.items()}
        self.unfolded: set[str] = set()

    def sort(self, t: Expr) -> Any:
        return _sort_of_type(t, self.enum_by_decl)

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
        if "bvar" in e:
            return self.var(e["bvar"], ctx)
        if "lit" in e and "nat" in e["lit"]:
            return {"tag": "nat", "value": e["lit"]["nat"]}
        n, args = head_const(e)
        if n is None:
            raise Unsupported("term head is not a constant")
        if n == "OfNat.ofNat" and len(args) == 3 and self.try_sort(args[0]) == "Nat" and "lit" in args[1]:
            inst_n, inst_args = head_const(args[2])
            if inst_n == "instOfNatNat" and inst_args == [args[1]]:
                return {"tag": "nat", "value": args[1]["lit"]["nat"]}
            raise Unsupported("numeral with a non-standard OfNat instance")
        if n == "Nat.zero" and not args:
            return {"tag": "nat", "value": "0"}
        if n in ("HAdd.hAdd", "HSub.hSub", "HMul.hMul") and len(args) == 6:
            if not all(self.try_sort(a) == "Nat" for a in args[:3]):
                raise Unsupported(f"{n} outside Nat")
            tag = {"HAdd.hAdd": "add", "HSub.hSub": "sub", "HMul.hMul": "mul"}[n]
            return {"tag": tag, "left": self.term(args[4], ctx), "right": self.term(args[5], ctx)}
        if n in ("Nat.add", "Nat.sub", "Nat.mul") and len(args) == 2:
            tag = n.split(".")[1]
            return {"tag": tag, "left": self.term(args[0], ctx), "right": self.term(args[1], ctx)}
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
            if self.try_sort(args[0]) != "Nat":
                raise Unsupported(f"{n} outside Nat")
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
    return f, "reified into verislop.contract-dsl/0.1", r.unfolded


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
        if s == "Nat":
            return const("Nat")
        if s == "Bool":
            return const("Bool")
        if s == "Unit":
            return const("Unit")
        if "enum" in s:
            return const(self.p.enums[s["enum"]]["lean_decl"])
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

    def term(self, t: dict[str, Any], ctx: list[tuple]) -> tuple[Expr, Any]:
        tag = t["tag"]
        if tag == "var":
            return self.var(t["index"], ctx)
        if tag == "nat":
            return self.nat(t["value"]), "Nat"
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
            a, _ = self.term(p["left"], ctx)
            b, _ = self.term(p["right"], ctx)
            cls, inst = ("LT.lt", "instLTNat") if tag == "lt" else ("LE.le", "instLENat")
            return app(const(cls, [0]), nat, const(inst), a, b)
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
