def solve(data):
    lines = list(data["lines"])
    for index, operation in enumerate(data["operations"]):
        at = operation["at"]
        if isinstance(at, bool) or not isinstance(at, int) or at < 0 or at > len(lines):
            return {"error": "range", "operation": index}

        remove = operation.get("remove", [])
        insert = operation.get("insert", [])
        end = at + len(remove)
        if end > len(lines) or lines[at:end] != remove:
            return {"error": "context", "operation": index}

        lines[at:end] = insert

    return {"lines": lines}
