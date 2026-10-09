"""Linux containment shared by candidate builds and streaming target execution.

Bubblewrap exposes read-only system runtimes and explicit toolchain grants, a writable
stage, and private /proc and /dev. This is not a VM or a complete syscall/resource sandbox.
Required containment fails closed; returned profiles describe the selected launcher.
"""

from __future__ import annotations

import os
import resource
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable

SYSTEM_READ_ONLY = ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc/ld.so.cache")
ENV_EXTRA_ALLOWLIST = frozenset({"PATH"})


@dataclass
class SandboxResult:
    argv: list[str]
    returncode: int
    stdout: bytes
    stderr: bytes
    timed_out: bool
    wall_seconds: float
    isolation: dict[str, object] = field(default_factory=dict)


def _environment(cwd: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    if set(extra or {}) - ENV_EXTRA_ALLOWLIST:
        raise RuntimeError("sandbox environment overrides are limited to PATH")
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(cwd), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        "TMPDIR": str(cwd), "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1",
    }
    env.update(extra or {})
    return env


def _bwrap_argv(bwrap: str, argv: list[str], cwd: Path,
                read_only_paths: Iterable[Path], isolated_net: bool) -> list[str]:
    full = [bwrap, "--unshare-user", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
            "--die-with-parent", "--new-session", "--cap-drop", "ALL"]
    if isolated_net:
        full.append("--unshare-net")
    for raw in SYSTEM_READ_ONLY:
        if Path(raw).exists():
            full.extend(["--ro-bind", raw, raw])
    # Private proc belongs to the private PID namespace. No host /proc, /dev, /tmp,
    # /run, /etc or home-directory bind; no parent process or inherited directory FDs.
    full.extend(["--proc", "/proc", "--dev", "/dev", "--bind", str(cwd), str(cwd)])
    for path in read_only_paths:
        full.extend(["--ro-bind", str(path), str(path)])
    full.extend(["--remount-ro", "/", "--chdir", str(cwd), "--", *argv])
    return full


@lru_cache(maxsize=1)
def filesystem_isolation_available() -> bool:
    """Probe actual namespaces, hidden host-file access, and writable stage behavior."""
    bwrap = shutil.which("bwrap")
    if not bwrap:
        return False
    try:
        with tempfile.TemporaryDirectory(prefix="verislop-sandbox-probe-") as tmp:
            root = Path(tmp).resolve()
            stage = root / "stage"
            stage.mkdir()
            hidden = root / "outside"
            hidden.write_text("probe")
            script = '[ ! -r "$1" ] && [ ! -e /proc/$2 ] && : > "$3"'
            args = ["/bin/sh", "-c", script, "probe", str(hidden), str(os.getpid()), str(stage / "ok")]
            result = subprocess.run(_bwrap_argv(bwrap, args, stage, (), False),
                                    cwd=stage, env=_environment(stage), capture_output=True,
                                    timeout=10, close_fds=True)
            return result.returncode == 0 and (stage / "ok").is_file()
    except (OSError, subprocess.SubprocessError):
        return False


@lru_cache(maxsize=1)
def network_isolation_available() -> bool:
    unshare = shutil.which("unshare")
    if not unshare:
        return False
    try:
        r = subprocess.run([unshare, "-rn", "--", "true"], capture_output=True,
                           env={"PATH": "/usr/bin:/bin"}, timeout=10, close_fds=True)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def isolation_profile() -> dict[str, object]:
    """Available default profile; popen returns the actual selected per-process profile."""
    fs = filesystem_isolation_available()
    return {
        "staged_working_directory": True,
        "scrubbed_environment": True,
        "resource_limits": ["RLIMIT_AS", "RLIMIT_CPU", "RLIMIT_FSIZE", "RLIMIT_CORE"],
        "process_group_kill_on_timeout": True,
        "network_namespace": network_isolation_available(),
        "filesystem_read_isolation": fs,
        "filesystem_write_isolation": fs,
        "filesystem_backend": "bubblewrap" if fs else None,
        "pid_namespace": fs,
        "ipc_namespace": fs,
        "private_proc": fs,
        "inherited_file_descriptors": "stdin/stdout/stderr only",
        "note": ("Mount/PID/IPC containment; system runtimes and explicit read-only grants remain readable. "
                 "Kernel, bubblewrap and runtime contents are trusted; no seccomp or aggregate cgroup limits."
                 if fs else "No filesystem containment: candidate can access host files permitted to this user."),
    }


def _limits(memory_mb: int, cpu_seconds: int, fsize_mb: int):
    def apply() -> None:
        os.setsid()
        mem = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 5))
        fs = fsize_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_FSIZE, (fs, fs))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return apply


