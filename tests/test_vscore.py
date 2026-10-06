"""VSCore 0.1 Tier 2: normative parsing and typing in the kernel, host/kernel agreement, library
audit, goal derivation and transfer, re-export, registered acceptance and the Tier 2 rejection suite
of docs/tier-2-4.md §7."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import EX, TempDir, codes, copy_pkg, run_cli, writable  # noqa: E402
from verislop import canonical, leanbridge, schemas  # noqa: E402
from verislop.bridges import prepare, vscore_checker as vc  # noqa: E402
from verislop.capabilities import capability  # noqa: E402
from verislop.exprjson import constants, name_str  # noqa: E402
from verislop.package import Package  # noqa: E402
from verislop.policy import BASELINE_AXIOMS  # noqa: E402
from verislop.targets import vscore_source as src, vscore_target as T  # noqa: E402

VS = EX / "vscore"
SOURCE = (VS / "program.vscore.json").read_bytes()
RELATION = (VS / "relation.json").read_bytes()
PROOF = (VS / "Proof.lean").read_bytes()
PROGRAM = canonical.loads(SOURCE)
ENUMS = {"IncrementError": ["limitReached"]}
BRIDGE = "bi-vscore"


def variant(edit) -> bytes:
    """Canonical bytes of an edited copy of the example program (still canonical JSON)."""
    obj = copy.deepcopy(PROGRAM)
    edit(obj)
    return canonical.dumps(obj)


def body(obj: dict) -> dict:
    return obj["entries"][0]["body"]


# Byte-level malformations: every one must be rejected by the kernel parser and the host proposal.
MALFORMED = {
    "whitespace": SOURCE.replace(b",", b", ", 1),
    "trailing_newline": SOURCE + b"\n",
    "two_documents": SOURCE + SOURCE,
    "empty": b"",
    "unsorted_keys": b'{"language":"vscore/0.1","entries":[]}',
    "duplicate_key": SOURCE.replace(b'"language":"vscore/0.1"', b'"language":"vscore/0.1","language":"vscore/0.1"'),
    "escape": SOURCE.replace(b'"increment"', b'"incr\\u0065ment"'),
    "non_ascii": SOURCE.replace(b'"increment"', '"incrément"'.encode()),
    "leading_zero_index": SOURCE.replace(b'"index":1', b'"index":01'),
    "negative_index": SOURCE.replace(b'"index":1', b'"index":-1'),
    "fraction_index": SOURCE.replace(b'"index":1', b'"index":1.0'),
    "null_value": SOURCE.replace(b'"value":"1"', b'"value":null'),
    "nat_as_json_number": SOURCE.replace(b'"value":"1"', b'"value":1'),
    "nat_leading_zero": SOURCE.replace(b'"value":"1"', b'"value":"01"'),
    "unknown_field": variant(lambda o: o["entries"][0].update({"zzz": 1})),
    "missing_field": variant(lambda o: o["entries"][0].pop("result")),
    "unsupported_while": variant(lambda o: body(o).update({"tag": "while"})),
    "unsupported_call": variant(lambda o: o["entries"][0].update(
        {"body": {"args": [], "entry": "increment", "tag": "call"}})),
    "wrong_language": variant(lambda o: o.update({"language": "vscore/0.2"})),
    "bad_identifier": variant(lambda o: o["entries"][0].update({"id": "1increment"})),
    "huge_integer": SOURCE.replace(b'"index":1', b'"index":9007199254740992'),
}

# Well-formed source that the static semantics must reject.
ILL_TYPED = {
    "no_entries": variant(lambda o: o.update({"entries": []})),
    "duplicate_entries": variant(lambda o: o.update({"entries": o["entries"] * 2})),
    "unbound_variable": variant(lambda o: body(o)["cond"].update({"right": {"index": 2, "tag": "var"}})),
    "add_bool": variant(lambda o: body(o)["then"]["value"].update({"right": {"tag": "bool", "value": True}})),
    "branch_types_differ": variant(lambda o: body(o).update({"else": {"tag": "nat", "value": "0"}})),
    "unknown_constructor": variant(lambda o: body(o)["else"]["value"].update({"ctor": "overflow"})),
    "unknown_enumeration": variant(lambda o: body(o)["else"]["value"].update({"enum": "Other"})),
    "declared_result_differs": variant(lambda o: o["entries"][0].update({"result": "nat"})),
    "condition_not_bool": variant(lambda o: body(o).update({"cond": {"tag": "nat", "value": "1"}})),
}

PROFILE_LEAN = 'def profile : VSCore.Profile := { enums := [("IncrementError", ["limitReached"])] }'


def lean_bytes(data: bytes) -> str:
    return "[" + ", ".join(str(b) for b in data) + "]"


def library_modules(tc, root: Path) -> tuple[dict, dict]:
    deps: dict[str, dict[str, str]] = {}
    modules: dict[str, dict[str, bytes]] = {}
    for m, source in T.library_sources().items():
        res, parts = leanbridge.compile_named_module(tc, root, m, source, dict(deps), read_only=[])
        if not res.ok:
            raise AssertionError(f"{m}: {res.errors}")
        modules[m] = parts
        deps[m] = {s: str(root / (leanbridge.module_relpath(m) + s)) for s in parts}
    return modules, deps


class HostProposalTests(unittest.TestCase):
    def test_example_round_trips_through_the_canonical_encoding(self):
        prog = src.parse_source(SOURCE)
        self.assertEqual(canonical.dumps(src.program_json(prog)), SOURCE)
        sigs = src.check_program(ENUMS, prog)
        self.assertEqual(sigs, [{"id": "increment", "params": ["nat", "nat"],
                                 "result": ("result", ("enum", "IncrementError"), "nat")}])
        self.assertEqual(schemas.validate("vscore-source", PROGRAM), [])

    def test_malformed_and_ill_typed_sources_are_rejected(self):
        for name, data in MALFORMED.items():
            with self.subTest(name=name), self.assertRaises(src.SourceError):
                src.parse_source(data)
        for name, data in ILL_TYPED.items():
            with self.subTest(name=name):
                prog = src.parse_source(data)
                with self.assertRaises(src.SourceError):
                    src.check_program(ENUMS, prog)

    def test_parse_command_is_advisory_and_fails_closed(self):
        tmp = TempDir()
        self.addCleanup(tmp.cleanup)
        profile = tmp.path / "profile.json"
        profile.write_bytes(canonical.dumps({"enums": {"IncrementError": {"constructors": ["limitReached"]}}}))
        code, result, _ = run_cli("vscore", "parse", "--package", str(tmp.path), "--source", str(VS / "program.vscore.json"),
                                  "--profile", str(profile))
        self.assertEqual(code, 0, result)
        self.assertIs(result["summary"]["authoritative"], False)
        self.assertEqual(canonical.dumps(result["summary"]["program"]), SOURCE)
        bad = tmp.path / "bad.json"
        bad.write_bytes(MALFORMED["whitespace"])
        code, result, _ = run_cli("vscore", "parse", "--package", str(tmp.path), "--source", str(bad), "--profile", str(profile))
        self.assertEqual(code, 2, result)
        self.assertIn("INVALID_CANDIDATE", codes(result))

    def test_lean_literals_quote_only_safe_strings(self):
        with self.assertRaises(src.SourceError):
            src.lean_string('a"b')
        with self.assertRaises(T.BridgeUnsupported):
            T.lean_component("a»b")
        self.assertEqual(T.lean_component("fun"), "«fun»")
        self.assertEqual(T.lean_name(["VeriSlopBridgeGoal", "impl_a.b-c"]), "VeriSlopBridgeGoal.«impl_a.b-c»")


class KernelSemanticsTests(unittest.TestCase):
    """The normative Lean parser, type checker and evaluator, evaluated by the kernel itself."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.tc = leanbridge.resolve_toolchain(leanbridge.DEFAULT_TOOLCHAIN)
        cls.modules, cls.deps = library_modules(cls.tc, cls.tmp.path / "lib")
        prog = src.parse_source(SOURCE)
        lines = ["import VSCore", "", "namespace VSCoreTests", "open VSCore", "", PROFILE_LEAN, "",
                 "def parsesOk (bs : List Nat) : Bool := match parseSource bs with | .ok _ => true | .error _ => false",
                 "def checksOk (bs : List Nat) : Bool :=",
                 "  match parseSource bs with",
                 "  | .ok p => (match checkProgram profile p with | .ok _ => true | .error _ => false)",
                 "  | .error _ => false",
                 "def returns (r : Except EvalError Value) (v : Value) : Bool :=",
                 "  match r with | .ok x => decide (x = v) | .error _ => false",
                 "def faults (r : Except EvalError Value) (e : EvalError) : Bool :=",
                 "  match r with | .error x => decide (x = e) | .ok _ => false",
                 "", "def program : Program :=", "  " + src.lean_program(prog), "",
                 f"theorem accepts_example : parseSource {lean_bytes(SOURCE)} = .ok program :=",
                 "  parseSource_of_check (by decide +kernel)",
                 "theorem checks_example : checkProgram profile program = .ok "
                 + src.lean_signatures(src.check_program(ENUMS, prog)) + " :=",
                 "  checkProgram_of_check (by decide +kernel)", ""]
        for name, data in MALFORMED.items():
            lines.append(f"theorem rejects_{name} : parsesOk {lean_bytes(data)} = false := by decide +kernel")
        for name, data in ILL_TYPED.items():
            lines.append(f"theorem ill_typed_{name} : parsesOk {lean_bytes(data)} = true ∧ "
                         f"checksOk {lean_bytes(data)} = false := by decide +kernel")
        nat, err = "Value.nat", 'Value.enum "IncrementError" "limitReached"'
        lines += [
            "",
            f"theorem eval_success : returns (evalEntry program \"increment\" [{nat} 5, {nat} 2]) (.ok ({nat} 3)) = true := by decide +kernel",
            f"theorem eval_limit : returns (evalEntry program \"increment\" [{nat} 5, {nat} 5]) (.error ({err})) = true := by decide +kernel",
            f"theorem eval_above_limit : returns (evalEntry program \"increment\" [{nat} 5, {nat} 9]) (.error ({err})) = true := by decide +kernel",
            f"theorem eval_arity : faults (evalEntry program \"increment\" [{nat} 5]) .arity = true := by decide +kernel",
            "theorem eval_unknown : faults (evalEntry program \"decrement\" []) .unknownEntry = true := by decide +kernel",
            "",
            "/-- Type soundness applied to the example: every typed call evaluates to a typed value. -/",
            "theorem example_total (a b : Nat) : ∃ v, evalEntry program \"increment\" [.nat a, .nat b] = .ok v ∧",
            "    HasType profile v (.result (.enum \"IncrementError\") .nat) := by",
            "  have hc := checkProgram_of_check (p := profile) (prog := program)",
            "    (expected := " + src.lean_signatures(src.check_program(ENUMS, prog)) + ") (by decide +kernel)",
            "  have he : findEntry program \"increment\" = some (program.entries.get ⟨0, by decide⟩) := by decide +kernel",
            "  exact checkProgram_sound hc he ((ArgsTypedIn.cons (.nat a) (.cons (.nat b) .nil)).toEnv)",
            "", "end VSCoreTests", ""]
        cls.text = "\n".join(lines)
        cls.result, cls.parts = leanbridge.compile_named_module(
            cls.tc, cls.tmp.path / "tests", "VSCoreTests", cls.text.encode(), dict(cls.deps),
            read_only=[cls.tmp.path / "lib"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_kernel_parser_typing_and_evaluator_agree_with_the_rejection_suite(self):
        self.assertTrue(self.result.ok, self.result.errors[:5])
        self.assertEqual(self.result.sorry_positions, [])

    def test_library_and_checks_replay_with_baseline_axioms_only(self):
        self.assertTrue(self.result.ok, self.result.errors[:5])
        modules = dict(self.modules)
        modules["VSCoreTests"] = self.parts
        resp = leanbridge.run_kernel_tool_modules(self.tc, modules, "VSCoreTests", {"export": True, "axioms": True})
        self.assertTrue(resp["replay"]["ok"], resp["replay"])
        theorems = {name_str(c["name"]): c for c in resp["constants"] if c.get("kind") == "theorem"}
        for required in ("VSCore.typeOf_sound", "VSCore.checkProgram_sound", "VSCore.evalEntry_deterministic",
                         "VSCore.parseSource_of_check", "VSCore.checkProgram_of_check", "VSCore.Adapter.enc_eq_iff",
                         "VSCore.Adapter.represents", "VSCoreTests.example_total", "VSCoreTests.rejects_escape"):
            self.assertIn(required, theorems)
        for name, c in theorems.items():
            axioms = {name_str(a) for a in c.get("axioms", [])}
            self.assertLessEqual(axioms, set(BASELINE_AXIOMS), name)
            self.assertEqual(c.get("unresolved_constants", []), [], name)
        skipped = [name_str(n) for n in resp["replay"]["not_replayed_unsafe_or_partial"]]
        self.assertTrue(all(n.endswith("._unsafe_rec") for n in skipped), skipped)


# A synthetic accepted profile with two symbols, used to test derivation without Lean.
PROFILE2 = {
    "profile_id": "two-symbols.v0_1", "dsl": "verislop.contract-dsl/0.1",
    "enums": {"E": {"constructors": ["a", "b"], "decl_hash": "sha256:" + "0" * 64,
                    "lean_constructors": ["T.E.a", "T.E.b"], "lean_decl": "T.E"}},
    "symbols": {
        "f": {"args": ["Nat"], "result": "Nat", "decl_hash": "sha256:" + "1" * 64, "lean_decl": "T.f", "level_params": []},
        "g": {"args": ["Nat"], "result": {"result": {"error": {"enum": "E"}, "ok": "Nat"}},
              "decl_hash": "sha256:" + "2" * 64, "lean_decl": "T.g", "level_params": []},
    },
    "predicates": {},
}
V = lambda i: {"tag": "var", "index": i}  # noqa: E731
CALL = lambda s, *a: {"tag": "call", "symbol": s, "args": list(a)}  # noqa: E731
OK = {"tag": "ok", "error_sort": {"enum": "E"}, "value": V(0)}
NESTED = {"tag": "forall", "sort": "Nat", "body": {"tag": "eq", "left": CALL("g", CALL("f", V(0))), "right": OK}}
F_SOURCE = canonical.dumps({"entries": [{"body": {"index": 0, "tag": "var"}, "id": "f", "params": ["nat"], "result": "nat"}],
                            "language": "vscore/0.1"})
FG_SOURCE = canonical.dumps({"entries": [
    {"body": {"index": 0, "tag": "var"}, "id": "f", "params": ["nat"], "result": "nat"},
    {"body": {"error_type": {"enum": "E"}, "tag": "ok", "value": {"index": 0, "tag": "var"}}, "id": "g", "params": ["nat"],
     "result": {"result": {"error": {"enum": "E"}, "ok": "nat"}}}], "language": "vscore/0.1"})


def relation(*bindings: tuple[str, str]) -> dict:
    return {"schema_version": "0.1", "format": T.RELATION_FORMAT, "template": T.TEMPLATE, "source_slot": "s",
            "proof_slot": "p", "bindings": [{"symbol": s, "entry": e} for s, e in bindings]}


def ob(formula: dict) -> dict:
    return {"N1": {"formula": formula, "lean_symbol": "T.n1", "statement_hash": "sha256:" + "3" * 64}}


class GoalDerivationTests(unittest.TestCase):
    def test_nested_calls_are_read_through_the_implementation_relations(self):
        spec = T.build_goal(FG_SOURCE, relation(("f", "f"), ("g", "g")), PROFILE2, ob(NESTED))
        e = spec.expected["Transfer_N1"]["value"]
        # ∀ x, ∀ r1, impl_f x r1 → ∀ r2, impl_g r1 r2 → r2 = ok x
        x = e["pi"]["body"]
        self.assertEqual(x["pi"]["body"]["pi"]["type"]["app"][0], T.gconst("impl_f"))
        self.assertEqual(x["pi"]["body"]["pi"]["type"]["app"][1:], [{"bvar": 1}, {"bvar": 0}])
        inner = x["pi"]["body"]["pi"]["body"]
        self.assertEqual(inner["pi"]["body"]["pi"]["type"]["app"], [T.gconst("impl_g"), {"bvar": 2}, {"bvar": 0}])
        used = constants(e)
        self.assertFalse({"T.f", "T.g"} & used, "a transfer statement must not mention the reference model")
        self.assertLessEqual({"VeriSlopBridgeGoal.impl_f", "VeriSlopBridgeGoal.impl_g"}, used)

    def test_multi_symbol_correspondence_cannot_be_omitted(self):
        with self.assertRaises(T.BridgeInvalid) as ctx:
            T.build_goal(F_SOURCE, relation(("f", "f")), PROFILE2, ob(NESTED))
        self.assertEqual(ctx.exception.code, "UNMAPPED_IMPLEMENTATION_OBJECT")

    def test_unbound_entries_and_signature_mismatches_are_rejected(self):
        with self.assertRaises(T.BridgeInvalid) as ctx:
            T.build_goal(FG_SOURCE, relation(("f", "f")), PROFILE2, ob(NESTED))
        self.assertEqual(ctx.exception.code, "UNMAPPED_IMPLEMENTATION_OBJECT")
        with self.assertRaises(T.BridgeInvalid) as ctx:
            T.build_goal(FG_SOURCE, relation(("f", "g"), ("g", "f")), PROFILE2, ob(NESTED))
        self.assertEqual(ctx.exception.code, "STATEMENT_MISMATCH")

    def test_formulas_without_a_transfer_rule_are_unsupported(self):
        no_call = {"tag": "forall", "sort": "Nat", "body": {"tag": "le", "left": V(0), "right": V(0)}}
        in_bound = {"tag": "forall", "sort": "Nat", "body": {"tag": "forall_range", "lower": {"tag": "nat", "value": "0"},
                                                             "upper": CALL("f", V(0)), "body": {"tag": "true"}}}
        for formula in (no_call, in_bound):
            with self.assertRaises(T.BridgeUnsupported):
                T.build_goal(F_SOURCE, relation(("f", "f")), PROFILE2, ob(formula))

    def test_relation_descriptor_is_closed_and_one_to_one(self):
        good = relation(("f", "f"), ("g", "g"))
        T.load_relation(canonical.dumps(good))
        for bad in (relation(("f", "f"), ("g", "f")), relation(("g", "g"), ("f", "f")),
                    {**good, "template": "vscore.other/0.1"}, {**good, "extra": True}):
            with self.assertRaises(T.BridgeInvalid):
                T.load_relation(canonical.dumps(bad))

    def test_statement_identity_detects_a_copied_model_statement(self):
        spec = T.build_goal(FG_SOURCE, relation(("f", "f"), ("g", "g")), PROFILE2, ob(NESTED))
        decls = {name_str(T.gname(k)): {"kind": "definition", "level_params": [], **v} for k, v in spec.expected.items()}
        self.assertEqual(T.statement_mismatches(spec, decls), [])
        model = T._Denoter(spec.profile).formula(NESTED, [])  # the reference reading, not the implementation's
        decls["VeriSlopBridgeGoal.Transfer_N1"]["value"] = model
        self.assertEqual(T.statement_mismatches(spec, decls), ["VeriSlopBridgeGoal.Transfer_N1"])


def accepted_run(root: Path) -> Path:
    runs = root / "runs"
    code, result, out = run_cli(
        "run", "--runs-dir", str(runs), "--run-id", "vscore", "--prompt-file", str(EX / "request.txt"),
        "--request-ref", "examples/request.txt", "--tier", "2", "--target", "vscore", "--endpoint", "restricted-source",
        "--draft-candidate", str(EX / "draft.json"), "--ledger-candidate", str(EX / "interpretation.json"),
        "--formalization-candidate", str(EX / "formalization"), "--non-interactive")
    package = runs / "vscore"
    if not (package / "accepted" / "accepted-ir.json").is_file():
        raise AssertionError((code, result, out))
    return package


def certificate_dir(package: Path, bridge: str = BRIDGE) -> Path:
    return package / "bridges" / bridge / "semantic" / vc.edge_key("reference-to-vscore")


class VSCoreBridgeFlowTests(unittest.TestCase):
    """End-to-end registered acceptance on a fresh accepted bounded-increment run."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.package = accepted_run(cls.tmp.path)
        cls.candidate = cls.tmp.path / "candidate"
        cls.goal = run_cli("vscore", "goal", "--package", str(cls.package), "--source", str(VS / "program.vscore.json"),
                           "--relation", str(VS / "relation.json"), "--proof", str(VS / "Proof.lean"),
                           "--out", str(cls.candidate), "--bridge-id", BRIDGE)
        cls.prepared = run_cli("bridge", "prepare", "--package", str(cls.package),
                               "--proposal", str(cls.candidate / "proposal.json"), "--candidate-dir", str(cls.candidate))
        cls.accepted = run_cli("bridge", "accept", "--package", str(cls.package), "--bridge-id", BRIDGE)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        for name in ("goal", "prepared", "accepted"):
            code, result, out = getattr(self, name)
            self.assertEqual(code, 0, (name, result, out))

    # -- positive release fixture -----------------------------------------------------------------

    def test_acceptance_certificate_reexport_and_two_builds(self):
        folder = certificate_dir(self.package)
        cert = canonical.load_file(folder / "certificate.json")
        self.assertEqual(schemas.validate("vscore-edge-certificate", cert), [])
        self.assertEqual([o["id"] for o in cert["obligations"]], ["E1", "I2", "O17"])
        self.assertEqual(cert["proposition_hash"], self.goal[1]["summary"]["proposition_hash"])
        self.assertLessEqual(set(cert["theorem"]["axioms"]), set(BASELINE_AXIOMS))
        self.assertIn("VeriSlopBridgeGoal.Transfer_E1", cert["statement_identity"])
        ir = canonical.load_file(folder / "implementation-ir.json")
        self.assertEqual(schemas.validate("vscore-implementation-ir", ir), [])
        self.assertEqual(canonical.dumps(ir["program"]), SOURCE)
        self.assertEqual(ir["bindings"][0]["lean_decl"], "VeriSlop.BoundedIncrement.increment")
        a, b = (canonical.load_file(folder / "builds" / f"{x}.json") for x in "AB")
        for key in vc.DETERMINISTIC:
            self.assertEqual(a[key], b[key], key)
        goal = (folder / "goal" / "VeriSlopBridgeGoal.lean").read_text()
        self.assertEqual(goal, (self.candidate / "VeriSlopBridgeGoal.lean").read_text())
        self.assertEqual(self.accepted[1]["summary"]["pending_semantic_claims"], [])

    def test_verify_reexecutes_the_checker_and_reports_acceptance(self):
        code, result, out = run_cli("bridge", "verify", "--package", str(self.package), "--bridge-id", BRIDGE)
        self.assertEqual(code, 0, (result, out))
        summary = result["summary"]
        self.assertTrue(summary["semantic_acceptance"])
        self.assertEqual(summary["pending_semantic_claims"], [])
        self.assertTrue(summary["semantic_certificates"][0]["rechecked"])
        self.assertIs(summary["assigns_end_to_end_verified"], False)

    def test_end_to_end_milestone_is_still_not_published(self):
        ok, why = capability(2, "vscore", "restricted_source")
        self.assertFalse(ok)
        self.assertIn("END_TO_END_VERIFIED", why)

    def test_acceptance_is_write_once(self):
        code, result, _ = run_cli("bridge", "accept", "--package", str(self.package), "--bridge-id", BRIDGE)
        self.assertEqual(code, 2, result)
        self.assertIn("INPUT_MUTATION", codes(result))

    # -- bindings of published acceptances ----------------------------------------------------------

    def recheck(self, mutate) -> set[str]:
        package = copy_pkg(self.package, self.tmp.path / f"copy-{self.id().rsplit('.', 1)[-1]}")
        mutate(package)
        checked = prepare.verify_preparation(Package(package, resolve_root=False), BRIDGE)
        self.assertNotEqual(checked.status, "PASS")
        return {d.code for d in checked.diagnostics}

    def test_source_mutation_after_acceptance_is_detected(self):
        def mutate(package: Path) -> None:
            path = package / "bridges" / BRIDGE / "candidate-inputs" / "program.vscore.json"
            writable(path)
            path.write_bytes(SOURCE.replace(b'"value":"1"', b'"value":"2"'))
        self.assertIn("INPUT_MUTATION", self.recheck(mutate))

    def test_forged_certificate_metadata_is_rejected(self):
        def mutate(package: Path) -> None:
            path = certificate_dir(package) / "certificate.json"
            cert = canonical.load_file(path)
            cert["proposition_hash"] = "sha256:" + "0" * 64
            writable(path)
            path.write_bytes(canonical.dumps(cert))
        self.assertIn("STATEMENT_MISMATCH", self.recheck(mutate))

    def test_tampered_reexported_ir_is_rejected(self):
        def mutate(package: Path) -> None:
            path = certificate_dir(package) / "implementation-ir.json"
            writable(path)
            path.write_bytes(path.read_bytes().replace(b'"value":"1"', b'"value":"2"'))
        self.assertIn("INPUT_MUTATION", self.recheck(mutate))

    def test_stale_checker_semantics_are_rejected(self):
        original = vc.verifier_hash
        vc.verifier_hash = lambda vid: "sha256:" + "f" * 64 if vid == vc.VERIFIER else original(vid)
        try:
            self.assertIn("STALE_OR_UNBOUND_EVIDENCE", self.recheck(lambda package: None))
        finally:
            vc.verifier_hash = original

    # -- frozen-bundle rejections -------------------------------------------------------------------

    def prepare_variant(self, bridge: str, edit) -> tuple[int, dict]:
        package = copy_pkg(self.package, self.tmp.path / f"pkg-{bridge}")
        cand = self.tmp.path / f"cand-{bridge}"
        cand.mkdir()
        for p in self.candidate.iterdir():
            (cand / p.name).write_bytes(p.read_bytes())
        proposal = canonical.loads((cand / "proposal.json").read_bytes())
        proposal["bridge_id"] = bridge
        edit(proposal, cand)
        (cand / "proposal.json").write_bytes(canonical.dumps(proposal))
        code, result, out = run_cli("bridge", "prepare", "--package", str(package),
                                    "--proposal", str(cand / "proposal.json"), "--candidate-dir", str(cand))
        self.assertEqual(code, 0, (result, out))
        code, result, _ = run_cli("bridge", "accept", "--package", str(package), "--bridge-id", bridge)
        return code, result

    def test_wrong_expected_proposition_is_rejected(self):
        def edit(proposal, cand):
            proposal["edges"][0]["expected_proposition_hash"] = "sha256:" + "1" * 64
        code, result = self.prepare_variant("wrong-hash", edit)
        self.assertEqual(code, 2, result)
        self.assertIn("STATEMENT_MISMATCH", codes(result))

    def test_wrong_enumeration_mapping_in_the_node_profile_is_rejected(self):
        def edit(proposal, cand):
            prof = canonical.loads((cand / "profile.json").read_bytes())
            prof["enums"][0]["constructors"] = ["overflow"]
            (cand / "profile.json").write_bytes(canonical.dumps(prof))
        code, result = self.prepare_variant("wrong-enum", edit)
        self.assertEqual(code, 2, result)
        self.assertIn("STATEMENT_MISMATCH", codes(result))

    def test_source_evidence_cannot_serve_a_native_endpoint(self):
        def edit(proposal, cand):
            proposal["tier"], proposal["endpoint"] = 4, "native_binary"
            proposal["nodes"][0]["kind"] = "native_binary"
        code, result = self.prepare_variant("native", edit)
        self.assertEqual(code, 2, result)
        self.assertIn("UNSUPPORTED_CAPABILITY", codes(result))

    # -- candidate rejections in one isolated build -------------------------------------------------

    def preview(self, source: bytes = SOURCE, proof: bytes | None = PROOF, rel: bytes = RELATION) -> set[str]:
        with self.assertRaises(vc.EdgeFailure) as ctx:
            vc.preview(Package(self.package, resolve_root=False), source, rel, proof)
        return {d.code for d in ctx.exception.diagnostics}

    def proof(self, body: str) -> bytes:
        return ("import VeriSlopBridgeGoal\n\nnamespace VeriSlopBridgeProof\n\n" + body + "\n\nend VeriSlopBridgeProof\n").encode()

    def test_sorry_is_unresolved(self):
        self.assertIn("PROOF_UNRESOLVED", self.preview(proof=self.proof("theorem edge : VeriSlopBridgeGoal.EdgeProp := sorry")))

    def test_candidate_axioms_and_native_evaluation_are_inadmissible(self):
        cheat = self.proof("axiom cheat : VeriSlopBridgeGoal.EdgeProp\ntheorem edge : VeriSlopBridgeGoal.EdgeProp := cheat")
        self.assertIn("INADMISSIBLE_AXIOM", self.preview(proof=cheat))
        text = PROOF.decode().replace(
            "VeriSlopBridgeGoal.edge_of_refines refines_increment",
            "have _h : (2 : Nat) + 2 = 4 := by native_decide\n  VeriSlopBridgeGoal.edge_of_refines refines_increment")
        self.assertIn("INADMISSIBLE_AXIOM", self.preview(proof=text.encode()))

    def test_a_weaker_statement_is_a_mismatch(self):
        self.assertIn("STATEMENT_MISMATCH", self.preview(proof=self.proof("theorem edge : True := trivial")))

    def test_proof_for_another_program_fails(self):
        plus_two = SOURCE.replace(b'"value":"1"', b'"value":"2"')
        swapped = SOURCE.replace(b'"left":{"index":0,"tag":"var"},"right":{"index":1,"tag":"var"},"tag":"lt"',
                                 b'"left":{"index":1,"tag":"var"},"right":{"index":0,"tag":"var"},"tag":"lt"')
        self.assertNotEqual(swapped, SOURCE)
        for source in (plus_two, swapped):
            self.assertIn("CANDIDATE_BUILD_FAILURE", self.preview(source=source))

    def test_unsupported_and_noncanonical_sources_are_rejected_before_building(self):
        for name in ("unsupported_while", "unsupported_call", "whitespace", "unsorted_keys"):
            with self.subTest(name=name):
                self.assertIn("INVALID_CANDIDATE", self.preview(source=MALFORMED[name]))

    def test_binding_to_a_missing_entry_is_rejected(self):
        rel = canonical.loads(RELATION)
        rel["bindings"][0]["entry"] = "inc"
        self.assertIn("UNMAPPED_IMPLEMENTATION_OBJECT", self.preview(rel=canonical.dumps(rel)))

    def test_a_structurally_different_equivalent_program_is_accepted(self):
        # let next = input + 1 in if input < limit then ok(next) else error(limitReached)
        def edit(o):
            b = body(o)
            b["cond"] = {"left": {"index": 1, "tag": "var"}, "right": {"index": 2, "tag": "var"}, "tag": "lt"}
            b["then"]["value"] = {"index": 0, "tag": "var"}
            o["entries"][0]["body"] = {"body": b, "tag": "let",
                                       "value": {"left": {"index": 0, "tag": "var"}, "right": {"tag": "nat", "value": "1"},
                                                 "tag": "add"}}
        source = variant(edit)
        spec, build, info = vc.preview(Package(self.package, resolve_root=False), source, RELATION, PROOF)
        self.assertNotEqual(info["proposition_hash"], self.goal[1]["summary"]["proposition_hash"])
        self.assertEqual(canonical.dumps(build.ir["program"]), source)


if __name__ == "__main__":
    unittest.main()
