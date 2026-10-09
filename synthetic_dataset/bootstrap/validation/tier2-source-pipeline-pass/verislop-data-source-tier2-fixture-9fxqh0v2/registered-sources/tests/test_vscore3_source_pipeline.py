"""Fresh unrelated record/value/source fixture through the registered 0.3 path."""
from __future__ import annotations

import tempfile
import copy
import json
import shutil
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import MockLLM, mock_config, unanimous

from verislop import accept, agents, canonical, closure, export, formal_frontend, formalize, fsutil, generate, interpret, link, prove, review, review_counterexamples as replay, schemas, source_contract, source_policy, view, verifiers
from verislop.backends import registry, vscore3, vscore3_closure
from verislop.bridges import prepare, vscore3_checker
from verislop.evidence import validated_execution
from verislop.events import EventSink
from verislop.package import Package
from verislop.targets import vscore3_source

REQUEST = (b"Deliver a VSCore 0.3 pure source implementation. Packet has amount:Int, words:List String and extra:Option Int. "
           b"shift subtracts three from every mathematical integer. solve returns Packet.amount minus three. "
           b"Mapping shift over any integer list equals mapping subtraction of three. Deliver solve and shift in program.vscore.json "
           b"with typed total evaluation, deterministic results, preserved inputs, no external I/O or floating point, "
           b"pure data and the restricted runtime. These source requirements are independently required and also part "
           b"of the value guarantee. This is a restricted source contract.")
VARIABLE = {"tag": "var", "index": 0}
ARITHMETIC = {"tag": "int_add", "left": VARIABLE, "right": {"tag": "int", "value": "-3"}}
SOLVE = {"tag": "int_add", "left": {"tag": "field", "sort": "Packet", "field": "amount", "value": VARIABLE},
         "right": {"tag": "int", "value": "-3"}}
AST = {
    "encoding": formal_frontend.VERSION,
    "records": {"Packet": {"fields": [{"name": "amount", "sort": "Int"},
        {"name": "words", "sort": {"list": "String"}}, {"name": "extra", "sort": {"option": "Int"}}]}},
    "symbols": {"shift": {"args": ["Int"], "result": "Int", "body": ARITHMETIC},
                "solve": {"args": [{"record": "Packet"}], "result": "Int", "body": SOLVE}},
    "predicates": {},
    "theorems": {
        "result": {"formula": {"tag": "forall", "sort": {"record": "Packet"}, "body": {"tag": "eq",
            "left": {"tag": "call", "symbol": "solve", "args": [VARIABLE]}, "right": SOLVE}}},
        "binder": {"formula": {"tag": "forall", "sort": {"list": "Int"}, "body": {"tag": "eq",
            "left": {"tag": "list_map", "value": VARIABLE, "function": {"sort": "Int", "body": {
                "tag": "call", "symbol": "shift", "args": [VARIABLE]}}},
            "right": {"tag": "list_map", "value": VARIABLE, "function": {"sort": "Int", "body": ARITHMETIC}}}}}},
    "obligations": {"D1": {"declarations": [{"kind": "record", "name": "Packet"},
        {"kind": "symbol", "name": "shift"}, {"kind": "symbol", "name": "solve"}]},
        "O1": {"theorem": "result"}, "O2": {"theorem": "binder"}},
    "witness_obligations": {},
}
AST["source_requirements"] = {"Delivery": {"symbol": "solve", "requirements": [
    {"tag": "entry", "file": "program.vscore.json", "entry": "solve", "arity": 1},
    *({"tag": tag} for tag in ("typed_total", "deterministic", "input_preserved", "no_external_io",
                              "no_floating_point", "pure_data", "restricted_runtime_only"))]}}
