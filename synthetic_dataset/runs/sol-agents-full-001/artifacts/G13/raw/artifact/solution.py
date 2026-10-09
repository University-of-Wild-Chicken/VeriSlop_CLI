def solve(data):
    n = data['n']
    edges = sorted(set((u, v) for u, v in data['edges']))
    adj = [[] for _ in range(n)]
    indegree = [0] * n
    for u, v in edges:
        adj[u].append(v)
        indegree[v] += 1
    ready = [u for u in range(n) if indegree[u] == 0]
    order = []
    while ready:
        u = ready.pop()
        order.append(u)
        for v in adj[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                ready.append(v)
    if len(order) != n:
        return None
    reach = [set() for _ in range(n)]
    for u in reversed(order):
        for v in adj[u]:
            reach[u].add(v)
            reach[u].update(reach[v])
    return [[u, v] for u, v in edges
            if not any(w != v and v in reach[w] for w in adj[u])]
