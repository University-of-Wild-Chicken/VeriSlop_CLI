"""Real isolated 0.3 source reconstruction and trust-bound publication checks."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from verislop import canonical
from verislop.targets import vscore3_source as src, vscore3_check as checker

HEADER = 'program "vscore/0.3" profile "data-pipeline/0.3"; '
FIXTURE = HEADER + '''
record Cell { title:String; payload:Option(Int); }
variant Choice { empty; cell(Record(Cell)); }
fn adjust(x:Int)->Int{-x+Int.ofNat(2)}
entry integer(x:Int)->Int{Int.fdiv(call adjust(x),int(-3))}
entry trunc(x:Int)->Nat{Int.toNat(x)}
entry unicode()->String{string(955,128640)}
entry less(x:String,y:String)->Bool{x<y}
entry cell()->Variant(Choice){variant Choice.cell(record Cell{title="z",payload=some(-7)})}
entry inspect(x:Variant(Choice))->Option(Int){match x{variant Choice.empty()=>none[Int];variant Choice.cell(c)=>c.payload;}}
entry do_length(xs:List(Int))->Nat{List.length(xs)}
entry do_range()->List(Nat){List.range(3)}
entry do_get(xs:List(Int))->Option(Int){List.get(xs,1)}
entry do_append(xs:List(Int))->List(Int){List.append(xs,List.reverse(xs))}
entry do_sort(xs:List(String))->List(String){List.sort(xs)}
entry do_unique(xs:List(Bool))->List(Bool){List.unique(xs)}
entry do_map(xs:List(Int),offset:Int)->List(Int){List.map(xs;item=>item+offset)}
entry do_filter(xs:List(Int))->List(Int){List.filter(xs;item=>item<int(0))}
entry do_sum(xs:List(Int))->Int{List.sum(xs)}
entry do_fold(xs:List(Int))->Int{List.fold(xs,int(0);acc,item=>acc+item)}
entry count()->Int{Nat.fold(3,int(0);i,acc=>acc+Int.ofNat(i))}
entry result()->Result(Int,List(Int)){ok[Int](nil[Int])}
entry enum_identity(e:Enum(Color))->Enum(Color){e}
'''


class VSCore3SourceCheckTests(unittest.TestCase):
    def test_complete_source_reconstructs_after_two_clean_kernel_replays(self):
        registry = {"Color": ["red", "blue"]}
        program = src.parse_surface(FIXTURE, registry)
        data = src.source_bytes(program)
        with tempfile.TemporaryDirectory(prefix="verislop-vscore3-certificate-test-") as tmp:
            out = Path(tmp) / "certificate"
            result = checker.check(data, registry, out)
            self.assertEqual(result.status, "PASS", [d.to_json() for d in result.diagnostics])
            report = canonical.load_file(out / "report.json")
            ir = canonical.load_file(out / "implementation-ir.json")
            self.assertEqual(report["status"], "VERIFIED")
            self.assertEqual(report["input_root"], canonical.digest_json(report["inputs"]))
            self.assertEqual(report["builds"][0], report["builds"][1])
            self.assertEqual(set(report["builds"][0]["modules"]), {*checker.LIB_MODULES, checker.MODULE})
            self.assertEqual(ir["program"], src.program_json(program))
            self.assertEqual(ir["required_features"], list(src.FEATURES))
            self.assertEqual((out / "source.vscore.json").read_bytes(), data)
            self.assertFalse(report["assigns_obligation_milestones"])
            self.assertFalse(report["assigns_end_to_end_verified"])
            before = canonical.digest_file(out / "report.json")
            self.assertEqual(checker.check(data, registry, out).status, "BLOCKED")
            self.assertEqual(canonical.digest_file(out / "report.json"), before)

    def test_changed_library_and_nondeterminism_block_publication(self):
        data = src.compile_surface(HEADER + "entry run()->Int{int(0)}")
        tc = Mock()
        tc.identity.return_value = {"pin": "fixture toolchain"}
        build = checker.Build({"toolchain": tc.identity()}, {}, {})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "certificate"
            with patch.object(checker.leanbridge, "resolve_toolchain", return_value=tc), \
                 patch.object(checker, "library_sources", side_effect=[{"Library": b"original"}, {"Library": b"changed"}]), \
                 patch.object(checker, "run_build", return_value=build):
                result = checker.check(data, {}, out)
            self.assertEqual(result.status, "BLOCKED")
            self.assertIn("INPUT_MUTATION", {d.code for d in result.diagnostics})
            self.assertFalse(out.exists())
            different = checker.Build({"toolchain": tc.identity(), "changed": True}, {}, {})
            with patch.object(checker.leanbridge, "resolve_toolchain", return_value=tc), \
                 patch.object(checker, "run_build", side_effect=[build, different]):
                result = checker.check(data, {}, out)
            self.assertEqual(result.status, "BLOCKED")
            self.assertIn("NONDETERMINISM", {d.code for d in result.diagnostics})
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
