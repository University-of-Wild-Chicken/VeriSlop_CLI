"""Independent kernel fixtures for the 0.3 semantics and canonical transport.

The fixtures are unrelated to retained bootstrap tasks. Clean compilation and
full staged-module replay check the normative library, rather than a host oracle.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from verislop import canonical, leanbridge
from verislop.targets import vscore3_source as src

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("VSCore.Syntax", "VSCore.Decode", "VSCore2.Syntax", "VSCore2.Decode",
           "VSCore3.Syntax", "VSCore3.Equality", "VSCore3.Decode", "VSCore3.Typed",
           "VSCore3.Typing", "VSCore3.Semantics", "VSCore3.Proofs", "VSCore3.Transport", "VSCore3")


def fixture() -> bytes:
    text = '''program "vscore/0.3" profile "data-pipeline/0.3";
record Parcel { label: String; count: Int; }
entry divide(a: Int, b: Int) -> Int { Int.fdiv(a, b) }
entry difference(a: Int, b: Int) -> Int { a - b }
entry natural_result(a: Int) -> Nat { Int.toNat(a) }
entry ordered(a: String, b: String) -> Bool { a < b }
entry unique_result(xs: List(String)) -> List(String) { List.unique(xs) }
entry sorted_result(xs: List(Int)) -> List(Int) { List.sort(xs) }
entry get_result(xs: List(Int), i: Nat) -> Option(Int) { List.get(xs, i) }
entry range_result(n: Nat) -> List(Nat) { List.range(n) }
entry joined(a: List(Int), b: List(Int)) -> List(Int) { List.reverse(List.append(a, b)) }
entry length_result(a: List(Int)) -> Nat { List.length(a) }
entry scalar() -> String { string(0, 955, 128640, 1114111) }
entry parcel(p: Record(Parcel)) -> Record(Parcel) { p }
'''
    prog = src.parse_surface(text)
    data = src.source_bytes(prog)
    sigs = src.check_program({}, prog)
    lean = ('import VSCore3\nimport VSCore2.Decode\n'
            'set_option maxRecDepth 100000\nset_option maxHeartbeats 20000000\n'
            'open VSCore3\nnamespace DataConformance\n'
            'def resultMatches (v : Value) : Except EvalError Value → Bool | .ok x => x == v | .error _ => false\n'
            'theorem resultMatches_sound (r : Except EvalError Value) (v : Value) (h : resultMatches v r = true) : r = .ok v := by\n'
            '  cases r with\n'
            '  | error e => simp [resultMatches] at h\n'
            '  | ok x => exact congrArg Except.ok ((value_beq_iff x v).mp h)\n'
            'def profile : Profile := {enums := []}\n'
            f'def source : List Nat := {src.lean_list([str(b) for b in data])}\n'
            f'def program : Program := {src.lean_program(prog)}\n'
            'theorem parses : parseSource source = .ok program := by rfl\n'
            f'theorem checks : checkProgram profile program = .ok {src.lean_signatures(sigs)} := '
            'checkProgram_of_check (by decide +kernel)\n'
            'def rejected {α : Type} : Except String α → Bool | .error _ => true | .ok _ => false\n'
            'example : rejected (VSCore2.parseSource source) = true := by decide +kernel\n')
    values = [
        ("divide", "[.int (-7), .int 3]", ".int (-3)"),
        ("divide", "[.int 7, .int (-3)]", ".int (-3)"),
        ("divide", "[.int (-7), .int (-3)]", ".int 2"),
        ("divide", "[.int (-7), .int 0]", ".int 0"),
        ("difference", "[.int (-2), .int 7]", ".int (-9)"),
        ("natural_result", "[.int (-8)]", ".nat 0"),
        ("natural_result", "[.int 8]", ".nat 8"),
        ("ordered", '[.string "", .string "x"]', ".bool true"),
        ("ordered", '[.string (String.ofList [Char.ofNat 57344]), .string (String.ofList [Char.ofNat 65536])]', ".bool true"),
        ("unique_result", '[.cons (.string "b") (.cons (.string "a") (.cons (.string "b") .nil))]', '.cons (.string "b") (.cons (.string "a") .nil)'),
        ("sorted_result", "[.cons (.int 3) (.cons (.int (-2)) (.cons (.int 3) .nil))]", ".cons (.int (-2)) (.cons (.int 3) (.cons (.int 3) .nil))"),
        ("get_result", "[.cons (.int 4) .nil, .nat 0]", ".some (.int 4)"),
        ("get_result", "[.cons (.int 4) .nil, .nat 1]", ".none"),
        ("range_result", "[.nat 3]", ".cons (.nat 0) (.cons (.nat 1) (.cons (.nat 2) .nil))"),
        ("joined", "[.cons (.int 1) .nil, .cons (.int 2) .nil]", ".cons (.int 2) (.cons (.int 1) .nil)"),
        ("length_result", "[.cons (.int 1) .nil]", ".nat 1"),
        ("scalar", "[]", ".string (String.ofList [Char.ofNat 0, Char.ofNat 955, Char.ofNat 128640, Char.ofNat 1114111])"),
    ]
    for entry, args, value in values:
        if entry == "sorted_result":
            lean += f'''example : evalEntry profile program "{entry}" {args} = .ok ({value}) := by
  have hs : ([3, -2, 3] : List Int).mergeSort (fun a b => decide (a ≤ b)) = [-2, 3, 3] := by
    simp [List.mergeSort, List.MergeSort.Internal.splitInTwo, List.splitAt_eq]
  with_unfolding_all
    change Except.ok (encode (.list .int) (([3, -2, 3] : List Int).mergeSort (fun a b => decide (a ≤ b)))) = .ok ({value})
  rw [hs]
  with_unfolding_all rfl
'''
        else:
            lean += f'example : evalEntry profile program "{entry}" {args} = .ok ({value}) := resultMatches_sound _ _ (by decide +kernel)\n'
    lean += '''
example : evalEntry profile program "divide" [.nat 1, .int 1] = .error .invalidArguments := by with_unfolding_all rfl
example : compileBin (.eq) (⟨.nat, fun (_ : Env []) => 0⟩) (⟨.nat, fun _ => 0⟩) = .error "eq compiled in compileExpr after representation is available" := by rfl
def payload : Shape := .product .string (.product .int .unit)
def layout : RecordLayout ["label", "count"] payload := .cons "label" (.cons "count" .nil)
def parcelLaws : RawLaws (.record "Parcel" ["label", "count"] payload) :=
  recordRawLaws "Parcel" layout (productRawLaws stringRawLaws (productRawLaws intRawLaws unitRawLaws))
def aggregateLaws : RawLaws (.list (.option (.record "Parcel" ["label", "count"] payload))) :=
  listRawLaws (optionRawLaws parcelLaws)
example (xs : Denote (.list (.option (.record "Parcel" ["label", "count"] payload)))) :
    decode _ (encode _ xs) = some xs := aggregateLaws.decode_encode xs
example {v : Value} {xs : Denote (.list (.option (.record "Parcel" ["label", "count"] payload)))}
    (h : decode _ v = some xs) : encode _ xs = v := aggregateLaws.encode_decode h
example : ¬ RawLaws (.record "Bad" [] .nat) := by
  intro h
  have he := h.decode_encode 3
  simp [decode, encode, encodeFields, packFields] at he
example : ¬ (∀ x : Int, x + 1 = x - 1) := by
  intro h
  have h := h 0
  contradiction
example : rejected (compileExpr 3 profile [] [] [] (.string [55296])) = true := by decide +kernel
example : rejected (compileExpr 3 profile [] [] [] (.listSort (.nil .bool))) = true := by decide +kernel
example : rejected (compileExpr 3 profile [] [] [] (.bin .add (.nat 1) (.int 1))) = true := by decide +kernel
example : rejected (decodeIntLiteral "-0") = true := by decide +kernel
example : rejected (decodeIntLiteral "+1") = true := by decide +kernel
example : rejected (decodeIntLiteral "01") = true := by decide +kernel
example : rejected (decodeCodepoints [.num 1114112]) = true := by decide +kernel
example : rejected (decodeCodepoints [.num 55296]) = true := by decide +kernel
end DataConformance
'''
    return lean.encode()


class VSCore3KernelTests(unittest.TestCase):
    def test_two_clean_builds_and_full_kernel_replay(self):
        tc = leanbridge.resolve_toolchain()
        observations = []
        for _ in range(2):
            with tempfile.TemporaryDirectory(prefix="verislop-vscore3-kernel-") as tmp:
                root = Path(tmp)
                env = {**os.environ, "LEAN_PATH": str(root)}
                modules = {}
                sources = [(m, (ROOT / "verislop/lean" / (m.replace(".", "/") + ".lean")).read_bytes()) for m in MODULES]
                sources.append(("DataConformance", fixture()))
                for module, source in sources:
                    rel = Path(module.replace(".", "/") + ".lean")
                    path = root / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(source)
                    result = subprocess.run([str(tc.lean), "-o", str(rel.with_suffix(".olean")), str(rel)],
                                            cwd=root, env=env, capture_output=True, text=True, timeout=180)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertNotIn("declaration uses 'sorry'", result.stdout + result.stderr)
                    modules[module] = leanbridge.module_parts(root, module)
                response = leanbridge.run_kernel_tool_modules(tc, modules, "DataConformance", {"export": True, "axioms": True})
                self.assertTrue(response.get("import", {}).get("ok"), response)
                self.assertTrue(response.get("replay", {}).get("ok"), response)
                self.assertNotIn("sorryAx", str(response))
                observations.append({m: canonical.digest_json({s: canonical.digest(b) for s, b in ps.items()}) for m, ps in modules.items()})
                bad = root / "BadRefinement.lean"
                bad.write_text('import VSCore3\nexample : ∀ x : Int, x + 1 = x - 1 := by intro x; rfl\n')
                reject = subprocess.run([str(tc.lean), "BadRefinement.lean"], cwd=root, env=env,
                                        capture_output=True, text=True, timeout=60)
                self.assertNotEqual(reject.returncode, 0)
        self.assertEqual(observations[0], observations[1])


if __name__ == "__main__":
    unittest.main()
