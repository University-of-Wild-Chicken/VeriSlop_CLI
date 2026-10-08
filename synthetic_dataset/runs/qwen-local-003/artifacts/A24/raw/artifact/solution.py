import json

def solve(data):
    points = data.get("points", [])
    bounds = data.get("bounds", [0, 0])
    lo, hi = bounds[0], bounds[1]
    if not points:
        return {"cost": 0, "point": [lo, lo]}
    best_cost = None
    best_point = [lo, lo]
    for x in range(lo, hi + 1):
        for y in range(lo, hi + 1):
            max_w = 0
            for px, py, w in points:
                val = w * (abs(x - px) + abs(y - py))
                if val > max_w:
                    max_w = val
            if best_cost is None or max_w < best_cost or (max_w == best_cost and (x < best_point[0] or (x == best_point[0] and y < best_point[1]))):
                best_cost = max_w
                best_point = [x, y]
    return {"cost": best_cost, "point": best_point}
