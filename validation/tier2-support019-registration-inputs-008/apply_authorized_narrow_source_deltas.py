"""Apply only source deltas registered before edits; run no copied helper."""
import ast, hashlib, json, os
from pathlib import Path
ROOT=Path(__file__).absolute().parents[2]
REG='validation/tier2-support019-registration-inputs-008'
def ref(p):
 b=(ROOT/p).read_bytes();return {'path':p,'sha256':'sha256:'+hashlib.sha256(b).hexdigest(),'byte_count':len(b)}
def write_json(p,v):
 q=ROOT/p;q.parent.mkdir(parents=True,exist_ok=True)
 with q.open('x') as f:json.dump(v,f,sort_keys=True,indent=2);f.write('\n')
def diff(a,b,path=''):
 if type(a)!=type(b):return [{'path':path,'before':a,'after':b}]
 if type(a) is dict:
  assert set(a)==set(b);return [x for k in a for x in diff(a[k],b[k],path+'/'+k)]
 if type(a) is list:
  assert len(a)==len(b);return [x for i,(u,v) in enumerate(zip(a,b)) for x in diff(u,v,path+'/'+str(i))]
 return [] if a==b else [{'path':path,'before':a,'after':b}]
def ast_value(s):
 def cv(n):
  if isinstance(n,ast.AST):return {'_type':type(n).__name__,**{k:cv(v) for k,v in ast.iter_fields(n)}}
  if isinstance(n,list):return [cv(x) for x in n]
  return n
 return cv(ast.parse(s))
def main():
 spec_path=REG+'/NARROW_SOURCE_DELTA_EXECUTION_SPECIFICATION_BEFORE_EDITS.json';spec=json.loads((ROOT/spec_path).read_bytes());records=[]
 for ix,op in enumerate(spec['operations']):
  assert ref(op['source']['path'])==op['source'];source=(ROOT/op['source']['path']).read_bytes();text=source.decode('utf-8');before=text
  rawpath=REG+'/source-preimages/narrow-'+str(ix)+'-'+Path(op['source']['path']).name+'.raw';p=ROOT/rawpath;p.parent.mkdir(parents=True,exist_ok=True)
  with p.open('xb') as f:f.write(source)
  for patch in op['patches']:
   assert text.count(patch['exact_old'])==1,patch;text=text.replace(patch['exact_old'],patch['exact_new'],1)
  changes=diff(ast_value(before),ast_value(text));assert changes and all('/value' in x['path'] and type(x['before']) is str and type(x['after']) is str for x in changes)
  target=ROOT/op['target'];assert op['mode']=='replace_owned_unsealed' or not target.exists()
  if op['mode']=='replace_owned_unsealed':assert target.read_bytes()==source
  with target.open('wb' if op['mode']=='replace_owned_unsealed' else 'xb') as f:f.write(text.encode('utf-8'))
  records.append({'source_before':op['source'],'retained_raw_preimage':ref(rawpath),'target_after':ref(op['target']),'exact_literal_patches':op['patches'],'whole_AST_differences':changes,'only_registered_string_literal_delta':True})
 op=spec['adaptation'];assert ref(op['source']['path'])==op['source'];before=(ROOT/op['source']['path']).read_bytes();value=json.loads(before);original=json.loads(before)
 rawpath=REG+'/source-preimages/narrow-predicate-reader-adaptation-specification.json.raw'
 with (ROOT/rawpath).open('xb') as f:f.write(before)
 for path,(a,b) in op['changes'].items():
  keys=path.strip('/').split('/');obj=value
  for k in keys[:-1]:obj=obj[k]
  assert obj[keys[-1]]==a;obj[keys[-1]]=b
 changes=diff(original,value);assert {x['path'] for x in changes}==set(op['changes'])
 (ROOT/op['target']).write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
 report={'format':'verislop.support022-narrow-source-delta-fidelity/1','status':'AUTHORIZED_NARROW_DELTA_ONLY_UNRESOLVED_UNSEALED','actual_process_pid':os.getpid(),'specification':ref(spec_path),'source_operations':records,'adaptation_operation':{'source_before':op['source'],'retained_raw_preimage':ref(rawpath),'target_after':ref(op['target']),'recursive_field_differences':changes,'all_other_values_exact':True},'pending_state':spec['pending_state'],'current_qualification_authority':False,'tests_runtime_profile_fixture_model_preflight_materializer_compiler_native_task_executed':0}
 reportpath=REG+'/NARROW_SOURCE_DELTA_FIDELITY.json';write_json(reportpath,report);write_json(REG+'/CURRENT_BINDINGS_UNRESOLVED.json',{'format':'verislop.support022-current-bindings-pending/1','fidelity':ref(reportpath),**spec['pending_state']})
 print(json.dumps({'actual_process_pid':os.getpid(),'fidelity':ref(reportpath),'pending_bindings':ref(REG+'/CURRENT_BINDINGS_UNRESOLVED.json'),'source_operations':len(records),'qualification_authority':False},sort_keys=True))
if __name__=='__main__':main()
