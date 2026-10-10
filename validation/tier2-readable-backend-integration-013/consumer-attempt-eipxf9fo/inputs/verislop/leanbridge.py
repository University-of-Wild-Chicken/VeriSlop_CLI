"""Pinned Lean toolchain access, sandboxed compilation and the trusted kernel tool driver.

The toolchain is resolved from an explicit `lean-toolchain` pin and is never downloaded or
updated during verification; a missing toolchain is an infrastructure failure. Candidate
sources are compiled in the sandbox. The kernel tool runs in a separate process on a staging
directory containing only the candidate module's compiled data, staged by the supervisor.
Module-system artifacts are deterministic bundles of `.olean`, `.olean.server`, and
`.olean.private`; preserving the private part is mandatory for proof replay and audits.
"""

from __future__ import annotations

import json
import base64
import binascii
import copy
import math
import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import canonical, fsutil, sandbox
from .errors import Diagnostic, InfrastructureError

MODULE = "VeriSlopContract"
DEFAULT_TOOLCHAIN = "leanprover/lean4:v4.34.1"
KERNEL_TOOL = Path(__file__).resolve().parent / "lean" / "VeriSlopKernel.lean"
SORRY_WARNING = "declaration uses `sorry`"
# Lean reserves large virtual ranges per worker thread; RLIMIT_AS is only a coarse backstop and
# the heap itself is bounded with Lean's own -M option.
LEAN_AS_HEADROOM_MB = 16384
MODULE_BUNDLE_MAGIC = b"VERISLOP-LEAN-MODULE-BUNDLE-1\n"
MODULE_PARTS = tuple(f"{MODULE}{suffix}" for suffix in (".olean", ".olean.server", ".olean.private"))
MAX_MODULE_PART_BYTES = 64 * 1024 * 1024
MAX_MODULE_BUNDLE_BYTES = 256 * 1024 * 1024
COMPILE_PROCESS_FORMAT = "verislop.lean-compile-process/1"
COMPILE_FILE_SIZE_MB = 1024


