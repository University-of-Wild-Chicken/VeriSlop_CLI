def solve(data):
    latest = {}
    ignored = []

    for index, event in enumerate(data["events"]):
        key = event["key"]
        revision = event["revision"]
        current = latest.get(key)

        if current is not None and revision <= current[0]:
            ignored.append(index)
            continue

        op = event["op"]
        latest[key] = (revision, op, event.get("value"))

    items = []
    tombstones = []
    for key in sorted(latest):
        revision, op, value = latest[key]
        if op == "put":
            items.append({"key": key, "revision": revision, "value": value})
        else:
            tombstones.append({"key": key, "revision": revision})

    return {"items": items, "tombstones": tombstones, "ignored": ignored}