AST["theorems"]["result"]["source"] = ["Delivery"]
AST["source_requirements"]["ShiftDelivery"] = copy.deepcopy(AST["source_requirements"]["Delivery"])
AST["source_requirements"]["ShiftDelivery"]["symbol"] = "shift"
AST["source_requirements"]["ShiftDelivery"]["requirements"][0]["entry"] = "shift"
AST["theorems"]["binder"]["source"] = ["ShiftDelivery"]
AST["theorems"]["source_only"] = {"source": ["Delivery"]}
AST["obligations"]["S1"] = {"theorem": "source_only"}
SURFACE = '''program "vscore/0.3" profile "data-pipeline/0.3";
record Packet { amount:Int; words:List(String); extra:Option(Int); }
entry shift(x:Int)->Int{x+int(-3)}
entry solve(p:Record(Packet))->Int{p.amount+int(-3)}
'''
RELATION = {"schema_version": "0.3", "format": "verislop.vscore-relation/0.3",
    "template": "vscore.reference_refinement/0.3", "source_slot": "vscore-source", "proof_slot": "vscore-proof",
    "bindings": [{"symbol": "shift", "entry": "shift"}, {"symbol": "solve", "entry": "solve"}]}
PROOF = b'''import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  all_goals intro x; with_unfolding_all rfl
end VeriSlopBridgeProof
'''

SOURCE_POLICY = {"schema_version": "0.1", "format": source_policy.FORMAT, "obligations": {
    oid: {"file": "program.vscore.json", "entry": entry, "arity": 1,
          "properties": ["typed_total", "deterministic", "input_preserved", "no_external_io",
                         "no_floating_point", "pure_data", "restricted_runtime_only"],
          "value_required": oid != "S1"}
    for oid, entry in (("O1", "solve"), ("O2", "shift"), ("S1", "solve"))}}


def accepted_fixture(root: Path) -> Package:
    """Author this fixture's request, interpretation and reference from fresh constants."""
    pkg = Package(root / "package")
    pkg.ensure("data-source-tier2-fixture")
    source_policy_input = root / "required-source-policy.json"
    fsutil.write_json(source_policy_input, SOURCE_POLICY)
    source_policy.stage(pkg, source_policy_input)
    pkg.set_meta("requested", {"tier": 2, "target": "vscore", "endpoint": "restricted_source",
                               "backend_version": "0.3", "require_state": "END_TO_END_VERIFIED"})
    prompt = root / "request.txt"
    prompt.write_bytes(REQUEST)
    proposal = {"obligations": [{"id": oid, "kind": kind, "role": role, "statement": REQUEST.decode(),
        "required": True, "scope": ["all mathematical inputs under VSCore 0.3 semantics"], "dependencies": [],
        "acceptance_criteria": ["Exact accepted types and universal function equality"],
        "sources": [{"quote": REQUEST.decode(), "origin": "explicit", "interpretation": "the pure source record and integer function contract"}]}
        for oid, kind, role in (("D1", "entity", "declaration"), ("O1", "postcondition", "guarantee"),
                               ("O2", "invariant", "guarantee"), ("S1", "safety_property", "guarantee"))],
        "category_review": {k: "reviewed for the finite pure source fixture" for k in agents.DRAFT_CATEGORIES},
        "clauses": [{"quote": REQUEST.decode(), "disposition": "obligations", "refs": ["D1", "O1", "O2", "S1"]}],
        "assumptions": [], "ambiguities": [], "selected_defaults": []}
    events = EventSink(pkg.run_id, pkg.root, quiet=True)
    try:
        def interpreter(data, ref, routing):
            draft, ledger, problems = agents.assemble_interpretation(proposal, data, ref)
            if problems:
                raise AssertionError(problems)
            return draft, ledger
        stages = [interpret.run(pkg, events, prompt, mode="software", request_ref="request.txt", agent=interpreter)]
        raw = canonical.dumps(AST).decode()
        broker = SimpleNamespace(call=lambda *args: SimpleNamespace(text=raw, request_id="fresh-tier2-fixture"))
        with patch.object(agents, "_broker", return_value=(broker, {"roles": {"formalizer": "fixture-author"}})):
            stages.append(formalize.run(pkg, events, agent=agents.formalizer_agent("unused", pkg, events), max_attempts=1))
        for result in stages:
            if result.status != "PASS":
                raise AssertionError([d.to_json() for d in result.diagnostics])
        candidate = root / "contract-proof.lean"
        challenge = (pkg.path("contract") / "challenge/Contract.lean").read_text()
        tactics = {"binder": "exact ⟨by intros; rfl, VeriSlop.Source.contract_sound _⟩", "result": "exact ⟨by intros; rfl, VeriSlop.Source.contract_sound _⟩",
                   "source_only": "exact VeriSlop.Source.contract_sound _"}
        authored = challenge
        for offset in reversed(prove.sorry_sites(challenge)):
            name = prove._short(prove.enclosing_decl(challenge, offset))
            authored = authored[:offset] + tactics[name] + authored[offset + 5:]
        candidate.write_text(authored)
        for operation in (prove.run, accept.run, export.run):
            result = operation(pkg, events, **({"budget_seconds": 0, "candidate": candidate, "portfolio": False} if operation is prove.run else {}))
            if result.status != "PASS":
                raise AssertionError([d.to_json() for d in result.diagnostics])
        return pkg
    finally:
        events.close()


