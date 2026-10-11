"""Registered independent string reconstruction; no producer import/execution.

Only frozen literal/AST schemas are interpreted. This support module performs
no tool, file, viewer, model, compiler, task or qualification calls itself.
"""
import ast
import hashlib
import json

CONSTANT_NAMES = ("READER_SOURCE", "_EXEC_PRAGMA", "_VIEW_GUARD", "_NEXT_EMIT",
                  "CHECKPOINT_VALIDATOR_SOURCE", "OWN_SHA256_SOURCE")
FUNCTION_NAMES = ("inline_source", "inline_command", "inline_prefix", "own_session_key", "_closed_view",
                  "initial_session_template", "next_session_template", "legacy_agent_message",
                  "own_checkpoint_key", "own_pending_key", "own_hash_key", "_author_observer",
                  "author_initial_session_template", "author_next_session_template", "_checkpoint_bindings",
                  "confirm_session_template", "hash_session_template", "agent_message")


def require(ok, code):
    if not ok:
        raise ValueError(code)


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def flatten(node):
    return flatten(node.left) + flatten(node.right) if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add) else [node]


def return_value(function):
    values = [node.value for node in function.body if isinstance(node, ast.Return)]
    require(len(values) == 1, "AUTHOR_SOURCE_RETURN_NOT_SINGLE")
    return values[0]


def literal_assignment(function, name):
    found = [node.value for node in function.body if isinstance(node, ast.Assign)
             and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name]
    require(len(found) == 1, "AUTHOR_SOURCE_LITERAL_ASSIGNMENT_NOT_SINGLE:" + name)
    return ast.literal_eval(found[0])


def fragments(node, symbolic):
    """Closed string-concatenation schema, never eval or arbitrary AST execution."""
    output = []
    for part in flatten(node):
        if isinstance(part, ast.Constant) and type(part.value) is str:
            output.append({"literal": part.value})
        else:
            shape = ast.dump(part, include_attributes=False)
            require(shape in symbolic, "AUTHOR_UNSUPPORTED_TEMPLATE_EXPRESSION:" + shape)
            output.append({"symbol": symbolic[shape]})
    return output


def expression(source):
    return ast.dump(ast.parse(source, mode="eval").body, include_attributes=False)