def _atomic_stage_write(path: Path, data: bytes) -> None:
    """Replace the directory entry without following a candidate-created destination link."""
    fd, temporary = tempfile.mkstemp(prefix=".verislop-output-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _regular_artifact(path: Path, max_bytes: int) -> bool:
    try:
        info = path.lstat()
        return stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= max_bytes
    except FileNotFoundError:
        return False


def _bundle_module(olean: Path) -> Path:
    """Persist all module data together, with exact member names and content digests."""
    files = []
    for name in MODULE_PARTS:
        path = olean.parent / name
        if not _regular_artifact(path, MAX_MODULE_PART_BYTES):
            raise _infra(f"missing, unsafe, or oversized Lean module part: {name}")
        data = path.read_bytes()
        files.append({"name": name, "sha256": canonical.digest(data),
                      "content_b64": base64.b64encode(data).decode("ascii")})
    blob = MODULE_BUNDLE_MAGIC + canonical.dumps({"format": "verislop.lean-module/1", "module": MODULE, "files": files})
    if len(blob) > MAX_MODULE_BUNDLE_BYTES:
        raise _infra("Lean module artifact exceeds bundle size limit")
    bundle = olean.with_suffix(".vslean")
    _atomic_stage_write(bundle, blob)
    return bundle


def _stage_module(artifact: Path, stage: Path) -> None:
    """Decode a stored module artifact without archive extraction or external paths."""
    if not _regular_artifact(artifact, MAX_MODULE_BUNDLE_BYTES):
        raise _infra("unsafe or oversized Lean module artifact")
    data = artifact.read_bytes()
    if not data.startswith(MODULE_BUNDLE_MAGIC):
        (stage / MODULE_PARTS[0]).write_bytes(data)
        return
    try:
        body = data[len(MODULE_BUNDLE_MAGIC):]
        bundle = canonical.loads(body)
        if (not isinstance(bundle, dict) or set(bundle) != {"format", "module", "files"}
                or bundle["format"] != "verislop.lean-module/1" or bundle["module"] != MODULE
                or canonical.dumps(bundle) != body or not isinstance(bundle["files"], list)
                or len(bundle["files"]) != len(MODULE_PARTS)):
            raise ValueError("invalid module bundle envelope")
        decoded = []
        for row, expected in zip(bundle["files"], MODULE_PARTS):
            if not isinstance(row, dict) or set(row) != {"name", "sha256", "content_b64"} or row["name"] != expected:
                raise ValueError("invalid, reordered, or duplicate module bundle member")
            if not isinstance(row["content_b64"], str) or len(row["content_b64"]) > (MAX_MODULE_PART_BYTES + 2) // 3 * 4:
                raise ValueError("oversized or invalid module bundle member")
            part = base64.b64decode(row["content_b64"], validate=True)
            if len(part) > MAX_MODULE_PART_BYTES or canonical.digest(part) != row["sha256"]:
                raise ValueError("module bundle member digest or size mismatch")
            decoded.append((expected, part))
    except (ValueError, TypeError, KeyError, binascii.Error, canonical.CanonicalJSONError) as exc:
        raise _infra(f"invalid Lean module artifact: {exc}") from None
    for name, part in decoded:
        (stage / name).write_bytes(part)


def kernel_tool_hash() -> str:
    return canonical.digest(KERNEL_TOOL.read_bytes())


def _infra(msg: str) -> InfrastructureError:
    return InfrastructureError(msg, [Diagnostic("VERIFIER_FAILURE", msg, severity="infrastructure")])


@dataclass(frozen=True)
class Toolchain:
    pin: str
    prefix: Path

    @property
    def lean(self) -> Path:
        return self.prefix / "bin" / "lean"

    @property
    def libdir(self) -> Path:
        return self.prefix / "lib" / "lean"

    def identity(self) -> dict[str, str]:
        return _identity(str(self.prefix), self.pin)


@lru_cache(maxsize=None)
def _identity(prefix: str, pin: str) -> dict[str, str]:
    lean = Path(prefix) / "bin" / "lean"
    version = subprocess.run([str(lean), "--version"], capture_output=True, text=True, timeout=60).stdout.strip()
    githash = subprocess.run([str(lean), "--githash"], capture_output=True, text=True, timeout=60).stdout.strip()
    return {
        "pin": pin,
        "version": version,
        "githash": githash,
        "lean_binary_sha256": canonical.digest_file(lean),
    }


def resolve_toolchain(pin: str = DEFAULT_TOOLCHAIN) -> Toolchain:
    pin = pin.strip()
    override = os.environ.get("VERISLOP_LEAN_PREFIX")
    if override:
        prefix = Path(override)
    else:
        elan_home = Path(os.environ.get("ELAN_HOME", Path.home() / ".elan"))
        prefix = elan_home / "toolchains" / pin.replace("/", "--").replace(":", "---")
    if not (prefix / "bin" / "lean").is_file():
        raise _infra(
            f"pinned Lean toolchain {pin} is not installed at {prefix}; VeriSlop never downloads toolchains "
            "during verification (install it with elan beforehand, or set VERISLOP_LEAN_PREFIX)"
        )
    tc = Toolchain(pin, prefix)
    ident = tc.identity()
    expected = pin.split(":")[-1].lstrip("v")
    if expected not in ident["version"]:
        raise _infra(f"toolchain at {prefix} reports {ident['version']!r}, not the pinned {pin}")
    return tc


# ------------------------------------------------------------------------------------------
# toolchain module identity (hash of imported .olean files, cached by size/mtime)
# ------------------------------------------------------------------------------------------

def _cache_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "verislop"
    base.mkdir(parents=True, exist_ok=True)
    return base


def olean_closure_identity(tc: Toolchain, modules: list[dict[str, Any]]) -> tuple[str, list[Diagnostic]]:
    """Bind every loaded toolchain olean data part; third-party dependencies stay forbidden."""
    diags: list[Diagnostic] = []
    cache_path = _cache_dir() / f"olean-hashes-{tc.identity()['githash'][:16]}.json"
    try:
        cache = json.loads(cache_path.read_text()) if cache_path.is_file() else {}
    except (OSError, ValueError):
        cache = {}
    rows = []
    lib = os.path.realpath(tc.libdir)
    changed = False
    for m in modules:
        name = ".".join(str(c) for c in m["name"])
        if name == MODULE:
            continue
        path = m.get("olean") or ""
        real = os.path.realpath(path) if path else ""
        if not real or not real.startswith(lib + os.sep):
            diags.append(Diagnostic("UNDECLARED_DEPENDENCY", f"imported module {name} does not resolve inside the pinned toolchain ({path or 'unresolved'})"))
            continue
        parts = [real]
        if m.get("is_module_system"):
            parts.extend(real + suffix for suffix in (".server", ".private"))
        # Lean's private-level import also opportunistically reads .ir.sig + .ir, although
        # extension/initializer execution is disabled. Bind these loaded toolchain parts too.
        ir_sig = str(Path(real).with_suffix(".ir.sig"))
        if os.path.isfile(ir_sig):
            parts.extend([ir_sig, str(Path(real).with_suffix(".ir"))])
        for part in parts:
            if not os.path.realpath(part).startswith(lib + os.sep) or not os.path.isfile(part):
                diags.append(Diagnostic("UNDECLARED_DEPENDENCY", f"missing or external toolchain module part {part}"))
                continue
            st = os.stat(part)
            key = f"{part}:{st.st_size}:{st.st_mtime_ns}:{st.st_ctime_ns}"
            digest = cache.get(key)
            if digest is None:
                digest = canonical.digest_file(part)
                cache[key] = digest
                changed = True
            rows.append([name, Path(part).name, digest])
    if changed:
        try:
            tmp = cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(cache))
            os.replace(tmp, cache_path)
        except OSError:
            pass
    rows.sort()
    return canonical.digest_json(rows), diags


