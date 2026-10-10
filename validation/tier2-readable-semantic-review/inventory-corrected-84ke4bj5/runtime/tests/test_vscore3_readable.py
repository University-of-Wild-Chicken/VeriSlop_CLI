"""Fresh generic readable fixtures: no retained task sources or expected answers."""
from __future__ import annotations

import copy
import tempfile
import json
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from pathlib import Path

from helpers import TempDir
from verislop import canonical, leanbridge, policy, schemas
from verislop import agents
from verislop.errors import Diagnostic
from verislop.events import EventSink
from verislop.package import Package
from verislop.bridges import vscore3_checker as C, vscore3_readable_support as RS
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
        self.assertEqual(R.render(src,{}).typed_ir,a.typed_ir)
        base=T.build_goal(src,rel,p,obs); enriched=T.enrich_readable(base)
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

    def test_all39_universal_selection_and_frozen_replay(self):
        ctx=matrix_context(self.contract)
        spec=T.build_goal(ctx.inputs["source"][1],ctx.relation,ctx.accepted_profile,ctx.obligations)
        selected,first=C._select_readable(self.tc,ctx,spec)
        capture("matrix-selection",ctx,selected,first)
        diagnostic=canonical.loads(first.readable_artifacts.get("support/readable/diagnostics/0.json",b"{}"))
        self.assertEqual(first.readable_support["mode"],"CHECKED",[d["message"] for d in diagnostic.get("diagnostics",[])])
        self.assertEqual(set(selected.readable_view.constructors),set(R.CONSTRUCTORS))
        a=C.run_build(self.tc,ctx,selected,with_proof=True)
        capture("matrix-replay-A",ctx,selected,a)
        b=C.run_build(self.tc,ctx,selected,with_proof=True)
        capture("matrix-replay-B",ctx,selected,b)
        self.assertEqual(a.observation,b.observation)
        self.assertEqual(a.readable_artifacts,b.readable_artifacts)
        self.assertEqual(C.readable_artifact_refs(a.readable_support,a.readable_artifacts.__getitem__),
                         {p:canonical.digest(d) for p,d in a.readable_artifacts.items()})


if __name__=="__main__":unittest.main()
