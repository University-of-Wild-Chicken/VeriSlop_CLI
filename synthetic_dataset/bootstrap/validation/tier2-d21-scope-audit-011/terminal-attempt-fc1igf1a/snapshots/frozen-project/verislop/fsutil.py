"""Filesystem discipline: atomic/write-once writes, manifests with fixed path rules, run locks.

Manifest rules (specification §§10.1, 12): paths are relative POSIX paths of regular files,
sorted by their UTF-8 bytes; symlinks, absolute or escaping paths, non-UTF-8 names, and
case-insensitive collisions are rejected; bytes are hashed exactly as stored (no newline
normalisation). Hash fields never contain their own final value.
"""

from __future__ import annotations

import fcntl
import os
import shutil
import stat
import tempfile
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

from . import canonical
from .errors import blocked, UsageError, Diagnostic

MANIFEST_FORMAT = "verislop.manifest/0.1"


def atomic_write(path: Path, data: bytes, readonly: bool = False) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if readonly:
            os.chmod(tmp, 0o444)
        if path.exists() and not os.access(path, os.W_OK):
            os.chmod(path, 0o644)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_once(path: Path, data: bytes) -> None:
    """Write an immutable artifact. Rewriting identical bytes is a no-op; different bytes fail."""
    path = Path(path)
    if path.exists():
        if path.read_bytes() == data:
            return
        raise blocked(
            "INPUT_MUTATION",
            f"immutable artifact {path} already exists with different content",
        )
    atomic_write(path, data, readonly=True)


def write_json(path: Path, obj: object, pretty: bool = False, once: bool = False) -> bytes:
    data = canonical.dumps_pretty(obj) if pretty else canonical.dumps(obj)
    if once:
        write_once(path, data)
    else:
        atomic_write(path, data)
    return data


def make_readonly_tree(root: Path) -> None:
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            p = os.path.join(dirpath, name)
            os.chmod(p, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def make_writable_tree(root: Path) -> None:
    for dirpath, _dirnames, filenames in os.walk(root):
        os.chmod(dirpath, 0o755)
        for name in filenames:
            os.chmod(os.path.join(dirpath, name), 0o644)


def remove_tree(root: Path) -> None:
    """Remove a staged tree without chmodding or following candidate-created links.

    Read-only files can be unlinked from writable directories. Recursively changing
    their permissions first would modify outside files through symlinks or hardlinks.
    Linux's fd-based rmtree also protects traversal against symlink substitution.
    """
    root = Path(root)
    if root.is_symlink():
        root.unlink()
    elif root.exists():
        if not shutil.rmtree.avoids_symlink_attacks:
            raise RuntimeError("safe staged cleanup requires fd-based shutil.rmtree")
        shutil.rmtree(root)


@contextmanager
def temporary_directory(*, prefix: str = "verislop-", suffix: str = "", dir: str | Path | None = None) -> Iterator[str]:
    """A candidate stage whose cleanup never follows links to repair permissions.

    Some Python TemporaryDirectory implementations chmod failed unlink targets,
    including symlinks. Fail cleanup safely on hostile directory permissions instead.
    """
    root = tempfile.mkdtemp(prefix=prefix, suffix=suffix, dir=dir)
    try:
        yield root
    finally:
        remove_tree(Path(root))


def check_relpath(rel: str) -> str:
    """Validate a manifest-relative path; return its canonical POSIX form."""
    if not rel or rel.startswith("/") or "\\" in rel:
        raise UsageError(f"invalid manifest path {rel!r}")
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise UsageError(f"ambiguous or escaping path {rel!r}")
    if unicodedata.normalize("NFC", rel) != rel:
        raise UsageError(f"path is not NFC-normalised: {rel!r}")
    return rel


def inside(root: Path, path: Path) -> bool:
    try:
        Path(os.path.realpath(path)).relative_to(os.path.realpath(root))
        return True
    except ValueError:
        return False


def list_files(root: Path, exclude: Iterable[str] = ()) -> list[str]:
    """All regular files under root as sorted relative POSIX paths; rejects symlinks."""
    root = Path(root)
    excluded = set(exclude)
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root)
        for d in list(dirnames):
            full = os.path.join(dirpath, d)
            rel = d if rel_dir == "." else f"{rel_dir}/{d}"
            if os.path.islink(full):
                raise blocked("INPUT_MUTATION", f"symlink {rel!r} is not permitted in a manifest")
            if rel in excluded or d == "__pycache__":
                dirnames.remove(d)
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = name if rel_dir == "." else f"{rel_dir}/{name}"
            if rel in excluded:
                continue
            st = os.lstat(full)
            if stat.S_ISLNK(st.st_mode):
                raise blocked("INPUT_MUTATION", f"symlink {rel!r} is not permitted in a manifest")
            if not stat.S_ISREG(st.st_mode):
                raise blocked("INPUT_MUTATION", f"non-regular file {rel!r} in manifest root")
            try:
                rel.encode("utf-8")
            except UnicodeEncodeError:
                raise blocked("INPUT_MUTATION", f"non-UTF-8 file name under {root}") from None
            out.append(check_relpath(rel))
    out.sort(key=lambda s: s.encode("utf-8"))
    lowered: dict[str, str] = {}
    for rel in out:
        key = rel.casefold()
        if key in lowered:
            raise blocked("INPUT_MUTATION", f"case-insensitive path collision: {lowered[key]!r} vs {rel!r}")
        lowered[key] = rel
    return out


