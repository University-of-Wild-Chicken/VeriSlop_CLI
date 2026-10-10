"""Untrusted deterministic source-only readable proposal; kernel equality is authority."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import canonical
from . import vscore3_source as S

VERSION = "vscore-readable/1"
NAMESPACE = "VeriSlopReadableSource"
SELECTION_PATH = "support/readable/selection.json"
SELECTION_SLOT = "vscore-readable-selection"
SELECTION_ROLE = "readable_selection"
MANIFEST_PATH = "readable/manifest.json"
BUDGETS = {"source_ast_nodes": 4096, "source_ast_depth": 128, "helpers": 128, "entries": 64,
           "type_depth": 64, "total_record_fields": 4096, "max_call_arity": 64,
           "generation_steps": 2000000, "source_block_bytes": 2097152,
           "correspondence_bytes": 8388608, "typed_ir_bytes": 16777216,
           "support_declarations": 65536, "support_export_bytes": 67108864,
           "manifest_bytes": 4194304, "optional_stdout_bytes": 16777216,
           "optional_stderr_bytes": 16777216, "optional_kernel_response_bytes": 67108864,
           "diagnostic_display_chars_per_row": 240}
CONSTRUCTORS = ("var", "nat", "int", "string", "bool", "unit", "enum", "bin", "not", "ite", "letE",
                "ok", "error", "matchResult", "record", "project", "none", "some", "matchOption", "nil",
                "cons", "matchList", "call", "listFold", "natFold", "intNeg", "intFdiv", "natToInt",
                "intToNat", "listLength", "listRange", "listGet", "listAppend", "listReverse", "listSort",
                "listUnique", "listMap", "listFilter", "listSum")
TAGS = {"let": "letE", "match": "matchResult", "match_option": "matchOption", "match_list": "matchList",
        "list_fold": "listFold", "nat_fold": "natFold", "int_neg": "intNeg", "int_fdiv": "intFdiv",
        "nat_to_int": "natToInt", "int_to_nat": "intToNat", "list_length": "listLength", "list_range": "listRange",
        "list_get": "listGet", "list_append": "listAppend", "list_reverse": "listReverse", "list_sort": "listSort",
        "list_unique": "listUnique", "list_map": "listMap", "list_filter": "listFilter", "list_sum": "listSum"}


class Unavailable(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def descriptor() -> dict:
    coverage = {"constructors": list(CONSTRUCTORS), "excluded": ["variant", "matchVariant"], "budgets": BUDGETS}
    return {"version": VERSION, "implementation_hash": canonical.digest(Path(__file__).read_bytes()),
            "coverage_hash": canonical.digest_json(coverage),
            "recipe_hash": canonical.digest_json({"version": 1, "universal": "intro env; with_unfolding_all rfl",
                                                  "helper_lookup": "checkedProgram.helpers.find?",
                                                  "body_order": "params.reverse", "calls": "declared-order"}),
            "proof_identity_mode": "MODULE_BOUND_PROOF"}


def source_registry(enums: dict[str, list[str]]) -> dict:
    return {"enums": [[key, list(enums[key])] for key in sorted(enums)]}


def _join(parts, separator="") -> str:
    """Bound concatenation before allocating the composite source term."""
    items=[];total=0
    for part in parts:
        total+=len(part.encode())+(len(separator.encode()) if items else 0)
        if total>BUDGETS["source_block_bytes"]:
            raise Unavailable("OUTPUT_BUDGET","readable intermediate term byte budget exceeded")
        items.append(part)
    return separator.join(items)


class Lines(list):
    def __init__(self):super().__init__();self.byte_count=0
    def append(self,line):
        self.byte_count+=len(line.encode())+1
        if self.byte_count>BUDGETS["source_block_bytes"]:
            raise Unavailable("OUTPUT_BUDGET","readable source block byte budget exceeded before emission")
        super().append(line)
    def __iadd__(self,lines):
        for line in lines:self.append(line)
        return self


def _tuple(items: list[str]) -> str:
    term = "()"
    for item in reversed(items):
        term = _join(["(",item,", ",term,")"])
    return term


def _projection(index: int, root: str = "env") -> str:
    return "(" + root + ")" + ".2" * index + ".1"


@dataclass
class View:
    block: bytes
    standalone: bytes
    typed_ir: bytes
    functions: list[dict]
    constructors: list[str]
    source_key: str


class Renderer:
    def __init__(self, source: bytes, enums: dict[str, list[str]], program: dict):
        self.source, self.enums, self.program = source, enums, program
        self.decls = {d["id"]: d for d in program["declarations"]}
        self.helpers = {f["id"]: f for f in program["helpers"]}
        self.names = {f["id"]: f"helper_{i}" for i, f in enumerate(program["helpers"])}
        self.names.update({f["id"]: f"entry_{i}" for i, f in enumerate(program["entries"])})
        self.nodes, self.steps, self.serial = 0, 0, 0
        self.seen: set[str] = set()
        self.ir: list[dict] = []
        self.ir_bytes = 0

    def tick(self):
        self.steps += 1
        if self.steps > BUDGETS["generation_steps"]:
            raise Unavailable("GENERATION_STEP_BUDGET", "readable generation step budget exceeded")

    def fresh(self) -> str:
        self.serial += 1
        return f"v__{self.serial}"

    def shape(self, ty: Any, depth: int = 0, pending: frozenset = frozenset()) -> str:
        self.tick()
        if depth > BUDGETS["type_depth"]:
            raise Unavailable("TYPE_DEPTH_BUDGET", "readable type depth exceeded")
        if isinstance(ty, str):
            if ty not in ("nat", "int", "bool", "string", "unit"):
                raise Unavailable("UNSUPPORTED_TYPE", f"unsupported readable type {ty}")
            return "." + ty
        tag = ty[0]
        if tag in ("option", "list"):
            return _join([f"(.{tag} ",self.shape(ty[1], depth + 1, pending),")"])
        if tag == "result":
            return _join(["(.result ",self.shape(ty[1], depth + 1, pending)," ",self.shape(ty[2], depth + 1, pending),")"])
        if tag == "enum":
            return _join([f"(.enum {S.lean_string(ty[1])} [",_join((S.lean_string(x) for x in self.enums[ty[1]]),", "),"])"])
        if tag == "record":
            if ty[1] in pending:
                raise Unavailable("UNSUPPORTED_TYPE", "recursive readable record")
            d = self.decls[ty[1]]
            if d["tag"] != "record":
                raise Unavailable("UNSUPPORTED_TYPE", "variant-dependent readable record")
            payload = ".unit"
            for _, field in reversed(d["fields"]):
                payload = _join(["(.product ",self.shape(field, depth + 1, pending | {ty[1]})," ",payload,")"])
            names = _join(["[",_join((S.lean_string(n) for n, _ in d["fields"]),", "),"]"])
            return _join(["(.record ",S.lean_string(ty[1])," ",names," ",payload,")"])
        raise Unavailable("UNSUPPORTED_TYPE", f"unsupported readable type {tag}")

    def expr(self, e: Any, stack: list[tuple[Any, str]], depth: int = 0) -> tuple[Any, str]:
        ty,term=self._expr(e,stack,depth)
        return ty,_join([term])

    def _expr(self, e: Any, stack: list[tuple[Any, str]], depth: int = 0) -> tuple[Any, str]:
        self.tick()
        self.nodes += 1
        if self.nodes > BUDGETS["source_ast_nodes"]:
            raise Unavailable("NODE_BUDGET", "readable source node budget exceeded")
        if depth > BUDGETS["source_ast_depth"]:
            raise Unavailable("DEPTH_BUDGET", "readable source depth exceeded")
        tag = e[0]
        constructor = TAGS.get(tag, tag)
        if constructor not in CONSTRUCTORS:
            raise Unavailable("UNSUPPORTED_CONSTRUCTOR", f"unsupported readable constructor {constructor}")
        self.seen.add(constructor)
        node={"constructor": constructor, "binder_types": [S.ty_json(t) for t, _ in stack], "depth": depth}
        self.ir_bytes+=len(canonical.dumps(node))+1
        if self.ir_bytes>BUDGETS["typed_ir_bytes"]:
            raise Unavailable("OUTPUT_BUDGET","readable typed metadata byte budget exceeded before emission")
        self.ir.append(node)
        child = lambda x, gamma=stack: self.expr(x, gamma, depth + 1)
        if tag == "var":
            return stack[e[1]]
        if tag in ("nat", "int", "bool", "unit", "string"):
            if tag == "unit": value = "()"
            elif tag == "bool": value = "true" if e[1] else "false"
            elif tag == "string": value = "String.ofList ([" + ", ".join(map(str, e[1])) + "].map Char.ofNat)"
            elif tag == "int": value = f"(Int.ofNat {e[1]})" if e[1] >= 0 else f"(Int.negSucc {-e[1] - 1})"
            else: value = f"({e[1]} : Nat)"
            return tag, value
        if tag == "enum":
            ty = ("enum", e[1])
            return ty, f"(⟨{S.lean_string(e[2])}, by decide +kernel⟩ : VSCore3.Denote {self.shape(ty)})"
        if tag == "bin":
            ty, a = child(e[2]); _, b = child(e[3]); op = e[1]
            if op == "eq":
                return "bool", f"(letI := VSCore3.denoteDecidableEq {self.shape(ty)}; decide (({a}) = ({b})))"
            symbol = {"add": "+", "sub": "-", "mul": "*", "lt": "<", "le": "≤", "and": "&&", "or": "||"}[op]
            value = f"(({a}) {symbol} ({b}))"
            return ("bool", f"decide {value}") if op in ("lt", "le") else ("bool" if op in ("and", "or") else ty, value)
        if tag == "not":
            _, a = child(e[1]); return "bool", f"(!({a}))"
        if tag == "ite":
            _, c = child(e[1]); ty, t = child(e[2]); _, f = child(e[3])
            return ty, f"(if ({c}) then ({t}) else ({f}))"
        if tag == "let":
            ty, a = child(e[1]); v = self.fresh(); result, b = child(e[2], [(ty, v)] + stack)
            return result, f"(let {v} : VSCore3.Denote {self.shape(ty)} := ({a}); {b})"
        if tag in ("ok", "error"):
            ty, value = child(e[2]); other = e[1]
            result = ("result", other, ty) if tag == "ok" else ("result", ty, other)
            ctor = "inr" if tag == "ok" else "inl"
            return result, f"(Sum.{ctor} ({value}) : VSCore3.Denote {self.shape(result)})"
        if tag == "match":
            ty, value = child(e[1]); x, y = self.fresh(), self.fresh()
            result, ok = child(e[2], [(ty[2], x)] + stack)
            _, error = child(e[3], [(ty[1], y)] + stack)
            return result, f"(match ({value}) with | Sum.inl {y} => ({error}) | Sum.inr {x} => ({ok}))"
        if tag == "record":
            values = [child(x)[1] for _, x in e[2]]
            ty = ("record", e[1])
            return ty, f"({_tuple(values)} : VSCore3.Denote {self.shape(ty)})"
        if tag == "project":
            ty, value = child(e[1]); fields = self.decls[ty[1]]["fields"]
            i = next(i for i, (n, _) in enumerate(fields) if n == e[2])
            return fields[i][1], _projection(i, value)
        if tag in ("none", "nil"):
            ty = ("option" if tag == "none" else "list", e[1])
            return ty, f"({'none' if tag == 'none' else '[]'} : VSCore3.Denote {self.shape(ty)})"
        if tag == "some":
            ty, value = child(e[1]); return ("option", ty), f"(some ({value}))"
        if tag == "cons":
            ty, head = child(e[1]); _, tail = child(e[2]); return ("list", ty), f"(({head}) :: ({tail}))"
        if tag in ("match_option", "match_list"):
            ty, value = child(e[1]); result, nil = child(e[2]); x = self.fresh()
            if tag == "match_option":
                _, some = child(e[3], [(ty[1], x)] + stack)
                return result, f"(match ({value}) with | none => ({nil}) | some {x} => ({some}))"
            xs = self.fresh(); _, cons = child(e[3], [(ty, xs), (ty[1], x)] + stack)
            return result, f"(match ({value}) with | [] => ({nil}) | {x} :: {xs} => ({cons}))"
        if tag == "call":
            if len(e[2]) > BUDGETS["max_call_arity"]:
                raise Unavailable("ARITY_BUDGET", "readable call arity exceeded")
            args = [child(x)[1] for x in e[2]]
            return self.helpers[e[1]]["result"], _join([f"({self.names[e[1]]}_named ",_join((f"({x})" for x in args)," "),")"])
        if tag in ("list_fold", "nat_fold"):
            ty, source = child(e[1]); result, initial = child(e[2]); acc, item = self.fresh(), self.fresh()
            gamma = [(ty[1], item), (result, acc)] + stack if tag == "list_fold" else [(result, acc), ("nat", item)] + stack
            _, step = child(e[3], gamma)
            value = f"List.foldl (fun {acc} {item} => ({step})) ({initial}) ({source})" if tag == "list_fold" else f"Nat.rec ({initial}) (fun {item} {acc} => ({step})) ({source})"
            return result, f"({value})"
        if tag in ("list_map", "list_filter"):
            ty, value = child(e[1]); item = self.fresh(); result, body = child(e[2], [(ty[1], item)] + stack)
            primitive = "map" if tag == "list_map" else "filter"
            return (("list", result) if primitive == "map" else ty), f"(List.{primitive} (fun {item} => ({body})) ({value}))"
        if tag in ("int_fdiv", "list_append", "list_get"):
            ty, a = child(e[1]); _, b = child(e[2])
            if tag == "list_append": return ty, f"(({a}) ++ ({b}))"
            if tag == "list_get": return ("option", ty[1]), f"(List.get?Internal ({a}) ({b}))"
            return "int", f"(Int.fdiv ({a}) ({b}))"
        ty, value = child(e[1])
        unary = {"int_neg": ("int", "Int.neg"), "nat_to_int": ("int", "Int.ofNat"),
                 "int_to_nat": ("nat", "Int.toNat"), "list_range": (("list", "nat"), "List.range"),
                 "list_length": ("nat", "List.length"), "list_reverse": (ty, "List.reverse"),
                 "list_unique": (ty, "List.eraseDups"), "list_sum": (ty[1] if isinstance(ty, tuple) else ty, "List.sum")}
        if tag == "list_sort":
            return ty, f"(List.mergeSort ({value}) (fun a b => decide (a ≤ b)))"
        result, primitive = unary[tag]
        return result, f"({primitive} ({value}))"

    def render(self) -> View:
        for key in ("helpers", "entries"):
            if len(self.program[key]) > BUDGETS[key]:
                raise Unavailable("HELPER_BUDGET" if key == "helpers" else "ENTRY_BUDGET", f"readable {key} exceeded")
        if sum(len(d.get("fields", [])) for d in self.decls.values()) > BUDGETS["total_record_fields"]:
            raise Unavailable("FIELD_BUDGET", "readable field budget exceeded")
        for d in self.decls.values():
            if d["tag"] != "record":
                raise Unavailable("UNSUPPORTED_TYPE", "variant declarations are unavailable in readable view")
            self.shape(("record", d["id"]))
        pending = list(enumerate(self.program["helpers"])); order = []; available = set()
        while pending:
            next_pending = []; progress = False
            for i, f in pending:
                deps = {e[1] for e in S._walk(f["body"]) if e[0] == "call"}
                if deps <= available:
                    order.append(("helper", i, f, [x[2]["id"] for x in order]))
                    available.add(f["id"]); progress = True
                else: next_pending.append((i, f))
            if not progress:
                raise Unavailable("UNSUPPORTED_TYPE", "unresolved readable helper graph")
            pending = next_pending
        order += [("entry", i, f, [x[2]["id"] for x in order]) for i, f in enumerate(self.program["entries"])]
        out = Lines();out.append("namespace " + NAMESPACE)
        functions = []
        for compiled_i, (role, source_i, f, context) in enumerate(order):
            name = self.names[f["id"]]; params = [self.shape(t) for t in f["params"]]; result = self.shape(f["result"])
            p = _join(["[",_join(params,", "),"]"])
            stack = [(t, _projection(i)) for i, t in enumerate(reversed(f["params"]))]
            self.serial = 0
            ty, body = self.expr(f["body"], stack)
            if ty != f["result"]:
                raise Unavailable("CORRESPONDENCE_REJECTION", "readable proposed body type differs")
            binders = _join((f"(p__{i} : VSCore3.Denote {t})" for i, t in enumerate(params))," ")
            out += [_join([f"abbrev {name}_params : List VSCore3.Shape := ",p]),
                    _join([f"abbrev {name}_result : VSCore3.Shape := ",result]),
                    f"def {name}_body (env : VSCore3.Env {name}_params.reverse) : VSCore3.Denote {name}_result := by",
                    _join(["  with_unfolding_all exact ",body]),
                    f"def {name}_run (env : VSCore3.Env {name}_params) : VSCore3.Denote {name}_result :=",
                    f"  {name}_body (VSCore3.envReverse {name}_params env)",
                    _join([f"def {name}_named ",binders,f" : VSCore3.Denote {name}_result :="]),
                    _join([f"  {name}_run ",_tuple([f'p__{i}' for i in range(len(params))])])]
            functions.append({"role": role, "source_id": f["id"], "source_index": source_i,
                              "compiled_index": compiled_i if role == "helper" else source_i,
                              "name": name, "params": p, "result": result,
                              "source_declaration_hash": canonical.digest_json({"id": f["id"],
                                  "params": [S.ty_json(t) for t in f["params"]],
                                  "result": S.ty_json(f["result"]), "body": S.expr_json(f["body"])}),
                              "compilation_context_hash": canonical.digest_json(context)})
        out.append("end " + NAMESPACE)
        block = ("\n".join(out) + "\n").encode()
        if self.ir_bytes+len(canonical.dumps(functions))+len(canonical.dumps(source_registry(self.enums)))+512>BUDGETS["typed_ir_bytes"]:
            raise Unavailable("OUTPUT_BUDGET","readable typed metadata composite budget exceeded before emission")
        ir = canonical.dumps({"format": "verislop.vscore-readable-ir/1", "source": canonical.digest(self.source),
                              "registry": source_registry(self.enums), "nodes": self.ir, "functions": functions})
        if len(block) > BUDGETS["source_block_bytes"] or len(ir) > BUDGETS["typed_ir_bytes"]:
            raise Unavailable("OUTPUT_BUDGET", "readable artifact byte budget exceeded")
        key = canonical.digest_json({"source": canonical.digest(self.source), "registry": source_registry(self.enums),
                                     "renderer": descriptor()})
        return View(block, b"import VSCore3\n" + block, ir, functions, sorted(self.seen), key)


def render(source: bytes, enums: dict[str, list[str]], program: dict | None = None) -> View:
    program = program or S.parse_source(source)
    S.check_program(enums, program)
    return Renderer(source, enums, program).render()
