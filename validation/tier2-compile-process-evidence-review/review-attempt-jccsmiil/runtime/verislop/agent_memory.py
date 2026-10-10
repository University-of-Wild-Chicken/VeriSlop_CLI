"""Reloadable, bounded agent context; retained proposals are never proof evidence.

Raw bytes and canonical snapshot/index documents are written once. A locked,
append-only journal commits each new index; readers never fall back past a broken
head. Explicit historical snapshot refs remain independently restorable. The
filesystem/host is trusted to retain the journal: hashes do not authenticate a
wholesale, internally consistent rewrite or deletion of the entire store.
"""
from __future__ import annotations

import base64
import fcntl
import os
import re
import stat
from contextlib import contextmanager
from typing import Any, Iterator

from . import canonical, fsutil
from .errors import BlockedError, UsageError, blocked

BASE = "agents/memory"
SNAPSHOT_FORMAT = "verislop.agent-memory-snapshot/0.1"
INDEX_FORMAT = "verislop.agent-memory-index/0.1"
CONTEXT_FORMAT = "verislop.agent-memory-context/0.1"
MAX_ARTIFACTS = 64
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
MAX_CHECKPOINT_BYTES = 8 * 1024 * 1024
MAX_SNAPSHOTS = 256
MAX_MANIFEST_BYTES = 128 * 1024
MAX_CONTEXT_BYTES = 2 * 1024 * 1024
MAX_STORAGE_BYTES = 64 * 1024 * 1024
MAX_JSON_NODES = 65536
MAX_JSON_DEPTH = 64
MAX_JOURNAL_BYTES = MAX_SNAPSHOTS * 512
_HEX = r"[0-9a-f]{64}"
_AUTHORITY = "Retained agent context only; no proof, acceptance or milestone authority."


def _fail(message: str) -> None:
    raise blocked("STALE_OR_UNBOUND_EVIDENCE", f"agent memory: {message}")


def _bound(condition: bool, message: str, **details: Any) -> None:
    if not condition:
        raise blocked("BUDGET_EXHAUSTED", f"agent memory: {message}", details=details)


def _invalid(message: str) -> None:
    raise blocked("INVALID_CANDIDATE", f"agent memory: {message}")


