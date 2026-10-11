"""Freeze exact finite test IDs/source/binary guards before source controls."""
from pathlib import Path
import ast
import hashlib
import json
import os

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(raw):
    return "sha256:"+hashlib.sha256(raw).hexdigest()
sources=[path for path in sorted(HERE.rglob("*")) if path.is_file()]
external=[ROOT/"validation/tier2-author-continuation-support-023-design/SPECIFICATION_BEFORE_IMPLEMENTATION.json",
          ROOT/"validation/tier2-support-019-qualification-plan-012/claims.json"]
external += [ROOT/"validation/tier2-support-019-qualification-adapters-008"/name for name in ("predicate_reader.py","additional_predicates.py","assemble_ancillary_indexes.py")]
external += [Path("/usr/bin/python3.12")]
guards={str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path):sha(path.read_bytes()) for path in sources+external}
ids=[]
for module in ("test_continuation","test_source_fidelity"):
    tree=ast.parse((HERE/(module+".py")).read_bytes())
    for parent in tree.body:
        if isinstance(parent,ast.ClassDef):
            ids += [module+"."+parent.name+"."+node.name for node in parent.body if isinstance(node,ast.FunctionDef) and node.name.startswith("test_")]
assert len(ids)==16 and len(set(ids))==16
bootstrap = "import sys,unittest;sys.path.insert(0,"+repr(str(HERE))+");suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in "+repr(ids)+");result=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not result.wasSuccessful())"
registration={"format":"verislop.support023-source-control-registration/1","actual_registration_pid":os.getpid(),"test_ids":ids,"guards":guards,"argv":["/usr/bin/python3.12","-I","-B","-c",bootstrap],"environment":{"PATH":"/usr/bin:/bin","LANG":"C.UTF-8","PYTHONDONTWRITEBYTECODE":"1"},"authority":"SOURCE_ONLY_NO_QUALIFICATION_AUTHORITY","synthetic_observations":"SYNTHETIC_SOURCE_CONTROL_NO_ACTUAL_AGENT","model_VIEW_Lean_native_task_qualification_calls":0}
output=HERE/"CONTROL_REGISTRATION_BEFORE_EXECUTION.json"
with output.open("x") as stream:
    json.dump(registration,stream,indent=2);stream.write("\n")
print(json.dumps({"actual_registration_pid":os.getpid(),"registered_tests":len(ids),"nonempty_guard_count":len(guards),"registration_sha256":sha(output.read_bytes())}),flush=True)
