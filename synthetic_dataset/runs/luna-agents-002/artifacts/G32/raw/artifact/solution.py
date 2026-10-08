def solve(data):
    base = data["base"]
    local = data["local"]
    remote = data["remote"]
    absent = object()

    def encoded(value):
        if value is absent:
            return {"present": False}
        return {"present": True, "value": value}

    merged = {}
    conflicts = []

    for key in sorted(set(base) | set(local) | set(remote)):
        b = base.get(key, absent)
        l = local.get(key, absent)
        r = remote.get(key, absent)

        if l == r:
            chosen = l
        elif l == b:
            chosen = r
        elif r == b:
            chosen = l
        else:
            conflicts.append({
                "key": key,
                "base": encoded(b),
                "local": encoded(l),
                "remote": encoded(r),
            })
            continue

        if chosen is not absent:
            merged[key] = chosen

    return {"merged": merged, "conflicts": conflicts}
