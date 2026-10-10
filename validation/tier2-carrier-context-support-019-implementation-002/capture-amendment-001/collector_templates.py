"""Prepare fixed observable collector recipes; never execute a tool/model call.

This offline factory reads only the frozen generic002 source. Emitted viewer
recipes retain the inline reader and read only their exact own carrier.
The actual model author still receives the unmodified candidate002 message.
"""
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CANDIDATE_PATH = HERE.parent / "bootstrap_tier2_carrier_view.py"
CANDIDATE_SHA256 = "sha256:9930beff878848b05c8d69245fff12c1388f14254b6630504b36748c4c294366"
CASE_IDS = ("AC002-001", "AC002-002", "AC002-003", "AC002-004")
NORMAL_FORWARD = "text(await tools.exec_command({cmd, max_output_tokens: 16384}));"
NORMAL_PRAGMA = '// @exec: {"max_output_tokens": 20000}\n'
FAULT_PRAGMA = '// @exec: {"max_output_tokens": 256}\n'
FAULT_VIEW = {"operation": "field", "selector": "/user", "start_char": 0,
              "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048}


def _candidate():
    raw = CANDIDATE_PATH.read_bytes()
    if "sha256:" + hashlib.sha256(raw).hexdigest() != CANDIDATE_SHA256:
        raise ValueError("FROZEN_CANDIDATE002_MISMATCH")
    spec = importlib.util.spec_from_file_location("frozen_collector_candidate002", CANDIDATE_PATH)
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    return candidate


def collector_result_key(reference: dict[str, str], case_id: str) -> str:
    """One fixed own collector/case/path/raw-SHA key, never enumeration."""
    if case_id not in CASE_IDS:
        raise ValueError("UNREGISTERED_COLLECTOR_CASE")
    return "verislop.observable-carrier-collector-result/0.1:" + json.dumps(
        {"case_id": case_id, "path": reference["path"], "sha256": reference["sha256"]},
        sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _observe(recipe: str, reference: dict[str, str], case_id: str) -> str:
    if recipe.count(NORMAL_FORWARD) != 1:
        raise ValueError("ONE_FROZEN_FORWARDING_LINE_REQUIRED")
    key = json.dumps(collector_result_key(reference, case_id), ensure_ascii=True)
    observer = ('const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});\n'
                'text(ACTUAL_RESULT);\n'
                'store(' + key + ', {result: ACTUAL_RESULT, view: VIEW});')
    return recipe.replace(NORMAL_FORWARD, observer, 1)


def initial_collector_template(reference: dict[str, str], case_id: str = "AC002-001") -> str:
    """One unchanged normal inventory call, with only the fixed observer diff."""
    return _observe(_candidate().initial_session_template(reference), reference, case_id)


def next_collector_template(reference: dict[str, str], view: dict | None = None,
                            case_id: str = "AC002-001", *, fault: bool = False) -> str:
    """One explicit closed VIEW; normal calls have only the fixed observer diff."""
    candidate = _candidate()
    recipe = _observe(candidate.next_session_template(reference, view), reference, case_id)
    if not fault:
        return recipe
    if view != FAULT_VIEW or case_id not in ("AC002-002", "AC002-003"):
        raise ValueError("REGISTERED_FAULT_CASE_AND_EXACT_VIEW_REQUIRED")
    if case_id == "AC002-002":
        old = "await tools.exec_command({cmd, max_output_tokens: 16384})"
        new = "await tools.exec_command({cmd, max_output_tokens: 256})"
        if recipe.count(old) != 1:
            raise ValueError("ONE_NESTED_FAULT_BUDGET_POSITION_REQUIRED")
        return recipe.replace(old, new, 1)
    if not recipe.startswith(NORMAL_PRAGMA):
        raise ValueError("EXACT_OUTER_PRAGMA_REQUIRED")
    return FAULT_PRAGMA + recipe[len(NORMAL_PRAGMA):]


def plain_author_message(reference: dict[str, str]) -> str:
    """Original frozen002 message; collector observer never enters the author."""
    return _candidate().agent_message(reference)
