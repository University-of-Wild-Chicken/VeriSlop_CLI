import json

def solve(data):
    labels = data["labels"]
    prefix = data["prefix"]
    result = [prefix + label for label in labels if label != ""]
    return {"labels": result, "count": len(result)}
