import re

CORE_RE = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')
PRE_ID_RE = re.compile(r'^(0|[1-9]\d*|[a-zA-Z-][0-9a-zA-Z-]*)$')
BUILD_ID_RE = re.compile(r'^[0-9a-zA-Z-]+$')

def _parse_version(s):
    """Parse a strict SemVer 2.0.0 string.
    Returns (major, minor, patch, prerelease_ids, build_ids) or None if invalid.
    """
    if not isinstance(s, str):
        return None
    # Split build metadata
    build_ids = []
    if '+' in s:
        main, build = s.split('+', 1)
        if build == '':
            return None
        build_ids = build.split('.')
        for bid in build_ids:
            if not BUILD_ID_RE.match(bid):
                return None
    else:
        main = s

    # Split prerelease
    prerelease_ids = []
    if '-' in main:
        core, pre = main.split('-', 1)
        if pre == '':
            return None
        prerelease_ids = pre.split('.')
        for pid in prerelease_ids:
            if not PRE_ID_RE.match(pid):
                return None
    else:
        core = main

    # Validate core
    m = CORE_RE.match(core)
    if not m:
        return None
    major = int(m.group(1))
    minor = int(m.group(2))
    patch = int(m.group(3))
    return (major, minor, patch, prerelease_ids, build_ids)

def _pre_key(ids):
    """Return a sort key for prerelease identifiers.
    Numeric identifiers compare numerically and rank below nonnumeric.
    Nonnumeric compare lexicographically.
    """
    key = []
    for ident in ids:
        if ident.isdigit():
            # Numeric identifier: rank 0, value is the number
            key.append((0, int(ident), ''))
        else:
            # Nonnumeric identifier: rank 1, value is the string
            key.append((1, 0, ident))
    return key

def _compare(a, b):
    """Compare two parsed versions. Returns -1, 0, or 1."""
    # major, minor, patch
    for i in range(3):
        if a[i] < b[i]:
            return -1
        elif a[i] > b[i]:
            return 1
    # prerelease
    a_pre = a[3]
    b_pre = b[3]
    if a_pre and not b_pre:
        return -1
    if not a_pre and b_pre:
        return 1
    if a_pre and b_pre:
        a_key = _pre_key(a_pre)
        b_key = _pre_key(b_pre)
        if a_key < b_key:
            return -1
        elif a_key > b_key:
            return 1
    return 0

def _same_core(a, b):
    return a[0] == b[0] and a[1] == b[1] and a[2] == b[2]

def _has_prerelease(parsed):
    return len(parsed[3]) > 0

def _op_matches(op, cmp_val, ver_val):
    if op == '=':
        return cmp_val == ver_val
    elif op == '<':
        return cmp_val < ver_val
    elif op == '<=':
        return cmp_val <= ver_val
    elif op == '>':
        return cmp_val > ver_val
    elif op == '>=':
        return cmp_val >= ver_val
    else:
        return False

