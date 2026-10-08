def solve(x):
    rows = []
    total = 0
    for row in x['rows']:
        if row['enabled'] and x['minimum'] <= row['amount']:
            rows.append({'tag': row['tag'], 'amount': row['amount']})
            total += row['amount']
    return {'rows': rows, 'total': total, 'count': len(rows)}
