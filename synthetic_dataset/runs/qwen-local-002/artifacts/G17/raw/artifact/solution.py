import json

def solve(data):
    initial = data.get('initial', {})
    events = data.get('events', [])
    
    # Global state
    values = dict(initial)
    versions = {k: 0 for k in initial}
    global_version = 0
    
    # Active transactions: tx_id -> {'snapshot': {key: value}, 'snapshot_versions': {key: version}, 'read_set': set(), 'write_set': {key: value_or_None}}
    active_txs = {}
    
    results = []
    
    for event in events:
        op = event.get('op')
        tx = event.get('tx')
        
        if op == 'begin':
            if tx in active_txs:
                results.append('exists')
            else:
                # Snapshot current values and versions
                snapshot = dict(values)
                snapshot_versions = dict(versions)
                active_txs[tx] = {
                    'snapshot': snapshot,
                    'snapshot_versions': snapshot_versions,
                    'read_set': set(),
                    'write_set': {}
                }
                results.append('ok')
        elif op == 'get':
            key = event.get('key')
            if tx not in active_txs:
                results.append('unknown')
            else:
                tx_data = active_txs[tx]
                # Record read
                tx_data['read_set'].add(key)
                # Check own buffered writes first
                if key in tx_data['write_set']:
                    val = tx_data['write_set'][key]
                    results.append(val)  # None for deleted
                else:
                    # See snapshot value
                    if key in tx_data['snapshot']:
                        results.append(tx_data['snapshot'][key])
                    else:
                        results.append(None)
        elif op == 'set':
            key = event.get('key')
            value = event.get('value')
            if tx not in active_txs:
                results.append('unknown')
            else:
                tx_data = active_txs[tx]
                tx_data['write_set'][key] = value
                results.append('ok')
        elif op == 'delete':
            key = event.get('key')
            if tx not in active_txs:
                results.append('unknown')
            else:
                tx_data = active_txs[tx]
                tx_data['write_set'][key] = None  # Tombstone
                results.append('ok')
        elif op == 'abort':
            if tx not in active_txs:
                results.append('unknown')
            else:
                del active_txs[tx]
                results.append('ok')
        elif op == 'commit':
            if tx not in active_txs:
                results.append('unknown')
            else:
                tx_data = active_txs[tx]
                # Compare current versions against snapshot versions for every read or written key
                all_keys = tx_data['read_set'] | set(tx_data['write_set'].keys())
                conflicts = []
                for key in all_keys:
                    snap_ver = tx_data['snapshot_versions'].get(key, 0)
                    curr_ver = versions.get(key, 0)
                    if curr_ver != snap_ver:
                        conflicts.append(key)
                
                # Close the transaction even on failure
                del active_txs[tx]
                
                if conflicts:
                    results.append({'committed': False, 'conflicts': sorted(conflicts)})
                else:
                    # Nonempty write set increments global version once
                    if tx_data['write_set']:
                        global_version += 1
                        # Apply all writes atomically
                        for key, val in tx_data['write_set'].items():
                            if val is None:
                                # Deletion: remove from values, keep tombstone in versions
                                if key in values:
                                    del values[key]
                                versions[key] = global_version
                            else:
                                values[key] = val
                                versions[key] = global_version
                        results.append({'committed': True, 'version': global_version})
                    else:
                        # Empty commit does not increment
                        results.append({'committed': True, 'version': global_version})
        else:
            results.append('unknown')
    
    return {
        'results': results,
        'values': values,
        'versions': versions,
        'version': global_version
    }