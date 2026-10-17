"""Generic Unicode composition: exact frontends and actual accepted-contract bridge."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import shutil
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from verislop import accept, agents, canonical, export, formal_frontend, formalize, fsutil, generate, interpret, prove, schemas
from verislop.bridges import vscore3_checker as checker
from verislop.events import EventSink
from verislop.package import Package
from verislop.targets import vscore_source, vscore2_source, vscore3_source as source


HEADER = 'program "vscore/0.3" profile "data-pipeline/0.3"; '
SURFACE = HEADER + '''
entry combine(left:String,right:String)->String{String.append(left,right)}
entry extent(text:String)->Nat{String.length(text)}
entry combined_extent(left:String,right:String)->Nat{String.length(String.append(left,right))}
'''
REQUEST = ("Provide pure VSCore 0.3 entries combine and extent. combine concatenates its two Unicode scalar strings "
           "in argument order without normalization. extent returns the number of Unicode scalar values in its "
           "string argument, not its UTF-8 byte count or grapheme count. combined_extent returns the scalar length "
           "of its two string arguments concatenated in argument order. Every string input is admitted.")
PROOF = '''import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  · intro left right; with_unfolding_all rfl
  · intro left right; with_unfolding_all rfl
  · intro text; with_unfolding_all rfl
end VeriSlopBridgeProof
'''.encode("utf-8")


def ast():
    var = lambda i: {"tag": "var", "index": i}
    append = {"tag": "string_append", "left": var(1), "right": var(0)}
    length = {"tag": "string_length", "value": var(0)}
    combined_length = {"tag": "string_length", "value": append}
    equations = {}
    for name, arity, body in (("combine", 2, append), ("extent", 1, length), ("combined_extent", 2, combined_length)):
        formula = {"tag": "eq", "left": {"tag": "call", "symbol": name,
                   "args": [var(i) for i in reversed(range(arity))]}, "right": body}
        for _ in range(arity):
            formula = {"tag": "forall", "sort": "String", "body": formula}
        equations[name + "_contract"] = {"formula": formula}
    return {"encoding": formal_frontend.VERSION, "records": {}, "symbols": {
            "combine": {"args": ["String", "String"], "result": "String", "body": append},
            "extent": {"args": ["String"], "result": "Nat", "body": length},
            "combined_extent": {"args": ["String", "String"], "result": "Nat", "body": combined_length}},
            "predicates": {}, "theorems": equations,
            "obligations": {"D1": {"declarations": [{"kind": "symbol", "name": name}
                for name in ("combine", "extent", "combined_extent")]}, "O1": {"theorem": "combine_contract"},
                "O2": {"theorem": "extent_contract"}, "O3": {"theorem": "combined_extent_contract"}}, "witness_obligations": {}}


def accepted_fixture(root):
    pkg = Package(root / "package")
    pkg.ensure("unicode-string-bridge-fixture")
    pkg.set_meta("requested", {"tier": 2, "target": "vscore", "endpoint": "restricted_source",
                              "backend_version": "0.3", "require_state": "END_TO_END_VERIFIED"})
    prompt = root / "request.txt"
    prompt.write_text(REQUEST, encoding="utf-8")
    proposal = {"obligations": [{"id": oid, "kind": kind, "role": role, "statement": REQUEST,
        "required": True, "scope": ["all finite Unicode scalar strings"], "dependencies": [],
        "acceptance_criteria": ["Exact unrestricted string composition and scalar length"],
        "sources": [{"quote": REQUEST, "origin": "explicit", "interpretation": "pure string functions"}]}
        for oid, kind, role in (("D1", "entity", "declaration"), ("O1", "postcondition", "guarantee"),
                               ("O2", "postcondition", "guarantee"), ("O3", "postcondition", "guarantee"))],
        "category_review": {kind: "reviewed for this pure Unicode fixture" for kind in agents.DRAFT_CATEGORIES},
        "clauses": [{"quote": REQUEST, "disposition": "obligations", "refs": ["D1", "O1", "O2", "O3"]}],
        "assumptions": [], "ambiguities": [], "selected_defaults": []}
    events = EventSink(pkg.run_id, pkg.root, quiet=True)
    try:
        def interpreter(data, ref, _routing):
            draft, ledger, errors = agents.assemble_interpretation(proposal, data, ref)
            if errors:
                raise AssertionError(errors)
            return draft, ledger
        stages = [interpret.run(pkg, events, prompt, mode="software", request_ref="request.txt", agent=interpreter)]
        broker = SimpleNamespace(call=lambda *args: SimpleNamespace(text=canonical.dumps(ast()).decode(),
                                                                   request_id="unicode-fixture-author"))
        with patch.object(agents, "_broker", return_value=(broker, {"roles": {"formalizer": "fixture-author"}})):
            stages.append(formalize.run(pkg, events, agent=agents.formalizer_agent("unused", pkg, events), max_attempts=1))
        for stage in stages:
            if stage.status != "PASS":
                raise AssertionError([d.to_json() for d in stage.diagnostics])
        for operation in (prove.run, accept.run, export.run):
            result = operation(pkg, events, **({"budget_seconds": 0} if operation is prove.run else {}))
            if result.status != "PASS":
                raise AssertionError([d.to_json() for d in result.diagnostics])
        return pkg
    finally:
        events.close()


class StringFrontendTests(unittest.TestCase):
    def test_exact_nodes_roundtrip_and_no_new_feature(self):
        program = source.parse_surface(SURFACE)
        self.assertEqual(("string_append", ("var", 1), ("var", 0)), program["entries"][0]["body"])
        self.assertEqual(("string_length", ("var", 0)), program["entries"][1]["body"])
        self.assertEqual(["base", "string"], source.required_features(program))
        raw = source.source_bytes(program)
        self.assertEqual(program, source.parse_source(raw))
        self.assertEqual([], schemas.validate("vscore-source-v3", source.program_json(program)))
        self.assertIn("VSCore3.Expr.stringAppend", source.lean_program(program))
        self.assertIn("VSCore3.Expr.stringLength", source.lean_program(program))
        for old in (vscore_source, vscore2_source):
            with self.assertRaises(old.SourceError):
                old.parse_source(raw)

    def test_wrong_arity_types_and_unknown_operation_rejected(self):
        expressions = (("String.append()", "String"), ("String.append(x)", "String"),
                       ("String.append(x,x,x)", "String"), ("String.length()", "Nat"),
                       ("String.length(x,x)", "Nat"), ("String.length(1)", "Nat"),
                       ("String.append(x,1)", "String"), ("String.append(true,x)", "String"),
                       ("String.reverse(x)", "String"))
        for body, result in expressions:
            with self.subTest(body=body), self.assertRaises(source.SourceError):
                source.parse_surface(HEADER + f"entry f(x:String)->{result}{{{body}}}")

    def test_closed_json_fields_and_scalar_validation(self):
        original = source.program_json(source.parse_surface(SURFACE))
        for index in (0, 1):
            changed = deepcopy(original)
            changed["entries"][index]["body"]["unexpected"] = True
            self.assertTrue(schemas.validate("vscore-source-v3", changed))
            with self.assertRaises(source.SourceError):
                source.parse_source(canonical.dumps(changed))
            for field in ("left", "right") if index == 0 else ("value",):
                changed = deepcopy(original)
                del changed["entries"][index]["body"][field]
                self.assertTrue(schemas.validate("vscore-source-v3", changed))
                with self.assertRaises(source.SourceError):
                    source.parse_source(canonical.dumps(changed))
        for scalar in (55296, 57343, 1114112):
            with self.subTest(scalar=scalar), self.assertRaises(source.SourceError):
                source.parse_surface(HEADER + f'entry f()->Nat{{String.length(String.append("",string({scalar})))}}')

    def test_nested_helper_feature_and_captured_binder_inventory(self):
        program = source.parse_surface(HEADER + '''
fn measure(x:String)->Nat{String.length(x)}
entry lengths(prefix:String,items:List(String))->List(Nat){
  List.map(items;item=>call measure(String.append(prefix,item)))
}
''')
        self.assertEqual(("list_map", ("var", 0), ("call", "measure", [
            ("string_append", ("var", 2), ("var", 0))])), program["entries"][0]["body"])
        self.assertIn("string", source.required_features(program))
        with self.assertRaisesRegex(source.SourceError, "unsupported required features: string"):
            source.check_program({}, program, [f for f in source.FEATURES if f != "string"])


class AcceptedStringBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="verislop-string-bridge-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.pkg = accepted_fixture(Path(cls.tmp.name))
        cls.source = source.compile_surface(SURFACE)
        cls.relation = canonical.dumps({"schema_version": "0.3", "format": "verislop.vscore-relation/0.3",
            "template": "vscore.reference_refinement/0.3", "source_slot": "vscore-source",
            "proof_slot": "vscore-proof", "bindings": [{"symbol": n, "entry": n} for n in ("combine", "combined_extent", "extent")]})

    def test_surface_author_dispatch_compiles_and_checks_the_exact_native_source(self):
        destination = Path(self.tmp.name) / "surface-author"
        shutil.copytree(self.pkg.root, destination)
        fsutil.make_writable_tree(destination)
        pkg = Package(destination)
        response = canonical.dumps({"program_source": SURFACE,
            "relation": canonical.loads(self.relation), "proof_source": PROOF.decode()}).decode()
        dispatched = []

        def complete(agent, instance, system, user, purpose):
            self.assertEqual("generate", purpose)
            self.assertIn("program_source", system)
            self.assertIn("program =", user)
            dispatched.append((agent, instance))
            return SimpleNamespace(text=response)

        broker = SimpleNamespace(call=complete)
        conf = {"roles": {"implementer": "author", "prover": "prover"},
                "agents": {"author": {"vscore_authoring_format": "surface"}, "prover": {}}}
        events = EventSink(pkg.run_id, pkg.root, quiet=True)
        try:
            result = generate.run(pkg, events, tier=2, target="vscore", backend_version="0.3",
                agent=lambda ctx: agents._vscore_implementation(broker, conf, pkg, events, ctx, 1, 0))
        finally:
            events.close()
        self.assertEqual("PASS", result.status, [d.to_json() for d in result.diagnostics])
        self.assertEqual(1, len(dispatched))
        self.assertEqual(self.source, (pkg.path("implementation") / "program.vscore.json").read_bytes())
        attempt = pkg.root / "agents/vscore-attempts/source-1"
        self.assertEqual(SURFACE.encode(), (attempt / "program.vsc").read_bytes())
        self.assertEqual(response.encode(), (attempt / "response.txt").read_bytes())
        self.assertEqual(self.source, (attempt / "program.vscore.json").read_bytes())
        checked = canonical.load_file(attempt / "checks/initial-proof.json")
        self.assertTrue(checked["passed"])
        self.assertTrue(checked["proof_checked"])

    def test_actual_accepted_bridge_readable_selection_and_two_clean_replays(self):
        _, _, initial = checker.preview(self.pkg, self.source, self.relation, select_readable=True)
        self.assertEqual("CHECKED", initial["readable_source_view"]["status"])
        self.assertEqual("CHECKED", initial["readable_source_view"]["mode"])
        selection = initial["readable_selection"]
        diagnostics = {name: raw for name, raw in initial["readable_candidate_artifacts"].items()
                       if name != "support/readable/selection.json"}
        builds = []
        for _ in range(2):
            try:
                _, build, info = checker.preview(self.pkg, self.source, self.relation, PROOF,
                                                readable_selection=selection, readable_diagnostics=diagnostics)
            except checker.EdgeFailure as exc:
                self.fail(str([(d.code, d.message, d.details.get("errors")) for d in exc.diagnostics]))
            self.assertTrue(info["proof_checked"])
            self.assertEqual(["O1", "O2", "O3"], info["required_obligations"])
            self.assertEqual(self.source, canonical.dumps(build.ir["program"]))
            self.assertNotIn("sorryAx", build.axioms)
            builds.append(build)
        self.assertEqual(builds[0].observation, builds[1].observation)

    def test_well_typed_wrong_append_order_cannot_prove_refinement(self):
        program = canonical.loads(self.source)
        body = program["entries"][0]["body"]
        body["left"], body["right"] = body["right"], body["left"]
        changed = canonical.dumps(program)
        source.check_program({}, source.parse_source(changed))
        with self.assertRaises(checker.EdgeFailure) as caught:
            checker.preview(self.pkg, changed, self.relation, PROOF)
        self.assertIn("CANDIDATE_BUILD_FAILURE", {d.code for d in caught.exception.diagnostics})

    def test_well_typed_constant_length_cannot_prove_refinement(self):
        program = canonical.loads(self.source)
        program["entries"][1]["body"] = {"tag": "nat", "value": "0"}
        changed = canonical.dumps(program)
        source.check_program({}, source.parse_source(changed))
        with self.assertRaises(checker.EdgeFailure) as caught:
            checker.preview(self.pkg, changed, self.relation, PROOF)
        self.assertIn("CANDIDATE_BUILD_FAILURE", {d.code for d in caught.exception.diagnostics})


if __name__ == "__main__":
    unittest.main()
