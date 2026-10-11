from pathlib import Path
import ast
import hashlib
import json
import os
import shlex

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def wire(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

def put(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

descriptor_path = ROOT / "synthetic_dataset/tools/carrier_runtime020-registration.json"
descriptor = json.loads(descriptor_path.read_bytes())
guards = {str(descriptor_path.relative_to(ROOT)): digest(descriptor_path.read_bytes())}
for role, entry in descriptor["source_files"].items():
    path = ROOT / entry["path"]
    if digest(path.read_bytes()) != entry["sha256"]:
        raise ValueError("CURRENT_REGISTERED_SOURCE_MISMATCH: " + role)
    guards[entry["path"]] = entry["sha256"]
for role, entry in descriptor["interpreters"].items():
    path = Path(entry["path"])
    if digest(path.read_bytes()) != entry["sha256"]:
        raise ValueError("CURRENT_REGISTERED_BINARY_MISMATCH: " + role)
    guards[entry["path"]] = entry["sha256"]
generator = ROOT / descriptor["source_files"]["generator"]["path"]
tree = ast.parse(generator.read_bytes())
constants = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
             if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)}
launcher = constants[descriptor["launcher"]["name"]]
if digest(launcher.encode("utf-8")) != descriptor["launcher"]["sha256"]:
    raise ValueError("CURRENT_LAUNCHER_LITERAL_MISMATCH")
request = {"purpose": "unrelated public checkpoint interface reproduction", "revision": 1}
request_raw = wire(request).encode("utf-8")
(HERE / "public-request.json").write_bytes(request_raw)
user = "0123456789abcdef" * 64 + " é🙂é\u2028\0\t\r\n apostrophe' end"
carrier = {"format": "verislop.collaboration-carrier/0.1", "request_id": "public-runtime021-checkpoint-001",
           "request_sha256": digest(request_raw), "system": "", "user": user}
carrier_raw = wire(carrier).encode("utf-8")
(HERE / "public-carrier.json").write_bytes(carrier_raw)
reference = {"path": str(HERE / "public-carrier.json"), "sha256": digest(carrier_raw), "request_sha256": carrier["request_sha256"]}
session_directory = HERE / "runtime020-own-sessions"
session_directory.mkdir(exist_ok=False)
code = {"runtime_path": str(ROOT / descriptor["source_files"]["runtime"]["path"]),
        "runtime_sha256": descriptor["source_files"]["runtime"]["sha256"],
        "reader_path": str(ROOT / descriptor["source_files"]["reader"]["path"]),
        "reader_sha256": descriptor["source_files"]["reader"]["sha256"],
        "node_path": descriptor["interpreters"]["node"]["path"],
        "python_path": descriptor["interpreters"]["python"]["path"], "session_directory": str(session_directory)}
session_path = str(session_directory / ("verislop-runtime020-" + hashlib.sha256(wire(reference).encode("utf-8")).hexdigest() + ".json"))
binding = {"reference": reference, "code": code, "session_path": session_path,
           "request_format": constants["REQUEST_FORMAT"], "launcher_prefix": shlex.quote(constants["PYTHON_PATH"]) + " -I -B -c " + shlex.quote(launcher) + " ",
           "native_runtime_pid": "UNAVAILABLE_FROM_EXEC_COMMAND", "native_reader_pid": "UNAVAILABLE_FROM_EXEC_COMMAND", "separate_stderr": "UNAVAILABLE_FROM_EXEC_COMMAND_COMBINED_OUTPUT"}
put("OWN_REFERENCE_AND_CODE.json", binding)
put("PUBLIC_FIXTURE_LITERAL_DEFINITION.json", {"system": "", "user": user, "field_chars": {"/system": 0, "/user": len(user)}, "field_utf8_bytes": {"/system": 0, "/user": len(user.encode("utf-8"))}, "qualification_authority": False})
for name in ("SPECIFICATION_BEFORE_FIXTURE_AND_EXECUTION.json", "prepare_public_fixture_and_registration.py", "observe_own_guards_and_state.py", "record_actual_result.py", "public-request.json", "public-carrier.json", "OWN_REFERENCE_AND_CODE.json", "PUBLIC_FIXTURE_LITERAL_DEFINITION.json"):
    path = HERE / name
    guards[str(path.relative_to(ROOT))] = digest(path.read_bytes())
spec = json.loads((HERE / "SPECIFICATION_BEFORE_FIXTURE_AND_EXECUTION.json").read_bytes())
put("CONTROL_REGISTRATION_BEFORE_EXECUTION.json", {"format": "verislop.bounded-generic-control-registration/1", "actual_preparation_pid": os.getpid(), "interpreter": "/usr/bin/python3.12", "guards": guards, "sequence": spec["registered_sequence"], "authority": "NO_QUALIFICATION_AUTHORITY", "outer_ack": "Only after actual integer-zero intact exposed result; actual nested chunk_id copied without synthesis"})
print(json.dumps({"actual_preparation_pid": os.getpid(), "guard_count": len(guards), "binding": binding}, ensure_ascii=False), flush=True)
