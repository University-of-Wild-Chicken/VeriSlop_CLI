"""Appended to the byte-exact independent legacy helper, never a producer import.

Only a closed pure AST subset constructs strings. No eval/compile/exec, file
reads, tool calls, carrier access or arbitrary attribute/function dispatch.
"""
from pathlib import PurePosixPath
import shlex
import re

_validate_legacy_literals = validate_literals
_legacy_author_message = author_message
COMPACT_SCHEMA = "verislop.independent-compact-protocol-schema/1"
COMPACT_ROLES = {"generator", "reader", "runtime", "descriptor"}
PURE_FUNCTIONS = {"_request", "session_path", "own_pending_key", "runtime_command", "_recipe",
                  "runtime_initial_template", "runtime_next_template", "runtime_confirm_template",
                  "runtime_hash_template", "runtime_agent_message"}


def compact_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def compact_reference(value):
    require(type(value) is dict and set(value) == {"path", "sha256", "request_sha256"} and
            all(type(item) is str for item in value.values()), "COMPACT_REFERENCE_NOT_CLOSED")
    name = value["path"]
    name.encode("utf-8", "strict")
    require(PurePosixPath(name).is_absolute() and str(PurePosixPath(name)) == name and
            ".." not in PurePosixPath(name).parts, "COMPACT_REFERENCE_PATH_INVALID")
    for key in ("sha256", "request_sha256"):
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", value[key]) is not None, "COMPACT_REFERENCE_HASH_INVALID")
    return dict(value)


def compact_code(value):
    names = {"runtime_path", "runtime_sha256", "reader_path", "reader_sha256",
             "node_path", "python_path", "session_directory"}
    require(type(value) is dict and set(value) == names and all(type(v) is str for v in value.values()),
            "COMPACT_CODE_NOT_CLOSED")
    require(value["node_path"] == "/usr/bin/node" and value["python_path"] == "/usr/bin/python3.12",
            "COMPACT_INTERPRETER_PATH_INVALID")
    for key in ("runtime_path", "reader_path", "session_directory"):
        path = PurePosixPath(value[key])
        require(path.is_absolute() and str(path) == value[key] and ".." not in path.parts,
                "COMPACT_CODE_PATH_INVALID")
        value[key].encode("utf-8", "strict")
    for key in ("runtime_sha256", "reader_sha256"):
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", value[key]) is not None, "COMPACT_CODE_HASH_INVALID")
    return dict(value)


def compact_view(value):
    return closed_view(value)


