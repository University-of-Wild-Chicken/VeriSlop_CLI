"""Finite host/kernel conformance fixtures for exact 0.2 decoding and admission.

These fixtures check examples and counterexamples; they do not certify the host frontend
or connect a program to an accepted natural-language contract.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from verislop import leanbridge
from verislop.targets import vscore2_source as src

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("VSCore.Syntax", "VSCore.Decode", "VSCore2.Syntax", "VSCore2.Equality", "VSCore2.Decode",
           "VSCore2.Typed", "VSCore2.Typing", "VSCore2.Semantics", "VSCore2.Proofs", "VSCore2.Transport", "VSCore2")


def nat(n):
    return ("nat", n)


def program(body, result="nat"):
    return {"language": src.LANGUAGE, "profile": src.PROFILE, "declarations": [], "helpers": [],
            "entries": [{"id": "run", "params": [], "result": result, "body": body}]}


def negative_programs():
    cases = []
    p = program(nat(0)); p["entries"] = []; cases.append(("no_entries", p))
    p = program(("ite", ("bool", False), ("bin", "add", ("bool", True), nat(1)), nat(0))); cases.append(("hidden_bad_type", p))
    p = program(nat(0)); p["helpers"] = [{"id": "loop", "params": [], "result": "nat", "body": ("ite", ("bool", False), ("call", "loop", []), nat(0))}]; cases.append(("hidden_self_call", p))
    p = program(nat(0)); p["helpers"] = [{"id": "loop", "params": [], "result": "nat", "body": ("nat_fold", nat(0), nat(0), ("call", "loop", []))}]; cases.append(("fold_self_call", p))
    cases.append(("entry_call", program(("call", "run", []))))
    p = program(nat(0)); p["declarations"] = [{"tag": "record", "id": "Bad", "fields": [("next", ("option", ("list", ("record", "Bad"))))]}]; cases.append(("nominal_cycle", p))
    p = program(("record", "Pair", [("b", nat(2)), ("a", nat(1))]), ("record", "Pair")); p["declarations"] = [{"tag": "record", "id": "Pair", "fields": [("a", "nat"), ("b", "nat")]}]; cases.append(("record_order", p))
    p = program(("match_variant", ("variant", "V", "c", []), [("d", nat(1)), ("c", nat(0))])); p["declarations"] = [{"tag": "variant", "id": "V", "constructors": [("c", []), ("d", [])]}]; cases.append(("variant_order", p))
    p = program(("variant", "V", "c", [nat(0)]), ("variant", "V")); p["declarations"] = [{"tag": "variant", "id": "V", "constructors": [("c", [])]}]; cases.append(("variant_arity", p))
    cases.append(("heterogeneous_cons", program(("cons", ("bool", True), ("nil", "nat")), ("list", "nat"))))
    cases.append(("fold_type", program(("list_fold", ("nil", "nat"), nat(0), ("bool", True)))))
    return cases


def source_fixture():
    valid = [src.parse_surface((ROOT / f"examples/vscore-grammar/{name}.vsc").read_text()) for name in ("pure-data", "ordering")]
    valid.append(src.parse_surface('program "vscore/0.2" profile "pure-data/0.2"; record @"Record"{@"if":Nat;} entry @"legacy.name-with-hyphen"(@"let":Nat)->Nat{let @"x.y"=@"let";record @"Record"{@"if"=@"x.y"}.@"if"}'))
    valid.append(src.parse_surface('program "vscore/0.2" profile "pure-data/0.2"; record Outer{item:Record(Inner);} record Inner{n:Nat;} fn first(n:Nat)->Nat{call second(n)} fn second(n:Nat)->Nat{n+1} entry run()->Nat{call first(0)}'))
    text = 'import VSCore2\nset_option maxRecDepth 100000\nset_option maxHeartbeats 20000000\ndef profile : VSCore2.Profile := {enums := []}\ndef rejected {α : Type} (r : Except String α) : Bool := match r with | .error _ => true | .ok _ => false\n'
    for i, prog in enumerate(valid):
        data = src.source_bytes(prog)
        sigs = src.check_program({}, prog)
        text += f'def prog{i} : VSCore2.Program := ' + src.lean_program(prog) + '\n'
        text += f'example : VSCore2.parseSource [{",".join(map(str, data))}] = .ok prog{i} := by rfl\n'
        text += f'example : VSCore2.checkProgram profile prog{i} = .ok ' + src.lean_signatures(sigs) + ' := VSCore2.checkProgram_of_check (by decide +kernel)\n'
    for name, prog in negative_programs():
        try:
            src.check_program({}, prog)
        except src.SourceError:
            pass
        else:
            raise AssertionError(f"host accepted counterexample {name}")
        text += f'-- {name}\nexample : rejected (VSCore2.checkProgram profile ' + src.lean_program(prog) + ') = true := by decide +kernel\n'
    wire = src.source_bytes(valid[0])
    malformed = [wire+b'\n', wire.replace(b',', b', ', 1),
        wire.replace(b'"language":"vscore/0.2"', b'"language":"vscore/0.2","language":"vscore/0.2"'),
        wire.replace(b'"profile":"pure-data/0.2"', b'"profile":"pure-data/0.2","z":0'),
        src.source_bytes(program(("none", "nat"), ("option", "nat"))).replace(b'element_type', b'type')]
    for data in malformed:
        try:
            src.parse_source(data)
        except src.SourceError:
            pass
        else:
            raise AssertionError("host accepted malformed source")
        text += 'example : rejected (VSCore2.parseSource [' + ','.join(map(str, data)) + ']) = true := by decide +kernel\n'
    for enums in ({"E": []}, {"E": ["a", "a"]}, {"1E": ["a"]}, {"E": ["invalid ctor"]}):
        try:
            src.check_program(enums, program(nat(0)))
        except src.SourceError:
            pass
        else:
            raise AssertionError("host accepted invalid unused enum registry")
        profile = '{enums := [' + ', '.join('(' + src.lean_string(k) + ',[' + ', '.join(src.lean_string(c) for c in cs) + '])' for k, cs in enums.items()) + ']}'
        text += 'example : rejected (VSCore2.checkProgram ' + profile + ' ' + src.lean_program(program(nat(0))) + ') = true := by decide +kernel\n'
    valid_equality = src.parse_surface('''program "vscore/0.2" profile "pure-data/0.2";
record R { xs: List(Option(Nat)); }
variant V { lost; found(Record(R)); }
entry same_record() -> Bool {
  record R {xs = list[Option(Nat)](none[Nat], some(3))} ==
  record R {xs = list[Option(Nat)](none[Nat], some(3))}
}
entry different_list() -> Bool { list[Nat](1,2) == list[Nat](2,1) }
entry same_variant() -> Bool {
  variant V.found(record R {xs = nil[Option(Nat)]}) ==
  variant V.found(record R {xs = nil[Option(Nat)]})
}
entry different_constructor() -> Bool {
  variant V.lost() == variant V.found(record R {xs = nil[Option(Nat)]})
}
entry different_result() -> Bool { ok[Nat](7) == error[Nat](7) }
entry same_option() -> Bool { none[Nat] == none[Nat] }
''')
    text += 'def equalityProgram : VSCore2.Program := ' + src.lean_program(valid_equality) + '\n'
    text += 'example : VSCore2.checkProgram profile equalityProgram = .ok ' + src.lean_signatures(src.check_program({}, valid_equality)) + ' := VSCore2.checkProgram_of_check (by decide +kernel)\n'
    return text


def semantic_fixture():
    text = 'import VSCore2.Semantics\nimport SourceConformance\nset_option maxRecDepth 100000\nset_option maxHeartbeats 20000000\n'
    values = [(0, "pair_difference", "[]", ".nat 3"),
        (0, "sum", "[.cons (.nat 1) (.cons (.nat 2) .nil)]", ".nat 3"),
        (0, "lookup_or_zero", '[.variant "Lookup" "present" [.nat 7]]', ".nat 7"),
        (0, "option_or_zero", "[.some (.nat 9)]", ".nat 9"),
        (0, "head", "[.cons (.nat 8) .nil]", ".some (.nat 8)"),
        (1, "call_order", "[]", ".nat 3"), (1, "associativity", "[]", ".nat 1"),
        (1, "list_order", "[]", ".nat 12"), (1, "nat_order", "[]", ".nat 12"),
        (1, "fold_scope", "[]", ".nat 3"), (1, "shadowing", "[.nat 2,.nat 7]", ".nat 15"),
        (1, "result_payload", "[.nat 10]", ".nat 15"),
        (1, "exact_natural", "[]", ".nat 18446744073709551617"),
        (1, "legacy.id-with-hyphen", "[.nat 5]", ".nat 5")]
    for i, entry, args, value in values:
        text += f'example : VSCore2.evalEntry profile prog{i} "{entry}" {args} = .ok ({value}) := by with_unfolding_all rfl\n'
    for i, entry, args, error in [(0, "sum", "[.cons (.bool true) .nil]", "invalidArguments"),
        (0, "lookup_or_zero", '[.variant "Lookup" "present" []]', "invalidArguments"),
        (0, "head", "[]", "invalidArguments"), (0, "missing", "[]", "unknownEntry")]:
        text += f'example : VSCore2.evalEntry profile prog{i} "{entry}" {args} = .error .{error} := by with_unfolding_all rfl\n'
    for name, value in (("same_record", "true"), ("different_list", "false"),
                        ("same_variant", "true"), ("different_constructor", "false"),
                        ("different_result", "false"), ("same_option", "true")):
        text += f'example : VSCore2.evalEntry profile equalityProgram "{name}" [] = .ok (.bool {value}) := by with_unfolding_all rfl\n'
    return text


class VSCore2KernelConformanceTests(unittest.TestCase):
    def test_exact_source_checker_and_semantic_conformance(self):
        tc = leanbridge.resolve_toolchain()
        with tempfile.TemporaryDirectory(prefix="verislop-vscore2-kernel-test-") as tmp:
            root = Path(tmp)
            env = {**os.environ, "LEAN_PATH": str(root)}
            for module in MODULES:
                rel = Path(module.replace(".", "/") + ".lean")
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((ROOT / "verislop/lean" / rel).read_bytes())
                self.compile(tc, root, env, path, output=path.with_suffix(".olean"))
            source = root / "SourceConformance.lean"
            source.write_text(source_fixture())
            self.compile(tc, root, env, source, output=source.with_suffix(".olean"))
            semantics = root / "SemanticConformance.lean"
            semantics.write_text(semantic_fixture())
            self.compile(tc, root, env, semantics)

    def compile(self, tc, root, env, path, output=None):
        command = [str(tc.lean)]
        if output:
            command += ["-o", str(output)]
        command += [str(path)]
        result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("declaration uses 'sorry'", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
