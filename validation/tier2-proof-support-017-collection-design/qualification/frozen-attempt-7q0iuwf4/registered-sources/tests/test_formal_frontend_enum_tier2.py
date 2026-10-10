"""Fresh unrelated enum/record Tier 2 qualification, enabled only after a source freeze.

No provider, model, mocked compiler or benchmark artifact enters this fixture. Set
VERISLOP_ENUM_QUALIFICATION_FREEZE to the root's preregistered source-hash manifest
only after all implementation, specification and fixture bytes have stopped changing.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verislop import accept, agents, canonical, closure, dsl, export, formal_frontend as ff, formalize, fsutil, generate, interpret, link, prove, review, review_counterexamples, review_projection, source_policy, verifiers
from verislop.backends import vscore3, vscore3_closure
from verislop.bridges import vscore3_checker as checker
from verislop.events import EventSink
from verislop.package import Package
from verislop.targets import vscore3_readable as readable, vscore3_source as source

REPOSITORY = Path(__file__).resolve().parents[1]
CAPTURE_ROOT = REPOSITORY / "validation" / "formalizer-enumerations"
FREEZE_ENV = "VERISLOP_ENUM_QUALIFICATION_FREEZE"
REQUEST = (
    b"Deliver a pure VSCore 0.3 source implementation. Compass has exactly north, south and center. "
    b"Packet has direction:Compass and amount:Int. The adjust entry returns a Packet preserving direction, "
    b"adding two to amount when direction is north and subtracting three otherwise. "
    b"The domain contains every Compass alternative and every mathematical integer; a Packet with north and zero is a witness. "
    b"Deliver adjust in program.vscore.json with typed total evaluation, deterministic results, preserved inputs, "
    b"no external I/O or floating point, pure data and the restricted runtime. These source requirements are "
    b"independently required and are also part of the value guarantee. This is a restricted source contract."
)
VAR = {"tag": "var", "index": 0}
COMPASS = {"enum": "Compass"}
PACKET = {"record": "Packet"}
DIRECTION = {"tag": "field", "sort": "Packet", "field": "direction", "value": VAR}
AMOUNT = {"tag": "field", "sort": "Packet", "field": "amount", "value": VAR}
NORTH = {"tag": "enum", "sort": "Compass", "constructor": "north"}
ADJUSTED = {"tag": "record", "sort": "Packet", "fields": [DIRECTION, {"tag": "ite",
    "condition": {"tag": "bool_eq", "left": DIRECTION, "right": NORTH},
    "then": {"tag": "int_add", "left": AMOUNT, "right": {"tag": "int", "value": "2"}},
    "else": {"tag": "int_sub", "left": AMOUNT, "right": {"tag": "int", "value": "3"}}}]}
PROPERTIES = ["typed_total", "deterministic", "input_preserved", "no_external_io",
              "no_floating_point", "pure_data", "restricted_runtime_only"]
AST = {"encoding": ff.VERSION_V2,
    "enums": {"Compass": {"constructors": ["north", "south", "center"]}},
    "records": {"Packet": {"fields": [{"name": "direction", "sort": COMPASS}, {"name": "amount", "sort": "Int"}]}},
    "symbols": {"adjust": {"args": [PACKET], "result": PACKET, "body": ADJUSTED}},
    "predicates": {"packet_domain": {"args": [PACKET], "formula": {"tag": "eq", "left": AMOUNT, "right": AMOUNT}}},
    "source_requirements": {"Delivery": {"symbol": "adjust", "requirements": [
        {"tag": "entry", "file": "program.vscore.json", "entry": "adjust", "arity": 1},
        *({"tag": tag} for tag in PROPERTIES)]}},
    "theorems": {"adjustment": {"formula": {"tag": "forall", "sort": PACKET, "body": {"tag": "eq",
        "left": {"tag": "call", "symbol": "adjust", "args": [VAR]}, "right": ADJUSTED}}, "source": ["Delivery"]},
        "source_delivery": {"source": ["Delivery"]},
        "inhabited_domain": {"formula": {"tag": "exists", "sort": PACKET,
            "body": {"tag": "predicate", "predicate": "packet_domain", "args": [VAR]}}}},
    "obligations": {"D1": {"declarations": [{"kind": "enum", "name": "Compass"},
        {"kind": "record", "name": "Packet"}, {"kind": "symbol", "name": "adjust"}]},
        "A1": {"predicate": "packet_domain"}, "O1": {"theorem": "adjustment"}, "S1": {"theorem": "source_delivery"}},
    "witness_obligations": {"W1": {"theorem": "inhabited_domain", "witnesses_for": ["A1"],
        "description": "north and integer zero inhabit the full Packet domain"}}}
SOURCE_POLICY = {"schema_version": "0.1", "format": source_policy.FORMAT, "obligations": {
    oid: {"file": "program.vscore.json", "entry": "adjust", "arity": 1,
          "properties": PROPERTIES, "value_required": oid == "O1"} for oid in ("O1", "S1")}}
SURFACE = '''program "vscore/0.3" profile "data-pipeline/0.3";
record Packet { direction:Enum(Compass); amount:Int; }
entry adjust(p:Record(Packet))->Record(Packet){
  record Packet{direction=p.direction, amount=if p.direction == enum(Compass,north) then p.amount+int(2) else p.amount-int(3)}
}
'''
RELATION = {"schema_version": "0.3", "format": "verislop.vscore-relation/0.3",
    "template": "vscore.reference_refinement/0.3", "source_slot": "vscore-source", "proof_slot": "vscore-proof",
    "bindings": [{"symbol": "adjust", "entry": "adjust"}]}
BRIDGE_PROOF = '''import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  intro p
  change VeriSlopBridgeGoal.source_fn_adjust p = _
  rw [VeriSlopBridgeGoal.Readable.source_eq_adjust]
  rcases p with ⟨direction, amount⟩
  cases direction <;> with_unfolding_all rfl
end VeriSlopBridgeProof
'''.encode()


def qualification_source_files():
    return sorted({"verislop/" + rel for spec in verifiers.VERIFIERS.values() for rel in verifiers.CORE + spec["sources"]}
        | {"schemas/" + name for spec in verifiers.VERIFIERS.values() for name in spec["schemas"]}
        | {"docs/bootstrap-formalizer-enumerations.md", "tests/test_formal_frontend_enums.py",
           "tests/test_enum_equality_core.py", "tests/test_formal_frontend_enum_tier2.py"})


def require_frozen_sources(path):
    frozen = canonical.load_file(path)
    hashes = frozen.get("source_hashes", frozen.get("source_files"))
    if not isinstance(hashes, dict) or set(qualification_source_files()) - set(hashes):
        raise AssertionError("qualification freeze must bind every current registered source, schema, enum spec and fixture")
    for rel, expected in hashes.items():
        file = REPOSITORY / rel
        if not file.is_file() or canonical.digest_file(file) != expected:
            raise AssertionError("qualification source changed after freeze: " + rel)
    return hashes


def accepted_enum_fixture(root):
    """Actual statement/proof/accepted-AST pipeline with a local untrusted AST author."""
    pkg = Package(root / "package"); pkg.ensure("generic-enum-packet-tier2")
    policy_input = root / "required-source-policy.json"; fsutil.write_json(policy_input, SOURCE_POLICY)
    source_policy.stage(pkg, policy_input)
    pkg.set_meta("requested", {"tier": 2, "target": "vscore", "endpoint": "restricted_source",
        "backend_version": "0.3", "require_state": "END_TO_END_VERIFIED"})
    request = root / "request.txt"; request.write_bytes(REQUEST)
    interpretation = {"obligations": [{"id": oid, "kind": kind, "role": role, "statement": REQUEST.decode(),
        "required": True, "scope": ["every nominal Compass alternative and every mathematical integer"], "dependencies": [],
        "acceptance_criteria": ["exact accepted nominal types, universal value refinement and source facets"],
        "sources": [{"quote": REQUEST.decode(), "origin": "explicit", "interpretation": "the generic enum Packet source contract"}]}
        for oid, kind, role in (("D1", "entity", "declaration"), ("A1", "precondition", "assumption"),
                               ("O1", "postcondition", "guarantee"), ("S1", "safety_property", "guarantee"))],
        "category_review": {kind: "reviewed for this finite enum and mathematical integer fixture" for kind in agents.DRAFT_CATEGORIES},
        "clauses": [{"quote": REQUEST.decode(), "disposition": "obligations", "refs": ["D1", "A1", "O1", "S1"]}],
        "assumptions": [{"id": "A1", "supplied_by": "the full typed Packet domain", "discharged_at": "the constructive derived witness W1"}],
        "ambiguities": [], "selected_defaults": []}
    response = canonical.dumps(AST); fsutil.atomic_write(pkg.root / "formalizer-response.json", response)
    stages = []
    def retain_stage(result):
        stages.append(result.to_json()); fsutil.write_json(root / "stage-results.json", stages)
        if result.status != "PASS": raise AssertionError(result.to_json())
    def interpreter(data, ref, routing):
        draft, ledger, problems = agents.assemble_interpretation(interpretation, data, ref)
        if problems: raise AssertionError(problems)
        return draft, ledger
    def author(context):
        compiled = ff.compile_response(response, context["records"], "generic.enum.packet", response_ref="formalizer-response.json")
        fsutil.write_json(pkg.root / "formalizer-frozen.json", context["records"])
        author.last_compiled = compiled
        author.last_origin = {"proposal": compiled.proposal, "receipt": compiled.receipt}
        if not ff.reconstruct_origin(response, context["records"], compiled.source, compiled.formalization, compiled.receipt):
            raise AssertionError("fresh compiler origin did not replay")
        return compiled.source, compiled.formalization
    events = EventSink(pkg.run_id, pkg.root, quiet=True)
    try:
        retain_stage(interpret.run(pkg, events, request, mode="software", request_ref="request.txt", agent=interpreter))
        retain_stage(formalize.run(pkg, events, agent=author, max_attempts=1))
        # Only these freshly generated generic theorem holes receive local proof
        # expressions. There is no task solution, external provider or corpus input.
        challenge = (pkg.path("contract") / "challenge/Contract.lean").read_text()
        tactics = {"adjustment": "exact ⟨by intros; rfl, VeriSlop.Source.contract_sound _⟩",
            "source_delivery": "exact VeriSlop.Source.contract_sound _",
            "inhabited_domain": "exact ⟨VeriSlopAST.Packet.mk VeriSlopAST.Compass.north (0 : Int), rfl⟩"}
        authored = challenge
        for offset in reversed(prove.sorry_sites(challenge)):
            name = prove._short(prove.enclosing_decl(challenge, offset))
            authored = authored[:offset] + tactics[name] + authored[offset + 5:]
        proof = root / "contract-proof.lean"; proof.write_text(authored)
        retain_stage(prove.run(pkg, events, budget_seconds=0, candidate=proof, portfolio=False))
        retain_stage(accept.run(pkg, events)); retain_stage(export.run(pkg, events))
        return pkg
    finally:
        events.close()


@unittest.skipUnless(os.environ.get(FREEZE_ENV), "fresh full qualification requires root-frozen current sources")
class EnumFrontendRegisteredTier2Tests(unittest.TestCase):
    def test_actual_frozen_registered_enum_source_closure_and_retained_release_probe(self):
        freeze_path = Path(os.environ[FREEZE_ENV]); hashes = require_frozen_sources(freeze_path)
        CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
        destination = Path(tempfile.mkdtemp(prefix="tier2-frozen-attempt-", dir=CAPTURE_ROOT))
        annex = Path(tempfile.mkdtemp(prefix="tier2-retained-check-", dir=CAPTURE_ROOT))
        stage_status = "UNQUALIFIED"; portable = False; error = None
        try:
            with tempfile.TemporaryDirectory(prefix="fresh-enum-packet-tier2-") as dirname:
                root = Path(dirname)
                try:
                    pkg = accepted_enum_fixture(root)
                    certificate = canonical.load_file(pkg.path("accepted") / "acceptance.json")
                    profile_json = canonical.load_file(pkg.root / certificate["artifacts"]["profile"]["path"])
                    profile = dsl.Profile.from_json(profile_json)
                    self.assertEqual(["north", "south", "center"], profile.enums["Compass"]["constructors"])
                    self.assertNotIn("candidate_decidable_eq", profile.enums["Compass"])
                    self.assertIn("decl_hash", profile.enums["Compass"]["decidable_eq"])
                    delivered = source.compile_surface(SURFACE, {name: row["constructors"] for name, row in profile.enums.items()})
                    selected, built, info = checker.preview(pkg, delivered, canonical.dumps(RELATION), select_readable=True)
                    self.assertEqual("CHECKED", built.readable_support["mode"])
                    candidate = root / "candidate"
                    for path, data in {"program.vscore.json": delivered, "relation.json": canonical.dumps(RELATION),
                        "Proof.lean": BRIDGE_PROOF, **info["readable_candidate_artifacts"]}.items():
                        fsutil.atomic_write(candidate / path, data)
                    events = EventSink(pkg.run_id, pkg.root, quiet=True)
                    try:
                        stages = []
                        for operation, options in ((generate.run, {"tier": 2, "target": "vscore", "backend_version": "0.3", "candidate": candidate}),
                            (link.run, {}), (checker.accept, {"bridge_id": "implementation"}),
                            (closure.run, {"endpoint": "restricted_source", "require_state": "END_TO_END_VERIFIED"})):
                            result = operation(pkg, events=events, **options)
                            stages.append(result.to_json()); fsutil.write_json(root / "implementation-stage-results.json", stages)
                            self.assertEqual("PASS", result.status, result.to_json())
                        accepted, pending, diagnostics = checker.verify_published(pkg, "implementation", rebuild=False)
                        self.assertTrue(accepted); self.assertFalse(pending); self.assertEqual([], diagnostics)
                        context = checker.load_context(pkg.root / "bridges/implementation", "implementation", vscore3.selection(pkg)["edge_id"])
                        self.assertEqual(context.readable_selection, info["readable_selection"])
                        self.assertEqual(info["readable_candidate_artifacts"], checker.readable_candidate_metadata(
                            context.readable_selection, context.readable_diagnostics.__getitem__))
                        support = pkg.root / "bridges/implementation" / checker.SEMANTIC_DIR / checker.edge_key(context.edge["edge_id"])
                        manifest = canonical.load_file(support / readable.MANIFEST_PATH)
                        self.assertTrue(manifest["checked_proof_support_dependencies"])
                        snapshot = vscore3_closure.mechanical_snapshot(pkg)
                        self.assertEqual("VERIFIED", snapshot["mechanical_status"])
                        self.assertEqual(["A", "B"], [row["build"] for row in snapshot["builds"]])
                        self.assertTrue(all(row["ok"] for row in snapshot["builds"]))
                        self.assertEqual(snapshot["builds"][0]["outputs"], snapshot["builds"][1]["outputs"])
                        for build in snapshot["builds"]: self.assertEqual("CHECKED", build["outputs"]["readable_support"]["descriptor"]["mode"])
                        projection = review_projection.build(pkg, snapshot); self.assertIsNotNone(projection)
                        packet = review.build_packet(pkg, "release")
                        claim = vscore3.selection(pkg)["edge_claim_id"]
                        probe = review_counterexamples.replay(pkg, "release", {"kind": "mechanical_failure", "claim_id": claim})
                        self.assertEqual("NOT_REPRODUCED", probe["status"], probe)
                        self.assertEqual("PASS", probe["expected"]["outcome"])
                        self.assertEqual("PASS", probe["observed"]["outcome"])
                        fsutil.write_json(root / "release-packet.json", packet)
                        fsutil.write_json(root / "review-projection.json", projection)
                        fsutil.write_json(root / "release-probe.json", probe)
                        fsutil.write_json(root / "mechanical-snapshot.json", snapshot)
                        report = canonical.load_file(pkg.path("report"))
                        self.assertEqual("VERIFIED", report["mechanical_status"])
                        self.assertEqual("restricted_source", report["tier"]["requested_endpoint"])
                        self.assertEqual("END_TO_END_VERIFIED", report["tier"]["require_state"])
                        stage_status = "BUILT_PENDING_RETAINED"
                    finally: events.close()
                finally:
                    # Actual failing attempts and complete module bundles survive
                    # cleanup; no success record can replace an earlier failure.
                    for path in root.iterdir():
                        if path.is_dir(): shutil.copytree(path, destination / path.name)
                        else: shutil.copy2(path, destination / path.name)
                    fsutil.atomic_write(destination / "source-freeze.json", freeze_path.read_bytes())
                    for rel in hashes: fsutil.atomic_write(destination / "registered-sources" / rel, (REPOSITORY / rel).read_bytes())
                    fsutil.write_json(destination / "capture.json", {"format": "verislop.fresh-enum-tier2-capture/1",
                        "qualification": False, "stage_status": stage_status, "model_calls": 0,
                        "source_hashes": hashes, "source_root": canonical.digest_json(hashes),
                        "source_freeze_hash": canonical.digest_file(freeze_path),
                        "files": {str(p.relative_to(destination)): canonical.digest_file(p)
                                  for p in sorted(destination.rglob("*")) if p.is_file()}})
                    print("ENUM_TIER2_FROZEN_ATTEMPT_CAPTURE", destination, flush=True)
            self.assertFalse(root.exists())
            require_frozen_sources(freeze_path)
            retained = Package(destination / "package")
            accepted, pending, diagnostics = checker.verify_published(retained, "implementation", rebuild=False)
            self.assertTrue(accepted); self.assertFalse(pending); self.assertEqual([], diagnostics)
            snapshot = vscore3_closure.mechanical_snapshot(retained)
            self.assertEqual("VERIFIED", snapshot["mechanical_status"])
            claim = vscore3.selection(retained)["edge_claim_id"]
            probe = review_counterexamples.replay(retained, "release", {"kind": "mechanical_failure", "claim_id": claim})
            self.assertEqual("NOT_REPRODUCED", probe["status"], probe)
            self.assertEqual("PASS", probe["observed"]["outcome"])
            fsutil.write_json(annex / "retained-release-probe.json", probe)
            fsutil.write_json(annex / "retained-mechanical-snapshot.json", snapshot)
            portable = True
        except BaseException as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            fsutil.write_json(annex / "result.json", {"format": "verislop.fresh-enum-tier2-retained-check/1",
                "qualification": portable, "mechanical_status": "VERIFIED" if portable else "UNQUALIFIED",
                "attempt": str(destination.relative_to(REPOSITORY)), "capture_hash": canonical.digest_file(destination / "capture.json")
                    if (destination / "capture.json").is_file() else None,
                "original_temporary_root_removed": portable, "model_calls": 0, "error": error,
                "source_root": canonical.digest_json(hashes), "registered_actual_builds": "A,B" if portable else None})
            for capture in (destination, annex):
                for path in capture.rglob("*"):
                    if path.is_file(): path.chmod(0o444)
                for path in sorted((p for p in capture.rglob("*") if p.is_dir()), reverse=True): path.chmod(0o555)
                capture.chmod(0o555)
            print("ENUM_TIER2_RETAINED_CHECK_CAPTURE", annex, flush=True)


if __name__ == "__main__":
    unittest.main()
