"""Independent grammar, exact wire and version-boundary regressions for 0.3."""
from __future__ import annotations

import json
import unittest

from verislop import schemas
from verislop.targets import vscore_source as v1, vscore2_source as v2, vscore2_check
from verislop.targets import vscore3_source as src

HEADER = 'program "vscore/0.3" profile "data-pipeline/0.3"; '


def parse(body, params="", result="Int", declarations=""):
    return src.parse_surface(HEADER + declarations + f"entry run({params})->{result}{{{body}}}")


class VSCore3FrontendTests(unittest.TestCase):
    def test_signed_literals_conversions_and_numeric_types(self):
        for body, want in (("-123", ("int", -123)), ("int(0)", ("int", 0)),
                           ("int(123)", ("int", 123)), ("int(-1)", ("int", -1))):
            with self.subTest(body=body):
                self.assertEqual(parse(body)["entries"][0]["body"], want)
        prog = parse("Int.fdiv(-7,int(3))+Int.ofNat(2)")
        self.assertEqual(src.check_program({}, prog)[0]["result"], "int")
        self.assertEqual(parse("Int.toNat(-3)", result="Nat")["entries"][0]["body"],
                         ("int_to_nat", ("int", -3)))
        self.assertEqual(parse("-x", "x:Int")["entries"][0]["body"], ("int_neg", ("var", 0)))
        self.assertEqual(parse("5-3-1", result="Nat")["entries"][0]["body"],
                         ("bin", "sub", ("bin", "sub", ("nat", 5), ("nat", 3)), ("nat", 1)))
        for body in ("-0", "int(-0)", "int(01)", "int(+1)", "int(1.0)", "-" + "1" * 1025):
            with self.subTest(body=body), self.assertRaises(src.SourceError):
                parse(body)
        for body in ("1+int(1)", "Int.fdiv(1,int(2))", "Int.toNat(1)", "Int.ofNat(int(1))", "-true"):
            with self.subTest(body=body), self.assertRaises(src.SourceError):
                parse(body)

    def test_unicode_scalars_and_fixed_scalar_comparison(self):
        prog = parse("string(0,955,128640,1114111)", result="String")
        self.assertEqual(prog["entries"][0]["body"], ("string", (0, 955, 128640, 1114111)))
        self.assertEqual(parse('"abc"', result="String")["entries"][0]["body"], ("string", (97, 98, 99)))
        self.assertEqual(parse("string()", result="String")["entries"][0]["body"], ("string", ()))
        for body in ('"a"<"b"', "-3<=int(0)", "int(0)==int(0)"):
            self.assertEqual(src.check_program({}, parse(body, result="Bool"))[0]["result"], "bool")
        for body in ("string(55296)", "string(57343)", "string(1114112)", "string(-1)", '"λ"', '"a\\b"'):
            with self.subTest(body=body), self.assertRaises(src.SourceError):
                parse(body, result="String")
        with self.assertRaises(src.SourceError):
            parse('"a"<1', result="Bool")

    def test_all_pure_list_nodes_and_exact_port_types(self):
        cases = (("List.length(xs)", "xs:List(Int)", "Nat", "list_length"),
                 ("List.range(3)", "", "List(Nat)", "list_range"),
                 ("List.get(xs,0)", "xs:List(Int)", "Option(Int)", "list_get"),
                 ("List.append(xs,xs)", "xs:List(Int)", "List(Int)", "list_append"),
                 ("List.reverse(xs)", "xs:List(Int)", "List(Int)", "list_reverse"),
                 ("List.sort(xs)", "xs:List(String)", "List(String)", "list_sort"),
                 ("List.unique(xs)", "xs:List(Bool)", "List(Bool)", "list_unique"))
        for body, params, result, tag in cases:
            with self.subTest(tag=tag):
                p = parse(body, params, result)
                self.assertEqual(p["entries"][0]["body"][0], tag)
                self.assertEqual(src.parse_source(src.source_bytes(p)), p)
        invalid = (("List.range(int(2))", "", "List(Nat)"),
                   ("List.get(xs,int(0))", "xs:List(Int)", "Option(Int)"),
                   ("List.append(xs,ys)", "xs:List(Int),ys:List(Nat)", "List(Int)"),
                   ("List.sort(xs)", "xs:List(Bool)", "List(Bool)"),
                   ("List.unique(xs)", "xs:List(Option(Int))", "List(Option(Int))"),
                   ("List.length(int(3))", "", "Nat"),
                   ("List.sort(xs,xs)", "xs:List(Int)", "List(Int)"))
        for body, params, result in invalid:
            with self.subTest(body=body), self.assertRaises(src.SourceError):
                parse(body, params, result)

    def test_list_binders_preserve_ambient_scope_and_sum_types(self):
        p = parse("List.map(xs;item=>item+offset)", "xs:List(Int),offset:Int", "List(Int)")
        self.assertEqual(p["entries"][0]["body"], ("list_map", ("var", 1), ("bin", "add", ("var", 0), ("var", 1))))
        for body, result in (("List.filter(xs;item=>item<int(0))", "List(Int)"),
                             ("List.map(xs;item=>some(item))", "List(Option(Int))"),
                             ("List.sum(xs)", "Int")):
            p = parse(body, "xs:List(Int)", result)
            self.assertEqual(src.parse_source(src.source_bytes(p)), p)
            self.assertFalse(schemas.validate("vscore-source-v3", src.program_json(p)))
        for body, params, result in (("List.filter(xs;item=>item)", "xs:List(Int)", "List(Int)"),
                                     ("List.map(int(1);item=>item)", "", "Int"),
                                     ("List.sum(xs)", "xs:List(String)", "String"),
                                     ("List.map(xs;item=>missing)", "xs:List(Int)", "List(Int)")):
            with self.subTest(body=body), self.assertRaises(src.SourceError):
                parse(body, params, result)

    def test_scopes_aggregates_and_feature_inventory(self):
        p = src.parse_surface(HEADER + '''record Cell { text:String; value:Int; }
fn unused(xs:List(Option(Int)))->Nat{List.length(xs)}
entry run(xs:List(Record(Cell)))->Int{
  List.fold(xs,int(0);acc,item=>acc+item.value)
}
entry counters()->Int{Nat.fold(2,int(0);i,acc=>acc+Int.ofNat(i))}
''')
        self.assertEqual(p["entries"][0]["body"][3],
                         ("bin", "add", ("var", 1), ("project", ("var", 0), "value")))
        self.assertEqual(src.required_features(p), ["base", "nominalData", "option", "list", "listFold", "natFold", "int", "string", "pureList"])
        with self.assertRaisesRegex(src.SourceError, "unsupported required features"):
            src.check_program({}, p, ["base"])
        for source in ('record Bad{next:List(Record(Bad));} entry run()->Int{int(0)}',
                       'fn loop()->Int{if false then call loop() else int(0)} entry run()->Int{int(0)}'):
            with self.assertRaisesRegex(src.SourceError, "cyclic"):
                src.parse_surface(HEADER + source)

    def test_closed_canonical_numeric_and_scalar_wire(self):
        p = parse("-1")
        data = src.source_bytes(p)
        self.assertEqual(src.parse_source(data), p)
        for literal in ("-0", "+1", "01", "-01", "1e2", "1.0", "-" + "1" * 1025):
            obj = src.program_json(p)
            obj["entries"][0]["body"]["value"] = literal
            with self.subTest(literal=literal), self.assertRaises(src.SourceError):
                src.parse_source(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode())
        p = parse("string(955)", result="String")
        for value in ([True], [-1], [55296], [57343], [1114112], [1.5], "955"):
            obj = src.program_json(p)
            obj["entries"][0]["body"]["value"] = value
            with self.subTest(value=value):
                with self.assertRaises(src.SourceError):
                    src.parse_source(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode())
                self.assertTrue(schemas.validate("vscore-source-v3", obj))
        for raw in (data+b"\n", data.replace(b",", b", ", 1), data.replace(b'"value":"-1"', b'"value":"-1","z":0')):
            with self.assertRaises(src.SourceError):
                src.parse_source(raw)

    def test_versions_do_not_fall_back_or_expand_old_languages(self):
        p3 = parse("int(3)")
        d3 = src.source_bytes(p3)
        self.assertIs(vscore2_check.source_module(d3), src)
        for old in (v1, v2):
            with self.assertRaises(old.SourceError):
                old.parse_source(d3)
        p2 = v2.parse_surface('program "vscore/0.2" profile "pure-data/0.2"; entry run()->Nat{3}')
        self.assertIs(vscore2_check.source_module(v2.source_bytes(p2)), v2)
        with self.assertRaises(src.SourceError):
            src.parse_source(v2.source_bytes(p2))
        with self.assertRaises(vscore2_check.UnsupportedSource):
            vscore2_check.source_module(d3.replace(b"vscore/0.3", b"vscore/9.9"))

    def test_schema_and_lean_literals_preserve_nominal_scalar_wire(self):
        p = parse('record Cell{text=string(955),value=-5}', result="Record(Cell)",
                  declarations="record Cell{text:String;value:Int;}")
        self.assertEqual(schemas.validate("vscore-source-v3", src.program_json(p)), [])
        lean = src.lean_program(p)
        self.assertIn("VSCore3.Expr.string [ 955]", lean.replace("\n    ", " "))
        self.assertIn("VSCore3.Expr.int (Int.negSucc 4)", lean)
        self.assertIn("VSCore3.Ty.string", lean)
        self.assertIn("VSCore3.DataDecl.record", lean)


if __name__ == "__main__":
    unittest.main()
