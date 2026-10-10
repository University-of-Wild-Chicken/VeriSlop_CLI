import base64,dataclasses,json,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from verislop import canonical,leanbridge,cli
P=Path('validation/isolated-collection-bridge-20261010-gcb')
label=sys.argv[1];args=sys.argv[2:];D=P/'diagnostics'/label;D.mkdir(parents=True,exist_ok=True)
counters={}
def observer(name):
 original=getattr(leanbridge,name)
 def call(*a,**kw):
  i=counters.get(name,0);counters[name]=i+1;stem=D/f'{name}-{i:03}'
  meta={'actual_function':'verislop.leanbridge.'+name,'keyword_arguments':{k:str(v) if isinstance(v,Path) else v for k,v in kw.items()},'observational_wrapper_only':True}
  if name.startswith('compile'):
   meta['module']='VeriSlopContract' if name=='compile_module' else a[2]
   src=a[1] if name=='compile_module' else a[3]
   stem.with_suffix('.lean').write_bytes(src)
   meta['source_hash']=canonical.digest(src)
  try:
   result=original(*a,**kw)
   if dataclasses.is_dataclass(result):
    obj=dataclasses.asdict(result);obj['olean']=str(obj['olean']) if obj.get('olean') else None
   else:obj=result
   stem.with_suffix('.json').write_text(json.dumps({'invocation':meta,'actual_result':obj},default=lambda x: dataclasses.asdict(x) if dataclasses.is_dataclass(x) else {'base64':base64.b64encode(x).decode()} if isinstance(x,bytes) else str(x),sort_keys=True))
   return result
  except BaseException as e:
   stem.with_suffix('.json').write_text(json.dumps({'invocation':meta,'exception_type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()},default=str,sort_keys=True))
   raise
 setattr(leanbridge,name,call)
for n in ('compile_module','compile_named_module','run_kernel_tool','run_kernel_tool_modules'):observer(n)
with (P/'commands.jsonl').open('a') as f:f.write(json.dumps({'label':label,'argv':['python',str(P/'invoke_cli.py'),label,*args],'cwd':str(Path.cwd()),'utc_start':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})+'\n')
raise SystemExit(cli.main(args))
