#!/usr/bin/env python3
"""Finite, real-kernel evaluation of a configured prover; see the frozen protocol.

This program does not resume any prior run or call an interpreter/formalizer
model. All synthetic specification inputs are public and proof-free.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from contextlib import contextmanager
import importlib.metadata
import os
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from verislop import accept, agents, canonical, contract, export, formal_frontend as ff, formalize, fsutil, interpret, leanbridge, proof_fragments, prove, schemas, source_policy
from verislop.bridges import prepare, vscore3_checker as checker
from verislop.events import EventSink
from verislop.errors import Diagnostic, UsageError
from verislop.package import Package
from verislop.providers import config as provider_config
from verislop.providers.broker import Broker
from verislop.targets import vscore3_target as target
from synthetic_dataset.tools.small_prover_cohort import cases

FORMAT = "verislop.small-prover-evaluation/1"


def write(path, value):
    fsutil.write_json(path, value, pretty=True)


def record_exception(exc):
    return {"type": type(exc).__name__, "message": str(exc),
            "diagnostics": [d.to_json() for d in getattr(exc, "diagnostics", [])]}


def check_stop(args):
    if args.stop_file and Path(args.stop_file).exists():
        raise KeyboardInterrupt("external stop file exists")


def interrupt(_signum, _frame):
    raise KeyboardInterrupt("external signal")


def source_hashes():
    paths = [ROOT / "docs/small-prover-evaluation.md", Path(__file__).resolve(),
             Path(__file__).with_name("small_prover_cohort.py")]
    paths += [p for name in ("verislop", "schemas") for p in (ROOT / name).rglob("*")
              if p.is_file() and p.suffix in {".py", ".lean", ".json"}]
    return {p.relative_to(ROOT).as_posix(): canonical.digest_file(p) for p in sorted(set(paths))}


def unchanged(freeze):
    for name, expected in freeze["source_hashes"].items():
        if canonical.digest_file(ROOT / name) != expected:
            raise RuntimeError("evaluation source changed after freeze: " + name)
    for name, expected in freeze["run_inputs"].items():
        if canonical.digest_file(Path(freeze["output"]) / name) != expected:
            raise RuntimeError("evaluation input changed after freeze: " + name)
    for name, expected in freeze.get("external_inputs", {}).items():
        if canonical.digest_file(Path(name)) != expected:
            raise RuntimeError("evaluation external input changed after freeze: " + name)


def load_prompt_tokenizer(args, out):
    if not getattr(args, "tokenizer", None):
        return None, {}
    try:
        import transformers
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise UsageError("--tokenizer requires a Python environment containing Transformers", [Diagnostic(
            "CONFIGURATION_INVALID", str(exc), details={"path": "--tokenizer", "kind": "tokenizer_unavailable"})]) from None
    directory = Path(args.tokenizer).resolve()
    tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True, trust_remote_code=False)
    files = [p for p in directory.iterdir() if p.is_file() and
             (p.name.startswith(("tokenizer", "special_tokens", "added_tokens", "vocab", "merges")) or p.name == "config.json")]
    identities = {str(p): canonical.digest_file(p) for p in files}
    identities[str(Path(sys.executable).resolve())] = canonical.digest_file(Path(sys.executable).resolve())
    identities[str(Path(transformers.__file__).resolve())] = canonical.digest_file(Path(transformers.__file__).resolve())
    info = {"basis": "exact token count for local Hugging Face chat serialization; native Ollama template may differ",
        "directory": str(directory), "class": type(tokenizer).__name__,
        "versions": {name: importlib.metadata.version(name) for name in ("transformers", "tokenizers", "jinja2")},
        "python": sys.executable, "chat_template_sha256": canonical.digest(tokenizer.get_chat_template().encode()),
        "enable_thinking": False, "add_generation_prompt": True, "external_inputs": identities,
        "native_input_difference_threshold_tokens": 128}
    write(out / "prompt-tokenizer-freeze.json", info)
    return tokenizer, identities


def prompt_preflight(tokenizer, broker, agent, system, user):
    agent_conf = broker.r.agent(agent)
    context = agent_conf.get("context_window_tokens")
    maximum_output = agent_conf["max_output_tokens"]
    if context is None:
        raise UsageError("tokenizer preflight needs an explicit context_window_tokens", [Diagnostic(
            "CONFIGURATION_INVALID", "agent " + agent + " has no explicit context limit",
            details={"kind": "context_limit_unconfigured", "agent": agent})])
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    tokens = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, enable_thinking=False,
                                           return_dict=False)
    # Transformers versions differ in their default return envelope. Count the
    # input IDs, never the number of mapping fields or batch dimensions.
    if isinstance(tokens, Mapping):
        tokens = tokens.get("input_ids")
    if hasattr(tokens, "tolist"):
        tokens = tokens.tolist()
    if isinstance(tokens, list) and len(tokens) == 1 and isinstance(tokens[0], list):
        tokens = tokens[0]
    if not isinstance(tokens, list) or any(type(token) is not int or token < 0 for token in tokens):
        raise UsageError("tokenizer returned an unsupported input-ID shape", [Diagnostic(
            "CONFIGURATION_INVALID", "tokenizer must return one flat integer input-ID list",
            details={"kind": "tokenizer_output_shape", "agent": agent})])
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    record = {"basis": "local tokenizer chat template; native provider usage is compared after response",
        "input_tokens": len(tokens), "declared_max_output_tokens": maximum_output,
        "context_window_tokens": context, "total_budget_tokens": len(tokens) + maximum_output,
        "rendered_prompt_sha256": canonical.digest(rendered.encode()),
        "chat_template_sha256": canonical.digest(tokenizer.get_chat_template().encode()),
        "fits": len(tokens) + maximum_output <= context}
    if not record["fits"]:
        raise UsageError("full proof prompt plus declared output budget exceeds configured context", [Diagnostic(
            "BUDGET_EXHAUSTED", "local tokenization requires " + str(record["total_budget_tokens"]) + " tokens; context is " + str(context),
            severity="infrastructure", details={"kind": "context_budget_exceeded", **record})])
    return record


def compare_frozen_contracts(out, previous_summary, prepared):
    prior_path = Path(previous_summary).resolve()
    prior = canonical.load_file(prior_path)
    prior_cohort = prior_path.parent / "cohort.json"
    if canonical.digest_file(prior_cohort) != canonical.digest_file(out / "cohort.json"):
        raise RuntimeError("comparison cohort bytes differ from the original measurement")
    selected_ids = {case["id"] for case in canonical.load_file(out / "cohort.json")}
    if set(prepared) != selected_ids:
        raise RuntimeError("comparison cannot bind every selected frozen contract before inference")
    for cid, pair in prepared.items():
        old = prior["cases"][cid]["setup"]["model"]
        new = pair["model"][1]
        for key in ("challenge_hash", "required_ids", "expected_statement_hashes"):
            if old[key] != new[key]:
                raise RuntimeError("comparison frozen contract changed: " + cid + "/" + key)
    record = {"status": "IDENTICAL_CONTRACTS", "previous_summary": str(prior_path),
        "previous_summary_sha256": canonical.digest_file(prior_path), "cohort_sha256": canonical.digest_file(prior_cohort),
        "cases": sorted(prepared), "original_results_rewritten": False}
    write(out / "COMPARISON_BEFORE_INFERENCE.json", record)
    return {str(prior_path): record["previous_summary_sha256"], str(prior_cohort): record["cohort_sha256"]}


def failure_taxonomy(result):
    if result.get("accepted"):
        return []
    diagnostics = list(result.get("exception", {}).get("diagnostics", []))
    for key in ("proof_search", "acceptance", "export"):
        diagnostics += result.get(key, {}).get("diagnostics", [])
    kinds = set()
    for diagnostic in diagnostics:
        code, details = diagnostic.get("code"), diagnostic.get("details", {})
        if details.get("kind") in {"context_budget_exceeded", "context_limit_unconfigured", "native_prompt_context_mismatch"}:
            kinds.add("CONTEXT_OR_TOKENIZER_INFRASTRUCTURE")
        elif code == "PROVIDER_FAILURE":
            kinds.add("PROVIDER_TRANSPORT_OR_PROTOCOL")
        elif code == "CONFIGURATION_INVALID":
            kinds.add("CONFIGURATION_FAILURE")
        elif code in {"CLAIM_MUTATION", "STATEMENT_MISMATCH", "INPUT_MUTATION", "IR_REIFICATION_MISMATCH"}:
            kinds.add("FROZEN_CONTRACT_OR_EVIDENCE_REJECTED")
        elif code == "INVALID_CANDIDATE":
            kinds.add("MODEL_RESPONSE_ENVELOPE_OR_FRAGMENT_REJECTED")
        elif diagnostic.get("severity") == "infrastructure":
            kinds.add("VERIFIER_INFRASTRUCTURE")
    attempts = result.get("attempt_evidence", [])
    def protocol_rejected(attempt):
        if "protocol_rejected" in attempt:
            return attempt["protocol_rejected"] is True
        return any(error.startswith("fragment protocol:") for error in attempt.get("errors", []))
    protocol_attempts = [attempt for attempt in attempts if protocol_rejected(attempt)]
    lean_attempts = [attempt for attempt in attempts if not protocol_rejected(attempt)]
    if protocol_attempts:
        kinds.add("MODEL_RESPONSE_ENVELOPE_OR_FRAGMENT_REJECTED")
        if any("proof body is not exactly one Lean term:" in error
               for attempt in protocol_attempts for error in attempt.get("errors", [])):
            kinds.add("FRAGMENT_TERM_SYNTAX_REJECTION")
    if any(a.get("initial_scaffold_preserved") is False for a in lean_attempts):
        kinds.add("MODEL_SOURCE_SCAFFOLD_MISMATCH")
    protocol_errors = {error for attempt in protocol_attempts for error in attempt.get("errors", [])}
    summary_errors = result.get("proof_search", {}).get("summary", {}).get("errors", [])
    if any(error.startswith("fragment protocol:") for error in summary_errors):
        kinds.add("MODEL_RESPONSE_ENVELOPE_OR_FRAGMENT_REJECTED")
    errors = [error for attempt in lean_attempts for error in attempt.get("errors", [])]
    errors += [error for error in summary_errors if error not in protocol_errors and not error.startswith("fragment protocol:")]
    if errors:
        kinds.add("LEAN_ELABORATION_OR_TACTIC_FAILURE")
    if any("unknown tactic" in error for error in errors):
        kinds.add("LEAN_UNAVAILABLE_TACTIC")
    if any(a.get("ok") and a.get("sorries", 0) for a in lean_attempts):
        kinds.add("LEAN_ELABORATED_WITH_PROOF_HOLES")
    if result.get("status") == "EXTERNALLY_STOPPED":
        kinds.add("EXTERNAL_STOP")
    if result.get("status") == "EXPORT_FAILURE":
        kinds.add("ACCEPTED_EXPORT_FAILURE")
    if not kinds:
        kinds.add("PROOF_UNRESOLVED" if result.get("status") == "PROOF_UNRESOLVED" else "EVALUATION_FAILURE")
    return sorted(kinds)


def proof_attempt_evidence(pkg):
    log = pkg.path("contract") / "proofs/attempts.jsonl"
    if not log.is_file():
        return []
    challenge = (contract.challenge_dir(pkg) / "Contract.lean").read_text()
    sites = prove.sorry_sites(challenge)
    prefix = challenge[:sites[0]] if sites else challenge
    rows = []
    for line in log.read_bytes().splitlines():
        entry = canonical.loads(line)
        if not entry["generator"].startswith("agent:"):
            continue
        path = pkg.path("contract") / "proofs/proposals" / (entry["proposal_sha256"][7:23] + ".lean")
        submitted = path.read_text()
        rows.append({"proposal_sha256": entry["proposal_sha256"], "source_sha256": entry["source_sha256"],
            "ok": entry["ok"], "complete": entry["complete"], "sorries": entry["sorries"],
            "protocol_rejected": entry["protocol_rejected"] is True if "protocol_rejected" in entry else any(error.startswith("fragment protocol:") for error in entry["errors"]),
            "initial_scaffold_preserved": submitted.startswith(prefix), "errors": entry["errors"]})
    return rows


def stage(directory, name, result):
    write(directory / (name + ".json"), result.to_json())
    return result.status == "PASS"


def prepare_arm(directory, case):
    pkg = Package(directory / "package")
    pkg.ensure("small-prover-" + case["id"] + "-" + directory.name)
    request = directory / "request.txt"
    fsutil.write_once(request, case["request"].encode())
    response = canonical.dumps(case["ast"])
    fsutil.write_once(directory / "formalizer-input.json", response)
    if "source_requirements" in case["ast"]:
        pkg.set_meta("requested", {"tier": 2, "target": "vscore", "endpoint": "restricted_source",
                                  "backend_version": "0.3", "require_state": "PROVED"})
        delivery = next(iter(case["ast"]["source_requirements"].values()))
        entry = next(r for r in delivery["requirements"] if r["tag"] == "entry")
        properties = [r["tag"] for r in delivery["requirements"] if r["tag"] != "entry"]
        source_input = {"schema_version": "0.1", "format": source_policy.FORMAT, "obligations": {
            oid: {"file": entry["file"], "entry": entry["entry"], "arity": entry["arity"],
                  "properties": properties, "value_required": "formula" in case["ast"]["theorems"][binding["theorem"]]}
            for oid, binding in case["ast"]["obligations"].items() if "theorem" in binding}}
        write(directory / "required-source-policy.json", source_input)
        source_policy.stage(pkg, directory / "required-source-policy.json")
    interpretation = {"obligations": case["obligations"],
        "category_review": {kind: "reviewed for this published synthetic proof contract" for kind in agents.DRAFT_CATEGORIES},
        "clauses": [{"quote": case["request"], "disposition": "obligations",
                     "refs": [r["id"] for r in case["obligations"]]}],
        "assumptions": [], "ambiguities": [], "selected_defaults": []}

    def interpreter(data, ref, _routing):
        draft, ledger, problems = agents.assemble_interpretation(interpretation, data, ref)
        if problems:
            raise ValueError(problems)
        return draft, ledger

    def author(ctx):
        compiled = ff.compile_response(response, ctx["records"], "small-prover-" + case["id"],
                                       response_ref="formalizer-input.json")
        if not ff.reconstruct_origin(response, ctx["records"], compiled.source, compiled.formalization, compiled.receipt):
            raise RuntimeError("formal frontend origin replay failed")
        author.last_compiled = compiled
        author.last_origin = {"proposal": compiled.proposal, "receipt": compiled.receipt}
        return compiled.source, compiled.formalization

    events = EventSink(pkg.run_id, pkg.root, quiet=True)
    try:
        if not stage(directory, "interpret", interpret.run(pkg, events, request, mode="software",
                    request_ref=case["id"] + "-request.txt", agent=interpreter)):
            return pkg, {"status": "SETUP_FAILURE", "stage": "interpret"}
        if not stage(directory, "formalize", formalize.run(pkg, events, agent=author, max_attempts=1)):
            return pkg, {"status": "SETUP_FAILURE", "stage": "formalize"}
        frozen, diagnostics = contract.load_frozen(pkg)
        if diagnostics:
            return pkg, {"status": "SETUP_FAILURE", "diagnostics": [d.to_json() for d in diagnostics]}
        statements = contract.frozen_json(pkg, "statements.json")["statements"]
        expected = {oid: statements[oid]["statement_hash"] for oid in statements}
        info = {"status": "FROZEN", "contract_input_root": frozen["contract_input_root"],
                "challenge_hash": canonical.digest_file(contract.challenge_dir(pkg) / "Contract.lean"),
                "expected_statement_hashes": expected,
                "required_ids": sorted(r["id"] for r in case["obligations"] if r["required"]),
                "challenge_files": {p.name: canonical.digest_file(p) for p in contract.challenge_dir(pkg).iterdir() if p.is_file()}}
        write(directory / "frozen-contract.json", info)
        return pkg, info
    finally:
        events.close()


def evaluated_arm(directory, pkg, frozen, args, config, *, portfolio):
    started = time.monotonic()
    result = {"status": "UNFINISHED", "accepted": False, "arm": directory.name, "usage": [],
              "proof_response_format": "deterministic_portfolio" if portfolio else getattr(args, "proof_response_format", "complete_file")}
    events = EventSink(pkg.run_id, pkg.root, quiet=True)
    try:
        check_stop(args)
        agent = None if portfolio else agents.prover_agent(config, pkg, events)
        proof = prove.run(pkg, events, portfolio=portfolio, agent=agent, budget_seconds=0,
                          max_attempts=0 if portfolio else 3)
        stage(directory, "prove", proof)
        result["proof_search"] = proof.to_json()
        if not proof.summary.get("complete"):
            result["status"] = "PROOF_UNRESOLVED"
            return result
        check_stop(args)
        accepted = accept.run(pkg, events)
        stage(directory, "accept", accepted)
        if accepted.status != "PASS":
            result["status"] = "ACCEPTANCE_REJECTED"
            result["acceptance"] = accepted.to_json()
            return result
        exported = export.run(pkg, events)
        stage(directory, "export", exported)
        if exported.status != "PASS":
            result["status"] = "EXPORT_FAILURE"
            result["export"] = exported.to_json()
            return result
        ir, _, cert, diagnostics = export.verified_ir(pkg)
        if diagnostics or ir is None or cert is None:
            raise RuntimeError("accepted IR binding verification failed: " + str([d.to_json() for d in diagnostics]))
        observed = {oid: rec["formal"]["statement_hash"] for oid, rec in ir["obligations"].items()}
        if observed != frozen["expected_statement_hashes"] or sorted(observed) != frozen["required_ids"]:
            raise RuntimeError("accepted obligation inventory or frozen statement hash changed")
        result.update(status="ACCEPTED", accepted=True, accepted_statement_hashes=observed,
                      acceptance_hash=canonical.digest_file(pkg.path("accepted") / "acceptance.json"),
                      accepted_ir_hash=canonical.digest_file(pkg.path("accepted_ir")))
        return result
    except KeyboardInterrupt:
        result["status"] = "EXTERNALLY_STOPPED"
        raise
    except Exception as exc:
        result["status"] = "INFRASTRUCTURE_FAILURE" if type(exc).__name__ in {"InfrastructureError", "UsageError"} else "EVALUATION_FAILURE"
        result["exception"] = record_exception(exc)
        return result
    finally:
        events.close()
        result["attempt_evidence"] = proof_attempt_evidence(pkg)
        result["failure_taxonomy"] = failure_taxonomy(result)
        result["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        write(directory / "result.json", result)


@contextmanager
def usage_capture(out, args, freeze, tokenizer=None):
    """Observe actual returned Completion objects; never replace provider output."""
    original = Broker.call
    rows = []
    def measured(self, agent, instance, system, user, purpose):
        check_stop(args)
        unchanged(freeze)
        started = time.monotonic()
        provider_started = None
        preflight = None
        try:
            if tokenizer is not None:
                preflight = prompt_preflight(tokenizer, self, agent, system, user)
            provider_started = time.monotonic()
            completion = original(self, agent, instance, system, user, purpose)
        except BaseException as exc:
            row = {"agent": agent, "instance": instance, "purpose": purpose,
                   "completed": False, "elapsed_ms": int((time.monotonic() - started) * 1000),
                   "provider_elapsed_ms": int((time.monotonic() - provider_started) * 1000) if provider_started is not None else None,
                   "exception": record_exception(exc), "transcripts": str(self.transcripts),
                   "prompt_preflight": preflight}
            rows.append(row); write(out / "usage.json", rows)
            raise
        row = {"agent": agent, "instance": instance, "purpose": purpose, "completed": True,
               "requested_model": completion.requested_model, "returned_model": completion.returned_model,
               "model_digest_sha256": completion.model_digest_sha256,
               "input_tokens": completion.input_tokens, "output_tokens": completion.output_tokens,
               "elapsed_ms": int((time.monotonic() - started) * 1000), "transcripts": str(self.transcripts),
               "provider_elapsed_ms": int((time.monotonic() - provider_started) * 1000),
               "prompt_preflight": preflight}
        if preflight is not None and completion.input_tokens is not None:
            row["native_input_token_difference"] = completion.input_tokens - preflight["input_tokens"]
            row["native_input_token_comparison"] = "WITHIN_RECORDED_THRESHOLD" if abs(row["native_input_token_difference"]) <= 128 else "SUBSTANTIAL_TEMPLATE_OR_TRUNCATION_DIFFERENCE"
        rows.append(row); write(out / "usage.json", rows)
        unchanged(freeze)
        if preflight is not None and completion.input_tokens is not None and (
            abs(row["native_input_token_difference"]) > 128 or
            completion.input_tokens + preflight["declared_max_output_tokens"] > preflight["context_window_tokens"]):
            raise UsageError("native provider prompt consumption differs substantially from local preflight or exceeds context budget", [Diagnostic(
                "PROVIDER_FAILURE", row["native_input_token_comparison"], severity="infrastructure",
                details={"kind": "native_prompt_context_mismatch", "local_preflight": preflight,
                         "native_input_tokens": completion.input_tokens})])
        return completion
    Broker.call = measured
    try:
        yield rows
    finally:
        Broker.call = original


def configuration(out, args):
    conf = provider_config.load(Path(args.config)) if args.config else canonical.load_file(ROOT / "examples/ollama-review-config.json")
    # This arm measures the prover directly, without any optional routing policy.
    conf.pop("proof_search", None)
    conf.pop("proof_routing", None)
    agent = conf["agents"][conf["roles"]["prover"]]
    response_format = getattr(args, "proof_response_format", "complete_file")
    if response_format == "complete_file":
        agent.pop("proof_response_format", None)
    else:
        agent["proof_response_format"] = response_format
    provider = conf["providers"][agent["provider"]]
    if args.model:
        agent["model_ref"] = args.model
    elif not args.config:
        agent["model_ref"] = "verislop-pythagoras:4b-f16"
    if args.context_window:
        agent["context_window_tokens"] = args.context_window
    if args.max_output_tokens:
        agent["max_output_tokens"] = args.max_output_tokens
    model = agent["model_ref"]
    if model.startswith("env:"):
        model = os.environ.get(model[4:])
        if not model:
            path = "$.agents." + conf["roles"]["prover"] + ".model_ref"
            raise UsageError("the prover model environment reference is unset", [Diagnostic(
                "CONFIGURATION_INVALID", path + ": " + agent["model_ref"] + " is unset",
                details={"path": path, "model_ref": agent["model_ref"]})])
    # Freeze the resolved identifier itself; later environment changes cannot
    # silently redirect this evaluation's model reference.
    agent["model_ref"] = model
    if args.model_digest:
        agent["model_identity"] = {"mode": "pinned", "resolved_model": model,
                                   "model_digest_sha256": args.model_digest}
    provider["request_timeout_seconds"] = None
    profiles = provider_config.load_user_profiles(None)
    if args.endpoint:
        if provider["adapter"] != "ollama":
            raise ValueError("--endpoint is an Ollama override; select an Ollama prover")
        profiles[provider["endpoint_profile"]] = {"adapter": "ollama", "base_url": args.endpoint,
            "auth_scheme": "none", "families": ["ollama_chat"], "region": "explicit evaluation endpoint",
            "auth_check": "GET /api/tags", "allow_insecure_loopback": True}
    profile_payload = {"schema_version": "0.1", "artifact_kind": "endpoint_profiles", "profiles": profiles}
    schema_diagnostics = [Diagnostic("CONFIGURATION_INVALID", schema + " " + issue.path + ": " + issue.message,
                                    details={"schema": schema, "path": issue.path, "issue": issue.message})
        for schema, data in (("review-config", conf), ("endpoint-profiles", profile_payload))
        for issue in schemas.validate(schema, data)]
    if schema_diagnostics:
        raise UsageError("effective provider configuration or endpoint profiles fail schema validation", schema_diagnostics)
    resolved = provider_config.resolve(conf, profiles)
    if any(d.severity == "blocking" for d in resolved.diagnostics):
        raise UsageError("effective provider configuration has blocking semantic diagnostics", resolved.diagnostics)
    write(out / "effective-config.json", conf)
    write(out / "config-home/endpoint-profiles.json", profile_payload)
    return out / "effective-config.json"


def bridge_arm(directory, pkg, case, config, args, run_freeze):
    result = {"status": "UNFINISHED", "accepted": False, "assigns_end_to_end_verified": False, "attempts": []}
    events = EventSink(pkg.run_id, pkg.root, quiet=True)
    started = time.monotonic()
    try:
        source = canonical.dumps(case["bridge_program"])
        relation = canonical.dumps({"schema_version": "0.3", "format": target.RELATION_FORMAT,
            "template": target.TEMPLATE, "source_slot": "vscore-source", "proof_slot": "vscore-proof",
            "bindings": [{"symbol": "adjust", "entry": "adjust"}]})
        spec, _, info = checker.preview(pkg, source, relation, select_readable=True)
        for name, payload in {"program.vscore.json": source, "relation.json": relation,
                              "VeriSlopBridgeGoal.lean": spec.text.encode(), **info["readable_candidate_artifacts"]}.items():
            fsutil.write_once(directory / name, payload)
        certificate = canonical.load_file(pkg.path("accepted") / "acceptance.json")
        ir, _, _, ir_diagnostics = export.verified_ir(pkg)
        if ir_diagnostics or ir is None:
            raise RuntimeError("bridge context has no current accepted IR")
        accepted_profile = canonical.load_file(pkg.root / certificate["artifacts"]["profile"]["path"])
        parameters = {"backend": "verislop.backend.vscore/0.3", "backend_version": "0.3"}
        workflow = agents._vscore_context(pkg, {"parameters": parameters, "ir": ir,
            "profile": accepted_profile, "required_obligations": info["required_obligations"]})
        fixed = {"parameters": workflow["parameters"],
            "source": case["bridge_program"], "source_hash": canonical.digest(source),
            "relation": canonical.loads(relation), "relation_hash": canonical.digest(relation),
            "generated_goal": spec.text, "goal_hash": canonical.digest(spec.text.encode()),
            "accepted_reference": workflow["accepted_reference"],
            "accepted_packages": workflow["accepted_packages"], "accepted_profile": workflow["accepted_profile"],
            "lean_toolchain": workflow["lean_toolchain"],
            "verifier_library": {name: data.decode() for name, data in target.library_sources().items()},
            "refinement_symbols": sorted(spec.refinement_symbols),
            "proof_support": target.proof_support_catalog(), "readable_source_view": info["readable_source_view"]}
        write(directory / "frozen-proof-job.json", fixed)
        frozen_job_hash = canonical.digest_file(directory / "frozen-proof-job.json")
        broker, conf = agents._broker(config, pkg)
        proof_template = "import VeriSlopBridgeGoal\nnamespace VeriSlopBridgeProof\ntheorem edge : VeriSlopBridgeGoal.EdgeProp := by sorry\nend VeriSlopBridgeProof\n"
        proof = proof_template.encode()
        feedback = None
        metadata = dict(info["readable_candidate_artifacts"])
        diagnostics = {k: v for k, v in metadata.items() if k != "support/readable/selection.json"}
        for number in range(1, 4):
            check_stop(args); unchanged(run_freeze)
            if canonical.digest_file(directory / "frozen-proof-job.json") != frozen_job_hash:
                raise RuntimeError("frozen bridge job changed")
            context = {**fixed, "proof_hash": canonical.digest(proof)}
            user = "FIXED VSCORE PROOF CONTEXT (data):\n" + canonical.dumps(context).decode()
            user += "\nCURRENT CANDIDATE PROOF:\n```lean\n" + proof.decode() + "\n```\n"
            if feedback:
                user += "\nACTUAL CHECKER DIAGNOSTICS:\n" + canonical.dumps(feedback).decode()
            response_path = directory / f"attempt-{number}/response.txt"
            try:
                proposed_proof, raw_response = agents._proof_completion(
                    broker, conf, pkg, events, conf["roles"]["prover"], "small-prover/bridge/" + str(number),
                    agents.VSCORE3_PROVER_SYSTEM, user, "generate", proof_template, proof.decode(),
                    agents._proof_text, toolchain_pin=fixed["lean_toolchain"])
            except proof_fragments.FragmentError as exc:
                fsutil.write_once(response_path, exc.response.encode())
                full = agents._vscore_failure_record(exc, source, relation, exc.response.encode())
                full["response_artifact"] = {"path": str(response_path), "sha256": canonical.digest_file(response_path)}
                diagnostic_path = directory / f"attempt-{number}/diagnostics.json"
                write(diagnostic_path, full)
                feedback = agents._vscore_failure_feedback(full, str(diagnostic_path))
                result["attempts"].append({"attempt": number, "preview_passed": False,
                    "protocol_rejected": True, "exception": feedback})
                # Keep the last assembled source as the next baseline. Rejected
                # response text is retained as evidence, never promoted to Lean.
                continue
            proof = proposed_proof.encode()
            fsutil.write_once(response_path, raw_response.encode())
            fsutil.write_once(directory / f"attempt-{number}/Proof.lean", proof)
            try:
                if len(proof) > target.MAX_PROOF_BYTES:
                    raise ValueError("candidate exceeds the existing bridge proof byte limit")
                _, _, checked = checker.preview(pkg, source, relation, proof=proof,
                    readable_selection=info["readable_selection"], readable_diagnostics=diagnostics)
                if checked["proposition_hash"] != info["proposition_hash"]:
                    raise RuntimeError("candidate changed the frozen bridge proposition")
                result["attempts"].append({"attempt": number, "preview_passed": True, "protocol_rejected": False})
            except Exception as exc:
                full = agents._vscore_failure_record(exc, source, relation, proof)
                full["response_artifact"] = {"path": str(response_path), "sha256": canonical.digest_file(response_path)}
                diagnostic_path = directory / f"attempt-{number}/diagnostics.json"
                write(diagnostic_path, full)
                feedback = agents._vscore_failure_feedback(full, str(diagnostic_path))
                result["attempts"].append({"attempt": number, "preview_passed": False,
                    "protocol_rejected": False, "exception": feedback})
                continue
            candidate = directory / "candidate"
            for name, payload in checker.candidate_files("small-prover-refinement", info, source, relation, proof).items():
                fsutil.write_once(candidate / name, payload)
            prepared = prepare.run(pkg, events, Path("proposal.json"), candidate, expected_tier=2, expected_endpoint="restricted_source")
            stage(directory, "prepare", prepared)
            if prepared.status != "PASS":
                result["status"] = "PREPARATION_FAILURE"; break
            accepted = checker.accept(pkg, "small-prover-refinement", events)
            stage(directory, "bridge-accept", accepted)
            result.update(status="ACCEPTED" if accepted.status == "PASS" and accepted.summary.get("semantic_acceptance") else "BRIDGE_REJECTED",
                          accepted=accepted.status == "PASS" and bool(accepted.summary.get("semantic_acceptance")))
            break
        else:
            result["status"] = "PROOF_UNRESOLVED"
        return result
    except KeyboardInterrupt:
        result["status"] = "EXTERNALLY_STOPPED"; raise
    except Exception as exc:
        result.update(status="BRIDGE_SETUP_OR_INFRASTRUCTURE_FAILURE", exception=record_exception(exc))
        return result
    finally:
        events.close()
        result["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        write(directory / "result.json", result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--endpoint")
    parser.add_argument("--model-digest")
    parser.add_argument("--context-window", type=int)
    parser.add_argument("--max-output-tokens", type=int)
    parser.add_argument("--proof-response-format", choices=("complete_file", "theorem_fragment"), default="complete_file")
    parser.add_argument("--tokenizer", type=Path, help="optional local Transformers tokenizer directory; never trims prompts")
    parser.add_argument("--compare-to", type=Path, help="earlier summary.json; require identical cohort/challenge/statement identities before new inference")
    parser.add_argument("--cohort", type=Path, help="published proof-free cohort JSON; default is the six source-defined contracts")
    parser.add_argument("--case", action="append", help="select a case ID; may be repeated")
    parser.add_argument("--prepare-only", action="store_true", help="no inference: freeze setup and run deterministic portfolio baseline")
    parser.add_argument("--bridge", action="store_true", help="after accepted record-enum model contract, evaluate its exact Tier 2 refinement")
    parser.add_argument("--stop-file", type=Path)
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, interrupt)
    out = args.out.resolve()
    if out.exists():
        parser.error("--out must be a new directory; previous evidence is never overwritten")
    cohort = canonical.load_file(args.cohort) if args.cohort else cases()
    ids = [c["id"] for c in cohort]
    if len(ids) != len(set(ids)) or any(not isinstance(x, str) or not x or "/" in x or x in {".", ".."} for x in ids):
        parser.error("cohort IDs must be unique safe path components")
    if args.case and set(args.case) - set(ids):
        parser.error("unknown case IDs: " + str(sorted(set(args.case) - set(ids))))
    selected = [c for c in cohort if not args.case or c["id"] in args.case]
    out.mkdir(parents=True)
    report = {"format": FORMAT, "scope": "proof generation only; frozen synthetic contracts; no interpretation-model or release claim",
              "status": "PREPARING", "prepare_only": args.prepare_only, "model_attempt_limit": 3,
              "proof_response_format": args.proof_response_format,
              "cases": {}, "bridge": None}
    old_config_home = os.environ.get("VERISLOP_CONFIG_HOME")
    try:
        check_stop(args)
        config = configuration(out, args)
        tokenizer, external_inputs = load_prompt_tokenizer(args, out)
        os.environ["VERISLOP_CONFIG_HOME"] = str(out / "config-home")
        write(out / "cohort.json", selected)
        prepared = {}
        for case in selected:
            check_stop(args)
            print("preparing", case["id"], flush=True)
            pair = {}
            for arm in ("portfolio", "model"):
                directory = out / case["id"] / arm
                try:
                    pkg, info = prepare_arm(directory, case)
                    pair[arm] = (pkg, info)
                except Exception as exc:
                    info = {"status": "SETUP_FAILURE", "exception": record_exception(exc)}
                    write(directory / "setup-failure.json", info)
                    pair[arm] = (None, info)
            report["cases"][case["id"]] = {"setup": {a: pair[a][1] for a in pair}}
            if all(pair[a][1]["status"] == "FROZEN" for a in pair):
                if pair["portfolio"][1]["challenge_hash"] != pair["model"][1]["challenge_hash"]:
                    raise RuntimeError("arms do not have identical frozen challenge bytes: " + case["id"])
                prepared[case["id"]] = pair
        if args.compare_to:
            external_inputs.update(compare_frozen_contracts(out, args.compare_to, prepared))
        bound = [p for p in out.rglob("*") if p.is_file() and
                 ("challenge" in p.parts or p.name in {"cohort.json", "effective-config.json", "endpoint-profiles.json", "frozen-contract.json", "prompt-tokenizer-freeze.json", "COMPARISON_BEFORE_INFERENCE.json"})]
        freeze = {"format": FORMAT, "output": str(out), "source_hashes": source_hashes(),
                  "run_inputs": {p.relative_to(out).as_posix(): canonical.digest_file(p) for p in bound},
                  "external_inputs": external_inputs, "proof_response_format": args.proof_response_format,
                  "toolchain": leanbridge.DEFAULT_TOOLCHAIN, "model_calls_before_freeze": 0,
                  "selected_cases": [c["id"] for c in selected], "max_proposals_per_model_job": 3}
        write(out / "FREEZE_BEFORE_INFERENCE.json", freeze)
        report["freeze_sha256"] = canonical.digest_file(out / "FREEZE_BEFORE_INFERENCE.json")
        report["status"] = "RUNNING"; write(out / "summary.json", report)
        with usage_capture(out, args, freeze, tokenizer) as usage:
            for case in selected:
                if case["id"] not in prepared:
                    continue
                for arm in ("portfolio", "model"):
                    if args.prepare_only and arm == "model":
                        report["cases"][case["id"]][arm] = {"status": "NOT_RUN", "accepted": False}
                        continue
                    check_stop(args); unchanged(freeze)
                    print("evaluating", case["id"], arm, flush=True)
                    pkg, info = prepared[case["id"]][arm]
                    start = len(usage)
                    result = evaluated_arm(out / case["id"] / arm, pkg, info, args, config, portfolio=arm == "portfolio")
                    result["usage"] = usage[start:]
                    write(out / case["id"] / arm / "result.json", result)
                    report["cases"][case["id"]][arm] = result
                    write(out / "summary.json", report)
                if args.bridge and case.get("bridge_program"):
                    model = report["cases"][case["id"]].get("model", {})
                    if not model.get("accepted"):
                        report["bridge"] = {"status": "SKIPPED_CONTRACT_NOT_ACCEPTED", "accepted": False}
                    else:
                        start = len(usage)
                        report["bridge"] = bridge_arm(out / case["id"] / "bridge", prepared[case["id"]]["model"][0], case, config, args, freeze)
                        report["bridge"]["usage"] = usage[start:]
            report["usage"] = usage
        unchanged(freeze)
        report["status"] = "PREPARED_NO_INFERENCE" if args.prepare_only else "COMPLETE"
        report["counts"] = {arm: {"selected": len(selected), "setup_ready": len(prepared),
            "evaluated": sum(arm in v and v[arm]["status"] != "NOT_RUN" for v in report["cases"].values()),
            "accepted": sum(bool(v.get(arm, {}).get("accepted")) for v in report["cases"].values())}
            for arm in ("portfolio", "model")}
        completed_usage = [row for row in report.get("usage", []) if row["completed"]]
        report["provider_usage"] = {"completed_calls": len(completed_usage),
            "failed_calls": len(report.get("usage", [])) - len(completed_usage),
            "input_tokens": sum(row["input_tokens"] for row in completed_usage) if all(row["input_tokens"] is not None for row in completed_usage) else None,
            "output_tokens": sum(row["output_tokens"] for row in completed_usage) if all(row["output_tokens"] is not None for row in completed_usage) else None,
            "elapsed_ms": sum(row["elapsed_ms"] for row in report.get("usage", [])),
            "cost_or_savings_claim": None}
        write(out / "summary.json", report)
        print(canonical.dumps({"status": report["status"], "counts": report["counts"], "summary": str(out / "summary.json")}).decode(), flush=True)
        return 0
    except KeyboardInterrupt as exc:
        report.update(status="EXTERNALLY_STOPPED", exception=record_exception(exc))
        write(out / "summary.json", report)
        return 130
    except Exception as exc:
        report.update(status="EVALUATION_INFRASTRUCTURE_FAILURE", exception=record_exception(exc))
        write(out / "summary.json", report)
        print(str(exc), file=sys.stderr, flush=True)
        return 3
    finally:
        if old_config_home is None:
            os.environ.pop("VERISLOP_CONFIG_HOME", None)
        else:
            os.environ["VERISLOP_CONFIG_HOME"] = old_config_home


if __name__ == "__main__":
    raise SystemExit(main())
