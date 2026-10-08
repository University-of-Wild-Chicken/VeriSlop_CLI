import json

def solve(data):
    events = data.get('events', [])
    
    # State for MVCC
    # versions[key] = list of (at, value) where value is int or None (tombstone)
    # We maintain versions in chronological order, with at nondecreasing.
    # For duplicate timestamps, only the latest write is kept (per spec: "keep only the latest write at a duplicate timestamp")
    # But note: the spec says "For each key keep only the latest write at a duplicate timestamp" - this applies to writes.
    # Deletions are also writes of tombstones.
    
    versions = {}  # key -> list of [at, value]
    floor = 0
    reads = []
    
    # Process events in order
    for event in events:
        op = event.get('op')
        
        if op == 'write':
            at = event['at']
            key = event['key']
            value = event['value']
            
            if key not in versions:
                versions[key] = []
            
            # Check if there's already a version at this timestamp
            # If so, replace it (keep only latest write at duplicate timestamp)
            # Since timestamps are nondecreasing, the latest at this timestamp would be the last one if at == current at
            # But we need to be careful: if there are multiple writes at same timestamp, we keep only the last one.
            # Since we process in order, if the last version has the same 'at', we replace it.
            
            if versions[key] and versions[key][-1][0] == at:
                # Replace the last version (same timestamp)
                versions[key][-1] = [at, value]
            else:
                versions[key].append([at, value])
                
        elif op == 'delete':
            at = event['at']
            key = event['key']
            
            if key not in versions:
                versions[key] = []
            
            # Deletion is a null tombstone
            if versions[key] and versions[key][-1][0] == at:
                # Replace the last version (same timestamp)
                versions[key][-1] = [at, None]
            else:
                versions[key].append([at, None])
                
        elif op == 'compact':
            new_floor = event['floor']
            floor = new_floor
            
            # Compaction: retain the newest version <= floor (including tombstone) plus EVERY version > floor
            # For each key, we need to compact the versions list.
            # The retained versions should be:
            # 1. The newest version with at <= floor (if any)
            # 2. All versions with at > floor
            
            for key in list(versions.keys()):
                if key not in versions:
                    continue
                
                vlist = versions[key]
                if not vlist:
                    continue
                
                # Find the newest version with at <= floor
                # Since vlist is sorted by at, we can find the last one with at <= floor
                baseline_idx = -1
                for i in range(len(vlist)):
                    if vlist[i][0] <= floor:
                        baseline_idx = i
                    else:
                        break
                
                # Build new list
                new_vlist = []
                if baseline_idx >= 0:
                    new_vlist.append(vlist[baseline_idx])
                
                # Add all versions with at > floor
                for i in range(len(vlist)):
                    if vlist[i][0] > floor:
                        new_vlist.append(vlist[i])
                
                versions[key] = new_vlist
                
        elif op == 'read':
            at = event['at']
            
            # Read returns whole nondeleted snapshot at its timestamp using preceding retained versions
            # For each key, find the newest version with at <= at
            # If the value is None (tombstone), the key is absent
            # If no version with at <= at, the key is absent
            
            snapshot = {}
            for key, vlist in versions.items():
                if not vlist:
                    continue
                
                # Find the newest version with at <= at
                # Since vlist is sorted by at, we can find the last one with at <= at
                found = None
                for i in range(len(vlist)):
                    if vlist[i][0] <= at:
                        found = vlist[i]
                    else:
                        break
                
                if found is not None and found[1] is not None:
                    snapshot[key] = found[1]
            
            reads.append(snapshot)
    
    # Prepare output
    # versions maps keys to chronological [{at, value}] retained history
    # value should be null for tombstones
    output_versions = {}
    for key, vlist in versions.items():
        output_versions[key] = [{'at': v[0], 'value': v[1]} for v in vlist]
    
    return {
        'reads': reads,
        'versions': output_versions,
        'floor': floor
    }