def extract_schema(source):
    text = source.decode("utf-8", "strict")
    tree = ast.parse(text)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    require(len(functions) == sum(isinstance(node, ast.FunctionDef) for node in tree.body), "AUTHOR_DUPLICATE_SOURCE_FUNCTION")
    require(set(FUNCTION_NAMES).issubset(functions), "AUTHOR_SOURCE_FUNCTION_ABSENT")
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in CONSTANT_NAMES:
                require(name not in constants, "AUTHOR_DUPLICATE_SOURCE_CONSTANT")
                constants[name] = ast.literal_eval(node.value)
    require(set(constants) == set(CONSTANT_NAMES) and all(type(value) is str for value in constants.values()), "AUTHOR_SOURCE_CONSTANT_ABSENT_OR_NOT_STRING")
    hashes = {name: sha(ast.dump(functions[name], include_attributes=False).encode()) for name in FUNCTION_NAMES}
    legacy = flatten(return_value(functions["legacy_agent_message"]))
    require(isinstance(legacy[0], ast.Constant) and type(legacy[0].value) is str, "AUTHOR_LEGACY_PREFIX_NOT_LITERAL")
    legacy_parts = fragments(return_value(functions["legacy_agent_message"]), {
        expression("json.dumps(reference, sort_keys=True, ensure_ascii=True)"): "reference_json",
        expression("initial_session_template(reference)"): "legacy_first",
        expression("next_session_template(reference)"): "legacy_next"})
    own_keys = {}
    for name in ("own_checkpoint_key", "own_pending_key", "own_hash_key"):
        parts = flatten(return_value(functions[name]))
        require(isinstance(parts[0], ast.Constant) and type(parts[0].value) is str, "AUTHOR_OWN_KEY_PREFIX_NOT_LITERAL")
        own_keys[name] = parts[0].value
    observer = functions["_author_observer"]
    observer_old = literal_assignment(observer, "old")
    observer_new = literal_assignment(observer, "new")
    binding_values = [node.value for node in observer.body if isinstance(node, ast.Assign)
                      and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "bindings"]
    require(len(binding_values) == 1, "AUTHOR_OBSERVER_BINDINGS_NOT_SINGLE")
    observer_bindings = fragments(binding_values[0], {
        expression("json.dumps(reference, sort_keys=True, ensure_ascii=True)"): "reference_json",
        expression("json.dumps(own_pending_key(reference), ensure_ascii=True)"): "pending_key_json"})
    checkpoint_bindings = fragments(return_value(functions["_checkpoint_bindings"]), {
        expression("json.dumps(reference, sort_keys=True, ensure_ascii=True)"): "reference_json",
        expression("json.dumps(own_checkpoint_key(reference), ensure_ascii=True)"): "checkpoint_key_json"})
    symbolic = {expression("_EXEC_PRAGMA"): "pragma", expression("_checkpoint_bindings(reference)"): "checkpoint_bindings",
                expression("CHECKPOINT_VALIDATOR_SOURCE"): "validator", expression("OWN_SHA256_SOURCE"): "sha256",
                expression("json.dumps(own_pending_key(reference), ensure_ascii=True)"): "pending_key_json",
                expression("json.dumps(confirmation, sort_keys=True, ensure_ascii=True)"): "confirmation_json",
                expression("json.dumps(own_hash_key(reference), ensure_ascii=True)"): "hash_key_json"}
    confirm_parts = fragments(return_value(functions["confirm_session_template"]), symbolic)
    hash_parts = fragments(return_value(functions["hash_session_template"]), symbolic)
    message = functions["agent_message"]
    require(len(message.body) == 7 and isinstance(message.body[0], ast.Assign)
            and expression("legacy_agent_message(reference)") == ast.dump(message.body[0].value, include_attributes=False), "AUTHOR_MESSAGE_INITIALIZATION_SHAPE")
    transforms = []
    allowed_template_calls = {expression("initial_session_template(reference)"): "legacy_first",
                              expression("author_initial_session_template(reference)"): "author_first",
                              expression("next_session_template(reference)"): "legacy_next",
                              expression("author_next_session_template(reference)"): "author_next",
                              expression(r'instruction + "\nCARRIER:\n"'): "instruction_with_carrier"}
    for index in (1, 2, 3, 5):
        node = message.body[index]
        require(isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "message" and isinstance(node.value, ast.Call)
                and expression("message.replace") == ast.dump(node.value.func, include_attributes=False)
                and not node.value.keywords and len(node.value.args) == 3
                and type(ast.literal_eval(node.value.args[2])) is int and ast.literal_eval(node.value.args[2]) == 1,
                "AUTHOR_MESSAGE_TRANSFORM_SHAPE")
        sides = []
        for side in node.value.args[:2]:
            if isinstance(side, ast.Constant) and type(side.value) is str:
                sides.append({"literal": side.value})
            else:
                shape = ast.dump(side, include_attributes=False)
                require(shape in allowed_template_calls, "AUTHOR_MESSAGE_TRANSFORM_UNSUPPORTED")
                sides.append({"symbol": allowed_template_calls[shape]})
        transforms.append(sides)
    require(isinstance(message.body[4], ast.Assign) and len(message.body[4].targets) == 1
            and isinstance(message.body[4].targets[0], ast.Name) and message.body[4].targets[0].id == "instruction",
            "AUTHOR_MESSAGE_INSTRUCTION_SHAPE")
    instruction = ast.literal_eval(message.body[4].value)
    require(type(instruction) is str, "AUTHOR_MESSAGE_INSTRUCTION_NOT_LITERAL")
    append_parts = fragments(return_value(message), {
        expression("message"): "message", expression("confirm_session_template(reference)"): "confirm",
        expression("hash_session_template(reference)"): "hash"})
    require("observable-carrier-collector-result" not in observer_new and "store(PENDING_KEY" in observer_new,
            "AUTHOR_OBSERVER_IS_NOT_OWN_PENDING")
    return {"constants": constants, "function_ast_hashes": hashes, "agent_message_prefix": legacy[0].value,
            "message_suffix_parts": [part.value for part in legacy[2:] if isinstance(part, ast.Constant)],
            "author_protocol": {"format": "verislop.author-protocol-literal-schema/1", "own_keys": own_keys,
                "legacy_message": legacy_parts, "observer_old": observer_old, "observer_new": observer_new,
                "observer_bindings": observer_bindings, "checkpoint_bindings": checkpoint_bindings,
                "confirm": confirm_parts, "hash": hash_parts, "message_transforms": transforms,
                "instruction": instruction, "message_append": append_parts}}


