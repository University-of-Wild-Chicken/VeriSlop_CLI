import heapq


def solve(data):
    events = data["events"]
    n = len(events)
    relations = [[None] * n for _ in range(n)]
    edges = [[] for _ in range(n)]
    indegree = [0] * n

    for i in range(n):
        a = events[i]["clock"]
        for j in range(n):
            b = events[j]["clock"]
            less = all(x <= y for x, y in zip(a, b))
            greater = all(x >= y for x, y in zip(a, b))
            if less and greater:
                relation = "equal"
            elif less:
                relation = "before"
                edges[i].append(j)
                indegree[j] += 1
            elif greater:
                relation = "after"
            else:
                relation = "concurrent"
            relations[i][j] = relation

    eligible = [(event["id"], i) for i, event in enumerate(events) if indegree[i] == 0]
    heapq.heapify(eligible)
    order = []
    while eligible:
        event_id, i = heapq.heappop(eligible)
        order.append(event_id)
        for j in edges[i]:
            indegree[j] -= 1
            if indegree[j] == 0:
                heapq.heappush(eligible, (events[j]["id"], j))

    return {"order": order, "relations": relations}
