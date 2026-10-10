"""Fresh unrelated collection qualification; only a root freeze enables its full run.

All candidate inputs are defined here, independently of task artifacts. Development
previews are unqualified. Set VERISLOP_COLLECTION_QUALIFICATION_FREEZE to the root's
preregistered current-source manifest only after implementation has stopped changing.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
import time
from types import SimpleNamespace
import unittest

from verislop import (accept, agents, canonical, closure, dsl, export, formal_frontend as ff,
                      formalize, fsutil, generate, interpret, leanbridge, link, policy, prove, review,
                      review_counterexamples, review_projection, source_policy, verifiers)
from verislop.backends import vscore3, vscore3_closure
from verislop.bridges import vscore3_checker as checker
from verislop.events import EventSink
from verislop.errors import InfrastructureError
from verislop.exprjson import name_str, parse_name, semantic_refs
from verislop.package import Package
from verislop.targets import (vscore3_check as admission, vscore3_readable as readable,
                              vscore3_replay as replay, vscore3_source as source, vscore3_target as target)

REPOSITORY = Path(__file__).resolve().parents[1]
CAPTURE_ROOT = REPOSITORY / "validation" / "tier2-proof-support-017-collection-design" / "qualification"
FREEZE_ENV = "VERISLOP_COLLECTION_QUALIFICATION_FREEZE"
REQUEST = (
    b"Deliver pure VSCore 0.3 source. Shade has exactly light, dark and neutral. Parcel has shade:Shade "
    b"and n:Nat. Envelope has parcel:Parcel and active:Bool. The domain includes every Shade, every "
    b"mathematical natural, every Envelope and every finite list, preserving order and duplicates. "
    b"shiftEnvelopes(xs,increment) adds increment to each parcel.n and preserves shade and active. "
    b"keepParcel(xs,needle) keeps exactly envelopes whose entire parcel equals needle. "
    b"shadeTotal(xs,initial,shade) left-folds from initial, adding parcel.n exactly for matching shades. "
    b"sameShade(x,y) returns the fixed canonical equality decision of the two shades. "
    b"The source map calls a helper which calls another helper, with heterogeneous declared-order "
    b"arguments; map/filter/fold lambdas capture increment, needle and shade respectively. "
    b"The shadeTotal step also calls a helper. The accepted filter uses fixed enum/Nat field decisions, "
    b"and source filtering uses intrinsic full Parcel equality; prove their universal correspondence. "
    b"shiftEnvelopes also has independently required source properties and a Mixed value/source guarantee. "
    b"A distinct inspectEnvelope source entry takes one Envelope and returns Nat, with source properties "
    b"only and no value equation. Required source properties are typed total evaluation, deterministic "
    b"results, preserved inputs, no external I/O or floating point, pure data and restricted runtime. "
    b"An Envelope with light, zero and inactive witnesses the full typed domain. Deliver program.vscore.json "
    b"under restricted VSCore source semantics; no host-language execution guarantee is requested."
)
SHADE, PARCEL, ENVELOPE = {"enum": "Shade"}, {"record": "Parcel"}, {"record": "Envelope"}
ENVELOPES = {"list": ENVELOPE}
PROPERTIES = ["typed_total", "deterministic", "input_preserved", "no_external_io",
              "no_floating_point", "pure_data", "restricted_runtime_only"]
SUPPORT_NAMES = {"VSCore3.ProofSupport." + n for n in
                 ("to_eq_iff", "decide_to_eq", "map_transport", "filter_transport", "foldl_transport")}


def var(index):
    return {"tag": "var", "index": index}


def field(sort, name, value):
    return {"tag": "field", "sort": sort, "field": name, "value": value}


def parcel(value):
    return field("Envelope", "parcel", value)


def shade(value):
    return field("Parcel", "shade", value)


def amount(value):
    return field("Parcel", "n", value)


def call(symbol, arguments):
    return {"tag": "call", "symbol": symbol, "args": arguments}


def universally(sorts, body):
    for sort in reversed(sorts):
        body = {"tag": "forall", "sort": sort, "body": body}
    return body


SHIFT_BODY = {"tag": "list_map", "value": var(1), "function": {"sort": ENVELOPE, "body": {
    "tag": "record", "sort": "Envelope", "fields": [
        {"tag": "record", "sort": "Parcel", "fields": [shade(parcel(var(0))),
            {"tag": "add", "left": amount(parcel(var(0))), "right": var(1)}]},
        field("Envelope", "active", var(0))]}}}
FILTER_BODY = {"tag": "list_filter", "value": var(1), "function": {"sort": ENVELOPE, "body": {
    "tag": "bool_and", "left": {"tag": "bool_eq", "left": shade(parcel(var(0))), "right": shade(var(1))},
    "right": {"tag": "bool_eq", "left": amount(parcel(var(0))), "right": amount(var(1))}}}}
FOLD_BODY = {"tag": "list_foldl", "value": var(2), "initial": var(1), "function": {
    "accumulator_sort": "Nat", "element_sort": ENVELOPE, "body": {"tag": "ite",
        "condition": {"tag": "bool_eq", "left": shade(parcel(var(0))), "right": var(2)},
        "then": {"tag": "add", "left": var(1), "right": amount(parcel(var(0)))}, "else": var(1)}}}
EQUALITY_BODY = {"tag": "bool_eq", "left": var(1), "right": var(0)}
SYMBOLS = {
    "shiftEnvelopes": {"args": [ENVELOPES, "Nat"], "result": ENVELOPES, "body": SHIFT_BODY},
    "keepParcel": {"args": [ENVELOPES, PARCEL], "result": ENVELOPES, "body": FILTER_BODY},
    "shadeTotal": {"args": [ENVELOPES, "Nat", SHADE], "result": "Nat", "body": FOLD_BODY},
    "sameShade": {"args": [SHADE, SHADE], "result": "Bool", "body": EQUALITY_BODY},
    # This reference body has no accepted value guarantee; solely operational
    # source delivery must not introduce a refinement equation for it.
    "inspectEnvelope": {"args": [ENVELOPE], "result": "Nat", "body": amount(parcel(var(0)))},
}
VALUE_OBLIGATIONS = {"G-map": ("law_shift", "shiftEnvelopes"), "G.filter": ("law_filter", "keepParcel"),
                     "G:fold": ("law_fold", "shadeTotal"), "G-equality": ("law_equality", "sameShade")}
OBLIGATIONS = [("D1", "entity", "declaration"), ("A1", "precondition", "assumption"),
               *((oid, "postcondition", "guarantee") for oid in VALUE_OBLIGATIONS),
               ("S:delivery.only", "safety_property", "guarantee")]
SOURCE_POLICY = {"schema_version": "0.1", "format": source_policy.FORMAT, "obligations": {
    "G-map": {"file": "program.vscore.json", "entry": "shiftEnvelopes", "arity": 2,
              "properties": PROPERTIES, "value_required": True},
    "S:delivery.only": {"file": "program.vscore.json", "entry": "inspectEnvelope", "arity": 1,
                        "properties": PROPERTIES, "value_required": False}}}
AST = {"encoding": ff.VERSION_V2, "enums": {"Shade": {"constructors": ["light", "dark", "neutral"]}},
       "records": {"Parcel": {"fields": [{"name": "shade", "sort": SHADE}, {"name": "n", "sort": "Nat"}]},
                   "Envelope": {"fields": [{"name": "parcel", "sort": PARCEL}, {"name": "active", "sort": "Bool"}]}},
       "symbols": SYMBOLS,
       "predicates": {"envelope_domain": {"args": [ENVELOPE], "formula": {
           "tag": "eq", "left": amount(parcel(var(0))), "right": amount(parcel(var(0)))}}},
       "source_requirements": {name: {"symbol": symbol, "requirements": [
           {"tag": "entry", "file": "program.vscore.json", "entry": symbol, "arity": arity},
           *({"tag": tag} for tag in PROPERTIES)]}
           for name, symbol, arity in (("MapDelivery", "shiftEnvelopes", 2), ("InspectDelivery", "inspectEnvelope", 1))},
       "theorems": {theorem: {"formula": universally(SYMBOLS[symbol]["args"], {"tag": "eq",
           "left": call(symbol, [var(len(SYMBOLS[symbol]["args"]) - i - 1)
                                 for i in range(len(SYMBOLS[symbol]["args"]))]),
           "right": SYMBOLS[symbol]["body"]}), **({"source": ["MapDelivery"]} if oid == "G-map" else {})}
           for oid, (theorem, symbol) in VALUE_OBLIGATIONS.items()},
       "obligations": {"D1": {"declarations": [{"kind": "enum", "name": "Shade"},
           {"kind": "record", "name": "Parcel"}, {"kind": "record", "name": "Envelope"},
           *({"kind": "symbol", "name": name} for name in SYMBOLS)]},
           "A1": {"predicate": "envelope_domain"},
           **{oid: {"theorem": theorem} for oid, (theorem, _) in VALUE_OBLIGATIONS.items()},
           "S:delivery.only": {"theorem": "source_delivery"}},
       "witness_obligations": {"W1": {"theorem": "inhabited_domain", "witnesses_for": ["A1"],
           "description": "light, natural zero and inactive inhabit the full typed Envelope domain"}}}
AST["theorems"].update({"source_delivery": {"source": ["InspectDelivery"]}, "inhabited_domain": {
    "formula": {"tag": "exists", "sort": ENVELOPE,
                "body": {"tag": "predicate", "predicate": "envelope_domain", "args": [var(0)]}}}})
SURFACE = '''program "vscore/0.3" profile "data-pipeline/0.3";
record Parcel { shade: Enum(Shade); n: Nat; }
record Envelope { parcel: Record(Parcel); active: Bool; }
fn shiftParcel(increment:Nat,p:Record(Parcel))->Record(Parcel){
  record Parcel{shade=p.shade,n=p.n+increment}
}
fn shiftEnvelope(increment:Nat,e:Record(Envelope))->Record(Envelope){
  record Envelope{parcel=call shiftParcel(increment,e.parcel),active=e.active}
}
fn keepEnvelope(needle:Record(Parcel),e:Record(Envelope))->Bool{e.parcel == needle}
fn totalStep(chosen:Enum(Shade),acc:Nat,e:Record(Envelope))->Nat{
  if e.parcel.shade == chosen then acc+e.parcel.n else acc
}
entry shiftEnvelopes(xs:List(Record(Envelope)),increment:Nat)->List(Record(Envelope)){
  List.map(xs;e=>call shiftEnvelope(increment,e))
}
entry keepParcel(xs:List(Record(Envelope)),needle:Record(Parcel))->List(Record(Envelope)){
  List.filter(xs;e=>call keepEnvelope(needle,e))
}
entry shadeTotal(xs:List(Record(Envelope)),initial:Nat,chosen:Enum(Shade))->Nat{
  List.fold(xs,initial;acc,e=>call totalStep(chosen,acc,e))
}
entry sameShade(x:Enum(Shade),y:Enum(Shade))->Bool{x == y}
entry inspectEnvelope(e:Record(Envelope))->Nat{0}
'''
RELATION = {"schema_version": "0.3", "format": target.RELATION_FORMAT, "template": target.TEMPLATE,
            "source_slot": "vscore-source", "proof_slot": "vscore-proof",
            "bindings": [{"symbol": name, "entry": name} for name in sorted(SYMBOLS)]}


def qualification_source_files():
    return sorted({"verislop/" + rel for spec in verifiers.VERIFIERS.values()
                   for rel in verifiers.CORE + spec["sources"]}
                  | {"schemas/" + name for spec in verifiers.VERIFIERS.values() for name in spec["schemas"]}
                  | {str((target.LIB_ROOT / target.module_path(module)).relative_to(REPOSITORY))
                     for module in target.LIB_MODULES}
                  | {"docs/bootstrap-tier2-collection-proof-support.md", "tests/test_vscore3_proof_support.py",
                     "tests/test_vscore3_collection_bridge.py",
                     "validation/tier2-native-boundary-gate-017/qualification-specification.json",
                     "validation/tier2-native-boundary-gate-017/gate.py"})


def require_frozen_sources(path):
    frozen = canonical.load_file(path)
    hashes = frozen.get("source_hashes", frozen.get("source_files"))
    if not isinstance(hashes, dict) or set(qualification_source_files()) - set(hashes):
        raise AssertionError("collection qualification freeze must bind every registered source/schema and fixture/spec/driver")
    for rel, expected in hashes.items():
        file = REPOSITORY / rel
        if not file.is_file() or canonical.digest_file(file) != expected:
            raise AssertionError("collection qualification source changed after freeze: " + rel)
    return hashes


def accepted_collection_fixture(root):
    """Actual compiler, denotation audits, witnesses and accepted AST reconstruction."""
    pkg = Package(root / "package"); pkg.ensure("generic-shade-parcel-envelope-tier2")
    policy_input = root / "required-source-policy.json"; fsutil.write_json(policy_input, SOURCE_POLICY)
    source_policy.stage(pkg, policy_input)
    pkg.set_meta("requested", {"tier": 2, "target": "vscore", "endpoint": "restricted_source",
                 "backend_version": "0.3", "require_state": "END_TO_END_VERIFIED"})
    request = root / "request.txt"; request.write_bytes(REQUEST)
    interpretation = {"obligations": [{"id": oid, "kind": kind, "role": role, "statement": REQUEST.decode(),
        "required": True, "scope": ["all alternatives, unbounded naturals, arbitrary finite lists and accumulators"],
        "dependencies": [], "acceptance_criteria": ["exact nominal types, universal values and the stated source facets"],
        "sources": [{"quote": REQUEST.decode(), "origin": "explicit", "interpretation": "the unrelated collection source contract"}]}
        for oid, kind, role in OBLIGATIONS],
        "category_review": {kind: "reviewed for the universal unrelated collection fixture" for kind in agents.DRAFT_CATEGORIES},
        "clauses": [{"quote": REQUEST.decode(), "disposition": "obligations", "refs": [oid for oid, _, _ in OBLIGATIONS]}],
        "assumptions": [{"id": "A1", "supplied_by": "the full typed Envelope domain", "discharged_at": "constructive witness W1"}],
        "ambiguities": [], "selected_defaults": []}
    response = canonical.dumps(AST); fsutil.atomic_write(pkg.root / "formalizer-response.json", response)
    stages = []

    def retain(result):
        stages.append(result.to_json()); fsutil.write_json(root / "contract-stage-results.json", stages)
        if result.status != "PASS":
            raise AssertionError(result.to_json())

    def interpreter(data, ref, routing):
        draft, ledger, problems = agents.assemble_interpretation(interpretation, data, ref)
        if problems:
            raise AssertionError(problems)
        return draft, ledger

    def author(context):
        compiled = ff.compile_response(response, context["records"], "generic.collection.shade",
                                       response_ref="formalizer-response.json")
        fsutil.write_json(pkg.root / "formalizer-frozen.json", context["records"])
        author.last_compiled = compiled
        author.last_origin = {"proposal": compiled.proposal, "receipt": compiled.receipt}
        if not ff.reconstruct_origin(response, context["records"], compiled.source, compiled.formalization, compiled.receipt):
            raise AssertionError("fresh collection compiler origin did not replay")
        return compiled.source, compiled.formalization

    events = EventSink(pkg.run_id, pkg.root, quiet=True)
    try:
        retain(interpret.run(pkg, events, request, mode="software", request_ref="request.txt", agent=interpreter))
        retain(formalize.run(pkg, events, agent=author, max_attempts=1))
        challenge = (pkg.path("contract") / "challenge/Contract.lean").read_text()
        tactics = {theorem: "intros; rfl" for theorem, _ in VALUE_OBLIGATIONS.values()}
        tactics.update({"law_shift": "exact ⟨by intros; rfl, VeriSlop.Source.contract_sound _⟩",
                        "source_delivery": "exact VeriSlop.Source.contract_sound _",
                        "inhabited_domain": "exact ⟨VeriSlopAST.Envelope.mk (VeriSlopAST.Parcel.mk VeriSlopAST.Shade.light 0) false, rfl⟩"})
        authored = challenge
        for offset in reversed(prove.sorry_sites(challenge)):
            name = prove._short(prove.enclosing_decl(challenge, offset))
            authored = authored[:offset] + tactics[name] + authored[offset + 5:]
        proof = root / "contract-proof.lean"; proof.write_text(authored)
        retain(prove.run(pkg, events, budget_seconds=0, candidate=proof, portfolio=False))
        retain(accept.run(pkg, events)); retain(export.run(pkg, events))
        return pkg
    finally:
        events.close()


def bridge_proof(spec, *, baseline=False):
    adapters = {canonical.dumps(row.sort): row.name for row in spec.adapters}
    enum, record, envelope, nat = (adapters[canonical.dumps(sort)] for sort in (SHADE, PARCEL, ENVELOPE, "Nat"))
    prefix = """import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
