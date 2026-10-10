"""Fresh generic readable fixtures: no retained task sources or expected answers."""
from __future__ import annotations

import copy
import tempfile
import json
import shutil
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from pathlib import Path

from helpers import TempDir
from verislop import canonical, leanbridge, policy, schemas, fsutil
from verislop import agents
from verislop.errors import Diagnostic
from verislop.events import EventSink
from verislop.package import Package
from verislop.bridges import vscore3_checker as C, vscore3_readable_support as RS, prepare
from verislop.targets import vscore3_target as T, vscore3_source as S, vscore3_readable as R

CONTRACT='''import Std
namespace ReadableFixture
def difference (x y : Int) : Int := x - y
theorem difference_contract : ∀ x y : Int, difference x y = x - y := by intros; rfl
end ReadableFixture
'''.encode()
PROOF=b'''import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  intro x y
  with_unfolding_all rfl
end VeriSlopBridgeProof
'''


def fixture():
    p={"profile_id":"fresh-readable","dsl":"verislop.contract-dsl/0.2","enums":{},"predicates":{},"records":{},
       "symbols":{"difference":{"lean_decl":"ReadableFixture.difference","args":["Int","Int"],"result":"Int"}}}
    source=S.source_bytes({"language":S.LANGUAGE,"profile":S.PROFILE,"declarations":[],"helpers":[],
        "entries":[{"id":"difference","params":["int","int"],"result":"int","body":("bin","sub",("var",1),("var",0))}]})
    relation={"schema_version":"0.3","format":T.RELATION_FORMAT,"template":T.TEMPLATE,
        "source_slot":"vscore-source","proof_slot":"vscore-proof","bindings":[{"symbol":"difference","entry":"difference"}]}
    v=lambda i:{"tag":"var","index":i}
    formula={"tag":"forall","sort":"Int","body":{"tag":"forall","sort":"Int","body":{"tag":"eq",
        "left":{"tag":"call","symbol":"difference","args":[v(1),v(0)]},
        "right":{"tag":"int_sub","left":v(1),"right":v(0)}}}}
    obs={"RD1":{"formula":formula,"lean_symbol":"ReadableFixture.difference_contract","statement_hash":"sha256:"+"3"*64,"revision":1}}
    return source,relation,p,obs


def context(contract):
    source,relation,p,obs=fixture()
    return C.EdgeContext("fresh",{},"sha256:"+"a"*64,"sha256:"+"b"*64,
        {"edge_id":"fresh","expected_proposition_hash":None},{"claim_id":"FRESH"},{},relation,
        {"source":("vscore-source",source),"relation":("vscore-relation",canonical.dumps(relation)),
         "proof_source":("vscore-proof",PROOF)}, {}, {"toolchain":{"pin":leanbridge.DEFAULT_TOOLCHAIN}},
        p,"sha256:"+"0"*64,contract,policy.get("strict"),obs)


def matrix_context(contract):
    ctx=context(contract);prog=S.parse_source(ctx.inputs["source"][1])
    v=lambda i:("var",i)
    op=lambda name,a,b:("bin",name,a,b)
    ni=("list","int");nn=("list","nat");ns=("list","string")
    result=("result","string","int");small=("record","Small");crate=("record","Crate")
    def h(name,params,ret,body):return {"id":name,"params":params,"result":ret,"body":body}
    prog["declarations"]=[{"tag":"record","id":"Small","fields":[("score","int"),("enabled","bool")]},
        {"tag":"record","id":"Crate","fields":[("small",small),("items",("list",("option",result)))]}]
    prog["helpers"]=[
      h("early",["int","int"],"int",("call","leaf",[v(1),v(0)])),
      h("capturedMap",[ni,"int"],ni,("list_map",v(1),("call","early",[v(0),v(1)]))),
      h("capturedFilter",[ni,"int"],ni,("list_filter",v(1),op("le",v(0),v(1)))),
      h("listAccumulator",[ni,"int","int"],"int",("list_fold",v(2),v(1),op("sub",op("add",v(1),v(2)),v(0)))),
      h("natAccumulator",["nat","nat","nat"],"nat",("nat_fold",v(2),v(1),op("sub",op("add",v(0),v(2)),v(1)))),
      h("listCase",[ni,"int"],"int",("match_list",v(1),v(0),op("sub",v(1),v(2)))),
      h("optionCase",[("option","int"),"int"],"int",("match_option",v(1),v(0),op("sub",v(0),v(1)))),
      h("resultCase",[result,"int"],"int",("match",v(1),op("add",v(0),v(1)),v(1))),
      h("resultOk",["int"],result,("ok","string",v(0))),
      h("resultError",["string"],result,("error","int",v(0))),
      h("maybe",["int","bool"],("option","int"),("ite",v(0),("some",v(1)),("none","int"))),
      h("intMath",["int","int"],"int",("let",op("mul",v(1),v(0)),("ite",op("and",op("lt",v(2),v(1)),("not",op("eq",v(2),v(1)))),("int_neg",v(0)),("int_fdiv",v(0),v(1))))),
      h("natMath",["nat","nat"],"nat",("int_to_nat",("nat_to_int",op("mul",op("add",v(1),v(0)),op("sub",v(1),v(0)))))),
      h("listPrimitives",[ni,"nat"],"int",("list_sum",("list_unique",("list_sort",("list_reverse",("list_append",v(1),("cons",("int",-7),("nil","int")))))))),
      h("natPrimitives",["nat"],("option","nat"),("list_get",("list_range",v(0)),("list_length",("list_range",v(0))))),
      h("stringOrder",[ns,"string"],ns,("list_sort",("list_unique",("cons",("string",tuple(map(ord,"λ snow"))),v(1))))),
      h("stringCompare",["string","string"],"bool",op("or",op("lt",v(1),v(0)),op("le",v(1),v(0)))),
      h("unitValue",[],"unit",("unit",)),
      h("boolValue",[],"bool",("bool",True)),
      h("natValue",[],"nat",("nat",11)),
      h("enumValue",[],("enum","Mood"),("enum","Mood","clear")),
      h("makeSmall",["int","bool"],small,("record","Small",[("score",v(1)),("enabled",v(0))])),
      h("makeCrate",[small,("list",("option",result))],crate,("record","Crate",[("small",v(1)),("items",v(0))])),
      h("nestedField",[crate],"int",("project",("project",v(0),"small"),"score")),
      h("nominalEq",[crate,crate],"bool",op("eq",v(1),v(0))),
      h("leaf",["int","int"],"int",op("sub",v(1),v(0))),
    ]
    ctx.accepted_profile=copy.deepcopy(ctx.accepted_profile)
    ctx.accepted_profile["enums"]={"Mood":{"constructors":["clear","cloudy"],"lean_decl":"ReadableFixture.Mood",
        "lean_constructors":["ReadableFixture.Mood.clear","ReadableFixture.Mood.cloudy"]}}
    ctx.inputs["source"]=("vscore-source",S.source_bytes(prog))
    return ctx


