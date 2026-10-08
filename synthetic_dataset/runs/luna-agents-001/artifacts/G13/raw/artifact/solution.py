def solve(data):
    n = data["n"]
    edges = sorted({(u, v) for u, v in data["edges"]})
    adjacency = [0] * n

    for u, v in edges:
        adjacency[u] |= 1 << v

    # Compute reachability and detect cycles, including self-loops.
    reach = adjacency[:]
    for k in range(n):
        bit_k = 1 << k
        for i in range(n):
            if reach[i] & bit_k:
                reach[i] |= reach[k]

    if any(reach[i] & (1 << i) for i in range(n)):
        return None

    reduced = []
    for u, v in edges:
        # An alternate path must begin with a neighbor other than v.
        if not any(w != v and (reach[w] & (1 << v))
                   for w in range(n) if adjacency[u] & (1 << w)):
            reduced.append([u, v])

    return reduced