"""Candidate generic source inventory and explicit compact message selection.

No carrier contents are read here. Registration/source identity checks are not
qualification. Installation and the descriptor are supplied by root later.
"""
from pathlib import Path, PurePosixPath
import hashlib
import importlib.util
import json
import os
import re

FORMAT = "verislop.carrier-runtime-registration/1"
REGISTRATION_PATH = "synthetic_dataset/tools/carrier_runtime020-registration.json"
INTEGRATION_PATH = "synthetic_dataset/tools/bootstrap_tier2_runtime_integration.py"
REVISION = "support020-compact-runtime/1"
ROLES = {"generator", "reader", "runtime"}
CODE_KEYS = {"runtime_path", "runtime_sha256", "reader_path", "reader_sha256",
             "node_path", "python_path", "session_directory"}


def need(ok, code):
    if not ok:
        raise ValueError(code)


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def unique(items):
    result = {}
    for key, value in items:
        need(key not in result, "RUNTIME_REGISTRATION_DUPLICATE_KEY")
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=unique,
                      parse_constant=lambda value: need(False, "RUNTIME_REGISTRATION_NONFINITE"))


def identity(value, *, relative):
    need(type(value) is dict and set(value) == {"path", "sha256"}, "RUNTIME_IDENTITY_NOT_CLOSED")
    name, digest = value["path"], value["sha256"]
    need(type(name) is str and type(digest) is str and
         re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is not None, "RUNTIME_IDENTITY_INVALID")
    name.encode("utf-8", "strict")
    path = PurePosixPath(name)
    need(str(path) == name and ".." not in path.parts and "." not in path.parts and
         path.is_absolute() is (not relative), "RUNTIME_IDENTITY_PATH_INVALID")
    if relative:
        need(name.startswith("synthetic_dataset/tools/") and name != REGISTRATION_PATH and
             not name.endswith("/"), "RUNTIME_SOURCE_OUTSIDE_GENERIC_TRANSPORT")
    return value


def registration(value):
    need(type(value) is dict and set(value) == {"format", "api_revision", "source_files",
         "interpreters", "launcher", "session_policy"}, "RUNTIME_REGISTRATION_NOT_CLOSED")
    need(value["format"] == FORMAT and value["api_revision"] == REVISION,
         "RUNTIME_REGISTRATION_VERSION_UNSUPPORTED")
    sources = value["source_files"]
    need(type(sources) is dict and set(sources) == ROLES, "RUNTIME_SOURCE_ROLES_NOT_EXACT")
    for ref in sources.values():
        identity(ref, relative=True)
    need(len({ref["path"] for ref in sources.values()}) == len(ROLES), "RUNTIME_SOURCE_PATH_REUSED")
    need(PurePosixPath(sources["runtime"]["path"]).name == "carrier_runtime.js" and
         PurePosixPath(sources["reader"]["path"]).name == "reader.py" and
         PurePosixPath(sources["runtime"]["path"]).parent ==
         PurePosixPath(sources["reader"]["path"]).parent, "RUNTIME_STATIC_LAYOUT_MISMATCH")
    interpreters = value["interpreters"]
    need(type(interpreters) is dict and set(interpreters) == {"node", "python"},
         "RUNTIME_INTERPRETERS_NOT_CLOSED")
    for ref in interpreters.values():
        identity(ref, relative=False)
    need(interpreters["node"]["path"] == "/usr/bin/node" and
         interpreters["python"]["path"] == "/usr/bin/python3.12", "RUNTIME_INTERPRETER_PATH_UNSUPPORTED")
    launcher = value["launcher"]
    need(type(launcher) is dict and set(launcher) == {"kind", "name", "sha256"} and
         launcher["kind"] == "generator_literal" and launcher["name"] == "LAUNCHER_SOURCE" and
         type(launcher["sha256"]) is str and
         re.fullmatch(r"sha256:[0-9a-f]{64}", launcher["sha256"]) is not None,
         "RUNTIME_LAUNCHER_NOT_REGISTERED")
    need(value["session_policy"] == "own-carrier-parent/runtime020-own-sessions",
         "RUNTIME_SESSION_POLICY_UNSUPPORTED")
    return value


def regular(path):
    need(path.is_absolute() and path.resolve() == path and path.is_file() and not path.is_symlink(),
         "RUNTIME_SOURCE_NOT_REGULAR:" + str(path))
    return path.read_bytes()


