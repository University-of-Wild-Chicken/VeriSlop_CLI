"""Common result type for pipeline commands and their mapping to exit codes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import EXIT_BLOCKED, EXIT_INFRASTRUCTURE, EXIT_OK, Diagnostic

STATUS_EXIT = {"PASS": EXIT_OK, "BLOCKED": EXIT_BLOCKED, "INFRASTRUCTURE_FAILURE": EXIT_INFRASTRUCTURE}


@dataclass
class StageResult:
    command: str
    status: str  # PASS (the command's requested gate passed) | BLOCKED | INFRASTRUCTURE_FAILURE
    gate: str  # what this command's gate checks; never a claim of closure VERIFIED
    diagnostics: list[Diagnostic] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.status not in STATUS_EXIT:
            raise ValueError(self.status)

    @property
    def exit_code(self) -> int:
        return STATUS_EXIT[self.status]

    def to_json(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "status": self.status,
            "gate": self.gate,
            "asserts_closure_verified": False,
            "diagnostics": [d.to_json() for d in self.diagnostics],
            "artifacts": self.artifacts,
            "summary": self.summary,
        }


def status_from(diags: list[Diagnostic]) -> str:
    if any(d.severity == "infrastructure" for d in diags):
        return "INFRASTRUCTURE_FAILURE"
    if any(d.severity == "blocking" for d in diags):
        return "BLOCKED"
    return "PASS"
