"""`verislop auth`: user-owned provider credentials.

* Secrets are read from a masked prompt or stdin (`--from-stdin`); never from argv.
* The default store is the OS keyring (libsecret `secret-tool`). Without a keyring backend the
  CLI refuses rather than inventing a plaintext fallback; `--store file` requires the explicit
  `--allow-plaintext-file` choice and writes a 0600 file outside any run package.
* `env:VAR` and `secret-manager:REF` stores record metadata only.
* Metadata (logical ID, provider, auth profile, store reference, rotation events) is kept in
  `$VERISLOP_CONFIG_HOME/credentials.json`; secrets never enter run packages, prompts, logs,
  transcripts, manifests or hashes.

Reference forms usable in verislop.json `credential_ref`:
  env:VAR · keyring:verislop/<id> · secret-manager:<ref> (resolved by the command in
  $VERISLOP_SECRET_MANAGER_COMMAND) · secret-manager:verislop-file/<id> (the explicit file store).
"""

from __future__ import annotations

import argparse
import getpass
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import canonical, fsutil
from .errors import Diagnostic, UsageError
from .providers.config import config_home
from .stage import StageResult

KEYRING_SERVICE = "verislop"


def _meta_path() -> Path:
    return config_home() / "credentials.json"


def _load_meta() -> dict[str, Any]:
    p = _meta_path()
    if p.is_file():
        return canonical.load_file(p)
    return {"schema_version": "0.1", "artifact_kind": "credential_metadata", "credentials": {}}


def _save_meta(meta: dict[str, Any]) -> None:
    p = _meta_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fsutil.write_json(p, meta, pretty=True)
    os.chmod(p, 0o600)


def keyring_available() -> bool:
    return shutil.which("secret-tool") is not None


def _read_secret(from_stdin: bool) -> str:
    if from_stdin:
        secret = sys.stdin.readline().rstrip("\r\n")
    else:
        if not sys.stdin.isatty():
            raise UsageError("no TTY for a masked prompt; pass --from-stdin to read the secret from standard input")
        secret = getpass.getpass("API credential (input hidden): ")
    if not secret:
        raise UsageError("empty credential")
    return secret


def resolve(ref: str) -> str:
    """Resolve a credential reference to its secret. Callers must never log or persist it."""
    kind, _, rest = ref.partition(":")
    if kind == "env":
        val = os.environ.get(rest)
        if not val:
            raise LookupError(f"environment variable {rest} is not set")
        return val
    if kind == "keyring":
        if not keyring_available():
            raise LookupError("no OS keyring backend (secret-tool) is available")
        service, _, account = rest.partition("/")
        r = subprocess.run(["secret-tool", "lookup", "service", service, "account", account], capture_output=True, timeout=30)
        if r.returncode != 0 or not r.stdout:
            raise LookupError(f"keyring entry {rest} not found")
        return r.stdout.decode().rstrip("\n")
    if kind == "secret-manager":
        if rest.startswith("verislop-file/"):
            p = config_home() / "secrets" / rest.split("/", 1)[1]
            if not p.is_file():
                raise LookupError(f"file-store credential {p.name} not found")
            if p.stat().st_mode & 0o077:
                raise LookupError(f"file-store credential {p} is readable by other users; refusing to use it")
            return p.read_text().rstrip("\n")
        cmd = os.environ.get("VERISLOP_SECRET_MANAGER_COMMAND")
        if not cmd:
            raise LookupError("secret-manager references need VERISLOP_SECRET_MANAGER_COMMAND to be configured explicitly")
        r = subprocess.run([*cmd.split(), rest], capture_output=True, timeout=60)
        if r.returncode != 0 or not r.stdout:
            raise LookupError(f"secret manager could not resolve {rest}")
        return r.stdout.decode().rstrip("\n")
    raise LookupError(f"unsupported credential reference scheme {kind!r}")