class PureTemplateAST:
    """A string recipe interpreter with a closed function and operation set."""
    def __init__(self, source):
        self.tree = ast.parse(source.decode("utf-8", "strict"))
        self.functions = {}
        self.constants = {}
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef):
                require(node.name not in self.functions and not node.decorator_list,
                        "COMPACT_DUPLICATE_OR_DECORATED_FUNCTION")
                self.functions[node.name] = node
            elif isinstance(node, ast.Assign):
                require(len(node.targets) == 1 and isinstance(node.targets[0], ast.Name),
                        "COMPACT_CONSTANT_ASSIGNMENT_UNSUPPORTED")
                name = node.targets[0].id
                require(name not in self.constants, "COMPACT_DUPLICATE_CONSTANT")
                self.constants[name] = ast.literal_eval(node.value)
            else:
                require(isinstance(node, (ast.Import, ast.ImportFrom)) or
                        isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and
                        type(node.value.value) is str, "COMPACT_TOP_LEVEL_UNSUPPORTED")
        require(PURE_FUNCTIONS.issubset(self.functions), "COMPACT_SOURCE_API_ABSENT")
        require(self.constants.get("API_REVISION") == "support020-compact-runtime/1" and
                self.constants.get("REQUEST_FORMAT") == "verislop.carrier-runtime-request/0.1" and
                self.constants.get("EXEC_PRAGMA") == '// @exec: {"max_output_tokens": 20000}\n' and
                self.constants.get("NODE_PATH") == "/usr/bin/node" and
                self.constants.get("PYTHON_PATH") == "/usr/bin/python3.12" and
                type(self.constants.get("LAUNCHER_SOURCE")) is str and
                type(self.constants.get("SHELL_SAFE_JS")) is str, "COMPACT_SOURCE_CONSTANTS_UNSUPPORTED")

    def schema(self):
        return {"format": COMPACT_SCHEMA, "constants": self.constants,
                "function_ast_hashes": {name: sha(ast.dump(node, include_attributes=False).encode())
                                        for name, node in self.functions.items()}}

    def value(self, node, scope):
        if isinstance(node, ast.Constant):
            require(type(node.value) in (str, int, bool, type(None)), "COMPACT_VALUE_UNSUPPORTED")
            return node.value
        if isinstance(node, ast.Name):
            if node.id in scope:
                return scope[node.id]
            if node.id in self.constants:
                return self.constants[node.id]
            require(node.id in {"str", "dict", "int", "bool"}, "COMPACT_NAME_UNSUPPORTED:" + node.id)
            return {"str": str, "dict": dict, "int": int, "bool": bool}[node.id]
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            values = [self.value(part, scope) for part in node.elts]
            return tuple(values) if isinstance(node, ast.Tuple) else set(values) if isinstance(node, ast.Set) else values
        if isinstance(node, ast.Dict):
            require(None not in node.keys, "COMPACT_DICT_UNPACK_UNSUPPORTED")
            return {self.value(key, scope): self.value(value, scope) for key, value in zip(node.keys, node.values)}
        if isinstance(node, ast.Subscript):
            value, key = self.value(node.value, scope), self.value(node.slice, scope)
            require(type(value) in (dict, str, list, tuple) and type(key) in (str, int), "COMPACT_SUBSCRIPT_UNSUPPORTED")
            return value[key]
        if isinstance(node, ast.BinOp):
            left, right = self.value(node.left, scope), self.value(node.right, scope)
            if isinstance(node.op, ast.Add):
                require(type(left) is type(right) is str, "COMPACT_CONCAT_NOT_STRING")
                return left + right
            require(isinstance(node.op, ast.Div) and isinstance(left, PurePosixPath) and type(right) is str,
                    "COMPACT_OPERATOR_UNSUPPORTED")
            return left / right
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(bool(self.value(part, scope)) for part in node.values)
            require(isinstance(node.op, ast.Or), "COMPACT_BOOLEAN_UNSUPPORTED")
            return any(bool(self.value(part, scope)) for part in node.values)
        if isinstance(node, ast.UnaryOp):
            require(isinstance(node.op, ast.Not), "COMPACT_UNARY_UNSUPPORTED")
            return not self.value(node.operand, scope)
        if isinstance(node, ast.Compare):
            left = self.value(node.left, scope)
            for operator, part in zip(node.ops, node.comparators):
                right = self.value(part, scope)
                if isinstance(operator, ast.Is): ok = left is right
                elif isinstance(operator, ast.IsNot): ok = left is not right
                elif isinstance(operator, ast.Eq): ok = left == right
                elif isinstance(operator, ast.NotEq): ok = left != right
                elif isinstance(operator, ast.In): ok = left in right
                elif isinstance(operator, ast.NotIn): ok = left not in right
                else: raise ValueError("COMPACT_COMPARISON_UNSUPPORTED")
                if not ok: return False
                left = right
            return True
        require(isinstance(node, ast.Call) and all(part.arg is not None for part in node.keywords),
                "COMPACT_EXPRESSION_UNSUPPORTED")
        args = [self.value(part, scope) for part in node.args]
        kwargs = {part.arg: self.value(part.value, scope) for part in node.keywords}
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in PURE_FUNCTIONS: return self.call(name, *args, **kwargs)
            native = {"_json": compact_json, "_reference": compact_reference, "_code": compact_code,
                      "_view": compact_view, "Path": PurePosixPath, "str": str, "type": type,
                      "set": set, "len": len, "ValueError": ValueError}
            require(name in native, "COMPACT_CALL_UNSUPPORTED:" + name)
            return native[name](*args, **kwargs)
        require(isinstance(node.func, ast.Attribute) and not kwargs, "COMPACT_CALL_UNSUPPORTED")
        if isinstance(node.func.value, ast.Name) and node.func.value.id == "shlex" and node.func.attr == "quote":
            require(len(args) == 1 and type(args[0]) is str, "COMPACT_QUOTE_NOT_STRING")
            return shlex.quote(args[0])
        if isinstance(node.func.value, ast.Name) and node.func.value.id == "hashlib" and node.func.attr == "sha256":
            require(len(args) == 1 and type(args[0]) is bytes, "COMPACT_HASH_NOT_BYTES")
            return hashlib.sha256(args[0])
        owner = self.value(node.func.value, scope)
        if node.func.attr == "encode":
            require(type(owner) is str and args in (["utf-8"], ["utf-8", "strict"]), "COMPACT_ENCODING_UNSUPPORTED")
            return owner.encode("utf-8", "strict")
        require(node.func.attr == "hexdigest" and not args and type(owner) is type(hashlib.sha256()),
                "COMPACT_ATTRIBUTE_CALL_UNSUPPORTED")
        return owner.hexdigest()

    def statements(self, nodes, scope):
        for node in nodes:
            if isinstance(node, ast.Expr):
                require(isinstance(node.value, ast.Constant) and type(node.value.value) is str,
                        "COMPACT_STATEMENT_EXPRESSION_UNSUPPORTED")
            elif isinstance(node, ast.Assign):
                require(len(node.targets) == 1 and isinstance(node.targets[0], ast.Name),
                        "COMPACT_ASSIGNMENT_UNSUPPORTED")
                scope[node.targets[0].id] = self.value(node.value, scope)
            elif isinstance(node, ast.AugAssign):
                require(isinstance(node.target, ast.Name) and isinstance(node.op, ast.Add),
                        "COMPACT_AUGMENT_UNSUPPORTED")
                old, new = scope[node.target.id], self.value(node.value, scope)
                require(type(old) is type(new) is str, "COMPACT_AUGMENT_NOT_STRING")
                scope[node.target.id] = old + new
            elif isinstance(node, ast.If):
                done, value = self.statements(node.body if self.value(node.test, scope) else node.orelse, scope)
                if done: return True, value
            elif isinstance(node, ast.Return):
                return True, self.value(node.value, scope)
            elif isinstance(node, ast.Raise):
                value = self.value(node.exc, scope)
                require(type(value) is ValueError and node.cause is None, "COMPACT_RAISE_UNSUPPORTED")
                raise value
            else:
                raise ValueError("COMPACT_STATEMENT_UNSUPPORTED:" + type(node).__name__)
        return False, None

    def call(self, name, *args, **kwargs):
        require(name in PURE_FUNCTIONS, "COMPACT_API_UNSUPPORTED")
        function = self.functions[name]
        params = function.args
        require(not params.posonlyargs and params.vararg is None and params.kwarg is None,
                "COMPACT_API_ARGUMENTS_UNSUPPORTED")
        positional = [arg.arg for arg in params.args]
        keyword = [arg.arg for arg in params.kwonlyargs]
        require(len(args) <= len(positional) and set(kwargs).issubset(set(positional + keyword)),
                "COMPACT_API_ARGUMENTS_INVALID")
        scope = dict(zip(positional, args))
        for key, value in kwargs.items():
            require(key not in scope, "COMPACT_API_DUPLICATE_ARGUMENT")
            scope[key] = value
        for key, default in zip(positional[-len(params.defaults):] if params.defaults else [], params.defaults):
            if key not in scope: scope[key] = self.value(default, {})
        for key, default in zip(keyword, params.kw_defaults):
            if key not in scope:
                require(default is not None, "COMPACT_API_ARGUMENT_MISSING")
                scope[key] = self.value(default, {})
        require(set(scope) == set(positional + keyword), "COMPACT_API_ARGUMENT_MISSING")
        done, value = self.statements(function.body, scope)
        require(done, "COMPACT_API_RETURN_MISSING")
        return value


