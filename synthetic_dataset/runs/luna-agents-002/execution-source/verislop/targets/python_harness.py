"""VeriSlop trusted test harness for Python targets (runs inside the target sandbox).

Protocol: JSON Lines on stdin/stdout.

* `{"op": "load", "root": DIR, "files": {REL: "sha256:..."}, "symbols": {ID: [REL, QUALNAME]}}`
  Verifies the exact bytes of every implementation file before executing anything, refuses to
  run with assertions disabled, and imports modules only from the staged directory.
* `{"op": "call", "id": N, "symbol": ID, "args": [GENERIC...]}` -> result / exception
* `{"op": "coverage"}` -> executed and executable lines of implementation files

Values use a generic tagged encoding; the supervisor decodes results strictly against the
expected DSL sort. The harness never decides whether a property holds.
"""

import hashlib
import importlib
import json
import os
import sys
import traceback


def enc(v, depth=0):
    if depth > 64:
        return {"other": "<too deep>", "type": type(v).__name__}
    if isinstance(v, bool):
        return {"bool": v}
    if isinstance(v, int):
        return {"int": str(v)}
    if v is None:
        return {"none": None}
    if isinstance(v, str):
        return {"str": v}
    if isinstance(v, tuple):
        return {"tuple": [enc(x, depth + 1) for x in v]}
    if isinstance(v, list):
        return {"list": [enc(x, depth + 1) for x in v]}
    return {"other": repr(v)[:200], "type": type(v).__name__}


def dec(j):
    if "bool" in j:
        return bool(j["bool"])
    if "int" in j:
        return int(j["int"])
    if "none" in j:
        return None
    if "str" in j:
        return j["str"]
    if "tuple" in j:
        return tuple(dec(x) for x in j["tuple"])
    raise ValueError("unsupported argument encoding")


def main():
    out = sys.stdout
    def send(obj):
        out.write(json.dumps(obj, sort_keys=True) + "\n")
        out.flush()

    executed = {}
    root = None
    symbols = {}
    files = {}

    def tracer(frame, event, arg):
        fn = frame.f_code.co_filename
        if root and fn.startswith(root):
            if event in ("call", "line"):
                executed.setdefault(fn, set()).add(frame.f_lineno)
            return tracer
        return None

    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            send({"op": "error", "kind": "protocol", "message": "malformed request"})
            continue
        op = msg.get("op")
        if op == "load":
            if not __debug__ or sys.flags.optimize:
                send({"op": "error", "kind": "assertions_disabled", "message": "interpreter runs with -O; assertions are disabled"})
                return
            root = os.path.realpath(msg["root"]) + os.sep
            files = msg["files"]
            for rel, digest in files.items():
                path = os.path.join(root, rel)
                with open(path, "rb") as fh:
                    actual = "sha256:" + hashlib.sha256(fh.read()).hexdigest()
                if actual != digest:
                    send({"op": "error", "kind": "hash_mismatch", "message": rel})
                    return
            sys.path.insert(0, root)
            sys.dont_write_bytecode = True
            sys.settrace(tracer)
            try:
                for sid, (rel, qual) in msg["symbols"].items():
                    modname = rel[:-3].replace("/", ".")
                    mod = importlib.import_module(modname)
                    if os.path.realpath(mod.__file__) != os.path.realpath(os.path.join(root, rel)):
                        send({"op": "error", "kind": "module_resolution", "message": f"{modname} resolved outside the staged artifact"})
                        return
                    symbols[sid] = getattr(mod, qual)
            except Exception as exc:  # noqa: BLE001
                sys.settrace(None)
                send({"op": "error", "kind": "import_failure", "message": "".join(traceback.format_exception_only(type(exc), exc)).strip()})
                return
            sys.settrace(None)
            send({"op": "ready", "python": sys.version.split()[0], "assertions": __debug__, "files_verified": len(files)})
        elif op == "call":
            fn = symbols.get(msg["symbol"])
            try:
                args = [dec(a) for a in msg["args"]]
                sys.settrace(tracer)
                try:
                    value = fn(*args)
                finally:
                    sys.settrace(None)
                send({"op": "result", "id": msg["id"], "value": enc(value)})
            except BaseException as exc:  # noqa: BLE001 - every target failure is reported
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    send({"op": "exception", "id": msg["id"], "type": type(exc).__name__, "message": "target attempted to exit"})
                else:
                    send({"op": "exception", "id": msg["id"], "type": type(exc).__name__, "message": str(exc)[:500]})
        elif op == "coverage":
            report = {}
            for rel in files:
                path = os.path.join(root, rel)
                try:
                    with open(path, "rb") as fh:
                        code = compile(fh.read(), path, "exec")
                except SyntaxError:
                    continue
                lines = set()
                stack = [code]
                while stack:
                    c = stack.pop()
                    for _, _, ln in c.co_lines():
                        if ln is not None and ln > 0:
                            lines.add(ln)
                    stack.extend(k for k in c.co_consts if hasattr(k, "co_lines"))
                hit = executed.get(os.path.realpath(path), set())
                report[rel] = {"executable": sorted(lines), "executed": sorted(hit & lines)}
            send({"op": "coverage", "files": report})
        elif op == "exit":
            return


if __name__ == "__main__":
    main()
