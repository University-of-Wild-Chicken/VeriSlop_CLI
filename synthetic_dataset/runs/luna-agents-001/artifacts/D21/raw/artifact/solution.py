def solve(data):
    events = data["events"]
    start = data["start"]
    end = data["end"]
    width = data["width"]
    fill = data["fill"]

    groups = sorted({event["group"] for event in events})
    buckets = list(range(start, end, width))
    sums = {group: {} for group in groups}
    counts = {group: {} for group in groups}

    for event in events:
        time = event["time"]
        value = event["value"]
        if start <= time < end and value is not None:
            bucket_start = start + ((time - start) // width) * width
            group = event["group"]
            sums[group][bucket_start] = sums[group].get(bucket_start, 0) + value
            counts[group][bucket_start] = counts[group].get(bucket_start, 0) + 1

    result = []
    for group in groups:
        previous = None
        for bucket_start in buckets:
            count = counts[group].get(bucket_start, 0)
            if count:
                value = sums[group][bucket_start]
                previous = value
            elif fill == "previous":
                value = previous
            else:
                value = None
            result.append({
                "group": group,
                "start": bucket_start,
                "count": count,
                "value": value,
            })
    return result
