"""Independent finite support020 controls. Refuses execution without pinned registration.

Synthetic tool envelopes are explicit fixtures, never native tool attestation.
Actual OS process PIDs/status/stdout/stderr are separately retained. No deadlines.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import traceback


PYTHON = "/usr/bin/python3.12"
NODE = "/usr/bin/node"
CONTRACT_SHA = "sha256:4fb5a3aba15cab2f83878132110068080e45d1ea4434393ec43c2da79bb8dac0"
BASELINE_SHA = "sha256:f855de49fa8522cfc91053fe3f1f0db1ebd3c199260acbb97618d0f998c5eb4a"
IDS = ["S020-R" + str(i).zfill(2) for i in range(1, 20)]
REQUEST_FORMAT = "verislop.carrier-runtime-request/0.1"


def need(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def wire(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "DUPLICATE_CONTROL_JSON_KEY")
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs)


def identity(path):
    data = path.read_bytes()
    return {"path": str(path), "sha256": sha(data), "byte_count": len(data)}


def save(path, value):
    with path.open("xb") as stream:
        stream.write((json.dumps(value, sort_keys=True, indent=2,
                                 ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))


def literal_sources(raw):
    wanted = {"READER_SOURCE", "CHECKPOINT_VALIDATOR_SOURCE", "OWN_SHA256_SOURCE"}
    found = {}
    for node in ast.parse(raw.decode("utf-8", "strict")).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in wanted:
                    found[target.id] = ast.literal_eval(node.value)
    need(set(found) == wanted, "BASELINE_LITERAL_INVENTORY")
    return found


class Observer:
    def __init__(self, root):
        self.root = root
        self.root.mkdir()
        self.records = []

    def run(self, argv, *, stdin=None, shell=False):
        number = len(self.records) + 1
        start = time.monotonic()
        process = subprocess.Popen(argv, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   shell=shell, cwd=str(self.root), env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        stdout, stderr = process.communicate(stdin)
        status = process.returncode
        need(type(status) is int, "ACTUAL_OS_STATUS_NOT_INTEGER")
        prefix = self.root / ("process-" + str(number).zfill(5))
        out = prefix.with_suffix(".stdout"); err = prefix.with_suffix(".stderr")
        out.write_bytes(stdout); err.write_bytes(stderr)
        record = {"format": "verislop.runtime020-actual-generic-process/1",
                  "argv_or_shell_command": argv, "shell": shell,
                  "observed_process_PID": process.pid, "exit_code": status,
                  "elapsed_seconds": time.monotonic() - start,
                  "stdout_ref": identity(out), "stderr_ref": identity(err),
                  "model_or_tool_identity": "UNATTESTED",
                  "native_tool_envelope": "NOT_OBSERVED",
                  "nested_PID": "UNAVAILABLE_UNLESS_EXPOSED_BY_TEMPLATE_PROBE"}
        recpath = prefix.with_suffix(".json"); save(recpath, record)
        self.records.append(identity(recpath))
        return {"exit_code": status, "stdout": stdout, "stderr": stderr,
                "observed_process_PID": process.pid, "record_ref": identity(recpath)}


class Fixture:
    def __init__(self, suite, tag, system="generic system", user="Aé🧪e\u0301\n\t\x00", *, odd_path=False):
        self.suite = suite
        basename = tag + (" quote' dollar$ backtick` semicolon;\n🧪" if odd_path else "")
        self.directory = suite.root / basename
        self.directory.mkdir()
        self.session_directory = self.directory / "own-session"
        self.session_directory.mkdir()
        self.system = system; self.user = user
        self.carrier = self.directory / "own-carrier.json"
        request_hash = sha(wire({"system": system, "user": user, "request_id": tag}).encode("utf-8"))
        self.doc = {"format": "verislop.collaboration-carrier/0.1", "request_id": tag,
                    "request_sha256": request_hash, "system": system, "user": user}
        self.carrier.write_bytes((wire(self.doc) + "\n").encode("utf-8"))
        self.reference = {"path": str(self.carrier), "sha256": sha(self.carrier.read_bytes()),
                          "request_sha256": request_hash}
        self.code = suite.api.code_bindings(str(self.session_directory))
        self.state_path = Path(suite.api.session_path(self.reference, self.code))

    def request(self, operation, **extra):
        return {"format": REQUEST_FORMAT, "operation": operation,
                "reference": self.reference, "code": self.code,
                "session_path": str(self.state_path), **extra}

    def accepted(self):
        return self.state_path.read_bytes() if self.state_path.exists() else None

    def invoke(self, request, *, raw=None, launcher=False):
        self.suite.guard()
        if launcher:
            return self.suite.observer.run(self.suite.api.runtime_command(request), shell=True)
        text = wire(request) if raw is None else raw
        return self.suite.observer.run([NODE, self.code["runtime_path"], text])

    def view(self, selector=None, start=0, cap=8192, reserve=2048):
        view = {"operation": "inventory", "output_cap_bytes": cap, "metadata_reserve_bytes": reserve}
        if selector is not None:
            view.update(operation="field", selector=selector, start_char=start)
        before = self.accepted()
        actual = self.invoke(self.request("view", view=view))
        need(actual["exit_code"] == 0 and not actual["stderr"], "GENERIC_VIEW_FAILED")
        need(self.accepted() == before, "VIEW_ADVANCED_ACCEPTED_STATE")
        # This deliberately synthetic envelope is not a native exec_command result.
        pending = {"reference": self.reference, "view": view,
                   "result": {"chunk_id": "SYNTHETIC_CONTROL_CHUNK_" + str(len(self.suite.observer.records)),
                              "exit_code": actual["exit_code"], "output": actual["stdout"].decode("utf-8", "strict")}}
        self.suite.synthetic_pending_count += 1
        return pending

    def confirm(self, pending, confirmation=None, *, reject=False):
        if confirmation is None:
            confirmation = {"chunk_id": pending["result"]["chunk_id"], "outer_output_intact": True}
        before = self.accepted()
        actual = self.invoke(self.request("confirm", pending=pending, confirmation=confirmation))
        if reject:
            need(actual["exit_code"] != 0, "REJECTED_CONFIRM_SUCCEEDED")
            need(self.accepted() == before, "REJECTED_CONFIRM_MUTATED_ACCEPTED_STATE")
        else:
            need(actual["exit_code"] == 0 and not actual["stderr"], "CONFIRM_FAILED")
        return actual

    def inventory(self):
        pending = self.view(); self.confirm(pending); return pending

    def finish(self, *, cap=8192, reserve=2048):
        if self.accepted() is None:
            self.inventory()
        # Fixed generic test-driver sequence; never supplied to an author or runtime recipe.
        for selector in ("/system", "/user"):
            while not parse(self.accepted())["fields"][selector]["field_eof"]:
                start = parse(self.accepted())["fields"][selector]["next_char"]
                pending = self.view(selector, start, cap, reserve)
                self.confirm(pending)
        return parse(self.accepted())

    def hash(self, *, reject=False):
        before = self.accepted()
        actual = self.invoke(self.request("hash"))
        need(self.accepted() == before, "HASH_MUTATED_CHECKPOINT")
        need((actual["exit_code"] != 0) if reject else actual["exit_code"] == 0,
             "HASH_COMPLETION_MISMATCH")
        return actual


def changed_output(pending, mutate):
    value = copy.deepcopy(pending)
    doc = parse(value["result"]["output"].encode("utf-8"))
    mutate(doc)
    value["result"]["output"] = wire(doc) + "\n"
    return value


class Suite:
    def __init__(self, root, registration, api, sources, observed_hashes):
        self.root = root; self.root.mkdir()
        self.api = api; self.sources = sources; self.observed_hashes = observed_hashes
        self.registration = registration
        self.observer = Observer(root / "actual-processes")
        self.synthetic_pending_count = 0

    def guard(self):
        for filename, expected in self.observed_hashes.items():
            need(sha(Path(filename).read_bytes()) == expected, "REGISTERED_SOURCE_CHANGED:" + filename)

    def fixture(self, tag, **kwargs):
        return Fixture(self, tag, **kwargs)

    def rejected_request(self, fixture, request, *, raw=None):
        before = fixture.accepted()
        actual = fixture.invoke(request, raw=raw)
        need(actual["exit_code"] != 0 and fixture.accepted() == before, "INVALID_REQUEST_ACCEPTED_OR_MUTATED_STATE")
        return parse(actual["stdout"])["code"] if actual["stdout"] else "NO_STDOUT"

    def template(self, fixture, recipe, memory=None):
        """Execute literal template as a standalone module with a declared transport fixture.

        No eval/Function or callable serialization. The shim invokes a real shell child;
        its native-like tool return fields/chunk identity are explicitly synthetic.
        """
        self.guard()
        shim = """import childProcess from 'node:child_process';
