def solve(data):
    values = [value * data["factor"] for value in data["values"] if value >= data["minimum"]]
    return {"values": values, "total": sum(values), "count": len(values)}
