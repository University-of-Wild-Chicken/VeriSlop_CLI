"""Authoritative evidence store.

Only registered verifier code paths in the supervisor call :meth:`EvidenceStore.record`.
Candidate generators never receive the store location. Records are write-once, read-only,
content-addressed (the evidence ID is derived from the record content) and each binds a claim
to an input root and to the exact hash of the verifier that produced it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION, canonical, fsutil, schemas
from .errors import InfrastructureError, Diagnostic
from .verifiers import VERIFIERS, host_environment, trusted_dependencies, verifier_hash

STATUSES = ("PASS", "BLOCK", "INFRASTRUCTURE_FAILURE")


@dataclass
class Evidence:
    record: dict[str, Any]
    result: dict[str, Any]
    problems: list[str]

    @property
    def id(self) -> str:
        return self.record["evidence_id"]

    @property
    def claim_id(self) -> str:
        return self.record["claim_id"]

    @property
    def status(self) -> str:
        return self.record["status"]

    @property
    def sequence(self) -> int:
        return int(self.result.get("sequence", 0))

    @property
    def verifier_current(self) -> bool:
        vid = self.record["verifier_id"]
        return vid in VERIFIERS and verifier_hash(vid) == self.record["verifier_hash"]

    @property
    def valid(self) -> bool:
        return not self.problems


class EvidenceStore:
    def __init__(self, pkg: Path, closure_id: str, *, sequence_base: int = 0) -> None:
        self.pkg = Path(pkg)
        self.dir = self.pkg / "evidence"
        self.raw_dir = self.dir / "raw"
        self.closure_id = closure_id
        self.sequence_base = sequence_base
        self._cache: list[Evidence] | None = None

    # -- writing ------------------------------------------------------------------------------

    def record(
        self,
        *,
        claim_id: str,
        verifier_id: str,
        status: str,
        scope: list[str],
        input_root: str,
        result: dict[str, Any],
        invocation: list[str],
        exit_code: int = 0,
        environment: dict[str, str] | None = None,
        trusted: list[str] | None = None,
    ) -> Evidence:
        if status not in STATUSES:
            raise ValueError(f"invalid evidence status {status}")
        if verifier_id not in VERIFIERS:
            raise ValueError(f"unregistered verifier {verifier_id}")
        if not scope:
            raise ValueError("evidence requires a non-empty scope")
        seq = self.sequence_base + len(self.load()) + 1
        raw = dict(result)
        raw.update({
            "claim_id": claim_id,
            "sequence": seq,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        raw_bytes = canonical.dumps(raw)
        raw_hash = canonical.digest(raw_bytes)
        raw_ref = f"evidence/raw/{raw_hash.split(':', 1)[1]}.json"
        fsutil.write_once(self.pkg / raw_ref, raw_bytes)
        env = dict(host_environment())
        env.update(environment or {})
        body = {
            "schema_version": SCHEMA_VERSION,
            "closure_id": self.closure_id,
            "claim_id": claim_id,
            "input_root_hash": input_root,
            "verifier_id": verifier_id,
            "verifier_hash": verifier_hash(verifier_id),
            "execution_environment": {k: v for k, v in env.items() if v},
            "invocation": [a for a in invocation if a] or ["verislop"],
            "raw_result_ref": raw_ref,
            "raw_result_hash": raw_hash,
            "exit_code": exit_code,
            "status": status,
            "scope": scope,
            "trusted_dependencies": sorted(set((trusted or []) + trusted_dependencies(verifier_id))),
        }
        evidence_id = "ev-" + canonical.sha256_hex(canonical.dumps(body))[:32]
        record = {"evidence_id": evidence_id, **body}
        issues = schemas.validate("evidence", record)
        if issues:
            raise InfrastructureError(
                f"internal evidence record failed schema validation: {issues[0]}",
                [Diagnostic("VERIFIER_FAILURE", str(issues[0]), severity="infrastructure")],
            )
        fsutil.write_once(self.dir / f"{evidence_id}.json", canonical.dumps(record))
        ev = Evidence(record, raw, [])
        if self._cache is not None:
            self._cache.append(ev)
        return ev

    # -- reading ------------------------------------------------------------------------------

    def load(self) -> list[Evidence]:
        if self._cache is not None:
            return self._cache
        out: list[Evidence] = []
        if self.dir.is_dir():
            for path in sorted(self.dir.glob("ev-*.json")):
                out.append(self._load_one(path))
        executions = self.pkg / "closure" / "executions"
        if executions.is_dir():
            for folder in sorted(executions.iterdir()):
                if not folder.is_dir() or folder.is_symlink():
                    continue
                try:
                    snapshot = validated_execution(folder)
                except (OSError, ValueError, RuntimeError):
                    # No portion of an incomplete/corrupt publication is authority.
                    continue
                for entry in snapshot["execution_inventory"]:
                    if entry["path"].startswith("evidence/ev-") and entry["path"].endswith(".json"):
                        ev = self._load_one(folder / entry["path"], base=folder)
                        if (ev.claim_id.startswith("END_TO_END_VERIFIED:") and ev.status == "PASS"
                                and snapshot["mechanical_status"] != "VERIFIED"):
                            continue
                        out.append(ev)
        out.sort(key=lambda e: e.sequence)
        self._cache = out
        return out

    def _load_one(self, path: Path, *, base: Path | None = None) -> Evidence:
        problems: list[str] = []
        try:
            record = canonical.loads(path.read_bytes())
        except Exception as exc:  # noqa: BLE001 - reported as an integrity problem
            return Evidence({"evidence_id": path.stem, "claim_id": "?", "status": "BLOCK",
                             "verifier_id": "?", "verifier_hash": "?"}, {}, [f"unreadable: {exc}"])
        for issue in schemas.validate("evidence", record)[:3]:
            problems.append(f"schema: {issue}")
        body = {k: v for k, v in record.items() if k != "evidence_id"}
        expected_id = "ev-" + canonical.sha256_hex(canonical.dumps(body))[:32]
        if record.get("evidence_id") != expected_id or path.stem != expected_id:
            problems.append("evidence ID does not match record content (tampered or corrupt)")
        result: dict[str, Any] = {}
        raw_path = (base or self.pkg) / str(record.get("raw_result_ref", ""))
        if raw_path.is_file():
            raw_bytes = raw_path.read_bytes()
            if canonical.digest(raw_bytes) != record.get("raw_result_hash"):
                problems.append("raw result hash mismatch")
            else:
                result = canonical.loads(raw_bytes)
        else:
            problems.append("raw result missing")
        if result and result.get("claim_id") != record.get("claim_id"):
            problems.append("raw result is bound to a different claim")
        return Evidence(record, result, problems)

    def for_claim(self, claim_id: str) -> list[Evidence]:
        return [e for e in self.load() if e.claim_id == claim_id]

    def by_id(self, evidence_id: str) -> Evidence | None:
        for e in self.load():
            if e.id == evidence_id:
                return e
        return None


def validated_execution(folder: Path) -> dict[str, Any]:
    """Validate the complete frozen graph and retained outputs without recursion.

    The staged evidence store read by validate_execution has no executions child,
    so checking a published execution cannot recursively reload the run's history.
    A malformed, incomplete or stale publication contributes no current evidence.
    """
    from .backends import vscore_closure
    from .bridges.manifest import InvalidPackage
    from .errors import VeriSlopError
    from .package import Package

    folder = Path(folder)
    try:
        if folder.parent.name != "executions" or folder.parent.parent.name != "closure":
            raise ValueError("not a declared closure execution directory")
        pkg = Package(folder.parents[2], resolve_root=False)
        from .backends.registry import closure_backend
        vscore_closure = closure_backend(pkg)
        claims = vscore_closure._claims(pkg)
        root = vscore_closure.closure_input_root(pkg)
        roots = vscore_closure._roots(pkg, vscore_closure._selection(pkg), root)
        return vscore_closure.validate_execution(folder,
            expected_root=root, frozen_claims=claims, expected_roots=roots)
    except (vscore_closure.checker.EdgeFailure, InvalidPackage, VeriSlopError, KeyError, TypeError) as exc:
        raise ValueError(str(exc)) from exc
