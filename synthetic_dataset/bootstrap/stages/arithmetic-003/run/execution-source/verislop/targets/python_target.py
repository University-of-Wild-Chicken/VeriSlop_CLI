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
import re
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
PROFILE_ID_V2 = "python-v0_2"
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
PROFILE_DOC_V2 = {**PROFILE_DOC, "id": PROFILE_ID_V2,
    "Int": "exact int (bool rejected); signed arbitrary precision",
    "String": "str of Unicode scalar values; surrogate code points rejected",
    "List": "exact Python list; recursively mapped element sort",
    "Record": "exact Python dict with precisely the accepted fixed fields and recursively mapped values",
    "Option": "None for none; ordinary payload representation for some; Unit and nested Option payloads rejected"}
WIRE_LIMITS = {"depth": 32, "nodes": 4096, "items": 256, "fields": 64,
               "string_chars": 16384, "integer_digits": 4096, "text_chars": 262144}


def profile_id(profile: dsl.Profile | dict[str, Any] | None = None) -> str:
    raw = profile.raw if isinstance(profile, dsl.Profile) else (profile or {})
    return PROFILE_ID_V2 if raw.get("dsl") == "verislop.contract-dsl/0.2" else PROFILE_ID


def profile_doc(profile: dsl.Profile | dict[str, Any] | None = None) -> dict[str, Any]:
    return dict(PROFILE_DOC_V2 if profile_id(profile) == PROFILE_ID_V2 else PROFILE_DOC)


class WireBudgetExceeded(ValueError):
    """Transport work limit, not evidence that an otherwise legal target value is false."""


def scalar_string(value: Any) -> bool:
    return type(value) is str and not any(0xD800 <= ord(c) <= 0xDFFF for c in value)


def check_wire(value: Any, *, limits: dict[str, int] | None = None) -> None:
    """Check closed generic value syntax and finite transport work before sort decoding."""
    limits = {**WIRE_LIMITS, **(limits or {})}
    nodes = 0
    text_chars = 0

    def visit(v: Any, depth: int) -> None:
        nonlocal nodes, text_chars
        nodes += 1
        if depth > limits["depth"] or nodes > limits["nodes"]:
            raise WireBudgetExceeded("tagged value exceeds depth or node budget")
        if type(v) is not dict or len(v) != 1:
            raise ValueError("tagged value must be an object with exactly one tag")
        tag, item = next(iter(v.items()))
        text_chars += len(item) if type(item) is str else (sum(len(k) for k in item if type(k) is str) if type(item) is dict else 0)
        if text_chars > limits["text_chars"]:
            raise WireBudgetExceeded("value exceeds aggregate text budget")
        if tag == "int":
            if type(item) is not str or re.fullmatch(r"0|-?[1-9][0-9]*", item) is None:
                raise ValueError("int payload must be a canonical signed decimal string")
            if len(item.lstrip("-")) > limits["integer_digits"]:
                raise WireBudgetExceeded("integer exceeds decimal digit budget")
        elif tag == "bool":
            if type(item) is not bool:
                raise ValueError("bool payload must be a JSON Boolean")
        elif tag == "none":
            if item is not None:
                raise ValueError("none payload must be null")
        elif tag == "str":
            if not scalar_string(item):
                raise ValueError("str payload must contain Unicode scalar values")
            if len(item) > limits["string_chars"]:
                raise WireBudgetExceeded("string exceeds character budget")
        elif tag in ("tuple", "list"):
            if type(item) is not list or (tag == "tuple" and len(item) != 2):
                raise ValueError("tuple requires exactly two tagged values; list requires an array")
            if len(item) > limits["items"]:
                raise WireBudgetExceeded("sequence exceeds item budget")
            for child in item:
                visit(child, depth + 1)
        elif tag == "dict":
            if type(item) is not dict or not all(scalar_string(k) for k in item):
                raise ValueError("dict payload must have Unicode scalar string keys")
            if len(item) > limits["fields"] or any(len(k) > 256 for k in item):
                raise WireBudgetExceeded("record exceeds field budget")
            for child in item.values():
                visit(child, depth + 1)
        else:
            raise ValueError(f"unknown value tag {tag!r}")

    visit(value, 0)


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