def _stage(value: Any) -> str:
    if (not isinstance(value, str) or not value or len(value) > 128
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        _invalid("stage must be a nonempty, bounded string without control characters")
    return value


def _source(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        _invalid("artifact names must be bounded source-relative paths")
    try:
        value.encode("utf-8")
        return fsutil.check_relpath(value)
    except (UnicodeError, UsageError) as exc:
        # check_relpath raises UsageError; never normalize or repair a source ref.
        _invalid(f"unsafe artifact source path ({type(exc).__name__})")


def _json(value: Any, limit: int) -> bytes:
    pending = [(value, 0)]
    nodes = 0
    while pending:
        node, depth = pending.pop()
        nodes += 1
        _bound(nodes <= MAX_JSON_NODES and depth <= MAX_JSON_DEPTH, "JSON context exceeds node/depth bounds")
        if isinstance(node, dict):
            _bound(len(node) <= MAX_JSON_NODES, "JSON object exceeds node bounds")
            pending.extend((v, depth + 1) for v in node.values())
        elif isinstance(node, list):
            _bound(len(node) <= MAX_JSON_NODES, "JSON list exceeds node bounds")
            pending.extend((v, depth + 1) for v in node)
        elif node is not None and type(node) not in (str, int, bool):
            _invalid("context contains a non-JSON value")
    try:
        data = canonical.dumps(value)
    except (ValueError, TypeError, RecursionError) as exc:
        _invalid(f"context is not canonical JSON ({type(exc).__name__})")
    _bound(len(data) <= limit, "canonical JSON exceeds byte bound", bytes=len(data), limit=limit)
    return data


def _ref(path: str, data: bytes) -> dict:
    return {"path": path, "sha256": canonical.digest(data), "size": len(data)}


def _reference(value: Any, kind: str) -> dict:
    if not isinstance(value, dict) or set(value) != {"path", "sha256", "size"}:
        _fail("artifact reference has an invalid schema")
    digest = value["sha256"]
    if not isinstance(digest, str) or re.fullmatch("sha256:" + _HEX, digest) is None:
        _fail("invalid reference digest")
    size = value["size"]
    limit = MAX_ARTIFACT_BYTES if kind == "blobs" else MAX_MANIFEST_BYTES
    if type(size) is not int or not 0 <= size <= limit:
        _fail("invalid reference byte size")
    name = digest[7:]
    pattern = (rf"{BASE}/blobs/{name}\.blob" if kind == "blobs"
               else rf"{BASE}/{kind}/[0-9]{{8}}-{name}\.json")
    if not isinstance(value["path"], str) or re.fullmatch(pattern, value["path"]) is None:
        _fail("reference path is not bound to its content digest and artifact kind")
    return value


def _identity(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _regular(info: os.stat_result) -> None:
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        _fail("artifact must be a regular file with exactly one link")


def _open(root: int, relative: str, flags: int) -> tuple[int, int, str]:
    parts = relative.split("/")
    parent = os.dup(root)
    leaf = None
    try:
        for part in parts[:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            os.close(parent)
            parent = nxt
        leaf = os.open(parts[-1], flags | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o600, dir_fd=parent)
        _regular(os.fstat(leaf))
        return parent, leaf, parts[-1]
    except BaseException:
        if leaf is not None:
            os.close(leaf)
        os.close(parent)
        raise


def _anchored(parent: int, leaf: int, name: str) -> None:
    info = os.fstat(leaf)
    _regular(info)
    if _identity(info) != _identity(os.stat(name, dir_fd=parent, follow_symlinks=False)):
        _fail("artifact was replaced while being accessed")


def _read(root: int, relative: str, limit: int) -> bytes:
    parent, leaf, name = _open(root, relative, os.O_RDONLY)
    try:
        before = os.fstat(leaf)
        _bound(before.st_size <= limit, "persisted file exceeds read bound", limit=limit, bytes=before.st_size)
        data = bytearray()
        while True:
            chunk = os.read(leaf, min(65536, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            _bound(len(data) <= limit, "persisted file grew beyond read bound")
        _anchored(parent, leaf, name)
        if _identity(before) != _identity(os.fstat(leaf)) or len(data) != before.st_size:
            _fail("artifact changed during reading")
        return bytes(data)
    finally:
        os.close(leaf)
        os.close(parent)


def _write(root: int, relative: str, data: bytes) -> None:
    try:
        parent, leaf, name = _open(root, relative, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        if _read(root, relative, max(len(data), 1)) != data:
            _fail("write-once artifact already exists with different bytes")
        return
    try:
        remaining = memoryview(data)
        while remaining:
            written = os.write(leaf, remaining)
            if written <= 0:
                _fail("artifact write made no progress")
            remaining = remaining[written:]
        os.fsync(leaf)
        os.fchmod(leaf, 0o444)
        _anchored(parent, leaf, name)
        os.fsync(parent)
    finally:
        os.close(leaf)
        os.close(parent)


@contextmanager
def _store(pkg: Any, *, create: bool = False) -> Iterator[int | None]:
    path = pkg.root / BASE
    if not create and not os.path.lexists(path):
        yield None
        return
    try:
        with fsutil.open_directory(path, create=create) as root:
            if create:
                for name in ("blobs", "snapshots", "indexes"):
                    try:
                        os.mkdir(name, 0o700, dir_fd=root)
                    except FileExistsError:
                        pass
            parent, lock, name = _open(root, ".journal.lock", os.O_RDWR | os.O_CREAT if create else os.O_RDONLY)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX if create else fcntl.LOCK_SH)
                _anchored(parent, lock, name)
                if os.fstat(lock).st_size != 0:
                    _fail("journal lock file contains unexpected bytes")
                yield root
                _anchored(parent, lock, name)
                with fsutil.open_directory(path) as current:
                    a, b = os.fstat(root), os.fstat(current)
                    if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino):
                        _fail("memory directory was replaced")
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
                os.close(lock)
                os.close(parent)
    except OSError as exc:
        _fail(f"cannot safely access retained artifact ({exc.strerror})")
    except BlockedError as exc:
        if exc.diagnostics and exc.diagnostics[0].code == "INPUT_MUTATION":
            _fail("unsafe memory directory or ancestor")
        raise


def _inventory(root: int) -> tuple[dict[str, set[str]], int]:
    expected = {"blobs", "snapshots", "indexes", ".journal.lock", "journal.jsonl"}
    with os.scandir(root) as entries:
        names = set()
        for entry in entries:
            names.add(entry.name)
            if len(names) > len(expected) or entry.name not in expected:
                _fail("unexpected memory directory entry")
    if not {"blobs", "snapshots", "indexes", ".journal.lock"} <= names:
        _fail("memory directory is incomplete")
    found = {}
    total = 0
    for folder in ("blobs", "snapshots", "indexes"):
        fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=root)
        try:
            rows = set()
            maximum = MAX_ARTIFACTS * MAX_SNAPSHOTS if folder == "blobs" else MAX_SNAPSHOTS
            pattern = (_HEX + r"\.blob" if folder == "blobs" else r"[0-9]{8}-" + _HEX + r"\.json")
            with os.scandir(fd) as entries:
                for entry in entries:
                    rows.add(entry.name)
                    _bound(len(rows) <= maximum, "memory file count exceeds bound")
                    if re.fullmatch(pattern, entry.name) is None:
                        _fail("unexpected memory artifact filename")
                    info = entry.stat(follow_symlinks=False)
                    _regular(info)
                    limit = MAX_ARTIFACT_BYTES if folder == "blobs" else MAX_MANIFEST_BYTES
                    _bound(info.st_size <= limit, "memory artifact exceeds its file byte bound", limit=limit, bytes=info.st_size)
                    total += info.st_size
            found[folder] = rows
        finally:
            os.close(fd)
    if "journal.jsonl" in names:
        info = os.stat("journal.jsonl", dir_fd=root, follow_symlinks=False)
        _regular(info)
        total += info.st_size
    _bound(total <= MAX_STORAGE_BYTES, "memory storage exceeds byte bound", bytes=total, limit=MAX_STORAGE_BYTES)
    return found, total


def _document(root: int, ref: dict, kind: str) -> dict:
    _reference(ref, kind)
    data = _read(root, ref["path"][len(BASE) + 1:], MAX_MANIFEST_BYTES)
    if len(data) != ref["size"] or canonical.digest(data) != ref["sha256"]:
        _fail("snapshot/index size or digest does not match its reference")
    try:
        value = canonical.loads(data)
    except (ValueError, RecursionError):
        _fail("snapshot/index is not strict JSON")
    if _json(value, MAX_MANIFEST_BYTES) != data or not isinstance(value, dict):
        _fail("snapshot/index is not a canonical JSON object")
    return value


def _snapshot(root: int, ref: dict) -> dict:
    value = _document(root, ref, "snapshots")
    if (set(value) != {"format", "sequence", "stage", "previous_snapshot", "metadata", "artifacts"}
            or value["format"] != SNAPSHOT_FORMAT or type(value["sequence"]) is not int
            or not 1 <= value["sequence"] <= MAX_SNAPSHOTS
            or ref["path"].split("/")[-1][:8] != f"{value['sequence']:08d}"
            or not isinstance(value["metadata"], dict) or not isinstance(value["artifacts"], list)):
        _fail("snapshot manifest has an invalid schema or version")
    _stage(value["stage"])
    _json(value["metadata"], MAX_MANIFEST_BYTES)
    if value["previous_snapshot"] is not None:
        _reference(value["previous_snapshot"], "snapshots")
    _bound(len(value["artifacts"]) <= MAX_ARTIFACTS, "snapshot artifact count exceeds bound")
    names = []
    total = 0
    for row in value["artifacts"]:
        if not isinstance(row, dict) or set(row) != {"source_ref", "blob_ref"}:
            _fail("snapshot artifact entry has an invalid schema")
        names.append(_source(row["source_ref"]))
        _reference(row["blob_ref"], "blobs")
        total += row["blob_ref"]["size"]
    if names != sorted(set(names), key=lambda n: n.encode("utf-8")) or len({n.casefold() for n in names}) != len(names):
        _fail("snapshot source refs are unordered, repeated or collide")
    _bound(total <= MAX_CHECKPOINT_BYTES, "snapshot artifact bytes exceed bound")
    return value


def _history(root: int) -> tuple[list[tuple[dict, dict]], dict | None, bytes, int]:
    files, storage = _inventory(root)
    # Validate retained raw proposals even when a caller selects another stage.
    # Otherwise an append could reach a provider before discovering corruption
    # in a previous response. Inventory already bounds total work to 64 MiB.
    for name in sorted(files["blobs"]):
        data = _read(root, "blobs/" + name, MAX_ARTIFACT_BYTES)
        if canonical.sha256_hex(data) != name[:-5]:
            _fail("content-addressed retained artifact has changed")
    try:
        journal = _read(root, "journal.jsonl", MAX_JOURNAL_BYTES)
    except FileNotFoundError:
        journal = b""
    if journal and not journal.endswith(b"\n"):
        _fail("journal has an incomplete commit record")
    lines = journal.splitlines()
    _bound(len(lines) <= MAX_SNAPSHOTS, "snapshot history exceeds count bound")
    history = []
    previous_index = None
    snapshot_refs = []
    index_names = set()
    for sequence, line in enumerate(lines, 1):
        try:
            commit = canonical.loads(line)
        except (ValueError, RecursionError):
            _fail("journal commit is not strict JSON")
        if (not isinstance(commit, dict) or set(commit) != {"sequence", "index_ref"}
                or type(commit["sequence"]) is not int or commit["sequence"] != sequence
                or _json(commit, 512) != line):
            _fail("journal commits are stale, unordered or malformed")
        ref = _reference(commit["index_ref"], "indexes")
        index = _document(root, ref, "indexes")
        if (set(index) != {"format", "sequence", "previous_index", "snapshots"}
                or index["format"] != INDEX_FORMAT or type(index["sequence"]) is not int
                or index["sequence"] != sequence
                or ref["path"].split("/")[-1][:8] != f"{sequence:08d}"
                or index["previous_index"] != previous_index
                or not isinstance(index["snapshots"], list) or len(index["snapshots"]) != sequence
                or index["snapshots"][:-1] != snapshot_refs):
            _fail("latest index does not extend the committed snapshot chain")
        snapshot_ref = _reference(index["snapshots"][-1], "snapshots")
        snapshot = _snapshot(root, snapshot_ref)
        if snapshot["sequence"] != sequence or snapshot["previous_snapshot"] != (snapshot_refs[-1] if snapshot_refs else None):
            _fail("snapshot does not extend the committed chain")
        if any(row["blob_ref"]["path"].split("/")[-1] not in files["blobs"] for row in snapshot["artifacts"]):
            _fail("committed snapshot references a missing artifact")
        snapshot_refs.append(snapshot_ref)
        history.append((snapshot_ref, snapshot))
        previous_index = ref
        index_names.add(ref["path"].split("/")[-1])
    if files["indexes"] != index_names or files["snapshots"] != {r["path"].split("/")[-1] for r in snapshot_refs}:
        _fail("snapshot/index files are missing, stale or uncommitted")
    return history, previous_index, journal, storage


def _restore(root: int, snapshot: dict) -> dict[str, bytes]:
    artifacts = {}
    for row in snapshot["artifacts"]:
        ref = row["blob_ref"]
        data = _read(root, ref["path"][len(BASE) + 1:], MAX_ARTIFACT_BYTES)
        if len(data) != ref["size"] or canonical.digest(data) != ref["sha256"]:
            _fail("retained artifact size or hash does not match its snapshot")
        artifacts[row["source_ref"]] = data
    return artifacts


def checkpoint(pkg: Any, stage: str, artifacts: dict[str, bytes], *, metadata: dict | None = None) -> dict:
    """Commit exact source-relative byte artifacts; return manifest and pinned refs."""
    _stage(stage)
    if not isinstance(artifacts, dict) or any(type(v) is not bytes for v in artifacts.values()):
        _invalid("artifacts must map source-relative names to exact bytes")
    artifacts = dict(artifacts)
    _bound(len(artifacts) <= MAX_ARTIFACTS, "too many checkpoint artifacts")
    names = [_source(name) for name in artifacts]
    if len({name.casefold() for name in names}) != len(names):
        _invalid("artifact names have a case-insensitive collision")
    for data in artifacts.values():
        _bound(len(data) <= MAX_ARTIFACT_BYTES, "artifact exceeds byte bound", bytes=len(data), limit=MAX_ARTIFACT_BYTES)
    _bound(sum(map(len, artifacts.values())) <= MAX_CHECKPOINT_BYTES, "checkpoint exceeds total byte bound")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        _invalid("metadata must be a canonical JSON object")
    metadata = canonical.loads(_json(metadata, MAX_MANIFEST_BYTES))
    with _store(pkg, create=True) as root:
        history, previous_index, journal, storage = _history(root)
        sequence = len(history) + 1
        _bound(sequence <= MAX_SNAPSHOTS, "snapshot count exhausted")
        rows = []
        blobs = {}
        for name in sorted(names, key=lambda n: n.encode("utf-8")):
            data = artifacts[name]
            path = f"{BASE}/blobs/{canonical.sha256_hex(data)}.blob"
            rows.append({"source_ref": name, "blob_ref": _ref(path, data)})
            blobs[path[len(BASE) + 1:]] = data
        manifest = {"format": SNAPSHOT_FORMAT, "sequence": sequence, "stage": stage,
                    "previous_snapshot": history[-1][0] if history else None,
                    "metadata": metadata, "artifacts": rows}
        data = _json(manifest, MAX_MANIFEST_BYTES)
        snapshot_ref = _ref(f"{BASE}/snapshots/{sequence:08d}-{canonical.sha256_hex(data)}.json", data)
        index = {"format": INDEX_FORMAT, "sequence": sequence, "previous_index": previous_index,
                 "snapshots": [ref for ref, _ in history] + [snapshot_ref]}
        index_data = _json(index, MAX_MANIFEST_BYTES)
        index_ref = _ref(f"{BASE}/indexes/{sequence:08d}-{canonical.sha256_hex(index_data)}.json", index_data)
        commit = _json({"sequence": sequence, "index_ref": index_ref}, 512) + b"\n"
        new_blob_bytes = 0
        for path, content in blobs.items():
            try:
                existing = _read(root, path, max(len(content), 1))
            except FileNotFoundError:
                new_blob_bytes += len(content)
            else:
                if existing != content:
                    _fail("content-addressed blob already contains different bytes")
        _bound(storage + new_blob_bytes + len(data) + len(index_data) + len(commit) <= MAX_STORAGE_BYTES,
               "checkpoint would exceed memory storage bound")
        for path, content in blobs.items():
            _write(root, path, content)
        _write(root, snapshot_ref["path"][len(BASE) + 1:], data)
        _write(root, index_ref["path"][len(BASE) + 1:], index_data)
        parent, leaf, name = _open(root, "journal.jsonl", os.O_RDWR | os.O_APPEND | os.O_CREAT)
        try:
            if os.fstat(leaf).st_size != len(journal) or os.read(leaf, len(journal) + 1) != journal:
                _fail("journal changed before commit")
            remaining = memoryview(commit)
            while remaining:
                written = os.write(leaf, remaining)
                if written <= 0:
                    _fail("journal write made no progress")
                remaining = remaining[written:]
            os.fsync(leaf)
            _anchored(parent, leaf, name)
            os.fsync(parent)
        finally:
            os.close(leaf)
            os.close(parent)
        return {**manifest, "snapshot_ref": snapshot_ref, "index_ref": index_ref}


def restore(pkg: Any, snapshot_ref: dict) -> dict[str, bytes]:
    """Restore one explicitly pinned historical snapshot without rewriting it."""
    with _store(pkg) as root:
        if root is None:
            _fail("referenced memory store is missing")
        return _restore(root, _snapshot(root, snapshot_ref))


def capture_context(pkg: Any, stage: str, payload: dict, *, extra_artifacts: dict | None = None) -> dict:
    """Persist current inputs before hydration; never recursively persist memory."""
    if not isinstance(payload, dict):
        _invalid("context payload must be a canonical JSON object")
    data = _json(payload, MAX_ARTIFACT_BYTES)
    pending = [payload]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            if node.get("format") == CONTEXT_FORMAT:
                _invalid("capture current inputs before adding hydrated agent memory")
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    if extra_artifacts is not None and not isinstance(extra_artifacts, dict):
        _invalid("extra_artifacts must map source-relative names to bytes")
    artifacts = dict(extra_artifacts or {})
    if "payload.json" in artifacts:
        _invalid("extra_artifacts cannot replace payload.json")
    artifacts["payload.json"] = data
    manifest = checkpoint(pkg, stage, artifacts, metadata={"kind": "agent-context", "authority": _AUTHORITY})
    return {**manifest, "authority": _AUTHORITY}


def _select(history: list, *, stage_prefixes: list[str] | None, stages: list[str] | None) -> list:
    if stage_prefixes is not None and stages is not None:
        _invalid("choose either exact stages or stage prefixes")
    selected = stage_prefixes if stage_prefixes is not None else stages
    if selected is not None:
        if not isinstance(selected, list) or len(selected) > MAX_ARTIFACTS:
            _invalid("stage filter must be a bounded list")
        for stage in selected:
            _stage(stage)
        return [(ref, doc) for ref, doc in history
                if any(doc["stage"].startswith(s) if stage_prefixes is not None else doc["stage"] == s for s in selected)]
    return history


def latest_snapshot(pkg: Any, *, stage_prefix: str | None = None) -> dict | None:
    """Return the latest validated snapshot ref without hydrating its artifacts."""
    if stage_prefix is not None:
        _stage(stage_prefix)
    with _store(pkg) as root:
        if root is None:
            return None
        history, _index, _journal, _storage = _history(root)
        selected = _select(history, stage_prefixes=[stage_prefix] if stage_prefix is not None else None, stages=None)
        if selected:
            _restore(root, selected[-1][1])
        return dict(selected[-1][0]) if selected else None


def context_for(pkg: Any, *, last: int = 3, stage_prefixes: list[str] | None = None,
                stages: list[str] | None = None) -> dict:
    """Reload selected complete snapshots; oversize is explicit, never trimmed."""
    if type(last) is not int or not 1 <= last <= MAX_SNAPSHOTS:
        _invalid("last must be an integer within snapshot bounds")
    _select([], stage_prefixes=stage_prefixes, stages=stages)
    with _store(pkg) as root:
        history, index_ref = [], None
        if root is not None:
            history, index_ref, _journal, _storage = _history(root)
        selected = _select(history, stage_prefixes=stage_prefixes, stages=stages)[-last:]
        snapshots = []
        for ref, manifest in selected:
            artifacts = {}
            for source, data in _restore(root, manifest).items():
                try:
                    content, encoding = data.decode("utf-8", errors="strict"), "utf-8"
                except UnicodeDecodeError:
                    content, encoding = base64.b64encode(data).decode("ascii"), "base64"
                artifacts[source] = {"encoding": encoding, "content": content}
            snapshots.append({"snapshot_ref": ref, "manifest": manifest, "artifacts": artifacts})
        context = {"format": CONTEXT_FORMAT, "authority": _AUTHORITY, "index_ref": index_ref,
                   "selection": {"last": last, "stage_prefixes": stage_prefixes, "stages": stages},
                   "snapshots": snapshots}
        _json(context, MAX_CONTEXT_BYTES)
        return context