def validate_literals(source, literals):
    require(type(literals) is dict and literals["source"]["sha256"] == sha(source), "AUTHOR_SOURCE_HASH_MISMATCH")
    extracted = extract_schema(source)
    for name in ("constants", "function_ast_hashes", "agent_message_prefix", "message_suffix_parts"):
        require(literals[name] == extracted[name], "AUTHOR_LITERAL_OR_AST_MISMATCH:" + name)
    profile = dict(literals["author_protocol"])
    reference = profile.pop("reconstruction_source")
    require(type(reference) is dict and set(reference) == {"path", "sha256"}
            and type(reference["path"]) is str and type(reference["sha256"]) is str, "AUTHOR_RECONSTRUCTION_REFERENCE_SHAPE")
    require(profile == extracted["author_protocol"], "AUTHOR_PROTOCOL_SCHEMA_NOT_SOURCE_DERIVED")
    return literals


def emit(parts, values):
    result = []
    for part in parts:
        require(type(part) is dict and set(part) in ({"literal"}, {"symbol"}), "AUTHOR_TEMPLATE_FRAGMENT_SHAPE")
        value = part["literal"] if "literal" in part else values[part["symbol"]]
        require(type(value) is str, "AUTHOR_TEMPLATE_FRAGMENT_NOT_STRING")
        result.append(value)
    return "".join(result)


def own_key(prefix, reference):
    return prefix + json.dumps({"path": reference["path"], "sha256": reference["sha256"]}, sort_keys=True,
                              ensure_ascii=True, separators=(",", ":"))


def closed_view(view):
    require(type(view) is dict and view.get("operation") in ("inventory", "field"), "AUTHOR_VIEW_NOT_CLOSED")
    keys = {"operation", "output_cap_bytes", "metadata_reserve_bytes"}
    if view["operation"] == "field":
        keys |= {"selector", "start_char"}
    require(set(view) == keys and type(view["output_cap_bytes"]) is int and 256 <= view["output_cap_bytes"] <= 8192
            and type(view["metadata_reserve_bytes"]) is int and 128 <= view["metadata_reserve_bytes"] < view["output_cap_bytes"],
            "AUTHOR_VIEW_FIELDS_OR_BOUNDS")
    if view["operation"] == "field":
        require(view["selector"] in ("/system", "/user") and type(view["start_char"]) is int
                and 0 <= view["start_char"] <= 2**53 - 1, "AUTHOR_VIEW_SELECTOR_OR_CURSOR")
    return view


