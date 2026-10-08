import json

def solve(data):
    events = data.get('events', [])
    # state: key -> (revision, op, value)
    state = {}
    ignored = []
    
    for idx, ev in enumerate(events):
        key = ev.get('key')
        rev = ev.get('revision')
        op = ev.get('op')
        value = ev.get('value')
        
        if key not in state:
            # First event for this key wins
            if op == 'put':
                state[key] = (rev, 'put', value)
            else:  # delete
                state[key] = (rev, 'delete', None)
        else:
            cur_rev, cur_op, cur_val = state[key]
            if rev > cur_rev:
                # Replace
                if op == 'put':
                    state[key] = (rev, 'put', value)
                else:  # delete
                    state[key] = (rev, 'delete', None)
            else:
                # Equal or lower revision: ignore
                ignored.append(idx)
    
    items = []
    tombstones = []
    
    for key in sorted(state.keys()):
        rev, op, val = state[key]
        if op == 'put':
            items.append({'key': key, 'revision': rev, 'value': val})
        else:
            tombstones.append({'key': key, 'revision': rev})
    
    return {
        'items': items,
        'tombstones': tombstones,
        'ignored': ignored
    }