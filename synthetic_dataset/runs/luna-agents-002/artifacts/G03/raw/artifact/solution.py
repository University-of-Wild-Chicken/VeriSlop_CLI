def solve(data):
    n = data["n"]
    source = data["source"]
    edges = data["edges"]

    dist = [None] * n
    dist[source] = 0

    for _ in range(n - 1):
        changed = False
        for u, v, cost in edges:
            if dist[u] is not None and (dist[v] is None or dist[u] + cost < dist[v]):
                dist[v] = dist[u] + cost
                changed = True
        if not changed:
            break

    adjacency = [[] for _ in range(n)]
    affected = [False] * n
    for u, v, cost in edges:
        adjacency[u].append(v)
        if dist[u] is not None and (dist[v] is None or dist[u] + cost < dist[v]):
            affected[v] = True

    queue = [v for v, is_affected in enumerate(affected) if is_affected]
    for v in queue:
        affected[v] = True

    index = 0
    while index < len(queue):
        u = queue[index]
        index += 1
        for v in adjacency[u]:
            if not affected[v]:
                affected[v] = True
                queue.append(v)

    return ["-inf" if affected[v] else dist[v] for v in range(n)]
