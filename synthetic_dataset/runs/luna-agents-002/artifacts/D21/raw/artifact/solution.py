def solve(data):
    events = data["events"]
    start = data["start"]
    end = data["end"]
    width = data["width"]
    fill = data["fill"]

    groups = sorted({event["group"] for event in events})
    buckets = list(range(start, end, width))
    grouped = {group: {} for group in groups}

    for event in events:
        t = event["time"]
        value = event["value"]
        if start <= t < end and value is not None:
            bucket_start = start + ((t - start) // width) * width
            total, count = grouped[event["group"]].get(bucket_start, (0, 0))
            grouped[event["group"]][bucket_start] = (total + value, count + 1)

    result = []
    for group in groups:
        previous = None
        for bucket_start in buckets:
            total, count = grouped[group].get(bucket_start, (0, 0))
            if count:
                value = total
                previous = total
            else:
                value = previous if fill == "previous" else None
            result.append({
                "group": group,
                "start": bucket_start,
                "count": count,
                "value": value,
            })
    return result
