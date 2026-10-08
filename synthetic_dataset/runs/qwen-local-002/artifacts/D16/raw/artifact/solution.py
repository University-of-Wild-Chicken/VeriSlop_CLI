import copy


def _escape_pointer_segment(segment):
    return str(segment).replace('~', '~0').replace('/', '~1')


def _join_pointer(base, segment):
    if base == '':
        return '/' + _escape_pointer_segment(segment)
    return base + '/' + _escape_pointer_segment(segment)


def _type_matches(value, type_name):
    if type_name == 'null':
        return value is None
    if type_name == 'boolean':
        return isinstance(value, bool)
    if type_name == 'integer':
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == 'number':
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_name == 'string':
        return isinstance(value, str)
    if type_name == 'array':
        return isinstance(value, list)
    if type_name == 'object':
        return isinstance(value, dict)
    return False


def _validate(value, schema, path, errors):
    if not isinstance(schema, dict):
        return

    type_name = schema.get('type')
    if type_name is not None and not _type_matches(value, type_name):
        errors.append({'path': path, 'error': 'type'})
        return

    if isinstance(value, dict) and type_name in (None, 'object'):
        properties = schema.get('properties')
        if isinstance(properties, dict):
            for name in sorted(properties.keys()):
                prop_schema = properties[name]
                if name in value:
                    _validate(value[name], prop_schema, _join_pointer(path, name), errors)
                else:
                    if 'default' in prop_schema:
                        value[name] = copy.deepcopy(prop_schema['default'])
                        _validate(value[name], prop_schema, _join_pointer(path, name), errors)
                    elif name in (schema.get('required') or []):
                        errors.append({'path': _join_pointer(path, name), 'error': 'required'})

        if schema.get('additional') is False:
            known = set(properties.keys()) if isinstance(properties, dict) else set()
            for name in sorted(value.keys()):
                if name not in known:
                    errors.append({'path': _join_pointer(path, name), 'error': 'additional'})

    if isinstance(value, list) and type_name in (None, 'array'):
        items_schema = schema.get('items')
        if isinstance(items_schema, dict):
            for i, item in enumerate(value):
                _validate(item, items_schema, _join_pointer(path, i), errors)

    if isinstance(value, int) and not isinstance(value, bool):
        if 'minimum' in schema and value < schema['minimum']:
            errors.append({'path': path, 'error': 'range'})
        elif 'maximum' in schema and value > schema['maximum']:
            errors.append({'path': path, 'error': 'range'})

    if 'enum' in schema:
        enum = schema['enum']
        if isinstance(enum, list):
            if value not in enum:
                errors.append({'path': path, 'error': 'enum'})


def solve(data):
    value = copy.deepcopy(data.get('value'))
    schema = data.get('schema')
    errors = []
    _validate(value, schema, '', errors)
    return {'value': value, 'errors': errors}
