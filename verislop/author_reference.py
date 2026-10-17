"""Exact author-only Lean registry display, authenticated by accepted artifacts."""
from __future__ import annotations

import copy
from pathlib import Path

from . import agent_memory, canonical, contract, exprjson
from .bridges.manifest import PackageReader, InvalidPackage
from .errors import blocked

FORMAT = "verislop.author-reference-display/0.1"
CERT = "reference/acceptance-certificate.json"
ENV = "reference/environment.json"
RENDERER = "reference/registry-renderer.py"
REGISTRY = "reference/registry.lean"
VIEW = "reference/view.json"
ARTIFACTS = {CERT, ENV, RENDERER, REGISTRY, VIEW}
AUTHORITY = ("Author-only display, not complete compilable source. All non-registry bytes remain exact; "
             "full original source remains unchanged for checkers and provers.")


def _fail(message):
    raise blocked("STALE_OR_UNBOUND_EVIDENCE", "author reference display: " + message)


def _authenticated(fixed, artifacts):
    """Validate only retained bytes; historical restoration has no ambient reads."""
    try:
        ir, reference = fixed["accepted_ir"], fixed["accepted_reference"]
        source = reference["lean_source"].encode("utf-8")
        certificate = canonical.loads(artifacts[CERT])
        environment = canonical.loads(artifacts[ENV])
        cert_hash, env_hash = canonical.digest(artifacts[CERT]), canonical.digest(artifacts[ENV])
        if (Path(ir["acceptance_certificate_ref"]).name != cert_hash[7:] + ".json"
                or certificate["artifact_kind"] != "acceptance_certificate"
                or certificate["gate"] != "accepted_and_proved"
                or certificate["contract_input_root"] != ir["contract_input_root"]
                or certificate["toolchain"]["pin"] != fixed["lean_toolchain"]
                or ir["lean_toolchain"] != fixed["lean_toolchain"]
                or certificate["artifacts"]["source"] != {"path": reference["path"], "sha256": reference["sha256"]}
                or canonical.digest(source) != reference["sha256"]
                or certificate["artifacts"]["environment_export"]["sha256"] != env_hash
                or ir["accepted_environment_hash"] != env_hash
                or environment["lean_githash"] != certificate["toolchain"]["githash"]
                or environment["import"]["ok"] is not True or environment["replay"]["ok"] is not True):
            _fail("certificate, environment, source or toolchain binding differs")
        constants = environment["constants"]
        if not isinstance(constants, list) or any(not isinstance(c, dict) for c in constants):
            _fail("malformed native declaration inventory")
        decls = {exprjson.name_str(c["name"]): c for c in constants}
        if len(decls) != len(constants):
            _fail("duplicate native declaration identity")
        return certificate, decls, source
    except (KeyError, TypeError, ValueError, UnicodeError, AttributeError, RecursionError) as exc:
        _fail("malformed bound artifact: " + str(exc))


def _records(fixed, decls):
    try:
        records = contract.decode_registry(decls)
    except (contract.RegistryError, KeyError, TypeError, ValueError, RecursionError):
        return None
    obligations = fixed["accepted_ir"].get("obligations")
    if not isinstance(obligations, dict) or any(not isinstance(value, dict) for value in obligations.values()):
        _fail("malformed accepted obligation inventory")
    ids = [r["id"] for r in records]
    if len(ids) != len(set(ids)) or set(ids) != set(obligations):
        _fail("registry and accepted obligation inventories differ")
    for row in records:
        # Export deliberately reconstructs dependencies. Retain original registry
        # dependencies and all bindings verbatim instead of equating the two.
        for key in contract.RECORD_FIELDS:
            if key != "dependencies" and canonical.dumps(row[key]) != canonical.dumps(obligations[row["id"]].get(key)):
                _fail("registry metadata differs from accepted IR: " + row["id"] + "." + key)
    return records


def _operative(decls):
    prefix = contract.REGISTRY_NS + "."
    found = []
    for name, declaration in decls.items():
        if name.startswith(prefix):
            continue
        references = exprjson.constants(declaration.get("type")) | exprjson.constants(declaration.get("value"))
        proof_references = declaration.get("value_constants", [])
        if (not isinstance(proof_references, list) or any(not isinstance(row, list) or not row
                or any(type(part) not in (str, int) for part in row) for row in proof_references)):
            _fail("malformed native theorem constant inventory")
        references.update(exprjson.name_str(row) for row in proof_references)
        if any(ref.startswith(prefix) for ref in references):
            found.append(name)
    return sorted(found)


