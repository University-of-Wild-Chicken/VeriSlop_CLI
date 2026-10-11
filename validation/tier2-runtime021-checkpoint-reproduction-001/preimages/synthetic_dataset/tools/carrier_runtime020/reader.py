import hashlib
import json
import os
import stat
import sys

VIEW_FORMAT = "verislop.exact-carrier-view/0.1"

class ViewError(ValueError):
    pass

def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")

def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ViewError("DUPLICATE_KEY")
        result[key] = value
    return result

def _forbidden_number(value):
    raise ViewError("UNSUPPORTED_NUMBER")

def _integer(value):
    number = int(value)
    if abs(number) > 2**53 - 1:
        raise ViewError("UNSUPPORTED_INTEGER")
    return number

def _failure(code, cap):
    record = {"format": VIEW_FORMAT, "status": "error", "code": code,
              "next_char": None, "field_eof": False}
    encoded = _json(record) + b"\n"
    return encoded if len(encoded) <= cap else b""

def carrier_view(reference, view):
    cap = view.get("output_cap_bytes", 8192) if isinstance(view, dict) else 0
    if type(cap) is not int or not 256 <= cap <= 8192:
        return b""
    try:
        reserve = view.get("metadata_reserve_bytes", 2048)
        if type(reserve) is not int or not 128 <= reserve < cap:
            raise ViewError("INVALID_BOUNDS")
        if set(view) - {"operation", "selector", "start_char", "output_cap_bytes", "metadata_reserve_bytes"}:
            raise ViewError("INVALID_VIEW_FIELDS")
        if not isinstance(reference, dict) or set(reference) != {"path", "sha256", "request_sha256"}:
            raise ViewError("INVALID_REFERENCE")
        if not all(isinstance(value, str) for value in reference.values()):
            raise ViewError("INVALID_REFERENCE")
        path = reference["path"]
        if not os.path.isabs(path) or os.path.realpath(path) != path:
            raise ViewError("INDIRECT_PATH")
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode):
            raise ViewError("NONREGULAR_PATH")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino) or not stat.S_ISREG(opened.st_mode):
                raise ViewError("INPUT_MUTATION")
            raw = stream.read()
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        if digest != reference["sha256"]:
            raise ViewError("CARRIER_HASH_MISMATCH")
        if raw.startswith(b"\xef\xbb\xbf"):
            raise ViewError("UNSUPPORTED_JSON")
        carrier = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_pairs,
                             parse_float=_forbidden_number, parse_constant=_forbidden_number,
                             parse_int=_integer)
        if not isinstance(carrier, dict) or set(carrier) != {"format", "request_id", "request_sha256", "system", "user"}:
            raise ViewError("INVALID_CARRIER")
        if not all(isinstance(value, str) for value in carrier.values()):
            raise ViewError("INVALID_CARRIER")
        for value in carrier.values():
            value.encode("utf-8", errors="strict")
        if carrier["format"] != "verislop.collaboration-carrier/0.1":
            raise ViewError("INVALID_CARRIER_FORMAT")
        if carrier["request_sha256"] != reference["request_sha256"]:
            raise ViewError("REQUEST_METADATA_MISMATCH")
        base = {"format": VIEW_FORMAT, "status": "ok", "carrier_path": path,
                "carrier_raw_bytes": len(raw), "carrier_sha256": digest,
                "request_sha256": carrier["request_sha256"], "request_id": carrier["request_id"],
                "char_unit": "decoded_unicode_code_points", "byte_unit": "decoded_field_utf8",
                "output_cap_bytes": cap, "metadata_reserve_bytes": reserve}
        operation = view.get("operation", "field")
        if operation == "inventory":
            record = {**base, "operation": "inventory", "fields": [
                {"selector": "/" + field, "field_chars": len(carrier[field]),
                 "field_utf8_bytes": len(carrier[field].encode("utf-8")),
                 "start_char": 0, "end_char": len(carrier[field])}
                for field in ("system", "user")], "navigation": "complete_linear_fields_only"}
            encoded = _json(record) + b"\n"
            if len(encoded) > reserve or len(encoded) > cap:
                raise ViewError("METADATA_RESERVE_EXCEEDED")
            return encoded
        if operation != "field":
            raise ViewError("INVALID_OPERATION")
        selector = view.get("selector", "/system")
        if selector not in ("/system", "/user"):
            raise ViewError("INVALID_SELECTOR")
        text = carrier[selector[1:]]
        start = view.get("start_char", 0)
        if type(start) is not int or not 0 <= start <= len(text):
            raise ViewError("INVALID_CURSOR")
        total_bytes = len(text.encode("utf-8"))
        start_bytes = len(text[:start].encode("utf-8"))

        def candidate(end):
            content = text[start:end]
            content_bytes = len(content.encode("utf-8"))
            record = {**base, "operation": "field", "selector": selector,
                      "field_chars": len(text), "field_utf8_bytes": total_bytes,
                      "start_char": start, "end_char": end,
                      "start_utf8_byte": start_bytes, "end_utf8_byte": start_bytes + content_bytes,
                      "content_chars": end - start, "content_utf8_bytes": content_bytes,
                      "content": content, "next_char": end, "field_eof": end == len(text)}
            encoded_content = _json(content)
            encoded = _json(record) + b"\n"
            metadata_bytes = len(encoded) - len(encoded_content) + 2
            return encoded, metadata_bytes, len(encoded_content)

        empty, metadata_bytes, content_bytes = candidate(start)
        if start == len(text):
            if metadata_bytes > reserve:
                raise ViewError("METADATA_RESERVE_EXCEEDED")
            if len(empty) > cap or content_bytes > cap - reserve:
                raise ViewError("NO_CONTENT_CAPACITY")
            return empty
        low, high = start, min(len(text), start + cap - reserve)
        # The final EOF header is one byte shorter than a non-final header.
        # Check this endpoint explicitly before monotone non-final selection.
        endpoint, endpoint_meta, endpoint_content = candidate(high)
        if endpoint_meta <= reserve and endpoint_content <= cap - reserve and len(endpoint) <= cap:
            return endpoint
        while low < high:
            middle = (low + high + 1) // 2
            encoded, meta_size, content_size = candidate(middle)
            if meta_size <= reserve and content_size <= cap - reserve and len(encoded) <= cap:
                low = middle
            else:
                high = middle - 1
        if low == start:
            if metadata_bytes > reserve:
                raise ViewError("METADATA_RESERVE_EXCEEDED")
            raise ViewError("NO_CONTENT_CAPACITY")
        return candidate(low)[0]
    except ViewError as exc:
        return _failure(str(exc), cap)
    except (UnicodeError, ValueError, TypeError, OverflowError, RecursionError):
        return _failure("UNSUPPORTED_JSON_OR_TEXT", cap)
    except OSError:
        return _failure("CARRIER_READ_ERROR", cap)

