def aggregate(x):
    groups = []
    for event in x['events']:
        group = event['group']
        found = False
        for existing in groups:
            if existing == group:
                found = True
                break
        if not found:
            position = len(groups)
            for index in range(len(groups)):
                if group < groups[index]:
                    position = index
                    break
            groups = groups[:position] + [group] + groups[position:]
    width = x['width']
    bucket_count = 0
    if width != 0:
        bucket_count = (x['end'] - x['start'] + width - 1) // width
    if bucket_count < 0:
        bucket_count = 0
    result = []
    for group in groups:
        previous = None
        for index in range(bucket_count):
            start = x['start'] + index * width
            stop = x['start'] + (index + 1) * width
            count = 0
            total = 0
            for event in x['events']:
                if event['group'] == group and event['value'] != None and start <= event['time'] and event['time'] < x['end'] and event['time'] < stop:
                    count = count + 1
                    total = total + event['value']
            if count > 0:
                value = total
            elif x['fill'] == 'previous':
                value = previous
            else:
                value = None
            result = result + [{'group': group, 'start': start, 'count': count, 'value': value}]
            previous = value
    return result

def solve(x):
    return aggregate(x)