def solve(data):
    versions = data.get('versions', [])
    clauses = data.get('clauses', [])
    
    # Parse all versions, track validity
    parsed_versions = []
    invalid_indices = []
    for i, v in enumerate(versions):
        p = _parse_version(v)
        if p is None:
            invalid_indices.append(i)
            parsed_versions.append(None)
        else:
            parsed_versions.append(p)
    
    # Parse clauses
    parsed_clauses = []
    for clause in clauses:
        parsed_clause = []
        for cond in clause:
            op = cond.get('op')
            ver_str = cond.get('version')
            p = _parse_version(ver_str)
            if p is None:
                # Invalid comparator version - treat as always false? 
                # The problem says "comparator versions are valid", so this shouldn't happen.
                # But to be safe, we'll mark this clause as always false.
                parsed_clause.append((op, None))
            else:
                parsed_clause.append((op, p))
        parsed_clauses.append(parsed_clause)
    
    # Determine which versions are accepted
    accepted_indices = []
    for i, p in enumerate(parsed_versions):
        if p is None:
            continue
        # Check if version matches any clause (OR)
        matched = False
        for clause in parsed_clauses:
            # Empty clause admits all releases
            if len(clause) == 0:
                matched = True
                break
            # Check prerelease constraint: a prerelease candidate can match a clause
            # only if that clause has a prerelease comparator with the same major/minor/patch
            if _has_prerelease(p):
                # Find if any comparator in this clause has prerelease and same core
                has_pre_comparator_same_core = False
                for op, cp in clause:
                    if cp is not None and _has_prerelease(cp) and _same_core(p, cp):
                        has_pre_comparator_same_core = True
                        break
                if not has_pre_comparator_same_core:
                    continue
            # All conditions in clause must be true (AND)
            clause_ok = True
            for op, cp in clause:
                if cp is None:
                    clause_ok = False
                    break
                cmp_result = _compare(cp, p)
                if not _op_matches(op, cmp_result, 0):
                    clause_ok = False
                    break
            if clause_ok:
                matched = True
                break
        if matched:
            accepted_indices.append(i)
    
    # Sort accepted versions by precedence, stable ties
    # We need to sort by precedence, and for ties, preserve original order
    # Create list of (precedence_key, original_index, version_string)
    # Since _compare is a total order, we can use a stable sort with a key
    # But Python's sort is stable, so if we sort by a key that reflects precedence,
    # ties will preserve original order.
    
    # We'll use a custom sort. Since the number of versions is bounded, we can do
    # a stable sort using a key that captures the precedence.
    # The precedence is determined by (major, minor, patch, prerelease_key)
    # where prerelease_key is a tuple that can be compared.
    
    def sort_key(idx):
        p = parsed_versions[idx]
        # major, minor, patch
        key = [p[0], p[1], p[2]]
        # prerelease: if no prerelease, it ranks higher than any prerelease
        # We can represent no prerelease as a special value that sorts after all prereleases
        # Since prerelease identifiers are compared with numeric < nonnumeric,
        # and shorter prefix ranks lower, we can use the _pre_key function.
        # For no prerelease, we want it to sort after all prereleases.
        # We can use a tuple: (0, prerelease_key) for prerelease, (1, ()) for no prerelease
        # But we need to be careful with the comparison.
        # Actually, let's just use the _compare function in a stable sort.
        # Since Python's sort is stable, we can sort by a key that is the parsed version,
        # but we need a comparable key.
        
        # Let's create a key that is a tuple of comparable elements.
        # major, minor, patch are integers.
        # For prerelease, we need a key that:
        # - No prerelease > any prerelease
        # - Among prereleases, compare identifier by identifier
        #   - Numeric identifiers compare numerically and rank below nonnumeric
        #   - Nonnumeric compare lexicographically
        #   - Shorter prefix ranks lower
        
        # We can represent the prerelease key as a list of tuples, where each tuple is
        # (type, value) with type 0 for numeric, 1 for nonnumeric.
        # But we need to handle the "shorter prefix ranks lower" rule.
        # This is naturally handled if we compare the lists lexicographically,
        # because a shorter list that is a prefix of a longer list will be considered
        # smaller in lexicographic order (if all elements are equal up to the length of the shorter).
        # Wait, no. In Python, [1] < [1, 2] is True. So a shorter prefix is considered smaller.
        # That matches "shorter equal prefix ranks lower".
        
        # So we can use the _pre_key function, which returns a list of tuples.
        # For no prerelease, we need a key that is greater than any prerelease key.
        # We can use a special marker. Let's use (1,) as a marker for no prerelease,
        # and ensure that any prerelease key is less than (1,).
        # But _pre_key returns a list of tuples like (0, num, '') or (1, 0, str).
        # We can't directly compare a list of tuples with a single tuple.
        
        # Let's restructure: the full sort key will be a tuple:
        # (major, minor, patch, pre_rank, pre_key)
        # where pre_rank is 0 for prerelease, 1 for no prerelease.
        # And pre_key is the list of identifier keys.
        # But we need to ensure that when pre_rank differs, the comparison is correct.
        # If pre_rank is 0 (prerelease), we compare pre_key.
        # If pre_rank is 1 (no prerelease), we don't need to compare pre_key.
        # But in a tuple, if pre_rank is 0 for one and 1 for another, the one with 0 is smaller,
        # which is correct (prerelease < release).
        # If both have pre_rank 0, we compare pre_key.
        # If both have pre_rank 1, pre_key is empty for both, so they are equal.
        
        # So the key is: (major, minor, patch, pre_rank, pre_key)
        # where pre_rank is 0 if prerelease, 1 if no prerelease.
        # pre_key is _pre_key(prerelease_ids) if prerelease, else [].
        
        if _has_prerelease(p):
            pre_rank = 0
            pre_key = _pre_key(p[3])
        else:
            pre_rank = 1
            pre_key = []
        
        return (p[0], p[1], p[2], pre_rank, pre_key)
    
    # Sort accepted_indices by sort_key, stable
    accepted_indices.sort(key=sort_key)
    
    accepted = [versions[i] for i in accepted_indices]
    
    return {
        'accepted': accepted,
        'invalid': invalid_indices
    }