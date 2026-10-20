"""Independent finite G04 request oracle. Never import from generation/review code."""
from __future__ import annotations

from copy import deepcopy

TASK = "G04-release-manifest"
VERSION = "g04-independent-semantics/1"
REQUEST_SHA256 = "sha256:128aeea6d95a4df6fc679c5101e58e5178033d3e82da9eb978be48f57e4e6298"


def scalar_length(text: str) -> int:
    if type(text) is not str:
        raise ValueError("expected a Unicode scalar string")
    count = 0
    for char in text:
        if 0xD800 <= ord(char) <= 0xDFFF:
            raise ValueError("surrogates are not Unicode scalar values")
        count += 1
    return count


def expected(data: dict) -> dict:
    """Direct imperative reading of the request, independent of candidate/Lean ASTs."""
    if type(data) is not dict or set(data) != {"prefix", "assets"}:
        raise ValueError("expected exactly prefix and assets")
    scalar_length(data["prefix"])
    if type(data["assets"]) is not list:
        raise ValueError("assets must be a list")
    items, total = [], 0
    for asset in data["assets"]:
        if type(asset) is not dict or set(asset) != {"path", "bytes", "enabled"}:
            raise ValueError("expected exactly path, bytes and enabled")
        length = scalar_length(asset["path"])
        if type(asset["bytes"]) is not int or asset["bytes"] < 0 or type(asset["enabled"]) is not bool:
            raise ValueError("bytes must be a mathematical Nat and enabled a Bool")
        if asset["enabled"] and length:
            destination = data["prefix"] + asset["path"]
            items.append({"destination": destination, "bytes": asset["bytes"],
                          "destination_length": scalar_length(destination)})
            total += asset["bytes"]
    return {"items": items, "total_bytes": total, "item_count": len(items)}


def cases() -> list[dict]:
    """Fixed named cases, no RNG, timestamps, model calls or generated answers."""
    def a(path, size=3, enabled=True):
        return {"path": path, "bytes": size, "enabled": enabled}
    rows = [
        ("scalar-nul-duplicates", "\U0001f511\0", [a("e\u0301"), a("e\u0301"), a("", 99), a("skip", 8, False)]),
        ("empty-input", "", []),
        ("prefix-with-no-assets", "\0\U0010ffff", []),
        ("all-filtered", "prefix/", [a("", 999), a("x", 999, False), a("", 999, False)]),
        ("order-and-duplicates", "pkg/", [a("z", 2), a("a", 5), a("z", 2), a("m", 0)]),
        ("nul-is-not-empty", "", [a("\0"), a(""), a("\0x\0", 7)]),
        ("exact-concatenation", "p", [a("x"), a("/x"), a("../x"), a(" "), a("\t\n")]),
        ("no-normalization", "e", [a("\u0301"), a("é"), a("e\u0301"), a("\u0301\u0308")]),
        ("no-case-or-trim", " A ", [a(" X "), a("x"), a("ß"), a("\r\n")]),
        ("scalar-boundaries", "\ud7ff", [a("\ue000"), a("\uffff"), a("\U00010000"), a("\U0010ffff")]),
        ("supplementary-and-zwj", "\U0001f511", [a("\U0001f600"), a("👩\u200d💻"), a("🇨🇳")]),
        ("exact-big-nats", "", [a("a", 2**53+1), a("b", 2**64-1), a("c", 2**128+7),
                                     a("c", 2**128+7), a("d", 10**100), a("", 10**101), a("skip", 10**102, False)]),
        ("enabled-zero-bytes", "", [a("x", 0), a("x", 0), a("off", 0, False)]),
    ]
    # Small exhaustive cross product exercises each filter with varied prefixes.
    for pi, prefix in enumerate(("", "p/", "\0", "\U0001f511", "e\u0301")):
        rows.append((f"filter-cross-product-{pi}", prefix,
                     [a(path, i, enabled) for i, path in enumerate(("", "x", "\0", "e\u0301", "\U0010ffff"))
                      for enabled in (False, True)]))
    return [{"case_id": name, "input": {"prefix": prefix, "assets": deepcopy(assets)}}
            for name, prefix, assets in rows]


def wire(value):
    """JSON-safe transport: all arbitrary precision naturals are decimal strings."""
    if type(value) is bool:
        return {"bool": value}
    if type(value) is int and value >= 0:
        return {"nat": str(value)}
    if type(value) is str:
        scalar_length(value)
        return {"string": value}
    if type(value) is list:
        return {"list": [wire(v) for v in value]}
    if type(value) is dict:
        return {"record": {k: wire(v) for k, v in value.items()}}
    raise ValueError("outside the G04 transport domain")


def suite() -> list[dict]:
    return [{"case_id": row["case_id"], "input": wire(row["input"]),
             "expected": wire(expected(row["input"]))} for row in cases()]
