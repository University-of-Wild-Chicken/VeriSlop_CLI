"""Exact recursive-schema behavior and bounded traversal independent of task inputs.

BaselineRegistry retains the previous core method verbatim for differential checks.
Its source hash is sha256:d912a0488a2570bd254aa5844eb60630d5c19727fe8b5d1d51270a0f2b60511e.
Timing is deliberately not an assertion; operation counts prove the cost bound.
"""
from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock
import unittest

from verislop import canonical
from verislop.jsonschema_lite import Registry, SchemaError, ValidationIssue, _is_type, _json_equal

SID = "urn:verislop:schema:vscore-source:0.3"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas/vscore-source-v3.schema.json"


class BaselineRegistry(Registry):
    def _validate(self, inst: Any, schema: Any, base: str, path: str, out: list[ValidationIssue]) -> None:
        if schema is True:
            return
        if schema is False:
            out.append(ValidationIssue(path, "no value is permitted here"))
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



class CountedRegistry(Registry):
    def validate(self, instance, schema_id):
        self.calls = 0
        return super().validate(instance, schema_id)

    def _validate(self, inst, schema, base, path, out):
        self.calls += 1
        return super()._validate(inst, schema, base, path, out)


class CountedBaseline(BaselineRegistry):
    def validate(self, instance, schema_id):
        self.calls = 0
        return super().validate(instance, schema_id)

    def _validate(self, inst, schema, base, path, out):
        self.calls += 1
        return super()._validate(inst, schema, base, path, out)


def source(depth):
    expr = {"tag": "var", "index": 0}
    for _ in range(depth):
        expr = {"tag": "list_map", "value": expr, "body": {
            "tag": "add", "left": {"tag": "var", "index": 0},
            "right": {"tag": "int", "value": "-7"}}}
    return {"declarations": [], "entries": [{"id": "map_chain", "body": expr,
        "params": [{"list": "int"}], "result": {"list": "int"}}], "helpers": [],
        "language": "vscore/0.3", "profile": "data-pipeline/0.3"}


def registered(kind=Registry, schema=None):
    reg = kind()
    reg.add(schema or canonical.load_file(SCHEMA_PATH))
    return reg


