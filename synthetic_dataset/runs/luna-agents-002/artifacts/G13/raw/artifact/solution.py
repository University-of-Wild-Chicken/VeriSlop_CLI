def solve(data):
    n = data["n"]
    edges = sorted({(u, v) for u, v in data["edges"]})

    adjacency = [[] for _ in range(n)]
    indegree = [0] * n
    for u, v in edges:
        adjacency[u].append(v)
        indegree[v] += 1

    # A DAG has a topological ordering containing every vertex.
    queue = [vertex for vertex in range(n) if indegree[vertex] == 0]
    index = 0
    visited = 0
    while index < len(queue):
        u = queue[index]
        index += 1
        visited += 1
        for v in adjacency[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    if visited != n:
        return None

    reduced = []
    for omitted_u, omitted_v in edges:
        stack = [omitted_u]
        seen = {omitted_u}
        while stack:
            u = stack.pop()
            for v in adjacency[u]:
                if u == omitted_u and v == omitted_v:
                    continue
                if v == omitted_v:
                    reduced.append([omitted_u, omitted_v])
                    stack.clear()
                    break
                if v not in seen:
                    seen.add(v)
                    stack.append(v)

    return reduced