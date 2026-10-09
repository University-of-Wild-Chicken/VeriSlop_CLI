def _canonical(value):
    if value is None:
        return ('null',)
    if isinstance(value, bool):
        return ('bool', value)
    if isinstance(value, (int, float)):
        return ('number', value)
    if isinstance(value, str):
        return ('string', value)
    if isinstance(value, list):
        return ('array', tuple(_canonical(item) for item in value))
    if isinstance(value, dict):
        return ('object', tuple((key, _canonical(value[key])) for key in sorted(value)))
    raise TypeError('Unsupported JSON value')


def solve(data):
    left = data['left']
    right = data['right']
    key = data['key']
    mode = data['mode']
    index = {}
    for position, row in enumerate(right):
        if key in row and row[key] is not None:
            token = _canonical(row[key])
            index.setdefault(token, []).append(position)

    result = []
    matched_right = [False] * len(right)
    for row in left:
        matches = []
        if key in row and row[key] is not None:
            matches = index.get(_canonical(row[key]), [])
        if matches:
            for position in matches:
                result.append({'left': row, 'right': right[position]})
                matched_right[position] = True
        elif mode in ('left', 'full'):
            result.append({'left': row, 'right': None})

    if mode == 'full':
        for position, row in enumerate(right):
            if not matched_right[position]:
                result.append({'left': None, 'right': row})
    return result
