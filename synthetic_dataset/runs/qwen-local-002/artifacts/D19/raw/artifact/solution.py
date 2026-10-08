import json

def _canonical(value):
    """Return a canonical JSON-compatible representation for structural equality.
    
    Booleans are distinct from numbers. Object key order is ignored.
    """
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        # Use repr for deterministic float representation
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, sort_keys=True)
    if isinstance(value, list):
        return '[' + ','.join(_canonical(v) for v in value) + ']'
    if isinstance(value, dict):
        # Sort keys for order-insensitive comparison
        items = sorted(value.items(), key=lambda x: _canonical(x[0]))
        return '{' + ','.join(_canonical(k) + ':' + _canonical(v) for k, v in items) + '}'
    # Fallback for any other type (should not happen in JSON-compatible data)
    return repr(value)

def solve(data):
    left = data.get('left', [])
    right = data.get('right', [])
    key = data.get('key')
    mode = data.get('mode', 'inner')
    
    # Build a map from canonical key value to list of right rows (preserving order)
    # Missing or null key never matches
    right_map = {}
    right_matched = [False] * len(right)
    
    for i, row in enumerate(right):
        if not isinstance(row, dict):
            continue
        if key not in row:
            continue
        kv = row[key]
        if kv is None:
            continue
        # Canonicalize the key value
        ck = _canonical(kv)
        if ck not in right_map:
            right_map[ck] = []
        right_map[ck].append(i)
    
    result = []
    left_matched = [False] * len(left)
    
    for i, lrow in enumerate(left):
        if not isinstance(lrow, dict):
            # Left row is not a dict, so key is missing -> never matches
            if mode in ('left', 'full'):
                result.append({'left': lrow, 'right': None})
            continue
        
        if key not in lrow:
            if mode in ('left', 'full'):
                result.append({'left': lrow, 'right': None})
            continue
        
        kv = lrow[key]
        if kv is None:
            if mode in ('left', 'full'):
                result.append({'left': lrow, 'right': None})
            continue
        
        ck = _canonical(kv)
        if ck in right_map:
            left_matched[i] = True
            for j in right_map[ck]:
                right_matched[j] = True
                result.append({'left': lrow, 'right': right[j]})
        else:
            if mode in ('left', 'full'):
                result.append({'left': lrow, 'right': None})
    
    # Full mode: append unmatched right rows in input order
    if mode == 'full':
        for j in range(len(right)):
            if not right_matched[j]:
                result.append({'left': None, 'right': right[j]})
    
    return result
