def solve(data):
    lines = list(data.get('lines', []))
    operations = data.get('operations', [])

    for idx, op in enumerate(operations):
        at = op.get('at')
        # Check if at is a boolean (bool is subclass of int in Python, so check first)
        if isinstance(at, bool):
            return {'error': 'range', 'operation': idx}
        # Check if at is an integer (not float, not string, etc.)
        if not isinstance(at, int):
            return {'error': 'range', 'operation': idx}
        # Check range: 0 <= at <= len(lines)
        if at < 0 or at > len(lines):
            return {'error': 'range', 'operation': idx}

        remove = op.get('remove', [])
        insert = op.get('insert', [])

        # Check if remove sequence matches current lines starting at at
        # Mismatch or running past EOF returns context error
        if at + len(remove) > len(lines):
            return {'error': 'context', 'operation': idx}
        for i in range(len(remove)):
            if lines[at + i] != remove[i]:
                return {'error': 'context', 'operation': idx}

        # Replace the sequence with insert
        lines[at:at + len(remove)] = insert

    return {'lines': lines}