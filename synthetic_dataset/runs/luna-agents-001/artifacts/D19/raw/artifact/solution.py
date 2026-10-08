def solve(data):
    key_name = data["key"]
    left_rows = data["left"]
    right_rows = data["right"]
    mode = data["mode"]

    def freeze(value):
        if value is None:
            return ("null",)
        if isinstance(value, bool):
            return ("bool", value)
        if isinstance(value, (int, float)):
            return ("number", value)
        if isinstance(value, str):
            return ("string", value)
        if isinstance(value, list):
            return ("array", tuple(freeze(item) for item in value))
        if isinstance(value, dict):
            return ("object", frozenset((name, freeze(item)) for name, item in value.items()))
        raise TypeError("Unsupported JSON value")

    right_by_key = {}
    for index, row in enumerate(right_rows):
        value = row.get(key_name)
        if value is not None:
            right_by_key.setdefault(freeze(value), []).append(index)

    matched_right = [False] * len(right_rows)
    result = []

    for left_row in left_rows:
        value = left_row.get(key_name)
        matches = right_by_key.get(freeze(value), []) if value is not None else []
        if matches:
            for index in matches:
                matched_right[index] = True
                result.append({"left": left_row, "right": right_rows[index]})
        elif mode in ("left", "full"):
            result.append({"left": left_row, "right": None})

    if mode == "full":
        for index, right_row in enumerate(right_rows):
            if not matched_right[index]:
                result.append({"left": None, "right": right_row})

    return result
