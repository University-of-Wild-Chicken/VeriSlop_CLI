def solve(data):
    stock = dict(data.get("stock", {}))
    events = data.get("events", [])

    results = []
    status = {}
    reserved = {}

    for ev in events:
        op = ev.get("op")
        if op == "reserve":
            eid = ev.get("id")
            items = ev.get("items", {})
            if eid in reserved:
                results.append("exists")
                continue
            # Check availability for all items
            ok = True
            for k, q in items.items():
                if stock.get(k, 0) < q:
                    ok = False
                    break
            if not ok:
                results.append("insufficient")
                continue
            # Atomically subtract
            for k, q in items.items():
                stock[k] = stock.get(k, 0) - q
            reserved[eid] = dict(items)
            status[eid] = "reserved"
            results.append("reserved")
        elif op == "commit":
            eid = ev.get("id")
            if eid not in reserved:
                results.append("unknown")
                continue
            # Consume permanently: reserved items are already subtracted from stock
            del reserved[eid]
            status[eid] = "committed"
            results.append("committed")
        elif op == "cancel":
            eid = ev.get("id")
            if eid not in reserved:
                results.append("unknown")
                continue
            # Restore all reserved items
            for k, q in reserved[eid].items():
                stock[k] = stock.get(k, 0) + q
            del reserved[eid]
            status[eid] = "cancelled"
            results.append("cancelled")
        else:
            # Unknown op: ignore (should not happen per spec)
            continue

    return {
        "results": results,
        "available": stock,
        "status": status
    }