"""Shared strict artifact binding for a future support019 run; no target execution."""
from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path


class Block(ValueError):
    pass


def need(predicate, reason):
    if not predicate:
        raise Block(reason)


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def map_digest(files):
    """JCS for the actual source/input schema: scalar-string -> digest-string.

    UTF16 member order matches the existing canonical producer; there are no
    numeric/float objects in these map-root calculations.
    """
    need(isinstance(files, dict) and all(isinstance(k, str) and isinstance(v, str)
         for k, v in files.items()), "ROOT_MAP_SCHEMA_MISMATCH")
    ordered = {key: files[key] for key in sorted(files, key=lambda s: s.encode("utf-16-be", "strict"))}
    return digest(json.dumps(ordered, ensure_ascii=False, separators=(",", ":"),
                             allow_nan=False).encode("utf-8", "strict"))


def source_names(root, registration):
    names = set(registration["transport_files"])
    for directory, suffixes in registration["directory_suffixes"].items():
        names.update(p.relative_to(root).as_posix() for p in (root / directory).rglob("*")
                     if p.suffix in suffixes)
    names.update(name for name in registration["optional_root_files"] if (root / name).exists())
    need(registration["required_source_file"] in names, "SOURCE_SPECIFICATION_MISSING")
    return names


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "DUPLICATE_JSON_KEY:" + key)
        result[key] = value
    return result


def parse(raw):
    need(not raw.startswith(b"\xef\xbb\xbf"), "UNSUPPORTED_JSON_BOM")
    value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=unique,
                       parse_constant=lambda value: (_ for _ in ()).throw(Block("NONFINITE_JSON")))
    return value


def load(path):
    need(path.is_file() and not path.is_symlink() and path.resolve() == path.absolute(),
         "MISSING_OR_INDIRECT_JSON:" + str(path))
    return parse(path.read_bytes())


def regular(root, value):
    need(isinstance(value, str), "PATH_NOT_TEXT")
    path = Path(value)
    need(not path.is_absolute() and ".." not in path.parts and path.as_posix() == value,
         "NONCANONICAL_RELATIVE_PATH:" + value)
    path = root / path
    need(path.is_file() and not path.is_symlink() and path.resolve() == path.absolute(),
         "MISSING_OR_INDIRECT_INPUT:" + value)
    return path


def ref(root, record):
    path = regular(root, record["path"])
    raw = path.read_bytes()
    need(digest(raw) == record["sha256"], "HASH_MISMATCH:" + record["path"])
    need(type(record["byte_count"]) is int and record["byte_count"] == len(raw),
         "SIZE_MISMATCH:" + record["path"])
    return raw


def timestamp(value):
    need(isinstance(value, str), "TIMESTAMP_NOT_TEXT")
    result = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    need(result.utcoffset() == datetime.timedelta(0), "TIMESTAMP_NOT_UTC")
    return result


def file_map(root, names):
    need(names and len(names) == len(set(names)), "EMPTY_OR_DUPLICATE_FILE_INVENTORY")
    return {name: digest(regular(root, name).read_bytes()) for name in sorted(names)}


def verify_map(root, files):
    need(isinstance(files, dict) and files, "EMPTY_FILE_MAP")
    need(file_map(root, list(files)) == files, "INPUT_MUTATION")


def write_once(path, value):
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                      allow_nan=False) + "\n").encode("utf-8", "strict")
    with path.open("xb") as stream:
        stream.write(raw)
    return {"sha256": digest(raw), "byte_count": len(raw)}


def process_receipt(root, registered, receipt, source_root, input_root, frozen_at):
    """Validate direct subprocess receipt fields from the actual existing producer."""
    need(receipt["format"] in ("verislop.support018-actual-process-receipt/1",
                               "verislop.support019-actual-process-receipt/1"), "PROCESS_SCHEMA")
    need(receipt["id"] == registered["id"] and receipt["argv"] == registered["argv"] and
         receipt["registered_environment"] == registered.get("environment", {}) and
         receipt["cwd"] == str(root), "UNREGISTERED_PROCESS")
    need(type(receipt["pid"]) is int and receipt["pid"] > 0, "DIRECT_PROCESS_PID_MISSING")
    need(type(receipt["returncode"]) is int and receipt["returncode"] == registered["accepted_exit_code"]
         and receipt["timed_out"] is False, "PROCESS_NOT_SUCCESSFUL")
    need(receipt["source_root"] == source_root and receipt["input_root"] == input_root,
         "STALE_OR_UNBOUND_PROCESS")
    need(timestamp(frozen_at) <= timestamp(receipt["started_utc"]) <= timestamp(receipt["completed_utc"]),
         "PROCESS_STARTED_BEFORE_FREEZE")
    for stream in ("stdout", "stderr"):
        ref(root, receipt[stream])
    # Existing phase receipts have no report binding. A new authenticated output
    # sidecar is required; do not invent fields on the original schema.
    return receipt
