def solve(inp):
    labels = inp["labels"]
    prefix = inp["prefix"]
    filtered = []
    for lbl in labels:
        if len(lbl) > 0:
            filtered.append(lbl)
    mapped = []
    for lbl in filtered:
        mapped.append(prefix + lbl)
    return {"labels": mapped, "count": len(filtered)}
