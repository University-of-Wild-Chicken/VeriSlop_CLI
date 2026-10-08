"""Python target adapter: python-v0_1 serialization profile, inventory and harness client.

python-v0_1 (fixed, not proved):
  Nat            <-> int, non-negative, not bool (arbitrary precision, so no overflow edge)
  Bool           <-> bool
  Unit           <-> None
  Enum E         <-> str naming the constructor
  Result(E, A)   <-> ("ok", a) | ("error", e)   (a 2-tuple; lists are rejected)
"""

from __future__ import annotations

import ast
import json
import os
import select
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import canonical, dsl, fsutil, sandbox

PROFILE_ID = "python-v0_1"
HARNESS = Path(__file__).resolve().parent / "python_harness.py"
PROFILE_DOC = {
    "id": PROFILE_ID,
    "Nat": "int >= 0 (bool rejected); arbitrary precision",
    "Bool": "bool",
    "Unit": "None",
    "Enum": "str constructor name",
    "Result": "('ok', value) | ('error', value) as a 2-tuple",
    "errors": "an exception raised by the target is a contract violation for total functions",
}


def python_identity() -> dict[str, str]:
    return {"python": sys.version.split()[0], "executable": sys.executable,
            "executable_sha256": canonical.digest_file(os.path.realpath(sys.executable))}


def python_runtime_paths() -> list[Path]:
    """Explicit read-only runtime grants for Python installed outside system directories.

    Grant the binary, standard library, and runtime shared libraries, not the user's home
    or the entire environment prefix (which can contain unrelated environments/config).
    The granted runtime contents remain trusted/readable. -S disables site startup hooks.
    """
    paths = {Path(sys.executable).resolve()}
    for key in ("stdlib", "platstdlib"):
        value = sysconfig.get_path(key)
        if value:
            paths.add(Path(value).resolve())
    for prefix in {Path(sys.base_prefix), Path(sys.prefix)}:
        lib = prefix / "lib"
        if lib.is_dir():
            paths.update(p.absolute() for p in lib.glob("*.so*") if p.is_file())
    system = [Path(p).resolve() for p in sandbox.SYSTEM_READ_ONLY if Path(p).is_dir()]
    return sorted((p for p in paths if p.exists() and not any(p.is_relative_to(root) for root in system)), key=str)


# ------------------------------------------------------------------------------------------
# inventory
# ------------------------------------------------------------------------------------------

@dataclass
class Inventory:
    files: dict[str, str]
    objects: list[dict[str, Any]]
    errors: list[str] = field(default_factory=list)

    def find(self, file: str, qualname: str) -> dict[str, Any] | None:
        for o in self.objects:
            if o["file"] == file and o["qualname"] == qualname:
                return o
        return None


def inventory(impl_dir: Path) -> Inventory:
    files = {rel: canonical.digest((impl_dir / rel).read_bytes()) for rel in fsutil.list_files(impl_dir)}
    objects: list[dict[str, Any]] = []
    errors: list[str] = []
    for rel in sorted(files):
        if not rel.endswith(".py"):
            continue
        data = (impl_dir / rel).read_bytes()
        try:
            tree = ast.parse(data, filename=rel)
        except SyntaxError as exc:
            errors.append(f"{rel}:{exc.lineno}: {exc.msg}")
            continue
        lines = data.decode("utf-8").splitlines(keepends=True)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = (node.decorator_list[0].lineno if getattr(node, "decorator_list", None) else node.lineno)
                seg = "".join(lines[start - 1 : node.end_lineno]).encode("utf-8")
                obj: dict[str, Any] = {
                    "file": rel, "qualname": node.name,
                    "kind": "class" if isinstance(node, ast.ClassDef) else ("async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"),
                    "lineno": start, "end_lineno": node.end_lineno,
                    "source_hash": canonical.digest(seg), "public": not node.name.startswith("_"),
                    "decorated": bool(getattr(node, "decorator_list", [])),
                }
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    a = node.args
                    obj["positional"] = len(a.posonlyargs) + len(a.args)
                    obj["defaults"] = len(a.defaults)
                    obj["varargs"] = a.vararg is not None or a.kwarg is not None
                    obj["kwonly_required"] = sum(1 for d in a.kw_defaults if d is None)
                objects.append(obj)
    return Inventory(files, objects, errors)


