def solve(data):
    rows = [
        {"tag": row["tag"], "amount": row["amount"]}
        for row in data["rows"]
        if row["enabled"] and row["amount"] >= data["minimum"]
    ]
    return {
        "rows": rows,
        "total": sum(row["amount"] for row in rows),
        "count": len(rows),
    }
