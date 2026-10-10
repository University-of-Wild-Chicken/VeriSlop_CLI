from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile,json,sys
sys.path.insert(0,str(Path(__file__).parent/'runtime'))
sys.path.insert(0,str(Path(__file__).parent/'runtime/tests'))
from test_vscore3_readable_integration import ProductionReadableMetadata
from verislop import canonical,policy,fsutil
from verislop.bridges import prepare,vscore3_checker as C
from verislop.targets import vscore3_target as T,vscore3_source as S

factory=ProductionReadableMetadata();factory.setUp()
try:
 src=S.compile_surface('program "vscore/0.3" profile "data-pipeline/0.3"; entry echo(x:Bool)->Bool{x}')
 rel=canonical.dumps({'schema_version':'0.3','format':T.RELATION_FORMAT,'template':T.TEMPLATE,'source_slot':'vscore-source','proof_slot':'vscore-proof','bindings':[{'symbol':'echo','entry':'echo'}]})
 certificate_path='accepted/certificate.json';ir_path='accepted/accepted-ir.json'
 digest=canonical.digest(b'generic accepted statement');rec={'id':'GF','revision':1,'required':True,'role':'guarantee','kind':'behavior','formal':{'representation':'contract_dsl','statement_hash':digest,'formula_ref':'expr@'+canonical.digest(b'generic expression')}}
 imported_files={f'contract/{role}':b'generic '+role.encode() for role in ('source','profile','olean','environment_export','statements')}
 imported_files['contract/profile']=canonical.dumps({'profile_id':'generic-profile','symbols':{},'enums':{},'records':{}})
 cert={'artifacts':{role:{'path':f'contract/{role}','sha256':canonical.digest(imported_files[f'contract/{role}'])} for role in ('source','profile','olean','environment_export','statements')},'policy':{'id':policy.get('strict')['id'],'hash':policy.policy_hash(policy.get('strict'))},'gate':'accepted_and_proved','toolchain':{'pin':'generic-test'}}
 ir={'acceptance_certificate_ref':certificate_path,'obligations':{'GF':rec}}
 imported_files[certificate_path]=canonical.dumps(cert);imported_files[ir_path]=canonical.dumps(ir)
 imported=SimpleNamespace(ir_path=ir_path,certificate_path=certificate_path,files=imported_files,certificate=cert,ir=ir,replay_receipt={})
 observations=[]
 for case in ("legacy","selected","extra-diagnostic","extra-selection"):
  selected=case!="legacy"
  info={'proposition_hash':canonical.digest(b'generic proposition'),'obligations':['GF'],'model':b'generic model','profile':b'generic profile','readable_selection':factory.selection if selected else None,'readable_candidate_artifacts':{C.READABLE_SELECTION_PATH:factory.selection,**factory.ctx.readable_diagnostics} if selected else {}}
  candidates=C.candidate_files('generic-readable',info,src,rel,b'generic proof')
  proposal=canonical.loads(candidates['proposal.json'])
  if case.startswith('extra-'):
   role='readable_diagnostic' if case=='extra-diagnostic' else 'readable_selection'
   path='support/readable/unused-'+case+'.json';candidates[path]=b'undeclared extra readable metadata'
   proposal['artifacts'].append({'slot_id':'extra-'+case,'role':role,'node_id':C.NODE,'path':path})
   proposal['reproducible_slots'].append('extra-'+case);proposal['reproducible_slots'].sort()
  C._schema('bridge-proposal',proposal)
  files,plan,manifest=prepare._assemble(imported,proposal,canonical.dumps(proposal),candidates)
  for value,name in [(plan,'bridge-plan'),(manifest,'bridge-artifacts')]:C._schema(name,value)
  with tempfile.TemporaryDirectory(prefix='generic-readable-context-') as tmp:
   root=Path(tmp)
   for name,data in files.items():fsutil.atomic_write(root/name,data)
   try:
    with patch.object(C,'_obligation_from_package',return_value={'generic':'accepted service isolated'}):ctx=C.load_context(root,'generic-readable','reference-to-vscore')
    outcome={'kind':'RETURNED','selection':ctx.readable_selection is not None}
   except Exception as exc:outcome={'kind':'EXCEPTION','type':type(exc).__name__,'message':str(exc)}
   rows=[x for x in manifest['artifacts'] if x['role'] in ('readable_selection','readable_diagnostic')]
   observations.append({'case':case,'selected':selected,'outcome':outcome,'prepared_metadata_rows':rows,'returned_diagnostics':sorted(ctx.readable_diagnostics) if outcome['kind']=='RETURNED' else None})
  if selected:
   saved=Path(__file__).parent/('generic-prepared-bundle-'+case);saved.mkdir(exist_ok=True)
   for name,data in files.items():fsutil.atomic_write(saved/name,data)
 assert observations[0]['outcome']=={'kind':'RETURNED','selection':False}
 assert all(x['outcome']['kind']=='RETURNED' for x in observations)
 assert all(x['returned_diagnostics']==['support/readable/diagnostics/0.json'] for x in observations[1:])
 result={'observations':observations,'real_boundaries':['canonical readable BASE schema/helper','candidate_files','prepare._assemble','bridge-plan/bridge-artifacts closed schemas','PackageReader','load_context'],'isolated_boundary':'_obligation_from_package + synthetic accepted contract metadata; no contract acceptance or semantic kernel claim','source':'fresh Bool echo fixture; no retained task/corpus artifact','defects':['selected prepared loader silently accepts extra readable_diagnostic/readable_selection artifact roles outside the frozen sidecar inventory; ctx drops them']}
 print(json.dumps(result,indent=2));(Path(__file__).parent/'prepared-context-witness.json').write_text(json.dumps(result,indent=2)+'\n')
finally:factory.doCleanups()
