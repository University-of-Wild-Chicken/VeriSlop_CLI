import json

def solve(data):
    n = data['n']
    source = data['source']
    edges = data['edges']
    
    # Initialize distances
    dist = [float('inf')] * n
    dist[source] = 0
    
    # Relax edges n times to detect negative cycles
    for i in range(n):
        updated = False
        for u, v, cost in edges:
            if dist[u] != float('inf') and dist[u] + cost < dist[v]:
                dist[v] = dist[u] + cost
                updated = True
        if not updated:
            break
    
    # If no negative cycle detected, return distances
    if not updated:
        return [d if d != float('inf') else None for d in dist]
    
    # Negative cycle detected. Find all vertices reachable from source
    # that can reach a negative cycle (or are part of one).
    # First, find vertices that are part of or reachable from negative cycles
    # that are themselves reachable from source.
    
    # Build adjacency list
    adj = [[] for _ in range(n)]
    for u, v, cost in edges:
        adj[u].append(v)
    
    # Find vertices reachable from source
    reachable_from_source = [False] * n
    stack = [source]
    reachable_from_source[source] = True
    while stack:
        u = stack.pop()
        for v in adj[u]:
            if not reachable_from_source[v]:
                reachable_from_source[v] = True
                stack.append(v)
    
    # Find vertices that can reach a negative cycle.
    # A vertex is affected if it is reachable from source AND
    # there exists a path from it to a vertex that is part of a negative cycle
    # (or more precisely, if relaxing one more time changes its distance,
    # it means it can reach a negative cycle).
    
    # Do one more relaxation to find which vertices are affected by negative cycles
    affected = [False] * n
    for u, v, cost in edges:
        if dist[u] != float('inf') and dist[u] + cost < dist[v]:
            affected[v] = True
    
    # Propagate affected status backwards: if v is affected, then any u that can reach v
    # and is reachable from source is also affected.
    # Actually, we need to find all vertices that can reach an affected vertex.
    # Build reverse graph
    radj = [[] for _ in range(n)]
    for u, v, cost in edges:
        radj[v].append(u)
    
    # BFS/DFS from all affected vertices in reverse graph
    stack = [v for v in range(n) if affected[v]]
    for v in stack:
        affected[v] = True
    while stack:
        u = stack.pop()
        for pred in radj[u]:
            if not affected[pred]:
                affected[pred] = True
                stack.append(pred)
    
    # Now, a vertex is "-inf" if it is reachable from source AND affected
    result = []
    for i in range(n):
        if not reachable_from_source[i]:
            result.append(None)
        elif affected[i]:
            result.append("-inf")
        else:
            result.append(dist[i])
    
    return result