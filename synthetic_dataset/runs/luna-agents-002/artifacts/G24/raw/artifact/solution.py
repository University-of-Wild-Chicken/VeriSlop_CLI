def solve(data):
    flows = data["flows"]
    deficits = [0] * len(flows)
    positions = [0] * len(flows)
    order = []
    rounds = 0

    while any(positions[i] < len(flow["jobs"]) for i, flow in enumerate(flows)):
        rounds += 1
        for i, flow in enumerate(flows):
            jobs = flow["jobs"]
            if positions[i] >= len(jobs):
                deficits[i] = 0
                continue
            deficits[i] += flow["quantum"]
            while positions[i] < len(jobs) and jobs[positions[i]] <= deficits[i]:
                order.append([i, positions[i]])
                deficits[i] -= jobs[positions[i]]
                positions[i] += 1

    return {"order": order, "rounds": rounds}
