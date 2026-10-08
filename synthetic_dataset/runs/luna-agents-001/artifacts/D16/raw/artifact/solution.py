import copy


def solve(data):
    value = copy.deepcopy(data["value"])
    errors = []

    def escape(part):
        return str(part).replace("~", "~0").replace("/", "~1")

    def validate(current, schema, path):
        expected = schema.get("type")
        matches = {
            "object": lambda v: isinstance(v, dict),
            "array": lambda v: isinstance(v, list),
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "null": lambda v: v is None,
        }
        if expected in matches and not matches[expected](current):
            errors.append({"path": path, "error": "type"})
            return current

        if expected == "object" and isinstance(current, dict):
            properties = schema.get("properties", {})
            required = set(schema.get("required", []))
            for name in sorted(set(properties) | required):
                child_path = path + "/" + escape(name)
                if name not in current:
                    if name in properties and "default" in properties[name]:
                        current[name] = copy.deepcopy(properties[name]["default"])
                        current[name] = validate(current[name], properties[name], child_path)
                    elif name in required:
                        errors.append({"path": child_path, "error": "required"})
                elif name in properties:
                    current[name] = validate(current[name], properties[name], child_path)
            if schema.get("additional", True) is False:
                for name in sorted(set(current) - set(properties)):
                    errors.append({"path": path + "/" + escape(name), "error": "additional"})

        elif expected == "array" and isinstance(current, list) and "items" in schema:
            for index, item in enumerate(current):
                current[index] = validate(item, schema["items"], path + "/" + str(index))

        elif expected == "integer" and isinstance(current, int) and not isinstance(current, bool):
            if "minimum" in schema and current < schema["minimum"]:
                errors.append({"path": path, "error": "range"})
            if "maximum" in schema and current > schema["maximum"]:
                errors.append({"path": path, "error": "range"})

        if "enum" in schema and current not in schema["enum"]:
            errors.append({"path": path, "error": "enum"})
        return current

    value = validate(value, data["schema"], "")
    return {"value": value, "errors": errors}