const MEMORY = new Map(Object.entries(MEMORY_LITERAL));
const CALLS = []; let FORWARDED;
const tools = {exec_command: async args => {
  const started = process.hrtime.bigint();
  const result = childProcess.spawnSync('/bin/sh', ['-c', args.cmd], {encoding:'utf8', maxBuffer:32768});
  if(result.error) throw result.error;
  const returned = {chunk_id:'SYNTHETIC_TEMPLATE_CHUNK', exit_code:result.status,
    output:result.stdout, wall_time_seconds:Number(process.hrtime.bigint()-started)/1e9};
  CALLS.push({args, returned, actual_child_PID:result.pid, actual_child_signal:result.signal, actual_child_stderr:result.stderr});
  return returned;
}};
function store(key,value) { MEMORY.set(key,value); }
function load(key) { return MEMORY.get(key); }
function text(value) { FORWARDED=value; }
""".replace("MEMORY_LITERAL", wire(memory or {}))
        tail = "\nconsole.log(JSON.stringify({fixture_kind:'SYNTHETIC_TOOL_TRANSPORT_WITH_ACTUAL_OS_CHILD',calls:CALLS,forwarded:FORWARDED,memory:Object.fromEntries(MEMORY)}));\n"
        actual = self.observer.run([NODE, "--input-type=module", "-"], stdin=(shim + recipe + tail).encode("utf-8"))
        need(actual["exit_code"] == 0 and not actual["stderr"], "LITERAL_TEMPLATE_EXECUTION_FAILED")
        value = parse(actual["stdout"])
        need(value["fixture_kind"] == "SYNTHETIC_TOOL_TRANSPORT_WITH_ACTUAL_OS_CHILD"
             and len(value["calls"]) == 1 and value["forwarded"] == value["calls"][0]["returned"],
             "TEMPLATE_DID_NOT_FORWARD_ONE_COMPLETE_RESULT")
        call = value["calls"][0]
        need(type(call["returned"]["exit_code"]) is int and type(call["actual_child_PID"]) is int,
             "TEMPLATE_CHILD_STATUS_OR_PID_UNAVAILABLE")
        self.synthetic_pending_count += 1
        return value

    def r01(self):
        baseline = Path(self.registration["baseline_ref"]["path"]).read_bytes()
        need(sha(baseline) == BASELINE_SHA, "BASELINE_SOURCE_CHANGED")
        literals = literal_sources(baseline)
        candidate = Path(self.registration["candidate_directory"])
        need((candidate / "legacy006.py").read_bytes() == baseline, "LEGACY_MODULE_CHANGED")
        need((candidate / "reader.py").read_bytes().startswith(literals["READER_SOURCE"].encode("utf-8")), "READER_SOURCE_CHANGED")
        runtime = (candidate / "carrier_runtime.js").read_bytes()
        for name in ("CHECKPOINT_VALIDATOR_SOURCE", "OWN_SHA256_SOURCE"):
            need(runtime.count(literals[name].encode("utf-8")) == 1, "FIXED_SOURCE_CHANGED_OR_DUPLICATED:" + name)
        # One static subprocess site, inside explicit view branch; no Node eval/Function.
        tail = runtime.split(literals["OWN_SHA256_SOURCE"].encode("utf-8"), 1)[1]
        need(tail.count(b"childProcess.spawnSync(") == 1 and b"eval(" not in tail and b"new Function" not in tail,
             "RUNTIME_OPEN_EXECUTION_OR_MULTIPLE_READER_SITES")
        return {name: sha(value.encode("utf-8")) for name, value in literals.items()}

    def r02(self):
        fixture = self.fixture("r02")
        copydir = fixture.directory / "changed-copy"; copydir.mkdir()
        runtime = copydir / "carrier_runtime.js"
        reader = copydir / "reader.py"
        shutil.copyfile(fixture.code["runtime_path"], runtime)
        shutil.copyfile(fixture.code["reader_path"], reader)
        runtime.write_bytes(runtime.read_bytes() + b"\n// Generic one-byte identity failure.\n")
        request = fixture.request("view", view={"operation":"inventory", "output_cap_bytes":8192, "metadata_reserve_bytes":2048})
        request = copy.deepcopy(request); request["code"]["runtime_path"] = str(runtime); request["code"]["reader_path"] = str(reader)
        result = fixture.invoke(request, launcher=True)
        need(result["exit_code"] != 0 and b"REGISTERED_CODE_HASH_MISMATCH" in result["stderr"]
             and fixture.accepted() is None, "CHANGED_TARGET_EXECUTED_WITH_UNCHANGED_PINS")
        foreign = fixture.directory / "unrelated-runtime.js"
        foreign.write_text('process.stdout.write("UNRELATED_CODE_MUST_NOT_RUN");\n', encoding="utf-8")
        request["code"]["runtime_path"] = str(foreign)
        result = fixture.invoke(request, launcher=True)
        need(result["exit_code"] != 0 and b"UNRELATED_CODE_MUST_NOT_RUN" not in result["stdout"], "FOREIGN_CODE_EXECUTED")
        return {"unchanged_pins_reject_changed_targets": True, "arbitrary_repinning": "OUT_OF_SCOPE"}

    def r03(self):
        fixture = self.fixture("r03", odd_path=True)
        api = self.api; key = api.own_pending_key(fixture.reference)
        first = api.runtime_initial_template(fixture.reference, fixture.code)
        before = fixture.accepted(); value = self.template(fixture, first)
        need(fixture.accepted() == before and value["calls"][0]["returned"]["exit_code"] == 0, "FIRST_COMMIT_OR_QUOTE_FAILURE")
        confirmation = {"chunk_id":"SYNTHETIC_TEMPLATE_CHUNK", "outer_output_intact":True}
        confirm = api.runtime_confirm_template(fixture.reference, fixture.code, confirmation)
        self.template(fixture, confirm, value["memory"])
        next_recipe = api.runtime_next_template(fixture.reference, fixture.code)
        value = self.template(fixture, next_recipe)
        self.template(fixture, confirm, value["memory"])
        user_recipe = api.runtime_next_template(fixture.reference, fixture.code,
            {"operation":"field", "selector":"/user", "start_char":0, "output_cap_bytes":8192, "metadata_reserve_bytes":2048})
        value = self.template(fixture, user_recipe)
        self.template(fixture, confirm, value["memory"])
        hashed = self.template(fixture, api.runtime_hash_template(fixture.reference, fixture.code))
        need(hashed["calls"][0]["returned"]["exit_code"] == 0 and key in value["memory"], "HASH_TEMPLATE_FAILURE")
        sizes = [len(recipe.encode("utf-8")) for recipe in (first,next_recipe,confirm,api.runtime_hash_template(fixture.reference,fixture.code))]
        need(max(sizes) < 131072, "COMMAND_CHANNEL_LIMIT")
        return {"template_bytes":sizes, "quoted_paths_exact":True, "full_result_forwarded":True}

    def r04(self):
        fixture = self.fixture("r04")
        request = fixture.request("view", view={"operation":"field", "selector":"/system", "start_char":0, "output_cap_bytes":8192, "metadata_reserve_bytes":2048})
        cases = []
        for key,value in (("start_char",True),("start_char",1.5),("start_char",2**53),("selector","/other"),
                          ("output_cap_bytes",255),("output_cap_bytes",8193),("output_cap_bytes",True),
                          ("metadata_reserve_bytes",127),("metadata_reserve_bytes",8192)):
            case=copy.deepcopy(request);case["view"][key]=value;cases.append(case)
        for change in (lambda r:r.update(operation="unknown"),lambda r:r.update(arbitrary="input"),
                       lambda r:r.update(view=[]),lambda r:r["view"].update(arbitrary="input")):
            case=copy.deepcopy(request);change(case);cases.append(case)
        codes=[self.rejected_request(fixture,case) for case in cases]
        duplicate=wire(request)[:-1]+',"operation":"view"}'
        codes.append(self.rejected_request(fixture,request,raw=duplicate))
        result=self.observer.run([NODE,fixture.code["runtime_path"],wire(request),"UNREGISTERED_EXTRA_ARGUMENT"])
        need(result["exit_code"]!=0 and fixture.accepted() is None,"EXTRA_ARGUMENT_ACCEPTED")
        return {"rejections":len(codes)+1}

    def r05(self):
        fixture=self.fixture("r05");foreign=self.fixture("r05-foreign")
        base=fixture.request("view",view={"operation":"inventory","output_cap_bytes":8192,"metadata_reserve_bytes":2048})
        cases=[]
        for reference in (foreign.reference,dict(fixture.reference,path="relative.json")):
            case=copy.deepcopy(base);case["reference"]=reference;cases.append(case)
        case=copy.deepcopy(base);case["session_path"]=str(foreign.state_path);cases.append(case)
        codes=[self.rejected_request(fixture,case) for case in cases]
        for key in ("sha256","request_sha256"):
            case=copy.deepcopy(base);case["reference"][key]="sha256:"+"0"*64
            # A mismatched digest is tested on the bound carrier, not a foreign helper.
            case["session_path"]=self.api.session_path(case["reference"],case["code"])
            codes.append(self.rejected_request(fixture,case))
        return {"rejections":len(codes),"template_descriptor_pins":"TRUSTED"}

    def r06(self):
        fixture=self.fixture("r06",system="",user="Aé🧪e\u0301\n\t\x00")
        baseline=literal_sources(Path(self.registration["baseline_ref"]["path"]).read_bytes())["READER_SOURCE"]
        pending=fixture.inventory();observations=[pending]
        for selector in ("/system","/user"):
            pending=fixture.view(selector);observations.append(pending)
            program=baseline+"\nemit_view("+repr(fixture.reference)+","+repr(pending["view"])+")\n"
            original=self.observer.run([PYTHON,"-I","-B","-"],stdin=program.encode("utf-8"))
            need(original["exit_code"]==0 and original["stdout"].decode("utf-8")==pending["result"]["output"],"READER_STDOUT_FIDELITY")
            fixture.confirm(pending)
        return {"view_count":len(observations),"exact_reader_stdout":True,"state":parse(fixture.accepted())["fields"]}

    def r07(self):
        fixture=self.fixture("r07");fixture.inventory();pending=fixture.view("/system")
        cases=[]
        for value in (False,None,"0",1):
            case=copy.deepcopy(pending);case["result"]["exit_code"]=value;cases.append(case)
        case=copy.deepcopy(pending);del case["result"]["exit_code"];cases.append(case)
        for key,value in (("session_id",7),("chunk_id","DIFFERENT_CHUNK"),("original_token_count",16385),("original_token_count",False)):
            case=copy.deepcopy(pending);case["result"][key]=value;cases.append(case)
        case=copy.deepcopy(pending);del case["result"]["chunk_id"];cases.append(case)
        confirm={"chunk_id":pending["result"]["chunk_id"],"outer_output_intact":True}
        for case in cases:fixture.confirm(case,confirm,reject=True)
        return {"rejected_completion_variants":len(cases)}

    def r08(self):
        fixture=self.fixture("r08");fixture.inventory();pending=fixture.view("/system")
        for intact in (False,1):fixture.confirm(pending,{"chunk_id":pending["result"]["chunk_id"],"outer_output_intact":intact},reject=True)
        fixture.confirm(pending,{"chunk_id":"UNMATCHED","outer_output_intact":True},reject=True)
        fixture.confirm(None,{"chunk_id":"MISSING","outer_output_intact":True},reject=True)
        bad=copy.deepcopy(pending);bad["reference"]["request_sha256"]="sha256:"+"0"*64;fixture.confirm(bad,reject=True)
        fixture.confirm(fixture.view("/system",0,4096,2048))
        return {"rejections":5,"explicit_same_cursor_recovery":True}

    def r09(self):
        fixture=self.fixture("r09");fixture.inventory();pending=fixture.view("/system")
        output=pending["result"]["output"]
        variants=[output[:-12]," "+output,output.rstrip("\n"),output.rstrip("\n")[:-1]+',"status":"ok"}\n',"{not JSON}\n"]
        for raw in variants:
            bad=copy.deepcopy(pending);bad["result"]["output"]=raw;fixture.confirm(bad,reject=True)
        fixture.confirm(pending,{"chunk_id":pending["result"]["chunk_id"],"outer_output_intact":False},reject=True)
        fixture.confirm(fixture.view("/system",0,4096,2048))
        return {"rejections":len(variants)+1,"explicit_same_cursor_recovery":True}

    def r10(self):
        fixture=self.fixture("r10");fixture.inventory();pending=fixture.view("/system")
        changes=[("carrier_path","/unrelated"),("carrier_sha256","sha256:"+"0"*64),
                 ("request_sha256","sha256:"+"0"*64),("request_id","different"),
                 ("operation","inventory"),("output_cap_bytes",4096),("metadata_reserve_bytes",1024),
                 ("field_chars",999),("carrier_raw_bytes",999),("content","x"*9000)]
        for key,value in changes:fixture.confirm(changed_output(pending,lambda d,k=key,v=value:d.update({k:v})),reject=True)
        return {"rejections":len(changes)}

    def r11(self):
        fixture=self.fixture("r11",system="Aé🧪e\u0301\n\t\x00",user="")
        fixture.inventory();pending=fixture.view("/system")
        for name in ("content_chars","content_utf8_bytes","end_char","start_utf8_byte","end_utf8_byte"):
            fixture.confirm(changed_output(pending,lambda d,k=name:d.update({k:d[k]+1})),reject=True)
        bad=copy.deepcopy(pending);doc=parse(bad["result"]["output"].encode("utf-8"));doc["content"]="\ud800"
        bad["result"]["output"]=json.dumps(doc,sort_keys=True,ensure_ascii=True,separators=(",",":"))+"\n"
        fixture.confirm(bad,reject=True)
        fixture.confirm(pending);fixture.confirm(fixture.view("/user"))
        return {"strict_scalar_fields":parse(fixture.accepted())["fields"],"rejections":6}

    def r12(self):
        fixture=self.fixture("r12",system="s"*12000)
        fixture.confirm(fixture.view("/system"),reject=True)
        fixture.inventory();fixture.confirm(fixture.view("/user"),reject=True)
        fixture.confirm(fixture.view("/system",1),reject=True)
        pending=fixture.view("/system")
        fixture.confirm(changed_output(pending,lambda d:d.update(start_utf8_byte=1)),reject=True)
        zero=changed_output(pending,lambda d:d.update(content="",content_chars=0,content_utf8_bytes=0,end_char=0,end_utf8_byte=0,next_char=0,field_eof=False))
        fixture.confirm(zero,reject=True)
        return {"ordering_gap_and_progress_rejections":5}

    def r13(self):
        fixture=self.fixture("r13",system="s"*12000);inventory=fixture.inventory()
        pending=fixture.view("/system",0,4096,2048);fixture.confirm(pending)
        before=parse(fixture.accepted());fixture.confirm(pending);after=parse(fixture.accepted())
        need(before["fields"]==after["fields"] and before["inventory"]==after["inventory"]
             and len(after["observations"])==len(before["observations"])+1,"REPLAY_ADVANCED_FIELDS_OR_CHANGED_BASELINE_HISTORY_SEMANTICS")
        fixture.confirm(changed_output(pending,lambda d:d.update(content="z"+d["content"][1:])),reject=True)
        fixture.confirm(fixture.view("/system",0,8192,2048),reject=True)
        bad=changed_output(inventory,lambda d:d.update(request_id="different"));fixture.confirm(bad,reject=True)
        return {"replay_field_idempotence":True,"exact_replay_observation_appended":True,"rejections":3}

    def r14(self):
        empty=self.fixture("r14-empty",system="",user="");state=empty.finish()
        result=parse(empty.hash()["stdout"])
        need(all(field["field_eof"] for field in state["fields"].values())
             and set(result["field_roots"].values())=={sha(b"")},"EMPTY_EOF_HASH")
        empty.confirm(empty.view("/user",0))
        fixture=self.fixture("r14-negative",system="s"*12000);fixture.inventory();pending=fixture.view("/system")
        fixture.confirm(changed_output(pending,lambda d:d.update(field_eof=True)),reject=True)
        fixture.confirm(changed_output(pending,lambda d:d.update(field_eof=1)),reject=True)
        terminal=self.fixture("r14-terminal");terminal.inventory();end=terminal.view("/system")
        terminal.confirm(changed_output(end,lambda d:d.update(end_utf8_byte=d["end_utf8_byte"]-1)),reject=True)
        return {"empty_hash":sha(b""),"explicit_empty_eof":True,"rejections":3}

    def r15(self):
        fixture=self.fixture("r15");fixture.hash(reject=True);fixture.inventory()
        fixture.confirm(fixture.view("/system"));fixture.hash(reject=True);fixture.finish()
        valid=fixture.accepted();state=parse(valid)
        mutations=[lambda s:s["fields"]["/user"].update(content="tampered"),
                   lambda s:s.update(observations=[]),lambda s:s["observations"][-1]["pending"]["result"].update(output="truncated"),
                   lambda s:s["reference"].update(request_sha256="sha256:"+"0"*64)]
        for change in mutations:
            bad=copy.deepcopy(state);change(bad);fixture.state_path.write_bytes((wire(bad)+"\n").encode("utf-8"))
            injected=fixture.accepted();fixture.hash(reject=True);need(fixture.accepted()==injected,"INVALID_CHECKPOINT_OVERWRITTEN")
            fixture.state_path.write_bytes(valid)
        return {"incomplete_or_tampered_hash_rejections":len(mutations)+2}

    def r16(self):
        cases=[("length-"+str(n),"x"*n) for n in (0,55,56,63,64,65)]
        cases += [("unicode","Aé🧪e\u0301\n\t\x00"),("large","x"*400019+"🧪")]
        witnesses=[]
        for tag,user in cases:
            fixture=self.fixture("r16-"+tag,system="",user=user);fixture.finish()
            result=parse(fixture.hash()["stdout"])
            roots={"/system":sha(b""),"/user":sha(user.encode("utf-8"))}
            need(result["field_roots"]==roots and result["field_chars"]=={"/system":0,"/user":len(user)}
                 and result["field_utf8_bytes"]=={"/system":0,"/user":len(user.encode("utf-8"))},"STDLIB_DIGEST_OR_TOTAL_MISMATCH")
            need(result["availability_only"] is True and result["semantic_consumption"]=="UNATTESTED"
                 and result["semantic_acceptance_authority"] is False and "markers" not in result,"HASH_AUTHORITY_OR_MARKER_LEAK")
            state=parse(fixture.accepted());view_count=sum(o["pending"]["view"]["operation"]=="field" for o in state["observations"])
            if tag=="large":need(view_count>2,"LARGE_FIXTURE_NOT_MULTISLICE")
            witnesses.append({"tag":tag,"roots":roots,"chars":len(user),"utf8_bytes":len(user.encode("utf-8")),"field_views":view_count})
        for record in self.observer.records:
            args=parse(Path(record["path"]).read_bytes())["argv_or_shell_command"]
            need(max([len(a.encode("utf-8")) for a in args] if type(args) is list else [len(args.encode("utf-8"))])<131072,"WHOLE_FIELD_COMMAND_ARGUMENT")
        return {"digest_witnesses":witnesses}

    def r17(self):
        fixture=self.fixture("r17");fixture.finish();valid=fixture.accepted()
        before=parse(fixture.hash()["stdout"]);fixture.carrier.rename(fixture.carrier.with_suffix(".unavailable"))
        need(parse(fixture.hash()["stdout"])==before,"HASH_READ_CARRIER_OR_RESTART_CHANGED_STATE")
        for bad in (valid[:-9],b'{"broken":true}\n',b"\xff\n"):
            fixture.state_path.write_bytes(bad);fixture.hash(reject=True)
            need(fixture.accepted()==bad,"INJECTED_INVALID_STATE_MUTATED")
            fixture.state_path.write_bytes(valid)
        need(parse(fixture.hash()["stdout"])==before,"STATE_RESTORE_DID_NOT_REVALIDATE")
        return {"restart_persistence":True,"hash_without_carrier":True,"corrupt_rejections":3}

    def r18(self):
        fixture=self.fixture("r18");fixture.inventory();pending=fixture.view("/system")
        before=fixture.accepted();lock=Path(str(fixture.state_path)+".lock")
        lock.write_bytes(b"generic own-session busy control\n")
        actual=fixture.confirm(pending,reject=True)
        need(parse(actual["stdout"])["code"]=="OWN_SESSION_BUSY" and fixture.accepted()==before,"LOCK_FAILURE_COMMITTED")
        lock.unlink();fixture.confirm(pending)
        # A fixed generic preloader creates the collision before requiring unchanged runtime.
        # This is deterministic fault injection, not an author template or timing race.
        pending=fixture.view("/user");before=fixture.accepted()
        script="""const fs=require('node:fs');