def capture(label,ctx,spec,build):
    root=Path(__file__).resolve().parents[1]/"validation/tier2-readable-view-qualification"
    path=Path(tempfile.mkdtemp(prefix=label+"-",dir=root))
    files={"source.json":ctx.inputs["source"][1],"relation.json":canonical.dumps(ctx.relation),
           "profile.json":canonical.dumps(ctx.accepted_profile),"goal.lean":spec.text.encode(),
           "observation.json":canonical.dumps(build.observation),"compile-process.json":canonical.dumps(build.process_evidence),
           "full-kernel-export.json":canonical.dumps(build.decls),
           **build.readable_artifacts}
    for module,parts in build.modules.items():
        for suffix,data in parts.items():files[f"modules/{module}{suffix}"]=data
    for name,data in files.items():
        dest=path/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    (path/"manifest.json").write_bytes(canonical.dumps({"format":"verislop.fresh-readable-capture/1",
        "artifacts":{p:{"sha256":canonical.digest(d),"size":len(d)} for p,d in sorted(files.items())}}))
    for p in path.rglob("*"):
        if p.is_file():p.chmod(0o444)
    for p in sorted((p for p in path.rglob("*") if p.is_dir()),reverse=True):p.chmod(0o555)
    path.chmod(0o555)
    return path


