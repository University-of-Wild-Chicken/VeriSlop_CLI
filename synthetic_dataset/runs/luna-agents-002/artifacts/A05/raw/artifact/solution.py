def solve(data):
    strings = sorted(set(s for s in data["strings"] if s))
    strings = [s for s in strings if not any(s != t and s in t for t in strings)]
    n = len(strings)
    if n == 0:
        return ""

    overlap = [[0] * n for _ in range(n)]
    for i, a in enumerate(strings):
        for j, b in enumerate(strings):
            if i != j:
                for k in range(min(len(a), len(b)), 0, -1):
                    if a.endswith(b[:k]):
                        overlap[i][j] = k
                        break

    dp = {}
    for i, s in enumerate(strings):
        dp[(1 << i, i)] = s

    for mask in range(1, 1 << n):
        for last in range(n):
            current = dp.get((mask, last))
            if current is None:
                continue
            for nxt in range(n):
                bit = 1 << nxt
                if mask & bit:
                    continue
                candidate = current + strings[nxt][overlap[last][nxt]:]
                key = (mask | bit, nxt)
                previous = dp.get(key)
                if previous is None or (len(candidate), candidate) < (len(previous), previous):
                    dp[key] = candidate

    full = (1 << n) - 1
    return min((dp[(full, i)] for i in range(n)), key=lambda s: (len(s), s))