const request=JSON.parse(process.argv[2]);
fs.writeFileSync(request.session_path+'.temporary-'+process.pid,'generic temporary-name collision');
require(process.argv[1]);
"""
        request=fixture.request("confirm",pending=pending,confirmation={"chunk_id":pending["result"]["chunk_id"],"outer_output_intact":True})
        result=self.observer.run([NODE,"-e",script,fixture.code["runtime_path"],wire(request)])
        observed=parse(result["stdout"])
        need(result["exit_code"]!=0 and observed["status"]=="error"
             and "EEXIST" in observed["code"] and fixture.accepted()==before,
             "ATOMIC_OPEN_FAILURE_NOT_OBSERVED_OR_STATE_MUTATED")
        fixture.confirm(pending)
        return {"busy_reject_preserved_state":True,"precommit_failure_preserved_state":True}


def authenticate(args):
    registration_path=Path(args.registration).resolve();raw=registration_path.read_bytes()
    need(sha(raw)==args.registration_sha256,"REGISTRATION_IDENTITY_MISMATCH")
    registration=parse(raw)
    need(registration["format"]=="verislop.carrier-runtime-independent-control-registration/1"
         and registration["controls_authorized"] is True and registration["control_ids"]==IDS,
         "CONTROL_EXECUTION_NOT_AUTHORIZED_OR_REGISTERED")
    need(registration["contract_ref"]["sha256"]==CONTRACT_SHA,"CONTROL_PREDICATES_CHANGED")
    refs=[registration["contract_ref"],registration["boundary_amendment_ref"],registration["baseline_ref"],registration["harness_ref"]]+registration["candidate_source_refs"]
    hashes={}
    for entry in refs:
        path=Path(entry["path"]).resolve();observed=identity(path)
        need(observed["sha256"]==entry["sha256"] and observed["byte_count"]==entry["byte_count"],"REGISTERED_INPUT_MISMATCH:"+str(path))
        hashes[str(path)]=entry["sha256"]
    need(Path(registration["harness_ref"]["path"]).resolve()==Path(__file__).resolve(),"OTHER_HARNESS_REGISTERED")
    candidate=Path(registration["candidate_directory"]).resolve()
    api_path=candidate/"compact_protocol.py"
    need(str(api_path) in hashes,"API_SOURCE_NOT_REGISTERED")
    for name in ("reader.py","carrier_runtime.js","legacy006.py"):
        need(str(candidate/name) in hashes,"REQUIRED_CANDIDATE_SOURCE_NOT_REGISTERED")
    output=Path(registration["output_directory"])
    need(output.is_absolute() and output.resolve()==output and not output.exists(),"OUTPUT_NOT_FRESH_CANONICAL_DIRECTORY")
    output.mkdir()
    save(output/"authenticated-inputs.json",{"format":"verislop.runtime020-independent-inputs/1","registration_ref":identity(registration_path),"input_hashes":hashes,"control_ids":IDS,"qualification_authority":False})
    module_spec=importlib.util.spec_from_file_location("registered_support020_compact_api",api_path)
    api=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(api)
    need(api.PYTHON_PATH==PYTHON and api.NODE_PATH==NODE and api.REQUEST_FORMAT==REQUEST_FORMAT,"REGISTERED_API_INTERFACE_CHANGED")
    return registration,api,hashes,output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration",required=True)
    parser.add_argument("--registration-sha256",required=True)
    args=parser.parse_args()
    registration,api,hashes,output=authenticate(args)
    results=[];runs=[]
    for run in (1,2):
        suite=Suite(output/("clean-run-"+str(run).zfill(2)),registration,api,None,hashes)
        records=[]
        for number in range(1,19):
            ident=IDS[number-1];print("CONTROL_START",run,ident,flush=True)
            start=time.monotonic()
            try:
                witness=getattr(suite,"r"+str(number).zfill(2))()
                suite.guard();record={"id":ident,"status":"PASS","witness":witness}
            except Exception as error:
                record={"id":ident,"status":"BLOCK","error_type":type(error).__name__,"error_literal":str(error),"traceback":traceback.format_exc()}
            record["elapsed_seconds"]=time.monotonic()-start
            save(suite.root/(ident+".json"),record);records.append(record)
            print("CONTROL_END",run,ident,record["status"],flush=True)
            if record["status"]!="PASS":
                break
        save(suite.root/"process-index.json",{"format":"verislop.runtime020-independent-process-index/1","records":suite.observer.records,"synthetic_pending_count":suite.synthetic_pending_count,"chunk_envelopes":"EXPLICIT_SYNTHETIC_FIXTURES_NOT_NATIVE_TOOL_ATTESTATION","observed_OS_process_count":len(suite.observer.records),"hidden_model_reason":"UNAVAILABLE","qualification_authority":False})
        runs.append({"run":run,"controls":records,"process_count":len(suite.observer.records),"synthetic_pending_count":suite.synthetic_pending_count})
        results.append({r["id"]:{k:v for k,v in r.items() if k not in {"elapsed_seconds"}} for r in records})
        if any(r["status"]!="PASS" for r in records):break
    complete=len(runs)==2 and all(len(run["controls"])==18 and all(r["status"]=="PASS" for r in run["controls"]) for run in runs)
    deterministic=complete and results[0]==results[1]
    comparison={"id":"S020-R19","status":"PASS" if deterministic else "BLOCK","two_fresh_run_directories":len(runs)==2,"deterministic_witnesses_equal":deterministic,"excluded_fields":["elapsed_seconds","observed_PIDs","fresh_session_paths"],"prior_outcome_reuse":False}
    save(output/"S020-R19.json",comparison)
    final={"format":"verislop.runtime020-independent-finite-controls/1","status":"PASS" if deterministic else "BLOCK","qualification_authority":False,"control_ids":IDS,"runs":runs,"determinism":comparison,"controller_process_PID":os.getpid(),"models":0,"tasks":0,"Lean":0,"historical_Q005_cause":"UNKNOWN","native_tool_attestation":False,"input_hashes":hashes,"no_inference_or_retrieval_deadline":True}
    save(output/"report.json",final)
    print(json.dumps({"status":final["status"],"report_ref":identity(output/"report.json"),"actual_controller_PID":os.getpid()},sort_keys=True),flush=True)
    return 0 if deterministic else 1


if __name__=="__main__":
    raise SystemExit(main())