def legacy_recipe(literals, reference, view=None, first=False):
    c = literals["constants"]
    if view is None:
        view = {"operation": "field", "selector": "/system", "start_char": 0, "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048}
    closed_view(view)
    key = own_key("verislop.exact-carrier-session/0.1:", reference)
    if first:
        view = {"operation": "inventory", "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048}
        prefix = "python -I -B - <<'VERISLOP_EXACT_CARRIER_VIEW'\n" + c["READER_SOURCE"] + "\nREFERENCE = json.loads(" + repr(json.dumps(reference, sort_keys=True, ensure_ascii=True)) + ")\n"
        return (c["_EXEC_PRAGMA"] + "const OWN_KEY = " + json.dumps(key, ensure_ascii=True) + ";\nconst PREFIX = "
                + json.dumps(prefix, ensure_ascii=True) + ";\nstore(OWN_KEY, PREFIX);\nconst VIEW = "
                + json.dumps(view, sort_keys=True, ensure_ascii=True) + ";\n" + c["_VIEW_GUARD"])
    return (c["_EXEC_PRAGMA"] + "const PREFIX = load(" + json.dumps(key, ensure_ascii=True) + ");\n"
            + 'if (typeof PREFIX !== "string") { throw new Error("OWN_CARRIER_PREFIX_ABSENT"); }\n'
            + "const VIEW = " + json.dumps(view, sort_keys=True, ensure_ascii=True) + ";\n" + c["_NEXT_EMIT"])


def recipes(literals, reference, confirmation=None, view=None):
    profile, c = literals["author_protocol"], literals["constants"]
    require(type(reference) is dict and set(reference) == {"path", "sha256", "request_sha256"}
            and all(type(value) is str for value in reference.values()), "AUTHOR_REFERENCE_NOT_EXACT")
    if confirmation is None:
        confirmation = {"chunk_id": "COPY_ACTUAL_CHUNK_ID", "outer_output_intact": True}
    require(type(confirmation) is dict and set(confirmation) == {"chunk_id", "outer_output_intact"}
            and type(confirmation["chunk_id"]) is str and confirmation["chunk_id"]
            and type(confirmation["outer_output_intact"]) is bool, "AUTHOR_CONFIRMATION_NOT_CLOSED")
    values = {"reference_json": json.dumps(reference, sort_keys=True, ensure_ascii=True), "pragma": c["_EXEC_PRAGMA"],
              "validator": c["CHECKPOINT_VALIDATOR_SOURCE"], "sha256": c["OWN_SHA256_SOURCE"],
              "confirmation_json": json.dumps(confirmation, sort_keys=True, ensure_ascii=True)}
    for function, symbol in (("own_pending_key", "pending_key_json"), ("own_checkpoint_key", "checkpoint_key_json"),
                             ("own_hash_key", "hash_key_json")):
        values[symbol] = json.dumps(own_key(profile["own_keys"][function], reference), ensure_ascii=True)
    values["checkpoint_bindings"] = emit(profile["checkpoint_bindings"], values)
    values["legacy_first"] = legacy_recipe(literals, reference, first=True)
    values["legacy_next"] = legacy_recipe(literals, reference, view=view)
    for before, after in (("legacy_first", "author_first"), ("legacy_next", "author_next")):
        lines = values[before].split("\n")
        require(lines.count(profile["observer_old"]) == 1, "AUTHOR_SINGLE_FORWARDING_STATEMENT_REQUIRED")
        replaced = "\n".join(profile["observer_new"] if line == profile["observer_old"] else line for line in lines)
        require(replaced.startswith(c["_EXEC_PRAGMA"]), "AUTHOR_PRAGMA_CHANGED")
        values[after] = c["_EXEC_PRAGMA"] + emit(profile["observer_bindings"], values) + replaced[len(c["_EXEC_PRAGMA"]):]
    values["confirm"] = emit(profile["confirm"], values)
    values["hash"] = emit(profile["hash"], values)
    return {name: values[name] for name in ("legacy_first", "legacy_next", "author_first", "author_next", "confirm", "hash")}


def author_message(literals, reference):
    values = recipes(literals, reference)
    values["reference_json"] = json.dumps(reference, sort_keys=True, ensure_ascii=True)
    profile = literals["author_protocol"]
    values["message"] = emit(profile["legacy_message"], values)
    values["instruction_with_carrier"] = profile["instruction"] + "\nCARRIER:\n"
    for sides in profile["message_transforms"]:
        require(type(sides) is list and len(sides) == 2, "AUTHOR_MESSAGE_TRANSFORM_NOT_CLOSED")
        values["message"] = values["message"].replace(emit([sides[0]], values), emit([sides[1]], values), 1)
    message = emit(profile["message_append"], values)
    require("observable-carrier-collector-result" not in profile["observer_new"]
            and "store(PENDING_KEY" in profile["observer_new"], "AUTHOR_MESSAGE_CONTAINS_COLLECTOR_OBSERVER")
    require(values["author_first"] in message and values["author_next"] in message
            and values["confirm"] in message and values["hash"] in message, "AUTHOR_RECIPE_BYTES_NOT_COMPLETE")
    return message.encode("utf-8", "strict")


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
