import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from synthetic_dataset.tools import bootstrap_tier2 as bootstrap

cohort = Path('/home/augustus/VeriSlop_CLI/synthetic_dataset/bootstrap/stages/tier2-source-facets-018/run')
pending = bootstrap.pending_request(cohort)
if pending is not None:
    result = {key: pending[key] for key in bootstrap.BINDINGS}
    result.update(request_id=pending['request']['request_id'], request_sha256=pending['request_sha256'], role=pending['request']['instance'], agent_message=pending['agent_message'])
    print(json.dumps(result, ensure_ascii=False))
else:
    terminal = Path('/home/augustus/VeriSlop_CLI/validation/tier2-native-live-driver-018/driver-result.json')
    print(json.dumps({'pending': None, 'terminal_exists': terminal.is_file(), 'terminal': bootstrap.load(terminal) if terminal.is_file() else None}, ensure_ascii=False))
