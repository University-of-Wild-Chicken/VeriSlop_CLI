import json
from collections import deque

def solve(data):
    capacity = data.get('capacity', 0)
    events = data.get('events', [])
    
    buffer = deque()
    waiting_send = deque()
    waiting_recv = deque()
    closed = False
    completed = []
    
    for event in events:
        op = event.get('op')
        
        if op == 'send':
            eid = event.get('id')
            value = event.get('value')
            
            if closed:
                completed.append({'id': eid, 'status': 'closed', 'value': None})
            elif waiting_recv:
                # Rendezvous with waiting receiver
                r_id = waiting_recv.popleft()
                completed.append({'id': r_id, 'status': 'received', 'value': value})
                completed.append({'id': eid, 'status': 'sent', 'value': None})
            elif len(buffer) < capacity:
                buffer.append(value)
                completed.append({'id': eid, 'status': 'sent', 'value': None})
            else:
                waiting_send.append((eid, value))
        
        elif op == 'recv':
            eid = event.get('id')
            
            if buffer:
                value = buffer.popleft()
                completed.append({'id': eid, 'status': 'received', 'value': value})
                # Promote one blocked sender into buffer
                if waiting_send:
                    s_id, s_val = waiting_send.popleft()
                    buffer.append(s_val)
                    completed.append({'id': s_id, 'status': 'sent', 'value': None})
            elif waiting_send:
                # Rendezvous with blocked sender
                s_id, s_val = waiting_send.popleft()
                completed.append({'id': eid, 'status': 'received', 'value': s_val})
                completed.append({'id': s_id, 'status': 'sent', 'value': None})
            elif closed:
                completed.append({'id': eid, 'status': 'closed', 'value': None})
            else:
                waiting_recv.append(eid)
        
        elif op == 'close':
            if not closed:
                closed = True
                # Complete all blocked senders as "closed"
                while waiting_send:
                    s_id, _ = waiting_send.popleft()
                    completed.append({'id': s_id, 'status': 'closed', 'value': None})
                # Complete all waiting receivers
                while waiting_recv:
                    r_id = waiting_recv.popleft()
                    if buffer:
                        value = buffer.popleft()
                        completed.append({'id': r_id, 'status': 'received', 'value': value})
                    else:
                        completed.append({'id': r_id, 'status': 'closed', 'value': None})
    
    return {
        'completed': completed,
        'buffer': list(buffer),
        'waiting_send': [s[0] for s in waiting_send],
        'waiting_recv': list(waiting_recv),
        'closed': closed
    }