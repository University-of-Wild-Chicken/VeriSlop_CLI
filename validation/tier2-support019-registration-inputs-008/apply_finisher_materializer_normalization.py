"""Apply root-authorized finisher source delta only; never execute the finisher."""
import ast, hashlib, json, os
from pathlib import Path
ROOT=Path(__file__).absolute().parents[2]
REG='validation/tier2-support019-registration-inputs-008'
def ref(p):
 b=(ROOT/p).read_bytes();return {'path':p,'sha256':'sha256:'+hashlib.sha256(b).hexdigest(),'byte_count':len(b)}
def write_json(p,v):
 with (ROOT/p).open('x') as f:json.dump(v,f,sort_keys=True,indent=2);f.write('\n')
def main():
 amendment=REG+'/FINISHER_MATERIALIZER_NORMALIZATION_AMENDMENT_BEFORE_SOURCE.json';s=json.loads((ROOT/amendment).read_bytes());target=s['finisher_preimage']['path'];assert ref(target)==s['finisher_preimage']
 before=(ROOT/target).read_bytes();text=before.decode('utf-8');delta=s['allowed_delta'];old=delta['existing_main_assert_exact_old'];new=delta['existing_main_assert_exact_new'];helper=delta['new_helper_exact_source']
 assert text.count('import hashlib\n')==text.count('def main():\n')==text.count(old)==1
 raw=REG+'/source-preimages/finisher-before-materializer-normalization.py.raw'
 with (ROOT/raw).open('xb') as f:f.write(before)
 after=text.replace('import hashlib\n','import ast\nimport hashlib\n',1).replace('def main():\n',helper+'\ndef main():\n',1).replace(old,new,1)
 reverse=after.replace('import ast\nimport hashlib\n','import hashlib\n',1).replace(helper+'\ndef main():\n','def main():\n',1).replace(new,old,1);assert reverse.encode('utf-8')==before
 original=ast.parse(text);projected=ast.parse(after);imports=[n for n in projected.body if isinstance(n,ast.Import) and len(n.names)==1 and n.names[0].name=='ast' and n.names[0].asname is None];functions=[n for n in projected.body if isinstance(n,ast.FunctionDef) and n.name=='materializer_adapter_revision_fidelity'];assert len(imports)==len(functions)==1
 projected.body.remove(imports[0]);projected.body.remove(functions[0]);mainnode=next(n for n in projected.body if isinstance(n,ast.FunctionDef) and n.name=='main');wanted=ast.dump(ast.parse(new).body[0],include_attributes=False);positions=[i for i,n in enumerate(mainnode.body) if ast.dump(n,include_attributes=False)==wanted];assert len(positions)==1;mainnode.body[positions[0]]=ast.parse(old).body[0]
 assert ast.dump(projected,include_attributes=False)==ast.dump(original,include_attributes=False)
 (ROOT/target).write_bytes(after.encode('utf-8'))
 report={'format':'verislop.support022-finisher-normalization-source-fidelity/1','status':'REGISTERED_SOURCE_DELTA_APPLIED_FINISHER_NOT_EXECUTED','actual_source_editor_pid':os.getpid(),'amendment':ref(amendment),'source_before':s['finisher_preimage'],'retained_raw_preimage':ref(raw),'source_after':ref(target),'exact_registered_delta':delta,'whole_AST_projection_exact_after_removing_only_registered_import_helper_and_restoring_assertion':True,'inverse_literal_projection_byte_exact':True,'all_other_function_ASTs_exact':True,'finisher_or_materializer_executed':False,'current_qualification_authority':False,'preflight_profile_fixture_finalseal_model_VIEW_current27_native_task_kernel_executed':0,'pending_dependency':'Await root authenticated023 final and actual009 package before final current source preparation.'}
 p=REG+'/FINISHER_MATERIALIZER_NORMALIZATION_SOURCE_FIDELITY.json';write_json(p,report);print(json.dumps({'source_editor_pid':os.getpid(),'fidelity':ref(p),'source_after':report['source_after'],'finisher_executed':False},sort_keys=True))
if __name__=='__main__':main()
