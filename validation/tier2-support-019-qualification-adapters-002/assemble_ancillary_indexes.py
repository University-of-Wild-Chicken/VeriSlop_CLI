#!/usr/bin/env python3
"""Bind retained actual artifacts into new indexes; never launch any producer."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNAVAILABLE = {"hidden_native_outer_http_mcp_envelope":"UNAVAILABLE", "separated_stdout":"UNAVAILABLE",
               "separated_stderr":"UNAVAILABLE", "pid":"UNAVAILABLE"}


def parse(raw):
    def unique(items):
        result = {}
        for key,value in items:
            if key in result: raise ValueError("Duplicate JSON key: "+key)
            result[key]=value
        return result
    return json.loads(raw.decode("utf-8","strict"),object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def sha(raw):
    return "sha256:"+hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-root",type=Path,required=True)
    parser.add_argument("--carrier-records",type=Path)
    parser.add_argument("--author-records",type=Path)
    args=parser.parse_args()
    gate=args.qualification_root.absolute()
    if gate.resolve()!=gate or gate.parent!=ROOT/"validation" or not gate.name.startswith("tier2-support-019-qualification-"):
        raise ValueError("Only canonical new qualification root")
    consumed={}
    allowed_prefixes=[gate]
    frozen_hashes={}
    def read(path):
        if not path.is_file() or path.is_symlink() or path.resolve()!=path.absolute(): raise ValueError("Noncanonical artifact")
        raw=path.read_bytes(); identity={"path":path.relative_to(ROOT).as_posix(),"sha256":sha(raw),"byte_count":len(raw)}
        if path in consumed and consumed[path]!=identity: raise ValueError("Artifact changed during index assembly")
        consumed[path]=identity
        return raw,identity
    def fresh(entry):
        path=ROOT/entry["path"]
        if not any(path.is_relative_to(prefix) for prefix in allowed_prefixes): raise ValueError("Artifact outside exact registered fresh prefixes")
        raw,identity=read(path)
        if not path.is_relative_to(gate) and frozen_hashes.get(identity["path"])!=identity["sha256"]:
            raise ValueError("External fresh fixture is not an exact frozen input")
        if entry.get("sha256",identity["sha256"])!=identity["sha256"] or entry.get("byte_count",len(raw))!=len(raw):
            raise ValueError("Retained artifact identity mismatch")
        return raw,identity
    frozen=parse(read(gate/"qualification-inputs.json")[0]); spec=parse(read(gate/"qualification-specification.json")[0])
    frozen_hashes=frozen["source_hashes"]
    prefixes=spec["adapters"]["fresh_evidence_prefixes"]
    if gate.relative_to(ROOT).as_posix() not in prefixes: raise ValueError("New root omitted from explicit fresh prefixes")
    allowed_prefixes=[]
    for prefix in prefixes:
        name=Path(prefix)
        if name.is_absolute() or ".." in name.parts or name.as_posix()!=prefix or not prefix.startswith("validation/"):
            raise ValueError("Noncanonical registered fresh prefix")
        allowed_prefixes.append(ROOT/name)
    for name,expected in frozen["source_hashes"].items():
        if read(ROOT/name)[1]["sha256"]!=expected: raise ValueError("Frozen source/input mutated")
    root_fields={"closure_id":spec["closure_id"],"source_root":frozen["source_root"],"input_root":frozen["input_root"]}
    def bound(doc):
        if doc["source_root"]!=root_fields["source_root"] or doc["input_root"]!=root_fields["input_root"]:
            raise ValueError("Stale producer artifacts")
    equality_path=gate/"equality/equality-result.json"; pure_path=gate/"carrier-pure-result.json"
    equality=parse(read(equality_path)[0]); bound(equality)
    if equality["format"]!="verislop.support019-equality-observations/1" or equality["status"]!="OBSERVED": raise ValueError("Equality producer schema")
    if set(equality["reports"])!={"original-main","original-additional","private-binding"} or len(equality["processes"])!=3: raise ValueError("Missing actual equality processes")
    for name,digest in equality["files"].items(): fresh({"path":name,"sha256":digest})
    for identity in equality["reports"].values(): fresh(identity)
    pure=parse(read(pure_path)[0]); bound(pure)
    if pure["format"]!="verislop.support019-carrier-pure-observations/1" or pure["status"]!="OBSERVED": raise ValueError("Pure producer schema")
    fresh(pure["semantic_witnesses_ref"])
    outputs=[]
    def walk_refs(value):
        if isinstance(value,dict):
            if "path" in value and "sha256" in value:
                _,identity=fresh(value)
                if "request_sha256" in value:
                    return value
                return dict(value,**identity)
            return {key:walk_refs(item) for key,item in value.items()}
        if isinstance(value,list): return [walk_refs(item) for item in value]
        return value
    for kind,path,format_name,subpath in (("carrier",args.carrier_records,"verislop.support019-observable-channel-capture/1","actual-channel/capture-index.json"),
                                        ("author",args.author_records,"verislop.support019-single-fresh-author-evidence/1","fresh-author/author-index.json")):
        if path is None: continue
        if not path.absolute().is_relative_to(gate): raise ValueError("Descriptor is not current-root actual evidence")
        descriptor=parse(read(path.absolute())[0]); bound(descriptor)
        descriptor=walk_refs(descriptor)
        if kind=="carrier":
            if descriptor["unavailable"]!=UNAVAILABLE or not descriptor["calls"]: raise ValueError("Missing actual capture/unavailable declaration")
            for call in descriptor["calls"]:
                record=parse(fresh(call["retained_record_ref"])[0]); result=record["result"]
                if record["view"]!=call["view"] or type(result["exit_code"]) is not int or result["exit_code"]!=0 or "session_id" in result:
                    raise ValueError("Incomplete nested actual result")
                if result["output"].encode("utf-8","strict")!=fresh(call["returned_output_ref"])[0]: raise ValueError("Nested returned bytes differ")
        else:
            requests=descriptor["observed_author_requests"]
            if type(descriptor["spawn_count"]) is not int or descriptor["spawn_count"]!=1 or type(requests) is not list or len(requests)!=1 or descriptor["replacement_author_or_resampling"] is not False:
                raise ValueError("Single actual author requirement")
            row=requests[0]
            if type(row) is not dict or set(row)!={"spawn_request_ref","spawn_result_ref","agent_id"}:
                raise ValueError("Actual author request inventory schema")
            def wire(value):
                return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8","strict")
            if wire(row["spawn_request_ref"])!=wire(descriptor["spawn_request_ref"]) or wire(row["spawn_result_ref"])!=wire(descriptor["spawn_result_ref"]):
                raise ValueError("Actual author inventory raw reference differs")
            request=parse(fresh(row["spawn_request_ref"])[0]); result=parse(fresh(row["spawn_result_ref"])[0])
            if type(result["agent_id"]) is not str or not result["agent_id"] or type(descriptor["author_agent_id"]) is not str or result["agent_id"]!=descriptor["author_agent_id"] or result["agent_id"]!=row["agent_id"]:
                raise ValueError("Actual author agent identities differ")
            submitted=fresh(descriptor["submitted_message_ref"])[0]
            if descriptor["requested_model"]!="gpt-6.1-sol" or descriptor["fork_turns"]!="none" or request["model"]!="gpt-6.1-sol" or request["fork_turns"]!="none" or type(request["message"]) is not str or request["message"].encode("utf-8","strict")!=submitted or fresh(descriptor["expected_literal_message_ref"])[0]!=submitted or descriptor["evaluator_expectations_sent_to_author"] is not False:
                raise ValueError("Actual plain author request differs")
            if not (descriptor["model_identity"]==descriptor["semantic_consumption"]=="UNATTESTED"): raise ValueError("Unattested model boundary")
        output=gate/subpath
        if output.exists(): raise ValueError("Index exists")
        outputs.append((output,dict(descriptor,format=format_name,**root_fields)))
    for path,identity in list(consumed.items()):
        if read(path)[1]!=identity: raise ValueError("Consumed artifact mutated")
    for path,doc in outputs:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("x",encoding="utf-8") as stream:json.dump(doc,stream,sort_keys=True,indent=2,allow_nan=False);stream.write("\n")
    identities={"equality":read(equality_path)[1],"pure":read(pure_path)[1]}
    for path,_ in outputs:identities["carrier" if path.name=="capture-index.json" else "author"]=read(path)[1]
    with (gate/"ancillary-index-identities.json").open("x",encoding="utf-8") as stream:
        json.dump({"format":"verislop.support019-ancillary-index-identities/1","status":"OBSERVED",**root_fields,"indexes":identities},stream,sort_keys=True,indent=2);stream.write("\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
