"""Deterministic D01--D33 benchmark task specifications and private oracles.

This file is benchmark-author data, never included in candidate model prompts.
Run directly to check independent anchors and deterministic case generation.
"""
from __future__ import annotations

import copy
import csv
import io
import json
import random
import re
import urllib.parse
from functools import cmp_to_key


def _d01(d):
    text = "".join(d["chunks"])
    tokens, token, quote, escaped, active = [], [], None, False, False
    for ch in text:
        if escaped:
            token.append(ch); escaped = False; active = True
        elif ch == "\\" and quote != "'":
            escaped = True; active = True
        elif quote:
            if ch == quote: quote = None
            else: token.append(ch)
        elif ch in "'\"":
            quote = ch; active = True
        elif ch in " \t\r\n":
            if active: tokens.append("".join(token)); token = []; active = False
        else:
            token.append(ch); active = True
    if escaped: return {"error": "trailing_escape"}
    if quote: return {"error": "unclosed_quote"}
    if active: tokens.append("".join(token))
    return {"tokens": tokens}


def _d02(d):
    def walk(node, path):
        if not path: return [node]
        head, *tail = path
        if head == "*":
            children = [node[k] for k in sorted(node)] if isinstance(node, dict) else node if isinstance(node, list) else []
            return [v for child in children for v in walk(child, tail)]
        if isinstance(node, dict) and isinstance(head, str) and head in node:
            return walk(node[head], tail)
        if isinstance(node, list) and type(head) is int and 0 <= head < len(node):
            return walk(node[head], tail)
        return []
    return [walk(d["document"], p) for p in d["paths"]]


