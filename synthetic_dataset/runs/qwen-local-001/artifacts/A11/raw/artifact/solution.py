import json

def solve(data):
    values = data["values"]
    n = len(values)
    if n == 0:
        return {"difference": 0, "left_indices": []}

    # Enumerate all subsets of indices (0..2^n - 1)
    # For each subset, compute left sum and right sum
    # We want to minimize |left_sum - right_sum|, then lexicographically minimize the sorted left indices
    
    best_diff = None
    best_left = None
    
    for mask in range(1 << n):
        left_sum = 0
        left_indices = []
        for i in range(n):
            if mask & (1 << i):
                left_sum += values[i]
                left_indices.append(i)
        right_sum = sum(values) - left_sum
        diff = abs(left_sum - right_sum)
        
        if best_diff is None or diff < best_diff or (diff == best_diff and left_indices < best_left):
            best_diff = diff
            best_left = left_indices
    
    return {"difference": best_diff, "left_indices": best_left}
