import re

_SEMVER_RE = re.compile(r'^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+))?(?:\+([0-9A-Za-z-]+))?$')

def _parse_semver(s):
    m = _SEMVER_RE.match(s)
    if not m:
        raise ValueError('invalid semver: ' + s)
    major = int(m.group(1))
    minor = int(m.group(2))
    patch = int(m.group(3))
    prerelease = m.group(4)
    build = m.group(5)
    return (major, minor, patch, prerelease, build)

def _prerelease_key(prerelease):
    if prerelease is None:
        return (1, ())
    ids = prerelease.split('.')
    key = []
    for ident in ids:
        if ident.isdigit():
            key.append((0, int(ident), ''))
        else:
            key.append((1, 0, ident))
    return (0, tuple(key))

def _precedence_key(s):
    major, minor, patch, prerelease, build = _parse_semver(s)
    return (major, minor, patch, _prerelease_key(prerelease))

def _compare(a, b):
    ka = _precedence_key(a)
    kb = _precedence_key(b)
    if ka < kb:
        return -1
    if ka > kb:
        return 1
    return 0

def _satisfies(version, constraints):
    for c in constraints:
        op = c['op']
        target = c['version']
        cmp = _compare(version, target)
        if op == '=' and cmp != 0:
            return False
        if op == '>' and cmp <= 0:
            return False
        if op == '>=' and cmp < 0:
            return False
        if op == '<' and cmp >= 0:
            return False
        if op == '<=' and cmp > 0:
            return False
    return True

def solve(data):
    available = data.get('available', [])
    constraints = data.get('constraints', [])
    include_prerelease = data.get('include_prerelease', False)

    # Deduplicate exact input strings
    seen = set()
    unique_versions = []
    for v in available:
        if v not in seen:
            seen.add(v)
            unique_versions.append(v)

    eligible = []
    for v in unique_versions:
        # Parse to check if prerelease
        parsed = _parse_semver(v)
        prerelease = parsed[3]
        if not include_prerelease and prerelease is not None:
            continue
        if _satisfies(v, constraints):
            eligible.append(v)

    # Sort by ascending precedence, breaking ties by ASCII full-string order
    def sort_key(v):
        return (_precedence_key(v), v)

    eligible.sort(key=sort_key)

    if eligible:
        # Highest precedence is last in ascending sort
        # Among ties (same precedence), smallest full string
        # Since we sorted by (precedence, string), the last element has highest precedence
        # But we need the smallest string among those with highest precedence
        # Find the highest precedence key
        max_prec = _precedence_key(eligible[-1])
        # Filter all with that precedence and pick smallest string
        candidates = [v for v in eligible if _precedence_key(v) == max_prec]
        selected = min(candidates)
    else:
        selected = None

    return {'eligible': eligible, 'selected': selected}
