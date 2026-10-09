"""Strict JSON parsing and RFC 8785 (JCS) canonical serialisation.

Rules (specification §7.2):
* duplicate keys, non-finite numbers, binary floating point values, integers outside the
  I-JSON safe range and invalid Unicode (lone surrogates) are rejected;
* large integers and rationals must be carried as decimal strings by the producing schema;
* canonical bytes sort object members by UTF-16 code units and use minimal escaping.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

MAX_SAFE_INT = 2**53 - 1


class CanonicalJSONError(ValueError):
    """Raised when input is not acceptable strict JSON."""


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise CanonicalJSONError(f"duplicate object key: {key!r}")
        out[key] = value
    return out


def _reject_constant(name: str) -> Any:
    raise CanonicalJSONError(f"non-finite number {name} is not permitted")


def _reject_float(text: str) -> Any:
    raise CanonicalJSONError(
        f"binary floating-point number {text} is not permitted; use a decimal string"
    )


def _check_int(text: str) -> int:
    value = int(text)
    if abs(value) > MAX_SAFE_INT:
        raise CanonicalJSONError(
            f"integer {text} exceeds the I-JSON safe range; use a decimal string"
        )
    return value


def _check_strings(obj: Any, path: str = "$") -> None:
    if isinstance(obj, str):
        _check_text(obj, path)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            _check_text(key, path)
            _check_strings(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            _check_strings(value, f"{path}[{i}]")


def _check_text(text: str, path: str) -> None:
    for ch in text:
        if 0xD800 <= ord(ch) <= 0xDFFF:
            raise CanonicalJSONError(f"invalid Unicode (lone surrogate) at {path}")


def loads(data: bytes | str) -> Any:
    """Parse strict JSON. Bytes must be valid UTF-8 (a BOM is rejected)."""
    if isinstance(data, bytes):
        if data.startswith(b"\xef\xbb\xbf"):
            raise CanonicalJSONError("UTF-8 byte order mark is not permitted")
        try:
            text = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise CanonicalJSONError(f"invalid UTF-8: {exc}") from None
    else:
        text = data
    try:
        obj = json.loads(
            text,
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
            parse_int=_check_int,
        )
    except json.JSONDecodeError as exc:
        raise CanonicalJSONError(f"invalid JSON: {exc}") from None
    _check_strings(obj)
    return obj


def load_file(path: str | Any) -> Any:
    with open(path, "rb") as fh:
        return loads(fh.read())


_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def _encode_string(text: str) -> str:
    out = ['"']
    for ch in text:
        if ch in _ESCAPES:
            out.append(_ESCAPES[ch])
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _utf16_key(key: str) -> list[int]:
    return list(key.encode("utf-16-be"))


def _encode(obj: Any, out: list[str]) -> None:
    if obj is None:
        out.append("null")
    elif obj is True:
        out.append("true")
    elif obj is False:
        out.append("false")
    elif isinstance(obj, int):
        if abs(obj) > MAX_SAFE_INT:
            raise CanonicalJSONError(f"integer {obj} exceeds the I-JSON safe range")
        out.append(str(obj))
    elif isinstance(obj, float):
        raise CanonicalJSONError("binary floating-point values are not canonicalisable here")
    elif isinstance(obj, str):
        _check_text(obj, "$")
        out.append(_encode_string(obj))
    elif isinstance(obj, (list, tuple)):
        out.append("[")
        for i, item in enumerate(obj):
            if i:
                out.append(",")
            _encode(item, out)
        out.append("]")
    elif isinstance(obj, dict):
        for key in obj:
            if not isinstance(key, str):
                raise CanonicalJSONError("object keys must be strings")
        out.append("{")
        for i, key in enumerate(sorted(obj, key=_utf16_key)):
            if i:
                out.append(",")
            out.append(_encode_string(key))
            out.append(":")
            _encode(obj[key], out)
        out.append("}")
    else:
        raise CanonicalJSONError(f"unsupported JSON value of type {type(obj).__name__}")


def dumps(obj: Any) -> bytes:
    """RFC 8785 canonical bytes."""
    out: list[str] = []
    _encode(obj, out)
    return "".join(out).encode("utf-8")


def dumps_pretty(obj: Any) -> bytes:
    """Deterministic human-readable JSON (sorted keys, two-space indent, trailing newline).

    Used for human-reviewed artifacts. Hashes are always computed over the exact bytes written.
    """
    _encode(obj, [])  # validate with the same rules
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(data: bytes) -> str:
    return "sha256:" + sha256_hex(data)


def digest_json(obj: Any) -> str:
    return digest(dumps(obj))


def digest_file(path: str | Any) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()
