import heapq


def solve(data):
    if not data:
        return {"jobs": [], "makespan": 0}
    jobs = data.get("jobs", [])
    workers = data.get("workers", 1)
    if not jobs:
        return {"jobs": [], "makespan": 0}

    job_map = {}
    for j in jobs:
        job_map[j["id"]] = j

    # Deduplicate deps and build adjacency
    indeg = {j["id"]: 0 for j in jobs}
    children = {j["id"]: [] for j in jobs}
    for j in jobs:
        deps = list(dict.fromkeys(j.get("deps", [])))
        for d in deps:
            indeg[j["id"]] += 1
            children[d].append(j["id"])

    # Kahn's algorithm to detect cycle and get topological order
    from collections import deque
    q = deque([jid for jid in indeg if indeg[jid] == 0])
    topo = []
    indeg_copy = dict(indeg)
    while q:
        node = q.popleft()
        topo.append(node)
        for ch in children[node]:
            indeg_copy[ch] -= 1
            if indeg_copy[ch] == 0:
                q.append(ch)
    if len(topo) != len(jobs):
        return None

    # Simulate scheduling
    # ready: min-heap of (id) for jobs with all deps done
    # running: min-heap of (finish_time, id)
    # worker_free: min-heap of times when workers become free
    # We process events in time order.
    # At each event time, first process all completions (free workers, mark jobs done, add newly ready jobs),
    # then assign ready jobs to free workers.

    # We'll use a priority queue for events: (time, type, id)
    # type 0 = completion, type 1 = assignment (but we handle assignment immediately after processing completions at same time)
    # Actually, let's do it step by step:
    # 1. Start with all indeg==0 jobs as ready.
    # 2. Use a time-based simulation.

    # Let's use a different approach: event-driven with a single priority queue for completions,
    # and a ready set. At each step, we look at the next completion time, but we also need to assign
    # jobs as soon as workers are free.

    # Better: maintain a min-heap of (finish_time, id) for running jobs.
    # Maintain a min-heap of ready job IDs.
    # Maintain a min-heap of worker free times (initially all 0).
    # Process in order of time.

    # Actually, the standard approach:
    # - ready: min-heap of job IDs (sorted by ID)
    # - running: min-heap of (finish_time, id)
    # - worker_free: min-heap of times (initially [0]*workers)
    # - completed: set of job IDs
    # - start_time, finish_time: dict

    # At each step:
    #   If running is empty and ready is empty: break
    #   If running is empty: current_time = min(worker_free) (but all workers free at same time if none running)
    #   Actually, we need to advance time to the next event.

    # Let me think again. The key insight: we process events in chronological order.
    # Events are: job completions.
    # Between completions, if there are free workers and ready jobs, we assign them.

    # Algorithm:
    # 1. Initialize ready with all jobs having indeg 0.
    # 2. Initialize worker_free = [0] * workers (min-heap)
    # 3. running = [] (min-heap of (finish_time, id))
    # 4. current_time = 0
    # 5. While there are running jobs or ready jobs:
    #    a. If running is not empty, the next event is at min(running).finish_time.
    #       But before that, if there are free workers (worker_free top < next completion time),
    #       we can assign ready jobs at the current free time.
    #    b. Actually, let's process in order:
    #       - If running is empty and ready is empty: break
    #       - If running is empty: current_time = min(worker_free) (all workers free at this time)
    #         Assign as many ready jobs as possible to free workers at current_time.
    #       - If running is not empty:
    #         next_completion = min(running).finish_time
    #         If worker_free top < next_completion and ready is not empty:
    #             Assign ready jobs at worker_free top time.
    #         Else:
    #             Process all completions at next_completion.

    # This is getting complex. Let me use a simpler event-driven approach:

    # We'll use a priority queue for all events: (time, event_type, job_id)
    # event_type 0 = job becomes ready (initially for indeg 0 jobs at time 0)
    # event_type 1 = job completes
    # But we also need to handle worker assignment.

    # Let me try a cleaner simulation:

    ready = []  # min-heap of job IDs
    for jid in job_map:
        if indeg[jid] == 0:
            heapq.heappush(ready, jid)

    running = []  # min-heap of (finish_time, id)
    worker_free = [0] * workers  # min-heap of times
    heapq.heapify(worker_free)

    start_time = {}
    finish_time = {}
    completed = set()
    current_time = 0

    # We need to process in time order. Let's use a loop that always advances to the next relevant time.
    # The next relevant time is either the next worker free time (if there are ready jobs) or the next completion time.

    while running or ready:
        # Determine the next time to process
        next_time = None
        if running:
            next_time = min(next_time, running[0][0]) if next_time is not None else running[0][0]
        if ready and worker_free:
            next_time = min(next_time, worker_free[0]) if next_time is not None else worker_free[0]

        if next_time is None:
            break

        current_time = next_time

        # Process all completions at current_time
        while running and running[0][0] == current_time:
            _, jid = heapq.heappop(running)
            finish_time[jid] = current_time
            completed.add(jid)
            # Free the worker
            heapq.heappush(worker_free, current_time)
            # Check if any children become ready
            for ch in children[jid]:
                indeg[ch] -= 1
                if indeg[ch] == 0:
                    heapq.heappush(ready, ch)

        # Now assign ready jobs to free workers at current_time
        while ready and worker_free and worker_free[0] == current_time:
            jid = heapq.heappop(ready)
            free_time = heapq.heappop(worker_free)
            start_time[jid] = free_time
            ft = free_time + job_map[jid]["duration"]
            heapq.heappush(running, (ft, jid))

    # Build result
    result_jobs = []
    for jid in sorted(job_map.keys()):
        result_jobs.append({
            "id": jid,
            "start": start_time[jid],
            "finish": finish_time[jid]
        })

    makespan = max(finish_time.values()) if finish_time else 0
    return {"makespan": makespan, "jobs": result_jobs}
