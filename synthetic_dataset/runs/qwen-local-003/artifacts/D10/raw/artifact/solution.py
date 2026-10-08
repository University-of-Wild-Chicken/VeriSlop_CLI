import copy


def _json_equal(a, b):
    """Structural JSON equality: object order ignored, numbers compared numerically,
    booleans distinct from numbers."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        if len(a) != len(b):
            return False
        for k in a:
            if k not in b:
                return False
            if not _json_equal(a[k], b[k]):
                return False
        return True
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        for x, y in zip(a, b):
            if not _json_equal(x, y):
                return False
        return True
    return a == b


def _decode_token(token):
    """Decode a single JSON Pointer token. Returns decoded string or None if invalid."""
    i = 0
    out = []
    while i < len(token):
        c = token[i]
        if c == '~':
            if i + 1 >= len(token):
                return None
            nxt = token[i + 1]
            if nxt == '0':
                out.append('~')
            elif nxt == '1':
                out.append('/')
            else:
                return None
            i += 2
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def _parse_pointer(pointer):
    """Parse a JSON Pointer string. Returns list of decoded tokens, or None if malformed."""
    if pointer == '':
        return []
    if not pointer.startswith('/'):
        return None
    raw_tokens = pointer[1:].split('/')
    tokens = []
    for raw in raw_tokens:
        decoded = _decode_token(raw)
        if decoded is None:
            return None
        tokens.append(decoded)
    return tokens


def _is_valid_array_index(token):
    """Check if token is a canonical decimal array index: '0' or nonzero digits without leading zero."""
    if not token:
        return False
    if not all(c in '0123456789' for c in token):
        return False
    if token == '0':
        return True
    if token[0] == '0':
        return False
    return True


def _resolve_parent(doc, tokens):
    """Resolve all tokens except the last. Returns (parent, True) or (None, False) on failure."""
    current = doc
    for token in tokens[:-1]:
        if isinstance(current, dict):
            if token not in current:
                return None, False
            current = current[token]
        elif isinstance(current, list):
            if not _is_valid_array_index(token):
                return None, False
            idx = int(token)
            if idx >= len(current):
                return None, False
            current = current[idx]
        else:
            return None, False
    return current, True


def solve(data):
    document = data.get('document')
    operations = data.get('operations', [])

    doc = copy.deepcopy(document)

    for i, op_obj in enumerate(operations):
        op = op_obj.get('op')
        path = op_obj.get('path')
        value = op_obj.get('value')

        if op not in ('add', 'remove', 'replace', 'test'):
            return {'error': 'patch', 'operation': i, 'document': document}

        if not isinstance(path, str):
            return {'error': 'patch', 'operation': i, 'document': document}

        tokens = _parse_pointer(path)
        if tokens is None:
            return {'error': 'patch', 'operation': i, 'document': document}

        # Root operations
        if len(tokens) == 0:
            if op == 'add':
                doc = copy.deepcopy(value)
            elif op == 'replace':
                doc = copy.deepcopy(value)
            elif op == 'remove':
                doc = None
            elif op == 'test':
                if not _json_equal(doc, value):
                    return {'error': 'patch', 'operation': i, 'document': document}
            continue

        # Non-root: resolve parent
        parent, ok = _resolve_parent(doc, tokens)
        if not ok:
            return {'error': 'patch', 'operation': i, 'document': document}

        last_token = tokens[-1]

        if isinstance(parent, dict):
            if op == 'add':
                parent[last_token] = copy.deepcopy(value)
            elif op == 'replace':
                if last_token not in parent:
                    return {'error': 'patch', 'operation': i, 'document': document}
                parent[last_token] = copy.deepcopy(value)
            elif op == 'remove':
                if last_token not in parent:
                    return {'error': 'patch', 'operation': i, 'document': document}
                del parent[last_token]
            elif op == 'test':
                if last_token not in parent:
                    return {'error': 'patch', 'operation': i, 'document': document}
                if not _json_equal(parent[last_token], value):
                    return {'error': 'patch', 'operation': i, 'document': document}

        elif isinstance(parent, list):
            if op == 'add':
                if last_token == '-':
                    parent.append(copy.deepcopy(value))
                elif _is_valid_array_index(last_token):
                    idx = int(last_token)
                    if idx > len(parent):
                        return {'error': 'patch', 'operation': i, 'document': document}
                    parent.insert(idx, copy.deepcopy(value))
                else:
                    return {'error': 'patch', 'operation': i, 'document': document}
            elif op == 'replace':
                if not _is_valid_array_index(last_token):
                    return {'error': 'patch', 'operation': i, 'document': document}
                idx = int(last_token)
                if idx >= len(parent):
                    return {'error': 'patch', 'operation': i, 'document': document}
                parent[idx] = copy.deepcopy(value)
            elif op == 'remove':
                if not _is_valid_array_index(last_token):
                    return {'error': 'patch', 'operation': i, 'document': document}
                idx = int(last_token)
                if idx >= len(parent):
                    return {'error': 'patch', 'operation': i, 'document': document}
                del parent[idx]
            elif op == 'test':
                if not _is_valid_array_index(last_token):
                    return {'error': 'patch', 'operation': i, 'document': document}
                idx = int(last_token)
                if idx >= len(parent):
                    return {'error': 'patch', 'operation': i, 'document': document}
                if not _json_equal(parent[idx], value):
                    return {'error': 'patch', 'operation': i, 'document': document}

        else:
            # Scalar traversal
            return {'error': 'patch', 'operation': i, 'document': document}

    return {'document': doc}