import heapq

def solve(data):
    flows = data.get('flows', [])
    n = len(flows)
    if n == 0:
        return {'order': [], 'rounds': 0}

    # Initialize state
    # Each flow: [quantum, jobs_list, deficit, next_job_index]
    state = []
    for i, f in enumerate(flows):
        state.append({
            'quantum': f['quantum'],
            'jobs': f['jobs'],
            'deficit': 0,
            'next': 0
        })

    order = []
    rounds = 0
    total_jobs = sum(len(f['jobs']) for f in flows)
    emitted = 0

    while emitted < total_jobs:
        rounds += 1
        # Visit flows in ascending index order
        for i in range(n):
            s = state[i]
            if s['next'] >= len(s['jobs']):
                # Empty flow resets deficit to zero
                s['deficit'] = 0
                continue
            
            # Nonempty flow adds its quantum
            s['deficit'] += s['quantum']
            
            # Emit as many consecutive head packets as deficit covers
            while s['next'] < len(s['jobs']):
                job_size = s['jobs'][s['next']]
                if s['deficit'] >= job_size:
                    s['deficit'] -= job_size
                    order.append([i, s['next']])
                    s['next'] += 1
                    emitted += 1
                else:
                    # Never skip an oversized head packet
                    break

    return {'order': order, 'rounds': rounds}