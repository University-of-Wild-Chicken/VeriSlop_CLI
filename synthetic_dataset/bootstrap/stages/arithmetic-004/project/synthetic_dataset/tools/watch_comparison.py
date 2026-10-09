"""Refresh audited comparison artifacts; publish final results only after both manifests.

This observer makes no model calls and never cancels either experiment.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

from synthetic_dataset.tools.compare_runs import REPO


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', nargs=2, default=['qwen-local-003', 'luna-agents-002'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--interval', type=float, default=45)
    args = parser.parse_args()
    if not 1 <= args.interval <= 60:
        parser.error('--interval must be between 1 and 60 seconds')
    args.out.mkdir(parents=True, exist_ok=True)
    previous = None
    while True:
        roots = [REPO / 'synthetic_dataset/runs' / name for name in args.runs]
        final = all((root / 'run-manifest.json').exists() for root in roots)
        signature = [(root / name).stat().st_mtime_ns if (root / name).exists() else None
                     for root in roots for name in ('results.jsonl', 'run-manifest.json')]
        if signature != previous or final:
            command = [sys.executable, '-m', 'synthetic_dataset.tools.compare_runs',
                       '--runs', *args.runs, '--out', str(args.out)]
            if not final:
                command.append('--partial')
            result = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
            status = {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
                      'final_manifests_available': final, 'audit_exit_code': result.returncode,
                      'audit_output': result.stdout.strip(), 'audit_stderr': result.stderr.strip()}
            (args.out / 'WATCH_STATUS.json').write_text(json.dumps(status, indent=2) + '\n')
            print(json.dumps(status), flush=True)
            if final:
                return result.returncode
            previous = signature if result.returncode == 0 else None
        time.sleep(args.interval)


if __name__ == '__main__':
    raise SystemExit(main())
