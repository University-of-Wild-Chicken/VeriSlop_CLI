def solve(x):
    if x['width'] <= 0 or x['start'] > x['end'] or (x['fill'] != 'none' and x['fill'] != 'previous'):
        return []
    groups = []
    for event in x['events']:
        found = False
        for group in groups:
            if group == event['group']:
                found = True
                break
        if not found:
            groups = groups + [event['group']]
    ordered = []
    for group in groups:
        position = len(ordered)
        for index in range(len(ordered)):
            if group < ordered[index]:
                position = index
                break
        ordered = ordered[:position] + [group] + ordered[position:]
    rows = []
    buckets = (x['end'] - x['start'] + x['width'] - 1) // x['width']
    for group in ordered:
        previous = None
        for index in range(buckets):
            start = x['start'] + index * x['width']
            count = 0
            total = 0
            for event in x['events']:
                if event['group'] == group and event['value'] is not None and start <= event['time'] and event['time'] < x['end'] and event['time'] < start + x['width']:
                    count += 1
                    total += event['value']
            if count > 0:
                value = total
                previous = total
            elif x['fill'] == 'previous':
                value = previous
            else:
                value = None
            rows.append({'group': group, 'start': start, 'count': count, 'value': value})
    return rows