class ReadableUnitTests(unittest.TestCase):
    def test_render_is_deterministic_and_source_only(self):
        src,rel,p,obs=fixture(); a=R.render(src,{})
        self.assertEqual(a.block,R.render(src,{}).block)
        p2=copy.deepcopy(p); p2["symbols"]["difference"]["lean_decl"]="Alternate.reference"
        obs2=copy.deepcopy(obs);obs2["RD1"]["lean_symbol"]="Alternate.guarantee"
        obs2["RD1"]["formula"]["body"]["body"]["right"]={"tag":"int","value":"0"}
        base=T.build_goal(src,rel,p,obs); enriched=T.enrich_readable(base)
        alternate=T.enrich_readable(T.build_goal(src,rel,p2,obs2))
        self.assertNotEqual(alternate.base_text,enriched.base_text)
        self.assertEqual(alternate.readable_view.block,enriched.readable_view.block)
        self.assertEqual(alternate.readable_view.typed_ir,enriched.readable_view.typed_ir)
        self.assertTrue(enriched.text.startswith(base.text+"\n"))
        self.assertEqual(base.expected["EdgeProp"],enriched.expected["EdgeProp"])
        self.assertIn("VSCore3.ReadableRunEquals",enriched.text)
        self.assertEqual(len(a.functions),1)

    def test_excluded_variant_type_is_explicit(self):
        src,_,_,_=fixture(); prog=S.parse_source(src)
        prog["declarations"]=[{"tag":"variant","id":"FreshV","constructors":[("a",[])]}]
        with self.assertRaisesRegex(R.Unavailable,"variant"):
            R.render(S.source_bytes(prog),{})

    def test_all39_matrix_is_source_typed_and_incrementally_bounded(self):
        ctx=matrix_context(b"");view=R.render(ctx.inputs["source"][1],{"Mood":["clear","cloudy"]})
        self.assertEqual(set(view.constructors),set(R.CONSTRUCTORS))
        helpers=[r for r in view.functions if r["role"]=="helper"]
        self.assertEqual(helpers[0]["source_id"],"capturedFilter")
        self.assertGreater(next(r["compiled_index"] for r in helpers if r["source_id"]=="early"),0)
        src,_,_,_=fixture();prog=S.parse_source(src)
        prog["declarations"]=[{"tag":"record","id":"R0","fields":[("a","int"),("b","int")]}]
        for i in range(1,21):
            prog["declarations"].append({"tag":"record","id":f"R{i}","fields":[("a",("record",f"R{i-1}")),("b",("record",f"R{i-1}"))]})
        with self.assertRaisesRegex(R.Unavailable,"byte budget"):
            R.render(S.source_bytes(prog),{})

    def test_agent_freezes_checked_and_base_metadata_through_repairs_and_exhaustion(self):
        for mode in ("BASE","CHECKED"):
          for success in (True,False):
            with self.subTest(mode=mode,success=success),tempfile.TemporaryDirectory(prefix="fresh-readable-transport-") as dirname:
                ctx=context(b"");src,rel,p,obs=fixture();spec=T.build_goal(src,rel,p,obs)
                base=C.Build({"toolchain_olean_closure":"sha256:"+"7"*64},{},{},"sha256:"+"4"*64,{},[])
                path="support/readable/diagnostics/0.json";diag=canonical.dumps({"format":"fresh diagnostic","errors":["generic unavailable"]})
                a=RS.ref(path,diag)
                reasons=[{"code":"UNSUPPORTED_CONSTRUCTOR","stage":"coverage","source_path":None,
                    "message":"fresh unavailable", "reported_error_count":1,"diagnostic_artifact":a,"diagnostic_complete":True}]
                record=RS.selection_record(ctx,spec,base,reasons=reasons,
                    diagnostics=[{"slot_id":"vscore-readable-diagnostic-0","role":"readable_diagnostic","artifact":a}])
                meta={path:diag}
                if mode=="CHECKED":
                    record.update(selected_mode="CHECKED",status="CHECKED",reasons=[],diagnostic_inputs=[],
                        checked_descriptor={k:"sha256:"+"5"*64 for k in ["source_block_hash","typed_ir_hash","correspondence_hash",
                        "selected_goal_hash","compiled_inventory_hash","support_declarations_hash","equalities_hash",
                        "dependency_inventory_hash","axiom_inventory_hash","goal_module_parts_hash"]})
                    meta={}
                selection=canonical.dumps(record);self.assertEqual([],schemas.validate("vscore-readable-selection",record))
                meta[R.SELECTION_PATH]=selection
                info={"proposition_hash":base.proposition_hash,"model":b"{}","profile":b"{}",
                      "readable_selection":selection,"readable_candidate_artifacts":meta,
                      "readable_artifacts":meta,"readable_source_view":{"mode":mode,"selection_hash":canonical.digest(selection)}}
                params={"tier":2,"target":"vscore","endpoint":"restricted_source","backend":"verislop.backend.vscore/0.3",
                    "backend_version":"0.3","require_state":"END_TO_END_VERIFIED","require_tests":False}
                fixed={"parameters":params,"accepted_reference":{},"accepted_packages":{},"accepted_profile":{},"lean_toolchain":leanbridge.DEFAULT_TOOLCHAIN}
                pkg=Package(Path(dirname)/"package");pkg.ensure("fresh-readable-transport");events=EventSink(pkg.run_id,quiet=True)
                responses=iter([json.dumps({"program":canonical.loads(src),"relation":rel,"proof_source":"initial rejected proof"}),"replacement proof"])
                calls=[]
                def preview(_pkg,got_src,got_rel,proof=None,**kw):
                    calls.append((proof,kw));self.assertEqual((got_src,got_rel),(src,canonical.dumps(rel)))
                    if proof is None:
                        self.assertEqual(kw,{"select_readable":True,"readable_selection":None,"readable_diagnostics":{}})
                    else:
                        self.assertEqual(kw,{"select_readable":False,"readable_selection":selection,
                            "readable_diagnostics":{k:v for k,v in meta.items() if k!=R.SELECTION_PATH}})
                        if proof==b"initial rejected proof" or not success:
                            raise C.EdgeFailure([Diagnostic("CANDIDATE_BUILD_FAILURE","fresh rejected proof")])
                    return spec,None,info
                try:
                    with patch.object(agents,"_vscore_context",return_value=fixed),patch.object(agents,"_role",return_value="implementer"),\
                         patch.object(agents,"recorded_call",side_effect=lambda *args:SimpleNamespace(text=next(responses))),\
                         patch.object(C,"preview",side_effect=preview):
                        files,_=agents._vscore_implementation(None,{"roles":{"prover":"prover"}},pkg,events,{"parameters":params},1,1)
                    self.assertEqual({k:files[k] for k in meta},meta)
                    self.assertEqual(len(calls),3)
                    for k,v in meta.items():self.assertEqual((pkg.root/"agents/vscore-attempts/source-1"/k).read_bytes(),v)
                finally:events.close()

    def test_real_prepare_loader_preserves_exact_metadata_and_rejects_extra_roles(self):
        # The accepted service reconstruction is isolated here; all candidate,
        # preparation, schema, snapshot and selected-metadata boundaries are real.
        from test_vscore3_readable_integration import ProductionReadableMetadata
        factory=ProductionReadableMetadata();factory.setUp()
        self.addCleanup(factory.doCleanups)
        src=S.compile_surface('program "vscore/0.3" profile "data-pipeline/0.3"; entry echo(x:Bool)->Bool{x}')
        rel=canonical.dumps({"schema_version":"0.3","format":T.RELATION_FORMAT,"template":T.TEMPLATE,
            "source_slot":"vscore-source","proof_slot":"vscore-proof","bindings":[{"symbol":"echo","entry":"echo"}]})
        cert_path="accepted/certificate.json";ir_path="accepted/accepted-ir.json"
        rec={"id":"GF","revision":1,"required":True,"role":"guarantee","kind":"behavior","formal":{
            "representation":"contract_dsl","statement_hash":canonical.digest(b"generic accepted statement"),
            "formula_ref":"expr@"+canonical.digest(b"generic expression")}}
        imported_files={f"contract/{role}":b"generic "+role.encode() for role in ("source","profile","olean","environment_export","statements")}
        imported_files["contract/profile"]=canonical.dumps({"profile_id":"generic-profile","symbols":{},"enums":{},"records":{}})
        cert={"artifacts":{role:{"path":f"contract/{role}","sha256":canonical.digest(data)}
            for role,data in ((r,imported_files[f"contract/{r}"]) for r in ("source","profile","olean","environment_export","statements"))},
            "policy":{"id":policy.get("strict")["id"],"hash":policy.policy_hash(policy.get("strict"))},
            "gate":"accepted_and_proved","toolchain":{"pin":"generic-test"}}
        ir={"acceptance_certificate_ref":cert_path,"obligations":{"GF":rec}}
        imported_files.update({cert_path:canonical.dumps(cert),ir_path:canonical.dumps(ir)})
        imported=SimpleNamespace(ir_path=ir_path,certificate_path=cert_path,files=imported_files,certificate=cert,ir=ir,replay_receipt={})
        for extra in (None,"readable_diagnostic","readable_selection"):
          for owner in (C.NODE,"foreign-node") if extra else (C.NODE,):
            with self.subTest(extra=extra,owner=owner),tempfile.TemporaryDirectory(prefix="fresh-readable-prepared-") as dirname:
                metadata={R.SELECTION_PATH:factory.selection,**factory.ctx.readable_diagnostics}
                info={"proposition_hash":canonical.digest(b"generic proposition"),"obligations":["GF"],
                    "model":b"generic model","profile":b"generic profile","readable_selection":factory.selection,
                    "readable_candidate_artifacts":metadata}
                candidate=C.candidate_files("generic-readable",info,src,rel,b"generic proof")
                proposal=canonical.loads(candidate["proposal.json"])
                if extra:
                    path="support/readable/unused.json";candidate[path]=b"undeclared metadata"
                    proposal["artifacts"].append({"slot_id":"extra-readable","role":extra,"node_id":owner,"path":path})
                    proposal["reproducible_slots"].append("extra-readable");proposal["reproducible_slots"].sort()
                    if owner!=C.NODE:
                        proposal["nodes"].append({**copy.deepcopy(proposal["nodes"][-1]),"node_id":owner})
                C._schema("bridge-proposal",proposal)
                files,plan,manifest=prepare._assemble(imported,proposal,canonical.dumps(proposal),candidate)
                C._schema("bridge-plan",plan);C._schema("bridge-artifacts",manifest)
                root=Path(dirname)
                for path,data in files.items():fsutil.atomic_write(root/path,data)
                with patch.object(C,"_obligation_from_package",return_value={"generic":"isolated accepted service"}):
                    if extra:
                        with self.assertRaises(C.EdgeFailure) as rejected:C.load_context(root,"generic-readable","reference-to-vscore")
                        self.assertEqual(rejected.exception.diagnostics[0].code,"INVALID_CANDIDATE")

                    else:
                        loaded=C.load_context(root,"generic-readable","reference-to-vscore")
                        self.assertEqual(loaded.readable_selection,factory.selection)
                        self.assertEqual(loaded.readable_diagnostics,factory.ctx.readable_diagnostics)
                        size_changed=copy.deepcopy(manifest)
                        next(r for r in size_changed["artifacts"] if r["slot_id"]==R.SELECTION_SLOT)["size"]+=1
                        fsutil.write_json(root/"artifacts.json",size_changed)
                        with self.assertRaises(C.EdgeFailure) as rejected:C.load_context(root,"generic-readable","reference-to-vscore")
                        self.assertEqual(rejected.exception.diagnostics[0].code,"INPUT_MUTATION")
                        legacy=C.candidate_files("generic-readable",{**info,"readable_selection":None,"readable_candidate_artifacts":{}},src,rel,b"generic proof")
                        legacy_proposal=canonical.loads(legacy["proposal.json"])
                        legacy_files,legacy_plan,legacy_manifest=prepare._assemble(imported,legacy_proposal,legacy["proposal.json"],legacy)
                        legacy_plan["artifact_slots"].append({**copy.deepcopy(legacy_plan["artifact_slots"][-1]),
                            "slot_id":"undeclared-readable","role":"readable_diagnostic"})
                        legacy_manifest["plan_hash"]=canonical.digest_json(legacy_plan)
                        legacy_files.update({"plan.json":canonical.dumps(legacy_plan),"artifacts.json":canonical.dumps(legacy_manifest)})
                        for path,data in legacy_files.items():fsutil.atomic_write(root/path,data)
                        with self.assertRaises(C.EdgeFailure) as rejected:C.load_context(root,"generic-readable","reference-to-vscore")
                        self.assertEqual(rejected.exception.diagnostics[0].code,"INVALID_CANDIDATE")

    def test_frozen_checked_failure_and_same_type_proof_change_never_downgrade(self):
        ctx=context(b"");spec=T.enrich_readable(T.build_goal(ctx.inputs["source"][1],ctx.relation,ctx.accepted_profile,ctx.obligations))
        base=C.Build({"toolchain_olean_closure":canonical.digest(b"fresh closure")},{},{},canonical.digest(b"fresh proposition"),{},[])
        record=RS.selection_record(ctx,spec,base)
        record.update(selected_mode="CHECKED",status="CHECKED",checked_descriptor={k:canonical.digest(k.encode()) for k in
            ["source_block_hash","typed_ir_hash","correspondence_hash","selected_goal_hash","compiled_inventory_hash",
             "support_declarations_hash","equalities_hash","dependency_inventory_hash","axiom_inventory_hash","goal_module_parts_hash"]})
        spec.readable_selection=ctx.readable_selection=canonical.dumps(record)
        rejected=C.EdgeFailure([Diagnostic("CANDIDATE_BUILD_FAILURE","fresh selected proof failed",details={"module":T.GOAL_MODULE})])
        with patch.object(C,"_run_build_once",side_effect=[base,rejected]) as builds:
            with self.assertRaises(C.EdgeFailure) as result:C.run_build(None,ctx,spec,with_proof=True)
            self.assertIs(result.exception,rejected);self.assertEqual(builds.call_count,2)
        changed=copy.deepcopy(spec)
        # Same theorem name and expected type; only its proposed proof expression
        # is substituted. Frozen replay must reject before compiling enrichment.
        changed.text=changed.text.replace("    rfl\n","    exact id rfl\n",1)
        self.assertEqual(changed.expected,spec.expected)
        with patch.object(C,"_run_build_once",return_value=base) as builds:
            with self.assertRaises(C.EdgeFailure) as result:C.run_build(None,ctx,changed,with_proof=True)
            self.assertEqual(result.exception.diagnostics[0].code,"INPUT_MUTATION")
            self.assertEqual(builds.call_count,1)


class ReadableKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=TempDir();cls.tc=leanbridge.resolve_toolchain()
        built=leanbridge.compile_module(cls.tc,CONTRACT,cls.tmp.path/"contract")
        if not built.ok: raise AssertionError(built.errors)
        cls.contract=Path(built.olean).read_bytes()

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_checked_scalar_selection(self):
        ctx=context(self.contract)
        spec=T.build_goal(ctx.inputs["source"][1],ctx.relation,ctx.accepted_profile,ctx.obligations)
        selected,build=C._select_readable(self.tc,ctx,spec)
        capture("scalar",ctx,selected,build)
        diagnostic=canonical.loads(build.readable_artifacts.get("support/readable/diagnostics/0.json",b"{}"))
        self.assertEqual(build.readable_support["mode"],"CHECKED",[d["message"] for d in diagnostic.get("diagnostics",[])])
        self.assertEqual([],schemas.validate("vscore-readable-selection",canonical.loads(selected.readable_selection)))
        refs=C.readable_artifact_refs(build.readable_support,build.readable_artifacts.__getitem__)
        self.assertEqual(set(refs),set(build.readable_artifacts))
        self.assertTrue(all(x.startswith(("BASE::","SELECTED::")) for x in build.process_evidence))

    def test_excluded_variant_and_match_variant_preserve_admitted_base(self):
        ctx=context(self.contract);program=S.parse_source(ctx.inputs["source"][1]);variant=("variant","FreshChoice")
        program["declarations"]=[{"tag":"variant","id":"FreshChoice","constructors":[("left",["int"]),("right",[])]}]
        program["helpers"]=[{"id":"choose","params":["int"],"result":variant,"body":("variant","FreshChoice","left",[("var",0)])},
            {"id":"readChoice","params":[variant],"result":"int","body":("match_variant",("var",0),[("left",("var",0)),("right",("int",0))])}]
        ctx.inputs["source"]=("vscore-source",S.source_bytes(program))
        base=T.build_goal(ctx.inputs["source"][1],ctx.relation,ctx.accepted_profile,ctx.obligations)
        selected,build=C._select_readable(self.tc,ctx,base)
        capture("excluded-variant-base",ctx,selected,build)
        self.assertEqual(build.readable_support["mode"],"BASE")
        self.assertEqual(selected.text,base.text)
        self.assertEqual(canonical.loads(selected.readable_selection)["reasons"][0]["code"],"UNSUPPORTED_TYPE")

    def test_all39_universal_selection_and_frozen_replay(self):
        ctx=matrix_context(self.contract)
        spec=T.build_goal(ctx.inputs["source"][1],ctx.relation,ctx.accepted_profile,ctx.obligations)
        selected,first=C._select_readable(self.tc,ctx,spec)
        capture("matrix-selection",ctx,selected,first)
        diagnostic=canonical.loads(first.readable_artifacts.get("support/readable/diagnostics/0.json",b"{}"))
        self.assertEqual(first.readable_support["mode"],"CHECKED",[d["message"] for d in diagnostic.get("diagnostics",[])])
        self.assertEqual(set(selected.readable_view.constructors),set(R.CONSTRUCTORS))
        type(self)._matrix=(ctx,selected,first)
        a=C.run_build(self.tc,ctx,selected,with_proof=True)
        capture("matrix-replay-A",ctx,selected,a)
        b=C.run_build(self.tc,ctx,selected,with_proof=True)
        capture("matrix-replay-B",ctx,selected,b)
        self.assertEqual(a.observation,b.observation)
        self.assertEqual(a.readable_artifacts,b.readable_artifacts)
        self.assertEqual(C.readable_artifact_refs(a.readable_support,a.readable_artifacts.__getitem__),
                         {p:canonical.digest(d) for p,d in a.readable_artifacts.items()})

    def test_checked_support_and_same_sort_lowering_negatives(self):
        cached=getattr(type(self),"_matrix",None)
        if cached is None:
            ctx=matrix_context(self.contract)
            base=T.build_goal(ctx.inputs["source"][1],ctx.relation,ctx.accepted_profile,ctx.obligations)
            selected,checked=C._select_readable(self.tc,ctx,base)
            self.assertEqual(checked.readable_support["mode"],"CHECKED")
            capture("matrix-negative-control",ctx,selected,checked)
            cached=ctx,selected,checked
        self._audit_negative_exports(*cached)
        self._lowering_negative(*cached)

    def _audit_negative_exports(self,ctx,spec,checked):
        # Boundary mutations of a real kernel export. These negatives test the
        # host audit, and do not claim the mutated records were kernel replayed.
        support_prefix=(R.NAMESPACE+".",T.GOAL_MODULE+".Readable.")
        base=copy.copy(checked);base.decls={n:c for n,c in checked.decls.items() if not n.startswith(support_prefix)}
        base.observation={**checked.observation,"readable_support":None}
        theorem=T.GOAL_MODULE+".Readable.runEquals_helper_0"
        replacement=copy.copy(checked);replacement.decls=copy.deepcopy(checked.decls)
        replacement.decls[theorem]["value_constants"].append(["Nat","add"])
        audited=RS.audit(ctx,spec,base,replacement)
        with self.assertRaises(C.EdgeFailure) as result:RS.attach(ctx,spec,base,replacement,spec.readable_selection,audited)
        self.assertEqual(result.exception.diagnostics[0].code,"INPUT_MUTATION")
        unused=copy.copy(checked);unused.decls=copy.deepcopy(checked.decls)
        record=copy.deepcopy(unused.decls[theorem]);record["name"]=[R.NAMESPACE,"unused_forbidden"]
        record["axioms"]=[["sorryAx"]];unused.decls[R.NAMESPACE+".unused_forbidden"]=record
        with self.assertRaises(C.EdgeFailure) as result:RS.audit(ctx,spec,base,unused)
        self.assertEqual(result.exception.diagnostics[0].code,"INADMISSIBLE_AXIOM")
        weakened=copy.deepcopy(checked.decls);weakened[theorem]["type"]={"const":["True"],"levels":[]}
        self.assertIn(theorem,T.statement_mismatches(spec,weakened))
        files=dict(checked.readable_artifacts);path="readable/base-kernel-export.json"
        baseline=canonical.loads(files[path]);next(iter(baseline.values())).pop("axioms")
        files[path]=canonical.dumps(baseline)
        manifest=canonical.loads(files[R.MANIFEST_PATH])
        next(row for row in manifest["artifacts"] if row["artifact"]["path"]==path)["artifact"]=RS.ref(path,files[path])
        files[R.MANIFEST_PATH]=canonical.dumps(manifest)
        descriptor={**checked.readable_support,"manifest":{"path":R.MANIFEST_PATH,"sha256":canonical.digest(files[R.MANIFEST_PATH])}}
        with self.assertRaises(C.EdgeFailure) as result:C.readable_artifact_refs(descriptor,files.__getitem__)
        self.assertEqual(result.exception.diagnostics[0].code,"INVALID_CANDIDATE")

    def _lowering_negative(self,ctx,spec,checked):
        original=R.Renderer._expr
        entry=S.parse_source(ctx.inputs["source"][1])["entries"][0]["body"]
        def swap(node):
            if isinstance(node,(tuple,list)):
                if node and node[0]=="var" and node[1] in (0,1):return ("var",1-node[1])
                return tuple(swap(x) for x in node) if isinstance(node,tuple) else [swap(x) for x in node]
            return node
        def malformed_lowering(renderer,node,stack,depth=0):
            if node==entry:node=swap(node)
            elif node[0] in ("list_fold","nat_fold"):node=(node[0],node[1],node[2],swap(node[3]))
            return original(renderer,node,stack,depth)
        base=T.build_goal(ctx.inputs["source"][1],ctx.relation,ctx.accepted_profile,ctx.obligations)
        with patch.object(R.Renderer,"_expr",malformed_lowering):mutant=T.enrich_readable(base)
        self.assertEqual(mutant.source_bytes,spec.source_bytes)
        self.assertEqual(mutant.expected,spec.expected)
        root=Path(tempfile.mkdtemp(prefix="lowering-negative-",dir=Path(__file__).resolve().parents[1]/"validation/tier2-readable-view-qualification"))
        deps={m:leanbridge.write_module_parts(root/"deps",m,parts) for m,parts in checked.modules.items()
              if m not in (T.GOAL_MODULE,T.PROOF_MODULE)}
        result,_=leanbridge.compile_named_module(self.tc,root/"compile",T.GOAL_MODULE,mutant.text.encode(),deps,
            read_only=[root/"deps"],timeout=ctx.policy["build_timeout_seconds"],memory_mb=ctx.policy["memory_mb"],
            require_network_isolation=ctx.policy["require_network_isolation"],require_filesystem_isolation=ctx.policy["require_filesystem_isolation"])
        files={"goal.lean":mutant.text.encode(),"source.json":spec.source_bytes,
            "diagnostics.json":canonical.dumps({"ok":result.ok,"errors":result.errors,"messages":result.messages,
                "process_evidence":result.process_evidence,"mutations":["same-sort parameters","list-fold item/accumulator","nat-fold index/accumulator"]}),
            "dependencies.json":canonical.dumps({m:{s:canonical.digest(d) for s,d in parts.items()} for m,parts in checked.modules.items()
                if m not in (T.GOAL_MODULE,T.PROOF_MODULE)})}
        for path,data in files.items():fsutil.atomic_write(root/path,data)
        fsutil.write_json(root/"manifest.json",{"format":"verislop.fresh-readable-lowering-negatives/1",
            "artifacts":{p:RS.ref(p,d) for p,d in files.items()}})
        for p in root.rglob("*"):
            if p.is_file():p.chmod(0o444)
        for p in sorted((p for p in root.rglob("*") if p.is_dir()),reverse=True):p.chmod(0o555)
        root.chmod(0o555)
        print("READABLE_LOWERING_NEGATIVE_CAPTURE",root,flush=True)
        self.assertFalse(result.ok)
        errors=[m for m in result.messages if m.get("severity")=="error"]
        self.assertTrue(errors);self.assertTrue(all("Tactic `rfl` failed" in m["data"] for m in errors),result.errors)
        lines=mutant.text.splitlines()
        failed=[]
        for message in errors:
            before="\n".join(lines[:message["pos"]["line"]])
            failed.append(before.rsplit("theorem ",1)[-1].split()[0])
        self.assertTrue({"runEquals_helper_3","runEquals_helper_4","runEquals_entry_0"}.issubset(failed),failed)


