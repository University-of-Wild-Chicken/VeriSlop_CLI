def solve(data):
    n = data['n']
    edges = data['edges']
    distances = [None] * n
    distances[data['source']] = 0
    for _ in range(n - 1):
        changed = False
        for u, v, cost in edges:
            if distances[u] is not None:
                candidate = distances[u] + cost
                if distances[v] is None or candidate < distances[v]:
                    distances[v] = candidate
                    changed = True
        if not changed:
            break
    adjacency = [[] for _ in range(n)]
    affected = set()
    for u, v, cost in edges:
        adjacency[u].append(v)
        if distances[u] is not None and (distances[v] is None or distances[u] + cost < distances[v]):
            affected.add(v)
    pending = list(affected)
    while pending:
        u = pending.pop()
        for v in adjacency[u]:
            if v not in affected:
                affected.add(v)
                pending.append(v)
    return ['-inf' if v in affected else distances[v] for v in range(n)]
