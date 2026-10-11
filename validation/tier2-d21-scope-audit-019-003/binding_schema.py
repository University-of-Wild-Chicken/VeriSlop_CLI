"""Pure stdlib validation for the explicitly registered finite schema subset.

This module reads no files, imports no project code, and grants no authority.
Unsupported schema keywords/types/refs fail before instance validation. Local
nonrecursive references, typed JSON equality, all declared object/array/string
constraints, and strict finite duplicate-free UTF-8 JSON are supported.
Registration integer fields/consts require integer tokens exactly; decimal and
exponent tokens are preserved as Decimal and do not coerce, including1.0.
Binary float values are never admitted as schema/instance inputs.
"""
import json
from decimal import Decimal, InvalidOperation
import re


class SchemaError(ValueError):
    pass


ANNOTATIONS = {"$schema", "title", "description"}
KEYWORDS = ANNOTATIONS | {"$defs", "$ref", "type", "const", "enum", "properties",
                          "required", "additionalProperties", "items", "minItems", "pattern"}
TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}


def require(condition, message):
    if not condition:
        raise SchemaError(message)


def strict_json(raw):
    require(type(raw) is bytes and not raw.startswith(b"\xef\xbb\xbf"), "JSON_BOM_OR_NON_BYTES")
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "JSON_DUPLICATE_KEY:" + key)
            value[key] = item
        return value
    def number(token):
        try:
            value = Decimal(token)
        except InvalidOperation as error:
            raise SchemaError("UNREPRESENTABLE_DECIMAL_LITERAL") from error
        require(value.is_finite(), "JSON_NONFINITE_NUMBER")
        return value
    def nonfinite(token):
        raise SchemaError("JSON_NONFINITE_CONSTANT:" + token)
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs,
                           parse_float=number, parse_constant=nonfinite)
        validate_json_domain(value)
        return value
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SchemaError("MALFORMED_UTF8_JSON:" + str(error)) from error


def json_equal(left, right):
    if type(left) is float or type(right) is float:
        return False
    if type(left) in (int, Decimal) or type(right) in (int, Decimal):
        return type(left) is type(right) and finite_number(left) and finite_number(right) and left == right
    if type(left) is not type(right):
        return False
    if type(left) is list:
        return len(left) == len(right) and all(json_equal(a, b) for a, b in zip(left, right))
    if type(left) is dict:
        return set(left) == set(right) and all(json_equal(left[k], right[k]) for k in left)
    return left == right


def finite_number(value):
    return type(value) is int or (type(value) is Decimal and value.is_finite())


def validate_json_domain(value):
    """Lexical registration domain: exact integer tokens and exact decimals.

    Decimal/exponent tokens never coerce to integer constants, even1.0/1e0.
    No binary float or nonfinite value is an admitted schema/instance value.
    """
    if type(value) in (str, bool, int) or value is None:
        return
    if type(value) is Decimal:
        require(value.is_finite(), "JSON_NONFINITE_DECIMAL")
        return
    if type(value) is list:
        for child in value:
            validate_json_domain(child)
        return
    if type(value) is dict:
        require(all(type(key) is str for key in value), "NON_JSON_OBJECT_KEY")
        for child in value.values():
            validate_json_domain(child)
        return
    raise SchemaError("UNSUPPORTED_JSON_VALUE_TYPE:" + type(value).__name__)


def resolve(root, reference):
    require(type(reference) is str and reference.startswith("#/$defs/"), "UNSUPPORTED_SCHEMA_REF")
    value = root
    for token in reference[2:].split("/"):
        require(re.search(r"~(?:[^01]|$)", token) is None, "MALFORMED_SCHEMA_REF")
        key = token.replace("~1", "/").replace("~0", "~")
        require(type(value) is dict and key in value, "UNRESOLVED_SCHEMA_REF:" + reference)
        value = value[key]
    require(type(value) is dict, "NON_SCHEMA_REF_TARGET")
    return value


