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
MODULES = ("SourceBoundary", "VSCore.Syntax", "VSCore.Decode", "VSCore2.Syntax", "VSCore2.Decode",
           "VSCore3.Syntax", "VSCore3.Equality", "VSCore3.Decode", "VSCore3.Typed",
           "VSCore3.Typing", "VSCore3.Semantics", "VSCore3.Proofs", "VSCore3.Transport",
           "VSCore3.SourceFacts", "VSCore3")


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
entry mapped(offset: Int, xs: List(Int)) -> List(Int) { List.map(xs; item => item + offset) }
entry picked(limit: Int, xs: List(Int)) -> List(Int) { List.filter(xs; item => item < limit) }
entry total(limit: Int, xs: List(Int)) -> Int { List.sum(List.map(List.filter(xs; item => item < limit); item => item + limit)) }
entry nat_total(xs: List(Nat)) -> Nat { List.sum(xs) }
entry bool_mapped(xs: List(Int)) -> List(Bool) { List.map(xs; item => item < int(0)) }
entry string_joined(left: String, right: String) -> String { String.append(left, right) }
entry string_count(value: String) -> Nat { String.length(value) }
'''
    prog = src.parse_surface(text)
    data = src.source_bytes(prog)
    sigs = src.check_program({}, prog)
    lean = ('import VSCore3\nimport VSCore2.Decode\nimport SourceBoundary\nimport VSCore3.SourceFacts\n'
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
        ("mapped", "[.int (-1), .cons (.int 0) (.cons (.int 2) .nil)]", ".cons (.int (-1)) (.cons (.int 1) .nil)"),
        ("picked", "[.int 0, .cons (.int (-2)) (.cons (.int 0) (.cons (.int 3) .nil))]", ".cons (.int (-2)) .nil"),
        ("total", "[.int 2, .cons (.int 3) (.cons (.int (-2)) (.cons (.int 1) .nil))]", ".int 3"),
        ("nat_total", "[.cons (.nat 1) (.cons (.nat 4) .nil)]", ".nat 5"),
        ("bool_mapped", "[.cons (.int (-1)) (.cons (.int 0) .nil)]", ".cons (.bool true) (.cons (.bool false) .nil)"),
        ("string_joined", '[.string "", .string ""]', '.string ""'),
        ("string_joined", '[.string "", .string "abc"]', '.string "abc"'),
        ("string_joined", '[.string "abc", .string ""]', '.string "abc"'),
        ("string_joined", '[.string "ab", .string "cd"]', '.string "abcd"'),
        ("string_joined", '[.string "e", .string (String.ofList [Char.ofNat 769])]', '.string (String.ofList [Char.ofNat 101, Char.ofNat 769])'),
        ("string_joined", '[.string (String.ofList [Char.ofNat 0, Char.ofNat 955]), .string (String.ofList [Char.ofNat 128640, Char.ofNat 1114111])]', '.string (String.ofList [Char.ofNat 0, Char.ofNat 955, Char.ofNat 128640, Char.ofNat 1114111])'),
        ("string_count", '[.string ""]', '.nat 0'),
        ("string_count", '[.string "abc"]', '.nat 3'),
        ("string_count", '[.string (String.ofList [Char.ofNat 0])]', '.nat 1'),
        ("string_count", '[.string "λ🚀"]', '.nat 2'),
        ("string_count", '[.string (String.ofList [Char.ofNat 101, Char.ofNat 769])]', '.nat 2'),
        ("string_count", '[.string (String.ofList [Char.ofNat 1114111])]', '.nat 1'),
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
example : rejected (compileExpr 3 profile [] [] [] (.listMap (.int 0) (.var 0))) = true := by decide +kernel
example : rejected (compileExpr 3 profile [] [] [] (.listMap (.nil .int) (.var 1))) = true := by decide +kernel
example : rejected (compileExpr 3 profile [] [] [] (.listFilter (.nil .int) (.int 1))) = true := by decide +kernel
example : rejected (compileExpr 3 profile [] [] [] (.listSum (.nil .bool))) = true := by decide +kernel
example : rejected (compileExpr 3 profile [] [] [] (.stringAppend (.nat 1) (.string []))) = true := by decide +kernel
example : rejected (compileExpr 3 profile [] [] [] (.stringAppend (.string []) (.bool true))) = true := by decide +kernel
example : rejected (compileExpr 3 profile [] [] [] (.stringLength (.nat 1))) = true := by decide +kernel
example : rejected (compileExpr 3 profile [] [] [] (.stringLength (.string [55296]))) = true := by decide +kernel
example : rejected (compileExpr 3 profile [] [] [] (.stringAppend (.string []) (.string [1114112]))) = true := by decide +kernel
example : featuresExpr (.stringLength (.var 0)) = ["string", "base"] := by decide +kernel
example : featuresExpr (.stringAppend (.var 0) (.var 1)) = ["string", "base", "base"] := by decide +kernel
example : rejected (decodeExpr 10 (.obj [("left", .obj [("tag", .str "string"), ("value", .arr [])]), ("tag", .str "string_append")])) = true := by decide +kernel
example : rejected (decodeExpr 10 (.obj [("extra", .bool true), ("left", .obj [("tag", .str "string"), ("value", .arr [])]), ("right", .obj [("tag", .str "string"), ("value", .arr [])]), ("tag", .str "string_append")])) = true := by decide +kernel
example : rejected (decodeExpr 10 (.obj [("tag", .str "string_length")])) = true := by decide +kernel
example : rejected (decodeExpr 10 (.obj [("extra", .bool true), ("tag", .str "string_length"), ("value", .obj [("tag", .str "string"), ("value", .arr [])])])) = true := by decide +kernel
-- λ plus a supplementary-plane scalar is two scalars but six UTF-8 bytes.
example : "λ🚀".length = 2 ∧ "λ🚀".utf8ByteSize = 6 := by decide +kernel
-- A decomposed accent remains two scalars rather than normalizing to é.
example : String.append "e" (String.ofList [Char.ofNat 769]) ≠ "é" := by decide +kernel
example : rejected (decodeIntLiteral "-0") = true := by decide +kernel
example : rejected (decodeIntLiteral "+1") = true := by decide +kernel
example : rejected (decodeIntLiteral "01") = true := by decide +kernel
example : rejected (decodeCodepoints [.num 1114112]) = true := by decide +kernel
example : rejected (decodeCodepoints [.num 55296]) = true := by decide +kernel
-- The abstract SourceBoundary rule does not assert delivered-source facts.
example : VeriSlop.Source.Contract ({
    endpoint := (fun (x _y : Int) => x)
    requirements := [.entry "program.vscore.json" "divide" 2, .typedTotal,
      .deterministic, .inputPreserved, .noExternalIO, .noFloatingPoint,
      .pureData, .restrictedRuntimeOnly] } : VeriSlop.Source.SourceDefinition (Int → Int → Int)) :=
  VeriSlop.Source.contract_sound _
example : (exactSourceFacts profile program "missing").typedTotal = false := by with_unfolding_all rfl
example : (exactSourceFacts profile program "divide").entries =
    [⟨"program.vscore.json", "divide", 2⟩] := by with_unfolding_all rfl
example : VeriSlop.Source.checkRequirement (.entry "program.vscore.json" "wrong" 2)
    { entries := [⟨"program.vscore.json", "divide", 2⟩], uniqueEntries := true,
      typedTotal := true, deterministic := true, inputPreserved := true,
      noExternalIO := true, noFloatingPoint := true, pureData := true,
      restrictedRuntimeOnly := true } = false := by decide +kernel
example (p : Profile) (prog : Program) (cp : CheckedProgram) (id : String)
    (e : CompiledFunction) (hc : compileProgram p prog = .ok cp)
    (he : findEntry cp id = some e) (laws : ∀ t ∈ e.params, RawLaws t)
    (resultLaw : RawLaws e.result) : SourceFactsAdequate p prog id cp e :=
  exactSourceFacts_adequate hc he laws resultLaw
example (p : Profile) (prog : Program) (id : String) (args : List Value) :
    (observeEntry p prog id args).arguments = args ∧
    (observeEntry p prog id args).effects = [] ∧
    (observeEntry p prog id args).result = evalEntry p prog id args := ⟨rfl, rfl, rfl⟩
end DataConformance
'''
    return lean.encode()


class VSCore3KernelTests(unittest.TestCase):
    def test_string_feature_cannot_be_disabled(self):
        text = '''program "vscore/0.3" profile "data-pipeline/0.3";
fn count(value: String) -> Nat { String.length(value) }
entry count_empty() -> Nat { call count(String.append(string(), string())) }
'''
        prog = src.parse_surface(text)
        self.assertIn("string", src.required_features(prog))
        with self.assertRaisesRegex(src.SourceError, "unsupported required features: string"):
            src.check_program({}, prog, allowed_features=tuple(f for f in src.FEATURES if f != "string"))

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
