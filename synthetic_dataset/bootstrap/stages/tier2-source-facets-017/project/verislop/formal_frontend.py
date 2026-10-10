"""Prototype untrusted typed formalizer AST → canonical Lean candidate, never accepted IR.

The frontend is deliberately a candidate compiler. Kernel replay, theorem denotation checks,
proof/witness audits and AST-derived downstream export remain mandatory. This module performs
no model calls, introduces no task templates and does not repair or strengthen formulas.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from . import canonical, dsl, native_contract, reify, source_contract
from .exprjson import app, bvar, const, parse_name, pi

VERSION = "verislop.formalizer-ast/0.1"
COMPILER = "verislop.formalizer-ast-compiler/0.1"
VERSION_V2 = "verislop.formalizer-ast/0.2"
COMPILER_V2 = "verislop.formalizer-ast-compiler/0.2"
SUPPORTED_VERSIONS = (VERSION, VERSION_V2)
NAMESPACE = "VeriSlopAST"
TOOLCHAIN = "leanprover/lean4:v4.34.1"
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_DECLARATIONS = 128
MAX_RESPONSE_BYTES = 1 << 20
MAX_ENUM_CONSTRUCTORS = 64
MAX_TOTAL_ENUM_CONSTRUCTORS = 4096
# These declarations are emitted by the pinned Lean nullary-inductive/structure
# elaborators. Proposal constructors/projections cannot overwrite that machinery.
GENERATED_TYPE_MEMBERS = {"rec", "recOn", "casesOn", "noConfusion", "noConfusionType",
    "ctorIdx", "ctorElim", "ctorElimType", "ofNat", "ofNat_ctorIdx", "_sizeOf_1", "_sizeOf_inst"}
GENERATED_SINGLETON_MEMBERS = GENERATED_TYPE_MEMBERS - {"ctorElim", "ctorElimType"}
GENERATED_RECORD_MEMBERS = GENERATED_SINGLETON_MEMBERS - {"ofNat", "ofNat_ctorIdx"} | {"mk"}
RESERVED_DECLARATIONS = {"Nat", "Int", "Bool", "String", "List", "Option", "Except", "Unit", "PUnit", "True", "False",
    "Eq", "LT", "LE", "Decidable", "HAdd", "HSub", "HMul", "OfNat", "NatCast", "And", "Or", "Not",
    "Iff", "Exists", "BEq", "decide", "cond", "sorryAx", NAMESPACE, "VeriSlop", "Native"}


class FrontendError(ValueError):
    """Stable structural/typing feedback for the untrusted proposal's next repair attempt."""
    def __init__(self, path: str, message: str):
        self.path, self.message = path, message
        super().__init__(f"{path}: {message}")