# ------------------------------------------------------------------------------------------
# compilation
# ------------------------------------------------------------------------------------------

@dataclass
class CompileResult:
    ok: bool
    olean: Path | None
    messages: list[dict[str, Any]]
    errors: list[str]
    sorry_positions: list[dict[str, int]]
    timed_out: bool
    wall_seconds: float
    isolation: dict[str, Any] = field(default_factory=dict)
    raw_stderr: str = ""
    # Optional for compatibility with existing positional and synthetic results. This is
    # attempt-local telemetry, never a deterministic build observation or acceptance rule.
    process_evidence: dict[str, Any] | None = None


def _output_evidence(data: bytes) -> dict[str, Any]:
    """Losslessly retain subprocess output, including non-UTF-8 bytes."""
    return {"byte_count": len(data), "sha256": canonical.digest(data),
            "content_b64": base64.b64encode(data).decode("ascii")}


def _compile_process_evidence(res: sandbox.SandboxResult, *, argv: list[str], working_directory: str,
                              module: str, source: bytes, timeout: float, memory_mb: int,
                              cpu_seconds: int, setup: bytes | None = None) -> dict[str, Any]:
    """Record observations separately from requested limits; do not attribute a failure.

    SandboxResult.argv and returncode describe the launcher, which may be a wrapper.
    In particular, a memory-panic report does not establish which boundary failed.
    Decimal text keeps measured durations compatible with strict canonical JSON.
    """
    elapsed = res.wall_seconds
    measured_elapsed = str(elapsed) if isinstance(elapsed, (int, float)) and math.isfinite(elapsed) else None
    return {
        "format": COMPILE_PROCESS_FORMAT,
        "input": {"module": module, "module_source_sha256": canonical.digest(source),
                  "setup_sha256": canonical.digest(setup) if setup is not None else None},
        "requested_argv": list(argv),
        "launcher_argv": list(res.argv),
        "working_directory": working_directory,
        "returncode": res.returncode,
        "timed_out": res.timed_out,
        "requested_limits": {
            "lean_heap_mb": memory_mb,
            "sandbox_address_space_bytes": (memory_mb + LEAN_AS_HEADROOM_MB) * 1024 * 1024,
            "sandbox_cpu_soft_seconds": cpu_seconds,
            "sandbox_cpu_hard_seconds": cpu_seconds + 5,
            "sandbox_file_size_bytes": COMPILE_FILE_SIZE_MB * 1024 * 1024,
            "sandbox_core_bytes": 0,
            "wall_timeout_seconds": str(timeout),
        },
        "elapsed_seconds": measured_elapsed,
        "sandbox_profile": copy.deepcopy(res.isolation),
        "stdout": _output_evidence(res.stdout),
        "stderr": _output_evidence(res.stderr),
        "reported_stderr_panics": ([{"kind": "out_of_memory", "report": "INTERNAL PANIC: out of memory"}]
                                   if b"INTERNAL PANIC: out of memory" in res.stderr else []),
    }


