"""Bounded, descriptor-relative reads of an untrusted bridge package.

These checks describe one stable observed snapshot, not future file immutability.
No path is resolved through a symlink, including ancestor directories. Regular
file hardlinks are rejected; FIFO/device/socket leaves are rejected before reading.
"""

from __future__ import annotations

import hashlib
import os
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import canonical

MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_PACKAGE_BYTES = 256 * 1024 * 1024
MAX_COLLECTION_ITEMS = 512
MAX_JSON_NODES = 32768
MAX_JSON_DEPTH = 64


class InvalidPackage(Exception):
    def __init__(self, message: str, code: str = "INVALID_CANDIDATE"):
        super().__init__(message)
        self.code = code


def safe_relative(value: str) -> str:
    if (not isinstance(value, str) or not value or len(value) > 4096 or
            value.startswith("/") or "\\" in value or
            unicodedata.normalize("NFC", value) != value or
            any(ord(c) < 32 or ord(c) == 127 for c in value) or
            any(p in ("", ".", "..") for p in value.split("/"))):
        raise InvalidPackage(f"unsafe package-relative path: {value!r}")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise InvalidPackage("path is not valid Unicode") from exc
    return value


def _identity(st: os.stat_result) -> tuple[int, ...]:
    return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink,
            st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _bounded_json(value: Any) -> None:
    """Bound schema work before uniqueItems comparisons or recursive validation."""
    pending = [(value, 0)]
    nodes = 0
    while pending:
        node, depth = pending.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise InvalidPackage("JSON exceeds supported node count or nesting depth")
        if isinstance(node, (dict, list)):
            if len(node) > MAX_COLLECTION_ITEMS:
                raise InvalidPackage("JSON collection exceeds supported cardinality")
            children = node.values() if isinstance(node, dict) else node
            pending.extend((child, depth + 1) for child in children)


@dataclass(frozen=True)
class Snapshot:
    path: str
    size: int
    sha256: str
    identity: tuple[int, ...]
    data: bytes | None = None


class PackageReader:
    def __init__(self, root: Path):
        # abspath is lexical, unlike Path.resolve(), so symlink components remain visible.
        self.root = Path(os.path.abspath(os.fspath(root)))
        self.fd = self._open_root()
        self.root_identity = os.fstat(self.fd).st_dev, os.fstat(self.fd).st_ino
        self.snapshots: dict[str, Snapshot] = {}
        self.total_bytes = 0

    def _open_root(self) -> int:
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in self.root.parts[1:]:
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = nxt
            return fd
        except OSError as exc:
            os.close(fd)
            raise InvalidPackage(f"package root must be a real directory without symlink ancestors: {exc.strerror}") from exc

    def close(self) -> None:
        os.close(self.fd)

    def relative(self, path: Path | str) -> str:
        text = os.fspath(path)
        if os.path.isabs(text):
            # Do not normalize away traversal before checking it.
            if ".." in Path(text).parts:
                raise InvalidPackage("absolute package path contains traversal")
            try:
                text = str(Path(text).relative_to(self.root))
            except ValueError as exc:
                raise InvalidPackage("file is outside the package root") from exc
        return safe_relative(text)

    def _open_leaf(self, rel: str) -> int:
        parts = safe_relative(rel).split("/")
        fd = os.dup(self.fd)
        try:
            for part in parts[:-1]:
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = nxt
            # NONBLOCK matters for an attacker-supplied FIFO; reject it with fstat.
            leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            st = os.fstat(leaf)
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                os.close(leaf)
                raise InvalidPackage(f"{rel}: expected a regular file with exactly one hardlink")
            return leaf
        except OSError as exc:
            raise InvalidPackage(f"{rel}: cannot read a regular, non-symlink package file ({exc.strerror})") from exc
        finally:
            os.close(fd)

    def read(self, path: Path | str, *, keep: bool = False,
             limit: int = MAX_ARTIFACT_BYTES) -> Snapshot:
        rel = self.relative(path)
        fd = self._open_leaf(rel)
        try:
            before = os.fstat(fd)
            if before.st_size > limit:
                raise InvalidPackage(f"{rel}: file exceeds {limit}-byte read limit")
            if rel not in self.snapshots and self.total_bytes + before.st_size > MAX_PACKAGE_BYTES:
                raise InvalidPackage("bridge package exceeds total read budget")
            h = hashlib.sha256()
            chunks: list[bytes] = []
            size = 0
            while True:
                chunk = os.read(fd, min(65536, limit + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise InvalidPackage(f"{rel}: file grew beyond read limit", "INPUT_MUTATION")
                h.update(chunk)
                if keep:
                    chunks.append(chunk)
            after = os.fstat(fd)
            if _identity(before) != _identity(after) or size != before.st_size:
                raise InvalidPackage(f"{rel}: file changed while being read", "INPUT_MUTATION")
            snap = Snapshot(rel, size, "sha256:" + h.hexdigest(), _identity(after),
                            b"".join(chunks) if keep else None)
            prior = self.snapshots.get(rel)
            if prior and (prior.identity != snap.identity or prior.sha256 != snap.sha256):
                raise InvalidPackage(f"{rel}: file changed during validation", "INPUT_MUTATION")
            if not prior:
                self.total_bytes += size
            self.snapshots[rel] = snap
            return snap
        finally:
            os.close(fd)

    def json(self, path: Path | str) -> tuple[Any, Snapshot]:
        snap = self.read(path, keep=True, limit=MAX_JSON_BYTES)
        try:
            value = canonical.loads(snap.data)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise InvalidPackage(f"{snap.path}: invalid canonical-domain JSON ({type(exc).__name__})") from exc
        _bounded_json(value)
        return value, snap

    def recheck(self) -> None:
        """Detect path substitution/mutation between earlier reads and this return."""
        root_fd = self._open_root()
        try:
            st = os.fstat(root_fd)
            if (st.st_dev, st.st_ino) != self.root_identity:
                raise InvalidPackage("package root changed during validation", "INPUT_MUTATION")
        finally:
            os.close(root_fd)
        for rel, snap in self.snapshots.items():
            fd = self._open_leaf(rel)
            try:
                if _identity(os.fstat(fd)) != snap.identity:
                    raise InvalidPackage(f"{rel}: file changed before validation completed", "INPUT_MUTATION")
            finally:
                os.close(fd)
