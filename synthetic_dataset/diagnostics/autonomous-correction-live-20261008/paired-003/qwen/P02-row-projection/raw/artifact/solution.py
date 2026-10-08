import json

def solve(data):
    minimum = data["minimum"]
    rows = data["rows"]
    retained = []
    total = 0
    for row in rows:
        if row["enabled"] and row["amount"] >= minimum:
            retained.append({"tag": row["tag"], "amount": row["amount"]})
            total += row["amount"]
    return {"rows": retained, "total": total, "count": len(retained)}