def compile_process_details(result: CompileResult) -> dict[str, Any]:
    """Detached optional telemetry for diagnostic and observational inventories."""
    return {"availability": "available" if result.process_evidence is not None else "unavailable",
            "record": copy.deepcopy(result.process_evidence)}


def _attach_compile_process_evidence(exc: InfrastructureError, process: dict[str, Any]) -> InfrastructureError:
    """Preserve existing post-invocation infrastructure errors and their observations."""
    for diagnostic in exc.diagnostics:
        diagnostic.details = {**diagnostic.details,
                              "process_evidence": {"availability": "available", "record": copy.deepcopy(process)}}
    return exc


def _messages(res: Any) -> tuple[list[dict[str, Any]], list[str], list[dict[str, int]]]:
    messages: list[dict[str, Any]] = []
    errors: list[str] = []
    sorries: list[dict[str, int]] = []
    for line in res.stdout.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        messages.append(msg)
        text = str(msg.get("data", ""))
        pos = msg.get("pos") or {}
        if msg.get("severity") == "error":
            errors.append(f"{pos.get('line', '?')}:{pos.get('column', '?')}: {text}")
        if SORRY_WARNING in text:
            sorries.append({"line": int(pos.get("line", 0)), "column": int(pos.get("column", 0))})
    return messages, errors, sorries


