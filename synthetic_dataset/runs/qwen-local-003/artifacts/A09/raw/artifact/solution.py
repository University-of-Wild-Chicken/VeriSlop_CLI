import json

def solve(data):
    dims = data["dimensions"]
    n = len(dims) - 1
    # cost[i][j] = minimum cost to multiply matrices i..j (inclusive)
    # expr[i][j] = lexicographically smallest expression achieving that cost
    cost = [[0] * n for _ in range(n)]
    expr = [["A" + str(i) for i in range(n)] for _ in range(n)]

    for length in range(2, n + 1):
        for i in range(n - length + 1):
            j = i + length - 1
            best_cost = None
            best_expr = None
            for k in range(i, j):
                c = cost[i][k] + cost[k + 1][j] + dims[i] * dims[k + 1] * dims[j + 1]
                e = "(" + expr[i][k] + "*" + expr[k + 1][j] + ")"
                if best_cost is None or c < best_cost or (c == best_cost and e < best_expr):
                    best_cost = c
                    best_expr = e
            cost[i][j] = best_cost
            expr[i][j] = best_expr

    return {"cost": cost[0][n - 1], "expression": expr[0][n - 1]}