def load_registration(repo):
    return registration(decode(regular(Path(repo).absolute() / REGISTRATION_PATH)))


def delivery_registration(repo):
    path = Path(repo).absolute() / REGISTRATION_PATH
    if not path.exists() and not path.is_symlink():
        return None
    value = load_registration(repo)
    return {"path": REGISTRATION_PATH, "sha256": sha(regular(path)), "api_revision": value["api_revision"]}


def verify_interpreters(descriptor):
    for ref in descriptor["interpreters"].values():
        path = Path(ref["path"])
        need(path.is_file() and sha(path.read_bytes()) == ref["sha256"],
             "REGISTERED_RUNTIME_INTERPRETER_HASH_MISMATCH")


def source_inventory(repo):
    """Exact registered JS/reader/generator/embedded-launcher inclusion."""
    repo = Path(repo).absolute()
    if delivery_registration(repo) is None:
        return {}
    descriptor = load_registration(repo)
    verify_interpreters(descriptor)
    result = {}
    for name in (REGISTRATION_PATH, INTEGRATION_PATH):
        result[name] = sha(regular(repo / name))
    for ref in descriptor["source_files"].values():
        raw = regular(repo / ref["path"])
        need(sha(raw) == ref["sha256"], "REGISTERED_RUNTIME_SOURCE_HASH_MISMATCH")
        result[ref["path"]] = ref["sha256"]
    return result


def code_bindings(repo, descriptor, session_directory):
    """Bind actual deployed code; never query a model or read the carrier."""
    repo = Path(repo).absolute()
    registration(descriptor)
    verify_interpreters(descriptor)
    session = Path(session_directory)
    need(type(session_directory) is str and session.is_absolute() and str(session) == session_directory
         and session.resolve() == session and session.is_dir(), "RUNTIME_SESSION_DIRECTORY_NOT_REGISTERED")
    result = {"session_directory": session_directory}
    for role in ("runtime", "reader", "generator"):
        ref = descriptor["source_files"][role]
        need(sha(regular(repo / ref["path"])) == ref["sha256"], "REGISTERED_RUNTIME_SOURCE_HASH_MISMATCH")
        if role != "generator":
            result[role + "_path"] = str(repo / ref["path"])
            result[role + "_sha256"] = ref["sha256"]
    for role in ("node", "python"):
        ref = descriptor["interpreters"][role]
        result[role + "_path"] = ref["path"]
    return result


def compact_message(repo, descriptor, reference, session_directory):
    """Trusted producer selection; independent reconstruction imports no producer."""
    code = code_bindings(repo, descriptor, session_directory)
    ref = descriptor["source_files"]["generator"]
    path = Path(repo).absolute() / ref["path"]
    spec = importlib.util.spec_from_file_location("registered_runtime020_generator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    need(module.API_REVISION == descriptor["api_revision"] and
         sha(module.LAUNCHER_SOURCE.encode("utf-8", "strict")) == descriptor["launcher"]["sha256"],
         "REGISTERED_RUNTIME_GENERATOR_INTERFACE_MISMATCH")
    message = module.runtime_agent_message(reference, code)
    need(type(message) is str, "RUNTIME_MESSAGE_NOT_STRING")
    return message


def native_message(repo, reference, *, create):
    descriptor = load_registration(repo)
    carrier_path = Path(reference["path"])
    need(carrier_path.is_absolute() and carrier_path.parent.resolve() == carrier_path.parent,
         "RUNTIME_OWN_CARRIER_PARENT_INDIRECT")
    session = carrier_path.parent / "runtime020-own-sessions"
    if not session.exists():
        need(create, "RUNTIME_OWN_SESSION_DIRECTORY_MISSING")
        session.mkdir(mode=0o700)
    need(not session.is_symlink() and session.resolve() == session and session.is_dir(),
         "RUNTIME_OWN_SESSION_DIRECTORY_INDIRECT")
    message = compact_message(repo, descriptor, reference, str(session))
    metadata = {"format": "verislop.compact-carrier-message-binding/1",
                "api_revision": descriptor["api_revision"],
                "registration_path": REGISTRATION_PATH,
                "registration_sha256": sha(regular(Path(repo).absolute() / REGISTRATION_PATH)),
                "runtime_source_files": descriptor["source_files"],
                "interpreters": descriptor["interpreters"], "session_directory": str(session),
                "message_sha256": sha(message.encode("utf-8", "strict"))}
    return message, metadata
