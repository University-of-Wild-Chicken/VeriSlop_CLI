def solve(data):
    def canonical(value):
        if value is None:
            return ("null",)
        if isinstance(value, bool):
            return ("bool", value)
        if isinstance(value, (int, float)):
            # JSON numbers compare numerically, while booleans remain distinct.
            return ("number", value)
        if isinstance(value, str):
            return ("string", value)
        if isinstance(value, list):
            return ("array", tuple(canonical(item) for item in value))
        if isinstance(value, dict):
            return ("object", tuple(sorted((key, canonical(item)) for key, item in value.items())))
        raise TypeError("Input must contain JSON-compatible values")

    left = data["left"]
    right = data["right"]
    key = data["key"]
    mode = data["mode"]

    right_by_key = {}
    for index, row in enumerate(right):
        if key in row and row[key] is not None:
            right_by_key.setdefault(canonical(row[key]), []).append(index)

    matched_right = set()
    result = []
    for left_row in left:
        if key in left_row and left_row[key] is not None:
            matches = right_by_key.get(canonical(left_row[key]), ())
        else:
            matches = ()
        if matches:
            for index in matches:
                matched_right.add(index)
                result.append({"left": left_row, "right": right[index]})
        elif mode in ("left", "full"):
            result.append({"left": left_row, "right": None})

    if mode == "full":
        for index, row in enumerate(right):
            if index not in matched_right:
                result.append({"left": None, "right": row})

    return result