def dispatch(args: argparse.Namespace) -> StageResult:
    action = args.auth_action
    meta = _load_meta()
    creds = meta["credentials"]
    if action == "add":
        cid = args.credential_id
        if not cid.replace("-", "").replace("_", "").replace(".", "").isalnum():
            raise UsageError("credential IDs use letters, digits, '-', '_' and '.' only")
        store = args.store
        entry: dict[str, Any] = {"provider": args.provider, "auth_profile": args.auth_profile,
                                 "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                 "rotations": list(creds.get(cid, {}).get("rotations", []))}
        if cid in creds:
            entry["rotations"].append({"rotated_at": entry["created_at"], "previous_ref": creds[cid]["ref"]})
        if store.startswith("env:"):
            entry.update({"store": "env", "ref": store})
        elif store.startswith("secret-manager:"):
            entry.update({"store": "secret-manager", "ref": store})
        elif store == "keyring":
            if not keyring_available():
                raise UsageError(
                    "no OS keyring backend is available (libsecret `secret-tool`); VeriSlop does not fall back to plaintext. "
                    "Use --store env:VAR, --store secret-manager:REF, or --store file --allow-plaintext-file")
            secret = _read_secret(args.from_stdin)
            r = subprocess.run(["secret-tool", "store", "--label", f"VeriSlop {cid}", "service", KEYRING_SERVICE, "account", cid],
                               input=secret.encode(), capture_output=True, timeout=60)
            del secret
            if r.returncode != 0:
                raise UsageError("the OS keyring rejected the credential")
            entry.update({"store": "keyring", "ref": f"keyring:{KEYRING_SERVICE}/{cid}"})
        elif store == "file":
            if not args.allow_plaintext_file:
                raise UsageError("--store file writes the secret unencrypted (mode 0600); confirm with --allow-plaintext-file")
            secret = _read_secret(args.from_stdin)
            d = config_home() / "secrets"
            d.mkdir(parents=True, exist_ok=True)
            os.chmod(d, 0o700)
            p = d / cid
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(secret + "\n")
            del secret
            entry.update({"store": "file", "ref": f"secret-manager:verislop-file/{cid}"})
        else:
            raise UsageError("--store must be keyring, env:VAR, secret-manager:REF or file")
        creds[cid] = entry
        _save_meta(meta)
        res = StageResult("auth", "PASS", "credential reference recorded (secret never printed or stored in run packages)")
        res.summary = {"credential_id": cid, "ref": entry["ref"], "store": entry["store"]}
        res.lines = [f"{cid}: use credential_ref {entry['ref']!r} in verislop.json"]
        return res
    if action == "list":
        res = StageResult("auth", "PASS", "credential metadata listed (no secrets)")
        res.summary = {"credentials": creds}
        res.lines = [f"{cid}: provider={c['provider']} store={c['store']} ref={c['ref']} rotations={len(c['rotations'])}" for cid, c in sorted(creds.items())] or ["no credentials recorded"]
        return res
    if action == "remove":
        c = creds.pop(args.credential_id, None)
        if c is None:
            raise UsageError(f"unknown credential {args.credential_id}")
        if c["store"] == "keyring" and keyring_available():
            subprocess.run(["secret-tool", "clear", "service", KEYRING_SERVICE, "account", args.credential_id], capture_output=True, timeout=30)
        if c["store"] == "file":
            p = config_home() / "secrets" / args.credential_id
            if p.exists():
                p.unlink()
        _save_meta(meta)
        res = StageResult("auth", "PASS", "credential removed")
        res.lines = [f"removed {args.credential_id}"]
        return res
    if action == "check":
        c = creds.get(args.credential_id)
        if c is None:
            raise UsageError(f"unknown credential {args.credential_id}")
        res = StageResult("auth", "PASS", "credential resolves" + (" and authenticates" if args.live else ""))
        try:
            secret = resolve(c["ref"])
            present = True
            del secret
        except LookupError as exc:
            present = False
            res.diagnostics.append(Diagnostic("PROVIDER_FAILURE", f"credential does not resolve: {exc}"))
        res.summary = {"credential_id": args.credential_id, "resolves": present, "live_check": None,
                       "may_incur_model_call": False}
        if present and args.live:
            from .providers import check as pcheck

            if not c.get("auth_profile"):
                res.diagnostics.append(Diagnostic("CONFIGURATION_INVALID", "a live check needs --auth-profile (an endpoint profile ID) recorded with the credential"))
            else:
                outcome = pcheck.live_auth_check(c["auth_profile"], c["ref"], None)
                res.summary["live_check"] = outcome
                if not outcome["ok"]:
                    res.diagnostics.append(Diagnostic("PROVIDER_FAILURE", f"live check: {outcome['diagnostic']}"))
        res.status = "BLOCKED" if res.diagnostics else "PASS"
        res.lines = [f"{args.credential_id}: resolves={present}" + (f" live={res.summary['live_check']}" if args.live else "")]
        return res
    raise UsageError(f"unknown auth action {action}")
