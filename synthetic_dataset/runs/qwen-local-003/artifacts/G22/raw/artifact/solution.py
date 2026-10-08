def solve(data):
    ttl = data["ttl"]
    events = data["events"]

    last_token = 0
    lease = None  # dict with owner, token, expires
    results = []

    for ev in events:
        at = ev["at"]
        # Expire lease if necessary before processing event
        if lease is not None and lease["expires"] <= at:
            lease = None

        op = ev["op"]
        if op == "acquire":
            owner = ev["owner"]
            if lease is None:
                last_token += 1
                lease = {
                    "owner": owner,
                    "token": last_token,
                    "expires": at + ttl
                }
                results.append({"ok": True, "token": last_token})
            else:
                if lease["owner"] == owner:
                    # Same live owner: succeed with same token, no expiry extension
                    results.append({"ok": True, "token": lease["token"]})
                else:
                    results.append({"ok": False, "token": None})
        elif op == "renew":
            owner = ev["owner"]
            token = ev["token"]
            if lease is not None and lease["owner"] == owner and lease["token"] == token:
                lease["expires"] = at + ttl
                results.append(True)
            else:
                results.append(False)
        elif op == "release":
            owner = ev["owner"]
            token = ev["token"]
            if lease is not None and lease["owner"] == owner and lease["token"] == token:
                lease = None
                results.append(True)
            else:
                results.append(False)
        else:
            # Unknown op; per spec inputs conform, but keep safe
            results.append(False)

    return {
        "results": results,
        "lease": lease,
        "last_token": last_token
    }