"""Source-bound, conservative admission of closed Python JSON computations.

This is an explicitly trusted AST/ownership checker, not a proof of CPython or
physical execution.  It never executes candidates.  The returned receipt is
computed from source bytes and policy inputs; it cannot accept a proposed PASS.
Fresh containers own their root, while indexed/iterated borrowed descendants
remain borrowed.  Unsupported syntax or uncertain ownership blocks admission.
"""
from __future__ import annotations

import ast
import keyword
import platform
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from . import canonical

CHECKER_ID = "verislop.python-boundary/0.1"
FORMAT = "verislop.python-boundary-receipt/0.1"
DEFAULT_LIMITS = {"files": 64, "file_bytes": 2 * 1024 * 1024,
                  "total_bytes": 4 * 1024 * 1024, "nodes": 100000,
                  "depth": 128, "functions": 256, "analysis_steps": 200000,
                  "loop_iterations": 16, "regions": 4096, "diagnostics": 64}
MAX_VALUE_REFS = 256
BUILTINS = frozenset({"len", "sum", "list", "range"})
EXCEPTIONS = frozenset({"ValueError", "TypeError", "RuntimeError", "ArithmeticError", "AssertionError"})
JSON_KINDS = frozenset({"scalar", "list", "dict", "tuple"})


class _LatticeLimit(Exception):
    pass


@dataclass(frozen=True)
class _Value:
    kinds: frozenset[str] = frozenset()
    refs: frozenset[str] = frozenset()
    unbound: bool = False
    integer_origin: bool = False

    def join(self, other: "_Value") -> "_Value":
        refs = self.refs | other.refs
        if len(refs) > MAX_VALUE_REFS:
            raise _LatticeLimit("abstract value exceeds the registered alias-set bound")
        if not self.kinds and not self.refs and not self.unbound:
            integer = other.integer_origin
        elif not other.kinds and not other.refs and not other.unbound:
            integer = self.integer_origin
        else:
            integer = self.integer_origin and other.integer_origin
        return _Value(self.kinds | other.kinds, refs,
                      self.unbound or other.unbound, integer)


BOTTOM = _Value()
SCALAR = _Value(frozenset({"scalar"}))
INTEGER = _Value(frozenset({"scalar"}), integer_origin=True)
RANGE = _Value(frozenset({"range"}))


@dataclass
class _Region:
    kind: str
    owned: bool
    item: _Value = BOTTOM
    fields: dict[str, _Value] = field(default_factory=dict)

    def copy(self) -> "_Region":
        return _Region(self.kind, self.owned, self.item, dict(self.fields))


class _Rejected(Exception):
    def __init__(self, code: str, message: str, file: str, path: str,
                 node: ast.AST | None = None):
        self.diagnostic = {"code": code, "message": message, "file": file,
                           "ast_path": path, "line": getattr(node, "lineno", None),
                           "column": getattr(node, "col_offset", None)}


def _join(values) -> _Value:
    out = BOTTOM
    for value in values:
        out = out.join(value)
    return out


def _copy_heap(heap):
    return {key: region.copy() for key, region in heap.items()}


def _merge_heap(left, right):
    out = _copy_heap(left)
    for key, value in right.items():
        if key not in out:
            out[key] = value.copy()
        else:
            prior = out[key]
            prior.owned = prior.owned and value.owned
            prior.item = prior.item.join(value.item)
            for name, item in value.fields.items():
                prior.fields[name] = prior.fields.get(name, BOTTOM).join(item)
    return out


def _merge_env(left, right):
    return {key: left.get(key, _Value(unbound=True)).join(
        right.get(key, _Value(unbound=True))) for key in left.keys() | right.keys()}


def _safe_path(value: Any) -> bool:
    return (isinstance(value, str) and bool(value) and "\\" not in value and
            "\x00" not in value and not PurePosixPath(value).is_absolute() and
            all(part not in {"", ".", ".."} for part in value.split("/")))


def _policy_hash(value, limits):
    """Bound host policy traversal too; malformed metadata is never a PASS."""
    stack, seen = [(value, 0)], 0
    while stack:
        node, depth = stack.pop()
        seen += 1
        if seen > limits["nodes"] or depth > limits["depth"]:
            raise _Rejected("TYPE_SHAPE", "policy metadata exceeds its node/depth bound", "", "/")
        if type(node) is dict:
            if any(type(key) is not str for key in node):
                raise _Rejected("TYPE_SHAPE", "policy metadata requires string dictionary keys", "", "/")
            stack.extend((item, depth + 1) for item in node.values())
        elif type(node) is list:
            stack.extend((item, depth + 1) for item in node)
        elif type(node) not in {str, int, bool, type(None)}:
            raise _Rejected("TYPE_SHAPE", "policy metadata is not canonical JSON", "", "/")
    try:
        return canonical.digest_json(value)
    except (canonical.CanonicalJSONError, RecursionError) as exc:
        raise _Rejected("TYPE_SHAPE", "policy metadata is not bounded canonical JSON: " + str(exc), "", "/") from None


