def solve(data):
    values = data["values"]
    total = sum(values)
    best_difference = None
    best_indices = None

    for mask in range(1 << len(values)):
        left_sum = 0
        indices = []
        for i, value in enumerate(values):
            if mask & (1 << i):
                left_sum += value
                indices.append(i)
        difference = abs(total - 2 * left_sum)
        if (best_difference is None or difference < best_difference or
                (difference == best_difference and indices < best_indices)):
            best_difference = difference
            best_indices = indices

    return {"difference": best_difference, "left_indices": best_indices}
