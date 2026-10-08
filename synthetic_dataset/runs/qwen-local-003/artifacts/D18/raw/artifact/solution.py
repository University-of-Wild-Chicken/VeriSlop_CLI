import re

def solve(data):
    path = data.get('path', '')
    routes = data.get('routes', [])

    # Split path into segments, preserving empty segments
    # Split on '/' after initial slash
    # For path "/a/b", segments = ['a', 'b']
    # For path "/a/", segments = ['a', '']
    # For path "/", segments = ['']
    # For path "", segments = []
    def split_path(p):
        if p == '':
            return []
        # Remove leading slash if present
        if p.startswith('/'):
            p = p[1:]
        # Split on '/'
        return p.split('/')

    path_segments = split_path(path)

    # For each route, check if it matches and compute specificity
    # Specificity: (literal_count, nongreedy_flag, param_count, -route_index)
    # We want highest literal_count, then nongreedy before greedy (so nongreedy=1, greedy=0), then fewest params, then earliest route
    # So sort key: (literal_count, nongreedy_flag, -param_count, -route_index) and take max
    # Or: (literal_count, nongreedy_flag, -param_count, -route_index)

    best = None
    best_key = None

    for idx, route in enumerate(routes):
        pattern = route.get('pattern', '')
        route_id = route.get('id', '')

        # Split pattern into segments
        pattern_segments = split_path(pattern)

        # Check if pattern matches path_segments
        # We need to match segment by segment
        # Literal segments must match exactly
        # ':name' matches exactly one segment (even empty)
        # '*name' matches remaining zero or more segments

        # First, check if the pattern can match
        # The pattern must have the same number of segments as path, except when there's a wildcard
        # If there's a wildcard, it must be the last segment

        # Let's check if there's a wildcard
        wildcard_idx = -1
        for i, seg in enumerate(pattern_segments):
            if seg.startswith('*'):
                wildcard_idx = i
                break

        if wildcard_idx != -1:
            # Wildcard must be the last segment
            if wildcard_idx != len(pattern_segments) - 1:
                continue
            # The number of non-wildcard segments must be <= len(path_segments)
            non_wild_count = wildcard_idx
            if non_wild_count > len(path_segments):
                continue
            # Match the non-wildcard segments
            params = {}
            match = True
            for i in range(non_wild_count):
                pseg = pattern_segments[i]
                if pseg.startswith(':'):
                    name = pseg[1:]
                    params[name] = path_segments[i]
                elif pseg.startswith('*'):
                    # Should not happen since wildcard is last
                    match = False
                    break
                else:
                    if pseg != path_segments[i]:
                        match = False
                        break
            if not match:
                continue
            # The wildcard captures the remaining segments
            wildcard_name = pattern_segments[wildcard_idx][1:]
            remaining = path_segments[non_wild_count:]
            params[wildcard_name] = '/'.join(remaining)
            # Calculate specificity
            literal_count = 0
            param_count = 0
            for i in range(non_wild_count):
                pseg = pattern_segments[i]
                if pseg.startswith(':'):
                    param_count += 1
                elif not pseg.startswith('*'):
                    literal_count += 1
            # nongreedy_flag: 1 for nongreedy (no wildcard), 0 for greedy (has wildcard)
            # Wait, the problem says "nongreedy before greedy"
            # I think this means routes without wildcards (nongreedy) are preferred over routes with wildcards (greedy)
            # So nongreedy_flag = 1 if no wildcard, 0 if wildcard
            nongreedy_flag = 0  # has wildcard, so greedy
            key = (literal_count, nongreedy_flag, -param_count, -idx)
            if best_key is None or key > best_key:
                best_key = key
                best = {'id': route_id, 'parameters': params}
        else:
            # No wildcard, must have exactly same number of segments
            if len(pattern_segments) != len(path_segments):
                continue
            params = {}
            match = True
            literal_count = 0
            param_count = 0
            for i in range(len(pattern_segments)):
                pseg = pattern_segments[i]
                if pseg.startswith(':'):
                    name = pseg[1:]
                    params[name] = path_segments[i]
                    param_count += 1
                elif pseg.startswith('*'):
                    # Should not happen since no wildcard
                    match = False
                    break
                else:
                    if pseg != path_segments[i]:
                        match = False
                        break
                    literal_count += 1
            if not match:
                continue
            nongreedy_flag = 1  # no wildcard, so nongreedy
            key = (literal_count, nongreedy_flag, -param_count, -idx)
            if best_key is None or key > best_key:
                best_key = key
                best = {'id': route_id, 'parameters': params}

    return best
