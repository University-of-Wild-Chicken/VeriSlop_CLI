"""Prepare fixed observable collector recipes; never execute a tool/model call.

This offline factory reads only the candidate003 generic source source. Emitted viewer
recipes retain the inline reader and read only their exact own carrier.
The actual model author still receives the candidate003 author message (with explicit non-VIEW checkpoint/hash recipes).
"""
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CANDIDATE_PATH = HERE.parent / "bootstrap_tier2_carrier_view.py"
CANDIDATE_SHA256 = "sha256:1f70b9f4925ec0c1ff657f3e68f36c7f65e2222764ea1bc6c1d038868e5585d5"
CASE_IDS = ("AC002-001", "AC002-002", "AC002-003", "AC002-004")
NORMAL_FORWARD = "text(await tools.exec_command({cmd, max_output_tokens: 16384}));"
NORMAL_ACTUAL_RESULT = "const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});"
FAULT_ACTUAL_RESULT = "const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 256});"
NORMAL_PRAGMA = '// @exec: {"max_output_tokens": 20000}\n'
FAULT_PRAGMA = '// @exec: {"max_output_tokens": 256}\n'
FAULT_VIEW = {"operation": "field", "selector": "/user", "start_char": 0,
              "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048}


def _candidate():
    raw = CANDIDATE_PATH.read_bytes()
    if "sha256:" + hashlib.sha256(raw).hexdigest() != CANDIDATE_SHA256:
        raise ValueError("FROZEN_CANDIDATE003_MISMATCH")
    spec = importlib.util.spec_from_file_location("frozen_collector_candidate003", CANDIDATE_PATH)
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


def _replace_exact_source_line(recipe: str, old_line: str, new_source: str, error: str) -> str:
    """Replace one complete frozen LF-delimited statement, never quoted data."""
    lines = recipe.split("\n")
    if lines.count(old_line) != 1:
        raise ValueError(error)
    return "\n".join(new_source if line == old_line else line for line in lines)


def _observe(recipe: str, reference: dict[str, str], case_id: str) -> str:
    key = json.dumps(collector_result_key(reference, case_id), ensure_ascii=True)
    observer = ('const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});\n'
                'text(ACTUAL_RESULT);\n'
                'store(' + key + ', {result: ACTUAL_RESULT, view: VIEW});')
    return _replace_exact_source_line(recipe, NORMAL_FORWARD, observer,
                                      "ONE_FROZEN_FORWARDING_LINE_REQUIRED")


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
        return _replace_exact_source_line(recipe, NORMAL_ACTUAL_RESULT, FAULT_ACTUAL_RESULT,
                                          "ONE_NESTED_FAULT_BUDGET_POSITION_REQUIRED")
    if not recipe.startswith(NORMAL_PRAGMA):
        raise ValueError("EXACT_OUTER_PRAGMA_REQUIRED")
    return FAULT_PRAGMA + recipe[len(NORMAL_PRAGMA):]


def plain_author_message(reference: dict[str, str]) -> str:
    """Candidate003 author message; legacy collector observer never enters author."""
    return _candidate().agent_message(reference)
