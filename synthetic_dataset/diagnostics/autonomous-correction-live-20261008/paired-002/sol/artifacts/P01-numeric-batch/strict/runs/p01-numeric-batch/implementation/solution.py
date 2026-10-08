def solve(x):
    values = [v * x["factor"] for v in x["values"] if x["minimum"] <= v]
    return {"values": values, "total": sum(values), "count": len(values)}
