def solve(x0):
    values = x0["values"]
    minimum = x0["minimum"]
    factor = x0["factor"]
    filtered = []
    for x1 in values:
        if minimum <= x1:
            filtered.append(x1)
    mapped = []
    for x1 in filtered:
        mapped.append(x1 * factor)
    total = 0
    for x1 in mapped:
        total = total + x1
    count = len(filtered)
    return {"values": mapped, "total": total, "count": count}