# ------------------------------------------------------------------------------------------
# value transport
# ------------------------------------------------------------------------------------------

def encode_arg(v: Any, sort: Any) -> dict[str, Any]:
    if sort == "Nat":
        return {"int": str(v)}
    if sort == "Bool":
        return {"bool": v}
    if sort == "Unit":
        return {"none": None}
    if "enum" in sort:
        return {"str": v[2]}
    side, inner = v
    return {"tuple": [{"str": side}, encode_arg(inner, sort["result"][side])]}


def decode_result(j: dict[str, Any], sort: Any, profile: dsl.Profile) -> Any:
    """Strict python-v0_1 decoding; raises ValueError for anything outside the profile."""
    if sort == "Nat":
        if "int" in j and int(j["int"]) >= 0:
            return int(j["int"])
        raise ValueError(f"expected a non-negative int, got {j}")
    if sort == "Bool":
        if "bool" in j:
            return j["bool"]
        raise ValueError(f"expected a bool, got {j}")
    if sort == "Unit":
        if "none" in j:
            return dsl.UNIT
        raise ValueError(f"expected None, got {j}")
    if "enum" in sort:
        ctors = profile.enums[sort["enum"]]["constructors"]
        if "str" in j and j["str"] in ctors:
            return dsl.enum_v(sort["enum"], j["str"])
        raise ValueError(f"expected one of {ctors}, got {j}")
    t = j.get("tuple")
    if isinstance(t, list) and len(t) == 2 and t[0].get("str") in ("ok", "error"):
        side = t[0]["str"]
        return (side, decode_result(t[1], sort["result"][side], profile))
    raise ValueError(f"expected ('ok', v) or ('error', e), got {j}")


# ------------------------------------------------------------------------------------------
# harness client
# ------------------------------------------------------------------------------------------

class HarnessError(Exception):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


