import json

def solve(data):
    events = data.get('events', [])
    total = 0
    next_seq = 1
    results = []
    # Store all seen events: seq -> delta (first arrival is authoritative)
    seen = {}
    # Buffer for events that are not yet contiguous from next_seq
    # We need to keep track of buffered events in order of arrival? 
    # Actually, the spec says: "A new arrival is buffered, then apply and remove every contiguous buffered event starting at next, incrementing next."
    # And "pending sorted [seq,delta] pairs".
    # The buffer should contain events that have arrived but not yet applied.
    # When a new event arrives:
    # 1. If seq already in seen:
    #    - if delta matches: result "duplicate"
    #    - else: result "conflict"
    #    - no state change (so it doesn't affect buffer or total)
    # 2. If seq not in seen:
    #    - mark as seen (first arrival is authoritative)
    #    - add to buffer
    #    - then flush: while next_seq is in buffer, apply it (total += delta), remove from buffer, next_seq += 1
    #    - result is "applied" if this specific seq was consumed in this flush, else "buffered"
    
    # We need a buffer that allows us to check if next_seq is present and remove it.
    # Since we need to return pending sorted by seq, and we need to efficiently check/remove next_seq,
    # we can use a dict for the buffer: seq -> delta.
    # But wait, the flush condition is "contiguous buffered event starting at next".
    # So we apply next_seq if it's in the buffer, then next_seq+1, etc.
    
    buffer = {}  # seq -> delta
    
    for event in events:
        seq = event['seq']
        delta = event['delta']
        
        if seq in seen:
            if seen[seq] == delta:
                results.append("duplicate")
            else:
                results.append("conflict")
            # No state change
        else:
            # First arrival for this sequence
            seen[seq] = delta
            buffer[seq] = delta
            
            # Flush contiguous events starting at next_seq
            # We need to check if next_seq is in buffer, and if so, apply and remove, then check next_seq+1, etc.
            # But we only care if *this* seq was consumed in this flush.
            # Let's simulate the flush.
            
            # We'll keep a flag to see if this seq gets applied.
            # But note: the flush applies ALL contiguous events starting at next_seq.
            # So we need to actually perform the flush to update total and next_seq.
            
            # Let's do the flush now.
            # We'll use a temporary variable to track the current next during flush?
            # No, we should update the actual next_seq and total.
            
            # But we need to know if *this* seq was part of the flush.
            # We can check: if seq == next_seq, and it was in buffer, then it will be applied first.
            # But what if seq > next_seq, but next_seq was already in buffer from before? Then next_seq gets applied, then next_seq+1, etc., and maybe seq gets applied too.
            
            # So we need to actually run the flush loop.
            
            # Let's save the current next_seq before flush to see how far it goes.
            # Actually, we can just run the flush and check if seq was removed from buffer during this flush.
            
            # But we already added seq to buffer. So if seq is in the contiguous chain starting at next_seq, it will be removed.
            
            # Let's run the flush:
            # while next_seq in buffer:
            #   total += buffer[next_seq]
            #   del buffer[next_seq]
            #   next_seq += 1
            
            # But we need to know if *this* seq was consumed. We can check if seq was in the range [old_next, new_next-1].
            
            old_next = next_seq
            while next_seq in buffer:
                total += buffer[next_seq]
                del buffer[next_seq]
                next_seq += 1
            
            # Now, was this seq consumed?
            # It was consumed if old_next <= seq < next_seq
            if old_next <= seq < next_seq:
                results.append("applied")
            else:
                results.append("buffered")
    
    # Prepare pending: sorted [seq, delta] pairs from buffer
    pending = [[seq, buffer[seq]] for seq in sorted(buffer.keys())]
    
    return {
        "results": results,
        "next": next_seq,
        "total": total,
        "pending": pending
    }