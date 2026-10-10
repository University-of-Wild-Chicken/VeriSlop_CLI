"""Kernel-compiled regressions for VSCore goal generation and property transfer."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import TempDir  # noqa: E402
from verislop import canonical, leanbridge  # noqa: E402
from verislop.exprjson import name_str  # noqa: E402
from verislop.policy import BASELINE_AXIOMS  # noqa: E402
from verislop.targets import vscore_source as src, vscore_target as T  # noqa: E402


NS = "VSCoreGoalFixture"
FLAG = {"enum": "Flag"}
RESULT = {"result": {"error": FLAG, "ok": "Nat"}}
NESTED_RESULT = {"result": {"error": RESULT, "ok": RESULT}}


def var(index):
    return {"tag": "var", "index": index}


def nat(value):
    return {"tag": "nat", "value": str(value)}


def call(symbol, *args):
    return {"tag": "call", "symbol": symbol, "args": list(args)}


def eq(left, right):
    return {"tag": "eq", "left": left, "right": right}


def forall(sort, body):
    return {"tag": "forall", "sort": sort, "body": body}


class CompiledGoalRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.tc = leanbridge.resolve_toolchain()
        cls.modules, cls.deps = {}, {}
        cls.lib = cls.tmp.path / "lib"
        for module, source in T.library_sources().items():
            result, parts = leanbridge.compile_named_module(
                cls.tc, cls.lib, module, source, dict(cls.deps), read_only=[])
            if not result.ok:
                raise AssertionError((module, result.errors))
            cls.modules[module] = parts
            cls.deps[module] = {suffix: str(cls.lib / (leanbridge.module_relpath(module) + suffix))
                                for suffix in parts}
        cls.contract = cls.tmp.path / "contract"
        source = (Path(__file__).parent / "fixtures" / "vscore-goals" / "Contract.lean").read_bytes()
        result, parts = leanbridge.compile_named_module(
            cls.tc, cls.contract, T.CONTRACT_MODULE, source, {}, read_only=[])
        if not result.ok:
            raise AssertionError(result.errors)
        cls.modules[T.CONTRACT_MODULE] = parts
        cls.deps[T.CONTRACT_MODULE] = {
            suffix: str(cls.contract / (T.CONTRACT_MODULE + suffix)) for suffix in parts}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check_compiled_edge(self, case, symbols, formulas):
        """Compile actual candidate refinements, then replay and re-export the complete edge."""
        profile = {
            "profile_id": "vscore-goal-regressions.v0_1", "dsl": "verislop.contract-dsl/0.1",
            "enums": {"Flag": {"constructors": ["on", "off"], "lean_decl": NS + ".Flag",
                                "lean_constructors": [NS + ".Flag.on", NS + ".Flag.off"],
                                "decl_hash": "sha256:" + "0" * 64}},
            "symbols": {name: {"args": args, "result": result, "lean_decl": NS + "." + name,
                               "level_params": [], "decl_hash": "sha256:" + "0" * 64}
                        for name, (args, result, _) in symbols.items()},
            "predicates": {name: {"args": ["Nat"], "lean_decl": NS + "." + name,
                                   "decl_hash": "sha256:" + "0" * 64}
                           for name in ("validInput", "identityProperty")},
        }
        program = {"language": src.LANGUAGE, "entries": [
            {"id": name, "params": [T.sort_ty(s) for s in args], "result": T.sort_ty(result), "body": body}
            for name, (args, result, body) in sorted(symbols.items())]}
        source = canonical.dumps(src.program_json(program))
        relation = {"bindings": [{"symbol": name, "entry": name} for name in sorted(symbols)]}
        obligations = {name: {"formula": formula, "lean_symbol": NS + "." + name,
                               "statement_hash": "sha256:" + "0" * 64}
                       for name, formula in formulas.items()}
        # JSON source/formula packages are trees, even if test construction reused Python nodes.
        obligations = canonical.loads(canonical.dumps(obligations))
        spec = T.build_goal(source, relation, profile, obligations)
        workdir = self.tmp.path / case
        modules, deps = dict(self.modules), dict(self.deps)
        result, parts = leanbridge.compile_named_module(
            self.tc, workdir / "goal", T.GOAL_MODULE, spec.text.encode(), deps,
            read_only=[self.lib, self.contract])
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.sorry_positions, [])
        modules[T.GOAL_MODULE] = parts
        deps[T.GOAL_MODULE] = {
            suffix: str(workdir / "goal" / (T.GOAL_MODULE + suffix)) for suffix in parts}

        proof = ["import VeriSlopBridgeGoal", "namespace VeriSlopBridgeProof", "open VeriSlopBridgeGoal"]
        definitions = [a.name for a in spec.adapters] + ["name_0"]
        for name, (args, _, _) in sorted(symbols.items()):
            proof += [f"theorem refines_{name} : Refines_{name} := by"]
            proof += [f"  unfold Refines_{name}"]
            if args:
                proof += ["  intro " + " ".join(f"x{i}" for i in range(len(args)))]
            if name == "combine":
                proof += ["  cases x1 <;>"]
            proof += [f"  simp [impl_{name}, {NS}.{name}, rawProgram, profile, VSCore.evalEntry,",
                      "    VSCore.findEntry, VSCore.evalExpr, VSCore.evalBin, VSCore.natAdapter,",
                      "    VSCore.boolAdapter, VSCore.unitAdapter, VSCore.enumAdapter, VSCore.exceptAdapter,",
                      "    " + ", ".join(definitions) + "]"]
        proof += ["theorem edge : VeriSlopBridgeGoal.EdgeProp :=",
                  "  VeriSlopBridgeGoal.edge_of_refines " + " ".join("refines_" + n for n in sorted(symbols)),
                  "end VeriSlopBridgeProof", ""]
        result, parts = leanbridge.compile_named_module(
            self.tc, workdir / "proof", T.PROOF_MODULE, "\n".join(proof).encode(), deps,
            read_only=[self.lib, self.contract, workdir / "goal"])
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.sorry_positions, [])
        modules[T.PROOF_MODULE] = parts
        exported = leanbridge.run_kernel_tool_modules(
            self.tc, modules, T.PROOF_MODULE, {"export": True, "axioms": True})
        self.assertTrue(exported["replay"]["ok"], exported["replay"])
        decls = T.decl_index(exported["constants"])
        self.assertEqual(T.statement_mismatches(spec, decls), [])
        for obligation in spec.obligations:
            transfer = decls[T.GOAL_MODULE + ".transfer_" + obligation.oid]
            self.assertIn(obligation.lean_symbol, {name_str(n) for n in transfer["value_constants"]})
        edge = decls[T.EDGE_THEOREM]
        self.assertEqual(edge["type"], T.gconst("EdgeProp"))
        self.assertLessEqual({name_str(a) for a in edge["axioms"]}, set(BASELINE_AXIOMS))
        self.assertEqual(edge.get("unresolved_constants", []), [])
        self.assertEqual(T.reexport(spec, decls)["program"], src.program_json(program))

    def test_reflexive_atoms_and_logical_connectives(self):
        same_call = eq(call("f", var(0)), call("f", var(0)))
        identity = eq(call("f", var(0)), var(0))
        self.check_compiled_edge("logic", {"f": (["Nat"], "Nat", ("var", 0))}, {
            "reflexive": forall("Nat", same_call),
            "nontrivialIff": forall("Nat", {"tag": "iff", "left": same_call, "right": identity}),
            "implication": forall("Nat", {"tag": "implies", "left": same_call, "right": identity}),
        })

    def test_unit_results_and_nested_calls(self):
        self.check_compiled_edge("unit", {
            "unitResult": (["Nat"], "Unit", ("unit",)),
            "unitConsumer": (["Unit"], "Nat", ("nat", 0)),
        }, {
            "unitOutput": forall("Nat", eq(call("unitResult", var(0)), {"tag": "unit"})),
            "nestedUnit": forall("Nat", eq(call("unitConsumer", call("unitResult", var(0))), nat(0))),
        })

    def test_registered_predicate_aliases(self):
        self.check_compiled_edge("predicates", {"f": (["Nat"], "Nat", ("var", 0))}, {
            "predicateAlias": forall("Nat", {
                "tag": "implies",
                "left": {"tag": "le", "left": var(0),
                         "right": {"tag": "add", "left": var(0), "right": nat(1)}},
                "right": eq(call("f", var(0)), var(0)),
            }),
        })

    def test_symbol_named_like_another_symbols_helper(self):
        self.check_compiled_edge("collision", {
            "f": (["Nat"], "Nat", ("var", 0)), "f_iff": (["Nat"], "Nat", ("var", 0)),
        }, {"collision": forall("Nat", eq(call("f", var(0)), call("f_iff", var(0))))})

    def test_nested_results_argument_order_and_range_scopes(self):
        error = {"tag": "error", "ok_sort": "Nat",
                 "value": {"tag": "enum", "sort": "Flag", "constructor": "off"}}
        self.check_compiled_edge("representations", {
            "f": (["Nat"], "Nat", ("var", 0)),
            "g": (["Nat"], RESULT, ("ok", ("enum", "Flag"), ("var", 0))),
            "combine": (["Nat", "Bool", "Nat"], "Nat",
                        ("ite", ("var", 1), ("bin", "sub", ("var", 2), ("var", 0)), ("var", 0))),
            "boolIdentity": (["Bool"], "Bool", ("var", 0)),
            "enumIdentity": ([FLAG], FLAG, ("var", 0)),
            "resultIdentity": ([RESULT], RESULT, ("var", 0)),
            "nestedResultIdentity": ([NESTED_RESULT], NESTED_RESULT, ("var", 0)),
            "zero": ([], "Nat", ("nat", 0)),
        }, {
            "nestedCalls": forall("Nat", eq(call("g", call("f", var(0))),
                                                {"tag": "ok", "error_sort": FLAG, "value": var(0)})),
            "argumentOrder": forall("Nat", forall("Nat", eq(
                call("combine", var(1), {"tag": "bool", "value": True}, var(0)),
                {"tag": "sub", "left": var(1), "right": var(0)}))),
            "enumInput": forall(FLAG, eq(call("enumIdentity", var(0)), var(0))),
            "resultInput": forall(RESULT, eq(call("resultIdentity", var(0)), var(0))),
            "nestedResultInput": forall(NESTED_RESULT, eq(call("nestedResultIdentity", var(0)), var(0))),
            "resultError": eq(call("resultIdentity", error), error),
            "holdsBool": {"tag": "holds", "term": call("boolIdentity", {"tag": "bool", "value": True})},
            "zeroArity": eq(call("zero"), nat(0)),
            **{name: forall("Nat", {"tag": tag, "lower": var(0),
                                     "upper": {"tag": "add", "left": var(0), "right": nat(1)},
                                     "body": eq(call("f", var(0)), var(0))})
               for name, tag in (("forallRange", "forall_range"), ("existsRange", "exists_range"))},
        })


if __name__ == "__main__":
    unittest.main()
