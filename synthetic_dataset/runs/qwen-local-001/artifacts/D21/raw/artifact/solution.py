import json

def solve(data):
    events = data.get('events', [])
    start = data['start']
    end = data['end']
    width = data['width']
    fill = data.get('fill', 'none')

    # Collect all unique group names from events
    groups = sorted(set(e['group'] for e in events))

    # Precompute bucket indices for each event that falls in range
    # bucket index = (time - start) // width
    # We only care about events with start <= time < end
    # and value is not None
    # For each group, we'll accumulate sums and counts per bucket index
    # bucket index can be negative if time < start, but we only count in-range
    # Actually, we only sum in-range events, so time must be >= start and < end
    # bucket index for in-range events: (time - start) // width, which is >= 0
    
    # Number of buckets: from start to end, step width
    # Buckets: start, start+width, start+2*width, ... strictly below end
    # So bucket starts: start + i*width < end
    # i ranges from 0 to (end - start - 1) // width inclusive, if end > start
    # If end <= start, no buckets (but start <= end given)
    
    if end <= start:
        return []
    
    num_buckets = (end - start + width - 1) // width  # ceil division
    # Actually: number of i such that start + i*width < end
    # i*width < end - start
    # i < (end - start) / width
    # i_max = floor((end - start - 1) / width) if end > start
    # count = i_max + 1 = floor((end - start - 1) / width) + 1
    # Let's compute directly:
    num_buckets = 0
    if end > start:
        num_buckets = (end - start - 1) // width + 1
    
    # Initialize sums and counts for each group and bucket
    # sums[group][bucket_idx] = sum of values
    # counts[group][bucket_idx] = count of non-null values
    sums = {g: [0] * num_buckets for g in groups}
    counts = {g: [0] * num_buckets for g in groups}
    
    for e in events:
        g = e['group']
        t = e['time']
        v = e['value']
        if v is None:
            continue
        if t < start or t >= end:
            continue
        # Compute bucket index
        idx = (t - start) // width
        # idx should be in [0, num_buckets-1]
        if 0 <= idx < num_buckets:
            sums[g][idx] += v
            counts[g][idx] += 1
    
    # Now build output
    result = []
    for g in groups:
        prev = None  # latest previous nonempty bucket sum, None means no previous nonempty yet
        for i in range(num_buckets):
            bucket_start = start + i * width
            c = counts[g][i]
            if c > 0:
                val = sums[g][i]
                prev = val  # nonempty bucket becomes previous value
            else:
                if fill == 'previous':
                    val = prev  # could be None
                else:
                    val = None
            result.append({
                'group': g,
                'start': bucket_start,
                'count': c,
                'value': val
            })
    
    return result
