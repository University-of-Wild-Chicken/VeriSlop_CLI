import json
from itertools import permutations

def solve(data):
    left = data.get('left', 0)
    right = data.get('right', 0)
    edges = data.get('edges', [])
    
    # Build adjacency list: for each left vertex, set of right vertices it can connect to
    adj = [set() for _ in range(left)]
    for e in edges:
        l, r = e
        if 0 <= l < left and 0 <= r < right:
            adj[l].add(r)
    
    # If either side is empty, no matching possible
    if left == 0 or right == 0:
        return {"size": 0, "pairs": []}
    
    # We need to find a maximum-cardinality matching.
    # Tie-break: lexicographically minimize the assignment vector of length `left`,
    # where assignment[i] = matched right vertex, or `right` (sentinel) if unmatched.
    # "Matching an earlier left vertex beats leaving it unmatched" means we prefer
    # assignments where earlier left vertices are matched (i.e., have value < right) over unmatched (value == right).
    # Lexicographic minimization of the vector: we want the smallest possible value at index 0, then index 1, etc.
    # Since unmatched is `right` (the largest possible value), matching a left vertex to any right vertex (0..right-1) is better than leaving it unmatched.
    # Among matched, smaller right index is lexicographically smaller.
    
    # Strategy: enumerate all possible matchings (or use a smarter approach).
    # Since left and right are at most 6, we can use a brute-force approach.
    # 
    # A matching can be represented as a tuple of length `left` where each entry is either a right vertex index or `right` (unmatched).
    # Constraints:
    # 1. If assignment[i] != right, then assignment[i] must be in adj[i]
    # 2. No two left vertices can be assigned the same right vertex
    # 
    # We want to maximize the number of matched vertices (i.e., minimize the number of `right` values),
    # and among those with maximum cardinality, lexicographically minimize the assignment vector.
    
    # Since left <= 6, we can try all possible assignments.
    # But the number of possible assignments is (right+1)^left which for right=6, left=6 is 7^6 = 117649, which is manageable.
    
    best_assignment = None
    best_size = -1
    
    # Generate all possible assignments
    # For each left vertex i, the possible values are: right (unmatched) or any r in adj[i]
    # But we also need to ensure no duplicate right vertices are used.
    
    # We'll use backtracking to generate valid matchings.
    
    def backtrack(i, used_rights, current_assignment):
        nonlocal best_assignment, best_size
        
        if i == left:
            # Calculate size (number of matched vertices)
            size = sum(1 for v in current_assignment if v != right)
            # Check if this is better than the current best
            if size > best_size:
                best_size = size
                best_assignment = list(current_assignment)
            elif size == best_size:
                # Lexicographic comparison
                if best_assignment is None or current_assignment < best_assignment:
                    best_assignment = list(current_assignment)
            return
        
        # Option 1: leave left vertex i unmatched
        backtrack(i + 1, used_rights, current_assignment + [right])
        
        # Option 2: match left vertex i to some right vertex
        for r in sorted(adj[i]):
            if r not in used_rights:
                used_rights.add(r)
                backtrack(i + 1, used_rights, current_assignment + [r])
                used_rights.remove(r)
    
    backtrack(0, set(), [])
    
    if best_assignment is None:
        best_assignment = [right] * left
        best_size = 0
    
    # Build pairs from the assignment
    pairs = []
    for i in range(left):
        if best_assignment[i] != right:
            pairs.append([i, best_assignment[i]])
    
    return {"size": best_size, "pairs": pairs}
