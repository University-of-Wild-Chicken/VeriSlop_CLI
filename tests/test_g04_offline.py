"""Oracle/mutation tests plus explicitly opt-in, model-free native replay tests."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import io
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unicodedata
import unittest
from unittest.mock import patch

from synthetic_dataset.tools import g04_oracle as oracle, check_g04_offline as check
from verislop import canonical, dsl, leanbridge, policy
from verislop.exprjson import constants, loose_bvar_range
from verislop.targets import vscore3_source as source, vscore3_target as target


# Handwritten engineering source, never a historical model output. The accepted
# contract below is deliberately vacuous: independent comparison must still work.
SURFACE = '''program "vscore/0.3" profile "data-pipeline/0.3";
record Asset { path:String; bytes:Nat; enabled:Bool; }
record Input { prefix:String; assets:List(Record(Asset)); }
record Planned { destination:String; bytes:Nat; destination_length:Nat; }
record Output { items:List(Record(Planned)); total_bytes:Nat; item_count:Nat; }
entry solve(x:Record(Input))->Record(Output){
  let kept=List.filter(x.assets;a=>a.enabled && not (a.path==""));
  let items=List.map(kept;a=>let dest=String.append(x.prefix,a.path);
    record Planned{destination=dest,bytes=a.bytes,destination_length=String.length(dest)});
  record Output{items=items,total_bytes=List.sum(List.map(kept;a=>a.bytes)),item_count=List.length(items)}
}
'''
CONTRACT = '''import Std
namespace Fixture
structure Asset where
  path : String
  bytes : Nat
  enabled : Bool
structure Input where
  «prefix» : String
  assets : List Asset
structure Planned where
  destination : String
  bytes : Nat
  destination_length : Nat
structure Output where
  items : List Planned
  total_bytes : Nat
  item_count : Nat
def solve (_ : Input) : Output := { items := [], total_bytes := 0, item_count := 0 }
theorem vacuous (x : Input) : solve x = solve x := rfl
end Fixture
'''.encode("utf-8")


def fixture(surface=SURFACE):
    program = source.parse_surface(surface)
    declarations = {d["id"]: d for d in program["declarations"]}
    def sort(ty):
        if isinstance(ty, str):
            return ty.capitalize()
        return {ty[0]: sort(ty[1]) if ty[0] == "list" else ty[1]}
    records = {name: {"lean_decl": "Fixture." + name, "lean_constructor": "Fixture." + name + ".mk",
               "fields": [{"name": f[0], "sort": sort(f[1]),
                           "lean_projection": "Fixture." + name + "." + f[0]} for f in d["fields"]]}
               for name, d in declarations.items()}
    profile = {"profile_id": "fixture-g04", "dsl": "verislop.contract-dsl/0.2", "enums": {},
               "predicates": {}, "records": records, "symbols": {"model": {"lean_decl": "Fixture.solve",
               "args": [{"record": "Input"}], "result": {"record": "Output"}}}}
    call = {"tag": "call", "symbol": "model", "args": [{"tag": "var", "index": 0}]}
    obligations = {"O1": {"formula": {"tag": "forall", "sort": {"record": "Input"},
                    "body": {"tag": "eq", "left": call, "right": call}},
                    "lean_symbol": "Fixture.vacuous", "statement_hash": "sha256:" + "1"*64}}
    relation = {"schema_version": "0.3", "format": target.RELATION_FORMAT, "template": target.TEMPLATE,
                "source_slot": "vscore-source", "proof_slot": "vscore-proof",
                "bindings": [{"symbol": "model", "entry": "solve"}]}
    return target.build_goal(source.source_bytes(program), relation, profile, obligations)


def functional(data):
    """Separate positive test implementation: comprehension and UTF-32 counting."""
    pairs = [(data["prefix"] + a["path"], a["bytes"]) for a in data["assets"] if a["enabled"] and a["path"]]
    return {"items": [{"destination": d, "bytes": n, "destination_length": len(d.encode("utf-32-le"))//4}
                      for d, n in pairs], "total_bytes": sum(n for _, n in pairs), "item_count": len(pairs)}


class OracleTests(unittest.TestCase):
    def test_discriminating_literal_and_input_immutability(self):
        data = oracle.cases()[0]["input"]
        before = deepcopy(data)
        dest = "\U0001f511\0e\u0301"
        item = {"destination": dest, "bytes": 3, "destination_length": 4}
        self.assertEqual(oracle.expected(data), {"items": [item, item], "total_bytes": 6, "item_count": 2})
        self.assertEqual(len(dest.encode("utf-16-le"))//2, 5)
        self.assertEqual(len(dest.encode("utf-8")), 8)
        self.assertEqual(data, before)

    def test_fixed_suite_positive_and_repeated_determinism(self):
        first = canonical.dumps(oracle.suite())
        self.assertEqual(first, canonical.dumps(oracle.suite()))
        self.assertEqual(len(oracle.cases()), 18)
        for case in oracle.cases():
            with self.subTest(case=case["case_id"]):
                self.assertEqual(oracle.expected(case["input"]), functional(case["input"]))
        big = oracle.expected(next(r["input"] for r in oracle.cases() if r["case_id"] == "exact-big-nats"))
        self.assertEqual(big["total_bytes"], (2**53+1)+(2**64-1)+2*(2**128+7)+10**100)
        self.assertIn(str(big["total_bytes"]), first.decode())

    def test_invalid_domain_is_not_silently_coerced(self):
        for asset in ({"path": "\ud800", "bytes": 1, "enabled": False},
                      {"path": "a", "bytes": -1, "enabled": True},
                      {"path": "a", "bytes": True, "enabled": True},
                      {"path": "a", "bytes": 1, "enabled": 1},
                      {"path": "a", "bytes": 1.0, "enabled": True}):
            with self.subTest(asset=asset), self.assertRaises(ValueError):
                oracle.expected({"prefix": "", "assets": [asset]})
        for surrogate in ("\ud800", "\udfff", "\ud83d\udd11"):
            with self.assertRaises(ValueError):
                oracle.expected({"prefix": surrogate, "assets": []})

    def test_deliberate_wrong_implementations_are_killed(self):
        def wrong(data, mutation):
            result = functional(data)
            items = result["items"]
            if mutation == "dedup":
                items[:] = [i for n, i in enumerate(items) if i not in items[:n]]
            elif mutation == "sort":
                items.sort(key=lambda i: i["destination"])
            elif mutation == "reverse":
                items.reverse()
            elif mutation in ("include-disabled", "include-empty"):
                other = deepcopy(data)
                if mutation == "include-disabled":
                    for a in other["assets"]: a["enabled"] = True
                else:
                    for a in other["assets"]:
                        if not a["path"]: a["path"] = "EMPTY"
                return functional(other)
            elif mutation in ("utf8", "utf16", "graphemes", "nul-terminated", "normalize", "separator", "trim", "lower", "bytes"):
                for i in items:
                    d = i["destination"]
                    if mutation == "utf8": i["destination_length"] = len(d.encode("utf-8"))
                    if mutation == "utf16": i["destination_length"] = len(d.encode("utf-16-le"))//2
                    if mutation == "graphemes": i["destination_length"] = sum(not unicodedata.combining(c) for c in d)
                    if mutation == "nul-terminated": i["destination_length"] = len(d.split("\0")[0])
                    if mutation == "normalize": i["destination"] = unicodedata.normalize("NFC", d)
                    if mutation == "separator": i["destination"] = data["prefix"] + "/" + d[len(data["prefix"]):]
                    if mutation == "trim": i["destination"] = d.strip()
                    if mutation == "lower": i["destination"] = d.lower()
                    if mutation == "bytes": i["bytes"] += 1
            elif mutation == "overflow": result["total_bytes"] %= 2**64
            elif mutation == "float-sum": result["total_bytes"] = int(float(result["total_bytes"]))
            elif mutation == "count-input": result["item_count"] = len(data["assets"])
            elif mutation == "empty-totals":
                if not items: result["total_bytes"] = 1
            return result
        mutations = ("dedup", "sort", "reverse", "include-disabled", "include-empty", "utf8", "utf16",
                     "graphemes", "nul-terminated", "normalize", "separator", "trim", "lower", "bytes",
                     "overflow", "float-sum", "count-input", "empty-totals")
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertTrue(any(wrong(r["input"], mutation) != oracle.expected(r["input"]) for r in oracle.cases()))


class AdapterTests(unittest.TestCase):
    def test_actual_vscore_goal_and_independent_equality(self):
        spec = fixture()
        selected = check.endpoint(spec)
        expr = check.equality(spec, selected, oracle.cases()[0]["input"])
        names = constants(expr)
        self.assertEqual(loose_bvar_range(expr), 0)
        self.assertIn("VeriSlopBridgeGoal.source_fn_model", names)
        self.assertNotIn("Fixture.solve", names)
        self.assertNotIn("Fixture.vacuous", names)
        rendered = target.Printer().term(expr)
        self.assertIn("Fixture.Output.mk", rendered)
        self.assertIn("Fixture.Planned.mk", rendered)
        # A vacuous accepted equality has not been reused as the expected predicate.
        self.assertNotEqual(expr, check.kernel.ground(spec, spec.obligations[0].formula,
            [check.carrier(oracle.cases()[0]["input"], selected.arg_sorts[0], spec.profile)]))

    def test_reordered_nominal_fields_and_signature_rejection(self):
        spec = fixture()
        selected = check.endpoint(spec)
        spec.profile.records["Input"]["fields"].reverse()
        self.assertEqual(check.endpoint(spec), selected)
        value = check.carrier({"prefix": "X", "assets": []}, selected.arg_sorts[0], spec.profile)
        self.assertEqual(value, ("record", "Input", ((), "X")))
        spec.profile.records["Input"]["fields"][1]["sort"] = "Int"
        with self.assertRaisesRegex(ValueError, "sort mismatch"): check.endpoint(spec)
        spec = fixture()
        spec.profile.records["Output"]["fields"].pop()
        with self.assertRaisesRegex(ValueError, "field inventory"): check.endpoint(spec)

    def test_reporting_requires_native_boolean_and_keeps_unresolved_separate(self):
        spec = fixture()
        for value, status in ((True, "PASS"), (False, "FAIL"), (1, "UNRESOLVED"), (None, "UNRESOLVED")):
            result = check.compare(spec, lambda expr: {"kernel_replay": True, "predicate": value})
            self.assertEqual(result["status"], status)
        def timeout(_): raise TimeoutError("bounded native replay")
        self.assertEqual(check.compare(spec, timeout)["status"], "UNRESOLVED")
        self.assertEqual(check.compare(spec, lambda _: {"predicate": True})["status"], "UNRESOLVED")
        sequence = iter([False] + [None]*17)
        result = check.compare(spec, lambda _: {"kernel_replay": True, "predicate": next(sequence)})
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(sum(r["status"] == "UNRESOLVED" for r in result["cases"]), 17)

    def test_cli_cases_and_unavailable_bundle(self):
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(check.main(["--cases"]), 0)
        report = canonical.loads(out.getvalue())
        self.assertEqual(report["status"], "NOT_RUN")
        self.assertEqual(len(report["cases"]), 18)
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as out:
            self.assertEqual(check.main(["--bundle", tmp, "--bridge-id", "b", "--edge-id", "e",
                                         "--source-sha256", "sha256:"+"0"*64]), 2)
            self.assertEqual(list(Path(tmp).iterdir()), [])
        self.assertEqual(canonical.loads(out.getvalue())["status"], "UNRESOLVED")

    def test_frozen_source_pin_read_only_and_mutation_detection(self):
        # Mock native admission/execution only; exercise real descriptor reads,
        # hashes and snapshot rechecks. This is not native qualification evidence.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_bytes = fixture().source_bytes
            (root / "program.json").write_bytes(source_bytes)
            (root / "plan.json").write_bytes(canonical.dumps({}))
            manifest = {"artifacts": [{"path": "program.json", "size": len(source_bytes),
                                      "sha256": canonical.digest(source_bytes)}]}
            (root / "artifacts.json").write_bytes(canonical.dumps(manifest))
            ctx = SimpleNamespace(plan_hash=canonical.digest_file(root / "plan.json"),
                artifacts_hash=canonical.digest_file(root / "artifacts.json"),
                inputs={"source": ("source", source_bytes)}, accepted_profile_hash="fixture-profile",
                acceptance={"toolchain": {"pin": leanbridge.DEFAULT_TOOLCHAIN}})
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            with patch.object(check.checker, "_schema"), \
                 patch.object(check.checker, "load_context", return_value=ctx), \
                 patch.object(check.checker, "derive_goal", return_value=fixture()), \
                 patch.object(check.leanbridge, "resolve_toolchain", return_value=SimpleNamespace(identity=lambda: {})), \
                 patch.object(check.kernel, "check", return_value={"kernel_replay": True, "predicate": True}) as native:
                with self.assertRaisesRegex(ValueError, "source hash"):
                    check.run(root, "b", "e", "sha256:"+"0"*64, 60)
                native.assert_not_called()
                result = check.run(root, "b", "e", canonical.digest(source_bytes), 60)
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})
                def mutate(*args, **kwargs):
                    (root / "program.json").write_bytes(b"changed")
                    return {"kernel_replay": True, "predicate": True}
                native.side_effect = mutate
                with self.assertRaisesRegex(Exception, "changed"):
                    check.run(root, "b", "e", canonical.digest(source_bytes), 60)
                native.reset_mock()
                with self.assertRaisesRegex(ValueError, "artifact binding"):
                    check.run(root, "b", "e", canonical.digest(source_bytes), 60)
                native.assert_not_called()

    def test_reject_symlink_bundle_and_nonfinite_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real").mkdir()
            (root / "link").symlink_to(root / "real", target_is_directory=True)
            with self.assertRaisesRegex(Exception, "symlink"):
                check.run(root / "link", "b", "e", "sha256:"+"0"*64, 60)
            for seconds in (0, -1, float("nan"), float("inf")):
                with self.assertRaises(ValueError): check.run(root, "b", "e", "unused", seconds)


@unittest.skipUnless(os.environ.get("VERISLOP_G04_NATIVE_TESTS") == "1",
                     "opt in with VERISLOP_G04_NATIVE_TESTS=1 and the pinned Lean toolchain")
class NativeReplayTests(unittest.TestCase):
    def test_correct_source_and_wrong_length_against_vacuous_contract(self):
        # Missing tools after opt-in are a failure, never a skip or a semantic PASS.
        tc = leanbridge.resolve_toolchain()
        with tempfile.TemporaryDirectory() as tmp:
            built = leanbridge.compile_module(tc, CONTRACT, Path(tmp) / "contract")
            self.assertTrue(built.ok, built.errors)
            ctx = SimpleNamespace(policy=policy.get("strict"), contract_module=Path(built.olean).read_bytes())
            for surface, expected_status in ((SURFACE, "PASS"),
                    (SURFACE.replace("destination_length=String.length(dest)", "destination_length=0"), "FAIL")):
                spec = fixture(surface)
                result = check.compare(spec, lambda expr: check.kernel.check(tc, ctx, spec, expr,
                                           deadline=time.monotonic()+120))
                self.assertEqual(result["status"], expected_status, result)
                self.assertNotIn("UNRESOLVED", {r["status"] for r in result["cases"]})


if __name__ == "__main__":
    unittest.main()
