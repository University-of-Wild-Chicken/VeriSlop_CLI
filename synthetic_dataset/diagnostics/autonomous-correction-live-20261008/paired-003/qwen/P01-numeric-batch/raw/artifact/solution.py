import json

def solve(data):
    values = data['values']
    minimum = data['minimum']
    factor = data['factor']
    kept = [v * factor for v in values if v >= minimum]
    return {
        'values': kept,
        'total': sum(kept),
        'count': len(kept)
    }