class RecursiveSchemaCostTests(unittest.TestCase):
    def equivalent(self, schema, inputs, extra=()):
        old, new = registered(BaselineRegistry, schema), registered(Registry, schema)
        for referenced in extra:
            old.add(referenced)
            new.add(referenced)
        for value in inputs:
            with self.subTest(value=value):
                self.assertEqual(old.validate(value, schema["$id"]), new.validate(value, schema["$id"]))

    def test_nested_int_list_maps_have_linear_calls_with_exact_reference_output(self):
        old, new = registered(CountedBaseline), registered(CountedRegistry)
        counts = []
        for depth in range(3):
            value = source(depth)
            self.assertEqual(old.validate(value, SID), new.validate(value, SID))
            counts.append((old.calls, new.calls))
        self.assertEqual([195, 37654, 711916], [row[0] for row in counts])
        self.assertEqual([195, 804, 1413], [row[1] for row in counts])
        self.assertGreater(counts[-1][0], 400 * counts[-1][1])
        self.assertEqual([], new.validate(source(8), SID))
        self.assertLess(new.calls, 6000)

    def test_recursive_invalid_tags_operands_fields_and_literals_match_reference(self):
        values = [source(2)]
        for change in (lambda e: e.update(tag="unknown"), lambda e: e.pop("tag"),
                       lambda e: e.pop("body"), lambda e: e.update(unexpected=7),
                       lambda e: e.update(body=True),
                       lambda e: e["body"]["right"].update(value="-0"),
                       lambda e: e["body"]["left"].update(index=True)):
            value = source(2)
            change(value["entries"][0]["body"])
            values.append(value)
        self.equivalent(canonical.load_file(SCHEMA_PATH), values)

    def test_overlapping_oneof_keeps_exact_match_count_and_boolean_distinction(self):
        schema = {"$id": "urn:test:overlap", "oneOf": [{"type": "integer"}, {"type": "number"}]}
        self.equivalent(schema, [0, True, "text", {}, []])
        reg = registered(schema=schema)
        self.assertEqual([ValidationIssue("$", "matches 2 alternatives; exactly one required")], reg.validate(0, schema["$id"]))

    def test_refs_allof_anyof_not_and_conditionals_preserve_outputs(self):
        schema = {"$id": "urn:test:logic", "allOf": [
            {"anyOf": [{"$ref": "urn:test:positive"}, {"const": "allowed"}]},
            {"not": {"const": 2}},
            {"if": {"type": "integer"}, "then": {"maximum": 4}, "else": {"minLength": 7}}]}
        self.equivalent(schema, [0, 1, 2, 4, 5, True, "allowed", "no", {}],
            [{"$id": "urn:test:positive", "type": "integer", "minimum": 1}])
        relative = {"$id": "urn:test:relative", "$defs": {"x": {"type": "integer"}},
            "properties": {"n": {"$ref": "#/$defs/x"},
                           "m": {"$id": "urn:test:positive", "$ref": "#"}}}
        self.equivalent(relative, [{"n": "bad", "m": 0}, {"n": 1, "m": 1}],
            [{"$id": "urn:test:positive", "type": "integer", "minimum": 1}])

    def test_reached_configuration_errors_are_not_hidden_in_impossible_alternatives(self):
        for broken in ({"const": "different", "$ref": "urn:test:missing"},
                       {"const": "different", "type": "unknown-type"},
                       {"type": "object", "properties": {"tag": {"const": "different"},
                            "child": {"$ref": "urn:test:missing"}}}):
            schema = {"$id": "urn:test:broken", "oneOf": [{"const": 7}, broken]}
            for kind in (BaselineRegistry, Registry):
                for value in (7, {"tag": "actual", "child": 0}):
                    if broken.get("type") == "object" and value == 7:
                        continue  # This branch fails type before reaching its reference in both validators.
                    with self.subTest(broken=broken, kind=kind, value=value), self.assertRaises(SchemaError):
                        registered(kind, schema).validate(value, schema["$id"])
        malformed = {"$id": "urn:test:unknown-keyword", "oneOf": [{"const": 7}, {"unknownKeyword": False}]}
        for kind in (BaselineRegistry, Registry):
            with self.assertRaises(SchemaError):
                registered(kind, malformed)

    def test_shared_subtree_replays_errors_at_each_distinct_path(self):
        shared_schema = {"type": "integer"}
        schema = {"$id": "urn:test:paths", "properties": {"first": shared_schema, "second": shared_schema}}
        value = "same wrong value"
        data = {"first": value, "second": value}
        self.equivalent(schema, [data])
        issues = registered(schema=schema).validate(data, schema["$id"])
        self.assertEqual(["$.first", "$.second"], [issue.path for issue in issues])

    def test_shared_relative_reference_keeps_each_current_base(self):
        shared = {"$ref": "#/$defs/x"}
        schema = {"$id": "urn:test:two-bases", "allOf": [
            {"$id": "urn:test:left-base", "allOf": [shared]},
            {"$id": "urn:test:right-base", "allOf": [shared]}]}
        extra = [{"$id": "urn:test:left-base", "$defs": {"x": {"minimum": 0}}},
                 {"$id": "urn:test:right-base", "$defs": {"x": {"maximum": 2}}}]
        self.equivalent(schema, [-1, 1, 3], extra)
        reg = registered(schema=schema)
        for target in extra:
            reg.add(target)
        self.assertEqual([ValidationIssue("$", "value above maximum 2")], reg.validate(3, schema["$id"]))

    def test_instance_schema_and_registry_changes_do_not_reuse_prior_results(self):
        schema = {"$id": "urn:test:mutating", "type": "object", "properties": {"n": {"type": "integer"}}}
        reg = registered(schema=schema)
        data = {"n": 1}
        self.assertEqual([], reg.validate(data, schema["$id"]))
        data["n"] = "bad"
        self.assertTrue(reg.validate(data, schema["$id"]))
        schema["properties"]["n"]["type"] = "string"
        self.assertEqual([], reg.validate(data, schema["$id"]))
        reg.add({"$id": schema["$id"], "const": "changed registry"})
        self.assertTrue(reg.validate(data, schema["$id"]))
        unresolved = {"$id": "urn:test:later-ref", "$ref": "urn:test:later-target"}
        reg.add(unresolved)
        with self.assertRaises(SchemaError):
            reg.validate(1, unresolved["$id"])
        reg.add({"$id": "urn:test:later-target", "type": "integer"})
        self.assertEqual([], reg.validate(1, unresolved["$id"]))
        self.assertIsNone(reg._validation_cache.get())

    def test_shared_registry_uses_separate_concurrent_invocation_caches(self):
        barrier, lock, seen = Barrier(2), Lock(), []
        class ConcurrentRegistry(Registry):
            def _validate_uncached(self, inst, schema, base, path, out):
                if path == "$":
                    with lock:
                        seen.append(id(self._validation_cache.get()))
                    barrier.wait(timeout=10)
                return super()._validate_uncached(inst, schema, base, path, out)
        schema = {"$id": "urn:test:concurrent", "type": "integer"}
        reg = registered(ConcurrentRegistry, schema)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(reg.validate, value, schema["$id"]) for value in (1, "bad")]
            result = [future.result() for future in futures]
        self.assertEqual([], result[0])
        self.assertTrue(result[1])
        self.assertEqual(2, len(set(seen)))
        self.assertIsNone(reg._validation_cache.get())


if __name__ == "__main__":
    unittest.main()