class ReadableRegisteredPipelineTests(unittest.TestCase):
    def test_selected_checked_publication_registered_closure_and_retained_review(self):
        from test_vscore3_source_pipeline import accepted_fixture,SURFACE,RELATION
        from verislop import generate,link,closure,review,review_counterexamples,review_projection,verifiers
        from verislop.backends import vscore3,vscore3_closure
        repository=Path(__file__).resolve().parents[1]
        capture_root=repository/"validation/tier2-readable-view-qualification"
        status="UNQUALIFIED";pkg=None
        with tempfile.TemporaryDirectory(prefix="fresh-readable-pipeline-") as dirname:
            root=Path(dirname);candidate=root/"candidate"
            try:
                pkg=accepted_fixture(root)
                source=S.compile_surface(SURFACE);relation=canonical.dumps(RELATION)
                selected,build,info=C.preview(pkg,source,relation,select_readable=True)
                self.assertEqual(build.readable_support["mode"],"CHECKED")
                metadata=info["readable_candidate_artifacts"]
                proof=b'''import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  \u00b7 intro x
    change VeriSlopBridgeGoal.source_fn_shift x = _
    rw [VeriSlopBridgeGoal.Readable.source_eq_shift]
    with_unfolding_all rfl
  \u00b7 intro x
    change VeriSlopBridgeGoal.source_fn_solve x = _
    rw [VeriSlopBridgeGoal.Readable.source_eq_solve]
    with_unfolding_all rfl
end VeriSlopBridgeProof
'''.replace(b'\\u00b7',"·".encode())
                for path,data in {"program.vscore.json":source,"relation.json":relation,"Proof.lean":proof,**metadata}.items():
                    fsutil.atomic_write(candidate/path,data)
                events=EventSink(pkg.run_id,pkg.root,quiet=True)
                try:
                    for operation,options in ((generate.run,{"tier":2,"target":"vscore","backend_version":"0.3","candidate":candidate}),
                                              (link.run,{}),(C.accept,{"bridge_id":"implementation"}),
                                              (closure.run,{"endpoint":"restricted_source","require_state":"END_TO_END_VERIFIED"})):
                        result=operation(pkg,events=events,**options)
                        self.assertEqual(result.status,"PASS",[d.to_json() for d in result.diagnostics])
                    accepted,pending,diagnostics=C.verify_published(pkg,"implementation",rebuild=False)
                    self.assertTrue(accepted);self.assertFalse(pending);self.assertFalse(diagnostics)
                    selected_context=C.load_context(pkg.root/"bridges/implementation","implementation",vscore3.selection(pkg)["edge_id"])
                    self.assertEqual(selected_context.readable_selection,info["readable_selection"])
                    self.assertEqual(C.readable_candidate_metadata(selected_context.readable_selection,
                        selected_context.readable_diagnostics.__getitem__),metadata)
                    support_root=pkg.root/"bridges/implementation"/C.SEMANTIC_DIR/C.edge_key(selected_context.edge["edge_id"])
                    manifest=canonical.load_file(support_root/R.MANIFEST_PATH)
                    self.assertTrue(manifest["checked_proof_support_dependencies"])
                    snapshot=vscore3_closure.mechanical_snapshot(pkg)
                    self.assertEqual(snapshot["mechanical_status"],"VERIFIED")
                    self.assertEqual(snapshot["builds"][0]["outputs"],snapshot["builds"][1]["outputs"])
                    for output in (snapshot["builds"][0]["outputs"],snapshot["builds"][1]["outputs"]):
                        self.assertEqual(output["readable_support"]["descriptor"]["mode"],"CHECKED")
                    projection=review_projection.build(pkg,snapshot)
                    self.assertIsNotNone(projection)
                    packet=review.build_packet(pkg,"release")
                    claim=vscore3.selection(pkg)["edge_claim_id"]
                    receipt=review_counterexamples.replay(pkg,"release",{"kind":"mechanical_failure","claim_id":claim})
                    self.assertEqual([],schemas.validate("review-counterexample-receipt",receipt))
                    self.assertEqual(receipt["status"],"NOT_REPRODUCED")
                    fsutil.write_json(root/"retained-review-packet.json",packet)
                    fsutil.write_json(root/"retained-projection.json",projection)
                    fsutil.write_json(root/"mechanical-probe.json",receipt)
                    report=canonical.load_file(pkg.path("report"))
                    self.assertEqual(report["mechanical_status"],"VERIFIED")
                    status="VERIFIED"
                finally:events.close()
            finally:
                # Retain the complete unrelated fixture even on a failed gate.
                destination=Path(tempfile.mkdtemp(prefix="selected-pipeline-",dir=capture_root))
                for path in root.iterdir():
                    if path.is_dir():shutil.copytree(path,destination/path.name)
                    else:shutil.copy2(path,destination/path.name)
                sources=sorted({"verislop/"+rel for spec in verifiers.VERIFIERS.values() for rel in verifiers.CORE+spec["sources"]}
                    |{"schemas/"+name for spec in verifiers.VERIFIERS.values() for name in spec["schemas"]}
                    |{"tests/test_vscore3_readable.py","tests/test_vscore3_source_pipeline.py"})
                source_hashes={}
                for rel in sources:
                    data=(repository/rel).read_bytes();fsutil.atomic_write(destination/"registered-sources"/rel,data)
                    source_hashes[rel]=canonical.digest(data)
                fsutil.write_json(destination/"capture.json",{"format":"verislop.fresh-readable-pipeline-capture/1",
                    "mechanical_status":status,"captured_before_test_temp_cleanup":True,"source_hashes":source_hashes,
                    "source_root":canonical.digest_json(source_hashes),"files":{str(p.relative_to(destination)):canonical.digest_file(p)
                    for p in sorted(destination.rglob("*")) if p.is_file()}})
                for p in destination.rglob("*"):
                    if p.is_file():p.chmod(0o444)
                for p in sorted((p for p in destination.rglob("*") if p.is_dir()),reverse=True):p.chmod(0o555)
                destination.chmod(0o555)
                print("READABLE_SOURCE_PIPELINE_CAPTURE",destination,flush=True)
        # The original temporary root is gone. All authoritative package refs
        # must still resolve in the retained copy; telemetry paths are advisory.
        retained=Package(destination/"package")
        accepted,pending,diagnostics=C.verify_published(retained,"implementation",rebuild=False)
        self.assertTrue(accepted);self.assertFalse(pending);self.assertFalse(diagnostics)
        retained_snapshot=vscore3_closure.mechanical_snapshot(retained)
        self.assertEqual(retained_snapshot["mechanical_status"],"VERIFIED")
        annex=Path(tempfile.mkdtemp(prefix="pipeline-portability-",dir=capture_root))
        fsutil.write_json(annex/"receipt.json",{"format":"verislop.fresh-readable-portability/1",
            "capture":str(destination.relative_to(repository)),"capture_hash":canonical.digest_file(destination/"capture.json"),
            "original_temporary_root_removed":not root.exists(),"published_check":"PASS",
            "mechanical_status":retained_snapshot["mechanical_status"],"closure_root":retained_snapshot["closure_root"],
            "absolute_compile_process_paths":"retained advisory facts; excluded from deterministic identity"})
        (annex/"receipt.json").chmod(0o444);annex.chmod(0o555)
        print("READABLE_PIPELINE_PORTABILITY_CAPTURE",annex,flush=True)


if __name__=="__main__":unittest.main()
