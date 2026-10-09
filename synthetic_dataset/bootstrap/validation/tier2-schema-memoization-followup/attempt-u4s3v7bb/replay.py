import importlib.util,json,sys
from pathlib import Path
p=Path(__file__).resolve().parent
modules={}
for name in ('original','inline'):
    spec=importlib.util.spec_from_file_location('schema_followup_'+name,p/(name+'-validator.py'))
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);modules[name]=module
def path_get(x,path):
    for key in path:x=x[key]
    return x
rows=[]
for schemafile,casefile in (('recursive-array-schema.json','array-depth-240.json'),('recursive-array-schema.json','array-depth-250.json'),('vscore-v3-schema.json','type-depth-100.json'),('vscore-v3-schema.json','type-depth-125.json')):
    schema=json.loads((p/schemafile).read_bytes());value=json.loads((p/casefile).read_bytes());result={}
    for name,module in modules.items():
        reg=module.Registry();reg.add(schema)
        result[name]=[{'path':i.path,'message':i.message} for i in reg.validate(value,schema['$id'])]
        if hasattr(reg,'_validation_cache'):assert reg._validation_cache.get() is None
    assert result['original']==result['inline']==[]
    rows.append({'kind':'retained-depth-witness','schema':schemafile,'input':casefile,'outcomes':result})
for case in json.loads((p/'diagnostic-cases.json').read_bytes()):
    schema=case['schema']
    for target,source in case.get('aliases',[]):path_get(schema,target[:-1])[target[-1]]=path_get(schema,source)
    result={}
    for name,module in modules.items():
        reg=module.Registry();reg.add(schema)
        for extra in case.get('extra',[]):reg.add(extra)
        try:result[name]={'issues':[{'path':i.path,'message':i.message} for i in reg.validate(case['value'],schema['$id'])]}
        except module.SchemaError as exc:result[name]={'SchemaError':str(exc)}
        if hasattr(reg,'_validation_cache'):assert reg._validation_cache.get() is None
    assert result['original']==result['inline']
    rows.append({'kind':'diagnostic-equivalence','case':case['id'],'outcomes':result})
print(json.dumps({'python':sys.version,'recursion_limit':sys.getrecursionlimit(),'status':'PASS','cache_reset_after_all_calls':True,'observations':rows},sort_keys=True))