def compile_module(tc: Toolchain, source: bytes, workdir: Path, *, timeout: float = 300, memory_mb: int = 8192,
                   require_network_isolation: bool = True, require_filesystem_isolation: bool = True) -> CompileResult:
    """Elaborate a candidate module in the sandbox (module name fixed to VeriSlopContract)."""
    workdir.mkdir(parents=True, exist_ok=True)
    if workdir.is_symlink() or not workdir.is_dir():
        raise _infra("Lean compilation requires a regular stage directory")
    original_dir = workdir.resolve(strict=True)
    original_stat = workdir.stat()
    invocation_cwd = str(original_dir)
    _atomic_stage_write(workdir / f"{MODULE}.lean", source)
    argv = [str(tc.lean), "-j4", "--json", f"-M{memory_mb}", "-o", f"{MODULE}.olean", f"{MODULE}.lean"]
    cpu_seconds = max(10, int(timeout) + 5)
    try:
        res = sandbox.run(
            argv,
            workdir, timeout=timeout, memory_mb=memory_mb + LEAN_AS_HEADROOM_MB,
            cpu_seconds=cpu_seconds, fsize_mb=COMPILE_FILE_SIZE_MB,
            require_network_isolation=require_network_isolation,
            env_extra={"PATH": f"{tc.prefix / 'bin'}:/usr/bin:/bin"},
            read_only_paths=[tc.prefix],
            require_filesystem_isolation=require_filesystem_isolation,
        )
    except RuntimeError as exc:
        raise _infra(str(exc)) from None
    process = _compile_process_evidence(res, argv=argv, working_directory=invocation_cwd, module=MODULE, source=source,
                                        timeout=timeout, memory_mb=memory_mb, cpu_seconds=cpu_seconds)
    try:
        current_stat = workdir.lstat()
        same_stage = (stat.S_ISDIR(current_stat.st_mode) and workdir.resolve(strict=True) == original_dir
                      and (current_stat.st_dev, current_stat.st_ino) == (original_stat.st_dev, original_stat.st_ino))
    except (OSError, RuntimeError):
        same_stage = False
    if not same_stage:
        raise _attach_compile_process_evidence(
            _infra("Lean compilation stage identity changed during candidate execution"), process)
    messages, errors, sorries = _messages(res)
    olean = workdir / f"{MODULE}.olean"
    regular_output = _regular_artifact(olean, MAX_MODULE_PART_BYTES)
    ok = res.returncode == 0 and not errors and regular_output and not res.timed_out
    if res.timed_out:
        errors.append(f"elaboration timed out after {timeout}s")
    elif res.returncode != 0 and not errors:
        errors.append(f"lean exited with code {res.returncode}: {res.stderr.decode('utf-8', 'replace')[-2000:]}")
    elif res.returncode == 0 and not regular_output:
        errors.append("compiled Lean artifact is missing, linked, non-regular, or oversized")
    if ok and any((workdir / name).exists() for name in MODULE_PARTS[1:]):
        try:
            olean = _bundle_module(olean)
        except InfrastructureError as exc:
            raise _attach_compile_process_evidence(exc, process)
    return CompileResult(ok, olean if ok else None, messages, errors, sorries, res.timed_out, res.wall_seconds,
                         res.isolation, res.stderr.decode("utf-8", "replace")[-4000:], process)


# ------------------------------------------------------------------------------------------
# kernel tool
# ------------------------------------------------------------------------------------------

def run_kernel_tool(tc: Toolchain, olean: Path, request: dict[str, Any], *, timeout: float = 300,
                    memory_mb: int = 8192, require_network_isolation: bool = True,
                    require_filesystem_isolation: bool = True) -> dict[str, Any]:
    """Run the trusted kernel tool on one raw legacy olean or complete module bundle."""
    with fsutil.temporary_directory(prefix="verislop-kernel-") as tmp:
        stage = Path(tmp) / "stage"
        stage.mkdir()
        _stage_module(olean, stage)
        tool = Path(tmp) / "VeriSlopKernel.lean"
        shutil.copyfile(KERNEL_TOOL, tool)
        req = dict(request)
        req["search_dir"] = str(stage)
        req["module"] = MODULE
        req["sysroot"] = str(tc.prefix)
        (Path(tmp) / "request.json").write_text(json.dumps(req))
        try:
            res = sandbox.run(
                [str(tc.lean), "-j4", f"-M{memory_mb}", "--run", str(tool), "request.json", "response.json"],
                Path(tmp), timeout=timeout, memory_mb=memory_mb + LEAN_AS_HEADROOM_MB,
                require_network_isolation=require_network_isolation,
                env_extra={"PATH": f"{tc.prefix / 'bin'}:/usr/bin:/bin"},
                read_only_paths=[tc.prefix],
                require_filesystem_isolation=require_filesystem_isolation,
            )
        except RuntimeError as exc:
            raise _infra(str(exc)) from None
        if res.timed_out:
            raise _infra(f"kernel tool timed out after {timeout}s")
        out = Path(tmp) / "response.json"
        if res.returncode != 0 or not out.is_file():
            raise _infra(f"kernel tool failed (exit {res.returncode}): {res.stderr.decode('utf-8', 'replace')[-2000:]}")
        try:
            resp = canonical.loads(out.read_bytes())
        except canonical.CanonicalJSONError as exc:
            raise _infra(f"kernel tool produced malformed output: {exc}") from None
        # The staged candidate path is a temporary directory: a declared nondeterministic field.
        for m in resp.get("import", {}).get("modules", []):
            if m.get("name") == [MODULE]:
                m["olean"] = "<staged candidate module>"
        return resp


