def solve(data):
    values = dict(data.get("initial", {}))
    versions = {key: 0 for key in values}
    version = 0
    transactions = {}
    results = []

    for event in data.get("events", []):
        tx_id = event.get("tx")
        op = event.get("op")

        if op == "begin":
            if tx_id in transactions:
                results.append("exists")
            else:
                transactions[tx_id] = {
                    "snapshot_values": dict(values),
                    "snapshot_versions": dict(versions),
                    "reads": set(),
                    "writes": {},
                }
                results.append("ok")
            continue

        tx = transactions.get(tx_id)
        if tx is None:
            results.append("unknown")
            continue

        if op == "get":
            key = event.get("key")
            tx["reads"].add(key)
            if key in tx["writes"]:
                result = tx["writes"][key]
            else:
                result = tx["snapshot_values"].get(key)
            results.append(result)
        elif op == "set":
            tx["writes"][event.get("key")] = event.get("value")
            results.append("ok")
        elif op == "delete":
            tx["writes"][event.get("key")] = None
            results.append("ok")
        elif op == "abort":
            del transactions[tx_id]
            results.append("ok")
        elif op == "commit":
            checked = tx["reads"] | set(tx["writes"])
            conflicts = sorted(
                key for key in checked
                if versions.get(key, 0) != tx["snapshot_versions"].get(key, 0)
            )
            del transactions[tx_id]
            if conflicts:
                results.append({"committed": False, "conflicts": conflicts})
            else:
                if tx["writes"]:
                    version += 1
                    for key, value in tx["writes"].items():
                        if value is None:
                            values.pop(key, None)
                        else:
                            values[key] = value
                        versions[key] = version
                results.append({"committed": True, "version": version})
        else:
            results.append("unknown")

    return {"results": results, "values": values, "versions": versions, "version": version}