def check_schema(schema):
    validate_json_domain(schema)
    require(type(schema) is dict, "SCHEMA_NOT_OBJECT")
    def visit(node, references):
        require(type(node) is dict and set(node) <= KEYWORDS, "UNSUPPORTED_SCHEMA_KEYWORD")
        for name in ANNOTATIONS:
            if name in node:
                require(type(node[name]) is str, "SCHEMA_ANNOTATION_NOT_TEXT")
        if "$schema" in node:
            require(node["$schema"] == "https://json-schema.org/draft/2020-12/schema", "UNSUPPORTED_SCHEMA_DIALECT")
        if "$ref" in node:
            reference = node["$ref"]
            require(reference not in references, "CYCLIC_SCHEMA_REF")
            visit(resolve(schema, reference), references + (reference,))
        if "type" in node:
            require(type(node["type"]) is str and node["type"] in TYPES, "UNSUPPORTED_SCHEMA_TYPE")
        if "enum" in node:
            values = node["enum"]
            require(type(values) is list and len(values) > 0 and
                    all(not json_equal(v, previous) for i, v in enumerate(values) for previous in values[:i]),
                    "SCHEMA_ENUM_INVALID")
        if "required" in node:
            values = node["required"]
            require(type(values) is list and all(type(v) is str for v in values) and
                    len(values) == len(set(values)), "SCHEMA_REQUIRED_INVALID")
        for name in ("properties", "$defs"):
            if name in node:
                require(type(node[name]) is dict and all(type(k) is str for k in node[name]), "SCHEMA_MAP_INVALID")
                for child in node[name].values():
                    visit(child, references)
        if "additionalProperties" in node:
            extra = node["additionalProperties"]
            require(type(extra) in (bool, dict), "SCHEMA_ADDITIONAL_PROPERTIES_INVALID")
            if type(extra) is dict:
                visit(extra, references)
        if "items" in node:
            visit(node["items"], references)
        if "minItems" in node:
            require(type(node["minItems"]) is int and node["minItems"] >= 0, "SCHEMA_MIN_ITEMS_INVALID")
        if "pattern" in node:
            require(type(node["pattern"]) is str, "SCHEMA_PATTERN_NOT_TEXT")
            try:
                re.compile(node["pattern"])
            except re.error as error:
                raise SchemaError("SCHEMA_PATTERN_INVALID") from error
    visit(schema, ())


def validate_closed_schema(schema, value):
    check_schema(schema)
    validate_json_domain(value)
    def visit(node, item, location):
        if "$ref" in node:
            visit(resolve(schema, node["$ref"]), item, location)
        kind = node.get("type")
        if kind is not None:
            matches = {"object": type(item) is dict, "array": type(item) is list,
                       "string": type(item) is str, "boolean": type(item) is bool,
                       "null": item is None,
                       "number": finite_number(item),
                       "integer": type(item) is int}
            require(matches[kind], "SCHEMA_TYPE:" + location)
        if "const" in node:
            require(json_equal(item, node["const"]), "SCHEMA_CONST:" + location)
        if "enum" in node:
            require(any(json_equal(item, v) for v in node["enum"]), "SCHEMA_ENUM:" + location)
        if type(item) is dict:
            require(all(type(k) is str for k in item), "NON_JSON_OBJECT_KEY:" + location)
            required = node.get("required", [])
            require(set(required) <= set(item), "SCHEMA_REQUIRED:" + location)
            properties = node.get("properties", {})
            for key, child in item.items():
                child_location = location + "/" + key.replace("~", "~0").replace("/", "~1")
                if key in properties:
                    visit(properties[key], child, child_location)
                else:
                    extra = node.get("additionalProperties", True)
                    require(extra is not False, "SCHEMA_ADDITIONAL_PROPERTY:" + child_location)
                    if type(extra) is dict:
                        visit(extra, child, child_location)
        if type(item) is list:
            require(len(item) >= node.get("minItems", 0), "SCHEMA_MIN_ITEMS:" + location)
            if "items" in node:
                for index, child in enumerate(item):
                    visit(node["items"], child, location + "/" + str(index))
        if type(item) is str and "pattern" in node:
            require(re.search(node["pattern"], item) is not None, "SCHEMA_PATTERN:" + location)
    visit(schema, value, "")
    return True


def exact_driver_reference(reference, expected):
    require(json_equal(reference, expected), "NATIVE_DRIVER_REFERENCE_MISMATCH")
    return True


def exact_activation_binding(binding, expected):
    for key, value in expected.items():
        require(key in binding and json_equal(binding[key], value), "ACTIVATION_BINDING_MISMATCH:" + key)
    return True