class _Checker:
    def __init__(self, sources, limits, typed_args, profile):
        self.sources, self.limits = sources, limits
        self.typed_args, self.profile = typed_args, profile
        self.trees = {}
        self.paths = {}
        self.functions = {}
        self.calls = {}
        self.summaries = {}
        self.heap = {}
        self.active = frozenset()
        self.steps = 0
        self.file = ""
        self.function = ""
        self.locals = set()
        self.returns = []
        self.last_node = None
        self.floating_point_sites = []
        self.floating_point_keys = set()
        self.floating_point_sites_truncated = False

    def fail(self, code, message, node=None, path=None):
        raise _Rejected(code, message, self.file, path or self.paths.get(id(node), "/"), node)

    def tick(self, node=None, amount=1):
        if node is not None:
            self.last_node = node
        self.steps += amount
        if self.steps > self.limits["analysis_steps"]:
            self.fail("ANALYSIS_LIMIT", "ownership analysis exceeded its explicit work bound", node)

    def heap_work(self, *heaps):
        self.tick(self.last_node, sum(1 + len(region.fields) + len(region.item.refs) +
                  sum(len(value.refs) for value in region.fields.values())
                  for heap in heaps for region in heap.values()))

    def copy_heap(self):
        self.heap_work(self.heap)
        return _copy_heap(self.heap)

    def merge_heap(self, left, right):
        self.heap_work(left, right)
        return _merge_heap(left, right)

    def region_bound(self):
        if len(self.heap) > self.limits["regions"]:
            self.fail("ANALYSIS_LIMIT", "ownership heap exceeds the registered region bound", self.last_node)

    def floating_site(self, node, path=None):
        path = path or self.paths[id(node)]
        key = (self.file, path)
        if key in self.floating_point_keys:
            return
        self.floating_point_keys.add(key)
        if len(self.floating_point_sites) >= self.limits["diagnostics"]:
            self.floating_point_sites_truncated = True
            return
        self.floating_point_sites.append({"code": "FLOATING_POINT_OPERATION", "file": self.file,
            "ast_path": path, "line": getattr(node, "lineno", None), "column": getattr(node, "col_offset", None),
            "message": "source operation may introduce floating point; the required policy admits only integer arithmetic"})

    def parse(self):
        total_nodes = 0
        for file, source in sorted(self.sources.items()):
            if not file.endswith(".py"):
                continue
            self.file = file
            try:
                tree = ast.parse(source, filename=file)
            except (SyntaxError, ValueError, UnicodeError, RecursionError) as exc:
                self.fail("SOURCE_PARSE", str(exc), path="/")
            self.trees[file] = tree
            stack = [(tree, "/", 0)]
            while stack:
                node, path, depth = stack.pop()
                total_nodes += 1
                if total_nodes > self.limits["nodes"] or depth > self.limits["depth"]:
                    self.fail("SYNTAX_LIMIT", "source AST exceeds the node/depth bound", node, path)
                self.paths[id(node)] = path
                exponent = node.right if isinstance(node, ast.BinOp) else node.value if isinstance(node, ast.AugAssign) else None
                floating = (isinstance(node, ast.Constant) and type(node.value) is float or
                    isinstance(node, (ast.BinOp, ast.AugAssign)) and (isinstance(node.op, ast.Div) or
                        isinstance(node.op, ast.Pow) and not (isinstance(exponent, ast.Constant)
                            and type(exponent.value) is int and exponent.value >= 0)))
                if floating:
                    self.floating_site(node, path)
                for name, value in ast.iter_fields(node):
                    if isinstance(value, ast.AST):
                        stack.append((value, path.rstrip("/") + "/" + name, depth + 1))
                    elif isinstance(value, list):
                        stack.extend((child, path.rstrip("/") + f"/{name}/{i}", depth + 1)
                                     for i, child in enumerate(value) if isinstance(child, ast.AST))
            names = set()
            for node in tree.body:
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and type(node.value.value) is str:
                    continue
                if not isinstance(node, ast.FunctionDef):
                    self.fail("MODULE_STATEMENT", "only plain function definitions and docstrings are admitted at module scope", node)
                if node.name in names:
                    self.fail("DUPLICATE_GLOBAL", "top-level function name is defined more than once: " + node.name, node)
                names.add(node.name)
                if node.name in BUILTINS | EXCEPTIONS or node.name.startswith("__"):
                    self.fail("RESERVED_GLOBAL", "function shadows a registered primitive or reflection name", node)
                if (node.decorator_list or node.returns is not None or getattr(node, "type_params", []) or
                        node.args.defaults or node.args.kwonlyargs or node.args.vararg or node.args.kwarg or
                        any(arg.annotation is not None for arg in [*node.args.posonlyargs, *node.args.args])):
                    self.fail("FUNCTION_METADATA", "annotations, defaults, decorators, variadic and keyword-only arguments are unsupported", node)
                args = [arg.arg for arg in [*node.args.posonlyargs, *node.args.args]]
                if len(set(args)) != len(args):
                    self.fail("DUPLICATE_PARAMETER", "function parameters must be unique", node)
                self.functions[(file, node.name)] = node
        if len(self.functions) > self.limits["functions"]:
            self.fail("SYNTAX_LIMIT", "source exceeds the function-count bound")

    def local_names(self, function):
        names = {arg.arg for arg in [*function.args.posonlyargs, *function.args.args]}
        stack = list(function.body)
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.ListComp, ast.DictComp, ast.GeneratorExp, ast.SetComp)):
                # Comprehension targets live in a separate Python lexical scope.
                continue
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.add(node.id)
            stack.extend(ast.iter_child_nodes(node))
        return names

    def graph(self):
        for key, function in self.functions.items():
            self.file = key[0]
            local = self.local_names(function)
            calls = set()
            for node in ast.walk(function):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    target = (self.file, node.func.id)
                    if target in self.functions and node.func.id not in local:
                        calls.add(target)
            self.calls[key] = calls
        colors, order = {}, []
        def visit(key, depth=0):
            if depth > self.limits["depth"]:
                self.file = key[0]
                self.fail("ANALYSIS_LIMIT", "call graph exceeds its depth bound", self.functions[key])
            if colors.get(key) == 1:
                self.file = key[0]
                self.fail("CYCLIC_CALLS", "recursive/cyclic helper calls are outside the closed source profile", self.functions[key])
            if colors.get(key) == 2:
                return
            colors[key] = 1
            for child in sorted(self.calls[key]):
                visit(child, depth + 1)
            colors[key] = 2
            order.append(key)
        for key in sorted(self.functions):
            visit(key)
        return order

    def borrow(self, sort=None, key="unknown", depth=0, visiting=frozenset()):
        self.tick()
        if depth > self.limits["depth"]:
            self.fail("ANALYSIS_LIMIT", "typed ownership shape exceeds its depth bound")
        if isinstance(sort, str) and sort in {"Nat", "Int", "Bool"}:
            return INTEGER
        if isinstance(sort, str) and sort in {"Unit", "String"}:
            return SCALAR
        if isinstance(sort, dict) and "enum" in sort:
            return SCALAR
        if isinstance(sort, dict) and "option" in sort:
            return SCALAR.join(self.borrow(sort["option"], key + ".some", depth + 1, visiting))
        ref = "$borrow:" + key
        if isinstance(sort, dict) and "list" in sort:
            self.heap[ref] = _Region("list", False, self.borrow(sort["list"], key + ".item", depth + 1, visiting))
            self.region_bound()
            return _Value(frozenset({"list"}), frozenset({ref}))
        if isinstance(sort, dict) and "record" in sort:
            name = sort["record"]
            records = self.profile.get("records", {})
            if isinstance(name, str) and name in records:
                if name in visiting:
                    self.fail("TYPE_SHAPE", "recursive record ownership shapes are unsupported")
                fields = {f["name"]: self.borrow(f["sort"], key + "." + f["name"], depth + 1, visiting | {name})
                          for f in records[name]["fields"]}
                self.heap[ref] = _Region("dict", False, fields=fields)
                self.region_bound()
                return _Value(frozenset({"dict"}), frozenset({ref}))
        if isinstance(sort, dict) and "result" in sort:
            payload = self.borrow(sort["result"]["ok"], key + ".ok", depth + 1, visiting).join(
                self.borrow(sort["result"]["error"], key + ".error", depth + 1, visiting))
            self.heap[ref] = _Region("tuple", False, SCALAR.join(payload), {"0": SCALAR, "1": payload})
            self.region_bound()
            return _Value(frozenset({"tuple"}), frozenset({ref}))
        self.heap[ref] = _Region("unknown", False)
        self.region_bound()
        return _Value(JSON_KINDS, frozenset({ref}))

    def allocate(self, kind, node, item=BOTTOM, fields=None, suffix=""):
        ref = "$fresh:" + self.file + ":" + self.function + ":" + self.paths[id(node)] + suffix
        region = _Region(kind, True, item, fields or {})
        if ref in self.heap:
            old = self.heap[ref]
            self.tick(node, 1 + len(old.item.refs) + len(item.refs) + len(fields or {}))
            old.item = old.item.join(item)
            for key, value in (fields or {}).items():
                old.fields[key] = old.fields.get(key, BOTTOM).join(value)
        else:
            self.heap[ref] = region
            self.region_bound()
        return _Value(frozenset({kind}), frozenset({ref}))

    def items(self, value):
        items = []
        if value.kinds & {"scalar", "dict"}:
            # String elements and JSON dictionary keys are immutable.
            items.append(SCALAR)
        if "range" in value.kinds:
            items.append(INTEGER)
        for ref in value.refs:
            region = self.heap[ref]
            if region.kind == "unknown":
                items.append(self.borrow(key="unknown-child"))
            elif region.kind != "dict":
                items.append(region.item)
        return _join(items) or BOTTOM

    def child(self, value, key):
        items = []
        if "scalar" in value.kinds:
            items.append(SCALAR)  # Only strings among scalar JSON values support indexing.
        for ref in value.refs:
            region = self.heap[ref]
            if region.kind == "unknown":
                items.append(self.borrow(key="unknown-child"))
            elif region.kind == "dict":
                items.append(region.fields.get(key, BOTTOM).join(region.item) if key is not None
                             else _join([region.item, *region.fields.values()]))
            elif region.kind == "tuple" and region.fields and isinstance(key, int):
                index = key if key >= 0 else len(region.fields) + key
                items.append(region.fields.get(str(index), BOTTOM))
            else:
                items.append(region.item)
        return _join(items)

    def mutable(self, value, node, operation):
        if not value.refs or any(not self.heap[ref].owned for ref in value.refs):
            self.fail("BORROWED_WRITE", operation + " requires a proved fresh receiver; a local name does not establish ownership", node)
        if value.refs & self.active:
            self.fail("ACTIVE_ITERABLE_WRITE", operation + " may mutate a currently active iterable or its alias", node)

    def write(self, container, value, node, key=None):
        self.mutable(container, node, "container write")
        if not container.kinds <= {"list", "dict"}:
            self.fail("WRITE_SHAPE", "only fresh list/dictionary receivers support writes", node)
        for ref in container.refs:
            region = self.heap[ref]
            if region.kind == "dict" and key is not None:
                region.fields[key] = region.fields.get(key, BOTTOM).join(value)
            else:
                region.item = region.item.join(value)

    def name(self, node, env):
        if node.id.startswith("__"):
            self.fail("REFLECTION_NAME", "reflection names are outside the closed source profile", node)
        value = env.get(node.id)
        if value is None or value.unbound:
            self.fail("UNCLOSED_NAME", "name has no definitely bound JSON value in this lexical scope: " + node.id, node)
        return value

    def binary(self, left, right, op, node):
        if not isinstance(op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)):
            self.fail("UNSUPPORTED_OPERATOR", "operator is outside the registered primitive profile", node)
        if isinstance(op, ast.Mod) and not left.integer_origin:
            # String %-formatting can convert an integer through floating
            # point. Unknown left values must not masquerade as integer modulo.
            self.floating_site(node)
        exponent = node.right if isinstance(node, ast.BinOp) else node.value if isinstance(node, ast.AugAssign) else None
        literal_power = isinstance(exponent, ast.Constant) and type(exponent.value) is int and exponent.value >= 0
        integer = left.integer_origin and right.integer_origin and not isinstance(op, ast.Div) and (not isinstance(op, ast.Pow) or literal_power)
        result = INTEGER if integer else SCALAR
        if isinstance(op, ast.Add) and left.kinds == right.kinds and left.kinds in (frozenset({"list"}), frozenset({"tuple"})):
            result = BOTTOM
        elif isinstance(op, ast.Mult) and ((left.kinds in (frozenset({"list"}), frozenset({"tuple"})) and right.kinds <= {"scalar"}) or
                                           (right.kinds in (frozenset({"list"}), frozenset({"tuple"})) and left.kinds <= {"scalar"})):
            result = BOTTOM
        if isinstance(op, (ast.Add, ast.Mult)):
            for kind in {"list", "tuple"} & (left.kinds | right.kinds):
                result = result.join(self.allocate(kind, node, self.items(left).join(self.items(right)), suffix=":" + kind))
        return result

    def expr(self, node, env):
        self.tick(node)
        if isinstance(node, ast.Constant):
            if type(node.value) not in {type(None), bool, int, float, str}:
                self.fail("NON_JSON_LITERAL", "literal is not an admitted JSON scalar", node)
            if type(node.value) is str and any(0xD800 <= ord(c) <= 0xDFFF for c in node.value):
                self.fail("NON_JSON_LITERAL", "string contains a non-scalar surrogate", node)
            if type(node.value) is float and (node.value != node.value or abs(node.value) == float("inf")):
                self.fail("NON_JSON_LITERAL", "nonfinite float literals are not JSON scalars", node)
            return INTEGER if type(node.value) in {int, bool} else SCALAR
        if isinstance(node, ast.Name):
            return self.name(node, env)
        if isinstance(node, (ast.List, ast.Tuple)):
            values = [self.expr(item, env) for item in node.elts]
            return self.allocate("list" if isinstance(node, ast.List) else "tuple", node,
                                 _join(values), {str(i): v for i, v in enumerate(values)} if isinstance(node, ast.Tuple) else {})
        if isinstance(node, ast.Dict):
            fields, unknown = {}, BOTTOM
            for key, value in zip(node.keys, node.values):
                if key is None:
                    self.fail("DICT_UNPACKING", "dictionary unpacking is outside the closed source profile", node)
                self.expr(key, env)
                item = self.expr(value, env)
                if isinstance(key, ast.Constant) and type(key.value) is str:
                    fields[key.value] = fields.get(key.value, BOTTOM).join(item)
                else:
                    unknown = unknown.join(item)
            return self.allocate("dict", node, unknown, fields)
        if isinstance(node, ast.Subscript):
            value = self.expr(node.value, env)
            if isinstance(node.slice, ast.Slice):
                for bound in [node.slice.lower, node.slice.upper, node.slice.step]:
                    if bound is not None:
                        self.expr(bound, env)
                out = SCALAR if "scalar" in value.kinds else BOTTOM
                for kind in {"list", "tuple"} & value.kinds:
                    out = out.join(self.allocate(kind, node, self.items(value), suffix=":" + kind))
                return out
            self.expr(node.slice, env)
            key = node.slice.value if isinstance(node.slice, ast.Constant) and type(node.slice.value) in {str, int} else None
            return self.child(value, key)
        if isinstance(node, ast.BinOp):
            return self.binary(self.expr(node.left, env), self.expr(node.right, env), node.op, node)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Not, ast.USub, ast.UAdd)):
            operand = self.expr(node.operand, env)
            return INTEGER if isinstance(node.op, ast.Not) or operand.integer_origin else SCALAR
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            return _join(self.expr(value, env) for value in node.values)
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            for i, op in enumerate(node.ops):
                if isinstance(op, (ast.Is, ast.IsNot)):
                    if not any(isinstance(value, ast.Constant) and value.value is None for value in operands[i:i + 2]):
                        self.fail("IDENTITY_OBSERVATION", "identity comparison is admitted only against None; other identities are not JSON-value deterministic", node)
                elif not isinstance(op, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn)):
                    self.fail("UNSUPPORTED_OPERATOR", "comparison is outside the registered primitive profile", node)
            for value in operands:
                self.expr(value, env)
            return INTEGER
        if isinstance(node, ast.IfExp):
            self.expr(node.test, env)
            before = self.copy_heap()
            left = self.expr(node.body, dict(env)); left_heap = self.heap
            self.heap = before
            right = self.expr(node.orelse, dict(env))
            self.heap = self.merge_heap(left_heap, self.heap)
            return left.join(right)
        if isinstance(node, (ast.ListComp, ast.DictComp)):
            return self.comprehension(node, env)
        if isinstance(node, ast.Call):
            return self.call(node, env)
        self.fail("UNSUPPORTED_EXPRESSION", "expression is outside the closed source profile: " + type(node).__name__, node)

    def instantiate(self, value, heap, node, memo=None):
        memo = {} if memo is None else memo
        refs = set()
        for old in sorted(value.refs):
            self.tick(node)
            region = heap[old]
            if not region.owned:
                refs.update(self.borrow(key="helper-return").refs)
                continue
            if old not in memo:
                new = "$fresh:" + self.file + ":" + self.function + ":" + self.paths[id(node)] + ":" + old
                memo[old] = new
                prior = self.heap.get(new)
                self.heap[new] = _Region(region.kind, True)
                self.region_bound()
                self.heap[new].item = self.instantiate(region.item, heap, node, memo)
                self.heap[new].fields = {key: self.instantiate(item, heap, node, memo) for key, item in region.fields.items()}
                if prior:
                    self.heap = self.merge_heap(self.heap, {new: prior})
            refs.add(memo[old])
        return _Value(value.kinds, frozenset(refs), value.unbound, value.integer_origin)

    def call(self, node, env):
        if node.keywords or any(isinstance(arg, ast.Starred) for arg in node.args):
            self.fail("DYNAMIC_CALL", "calls require positional arguments without expansion", node)
        if isinstance(node.func, ast.Attribute):
            if node.func.attr != "append" or len(node.args) != 1:
                self.fail("ATTRIBUTE_CALL", "only one-argument append on a proved fresh list receiver is admitted", node)
            receiver = self.expr(node.func.value, env)
            self.mutable(receiver, node, "append")
            if receiver.kinds != frozenset({"list"}):
                self.fail("WRITE_SHAPE", "append receiver is not definitely a fresh list", node)
            item = self.expr(node.args[0], env)
            for ref in receiver.refs:
                self.heap[ref].item = self.heap[ref].item.join(item)
            return SCALAR
        if not isinstance(node.func, ast.Name):
            self.fail("DYNAMIC_CALL", "call target must be a lexically resolved helper or registered primitive", node)
        name = node.func.id
        if name in self.locals or name in env:
            self.fail("SHADOWED_CALL", "call target is a local binding, not the registered helper/primitive: " + name, node)
        args = [self.expr(arg, env) for arg in node.args]
        key = (self.file, name)
        if key in self.summaries:
            function = self.functions[key]
            if len(args) != len(function.args.posonlyargs) + len(function.args.args):
                self.fail("CALL_ARITY", "helper call does not match its positional arity", node)
            value, heap = self.summaries[key]
            return self.instantiate(value, heap, node)
        if name not in BUILTINS:
            self.fail("UNCLOSED_CALL", "call target is outside the registered closed language: " + name, node)
        if ((name in {"len", "list"} and len(args) != 1) or
                (name == "sum" and len(args) not in {1, 2}) or
                (name == "range" and len(args) not in {1, 2, 3})):
            self.fail("CALL_ARITY", "primitive call does not match its registered arity", node)
        if name == "len":
            return INTEGER
        if name == "range":
            return RANGE
        if name == "list":
            return self.allocate("list", node, self.items(args[0]))
        items = self.items(args[0])
        if items.kinds <= {"scalar"} and (len(args) == 1 or args[1].kinds <= {"scalar"}):
            return INTEGER if (items.integer_origin or not items.kinds) and (len(args) == 1 or args[1].integer_origin) else SCALAR
        return self.borrow(key="sum-result")

    def bind(self, target, value, env):
        self.tick(target)
        if isinstance(target, ast.Name):
            if target.id.startswith("__"):
                self.fail("REFLECTION_NAME", "reflection names are outside the closed source profile", target)
            env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            for i, child in enumerate(target.elts):
                self.bind(child, self.child(value, i), env)
        elif isinstance(target, ast.Subscript):
            receiver = self.expr(target.value, env)
            if isinstance(target.slice, ast.Slice):
                for bound in [target.slice.lower, target.slice.upper, target.slice.step]:
                    if bound is not None:
                        self.expr(bound, env)
                self.write(receiver, self.items(value), target)
            else:
                self.expr(target.slice, env)
                key = target.slice.value if isinstance(target.slice, ast.Constant) and type(target.slice.value) is str else None
                self.write(receiver, value, target, key)
        else:
            self.fail("UNSUPPORTED_ASSIGNMENT", "assignment target is outside the closed source profile", target)

    def augmented(self, node, env):
        value = self.expr(node.target, env)
        right = self.expr(node.value, env)
        if isinstance(node.op, (ast.Add, ast.Mult)) and "list" in value.kinds:
            self.mutable(value, node, "mutating augmented assignment")
            if value.kinds != frozenset({"list"}):
                self.fail("WRITE_SHAPE", "augmented assignment receiver has uncertain mutable shape", node)
            for ref in value.refs:
                self.heap[ref].item = self.heap[ref].item.join(self.items(right))
            result = value
        elif value.kinds & {"dict"}:
            self.fail("WRITE_SHAPE", "augmented assignment on an uncertain container is unsupported", node)
        else:
            result = self.binary(value, right, node.op, node)
        self.bind(node.target, result, env)

    def loop(self, node, env):
        iterable = self.expr(node.iter, env)
        before = dict(env)
        active = self.active
        self.active |= iterable.refs
        try:
            for _ in range(self.limits["loop_iterations"]):
                old_env, old_heap = dict(env), self.copy_heap()
                self.bind(node.target, self.items(iterable), env)
                self.block(node.body, env)
                merged = _merge_env(before, _merge_env(old_env, env))
                env.clear(); env.update(merged)
                # Join the zero-iteration and successive-iteration paths.
                self.heap = self.merge_heap(old_heap, self.heap)
                if env == old_env and self.heap == old_heap:
                    break
            else:
                self.fail("OWNERSHIP_FIXPOINT", "loop ownership did not stabilize within its explicit analysis bound", node)
        finally:
            self.active = active
        self.block(node.orelse, env)

    def comprehension(self, node, env):
        local = dict(env)
        active = self.active
        try:
            for generator in node.generators:
                if generator.is_async:
                    self.fail("ASYNC_COMPREHENSION", "asynchronous comprehensions are unsupported", generator)
                iterable = self.expr(generator.iter, local)
                self.active |= iterable.refs
                self.bind(generator.target, self.items(iterable), local)
                for condition in generator.ifs:
                    self.expr(condition, local)
            if isinstance(node, ast.ListComp):
                return self.allocate("list", node, self.expr(node.elt, local))
            self.expr(node.key, local)
            return self.allocate("dict", node, self.expr(node.value, local))
        finally:
            self.active = active

    def block(self, statements, env):
        always_returns = False
        for node in statements:
            self.tick(node)
            if isinstance(node, ast.Return):
                self.returns.append(SCALAR if node.value is None else self.expr(node.value, env))
                always_returns = True
            elif isinstance(node, ast.Assign):
                value = self.expr(node.value, env)
                for target in node.targets:
                    self.bind(target, value, env)
            elif isinstance(node, ast.AugAssign):
                self.augmented(node, env)
            elif isinstance(node, ast.Expr):
                self.expr(node.value, env)
            elif isinstance(node, ast.If):
                self.expr(node.test, env)
                before = self.copy_heap()
                left_env = dict(env); left_returns = self.block(node.body, left_env); left_heap = self.heap
                self.heap = before
                right_env = dict(env); right_returns = self.block(node.orelse, right_env)
                self.heap = self.merge_heap(left_heap, self.heap)
                merged = _merge_env(left_env, right_env)
                env.clear(); env.update(merged)
                always_returns |= left_returns and right_returns
            elif isinstance(node, ast.For):
                self.loop(node, env)
            elif isinstance(node, (ast.Pass, ast.Break, ast.Continue)):
                if isinstance(node, (ast.Break, ast.Continue)) and not self.active:
                    # A range has no mutable root, so inspect its lexical ancestry instead.
                    path = self.paths[id(node)]
                    if not any(path.startswith(self.paths[id(loop)] + "/body/") for loop in ast.walk(self.functions[(self.file, self.function)]) if isinstance(loop, ast.For)):
                        self.fail("LOOP_CONTROL", "break/continue is outside a for loop", node)
            elif isinstance(node, ast.Raise):
                exc = node.exc
                if (node.cause is not None or not isinstance(exc, ast.Call) or
                        not isinstance(exc.func, ast.Name) or exc.func.id not in EXCEPTIONS or
                        exc.func.id in self.locals or exc.keywords or
                        any(not isinstance(arg, ast.Constant) for arg in exc.args)):
                    self.fail("UNSUPPORTED_RAISE", "only an unshadowed registered exception with literal arguments is admitted", node)
                for arg in exc.args:
                    self.expr(arg, env)
                always_returns = True
            elif isinstance(node, ast.Assert):
                self.expr(node.test, env)
                if node.msg is not None:
                    self.expr(node.msg, env)
            else:
                self.fail("UNSUPPORTED_STATEMENT", "statement is outside the closed source profile: " + type(node).__name__, node)
        return always_returns

    def analyze(self, order):
        called = set().union(*self.calls.values()) if self.calls else set()
        for key in order:
            self.file, self.function = key
            function = self.functions[key]
            self.locals = self.local_names(function)
            self.heap, self.returns, self.active = {}, [], frozenset()
            params = [arg.arg for arg in [*function.args.posonlyargs, *function.args.args]]
            sorts = self.typed_args.get(self.file + ":" + self.function,
                        self.typed_args.get(self.function, [None] * len(params)))
            if not isinstance(sorts, list) or len(sorts) != len(params):
                self.fail("TYPE_SHAPE", "typed argument manifest does not match the function arity", function)
            if key in called:
                # External adapter signatures cannot establish the types of
                # internal Python calls.  Every helper parameter stays borrowed.
                sorts = [None] * len(params)
            env = {name: self.borrow(sort, self.function + "." + name) for name, sort in zip(params, sorts)}
            if not self.block(function.body, env):
                self.returns.append(SCALAR)
            self.summaries[key] = (_join(self.returns), self.copy_heap())