# ------------------------------------------------------------------------------------------
# named modules against exactly bound dependency artifacts (bridge goals and proofs)
# ------------------------------------------------------------------------------------------

MODULE_SUFFIXES = (".olean", ".olean.server", ".olean.private")


def module_relpath(module: str) -> str:
    parts = module.split(".")
    if not parts or any(not p or not p.replace("_", "a").isalnum() or not p.isascii() for p in parts):
        raise _infra(f"unsupported module name {module!r}")
    return "/".join(parts)


def module_parts(root: Path, module: str) -> dict[str, bytes]:
    """The compiled data parts of `module` below `root` (the .olean part is required)."""
    base = root / module_relpath(module)
    parts: dict[str, bytes] = {}
    for suffix in MODULE_SUFFIXES:
        path = base.parent / (base.name + suffix)
        if _regular_artifact(path, MAX_MODULE_PART_BYTES):
            parts[suffix] = path.read_bytes()
        elif os.path.lexists(path):
            raise _infra(f"unsafe or oversized Lean module part {module}{suffix}")
    if ".olean" not in parts:
        raise _infra(f"compiled Lean module {module} is missing")
    return parts


def write_module_parts(root: Path, module: str, parts: dict[str, bytes]) -> dict[str, str]:
    """Stage module parts below `root`; returns the setup artifact paths in Lean's part order."""
    base = root / module_relpath(module)
    base.parent.mkdir(parents=True, exist_ok=True)
    paths = {}
    for suffix in MODULE_SUFFIXES:
        if suffix in parts:
            target = base.parent / (base.name + suffix)
            _atomic_stage_write(target, parts[suffix])
            paths[suffix] = str(target)
    return paths


