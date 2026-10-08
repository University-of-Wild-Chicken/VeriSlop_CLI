import heapq

def solve(data):
    n = data.get('n', 0)
    edges = data.get('edges', [])

    if n <= 0:
        return {'order': [], 'blocked': []}

    # Build adjacency list and indegree, deduplicating edges
    adj = [[] for _ in range(n)]
    indeg = [0] * n
    seen = set()
    for u, v in edges:
        if u == v:
            # Self-loop: treat as a cycle edge; keep it for indegree
            if (u, v) not in seen:
                seen.add((u, v))
                adj[u].append(v)
                indeg[v] += 1
        else:
            if (u, v) not in seen:
                seen.add((u, v))
                adj[u].append(v)
                indeg[v] += 1

    # Kahn's algorithm with min-heap for smallest zero-indegree vertex
    heap = []
    for i in range(n):
        if indeg[i] == 0:
            heapq.heappush(heap, i)

    order = []
    while heap:
        u = heapq.heappop(heap)
        order.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(heap, v)

    # Blocked vertices are those not in order
    order_set = set(order)
    blocked = [i for i in range(n) if i not in order_set]
    blocked.sort()

    return {'order': order, 'blocked': blocked}