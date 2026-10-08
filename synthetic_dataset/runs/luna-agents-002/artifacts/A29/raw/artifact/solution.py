import heapq


def solve(data):
    n = data["n"]
    source = data["source"]
    target = data["target"]
    graph = [[] for _ in range(n)]
    for u, v, weight in data["edges"]:
        graph[u].append((v, weight))

    distances = [[] for _ in range(n)]
    distances[source].append(0)
    queue = [(0, source)]

    while queue:
        distance, vertex = heapq.heappop(queue)
        if distance not in distances[vertex]:
            continue

        for neighbor, weight in graph[vertex]:
            candidate = distance + weight
            known = distances[neighbor]
            if candidate in known:
                continue
            if len(known) < 2 or candidate < known[-1]:
                known.append(candidate)
                known.sort()
                if len(known) > 2:
                    known.pop()
                heapq.heappush(queue, (candidate, neighbor))

    return distances[target][1] if len(distances[target]) >= 2 else None
