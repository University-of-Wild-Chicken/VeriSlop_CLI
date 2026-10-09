"""Deterministic graph and state-machine tasks for the local coding benchmark.

The oracles and literal anchors are fixed independently of model completions.
Only the two public cases should be included in candidate prompts.
"""
from __future__ import annotations

import copy
import heapq
import itertools
import random
from collections import defaultdict, deque
from functools import cmp_to_key, lru_cache


def _topo(n, edges):
    adjacency = [set() for _ in range(n)]
    indegree = [0] * n
    for u, v in edges:
        if v not in adjacency[u]:
            adjacency[u].add(v)
            indegree[v] += 1
    ready = [u for u in range(n) if indegree[u] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in sorted(adjacency[u]):
            indegree[v] -= 1
            if indegree[v] == 0:
                heapq.heappush(ready, v)
    return order, adjacency


def _g01(d):
    order, _ = _topo(d['n'], d['edges'])
    return {'order': order, 'blocked': sorted(set(range(d['n'])) - set(order))}


def _g02(d):
    n = d['n']
    reachable = [[False] * n for _ in range(n)]
    for i in range(n):
        reachable[i][i] = True
    for u, v in d['edges']:
        reachable[u][v] = True
    for k in range(n):
        for i in range(n):
            for j in range(n):
                reachable[i][j] |= reachable[i][k] and reachable[k][j]
    left = set(range(n))
    components = []
    while left:
        u = min(left)
        component = sorted(v for v in left if reachable[u][v] and reachable[v][u])
        components.append(component)
        left.difference_update(component)
    owner = {v: i for i, component in enumerate(components) for v in component}
    dag = sorted({(owner[u], owner[v]) for u, v in d['edges'] if owner[u] != owner[v]})
    return {'components': components, 'dag': [list(edge) for edge in dag]}


def _g03(d):
    n, source, edges = d['n'], d['source'], d['edges']
    distance = [None] * n
    distance[source] = 0
    for _ in range(n - 1):
        old = distance[:]
        for u, v, cost in edges:
            if old[u] is not None and (distance[v] is None or old[u] + cost < distance[v]):
                distance[v] = old[u] + cost
    affected = set()
    for u, v, cost in edges:
        if distance[u] is not None and (distance[v] is None or distance[u] + cost < distance[v]):
            affected.add(v)
    while True:
        enlarged = affected | {v for u, v, _ in edges if u in affected}
        if enlarged == affected:
            break
        affected = enlarged
    return ['-inf' if v in affected else distance[v] for v in range(n)]


def _g04(d):
    adjacency = [[] for _ in range(d['n'])]
    for u, v, cost in d['edges']:
        adjacency[u].append((v, cost))
    source, target = d['source'], d['target']
    best = {source: (0, 0, (source,))}
    todo = [(0, 0, (source,), source)]
    while todo:
        cost, hops, path, u = heapq.heappop(todo)
        if best[u] != (cost, hops, path):
            continue
        for v, weight in adjacency[u]:
            candidate = (cost + weight, hops + 1, path + (v,))
            if v not in best or candidate < best[v]:
                best[v] = candidate
                heapq.heappush(todo, (*candidate, v))
    if target not in best:
        return None
    cost, _, path = best[target]
    return {'cost': cost, 'path': list(path)}


def _component_count(n, edges, removed_vertex=None, removed_edge=None):
    adjacency = [set() for _ in range(n)]
    for i, (u, v) in enumerate(edges):
        if i != removed_edge and u != removed_vertex and v != removed_vertex:
            adjacency[u].add(v)
            adjacency[v].add(u)
    unseen = set(range(n)) - ({removed_vertex} if removed_vertex is not None else set())
    count = 0
    while unseen:
        count += 1
        todo = [unseen.pop()]
        while todo:
            u = todo.pop()
            neighbors = adjacency[u] & unseen
            unseen.difference_update(neighbors)
            todo.extend(neighbors)
    return count


def _g05(d):
    baseline = _component_count(d['n'], d['edges'])
    return [i for i in range(len(d['edges']))
            if _component_count(d['n'], d['edges'], removed_edge=i) > baseline]


def _g06(d):
    baseline = _component_count(d['n'], d['edges'])
    return [v for v in range(d['n'])
            if _component_count(d['n'], d['edges'], removed_vertex=v) > baseline]


def _g07(d):
    adjacency = [[] for _ in range(d['n'])]
    for edge_id, (u, v) in enumerate(d['edges']):
        heapq.heappush(adjacency[u], (edge_id, v))
    stack = [(d['start'], None)]
    backwards = []
    while stack:
        u, incoming = stack[-1]
        if adjacency[u]:
            edge_id, v = heapq.heappop(adjacency[u])
            stack.append((v, edge_id))
        else:
            backwards.append(stack.pop())
    trail = list(reversed(backwards))
    vertices = [u for u, _ in trail]
    edge_ids = [edge_id for _, edge_id in trail[1:]]
    if len(edge_ids) != len(d['edges']):
        return None
    if any(d['edges'][edge_id] != [vertices[i], vertices[i + 1]]
           for i, edge_id in enumerate(edge_ids)):
        return None
    return {'vertices': vertices, 'edge_ids': edge_ids}


def _g08(d):
    n, source, sink = d['n'], d['source'], d['sink']
    residual = [[0] * n for _ in range(n)]
    for u, v, capacity in d['edges']:
        residual[u][v] += capacity
    flow = 0
    while True:
        parent = {source: None}
        todo = deque([source])
        while todo and sink not in parent:
            u = todo.popleft()
            for v in range(n):
                if residual[u][v] > 0 and v not in parent:
                    parent[v] = u
                    todo.append(v)
        if sink not in parent:
            return {'flow': flow, 'reachable': sorted(parent)}
        path = []
        v = sink
        while v != source:
            u = parent[v]
            path.append((u, v))
            v = u
        amount = min(residual[u][v] for u, v in path)
        for u, v in path:
            residual[u][v] -= amount
            residual[v][u] += amount
        flow += amount


def _g09(d):
    left, right = d['left'], d['right']
    adjacency = [set() for _ in range(left)]
    for u, v in d['edges']:
        adjacency[u].add(v)

    @lru_cache(None)
    def visit(u, used):
        if u == left:
            return (0, ())
        size, tail = visit(u + 1, used)
        choices = [(size, (right,) + tail)]
        for v in sorted(adjacency[u]):
            if not (used >> v) & 1:
                size, tail = visit(u + 1, used | (1 << v))
                choices.append((size + 1, (v,) + tail))
        return min(choices, key=lambda item: (-item[0], item[1]))

    size, assignments = visit(0, 0)
    return {'size': size, 'pairs': [[u, v] for u, v in enumerate(assignments) if v != right]}


def _g10(d):
    order, adjacency = _topo(d['n'], d['edges'])
    if len(order) != d['n']:
        return {'error': 'cycle'}
    counts = [0] * d['n']
    counts[d['source']] = 1
    for u in order:
        for v in adjacency[u]:
            counts[v] += counts[u]
    return {'paths': counts[d['target']]}


def _job_graph(d):
    jobs = {job['id']: job for job in d['jobs']}
    names = sorted(jobs)
    indexes = {name: i for i, name in enumerate(names)}
    edges = [(indexes[dep], indexes[name]) for name in names for dep in jobs[name]['deps']]
    order, adjacency = _topo(len(names), edges)
    return jobs, names, order, adjacency


def _g11(d):
    jobs, names, order, _ = _job_graph(d)
    if len(order) != len(names):
        return None
    now, complete, pending, running = 0, set(), set(names), []
    schedule = {}
    while pending or running:
        while running and running[0][0] == now:
            _, name = heapq.heappop(running)
            complete.add(name)
        ready = sorted(name for name in pending if set(jobs[name]['deps']) <= complete)
        for name in ready[:d['workers'] - len(running)]:
            finish = now + jobs[name]['duration']
            schedule[name] = {'id': name, 'start': now, 'finish': finish}
            pending.remove(name)
            heapq.heappush(running, (finish, name))
        if running:
            now = running[0][0]
    return {'makespan': now, 'jobs': [schedule[name] for name in names]}


def _g12(d):
    jobs, names, order, adjacency = _job_graph(d)
    if len(order) != len(names):
        return None
    start, finish, latest_start = {}, {}, {}
    for i in order:
        name = names[i]
        start[name] = max((finish[dep] for dep in jobs[name]['deps']), default=0)
        finish[name] = start[name] + jobs[name]['duration']
    makespan = max(finish.values(), default=0)
    for i in reversed(order):
        name = names[i]
        latest_finish = min((latest_start[names[j]] for j in adjacency[i]), default=makespan)
        latest_start[name] = latest_finish - jobs[name]['duration']
    return {'makespan': makespan, 'jobs': [
        {'id': name, 'start': start[name], 'finish': finish[name],
         'slack': latest_start[name] - start[name]} for name in names]}


def _g13(d):
    order, adjacency = _topo(d['n'], d['edges'])
    if len(order) != d['n']:
        return None
    output = []
    for u in range(d['n']):
        for v in sorted(adjacency[u]):
            visited, todo = set(), list(adjacency[u] - {v})
            while todo:
                node = todo.pop()
                if node not in visited:
                    visited.add(node)
                    todo.extend(adjacency[node])
            if v not in visited:
                output.append([u, v])
    return output


def _g14(d):
    adjacency = [[] for _ in range(d['n'])]
    for u, v, cost, resource in d['edges']:
        adjacency[u].append((v, cost, resource))
    source, target, budget = d['source'], d['target'], d['budget']
    best = {(source, 0): (0, 0, (source,))}
    todo = [(0, 0, (source,), source, 0)]
    while todo:
        cost, hops, path, u, used = heapq.heappop(todo)
        if best[u, used] != (cost, hops, path):
            continue
        for v, weight, consumption in adjacency[u]:
            next_used = used + consumption
            candidate = (cost + weight, hops + 1, path + (v,))
            if next_used <= budget and ((v, next_used) not in best or candidate < best[v, next_used]):
                best[v, next_used] = candidate
                heapq.heappush(todo, (*candidate, v, next_used))
    terminals = [(cost, used, hops, path) for (u, used), (cost, hops, path) in best.items() if u == target]
    if not terminals:
        return None
    cost, used, _, path = min(terminals)
    return {'cost': cost, 'resource': used, 'path': list(path)}


def _g15(d):
    multiplicity = defaultdict(int)
    answers = []
    for event in d['events']:
        action = event[0]
        if action in ('add', 'remove'):
            edge = tuple(sorted(event[1:]))
            if action == 'add':
                multiplicity[edge] += 1
            elif multiplicity[edge]:
                multiplicity[edge] -= 1
        elif action == 'count':
            answers.append(_component_count(d['n'], [edge for edge, count in multiplicity.items() if count]))
        else:
            u, v = event[1:]
            adjacency = [set() for _ in range(d['n'])]
            for (a, b), count in multiplicity.items():
                if count:
                    adjacency[a].add(b)
                    adjacency[b].add(a)
            seen, todo = {u}, [u]
            while todo:
                node = todo.pop()
                new = adjacency[node] - seen
                seen.update(new)
                todo.extend(new)
            answers.append(v in seen)
    return answers


def _g16(d):
    cache, order, used, results = {}, [], 0, []
    for event in d['events']:
        op, key = event['op'], event['key']
        if op == 'get':
            results.append(cache[key][0] if key in cache else None)
            if key in cache:
                order.remove(key)
                order.append(key)
        elif op == 'delete':
            results.append(key in cache)
            if key in cache:
                used -= cache.pop(key)[1]
                order.remove(key)
        elif event['size'] > d['capacity']:
            results.append(False)
        else:
            if key in cache:
                used -= cache.pop(key)[1]
                order.remove(key)
            while used + event['size'] > d['capacity']:
                evicted = order.pop(0)
                used -= cache.pop(evicted)[1]
            cache[key] = (event['value'], event['size'])
            order.append(key)
            used += event['size']
            results.append(True)
    return {'results': results, 'order': order, 'used': used}


def _g17(d):
    values, versions, generation = dict(d['initial']), {key: 0 for key in d['initial']}, 0
    transactions, results = {}, []
    for event in d['events']:
        op, name = event['op'], event['tx']
        if op == 'begin':
            if name in transactions:
                results.append('exists')
            else:
                transactions[name] = {'snapshot': dict(values), 'versions': dict(versions), 'reads': set(), 'writes': {}}
                results.append('ok')
            continue
        if name not in transactions:
            results.append('unknown')
            continue
        tx = transactions[name]
        if op == 'get':
            key = event['key']
            tx['reads'].add(key)
            results.append(tx['writes'].get(key, tx['snapshot'].get(key)))
        elif op in ('set', 'delete'):
            tx['writes'][event['key']] = event.get('value') if op == 'set' else None
            results.append('ok')
        elif op == 'abort':
            del transactions[name]
            results.append('ok')
        else:
            conflicts = sorted(key for key in tx['reads'] | tx['writes'].keys()
                               if versions.get(key, 0) != tx['versions'].get(key, 0))
            if conflicts:
                results.append({'committed': False, 'conflicts': conflicts})
            else:
                if tx['writes']:
                    generation += 1
                for key, value in tx['writes'].items():
                    if value is None:
                        values.pop(key, None)
                    else:
                        values[key] = value
                    versions[key] = generation
                results.append({'committed': True, 'version': generation})
            del transactions[name]
    return {'results': results, 'values': values, 'versions': versions, 'version': generation}


def _g18(d):
    histories, reads = defaultdict(list), []
    for sequence, event in enumerate(d['events']):
        key = event['key']
        if event['op'] in ('set', 'delete'):
            histories[key].append((event['at'], sequence, event.get('value') if event['op'] == 'set' else None))
        else:
            eligible = [row for row in histories[key] if row[0] <= event['asof']]
            reads.append(max(eligible)[2] if eligible else None)
    state = {key: rows[-1][2] for key, rows in histories.items() if rows and rows[-1][2] is not None}
    return {'reads': reads, 'state': state}


def _g19(d):
    available, reservations, results = dict(d['stock']), {}, []
    for event in d['events']:
        name, op = event['id'], event['op']
        if op == 'reserve':
            if name in reservations:
                results.append('exists')
            elif any(available.get(key, 0) < count for key, count in event['items'].items()):
                results.append('insufficient')
            else:
                for key, count in event['items'].items():
                    available[key] -= count
                reservations[name] = {'items': dict(event['items']), 'status': 'reserved'}
                results.append('reserved')
        elif name not in reservations:
            results.append('unknown')
        elif reservations[name]['status'] != 'reserved':
            results.append('closed')
        elif op == 'commit':
            reservations[name]['status'] = 'committed'
            results.append('committed')
        else:
            for key, count in reservations[name]['items'].items():
                available[key] += count
            reservations[name]['status'] = 'cancelled'
            results.append('cancelled')
    return {'results': results, 'available': available,
            'status': {name: row['status'] for name, row in reservations.items()}}


def _g20(d):
    seen, pending, next_sequence, total, results = {}, {}, 1, 0, []
    for event in d['events']:
        sequence, delta = event['seq'], event['delta']
        if sequence in seen:
            results.append('duplicate' if seen[sequence] == delta else 'conflict')
            continue
        seen[sequence] = delta
        pending[sequence] = delta
        while next_sequence in pending:
            total += pending.pop(next_sequence)
            next_sequence += 1
        results.append('applied' if sequence < next_sequence else 'buffered')
    return {'results': results, 'next': next_sequence, 'total': total,
            'pending': [[sequence, pending[sequence]] for sequence in sorted(pending)]}


def _g21(d):
    records, results = {}, []
    for request in d['requests']:
        now, key, payload = request['at'], request['key'], request['payload']
        records = {key: row for key, row in records.items() if row[2] > now}
        if key in records:
            old_payload, response, _ = records[key]
            results.append({'status': 'replayed', 'value': response} if old_payload == payload
                           else {'status': 'conflict', 'value': None})
        else:
            response = payload.upper()
            records[key] = (payload, response, now + d['ttl'])
            results.append({'status': 'new', 'value': response})
    return {'results': results, 'live_keys': sorted(records)}


def _g22(d):
    lease, counter, results = None, 0, []
    for event in d['events']:
        now = event['at']
        if lease is not None and lease['expires'] <= now:
            lease = None
        owner, op = event['owner'], event['op']
        if op == 'acquire':
            if lease is None:
                counter += 1
                lease = {'owner': owner, 'token': counter, 'expires': now + d['ttl']}
            allowed = lease['owner'] == owner
            results.append({'ok': allowed, 'token': lease['token'] if allowed else None})
        else:
            allowed = lease is not None and lease['owner'] == owner and lease['token'] == event['token']
            results.append(allowed)
            if allowed:
                if op == 'renew':
                    lease['expires'] = now + d['ttl']
                else:
                    lease = None
    return {'results': results, 'lease': lease, 'last_token': counter}


def _g23(d):
    capacity, period, rate = d['capacity'], d['period'], d['rate']
    balance, previous, accepted, balances = capacity * period, 0, [], []
    for now, amount in d['requests']:
        balance = min(capacity * period, balance + (now - previous) * rate)
        previous = now
        success = amount * period <= balance
        if success:
            balance -= amount * period
        accepted.append(success)
        balances.append(balance)
    return {'accepted': accepted, 'balances': balances, 'denominator': period}


def _g24(d):
    jobs = [deque(enumerate(flow['jobs'])) for flow in d['flows']]
    deficit, order, rounds = [0] * len(jobs), [], 0
    while any(jobs):
        rounds += 1
        for i, queue in enumerate(jobs):
            if not queue:
                deficit[i] = 0
                continue
            deficit[i] += d['flows'][i]['quantum']
            while queue and queue[0][1] <= deficit[i]:
                index, size = queue.popleft()
                deficit[i] -= size
                order.append([i, index])
    return {'order': order, 'rounds': rounds}


def _g25(d):
    capacity, available, active, queue = d['capacity'], d['capacity'], {}, []
    grants, timeouts, results, seen = [], [], [], set()

    def serve(now):
        nonlocal available
        while queue and queue[0]['permits'] <= available:
            request = queue.pop(0)
            available -= request['permits']
            active[request['id']] = request['permits']
            grants.append([now, request['id']])

    def advance(now):
        while queue and min(request['deadline'] for request in queue) <= now:
            deadline = min(request['deadline'] for request in queue)
            expired = sorted(request['id'] for request in queue if request['deadline'] == deadline)
            queue[:] = [request for request in queue if request['deadline'] != deadline]
            timeouts.extend([deadline, name] for name in expired)
            serve(deadline)

    for event in d['events']:
        now, op = event['at'], event['op']
        advance(now)
        name = event.get('id')
        if op == 'tick':
            results.append('tick')
        elif op == 'acquire':
            if name in seen:
                results.append('duplicate')
            else:
                seen.add(name)
                queue.append({'id': name, 'permits': event['permits'], 'deadline': now + event['timeout']})
                serve(now)
                results.append('granted' if name in active else 'queued')
                advance(now)
        elif op == 'release':
            if name not in active:
                results.append('unknown')
            else:
                available += active.pop(name)
                results.append('released')
                serve(now)
        else:
            matching = [request for request in queue if request['id'] == name]
            results.append('cancelled' if matching else 'unknown')
            queue[:] = [request for request in queue if request['id'] != name]
            serve(now)
    return {'results': results, 'grants': grants, 'timeouts': timeouts,
            'available': available, 'active': sorted(active), 'waiting': [row['id'] for row in queue]}


def _g26(d):
    pending, emitted = {}, []

    def advance(now):
        due = sorted((deadline, key, value) for key, (deadline, value) in pending.items() if deadline <= now)
        for deadline, key, value in due:
            emitted.append({'at': deadline, 'key': key, 'value': value})
            del pending[key]

    for event in d['events']:
        advance(event['at'])
        pending[event['key']] = (event['at'] + d['delay'], event['value'])
    advance(d['until'])
    return emitted


def _g27(d):
    opened_until, failures, results = None, 0, []
    for event in d['calls']:
        now = event['at']
        if opened_until is not None and now < opened_until:
            results.append('blocked')
            continue
        half_open = opened_until is not None
        if event['ok']:
            failures, opened_until = 0, None
            results.append('success')
        else:
            results.append('failure')
            failures += 1
            if half_open or failures >= d['threshold']:
                failures, opened_until = 0, now + d['cooldown']
    return {'results': results, 'state': 'open' if opened_until is not None else 'closed',
            'open_until': opened_until, 'failures': failures}


def _g28(d):
    buffer, senders, receivers, completed, closed = deque(), deque(), deque(), [], False

    def complete(name, status, value=None):
        completed.append({'id': name, 'status': status, 'value': value})

    for event in d['events']:
        op = event['op']
        if op == 'close':
            if closed:
                continue
            closed = True
            while senders:
                complete(senders.popleft()['id'], 'closed')
            while receivers:
                name = receivers.popleft()
                if buffer:
                    complete(name, 'received', buffer.popleft())
                else:
                    complete(name, 'closed')
        elif op == 'send':
            if closed:
                complete(event['id'], 'closed')
            elif receivers:
                complete(receivers.popleft(), 'received', event['value'])
                complete(event['id'], 'sent')
            elif len(buffer) < d['capacity']:
                buffer.append(event['value'])
                complete(event['id'], 'sent')
            else:
                senders.append(event)
        elif buffer:
            complete(event['id'], 'received', buffer.popleft())
            if senders:
                sender = senders.popleft()
                buffer.append(sender['value'])
                complete(sender['id'], 'sent')
        elif senders:
            sender = senders.popleft()
            complete(event['id'], 'received', sender['value'])
            complete(sender['id'], 'sent')
        elif closed:
            complete(event['id'], 'closed')
        else:
            receivers.append(event['id'])
    return {'completed': completed, 'buffer': list(buffer),
            'waiting_send': [sender['id'] for sender in senders],
            'waiting_recv': list(receivers), 'closed': closed}


def _g29(d):
    entries, results = {}, []

    def closure(key):
        removed = {key}
        while True:
            expanded = removed | {name for name, row in entries.items() if removed & set(row['deps'])}
            if expanded == removed:
                return removed
            removed = expanded

    for event in d['events']:
        key, op = event['key'], event['op']
        if op == 'get':
            results.append(entries[key]['value'] if key in entries else None)
        elif op == 'invalidate':
            removed = sorted(closure(key) & entries.keys())
            for name in removed:
                del entries[name]
            results.append(removed)
        else:
            deps = sorted(set(event['deps']))
            if any(dep not in entries for dep in deps):
                results.append('missing')
            elif key in deps or any(dep in closure(key) for dep in deps):
                results.append('cycle')
            else:
                for name in closure(key) - {key}:
                    entries.pop(name, None)
                entries[key] = {'value': event['value'], 'deps': deps}
                results.append('stored')
    return {'results': results, 'entries': entries}


def _version_parts(version):
    base = version.split('+', 1)[0]
    core, *pre = base.split('-', 1)
    return tuple(map(int, core.split('.'))), pre[0].split('.') if pre else None


def _version_compare(a, b):
    core_a, pre_a = _version_parts(a)
    core_b, pre_b = _version_parts(b)
    if core_a != core_b:
        return (core_a > core_b) - (core_a < core_b)
    if pre_a is None or pre_b is None:
        return (pre_a is None) - (pre_b is None)
    for x, y in zip(pre_a, pre_b):
        if x == y:
            continue
        if x.isdigit() and y.isdigit():
            return (int(x) > int(y)) - (int(x) < int(y))
        if x.isdigit() != y.isdigit():
            return -1 if x.isdigit() else 1
        return (x > y) - (x < y)
    return (len(pre_a) > len(pre_b)) - (len(pre_a) < len(pre_b))


def _g30(d):
    def accepted(version):
        if not d['include_prerelease'] and _version_parts(version)[1] is not None:
            return False
        for constraint in d['constraints']:
            comparison = _version_compare(version, constraint['version'])
            if not {'=': comparison == 0, '>': comparison > 0, '>=': comparison >= 0,
                    '<': comparison < 0, '<=': comparison <= 0}[constraint['op']]:
                return False
        return True

    def compare(a, b):
        return _version_compare(a, b) or ((a > b) - (a < b))

    eligible = sorted(set(filter(accepted, d['available'])), key=cmp_to_key(compare))
    selected = None
    if eligible:
        selected = min(version for version in eligible if _version_compare(version, eligible[-1]) == 0)
    return {'eligible': eligible, 'selected': selected}


def _g31(d):
    histories, reads, floor = defaultdict(list), [], 0
    for event in d['events']:
        op = event['op']
        if op in ('write', 'delete'):
            key, now = event['key'], event['at']
            row = {'at': now, 'value': event.get('value') if op == 'write' else None}
            if histories[key] and histories[key][-1]['at'] == now:
                histories[key][-1] = row
            else:
                histories[key].append(row)
        elif op == 'compact':
            floor = event['floor']
            for key, rows in list(histories.items()):
                older = [row for row in rows if row['at'] <= floor]
                histories[key] = (older[-1:] if older else []) + [row for row in rows if row['at'] > floor]
        else:
            state = {}
            for key, rows in histories.items():
                eligible = [row for row in rows if row['at'] <= event['at']]
                if eligible and eligible[-1]['value'] is not None:
                    state[key] = eligible[-1]['value']
            reads.append(state)
    return {'reads': reads, 'versions': dict(histories), 'floor': floor}


def _g32(d):
    missing, merged, conflicts = object(), {}, []

    def encode(value):
        return {'present': False} if value is missing else {'present': True, 'value': value}

    for key in sorted(d['base'].keys() | d['local'].keys() | d['remote'].keys()):
        base, local, remote = (d[name].get(key, missing) for name in ('base', 'local', 'remote'))
        if local == remote:
            chosen = local
        elif local == base:
            chosen = remote
        elif remote == base:
            chosen = local
        else:
            conflicts.append({'key': key, 'base': encode(base), 'local': encode(local), 'remote': encode(remote)})
            continue
        if chosen is not missing:
            merged[key] = chosen
    return {'merged': merged, 'conflicts': conflicts}


def _g33(d):
    events = d['events']
    n = len(events)
    relation = [['equal'] * n for _ in range(n)]
    edges = []
    for i, left in enumerate(events):
        for j, right in enumerate(events):
            a, b = left['clock'], right['clock']
            if a == b:
                result = 'equal'
            elif all(x <= y for x, y in zip(a, b)):
                result = 'before'
                edges.append((i, j))
            elif all(x >= y for x, y in zip(a, b)):
                result = 'after'
            else:
                result = 'concurrent'
            relation[i][j] = result
    done, order = set(), []
    while len(done) < n:
        candidates = [i for i in range(n) if i not in done and all(u in done for u, v in edges if v == i)]
        selected = min(candidates, key=lambda i: events[i]['id'])
        done.add(selected)
        order.append(events[selected]['id'])
    return {'order': order, 'relations': relation}


def _g34(d):
    pending, fired = {}, []

    def advance(now):
        while pending and min(row['next'] for row in pending.values()) <= now:
            deadline, name = min((row['next'], name) for name, row in pending.items())
            fired.append([deadline, name])
            row = pending[name]
            row['remaining'] -= 1
            if not row['remaining']:
                del pending[name]
            else:
                row['next'] += row['interval']

    for event in d['events']:
        advance(event['at'])
        if event['op'] == 'cancel':
            pending.pop(event['id'], None)
        else:
            pending[event['id']] = {'next': event['at'] + event['delay'],
                                    'remaining': event['count'], 'interval': event['interval']}
    advance(d['until'])
    return {'fired': fired, 'pending': [{'id': name, **pending[name]} for name in sorted(pending)]}


ORACLES = {f'G{i:02d}': globals()[f'_g{i:02d}'] for i in range(1, 35)}


def reference(task_id, data):
    """Return the frozen oracle result without mutating its JSON input."""
    return ORACLES[task_id](copy.deepcopy(data))


COMMON = ('Implement solution.py with solve(data). Use only the Python standard library. '
          'Do not read files, use the network, print, or retain state across calls. '
          'All inputs conform to this specification; return JSON-compatible values. ')

SPECS = {
    'G01': ('Canonical dependency order with cycle fallout', 'dependency_graph',
            'Input {n,edges}, n=0..10; edges are directed [u,v] with vertices 0..n-1. '
            'Treat repeated edges as one. Run Kahn ordering, always choosing the smallest currently '
            'zero-indegree vertex. Return {order:[vertices],blocked:[vertices]}, where blocked is '
            'the sorted complement of order, including both cycle vertices and their blocked descendants. '
            'Self-loops are cycles. Empty graph returns two empty lists.'),
    'G02': ('Canonical strongly connected condensation', 'graph_algorithms',
            'Input {n,edges}, n=0..10, directed [u,v] edges; duplicates/self-loops are permitted. '
            'Return {components,dag}. Each strongly connected component is a sorted vertex list. '
            'Sort components by their smallest vertex; these positions are component IDs. '
            'dag is the sorted, duplicate-free list [component_u,component_v] of edges between distinct components. '
            'Isolated vertices are singleton components. For n=0 both lists are empty.'),
    'G03': ('Negative-cycle propagation in shortest paths', 'graph_algorithms',
            'Input {n,source,edges}, n=1..10, edges [u,v,cost] with integer cost -6..9. '
            'Return a length-n distance list from source. Unreachable vertices are null. '
            'A vertex reachable from a negative-cost cycle that is itself reachable from source is "-inf". '
            'Other vertices have their minimum integer walk cost; source starts at distance zero. '
            'Parallel edges and self-loops are allowed; an unreachable negative cycle must not affect output.'),
    'G04': ('Deterministic shortest route with three tie breakers', 'graph_algorithms',
            'Input {n,edges,source,target}, n=1..10, directed edges [u,v,cost], positive integer costs 1..20. '
            'Return null if target is unreachable, otherwise {cost,path}, path a vertex list including endpoints. '
            'Choose by minimum total cost, then minimum edge count, then lexicographically smallest vertex list. '
            'Parallel edges and self-loops are allowed. source=target returns {cost:0,path:[source]}.'),
    'G05': ('Bridge detection in an undirected multigraph', 'graph_algorithms',
            'Input {n,edges}, n=0..10; undirected edges [u,v] may be repeated or self-loops. '
            'The edge ID is its zero-based position in the input. Return sorted edge IDs whose individual removal '
            'increases the number of connected components of the entire graph. Count isolated vertices. '
            'Parallel edges are distinct, and self-loops are never bridges.'),
    'G06': ('Articulation points across disconnected components', 'graph_algorithms',
            'Input {n,edges}, n=0..10; undirected edges [u,v], duplicates and self-loops allowed. '
            'Return sorted vertices whose removal, together with incident edges, increases the number of '
            'connected components relative to the original whole graph. Removed vertices do not count as '
            'components. Isolated vertices and endpoints of an isolated single edge are not articulation points.'),
    'G07': ('Lexicographically canonical directed Euler trail', 'graph_algorithms',
            'Input {n,edges,start}, n=1..8, at most 9 directed edges [u,v], duplicates/self-loops allowed. '
            'Use each input edge exactly once, beginning at start; its ID is its input position. '
            'Return null if impossible, otherwise {vertices:[...],edge_ids:[...]}. Among valid trails select '
            'the lexicographically smallest edge-ID sequence, not the smallest vertex sequence. '
            'With no edges return {vertices:[start],edge_ids:[]}.'),
    'G08': ('Maximum flow and canonical residual cut', 'graph_algorithms',
            'Input {n,edges,source,sink}, n=2..8, source!=sink; directed edges [u,v,capacity] with capacity 0..9. '
            'Parallel capacities add; self-loops are allowed. Compute an integral maximum flow. '
            'Return {flow,reachable}, where reachable is the sorted vertices reachable from source by '
            'positive residual-capacity edges in a maximum-flow residual graph. To fix the computation, use '
            'Edmonds-Karp BFS, visiting neighbors in increasing vertex order, augmenting full bottlenecks. '
            'Residual reverse capacities add to any pre-existing opposite edge capacity.'),
    'G09': ('Canonical maximum bipartite assignment', 'graph_algorithms',
            'Input {left,right,edges}, each side size 0..6; edges [left_index,right_index], duplicates allowed. '
            'Return {size,pairs}, a maximum-cardinality matching. Tie-break by lexicographically minimizing '
            'the length-left assignment vector, using right (the side size) as the unmatched sentinel. '
            'Thus matching an earlier left vertex beats leaving it unmatched. Output pairs sorted by left index. '
            'No vertex may appear in more than one pair.'),
    'G10': ('Path counting with global cycle rejection', 'dependency_graph',
            'Input {n,edges,source,target}, n=1..10, directed edges [u,v]. Deduplicate edges. '
            'If any cycle exists anywhere in the graph, even an unreachable component, return {error:"cycle"}. '
            'Otherwise return {paths:k}, counting distinct directed vertex paths from source to target. '
            'The zero-edge path counts once if source=target. Disconnected targets give zero. '
            'Use exact integer arithmetic.'),
    'G11': ('Bounded-worker dependency scheduler', 'dependency_scheduling',
            'Input {workers,jobs}; workers=1..4. Each job {id,duration,deps} has a distinct ASCII ID, '
            'duration 1..8, and existing dependency IDs (deduplicate deps). At time zero no job is complete. '
            'Whenever jobs finish, process all completions at that timestamp before assigning free workers. '
            'Choose ready unstarted jobs by increasing ID, without preemption; duration determines finish time. '
            'Return null for a dependency cycle. Otherwise return {makespan,jobs:[{id,start,finish}]}, '
            'jobs sorted by ID; an empty input has makespan zero.'),
    'G12': ('Critical-path slack for a dependency DAG', 'dependency_scheduling',
            'Input {jobs}, each distinct ASCII id with positive duration and existing deps (duplicates ignored). '
            'Assume unlimited workers. Earliest start=max dependency finish, or zero. Makespan=max finish, or zero. '
            'Latest finish=min immediate successor latest start, or makespan for a sink; latest start is latest '
            'finish minus duration. Return {makespan,jobs:[{id,start,finish,slack}]}, sorted by ID, '
            'slack=latest start-earliest start. Return null for any dependency cycle.'),
    'G13': ('Transitive reduction with global cycle checks', 'dependency_graph',
            'Input {n,edges}, n=0..10, directed [u,v]; duplicates are ignored. Return null if any cycle exists. '
            'Otherwise return sorted unique edges [u,v] retained by the DAG transitive reduction: retain an edge '
            'exactly when there is no alternate u-to-v path using at least two edges. Preserve reachability, '
            'include no redundant edges, and keep isolated vertices implicit.'),
    'G14': ('Resource-constrained route with zero-cost cycles', 'graph_algorithms',
            'Input {n,edges,source,target,budget}; n=1..8, budget=0..12. Directed edges [u,v,cost,resource] '
            'have nonnegative integer cost 0..8 and resource 0..4. Find a walk consuming at most budget. '
            'Rank feasible walks by (total cost,total resource,edge count,vertex-list lexicographic order). '
            'Return {cost,resource,path} for the best, or null if none. A zero-edge walk is allowed. '
            'Zero-cost/zero-resource cycles and parallel edges must terminate correctly; no arbitrary hop cutoff.'),
    'G15': ('Dynamic connectivity with reference-counted edges', 'event_simulation',
            'Input {n,events}, n=1..10. Events are ["add",u,v], ["remove",u,v], ["query",u,v], or ["count"]. '
            'Edges are undirected and reference-counted: every add increments multiplicity, remove decrements '
            'only if positive, and an edge exists iff its multiplicity is positive. Self-loops are permitted. '
            'Return the query results in event order: Boolean connectivity for query, integer whole-graph '
            'component count for count. Every vertex is connected to itself, including isolated vertices.'),
    'G16': ('Byte-weighted LRU with atomic replacement rejection', 'cache_state_machine',
            'Input {capacity,events}, nonnegative capacity. Events: {op:"put",key,value,size}, '
            '{op:"get",key}, {op:"delete",key}. Keys ASCII, values integers, sizes positive. '
            'A put larger than capacity returns false and changes nothing, including an existing value or recency. '
            'Other puts remove an existing key, evict least-recently-used keys until the new size fits, insert '
            'as most recent, and return true. Hit get returns value and makes key most recent; miss returns null. '
            'Delete returns existence and removes key. Return {results,order,used}; order is LRU to MRU.'),
    'G17': ('Snapshot optimistic transactions with tombstone versions', 'transactional_state_machine',
            'Input {initial,events}; initial maps ASCII keys to integer values. Events have tx and op '
            '(begin,get,set,delete,commit,abort); get/set/delete also key, set also integer value. '
            'Begin snapshots all current values and key versions, creates empty read/write sets; active ID returns "exists". '
            'Unknown transaction operations return "unknown". Get records a read and sees its own buffered writes '
            'before its begin snapshot; missing/deleted returns null. Set/delete buffer writes and return "ok"; '
            'abort closes the transaction and returns "ok". Commit compares current versions against snapshot '
            'versions for every read or written key (missing version=0), closes the transaction even on failure, '
            'and on conflict returns {committed:false,conflicts:[sorted keys]}. Otherwise a nonempty write set '
            'increments the global version once, applies all writes atomically, and records that version for '
            'each written key, including deletion tombstones. Empty commits do not increment. Successful commit '
            'returns {committed:true,version}. All initial versions/global version are zero; same-value writes '
            'still change version. Return {results,values,versions,version}; versions retains tombstones.'),
    'G18': ('Temporal key-value reads with equal-time overwrite', 'versioning',
            'Input {events}, with nondecreasing integer at timestamps. Events {op:"set",at,key,value}, '
            '{op:"delete",at,key}, or {op:"get",at,key,asof}, integer values and asof<=at. '
            'A get sees only preceding writes in input order at timestamps <=asof; latest timestamp wins, '
            'and equal timestamps use the last preceding write. Missing/deleted values return null. '
            'Return {reads,state}: reads contains only get responses, state contains current nondeleted keys '
            'after all events. Reads do not create keys. Repeated deletion is valid.'),
    'G19': ('Atomic multi-item inventory reservations', 'transactional_state_machine',
            'Input {stock,events}, stock maps keys to nonnegative quantities. Events reserve have '
            '{op:"reserve",id,items}, items maps existing stock keys to positive quantities; commit/cancel '
            'have {op,id}. Reserve succeeds only if all requested quantities are available, subtracts them '
            'atomically, and returns "reserved"; failure returns "insufficient" and does not claim the ID. '
            'Any previously successful ID, including closed IDs, returns "exists" on another reserve. '
            'Commit consumes reserved items permanently and returns "committed"; cancel restores all and '
            'returns "cancelled". For commit/cancel, unknown ID returns "unknown", already closed returns '
            '"closed". Return {results,available,status}, status maps successful IDs to reserved/committed/cancelled.'),
    'G20': ('Gap-aware idempotent event-log materializer', 'event_simulation',
            'Input {events}, each {seq,delta}, positive sequence and integer delta. Start total=0,next=1. '
            'The first arrival for each sequence is permanently authoritative. Identical repeats return '
            '"duplicate", unequal repeats "conflict", with no state change. A new arrival is buffered, '
            'then apply and remove every contiguous buffered event starting at next, incrementing next. '
            'Its result is "applied" if its sequence was consumed by this flush, otherwise "buffered". '
            'Return {results,next,total,pending}; pending sorted [seq,delta] pairs. Applied events remain '
            'remembered for duplicate/conflict detection.'),
    'G21': ('TTL idempotency records without sliding expiry', 'event_simulation',
            'Input {ttl,requests}, ttl positive; requests {at,key,payload}, nondecreasing integer at, '
            'ASCII key and ASCII payload. Before each request expire all records whose expires<=at. '
            'A new key stores payload, response=payload.upper(), expiry=at+ttl, and returns '
            '{status:"new",value:response}. A live matching payload returns {status:"replayed",value:response} '
            'without extending expiry. A live differing payload returns {status:"conflict",value:null} and '
            'does not change the record. Return {results,live_keys}, sorted live keys after the last request; '
            'there is no implicit final time advance.'),
    'G22': ('Lease ownership with expiry and fencing tokens', 'event_simulation',
            'Input {ttl,events}, positive ttl, nondecreasing at. Acquire event {op:"acquire",at,owner}; '
            'renew/release also token. Before each event expire a lease when expires<=at. Acquiring a free '
            'lease increases a global token counter (initial zero), sets owner/token/expires=at+ttl. '
            'Acquiring again by the same live owner succeeds with the same token without extending expiry; '
            'another owner is denied. Acquire returns {ok,token}, null token on denial. Renew/release '
            'succeeds only for matching live owner and token, returns Boolean; renew extends to at+ttl and '
            'release clears the lease. Return {results,lease,last_token}, lease null or {owner,token,expires}. '
            'An expired token can never be reused; no implicit final time advance.'),
    'G23': ('Exact rational token-bucket simulation', 'event_simulation',
            'Input {capacity,period,rate,requests}, nonnegative integer capacity/rate, positive period, '
            'requests [at,amount] in nondecreasing nonnegative time with nonnegative integer amount. '
            'Initially the bucket is full at time zero; refill continuously at rate/period tokens per time '
            'unit, capped at capacity. Each request succeeds iff enough tokens exist and deducts amount only '
            'on success. Do not round refill or use floating point. Return {accepted,balances,denominator}; '
            'accepted is Boolean per request; balances is remaining tokens multiplied by period after each '
            'request, denominator=period. Failed requests retain the refilled balance.'),
    'G24': ('Deficit round-robin packet scheduling', 'event_simulation',
            'Input {flows}, each flow {quantum,jobs}, quantum positive integer, jobs positive packet sizes. '
            'At each round visit flow indexes in ascending order. Empty flow resets its deficit to zero; '
            'nonempty flow adds its quantum, then emits as many consecutive head packets as its deficit '
            'covers, subtracting each size. Never skip an oversized head packet to send a later one. '
            'Deficits carry across rounds. Stop after the round in which all jobs are emitted. '
            'Return {order,rounds}, order [flow_index,original_job_index] per packet; empty inputs have zero rounds.'),
    'G25': ('FIFO semaphore with deadlines and cancellation', 'event_simulation',
            'Input {capacity,events}, capacity positive. Events at nondecreasing times: acquire '
            '{op,at,id,permits,timeout} (1<=permits<=capacity, timeout>=0), release/cancel {op,at,id}, '
            'or tick {op,at}. Acquisition IDs are never reusable, even after timeout/release; duplicate '
            'returns "duplicate". Before every event process waiting deadlines <=at in time order; '
            'at each deadline expire all requests with that deadline, sorted by ID, before granting others. '
            'After expiry, release, cancellation, or enqueue, grant FIFO heads while head permits fit; '
            'do not bypass a head. A grant consumes permits and appends [time,id] to grants. Acquire returns '
            '"granted" or "queued" according to immediate grant, then processes timeout=0 at that time. '
            'Release active ID returns "released" and restores permits; otherwise "unknown". Cancel '
            'waiting ID returns "cancelled", else "unknown". Tick returns "tick". No final time advance. '
            'Return {results,grants,timeouts,available,active,waiting}; timeouts [deadline,id], active sorted IDs, '
            'waiting FIFO IDs. Grant due to a timeout uses the deadline, not the next event timestamp.'),
    'G26': ('Per-key trailing debounce with exact tie ordering', 'event_simulation',
            'Input {delay,events,until}, positive delay, nondecreasing events {at,key,value}, integer values, '
            'until>=last event time (or zero for none). Each event replaces its key pending value and sets '
            'deadline=at+delay. Before processing an event emit all deadlines <=its at in order '
            '(deadline,key); ties at the event timestamp emit BEFORE that event. After events advance only '
            'to until. Return emitted [{at:deadline,key,value}] in emission order. Keys debounce independently, '
            'and replacement must not leave stale timers that emit overwritten values.'),
    'G27': ('Circuit breaker with synchronous half-open probes', 'event_simulation',
            'Input {threshold,cooldown,calls}, positive integers threshold/cooldown, nondecreasing calls '
            '{at,ok}. Initially closed with zero consecutive failures. Closed success resets failures; failure '
            'increments, opening the breaker for cooldown when threshold is reached and resetting failures '
            'to zero. While open at<open_until, calls return "blocked" and their ok is ignored. The first '
            'call at>=open_until is a half-open probe: success closes/resets, failure opens again until '
            'at+cooldown regardless of threshold. Accepted results are "success" or "failure". Return '
            '{results,state,open_until,failures}; state open/closed, open_until null if closed. The last '
            'stored open state is retained until a call probes, even if time otherwise passed.'),
    'G28': ('Bounded FIFO channel and close propagation', 'concurrency_simulation',
            'Input {capacity,events}, nonnegative capacity; send {op:"send",id,value}, recv '
            '{op:"recv",id}, close {op:"close"}. All request IDs unique, integer values. Model FIFO '
            'buffer plus FIFO blocked senders/receivers. Send to waiting receiver completes receiver '
            '("received",value) then sender ("sent",null); otherwise buffer if space, or block. Recv '
            'takes buffered head, completing receiver first, then promotes one blocked sender into buffer '
            'and completes it. With no buffered value but a blocked sender, rendezvous and complete receiver '
            'then sender (including capacity zero). Otherwise recv blocks unless closed. Close is idempotent; '
            'first close completes all blocked senders as "closed", then all waiting receivers as received '
            'if buffer has a value, otherwise "closed". Buffered values survive close for future receives; '
            'new sends fail closed. Return {completed,buffer,waiting_send,waiting_recv,closed}; every completion '
            'is {id,status,value}, with null value except received, ordered by the rules above.'),
    'G29': ('Dependency cache with transitive invalidation', 'cache_state_machine',
            'Input {events}; put {op:"put",key,value,deps}, get/invalidate {op,key}, integer values, ASCII keys. '
            'Put first requires every distinct dep already cached; otherwise "missing" and no change. '
            'Then reject "cycle" if self-dependency or the proposed dependency edges create a cycle in '
            'the CURRENT cache (before invalidation). Accepted put removes all transitive dependents of '
            'key except key itself, then stores {value,deps:sorted unique keys}; return "stored". '
            'Get returns current value or null. Invalidate removes key plus all its transitive dependents '
            'and returns sorted actually removed keys, even when key itself is absent. Return {results,entries}, '
            'entries mapping keys to {value,deps}. Rejected writes preserve all dependents.'),
    'G30': ('SemVer constraint solver with build-metadata ties', 'versioning',
            'Input {available,constraints,include_prerelease}. All version strings are valid SemVer '
            'MAJOR.MINOR.PATCH[-prerelease][+build], core numbers nonnegative with no leading zero. '
            'Prerelease dot identifiers use ASCII letters/digits/hyphens; numeric identifiers have no '
            'leading zero. Compare core integer triples, then release above prerelease; compare prerelease '
            'identifiers left-to-right, numeric numerically and below nonnumeric, nonnumeric ASCII '
            'lexicographically, shorter equal-prefix list below longer. Ignore build metadata for precedence. '
            'Each constraint {op,version} uses =,>,>=,<,<= on precedence. Require every constraint; '
            'exclude all prereleases if include_prerelease=false. Return {eligible,selected}; eligible '
            'deduplicates exact input strings and sorts by ascending precedence, breaking precedence ties '
            'by ASCII full-string order. selected is highest-precedence eligible, with the smallest '
            'full string among ties, or null. There are no implicit npm-style range/prerelease rules.'),
    'G31': ('MVCC compaction preserving floor snapshots', 'versioning',
            'Input {events}; write {op:"write",at,key,value}, delete {op:"delete",at,key}, '
            'compact {op:"compact",floor}, read {op:"read",at}. Writes/deletes have globally '
            'nondecreasing timestamps; initial compaction floor zero. Compact floors nondecrease and '
            'never exceed latest write timestamp (zero if none); subsequent writes and reads have at>=floor. '
            'For each key keep only the latest write at a duplicate timestamp. A deletion is a null '
            'tombstone, while stored values are integers. Compaction retains the newest version <=floor '
            '(including a tombstone) plus EVERY version >floor. Read returns whole nondeleted snapshot '
            'at its timestamp using preceding retained versions; missing/deleted keys are absent. '
            'Return {reads,versions,floor}, versions maps keys to chronological [{at,value}] retained history. '
            'Never discard a baseline tombstone or the last older version needed at floor.'),
    'G32': ('Three-way record merge distinguishing deletion from null', 'versioning',
            'Input {base,local,remote}, each object maps ASCII keys to integer/string/null values. '
            'Absence is distinct from null. For each key in the union: if local=remote choose that value; '
            'else if local=base choose remote; else if remote=base choose local; otherwise conflict. '
            'Choosing absence deletes the key. Return {merged,conflicts}; conflicted keys are absent from '
            'merged. Conflicts sorted by key, each {key,base,local,remote}, where each value is encoded '
            '{present:false} for absence or {present:true,value:v} for presence, including null. '
            'Do not recursively merge; object values are only the specified scalar types.'),
    'G33': ('Vector-clock relations and canonical causal order', 'concurrency_simulation',
            'Input {events}, each has unique ASCII id and clock, an equal-length array of nonnegative integers '
            '(length 1..5). For input positions i,j return relation equal if clocks identical, before if '
            'every component of i<=j and at least one strict, after for the reverse, else concurrent. '
            'Return {order,relations}, relations an input-order square matrix of these strings. order is '
            'the lexicographically smallest ID topological ordering of every strict before relation: '
            'repeatedly choose smallest eligible ID, not by sum or lexicographic clock. Equal clocks '
            'impose no ordering. Empty events return two empty arrays.'),
    'G34': ('Finite periodic timers with rearm and cancellation', 'event_simulation',
            'Input {events,until}, events nondecreasing at, until>=last at. Arm {op:"arm",at,id,delay,interval,count}; '
            'delay>=1, count>=1, interval>=1 when count>1 (zero allowed for one shot). Cancel {op:"cancel",at,id}. '
            'Before each operation fire every due timer at times <=at; process ties by (deadline,id). '
            'Arming replaces that ID remaining timer with next=at+delay, given interval/count. Each firing '
            'appends [deadline,id], decrements remaining, and either deletes the timer or advances next '
            'by interval, possibly firing repeatedly before the next operation. Cancel removes pending '
            'timer if present; same-time due firing happens before cancel/rearm. Advance to until after '
            'operations. Return {fired,pending}, pending sorted by ID as {id,next,remaining,interval}. '
            'No firing beyond until; overwritten timer generations must not fire later.'),
}


# These expected values are written out, rather than obtained from the oracle.
# Each is an independent, small calculation that guards its task's semantics.
ANCHORS = {
    'G01': [
        ({'n': 4, 'edges': [[0, 2], [1, 2], [2, 3]]},
         {'order': [0, 1, 2, 3], 'blocked': []}),
        ({'n': 4, 'edges': [[0, 1], [1, 0], [1, 2]]},
         {'order': [3], 'blocked': [0, 1, 2]}),
    ],
    'G02': [
        ({'n': 5, 'edges': [[0, 1], [1, 0], [1, 2], [2, 2], [3, 4], [4, 3]]},
         {'components': [[0, 1], [2], [3, 4]], 'dag': [[0, 1]]}),
        ({'n': 0, 'edges': []}, {'components': [], 'dag': []}),
    ],
    'G03': [
        ({'n': 5, 'source': 0, 'edges': [[0, 1, 2], [1, 2, -3], [2, 1, 1], [2, 3, 4], [4, 4, -1]]},
         [0, '-inf', '-inf', '-inf', None]),
        ({'n': 3, 'source': 0, 'edges': [[1, 1, -1]]}, [0, None, None]),
    ],
    'G04': [
        ({'n': 4, 'source': 0, 'target': 3,
          'edges': [[0, 1, 1], [1, 3, 1], [0, 2, 1], [2, 3, 1], [0, 3, 2]]},
         {'cost': 2, 'path': [0, 3]}),
        ({'n': 4, 'source': 0, 'target': 3,
          'edges': [[0, 2, 1], [2, 3, 1], [0, 1, 1], [1, 3, 1]]},
         {'cost': 2, 'path': [0, 1, 3]}),
    ],
    'G05': [
        ({'n': 4, 'edges': [[0, 1], [0, 1], [1, 2], [2, 2]]}, [2]),
        ({'n': 3, 'edges': []}, []),
    ],
    'G06': [
        ({'n': 6, 'edges': [[0, 1], [1, 2], [3, 4]]}, [1]),
        ({'n': 1, 'edges': [[0, 0]]}, []),
    ],
    'G07': [
        ({'n': 3, 'start': 0, 'edges': [[0, 1], [0, 2], [1, 0]]},
         {'vertices': [0, 1, 0, 2], 'edge_ids': [0, 2, 1]}),
        ({'n': 3, 'start': 0, 'edges': [[0, 1], [0, 2]]}, None),
    ],
    'G08': [
        ({'n': 4, 'source': 0, 'sink': 3,
          'edges': [[0, 1, 3], [0, 2, 2], [1, 2, 1], [1, 3, 2], [2, 3, 3]]},
         {'flow': 5, 'reachable': [0]}),
        ({'n': 3, 'source': 0, 'sink': 2, 'edges': [[0, 1, 2], [1, 2, 1]]},
         {'flow': 1, 'reachable': [0, 1]}),
    ],
    'G09': [
        ({'left': 3, 'right': 2, 'edges': [[0, 0], [0, 1], [1, 0], [2, 1]]},
         {'size': 2, 'pairs': [[0, 0], [2, 1]]}),
        ({'left': 2, 'right': 0, 'edges': []}, {'size': 0, 'pairs': []}),
    ],
    'G10': [
        ({'n': 4, 'source': 0, 'target': 3, 'edges': [[0, 1], [0, 2], [1, 3], [2, 3]]},
         {'paths': 2}),
        ({'n': 4, 'source': 0, 'target': 1, 'edges': [[0, 1], [3, 3]]}, {'error': 'cycle'}),
    ],
    'G11': [
        ({'workers': 2, 'jobs': [{'id': 'b', 'duration': 1, 'deps': []},
                                {'id': 'a', 'duration': 2, 'deps': []},
                                {'id': 'c', 'duration': 1, 'deps': ['a', 'b']}]},
         {'makespan': 3, 'jobs': [{'id': 'a', 'start': 0, 'finish': 2},
                                  {'id': 'b', 'start': 0, 'finish': 1},
                                  {'id': 'c', 'start': 2, 'finish': 3}]}),
        ({'workers': 1, 'jobs': []}, {'makespan': 0, 'jobs': []}),
    ],
    'G12': [
        ({'jobs': [{'id': 'b', 'duration': 1, 'deps': []},
                   {'id': 'a', 'duration': 2, 'deps': []},
                   {'id': 'c', 'duration': 1, 'deps': ['a', 'b']}]},
         {'makespan': 3, 'jobs': [{'id': 'a', 'start': 0, 'finish': 2, 'slack': 0},
                                  {'id': 'b', 'start': 0, 'finish': 1, 'slack': 1},
                                  {'id': 'c', 'start': 2, 'finish': 3, 'slack': 0}]}),
        ({'jobs': [{'id': 'a', 'duration': 1, 'deps': ['b']},
                   {'id': 'b', 'duration': 1, 'deps': ['a']}]}, None),
    ],
    'G13': [
        ({'n': 3, 'edges': [[0, 1], [1, 2], [0, 2], [0, 2]]}, [[0, 1], [1, 2]]),
        ({'n': 1, 'edges': [[0, 0]]}, None),
    ],
    'G14': [
        ({'n': 3, 'source': 0, 'target': 2, 'budget': 2,
          'edges': [[0, 2, 1, 3], [0, 1, 1, 1], [1, 2, 0, 1]]},
         {'cost': 1, 'resource': 2, 'path': [0, 1, 2]}),
        ({'n': 2, 'source': 0, 'target': 1, 'budget': 0,
          'edges': [[0, 0, 0, 0], [0, 1, 0, 0]]},
         {'cost': 0, 'resource': 0, 'path': [0, 1]}),
    ],
    'G15': [
        ({'n': 3, 'events': [['add', 0, 1], ['add', 0, 1], ['remove', 0, 1],
                             ['query', 0, 1], ['remove', 0, 1], ['query', 0, 1], ['count']]},
         [True, False, 3]),
        ({'n': 1, 'events': [['remove', 0, 0], ['query', 0, 0], ['count']]}, [True, 1]),
    ],
    'G16': [
        ({'capacity': 3, 'events': [{'op': 'put', 'key': 'a', 'value': 1, 'size': 2},
                                   {'op': 'put', 'key': 'b', 'value': 2, 'size': 1},
                                   {'op': 'get', 'key': 'a'},
                                   {'op': 'put', 'key': 'c', 'value': 3, 'size': 2}]},
         {'results': [True, True, 1, True], 'order': ['c'], 'used': 2}),
        ({'capacity': 2, 'events': [{'op': 'put', 'key': 'a', 'value': 7, 'size': 1},
                                   {'op': 'put', 'key': 'a', 'value': 9, 'size': 3},
                                   {'op': 'get', 'key': 'a'}]},
         {'results': [True, False, 7], 'order': ['a'], 'used': 1}),
    ],
    'G17': [
        ({'initial': {'x': 1}, 'events': [{'op': 'begin', 'tx': 'a'}, {'op': 'get', 'tx': 'a', 'key': 'x'},
             {'op': 'begin', 'tx': 'b'}, {'op': 'set', 'tx': 'b', 'key': 'x', 'value': 2},
             {'op': 'commit', 'tx': 'b'}, {'op': 'set', 'tx': 'a', 'key': 'y', 'value': 3},
             {'op': 'commit', 'tx': 'a'}]},
         {'results': ['ok', 1, 'ok', 'ok', {'committed': True, 'version': 1}, 'ok',
                      {'committed': False, 'conflicts': ['x']}],
          'values': {'x': 2}, 'versions': {'x': 1}, 'version': 1}),
        ({'initial': {}, 'events': [{'op': 'begin', 'tx': 'a'}, {'op': 'delete', 'tx': 'a', 'key': 'x'},
                                    {'op': 'commit', 'tx': 'a'}]},
         {'results': ['ok', 'ok', {'committed': True, 'version': 1}],
          'values': {}, 'versions': {'x': 1}, 'version': 1}),
    ],
    'G18': [
        ({'events': [{'op': 'set', 'at': 1, 'key': 'x', 'value': 1},
                     {'op': 'set', 'at': 1, 'key': 'x', 'value': 2},
                     {'op': 'get', 'at': 1, 'key': 'x', 'asof': 1},
                     {'op': 'delete', 'at': 2, 'key': 'x'},
                     {'op': 'get', 'at': 2, 'key': 'x', 'asof': 1},
                     {'op': 'get', 'at': 2, 'key': 'x', 'asof': 2}]},
         {'reads': [2, 2, None], 'state': {}}),
        ({'events': [{'op': 'get', 'at': 0, 'key': 'x', 'asof': 0}]}, {'reads': [None], 'state': {}}),
    ],
    'G19': [
        ({'stock': {'a': 2, 'b': 1}, 'events': [
            {'op': 'reserve', 'id': 'p', 'items': {'a': 1, 'b': 1}},
            {'op': 'reserve', 'id': 'q', 'items': {'a': 2}}, {'op': 'cancel', 'id': 'p'},
            {'op': 'commit', 'id': 'p'}, {'op': 'reserve', 'id': 'q', 'items': {'a': 2}},
            {'op': 'commit', 'id': 'q'}]},
         {'results': ['reserved', 'insufficient', 'cancelled', 'closed', 'reserved', 'committed'],
          'available': {'a': 0, 'b': 1}, 'status': {'p': 'cancelled', 'q': 'committed'}}),
        ({'stock': {'a': 0}, 'events': [{'op': 'cancel', 'id': 'missing'}]},
         {'results': ['unknown'], 'available': {'a': 0}, 'status': {}}),
    ],
    'G20': [
        ({'events': [{'seq': 2, 'delta': 5}, {'seq': 1, 'delta': 3}, {'seq': 2, 'delta': 5},
                     {'seq': 2, 'delta': 7}, {'seq': 4, 'delta': -1}]},
         {'results': ['buffered', 'applied', 'duplicate', 'conflict', 'buffered'],
          'next': 3, 'total': 8, 'pending': [[4, -1]]}),
        ({'events': []}, {'results': [], 'next': 1, 'total': 0, 'pending': []}),
    ],
    'G21': [
        ({'ttl': 3, 'requests': [{'at': 0, 'key': 'k', 'payload': 'a'},
                               {'at': 2, 'key': 'k', 'payload': 'a'},
                               {'at': 3, 'key': 'k', 'payload': 'b'}]},
         {'results': [{'status': 'new', 'value': 'A'}, {'status': 'replayed', 'value': 'A'},
                      {'status': 'new', 'value': 'B'}], 'live_keys': ['k']}),
        ({'ttl': 2, 'requests': [{'at': 0, 'key': 'k', 'payload': 'a'},
                               {'at': 1, 'key': 'k', 'payload': 'b'},
                               {'at': 2, 'key': 'j', 'payload': 'z'}]},
         {'results': [{'status': 'new', 'value': 'A'}, {'status': 'conflict', 'value': None},
                      {'status': 'new', 'value': 'Z'}], 'live_keys': ['j']}),
    ],
    'G22': [
        ({'ttl': 3, 'events': [{'at': 0, 'op': 'acquire', 'owner': 'a'},
                             {'at': 2, 'op': 'acquire', 'owner': 'a'},
                             {'at': 3, 'op': 'acquire', 'owner': 'b'},
                             {'at': 4, 'op': 'renew', 'owner': 'a', 'token': 1},
                             {'at': 5, 'op': 'release', 'owner': 'b', 'token': 2}]},
         {'results': [{'ok': True, 'token': 1}, {'ok': True, 'token': 1},
                      {'ok': True, 'token': 2}, False, True], 'lease': None, 'last_token': 2}),
        ({'ttl': 2, 'events': [{'at': 0, 'op': 'acquire', 'owner': 'a'},
                             {'at': 1, 'op': 'renew', 'owner': 'a', 'token': 1},
                             {'at': 2, 'op': 'acquire', 'owner': 'b'}]},
         {'results': [{'ok': True, 'token': 1}, True, {'ok': False, 'token': None}],
          'lease': {'owner': 'a', 'token': 1, 'expires': 3}, 'last_token': 1}),
    ],
    'G23': [
        ({'capacity': 2, 'period': 3, 'rate': 1, 'requests': [[0, 1], [1, 2], [3, 1]]},
         {'accepted': [True, False, True], 'balances': [3, 4, 3], 'denominator': 3}),
        ({'capacity': 0, 'period': 1, 'rate': 3, 'requests': [[0, 0], [10, 1]]},
         {'accepted': [True, False], 'balances': [0, 0], 'denominator': 1}),
    ],
    'G24': [
        ({'flows': [{'quantum': 2, 'jobs': [3, 1]}, {'quantum': 1, 'jobs': [1, 2]}]},
         {'order': [[1, 0], [0, 0], [0, 1], [1, 1]], 'rounds': 3}),
        ({'flows': []}, {'order': [], 'rounds': 0}),
    ],
    'G25': [
        ({'capacity': 2, 'events': [{'op': 'acquire', 'at': 0, 'id': 'a', 'permits': 2, 'timeout': 10},
             {'op': 'acquire', 'at': 1, 'id': 'b', 'permits': 2, 'timeout': 2},
             {'op': 'acquire', 'at': 2, 'id': 'c', 'permits': 1, 'timeout': 9},
             {'op': 'tick', 'at': 3}, {'op': 'release', 'at': 4, 'id': 'a'}]},
         {'results': ['granted', 'queued', 'queued', 'tick', 'released'],
          'grants': [[0, 'a'], [4, 'c']], 'timeouts': [[3, 'b']], 'available': 1,
          'active': ['c'], 'waiting': []}),
        ({'capacity': 2, 'events': [{'op': 'acquire', 'at': 0, 'id': 'a', 'permits': 1, 'timeout': 0},
             {'op': 'acquire', 'at': 0, 'id': 'b', 'permits': 2, 'timeout': 0}]},
         {'results': ['granted', 'queued'], 'grants': [[0, 'a']], 'timeouts': [[0, 'b']],
          'available': 1, 'active': ['a'], 'waiting': []}),
    ],
    'G26': [
        ({'delay': 2, 'events': [{'at': 0, 'key': 'a', 'value': 1},
                               {'at': 1, 'key': 'a', 'value': 2},
                               {'at': 3, 'key': 'a', 'value': 3}], 'until': 5},
         [{'at': 3, 'key': 'a', 'value': 2}, {'at': 5, 'key': 'a', 'value': 3}]),
        ({'delay': 2, 'events': [{'at': 0, 'key': 'b', 'value': 2},
                               {'at': 0, 'key': 'a', 'value': 1}], 'until': 2},
         [{'at': 2, 'key': 'a', 'value': 1}, {'at': 2, 'key': 'b', 'value': 2}]),
    ],
    'G27': [
        ({'threshold': 2, 'cooldown': 3, 'calls': [{'at': 0, 'ok': False}, {'at': 1, 'ok': False},
             {'at': 2, 'ok': True}, {'at': 4, 'ok': False}, {'at': 7, 'ok': True}]},
         {'results': ['failure', 'failure', 'blocked', 'failure', 'success'],
          'state': 'closed', 'open_until': None, 'failures': 0}),
        ({'threshold': 3, 'cooldown': 2, 'calls': [{'at': 0, 'ok': False}, {'at': 1, 'ok': True},
             {'at': 2, 'ok': False}]},
         {'results': ['failure', 'success', 'failure'], 'state': 'closed', 'open_until': None, 'failures': 1}),
    ],
    'G28': [
        ({'capacity': 1, 'events': [{'op': 'send', 'id': 's1', 'value': 1},
             {'op': 'send', 'id': 's2', 'value': 2}, {'op': 'recv', 'id': 'r1'}, {'op': 'close'},
             {'op': 'recv', 'id': 'r2'}, {'op': 'recv', 'id': 'r3'}]},
         {'completed': [{'id': 's1', 'status': 'sent', 'value': None},
                        {'id': 'r1', 'status': 'received', 'value': 1},
                        {'id': 's2', 'status': 'sent', 'value': None},
                        {'id': 'r2', 'status': 'received', 'value': 2},
                        {'id': 'r3', 'status': 'closed', 'value': None}],
          'buffer': [], 'waiting_send': [], 'waiting_recv': [], 'closed': True}),
        ({'capacity': 0, 'events': [{'op': 'recv', 'id': 'r0'},
             {'op': 'send', 'id': 's0', 'value': 7}, {'op': 'close'},
             {'op': 'send', 'id': 's1', 'value': 9}]},
         {'completed': [{'id': 'r0', 'status': 'received', 'value': 7},
                        {'id': 's0', 'status': 'sent', 'value': None},
                        {'id': 's1', 'status': 'closed', 'value': None}],
          'buffer': [], 'waiting_send': [], 'waiting_recv': [], 'closed': True}),
    ],
    'G29': [
        ({'events': [{'op': 'put', 'key': 'a', 'value': 1, 'deps': []},
                    {'op': 'put', 'key': 'b', 'value': 2, 'deps': ['a']},
                    {'op': 'put', 'key': 'c', 'value': 3, 'deps': ['b']},
                    {'op': 'put', 'key': 'a', 'value': 4, 'deps': []}, {'op': 'get', 'key': 'c'}]},
         {'results': ['stored', 'stored', 'stored', 'stored', None], 'entries': {'a': {'value': 4, 'deps': []}}}),
        ({'events': [{'op': 'put', 'key': 'a', 'value': 1, 'deps': []},
                    {'op': 'put', 'key': 'b', 'value': 2, 'deps': ['a']},
                    {'op': 'put', 'key': 'a', 'value': 3, 'deps': ['b']}, {'op': 'invalidate', 'key': 'a'}]},
         {'results': ['stored', 'stored', 'cycle', ['a', 'b']], 'entries': {}}),
    ],
    'G30': [
        ({'available': ['1.0.0-alpha', '1.0.0', '1.0.0+z', '1.0.0+a', '1.1.0'],
          'constraints': [{'op': '>=', 'version': '1.0.0'}, {'op': '<', 'version': '1.1.0'}],
          'include_prerelease': True},
         {'eligible': ['1.0.0', '1.0.0+a', '1.0.0+z'], 'selected': '1.0.0'}),
        ({'available': ['1.0.0-alpha.10', '1.0.0-alpha.2', '1.0.0-alpha.beta', '1.0.0-beta.1'],
          'constraints': [], 'include_prerelease': True},
         {'eligible': ['1.0.0-alpha.2', '1.0.0-alpha.10', '1.0.0-alpha.beta', '1.0.0-beta.1'],
          'selected': '1.0.0-beta.1'}),
    ],
    'G31': [
        ({'events': [{'op': 'write', 'at': 1, 'key': 'x', 'value': 1},
             {'op': 'delete', 'at': 2, 'key': 'x'}, {'op': 'compact', 'floor': 2},
             {'op': 'read', 'at': 2}, {'op': 'write', 'at': 3, 'key': 'x', 'value': 3},
             {'op': 'read', 'at': 3}]},
         {'reads': [{}, {'x': 3}], 'versions': {'x': [{'at': 2, 'value': None}, {'at': 3, 'value': 3}]}, 'floor': 2}),
        ({'events': [{'op': 'write', 'at': 0, 'key': 'x', 'value': 1},
             {'op': 'write', 'at': 0, 'key': 'x', 'value': 2}, {'op': 'read', 'at': 0}]},
         {'reads': [{'x': 2}], 'versions': {'x': [{'at': 0, 'value': 2}]}, 'floor': 0}),
    ],
    'G32': [
        ({'base': {'a': 1, 'b': None}, 'local': {'a': 2}, 'remote': {'a': 3, 'b': None, 'c': 4}},
         {'merged': {'c': 4}, 'conflicts': [{'key': 'a', 'base': {'present': True, 'value': 1},
             'local': {'present': True, 'value': 2}, 'remote': {'present': True, 'value': 3}}]}),
        ({'base': {}, 'local': {'x': None}, 'remote': {'x': None}}, {'merged': {'x': None}, 'conflicts': []}),
    ],
    'G33': [
        ({'events': [{'id': 'b', 'clock': [1, 0]}, {'id': 'a', 'clock': [0, 1]},
                    {'id': 'c', 'clock': [1, 1]}]},
         {'order': ['a', 'b', 'c'], 'relations': [['equal', 'concurrent', 'before'],
             ['concurrent', 'equal', 'before'], ['after', 'after', 'equal']]}),
        ({'events': [{'id': 'z', 'clock': [0]}, {'id': 'a', 'clock': [0]}]},
         {'order': ['a', 'z'], 'relations': [['equal', 'equal'], ['equal', 'equal']]}),
    ],
    'G34': [
        ({'events': [{'op': 'arm', 'at': 0, 'id': 'x', 'delay': 2, 'interval': 2, 'count': 3},
                    {'op': 'cancel', 'at': 4, 'id': 'x'}], 'until': 10},
         {'fired': [[2, 'x'], [4, 'x']], 'pending': []}),
        ({'events': [{'op': 'arm', 'at': 0, 'id': 'b', 'delay': 2, 'interval': 0, 'count': 1},
                    {'op': 'arm', 'at': 0, 'id': 'a', 'delay': 2, 'interval': 3, 'count': 2},
                    {'op': 'arm', 'at': 1, 'id': 'a', 'delay': 4, 'interval': 0, 'count': 1}], 'until': 5},
         {'fired': [[2, 'b'], [5, 'a']], 'pending': []}),
    ],
}


ADVERSARIAL = {
    'G01': {'n': 0, 'edges': []},
    'G02': {'n': 6, 'edges': [[5, 2], [2, 5], [1, 4], [4, 1], [0, 5], [4, 2]]},
    'G03': {'n': 4, 'source': 0, 'edges': [[0, 1, 0], [1, 1, -1], [1, 2, 0], [3, 3, -1]]},
    'G04': {'n': 1, 'source': 0, 'target': 0, 'edges': [[0, 0, 1], [0, 0, 2]]},
    'G05': {'n': 3, 'edges': [[0, 1], [1, 0], [1, 2], [2, 2], [0, 0]]},
    'G06': {'n': 7, 'edges': [[0, 1], [0, 2], [0, 3], [4, 5], [5, 6]]},
    'G07': {'n': 3, 'start': 2, 'edges': []},
    'G08': {'n': 3, 'source': 0, 'sink': 2,
            'edges': [[0, 1, 2], [1, 0, 4], [0, 1, 3], [1, 2, 4], [0, 2, 1]]},
    'G09': {'left': 4, 'right': 3, 'edges': [[u, v] for u in range(4) for v in range(3)]},
    'G10': {'n': 3, 'source': 1, 'target': 1, 'edges': [[0, 1], [1, 2], [0, 2]]},
    'G11': {'workers': 2, 'jobs': [{'id': 'a', 'duration': 2, 'deps': []},
            {'id': 'b', 'duration': 2, 'deps': []}, {'id': 'c', 'duration': 1, 'deps': ['a']},
            {'id': 'd', 'duration': 5, 'deps': ['b']}, {'id': 'e', 'duration': 1, 'deps': ['c', 'd']}]},
    'G12': {'jobs': [{'id': 'long', 'duration': 7, 'deps': []},
                    {'id': 'short', 'duration': 1, 'deps': []}]},
    'G13': {'n': 4, 'edges': [[0, 1], [1, 2], [2, 3], [0, 2], [0, 3], [1, 3]]},
    'G14': {'n': 4, 'source': 0, 'target': 3, 'budget': 2,
            'edges': [[0, 3, 1, 2], [0, 1, 1, 0], [1, 2, 0, 0], [2, 3, 0, 0], [2, 1, 0, 0]]},
    'G15': {'n': 2, 'events': [['remove', 0, 1], ['add', 0, 1], ['query', 0, 1],
                              ['remove', 1, 0], ['count'], ['query', 1, 1]]},
    'G16': {'capacity': 2, 'events': [{'op': 'put', 'key': 'a', 'value': 1, 'size': 1},
             {'op': 'put', 'key': 'b', 'value': 2, 'size': 1},
             {'op': 'put', 'key': 'a', 'value': 3, 'size': 3},
             {'op': 'put', 'key': 'c', 'value': 4, 'size': 1}, {'op': 'get', 'key': 'a'},
             {'op': 'get', 'key': 'b'}]},
    'G17': {'initial': {'x': 1}, 'events': [{'op': 'begin', 'tx': 'old'},
             {'op': 'get', 'tx': 'old', 'key': 'x'}, {'op': 'begin', 'tx': 'new'},
             {'op': 'delete', 'tx': 'new', 'key': 'x'}, {'op': 'commit', 'tx': 'new'},
             {'op': 'begin', 'tx': 'new'}, {'op': 'set', 'tx': 'new', 'key': 'x', 'value': 1},
             {'op': 'commit', 'tx': 'new'}, {'op': 'commit', 'tx': 'old'}]},
    'G18': {'events': [{'op': 'set', 'at': 1, 'key': 'a', 'value': 1},
             {'op': 'delete', 'at': 1, 'key': 'a'}, {'op': 'get', 'at': 1, 'key': 'a', 'asof': 1},
             {'op': 'set', 'at': 1, 'key': 'a', 'value': 2},
             {'op': 'get', 'at': 2, 'key': 'a', 'asof': 1}]},
    'G19': {'stock': {'a': 2, 'b': 0}, 'events': [
             {'op': 'reserve', 'id': 'bad', 'items': {'a': 2, 'b': 1}},
             {'op': 'reserve', 'id': 'good', 'items': {'a': 2}},
             {'op': 'cancel', 'id': 'good'}, {'op': 'reserve', 'id': 'good', 'items': {'a': 1}}]},
    'G20': {'events': [{'seq': 3, 'delta': 7}, {'seq': 3, 'delta': 8}, {'seq': 3, 'delta': 7},
                       {'seq': 2, 'delta': 3}, {'seq': 1, 'delta': -4}, {'seq': 1, 'delta': -4}]},
    'G21': {'ttl': 2, 'requests': [{'at': 0, 'key': 'a', 'payload': 'a'},
             {'at': 1, 'key': 'a', 'payload': 'A'}, {'at': 2, 'key': 'a', 'payload': 'A'}]},
    'G22': {'ttl': 2, 'events': [{'op': 'acquire', 'at': 0, 'owner': 'a'},
             {'op': 'acquire', 'at': 2, 'owner': 'a'},
             {'op': 'renew', 'at': 2, 'owner': 'a', 'token': 1},
             {'op': 'release', 'at': 3, 'owner': 'a', 'token': 1}]},
    'G23': {'capacity': 1, 'period': 3, 'rate': 2, 'requests': [[0, 1], [1, 1], [2, 1], [3, 1]]},
    'G24': {'flows': [{'quantum': 2, 'jobs': [5, 1, 1]}, {'quantum': 3, 'jobs': [4, 2]}]},
    'G25': {'capacity': 2, 'events': [
             {'op': 'acquire', 'at': 0, 'id': 'a', 'permits': 1, 'timeout': 20},
             {'op': 'acquire', 'at': 1, 'id': 'b', 'permits': 2, 'timeout': 2},
             {'op': 'acquire', 'at': 1, 'id': 'c', 'permits': 1, 'timeout': 10},
             {'op': 'tick', 'at': 10}]},
    'G26': {'delay': 3, 'events': [{'at': 0, 'key': 'a', 'value': 0},
             {'at': 1, 'key': 'a', 'value': 1}, {'at': 2, 'key': 'a', 'value': 2},
             {'at': 2, 'key': 'b', 'value': 8}, {'at': 5, 'key': 'a', 'value': 3}], 'until': 7},
    'G27': {'threshold': 1, 'cooldown': 4, 'calls': [{'at': 0, 'ok': False},
             {'at': 1, 'ok': True}, {'at': 3, 'ok': True}, {'at': 4, 'ok': False},
             {'at': 8, 'ok': True}]},
    'G28': {'capacity': 1, 'events': [{'op': 'send', 'id': 's1', 'value': 1},
             {'op': 'send', 'id': 's2', 'value': 2}, {'op': 'send', 'id': 's3', 'value': 3},
             {'op': 'close'}, {'op': 'recv', 'id': 'r1'}, {'op': 'recv', 'id': 'r2'}, {'op': 'close'}]},
    'G29': {'events': [{'op': 'put', 'key': 'a', 'value': 1, 'deps': []},
             {'op': 'put', 'key': 'b', 'value': 2, 'deps': ['a']},
             {'op': 'put', 'key': 'c', 'value': 3, 'deps': ['b']},
             {'op': 'put', 'key': 'a', 'value': 4, 'deps': ['c']}, {'op': 'get', 'key': 'b'},
             {'op': 'get', 'key': 'a'}, {'op': 'invalidate', 'key': 'b'}, {'op': 'get', 'key': 'a'}]},
    'G30': {'available': ['1.0.0-0', '1.0.0-0.0', '1.0.0-a', '1.0.0-a.0', '1.0.0-a-a',
                          '1.0.0-A', '1.0.0+two', '1.0.0+one'],
            'constraints': [], 'include_prerelease': True},
    'G31': {'events': [{'op': 'write', 'at': 0, 'key': 'x', 'value': 1},
             {'op': 'delete', 'at': 0, 'key': 'z'}, {'op': 'write', 'at': 2, 'key': 'x', 'value': 2},
             {'op': 'compact', 'floor': 1}, {'op': 'read', 'at': 1},
             {'op': 'compact', 'floor': 2}, {'op': 'read', 'at': 2}]},
    'G32': {'base': {'a': None, 'b': 0}, 'local': {'a': 1, 'b': None}, 'remote': {'b': None}},
    'G33': {'events': [{'id': 'z', 'clock': [0, 0]}, {'id': 'a', 'clock': [1, 0]},
                       {'id': 'b', 'clock': [0, 1]}, {'id': 'c', 'clock': [1, 0]},
                       {'id': 'd', 'clock': [1, 1]}]},
    'G34': {'events': [{'op': 'arm', 'at': 0, 'id': 'b', 'delay': 1, 'interval': 2, 'count': 4},
             {'op': 'arm', 'at': 0, 'id': 'a', 'delay': 1, 'interval': 2, 'count': 4},
             {'op': 'cancel', 'at': 2, 'id': 'b'},
             {'op': 'arm', 'at': 6, 'id': 'a', 'delay': 5, 'interval': 0, 'count': 1}], 'until': 9},
}


def _random_input(task_id, rng, iteration):
    """Produce bounded valid inputs, mixing cyclic/acyclic and event boundaries."""
    number = int(task_id[1:])
    n = 2 + iteration % 8
    if number in (1, 2, 3, 4, 5, 6, 10, 13):
        edges = []
        for _ in range(rng.randrange(2, 2 * n + 2)):
            u, v = rng.randrange(n), rng.randrange(n)
            if number in (1, 10, 13) and iteration % 2 == 0:
                if u == v:
                    continue
                u, v = sorted((u, v))
            edge = [u, v]
            if number == 3:
                edge.append(rng.randrange(-6, 10))
            elif number == 4:
                edge.append(rng.randrange(1, 7))
            edges.append(edge)
            if number in (1, 2, 5, 6, 10, 13) and rng.randrange(5) == 0:
                edges.append(edge[:])
        data = {'n': n, 'edges': edges}
        if number in (3, 4, 10):
            data['source'] = rng.randrange(n)
        if number in (4, 10):
            data['target'] = rng.randrange(n)
        return data
    if number == 7:
        n = 2 + iteration % 5
        start = rng.randrange(n)
        edges, u = [], start
        for _ in range(rng.randrange(0, 10)):
            v = rng.randrange(n)
            edges.append([u, v])
            u = v
        rng.shuffle(edges)
        if iteration % 3 == 2 and edges:
            edges[0][0] = rng.randrange(n)
        return {'n': n, 'start': start, 'edges': edges}
    if number == 8:
        n = 2 + iteration % 6
        return {'n': n, 'source': 0, 'sink': n - 1,
                'edges': [[rng.randrange(n), rng.randrange(n), rng.randrange(10)]
                          for _ in range(3 * n)]}
    if number == 9:
        left, right = 1 + iteration % 6, rng.randrange(0, 7)
        edges = [[u, v] for u in range(left) for v in range(right) if rng.randrange(2)]
        return {'left': left, 'right': right, 'edges': edges}
    if number in (11, 12):
        count = 2 + iteration % 7
        names = [f'j{i}' for i in range(count)]
        jobs = []
        for i, name in enumerate(names):
            candidates = names[:i] if iteration % 3 != 2 else names
            deps = [dep for dep in candidates if rng.randrange(4) == 0]
            if deps and rng.randrange(2):
                deps += deps[:1]
            jobs.append({'id': name, 'duration': rng.randrange(1, 9), 'deps': deps})
        rng.shuffle(jobs)
        data = {'jobs': jobs}
        if number == 11:
            data['workers'] = 1 + iteration % 4
        return data
    if number == 14:
        n = 2 + iteration % 6
        edges = [[rng.randrange(n), rng.randrange(n), rng.randrange(5), rng.randrange(4)]
                 for _ in range(3 * n)]
        if iteration % 2 == 0:
            edges.append([0, 0, 0, 0])
        return {'n': n, 'edges': edges, 'source': 0, 'target': n - 1, 'budget': iteration % 7}
    if number == 15:
        events = []
        for _ in range(25):
            action = rng.choice(['add', 'add', 'remove', 'query', 'count'])
            events.append([action] if action == 'count' else [action, rng.randrange(n), rng.randrange(n)])
        return {'n': n, 'events': events}
    if number == 16:
        events = []
        for _ in range(24):
            event = {'op': rng.choice(['put', 'put', 'get', 'delete']), 'key': rng.choice('abcd')}
            if event['op'] == 'put':
                event.update(value=rng.randrange(-9, 10), size=rng.randrange(1, 7))
            events.append(event)
        return {'capacity': iteration % 7, 'events': events}
    if number == 17:
        events = []
        for _ in range(30):
            op = rng.choice(['begin', 'begin', 'get', 'set', 'delete', 'commit', 'abort'])
            event = {'op': op, 'tx': rng.choice('abc')}
            if op in ('get', 'set', 'delete'):
                event['key'] = rng.choice('xyz')
            if op == 'set':
                event['value'] = rng.randrange(-5, 6)
            events.append(event)
        return {'initial': {key: rng.randrange(6) for key in 'xy'}, 'events': events}
    if number == 18:
        events, now = [], 0
        for _ in range(24):
            now += rng.randrange(3)
            event = {'at': now, 'op': rng.choice(['set', 'set', 'delete', 'get']), 'key': rng.choice('abc')}
            if event['op'] == 'set':
                event['value'] = rng.randrange(-8, 9)
            elif event['op'] == 'get':
                event['asof'] = rng.randrange(now + 1)
            events.append(event)
        return {'events': events}
    if number == 19:
        events = []
        for _ in range(24):
            event = {'op': rng.choice(['reserve', 'reserve', 'commit', 'cancel']), 'id': rng.choice('pqrs')}
            if event['op'] == 'reserve':
                event['items'] = {key: rng.randrange(1, 4) for key in 'abc' if rng.randrange(2)}
            events.append(event)
        return {'stock': {key: rng.randrange(0, 8) for key in 'abc'}, 'events': events}
    if number == 20:
        return {'events': [{'seq': rng.randrange(1, 10), 'delta': rng.randrange(-7, 8)} for _ in range(25)]}
    if number == 21:
        now, requests = 0, []
        for _ in range(20):
            now += rng.randrange(3)
            requests.append({'at': now, 'key': rng.choice('abc'), 'payload': rng.choice(['a', 'B', '', 'a b'])})
        return {'ttl': 1 + iteration % 5, 'requests': requests}
    if number == 22:
        now, events = 0, []
        for _ in range(24):
            now += rng.randrange(3)
            event = {'op': rng.choice(['acquire', 'acquire', 'renew', 'release']), 'at': now,
                     'owner': rng.choice('abc')}
            if event['op'] != 'acquire':
                event['token'] = rng.randrange(1, 10)
            events.append(event)
        return {'ttl': 1 + iteration % 5, 'events': events}
    if number == 23:
        now, requests = 0, []
        for _ in range(20):
            now += rng.randrange(4)
            requests.append([now, rng.randrange(0, 8)])
        return {'capacity': iteration % 6, 'period': 1 + iteration % 5, 'rate': iteration % 4,
                'requests': requests}
    if number == 24:
        return {'flows': [{'quantum': rng.randrange(1, 5),
                           'jobs': [rng.randrange(1, 12) for _ in range(rng.randrange(0, 7))]}
                          for _ in range(1 + iteration % 5)]}
    if number == 25:
        capacity, now, events = 1 + iteration % 4, 0, []
        ids = []
        for i in range(24):
            now += rng.randrange(3)
            op = rng.choice(['acquire', 'acquire', 'release', 'cancel', 'tick'])
            event = {'op': op, 'at': now}
            if op == 'acquire':
                name = f'q{i}'
                if ids and rng.randrange(5) == 0:
                    name = rng.choice(ids)
                ids.append(name)
                event.update(id=name, permits=rng.randrange(1, capacity + 1), timeout=rng.randrange(0, 8))
            elif op != 'tick':
                event['id'] = rng.choice(ids) if ids else 'missing'
            events.append(event)
        return {'capacity': capacity, 'events': events}
    if number == 26:
        now, events = 0, []
        for _ in range(18):
            now += rng.randrange(3)
            events.append({'at': now, 'key': rng.choice('abc'), 'value': rng.randrange(-9, 10)})
        return {'delay': 1 + iteration % 5, 'events': events, 'until': now + iteration % 7}
    if number == 27:
        now, calls = 0, []
        for _ in range(22):
            now += rng.randrange(4)
            calls.append({'at': now, 'ok': bool(rng.randrange(2))})
        return {'threshold': 1 + iteration % 4, 'cooldown': 1 + iteration % 5, 'calls': calls}
    if number == 28:
        events = []
        for i in range(22):
            op = rng.choice(['send', 'send', 'recv', 'recv', 'close'])
            event = {'op': op}
            if op != 'close':
                event['id'] = f'r{i}'
            if op == 'send':
                event['value'] = rng.randrange(-9, 10)
            events.append(event)
        return {'capacity': iteration % 4, 'events': events}
    if number == 29:
        events = []
        for _ in range(25):
            op = rng.choice(['put', 'put', 'get', 'invalidate'])
            event = {'op': op, 'key': rng.choice('abcd')}
            if op == 'put':
                event.update(value=rng.randrange(-5, 6), deps=[key for key in 'abcd' if rng.randrange(4) == 0])
            events.append(event)
        return {'events': events}
    if number == 30:
        pool = ['0.1.0', '1.0.0-alpha', '1.0.0-alpha.2', '1.0.0-alpha.10', '1.0.0-beta',
                '1.0.0', '1.0.0+a', '1.0.0+z', '1.0.1', '1.1.0', '2.0.0-1', '2.0.0']
        available = [rng.choice(pool) for _ in range(18)]
        constraints = [{'op': rng.choice(['=', '>', '>=', '<', '<=']), 'version': rng.choice(pool)}
                       for _ in range(iteration % 4)]
        return {'available': available, 'constraints': constraints, 'include_prerelease': bool(iteration % 2)}
    if number == 31:
        events, now, floor = [], 0, 0
        for _ in range(24):
            op = rng.choice(['write', 'write', 'delete', 'compact', 'read'])
            if op in ('write', 'delete'):
                now += rng.randrange(3)
                event = {'op': op, 'at': now, 'key': rng.choice('abc')}
                if op == 'write':
                    event['value'] = rng.randrange(-9, 10)
            elif op == 'compact':
                floor = rng.randrange(floor, now + 1)
                event = {'op': op, 'floor': floor}
            else:
                event = {'op': op, 'at': rng.randrange(floor, now + 1)}
            events.append(event)
        return {'events': events}
    if number == 32:
        pool = [None, 0, 1, 2, 'a', 'b']
        return {name: {key: rng.choice(pool) for key in 'abcdef' if rng.randrange(3) != 0}
                for name in ('base', 'local', 'remote')}
    if number == 33:
        width = 1 + iteration % 5
        names = list('abcdefg')[:2 + iteration % 6]
        rng.shuffle(names)
        return {'events': [{'id': name, 'clock': [rng.randrange(4) for _ in range(width)]} for name in names]}
    if number == 34:
        now, events = 0, []
        for _ in range(16):
            now += rng.randrange(3)
            event = {'op': rng.choice(['arm', 'arm', 'cancel']), 'at': now, 'id': rng.choice('abc')}
            if event['op'] == 'arm':
                event.update(delay=rng.randrange(1, 6), interval=rng.randrange(1, 5), count=rng.randrange(1, 5))
            events.append(event)
        return {'events': events, 'until': now + iteration % 9}
    raise KeyError(task_id)


def build_tasks():
    """Build 34 independently specified tasks, each with 10 distinct cases."""
    import json

    tasks = []
    for task_id, (title, category, specification) in SPECS.items():
        cases, inputs = [], set()
        for index, (data, expected) in enumerate(ANCHORS[task_id]):
            actual = reference(task_id, data)
            # JSON serialization also distinguishes Boolean from integer values.
            assert json.dumps(actual, sort_keys=True, separators=(',', ':')) == json.dumps(
                expected, sort_keys=True, separators=(',', ':')), (task_id, index, actual, expected)
            key = json.dumps(data, sort_keys=True, separators=(',', ':'))
            assert key not in inputs, (task_id, 'duplicate anchor')
            inputs.add(key)
            cases.append({'id': f'{task_id}-public-{index + 1}', 'input': copy.deepcopy(data),
                          'expected': copy.deepcopy(expected), 'visibility': 'public'})
        rng = random.Random(2026100700 + int(task_id[1:]))
        data = copy.deepcopy(ADVERSARIAL[task_id])
        key = json.dumps(data, sort_keys=True, separators=(',', ':'))
        assert key not in inputs, (task_id, 'duplicate adversarial input')
        inputs.add(key)
        cases.append({'id': f'{task_id}-hidden-1', 'input': data,
                      'expected': reference(task_id, data), 'visibility': 'hidden'})
        trial = 0
        while len(cases) < 10:
            data = _random_input(task_id, rng, trial)
            trial += 1
            key = json.dumps(data, sort_keys=True, separators=(',', ':'))
            if key in inputs:
                continue
            inputs.add(key)
            cases.append({'id': f'{task_id}-hidden-{len(cases) - 1}', 'input': data,
                          'expected': reference(task_id, data), 'visibility': 'hidden'})
        tasks.append({'id': task_id, 'title': title, 'category': category, 'difficulty': 'hard',
                      'prompt': COMMON + specification, 'cases': cases})
    return tasks


def validate_oracles():
    """Cross-check key graph oracles using different, exhaustive formulations."""
    rng = random.Random(173901)
    checks = 0
    # Floyd-Warshall independently checks Bellman-Ford and negative propagation.
    for _ in range(300):
        n, source = rng.randrange(1, 7), None
        source = rng.randrange(n)
        edges = [[rng.randrange(n), rng.randrange(n), rng.randrange(-4, 7)]
                 for _ in range(rng.randrange(15))]
        infinity = 10 ** 8
        distance = [[infinity] * n for _ in range(n)]
        for i in range(n):
            distance[i][i] = 0
        for u, v, cost in edges:
            distance[u][v] = min(distance[u][v], cost)
        for k in range(n):
            for i in range(n):
                for j in range(n):
                    if distance[i][k] < infinity and distance[k][j] < infinity:
                        distance[i][j] = min(distance[i][j], distance[i][k] + distance[k][j])
        expected = []
        for j in range(n):
            if any(distance[source][k] < infinity and distance[k][k] < 0 and distance[k][j] < infinity
                   for k in range(n)):
                expected.append('-inf')
            else:
                expected.append(None if distance[source][j] >= infinity else distance[source][j])
        assert reference('G03', {'n': n, 'source': source, 'edges': edges}) == expected
        checks += 1
    # Edge permutation enumeration checks Euler trails and their exact tie-break.
    for _ in range(200):
        n = rng.randrange(1, 5)
        source, count = rng.randrange(n), rng.randrange(7)
        edges = [[rng.randrange(n), rng.randrange(n)] for _ in range(count)]
        expected = None
        for permutation in itertools.permutations(range(count)):
            u, vertices = source, [source]
            for edge_id in permutation:
                a, b = edges[edge_id]
                if a != u:
                    break
                u = b
                vertices.append(u)
            else:
                expected = {'vertices': vertices, 'edge_ids': list(permutation)}
                break
        assert reference('G07', {'n': n, 'start': source, 'edges': edges}) == expected
        checks += 1
    # Every cut is enumerated independently of the max-flow augmentations.
    for _ in range(200):
        n = rng.randrange(2, 7)
        edges = [[rng.randrange(n), rng.randrange(n), rng.randrange(6)] for _ in range(3 * n)]
        result = reference('G08', {'n': n, 'source': 0, 'sink': n - 1, 'edges': edges})
        capacities = []
        for mask in range(1 << n):
            if (mask & 1) and not ((mask >> (n - 1)) & 1):
                capacities.append(sum(capacity for u, v, capacity in edges
                                      if (mask >> u) & 1 and not ((mask >> v) & 1)))
        assert result['flow'] == min(capacities)
        cut = set(result['reachable'])
        assert 0 in cut and n - 1 not in cut
        assert sum(capacity for u, v, capacity in edges if u in cut and v not in cut) == result['flow']
        checks += 1
    # Full assignment vectors check both matching optimality and tie-breaks.
    for _ in range(120):
        left, right = rng.randrange(5), rng.randrange(5)
        edges = [[u, v] for u in range(left) for v in range(right) if rng.randrange(2)]
        allowed, possibilities = set(map(tuple, edges)), []
        for vector in itertools.product(range(right + 1), repeat=left):
            used = [v for v in vector if v != right]
            if len(set(used)) != len(used):
                continue
            if any((u, v) not in allowed for u, v in enumerate(vector) if v != right):
                continue
            possibilities.append((-len(used), vector))
        negative_size, vector = min(possibilities)
        expected = {'size': -negative_size, 'pairs': [[u, v] for u, v in enumerate(vector) if v != right]}
        assert reference('G09', {'left': left, 'right': right, 'edges': edges}) == expected
        checks += 1
    # Optimal nonnegative walks never repeat a (vertex, resource-used) state.
    for _ in range(100):
        n, budget = rng.randrange(1, 4), rng.randrange(3)
        source, target = rng.randrange(n), rng.randrange(n)
        edges = [[rng.randrange(n), rng.randrange(n), rng.randrange(3), rng.randrange(2)] for _ in range(5)]
        candidates = []

        def visit(u, used, cost, path, seen):
            if u == target:
                candidates.append((cost, used, len(path) - 1, tuple(path)))
            for a, b, weight, resource in edges:
                state = (b, used + resource)
                if a == u and used + resource <= budget and state not in seen:
                    visit(b, used + resource, cost + weight, path + [b], seen | {state})

        visit(source, 0, 0, [source], {(source, 0)})
        expected = None
        if candidates:
            cost, used, _, path = min(candidates)
            expected = {'cost': cost, 'resource': used, 'path': list(path)}
        assert reference('G14', {'n': n, 'budget': budget, 'source': source,
                                 'target': target, 'edges': edges}) == expected
        checks += 1
    # Additional literal expected outputs for the most subtle hidden fixtures.
    assert reference('G17', ADVERSARIAL['G17']) == {
        'results': ['ok', 1, 'ok', 'ok', {'committed': True, 'version': 1}, 'ok', 'ok',
                    {'committed': True, 'version': 2}, {'committed': False, 'conflicts': ['x']}],
        'values': {'x': 1}, 'versions': {'x': 2}, 'version': 2}
    assert reference('G25', ADVERSARIAL['G25']) == {
        'results': ['granted', 'queued', 'queued', 'tick'], 'grants': [[0, 'a'], [3, 'c']],
        'timeouts': [[3, 'b']], 'available': 0, 'active': ['a', 'c'], 'waiting': []}
    assert reference('G30', ADVERSARIAL['G30']) == {
        'eligible': ['1.0.0-0', '1.0.0-0.0', '1.0.0-A', '1.0.0-a', '1.0.0-a.0',
                     '1.0.0-a-a', '1.0.0+one', '1.0.0+two'], 'selected': '1.0.0+one'}
    assert reference('G34', ADVERSARIAL['G34']) == {
        'fired': [[1, 'a'], [1, 'b'], [3, 'a'], [5, 'a']],
        'pending': [{'id': 'a', 'next': 11, 'remaining': 1, 'interval': 0}]}
    return {'literal_public_anchors': 68, 'independent_cross_checks': checks + 4}


if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='also run independent oracle cross-checks')
    args = parser.parse_args()
    tasks = build_tasks()
    assert len(tasks) == 34
    assert tasks == build_tasks()
    result = {'tasks': len(tasks), 'cases': sum(len(task['cases']) for task in tasks),
              'public': sum(case['visibility'] == 'public' for task in tasks for case in task['cases'])}
    if args.check:
        result.update(validate_oracles())
    print(json.dumps(result, sort_keys=True))
