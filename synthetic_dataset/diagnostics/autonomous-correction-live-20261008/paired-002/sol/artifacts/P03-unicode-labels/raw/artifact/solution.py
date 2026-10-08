def solve(data):
    labels = [data["prefix"] + label for label in data["labels"] if label != ""]
    return {"labels": labels, "count": len(labels)}