def encode_arg(v: Any, sort: Any, profile: dsl.Profile | None = None) -> dict[str, Any]:
    """Map immutable DSL values to native-Python wire shapes without type coercions."""
    nodes = 0
    def encode(value: Any, s: Any, depth: int = 0) -> dict[str, Any]:
        nonlocal nodes
        nodes += 1
        if depth > WIRE_LIMITS["depth"] or nodes > WIRE_LIMITS["nodes"]:
            raise WireBudgetExceeded("argument exceeds nesting or node budget")
        if s in ("Nat", "Int"):
            if type(value) is not int or (s == "Nat" and value < 0):
                raise ValueError(f"expected exact {s} integer")
            if value.bit_length() > 13608:
                raise WireBudgetExceeded("integer exceeds decimal digit budget")
            return {"int": str(value)}
        if s == "String":
            if not scalar_string(value):
                raise ValueError("expected Unicode scalar String")
            return {"str": value}
        if s == "Bool":
            if type(value) is not bool:
                raise ValueError("expected exact Bool")
            return {"bool": value}
        if s == "Unit":
            if value != dsl.UNIT:
                raise ValueError("expected DSL Unit")
            return {"none": None}
        if not isinstance(s, dict):
            raise ValueError("unknown argument sort")
        if "enum" in s:
            if (type(value) is not tuple or len(value) != 3 or value[:2] != ("enum", s["enum"]) or
                    (profile is not None and value[2] not in profile.enums[s["enum"]]["constructors"])):
                raise ValueError("expected accepted enumeration value")
            return {"str": value[2]}
        if "option" in s:
            if value == dsl.OPTION_NONE and type(value) is tuple:
                return {"none": None}
            if type(value) is tuple and len(value) == 2 and value[0] == "some":
                return encode(value[1], s["option"], depth + 1)
            raise ValueError("expected an accepted Option constructor")
        if "list" in s:
            if type(value) is not tuple or len(value) > WIRE_LIMITS["items"]:
                if type(value) is tuple:
                    raise WireBudgetExceeded("list exceeds item budget")
                raise ValueError("DSL list value must be an immutable tuple")
            return {"list": [encode(x, s["list"], depth + 1) for x in value]}
        if "record" in s:
            if profile is None:
                raise ValueError("record encoding requires its accepted profile")
            fields = profile.records[s["record"]]["fields"]
            if (type(value) is not tuple or len(value) != 3 or value[:2] != ("record", s["record"]) or
                    type(value[2]) is not tuple or len(value[2]) != len(fields)):
                raise ValueError("record value does not match its accepted field order")
            return {"dict": {f["name"]: encode(x, f["sort"], depth + 1) for f, x in zip(fields, value[2])}}
        if "result" in s and type(value) is tuple and len(value) == 2 and value[0] in ("ok", "error"):
            side, inner = value
            return {"tuple": [{"str": side}, encode(inner, s["result"][side], depth + 1)]}
        raise ValueError("value does not match accepted sort")

    if profile is not None:
        dsl.check_sort(sort, profile)
    encoded = encode(v, sort)
    check_wire(encoded)
    return encoded