open VeriSlopBridgeGoal VSCore3.ProofSupport
set_option maxRecDepth 100000
set_option maxHeartbeats 20000000
"""
    if baseline:
        return (prefix + "\n".join(f"theorem direct_{name} : Refines_{name} := by\n  intro {binders}\n  rw [Readable.source_eq_{name}]\n  with_unfolding_all rfl"
                for name, binders in (("shiftEnvelopes", "xs increment"), ("keepParcel", "xs needle"),
                                      ("shadeTotal", "xs initial chosen"), ("sameShade", "x y"))) +
                "\nend VeriSlopBridgeProof\n").encode()
    helpers = ", ".join("VeriSlopReadableSource." + row["name"] + "_" + suffix
                        for row in spec.readable_view.functions if row["role"] == "helper"
                        for suffix in ("named", "run", "body"))
    record_shape = next(row.shape for row in spec.adapters if row.sort == PARCEL)
    return (prefix + f"""
theorem ref_map : Refines_shiftEnvelopes := by
  intro xs increment
  rw [Readable.source_eq_shiftEnvelopes]
  with_unfolding_all
    apply map_transport {envelope} {envelope}
    intro e
    rfl

theorem ref_filter : Refines_keepParcel := by
  intro xs needle
  rw [Readable.source_eq_keepParcel]
  with_unfolding_all
    apply filter_transport {envelope}
    intro e
    simp only [{helpers}, VSCore3.envReverse, VSCore3.envReverseAux, Eq.mp, Eq.mpr, cast_eq]
    letI := VSCore3.denoteDecidableEq {record_shape}
    change decide ({record}.to e.parcel = {record}.to needle) = _
    apply Bool.eq_iff_iff.mpr
    simp only [decide_eq_true_eq, Bool.and_eq_true]
    change {record}.to e.parcel = {record}.to needle ↔ e.parcel.shade = needle.shade ∧ e.parcel.n = needle.n
    rw [to_eq_iff]
    constructor
    · intro h; cases h; exact ⟨rfl, rfl⟩
    · rintro ⟨hs, hn⟩
      cases e with
      | mk p active =>
        cases p with
        | mk shade n =>
          cases needle with
          | mk shade2 n2 => simp_all

