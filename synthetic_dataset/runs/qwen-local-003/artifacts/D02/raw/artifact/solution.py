import json

def solve(data):
    document = data.get("document")
    paths = data.get("paths", [])
    results = []
    for path in paths:
        results.append(query(document, path))
    return results

def query(doc, path):
    current = [doc]
    for seg in path:
        next_vals = []
        for node in current:
            if seg == "*":
                if isinstance(node, dict):
                    for k in sorted(node.keys()):
                        next_vals.append(node[k])
                elif isinstance(node, list):
                    for item in node:
                        next_vals.append(item)
                # scalar or other: no matches
            elif isinstance(seg, bool):
                # booleans are not integer indices; also not string keys per spec
                # missing key / wrong type yields zero matches
                pass
            elif isinstance(seg, int):
                if isinstance(node, list):
                    if 0 <= seg < len(node):
                        next_vals.append(node[seg])
                # dict with int segment: missing key (int not a key) -> zero matches
                # scalar: zero matches
            elif isinstance(seg, str):
                if isinstance(node, dict):
                    if seg in node:
                        next_vals.append(node[seg])
                # list with string segment: wrong type -> zero matches
                # scalar: zero matches
            else:
                # other types (float, None, etc.) - not valid segments per spec, treat as no match
                pass
        current = next_vals
    return current
