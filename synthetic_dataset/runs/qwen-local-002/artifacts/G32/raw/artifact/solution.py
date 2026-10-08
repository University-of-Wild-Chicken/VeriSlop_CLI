def solve(data):
    base = data.get("base", {})
    local = data.get("local", {})
    remote = data.get("remote", {})

    def enc(obj, key):
        if key in obj:
            return {"present": True, "value": obj[key]}
        else:
            return {"present": False}

    keys = set(base.keys()) | set(local.keys()) | set(remote.keys())
    merged = {}
    conflicts = []

    for key in keys:
        in_base = key in base
        in_local = key in local
        in_remote = key in remote

        # Determine if local and remote are equal (presence and value)
        local_eq_remote = in_local == in_remote
        if local_eq_remote and in_local:
            local_eq_remote = local[key] == remote[key]

        if local_eq_remote:
            # Choose that value (absence deletes)
            if in_local:
                merged[key] = local[key]
            # else absent -> not added
        else:
            # local != remote
            # if local == base choose remote
            local_eq_base = in_local == in_base
            if local_eq_base and in_local:
                local_eq_base = local[key] == base[key]
            if local_eq_base:
                # choose remote
                if in_remote:
                    merged[key] = remote[key]
                # else absent -> not added
            else:
                # if remote == base choose local
                remote_eq_base = in_remote == in_base
                if remote_eq_base and in_remote:
                    remote_eq_base = remote[key] == base[key]
                if remote_eq_base:
                    # choose local
                    if in_local:
                        merged[key] = local[key]
                    # else absent -> not added
                else:
                    # conflict
                    conflicts.append({
                        "key": key,
                        "base": enc(base, key),
                        "local": enc(local, key),
                        "remote": enc(remote, key)
                    })

    conflicts.sort(key=lambda c: c["key"])

    return {"merged": merged, "conflicts": conflicts}