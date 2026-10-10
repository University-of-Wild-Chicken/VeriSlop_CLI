"""Linux no-follow, no-clobber publication for supervisor-produced bridge bundles."""

from __future__ import annotations

import ctypes
import errno
import os
import re
import secrets
import stat
from pathlib import Path

from .. import canonical
from .manifest import InvalidPackage, PackageReader, safe_relative


def _directory(parent: int, name: str, *, create: bool = False) -> int:
    if create:
        try:
            os.mkdir(name, 0o755, dir_fd=parent)
        except FileExistsError:
            pass
    try:
        return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    except OSError as exc:
        raise InvalidPackage(f"unsafe publication directory {name!r}") from exc


def _write(root_fd: int, relative: str, data: bytes) -> None:
    parts = safe_relative(relative).split("/")
    fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            nxt = _directory(fd, part, create=True)
            os.close(fd)
            fd = nxt
        out = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        try:
            with os.fdopen(out, "wb", closefd=False) as handle:
                handle.write(data)
                handle.flush()
                os.fchmod(out, 0o444)
                os.fsync(out)
        finally:
            os.close(out)
    finally:
        os.close(fd)


def _rename_noreplace(parent: int, source: str, destination: str) -> None:
    # os.rename permits replacing an empty directory. Linux renameat2 makes the
    # absence check atomic, including against concurrent publication attempts.
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise OSError(errno.ENOSYS, "atomic no-clobber directory publication is unavailable")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(parent, os.fsencode(source), parent, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        if error in (errno.EEXIST, errno.ENOTEMPTY):
            raise InvalidPackage("bridge attempt already exists; choose a fresh bridge_id", "INPUT_MUTATION")
        raise OSError(error, os.strerror(error))


def _remove_tree(parent: int, name: str) -> None:
    """Anchored cleanup for Python versions without shutil.rmtree(dir_fd=...)."""
    info = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode):
        os.unlink(name, dir_fd=parent)
        return
    fd = _directory(parent, name)
    try:
        for child in os.listdir(fd):
            _remove_tree(fd, child)
    finally:
        os.close(fd)
    os.rmdir(name, dir_fd=parent)


def publish(root: Path, bridge_id: str, files: dict[str, bytes]) -> Path:
    """Atomically install a complete fresh bundle without following destination links."""
    if not isinstance(bridge_id, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", bridge_id) is None:
        raise InvalidPackage("publication requires a safe single-component bridge ID")
    reader = PackageReader(root)
    parent = stage_fd = None
    stage_name = ".preparing-" + secrets.token_hex(12)
    published = False
    created = False
    try:
        parent = _directory(reader.fd, "bridges", create=True)
        os.mkdir(stage_name, 0o700, dir_fd=parent)
        created = True
        stage_fd = _directory(parent, stage_name)
        for rel, data in sorted(files.items()):
            _write(stage_fd, rel, data)
        os.fsync(stage_fd)
        reader.recheck()
        current = _directory(reader.fd, "bridges")
        try:
            before, after = os.fstat(parent), os.fstat(current)
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                raise InvalidPackage("bridge publication parent changed", "INPUT_MUTATION")
        finally:
            os.close(current)
        _rename_noreplace(parent, stage_name, bridge_id)
        published = True
        os.fsync(parent)
        return reader.root / "bridges" / bridge_id
    finally:
        if stage_fd is not None:
            os.close(stage_fd)
        if parent is not None:
            if created and not published:
                # Delete only the temporary name anchored to the same open parent.
                # No chmod and no path traversal into candidate-created links.
                try:
                    _remove_tree(parent, stage_name)
                except FileNotFoundError:
                    pass
            os.close(parent)
        reader.close()


def publish_into(root: Path, parents: list[str], name: str, files: dict[str, bytes]) -> None:
    """Atomically add a fresh directory `parents/name` (created no-follow) to an existing package.

    Used for supervisor outputs added to an already published bundle, such as registered
    semantic acceptances. Existing destinations are never replaced.
    """
    for part in [*parents, name]:
        if not isinstance(part, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", part) is None:
            raise InvalidPackage("publication requires safe single-component directory names")
    reader = PackageReader(root)
    fds: list[int] = []
    stage_name = ".publishing-" + secrets.token_hex(12)
    created = published = False
    try:
        fd = reader.fd
        for i, part in enumerate(parents):
            # Only the last parent may be created; the bundle path itself must already exist.
            fd = _directory(fd, part, create=i == len(parents) - 1)
            fds.append(fd)
        parent = fd
        os.mkdir(stage_name, 0o700, dir_fd=parent)
        created = True
        stage_fd = _directory(parent, stage_name)
        try:
            for rel, data in sorted(files.items()):
                _write(stage_fd, rel, data)
            os.fsync(stage_fd)
        finally:
            os.close(stage_fd)
        reader.recheck()
        _rename_noreplace(parent, stage_name, name)
        published = True
        os.fsync(parent)
    finally:
        if created and not published:
            try:
                _remove_tree(parent, stage_name)
            except FileNotFoundError:
                pass
        for fd in reversed(fds):
            os.close(fd)
        reader.close()


def record_preparation(root: Path, bridge_id: str, run_id: str) -> None:
    """Update bookkeeping atomically without chmodding/following an existing link."""
    if not isinstance(bridge_id, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", bridge_id) is None:
        raise InvalidPackage("bookkeeping requires a safe single-component bridge ID")
    reader = PackageReader(root)
    temporary = ".package-" + secrets.token_hex(12)
    created = False
    try:
        meta, _ = reader.json("package.json")
        if not isinstance(meta, dict) or meta.get("run_id") != run_id:
            raise InvalidPackage("run identity changed during bridge preparation", "INPUT_MUTATION")
        prior = meta.get("bridge_preparations", {})
        if not isinstance(prior, dict):
            raise InvalidPackage("invalid bridge preparation bookkeeping")
        relative = f"bridges/{bridge_id}"
        if bridge_id in prior and prior[bridge_id] != relative:
            raise InvalidPackage("bridge preparation identity already has different bookkeeping", "INPUT_MUTATION")
        meta["bridge_preparations"] = {**prior, bridge_id: relative}
        _write(reader.fd, temporary, canonical.dumps(meta))
        created = True
        reader.recheck()
        os.replace(temporary, "package.json", src_dir_fd=reader.fd, dst_dir_fd=reader.fd)
        created = False
        os.fsync(reader.fd)
    finally:
        if created:
            os.unlink(temporary, dir_fd=reader.fd)
        reader.close()
