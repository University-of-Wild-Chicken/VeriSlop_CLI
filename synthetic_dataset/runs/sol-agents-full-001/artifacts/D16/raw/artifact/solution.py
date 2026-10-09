from copy import deepcopy


def solve(data):
    value = deepcopy(data['value'])
    errors = []

    def pointer(path, name):
        return path + '/' + str(name).replace('~', '~0').replace('/', '~1')

    def equal(a, b):
        if isinstance(a, bool) or isinstance(b, bool):
            return type(a) is type(b) and a == b
        if a is None or b is None:
            return a is None and b is None
        return a == b

    def validate(node, schema, path):
        kind = schema['type']
        matches = {
            'object': isinstance(node, dict),
            'array': isinstance(node, list),
            'string': isinstance(node, str),
            'integer': isinstance(node, int) and not isinstance(node, bool),
            'boolean': isinstance(node, bool),
            'null': node is None,
        }
        if not matches.get(kind, False):
            errors.append({'path': path, 'error': 'type'})
            return
        if kind == 'object':
            properties = schema.get('properties', {})
            required = set(schema.get('required', []))
            original = set(node)
            for name in sorted(set(properties) | required):
                child_path = pointer(path, name)
                child_schema = properties.get(name)
                if name not in node:
                    if child_schema is not None and 'default' in child_schema:
                        node[name] = deepcopy(child_schema['default'])
                    elif name in required:
                        errors.append({'path': child_path, 'error': 'required'})
                        continue
                    else:
                        continue
                if child_schema is not None:
                    validate(node[name], child_schema, child_path)
            if schema.get('additional', True) is False:
                for name in sorted(original - set(properties)):
                    errors.append({'path': pointer(path, name), 'error': 'additional'})
        elif kind == 'array':
            if 'items' in schema:
                for index, child in enumerate(node):
                    validate(child, schema['items'], pointer(path, index))
        else:
            if kind == 'integer':
                if ('minimum' in schema and node < schema['minimum']) or ('maximum' in schema and node > schema['maximum']):
                    errors.append({'path': path, 'error': 'range'})
            if 'enum' in schema and not any(equal(node, candidate) for candidate in schema['enum']):
                errors.append({'path': path, 'error': 'enum'})

    validate(value, data['schema'], '')
    return {'value': value, 'errors': errors}