def decode_result(j: dict[str, Any], sort: Any, profile: dsl.Profile) -> Any:
    """Strict sort-directed decoding; malformed values and work limits stay distinct."""
    if isinstance(j, dict) and set(j) == {"encoding_budget"}:
        raise WireBudgetExceeded("target output exceeds harness transport budget")
    dsl.check_sort(sort, profile)
    check_wire(j)

    def decode(v: dict[str, Any], s: Any) -> Any:
        if s in ("Nat", "Int"):
            if set(v) == {"int"}:
                out = int(v["int"])
                if s == "Int" or out >= 0:
                    return out
            raise ValueError(f"expected exact {s} integer")
        if s == "String":
            if set(v) == {"str"}:
                return v["str"]
            raise ValueError("expected Unicode scalar String")
        if s == "Bool":
            if set(v) == {"bool"}:
                return v["bool"]
            raise ValueError("expected Bool")
        if s == "Unit":
            if set(v) == {"none"}:
                return dsl.UNIT
            raise ValueError("expected None")
        if "enum" in s:
            if set(v) == {"str"} and v["str"] in profile.enums[s["enum"]]["constructors"]:
                return dsl.enum_v(s["enum"], v["str"])
            raise ValueError("expected accepted enumeration constructor")
        if "option" in s:
            if set(v) == {"none"}:
                return dsl.OPTION_NONE
            return dsl.option_some_v(decode(v, s["option"]))
        if "list" in s:
            if set(v) != {"list"}:
                raise ValueError("expected exact Python list (tuple rejected)")
            return tuple(decode(x, s["list"]) for x in v["list"])
        if "record" in s:
            fields = profile.records[s["record"]]["fields"]
            if set(v) != {"dict"} or set(v["dict"]) != {f["name"] for f in fields}:
                raise ValueError("record requires exactly its accepted field keys")
            return ("record", s["record"], tuple(decode(v["dict"][f["name"]], f["sort"]) for f in fields))
        t = v.get("tuple")
        if t is not None and set(t[0]) == {"str"} and t[0]["str"] in ("ok", "error"):
            side = t[0]["str"]
            return (side, decode(t[1], s["result"][side]))
        raise ValueError("expected ('ok', value) or ('error', error) tuple")

    return decode(j, sort)


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
        self._closed = False
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

    @property
    def closed(self) -> bool:
        """A failed channel is never reusable, even if a response later arrives."""
        return self._closed

    def _require_open(self) -> None:
        if self._closed or self.proc is None:
            raise HarnessError("closed", "harness channel is closed")

    def _send(self, obj: dict[str, Any]) -> None:
        self._require_open()
        assert self.proc is not None and self.proc.stdin is not None
        try:
            self.proc.stdin.write((json.dumps(obj) + "\n").encode())
            self.proc.stdin.flush()
        except (OSError, ValueError) as exc:
            self.close()
            raise HarnessError("crash", f"harness request could not be sent: {exc}") from None

    def _recv(self, timeout: float) -> dict[str, Any] | None:
        self._require_open()
        assert self.proc is not None and self.proc.stdout is not None
        deadline = time.monotonic() + timeout
        # A target can write a partial JSON line directly to stdout. select()+readline()
        # would then block forever, bypassing the per-call timeout.
        while b"\n" not in self._stdout_buffer:
            remaining = deadline - time.monotonic()
            try:
                readable = remaining > 0 and select.select([self.proc.stdout], [], [], remaining)[0]
            except (OSError, ValueError) as exc:
                self.close()
                raise HarnessError("crash", f"harness output could not be read: {exc}") from None
            if not readable:
                self.close()
                return None
            try:
                chunk = os.read(self.proc.stdout.fileno(), 65536)
            except (OSError, ValueError) as exc:
                self.close()
                raise HarnessError("crash", f"harness output could not be read: {exc}") from None
            if not chunk:
                self.close()
                raise HarnessError("crash", "harness closed its output")
            self._stdout_buffer.extend(chunk)
            if len(self._stdout_buffer) > 8 * 1024 * 1024:
                self.close()
                raise HarnessError("protocol", "harness response exceeds 8 MiB")
        line, _, remainder = self._stdout_buffer.partition(b"\n")
        self._stdout_buffer = bytearray(remainder)
        try:
            response = json.loads(line)
        except (ValueError, UnicodeDecodeError, RecursionError):
            self.close()
            raise HarnessError("protocol", "harness returned malformed JSON") from None
        if not isinstance(response, dict):
            self.close()
            raise HarnessError("protocol", "harness response must be an object")
        return response

    def call(self, symbol: str, args: list[dict[str, Any]]) -> dict[str, Any]:
        self._require_open()
        self.calls += 1
        self._send({"op": "call", "id": self.calls, "symbol": symbol, "args": args})
        resp = self._recv(self.per_call_timeout)
        if resp is None:
            raise HarnessError("timeout", f"call to {symbol} exceeded {self.per_call_timeout}s")
        if type(resp.get("id")) is not int or resp["id"] != self.calls:
            self.close()
            raise HarnessError("protocol", "target response is not correlated to this invocation")
        if resp.get("op") == "result":
            valid = set(resp) == {"op", "id", "value"}
        elif resp.get("op") == "exception":
            valid = (set(resp) == {"op", "id", "type", "message"} and
                     type(resp["type"]) is str and type(resp["message"]) is str)
        else:
            valid = False
        if not valid:
            self.close()
            raise HarnessError("protocol", "target returned a malformed call response")
        return resp

    def coverage(self) -> dict[str, Any]:
        if self._closed:
            return {}
        self._send({"op": "coverage"})
        resp = self._recv(30.0)
        if resp is None:
            return {}
        if set(resp) != {"op", "files"} or resp.get("op") != "coverage" or type(resp["files"]) is not dict:
            self.close()
            raise HarnessError("protocol", "harness returned a malformed coverage response")
        return resp["files"]

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._stdout_buffer.clear()
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
                        try:
                            pipe.close()
                        except OSError:
                            # A buffered stdin close can retry the very write that
                            # failed. Still close the other pipes and preserve the
                            # original channel failure rather than masking it.
                            pass
        finally:
            # Do not chmod every file before removal: a hostile scratch symlink could
            # make that follow a link and chmod an outside host file after containment
            # ends. Linux shutil.rmtree uses directory FDs and does not follow links.
            if Path(self.tmp).exists():
                shutil.rmtree(self.tmp)


def byte_compile(impl_dir: Path, files: list[str], out_dir: Path, timeout: float = 120) -> dict[str, Any]:
    """Materialization check: byte-compile the exact sources in the sandbox (checked-hash pycs)."""
    stage = out_dir / "src"
    stage.mkdir(parents=True, exist_ok=True)
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
