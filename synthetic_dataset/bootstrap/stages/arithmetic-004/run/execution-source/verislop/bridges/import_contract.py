"""Import an accepted contract by replaying its real acceptance/export pipeline.

Persisted evidence is checked for provenance, but never substitutes for the fresh Lean
execution. Untrusted source paths are read through PackageReader before any normal Package
API sees them. The source run is never written; replay runs in a supervisor-owned snapshot.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import SCHEMA_VERSION, accept, canonical, contract, export, fsutil, policy as policymod, schemas
from ..errors import Diagnostic, VeriSlopError
from ..events import EventSink
from ..package import DEFAULT_PATHS, Package
from ..stage import status_from
from ..verifiers import verifier_hash
from .manifest import InvalidPackage, PackageReader, MAX_COLLECTION_ITEMS, safe_relative

VERIFIER = "verislop.bridge-contract-importer"
HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
EVIDENCE_FILE = re.compile(r"ev-[0-9a-f]{32}\.json\Z")
REPLAY_PATHS = ("prompt", "request", "draft", "interpretation", "claims", "contract", "accepted", "accepted_ir", "routing")


class BridgeImportError(VeriSlopError):
    def __init__(self, diagnostics: list[Diagnostic]):
        self.status = status_from(diagnostics)
        self.exit_code = 3 if self.status == "INFRASTRUCTURE_FAILURE" else 2
        super().__init__("accepted contract import did not pass", diagnostics)


@dataclass
class ImportedContract:
    files: dict[str, bytes]
    ir: dict[str, Any]
    certificate: dict[str, Any]
    ir_path: str
    certificate_path: str
    replay_receipt: dict[str, Any]


def _require(condition: bool, message: str, code: str = "INVALID_CANDIDATE") -> None:
    if not condition:
        raise InvalidPackage(message, code)


def _schema(name: str, value: Any) -> None:
    issues = schemas.validate(name, value)
    _require(not issues, f"{name}: {issues[0] if issues else ''}")


def _evidence_names(reader: PackageReader) -> list[str]:
    """Bound directory enumeration without following an evidence-directory symlink."""
    try:
        fd = os.open("evidence", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=reader.fd)
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise InvalidPackage("evidence directory is not a real package directory") from exc
    try:
        names = []
        count = 0
        with os.scandir(fd) as entries:
            for entry in entries:
                count += 1
                _require(count <= 4096, "too many evidence directory entries")
                if EVIDENCE_FILE.fullmatch(entry.name):
                    names.append(entry.name)
        return sorted(names)
    finally:
        os.close(fd)


def import_contract(package_root: Path) -> ImportedContract:
    """Return stable checked inputs and a deterministic replay receipt, or structured failure.

    Returned files exclude mutable package metadata, event logs, and all evidence history.
    Those inputs are validated/copied only into the private replay snapshot. The receipt
    records actual replay and exact byte comparisons, never bridge semantic acceptance.
    """
    reader: PackageReader | None = None
    try:
        reader = PackageReader(package_root)  # lexical root: do not call Path.resolve first
        meta, _ = reader.json("package.json")
        _require(isinstance(meta, dict) and meta.get("schema_version") == SCHEMA_VERSION and
                 meta.get("artifact_kind") == "run_package", "not a supported run package")
        _require(isinstance(meta.get("run_id"), str) and 0 < len(meta["run_id"]) <= 256,
                 "run package needs a bounded run ID")
        overrides = meta.get("artifacts", {})
        _require(isinstance(overrides, dict) and set(overrides).issubset(DEFAULT_PATHS), "invalid package artifact mapping")
        for value in overrides.values():
            safe_relative(value)
        paths = {k: safe_relative(overrides.get(k, DEFAULT_PATHS[k])) for k in REPLAY_PATHS}
        _require(paths["contract"] != paths["accepted"] and
                 not paths["contract"].startswith(paths["accepted"] + "/") and
                 not paths["accepted"].startswith(paths["contract"] + "/"),
                 "contract and accepted directories must be separate")
        files: dict[str, bytes] = {}
        private: dict[str, bytes] = {}

        def read(rel: str, *, json: bool = False, private_only: bool = False):
            rel = safe_relative(rel)
            if json:
                value, snap = reader.json(rel)
            else:
                snap = reader.read(rel, keep=True)
                value = None
            (private if private_only else files)[rel] = snap.data
            return value, snap

        ir_path = paths["accepted_ir"]
        ir, ir_snap = read(ir_path, json=True)
        _schema("accepted-ir", ir)
        certificate_path = safe_relative(ir["acceptance_certificate_ref"])
        cert, cert_snap = read(certificate_path, json=True)
        _schema("acceptance-certificate", cert)
        _require(cert["gate"] == "accepted_and_proved", "only accepted-and-proved contracts may be imported", "PROOF_UNRESOLVED")
        for ref in cert["artifacts"].values():
            _, snap = read(ref["path"])
            _require(snap.sha256 == ref["sha256"], "accepted artifact bytes differ from the certificate", "INPUT_MUTATION")

        challenge_dir = paths["contract"] + "/challenge"
        challenge, _ = read(challenge_dir + "/challenge.json", json=True)
        for name in contract.CHALLENGE_FILES:
            read(challenge_dir + "/" + name, json=name.endswith(".json"))
        frozen_policy = canonical.loads(files[challenge_dir + "/policy.json"])
        policy_names = [name for name, value in policymod.POLICIES.items() if value == frozen_policy]
        _require(len(policy_names) == 1 and frozen_policy["id"] == cert["policy"]["id"] and
                 policymod.policy_hash(frozen_policy) == cert["policy"]["hash"] and
                 frozen_policy["allowed_axioms"] == cert["policy"]["allowed_axioms"],
                 "import requires the exact current registered acceptance policy", "CLAIM_MUTATION")
        policy_name = policy_names[0]
        claims, _ = read(paths["claims"], json=True)
        _schema("claims", claims)
        # Interpretation inputs are needed for source provenance and for the normal export view.
        for key in ("prompt", "draft", "interpretation", "request"):
            read(paths[key], json=key != "prompt")
        request = canonical.loads(files[paths["request"]])
        _require(isinstance(request, dict), "request metadata is not an object")
        attachments = request.get("attachments", [])
        _require(isinstance(attachments, list) and len(attachments) <= MAX_COLLECTION_ITEMS, "invalid attachment inventory")
        for attachment in attachments:
            _require(isinstance(attachment, dict) and isinstance(attachment.get("path"), str), "invalid attachment record")
            _, snap = read(attachment["path"])
            _require(snap.sha256 == attachment.get("sha256"), "request attachment changed", "INPUT_MUTATION")

        # Exact expression-package references are derived from the accepted IR, not a directory walk.
        for rec in ir["obligations"].values():
            digest = rec["formal"]["formula_ref"].rsplit("@", 1)[-1]
            _require(HASH.fullmatch(digest) is not None, "accepted formula reference has no content hash")
            expr, snap = read(paths["accepted"] + "/expressions/" + digest[7:] + ".json", json=True)
            _require(snap.sha256 == digest, "accepted expression package changed", "INPUT_MUTATION")
            if isinstance(expr, dict) and "dependency_closure_ref" in expr:
                digest = expr["dependency_closure_ref"].rsplit("@", 1)[-1]
                _require(HASH.fullmatch(digest) is not None, "opaque closure reference has no content hash")
                _, snap = read(paths["accepted"] + "/expressions/" + digest[7:] + ".closure.json", json=True)
                _require(snap.sha256 == digest, "opaque expression dependency closure changed", "INPUT_MUTATION")

        # Evidence is untrusted input. Validate its shape/path/hash before EvidenceStore reads
        # copied bytes with its ordinary Package API. It will be checked again by verified_ir.
        evidence_names = _evidence_names(reader)
        for name in evidence_names:
            ev, _ = read("evidence/" + name, json=True, private_only=True)
            _schema("evidence", ev)
            body = {k: v for k, v in ev.items() if k != "evidence_id"}
            expected = "ev-" + canonical.sha256_hex(canonical.dumps(body))[:32]
            _require(ev["evidence_id"] == expected and name == expected + ".json", "evidence identity mismatch", "STALE_OR_UNBOUND_EVIDENCE")
            raw, snap = read(ev["raw_result_ref"], json=True, private_only=True)
            _require(snap.sha256 == ev["raw_result_hash"] and isinstance(raw, dict) and raw.get("claim_id") == ev["claim_id"] and
                     type(raw.get("sequence")) is int and raw["sequence"] >= 0,
                     "evidence raw result is invalid or unbound", "STALE_OR_UNBOUND_EVIDENCE")

        # Only validated path overrides are allowed to influence the normal Package API.
        replay_meta = {"schema_version": SCHEMA_VERSION, "artifact_kind": "run_package", "run_id": meta["run_id"],
                       "artifacts": {k: v for k, v in paths.items() if v != DEFAULT_PATHS[k]}}
        private["package.json"] = canonical.dumps(replay_meta)
        _require(not (set(files) & set(private)), "verification inputs overlap private replay metadata/evidence")
        with fsutil.temporary_directory(prefix="verislop-contract-import-") as tmp:
            root = Path(tmp)
            for rel, data in {**files, **private}.items():
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            pkg = Package(root)
            _challenge, diags = contract.load_frozen(pkg)
            if diags:
                raise BridgeImportError(diags)
            _require(challenge["contract_input_root"] == cert["contract_input_root"], "challenge/certificate root mismatch", "INPUT_MUTATION")
            _require(pkg.interpretation_root() == claims["bound_to"].get("interpretation_root") and
                     pkg.file_digest("prompt") == claims["bound_to"].get("request"),
                     "interpretation inputs no longer match the frozen claim provenance", "INPUT_MUTATION")
            _ir, _hash, _cert, diags = export.verified_ir(pkg)
            if diags:
                raise BridgeImportError(diags)
            candidate = pkg.path("contract") / "proofs" / "candidate.lean"
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_bytes(files[cert["artifacts"]["source"]["path"]])
            events = EventSink(pkg.run_id, quiet=True)
            accepted = accept.run(pkg, events, policy_name=policy_name)
            if accepted.status != "PASS":
                raise BridgeImportError(accepted.diagnostics or [Diagnostic("PROOF_UNRESOLVED", "fresh acceptance did not pass")])
            replay_cert = (pkg.path("accepted") / "acceptance.json").read_bytes()
            _require(replay_cert == files[certificate_path], "fresh acceptance differs from the supplied certificate", "STATEMENT_MISMATCH")
            exported = export.run(pkg, events)
            if exported.status != "PASS":
                raise BridgeImportError(exported.diagnostics or [Diagnostic("IR_REIFICATION_MISMATCH", "fresh export did not pass")])
            _require(pkg.path("accepted_ir").read_bytes() == files[ir_path], "fresh export differs from supplied accepted IR", "IR_REIFICATION_MISMATCH")
            # Check all stored accepted bytes, including opaque expression closures.
            for rel, data in files.items():
                _require((root / rel).read_bytes() == data, f"replay changed frozen input {rel}", "INPUT_MUTATION")
        reader.recheck()
        _require(_evidence_names(reader) == evidence_names, "evidence history changed during import", "INPUT_MUTATION")
        receipt = {
            "format": "verislop.contract-import-replay/0.1", "source_contract_root": cert["contract_input_root"],
            "source_ir_hash": ir_snap.sha256, "source_certificate_hash": cert_snap.sha256,
            "accepted_contract_replayed": True, "semantic_bridge_acceptance": False,
            "checked_artifacts": {name: ref["sha256"] for name, ref in sorted(cert["artifacts"].items())},
            "verifiers": {vid: verifier_hash(vid) for vid in ("verislop.lean-acceptance", "verislop.reifier", VERIFIER)},
        }
        return ImportedContract(dict(sorted(files.items())), ir, cert, ir_path, certificate_path, receipt)
    except BridgeImportError:
        raise
    except InvalidPackage as exc:
        raise BridgeImportError([Diagnostic(exc.code, str(exc))]) from exc
    except VeriSlopError as exc:
        raise BridgeImportError(exc.diagnostics or [Diagnostic("VERIFIER_FAILURE", str(exc), severity="infrastructure")]) from exc
    except OSError as exc:
        raise BridgeImportError([Diagnostic("VERIFIER_FAILURE", f"contract replay filesystem failure: {type(exc).__name__}",
                                            severity="infrastructure")]) from exc
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        raise BridgeImportError([Diagnostic("INVALID_CANDIDATE", f"invalid contract import metadata: {type(exc).__name__}")]) from exc
    finally:
        if reader is not None:
            reader.close()
