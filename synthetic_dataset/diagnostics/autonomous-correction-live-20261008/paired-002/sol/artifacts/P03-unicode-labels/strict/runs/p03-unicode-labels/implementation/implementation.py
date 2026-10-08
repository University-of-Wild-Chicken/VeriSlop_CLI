def solve(x):
    labels = [x["prefix"] + label for label in x["labels"] if label != ""]
    return {"labels": labels, "count": len(labels)}