def _d03(d):
    variables = d["variables"]
    pattern = re.compile(r"\$\$\{|\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
    class Failure(Exception):
        def __init__(self, payload): self.payload = payload
    def expand(name, stack):
        if name in stack:
            raise Failure({"error": "cycle", "path": stack[stack.index(name):] + [name]})
        if name not in variables: raise Failure({"error": "missing", "name": name})
        def replace(m):
            return "${" if m.group(0) == "$${" else expand(m.group(1), stack + [name])
        return pattern.sub(replace, variables[name])
    out = []
    for name in d["targets"]:
        try: out.append({"value": expand(name, [])})
        except Failure as e: out.append(e.payload)
    return out


def _semver(s):
    m = re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?", s)
    if not m: return None
    pre = m.group(4).split(".") if m.group(4) else []
    if any(x.isdigit() and len(x) > 1 and x[0] == "0" for x in pre): return None
    return tuple(map(int, m.groups()[:3])), pre


def _svcmp(a, b):
    ac, ap = a; bc, bp = b
    if ac != bc: return (ac > bc) - (ac < bc)
    if not ap or not bp: return (not ap) - (not bp)
    for x, y in zip(ap, bp):
        if x == y: continue
        if x.isdigit() and y.isdigit(): return (int(x) > int(y)) - (int(x) < int(y))
        if x.isdigit() != y.isdigit(): return -1 if x.isdigit() else 1
        return (x > y) - (x < y)
    return (len(ap) > len(bp)) - (len(ap) < len(bp))


def _d04(d):
    parsed = [_semver(v) for v in d["versions"]]
    accepted = []
    for i, v in enumerate(parsed):
        if v is None: continue
        for clause in d["clauses"]:
            comps = [(c["op"], _semver(c["version"])) for c in clause]
            if v[1] and not any(c[1] and c[0] == v[0] for _, c in comps): continue
            if all({"=": z == 0, "<": z < 0, "<=": z <= 0, ">": z > 0, ">=": z >= 0}[op] for op, c in comps for z in [_svcmp(v, c)]):
                accepted.append(i); break
    accepted.sort(key=cmp_to_key(lambda i, j: _svcmp(parsed[i], parsed[j])))
    return {"accepted": [d["versions"][i] for i in accepted], "invalid": [i for i, v in enumerate(parsed) if v is None]}


def _d05(d):
    left, right = d["left"], d["right"]
    def conflict(a, b):
        x, y = a["start"], a["end"]; u, v = b["start"], b["end"]
        if x == y and u == v: return x == u
        if x == y: return u < x < v
        if u == v: return x < u < y
        return max(x, u) < min(y, v)
    bad = [[i, j] for i, a in enumerate(left) for j, b in enumerate(right) if a != b and conflict(a, b)]
    if bad: return {"conflicts": bad}
    edits = []
    for side in (left, right):
        for e in side:
            if e not in edits: edits.append(e)
    edits.sort(key=lambda e: (e["start"], e["end"]))
    cursor = 0; out = []
    for e in edits:
        out.extend([d["base"][cursor:e["start"]], e["text"]]); cursor = e["end"]
    out.append(d["base"][cursor:])
    return {"text": "".join(out)}


def _d06(d):
    lines = d["lines"][:]
    for i, op in enumerate(d["operations"]):
        at, remove = op["at"], op["remove"]
        if type(at) is not int or at < 0 or at > len(lines): return {"error": "range", "operation": i}
        if lines[at:at + len(remove)] != remove or at + len(remove) > len(lines):
            return {"error": "context", "operation": i}
        lines[at:at + len(remove)] = op["insert"]
    return {"lines": lines}


def _d07(d):
    s = d["text"]; rows = []; row = []; cell = []; state = "start"; i = 0; any_row = False
    def end_cell():
        row.append("".join(cell)); cell.clear()
    def end_row():
        nonlocal row, any_row
        end_cell(); rows.append(row); row = []; any_row = False
    while i < len(s):
        ch = s[i]
        if state == "quoted":
            if ch == '"':
                if i + 1 < len(s) and s[i + 1] == '"': cell.append('"'); i += 2; continue
                state = "closed"
            else: cell.append(ch)
            i += 1; continue
        if ch == ",": end_cell(); state = "start"; any_row = True
        elif ch in "\r\n":
            if ch == "\r" and (i + 1 == len(s) or s[i + 1] != "\n"): return {"error": "bare_cr", "offset": i}
            end_row(); state = "start"
            if ch == "\r": i += 1
        elif state == "closed": return {"error": "after_quote", "offset": i}
        elif ch == '"':
            if state != "start": return {"error": "quote_in_field", "offset": i}
            state = "quoted"; any_row = True
        else: cell.append(ch); state = "plain"; any_row = True
        i += 1
    if state == "quoted": return {"error": "unclosed_quote", "offset": len(s)}
    if any_row or row or cell: end_row()
    return {"rows": rows}


def _d08(d):
    def decode(s):
        if re.search(r"%(?![0-9a-fA-F]{2})", s): raise ValueError("percent")
        return urllib.parse.unquote_to_bytes(s.replace("+", " ")).decode("utf-8", "strict")
    pairs = []
    for i, chunk in enumerate(d["queries"]):
        if not chunk: continue
        for field in chunk.split("&"):
            raw = field.split("=", 1)
            try: pairs.append([decode(raw[0]), decode(raw[1] if len(raw) == 2 else "")])
            except (ValueError, UnicodeError): return {"error": "decode", "query": i}
    for k in d["remove"]: pairs = [p for p in pairs if p[0] != k]
    for k, v in d["set"]:
        positions = [i for i, p in enumerate(pairs) if p[0] == k]
        at = positions[0] if positions else len(pairs)
        pairs = [p for p in pairs if p[0] != k]; pairs.insert(at, [k, v])
    encode = lambda x: urllib.parse.quote(x, safe="-._~", encoding="utf-8", errors="strict")
    return {"pairs": pairs, "query": "&".join(encode(k) + "=" + encode(v) for k, v in pairs)}


def _d09(d):
    state = {}; ignored = []
    for i, e in enumerate(d["events"]):
        old = state.get(e["key"])
        if old is not None and e["revision"] <= old["revision"]: ignored.append(i); continue
        state[e["key"]] = {"revision": e["revision"], "deleted": e["op"] == "delete", "value": e.get("value")}
    return {"items": [{"key": k, "revision": v["revision"], "value": v["value"]} for k, v in sorted(state.items()) if not v["deleted"]], "tombstones": [{"key": k, "revision": v["revision"]} for k, v in sorted(state.items()) if v["deleted"]], "ignored": ignored}


def _d10(d):
    doc = copy.deepcopy(d["document"])
    class PatchError(Exception): pass
    def tokens(path):
        if path == "": return []
        if not path.startswith("/"): raise PatchError()
        out = []
        for part in path[1:].split("/"):
            if re.search(r"~(?![01])", part): raise PatchError()
            out.append(part.replace("~1", "/").replace("~0", "~"))
        return out
    def index(parent, key, add=False):
        if isinstance(parent, list):
            if add and key == "-": return len(parent)
            if not re.fullmatch(r"0|[1-9][0-9]*", key): raise PatchError()
            at = int(key)
            if at > len(parent) if add else at >= len(parent): raise PatchError()
            return at
        if isinstance(parent, dict):
            if not add and key not in parent: raise PatchError()
            return key
        raise PatchError()
    def parent(parts):
        node = doc
        for k in parts[:-1]: node = node[index(node, k)]
        return node
    for i, op in enumerate(d["operations"]):
        try:
            parts = tokens(op["path"]); kind = op["op"]
            if not parts:
                if kind in ("add", "replace"): doc = copy.deepcopy(op["value"])
                elif kind == "test":
                    if _json_typed(doc) != _json_typed(op["value"]): raise PatchError()
                elif kind == "remove": doc = None
                else: raise PatchError()
                continue
            p = parent(parts); k = index(p, parts[-1], kind == "add")
            if kind == "add":
                if isinstance(p, list): p.insert(k, copy.deepcopy(op["value"]))
                else: p[k] = copy.deepcopy(op["value"])
            elif kind == "replace": p[k] = copy.deepcopy(op["value"])
            elif kind == "remove":
                if isinstance(p, list): p.pop(k)
                else: del p[k]
            elif kind == "test":
                # JSON numeric equality is allowed; boolean is a separate JSON type.
                if _json_typed(p[k]) != _json_typed(op["value"]): raise PatchError()
            else: raise PatchError()
        except (PatchError, KeyError, IndexError, TypeError): return {"error": "patch", "operation": i, "document": d["document"]}
    return {"document": doc}


def _json_typed(v):
    if isinstance(v, dict): return ("object", tuple(sorted((k, _json_typed(x)) for k, x in v.items())))
    if isinstance(v, list): return ("array", tuple(map(_json_typed, v)))
    return ("boolean" if type(v) is bool else "number" if type(v) in (int, float) else type(v).__name__, v)


def _d11(d):
    edges = sorted({x for r in d["ranges"] for x in (r["start"], r["end"])})
    result = []
    for a, b in zip(edges, edges[1:]):
        hits = [(r["priority"], i, r["value"]) for i, r in enumerate(d["ranges"]) if r["start"] <= a and b <= r["end"] and r["start"] < r["end"]]
        if not hits: continue
        v = max(hits, key=lambda x: x[:2])[2]
        if result and result[-1]["end"] == a and _json_typed(result[-1]["value"]) == _json_typed(v): result[-1]["end"] = b
        else: result.append({"start": a, "end": b, "value": v})
    return result


def _d12(d):
    runs = []
    for i, r in enumerate(d["runs"]):
        if type(r["count"]) is not int or r["count"] < 0: return {"error": "count", "run": i}
        if r["count"] == 0: continue
        if runs and _json_typed(runs[-1]["value"]) == _json_typed(r["value"]): runs[-1]["count"] += r["count"]
        else: runs.append(copy.deepcopy(r))
    total = sum(r["count"] for r in runs)
    values = []; at = 0
    start, end = max(0, d["start"]), max(0, d["end"])
    for r in runs:
        overlap = max(0, min(end, at + r["count"]) - max(start, at))
        values.extend([r["value"]] * overlap); at += r["count"]
    return {"runs": runs, "length": total, "slice": values}


def _d13(d):
    pattern = d["pattern"]; pos = 0
    class Syntax(Exception): pass
    def expression(in_brace=False):
        nonlocal pos
        result = [""]; alternatives = []
        while pos < len(pattern):
            ch = pattern[pos]
            if ch == "\\":
                pos += 1
                if pos == len(pattern): raise Syntax()
                atom = [pattern[pos]]; pos += 1
            elif ch == "{":
                pos += 1; atom = expression(True)
            elif ch == "}" or (ch == "," and in_brace):
                if not in_brace: raise Syntax()
                alternatives.extend(result); result = [""]; pos += 1
                if len(alternatives) > 256: raise Syntax()
                if ch == "}": return alternatives
                continue
            else: atom = [ch]; pos += 1
            result = [a + b for a in result for b in atom]
            if len(result) > 256: raise Syntax()
        if in_brace: raise Syntax()
        return result
    try: expanded = expression()
    except Syntax: return {"error": "syntax_or_limit"}
    return {"values": list(dict.fromkeys(expanded))}


def _d14(d):
    # The protocol preserves malformed input positions and maximal UTF-8 subparts.
    bs = bytes(x for chunk in d["chunks"] for x in chunk); i = 0; out = []; errors = []
    while i < len(bs):
        b = bs[i]
        if b < 128: out.append(chr(b)); i += 1; continue
        n = 2 if 0xC2 <= b <= 0xDF else 3 if 0xE0 <= b <= 0xEF else 4 if 0xF0 <= b <= 0xF4 else 0
        if not n: errors.append(i); out.append("\ufffd"); i += 1; continue
        j = 1
        while j < n and i + j < len(bs):
            c = bs[i + j]
            lo, hi = (0xA0, 0xBF) if j == 1 and b == 0xE0 else (0x80, 0x9F) if j == 1 and b == 0xED else (0x90, 0xBF) if j == 1 and b == 0xF0 else (0x80, 0x8F) if j == 1 and b == 0xF4 else (0x80, 0xBF)
            if not lo <= c <= hi: break
            j += 1
        if j == n: out.append(bs[i:i+n].decode("utf-8")); i += n
        else: errors.append(i); out.append("\ufffd"); i += j
    return {"text": "".join(out), "errors": errors}


def _d15(d):
    def columns(prefix):
        n = 0
        for ch in prefix: n += 1 if ch == " " else d["tab_width"] - n % d["tab_width"]
        return n
    lines = d["text"].split("\n")
    nonblank = [columns(re.match(r"[ \t]*", line).group()) for line in lines if line.strip(" \t")]
    common = min(nonblank) if nonblank else 0
    out = []
    for line in lines:
        prefix = re.match(r"[ \t]*", line).group(); content = line[len(prefix):]
        if not content: out.append("")
        else: out.append(" " * (columns(prefix) - common + d["indent"]) + content)
    return {"text": "\n".join(out), "removed_columns": common}


def _d16(d):
    errors = []
    def validate(value, schema, path):
        kind = schema["type"]
        ok = {"object": isinstance(value, dict), "array": isinstance(value, list), "string": type(value) is str, "integer": type(value) is int, "boolean": type(value) is bool, "null": value is None}[kind]
        if not ok: errors.append({"path": path, "error": "type"}); return value
        if kind == "object":
            out = copy.deepcopy(value); properties = schema.get("properties", {})
            for key in sorted(properties):
                child = properties[key]; childpath = path + "/" + key.replace("~", "~0").replace("/", "~1")
                if key not in out:
                    if "default" in child: out[key] = copy.deepcopy(child["default"])
                    elif key in schema.get("required", []): errors.append({"path": childpath, "error": "required"}); continue
                    else: continue
                out[key] = validate(out[key], child, childpath)
            if schema.get("additional", True) is False:
                for key in sorted(set(value) - set(properties)):
                    errors.append({"path": path + "/" + key.replace("~", "~0").replace("/", "~1"), "error": "additional"})
            return out
        if kind == "array": return [validate(x, schema["items"], path + "/" + str(i)) for i, x in enumerate(value)]
        if kind == "integer" and (value < schema.get("minimum", value) or value > schema.get("maximum", value)): errors.append({"path": path, "error": "range"})
        if "enum" in schema and all(_json_typed(value) != _json_typed(x) for x in schema["enum"]): errors.append({"path": path, "error": "enum"})
        return value
    value = validate(d["value"], d["schema"], "")
    return {"value": value, "errors": errors}


def _d17(d):
    root = {}; failure = None; seen = []
    for i, item in enumerate(d["items"]):
        path = item["path"]
        if not path: return {"error": "empty_path", "item": i}
        for old in seen:
            if path == old or path == old[:len(path)]: return {"error": "duplicate_or_prefix", "item": i}
            if old == path[:len(old)]: return {"error": "prefix", "item": i}
        seen.append(path)
        node = root
        for key in path[:-1]:
            if key not in node: node[key] = {}
            if not isinstance(node[key], dict): failure = "prefix"; break
            node = node[key]
        if failure: return {"error": failure, "item": i}
        key = path[-1]
        if key in node: return {"error": "duplicate_or_prefix", "item": i}
        node[key] = copy.deepcopy(item["value"])
    def flatten(node, path):
        if isinstance(node, dict) and node:
            return [x for k in sorted(node) for x in flatten(node[k], path + [k])]
        return [{"path": path, "value": node}]
    return {"document": root, "flat": flatten(root, [])}


def _d18(d):
    matches = []
    parts = d["path"].split("/")[1:]
    for i, route in enumerate(d["routes"]):
        pattern = route["pattern"].split("/")[1:]; values = {}; literal = 0; single = 0; greedy = False; at = 0; good = True
        for token in pattern:
            if token.startswith("*"):
                values[token[1:]] = "/".join(parts[at:]); at = len(parts); greedy = True
            elif at >= len(parts): good = False; break
            elif token.startswith(":"): values[token[1:]] = parts[at]; at += 1; single += 1
            elif token == parts[at]: at += 1; literal += 1
            else: good = False; break
        if good and at == len(parts): matches.append(((-literal, greedy, single, i), route["id"], values))
    if not matches: return None
    _, routeid, parameters = min(matches)
    return {"id": routeid, "parameters": parameters}


def _d19(d):
    rows = []; used = set()
    for a in d["left"]:
        hits = [j for j, b in enumerate(d["right"]) if a.get(d["key"]) is not None and b.get(d["key"]) is not None and _json_typed(a[d["key"]]) == _json_typed(b[d["key"]])]
        if hits:
            for j in hits: rows.append({"left": a, "right": d["right"][j]}); used.add(j)
        elif d["mode"] in ("left", "full"): rows.append({"left": a, "right": None})
    if d["mode"] == "full":
        rows.extend({"left": None, "right": b} for j, b in enumerate(d["right"]) if j not in used)
    return rows


def _d20(d):
    rows = copy.deepcopy(d["rows"])
    for r, row in enumerate(rows):
        for i, op in enumerate(d["operations"]):
            field = op.get("field")
            if op["op"] == "rename":
                if field not in row: continue
                if op["to"] != field and op["to"] in row: return {"error": "collision", "row": r, "operation": i}
                row[op["to"]] = row.pop(field)
            elif op["op"] == "default":
                if field not in row: row[field] = copy.deepcopy(op["value"])
            elif op["op"] == "drop": row.pop(field, None)
            elif op["op"] == "integer":
                if field not in row: continue
                value = row[field]
                if type(value) is int: continue
                if type(value) is not str or re.fullmatch(r"[+-]?(?:0|[1-9][0-9]*)", value) is None:
                    return {"error": "integer", "row": r, "operation": i}
                row[field] = int(value)
    return {"rows": rows}


def _d21(d):
    groups = sorted(set(e["group"] for e in d["events"]))
    result = []
    for group in groups:
        last = None
        for at in range(d["start"], d["end"], d["width"]):
            points = [(i, e) for i, e in enumerate(d["events"]) if e["group"] == group and at <= e["time"] < min(at + d["width"], d["end"])]
            values = [e["value"] for _, e in points if e["value"] is not None]
            if values: last = sum(values)
            result.append({"group": group, "start": at, "count": len(values), "value": sum(values) if values else last if d["fill"] == "previous" else None})
    return result


def _d22(d):
    words = re.findall(r"\S+", d["text"]); lines = []; line = ""
    # ANSI SGR bytes have display width zero; all other code points width one.
    width = lambda s: len(re.sub(r"\x1b\[[0-9;]*m", "", s))
    for word in words:
        if line and width(line + " " + word) > d["width"]: lines.append(line); line = word
        else: line = line + " " + word if line else word
    if line: lines.append(line)
    return {"lines": lines, "widths": [width(s) for s in lines]}


def _d23(d):
    s = d["text"]; i = 0; pairs = []
    while i < len(s):
        while i < len(s) and s[i] in " \t": i += 1
        if i == len(s): break
        at = i; m = re.match(r"[A-Za-z_][A-Za-z0-9_]*=", s[i:])
        if not m: return {"error": "key", "offset": i}
        key = m.group()[:-1]; i += len(m.group()); value = []
        if i < len(s) and s[i] == '"':
            i += 1
            while i < len(s) and s[i] != '"':
                if s[i] == "\\":
                    i += 1
                    if i == len(s): return {"error": "escape", "offset": i}
                    escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
                    if s[i] not in escapes: return {"error": "escape", "offset": i}
                    value.append(escapes[s[i]])
                else: value.append(s[i])
                i += 1
            if i == len(s): return {"error": "quote", "offset": i}
            i += 1
            if i < len(s) and s[i] not in " \t": return {"error": "separator", "offset": i}
        else:
            while i < len(s) and s[i] not in " \t": value.append(s[i]); i += 1
        pairs.append([key, "".join(value)])
    return {"pairs": pairs, "last": {k: v for k, v in pairs}}


def _d24(d):
    s = d["text"]; offsets = {0: 0}; count = 0
    for i, ch in enumerate(s): count += 2 if ord(ch) > 0xFFFF else 1; offsets[count] = i + 1
    edits = d["edits"]
    for i, e in enumerate(edits):
        if e["start"] not in offsets or e["end"] not in offsets or e["start"] > e["end"]: return {"error": "boundary", "edit": i}
        if i and e["start"] < edits[i-1]["end"]: return {"error": "overlap", "edit": i}
        if i and e["start"] < edits[i-1]["start"]: return {"error": "order", "edit": i}
    out = []; cursor = 0
    for e in edits: out.extend([s[cursor:offsets[e["start"]]], e["text"]]); cursor = offsets[e["end"]]
    out.append(s[cursor:])
    return {"text": "".join(out)}


def _d25(d):
    used = set(); matched = []; removed = []
    for i, before in enumerate(d["before"]):
        hits = [j for j, after in enumerate(d["after"]) if j not in used and _json_typed(before[d["key"]]) == _json_typed(after[d["key"]])]
        if not hits: removed.append(i); continue
        j = hits[0]; used.add(j)
        changes = [k for k in sorted(set(before) | set(d["after"][j])) if k not in before or k not in d["after"][j] or _json_typed(before[k]) != _json_typed(d["after"][j][k])]
        matched.append({"before": i, "after": j, "changed": changes})
    return {"matched": matched, "removed": removed, "added": [j for j in range(len(d["after"])) if j not in used]}


def _d26(d):
    def key(s):
        return tuple((0, int(x)) if x.isascii() and x.isdigit() else (1, x.casefold()) for x in re.findall(r"[0-9]+|[^0-9]+", s))
    return sorted(d["values"], key=key)


def _d27(d):
    # Strict duplicate-key parsing and canonical serializer are one transaction.
    class Duplicate(Exception): pass
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out: raise Duplicate()
            out[k] = v
        return out
    try:
        value = json.loads(d["text"], object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except Duplicate: return {"error": "duplicate_key"}
    except (ValueError, json.JSONDecodeError): return {"error": "syntax"}
    def valid(v):
        if isinstance(v, float): return False
        if isinstance(v, str): return not any(0xD800 <= ord(c) <= 0xDFFF for c in v)
        if isinstance(v, list): return all(map(valid, v))
        if isinstance(v, dict): return all(valid(k) and valid(x) for k, x in v.items())
        return True
    if not valid(value): return {"error": "unsupported"}
    return {"canonical": json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")), "value": value}


def _d28(d):
    raw = [x for c in d["chunks"] for x in c]; frames = []; errors = []; current = []; escape = False; started = False
    def finish():
        if not current: return
        if len(current) < 2: errors.append("short"); return
        n = current[0]
        if len(current) != n + 2: errors.append("length"); return
        if sum(current[:-1]) % 256 != current[-1]: errors.append("checksum"); return
        frames.append(current[1:-1])
    for b in raw:
        if b == 0x7E:
            if started:
                if escape: errors.append("escape")
                else: finish()
            current = []; escape = False; started = True
        elif not started: continue
        elif escape: current.append(b ^ 0x20); escape = False
        elif b == 0x7D: escape = True
        else: current.append(b)
    if started and (current or escape): errors.append("incomplete")
    return {"frames": frames, "errors": errors}


def _d29(d):
    latest = {}
    for row in d["rows"]:
        old = latest.get(row["id"])
        if old is None or row["revision"] > old["revision"]: latest[row["id"]] = row
    rows = sorted((r for r in latest.values() if not r.get("deleted", False) and r["score"] >= d["minimum"]), key=lambda r: (-r["score"], r["id"]))
    if d["cursor"] is not None:
        cursor = (-d["cursor"][0], d["cursor"][1]); rows = [r for r in rows if (-r["score"], r["id"]) > cursor]
    page = rows[:d["limit"]]
    return {"rows": page, "next": [page[-1]["score"], page[-1]["id"]] if len(rows) > d["limit"] and page else None}


def _d30(d):
    todo = d["path"].split("/"); resolved = []; hops = 0
    while todo:
        part = todo.pop(0)
        if not part or part == ".": continue
        if part == "..":
            if resolved: resolved.pop()
            continue
        resolved.append(part); key = "/" + "/".join(resolved)
        if key in d["links"]:
            hops += 1
            if hops > d["max_hops"]: return {"error": "symlink_limit"}
            target = d["links"][key]; resolved.pop()
            if target.startswith("/"): resolved = []
            todo = target.split("/") + todo
    return {"path": "/" + "/".join(resolved), "hops": hops}


def _d31(d):
    blocks = []; active = None
    for i, line in enumerate(d["text"].split("\n")):
        if active is None:
            m = re.fullmatch(r" {0,3}(`{3,}|~{3,})(.*)", line)
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                active = {"marker": m.group(1)[0], "length": len(m.group(1)), "info": m.group(2).strip(), "start": i, "lines": []}
        else:
            m = re.fullmatch(r" {0,3}([`~]+)[ \t]*", line)
            if m and set(m.group(1)) == {active["marker"]} and len(m.group(1)) >= active["length"]:
                blocks.append({"info": active["info"], "start": active["start"], "end": i, "text": "\n".join(active["lines"]), "closed": True}); active = None
            else: active["lines"].append(line)
    if active: blocks.append({"info": active["info"], "start": active["start"], "end": None, "text": "\n".join(active["lines"]), "closed": False})
    return blocks


def _d32(d):
    # Three-valued predicates preserve missing/null; false AND unknown is false.
    def predicate(row, p):
        op = p["op"]
        if op == "not":
            v = predicate(row, p["arg"]); return None if v is None else not v
        if op in ("and", "or"):
            vals = [predicate(row, x) for x in p["args"]]
            if op == "and": return False if False in vals else None if None in vals else True
            return True if True in vals else None if None in vals else False
        v = row.get(p["field"])
        if op == "is_null": return v is None
        if v is None or p["value"] is None: return None
        if op == "eq": return _json_typed(v) == _json_typed(p["value"])
        if type(v) is not type(p["value"]) or type(v) not in (int, str): return None
        return {"lt": v < p["value"], "gt": v > p["value"]}[op]
    selected = [(i, r) for i, r in enumerate(d["rows"]) if predicate(r, d["where"]) is True]
    def cmp(a, b):
        for spec in d["order"]:
            x, y = a[1].get(spec["field"]), b[1].get(spec["field"])
            if x is None or y is None: z = (x is None) - (y is None)
            else:
                z = (x > y) - (x < y)
                if spec["descending"]: z = -z
            if z: return z
        return a[0] - b[0]
    selected.sort(key=cmp_to_key(cmp))
    return [{k: row.get(k) for k in d["select"]} for _, row in selected[d["offset"]:d["offset"] + d["limit"]]]


def _d33(d):
    operations = []
    def path(parent, key): return parent + "/" + str(key).replace("~", "~0").replace("/", "~1")
    def diff(a, b, pointer):
        if _json_typed(a) == _json_typed(b): return
        if isinstance(a, dict) and isinstance(b, dict):
            for k in sorted(set(a) - set(b)): operations.append({"op": "remove", "path": path(pointer, k)})
            for k in sorted(set(a) & set(b)): diff(a[k], b[k], path(pointer, k))
            for k in sorted(set(b) - set(a)): operations.append({"op": "add", "path": path(pointer, k), "value": b[k]})
        elif isinstance(a, list) and isinstance(b, list):
            for i in range(min(len(a), len(b))): diff(a[i], b[i], path(pointer, i))
            for i in range(len(a)-1, len(b)-1, -1): operations.append({"op": "remove", "path": path(pointer, i)})
            for i in range(len(a), len(b)): operations.append({"op": "add", "path": path(pointer, i), "value": b[i]})
        else: operations.append({"op": "replace", "path": pointer, "value": b})
    diff(d["before"], d["after"], "")
    return operations


REFERENCES = {f"D{i:02d}": globals()[f"_d{i:02d}"] for i in range(1, 34)}


def reference(task_id, data):
    return REFERENCES[task_id](copy.deepcopy(data))


SPECS = []


def _task(task_id, title, category, specification, anchors, private):
    SPECS.append((task_id, title, category, specification, anchors, private))


_task("D01", "Incremental shell-word lexer", "parsing", "Input {chunks:[strings]} is one logical command, with chunk boundaries irrelevant. Return {tokens:[strings]}. ASCII space, tab, CR and LF separate words outside quotes. Single and double quotes delimit portions that concatenate with adjacent portions; quote characters disappear. Empty quotes create an empty word. Backslash escapes exactly the next character outside single quotes (including inside double quotes); inside single quotes it is literal. Return {error:'trailing_escape'} if final backslash is active, otherwise {error:'unclosed_quote'} for an unclosed quote; errors discard all tokens. No expansion or comments.",
    [({"chunks": [" a' b'\"c\" ", "'' x\\ y"]}, {"tokens": ["a bc", "", "x y"]}), ({"chunks": ["ok \\"]}, {"error": "trailing_escape"})],
    [{"chunks": x} for x in [[], [""], ["\t\n "], ["'a\\b'"], ['"a\\"b"'], ['"bad'], ["a\\", "\nb"], ["a", "'", "b", "'c"], ["''\"\""], ["one\r\ntwo"]]])

_task("D02", "Deterministic wildcard document queries", "query", "Input {document:JSON,paths:[segment arrays]}. Return an array of result arrays, one per path. Empty path selects the entire document. A string segment selects an object key; an integer segment selects an array index only when nonnegative and in range (booleans are not integer indices). '*' instead selects all immediate object children by lexicographically sorted key, or array children in original order. Continue each branch and concatenate depth-first. A missing key, scalar traversal or wrong index type yields zero matches on that branch. '*' always denotes wildcard and cannot select a literal star key.",
    [({"document": {"b": {"x": 2}, "a": {"x": 1}}, "paths": [["*", "x"], []]}, [[1, 2], [{"b": {"x": 2}, "a": {"x": 1}}]]), ({"document": [10, 20], "paths": [[True], [-1], [1], ["*"]]}, [[], [], [20], [10, 20]])],
    [{"document": doc, "paths": [[], ["*"], ["*", "*"], ["a", 0], ["missing"], [0]]} for doc in [None, 7, {}, [], {"a": [1, 2], "z": [3]}, [[1], [2, 3]], {"*": 1}, {"a": [{"x": 4}]}]])

_task("D03", "Recursive configuration interpolation", "normalization", "Input {variables:{name:string},targets:[names]}; return an array of per-target results. Recursively substitute '${NAME}' where NAME matches [A-Za-z_][A-Za-z0-9_]*. '$${' becomes literal '${' and its following text is not expanded on a second pass. Everything not matched by these tokens stays literal. Evaluate matches left to right and stop at the first failure. Success {value:string}; unknown variable {error:'missing',name}; cycle {error:'cycle',path:[cycle names including repeated final name]}, using the active recursion suffix from the first repeated variable. Each target has independent evaluation; no external environment.",
    [({"variables": {"A": "${B}:$${B}", "B": "ok"}, "targets": ["A", "Z"]}, [{"value": "ok:${B}"}, {"error": "missing", "name": "Z"}]), ({"variables": {"A": "${B}", "B": "${C}", "C": "${B}"}, "targets": ["A"]}, [{"error": "cycle", "path": ["B", "C", "B"]}])],
    [{"variables": v, "targets": targets} for v, targets in [({}, []), ({"A": ""}, ["A"]), ({"A": "${A}"}, ["A"]), ({"A": "${BAD-NAME}"}, ["A"]), ({"A": "$${X}${B}", "B": "2"}, ["A"]), ({"A": "${X}${Y}"}, ["A"]), ({"A": "${B}${B}", "B": "x"}, ["A", "B"]), ({"A": "$$${B}", "B": "v"}, ["A"])]] )

_task("D04", "Semantic-version range filtering", "versioning", "Input {versions:[strings],clauses:[[ {op,version} ]]}: each clause is AND, clauses are OR; op is =,<,<=,>,>= and comparator versions are valid. Implement SemVer 2 precedence: major/minor/patch nonnegative decimals without leading zero; prerelease dot identifiers ASCII alphanumeric or hyphen, numeric identifiers without leading zero; optional build identifiers use same characters but permit numeric leading zero. Release outranks prerelease; numeric prerelease identifiers compare numerically below nonnumeric, nonnumeric lexicographically; shorter equal prefix ranks lower. Build metadata does not affect precedence. A prerelease candidate can match a clause only if that clause has a prerelease comparator with the same major/minor/patch. Empty clause admits all releases. Return {accepted:[original strings sorted ascending by precedence, stable ties],invalid:[original invalid indices]}. No loose parsing.",
    [({"versions": ["1.0.0", "1.0.0-alpha.2", "1.0.0-alpha.10", "01.0.0"], "clauses": [[{"op": ">=", "version": "1.0.0-alpha.2"}]]}, {"accepted": ["1.0.0-alpha.2", "1.0.0-alpha.10", "1.0.0"], "invalid": [3]}), ({"versions": ["2.0.0-rc", "1.0.0+b", "1.0.0+a"], "clauses": [[]]}, {"accepted": ["1.0.0+b", "1.0.0+a"], "invalid": []})],
    [{"versions": vals, "clauses": clauses} for vals, clauses in [([], [[]]), (["0.0.0", "1.2.3"], []), (["1.0.0-a", "1.0.0-1", "1.0.0-1.a", "1.0.0"], [[{"op": "<", "version": "1.0.0"}]]), (["1.0.0-01", "1.0.0+01", "v1.0.0", "1.0"], [[]]), (["1.0.0-alpha", "1.0.1-alpha", "1.0.1"], [[{"op": ">=", "version": "1.0.0-alpha"}]]), (["1.0.0-z", "1.0.0-a", "1.0.0-10", "1.0.0-2"], [[{"op": ">=", "version": "1.0.0-0"}]]), (["2.0.0", "1.0.0", "3.0.0"], [[{"op": ">", "version": "1.0.0"}, {"op": "<", "version": "3.0.0"}]]), (["1.0.0", "2.0.0", "3.0.0"], [[{"op": "=", "version": "1.0.0"}], [{"op": ">=", "version": "3.0.0"}]] )]])

_task("D05", "Base-coordinate three-way edit merge", "editing", "Input {base:string,left:[edits],right:[edits]}, edit {start,end,text} uses Python Unicode code-point half-open offsets into base. Each side is individually valid, ordered by (start,end), and has no internally conflicting edits. Identical edits on both sides coalesce. Two nonidentical edits conflict if their positive-length spans overlap, both insert at the same point, or an insertion is strictly inside the other span. Insertions at replacement boundaries do not conflict. Return {conflicts:[[left index,right index]]} in left-then-right index order if any conflict; otherwise {text:merged}. Merge edits by ascending (start,end), placing insertions before positive spans with the same start. Both endpoints 0 and len(base) are valid.",
    [({"base": "abcdef", "left": [{"start": 1, "end": 3, "text": "X"}], "right": [{"start": 3, "end": 3, "text": "!"}]}, {"text": "aX!def"}), ({"base": "abcd", "left": [{"start": 1, "end": 3, "text": "X"}], "right": [{"start": 2, "end": 2, "text": "Y"}]}, {"conflicts": [[0, 0]]})],
    [{"base": base, "left": l, "right": r} for base, l, r in [("", [], []), ("abc", [{"start": 0, "end": 0, "text": "!"}], []), ("abc", [{"start": 1, "end": 2, "text": "X"}], [{"start": 1, "end": 2, "text": "X"}]), ("abc", [{"start": 1, "end": 1, "text": "X"}], [{"start": 1, "end": 1, "text": "Y"}]), ("abcd", [{"start": 0, "end": 2, "text": ""}], [{"start": 2, "end": 4, "text": ""}]), ("abc", [{"start": 0, "end": 2, "text": "X"}], [{"start": 0, "end": 0, "text": "!"}]), ("abc", [], [{"start": 3, "end": 3, "text": "?"}]), ("abcdef", [{"start": 0, "end": 3, "text": "x"}, {"start": 4, "end": 5, "text": "y"}], [{"start": 2, "end": 5, "text": "z"}])]])

_task("D06", "Transactional contextual line splices", "editing", "Input {lines:[strings],operations:[{at,remove:[strings],insert:[strings]}]}. Apply operations sequentially to a private line-array copy; at is an integer boundary in the current array. at outside 0..current length or a boolean returns {error:'range',operation:index}. Otherwise require the full remove sequence to equal current lines starting at at; mismatch or running past EOF returns {error:'context',operation:index}. Replace that sequence with insert. Empty remove inserts; at==length can append. On first failure return only the error, publishing no partial lines. On success return {lines:[strings]}. Lines are opaque strings and may be empty or contain newline characters.",
    [({"lines": ["a", "b"], "operations": [{"at": 1, "remove": ["b"], "insert": ["x", "y"]}, {"at": 2, "remove": ["y"], "insert": []}]}, {"lines": ["a", "x"]}), ({"lines": ["a"], "operations": [{"at": 1, "remove": ["b"], "insert": []}]}, {"error": "context", "operation": 0})],
    [{"lines": ls, "operations": ops} for ls, ops in [([], []), ([], [{"at": 0, "remove": [], "insert": ["a"]}]), (["a"], [{"at": -1, "remove": [], "insert": []}]), (["a"], [{"at": True, "remove": [], "insert": []}]), (["a"], [{"at": 2, "remove": [], "insert": []}]), (["a", "b"], [{"at": 0, "remove": ["a"], "insert": []}, {"at": 1, "remove": [], "insert": ["c"]}]), (["", "x\ny"], [{"at": 0, "remove": ["", "x\ny"], "insert": ["z"]}]), (["a"], [{"at": 0, "remove": ["a"], "insert": ["b"]}, {"at": 0, "remove": ["a"], "insert": []}])]])

_task("D07", "Strict multiline CSV parser", "parsing", "Input {text:string}; return {rows:[[strings]]}. Comma separates fields; LF or CRLF separates records outside quoted fields; bare CR outside quotes is error. Quote may begin only at field start. In quoted fields comma/CR/LF are literal; double quote escapes a quote. Closing quote must be followed by comma, record end or EOF. Empty input has no rows, a final record terminator does not add a phantom row, but a blank record is ['']. Leading/trailing empty comma fields are preserved. Errors discard all rows: {error:'bare_cr'|'after_quote'|'quote_in_field'|'unclosed_quote',offset:code-point index}; unclosed quote offset is len(text), other offsets identify offending character. No whitespace trimming.",
    [({"text": 'a,"b\n c",\r\n'}, {"rows": [["a", "b\n c", ""]]}), ({"text": '"x" y'}, {"error": "after_quote", "offset": 3})],
    [{"text": s} for s in ["", "\n", ",", '""', '"a""b",c', 'a"b', 'a\rb', '"a\rb"', '"bad', 'a\n\n', 'a,b\r\nc,d']])

_task("D08", "Strict query-string reconciliation", "normalization", "Input {queries:[strings],remove:[decoded keys],set:[[decoded key,decoded value]]}. Concatenate query pairs in input order; an empty query contributes none, otherwise split '&' preserving empty fields, and split each field on first '=' (missing '=' means empty value). Decode '+' as space and percent bytes as strict UTF-8; malformed percent escape or invalid UTF-8 returns {error:'decode',query:input query index} before edits. Remove all pairs with each remove key. Apply set operations in order: delete all existing equal-key pairs and insert one replacement at the first former position, or append if absent. Return {pairs:[[key,value]],query:canonical encoding}; canonical UTF-8 percent encoding uses uppercase hex, spaces %20, unescaped only ASCII letters/digits/-._~, always includes '='. No URL parsing or '?' stripping.",
    [({"queries": ["a=1&a=2&b=x+y"], "remove": [], "set": [["a", "3"]]}, {"pairs": [["a", "3"], ["b", "x y"]], "query": "a=3&b=x%20y"}), ({"queries": ["ok=1", "x=%FF"], "remove": [], "set": []}, {"error": "decode", "query": 1})],
    [{"queries": qs, "remove": rm, "set": st} for qs, rm, st in [([], [], []), ([""], [], []), (["&"], [], []), (["k=a=b"], [], []), (["x=%"], [], []), (["x=%E2%82%AC"], [], [["z", "a/b"]]), (["a=1&b=2&a=3"], ["a"], [["a", "4"]]), (["a=1&b=2&c=3"], [], [["b", "x"], ["b", "y"], ["q", "!"]])]])

_task("D09", "Revision-aware tombstone log reducer", "data", "Input {events:[{key:string,revision:nonnegative integer,op:'put'|'delete',value:JSON for put}]}. Process in input order. First event for a key wins initially; later event replaces it only when revision is strictly greater. Equal or lower revision events are ignored even if operation differs. Deletes retain tombstone revisions so stale puts cannot resurrect. Return {items:[{key,revision,value}],tombstones:[{key,revision}],ignored:[original indices]}, items and tombstones independently sorted by key, ignored ascending input order. Keys can be empty. No compaction or revision arithmetic.",
    [({"events": [{"key": "x", "revision": 2, "op": "delete"}, {"key": "x", "revision": 1, "op": "put", "value": 5}, {"key": "x", "revision": 3, "op": "put", "value": None}]}, {"items": [{"key": "x", "revision": 3, "value": None}], "tombstones": [], "ignored": [1]}), ({"events": [{"key": "b", "revision": 0, "op": "put", "value": 1}, {"key": "b", "revision": 0, "op": "delete"}]}, {"items": [{"key": "b", "revision": 0, "value": 1}], "tombstones": [], "ignored": [1]})],
    [{"events": ev} for ev in [[], [{"key": "", "revision": 0, "op": "delete"}], [{"key": "z", "revision": 2, "op": "put", "value": []}, {"key": "a", "revision": 1, "op": "put", "value": {}}], [{"key": "k", "revision": n, "op": "put", "value": n} for n in range(5)], [{"key": "k", "revision": n, "op": "delete"} for n in range(4, -1, -1)], [{"key": "a", "revision": 1, "op": "delete"}, {"key": "b", "revision": 9, "op": "delete"}], [{"key": "x", "revision": 1, "op": "put", "value": 0}, {"key": "x", "revision": 2, "op": "delete"}], [{"key": str(n % 3), "revision": n % 4, "op": "put", "value": n} for n in range(15)]]])

_task("D10", "Atomic JSON Pointer patch engine", "editing", "Input {document:JSON,operations:[{op,path,value?}]} with op add/remove/replace/test. Apply sequentially to a deep copy. JSON Pointer root is ''; other paths begin '/', splitting tokens then decoding ~1 to slash and ~0 to tilde. Any other '~' escape is invalid. Objects accept exact keys including empty. Array indices use canonical decimal '0' or nonzero digits without leading zero; negative indices forbidden. Array add inserts at 0..length, '-' appends only for add; other ops require existing index. Object add inserts or replaces; replace/remove/test require existing member. Missing parents, scalar traversal, unknown op or malformed pointer fail. Root add/replace replace document, root remove sets document to null. Test compares JSON structurally with object order ignored, numbers equal numerically, but booleans distinct from numbers. First failure returns {error:'patch',operation:index,document:original document}; success {document:new document}. All mutation is transactional.",
    [({"document": {"a/b": [1, 2]}, "operations": [{"op": "add", "path": "/a~1b/1", "value": 9}, {"op": "remove", "path": "/a~1b/0"}]}, {"document": {"a/b": [9, 2]}}), ({"document": [1], "operations": [{"op": "add", "path": "/-", "value": 2}, {"op": "test", "path": "/0", "value": True}]}, {"error": "patch", "operation": 1, "document": [1]})],
    [{"document": doc, "operations": ops} for doc, ops in [(None, [{"op": "add", "path": "", "value": {"x": 1}}]), ({"": 4}, [{"op": "replace", "path": "/", "value": 5}]), ([1], [{"op": "replace", "path": "/01", "value": 3}]), ({"x": 1}, [{"op": "remove", "path": "/missing"}]), ({"x": [1]}, [{"op": "add", "path": "/x/1", "value": 2}]), ({"~": 1}, [{"op": "test", "path": "/~0", "value": 1}]), ({}, [{"op": "add", "path": "/~2", "value": 1}]), ({"x": 1}, [{"op": "remove", "path": ""}]), (True, [{"op": "test", "path": "", "value": 1}])]])

_task("D11", "Priority interval-map normalization", "data", "Input {ranges:[{start:int,end:int,priority:int,value:JSON}]}, with start<=end. Ranges are half-open; zero-length ranges have no effect. At every covered point select the covering range with highest priority, and among equal priorities the latest input index. Return maximal ordered nonempty {start,end,value} segments, omitting uncovered gaps. Adjacent selected segments with structurally equal JSON values coalesce even if winners differ; boolean differs from numeric, object key order does not matter. Endpoints can be negative, values can be null; do not enumerate individual coordinate points.",
    [({"ranges": [{"start": 0, "end": 10, "priority": 1, "value": "a"}, {"start": 3, "end": 5, "priority": 2, "value": "b"}]}, [{"start": 0, "end": 3, "value": "a"}, {"start": 3, "end": 5, "value": "b"}, {"start": 5, "end": 10, "value": "a"}]), ({"ranges": [{"start": 0, "end": 2, "priority": 1, "value": 0}, {"start": 1, "end": 3, "priority": 1, "value": 0}]}, [{"start": 0, "end": 3, "value": 0}])],
    [{"ranges": rs} for rs in [[], [{"start": 1, "end": 1, "priority": 5, "value": "x"}], [{"start": -5, "end": -1, "priority": 0, "value": None}], [{"start": 0, "end": 10**12, "priority": 0, "value": 1}], [{"start": 0, "end": 2, "priority": 0, "value": True}, {"start": 2, "end": 4, "priority": 0, "value": 1}], [{"start": 0, "end": 2, "priority": 1, "value": "a"}, {"start": 1, "end": 3, "priority": 1, "value": "b"}], [{"start": 0, "end": 1, "priority": 2, "value": "a"}, {"start": 2, "end": 3, "priority": 2, "value": "a"}], [{"start": n, "end": n+3, "priority": n % 2, "value": n % 3} for n in range(8)]]])

_task("D12", "Run-length stream normalization and slicing", "codec", "Input {runs:[{count:JSON,value:JSON}],start:int,end:int}. Reject first count that is not an integer (boolean is invalid) or is negative: {error:'count',run:index}. Remove zero-count runs and merge adjacent runs with structurally equal values (boolean distinct from number, object order ignored), preserving values. Return {runs:normalized runs,length:sum counts,slice:expanded half-open interval}. Clamp each requested endpoint below zero to zero and above total length through ordinary intersection; end<=start returns empty. Counts may be huge, but requested interval length is at most 100; never expand outside that slice.",
    [({"runs": [{"count": 2, "value": "a"}, {"count": 0, "value": "b"}, {"count": 3, "value": "a"}], "start": 1, "end": 4}, {"runs": [{"count": 5, "value": "a"}], "length": 5, "slice": ["a", "a", "a"]}), ({"runs": [{"count": True, "value": 0}], "start": 0, "end": 2}, {"error": "count", "run": 0})],
    [{"runs": rs, "start": a, "end": b} for rs, a, b in [([], 0, 10), ([{"count": -1, "value": "x"}], 0, 1), ([{"count": 10**12, "value": None}], 10**12-2, 10**12+2), ([{"count": 2, "value": 1}, {"count": 2, "value": True}], 0, 4), ([{"count": 2, "value": 1}], -3, 1), ([{"count": 2, "value": 1}], 2, 1), ([{"count": 0, "value": 1}], 0, 4), ([{"count": n % 4, "value": n % 2} for n in range(12)], 3, 10)]])

_task("D13", "Nested brace expansion with stable deduplication", "parsing", "Input {pattern:string}. Expand recursively nested braces using comma alternatives only inside braces; outside braces commas are literal. Adjacent literals/groups form Cartesian products, left prefix outer loop then right suffix inner loop. Backslash makes the next character literal everywhere and disappears; trailing backslash, unmatched braces or excessive expansion returns {error:'syntax_or_limit'}. A brace group with no comma acts as grouping; empty alternatives and empty groups produce empty string. Remove duplicate final strings preserving first occurrence. Return {values:[strings]}. Reject if any intermediate Cartesian product or a brace group's accumulated alternatives exceeds 256 entries, counting duplicates before final deduplication. No numeric ranges or environment expansion.",
    [({"pattern": "a{b,{c,d}}{1,2}"}, {"values": ["ab1", "ab2", "ac1", "ac2", "ad1", "ad2"]}), ({"pattern": "{x,x,}{y,}"}, {"values": ["xy", "x", "y", ""]})],
    [{"pattern": s} for s in ["", "{}", "a,b", r"\{a,b\}", "{a", "a}", "{a,{b,c}}", "{a,b}" * 9, "x\\", "{,a,,b}"]])

_task("D14", "Chunk-independent UTF-8 replacement decoder", "codec", "Input {chunks:[[byte integers 0..255]]}; concatenate bytes and return {text:string,errors:[starting byte offsets]}. Decode strict modern UTF-8; permit lead C2..DF, E0..EF and F0..F4 only. Valid second-byte ranges: E0 A0..BF; ED 80..9F; F0 90..BF; F4 80..8F; otherwise continuation 80..BF. Invalid lead consumes one byte and emits U+FFFD. Valid lead followed by invalid/restricted continuation or EOF consumes the lead plus all valid continuations preceding the failure, emits one U+FFFD, and resumes at the unconsumed offending byte. Thus errors identify each malformed maximal subpart, not every byte. Chunk boundaries never create errors. ASCII including NUL is preserved.",
    [({"chunks": [[0xE2], [0x82, 0xAC, 0x41]]}, {"text": "€A", "errors": []}), ({"chunks": [[0xE2, 0x82, 0x41, 0xFF]]}, {"text": "�A�", "errors": [0, 3]})],
    [{"chunks": chunks} for chunks in [[], [[]], [[0]], [[0xC0, 0xAF]], [[0xED, 0xA0, 0x80]], [[0xF0, 0x9F, 0x98, 0x80]], [[0xE2, 0x82]], [[0xF4, 0x90, 0x80, 0x80]], [[0xC2], [0xA2]], [[0xE0, 0xA0, 0x80], [0x7F]]]])

_task("D15", "Tab-aware block dedent and reindent", "editing", "Input {text:string,tab_width:positive int,indent:nonnegative int}. Split on LF preserving final empty line. Prefix indentation consists only of space/tab; space advances one column and tab advances to next multiple of tab_width from column zero. Determine minimum prefix column count among lines with non-space/tab content. For each such line replace indentation with spaces equal to original columns minus minimum plus indent, preserving content exactly. Blank lines become empty regardless of original indentation. Return {text:LF-joined transformed lines,removed_columns:minimum}; if all blank minimum is zero. CR is content, not a newline or indentation.",
    [({"text": "\talpha\n  beta\n \t", "tab_width": 4, "indent": 1}, {"text": "   alpha\n beta\n", "removed_columns": 2}), ({"text": " \t\n\t", "tab_width": 8, "indent": 3}, {"text": "\n", "removed_columns": 0})],
    [{"text": s, "tab_width": w, "indent": n} for s, w, n in [("", 4, 0), ("a\n b", 4, 2), ("\t x\n    y", 4, 0), ("\t\tfoo\n\tbar", 3, 1), ("  a\n", 8, 0), ("  a\r\n  b", 4, 1), (" \t x", 4, 0), (" x\n \t y\n  z", 2, 4)]])

_task("D16", "Recursive schema defaults with deterministic diagnostics", "data", "Input {value:JSON,schema:node}. Schema type is object,array,string,integer,boolean,null. Boolean is not integer. Type mismatch emits {path,error:'type'} and leaves that node unchanged without descending. Object schema has optional properties map, required name list, additional bool default true. Visit property names in sorted order: missing property with default is inserted by deep copy then validated; otherwise missing required emits 'required'; otherwise skip. Validate present known properties recursively, then emit 'additional' for unknown original properties in sorted order when additional:false, retaining them. Arrays validate items left to right via schema.items. Integer minimum/maximum inclusive violations emit 'range', then scalar enum membership violations emit 'enum'. Defaults may themselves be invalid. Paths are JSON Pointers with ~ and / escaped; root ''. Return {value:default-filled value,errors:[diagnostics in traversal order]}; validation errors do not roll back defaults.",
    [({"value": {"z": 1}, "schema": {"type": "object", "properties": {"a": {"type": "integer", "default": 2}}, "required": ["a"], "additional": False}}, {"value": {"z": 1, "a": 2}, "errors": [{"path": "/z", "error": "additional"}]}), ({"value": [True, 4], "schema": {"type": "array", "items": {"type": "integer", "maximum": 3}}}, {"value": [True, 4], "errors": [{"path": "/0", "error": "type"}, {"path": "/1", "error": "range"}]})],
    [{"value": val, "schema": schema} for val, schema in [(None, {"type": "null"}), (2, {"type": "object"}), ({}, {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}), ({}, {"type": "object", "properties": {"a/b": {"type": "integer", "default": "bad"}}}), ([1, 2, 3], {"type": "array", "items": {"type": "integer", "enum": [1, 3]}}), ({"x": {}}, {"type": "object", "properties": {"x": {"type": "object", "properties": {"y": {"type": "boolean", "default": False}}}}}), (0, {"type": "integer", "minimum": 1, "enum": [2]}), ({"~": True, "x": 2}, {"type": "object", "properties": {}, "additional": False})]])

_task("D17", "Conflict-detecting path unflattening", "data", "Input {items:[{path:[string keys],value:JSON}]}. Build an object tree from paths. Empty path fails {error:'empty_path',item:index}. Every supplied value is a leaf even if it is an object. At first conflict: exact duplicate path or a new path that is a prefix of any prior path returns {error:'duplicate_or_prefix',item:index}; a prior path that is a strict prefix of new path returns {error:'prefix',item:index}. Otherwise construct missing intermediate objects. Success {document:tree,flat:[{path,value}]}: flatten the constructed tree recursively in sorted key order, treating empty objects and all nonobjects as leaves. Supplied object leaves are recursively flattened on output, although they remain indivisible for insertion conflict detection. Empty input yields document {} and flat [{path:[],value:{}}]. Keys including empty, slash and tilde are literal.",
    [({"items": [{"path": ["b", "x"], "value": 2}, {"path": ["a"], "value": {}}]}, {"document": {"b": {"x": 2}, "a": {}}, "flat": [{"path": ["a"], "value": {}}, {"path": ["b", "x"], "value": 2}]}), ({"items": [{"path": ["a"], "value": {}}, {"path": ["a", "b"], "value": 1}]}, {"error": "prefix", "item": 1})],
    [{"items": items} for items in [[], [{"path": [], "value": 0}], [{"path": ["x"], "value": 1}, {"path": ["x"], "value": 1}], [{"path": ["x", "y"], "value": 1}, {"path": ["x"], "value": 2}], [{"path": [""], "value": []}], [{"path": ["a"], "value": {"z": 1, "b": 2}}], [{"path": ["a", "b"], "value": 1}, {"path": ["a", "c"], "value": 2}], [{"path": ["/", "~"], "value": None}]]])

_task("D18", "Deterministic route specificity resolver", "query", "Input {path:absolute slash-separated string,routes:[{id,pattern}]}. Split path and patterns on slash after initial slash, preserving empty/trailing segments; do not decode, normalize or treat query specially. Literal pattern segments match exactly. ':name' matches exactly one segment (even empty). Final '*name' matches remaining zero or more segments and captures their slash-joined text. Names are unique per route; patterns valid and wildcard only final. A successful route must consume the full path. Choose highest count of literal segments, then nongreedy before greedy, then fewest ':name' segments, then earliest input route. Return {id,parameters:{name:string}} or null. Literal '*' and ':' segment prefixes are reserved.",
    [({"path": "/a/b", "routes": [{"id": "wild", "pattern": "/a/*rest"}, {"id": "param", "pattern": "/a/:x"}, {"id": "exact", "pattern": "/a/b"}]}, {"id": "exact", "parameters": {}}), ({"path": "/a", "routes": [{"id": "r", "pattern": "/a/*rest"}]}, {"id": "r", "parameters": {"rest": ""}})],
    [{"path": path, "routes": routes} for path, routes in [("/", []), ("/", [{"id": "root", "pattern": "/"}]), ("/a/", [{"id": "r", "pattern": "/a/:x"}]), ("/a/b/c", [{"id": "r", "pattern": "/a/:x"}]), ("/a/b", [{"id": "x", "pattern": "/:p/b"}, {"id": "y", "pattern": "/a/:q"}]), ("/a//c", [{"id": "r", "pattern": "/a/*tail"}]), ("/%2F", [{"id": "r", "pattern": "/:x"}]), ("/a", [{"id": "x", "pattern": "/*rest"}, {"id": "y", "pattern": "/:p"}])]])

_task("D19", "Stable duplicate-preserving relational join", "data", "Input {left:[objects],right:[objects],key:string,mode:'inner'|'left'|'full'}. Join by exact structurally equal key values; booleans distinct from numeric, object order ignored. Missing or null key never matches, including another null. For each left row in input order emit {left:row,right:matched row} for every matching right row in right input order, preserving duplicate Cartesian multiplicities. Unmatched left rows emit right:null only in left/full modes. Full mode then appends every unmatched right row in input order with left:null. Return the result array; no row fields are merged or deduplicated.",
    [({"left": [{"k": 1}, {"k": None}], "right": [{"k": 1, "v": "a"}, {"k": 1, "v": "b"}, {}], "key": "k", "mode": "full"}, [{"left": {"k": 1}, "right": {"k": 1, "v": "a"}}, {"left": {"k": 1}, "right": {"k": 1, "v": "b"}}, {"left": {"k": None}, "right": None}, {"left": None, "right": {}}]), ({"left": [{"k": True}], "right": [{"k": 1}], "key": "k", "mode": "inner"}, [])],
    [{"left": l, "right": r, "key": "k", "mode": mode} for l, r, mode in [([], [], "full"), ([], [{"k": 2}], "left"), ([], [{"k": 2}], "full"), ([{}], [{}], "inner"), ([{"k": [1]}], [{"k": [1]}], "inner"), ([{"k": 1}, {"k": 1}], [{"k": 1}, {"k": 1}], "inner"), ([{"k": 0}, {"k": 2}], [{"k": 1}], "left"), ([{"k": {"b": 2, "a": 1}}], [{"k": {"a": 1, "b": 2}}], "full")]])

_task("D20", "Atomic ordered row-schema migrations", "data", "Input {rows:[objects],operations:[operations]}. Process rows in original order, applying all operations sequentially per row. rename {field,to}: absent source no-op; if source present and distinct destination present fail collision; identical names no-op. default {field,value}: deep-copy default only if field absent (null counts present). drop {field}: remove if present. integer {field}: absent no-op; existing integer (not bool) stays; string must match [+-]?(0|[1-9][0-9]*) exactly and becomes base-10 integer; all other values fail integer. On first failure return {error:'collision'|'integer',row:index,operation:index} with no partial rows. Success {rows:transformed rows}. Operations see previous changes, and row-major failure order matters.",
    [({"rows": [{"old": "-2"}, {}], "operations": [{"op": "rename", "field": "old", "to": "n"}, {"op": "default", "field": "n", "value": "3"}, {"op": "integer", "field": "n"}]}, {"rows": [{"n": -2}, {"n": 3}]}), ({"rows": [{"a": 1, "b": 2}], "operations": [{"op": "rename", "field": "a", "to": "b"}]}, {"error": "collision", "row": 0, "operation": 0})],
    [{"rows": rows, "operations": ops} for rows, ops in [([], []), ([{"x": None}], [{"op": "default", "field": "x", "value": 1}]), ([{"x": True}], [{"op": "integer", "field": "x"}]), ([{"x": "01"}], [{"op": "integer", "field": "x"}]), ([{"x": "+0"}, {"x": "-0"}], [{"op": "integer", "field": "x"}]), ([{"x": 1}], [{"op": "rename", "field": "x", "to": "x"}, {"op": "drop", "field": "missing"}]), ([{}, {}], [{"op": "default", "field": "x", "value": []}]), ([{"x": "2"}, {"x": " 2"}], [{"op": "integer", "field": "x"}, {"op": "drop", "field": "x"}])]])

_task("D21", "Grouped bucket aggregation with causal filling", "data", "Input {events:[{group:string,time:int,value:int|null}],start:int,end:int,width:positive int,fill:'none'|'previous'}, start<=end. Groups are all unique event group names sorted lexicographically, including groups with no in-range events. For each group, emit buckets starting start,start+width,... strictly below end, each covering [bucketStart,min(bucketStart+width,end)). Sum only non-null in-range values; count counts these values. A nonempty bucket has value=sum and becomes previous value. Empty bucket value is null for fill none, or latest previous nonempty bucket sum for fill previous (null before first); empty buckets never reset previous. Events before start never seed previous. Return [{group,start,count,value}] in group then bucket order. Zero sum is a real previous value, duplicates are counted.",
    [({"events": [{"group": "a", "time": 0, "value": 2}, {"group": "a", "time": 1, "value": -2}], "start": 0, "end": 5, "width": 2, "fill": "previous"}, [{"group": "a", "start": 0, "count": 2, "value": 0}, {"group": "a", "start": 2, "count": 0, "value": 0}, {"group": "a", "start": 4, "count": 0, "value": 0}]), ({"events": [{"group": "z", "time": -1, "value": 9}], "start": 0, "end": 1, "width": 2, "fill": "previous"}, [{"group": "z", "start": 0, "count": 0, "value": None}])],
    [{"events": events, "start": a, "end": b, "width": w, "fill": fill} for events, a, b, w, fill in [([], 0, 5, 1, "none"), ([{"group": "x", "time": 0, "value": 1}], 1, 1, 2, "none"), ([{"group": "x", "time": 1, "value": None}], 0, 3, 1, "previous"), ([{"group": "x", "time": 2, "value": 4}], 0, 4, 2, "none"), ([{"group": "b", "time": 0, "value": 2}, {"group": "a", "time": 0, "value": 1}], 0, 1, 1, "none"), ([{"group": "x", "time": 3, "value": 9}], 0, 3, 2, "previous"), ([{"group": "x", "time": -2, "value": 3}], -3, 0, 2, "none"), ([{"group": str(i % 2), "time": i % 5, "value": i-5} for i in range(10)], 0, 6, 2, "previous")]])

_task("D22", "ANSI-aware stable greedy line wrapping", "editing", "Input {text:string,width:positive int}. Split words on Python Unicode whitespace; discard leading/trailing whitespace and collapse interword spacing to one ASCII space. ANSI SGR escape sequences matching ESC '[' [0-9;]* 'm' have display width zero and remain verbatim; every other Unicode code point, including unmatched escapes, has width one. Greedily pack full words: append with one space if width fits, otherwise finish current line and begin next word. Never split a word; an overlong word gets its own line. No color-state propagation or terminal grapheme rules. Return {lines:[strings],widths:[display widths]}; empty/all-whitespace produces empty arrays.",
    [({"text": "\u001b[31mred\u001b[0m blue z", "width": 6}, {"lines": ["\u001b[31mred\u001b[0m", "blue z"], "widths": [3, 6]}), ({"text": "abcdef x y", "width": 3}, {"lines": ["abcdef", "x y"], "widths": [6, 3]})],
    [{"text": s, "width": w} for s, w in [("", 1), (" \t\n", 2), ("a b", 3), ("a b", 2), ("a\u00a0b\tc", 5), ("\u001b[mA\u001b[0m B", 3), ("\u001b[2JA b", 5), ("😀 x", 3), ("\u001b[31m \u001b[0m", 1)]])

_task("D23", "Structured log key-value lexer", "parsing", "Input {text:string}. Parse whitespace-separated key=value pairs; separators are only ASCII space and tab. Key must match [A-Za-z_][A-Za-z0-9_]* immediately followed by '='. Unquoted values run until separator and may be empty; characters including '=' and quote are literal inside them. A value beginning double quote is quoted: spaces/tabs literal, close quote required, with only backslash escapes n,t,double quote,backslash mapped to newline,tab,quote,backslash. Closing quote must be followed by separator or EOF. Return {pairs:[[key,value]],last:{key:last value}}, preserving duplicate pairs. First error returns {error:'key'|'escape'|'quote'|'separator',offset:code-point index}: key begins at offending token; bad escape at escaped character (EOF=len); missing quote EOF=len; separator at first character after close quote. No partial pairs.",
    [({"text": 'a=1 b="x y" a=2'}, {"pairs": [["a", "1"], ["b", "x y"], ["a", "2"]], "last": {"a": "2", "b": "x y"}}), ({"text": 'x="a"b'}, {"error": "separator", "offset": 5})],
    [{"text": s} for s in ["", " \t", "a=", "1x=y", 'x="bad', 'x="\\q"', 'x="a\\', 'x="a\\n\\t\\\"\\\\"', 'a=x=y b=z"k', "a=x\nb=y"]])

_task("D24", "Atomic UTF-16-coordinate text delta", "editing", "Input {text:string,edits:[{start:int,end:int,text:string}]} with code-point strings containing no isolated surrogates. Offsets count UTF-16 code units in the original text: BMP characters count one, supplementary characters count two. Half-open endpoints must be valid character boundaries in 0..total units; reversed span or invalid boundary returns {error:'boundary',edit:index}. Validate in input order: after boundary check, an edit whose start is less than previous edit's end returns {error:'overlap',edit:index}, covering overlaps and backwards ordering. Adjacent edits and multiple zero-length inserts at the same point are allowed in input order. After all validation, simultaneously splice original-coordinate edits and return {text:result}; no partial output or sequential coordinate shift.",
    [({"text": "A😀B", "edits": [{"start": 1, "end": 3, "text": "x"}, {"start": 3, "end": 3, "text": "!"}]}, {"text": "Ax!B"}), ({"text": "😀", "edits": [{"start": 1, "end": 2, "text": ""}]}, {"error": "boundary", "edit": 0})],
    [{"text": s, "edits": es} for s, es in [("", []), ("", [{"start": 0, "end": 0, "text": "x"}]), ("abc", [{"start": 1, "end": 1, "text": "x"}, {"start": 1, "end": 1, "text": "y"}]), ("abc", [{"start": 0, "end": 2, "text": ""}, {"start": 1, "end": 3, "text": "z"}]), ("abc", [{"start": 3, "end": 2, "text": "x"}]), ("😀😀", [{"start": 0, "end": 2, "text": ""}, {"start": 2, "end": 4, "text": "x"}]), ("a\nb", [{"start": 1, "end": 2, "text": "\r\n"}]), ("abc", [{"start": 4, "end": 4, "text": "x"}])]])

_task("D25", "Stable multiset record reconciliation", "data", "Input {before:[objects],after:[objects],key:string}; every row has key. Traverse before rows in order and match each to the earliest still-unused after row whose key is structurally equal, with booleans distinct from numbers and object key order ignored. For each match emit {before:index,after:index,changed:[field names]} where changed is sorted union of field names whose presence differs or whose JSON values differ structurally. Duplicate key occurrences are paired one-for-one, never by best similarity. Return {matched:[matches in before order],removed:[unmatched before indices],added:[unused after indices]}, removed/added ascending. Missing field differs from present null. Rows are not mutated.",
    [({"before": [{"k": 1, "x": 1}, {"k": 1, "x": 2}], "after": [{"k": 1, "x": 2}], "key": "k"}, {"matched": [{"before": 0, "after": 0, "changed": ["x"]}], "removed": [1], "added": []}), ({"before": [{"k": True}], "after": [{"k": 1}], "key": "k"}, {"matched": [], "removed": [0], "added": [0]})],
    [{"before": a, "after": b, "key": "k"} for a, b in [([], []), ([], [{"k": 1}]), ([{"k": None}], [{"k": None}]), ([{"k": 1}], [{"k": 1, "x": None}]), ([{"k": 1, "x": None}], [{"k": 1}]), ([{"k": [1], "v": {"x": 1, "y": 2}}], [{"k": [1], "v": {"y": 2, "x": 1}}]), ([{"k": 1}, {"k": 2}], [{"k": 2}, {"k": 1}]), ([{"k": 1}, {"k": 1}], [{"k": 1}, {"k": 1}, {"k": 1}])]])

_task("D26", "Stable Unicode natural ordering", "normalization", "Input {values:[strings]}; return sorted original strings. Tokenize each into maximal ASCII-digit [0-9]+ runs or maximal non-ASCII-digit runs. Numeric tokens compare by arbitrary-precision integer value, ignoring leading zeros. Text tokens compare by Python Unicode casefold lexicographic order. At a corresponding position numeric token sorts before text token. Tokens compare left-to-right; shorter equal token sequence sorts first. Completely equal token keys keep original input order (do not add spelling or zero-count tie breaks). Non-ASCII digits are text; empty string has no tokens. No locale, normalization, decimals or negative-number parsing.",
    [({"values": ["a10", "A2", "a02", "a1", "a"]}, ["a", "a1", "A2", "a02", "a10"]), ({"values": ["x٢", "x2", "x02", "X2"]}, ["x2", "x02", "X2", "x٢"])],
    [{"values": v} for v in [[], ["", "a", "0"], ["10", "2", "001", "1"], ["Straße2", "STRASSE2", "straße10"], ["x1a2", "x1a10", "x1"], ["-2", "-10", "2"], ["A", "a", "B", "b"], ["n" + str(10**30), "n9", "n0009"]]])

_task("D27", "Strict duplicate-safe canonical JSON codec", "codec", "Input {text:string}; parse exactly one JSON value allowing surrounding JSON whitespace. Duplicate object keys anywhere are rejected as {error:'duplicate_key'}. Other syntax errors, including NaN/Infinity, return {error:'syntax'}. Valid JSON containing any floating-point number (fraction or exponent) or any isolated surrogate code point in a decoded key/string is rejected as {error:'unsupported'}. Accepted data has null/bool/integer/string/array/object only; integers arbitrary precision. Return {value:parsed JSON,canonical:string}, canonical using lexicographically sorted object keys recursively, no spaces, Unicode emitted literally, quotes/backslashes/control characters escaped as Python json.dumps(ensure_ascii=False,sort_keys=True,separators=(',',':')). Do not ASCII-escape ordinary Unicode or escape slash. Test inputs do not combine duplicate keys with unrelated syntax errors.",
    [({"text": ' {"z":2,"a":"é"} '}, {"value": {"z": 2, "a": "é"}, "canonical": '{"a":"é","z":2}'}), ({"text": '{"a":1,"a":2}'}, {"error": "duplicate_key"})],
    [{"text": s} for s in ["null", "[true,0,-2]", '{"x":{"a":1,"a":2}}', "1.0", "1e2", "NaN", '"\\ud800"', '{"x":"\\n/"}', "{} {}", "123456789012345678901234567890"]])

_task("D28", "Escaped binary-frame stream decoder", "codec", "Input {chunks:[[byte integers]]}; concatenate bytes. Delimiter 0x7E starts and ends frames; before first delimiter ignore bytes. Inside frame, 0x7D escapes next nondelimiter byte by XOR 0x20. A delimiter always ends current frame and starts a new one, even after escape. Empty frames are ignored. Decoded frame is [length byte,payload bytes...,checksum byte]; require at least two bytes else 'short', exact payload length else 'length', checksum equal sum(length+payload) modulo 256 else 'checksum'. A delimiter encountered with pending escape emits 'escape' instead of parsing frame. At EOF any nonempty current frame or pending escape emits 'incomplete' (no parse); bare final delimiter adds none. Return {frames:[valid payload arrays],errors:[error strings in encounter order]}. Malformed frames do not discard earlier valid frames; chunk boundaries have no effect.",
    [({"chunks": [[126, 2, 1], [2, 5, 126]]}, {"frames": [[1, 2]], "errors": []}), ({"chunks": [[9, 126, 1, 125, 94, 127, 126]]}, {"frames": [[126]], "errors": []})],
    [{"chunks": chunks} for chunks in [[], [[126]], [[126, 126]], [[126, 0, 0, 126]], [[126, 1, 126]], [[126, 2, 3, 5, 126]], [[126, 1, 2, 0, 126]], [[126, 125, 126]], [[126, 1, 2, 3]], [[126, 1, 125], [93, 126, 126]], [[126, 0, 0, 126, 1, 2, 3, 126]]]])

_task("D29", "Revision-compacted keyset pagination", "query", "Input {rows:[{id:string,revision:int,score:int,deleted?:bool,...}],minimum:int,cursor:null|[score,id],limit:positive int}. Compact by id selecting greatest revision; tied revision keeps earliest input row. Drop latest rows with deleted:true, then filter score>=minimum. Sort score descending then id lexicographically ascending. Cursor is exclusive using this same order: retain rows ordered strictly after cursor, whether or not cursor row exists. Return {rows:first limit complete original row objects,next:null|[score,id]}; next is last returned row's cursor only if additional rows remain after page, otherwise null. Filter/compaction happen before cursor and limit. Do not resurrect deleted ids or reorder equal revisions.",
    [({"rows": [{"id": "b", "revision": 1, "score": 5}, {"id": "a", "revision": 1, "score": 5}, {"id": "c", "revision": 1, "score": 4}], "minimum": 0, "cursor": None, "limit": 1}, {"rows": [{"id": "a", "revision": 1, "score": 5}], "next": [5, "a"]}), ({"rows": [{"id": "a", "revision": 1, "score": 9}, {"id": "a", "revision": 2, "score": 0, "deleted": True}], "minimum": 0, "cursor": None, "limit": 2}, {"rows": [], "next": None})],
    [{"rows": rows, "minimum": minimum, "cursor": cursor, "limit": limit} for rows, minimum, cursor, limit in [([], 0, None, 1), ([{"id": "x", "revision": 0, "score": 0}], 0, None, 1), ([{"id": "x", "revision": 1, "score": 2}, {"id": "x", "revision": 1, "score": 8}], 3, None, 1), ([{"id": "x", "revision": 1, "score": 2}], 0, [2, "x"], 2), ([{"id": "a", "revision": 1, "score": 2}, {"id": "c", "revision": 1, "score": 2}], 0, [2, "b"], 2), ([{"id": "x", "revision": 1, "score": 8}], 9, None, 2), ([{"id": str(i), "revision": i, "score": i % 3} for i in range(8)], 1, [2, "3"], 3), ([{"id": "x", "revision": 2, "score": -1}, {"id": "y", "revision": 1, "score": -2}], -5, None, 5)]])

_task("D30", "Virtual symlink-aware path resolver", "normalization", "Input {path:absolute string,links:{absolute canonical path:target string},max_hops:nonnegative int}. Resolve lexically from root, processing components left to right. Empty and '.' components disappear; '..' removes previous resolved component or stays at root. After appending each normal component, if its current absolute path is a link, remove that component and prepend the link target components to pending components. Relative target starts from link's parent; absolute target resets resolved prefix to root. Follow links even if later '..' would remove them. Every link traversal increments hops; if hops exceeds max_hops return {error:'symlink_limit'} including cycles. Success {path:canonical absolute path,hops:int}. No filesystem access, existence checks or trailing-slash preservation. Targets may be empty.",
    [({"path": "/a/link/../x", "links": {"/a/link": "../b/c"}, "max_hops": 5}, {"path": "/b/x", "hops": 1}), ({"path": "/a", "links": {"/a": "/b", "/b": "/a"}, "max_hops": 2}, {"error": "symlink_limit"})],
    [{"path": p, "links": links, "max_hops": h} for p, links, h in [("/", {}, 0), ("/../a//./b/..", {}, 0), ("/x", {"/x": "/"}, 1), ("/a/b", {"/a": "/z"}, 1), ("/a/x", {"/a/x": ""}, 1), ("/a/../b", {"/a": "/x/y"}, 1), ("/x", {"/x": "/y"}, 0), ("/a/x", {"/a/x": "../x", "/x": "/done"}, 2)]])

_task("D31", "Markdown fenced-block extractor", "parsing", "Input {text:string}; split on LF preserving final empty line. Outside a fence, an opener has 0..3 ASCII spaces, at least three identical backticks or at least three tildes, then arbitrary info text. A backtick opener is invalid if info contains any backtick; tilde info unrestricted. Trim info using Python str.strip(). Inside, a closer has 0..3 spaces, only same marker repeated at least opener length, then spaces/tabs only. Other fences do not nest and are ordinary content. Emit [{info,start,end,text,closed}] in encounter order, zero-based line numbers; text joins body lines with LF without adding a newline, end is closing line or null at EOF, closed false for unclosed block. Four-space-indented fences are ordinary text. Empty final line belongs to an unclosed block if present in split input.",
    [({"text": "before\n```py\na\n~~~\n```\nafter"}, [{"info": "py", "start": 1, "end": 4, "text": "a\n~~~", "closed": True}]), ({"text": "~~~x\na\n"}, [{"info": "x", "start": 0, "end": None, "text": "a\n", "closed": False}])],
    [{"text": s} for s in ["", "plain", "```\n```", "````x\n```\n````", "    ```\nx", "```x`\na\n```", "~~~a`\nb\n~~~~", "  ``` x \na\n   ```  \t", "```\na\n```\n~~~\nb\n~~~"]])

_task("D32", "Three-valued row query and stable ordering", "query", "Input {rows:[objects],where:predicate,order:[{field,descending:bool}],select:[fields],offset:nonnegative int,limit:nonnegative int}. Predicates: {op:'eq'|'lt'|'gt',field,value}; {op:'is_null',field}; {op:'not',arg}; {op:'and'|'or',args:[predicates]}. Missing and null are unknown for comparisons; is_null true for either. Eq compares JSON structurally with bool distinct from number. Lt/gt compare only same Python type integer or string; differing types yield unknown. Not unknown remains unknown. AND false dominates unknown, otherwise unknown dominates true; empty AND true. OR true dominates unknown, otherwise unknown dominates false; empty OR false. Keep only predicate true. Sort lexicographically by order specs; null/missing always last regardless descending, nonnull values ascending or descending as configured; nonnull values within each order field share an integer or string type. Ties retain original row order. Apply offset/limit then project selected fields with missing represented null. Return projected row array.",
    [({"rows": [{"x": None}, {"x": 2}, {"x": 1}], "where": {"op": "or", "args": [{"op": "lt", "field": "x", "value": 2}, {"op": "is_null", "field": "x"}]}, "order": [{"field": "x", "descending": True}], "select": ["x", "missing"], "offset": 0, "limit": 9}, [{"x": 1, "missing": None}, {"x": None, "missing": None}]), ({"rows": [{"x": None}, {"x": 1}], "where": {"op": "not", "arg": {"op": "eq", "field": "x", "value": 1}}, "order": [], "select": ["x"], "offset": 0, "limit": 9}, [])],
    [{"rows": rows, "where": where, "order": order, "select": ["x", "y"], "offset": off, "limit": lim} for rows, where, order, off, lim in [([], {"op": "and", "args": []}, [], 0, 2), ([{"x": 1}, {}], {"op": "or", "args": []}, [], 0, 2), ([{"x": True}, {"x": 1}], {"op": "eq", "field": "x", "value": 1}, [], 0, 2), ([{}, {"x": None}, {"x": 1}], {"op": "is_null", "field": "x"}, [], 0, 3), ([{"x": 1}, {"x": 2}, {"x": 3}], {"op": "and", "args": []}, [{"field": "x", "descending": True}], 1, 1), ([{"x": None}, {"x": 1}, {}], {"op": "and", "args": []}, [{"field": "x", "descending": True}], 0, 9), ([{"x": 1}, {"x": "1"}, {}], {"op": "gt", "field": "x", "value": 0}, [], 0, 9), ([{"x": 1, "y": "b"}, {"x": 1, "y": "a"}, {"x": 2, "y": "z"}], {"op": "and", "args": []}, [{"field": "x", "descending": False}, {"field": "y", "descending": True}], 0, 9)]])

_task("D33", "Canonical structural JSON delta", "editing", "Input {before:JSON,after:JSON}; return deterministic JSON Pointer patch operation array using add/remove/replace. Equal JSON means object key order ignored, numbers numeric, bool distinct. For two objects: remove keys only in before in sorted order, recursively diff common keys in sorted order, then add keys only in after in sorted order. For two arrays: recursively diff common indices ascending, then remove surplus before indices descending, then add surplus after indices ascending using numeric pointers (not '-'). Other unequal type/value pairs emit one replace at current pointer, root ''. Escape pointer key ~ to ~0 and / to ~1. Values in operations are complete after values. Array positions align by index, with no LCS/move heuristics. Patches must apply sequentially to before and reconstruct after.",
    [({"before": {"a": 1, "z": 2}, "after": {"a": 3, "b": 4}}, [{"op": "remove", "path": "/z"}, {"op": "replace", "path": "/a", "value": 3}, {"op": "add", "path": "/b", "value": 4}]), ({"before": [1, 2, 3], "after": [1]}, [{"op": "remove", "path": "/2"}, {"op": "remove", "path": "/1"}])],
    [{"before": a, "after": b} for a, b in [(None, None), (True, 1), ({}, []), ([1], [2, 3]), ({"a/b": {"~": 1}}, {"a/b": {"~": 2}}), ({"b": 2, "a": 1}, {"a": 1, "b": 2}), ([{"x": 1}, 2], [{"x": 2}, 2]), ({"x": 1, "y": 2}, {})]])

# Ensure the comparator's unsupported equal-type cases are exercised, not merely
# documented. These independent expected results are additional held-out anchors.
_QUERY_ANCHORS = [
    ({"rows": [{"x": True}], "where": {"op": "gt", "field": "x", "value": False}, "order": [], "select": ["x"], "offset": 0, "limit": 2}, []),
    ({"rows": [{"x": [1]}], "where": {"op": "lt", "field": "x", "value": [2]}, "order": [], "select": ["x"], "offset": 0, "limit": 2}, []),
]
for _input, _expected in _QUERY_ANCHORS:
    if _json_typed(_d32(_input)) != _json_typed(_expected): raise AssertionError("D32 comparison anchor")
SPECS[31][-1].extend(data for data, _ in _QUERY_ANCHORS)

# Freeze a finite decimal domain below CPython's configurable 4,300-digit
# conversion guard. A larger valid input previously contradicted these prompts;
# the benchmark domain now states the same bound for candidates and oracles.
_DECIMAL_BOUNDS = {
    "D04": "For this bounded task, every core number and numeric prerelease/build identifier in candidates and comparators has at most 1000 decimal digits.",
    "D20": "For this bounded task, existing integer values and integer-like strings have at most 1000 decimal digits excluding a leading sign.",
    "D26": "For this bounded task, every maximal ASCII-digit run has at most 1000 digits.",
    "D27": "For this bounded task, each integer literal in the input has at most 1000 decimal digits excluding its optional minus sign.",
}
for _i, _spec in enumerate(SPECS):
    if _spec[0] in _DECIMAL_BOUNDS:
        SPECS[_i] = (*_spec[:3], _spec[3] + " " + _DECIMAL_BOUNDS[_spec[0]], *_spec[4:])
_THOUSAND_NINES = "9" * 1000
SPECS[3][-1].append({"versions": [_THOUSAND_NINES + ".0.0", "1.0.0"], "clauses": [[{"op": ">=", "version": "1.0.0"}]]})
SPECS[19][-1].append({"rows": [{"x": "+" + _THOUSAND_NINES}], "operations": [{"op": "integer", "field": "x"}]})
SPECS[25][-1].append({"values": ["n" + _THOUSAND_NINES, "n" + "1" + "0" * 999, "n" + "0" * 998 + "10", "n10"]})
SPECS[26][-1].append({"text": '{"n":' + _THOUSAND_NINES + '}'})
_BOUND_ANCHORS = {
    "D04": {"accepted": ["1.0.0", _THOUSAND_NINES + ".0.0"], "invalid": []},
    "D20": {"rows": [{"x": 10**1000 - 1}]},
    "D26": ["n" + "0" * 998 + "10", "n10", "n" + "1" + "0" * 999, "n" + _THOUSAND_NINES],
    "D27": {"canonical": '{"n":' + _THOUSAND_NINES + '}', "value": {"n": 10**1000 - 1}},
}
for _i in (3, 19, 25, 26):
    if _json_typed(reference(SPECS[_i][0], SPECS[_i][-1][-1])) != _json_typed(_BOUND_ANCHORS[SPECS[_i][0]]):
        raise AssertionError((SPECS[_i][0], "independent 1000-digit boundary anchor"))


def _seeded_cases(task_id):
    """Two small reproducible generated inputs per task, private to evaluation."""
    rng = random.Random(2026100700 + int(task_id[1:]))
    cases = []
    for iteration in range(2):
        n = rng.randrange(1000, 9000) + iteration * 10000
        word = "".join(rng.choice("abcxyz") for _ in range(7)) + str(n)
        table = {
            "D01": lambda: {"chunks": ["'" + word[:4], word[4:] + "' \\", " x\"y z\""]},
            "D02": lambda: {"document": {"b": [{"x": n}, {}], "a": [{"x": n+1}]}, "paths": [["*", "*", "x"], ["b", 1, "x"], ["a", 0]]},
            "D03": lambda: {"variables": {"A": word + "-${B}", "B": "${C}:$${C}", "C": str(n)}, "targets": ["A", "B", "MISSING"]},
            "D04": lambda: {"versions": [f"1.2.{n}-a.2", f"1.2.{n}-a.10", f"1.2.{n}", f"1.2.{n+1}-a", f"1.2.0{n}"], "clauses": [[{"op": ">", "version": f"1.2.{n}-a.2"}, {"op": "<=", "version": f"1.2.{n+1}"}]]},
            "D05": lambda: {"base": word, "left": [{"start": 0, "end": 2, "text": str(n)}], "right": [{"start": 2, "end": 2, "text": "!"}, {"start": len(word), "end": len(word), "text": "?"}]},
            "D06": lambda: {"lines": [word, "a", "b"], "operations": [{"at": 1, "remove": ["a"], "insert": [str(n), "x"]}, {"at": 3, "remove": ["b"], "insert": []}]},
            "D07": lambda: {"text": word + ',"a,b\n""c",' + str(n) + "\r\n\r\n"},
            "D08": lambda: {"queries": ["x=" + word + "&x=%E2%82%AC&blank", "z=a+b"], "remove": ["blank"], "set": [["x", str(n)], ["z", "a/b?"]]},
            "D09": lambda: {"events": [{"key": rng.choice(["a", "b", word]), "revision": rng.randrange(6), "op": "put", "value": n+i} for i in range(15)]},
            "D10": lambda: {"document": {"a/b": [n, n+1], "x": word}, "operations": [{"op": "add", "path": "/a~1b/1", "value": n+2}, {"op": "test", "path": "/a~1b/2", "value": n+1}, {"op": "replace", "path": "/x", "value": [word]}]},
            "D11": lambda: {"ranges": [{"start": i-5, "end": i+3, "priority": rng.randrange(4), "value": n+i % 3} for i in range(9)]},
            "D12": lambda: {"runs": [{"count": rng.randrange(5), "value": n+i % 3} for i in range(12)], "start": 3, "end": 13},
            "D13": lambda: {"pattern": word + "{a,{b,c},a}{1,2,}"},
            "D14": lambda: {"chunks": [[rng.randrange(256) for _ in range(7)], [rng.randrange(256) for _ in range(8)], list(word.encode())]},
            "D15": lambda: {"text": "\t " + word + "\n  " + str(n) + "\n\t\n    z", "tab_width": rng.randrange(2, 9), "indent": rng.randrange(4)},
            "D16": lambda: {"value": {"rows": [n, True, n+1], "extra": word}, "schema": {"type": "object", "properties": {"rows": {"type": "array", "items": {"type": "integer", "maximum": n}}, "default": {"type": "string", "default": word}}, "additional": False}},
            "D17": lambda: {"items": [{"path": ["x", word], "value": n}, {"path": ["a"], "value": {"v": [n]}}, {"path": ["x", "other"], "value": {}}]},
            "D18": lambda: {"path": "/" + word + "/a/b", "routes": [{"id": "greedy", "pattern": "/" + word + "/*rest"}, {"id": "param", "pattern": "/" + word + "/:x/:y"}, {"id": "exact", "pattern": "/" + word + "/a/b"}]},
            "D19": lambda: {"left": [{"k": i % 3, "v": n+i} for i in range(7)], "right": [{"k": i % 4, "v": word + str(i)} for i in range(8)], "key": "k", "mode": "full"},
            "D20": lambda: {"rows": [{"old": str(n)}, {"other": word}, {"old": "+" + str(n+1)}], "operations": [{"op": "rename", "field": "old", "to": "count"}, {"op": "default", "field": "count", "value": "-" + str(n)}, {"op": "integer", "field": "count"}]},
            "D21": lambda: {"events": [{"group": rng.choice(["a", word]), "time": rng.randrange(-3, 12), "value": None if i % 4 == 0 else n-i} for i in range(15)], "start": 0, "end": 10, "width": 3, "fill": "previous"},
            "D22": lambda: {"text": "\u001b[3" + str(n % 8) + "m" + word + "\u001b[0m a bb ccc " + str(n), "width": rng.randrange(5, 20)},
            "D23": lambda: {"text": 'key="' + word + '\\n\\t" n=' + str(n) + ' key="a\\\"b"'},
            "D24": lambda: {"text": word + "😀" + word, "edits": [{"start": len(word), "end": len(word)+2, "text": str(n)}, {"start": 2*len(word)+2, "end": 2*len(word)+2, "text": "!"}]},
            "D25": lambda: {"before": [{"k": i % 3, "v": n+i} for i in range(7)], "after": [{"k": (i+1) % 4, "v": n+i+1} for i in range(8)], "key": "k"},
            "D26": lambda: {"values": [word+"10", word+"2", word.upper()+"02", word+"1", word, "2"+word, "10"+word]},
            "D27": lambda: {"text": json.dumps({"z": [n, True, None], "a": word, "é": "\n/"}, ensure_ascii=True)},
            "D28": lambda: {"chunks": [[126, 2, n % 100], [n % 101, (2+n % 100+n % 101) % 256, 126, 1, 0, 0, 126]]},
            "D29": lambda: {"rows": [{"id": word if i < 2 else str(i), "revision": i, "score": rng.randrange(-2, 5), "deleted": i == 4} for i in range(9)], "minimum": 0, "cursor": [3, "3"], "limit": 3},
            "D30": lambda: {"path": "/" + word + "/link/../end", "links": {"/"+word+"/link": "../"+str(n)+"/nested", "/"+str(n): "/dest"}, "max_hops": 3},
            "D31": lambda: {"text": "```` " + word + "\n" + str(n) + "\n```\n~~~~\n`````\n~~~\n" + word},
            "D32": lambda: {"rows": [{"x": n+i % 3, "y": word+str(i)} for i in range(8)] + [{"x": None}], "where": {"op": "or", "args": [{"op": "gt", "field": "x", "value": n}, {"op": "is_null", "field": "x"}]}, "order": [{"field": "x", "descending": True}, {"field": "y", "descending": False}], "select": ["x", "y"], "offset": 1, "limit": 5},
            "D33": lambda: {"before": {"x": [n, {"a/b": word}, 0], "z": None}, "after": {"x": [n+1, {"a/b": word+"!"}], "a": [word]}},
        }
        cases.append(table[task_id]())
    return cases


def build_tasks():
    """Return frozen-input task records after hand-anchor and determinism checks."""
    tasks = []
    for task_id, title, category, specification, anchors, private in SPECS:
        cases = []
        for i, (data, expected) in enumerate(anchors):
            actual = reference(task_id, data)
            if _json_typed(actual) != _json_typed(expected):
                raise AssertionError((task_id, "independent anchor", i, expected, actual))
            cases.append({"id": f"{task_id}-P{i+1:02d}", "input": copy.deepcopy(data), "expected": copy.deepcopy(expected), "visibility": "public"})
        for i, data in enumerate(private + _seeded_cases(task_id)):
            expected = reference(task_id, data)
            # Repeat on a new deep copy to detect global state or input mutation.
            if _json_typed(reference(task_id, data)) != _json_typed(expected): raise AssertionError((task_id, "nondeterministic oracle"))
            cases.append({"id": f"{task_id}-H{i+1:02d}", "input": copy.deepcopy(data), "expected": expected, "visibility": "hidden"})
        keys = [json.dumps(c["input"], sort_keys=True, ensure_ascii=True, separators=(",", ":")) for c in cases]
        if len(cases) < 10 or len(keys) != len(set(keys)): raise AssertionError((task_id, "insufficient or duplicate inputs"))
        prompt = "Implement solution.py with a pure solve(data) function. Input and output are JSON-compatible Python values. Use Python standard library only, no external I/O. " + specification
        tasks.append({"id": task_id, "title": title, "category": category, "difficulty": "hard", "prompt": prompt, "cases": cases})
    if len(tasks) != 33 or [t["id"] for t in tasks] != [f"D{i:02d}" for i in range(1, 34)]: raise AssertionError("task inventory")
    return tasks


def self_check():
    a = build_tasks(); b = build_tasks()
    if json.dumps(a, sort_keys=True, ensure_ascii=True) != json.dumps(b, sort_keys=True, ensure_ascii=True): raise AssertionError("regeneration differs")
    # Independent consistency: D33 patches must reconstruct every generated after.
    for task in a:
        if task["id"] == "D33":
            for case in task["cases"]:
                applied = reference("D10", {"document": case["input"]["before"], "operations": case["expected"]})
                if _json_typed(applied) != _json_typed({"document": case["input"]["after"]}): raise AssertionError((case["id"], "delta round trip"))
        if task["id"] == "D14":
            for case in task["cases"]:
                raw = bytes(x for c in case["input"]["chunks"] for x in c)
                if case["expected"]["text"] != raw.decode("utf-8", errors="replace"): raise AssertionError((case["id"], "UTF-8 independent codec"))
        if task["id"] == "D07":
            for case in task["cases"]:
                if "rows" in case["expected"]:
                    reader = list(csv.reader(io.StringIO(case["input"]["text"], newline=""), strict=True))
                    # stdlib CSV treats a truly blank record as [] rather than this task's [''].
                    reader = [r if r else [""] for r in reader]
                    if reader != case["expected"]["rows"]: raise AssertionError((case["id"], "CSV independent parser"))
    return {"tasks": len(a), "cases": sum(len(t["cases"]) for t in a), "public": sum(c["visibility"] == "public" for t in a for c in t["cases"]), "hidden": sum(c["visibility"] == "hidden" for t in a for c in t["cases"]) }


if __name__ == "__main__":
    print(json.dumps(self_check(), sort_keys=True))