def emit_view(reference, view):
    encoded = carrier_view(reference, view)
    sys.stdout.buffer.write(encoded)
    return 0 if encoded and json.loads(encoded)["status"] == "ok" else 2


def runtime_reader_main():
    try:
        if len(sys.argv) != 2:
            raise ViewError("INVALID_READER_ARGUMENTS")
        payload = json.loads(sys.argv[1], object_pairs_hook=_pairs,
                             parse_float=_forbidden_number,
                             parse_constant=_forbidden_number, parse_int=_integer)
        if type(payload) is not dict or set(payload) != {"reference", "view", "reader_sha256"}:
            raise ViewError("INVALID_READER_ARGUMENTS")
        expected = payload["reader_sha256"]
        if (type(expected) is not str or len(expected) != 71 or not expected.startswith("sha256:")
                or any(char not in "0123456789abcdef" for char in expected[7:])):
            raise ViewError("INVALID_READER_SOURCE_IDENTITY")
        with open(__file__, "rb") as stream:
            actual = "sha256:" + hashlib.sha256(stream.read()).hexdigest()
        if actual != expected:
            raise ViewError("READER_SOURCE_IDENTITY_MISMATCH")
        view = payload["view"]
        required = {"operation", "output_cap_bytes", "metadata_reserve_bytes"}
        if type(view) is not dict:
            raise ViewError("INVALID_CLOSED_VIEW")
        if view.get("operation") == "field":
            required |= {"selector", "start_char"}
        elif view.get("operation") != "inventory":
            raise ViewError("INVALID_CLOSED_VIEW")
        if set(view) != required:
            raise ViewError("INVALID_CLOSED_VIEW")
        return emit_view(payload["reference"], view)
    except (ViewError, ValueError, TypeError, UnicodeError, OSError) as exc:
        code = str(exc) if isinstance(exc, ViewError) else "INVALID_READER_ARGUMENTS"
        sys.stdout.buffer.write(_failure(code, 8192))
        return 2


if __name__ == "__main__":
    raise SystemExit(runtime_reader_main())