def check_sources(sources: Mapping[str, bytes], *, expected_entry: dict | None = None,
                  typed_args: Mapping[str, list] | None = None,
                  profile: dict | None = None, limits: dict | None = None) -> dict:
    """Compute a hash-bound source receipt; never execute or alter candidate bytes.

    ``expected_entry`` is exactly ``{file, name, arity}``. ``typed_args`` maps
    ``file.py:function`` (or an unambiguous function name) to accepted DSL sorts;
    ``profile.records`` optionally resolves record field sorts.  Missing types
    are conservative borrowed JSON values.  Type information is a trusted
    adapter premise, retained by hash, never an assertion of fresh ownership.
    """
    bounds = dict(DEFAULT_LIMITS)
    diagnostics, inventory, functions = [], {}, []
    checker = None
    entry = None
    typed_hash = profile_hash = entry_hash = None
    typed_args = {} if typed_args is None else typed_args
    profile = {} if profile is None else profile
    try:
        if limits is not None:
            if not isinstance(limits, dict) or set(limits) - set(bounds) or any(type(v) is not int or v < 1 or v > DEFAULT_LIMITS[k] for k, v in limits.items()):
                raise _Rejected("INVALID_POLICY", "limits can only lower the registered positive integer bounds", "", "/")
            bounds.update(limits)
        if not isinstance(sources, Mapping) or not sources or len(sources) > bounds["files"]:
            raise _Rejected("SOURCE_LIMIT", "sources require a nonempty bounded mapping of relative paths to bytes", "", "/")
        if not isinstance(typed_args, Mapping) or not isinstance(profile, dict):
            raise _Rejected("TYPE_SHAPE", "typed arguments/profile have an invalid shape", "", "/")
        typed_hash = _policy_hash(dict(typed_args), DEFAULT_LIMITS)
        profile_hash = _policy_hash(profile, DEFAULT_LIMITS)
        entry_hash = _policy_hash(expected_entry, DEFAULT_LIMITS)
        total = 0
        for file, source in sources.items():
            if not _safe_path(file) or type(source) is not bytes:
                raise _Rejected("SOURCE_SHAPE", "source paths must be normalized safe relative paths and contents must be exact bytes", str(file), "/")
            inventory[file] = canonical.digest(source)
            total += len(source)
            if len(source) > bounds["file_bytes"] or total > bounds["total_bytes"]:
                raise _Rejected("SOURCE_LIMIT", "source bytes exceed the registered bound", file, "/")
        if expected_entry is not None:
            if (not isinstance(expected_entry, dict) or set(expected_entry) != {"file", "name", "arity"} or
                    not _safe_path(expected_entry["file"]) or not expected_entry["file"].endswith(".py") or
                    not isinstance(expected_entry["name"], str) or not expected_entry["name"].isidentifier() or
                    keyword.iskeyword(expected_entry["name"]) or type(expected_entry["arity"]) is not int or expected_entry["arity"] < 0):
                raise _Rejected("ENTRY_REQUIREMENT", "entry requirement must have exact safe file/name/nonnegative arity fields", "", "/")
            if unicodedata.normalize("NFKC", expected_entry["name"]) != expected_entry["name"]:
                raise _Rejected("ENTRY_REQUIREMENT", "entry name must already use Python's normalized identifier spelling", expected_entry["file"], "/")
        checker = _Checker(dict(sources), bounds, dict(typed_args), profile)
        checker.parse()
        for (file, name), node in sorted(checker.functions.items()):
            functions.append({"file": file, "name": name, "arity": len(node.args.posonlyargs) + len(node.args.args),
                              "ast_path": checker.paths[id(node)], "line": node.lineno,
                              "ast_hash": canonical.digest(ast.dump(node, include_attributes=False).encode())})
        if expected_entry is not None:
            found = [f for f in functions if f["file"] == expected_entry["file"] and f["name"] == expected_entry["name"]]
            if len(found) != 1 or found[0]["arity"] != expected_entry["arity"]:
                raise _Rejected("ENTRY_MISMATCH", "required file/function/arity does not identify exactly one delivered definition", expected_entry["file"], "/")
            entry = found[0]
        order = checker.graph()
        checker.analyze(order)
    except _Rejected as exc:
        diagnostics.append(exc.diagnostic)
    except _LatticeLimit as exc:
        diagnostics.append({"code": "ANALYSIS_LIMIT", "message": str(exc), "file": checker.file,
                            "ast_path": checker.paths.get(id(checker.last_node), "/"),
                            "line": getattr(checker.last_node, "lineno", None), "column": getattr(checker.last_node, "col_offset", None)})
    except (RecursionError, KeyError, TypeError, ValueError, OverflowError) as exc:
        diagnostics.append({"code": "ANALYSIS_INCOMPLETE", "message": "source/type ownership analysis is unsupported: " + str(exc),
                            "file": checker.file if checker else "", "ast_path": "/", "line": None, "column": None})
    accepted = not diagnostics
    facts = {"entry_valid": accepted if expected_entry is not None else True,
             "pure_json": accepted,
             "unique_global_names": accepted, "closed_top_level": accepted,
             "closed_calls": accepted, "acyclic_calls": accepted,
             "standard_runtime_only": accepted, "no_target_external_io": accepted,
             "input_frame_preserved": accepted, "deterministic_local_evaluation": accepted,
             "no_floating_point": accepted and not (checker and checker.floating_point_keys),
             "totality_claimed": False}
    receipt = {"format": FORMAT,
               "checker": {"id": CHECKER_ID, "source_hash": canonical.digest_file(Path(__file__))},
               "parser": {"implementation": platform.python_implementation(), "version": sys.version},
               "source_inventory": dict(sorted(inventory.items())), "expected_entry": expected_entry if entry_hash is not None else None,
               "entry_requirement_hash": entry_hash,
               "typed_args_hash": typed_hash, "profile_hash": profile_hash,
               "limits": {**bounds, "alias_refs_per_value": MAX_VALUE_REFS}, "accepted": accepted, "facts": facts, "entry": entry,
               "functions": functions, "call_graph": {f + ":" + n: [cf + ":" + cn for cf, cn in sorted(calls)]
                   for (f, n), calls in sorted(checker.calls.items())} if checker else {},
               "analysis_steps": checker.steps if checker else 0, "diagnostics": diagnostics,
               "floating_point_sites": checker.floating_point_sites if checker else [],
               "floating_point_sites_count": len(checker.floating_point_keys) if checker else 0,
               "floating_point_sites_truncated": checker.floating_point_sites_truncated if checker else False,
               "semantic_domain": {"values": "exact builtin values emitted by the typed JSON adapters",
                   "determinism": "repeated evaluation of the same canonical decoded input",
                   "record_order": "accepted record field order", "list_order": "preserved",
                   "fresh_dictionary_order": "deterministic insertion order",
                   "arbitrary_python_object_or_key_order_invariance": False},
               "trust": ["CPython AST parser and checker implementation", "typed JSON adapters and supplied accepted sort shapes",
                         "CPython semantics of registered exact JSON primitives"],
               "limitations": ["no proof of the Python parser, compiler or runtime", "no universal totality, physical resource or machine-code claim",
                               "host staging and harness I/O are outside target-attributable I/O",
                               "source determinism does not establish invariance across differently ordered raw Python dictionaries",
                               "uncertain ownership and unsupported syntax block conservatively"]}
    receipt["receipt_hash"] = canonical.digest_json(receipt)
    return receipt