def _validate_stage(cwd: Path) -> None:
    if not cwd.is_dir() or cwd == Path("/"):
        raise RuntimeError("sandbox requires a dedicated existing stage directory")
    # Hardlinked staged files alias outside inodes even across mount namespaces.
    # Staging must copy bytes. Symlinks resolve inside the private filesystem.
    for root, dirs, files in os.walk(cwd, followlinks=False):
        for name in dirs + files:
            info = (Path(root) / name).lstat()
            if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                raise RuntimeError("sandbox stage contains a hardlinked file")
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)):
                raise RuntimeError("sandbox stage contains an unsupported special file")


def popen(
    argv: list[str], cwd: Path, *, memory_mb: int = 8192, cpu_seconds: int = 300,
    fsize_mb: int = 1024, network: bool = False, require_network_isolation: bool = False,
    require_filesystem_isolation: bool = True, read_only_paths: Iterable[Path] = (),
    env_extra: dict[str, str] | None = None, stdin: int = subprocess.DEVNULL,
) -> tuple[subprocess.Popen, dict[str, object]]:
    """Shared contained launcher for bounded jobs and JSONL streaming clients."""
    cwd = Path(cwd).resolve(strict=True)
    _validate_stage(cwd)
    env = _environment(cwd, env_extra)
    # Keep lexical destinations for runtime symlinks (e.g. libcrypto.so aliases),
    # while validating their resolved source. The supervisor alone supplies grants.
    grants = sorted({Path(os.path.abspath(p)) for p in read_only_paths}, key=str)
    for grant in grants:
        real = grant.resolve(strict=True)
        if real == cwd or real in cwd.parents:
            raise RuntimeError("read-only grant must not cover the writable stage or its ancestors")
        if not (grant.is_file() or grant.is_dir()):
            raise RuntimeError("read-only grant is not a regular file or directory")
    fs = filesystem_isolation_available()
    if require_filesystem_isolation and not fs:
        raise RuntimeError("filesystem isolation required but bubblewrap/user namespaces are unavailable")
    isolated_net = not network and network_isolation_available()
    if not network and require_network_isolation and not isolated_net:
        raise RuntimeError("network isolation required by policy but unavailable on this host")
    full = list(argv)
    if fs:
        bwrap = shutil.which("bwrap")
        if not bwrap:
            raise RuntimeError("filesystem isolation backend disappeared before launch")
        full = _bwrap_argv(bwrap, full, cwd, grants, isolated_net)
    elif isolated_net:
        full = ["unshare", "-rn", "--", *full]
    profile = isolation_profile()
    profile["network_namespace"] = isolated_net
    profile["read_only_paths"] = (
        [p for p in SYSTEM_READ_ONLY if Path(p).exists()] + [
            "<stage>/" + str(p.relative_to(cwd)) if p.is_relative_to(cwd) else str(p) for p in grants
        ] if fs else []
    )
    profile["writable_host_paths"] = ["<stage>"] if fs else ["<host-user-permissions>"]
    proc = subprocess.Popen(full, cwd=str(cwd), env=env, stdin=stdin,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
                            preexec_fn=_limits(memory_mb, cpu_seconds, fsize_mb))
    return proc, profile


def kill_process_group(proc: subprocess.Popen) -> None:
    """Kill the launcher and namespace init, tearing down namespace descendants."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run(
    argv: list[str], cwd: Path, *, timeout: float, memory_mb: int = 8192,
    cpu_seconds: int | None = None, fsize_mb: int = 1024, network: bool = False,
    require_network_isolation: bool = False, require_filesystem_isolation: bool = True,
    read_only_paths: Iterable[Path] = (), env_extra: dict[str, str] | None = None,
    stdin: bytes | None = None,
) -> SandboxResult:
    start = time.monotonic()
    proc, profile = popen(argv, cwd, memory_mb=memory_mb,
                          cpu_seconds=int(cpu_seconds or max(10, int(timeout) + 5)), fsize_mb=fsize_mb,
                          network=network, require_network_isolation=require_network_isolation,
                          require_filesystem_isolation=require_filesystem_isolation,
                          read_only_paths=read_only_paths, env_extra=env_extra,
                          stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL)
    timed_out = False
    try:
        out, err = proc.communicate(input=stdin, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_process_group(proc)
        out, err = proc.communicate()
    except BaseException:
        kill_process_group(proc)
        proc.wait()
        raise
    return SandboxResult(list(proc.args), proc.returncode, out, err, timed_out,
                         time.monotonic() - start, profile)
