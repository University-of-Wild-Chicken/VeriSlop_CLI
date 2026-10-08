import heapq


def solve(data):
    n = data["n"]
    edges = data["edges"]
    source = data["source"]
    target = data["target"]

    # Build adjacency list
    adj = [[] for _ in range(n)]
    for u, v, w in edges:
        adj[u].append((v, w))

    # Dijkstra to find shortest distance from source to all nodes
    INF = float('inf')
    dist = [INF] * n
    dist[source] = 0
    pq = [(0, source)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))

    # If target is unreachable, no walks exist
    if dist[target] == INF:
        return None

    # Build shortest path DAG: edge (u,v,w) is in DAG if dist[u] + w == dist[v]
    # We need to find the second smallest distinct total weight among all walks.
    # A walk's total weight = shortest distance + extra, where extra >= 0.
    # The smallest weight is dist[target].
    # We need the second smallest distinct weight.
    #
    # Approach: Use a modified Dijkstra-like algorithm that tracks the two smallest
    # distinct distances to each node. However, since walks can revisit vertices,
    # we need to be careful.
    #
    # Actually, let's think differently. The set of all walk weights from source to target
    # is a set of non-negative integers (or reals, but weights are positive integers per problem).
    # The smallest is dist[target]. We need the second smallest distinct value.
    #
    # We can use a priority queue approach where we explore walks in order of total weight,
    # but we need to avoid infinite loops. Since all weights are positive, any walk that
    # revisits a vertex has weight strictly greater than the shortest path to that vertex.
    #
    # Let's use a state (node, total_weight) and track the two smallest distinct weights
    # for each node. But this could be infinite if there are cycles.
    #
    # Better approach: The second shortest walk weight can be found by considering:
    # 1. The shortest path weight: d1 = dist[target]
    # 2. Any walk that deviates from the shortest path DAG.
    #
    # Actually, a cleaner approach: Use a modified Dijkstra that keeps track of the
    # two smallest distinct distances to each node. Since all edge weights are positive,
    # the number of distinct distances we need to consider is bounded.
    #
    # Let's use a priority queue with states (weight, node). We'll track for each node
    # the set of distinct weights we've already processed. We stop when we've found
    # two distinct weights for the target.
    #
    # But this could be problematic with cycles. However, since we only need the second
    # smallest, and all weights are positive, we can bound the search.
    #
    # Let's try a different approach: enumerate all possible "deviations" from the
    # shortest path. The second shortest walk either:
    # a) Uses a different edge on the shortest path DAG, or
    # b) Takes a detour (cycle) somewhere.
    #
    # Actually, the most robust approach for small n (<=30) is to use a priority queue
    # that explores walks in order of total weight, keeping track of the best two distinct
    # weights for each node. Since weights are positive, we can terminate when the
    # minimum weight in the queue exceeds the second best weight for target.
    #
    # Let's implement this:
    # - dist1[v] = smallest distinct weight to v
    # - dist2[v] = second smallest distinct weight to v
    # - Use a priority queue of (weight, node)
    # - When we pop (w, v), if w > dist2[v], skip
    # - If w == dist1[v] or w == dist2[v], skip (already processed)
    # - Otherwise, this is a new distinct weight for v
    #   - If dist1[v] is INF, set dist1[v] = w
    #   - Else if w < dist2[v], set dist2[v] = w
    #   - If v == target and dist2[target] is set, we can return dist2[target]
    # - For each edge (v, u, w2), new_weight = w + w2
    #   - If new_weight < dist2[u] (or dist1[u] if dist2[u] is INF), push (new_weight, u)
    #
    # But we need to be careful: we might push many states. However, since we only care
    # about the two smallest distinct weights per node, and weights are positive, this
    # should be manageable for n<=30.
    #
    # Actually, let's reconsider. The issue is that with cycles, we could have infinitely
    # many distinct weights. But we only need the second smallest for target. So we can
    # stop as soon as we've found two distinct weights for target.
    #
    # Let's implement this carefully.

    # Initialize
    best1 = [INF] * n  # smallest distinct weight
    best2 = [INF] * n  # second smallest distinct weight

    pq = [(0, source)]
    heapq.heapify(pq)

    # We'll track how many distinct weights we've found for target
    # When we pop a weight for target that is different from best1[target] and best2[target],
    # we update. If best2[target] gets set, we can return it.

    while pq:
        w, u = heapq.heappop(pq)

        # If this weight is not one of the two best for u, skip
        if w > best2[u]:
            continue
        if w == best1[u] or w == best2[u]:
            continue

        # This is a new distinct weight for u
        if best1[u] == INF:
            best1[u] = w
        elif w < best2[u]:
            best2[u] = w
        else:
            # w >= best2[u], but we already checked w != best2[u], so this shouldn't happen
            # unless w > best2[u], which we already skipped
            continue

        # If u is target and we now have two distinct weights, return best2[target]
        if u == target and best2[u] != INF:
            return best2[u]

        # Explore outgoing edges
        for v, ew in adj[u]:
            nw = w + ew
            # Only push if nw could be one of the two best for v
            if nw < best2[v]:
                heapq.heappush(pq, (nw, v))

    # If we exit the loop, check if we have two distinct weights for target
    if best2[target] != INF:
        return best2[target]
    else:
        return None
