from collections import deque

def solve(data):
    n = data["n"]
    source = data["source"]
    sink = data["sink"]
    edges = data["edges"]

    # Build capacity matrix; parallel edges add capacities
    cap = [[0] * n for _ in range(n)]
    for u, v, c in edges:
        if 0 <= u < n and 0 <= v < n:
            cap[u][v] += c

    # Residual graph: residual[u][v] = cap[u][v] - flow[u][v]
    # We maintain residual directly; reverse residual is residual[v][u]
    residual = [row[:] for row in cap]

    def bfs_path():
        # BFS from source to sink in residual graph, visiting neighbors in increasing order
        parent = [-1] * n
        parent[source] = source
        q = deque([source])
        while q:
            u = q.popleft()
            if u == sink:
                break
            for v in range(n):
                if residual[u][v] > 0 and parent[v] == -1:
                    parent[v] = u
                    if v == sink:
                        break
                    q.append(v)
        if parent[sink] == -1:
            return None
        # Reconstruct path
        path = []
        v = sink
        while v != source:
            path.append(v)
            v = parent[v]
        path.append(source)
        path.reverse()
        return path

    flow = 0
    while True:
        path = bfs_path()
        if path is None:
            break
        # Find bottleneck
        bottleneck = float('inf')
        for i in range(len(path) - 1):
            u = path[i]
            v = path[i + 1]
            bottleneck = min(bottleneck, residual[u][v])
        # Augment
        for i in range(len(path) - 1):
            u = path[i]
            v = path[i + 1]
            residual[u][v] -= bottleneck
            residual[v][u] += bottleneck
        flow += bottleneck

    # Find reachable vertices from source in final residual graph
    reachable = [False] * n
    reachable[source] = True
    q = deque([source])
    while q:
        u = q.popleft()
        for v in range(n):
            if residual[u][v] > 0 and not reachable[v]:
                reachable[v] = True
                q.append(v)

    reachable_list = sorted([i for i in range(n) if reachable[i]])

    return {"flow": flow, "reachable": reachable_list}
