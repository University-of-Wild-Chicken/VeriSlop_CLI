"""Concrete grammar/elaboration/admission regressions. Host checks are not certificates."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from verislop.jsonschema_lite import Registry
from verislop.targets import vscore2_source as s

ROOT = Path(__file__).resolve().parents[1]
HEADER = 'program "vscore/0.2" profile "pure-data/0.2";\n'


def parse(body: str, enums=None):
    return s.parse_surface(HEADER + body, enums)


def entry(body: str, params="", result="Nat"):
    return parse(f"entry run({params}) -> {result} {{ {body} }}")


def bytes_of_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("ascii")


class VSCore2FrontendTests(unittest.TestCase):
    def reject(self, code: str, error: str | None = None):
        with self.assertRaises(s.SourceError) as caught:
            parse(code)
        if error:
            self.assertIn(error, str(caught.exception))

    def test_existing_examples_compile_to_closed_canonical_json(self):
        reg = Registry()
        sid = reg.add(json.loads((ROOT / "schemas/vscore-source-v2.schema.json").read_text()))
        for name in ("pure-data", "ordering"):
            with self.subTest(example=name):
                prog = s.parse_surface((ROOT / f"examples/vscore-grammar/{name}.vsc").read_text())
                data = s.source_bytes(prog)
                self.assertEqual(s.parse_source(data), prog)
                self.assertEqual(reg.validate(s.program_json(prog), sid), [])
                self.assertEqual(s.compile_surface((ROOT / f"examples/vscore-grammar/{name}.vsc").read_text()), data)

    def test_parameters_arguments_and_shadowing_use_frozen_binder_order(self):
        p = parse("fn diff(a:Nat,b:Nat)->Nat{a-b}\nentry run(x:Nat,y:Nat)->Nat{let x=y+1;x-y}")
        self.assertEqual(p["helpers"][0]["body"], ("bin", "sub", ("var", 1), ("var", 0)))
        self.assertEqual(p["entries"][0]["body"], ("let", ("bin", "add", ("var", 0), ("nat", 1)), ("bin", "sub", ("var", 0), ("var", 1))))
        p = parse("fn diff(a:Nat,b:Nat)->Nat{a-b} entry run()->Nat{call diff(5,2)}")
        self.assertEqual(p["entries"][0]["body"], ("call", "diff", [("nat", 5), ("nat", 2)]))

    def test_fold_binders_and_outer_scope_are_preserved(self):
        p = entry("List.fold(list[Nat](1,2), 0; acc,item=>let y=acc;item+y)")
        fold = p["entries"][0]["body"]
        self.assertEqual(fold[3], ("let", ("var", 1), ("bin", "add", ("var", 1), ("var", 0))))
        self.assertEqual(fold[1], ("cons", ("nat", 1), ("cons", ("nat", 2), ("nil", "nat"))))
        p = entry("Nat.fold(3,x;index,acc=>acc*10+index+x)", "x:Nat")
        self.assertEqual(p["entries"][0]["body"][3], ("bin", "add", ("bin", "add", ("bin", "mul", ("var", 0), ("nat", 10)), ("var", 1)), ("var", 2)))

    def test_match_payload_binders_are_reverse_written_order(self):
        p = parse("variant Pair { pair(Nat,Bool); } entry run(p:Variant(Pair),x:Nat)->Nat{match p{variant Pair.pair(n,b)=>if b then n+x else 0;}}")
        body = p["entries"][0]["body"][2][0][1]
        self.assertEqual(body, ("ite", ("var", 0), ("bin", "add", ("var", 1), ("var", 2)), ("nat", 0)))
        p = entry("match xs{nil=>none[Nat];cons(h,t)=>some(h);}", "xs:List(Nat)", "Option(Nat)")
        self.assertEqual(p["entries"][0]["body"][3], ("some", ("var", 1)))

    def test_nat_precision_precedence_and_left_associativity(self):
        self.assertEqual(entry("18446744073709551617")["entries"][0]["body"], ("nat", 18446744073709551617))
        self.assertEqual(entry("5-3-1")["entries"][0]["body"], ("bin", "sub", ("bin", "sub", ("nat", 5), ("nat", 3)), ("nat", 1)))
        self.assertEqual(entry("1+2*3")["entries"][0]["body"], ("bin", "add", ("nat", 1), ("bin", "mul", ("nat", 2), ("nat", 3))))
        self.reject("entry run()->Bool{1<2<3}")
        self.reject("entry run()->Bool{true==false==true}")

    def test_identifiers_are_opaque_with_quoted_keywords(self):
        p = parse('record @"Record"{@"if":Nat;} entry @"legacy.name-with-hyphen"(@"let":Nat)->Nat{let @"x.y"=@"let";record @"Record"{@"if"=@"x.y"}.@"if"}')
        self.assertEqual(p["entries"][0]["id"], "legacy.name-with-hyphen")
        self.assertEqual(p["entries"][0]["body"][2][2], "if")
        self.reject('entry run(if:Nat)->Nat{if}')
        self.reject('entry x()->Nat{0} entry @"x"()->Nat{0}', "duplicate function")

    def test_enum_registry_is_external_and_nominal_names_cannot_collide(self):
        p = s.parse_surface(HEADER+"entry run()->Bool{enum(E,a)==enum(E,a)}", {"E": ["a"]})
        self.assertEqual(s.check_program({"E": ["a"]}, p)[0]["result"], "bool")
        with self.assertRaises(s.SourceError):
            s.parse_surface(HEADER+"record E{} entry run()->Nat{0}", {"E": ["a"]})
        self.reject("entry run()->Enum(E){enum(E,a)}", "ill-formed signature")

    def test_unused_invalid_enumeration_registries_are_rejected(self):
        p = entry("0")
        for registry in ({"E": []}, {"E": ["a", "a"]}, {"1E": ["a"]},
                         {"E": ["not valid"]}, {"E": [1]}, {"E": "a"}, []):
            with self.subTest(registry=registry):
                with self.assertRaises(s.SourceError):
                    s.check_program(registry, p)
                with self.assertRaises(s.SourceError):
                    s.parse_surface(HEADER+"entry run()->Nat{0}", registry)

    def test_forward_helper_and_nominal_references_are_resolved(self):
        p = parse("record Outer{item:Record(Inner);} record Inner{n:Nat;} fn first(n:Nat)->Nat{call second(n)} fn second(n:Nat)->Nat{n+1} entry run()->Nat{call first(0)}")
        self.assertEqual(s.check_program({}, p)[0]["result"], "nat")

    def test_cycles_are_rejected_even_behind_option_list_and_dead_branches(self):
        self.reject("record Bad{next:Option(List(Record(Bad)));} entry run()->Nat{0}", "cyclic nominal")
        self.reject("record A{x:Variant(B);} variant B{b(Result(Nat,Record(A)));} entry run()->Nat{0}", "cyclic nominal")
        self.reject("fn loop()->Nat{if false then call loop() else 0} entry run()->Nat{0}", "cyclic helper")
        self.reject("fn a()->Nat{call b()} fn b()->Nat{call a()} entry run()->Nat{0}", "cyclic helper")
        self.reject("fn loop()->Nat{Nat.fold(0,0;i,a=>call loop())} entry run()->Nat{0}", "cyclic helper")

    def test_entries_cannot_be_called_and_helper_arity_types_are_exact(self):
        self.reject("entry one()->Nat{1} entry run()->Nat{call one()}", "declared helper")
        self.reject("fn x(n:Nat)->Nat{n} entry run()->Nat{call x()}", "arity")
        self.reject("fn x(n:Nat)->Nat{n} entry run()->Nat{call x(true)}", "types")
        self.reject("fn x(n:Nat,n:Nat)->Nat{n} entry run()->Nat{0}", "duplicate parameter")

    def test_records_reject_missing_duplicate_reordered_and_bad_field_types(self):
        decl = "record Pair{a:Nat;b:Nat;} "
        for fields in ("a=1", "a=1,a=2", "b=2,a=1", "a=true,b=1"):
            with self.subTest(fields=fields):
                self.reject(decl+"entry run()->Record(Pair){record Pair{"+fields+"}}")
        self.reject(decl+"entry run(p:Record(Pair))->Nat{p.c}", "unknown record field")
        self.reject("record A{} record B{} entry run()->Bool{record A{}==record B{}}", "operand types differ")

    def test_variants_enforce_nominal_identity_payload_arity_and_exhaustive_order(self):
        decl = "variant V{noneC;someC(Nat,Bool);} "
        for expression in ("variant V.someC(1)", "variant V.someC(true,1)", "variant V.absent()"):
            with self.subTest(expr=expression):
                self.reject(decl+f"entry run()->Variant(V){{{expression}}}")
        for branches in (
            "variant V.noneC()=>0;", "variant V.someC(n,b)=>n;variant V.noneC()=>0;",
            "variant V.noneC()=>0;variant V.someC(n)=>n;", "variant V.noneC()=>0;variant V.someC(n,n)=>n;",
            "variant W.noneC()=>0;variant V.someC(n,b)=>n;"):
            with self.subTest(branches=branches):
                self.reject(decl+"entry run(v:Variant(V))->Nat{match v{"+branches+"}}")
        self.reject("variant Empty{} entry run()->Nat{0}", "at least one constructor")

    def test_builtin_matches_have_exact_order_and_bindings(self):
        self.reject("entry run(x:Option(Nat))->Nat{match x{some(n)=>n;none=>0;}}", "branch order")
        self.reject("entry run(x:List(Nat))->Nat{match x{nil=>0;cons(n,n)=>n;}}", "duplicate pattern")
        self.reject("entry run(x:Result(Nat,Nat))->Nat{match x{ok(n)=>n;error(e)=>true;}}", "branch types")
        self.reject("entry run(x:Nat)->Nat{match x{none=>0;some(n)=>n;}}", "match requires")

    def test_fold_source_initial_and_step_are_checked(self):
        for code in ("List.fold(1,0;a,x=>a+x)", "Nat.fold(true,0;i,a=>a+i)", "Nat.fold(0,0;i,a=>true)", "List.fold(nil[Nat],0;a,a=>a)"):
            with self.subTest(code=code):
                self.reject(f"entry run()->Nat{{{code}}}")
        self.reject("entry run()->Nat{Nat.fold(0,0;i,a=>if false then true else a)}")
        self.reject("entry run()->List(Nat){cons(true,nil[Nat])}", "homogeneous")

    def test_features_include_signatures_unused_helpers_and_unreachable_branches(self):
        p = parse("fn unused(x:Option(Nat))->Nat{0} entry run(xs:List(Nat))->Nat{if false then Nat.fold(0,0;i,a=>a) else 0}")
        self.assertEqual(s.required_features(p), ["base", "option", "list", "natFold"])
        with self.assertRaisesRegex(s.SourceError, "unsupported required features"):
            s.check_program({}, p, ["base"])
        p = entry("ok[List(Option(Nat))](0)", result="Result(List(Option(Nat)),Nat)")
        self.assertEqual(s.required_features(p), ["base", "option", "list"])

    def test_exact_wire_closure_and_scalar_numeric_distinctions(self):
        p = entry("x", "x:Nat")
        data = s.source_bytes(p)
        malformed = [data+b"\n", data.replace(b',', b', ', 1), data.replace(b'"index":0', b'"index":true'),
                     data.replace(b'"index":0', b'"index":9007199254740992'), data.replace(b'"index":0', b'"index":00'),
                     data.replace(b'"run"', b'"r\\u0075n"'), data.replace(b'"run"', '"rún"'.encode()),
                     data.replace(b'"language":"vscore/0.2"', b'"language":"vscore/0.2","language":"vscore/0.2"')]
        obj = s.program_json(p)
        obj["entries"][0]["body"]["extra"] = False
        malformed.append(bytes_of_json(obj))
        for raw in malformed:
            with self.subTest(raw=raw[:150]):
                with self.assertRaises(s.SourceError):
                    s.parse_source(raw)
        p = entry("none[Nat]", result="Option(Nat)")
        obj = s.program_json(p)
        obj["entries"][0]["body"] = {"tag": "none", "type": "nat"}
        with self.assertRaises(s.SourceError):
            s.parse_source(bytes_of_json(obj))

    def test_lexical_and_resource_rejections_are_explicit(self):
        for code in ("entry run()->Nat{01}", "entry run()->Nat{-1}", "entry run()->Nat{1.0}", "entry run()->Nat{1e2}", 'entry @"a\\b"()->Nat{0}', "entry café()->Nat{0}"):
            with self.subTest(code=code):
                self.reject(code)
        self.reject("entry run()->Nat{" + "1" * 1025 + "}")
        self.reject("entry run()->Bool{" + "not " * 300 + "true}", "depth")
        self.reject("entry run()->Nat{0} fn late()->Nat{1}", "precede")
        self.reject("entry run()->Nat{x}", "unbound local")
        self.reject("entry run()->Nat{let x=x;x}", "unbound local")

    def test_unknown_nominal_references_are_diagnostics_before_pattern_elaboration(self):
        self.reject("entry run(x:Variant(Missing))->Nat{match x{variant Missing.c()=>0;}}", "ill-formed signature")
        self.reject("record A{next:Variant(Missing);} entry run(a:Record(A))->Nat{match a.next{variant Missing.c()=>0;}}", "ill-formed declaration")

    def test_host_inferred_signatures_are_closed_entry_interfaces(self):
        p = entry("0")
        sig = s.check_program({}, p)[0]
        self.assertEqual(sig, {"id": "run", "params": [], "result": "nat"})
        self.assertNotIn("body", sig)
        self.assertIn("VSCore2.Expr.nat", s.lean_program(p))
        self.assertIn("VSCore.BinOp.add", s.lean_program(entry("1+2")))
        self.assertEqual(s.lean_signature(sig), '{ id := "run", params := [], result := VSCore2.Ty.nat }')


if __name__ == "__main__":
    unittest.main()
