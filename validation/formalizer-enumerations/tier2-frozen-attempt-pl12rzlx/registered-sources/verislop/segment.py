"""Mechanical clause segmentation of request bytes (verislop.segment/0.1).

Segments are byte intervals ``[start, end)`` of the exact prompt bytes with surrounding
whitespace trimmed. They exist so that a mechanical coverage check can ask whether every
recorded clause received a disposition. Segmentation is deliberately simple and conservative:
it cannot prove that an interpretation is semantically complete.
"""

from __future__ import annotations

import re

SEGMENTER_ID = "verislop.segment/0.1"
_ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "cf.", "approx.", "no.", "fig.")
_BULLET = re.compile(r"^\s*([-*•]|\d+[.)]|#+)\s")


def _byte_offsets(text: str) -> list[int]:
    offsets = [0]
    total = 0
    for ch in text:
        total += len(ch.encode("utf-8"))
        offsets.append(total)
    return offsets


def segments(data: bytes) -> list[tuple[int, int]]:
    text = data.decode("utf-8")
    offs = _byte_offsets(text)
    cuts: list[int] = [0]
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if ch == "\n":
            nxt = text.find("\n", i + 1)
            line = text[i + 1 : nxt if nxt != -1 else n]
            if not line.strip() or _BULLET.match(line) or (i > 0 and text[i - 1] == "\n"):
                cuts.append(i + 1)
        elif ch in ".!?;":
            at_end = i + 1 >= n or text[i + 1].isspace()
            if at_end:
                window = text[max(0, i - 7) : i + 1].lower()
                if not any(window.endswith(a) for a in _ABBREVIATIONS):
                    cuts.append(i + 1)
        i += 1
    cuts.append(n)
    out: list[tuple[int, int]] = []
    for a, b in zip(cuts, cuts[1:]):
        chunk = text[a:b]
        stripped = chunk.strip()
        if not stripped:
            continue
        lead = len(chunk) - len(chunk.lstrip())
        trail = len(chunk) - len(chunk.rstrip())
        out.append((offs[a + lead], offs[b - trail]))
    return out


def uncovered(data: bytes, spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Segments containing non-whitespace bytes not covered by any of the given spans."""
    covered = bytearray(len(data))
    for a, b in spans:
        a = max(0, a)
        b = min(len(data), b)
        for k in range(a, b):
            covered[k] = 1
    out = []
    for a, b in segments(data):
        for k in range(a, b):
            if not covered[k] and not chr(data[k]).isspace():
                out.append((a, b))
                break
    return out