def manifest_for(entries: dict[str, Path]) -> dict:
    """Manifest over explicitly named files {manifest_path: filesystem_path}."""
    rows = []
    for rel in sorted(entries, key=lambda s: s.encode("utf-8")):
        check_relpath(rel)
        p = Path(entries[rel])
        if p.is_symlink() or not p.is_file():
            raise blocked("INPUT_MUTATION", f"manifest input {rel!r} is missing or not a regular file")
        data = p.read_bytes()
        rows.append({"path": rel, "sha256": canonical.digest(data), "size": len(data)})
    return {
        "format": MANIFEST_FORMAT,
        "newline_policy": "bytes-exact",
        "symlinks": "rejected",
        "case_collisions": "rejected",
        "entries": rows,
    }


def manifest_tree(root: Path, prefix: str = "", exclude: Iterable[str] = ()) -> dict:
    files = list_files(root, exclude)
    return manifest_for({(f"{prefix}/{f}" if prefix else f): Path(root) / f for f in files})


def manifest_root(manifest: dict) -> str:
    return canonical.digest_json(manifest)


def merge_manifests(*manifests: dict) -> dict:
    rows: dict[str, dict] = {}
    for m in manifests:
        for row in m["entries"]:
            if row["path"] in rows and rows[row["path"]] != row:
                raise blocked("INPUT_MUTATION", f"conflicting manifest entry {row['path']}")
            rows[row["path"]] = row
    return {
        "format": MANIFEST_FORMAT,
        "newline_policy": "bytes-exact",
        "symlinks": "rejected",
        "case_collisions": "rejected",
        "entries": [rows[k] for k in sorted(rows, key=lambda s: s.encode("utf-8"))],
    }


def verify_manifest(root: Path, manifest: dict) -> list[Diagnostic]:
    """Recompute the hashes of every manifest entry under root."""
    problems: list[Diagnostic] = []
    for row in manifest["entries"]:
        p = Path(root) / row["path"]
        if p.is_symlink() or not p.is_file():
            problems.append(Diagnostic("INPUT_MUTATION", f"frozen input {row['path']} is missing"))
            continue
        if canonical.digest(p.read_bytes()) != row["sha256"]:
            problems.append(Diagnostic("INPUT_MUTATION", f"frozen input {row['path']} changed after freeze"))
    return problems


def copy_files(src_root: Path, dst_root: Path, files: Iterable[str]) -> None:
    for rel in files:
        check_relpath(rel)
        src = Path(src_root) / rel
        dst = Path(dst_root) / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_symlink():
            raise blocked("INPUT_MUTATION", f"symlink {rel!r} cannot be staged")
        shutil.copyfile(src, dst)


@contextmanager
def open_directory(path: Path, *, create: bool = False) -> Iterator[int]:
    """Open a directory through anchored, non-following descriptor traversal."""
    absolute = Path(os.path.abspath(path))
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in absolute.parts[1:]:
            if create:
                try:
                    os.mkdir(part, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                            dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    except OSError as exc:
        raise blocked("INPUT_MUTATION", f"cannot safely open directory {absolute}: {exc.strerror}") from None
    finally:
        os.close(fd)


def open_regular_file(path: Path, flags: int, *, create_parents: bool = False) -> int:
    """Open a single-link regular file without following any path component.

    Callers receive an owned descriptor. O_TRUNC is prohibited so validation always
    precedes changes to existing bytes.
    """
    if flags & os.O_TRUNC:
        raise ValueError("validate files before truncating them")
    path = Path(path)
    with open_directory(path.parent, create=create_parents) as parent_fd:
        try:
            fd = os.open(path.name, flags | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                         0o600, dir_fd=parent_fd)
        except OSError as exc:
            raise blocked("INPUT_MUTATION", f"cannot safely open file {path}: {exc.strerror}") from None
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            os.close(fd)
            raise blocked("INPUT_MUTATION", f"file {path} must be a regular file with exactly one link")
        return fd


@contextmanager
def package_lock(pkg: Path) -> Iterator[None]:
    """Exclusive single-writer lock; reject unsafe paths before writing lock bytes."""
    pkg = Path(pkg)
    lock_path = pkg / ".verislop.lock"
    fd = open_regular_file(lock_path, os.O_RDWR | os.O_CREAT, create_parents=True)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise UsageError(
                f"run package {pkg} is locked by another writer",
                [Diagnostic("RUN_LOCKED", f"concurrent writer holds {lock_path}", severity="infrastructure")],
            ) from None
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode("ascii"))
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
