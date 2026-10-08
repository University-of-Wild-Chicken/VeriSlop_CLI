"""Stable diagnostic codes, outcome exceptions and exit codes (specification §§9, 10.4, 11)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EXIT_OK = 0
EXIT_BLOCKED = 2
EXIT_INFRASTRUCTURE = 3
EXIT_USAGE = 64
EXIT_INTERRUPTED = 130  # platform SIGINT convention; the run is recorded as interrupted

# Required baseline codes (specification §10.4).
BASELINE_CODES = (
    "INTERPRETATION_UNRESOLVED",
    "INPUT_MUTATION",
    "CLAIM_MUTATION",
    "STATEMENT_MISMATCH",
    "INADMISSIBLE_AXIOM",
    "PROOF_UNRESOLVED",
    "MISSING_WITNESS",
    "WITNESS_INVALID",
    "IR_REIFICATION_MISMATCH",
    "UNSUPPORTED_SEMANTICS",
    "UNDECLARED_DEPENDENCY",
    "VERIFIER_FAILURE",
    "VERIFIER_NOT_RUN",
    "STALE_OR_UNBOUND_EVIDENCE",
    "UNMAPPED_IMPLEMENTATION_OBJECT",
    "AMBIGUOUS_CORRESPONDENCE",
    "NON_MECHANICAL_CORRESPONDENCE",
    "TEST_FAILURE",
    "EMPTY_TEST_CAMPAIGN",
    "CLEAN_BUILD_FAILURE",
    "NONDETERMINISM",
    "ORPHAN_CLAIM",
    "UNDEFINED_BEHAVIOR_DEPENDENCY",
    "SCOPE_LEAK",
)

# Additional stable codes used by this implementation.
EXTENSION_CODES = (
    "CONTRACT_REFUTED",            # concrete closed counterexample replayed by Lean
    "REFERENCE_REQUEST_MISMATCH",  # checked actual output differs from untrusted quoted-clause expectation
    "NO_PROGRESS",                # repeated identical failed candidate and diagnostics
    "UNSUPPORTED_CAPABILITY",      # requested tier/endpoint/target/backend is not implemented
    "KERNEL_REJECTION",            # the Lean kernel rejected a replayed candidate declaration
    "CANDIDATE_BUILD_FAILURE",     # a candidate failed to elaborate/compile in the sandbox
    "INVALID_CANDIDATE",           # a candidate artifact failed schema/semantic validation
    "UNCOVERED_SOURCE_CLAUSE",     # mechanical clause coverage check found unaccounted text
    "NOT_APPLICABLE_ROUTING",      # the request was routed NOT_APPLICABLE; nothing was verified
    "TEST_INCOMPLETE",             # campaign timed out or could not evaluate required cases
    "REVIEW_REJECTED",             # a configured review tier rejected the candidate
    "REVIEW_INCOMPLETE",           # required reviewers could not produce valid ballots
    "REVIEW_NOT_RUN",              # review is configured as a release gate but has not run
    "CONFIGURATION_INVALID",       # provider/agent/review configuration diagnostic
    "PROVIDER_FAILURE",            # model provider transport/auth/quota failure
    "BUDGET_EXHAUSTED",            # bounded attempts/time/tokens ran out with work unresolved
    "INTERRUPTED",                 # the run was cancelled; unresolved checks remain
    "RUN_LOCKED",                  # another writer holds the run package
)

ALL_CODES = frozenset(BASELINE_CODES + EXTENSION_CODES)


@dataclass
class Diagnostic:
    code: str
    message: str
    severity: str = "blocking"  # blocking | infrastructure | warning | info
    obligations: list[str] = field(default_factory=list)
    claims: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.code not in ALL_CODES:
            raise ValueError(f"unregistered diagnostic code {self.code}")
        if self.severity not in ("blocking", "infrastructure", "warning", "info"):
            raise ValueError(f"invalid severity {self.severity}")

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "obligations": sorted(set(self.obligations)),
            "claims": sorted(set(self.claims)),
        }
        if self.details:
            out["details"] = self.details
        return out

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Diagnostic":
        return cls(
            code=data["code"],
            message=data["message"],
            severity=data.get("severity", "blocking"),
            obligations=list(data.get("obligations", [])),
            claims=list(data.get("claims", [])),
            details=dict(data.get("details", {})),
        )


class VeriSlopError(Exception):
    exit_code = EXIT_INFRASTRUCTURE

    def __init__(self, message: str, diagnostics: list[Diagnostic] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.diagnostics = diagnostics or []


class UsageError(VeriSlopError):
    """Invalid invocation or unusable configuration (exit 64)."""

    exit_code = EXIT_USAGE


class BlockedError(VeriSlopError):
    """A required claim cannot pass with the given inputs (exit 2)."""

    exit_code = EXIT_BLOCKED


class InfrastructureError(VeriSlopError):
    """A registered verifier or execution service failed independently of claim truth (exit 3)."""

    exit_code = EXIT_INFRASTRUCTURE


def blocked(code: str, message: str, **kw: Any) -> BlockedError:
    return BlockedError(message, [Diagnostic(code, message, **kw)])


def infra(code: str, message: str, **kw: Any) -> InfrastructureError:
    kw.setdefault("severity", "infrastructure")
    return InfrastructureError(message, [Diagnostic(code, message, **kw)])