def _rendered_span(raw, records):
    """Regenerate complete metadata syntax, then require its exact header position."""
    generated = contract.registry_lean(records, {r["id"]: r["bindings"] for r in records}).encode("utf-8")
    if raw.count(generated) != 1:
        return generated, None, "source does not contain exactly one complete regenerated registry span"
    start = raw.index(generated)
    text = raw.decode("utf-8")
    end_header, _imports, problems = contract.split_header(text)
    header_byte_end = len(text[:end_header].encode("utf-8"))
    if problems or start < header_byte_end or raw[header_byte_end:start].strip():
        return generated, None, "registry is outside the supported import-header placement"
    return generated, {"start_byte": start, "end_byte": start + len(generated),
                       "sha256": canonical.digest(generated)}, None


def capture_artifacts(pkg, fixed, *, retention_reserved_bytes=0):
    """Capture bound inputs once; valid unusual shapes keep a full source display."""
    reader = None
    try:
        reader = PackageReader(pkg.root)
        cert = reader.read(fixed["accepted_ir"]["acceptance_certificate_ref"], keep=True)
        parsed = canonical.loads(cert.data)
        env = reader.read(parsed["artifacts"]["environment_export"]["path"], keep=True)
        source = reader.read(parsed["artifacts"]["source"]["path"], keep=True)
        if source.data != fixed["accepted_reference"]["lean_source"].encode("utf-8"):
            _fail("current accepted source differs from the fixed source")
        artifacts = {CERT: cert.data, ENV: env.data, RENDERER: Path(contract.__file__).read_bytes()}
        _certificate, decls, raw = _authenticated(fixed, artifacts)
        records = _records(fixed, decls)
        reason, span, generated = None, None, b""
        if records is None:
            reason = "unsupported native registry shape"
        elif _operative(decls):
            reason = "outside native declarations reference VeriSlop.Registry"
        else:
            generated, span, reason = _rendered_span(raw, records)
        receipt = {"format": FORMAT, "mode": "full_source" if reason else "registry_display",
                   "reason": reason, "span": span, "records": records,
                   "renderer_sha256": canonical.digest(artifacts[RENDERER])}
        artifacts[REGISTRY] = generated
        artifacts[VIEW] = canonical.dumps(receipt)
        reader.recheck()
        if (any(len(data) > agent_memory.MAX_ARTIFACT_BYTES for data in artifacts.values())
                or retention_reserved_bytes + sum(map(len, artifacts.values())) > agent_memory.MAX_CHECKPOINT_BYTES):
            # This optimization must not add a rejection for a valid large native
            # environment. Retain the entire original source, and explicitly say
            # that native display-validation inputs were not retained.
            fallback = {"format": FORMAT, "mode": "full_source_retention_limit",
                "reason": "native reference display inputs exceed existing agent-memory retention limits",
                "environment_retained": False, "reserved_checkpoint_bytes": retention_reserved_bytes,
                "limits": {"artifact_bytes": agent_memory.MAX_ARTIFACT_BYTES,
                           "checkpoint_bytes": agent_memory.MAX_CHECKPOINT_BYTES},
                "observed_artifacts": {path: {"sha256": canonical.digest(data), "size": len(data)}
                                       for path, data in sorted(artifacts.items())}}
            return {VIEW: canonical.dumps(fallback)}
        project_reference(fixed, artifacts)
        return artifacts
    except (InvalidPackage, OSError, KeyError, TypeError, ValueError, UnicodeError) as exc:
        _fail("cannot capture accepted reference: " + str(exc))
    finally:
        if reader is not None:
            reader.close()