def compile_named_module(tc: Toolchain, workdir: Path, module: str, source: bytes,
                         dependencies: dict[str, dict[str, str]], *, read_only: list[Path],
                         timeout: float = 300, memory_mb: int = 8192, require_network_isolation: bool = True,
                         require_filesystem_isolation: bool = True) -> tuple[CompileResult, dict[str, bytes]]:
    """Compile `module` in the sandbox; imports resolve only to the given artifacts or the toolchain.

    `dependencies` maps module names to their staged part paths (from `write_module_parts`).
    The module header is used unchanged; a header import that is neither bound here nor in the
    pinned toolchain fails to elaborate. Returns the result and the produced module parts.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    rel = module_relpath(module)
    source_path = workdir / (rel + ".lean")
    source_path.parent.mkdir(parents=True, exist_ok=True)
    invocation_cwd = str(workdir.resolve())
    _atomic_stage_write(source_path, source)
    arts = {name: [[p[s] for s in MODULE_SUFFIXES if s in p], []] for name, p in sorted(dependencies.items())}
    setup = {"name": module, "isModule": False, "importArts": arts, "dynlibs": [], "plugins": [], "options": {}}
    setup_bytes = json.dumps(setup, sort_keys=True).encode()
    _atomic_stage_write(workdir / "setup.json", setup_bytes)
    argv = [str(tc.lean), "-j4", "--json", f"-M{memory_mb}", "--setup=setup.json", "-o", rel + ".olean", rel + ".lean"]
    cpu_seconds = max(10, int(timeout) + 5)
    try:
        res = sandbox.run(
            argv,
            workdir, timeout=timeout, memory_mb=memory_mb + LEAN_AS_HEADROOM_MB,
            cpu_seconds=cpu_seconds, fsize_mb=COMPILE_FILE_SIZE_MB,
            require_network_isolation=require_network_isolation,
            env_extra={"PATH": f"{tc.prefix / 'bin'}:/usr/bin:/bin"},
            read_only_paths=[tc.prefix, *read_only],
            require_filesystem_isolation=require_filesystem_isolation,
        )
    except RuntimeError as exc:
        raise _infra(str(exc)) from None
    process = _compile_process_evidence(res, argv=argv, working_directory=invocation_cwd, module=module, source=source,
                                        timeout=timeout, memory_mb=memory_mb, cpu_seconds=cpu_seconds, setup=setup_bytes)
    messages, errors, sorries = _messages(res)
    olean = workdir / (rel + ".olean")
    ok = res.returncode == 0 and not errors and not res.timed_out and _regular_artifact(olean, MAX_MODULE_PART_BYTES)
    if res.timed_out:
        errors.append(f"elaboration timed out after {timeout}s")
    elif res.returncode != 0 and not errors:
        errors.append(f"lean exited with code {res.returncode}: {res.stderr.decode('utf-8', 'replace')[-2000:]}")
    elif res.returncode == 0 and not ok and not errors:
        errors.append("compiled Lean artifact is missing, linked, non-regular, or oversized")
    try:
        parts = module_parts(workdir, module) if ok else {}
    except InfrastructureError as exc:
        raise _attach_compile_process_evidence(exc, process)
    result = CompileResult(ok, olean if ok else None, messages, errors, sorries, res.timed_out, res.wall_seconds,
                           res.isolation, res.stderr.decode("utf-8", "replace")[-4000:], process)
    return result, parts


def run_kernel_tool_modules(tc: Toolchain, modules: dict[str, dict[str, bytes]], root: str, request: dict[str, Any], *,
                            timeout: float = 300, memory_mb: int = 8192, require_network_isolation: bool = True,
                            require_filesystem_isolation: bool = True) -> dict[str, Any]:
    """Replay a set of staged modules (library, contract, goal, proof) in the trusted kernel tool.

    Only the given module parts are staged; every other import must resolve to the toolchain.
    The response's staged olean paths are rewritten to `<staged module>` markers.
    """
    with fsutil.temporary_directory(prefix="verislop-kernel-") as tmp:
        stage = Path(tmp) / "stage"
        stage.mkdir()
        for name, parts in sorted(modules.items()):
            write_module_parts(stage, name, parts)
        tool = Path(tmp) / "VeriSlopKernel.lean"
        shutil.copyfile(KERNEL_TOOL, tool)
        req = dict(request)
        req.update({"search_dir": str(stage), "module": root, "sysroot": str(tc.prefix),
                    "replay_modules": sorted(modules)})
        (Path(tmp) / "request.json").write_text(json.dumps(req))
        try:
            res = sandbox.run(
                [str(tc.lean), "-j4", f"-M{memory_mb}", "--run", str(tool), "request.json", "response.json"],
                Path(tmp), timeout=timeout, memory_mb=memory_mb + LEAN_AS_HEADROOM_MB,
                require_network_isolation=require_network_isolation,
                env_extra={"PATH": f"{tc.prefix / 'bin'}:/usr/bin:/bin"},
                read_only_paths=[tc.prefix],
                require_filesystem_isolation=require_filesystem_isolation,
            )
        except RuntimeError as exc:
            raise _infra(str(exc)) from None
        if res.timed_out:
            raise _infra(f"kernel tool timed out after {timeout}s")
        out = Path(tmp) / "response.json"
        if res.returncode != 0 or not out.is_file():
            raise _infra(f"kernel tool failed (exit {res.returncode}): {res.stderr.decode('utf-8', 'replace')[-2000:]}")
        try:
            resp = canonical.loads(out.read_bytes())
        except canonical.CanonicalJSONError as exc:
            raise _infra(f"kernel tool produced malformed output: {exc}") from None
        prefix = os.path.realpath(stage) + os.sep
        for m in resp.get("import", {}).get("modules", []):
            path = m.get("olean") or ""
            if path and os.path.realpath(path).startswith(prefix):
                m["olean"] = "<staged module>"
                m["staged"] = True
        return resp
