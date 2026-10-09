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
import re

LIMITS = {"depth": 32, "nodes": 4096, "items": 256, "fields": 64, "string_chars": 16384, "integer_digits": 4096, "text_chars": 262144}


class EncodingBudget(Exception):
    pass


def scalar_string(v):
    return type(v) is str and not any(0xD800 <= ord(c) <= 0xDFFF for c in v)


def enc(v, depth=0, budget=None):
    budget = [0, 0] if budget is None else budget
    budget[0] += 1
    if depth > LIMITS["depth"] or budget[0] > LIMITS["nodes"]:
        raise EncodingBudget("output exceeds depth or node budget")
    if type(v) is bool:
        return {"bool": v}
    if type(v) is int:
        if v.bit_length() > 13608:
            raise EncodingBudget("output integer exceeds digit budget")
        text = str(v)
        budget[1] += len(text)
        if budget[1] > LIMITS["text_chars"]:
            raise EncodingBudget("output exceeds aggregate text budget")
        if len(text.lstrip("-")) > LIMITS["integer_digits"]:
            raise EncodingBudget("output integer exceeds digit budget")
        return {"int": text}
    if v is None:
        return {"none": None}
    if type(v) is str:
        if not scalar_string(v):
            return {"other": "non-scalar string", "type": "str"}
        if len(v) > LIMITS["string_chars"]:
            raise EncodingBudget("output string exceeds character budget")
        budget[1] += len(v)
        if budget[1] > LIMITS["text_chars"]:
            raise EncodingBudget("output exceeds aggregate text budget")
        return {"str": v}
    if type(v) in (tuple, list):
        if len(v) > LIMITS["items"]:
            raise EncodingBudget("output sequence exceeds item budget")
        return {"tuple" if type(v) is tuple else "list": [enc(x, depth + 1, budget) for x in v]}
    if type(v) is dict:
        if len(v) > LIMITS["fields"] or any(type(k) is str and len(k) > 256 for k in v):
            raise EncodingBudget("output dictionary exceeds field budget")
        if not all(scalar_string(k) for k in v):
            return {"other": "dictionary keys are not scalar strings", "type": "dict"}
        budget[1] += sum(len(k) for k in v)
        if budget[1] > LIMITS["text_chars"]:
            raise EncodingBudget("output exceeds aggregate text budget")
        return {"dict": {k: enc(x, depth + 1, budget) for k, x in v.items()}}
    return {"other": repr(v)[:200], "type": type(v).__name__}


def dec(j, depth=0, budget=None):
    budget = [0, 0] if budget is None else budget
    budget[0] += 1
    if depth > LIMITS["depth"] or budget[0] > LIMITS["nodes"]:
        raise ValueError("argument exceeds depth or node budget")
    if type(j) is not dict or len(j) != 1:
        raise ValueError("argument requires exactly one closed value tag")
    item = next(iter(j.values()))
    budget[1] += len(item) if type(item) is str else (sum(len(k) for k in item if type(k) is str) if type(item) is dict else 0)
    if budget[1] > LIMITS["text_chars"]:
        raise ValueError("argument exceeds aggregate text budget")
    if "bool" in j and type(j["bool"]) is bool:
        return j["bool"]
    if "int" in j and type(j["int"]) is str and len(j["int"].lstrip("-")) <= LIMITS["integer_digits"] and re.fullmatch(r"0|-?[1-9][0-9]*", j["int"]):
        return int(j["int"])
    if "none" in j and j["none"] is None:
        return None
    if "str" in j and scalar_string(j["str"]) and len(j["str"]) <= LIMITS["string_chars"]:
        return j["str"]
    if "tuple" in j and type(j["tuple"]) is list and len(j["tuple"]) == 2:
        return tuple(dec(x, depth + 1, budget) for x in j["tuple"])
    if "list" in j and type(j["list"]) is list and len(j["list"]) <= LIMITS["items"]:
        return [dec(x, depth + 1, budget) for x in j["list"]]
    if ("dict" in j and type(j["dict"]) is dict and len(j["dict"]) <= LIMITS["fields"] and
            all(scalar_string(k) and len(k) <= 256 for k in j["dict"])):
        return {k: dec(x, depth + 1, budget) for k, x in j["dict"].items()}
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
                try:
                    encoded = enc(value)
                except EncodingBudget as exc:
                    encoded = {"encoding_budget": str(exc)}
                send({"op": "result", "id": msg["id"], "value": encoded})
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