def validate_compact(literals, sources):
    compact = literals["compact_protocol"]
    require(type(compact) is dict and set(compact) == {"format", "sources", "code", "source_schema"} and
            compact["format"] == COMPACT_SCHEMA and type(sources) is dict and set(sources) == COMPACT_ROLES and
            type(compact["sources"]) is dict and set(compact["sources"]) == COMPACT_ROLES,
            "COMPACT_MULTI_SOURCE_INTERFACE_NOT_CLOSED")
    for role, raw in sources.items():
        ref = compact["sources"][role]
        require(type(ref) is dict and set(ref) == {"path", "sha256"} and type(ref["path"]) is str and
                type(raw) is bytes and sha(raw) == ref["sha256"], "COMPACT_SOURCE_BYTES_NOT_AUTHENTICATED:" + role)
    engine = PureTemplateAST(sources["generator"])
    require(engine.schema() == compact["source_schema"], "COMPACT_SCHEMA_NOT_SOURCE_DERIVED")
    def unique_compact(items):
        result = {}
        for key, value in items:
            require(key not in result, "COMPACT_DESCRIPTOR_DUPLICATE_KEY")
            result[key] = value
        return result
    descriptor = json.loads(sources["descriptor"].decode("utf-8", "strict"), object_pairs_hook=unique_compact)
    require(type(descriptor) is dict and set(descriptor) == {"format", "api_revision", "source_files",
            "interpreters", "launcher", "session_policy"} and
            descriptor.get("format") == "verislop.carrier-runtime-registration/1" and
            descriptor.get("api_revision") == engine.constants["API_REVISION"], "COMPACT_DESCRIPTOR_VERSION_INVALID")
    require(type(descriptor["source_files"]) is dict and set(descriptor["source_files"]) == {"generator", "reader", "runtime"},
            "COMPACT_DESCRIPTOR_SOURCE_ROLES_INVALID")
    for role in ("generator", "reader", "runtime"):
        require(descriptor["source_files"][role] == compact["sources"][role], "COMPACT_DESCRIPTOR_SOURCE_DIFFERS")
        name = compact["sources"][role]["path"]
        path = PurePosixPath(name)
        require(not path.is_absolute() and str(path) == name and ".." not in path.parts and
                name.startswith("synthetic_dataset/tools/"), "COMPACT_SOURCE_PATH_INVALID")
    require(len({compact["sources"][role]["path"] for role in ("generator", "reader", "runtime")}) == 3,
            "COMPACT_SOURCE_PATH_REUSED")
    require(descriptor["session_policy"] == "own-carrier-parent/runtime020-own-sessions",
            "COMPACT_SESSION_POLICY_INVALID")
    require(descriptor["launcher"] == {"kind": "generator_literal", "name": "LAUNCHER_SOURCE",
            "sha256": sha(engine.constants["LAUNCHER_SOURCE"].encode("utf-8", "strict"))},
            "COMPACT_EMBEDDED_LAUNCHER_NOT_SOURCE_DERIVED")
    code = compact_code(compact["code"])
    deployed_roots = []
    for role in ("reader", "runtime"):
        require(code[role + "_sha256"] == compact["sources"][role]["sha256"] and
                code[role + "_path"].endswith("/" + compact["sources"][role]["path"]),
                "COMPACT_DEPLOYED_CODE_BINDING_DIFFERS")
        deployed_roots.append(code[role + "_path"][:-len(compact["sources"][role]["path"])])
    require(len(set(deployed_roots)) == 1, "COMPACT_DEPLOYED_SOURCE_ROOTS_DIFFER")
    require(sources["reader"].startswith(literals["constants"]["READER_SOURCE"].encode("utf-8", "strict")),
            "COMPACT_READER_IS_NOT_LEGACY_SOURCE_PREFIX")
    for name in ("CHECKPOINT_VALIDATOR_SOURCE", "OWN_SHA256_SOURCE"):
        require(sources["runtime"].count(literals["constants"][name].encode("utf-8", "strict")) == 1,
                "COMPACT_PURE_ALGORITHM_IS_NOT_BYTE_EXACT:" + name)
    require(type(descriptor["interpreters"]) is dict and set(descriptor["interpreters"]) == {"node", "python"},
            "COMPACT_INTERPRETER_ROLES_INVALID")
    for role in ("node", "python"):
        ref = descriptor["interpreters"][role]
        require(type(ref) is dict and set(ref) == {"path", "sha256"} and ref["path"] == code[role + "_path"] and
                re.fullmatch(r"sha256:[0-9a-f]{64}", ref["sha256"]) is not None,
                "COMPACT_INTERPRETER_IDENTITY_UNREGISTERED")
    return engine


def validate_literals(source, literals, sources=None):
    _validate_legacy_literals(source, literals)
    if "compact_protocol" in literals:
        validate_compact(literals, sources)
    else:
        require(sources in (None, {}), "LEGACY_PROTOCOL_HAS_UNDECLARED_SOURCES")
    return literals


def author_message(literals, reference, sources=None):
    if "compact_protocol" not in literals:
        require(sources in (None, {}), "LEGACY_PROTOCOL_HAS_UNDECLARED_SOURCES")
        return _legacy_author_message(literals, reference)
    engine = validate_compact(literals, sources)
    message = engine.call("runtime_agent_message", compact_reference(reference), compact_code(literals["compact_protocol"]["code"]))
    require(type(message) is str, "COMPACT_AUTHOR_MESSAGE_NOT_STRING")
    return message.encode("utf-8", "strict")
