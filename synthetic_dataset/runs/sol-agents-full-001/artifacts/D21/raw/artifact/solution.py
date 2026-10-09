def solve(data):
    start = data['start']
    end = data['end']
    width = data['width']
    groups = {}
    for event in data['events']:
        buckets = groups.setdefault(event['group'], {})
        time = event['time']
        value = event['value']
        if start <= time < end and value is not None:
            bucket = (time - start) // width
            total, count = buckets.get(bucket, (0, 0))
            buckets[bucket] = (total + value, count + 1)
    result = []
    fill_previous = data['fill'] == 'previous'
    for group in sorted(groups):
        previous = None
        buckets = groups[group]
        for index, bucket_start in enumerate(range(start, end, width)):
            total, count = buckets.get(index, (0, 0))
            if count:
                value = total
                previous = total
            else:
                value = previous if fill_previous else None
            result.append({'group': group, 'start': bucket_start, 'count': count, 'value': value})
    return result
