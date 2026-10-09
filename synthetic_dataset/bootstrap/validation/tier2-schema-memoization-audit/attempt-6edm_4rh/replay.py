import hashlib,importlib.util,json,sys
from pathlib import Path
p=Path(__file__).resolve().parent
modules={}
for name in ('original','corrected'):
    spec=importlib.util.spec_from_file_location('schema_audit_'+name,p/(name+'-validator.py'))
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);modules[name]=module
rows=[]
for schemafile,casefile in (('recursive-array-schema.json','array-depth-240.json'),('recursive-array-schema.json','array-depth-250.json'),('vscore-v3-schema.json','type-depth-100.json'),('vscore-v3-schema.json','type-depth-125.json')):
    schema=json.loads((p/schemafile).read_bytes()); value=json.loads((p/casefile).read_bytes());result={}
    for name,module in modules.items():
        reg=module.Registry();reg.add(schema)
        try:result[name]={'issues':[{'path':i.path,'message':i.message} for i in reg.validate(value,schema['$id'])]}
        except Exception as exc:result[name]={'exception':type(exc).__name__,'message':str(exc)}
        if hasattr(reg,'_validation_cache'):result[name]['cache_reset_after_call']=reg._validation_cache.get() is None
    rows.append({'schema':schemafile,'input':casefile,**result})
print(json.dumps({'python':sys.version,'recursion_limit':sys.getrecursionlimit(),'cases':rows},sort_keys=True))
