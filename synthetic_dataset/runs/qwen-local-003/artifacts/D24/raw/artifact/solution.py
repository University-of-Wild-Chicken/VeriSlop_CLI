import json

def solve(data):
    if not isinstance(data, dict):
        return {"error": "boundary", "edit": 0}
    text = data.get("text")
    edits = data.get("edits")
    if not isinstance(text, str) or not isinstance(edits, list):
        return {"error": "boundary", "edit": 0}

    # Precompute UTF-16 unit offsets for each character boundary in the original text.
    # boundaries[i] is the UTF-16 unit offset before character i (0-indexed).
    # boundaries has length len(text) + 1.
    boundaries = [0]
    for ch in text:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDBFF or 0xDC00 <= cp <= 0xDFFF:
            # Isolated surrogate - input spec says no isolated surrogates, but handle defensively
            # Actually spec says "containing no isolated surrogates", so this shouldn't happen.
            # But if it does, we can't really handle it properly. Let's treat as 1 unit for BMP-like.
            boundaries.append(boundaries[-1] + 1)
        elif cp > 0xFFFF:
            boundaries.append(boundaries[-1] + 2)
        else:
            boundaries.append(boundaries[-1] + 1)

    total_units = boundaries[-1]
    n_chars = len(text)

    # Validate each edit in input order
    prev_end = 0  # UTF-16 unit offset of previous edit's end
    validated = []  # list of (start_units, end_units, text, char_start, char_end)

    for i, edit in enumerate(edits):
        if not isinstance(edit, dict):
            return {"error": "boundary", "edit": i}
        start = edit.get("start")
        end = edit.get("end")
        new_text = edit.get("text")

        if not isinstance(start, int) or not isinstance(end, int) or not isinstance(new_text, str):
            return {"error": "boundary", "edit": i}

        # Check reversed span
        if start > end:
            return {"error": "boundary", "edit": i}

        # Check boundaries are valid character boundaries in 0..total_units
        # A UTF-16 unit offset is a valid character boundary if it equals boundaries[j] for some j
        # Find if start is a valid boundary
        start_valid = False
        start_char_idx = -1
        for j in range(n_chars + 1):
            if boundaries[j] == start:
                start_valid = True
                start_char_idx = j
                break
        if not start_valid:
            return {"error": "boundary", "edit": i}

        end_valid = False
        end_char_idx = -1
        for j in range(n_chars + 1):
            if boundaries[j] == end:
                end_valid = True
                end_char_idx = j
                break
        if not valid_end := end_valid:
            return {"error": "boundary", "edit": i}

        # Check overlap: start must be >= prev_end
        if start < prev_end:
            return {"error": "overlap", "edit": i}

        validated.append((start, end, new_text, start_char_idx, end_char_idx))
        prev_end = end

    # All validation passed. Now splice simultaneously.
    # Build result by walking through the original text and inserting edits at their positions.
    # Since edits are non-overlapping and in order (start >= prev_end), we can process them in order.
    # For each edit, we take the original text from the previous edit's end to this edit's start,
    # then append the edit's text, and continue.
    # Finally, append the remaining text after the last edit.

    result_parts = []
    prev_char_end = 0  # character index in original text where we left off

    for (start_units, end_units, new_text, start_char_idx, end_char_idx) in validated:
        # Append original text from prev_char_end to start_char_idx
        if start_char_idx > prev_char_end:
            result_parts.append(text[prev_char_idx:start_char_idx])
        # Append the edit's text
        result_parts.append(new_text)
        prev_char_end = end_char_idx

    # Append remaining text
    if prev_char_end < n_chars:
        result_parts.append(text[prev_char_end:])

    return {"text": "".join(result_parts)}
