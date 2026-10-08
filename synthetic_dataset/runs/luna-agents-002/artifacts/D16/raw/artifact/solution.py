import copy


def solve(data):
    value = copy.deepcopy(data["value"])
    errors = []

    def pointer(path, name):
        escaped = str(name).replace("~", "~0").replace("/", "~1")
        return path + "/" + escaped

    def scalar_equal(left, right):
        if isinstance(left, bool) or isinstance(right, bool):
            return type(left) is type(right) and left == right
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return type(left) is type(right) and left == right
        return type(left) is type(right) and left == right

    def validate(current, schema, path):
        if not isinstance(schema, dict):
            return current

        expected = schema.get("type")
        matches = True
        if expected == "object":
            matches = isinstance(current, dict)
        elif expected == "array":
            matches = isinstance(current, list)
        elif expected == "string":
            matches = isinstance(current, str)
        elif expected == "integer":
            matches = isinstance(current, int) and not isinstance(current, bool)
        elif expected == "boolean":
            matches = isinstance(current, bool)
        elif expected == "null":
            matches = current is None

        if not matches:
            errors.append({"path": path, "error": "type"})
            return current

        if expected == "object":
            properties = schema.get("properties", {})
            if not isinstance(properties, dict):
                properties = {}
            required = schema.get("required", [])
            required_set = set(required) if isinstance(required, list) else set()
            original_keys = set(current)

            for name in sorted(set(properties) | required_set):
                child_path = pointer(path, name)
                if name in current:
                    if name in properties:
                        current[name] = validate(current[name], properties[name], child_path)
                elif name in properties and isinstance(properties[name], dict) and "default" in properties[name]:
                    current[name] = copy.deepcopy(properties[name]["default"])
                    current[name] = validate(current[name], properties[name], child_path)
                elif name in required_set:
                    errors.append({"path": child_path, "error": "required"})

            if schema.get("additional", True) is False:
                for name in sorted(original_keys - set(properties)):
                    errors.append({"path": pointer(path, name), "error": "additional"})

        elif expected == "array":
            item_schema = schema.get("items")
            if item_schema is not None:
                for index, item in enumerate(current):
                    current[index] = validate(item, item_schema, pointer(path, index))

        elif expected == "integer":
            if "minimum" in schema and current < schema["minimum"]:
                errors.append({"path": path, "error": "range"})
            if "maximum" in schema and current > schema["maximum"]:
                errors.append({"path": path, "error": "range"})

        if expected in ("string", "integer", "boolean", "null") and "enum" in schema:
            choices = schema["enum"]
            if isinstance(choices, list) and not any(scalar_equal(current, item) for item in choices):
                errors.append({"path": path, "error": "enum"})

        return current

    result = validate(value, data["schema"], "")
    return {"value": result, "errors": errors}
