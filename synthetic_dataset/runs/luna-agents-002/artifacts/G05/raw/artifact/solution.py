def solve(data):
    n = data["n"]
    edges = data["edges"]
    graph = [[] for _ in range(n)]

    for edge_id, (u, v) in enumerate(edges):
        graph[u].append((v, edge_id))
        graph[v].append((u, edge_id))

    discovery = [-1] * n
    low = [0] * n
    bridges = []
    time = 0

    def dfs(vertex, parent_edge):
        nonlocal time
        discovery[vertex] = low[vertex] = time
        time += 1

        for neighbor, edge_id in graph[vertex]:
            if edge_id == parent_edge:
                continue
            if discovery[neighbor] == -1:
                dfs(neighbor, edge_id)
                low[vertex] = min(low[vertex], low[neighbor])
                if low[neighbor] > discovery[vertex]:
                    bridges.append(edge_id)
            else:
                low[vertex] = min(low[vertex], discovery[neighbor])

    for vertex in range(n):
        if discovery[vertex] == -1:
            dfs(vertex, -1)

    return sorted(bridges)
