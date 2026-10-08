import json

def solve(data):
    events = data.get("events", [])
    cache = {}
    results = []

    def get_transitive_dependents(key):
        # Returns set of all keys that transitively depend on key (excluding key itself)
        dependents = set()
        stack = [key]
        while stack:
            current = stack.pop()
            for k, v in cache.items():
                if current in v["deps"] and k not in dependents and k != key:
                    dependents.add(k)
                    stack.append(k)
        return dependents

    def creates_cycle(key, deps):
        # Check if adding key with given deps creates a cycle in the current cache
        # Self-dependency
        if key in deps:
            return True
        # Check if any dep transitively depends on key
        # We need to check if key is reachable from any of the deps in the current dependency graph
        # Build reverse adjacency: for each node, which nodes depend on it
        # Actually, we need to check if key is in the transitive closure of deps
        # Let's do BFS/DFS from each dep to see if we can reach key
        visited = set()
        stack = list(deps)
        while stack:
            current = stack.pop()
            if current == key:
                return True
            if current in visited:
                continue
            visited.add(current)
            if current in cache:
                for dep in cache[current]["deps"]:
                    if dep not in visited:
                        stack.append(dep)
        return False

    for event in events:
        op = event.get("op")
        if op == "put":
            key = event.get("key")
            value = event.get("value")
            deps = event.get("deps", [])
            # Check if all deps are already cached
            missing = False
            for d in deps:
                if d not in cache:
                    missing = True
                    break
            if missing:
                results.append("missing")
                continue
            # Check for cycle
            if creates_cycle(key, deps):
                results.append("cycle")
                continue
            # Accepted put: remove all transitive dependents of key except key itself
            dependents = get_transitive_dependents(key)
            for dep_key in dependents:
                del cache[dep_key]
            # Store the new entry
            sorted_unique_deps = sorted(set(deps))
            cache[key] = {"value": value, "deps": sorted_unique_deps}
            results.append("stored")
        elif op == "get":
            key = event.get("key")
            if key in cache:
                results.append(cache[key]["value"])
            else:
                results.append(None)
        elif op == "invalidate":
            key = event.get("key")
            # Remove key plus all its transitive dependents
            removed = set()
            if key in cache:
                removed.add(key)
            dependents = get_transitive_dependents(key)
            removed.update(dependents)
            for k in removed:
                if k in cache:
                    del cache[k]
            results.append(sorted(removed))
        else:
            # Unknown op, ignore or handle as needed
            results.append(None)

    # Build entries mapping
    entries = {}
    for k, v in cache.items():
        entries[k] = {"value": v["value"], "deps": v["deps"]}

    return {"results": results, "entries": entries}