class RegisteredVSCore3SourcePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="verislop-data-source-tier2-fixture-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.pkg = accepted_fixture(cls.root)
        cls.events = EventSink(cls.pkg.run_id, cls.pkg.root, quiet=True)
        cls.addClassCleanup(cls.events.close)
        cls.candidate = cls.root / "candidate"
        fsutil.atomic_write(cls.candidate / "program.vscore.json", vscore3_source.compile_surface(SURFACE))
        fsutil.write_json(cls.candidate / "relation.json", RELATION)
        fsutil.atomic_write(cls.candidate / "Proof.lean", PROOF)
        for operation, kwargs in ((generate.run, {"tier": 2, "target": "vscore", "backend_version": "0.3", "candidate": cls.candidate}),
                                  (link.run, {})):
            result = operation(cls.pkg, cls.events, **kwargs)
            if result.status != "PASS":
                raise AssertionError([d.to_json() for d in result.diagnostics])
        checked = vscore3_checker.accept(cls.pkg, "implementation", cls.events)
        if checked.status != "PASS":
            raise AssertionError([d.to_json() for d in checked.diagnostics])
        result = closure.run(cls.pkg, cls.events)
        if result.status != "PASS":
            raise AssertionError([d.to_json() for d in result.diagnostics])

        # Preserve actual observations and every module part before test cleanup.
        destination = Path(__file__).resolve().parents[1] / "synthetic_dataset/bootstrap/validation/tier2-source-pipeline-pass" / cls.root.name
        destination.mkdir(parents=True, exist_ok=False)
        shutil.copytree(cls.pkg.root, destination / "package")
        shutil.copytree(cls.candidate, destination / "candidate")
        sources = sorted({"verislop/" + rel for spec in verifiers.VERIFIERS.values() for rel in verifiers.CORE + spec["sources"]}
                         | {"schemas/" + name for spec in verifiers.VERIFIERS.values() for name in spec["schemas"]}
                         | {"tests/test_vscore3_source_pipeline.py"})
        repo = Path(__file__).resolve().parents[1]
        source_hashes = {}
        for rel in sources:
            data = (repo / rel).read_bytes()
            fsutil.atomic_write(destination / "registered-sources" / rel, data)
            source_hashes[rel] = canonical.digest(data)
        files = {str(path.relative_to(destination)): canonical.digest_file(path) for path in sorted(destination.rglob("*")) if path.is_file()}
        fsutil.write_json(destination / "capture.json", {"format": "verislop.tier2-source-pipeline-capture/0.1",
            "test": "tests.test_vscore3_source_pipeline", "captured_before_test_temp_cleanup": True,
            "historical_source_root": str(cls.root), "mechanical_status": "VERIFIED", "files": files,
            "source_hashes": source_hashes, "source_root": canonical.digest_json(source_hashes)})
        print("SOURCE_PIPELINE_CAPTURE", destination, flush=True)
        cls.review_capture = destination.parent.parent / "tier2-mechanical-review" / cls.root.name
        cls.review_capture.mkdir(parents=True, exist_ok=False)

    def review_copy(self, name: str) -> Package:
        """Keep the one checked fixture intact while changing concrete bound files."""
        root = self.root / self._testMethodName / name
        shutil.copytree(self.pkg.root, root)
        fsutil.make_writable_tree(root)
        return Package(root)

    def mechanical_probe(self, pkg: Package, claim_id: str, *, checkpoint="release", name=None) -> dict:
        receipt = replay.replay(pkg, checkpoint, {"kind": "mechanical_failure", "claim_id": claim_id})
        if name is not None:
            fsutil.write_json(self.review_capture / self._testMethodName / (name + ".json"), receipt)
        return receipt

    def assert_bound_pass(self, pkg: Package, snapshot: dict, claim_id: str, receipt: dict) -> None:
        row = next(c for c in snapshot["claims"] if c["claim_id"] == claim_id)
        self.assertTrue(row["required"], row)
        self.assertEqual("PASS", row["outcome"], row)
        self.assertEqual("NOT_REPRODUCED", receipt["status"], receipt)
        self.assertEqual([], schemas.validate("review-counterexample-receipt", receipt))
        self.assertEqual(claim_id, receipt["claim"]["claim_id"])
        self.assertEqual({"outcome": "PASS", "root_kind": row["root_kind"], "root": row["input_root"]}, receipt["expected"])
        self.assertIsNotNone(receipt["expected"]["root"])
        self.assertEqual("PASS", receipt["observed"]["outcome"])
        self.assertEqual(["evidence:" + receipt["observed"]["evidence_id"]], row["evidence_refs"])
        manifest = canonical.load_file(pkg.path("closure") / "manifest.json")
        execution = Path(snapshot["mechanical_result_path"]).parent
        bound_paths = {"closure/current.json", "closure/manifest.json", snapshot["mechanical_result_path"]}
        bound_paths.update(entry["path"] for entry in manifest["entries"])
        bound_paths.update(str(execution / entry["path"]) for entry in snapshot["execution_inventory"])
        for rel in sorted(bound_paths):
            self.assertEqual(canonical.digest_file(pkg.root / rel), receipt["input_bindings"].get(rel), rel)

    def test_release_replays_exact_semantic_edge_and_structural_bundle_evidence(self):
        snapshot = vscore3_closure.mechanical_snapshot(self.pkg)
        selected = vscore3.selection(self.pkg)
        bundle = self.pkg.path("bridges") / selected["bridge_id"]
        semantic = bundle / vscore3_checker.SEMANTIC_DIR / vscore3_checker.edge_key(selected["edge_id"])
        certificates = (("structural", bundle, canonical.load_file(bundle / prepare.CERTIFICATE), "bridge_artifacts"),
                        ("semantic", semantic, canonical.load_file(semantic / vscore3_checker.CERTIFICATE), "semantic_edge"))
        for name, base, certificate, root_kind in certificates:
            with self.subTest(scope=name):
                record_path = base / certificate["evidence"]["path"]
                record = canonical.load_file(record_path)
                raw_path = base / record["raw_result_ref"]
                self.assertEqual([], self.pkg.evidence.for_claim(record["claim_id"]))
                receipt = self.mechanical_probe(self.pkg, record["claim_id"], name=name)
                self.assert_bound_pass(self.pkg, snapshot, record["claim_id"], receipt)
                self.assertEqual(root_kind, receipt["expected"]["root_kind"])
                self.assertEqual(record["input_root_hash"], receipt["expected"]["root"])
                self.assertEqual(record["evidence_id"], receipt["observed"]["evidence_id"])
                self.assertEqual(canonical.digest_file(record_path), receipt["input_bindings"][self.pkg.rel(record_path)])
                self.assertEqual(canonical.digest_file(raw_path), receipt["input_bindings"][self.pkg.rel(raw_path)])
                if name == "semantic":
                    self.assertEqual(selected["edge_claim_id"], record["claim_id"])
                    self.assertEqual(certificate["semantic_edge_root"], receipt["expected"]["root"])
                else:
                    self.assertEqual(canonical.digest_file(bundle / "artifacts.json"), receipt["expected"]["root"])

    def test_every_advertised_current_release_mechanical_claim_has_a_bound_pass(self):
        packet = review.build_packet(self.pkg, "release")
        snapshot = packet["mechanical_snapshot"]
        self.assertEqual("VERIFIED", snapshot["mechanical_status"])
        self.assertEqual(["A", "B"], [build["build"] for build in snapshot["builds"]])
        self.assertTrue(all(build["ok"] for build in snapshot["builds"]))
        advertised = packet["counterexample_policy"]["mechanical_claim_ids"]
        self.assertEqual(set(advertised), set(packet["review_context"]["current_required_claim_ids"]))
        self.assertTrue({vscore3.selection(self.pkg)["edge_claim_id"], "BRIDGE:structure:implementation", "CLOSURE:provenance"}.issubset(advertised))
        self.assertTrue(set(advertised).issubset({c["claim_id"] for c in packet["required_mechanical_claims"]}))
        for index, claim_id in enumerate(advertised):
            with self.subTest(claim_id=claim_id):
                receipt = self.mechanical_probe(self.pkg, claim_id, name=str(index))
                self.assert_bound_pass(self.pkg, snapshot, claim_id, receipt)

    def test_release_ballot_accepts_replayed_bridge_and_provenance_probes(self):
        pkg = self.review_copy("campaign")
        claim_ids = [vscore3.selection(pkg)["edge_claim_id"], "BRIDGE:structure:implementation", "CLOSURE:provenance"]

        def reviewer(system, user, model):
            start = user.index("REVIEW PACKET (")
            start = user.index("\n", start) + 1
            packet, _ = json.JSONDecoder().raw_decode(user[start:])
            self.assertTrue(set(claim_ids).issubset(packet["counterexample_policy"]["mechanical_claim_ids"]))
            return json.dumps({"verdict": "ACCEPT", "reviewed_obligations": packet["scope"], "findings": [],
                "search": {"method": "probe the selected semantic edge, structural bundle and complete public provenance",
                           "attempted_cases": len(claim_ids), "probes": [{"kind": "mechanical_failure", "claim_id": cid} for cid in claim_ids],
                           "conclusion": "NO_COUNTEREXAMPLE_FOUND"},
                "limitations": ["finite fixture review"], "rationale": "All selected current mechanical probes were submitted for independent replay."})

        mock = MockLLM(reviewer)
        try:
            config, env = mock_config(pkg.root.parent, mock.port, [unanimous("release", "reviewer", 1)], checkpoints=["release"])
            events = EventSink(pkg.run_id, pkg.root, quiet=True)
            try:
                with patch.dict("os.environ", env):
                    result = review.run(pkg, events, config, checkpoint="release")
            finally:
                events.close()
        finally:
            mock.close()
        shutil.copytree(pkg.path("reviews"), self.review_capture / self._testMethodName / "reviews")
        fsutil.write_json(self.review_capture / self._testMethodName / "result.json", result.to_json())
        self.assertEqual("PASS", result.status, [d.to_json() for d in result.diagnostics])
        self.assertEqual("REVIEW_ACCEPTED", result.summary["final"])
        ballots = list(pkg.path("reviews").glob("rc-*/ballots/*.json"))
        self.assertEqual(1, len(ballots))
        ballot = canonical.load_file(ballots[0])
        self.assertEqual("ACCEPT", ballot["reported_verdict"])
        self.assertEqual("ACCEPT", ballot["verdict"])
        self.assertEqual(3, len(ballot["counterexample_receipts"]))
        snapshot = vscore3_closure.mechanical_snapshot(pkg)
        for claim_id, reference in zip(claim_ids, ballot["counterexample_receipts"]):
            receipt = canonical.load_file(pkg.root / reference["receipt_ref"])
            self.assertEqual("NOT_REPRODUCED", reference["status"])
            self.assertEqual(canonical.digest_file(pkg.root / reference["receipt_ref"]), reference["receipt_hash"])
            self.assert_bound_pass(pkg, snapshot, claim_id, receipt)
        with patch.dict("os.environ", env):
            gate = review.gate(pkg, config)
        fsutil.write_json(self.review_capture / self._testMethodName / "gate.json",
                          {**gate, "diagnostics": [d.to_json() for d in gate["diagnostics"]]})
        self.assertEqual([], gate["diagnostics"], [d.to_json() for d in gate["diagnostics"]])
        self.assertEqual("REVIEW_ACCEPTED", gate["checkpoints"]["release"])

    def test_changed_or_missing_release_bindings_cannot_forge_a_mechanical_observation(self):
        snapshot = vscore3_closure.mechanical_snapshot(self.pkg)
        selection = vscore3.selection(self.pkg)
        claim_id = selection["edge_claim_id"]
        row = next(c for c in snapshot["claims"] if c["claim_id"] == claim_id)
        evidence_id = row["evidence_refs"][0].removeprefix("evidence:")
        bundle = Path("bridges") / selection["bridge_id"]
        semantic = bundle / vscore3_checker.SEMANTIC_DIR / vscore3_checker.edge_key(selection["edge_id"])
        certificate = canonical.load_file(self.pkg.root / semantic / vscore3_checker.CERTIFICATE)
        semantic_record = canonical.load_file(self.pkg.root / semantic / certificate["evidence"]["path"])
        result_path = snapshot["mechanical_result_path"]
        execution = Path(result_path).parent
        different_hash = "sha256:" + "1" * 64

        def change_claim(field, value):
            def edit(obj):
                next(c for c in obj["claims"] if c["claim_id"] == claim_id)[field] = value
            return edit

        def change_row(field, value):
            def edit(obj):
                next(c for c in obj["claims"] if c["claim_id"] == claim_id)[field] = value
            return edit

        # Each case changes one exact current input or retained execution binding.
        # The checker must not fall back to the unchanged VERIFIED report/projection.
        cases = (
            ("delivered-source", "implementation/program.vscore.json", None),
            ("source-policy-bytes", source_policy.PATH, None),
            ("bridge-plan-bytes", bundle / "plan.json", None),
            ("bridge-artifacts-bytes", bundle / "artifacts.json", None),
            ("selected-edge", "closure/selection.json", lambda obj: obj.update(edge_id="unselected-edge")),
            ("selected-claim", "closure/selection.json", lambda obj: obj.update(edge_claim_id="BRIDGE:unselected-claim")),
            ("claim-requiredness", "closure/implementation-claims.json", change_claim("required", False)),
            ("claim-predicate", "closure/implementation-claims.json", change_claim("result_predicate", "milestone-pass/0.1")),
            ("claim-verifier", "closure/implementation-claims.json", change_claim("verifier", "verislop.interpretation-recorder")),
            ("claim-root-kind", "closure/implementation-claims.json", change_claim("root_kind", "contract_input_root")),
            ("claim-premises", "closure/implementation-claims.json", change_claim("premises", [])),
            ("claim-scope", "closure/implementation-claims.json", change_claim("scope", ["a different accepted scope"])),
            ("duplicate-claim", "closure/implementation-claims.json", lambda obj: obj["claims"].append(copy.deepcopy(next(c for c in obj["claims"] if c["claim_id"] == claim_id)))),
            ("missing-result-row", result_path, lambda obj: obj.update(claims=[c for c in obj["claims"] if c["claim_id"] != claim_id])),
            ("duplicate-result-row", result_path, lambda obj: obj["claims"].append(copy.deepcopy(next(c for c in obj["claims"] if c["claim_id"] == claim_id)))),
            ("result-row-root", result_path, change_row("input_root", different_hash)),
            ("result-row-outcome", result_path, change_row("outcome", "PENDING")),
            ("result-row-evidence", result_path, change_row("evidence_refs", ["evidence:ev-unbound"])),
            ("execution-root", result_path, lambda obj: obj.update(closure_root=different_hash)),
            ("consumed-record", execution / "consumed" / evidence_id / "record.json", None),
            ("consumed-raw", execution / "consumed" / evidence_id / "raw.json", None),
            ("semantic-record-verifier", semantic / certificate["evidence"]["path"], lambda obj: obj.update(verifier_hash=different_hash)),
            ("semantic-raw", semantic / semantic_record["raw_result_ref"], None),
            ("manifest-membership", "closure/manifest.json", lambda obj: obj["entries"].pop()),
        )
        for name, rel, edit in cases:
            with self.subTest(mutation=name):
                pkg = self.review_copy(name)
                path = pkg.root / rel
                if edit is None:
                    fsutil.atomic_write(path, path.read_bytes() + b"\n")
                else:
                    obj = canonical.load_file(path)
                    edit(obj)
                    fsutil.write_json(path, obj)
                receipt = self.mechanical_probe(pkg, claim_id, name=name)
                self.assertIn(receipt["status"], ("UNSUPPORTED", "INFRASTRUCTURE_FAILURE"), receipt)
                self.assertTrue(receipt["diagnostics"], receipt)

        for name, rel in (("absent-execution", result_path), ("absent-pointer", "closure/current.json")):
            with self.subTest(mutation=name):
                pkg = self.review_copy(name)
                (pkg.root / rel).unlink()
                # A report can still advertise VERIFIED, but it is not evidence.
                self.assertEqual("VERIFIED", canonical.load_file(pkg.path("report"))["mechanical_status"])
                for index, cid in enumerate((claim_id, "CLOSURE:provenance")):
                    receipt = self.mechanical_probe(pkg, cid, name=f"{name}-{index}")
                    self.assertIn(receipt["status"], ("UNSUPPORTED", "INFRASTRUCTURE_FAILURE"), receipt)

    def test_unknown_claim_and_unavailable_registered_checker_remain_unresolved(self):
        unknown = self.mechanical_probe(self.pkg, "BRIDGE:implementation:unknown-edge", name="unknown")
        self.assertEqual("UNSUPPORTED", unknown["status"], unknown)
        self.assertIsNone(unknown["claim"])
        claim_id = vscore3.selection(self.pkg)["edge_claim_id"]
        with patch.dict(verifiers.VERIFIERS):
            verifiers.VERIFIERS.pop(vscore3_checker.VERIFIER)
            unavailable = self.mechanical_probe(self.pkg, claim_id, name="unregistered-verifier")
        self.assertIn(unavailable["status"], ("UNSUPPORTED", "INFRASTRUCTURE_FAILURE"), unavailable)
        with patch.object(vscore3_closure.leanbridge, "resolve_toolchain", side_effect=OSError("pinned Lean executable unavailable")):
            unavailable_tool = self.mechanical_probe(self.pkg, claim_id, name="missing-toolchain")
        self.assertIn(unavailable_tool["status"], ("UNSUPPORTED", "INFRASTRUCTURE_FAILURE"), unavailable_tool)

    def test_earlier_checkpoint_replay_preserves_current_legacy_evidence(self):
        for checkpoint in ("interpretation", "formal_contract"):
            with self.subTest(checkpoint=checkpoint):
                receipt = self.mechanical_probe(self.pkg, "INTERPRETATION:request", checkpoint=checkpoint, name=checkpoint)
                self.assertEqual("NOT_REPRODUCED", receipt["status"], receipt)
                self.assertEqual("interpretation_root", receipt["expected"]["root_kind"])
                self.assertEqual(self.pkg.interpretation_root(), receipt["expected"]["root"])
                self.assertNotIn("closure/current.json", receipt["input_bindings"])

    def test_complete_claim_graph_and_distinct_registered_version(self):
        report = canonical.load_file(self.pkg.path("report"))
        self.assertEqual([], schemas.validate("run-report-v3", report))
        self.assertEqual("VERIFIED", report["terminal_status"])
        self.assertEqual("VERIFIED", report["mechanical_status"])
        self.assertEqual(registry.VSCORE3_ID, report["backend"])
        self.assertEqual("vscore/0.3", report["language"])
        self.assertIn("END_TO_END_VERIFIED [restricted_source; vscore/0.3]", report["qualified_result"])
        for oid in ("O1", "O2", "S1"):
            self.assertEqual("PASS", report["obligations"][oid]["outcomes"]["END_TO_END_VERIFIED"])
            self.assertEqual("PENDING", report["obligations"][oid]["outcomes"]["TESTED"])
        ir = canonical.load_file(self.pkg.path("accepted_ir"))
        self.assertEqual("source_facets", ir["obligations"]["O1"]["formal"]["representation"])
        self.assertEqual("source_facets", ir["obligations"]["S1"]["formal"]["representation"])
        self.assertEqual("source_facets", ir["obligations"]["O2"]["formal"]["representation"])
        self.assertEqual(SOURCE_POLICY, source_policy.context(self.pkg))
        closure_manifest = canonical.load_file(self.pkg.path("closure") / "manifest.json")
        self.assertIn(source_policy.PATH, {row["path"] for row in closure_manifest["entries"]})
        _, _, _, policy_diagnostics = export.verified_ir(self.pkg)
        self.assertEqual(policy_diagnostics, [])
        for oid in ("O1", "O2", "S1"):
            package = vscore3.admission.formula_package(self.pkg, ir["obligations"][oid])
            self.assertEqual({"shift" if oid == "O2" else "solve"}, source_contract.symbols(package))
            self.assertEqual(8, len(source_contract.source_facets(package)[0]["requirements"]))
            self.assertEqual(package["value"] is None, oid == "S1")
        selected = vscore3.selection(self.pkg)
        self.assertEqual(["O1", "O2", "S1"], [r["id"] for r in selected["covered"]])
        materialized = canonical.load_file(self.pkg.path("implementation") / "materialization.json")
        self.assertFalse(materialized["proof_checked"])
        linked = canonical.load_file(self.pkg.path("bridges") / "link.json")
        self.assertIn("accepted_record", {o["kind"] for d in linked["declarations"] for o in d["objects"]})
        self.assertTrue(all(report["obligations"]["D1"]["outcomes"][m] == "PASS" for m in ("IMPLEMENTED", "LINKED")))
        self.assertTrue(prepare.verify_preparation(self.pkg, "implementation", semantic="rebuild").summary["semantic_acceptance"])

    def test_current_execution_revalidates_and_source_mutation_invalidates(self):
        snapshot = vscore3_closure.mechanical_snapshot(self.pkg)
        self.assertIsNotNone(snapshot)
        execution = self.pkg.root / snapshot["mechanical_result_path"]
        self.assertEqual("VERIFIED", validated_execution(execution.parent)["mechanical_status"])
        child_root = self.root / "changed"
        import shutil
        shutil.copytree(self.pkg.root, child_root)
        child = Package(child_root)
        fsutil.atomic_write(child.path("implementation") / "program.vscore.json",
                            (child.path("implementation") / "program.vscore.json").read_bytes() + b"\n")
        with self.assertRaises(vscore3_closure.InvalidPackage):
            vscore3_closure.mechanical_snapshot(child)
        overlay = view.derive(child)
        self.assertNotEqual("PASS", overlay["obligations"]["O1"]["lifecycle"]["END_TO_END_VERIFIED"]["outcome"])
        policy_root = self.root / "changed-policy"
        shutil.copytree(self.pkg.root, policy_root)
        policy_child = Package(policy_root)
        policy_path = policy_child.root / source_policy.PATH
        fsutil.make_writable_tree(policy_root)
        fsutil.atomic_write(policy_path, policy_path.read_bytes() + b"\n")
        with self.assertRaises(vscore3_closure.InvalidPackage):
            vscore3_closure.mechanical_snapshot(policy_child)
        policy_overlay = view.derive(policy_child)
        self.assertNotEqual("PASS", policy_overlay["obligations"]["O1"]["lifecycle"]["END_TO_END_VERIFIED"]["outcome"])


if __name__ == "__main__":
    unittest.main()