def _shape(value: Any, fields: set[str], path: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise FrontendError(path, f"expected an object with exactly {sorted(fields)}")


def _ident(value: Any, path: str) -> str:
    if not isinstance(value, str) or not IDENT.fullmatch(value) or value.startswith("_vs_"):
        raise FrontendError(path, "identifier must match [A-Za-z_][A-Za-z0-9_]*; _vs_ prefix is reserved")
    return value


def _mapping(value: Any, path: str) -> dict:
    if not isinstance(value, dict) or len(value) > MAX_DECLARATIONS:
        raise FrontendError(path, f"expected an object with at most {MAX_DECLARATIONS} entries")
    return value


def compiler_for_version(version: str) -> str:
    if version == VERSION:
        return COMPILER
    if version == VERSION_V2:
        return COMPILER_V2
    raise FrontendError("encoding", f"expected one of {SUPPORTED_VERSIONS}")


def _ordered(graph: dict[str, set[str]], path: str) -> list[str]:
    result, done, visiting = [], set(), set()
    def visit(node):
        if node in done:
            return
        if node in visiting:
            raise FrontendError(path, f"cyclic definition or record dependency involving {node}")
        visiting.add(node)
        for child in sorted(graph[node]):
            if child not in graph:
                raise FrontendError(path, f"unknown dependency {child}")
            visit(child)
        visiting.remove(node)
        done.add(node)
        result.append(node)
    for node in sorted(graph):
        visit(node)
    return result


def _record_refs(sort: Any) -> set[str]:
    if isinstance(sort, dict):
        if "record" in sort:
            return {sort["record"]}
        if "list" in sort:
            return _record_refs(sort["list"])
        if "option" in sort:
            return _record_refs(sort["option"])
        if "result" in sort:
            return _record_refs(sort["result"]["error"]) | _record_refs(sort["result"]["ok"])
    return set()


def _quoted(name: str) -> str:
    # Only validated ASCII identifiers reach here, including Lean keywords.
    return "«" + name + "»"


def _lean_name(name: str) -> str:
    return NAMESPACE + "." + name


def _reference(name: str) -> str:
    return "_root_." + NAMESPACE + "." + _quoted(name)


def _string(value: str) -> str:
    # Lean supports \xHH and \uHHHH, but not JSON's \b/\f or surrogate-pair escapes.
    pieces = []
    escapes = {'"': '\\"', '\\': '\\\\', '\n': '\\n', '\r': '\\r', '\t': '\\t'}
    for ch in value:
        pieces.append(escapes.get(ch, f"\\x{ord(ch):02x}" if ord(ch) < 32 or ord(ch) == 127 else ch))
    return '"' + ''.join(pieces) + '"'


def _walk_variables(node: Any, mapper, depth: int = 0) -> Any:
    """Map de Bruijn variables while preserving quantifier and typed-lambda scopes."""
    if isinstance(node, list):
        return [_walk_variables(value, mapper, depth) for value in node]
    if not isinstance(node, dict):
        return node
    if node.get("tag") == "var":
        return mapper(node["index"], depth)
    result = {}
    for key, value in node.items():
        inner = depth
        if key == "body" and node.get("tag") in dsl.QUANTIFIERS + dsl.RANGE_QUANTIFIERS:
            inner += 1
        if key == "function" and node.get("tag") in ("list_map", "list_filter", "list_foldl"):
            result[key] = {**value, "body": _walk_variables(value["body"], mapper,
                           depth + (2 if node["tag"] == "list_foldl" else 1))}
        else:
            result[key] = _walk_variables(value, mapper, inner)
    return result


def _instantiate_predicate(body: dict, args: list[dict]) -> dict:
    def replace(index, depth):
        if index < depth:
            return {"tag": "var", "index": index}
        parameter = index - depth
        if parameter >= len(args):
            raise FrontendError("predicate", "loose variable in predicate definition")
        return _walk_variables(args[len(args) - parameter - 1],
            lambda i, d: {"tag": "var", "index": i + depth if i >= d else i})
    return _walk_variables(body, replace)


def _predicate_dependencies(node: Any) -> set[str]:
    if isinstance(node, list):
        return set().union(*(_predicate_dependencies(value) for value in node))
    if not isinstance(node, dict):
        return set()
    deps = set()
    if node.get("tag") == "predicate":
        name = _ident(node.get("predicate"), "predicate reference")
        deps.add(name)
    return deps | set().union(*(_predicate_dependencies(value) for value in node.values()))


class _Expander:
    """Frontend predicate calls disappear before standard DSL validation/denotation.

    Source rendering retains actual predicate constants so semantic-closure witness checks
    can see them. Macro substitution shifts variables through quantifiers, map and fold.
    """
    def __init__(self, profile: dsl.Profile, predicates: dict):
        self.profile, self.predicates = profile, predicates
        self.cache, self.visiting = {}, set()
        self.steps = dsl.LIMITS["max_nodes"]

    def predicate(self, name: str) -> dict:
        if name not in self.predicates:
            raise FrontendError("predicate", f"unknown predicate {name}")
        if name in self.visiting:
            raise FrontendError("predicate", f"cyclic predicate dependency involving {name}")
        if name not in self.cache:
            self.visiting.add(name)
            row = self.predicates[name]
            expanded = self.node(row["formula"], list(reversed(row["args"])))
            dsl.type_formula(expanded, list(reversed(row["args"])), self.profile)
            self.cache[name] = expanded
            self.visiting.remove(name)
        return self.cache[name]

    def node(self, node: Any, ctx: list[Any], depth: int = 0) -> Any:
        self.steps -= 1
        if self.steps < 0 or depth > dsl.LIMITS["max_depth"]:
            raise FrontendError("predicate expansion", "node/depth budget exhausted")
        if isinstance(node, list):
            return [self.node(value, ctx, depth + 1) for value in node]
        if not isinstance(node, dict):
            return node
        tag = node.get("tag")
        if tag == "predicate":
            _shape(node, {"tag", "predicate", "args"}, "predicate application")
            name = _ident(node["predicate"], "predicate application")
            if name not in self.predicates or not isinstance(node["args"], list):
                raise FrontendError("predicate application", "known predicate and argument array required")
            args = [self.node(arg, ctx, depth + 1) for arg in node["args"]]
            expected = self.predicates[name]["args"]
            if len(args) != len(expected) or any(not dsl.sort_eq(dsl.type_term(arg, ctx, self.profile), sort)
                                               for arg, sort in zip(args, expected)):
                raise FrontendError("predicate application", "argument arity/sorts differ from predicate signature")
            return _instantiate_predicate(self.predicate(name), args)
        result = {}
        for key, value in node.items():
            inner_ctx = ctx
            if key == "body" and tag in dsl.QUANTIFIERS + dsl.RANGE_QUANTIFIERS:
                inner_ctx = [("Nat" if tag in dsl.RANGE_QUANTIFIERS else node["sort"])] + ctx
            if key == "function" and tag in ("list_map", "list_filter", "list_foldl"):
                binders = [value["element_sort"], value["accumulator_sort"]] if tag == "list_foldl" else [value["sort"]]
                result[key] = {**value, "body": self.node(value["body"], binders + ctx, depth + 1)}
            else:
                result[key] = self.node(value, inner_ctx, depth + 1)
        return result


class _Renderer:
    def __init__(self, profile: dsl.Profile, expander: _Expander):
        self.p, self.expander = profile, expander

    def term_sort(self, term: dict, ctx: list[Any]) -> Any:
        return dsl.type_term(self.expander.node(term, ctx), ctx, self.p)

    def equality(self, sort: Any) -> str:
        if isinstance(sort, dict) and set(sort) == {"enum"}:
            # This identity is an untrusted compiler output. The compiler audit
            # must typecheck it against the actual compiled declarations; the
            # accepted registry derives its separate hash-bound binding later.
            name = self.p.enums[sort["enum"]]["candidate_decidable_eq"]["lean_decl"]
            return "_root_." + NAMESPACE + "." + _quoted(name.removeprefix(NAMESPACE + "."))
        return "_root_." + {"Nat": "instDecidableEqNat", "Int": "Int.instDecidableEq",
            "String": "instDecidableEqString", "Bool": "instDecidableEqBool", "Unit": "instDecidableEqPUnit"}[sort]

    def decision(self, formula: dict, names: list[str], ctx: list[Any]) -> str:
        """Render only the fixed computable decisions also built by the denoter."""
        formula = self.expander.node(formula, ctx)
        tag = formula["tag"]
        if tag in ("true", "false"):
            return "_root_.instDecidableTrue" if tag == "true" else "_root_.instDecidableFalse"
        if tag in ("eq", "lt", "le"):
            sort = self.term_sort(formula["left"], ctx)
            left, right = (self.term(formula[key], names, ctx) for key in ("left", "right"))
            if tag == "eq":
                instance = self.equality(sort)
            elif sort == "String":
                instance = "_root_.String." + ("decidableLT" if tag == "lt" else "decLE")
            else:
                instance = "_root_." + sort + (".decLt" if tag == "lt" else ".decLe")
            return f"({instance} {left} {right})"
        if tag == "holds":
            return f"(_root_.instDecidableEqBool {self.term(formula['term'], names, ctx)} _root_.Bool.true)"
        if tag == "not":
            return f"(@_root_.instDecidableNot {self.formula(formula['body'], names, ctx)} {self.decision(formula['body'], names, ctx)})"
        if tag in dsl.CONNECTIVES:
            instance = {"and": "instDecidableAnd", "or": "instDecidableOr", "iff": "instDecidableIff",
                        "implies": "instDecidableForall"}[tag]
            args = [self.formula(formula[key], names, ctx) for key in ("left", "right")]
            args.extend(self.decision(formula[key], names, ctx) for key in ("left", "right"))
            return "(@_root_." + instance + " " + " ".join(args) + ")"
        raise FrontendError("decision", "unsupported decidable formula")

    def sort(self, sort: Any) -> str:
        if isinstance(sort, str):
            return "_root_." + sort
        if "record" in sort:
            return _reference(sort["record"])
        if "enum" in sort:
            return _reference(sort["enum"])
        if "list" in sort:
            return f"(_root_.List {self.sort(sort['list'])})"
        if "option" in sort:
            return f"(_root_.Option {self.sort(sort['option'])})"
        if "result" in sort:
            return f"(_root_.Except {self.sort(sort['result']['error'])} {self.sort(sort['result']['ok'])})"
        raise FrontendError("sort", "finite enum declarations are outside this frontend version")

    def term(self, term: dict, names: list[str], ctx: list[Any]) -> str:
        tag = term["tag"]
        sub = lambda value: self.term(value, names, ctx)
        if tag == "var":
            return names[term["index"]]
        if tag == "nat":
            return f"({term['value']} : _root_.Nat)"
        if tag == "int":
            n = int(term["value"])
            return f"(_root_.Int.ofNat {n})" if n >= 0 else f"(_root_.Int.negSucc {-n - 1})"
        if tag == "string":
            return _string(term["value"])
        if tag == "bool":
            return "_root_.Bool.true" if term["value"] else "_root_.Bool.false"
        if tag == "unit":
            return "_root_.Unit.unit"
        if tag == "enum":
            return _reference(term["sort"]) + "." + _quoted(term["constructor"])
        if tag == "none":
            return f"(@_root_.Option.none {self.sort(term['element_sort'])})"
        if tag == "some":
            elem = self.term_sort(term["value"], ctx)
            return f"(@_root_.Option.some {self.sort(elem)} {sub(term['value'])})"
        if tag in ("option_get_or", "option_is_some"):
            elem = self.term_sort(term["value"], ctx)["option"]
            name = "Option.getD" if tag == "option_get_or" else "Option.isSome"
            tail = " " + sub(term["default"]) if tag == "option_get_or" else ""
            return f"(@_root_.{name} {self.sort(elem)} {sub(term['value'])}{tail})"
        if tag == "ite":
            result = self.term_sort(term["then"], ctx)
            return f"(@_root_.cond {self.sort(result)} {sub(term['condition'])} {sub(term['then'])} {sub(term['else'])})"
        if tag in dsl.NAT_OPS + dsl.INT_OPS + ("int_fdiv",):
            op = "Nat." + tag if tag in dsl.NAT_OPS else "Int." + tag[4:]
            return f"(_root_.{op} {sub(term['left'])} {sub(term['right'])})"
        if tag in ("int_neg", "nat_to_int", "int_to_nat", "bool_not", "string_length", "string_is_empty"):
            op = {"int_neg": "Int.neg", "nat_to_int": "Int.ofNat", "bool_not": "Bool.not",
                  "int_to_nat": "Int.toNat", "string_length": "String.length", "string_is_empty": "String.isEmpty"}[tag]
            return f"(_root_.{op} {sub(term['value'])})"
        if tag == "list_range":
            return f"(_root_.List.range {sub(term['stop'])})"
        if tag in ("bool_and", "bool_or", "string_append"):
            op = {"bool_and": "Bool.and", "bool_or": "Bool.or", "string_append": "String.append"}[tag]
            return f"(_root_.{op} {sub(term['left'])} {sub(term['right'])})"
        if tag == "bool_eq":
            if self.p.enums:
                sort = self.term_sort(term["left"], ctx)
                if isinstance(sort, dict) and "enum" in sort:
                    return f"(@_root_.Decidable.decide ({sub(term['left'])} = {sub(term['right'])}) ({self.equality(sort)} {sub(term['left'])} {sub(term['right'])}))"
            return f"(_root_.Decidable.decide ({sub(term['left'])} = {sub(term['right'])}))"
        if tag == "decide":
            if self.p.enums:
                return f"(@_root_.Decidable.decide {self.formula(term['formula'], names, ctx)} {self.decision(term['formula'], names, ctx)})"
            return f"(_root_.Decidable.decide {self.formula(term['formula'], names, ctx)})"
        if tag == "record":
            return f"({_reference(term['sort'])}.«mk» {' '.join(sub(value) for value in term['fields'])})"
        if tag == "field":
            return f"({_reference(term['sort'])}.{_quoted(term['field'])} {sub(term['value'])})"
        if tag == "list":
            return f"([{', '.join(sub(value) for value in term['items'])}] : {self.sort({'list': term['element_sort']})})"
        if tag == "list_cons":
            elem = self.term_sort(term["head"], ctx)
            return f"(@_root_.List.cons {self.sort(elem)} {sub(term['head'])} {sub(term['tail'])})"
        if tag == "list_append":
            elem = self.term_sort(term["left"], ctx)["list"]
            return f"(@_root_.List.append {self.sort(elem)} {sub(term['left'])} {sub(term['right'])})"
        if tag == "list_get":
            elem = self.term_sort(term["value"], ctx)["list"]
            return f"(@_root_.List.get?Internal {self.sort(elem)} {sub(term['value'])} {sub(term['index'])})"
        if tag == "list_sort":
            elem = self.term_sort(term["value"], ctx)["list"]
            comparator = f"(fun (_vs_left _vs_right : {self.sort(elem)}) => _root_.Decidable.decide (_vs_left ≤ _vs_right))"
            return f"(@_root_.List.mergeSort {self.sort(elem)} {sub(term['value'])} {comparator})"
        if tag == "list_unique":
            elem = self.term_sort(term["value"], ctx)["list"]
            # The compiler fixes builtin decidable equality, and denotation reconstructs
            # the exact instance independently; proposal instances cannot replace it.
            equality = {"Nat": "instDecidableEqNat", "Int": "Int.instDecidableEq", "String": "instDecidableEqString",
                        "Bool": "instDecidableEqBool"}[elem]
            instance = f"(@_root_.instBEqOfDecidableEq {self.sort(elem)} _root_.{equality})"
            return f"(@_root_.List.eraseDups {self.sort(elem)} {instance} {sub(term['value'])})"
        if tag in ("list_length", "list_reverse", "list_sum"):
            elem = self.term_sort(term["value"], ctx)["list"]
            # List.sum's builtin Add/Zero are selected by the fixed imported core, never proposal instances.
            if tag == "list_sum":
                return f"(_root_.List.sum {sub(term['value'])})"
            op = "List.length" if tag == "list_length" else "List.reverse"
            return f"(@_root_.{op} {self.sort(elem)} {sub(term['value'])})"
        if tag in ("list_map", "list_filter"):
            fn = term["function"]
            binder = _quoted(f"_v{len(names)}")
            body_ctx = [fn["sort"]] + ctx
            body = self.term(fn["body"], [binder] + names, body_ctx)
            function = f"(fun ({binder} : {self.sort(fn['sort'])}) => {body})"
            if tag == "list_map":
                result = self.term_sort(fn["body"], body_ctx)
                return f"(@_root_.List.map {self.sort(fn['sort'])} {self.sort(result)} {function} {sub(term['value'])})"
            return f"(@_root_.List.filter {self.sort(fn['sort'])} {function} {sub(term['value'])})"
        if tag == "list_foldl":
            fn = term["function"]
            acc, elem = fn["accumulator_sort"], fn["element_sort"]
            a, e = _quoted(f"_v{len(names)}"), _quoted(f"_v{len(names) + 1}")
            body = self.term(fn["body"], [e, a] + names, [elem, acc] + ctx)
            function = f"(fun ({a} : {self.sort(acc)}) ({e} : {self.sort(elem)}) => {body})"
            return f"(@_root_.List.foldl {self.sort(acc)} {self.sort(elem)} {function} {sub(term['initial'])} {sub(term['value'])})"
        if tag == "call":
            return "(" + _reference(term["symbol"]) + (" " + " ".join(map(sub, term["args"])) if term["args"] else "") + ")"
        if tag in ("ok", "error"):
            result = self.term_sort(term, ctx)["result"]
            return f"(@_root_.Except.{tag} {self.sort(result['error'])} {self.sort(result['ok'])} {sub(term['value'])})"
        raise FrontendError("term", f"unsupported term tag {tag}")

    def formula(self, formula: dict, names: list[str], ctx: list[Any]) -> str:
        tag = formula["tag"]
        sub = lambda value: self.formula(value, names, ctx)
        if tag == "predicate":
            args = [self.term(arg, names, ctx) for arg in formula["args"]]
            return "(" + _reference(formula["predicate"]) + (" " + " ".join(args) if args else "") + ")"
        if tag in ("true", "false"):
            return "_root_.True" if tag == "true" else "_root_.False"
        if tag in dsl.RELATIONS:
            op = {"eq": "=", "lt": "<", "le": "≤"}[tag]
            return f"({self.term(formula['left'], names, ctx)} {op} {self.term(formula['right'], names, ctx)})"
        if tag == "holds":
            return f"({self.term(formula['term'], names, ctx)} = _root_.Bool.true)"
        if tag == "not":
            return f"(¬ {sub(formula['body'])})"
        if tag in dsl.CONNECTIVES:
            op = {"and": "∧", "or": "∨", "implies": "→", "iff": "↔"}[tag]
            return f"({sub(formula['left'])} {op} {sub(formula['right'])})"
        if tag in dsl.QUANTIFIERS + dsl.RANGE_QUANTIFIERS:
            binder = _quoted(f"_v{len(names)}")
            sort = "Nat" if tag in dsl.RANGE_QUANTIFIERS else formula["sort"]
            body = self.formula(formula["body"], [binder] + names, [sort] + ctx)
            if tag in dsl.RANGE_QUANTIFIERS:
                lo, hi = self.term(formula["lower"], names, ctx), self.term(formula["upper"], names, ctx)
                body = f"({lo} ≤ {binder} → {binder} < {hi} → {body})" if tag == "forall_range" else f"({lo} ≤ {binder} ∧ {binder} < {hi} ∧ {body})"
            op = "∀" if tag in ("forall", "forall_range") else "∃"
            return f"({op} ({binder} : {self.sort(sort)}), {body})"
        raise FrontendError("formula", f"unsupported formula tag {tag}")

    def binders(self, args: list[Any]) -> tuple[str, list[str], list[Any]]:
        names = [_quoted(f"_v{i}") for i in range(len(args))]
        rendered = " ".join(f"({name} : {self.sort(sort)})" for name, sort in zip(names, args))
        return rendered, list(reversed(names)), list(reversed(args))



@dataclass
class CompiledAST:
    source: bytes
    formalization: dict[str, Any]
    receipt: dict[str, Any]
    profile: dsl.Profile
    proposal: dict[str, Any]
    audit_formulas: dict[str, dict[str, Any]]


def compile_response(response: bytes, frozen_records: list[dict], profile_id: str, *, response_ref: str = "captured-response.json") -> CompiledAST:
    """Compile exactly captured strict JSON bytes; no source snippets or supplied proofs."""
    if len(response) > MAX_RESPONSE_BYTES:
        raise FrontendError("response", "byte budget exhausted")
    try:
        proposal = canonical.loads(response)
    except (ValueError, UnicodeError) as exc:
        raise FrontendError("response", f"not strict canonicalizable JSON: {exc}") from None
    version = proposal.get("encoding") if isinstance(proposal, dict) else None
    required = {"encoding", "records", "symbols", "predicates", "theorems", "obligations", "witness_obligations"}
    if version == VERSION_V2:
        required.add("enums")
    if (not isinstance(proposal, dict) or not required <= set(proposal)
            or set(proposal) - required - {"native_requirements", "source_requirements"}):
        raise FrontendError("proposal", "expected the closed typed envelope with optional native_requirements/source_requirements")
    if version not in SUPPORTED_VERSIONS:
        raise FrontendError("encoding", f"expected {VERSION}")
    compiler = compiler_for_version(version)
    if not isinstance(profile_id, str) or not dsl.ID_RE.fullmatch(profile_id):
        raise FrontendError("profile_id", "invalid frozen profile identifier")
    maps = {key: _mapping(proposal[key], key) for key in ("records", "symbols", "predicates", "theorems", "obligations", "witness_obligations")}
    maps["native_requirements"] = _mapping(proposal.get("native_requirements", {}), "native_requirements")
    maps["source_requirements"] = _mapping(proposal.get("source_requirements", {}), "source_requirements")
    maps["enums"] = _mapping(proposal["enums"], "enums") if version == VERSION_V2 else {}
    all_names = set()
    for kind in ("enums", "records", "symbols", "predicates", "theorems", "native_requirements", "source_requirements"):
        for name in maps[kind]:
            _ident(name, kind + "." + name)
            if name in RESERVED_DECLARATIONS:
                raise FrontendError(kind + "." + name, "declaration would shadow a fixed Lean primitive")
            if name in all_names:
                raise FrontendError(kind, f"declaration name {name} is already used")
            all_names.add(name)
    if len(all_names) > MAX_DECLARATIONS:
        raise FrontendError("proposal", "total declaration budget exhausted")
    enums, total_constructors = {}, 0
    for name, row in maps["enums"].items():
        path = "enums." + name
        _shape(row, {"constructors"}, path)
        constructors = row["constructors"]
        if not isinstance(constructors, list) or not 1 <= len(constructors) <= MAX_ENUM_CONSTRUCTORS:
            raise FrontendError(path, f"constructors must contain 1 to {MAX_ENUM_CONSTRUCTORS} identifiers")
        for constructor in constructors:
            _ident(constructor, path + ".constructors")
            members = GENERATED_SINGLETON_MEMBERS if len(constructors) == 1 else GENERATED_TYPE_MEMBERS
            if constructor in members:
                raise FrontendError(path, "constructor would shadow generated Lean machinery")
        if len(set(constructors)) != len(constructors):
            raise FrontendError(path, "constructors must be unique")
        total_constructors += len(constructors)
        if total_constructors > MAX_TOTAL_ENUM_CONSTRUCTORS:
            raise FrontendError("enums", "aggregate constructor budget exhausted")
        instance = "instDecidableEq" + name
        if instance in all_names:
            raise FrontendError(path, "declaration would shadow generated Lean equality machinery")
        enums[name] = {"lean_decl": _lean_name(name), "constructors": list(constructors),
                       "lean_constructors": [_lean_name(name) + "." + ctor for ctor in constructors],
                       "candidate_decidable_eq": {"lean_decl": _lean_name(instance)}}
    records = {}
    for name, row in maps["records"].items():
        _shape(row, {"fields"}, "records." + name)
        if not isinstance(row["fields"], list):
            raise FrontendError("records." + name, "fields must be an ordered array")
        fields = []
        for field in row["fields"]:
            _shape(field, {"name", "sort"}, "records." + name + ".fields")
            _ident(field["name"], "records." + name + ".field")
            if version == VERSION_V2 and field["name"] in GENERATED_RECORD_MEMBERS:
                raise FrontendError("records." + name, "field would shadow generated Lean machinery")
            fields.append({**field, "lean_projection": _lean_name(name) + "." + field["name"]})
        records[name] = {"lean_decl": _lean_name(name), "lean_constructor": _lean_name(name) + ".mk", "fields": fields}
    for name, row in maps["symbols"].items():
        _shape(row, {"args", "result", "body"}, "symbols." + name)
        if not isinstance(row["args"], list):
            raise FrontendError("symbols." + name, "args must be an array of sorts")
    for name, row in maps["predicates"].items():
        _shape(row, {"args", "formula"}, "predicates." + name)
        if not isinstance(row["args"], list):
            raise FrontendError("predicates." + name, "args must be an array of sorts")
    try:
        native_contract.validate_definitions(maps["native_requirements"], maps["symbols"])
    except native_contract.NativeError as exc:
        raise FrontendError("native_requirements", str(exc)) from None
    try:
        source_contract.validate_definitions(maps["source_requirements"], maps["symbols"])
    except source_contract.SourceError as exc:
        raise FrontendError("source_requirements", str(exc)) from None
    raw_profile = {"profile_id": profile_id, "dsl": dsl.ENCODING_V2, "enums": enums, "records": records,
        "symbols": {name: {"lean_decl": _lean_name(name), "args": row["args"], "result": row["result"]} for name, row in maps["symbols"].items()},
        "predicates": {name: {"lean_decl": _lean_name(name), "args": row["args"]} for name, row in maps["predicates"].items()}}
    try:
        profile = dsl.Profile.from_json(raw_profile, allow_candidate_enum_equality=version == VERSION_V2)
        expander = _Expander(profile, maps["predicates"])
        expanded_symbols, expanded_theorems = {}, {}
        for name, row in maps["symbols"].items():
            expanded_symbols[name] = expander.node(row["body"], list(reversed(row["args"])))
            if not dsl.sort_eq(dsl.type_term(expanded_symbols[name], list(reversed(row["args"])), profile), row["result"]):
                raise FrontendError("symbols." + name + ".body", "body result differs from declared result sort")
        for name, row in maps["predicates"].items():
            expander.predicate(name)
        for name, row in maps["theorems"].items():
            if not isinstance(row, dict) or set(row) not in (
                    {"formula"}, {"native"}, {"formula", "native"}, {"source"}, {"formula", "source"}):
                raise FrontendError("theorems." + name,
                                    "require formula and/or one nonempty native or source reference list; native/source cannot mix")
            if "formula" in row:
                expanded_theorems[name] = expander.node(row["formula"], [])
                dsl.type_formula(expanded_theorems[name], [], profile)
            if "native" in row:
                refs = row["native"]
                if (not isinstance(refs, list) or not 1 <= len(refs) <= native_contract.MAX_NATIVE_FACETS
                        or not all(isinstance(r, str) and r in maps["native_requirements"] for r in refs)
                        or len(set(refs)) != len(refs)):
                    raise FrontendError("theorems." + name + ".native", "distinct known native requirement IDs required")
            if "source" in row:
                refs = row["source"]
                if (not isinstance(refs, list) or not 1 <= len(refs) <= source_contract.MAX_SOURCE_FACETS
                        or not all(isinstance(r, str) and r in maps["source_requirements"] for r in refs)
                        or len(set(refs)) != len(refs)):
                    raise FrontendError("theorems." + name + ".source", "distinct known source requirement IDs required")
    except (dsl.DSLError, KeyError, TypeError) as exc:
        raise FrontendError("typing", str(exc)) from None
    record_order = _ordered({name: set().union(*(_record_refs(f["sort"]) for f in row["fields"])) for name, row in records.items()}, "records")
    definition_order = _ordered({**{name: dsl.calls(row["body"]) | _predicate_dependencies(row["body"]) for name, row in maps["symbols"].items()},
        **{name: dsl.calls(row["formula"]) | _predicate_dependencies(row["formula"]) for name, row in maps["predicates"].items()}}, "definitions")
    frozen = {}
    for row in frozen_records:
        if row.get("origin", "interpreted") == "interpreted" and not row.get("blocked_by", []):
            if row["id"] in frozen:
                raise FrontendError("frozen_records", "duplicate frozen obligation ID")
            frozen[row["id"]] = row
    if set(maps["obligations"]) != set(frozen):
        raise FrontendError("obligations", f"must preserve exact active frozen IDs; missing={sorted(set(frozen)-set(maps['obligations']))}, extra={sorted(set(maps['obligations'])-set(frozen))}")
    bindings, used_theorems = [], set()
    for oid in sorted(frozen):
        row, context = maps["obligations"][oid], frozen[oid]
        if not isinstance(row, dict) or len(row) > 1 or not set(row).issubset({"theorem", "predicate", "declarations"}):
            raise FrontendError("obligations." + oid, "choose exactly one theorem, predicate or declaration list")
        binding = {"obligation": oid}
        if not row:
            if context.get("role") not in ("exclusion", "open_question"):
                raise FrontendError("obligations." + oid, "only frozen exclusions/open questions may have empty bindings")
        elif "theorem" in row:
            name = row["theorem"]
            if not isinstance(name, str) or name not in maps["theorems"]:
                raise FrontendError("obligations." + oid, "unknown theorem reference")
            if context.get("role") != "guarantee":
                raise FrontendError("obligations." + oid, "theorem binding requires a frozen guarantee role")
            binding["theorem"] = _lean_name(name)
            if "native" in maps["theorems"][name]:
                binding["native_requirements"] = [_lean_name(n) for n in maps["theorems"][name]["native"]]
                if "formula" in maps["theorems"][name]:
                    binding["value_projection"] = _lean_name("_vs_value_" + name)
            if "source" in maps["theorems"][name]:
                binding["source_requirements"] = [_lean_name(n) for n in maps["theorems"][name]["source"]]
                if "formula" in maps["theorems"][name]:
                    binding["value_projection"] = _lean_name("_vs_value_" + name)
            used_theorems.add(name)
        elif "predicate" in row:
            name = row["predicate"]
            if context.get("role") != "assumption" or not isinstance(name, str) or name not in maps["predicates"]:
                raise FrontendError("obligations." + oid, "predicate binding requires a frozen assumption and known predicate")
            binding["predicate"] = _lean_name(name)
        else:
            if context.get("role") != "declaration" or not isinstance(row["declarations"], list) or not row["declarations"]:
                raise FrontendError("obligations." + oid, "nonempty declaration references require a frozen entity")
            names = []
            for ref in row["declarations"]:
                _shape(ref, {"kind", "name"}, "obligations." + oid + ".declarations")
                kinds = {"record": "records", "symbol": "symbols", "predicate": "predicates"}
                if version == VERSION_V2:
                    kinds["enum"] = "enums"
                kind = kinds.get(ref["kind"]) if isinstance(ref["kind"], str) else None
                if kind is None or not isinstance(ref["name"], str) or ref["name"] not in maps[kind]:
                    raise FrontendError("obligations." + oid, "unknown typed declaration reference")
                names.append(_lean_name(ref["name"]))
            if len(set(names)) != len(names):
                raise FrontendError("obligations." + oid, "duplicate declaration reference")
            binding["declarations"] = names
        bindings.append(binding)
    internal = []
    for wid, row in sorted(maps["witness_obligations"].items()):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]*", wid) or wid in frozen:
            raise FrontendError("witness_obligations." + wid, "internal witness ID must be valid and distinct from frozen IDs")
        _shape(row, {"theorem", "witnesses_for", "description"}, "witness_obligations." + wid)
        name, covers = row["theorem"], row["witnesses_for"]
        if (not isinstance(name, str) or name not in maps["theorems"]
                or set(maps["theorems"][name]) != {"formula"}
                or not dsl.is_existential_shape(maps["theorems"][name]["formula"])):
            raise FrontendError("witness_obligations." + wid, "known theorem with constructive existential shape required")
        if (not isinstance(covers, list) or not covers or not all(isinstance(oid, str) for oid in covers) or len(set(covers)) != len(covers)
                or any(frozen.get(oid, {}).get("role") != "assumption" for oid in covers)):
            raise FrontendError("witness_obligations." + wid, "witnesses_for must name distinct frozen assumptions")
        if not isinstance(row["description"], str) or not row["description"]:
            raise FrontendError("witness_obligations." + wid, "nonempty witness description required")
        internal.append({"id": wid, "kind": "non_vacuity", "theorem": _lean_name(name), "witnesses_for": covers, "description": row["description"]})
        used_theorems.add(name)
    if set(maps["theorems"]) != used_theorems:
        raise FrontendError("theorems", "every supplied theorem must be explicitly bound to a frozen obligation or witness")
    used_native = {n for row in maps["theorems"].values() for n in row.get("native", [])}
    if set(maps["native_requirements"]) != used_native:
        raise FrontendError("native_requirements", "every native definition must be bound to an actual guarantee theorem")
    used_source = {n for row in maps["theorems"].values() for n in row.get("source", [])}
    if set(maps["source_requirements"]) != used_source:
        raise FrontendError("source_requirements", "every source definition must be bound to an actual guarantee theorem")
    prelude = native_contract.library_source().decode("utf-8") if used_native else "import Std"
    if used_source:
        source_prelude = source_contract.library_source().decode("utf-8")
        if used_native:
            if not source_prelude.startswith("import Std\n"):
                raise FrontendError("source_requirements", "normative source library has an unsupported import header")
            prelude += "\n" + source_prelude.removeprefix("import Std\n")
        else:
            prelude = source_prelude
    renderer, source, audits = _Renderer(profile, expander), [prelude, "namespace " + NAMESPACE], {}
    for name, row in sorted(enums.items()):
        source.append("inductive " + _quoted(name) + " where")
        source.extend("  | " + _quoted(ctor) for ctor in row["constructors"])
        source.append("  deriving _root_.DecidableEq")
    for name in record_order:
        source.append("structure " + _quoted(name) + " where")
        source.extend("  " + _quoted(field["name"]) + " : " + renderer.sort(field["sort"]) for field in records[name]["fields"])
    for name in definition_order:
        if name in maps["predicates"]:
            row = maps["predicates"][name]
            binders, names, ctx = renderer.binders(row["args"])
            source.append(f"@[reducible] def {_quoted(name)} {binders} : Prop := {renderer.formula(row['formula'], names, ctx)}")
            call = "(" + _reference(name) + (" " + " ".join(reversed(names)) if names else "") + ")"
            source.append(f"theorem {_quoted('_vs_predicate_' + name)} {binders} : ({call} ↔ {renderer.formula(row['formula'], names, ctx)}) := by rfl")
            continue
        row = maps["symbols"][name]
        binders, names, ctx = renderer.binders(row["args"])
        source.append(f"def {_quoted(name)} {binders} : {renderer.sort(row['result'])} := {renderer.term(row['body'], names, ctx)}")
        body_formula = {"tag": "eq", "left": {"tag": "call", "symbol": name,
            "args": [{"tag": "var", "index": len(row["args"]) - i - 1} for i in range(len(row["args"]))]}, "right": expanded_symbols[name]}
        for sort in reversed(row["args"]):
            body_formula = {"tag": "forall", "sort": sort, "body": body_formula}
        audit_name = "_vs_body_" + name
        source.append(f"theorem {_quoted(audit_name)} : {renderer.formula(body_formula, [], [])} := by intros; rfl")
        audits[audit_name] = body_formula
    for name, row in sorted(maps["native_requirements"].items()):
        endpoint = maps["symbols"][row["symbol"]]
        endpoint_type = " → ".join(renderer.sort(s) for s in [*endpoint["args"], endpoint["result"]])
        requirements = native_contract.render_requirements(row["requirements"], _string)
        source.append(f"def {_quoted(name)} : _root_.VeriSlop.Native.NativeDefinition ({endpoint_type}) := "
                      f"⟨{_reference(row['symbol'])}, {requirements}⟩")
    for name, row in sorted(maps["source_requirements"].items()):
        endpoint = maps["symbols"][row["symbol"]]
        endpoint_type = " → ".join(renderer.sort(s) for s in [*endpoint["args"], endpoint["result"]])
        requirements = source_contract.render_requirements(row["requirements"], _string)
        source.append(f"def {_quoted(name)} : _root_.VeriSlop.Source.SourceDefinition ({endpoint_type}) := "
                      f"⟨{_reference(row['symbol'])}, {requirements}⟩")
    for name, row in sorted(maps["theorems"].items()):
        props = [f"(_root_.VeriSlop.Native.Contract {_reference(n)})" for n in row.get("native", [])]
        props += [f"(_root_.VeriSlop.Source.Contract {_reference(n)})" for n in row.get("source", [])]
        facet_type = props[-1] if props else None
        for prop in reversed(props[:-1]):
            facet_type = f"({prop} ∧ {facet_type})"
        value_type = renderer.formula(row["formula"], [], []) if "formula" in row else None
        theorem_type = f"({value_type} ∧ {facet_type})" if value_type and facet_type else value_type or facet_type
        source.append(f"theorem {_quoted(name)} : {theorem_type} := by sorry")
        if value_type and facet_type:
            source.append(f"theorem {_quoted('_vs_value_' + name)} : {value_type} := by exact {_reference(name)}.1")
    source.append("end " + NAMESPACE)
    encoded_source = ("\n".join(source) + "\n").encode("utf-8")
    formalization = {"schema_version": "0.1", "artifact_kind": "formalization_candidate", "profile_id": profile_id,
        "lean_toolchain": TOOLCHAIN, "lean_file": "Contract.lean", "bindings": bindings, "internal_obligations": internal}
    receipt = {"schema_version": "0.1", "artifact_kind": "formalizer_compiler_origin", "compiler": compiler,
        "compiler_source_hash": canonical.digest(Path(__file__).read_bytes()), "response_ref": response_ref,
        "captured_response_hash": canonical.digest(response), "proposal_hash": canonical.digest_json(proposal),
        "frozen_records_hash": canonical.digest_json(frozen_records), "profile_id": profile_id, "namespace": NAMESPACE,
        "lean_toolchain": TOOLCHAIN, "source_hash": canonical.digest(encoded_source), "formalization_hash": canonical.digest_json(formalization),
        "origin_scope": "deterministic compilation from captured untrusted JSON; provider-origin authenticity requires the separate native call receipt"}
    if version == VERSION_V2:
        receipt["frontend_version"] = version
    if used_native:
        receipt.update({"native_support_hash": canonical.digest(Path(native_contract.__file__).read_bytes()),
                        "native_model_version": native_contract.MODEL_VERSION,
                        "native_model_source_hash": native_contract.model_source_hash()})
    if used_source:
        receipt.update({"source_support_hash": canonical.digest(Path(source_contract.__file__).read_bytes()),
                        "source_model_version": source_contract.MODEL_VERSION,
                        "source_model_source_hash": source_contract.model_source_hash()})
    return CompiledAST(encoded_source, formalization, receipt, profile, proposal, audits)