def project_reference(fixed, artifacts):
    """Recreate a bound view from retained inputs without current package/source IO."""
    if set(artifacts) == {VIEW} and type(artifacts[VIEW]) is bytes:
        receipt = canonical.loads(artifacts[VIEW])
        if (not isinstance(receipt, dict) or set(receipt) != {"format", "mode", "reason", "environment_retained",
                "reserved_checkpoint_bytes", "limits", "observed_artifacts"}
                or receipt["format"] != FORMAT or receipt["mode"] != "full_source_retention_limit"
                or receipt["environment_retained"] is not False or not isinstance(receipt["reason"], str)
                or not receipt["reason"] or not isinstance(receipt["observed_artifacts"], dict)
                or set(receipt["observed_artifacts"]) != ARTIFACTS
                or type(receipt["reserved_checkpoint_bytes"]) is not int or receipt["reserved_checkpoint_bytes"] < 0
                or not isinstance(receipt["limits"], dict) or set(receipt["limits"]) != {"artifact_bytes", "checkpoint_bytes"}
                or any(type(n) is not int or n <= 0 for n in receipt["limits"].values())):
            _fail("malformed historical retention-limit receipt")
        for row in receipt["observed_artifacts"].values():
            if (not isinstance(row, dict) or set(row) != {"sha256", "size"}
                    or type(row["size"]) is not int or row["size"] < 0
                    or not isinstance(row["sha256"], str) or len(row["sha256"]) != 71
                    or not row["sha256"].startswith("sha256:")
                    or any(c not in "0123456789abcdef" for c in row["sha256"][7:])):
                _fail("malformed historical retention-size binding")
        if (all(row["size"] <= receipt["limits"]["artifact_bytes"] for row in receipt["observed_artifacts"].values())
                and receipt["reserved_checkpoint_bytes"] + sum(row["size"] for row in receipt["observed_artifacts"].values())
                <= receipt["limits"]["checkpoint_bytes"]):
            _fail("retention-limit receipt does not exceed its declared limits")
        # No environment is reconstructed or claimed authenticated here. The
        # unchanged full reference comes from the independently bound fixed context.
        return copy.deepcopy(fixed["accepted_reference"])
    if set(artifacts) != ARTIFACTS or any(type(value) is not bytes for value in artifacts.values()):
        _fail("historical reference artifact inventory differs")
    certificate, decls, raw = _authenticated(fixed, artifacts)
    records = _records(fixed, decls)
    try:
        receipt = canonical.loads(artifacts[VIEW])
        if (not isinstance(receipt, dict) or set(receipt) != {"format", "mode", "reason", "span", "records", "renderer_sha256"}
                or receipt["format"] != FORMAT or receipt["mode"] not in ("full_source", "registry_display")
                or receipt["renderer_sha256"] != canonical.digest(artifacts[RENDERER])
                or canonical.dumps(receipt["records"]) != canonical.dumps(records)):
            _fail("historical reference receipt differs")
        reference = copy.deepcopy(fixed["accepted_reference"])
        if "lean_source_display" in reference:
            _fail("original source reference already contains display metadata")
        if receipt["mode"] == "full_source":
            if not isinstance(receipt["reason"], str) or not receipt["reason"] or receipt["span"] is not None:
                _fail("malformed full-source display reason")
            reference["lean_source_display"] = {"format": FORMAT, "mode": "full_source", "reason": receipt["reason"]}
            return reference
        span = receipt["span"]
        if (records is None or _operative(decls) or receipt["reason"] is not None
                or not isinstance(span, dict) or set(span) != {"start_byte", "end_byte", "sha256"}
                or type(span["start_byte"]) is not int or type(span["end_byte"]) is not int
                or not 0 <= span["start_byte"] < span["end_byte"] <= len(raw)):
            _fail("malformed or ineligible registry display span")
        start, end = span["start_byte"], span["end_byte"]
        generated, exact_span, reason = _rendered_span(raw, records)
        if (reason or canonical.dumps(exact_span) != canonical.dumps(span)
                or generated != artifacts[REGISTRY] or raw[start:end] != artifacts[REGISTRY]
                or canonical.digest(artifacts[REGISTRY]) != span["sha256"]):
            _fail("retained registry bytes differ from their source span")
        before, after = raw[:start].decode("utf-8"), raw[end:].decode("utf-8")
        if before.encode() + artifacts[REGISTRY] + after.encode() != raw:
            _fail("source segments did not restore exactly")
        del reference["lean_source"]
        reference["lean_source_display"] = {"format": FORMAT, "authority": AUTHORITY,
            "before_registry": before, "after_registry": after,
            "retained_registry": {**span, "certificate_sha256": canonical.digest(artifacts[CERT]),
                                  "environment_export": certificate["artifacts"]["environment_export"]},
            "registry_metadata": {"ordered_entries": records,
                "meaning": "Complete decoded registry records in original order, including original dependencies and every binding. Exported IR dependencies can differ."}}
        return reference
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        _fail("invalid historical reference display: " + str(exc))
