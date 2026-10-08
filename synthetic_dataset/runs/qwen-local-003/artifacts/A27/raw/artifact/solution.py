import json
from collections import deque

def solve(data):
    n = data.get('n', 0)
    edges = data.get('edges', [])
    
    # Build adjacency set (duplicates removed)
    adj = [set() for _ in range(n)]
    for u, v in edges:
        if 0 <= u < n and 0 <= v < n:
            adj[u].add(v)
    
    # Check for self-loops first (cycle of length 1)
    for i in range(n):
        if i in adj[i]:
            return {"order": None, "cycle": [i, i]}
    
    # Try to find lexicographically smallest topological order
    # Using Kahn's algorithm with a min-heap for lexicographic order
    import heapq
    
    in_degree = [0] * n
    for u in range(n):
        for v in adj[u]:
            in_degree[v] += 1
    
    # Min-heap of available nodes (in_degree 0)
    heap = []
    for i in range(n):
        if in_degree[i] == 0:
            heapq.heappush(heap, i)
    
    order = []
    while heap:
        u = heapq.heappop(heap)
        order.append(u)
        for v in sorted(adj[u]):
            in_degree[v] -= 1
            if in_degree[v] == 0:
                heapq.heappush(heap, v)
    
    if len(order) == n:
        return {"order": order, "cycle": None}
    
    # Graph has a cycle. Find the shortest simple directed cycle.
    # For each vertex, do BFS to find shortest cycle back to itself.
    # We want: minimize edge count, then lexicographic sequence (rotated to smallest vertex).
    
    best_cycle = None
    
    for start in range(n):
        # BFS from start, looking for path back to start
        # dist[v] = shortest distance from start to v
        # parent[v] = previous node in BFS tree
        dist = [-1] * n
        parent = [-1] * n
        dist[start] = 0
        queue = deque([start])
        
        while queue:
            u = queue.popleft()
            for v in sorted(adj[u]):
                if v == start:
                    # Found a cycle: start -> ... -> u -> start
                    # Reconstruct path
                    path = [u]
                    cur = u
                    while cur != start:
                        cur = parent[cur]
                        path.append(cur)
                    path.reverse()
                    # path is [start, ..., u], cycle is path + [start]
                    cycle = path + [start]
                    
                    # Rotate to smallest vertex
                    min_idx = 0
                    for i in range(len(cycle) - 1):
                        if cycle[i] < cycle[min_idx]:
                            min_idx = i
                    rotated = cycle[min_idx:] + cycle[:min_idx]
                    
                    if best_cycle is None:
                        best_cycle = rotated
                    else:
                        # Compare: edge count first, then lexicographic
                        if len(rotated) < len(best_cycle):
                            best_cycle = rotated
                        elif len(rotated) == len(best_cycle):
                            if rotated < best_cycle:
                                best_cycle = rotated
                    break
                elif dist[v] == -1:
                    dist[v] = dist[u] + 1
                    parent[v] = u
                    queue.append(v)
        
        if queue:
            break  # No need to continue BFS for this start if we found a cycle? Actually we should continue to find all possible cycles from this start, but BFS already finds shortest. Let's just break inner loop.
    
    # Actually, the above BFS for each start finds the shortest cycle that includes start.
    # But we need the global shortest cycle. Let's redo more carefully.
    
    best_cycle = None
    
    for start in range(n):
        # BFS from start
        dist = [-1] * n
        parent = [-1] * n
        dist[start] = 0
        queue = deque([start])
        found = False
        
        while queue and not found:
            u = queue.popleft()
            for v in sorted(adj[u]):
                if v == start:
                    # Found cycle
                    path = [u]
                    cur = u
                    while cur != start:
                        cur = parent[cur]
                        path.append(cur)
                    path.reverse()
                    cycle = path + [start]
                    
                    # Rotate to smallest vertex
                    min_idx = 0
                    for i in range(len(cycle) - 1):
                        if cycle[i] < cycle[min_idx]:
                            min_idx = i
                    rotated = cycle[min_idx:] + cycle[:min_idx]
                    
                    if best_cycle is None:
                        best_cycle = rotated
                    else:
                        if len(rotated) < len(best_cycle):
                            best_cycle = rotated
                        elif len(rotated) == len(best_cycle):
                            if rotated < best_cycle:
                                best_cycle = rotated
                    found = True
                    break
                elif dist[v] == -1:
                    dist[v] = dist[u] + 1
                    parent[v] = u
                    queue.append(v)
    
    return {"order": None, "cycle": best_cycle}
