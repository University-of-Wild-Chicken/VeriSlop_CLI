import json

def _canonical(value):
    """Return a canonical JSON string for structural equality (object key order ignored)."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'))

def solve(data):
    runs = data.get('runs', [])
    start = data.get('start', 0)
    end = data.get('end', 0)

    # Validate counts and collect valid runs
    valid_runs = []
    for i, run in enumerate(runs):
        count = run.get('count')
        # Reject if count is not an integer (boolean is invalid) or negative
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            return {'error': 'count', 'run': i}
        value = run.get('value')
        valid_runs.append((count, value))

    # Remove zero-count runs and merge adjacent runs with structurally equal values
    normalized = []
    for count, value in valid_runs:
        if count == 0:
            continue
        if normalized:
            last_count, last_value = normalized[-1]
            if _canonical(last_value) == _canonical(value):
                normalized[-1] = (last_count + count, last_value)
            else:
                normalized.append((count, value))
        else:
            normalized.append((count, value))

    # Calculate total length
    total_length = sum(count for count, _ in normalized)

    # Clamp endpoints
    if start < 0:
        start = 0
    if end > total_length:
        end = total_length

    # If end <= start, return empty slice
    if end <= start:
        slice_result = []
    else:
        # Expand only the requested slice (length at most 100)
        slice_result = []
        pos = 0
        for count, value in normalized:
            run_start = pos
            run_end = pos + count
            if run_end <= start:
                pos = run_end
                continue
            if run_start >= end:
                break
            # Determine overlap with [start, end)
            overlap_start = max(start, run_start)
            overlap_end = min(end, run_end)
            if overlap_start < overlap_end:
                slice_result.extend([value] * (overlap_end - overlap_start))
            pos = run_end

    # Format normalized runs for output
    output_runs = [{'count': count, 'value': value} for count, value in normalized]

    return {
        'runs': output_runs,
        'length': total_length,
        'slice': slice_result
    }