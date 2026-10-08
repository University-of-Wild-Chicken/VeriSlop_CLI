import json

def solve(data):
    n = data.get('n', 0)
    edges = data.get('edges', [])
    
    # Build adjacency set, ignoring duplicates and self-loops for cycle check
    adj = set()
    for u, v in edges:
        if u == v:
            # Self-loop is a cycle
            return None
        adj.add((u, v))
    
    # Check for cycles using DFS
    # We need to detect any cycle in the directed graph
    # Use standard DFS with three states: 0=unvisited, 1=in stack, 2=done
    state = [0] * n
    has_cycle = False
    
    def dfs(node):
        nonlocal has_cycle
        if has_cycle:
            return
        state[node] = 1
        for u, v in adj:
            if u == node:
                if state[v] == 1:
                    has_cycle = True
                    return
                elif state[v] == 0:
                    dfs(v)
                    if has_cycle:
                        return
        state[node] = 2
    
    for i in range(n):
        if state[i] == 0:
            dfs(i)
            if has_cycle:
                return None
    
    # No cycles, so it's a DAG
    # Now compute transitive reduction
    # An edge (u, v) is retained if there is no alternate path from u to v using at least 2 edges
    # i.e., if v is reachable from u without using the direct edge (u, v)
    
    # Build adjacency list for reachability
    adj_list = [[] for _ in range(n)]
    for u, v in adj:
        adj_list[u].append(v)
    
    # For each edge (u, v), check if v is reachable from u without using (u, v)
    # We can do this by temporarily removing (u, v) and checking reachability
    # Or more efficiently: check if there's a path from u to v of length >= 2
    
    # Since n <= 10, we can use BFS/DFS for each edge
    retained = []
    for u, v in adj:
        # Check if there's a path from u to v using at least 2 edges
        # i.e., is v reachable from u without using the direct edge (u, v)?
        # We can do BFS from u, but skip the direct edge to v
        # Actually, we need to check if there's any path from u to v that doesn't use the edge (u,v) directly
        # This is equivalent to: is v reachable from u in the graph with edge (u,v) removed?
        
        # BFS from u, avoiding the direct edge (u, v)
        visited = [False] * n
        queue = [u]
        visited[u] = True
        found = False
        while queue:
            curr = queue.pop(0)
            for neighbor in adj_list[curr]:
                # Skip the direct edge from u to v
                if curr == u and neighbor == v:
                    continue
                if not visited[neighbor]:
                    visited[neighbor] = True
                    if neighbor == v:
                        found = True
                        break
                    queue.append(neighbor)
            if found:
                break
        
        if not found:
            retained.append([u, v])
    
    # Sort and return unique edges
    retained = sorted(set(tuple(e) for e in retained))
    return [list(e) for e in retained]
