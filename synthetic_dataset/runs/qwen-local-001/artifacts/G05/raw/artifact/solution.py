import sys
from collections import defaultdict

def solve(data):
    n = data.get('n', 0)
    edges = data.get('edges', [])
    m = len(edges)
    if m == 0:
        return []
    
    # Build adjacency list with edge IDs
    adj = [[] for _ in range(n)]
    for eid, (u, v) in enumerate(edges):
        if u == v:
            # Self-loop: add to adjacency but it will never be a bridge
            adj[u].append((v, eid))
        else:
            adj[u].append((v, eid))
            adj[v].append((u, eid))
    
    # Tarjan's bridge-finding algorithm
    disc = [-1] * n
    low = [-1] * n
    parent_edge = [-1] * n  # edge ID used to reach this vertex from parent
    time = [0]
    is_bridge = [False] * m
    
    def dfs(u):
        time[0] += 1
        disc[u] = low[u] = time[0]
        for v, eid in adj[u]:
            if eid == parent_edge[u]:
                continue
            if disc[v] == -1:
                parent_edge[v] = eid
                dfs(v)
                low[u] = min(low[u], low[v])
                if low[v] > disc[u]:
                    is_bridge[eid] = True
            else:
                low[u] = min(low[u], disc[v])
    
    for i in range(n):
        if disc[i] == -1:
            dfs(i)
    
    # Self-loops are never bridges
    for eid, (u, v) in enumerate(edges):
        if u == v:
            is_bridge[eid] = False
    
    return [eid for eid in range(m) if is_bridge[eid]]