def reconstruct_origin(response: bytes, frozen_records: list[dict], source: bytes, formalization: dict, receipt: dict) -> bool:
    """Replay with this exact compiler version; reject changed bytes, context, receipt or artifacts."""
    try:
        generated = compile_response(response, frozen_records, receipt["profile_id"], response_ref=receipt["response_ref"])
        return generated.source == source and generated.formalization == formalization and generated.receipt == receipt
    except (FrontendError, KeyError, TypeError):
        return False


def kernel_audit_requests(compiled: CompiledAST) -> list[dict]:
    """Check candidate-compilation fidelity with the existing kernel API before freezing.

    These checks supplement, never substitute for, later proof/witness acceptance. In particular
    a candidate theorem containing sorry still cannot gain PROVED through this helper.
    """
    requests = [{"id": "body:" + name, "theorem": parse_name(_lean_name(name)),
                 "expr": reify.denote_formula(formula, compiled.profile)} for name, formula in sorted(compiled.audit_formulas.items())]
    for name, row in sorted(compiled.proposal["theorems"].items()):
        value = (reify.denote_formula(_Expander(compiled.profile, compiled.proposal["predicates"]).node(row["formula"], []), compiled.profile)
                 if "formula" in row else None)
        facets = []
        for kind, denote in (("native", native_contract.native_prop), ("source", source_contract.source_prop)):
            for ref in row.get(kind, []):
                endpoint = compiled.proposal["symbols"][compiled.proposal[kind + "_requirements"][ref]["symbol"]]
                denoter = reify._Denoter(compiled.profile)
                endpoint_type = denoter.sort(endpoint["result"])
                for sort in reversed(endpoint["args"]):
                    endpoint_type = pi("x", denoter.sort(sort), endpoint_type)
                facets.append(denote(_lean_name(ref), endpoint_type))
        expr = facets[-1] if facets else value
        for prop in reversed(facets[:-1]):
            expr = app(const("And"), prop, expr)
        if facets and value:
            expr = app(const("And"), value, expr)
        requests.append({"id": "statement:" + name, "theorem": parse_name(_lean_name(name)), "expr": expr})
        if facets and value:
            requests.append({"id": "value:" + name, "theorem": parse_name(_lean_name("_vs_value_" + name)), "expr": value})
    denoter = reify._Denoter(compiled.profile)
    for name, row in sorted(compiled.proposal["predicates"].items()):
        ctx = [("var", sort) for sort in reversed(row["args"])]
        expr = app(const("Iff"), app(const(_lean_name(name)), *(bvar(len(row["args"]) - i - 1) for i in range(len(row["args"])))),
                   denoter.formula(_Expander(compiled.profile, compiled.proposal["predicates"]).predicate(name), ctx))
        for sort in reversed(row["args"]):
            expr = pi("x", denoter.sort(sort), expr)
        requests.append({"id": "predicate:" + name, "theorem": parse_name(_lean_name("_vs_predicate_" + name)), "expr": expr})
    return requests


def compile_proposal(obj: dict, records: list[dict], *, profile_id: str = "generated.v0_2",
                     captured_response: bytes | None = None, response_ref: str = "captured-response.json") -> tuple[bytes, dict, dict]:
    """Public transport API; supplied response must contain this exact untrusted AST object."""
    response = canonical.dumps(obj) if captured_response is None else captured_response
    try:
        if canonical.loads(response) != obj:
            raise FrontendError("response", "captured response differs from the proposal object")
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, FrontendError):
            raise
        raise FrontendError("response", f"captured response is not strict JSON: {exc}") from None
    generated = compile_response(response, records, profile_id, response_ref=response_ref)
    return generated.source, generated.formalization, generated.receipt


def replay_receipt(obj: dict, records: list[dict], source: bytes, formalization: dict, receipt: dict,
                   *, captured_response: bytes | None = None) -> bool:
    """Public exact source-origin replay API; never establishes proof or provider authenticity."""
    try:
        response = canonical.dumps(obj) if captured_response is None else captured_response
        if canonical.loads(response) != obj:
            return False
        return reconstruct_origin(response, records, source, formalization, receipt)
    except (ValueError, TypeError, UnicodeError):
        return False
