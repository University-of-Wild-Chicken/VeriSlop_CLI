"""A small, fail-closed JSON Schema (Draft 2020-12) validator.

Only the keywords used by VeriSlop schemas are implemented. An unknown keyword in a schema is
an error rather than being silently ignored, so a schema change cannot quietly weaken
validation. Schema validation checks structure only; semantic validators are separate.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

ANNOTATION_KEYWORDS = {"$schema", "$id", "$defs", "$comment", "title", "description", "examples", "default"}
SUPPORTED_KEYWORDS = ANNOTATION_KEYWORDS | {
    "$ref", "type", "const", "enum", "properties", "additionalProperties", "required",
    "items", "minItems", "maxItems", "uniqueItems", "minLength", "maxLength", "pattern",
    "minimum", "maximum", "minProperties", "maxProperties", "allOf", "anyOf", "oneOf", "not",
    "if", "then", "else", "patternProperties", "propertyNames",
}


class SchemaError(Exception):
    """The schema itself is unsupported or malformed (a configuration problem)."""


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _is_type(value: Any, name: str) -> bool:
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    raise SchemaError(f"unknown type {name!r}")


def _json_equal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_json_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_json_equal(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


class Registry:
    """Holds schemas by `$id` and resolves `$ref` (absolute URN + JSON pointer fragment)."""

    def __init__(self) -> None:
        self._by_id: dict[str, dict] = {}
        self._patterns: dict[str, re.Pattern[str]] = {}
        self._validation_cache: ContextVar[dict | None] = ContextVar("jsonschema_validation_cache", default=None)

    def add(self, schema: dict) -> str:
        sid = schema.get("$id")
        if not isinstance(sid, str):
            raise SchemaError("schema without $id")
        self._check_keywords(schema, sid)
        self._by_id[sid] = schema
        return sid

    def _check_keywords(self, node: Any, where: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key not in SUPPORTED_KEYWORDS:
                    raise SchemaError(f"unsupported schema keyword {key!r} in {where}")
                if key in ("properties", "$defs", "patternProperties"):
                    for sub in value.values():
                        self._check_keywords(sub, where)
                elif key in ("allOf", "anyOf", "oneOf"):
                    for sub in value:
                        self._check_keywords(sub, where)
                elif key in ("items", "additionalProperties", "not", "if", "then", "else", "propertyNames"):
                    if isinstance(value, dict):
                        self._check_keywords(value, where)

    def resolve(self, ref: str, base: str) -> tuple[dict, str]:
        if ref.startswith("#"):
            uri, frag = base, ref[1:]
        elif "#" in ref:
            uri, frag = ref.split("#", 1)
        else:
            uri, frag = ref, ""
        root = self._by_id.get(uri)
        if root is None:
            raise SchemaError(f"unresolvable $ref {ref!r}")
        node: Any = root
        if frag:
            if not frag.startswith("/"):
                raise SchemaError(f"unsupported $ref fragment {ref!r}")
            for part in frag[1:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                if not isinstance(node, dict) or part not in node:
                    raise SchemaError(f"unresolvable $ref {ref!r}")
                node = node[part]
        if not isinstance(node, dict):
            raise SchemaError(f"$ref {ref!r} does not resolve to a schema object")
        return node, uri

    def pattern(self, pat: str) -> re.Pattern[str]:
        compiled = self._patterns.get(pat)
        if compiled is None:
            compiled = re.compile(pat)
            self._patterns[pat] = compiled
        return compiled

    def validate(self, instance: Any, schema_id: str) -> list[ValidationIssue]:
        schema = self._by_id.get(schema_id)
        if schema is None:
            raise SchemaError(f"unknown schema {schema_id!r}")
        issues: list[ValidationIssue] = []
        token = self._validation_cache.set({})
        try:
            self._validate(instance, schema, schema_id, "$", issues)
        finally:
            self._validation_cache.reset(token)
        return issues

    # -- core -------------------------------------------------------------------------------

    def _validate(self, inst: Any, schema: Any, base: str, path: str, out: list[ValidationIssue]) -> None:
        cache = self._validation_cache.get()
        cache_key = (id(inst), id(schema), base, path)
        if cache is not None:
            cached = cache.get(cache_key)
            if cached is not None:
                out.extend(cached[2])
                return
        start = len(out)
        if schema is True:
            if cache is not None:
                cache[cache_key] = (inst, schema, ())
            return
        if schema is False:
            out.append(ValidationIssue(path, "no value is permitted here"))
            if cache is not None:
                cache[cache_key] = (inst, schema, tuple(out[start:]))
            return
        if not isinstance(schema, dict):
            raise SchemaError(f"invalid schema node at {path}")
        if "$id" in schema and isinstance(schema["$id"], str):
            base = schema["$id"]

        if "$ref" in schema:
            target, target_base = self.resolve(schema["$ref"], base)
            self._validate(inst, target, target_base, path, out)

        if "type" in schema:
            types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(_is_type(inst, t) for t in types):
                out.append(ValidationIssue(path, f"expected type {'/'.join(types)}"))
                if cache is not None:
                    cache[cache_key] = (inst, schema, tuple(out[start:]))
                return
        if "const" in schema and not _json_equal(inst, schema["const"]):
            out.append(ValidationIssue(path, f"expected constant {schema['const']!r}"))
        if "enum" in schema and not any(_json_equal(inst, e) for e in schema["enum"]):
            out.append(ValidationIssue(path, f"value {inst!r} not in {schema['enum']!r}"))

        if isinstance(inst, str):
            if "minLength" in schema and len(inst) < schema["minLength"]:
                out.append(ValidationIssue(path, f"string shorter than {schema['minLength']}"))
            if "maxLength" in schema and len(inst) > schema["maxLength"]:
                out.append(ValidationIssue(path, f"string longer than {schema['maxLength']}"))
            if "pattern" in schema and not self.pattern(schema["pattern"]).search(inst):
                out.append(ValidationIssue(path, f"string does not match {schema['pattern']!r}"))

        if _is_type(inst, "number"):
            if "minimum" in schema and inst < schema["minimum"]:
                out.append(ValidationIssue(path, f"value below minimum {schema['minimum']}"))
            if "maximum" in schema and inst > schema["maximum"]:
                out.append(ValidationIssue(path, f"value above maximum {schema['maximum']}"))

        if isinstance(inst, list):
            if "minItems" in schema and len(inst) < schema["minItems"]:
                out.append(ValidationIssue(path, f"fewer than {schema['minItems']} items"))
            if "maxItems" in schema and len(inst) > schema["maxItems"]:
                out.append(ValidationIssue(path, f"more than {schema['maxItems']} items"))
            if schema.get("uniqueItems"):
                # One duplicate establishes failure. Enumerating every equal pair
                # can allocate quadratic diagnostics for hostile input arrays.
                duplicate = next(((i, j) for i in range(len(inst))
                                  for j in range(i + 1, len(inst))
                                  if _json_equal(inst[i], inst[j])), None)
                if duplicate is not None:
                    i, j = duplicate
                    out.append(ValidationIssue(path, f"items {i} and {j} are not unique"))
            if "items" in schema:
                for i, item in enumerate(inst):
                    self._validate(item, schema["items"], base, f"{path}[{i}]", out)

        if isinstance(inst, dict):
            if "minProperties" in schema and len(inst) < schema["minProperties"]:
                out.append(ValidationIssue(path, f"fewer than {schema['minProperties']} properties"))
            if "maxProperties" in schema and len(inst) > schema["maxProperties"]:
                out.append(ValidationIssue(path, f"more than {schema['maxProperties']} properties"))
            for req in schema.get("required", []):
                if req not in inst:
                    out.append(ValidationIssue(path, f"missing required property {req!r}"))
            props = schema.get("properties", {})
            pattern_props = schema.get("patternProperties", {})
            for key, value in inst.items():
                matched = False
                if key in props:
                    matched = True
                    self._validate(value, props[key], base, f"{path}.{key}", out)
                for pat, sub in pattern_props.items():
                    if self.pattern(pat).search(key):
                        matched = True
                        self._validate(value, sub, base, f"{path}.{key}", out)
                if not matched and "additionalProperties" in schema:
                    ap = schema["additionalProperties"]
                    if ap is False:
                        out.append(ValidationIssue(path, f"unexpected property {key!r}"))
                    elif isinstance(ap, dict):
                        self._validate(value, ap, base, f"{path}.{key}", out)
                if "propertyNames" in schema:
                    self._validate(key, schema["propertyNames"], base, f"{path}.<key {key}>", out)

        for sub in schema.get("allOf", []):
            self._validate(inst, sub, base, path, out)
        if "anyOf" in schema:
            if not any(not self._collect(inst, sub, base, path) for sub in schema["anyOf"]):
                out.append(ValidationIssue(path, "does not match any permitted alternative"))
        if "oneOf" in schema:
            matches = sum(1 for sub in schema["oneOf"] if not self._collect(inst, sub, base, path))
            if matches != 1:
                out.append(ValidationIssue(path, f"matches {matches} alternatives; exactly one required"))
        if "not" in schema and not self._collect(inst, schema["not"], base, path):
            out.append(ValidationIssue(path, "matches a forbidden schema"))
        if "if" in schema:
            if not self._collect(inst, schema["if"], base, path):
                if "then" in schema:
                    self._validate(inst, schema["then"], base, path, out)
            elif "else" in schema:
                self._validate(inst, schema["else"], base, path, out)
        # Keep identities alive and cache only completed checks, without adding
        # a recursive frame. Every oneOf alternative and reached error remains.
        if cache is not None:
            cache[cache_key] = (inst, schema, tuple(out[start:]))

    def _collect(self, inst: Any, schema: Any, base: str, path: str) -> list[ValidationIssue]:
        sub: list[ValidationIssue] = []
        self._validate(inst, schema, base, path, sub)
        return sub
