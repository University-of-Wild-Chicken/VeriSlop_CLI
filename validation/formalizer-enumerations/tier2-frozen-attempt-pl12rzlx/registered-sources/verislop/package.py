"""Run package layout (specification §12) and root computation (§10.1).

```
<package>/
  package.json        run identity and artifact index (non-authoritative bookkeeping)
  request/            prompt.txt (exact bytes), request.json, routing.json
  draft.json          proposal; never downstream authority
  interpretation.json clause dispositions, assumptions, ambiguity decisions
  claims.json         frozen contract-phase claim inventory
  contract/           candidate/, challenge/ (frozen), proofs/
  accepted/           certificate, environment export, accepted IR, expression packages
  implementation/     exact candidate source / build inputs
  bridges/            bindings and link records
  tests/              campaign configuration and results
  closure/            implementation claims, policy, manifests, TCB, verifier registry, builds
  reviews/            review campaigns (ballots, consensus certificates)
  evidence/           immutable verifier evidence
  obligation-view.json derived lifecycle overlay
  report.json         authoritative decision
```
"""

from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION, __version__, canonical, fsutil
from .errors import UsageError
from .evidence import EvidenceStore

DEFAULT_PATHS = {
    "prompt": "request/prompt.txt",
    "request": "request/request.json",
    "routing": "request/routing.json",
    "draft": "draft.json",
    "interpretation": "interpretation.json",
    "claims": "claims.json",
    "contract": "contract",
    "accepted": "accepted",
    "accepted_ir": "accepted/accepted-ir.json",
    "implementation": "implementation",
    "bridges": "bridges",
    "tests": "tests",
    "closure": "closure",
    "reviews": "reviews",
    "view": "obligation-view.json",
    "report": "report.json",
}


def new_run_id() -> str:
    return "run-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + secrets.token_hex(3)


class Package:
    def __init__(self, root: Path, *, resolve_root: bool = True) -> None:
        # Untrusted import/write paths must retain symlink components for the
        # descriptor-relative readers and locks to reject them.
        self.root = Path(root).resolve() if resolve_root else Path(os.path.abspath(root))
        self._meta: dict[str, Any] | None = None
        self._store: EvidenceStore | None = None

    # -- identity ---------------------------------------------------------------------------

    @property
    def meta_path(self) -> Path:
        return self.root / "package.json"

    def exists(self) -> bool:
        return self.meta_path.is_file()

    def meta(self) -> dict[str, Any]:
        if self._meta is None:
            if self.meta_path.is_file():
                self._meta = canonical.load_file(self.meta_path)
            else:
                self._meta = {}
        return self._meta

    def ensure(self, run_id: str | None = None) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.exists():
            self._meta = {
                "schema_version": SCHEMA_VERSION,
                "artifact_kind": "run_package",
                "run_id": run_id or new_run_id(),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "verislop_version": __version__,
                "artifacts": {},
            }
            self._save_meta()

    def _save_meta(self) -> None:
        fsutil.write_json(self.meta_path, self.meta(), pretty=True)

    @property
    def run_id(self) -> str:
        rid = self.meta().get("run_id")
        if not rid:
            raise UsageError(f"{self.root} is not a VeriSlop run package (package.json missing)")
        return rid

    # -- artifact paths -----------------------------------------------------------------------

    def path(self, kind: str) -> Path:
        rel = self.meta().get("artifacts", {}).get(kind, DEFAULT_PATHS[kind])
        return self.root / rel

    def set_path(self, kind: str, target: Path) -> Path:
        target = Path(target).resolve()
        try:
            rel = target.relative_to(self.root).as_posix()
        except ValueError:
            raise UsageError(
                f"{kind} output {target} must be inside the run package {self.root}; "
                "use --package to choose the package directory"
            ) from None
        if rel != DEFAULT_PATHS[kind]:
            self.meta().setdefault("artifacts", {})[kind] = rel
            self._save_meta()
        return target

    def rel(self, path: Path) -> str:
        return Path(path).resolve().relative_to(self.root).as_posix()

    def set_meta(self, key: str, value: Any) -> None:
        self.meta()[key] = value
        self._save_meta()

    # -- evidence ------------------------------------------------------------------------------

    @property
    def evidence(self) -> EvidenceStore:
        if self._store is None:
            self._store = EvidenceStore(self.root, self.run_id)
        return self._store

    def reset_evidence_cache(self) -> None:
        self._store = None

    # -- roots ----------------------------------------------------------------------------------

    def interpretation_root(self) -> str | None:
        files = {"request/prompt.txt": self.path("prompt"), "draft.json": self.path("draft"),
                 "interpretation.json": self.path("interpretation")}
        if not all(p.is_file() for p in files.values()):
            return None
        att = self.root / "request" / "attachments"
        if att.is_dir():
            for rel in fsutil.list_files(att):
                files[f"request/attachments/{rel}"] = att / rel
        from .source_policy import PATH
        if (self.root / PATH).exists() or self.meta().get("source_policy") is not None:
            files[PATH] = self.root / PATH
        return fsutil.manifest_root(fsutil.manifest_for(files))

    def contract_input_root(self) -> str | None:
        """Recomputed from the frozen challenge inputs (never trusted from a stored field alone)."""
        from .contract import challenge_manifest

        manifest = challenge_manifest(self)
        return fsutil.manifest_root(manifest) if manifest else None

    def implementation_root(self) -> str | None:
        from .backends.registry import is_vscore

        if is_vscore(self):
            from .backends.registry import implementation_backend

            return implementation_backend(self).implementation_root(self)
        impl = self.path("implementation")
        if not impl.is_dir():
            return None
        return fsutil.manifest_root(fsutil.manifest_tree(impl, "implementation"))

    def file_digest(self, kind: str) -> str | None:
        p = self.path(kind)
        return canonical.digest(p.read_bytes()) if p.is_file() else None

    def link_root(self) -> str | None:
        from .backends.registry import is_vscore

        if is_vscore(self):
            from .backends.registry import implementation_backend

            return implementation_backend(self).link_root(self)
        ir = self.file_digest("accepted_ir")
        impl = self.implementation_root()
        bindings = self.path("bridges") / "bindings.json"
        claims = self.path("closure") / "implementation-claims.json"
        if not (ir and impl and bindings.is_file() and claims.is_file()):
            return None
        return canonical.digest_json({
            "accepted_ir": ir,
            "implementation_root": impl,
            "bindings": canonical.digest(bindings.read_bytes()),
            "implementation_claims": canonical.digest(claims.read_bytes()),
        })

    def test_root(self) -> str | None:
        link = self.link_root()
        campaign = self.path("tests") / "campaign.json"
        if not (link and campaign.is_file()):
            return None
        return canonical.digest_json({"link_root": link, "campaign": canonical.digest(campaign.read_bytes())})

    def roots(self) -> dict[str, str | None]:
        return {
            "interpretation_root": self.interpretation_root(),
            "contract_input_root": self.contract_input_root(),
            "implementation_root": self.implementation_root(),
            "link_root": self.link_root(),
            "test_root": self.test_root(),
        }


def find_runs_dir(start: Path | None = None) -> Path:
    base = Path(start or os.getcwd()).resolve()
    return base / ".verislop" / "runs"
