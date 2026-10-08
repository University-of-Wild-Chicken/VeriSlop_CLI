def solve(data):
    n = data["n"]
    source = data["source"]
    edges = data["edges"]

    distances = [None] * n
    distances[source] = 0

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

    affected = [False] * n
    adjacency = [[] for _ in range(n)]
    for u, v, cost in edges:
        adjacency[u].append(v)
        if distances[u] is not None and (
            distances[v] is None or distances[u] + cost < distances[v]
        ):
            affected[v] = True

    queue = [v for v, is_affected in enumerate(affected) if is_affected]
    head = 0
    while head < len(queue):
        u = queue[head]
        head += 1
        for v in adjacency[u]:
            if not affected[v]:
                affected[v] = True
                queue.append(v)

    return ["-inf" if affected[v] else distances[v] for v in range(n)]