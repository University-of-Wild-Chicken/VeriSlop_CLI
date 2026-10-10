from pathlib import Path
import json,sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent/'runtime'))
sys.path.insert(0,str(Path(__file__).parent/'runtime/tests'))
from test_vscore3_readable_cli import ReadableCLITests
from test_vscore3_readable_integration import ProductionReadableMetadata
from verislop import cli,canonical
from verislop.backends import vscore3 as backend
from verislop.bridges import vscore3_checker as checker
from verislop.bridges.manifest import PackageReader

a=ReadableCLITests();a.setUp();b=ProductionReadableMetadata();b.setUp()
try:
 metadata={checker.READABLE_SELECTION_PATH:b.selection,**b.ctx.readable_diagnostics}
 selected={**a.info,'readable_selection':b.selection,'readable_candidate_artifacts':metadata,'readable_artifacts':dict(b.build.readable_artifacts)}
 a.args.readable_view=True
 with patch.object(checker,'preview',return_value=(a.spec,None,selected)):
  first=cli.cmd_vscore(a.args)
 assert first.status=='PASS'
 a.args.readable_view=False
 a.args.bridge_id='fresh-generic-bridge'
 proof=Path(a.root/'new-proof.lean');proof.write_bytes(b'generic second proof');a.args.proof=str(proof)
 legacy={k:v for k,v in a.info.items() if not k.startswith('readable_')}
 legacy.update(edge_axioms=[],readable_selection=None,readable_artifacts={},readable_candidate_artifacts={},readable_source_view=None)
 fresh={backend.SOURCE_FILE:Path(a.args.source).read_bytes(),'relation.json':Path(a.args.relation).read_bytes(),'Proof.lean':proof.read_bytes(),'proposal.json':b'{}'}
 with patch.object(checker,'preview',return_value=(a.spec,None,legacy)) as preview,patch.object(checker,'candidate_files',return_value=fresh):
  second=cli.cmd_vscore(a.args)
 assert second.status=='PASS'
 assert preview.call_args.kwargs=={}
 assert checker.READABLE_SELECTION_PATH not in second.summary['written']
 reader=PackageReader(Path(a.args.out))
 try:
  stale_selection,stale_meta=backend._candidate_readable_metadata(reader)
  reader.recheck()
 finally:reader.close()
 assert stale_selection==b.selection and stale_meta==metadata
 result={'first_status':first.status,'second_status':second.status,'second_flags':{'readable_view':False,'readable_selection':None},'second_preview_kwargs':preview.call_args.kwargs,'second_written':second.summary['written'],'second_reports_selection':second.summary.get('readable_selection'),'persisted_selection_hash':canonical.digest(stale_selection),'persisted_metadata_paths':sorted(stale_meta),'backend_interpretation':'nonlegacy frozen readable selection still read from successful legacy output directory','scope':'generic CLI writer and actual closed metadata/backend reader only; preview/candidate packaging kernel boundary mocked; no Lean/native/models'}
 print(json.dumps(result,indent=2))
 (Path(__file__).parent/'out-reuse-witness.json').write_text(json.dumps(result,indent=2)+'\n')
finally:
 a.doCleanups();b.doCleanups()
