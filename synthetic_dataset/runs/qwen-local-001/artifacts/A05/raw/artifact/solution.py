import json

def solve(data):
    strings = data.get("strings", [])
    # Remove empty strings and duplicates, and strings contained in others
    # First, remove empty strings
    non_empty = [s for s in strings if s]
    if not non_empty:
        return ""
    
    # Remove duplicates
    unique = list(set(non_empty))
    
    # Remove strings that are contained in other strings
    filtered = []
    for s in unique:
        contained = False
        for t in unique:
            if s != t and s in t:
                contained = True
                break
        if not contained:
            filtered.append(s)
    
    if not filtered:
        return ""
    
    # If only one string, return it
    if len(filtered) == 1:
        return filtered[0]
    
    # For small number of strings, use brute force with permutations
    # Since at most 6 strings, we can try all permutations
    from itertools import permutations
    
    def merge(a, b):
        # Merge two strings by finding the maximum overlap
        # Try all possible overlaps where suffix of a matches prefix of b
        best = a + b
        best_len = len(a) + len(b)
        for i in range(1, min(len(a), len(b)) + 1):
            if a[-i:] == b[:i]:
                merged = a + b[i:]
                if len(merged) < best_len:
                    best = merged
                    best_len = len(merged)
        return best
    
    def merge_all(order):
        result = order[0]
        for i in range(1, len(order)):
            result = merge(result, order[i])
        return result
    
    best = None
    for perm in permutations(filtered):
        candidate = merge_all(perm)
        if best is None or len(candidate) < len(best) or (len(candidate) == len(best) and candidate < best):
            best = candidate
    
    return best