class Harness:
    """Runs the exact staged implementation bytes in an isolated interpreter process."""

    def __init__(self, impl_dir: Path, files: dict[str, str], symbols: dict[str, tuple[str, str]],
                 per_call_timeout: float = 5.0, memory_mb: int = 2048,
                 require_network_isolation: bool = True,
                 require_filesystem_isolation: bool = True) -> None:
        self.tmp = tempfile.mkdtemp(prefix="verislop-harness-")
        self.proc = None
        self._stdout_buffer = bytearray()
        stage = Path(self.tmp) / "artifact"
        self.per_call_timeout = per_call_timeout
        self.calls = 0
        try:
            fsutil.copy_files(impl_dir, stage, list(files))
            fsutil.make_readonly_tree(stage)
            script = Path(self.tmp) / "harness.py"
            shutil.copyfile(HARNESS, script)
            argv = [str(Path(sys.executable).resolve()), "-I", "-S", "-B", str(script)]
            self.proc, self.isolation = sandbox.popen(
                argv, Path(self.tmp), memory_mb=memory_mb, cpu_seconds=3600, fsize_mb=64,
                stdin=subprocess.PIPE, require_network_isolation=require_network_isolation,
                require_filesystem_isolation=require_filesystem_isolation,
                read_only_paths=[*python_runtime_paths(), stage, script],
            )
            self.isolation["interpreter_flags"] = ["-I", "-S", "-B"]
            self._send({"op": "load", "root": str(stage), "files": files,
                        "symbols": {k: list(v) for k, v in symbols.items()}})
            ready = self._recv(30.0)
            if ready is None or ready.get("op") != "ready":
                if ready is None:
                    raise HarnessError("timeout", "harness did not become ready")
                raise HarnessError(ready.get("kind", "error"), ready.get("message", "harness failed to load"))
            self.ready = ready
        except RuntimeError as exc:
            self.close()
            raise HarnessError("isolation", str(exc)) from None
        except BaseException:
            self.close()
            raise

    def _send(self, obj: dict[str, Any]) -> None:
        assert self.proc is not None
        assert self.proc.stdin is not None
        self.proc.stdin.write((json.dumps(obj) + "\n").encode())
        self.proc.stdin.flush()

    def _recv(self, timeout: float) -> dict[str, Any] | None:
        assert self.proc is not None
        assert self.proc.stdout is not None
        deadline = time.monotonic() + timeout
        # A target can write a partial JSON line directly to stdout. select()+readline()
        # would then block forever, bypassing the per-call timeout.
        while b"\n" not in self._stdout_buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.proc.stdout], [], [], remaining)[0]:
                return None
            chunk = os.read(self.proc.stdout.fileno(), 65536)
            if not chunk:
                raise HarnessError("crash", "harness closed its output")
            self._stdout_buffer.extend(chunk)
            if len(self._stdout_buffer) > 8 * 1024 * 1024:
                raise HarnessError("protocol", "harness response exceeds 8 MiB")
        line, _, remainder = self._stdout_buffer.partition(b"\n")
        self._stdout_buffer = bytearray(remainder)
        try:
            response = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            raise HarnessError("protocol", "harness returned malformed JSON") from None
        if not isinstance(response, dict):
            raise HarnessError("protocol", "harness response must be an object")
        return response

    def call(self, symbol: str, args: list[dict[str, Any]]) -> dict[str, Any]:
        self.calls += 1
        self._send({"op": "call", "id": self.calls, "symbol": symbol, "args": args})
        resp = self._recv(self.per_call_timeout)
        if resp is None:
            raise HarnessError("timeout", f"call to {symbol} exceeded {self.per_call_timeout}s")
        return resp

    def coverage(self) -> dict[str, Any]:
        self._send({"op": "coverage"})
        resp = self._recv(30.0)
        return resp.get("files", {}) if resp else {}

    def close(self) -> None:
        try:
            if self.proc is not None:
                sandbox.kill_process_group(self.proc)
                try:
                    self.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=2)
                for pipe in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                    if pipe is not None:
                        pipe.close()
        finally:
            # Do not chmod every file before removal: a hostile scratch symlink could
            # make that follow a link and chmod an outside host file after containment
            # ends. Linux shutil.rmtree uses directory FDs and does not follow links.
            if Path(self.tmp).exists():
                shutil.rmtree(self.tmp)


def byte_compile(impl_dir: Path, files: list[str], out_dir: Path, timeout: float = 120) -> dict[str, Any]:
    """Materialization check: byte-compile the exact sources in the sandbox (checked-hash pycs)."""
    stage = out_dir / "src"
    fsutil.copy_files(impl_dir, stage, files)
    py = [f for f in files if f.endswith(".py")]
    script = (
        "import py_compile,sys,json\n"
        "errs=[]\n"
        "for f in sys.argv[1:]:\n"
        "    try:\n"
        "        py_compile.compile(f, cfile=f+'c', doraise=True, invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)\n"
        "    except py_compile.PyCompileError as e:\n"
        "        errs.append(str(e))\n"
        "print(json.dumps(errs))\n"
    )
    res = sandbox.run([str(Path(sys.executable).resolve()), "-I", "-S", "-c", script, *py], stage,
                      timeout=timeout, memory_mb=2048, read_only_paths=python_runtime_paths(),
                      require_network_isolation=True)
    errors = []
    try:
        errors = json.loads(res.stdout.decode() or "[]")
    except ValueError:
        errors = [res.stderr.decode("utf-8", "replace")[-500:] or "byte compilation failed"]
    if res.returncode != 0 and not errors:
        errors = [res.stderr.decode("utf-8", "replace")[-500:]]
    pycs = {}
    for f in py:
        p = stage / (f + "c")
        if p.is_file():
            pycs[f + "c"] = canonical.digest(p.read_bytes())
    return {"ok": not errors and res.returncode == 0, "errors": errors, "pyc": pycs, "isolation": res.isolation}
