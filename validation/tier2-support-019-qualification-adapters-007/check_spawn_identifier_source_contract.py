#!/usr/bin/env python3
"""Check isolated literal schema predicates and AST preservation; no verifier import."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import re


def identity(path, root):
    raw = path.read_bytes()
    return {"path": path.relative_to(root).as_posix(),
            "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(), "byte_count": len(raw)}


def declarations(tree):
    result = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[node.name] = ast.dump(node, include_attributes=False)
        elif isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result[node.name + "." + member.name] = ast.dump(member, include_attributes=False)
    return result


class Names(ast.NodeTransformer):
    def __init__(self, mapping):
        self.mapping = mapping

    def visit_Name(self, node):
        return ast.copy_location(ast.Name(id=self.mapping.get(node.id, node.id), ctx=node.ctx), node)


def guard(tree, message, mapping):
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and len(node.args) == 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value == message:
            matches.append(node.args[0])
        if isinstance(node, ast.If) and any(isinstance(member, ast.Raise) and isinstance(member.exc, ast.Call) and
                member.exc.args and isinstance(member.exc.args[0], ast.Constant) and member.exc.args[0].value == message
                for member in node.body):
            if not isinstance(node.test, ast.UnaryOp) or not isinstance(node.test.op, ast.Not):
                raise ValueError("Assembler guard must reject the exact negated positive predicate")
            matches.append(node.test.operand)
    if len(matches) != 1:
        raise ValueError("Expected exactly one registered isolated guard")
    result = Names(mapping).visit(copy.deepcopy(matches[0]))
    allowed = {"type", "dict", "set", "str", "re", "request", "response"}
    if any(isinstance(n, ast.Name) and n.id not in allowed for n in ast.walk(result)):
        raise ValueError("Guard refers to an unregistered operation or data source")
    calls = [ast.unparse(n.func) for n in ast.walk(result) if isinstance(n, ast.Call)]
    if any(name not in {"type", "set", "re.fullmatch", "response['task_name'].rsplit"} for name in calls):
        raise ValueError("Guard contains a non-schema call")
    return ast.fix_missing_locations(result)


class UnrelatedTree(ast.NodeTransformer):
    """Erase only the declared changed definitions for a whole-tree comparison."""
    def __init__(self, names, drop_re=False):
        self.names, self.drop_re, self.parent = names, drop_re, ""

    def visit_ClassDef(self, node):
        previous, self.parent = self.parent, node.name
        result = self.generic_visit(node)
        self.parent = previous
        return result

    def visit_FunctionDef(self, node):
        qualified = self.parent + "." + node.name if self.parent else node.name
        if qualified in self.names:
            return ast.FunctionDef(name=node.name, args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[],
                                   kw_defaults=[], defaults=[]), body=[ast.Pass()], decorator_list=[])
        return node

    def visit_Import(self, node):
        if self.drop_re and len(node.names) == 1 and node.names[0].name == "re":
            return None
        return node


class AuthorProjection(ast.NodeTransformer):
    """Erase only F010 guards and normalize the one relocated schema check."""
    def __init__(self, response_name, old):
        self.response_name, self.old = response_name, old

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call) and len(node.value.args) == 2 and isinstance(node.value.args[1], ast.Constant) and \
                node.value.args[1].value == "ACTUAL_FRESH_AUTHOR_CANONICAL_TASK_NAME_NOT_BOUND":
            return None
        return self.generic_visit(node)

    def visit_If(self, node):
        if any(isinstance(member, ast.Raise) and isinstance(member.exc, ast.Call) and member.exc.args and
                isinstance(member.exc.args[0], ast.Constant) and member.exc.args[0].value ==
                "Actual author canonical task_name response differs" for member in node.body):
            return None
        return self.generic_visit(node)

    def visit_Subscript(self, node):
        if not self.old and isinstance(node.value, ast.Name) and node.value.id == self.response_name and \
                isinstance(node.slice, ast.Constant) and node.slice.value == "task_name":
            node.slice.value = "agent_id"
        return self.generic_visit(node)

    def visit_BoolOp(self, node):
        node = self.generic_visit(node)
        if self.old:
            raw = self.response_name + "['agent_id']"
            excluded = {raw, "type(" + raw + ") is str"} if isinstance(node.op, ast.And) else \
                       {"not " + raw, "type(" + raw + ") is not str"}
            node.values = [value for value in node.values if ast.unparse(value) not in excluded]
        return node

    def visit_Constant(self, node):
        if not self.old and node.value == "Actual author internal canonical task_name bindings differ":
            node.value = "Actual author agent identities differ"
        return node


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter-dir", type=Path, required=True)
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--counterexample", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    candidate, baseline = args.adapter_dir.resolve(), args.baseline_dir.resolve()
    registration = json.loads((candidate / "source-schema-controls-registration-005.json").read_text())
    counterexample = json.loads(args.counterexample.read_text())
    raw_ref = counterexample["raw_response_ref"]
    actual_path = root / raw_ref["path"]
    if identity(actual_path, root) != raw_ref:
        raise ValueError("Observed raw counterexample bytes changed")
    actual = json.loads(actual_path.read_text())
    base_manifest = json.loads((baseline / "hash-manifest.json").read_text())
    for name, expected in base_manifest["files"].items():
        observed = identity(root / name, root)
        if {key: observed[key] for key in ("sha256", "byte_count")} != expected:
            raise ValueError("Immutable baseline source changed")
    sources = ("predicate_reader.py", "additional_predicates.py", "assemble_ancillary_indexes.py")
    allowed = {"predicate_reader.py": {"Reader.fresh_author"},
               "additional_predicates.py": {"AdditionalPredicates.fresh_author"},
               "assemble_ancillary_indexes.py": {"main"}}
    names = ({"spawn": "request", "response": "response"},
             {"request": "request", "actual_spawn": "response"},
             {"request": "request", "result": "response"})
    trees, expressions, changed = {}, [], {}
    for name, mapping in zip(sources, names):
        old_tree = ast.parse((baseline / name).read_text())
        new_tree = ast.parse((candidate / name).read_text())
        old, new = declarations(old_tree), declarations(new_tree)
        changed[name] = sorted(key for key in set(old) | set(new) if old.get(key) != new.get(key))
        if set(changed[name]) != allowed[name]:
            raise ValueError("Unexpected declaration change: " + name)
        old_other = [n for n in old_tree.body if not isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
        new_other = [n for n in new_tree.body if not isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
        if name == "assemble_ancillary_indexes.py":
            new_other = [n for n in new_other if not (isinstance(n, ast.Import) and len(n.names) == 1 and n.names[0].name == "re")]
        if [ast.dump(n) for n in old_other] != [ast.dump(n) for n in new_other]:
            raise ValueError("Unexpected non-declaration change: " + name)
        old_skeleton = UnrelatedTree(allowed[name]).visit(copy.deepcopy(old_tree))
        new_skeleton = UnrelatedTree(allowed[name], name == "assemble_ancillary_indexes.py").visit(copy.deepcopy(new_tree))
        if ast.dump(old_skeleton) != ast.dump(new_skeleton):
            raise ValueError("Unrelated full source AST changed: " + name)
        response_name = "response" if name == "predicate_reader.py" else "actual_spawn" if name == "additional_predicates.py" else "result"
        old_projection = AuthorProjection(response_name, True).visit(copy.deepcopy(old_tree))
        new_projection = AuthorProjection(response_name, False).visit(copy.deepcopy(new_tree))
        old_projection = UnrelatedTree(set()).visit(old_projection)
        new_projection = UnrelatedTree(set(), name == "assemble_ancillary_indexes.py").visit(new_projection)
        if ast.dump(old_projection) != ast.dump(new_projection):
            raise ValueError("F010 change contains unrelated author predicate mutation: " + name)
        trees[name] = new_tree
        expressions.append(guard(new_tree, registration["guards"][name], mapping))
    if len({ast.dump(expression) for expression in expressions}) != 1:
        raise ValueError("Three consumers use different identifier predicates")
    for name in ("current_root_reconcile.py", "materialize_adapter_configuration.py"):
        if (baseline / name).read_bytes() != (candidate / name).read_bytes():
            raise ValueError("Unrelated executable changed: " + name)
    preserved = {}
    for name in ("runtime-contract.json", "predicate-reader-specification.json", "reconciliation-specification.json"):
        old = json.loads((baseline / name).read_text())
        new = json.loads((candidate / name).read_text())
        keys = [key for key in ("original18", "additional9", "additional_claims") if key in old]
        for key in keys:
            if old[key] != new[key]:
                raise ValueError("Frozen claim objects changed: " + name + ":" + key)
        preserved[name] = keys
    leaf = actual["task_name"].rsplit("/", 1)[1]
    good = {"task_name": leaf}
    cases = [("actual_observed_singleton", actual, good, True),
             ("direct_canonical", {"task_name": "/root/" + leaf}, good, True),
             ("digit_underscore_segments", {"task_name": "/root/01_/" + leaf}, good, True)]
    for label, value in (("empty_dict", {}), ("legacy_only", {"agent_id": actual["task_name"]}),
                         ("legacy_extra", dict(actual, agent_id=actual["task_name"])),
                         ("extra_field", dict(actual, model="gpt-6.1-sol")), ("list", []),
                         ("string", actual["task_name"]), ("null", None), ("bool", True),
                         ("task_bool", {"task_name": True}), ("task_int", {"task_name": 1}),
                         ("task_null", {"task_name": None}), ("task_list", {"task_name": []})):
        cases.append((label, value, good, False))
    for label, value in (("empty", ""), ("relative", "root/" + leaf), ("nonroot", "/other/" + leaf),
                         ("trailing", "/root/" + leaf + "/"), ("double_slash", "/root//" + leaf),
                         ("dot", "/root/./" + leaf), ("dotdot", "/root/../" + leaf),
                         ("space", "/root/a b/" + leaf), ("backslash", "/root/a\\b/" + leaf),
                         ("uppercase", "/root/UPPER/" + leaf), ("wrong_leaf", "/root/wrong_leaf")):
        cases.append(("path_" + label, {"task_name": value}, good, False))
    for label, value in (("mismatch", "wrong_leaf"), ("empty", ""), ("bool", True), ("int", 1),
                         ("null", None), ("list", []), ("slash", "/" + leaf), ("uppercase", "UPPER")):
        cases.append(("request_" + label, actual, {"task_name": value}, False))
    results = []
    for expression in expressions:
        compiled = compile(ast.Expression(expression), "<isolated-registered-schema-expression>", "eval")
        observed = []
        for label, response, request, expected in cases:
            value = eval(compiled, {"__builtins__": {}}, {"type": type, "dict": dict, "set": set, "str": str,
                        "re": re, "request": request, "response": response})
            if type(value) is not bool or value is not expected:
                raise ValueError("Source schema counterexample: " + label)
            observed.append({"id": label, "accepted": value, "expected": expected})
        results.append(observed)
    report = {"format": "verislop.support019-source-contract-inspection/1", "status": "SOURCE_CONTRACT_CHECKED",
              "runtime_qualification": "UNQUALIFIED", "execution_authority": False, "qualification_authority": False,
              "actual_target_verifier_runs": 0, "actual_models": 0, "actual_Lean_runs": 0, "actual_task_runs": 0,
              "scope": "Only isolated literal schema expression evaluation and source AST/hash preservation; no target import or method invocation",
              "changed_declarations": changed, "frozen_claim_objects_preserved": preserved,
              "all_unrelated_ast_exact": True, "author_methods_exact_after_declared_schema_projection": True,
              "schema_expression_ast_sha256": "sha256:" + hashlib.sha256(ast.dump(expressions[0]).encode()).hexdigest(),
              "controls_per_expression": len(cases), "consumers": list(sources), "controls": results,
              "source_refs": [identity(candidate / name, root) for name in sources],
              "counterexample_ref": identity(args.counterexample.resolve(), root), "raw_response_ref": raw_ref,
              "fresh_runtime_required": True}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "consumers": 3, "controls_per_expression": len(cases),
                      "qualification_authority": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
