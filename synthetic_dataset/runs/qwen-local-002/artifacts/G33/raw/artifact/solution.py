import json

def solve(data):
    events = data.get('events', [])
    n = len(events)
    if n == 0:
        return {'order': [], 'relations': []}
    
    # Build relations matrix
    relations = [['equal'] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                relations[i][j] = 'equal'
                continue
            ci = events[i]['clock']
            cj = events[j]['clock']
            # Check if i before j: every component of i <= j and at least one strict
            before = True
            strict = False
            for k in range(len(ci)):
                if ci[k] > cj[k]:
                    before = False
                    break
                if ci[k] < cj[k]:
                    strict = True
            if before and strict:
                relations[i][j] = 'before'
            else:
                # Check if i after j: every component of j <= i and at least one strict
                after = True
                strict_after = False
                for k in range(len(ci)):
                    if cj[k] > ci[k]:
                        after = False
                        break
                    if cj[k] < ci[k]:
                        strict_after = True
                if after and strict_after:
                    relations[i][j] = 'after'
                else:
                    relations[i][j] = 'concurrent'
    
    # Build graph for topological sort: edge i -> j means i before j
    # We need lexicographically smallest topological ordering
    # Use Kahn's algorithm with a min-heap (priority queue) for eligible nodes
    import heapq
    
    # in_degree[i] = number of nodes that must come before i
    in_degree = [0] * n
    # adjacency: adj[i] = list of j such that i before j
    adj = [[] for _ in range(n)]
    
    for i in range(n):
        for j in range(n):
            if i != j and relations[i][j] == 'before':
                adj[i].append(j)
                in_degree[j] += 1
    
    # Initialize heap with all nodes with in_degree 0
    heap = []
    for i in range(n):
        if in_degree[i] == 0:
            heapq.heappush(heap, events[i]['id'])
    
    order = []
    # Map id to index for quick lookup
    id_to_idx = {events[i]['id']: i for i in range(n)}
    
    while heap:
        node_id = heapq.heappop(heap)
        order.append(node_id)
        idx = id_to_idx[node_id]
        for neighbor in adj[idx]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                heapq.heappush(heap, events[neighbor]['id'])
    
    return {'order': order, 'relations': relations}