theorem ref_fold : Refines_shadeTotal := by
  intro xs initial chosen
  rw [Readable.source_eq_shadeTotal]
  with_unfolding_all
    apply foldl_transport {envelope} {nat}
    intro z e
    cases e with
    | mk p active =>
      cases p with
      | mk shade n => cases shade <;> cases chosen <;> rfl

theorem ref_equality : Refines_sameShade := by
  intro x y
  rw [Readable.source_eq_sameShade]
  letI := VSCore3.denoteDecidableEq (.enum "Shade" ["light", "dark", "neutral"])
  with_unfolding_all
    exact decide_to_eq {enum} x y

theorem edge : EdgeProp := edge_of_refines ref_filter ref_equality ref_fold ref_map
end VeriSlopBridgeProof
""").encode()


def retain_preview(root, label, pkg, delivered, relation, proof=None, **options):
    attempt = root / "previews" / label
    fsutil.atomic_write(attempt / "program.vscore.json", delivered)
    fsutil.atomic_write(attempt / "relation.json", relation)
    if proof is not None:
        fsutil.atomic_write(attempt / "Proof.lean", proof)
    try:
        spec, build, info = checker.preview(pkg, delivered, relation, proof, **options)
    except checker.EdgeFailure as exc:
        fsutil.write_json(attempt / "failure.json", {"qualification": False,
                          "diagnostics": [diagnostic.to_json() for diagnostic in exc.diagnostics]})
        raise
    fsutil.atomic_write(attempt / "VeriSlopBridgeGoal.lean", spec.text.encode())
    fsutil.write_json(attempt / "declarations.json", build.decls)
    fsutil.write_json(attempt / "observation.json", build.observation)
    fsutil.write_json(attempt / "processes.json", build.process_evidence)
    for module, parts in build.modules.items():
        for suffix, data in parts.items():
            fsutil.atomic_write(attempt / "modules" / (module + suffix), data)
    for path, data in info.get("readable_candidate_artifacts", {}).items():
        fsutil.atomic_write(attempt / path, data)
    return spec, build, info


def proof_dependencies(roots, declarations):
    """Kernel-exported proof references, including theorem bodies (not just types)."""
    seen, pending = set(), list(roots)
    while pending:
        name = pending.pop()
        if name in seen or name not in declarations:
            continue
        seen.add(name)
        row = declarations[name]
        pending.extend(semantic_refs(row) | {name_str(n) for n in row.get("value_constants", [])})
    return seen


def concrete_wrong_source_control(root, test, pkg, certificate, spec, build):
    """The registered bounded replay decides the exact accepted value predicate."""
    assignment = [[dsl.record_v("Envelope", [dsl.record_v("Parcel", [dsl.enum_v("Shade", "light"), 0]), False])], 1]
    formula = next(row.formula for row in spec.obligations if row.oid == "G-map")
    expression = replay.ground(spec, formula, assignment)
    selected_policy = next(row for row in policy.POLICIES.values()
                           if row["id"] == certificate["policy"]["id"]
                           and policy.policy_hash(row) == certificate["policy"]["hash"])
    ctx = SimpleNamespace(policy=selected_policy,
                          contract_module=(pkg.root / certificate["artifacts"]["olean"]["path"]).read_bytes())
    record = {"claim_id": "G-map", "qualification": False, "replay_budget_seconds": 30,
              "public_assignment": {"xs": [{"parcel": {"shade": "light", "n": 0}, "active": False}], "increment": 1},
              "ground_expression": expression, "source_hash": canonical.digest(spec.source_bytes),
              "goal_module_parts_hash": checker._parts_digest(build.modules[target.GOAL_MODULE])}
    try:
        result = replay.check(leanbridge.resolve_toolchain(certificate["toolchain"]["pin"]), ctx, spec, expression,
                              deadline=time.monotonic() + 30, goal_parts=build.modules[target.GOAL_MODULE])
    except (replay.Unsupported, dsl.BudgetExceeded, InfrastructureError) as exc:
        record.update(status="UNRESOLVED_REPLAY_BOUNDARY", error={"type": type(exc).__name__, "message": str(exc)})
    else:
        test.assertIs(result["predicate"], False, result)
        test.assertTrue(result["kernel_replay"])
        record.update(status="KERNEL_PROVED_FALSE", result=result)
    finally:
        fsutil.write_json(root / "concrete-wrong-source-control.json", record)


def prepared_collection_candidate(root, test):
    pkg = accepted_collection_fixture(root)
    certificate = canonical.load_file(pkg.path("accepted") / "acceptance.json")
    profile = dsl.Profile.from_json(canonical.load_file(pkg.root / certificate["artifacts"]["profile"]["path"]))
    test.assertEqual(["light", "dark", "neutral"], profile.enums["Shade"]["constructors"])
    test.assertNotIn("candidate_decidable_eq", profile.enums["Shade"])
    test.assertIn("decl_hash", profile.enums["Shade"]["decidable_eq"])
    enums = {name: row["constructors"] for name, row in profile.enums.items()}
    delivered = source.compile_surface(SURFACE, enums)
    fsutil.atomic_write(root / "program.vscore.json", delivered)
    fsutil.atomic_write(root / "program.vsc", SURFACE.encode())
    admitted = admission.check(delivered, enums, root / "source-admission")
    fsutil.write_json(root / "source-admission-result.json", admitted.to_json())
    test.assertEqual("PASS", admitted.status, admitted.to_json())
    relation = canonical.dumps(RELATION)
    spec, built, info = retain_preview(root, "selected", pkg, delivered, relation, select_readable=True)
    test.assertEqual("CHECKED", built.readable_support["mode"])
    test.assertEqual("CHECKED", canonical.loads(info["readable_selection"])["selected_mode"])
    helpers = [row for row in spec.readable_view.functions if row["role"] == "helper"]
    test.assertEqual({"shiftParcel", "shiftEnvelope", "keepEnvelope", "totalStep"}, {row["source_id"] for row in helpers})
    test.assertEqual(set(SYMBOLS) - {"inspectEnvelope"}, spec.refinement_symbols)
    test.assertIn("SourceAdequate_inspectEnvelope", spec.expected)
    test.assertIn("SourceAdequate_shiftEnvelopes", spec.expected)
    test.assertNotIn("Refines_inspectEnvelope", str(spec.expected["EdgeProp"]))
    selected_options = {"readable_selection": info["readable_selection"],
                        "readable_diagnostics": info["readable_candidate_artifacts"]}
    with test.assertRaises(checker.EdgeFailure) as failed:
        retain_preview(root, "direct-conversion-baseline", pkg, delivered, relation,
                       bridge_proof(spec, baseline=True), **selected_options)
    test.assertTrue(any(d.code == "CANDIDATE_BUILD_FAILURE" for d in failed.exception.diagnostics))
    test.assertTrue(any("Tactic `rfl` failed" in error for d in failed.exception.diagnostics
                        for error in d.details.get("errors", [])))
    proof = bridge_proof(spec)
    _, checked, _ = retain_preview(root, "positive", pkg, delivered, relation, proof, **selected_options)
    names = proof_dependencies({target.EDGE_THEOREM}, checked.decls)
    test.assertTrue(SUPPORT_NAMES <= names, sorted(SUPPORT_NAMES - names))
    for oid in VALUE_OBLIGATIONS:
        identity = name_str([target.GOAL_MODULE, "transfer_" + oid])
        row = checked.decls[identity]
        test.assertEqual("theorem", row["kind"])
        test.assertEqual([target.GOAL_MODULE, "transfer_" + oid], parse_name(identity))
    wrong = source.compile_surface(SURFACE.replace("n=p.n+increment", "n=p.n+increment+1"), enums)
    wrong_admission = admission.check(wrong, enums, root / "wrong-source-admission")
    fsutil.write_json(root / "wrong-source-admission-result.json", wrong_admission.to_json())
    test.assertEqual("PASS", wrong_admission.status, wrong_admission.to_json())
    wrong_spec, wrong_built, wrong_info = retain_preview(root, "wrong-source-selected", pkg, wrong, relation, select_readable=True)
    test.assertEqual("CHECKED", wrong_built.readable_support["mode"])
    concrete_wrong_source_control(root, test, pkg, certificate, wrong_spec, wrong_built)
    with test.assertRaises(checker.EdgeFailure) as failed:
        retain_preview(root, "semantically-wrong-source", pkg, wrong, relation, bridge_proof(wrong_spec),
                       readable_selection=wrong_info["readable_selection"],
                       readable_diagnostics=wrong_info["readable_candidate_artifacts"])
    test.assertTrue(any(d.code == "CANDIDATE_BUILD_FAILURE" for d in failed.exception.diagnostics))
    tampered = canonical.loads(info["readable_selection"])
    tampered["checked_descriptor"]["selected_goal_hash"] = "sha256:" + "0" * 64
    with test.assertRaises(checker.EdgeFailure):
        retain_preview(root, "tampered-readable-selection", pkg, delivered, relation, proof,
                       readable_selection=canonical.dumps(tampered),
                       readable_diagnostics=info["readable_candidate_artifacts"])
    candidate = root / "candidate"
    for path, data in {"program.vscore.json": delivered, "relation.json": relation, "Proof.lean": proof,
                       **info["readable_candidate_artifacts"]}.items():
        fsutil.atomic_write(candidate / path, data)
    return pkg, candidate, info


@unittest.skipUnless(os.environ.get(FREEZE_ENV), "full collection qualification requires root-frozen current sources")
class CollectionRegisteredTier2Tests(unittest.TestCase):
    def test_actual_frozen_collection_closure_and_retained_release_probe(self):
        freeze_path = Path(os.environ[FREEZE_ENV]); hashes = require_frozen_sources(freeze_path)
        CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
        destination = Path(tempfile.mkdtemp(prefix="frozen-attempt-", dir=CAPTURE_ROOT))
        annex = Path(tempfile.mkdtemp(prefix="retained-check-", dir=CAPTURE_ROOT))
        stage_status = "UNQUALIFIED"; portable = False; error = None
        try:
            with tempfile.TemporaryDirectory(prefix="fresh-shade-collection-tier2-") as dirname:
                root = Path(dirname)
                try:
                    pkg, candidate, info = prepared_collection_candidate(root, self)
                    require_frozen_sources(freeze_path)
                    events = EventSink(pkg.run_id, pkg.root, quiet=True)
                    try:
                        stages = []
                        for operation, options in (
                            (generate.run, {"tier": 2, "target": "vscore", "backend_version": "0.3", "candidate": candidate}),
                            (link.run, {}), (checker.accept, {"bridge_id": "implementation"}),
                            (closure.run, {"endpoint": "restricted_source", "require_state": "END_TO_END_VERIFIED"})):
                            result = operation(pkg, events=events, **options)
                            stages.append(result.to_json()); fsutil.write_json(root / "implementation-stage-results.json", stages)
                            self.assertEqual("PASS", result.status, result.to_json())
                        accepted, pending, diagnostics = checker.verify_published(pkg, "implementation", rebuild=False)
                        self.assertTrue(accepted); self.assertFalse(pending); self.assertEqual([], diagnostics)
                        context = checker.load_context(pkg.root / "bridges/implementation", "implementation", vscore3.selection(pkg)["edge_id"])
                        self.assertEqual(context.readable_selection, info["readable_selection"])
                        support = pkg.root / "bridges/implementation" / checker.SEMANTIC_DIR / checker.edge_key(context.edge["edge_id"])
                        manifest = canonical.load_file(support / readable.MANIFEST_PATH)
                        self.assertTrue(manifest["checked_proof_support_dependencies"])
                        snapshot = vscore3_closure.mechanical_snapshot(pkg)
                        self.assertEqual("VERIFIED", snapshot["mechanical_status"])
                        self.assertEqual(["A", "B"], [row["build"] for row in snapshot["builds"]])
                        self.assertTrue(all(row["ok"] for row in snapshot["builds"]))
                        self.assertEqual(snapshot["builds"][0]["outputs"], snapshot["builds"][1]["outputs"])
                        for build in snapshot["builds"]:
                            self.assertEqual("CHECKED", build["outputs"]["readable_support"]["descriptor"]["mode"])
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
                        require_frozen_sources(freeze_path)
                        stage_status = "BUILT_PENDING_RETAINED"
                    finally:
                        events.close()
                finally:
                    for path in root.iterdir():
                        if path.is_dir(): shutil.copytree(path, destination / path.name)
                        else: shutil.copy2(path, destination / path.name)
                    fsutil.atomic_write(destination / "source-freeze.json", freeze_path.read_bytes())
                    for rel in hashes:
                        fsutil.atomic_write(destination / "registered-sources" / rel, (REPOSITORY / rel).read_bytes())
                    fsutil.write_json(destination / "capture.json", {"format": "verislop.fresh-collection-tier2-capture/1",
                        "qualification": False, "stage_status": stage_status, "model_calls": 0,
                        "source_hashes": hashes, "source_root": canonical.digest_json(hashes),
                        "source_freeze_hash": canonical.digest_file(freeze_path),
                        "files": {str(p.relative_to(destination)): canonical.digest_file(p)
                                  for p in sorted(destination.rglob("*")) if p.is_file()}})
                    print("COLLECTION_TIER2_FROZEN_ATTEMPT_CAPTURE", destination, flush=True)
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
            fsutil.write_json(annex / "result.json", {"format": "verislop.fresh-collection-tier2-retained-check/1",
                "qualification": portable, "mechanical_status": "VERIFIED" if portable else "UNQUALIFIED",
                "attempt": str(destination.relative_to(REPOSITORY)),
                "capture_hash": canonical.digest_file(destination / "capture.json") if (destination / "capture.json").is_file() else None,
                "original_temporary_root_removed": portable, "model_calls": 0, "error": error,
                "source_root": canonical.digest_json(hashes), "registered_actual_builds": "A,B" if portable else None})
            for capture in (destination, annex):
                for path in capture.rglob("*"):
                    if path.is_file(): path.chmod(0o444)
                for path in sorted((p for p in capture.rglob("*") if p.is_dir()), reverse=True): path.chmod(0o555)
                capture.chmod(0o555)
            print("COLLECTION_TIER2_RETAINED_CHECK_CAPTURE", annex, flush=True)


if __name__ == "__main__":
    unittest.main()
