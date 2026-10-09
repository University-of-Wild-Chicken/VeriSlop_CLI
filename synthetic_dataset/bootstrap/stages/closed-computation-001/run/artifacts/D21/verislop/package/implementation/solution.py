def stats(x, group):
    rows = []
    width = x['width']
    bins = 0
    if width != 0:
        bins = (x['end'] - x['start'] + width - 1) // width
    if bins < 0:
        bins = 0
    for i in range(bins):
        start = x['start'] + i * width
        stop = x['start'] + (i + 1) * width
        count = 0
        total = 0
        for event in x['events']:
            if event['group'] == group and event['value'] is not None and start <= event['time'] and event['time'] < x['end'] and event['time'] < stop:
                count = count + 1
                total = total + event['value']
        rows = rows + [{'group': group, 'start': start, 'count': count, 'sum': total}]
    return rows

def traverse(x, items):
    rows = []
    previous = None
    for item in items:
        value = None
        if item['count'] > 0:
            value = item['sum']
            previous = item['sum']
        elif x['fill'] == 'previous':
            value = previous
        rows = rows + [{'group': item['group'], 'start': item['start'], 'count': item['count'], 'value': value}]
    return rows

def solve(x):
    groups = []
    for event in x['events']:
        group = event['group']
        found = False
        for existing in groups:
            if existing == group:
                found = True
        if not found:
            ordered = []
            inserted = False
            for existing in groups:
                if not inserted and group < existing:
                    ordered = ordered + [group]
                    inserted = True
                ordered = ordered + [existing]
            if not inserted:
                ordered = ordered + [group]
            groups = ordered
    rows = []
    for group in groups:
        rows = rows + traverse(x, stats(x, group))
    return rows
