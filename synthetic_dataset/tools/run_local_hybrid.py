"""Bounded natural-language Qwen/Pythagoras trial with an explicit Sol mailbox.

Only the Sol transport is substituted. Every local proposal, compiler, acceptance,
IR export, implementation, test and review gate runs through the ordinary CLI.
The controller supplies exact fresh-agent finals; it never supplies solutions.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import gzip
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import threading
import time
from types import SimpleNamespace

from verislop import canonical, cli, fsutil, recovery
from verislop.errors import Diagnostic, EXIT_INTERRUPTED, InfrastructureError, UsageError
from verislop.package import Package
from verislop.providers import config as provider_config
from verislop.providers.broker import Broker
from synthetic_dataset.tools.evaluate_small_prover import load_prompt_tokenizer, prompt_preflight
from synthetic_dataset.tools.luna_data_pipeline_poc import (
    FILE_TOOL_POLICY, WITHHELD_MARKERS, _relay_binding,
)
from synthetic_dataset.tools.sol_data_pipeline_worker import (
    EMPTY_FINAL_ERROR, MODEL, MailboxTransport, SIMULATION_CREDENTIAL,
    atomic_json, validate_response,
)

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = ROOT / "examples/proof-of-concept/data-pipelines"
TASKS = ("P03-unicode-labels", "P01-numeric-batch")
PROJECT_PROMPTS = ROOT / "examples/project-bootstrap"
PROJECT_TASKS = ("G01-inference-admission", "G02-inventory-reconciliation",
                 "G03-telemetry-window", "G04-release-manifest")
TRIAL_MODES = ("tier0-python", "tier2-project")
FORMAT = "verislop.local-hybrid-trial/0.1"


def once(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical.dumps(value))


def failure(message: str, kind: str, **details) -> InfrastructureError:
    return InfrastructureError(message, [Diagnostic("PROVIDER_FAILURE", message,
        severity="infrastructure", details={"kind": kind, **details})])


def source_inventory() -> dict[str, str]:
    paths = [ROOT / "pyproject.toml", ROOT / "docs/local-hybrid-workflow.md",
             ROOT / "docs/bootstrap-local-projects.md",
             ROOT / "docs/bootstrap-string-coverage.md",
             ROOT / "docs/bootstrap-proof-focus.md",
             ROOT / "docs/bootstrap-implementation-context.md",
             ROOT / "docs/bootstrap-review-targets.md",
             ROOT / "docs/bootstrap-surface-authoring.md",
             ROOT / "docs/bootstrap-proof-retention.md",
             ROOT / "docs/bootstrap-critic-capacity.md",
             ROOT / "docs/bootstrap-relation-authoring.md",
             ROOT / "docs/bootstrap-release-context.md"]
    paths += [p for name in ("verislop", "schemas", "formal", "policies", "synthetic_dataset/tools")
              for p in (ROOT / name).rglob("*") if p.is_file() and p.suffix in {".py", ".lean", ".json"}]
    paths += list((ROOT / "synthetic_dataset").glob("*.py"))
    paths += list((ROOT / "grammar").glob("*.ebnf"))
    paths += list((ROOT / "examples/project-bootstrap").glob("*.txt"))
    paths += [ROOT / name for name in ("lean-toolchain", "lakefile.lean", "lake-manifest.json")
              if (ROOT / name).is_file()]
    return {p.relative_to(ROOT).as_posix(): canonical.digest_file(p)
            for p in sorted(set(paths)) if p.is_file()}


def tokenizer_input_inventory(directory: Path) -> dict[str, str]:
    """Bind optional tokenizer inputs' presence as well as their existing bytes."""
    paths = [p for p in directory.iterdir() if p.is_file() and (
        p.name.startswith(("tokenizer", "special_tokens", "added_tokens", "vocab", "merges"))
        or p.name == "config.json")]
    paths += [p for p in directory.rglob("*.jinja") if p.is_file()]
    return {p.relative_to(directory).as_posix(): canonical.digest_file(p) for p in sorted(set(paths))}


def freeze_sources(out: Path, sources: dict[str, str]) -> Path:
    """Retain the exact frozen source bytes before inference, without host metadata."""
    destination = out / "frozen-runtime-source.tar.gz"
    with destination.open("xb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for name, digest in sorted(sources.items()):
                    contents = (ROOT / name).read_bytes()
                    if canonical.digest(contents) != digest:
                        raise ValueError("INPUT_MUTATION: source changed while archiving: " + name)
                    entry = tarfile.TarInfo(name)
                    entry.size = len(contents)
                    entry.mode = 0o644
                    archive.addfile(entry, io.BytesIO(contents))
    return destination


def sol_routes(conf: dict) -> dict[str, list[str]]:
    """Exact simulated agents and purposes, derived only from declared routes."""
    routes = {conf["roles"]["prover"]: ["prove", "prove-vscore"]}
    critic = conf.get("critic_routing", {})
    if critic.get("enabled"):
        routes.setdefault(critic["fallback_agent"], []).append("critic")
    return routes


def mode_parameters(mode: str) -> dict:
    if mode == "tier0-python":
        return {"tier": 0, "target": "python", "required_state": "TESTED", "endpoint": "test_campaign"}
    if mode == "tier2-project":
        return {"tier": 2, "target": "vscore", "required_state": "END_TO_END_VERIFIED",
                "endpoint": "restricted_source", "backend_version": "0.3"}
    raise ValueError("unsupported hybrid trial mode")


def validate_configuration(conf: dict, profiles: dict, pyth_agent: str, *,
                           trial_mode: str = "tier0-python") -> None:
    selected = mode_parameters(trial_mode)
    resolved = provider_config.resolve(conf, profiles["profiles"])
    problems = [d for d in resolved.diagnostics if d.severity == "blocking"]
    if problems:
        raise UsageError("hybrid configuration has blocking diagnostics", problems)
    if conf.get("bridge_tier") != selected["tier"] or conf.get("endpoint") != selected["endpoint"]:
        raise ValueError(f"this trial requires explicit Tier {selected['tier']} {selected['endpoint']}")
    if conf["review"]["checkpoints"] != ["formal_contract", "release"]:
        raise ValueError("this trial freezes formal_contract and release review checkpoints")
    if conf["review"]["budgets"]["max_wall_seconds_per_tier"] != 0:
        raise ValueError("review model generation must have no wall deadline")
    if not all(conf["release"].get(k) is True for k in (
            "require_mechanical_pass", "require_all_review_tiers", "require_requested_bridge_tier")):
        raise ValueError("all native release gates are required")
    if pyth_agent not in conf["agents"]:
        raise ValueError("configured Pythagoras agent is missing")
    if conf["agents"][pyth_agent].get("proof_response_format") != "theorem_fragment":
        raise ValueError("Pythagoras requires theorem_fragment response mode")
    route = conf.get("proof_routing", {})
    if not route.get("enabled"):
        raise ValueError("explicit proof routing must be enabled")
    refinement = route.get("refinement_agent")
    if (route.get("initial_agent") != pyth_agent or route.get("initial_attempts") != 3
            or refinement not in conf["agents"] or route.get("refinement_attempts") != 3
            or conf["agents"][conf["roles"]["prover"]]["model_ref"] != MODEL):
        raise ValueError("this trial requires Pythagoras 3, local refinement 3, then Sol proof fallback")
    qwen_model = conf["agents"][refinement]["model_ref"]
    if qwen_model == MODEL or qwen_model == conf["agents"][pyth_agent]["model_ref"]:
        raise ValueError("local refinement and Pythagoras must designate different local models")
    for role in ("interpreter", "formalizer", "implementer", "repairer"):
        if conf["agents"][conf["roles"][role]]["model_ref"] != qwen_model:
            raise ValueError("proposal, implementation and repair roles must use the configured local refinement model")
    critic = conf.get("critic_routing", {})
    if critic.get("enabled"):
        fallback = conf["agents"][critic["fallback_agent"]]
        if fallback["model_ref"] != MODEL or fallback["tool_profile"] != "review_readonly":
            raise ValueError("this trial's optional critic fallback must be an explicit read-only Sol agent")
    for name, row in conf["agents"].items():
        provider = conf["providers"][row["provider"]]
        if provider.get("request_timeout_seconds") is not None:
            raise ValueError("model requests must have no hard wall timeout")
        if row["model_ref"].startswith("env:"):
            raise ValueError("freeze literal model names before preparing this trial")
        if row["model_ref"] == MODEL:
            if provider.get("credential_ref") != "env:VERISLOP_COLLABORATION_UNUSED":
                raise ValueError("Sol requires the explicit nonsecret simulation credential reference")
            if resolved.profiles[row["provider"]]["base_url"] != "https://collaboration.invalid/v1":
                raise ValueError("Sol requires the explicit collaboration simulation endpoint")
        elif provider["api_family"] != "ollama_chat" or row.get("model_identity", {}).get("mode") != "pinned":
            raise ValueError("every local model must use native Ollama and an explicit immutable digest pin")
    for tier in conf["review"]["review_tiers"]:
        for reviewer in tier["reviewers"]:
            if conf["agents"][reviewer["agent"]]["model_ref"] != qwen_model:
                raise ValueError("this trial's ordinary reviewer membership must use the local proposal model")


def prepare(out: Path, config: Path, profiles: Path, tokenizer: Path, *,
            tasks=None, pyth_agent="pythagoras", native_limit=48, sol_limit=8,
            independent_check=False, qwen_tokenizer: Path | None = None,
            runtime_manifest: Path | None = None, trial_mode: str = "tier0-python") -> dict:
    out = out.absolute()
    selected = mode_parameters(trial_mode)
    allowed_tasks = TASKS if trial_mode == "tier0-python" else PROJECT_TASKS
    tasks = allowed_tasks[:1] if tasks is None else tasks
    if out.exists() or out.is_symlink():
        raise ValueError("trial directory is write-once; select a fresh path")
    if not tasks or len(set(tasks)) != len(tasks) or any(t not in allowed_tasks for t in tasks):
        raise ValueError("select each supported task at most once for the frozen trial mode")
    if trial_mode == "tier2-project" and independent_check:
        raise ValueError("the Python independent checker is not a Tier 2 project checker")
    if not 1 <= native_limit <= 128 or not 1 <= sol_limit <= 128:
        raise ValueError("logical call bounds must be within 1..128")
    conf, prof = provider_config.load(config), canonical.load_file(profiles)
    provider_config.load_user_profiles(profiles)
    validate_configuration(conf, prof, pyth_agent, trial_mode=trial_mode)
    out.mkdir(parents=True)
    once(out / "config.json", conf)
    once(out / "provider-home/endpoint-profiles.json", prof)
    for task in tasks:
        prompt_directory = PROMPTS if trial_mode == "tier0-python" else PROJECT_PROMPTS
        fsutil.write_once(out / "prompts" / f"{task}.txt", (prompt_directory / f"{task}.txt").read_bytes())
    _, external = load_prompt_tokenizer(SimpleNamespace(tokenizer=tokenizer), out)
    tokenizers = [Path(tokenizer).resolve()]
    qwen_freeze = None
    if qwen_tokenizer is not None:
        qwen_directory = out / "qwen-tokenizer"
        qwen_directory.mkdir()
        _, qwen_external = load_prompt_tokenizer(SimpleNamespace(tokenizer=qwen_tokenizer), qwen_directory)
        external.update(qwen_external)
        tokenizers.append(Path(qwen_tokenizer).resolve())
        qwen_freeze = qwen_directory / "prompt-tokenizer-freeze.json"
    # HF can load a separate template file in preference to tokenizer_config.
    # Bind those bytes too, rather than just the rendered template digest.
    for directory in tokenizers:
        for path in directory.rglob("*.jinja"):
            if path.is_file():
                external[str(path)] = canonical.digest_file(path)
    inputs = {p.relative_to(out).as_posix(): canonical.digest_file(p) for p in (
        out / "config.json", out / "provider-home/endpoint-profiles.json", out / "prompt-tokenizer-freeze.json",
        *(out / "prompts" / f"{task}.txt" for task in tasks))}
    if qwen_freeze is not None:
        inputs[qwen_freeze.relative_to(out).as_posix()] = canonical.digest_file(qwen_freeze)
    runtime_binding = None
    if runtime_manifest is not None:
        manifest_path = runtime_manifest.resolve()
        once(out / "runtime-manifest.json", canonical.load_file(manifest_path))
        inputs["runtime-manifest.json"] = canonical.digest_file(out / "runtime-manifest.json")
        external[str(manifest_path)] = canonical.digest_file(manifest_path)
        runtime_binding = {"source": str(manifest_path), "source_sha256": external[str(manifest_path)],
            "retained": "runtime-manifest.json", "authority": "Recorded runtime settings and observations; no independent live-service attestation"}
    sources = source_inventory()
    archive = freeze_sources(out, sources)
    inputs[archive.name] = canonical.digest_file(archive)
    protocol = {"format": FORMAT, "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "tasks": list(tasks), "trial_mode": trial_mode, **selected,
        "contract_repair_rounds": 2, "builtin_tactics": True,
        "model_generation_deadline": None, "proof_search_deadline": None,
        "native_calls_per_task": native_limit, "sol_calls_per_task": sol_limit,
        "pyth_agent": pyth_agent, "tokenizer": str(Path(tokenizer).resolve()),
        "qwen_tokenizer": str(Path(qwen_tokenizer).resolve()) if qwen_tokenizer is not None else None,
        "qwen_agents": [name for name, agent in conf["agents"].items()
                        if name != pyth_agent and agent["model_ref"] != MODEL],
        "prompt_token_count_tolerance": 128, "prompt_capacity_safety_margin": 128,
        "runtime_manifest": runtime_binding,
        "tokenizer_inventories": {str(directory): tokenizer_input_inventory(directory) for directory in tokenizers},
        "independent_check": independent_check, "source_hashes": sources,
        "source_root": canonical.digest_json(sources),
        "source_archive": {"path": archive.name, "sha256": inputs[archive.name], "members": len(sources)},
        "run_inputs": inputs,
        "external_inputs": external, "relay_mode": "file", "tool_policy": FILE_TOOL_POLICY,
        "model_override": MODEL, "fork_turns": "none", "sol_model_identity_attested": False,
        "sol_token_usage_available": False, "fresh_agent_per_sol_call": True,
        "sol_routes": sol_routes(conf),
        "critic_routing": ({**conf["critic_routing"], "primary_protocol_attempts": 2,
                            "trigger": "invalid_primary_critic_protocol_exhausted"}
                           if conf.get("critic_routing", {}).get("enabled") else {"enabled": False}),
        "positive_candidate_arguments": [],
        "scope": ("Natural-language strict Tier 0 TESTED trial; no universal implementation refinement or END_TO_END_VERIFIED claim"
                  if trial_mode == "tier0-python" else
                  "Natural-language strict Tier 2 VSCore 0.3 project component; END_TO_END_VERIFIED only for restricted-source semantics"),
        "origin_audit": "Native transcripts, assembly snapshots and acceptance retained; full supplemental mixed-model origin replay is not performed",
        "limits": ["Builtin tactics may complete proofs without model calls",
                   "Local model digest is checked by the native broker; Sol snapshot and tool restrictions are unattested",
                   "Only declared proof and optional autonomous-critic routes may invoke Sol; ordinary review membership is unchanged",
                   "A valid local critic response is never overridden; other local non-proof stage blocks remain blocks"]}
    once(out / "protocol.json", protocol)
    once(out / "FREEZE_BEFORE_INFERENCE.json", {"format": FORMAT,
        "protocol_sha256": canonical.digest_file(out / "protocol.json"), "generation_started": False})
    verify_inputs(out)
    return protocol


def verify_inputs(out: Path) -> dict:
    protocol = canonical.load_file(out / "protocol.json")
    freeze = canonical.load_file(out / "FREEZE_BEFORE_INFERENCE.json")
    if (freeze.get("format") != FORMAT or protocol.get("format") != FORMAT
            or freeze.get("protocol_sha256") != canonical.digest_file(out / "protocol.json")
            or protocol["source_hashes"] != source_inventory()):
        raise ValueError("INPUT_MUTATION: protocol or runtime changed after freeze")
    mode = protocol.get("trial_mode", "tier0-python")
    if any(protocol.get(key) != value for key, value in mode_parameters(mode).items()):
        raise ValueError("INPUT_MUTATION: assurance mode differs from frozen invocation")
    allowed_tasks = TASKS if mode == "tier0-python" else PROJECT_TASKS
    if (not protocol.get("tasks") or len(protocol["tasks"]) != len(set(protocol["tasks"]))
            or any(task not in allowed_tasks for task in protocol["tasks"])
            or (mode == "tier2-project" and protocol.get("independent_check"))):
        raise ValueError("INPUT_MUTATION: task/checker selection differs from frozen mode")
    for name, digest in protocol["run_inputs"].items():
        if canonical.digest_file(out / name) != digest:
            raise ValueError("INPUT_MUTATION: trial input changed: " + name)
    for name, digest in protocol["external_inputs"].items():
        if canonical.digest_file(Path(name)) != digest:
            raise ValueError("INPUT_MUTATION: tokenizer input changed: " + name)
    for directory, inventory in protocol.get("tokenizer_inventories", {}).items():
        if tokenizer_input_inventory(Path(directory)) != inventory:
            raise ValueError("INPUT_MUTATION: tokenizer input inventory changed: " + directory)
    return protocol


def cli_argv(out: Path, task: str, protocol: dict | None = None) -> list[str]:
    mode = (protocol or {}).get("trial_mode", "tier0-python")
    selected = mode_parameters(mode)
    allowed_tasks = TASKS if mode == "tier0-python" else PROJECT_TASKS
    if task not in allowed_tasks:
        raise ValueError("task is outside the frozen trial mode")
    request_prefix = "data-pipelines" if mode == "tier0-python" else "project-bootstrap"
    argv = ["run", "--runs-dir", str(out / "tasks" / task / "runs"), "--run-id", task.lower(),
        "--prompt-file", str(out / "prompts" / f"{task}.txt"), "--request-ref", f"{request_prefix}/{task}.txt",
        "--mode", "software", "--tier", str(selected["tier"]), "--target", selected["target"],
        "--endpoint", selected["endpoint"], "--require-state", selected["required_state"],
        "--policy", "strict", "--non-interactive",
        "--config", str(out / "config.json"), "--budget-seconds", "0", "--repair-rounds", "2",
        "--json", "--quiet"]
    return argv + (["--require-tests", "--seed", "20261013", "--cases", "32"] if mode == "tier0-python"
                   else ["--backend-version", "0.3", "--no-tests"])


class HybridTransport:
    def __init__(self, out: Path, task: str, protocol: dict, tokenizer, qwen_tokenizer=None):
        self.out, self.task, self.protocol, self.tokenizer = out, task, protocol, tokenizer
        self.qwen_tokenizer = qwen_tokenizer
        if protocol.get("qwen_tokenizer") is not None and qwen_tokenizer is None:
            raise ValueError("frozen Qwen tokenizer is required for this trial")
        self.directory = out / "tasks" / task
        from synthetic_dataset.tools import hybrid_response
        self.mailbox = MailboxTransport(self.directory / "mailbox", protocol["sol_calls_per_task"],
            response_validator=lambda path, envelope: hybrid_response.validate_response(out, task, path, envelope))
        self.lock = threading.Lock()
        self.native_used = 0
        self.rows = []

    def save(self):
        atomic_json(self.directory / "calls.json", {"native_dispatched": self.native_used,
            "sol_token_usage_available": False, "calls": self.rows})

    def call(self, original, broker, agent, instance, system, user, purpose):
        verify_inputs(self.out)
        if any(marker in system or marker in user for marker in WITHHELD_MARKERS):
            raise failure("withheld evaluation material in outbound request", "input_binding", binding_failure=True)
        model = broker.model_for(agent)
        row = {"agent": agent, "model": model, "instance": instance, "purpose": purpose,
               "call_dispatched": False, "completed": False,
               "system_sha256": canonical.digest(system.encode()), "user_sha256": canonical.digest(user.encode())}
        started = time.monotonic()
        with self.lock:
            self.rows.append(row)
            self.save()
        try:
            if model == MODEL:
                if purpose not in self.protocol.get("sol_routes", {}).get(agent, []):
                    raise failure("Sol agent and purpose are not a declared fallback route in this trial",
                                  "route_binding", binding_failure=True)
                row["transport"] = "collaboration"
                row["call_dispatched"] = True
                comp = self.mailbox.call(broker, agent, instance, system, user, purpose)
            else:
                row["transport"] = "native_ollama"
                tokenizer = (self.tokenizer if agent == self.protocol["pyth_agent"] else
                    self.qwen_tokenizer if agent in self.protocol.get("qwen_agents", []) else None)
                if tokenizer is not None:
                    try:
                        row["prompt_preflight"] = prompt_preflight(tokenizer, broker, agent, system, user)
                    except UsageError as exc:
                        if any(d.details.get("kind") == "context_budget_exceeded" for d in exc.diagnostics):
                            details = next(d.details for d in exc.diagnostics if d.details.get("kind") == "context_budget_exceeded")
                            row["prompt_preflight"] = details
                            raise failure(str(exc), "context_budget_exceeded", call_dispatched=False,
                                          prompt_preflight=details) from None
                        raise
                    preflight = row["prompt_preflight"]
                    margin = self.protocol.get("prompt_capacity_safety_margin", 0)
                    preflight["safety_margin_tokens"] = margin
                    if preflight["total_budget_tokens"] + margin > preflight["context_window_tokens"]:
                        raise failure("full prompt plus output budget and tokenizer margin exceeds context",
                            "context_budget_exceeded", call_dispatched=False, prompt_preflight=preflight)
                with self.lock:
                    if self.native_used >= self.protocol["native_calls_per_task"]:
                        raise InfrastructureError("hybrid native logical-call budget exhausted", [Diagnostic(
                            "BUDGET_EXHAUSTED", "native task call limit reached", severity="infrastructure")])
                    self.native_used += 1
                    row["call_dispatched"] = True
                    self.save()
                comp = original(broker, agent, instance, system, user, purpose)
            row.update(completed=True, returned_model=comp.returned_model,
                       model_digest_sha256=comp.model_digest_sha256,
                       input_tokens=comp.input_tokens, output_tokens=comp.output_tokens,
                       response_sha256=canonical.digest(comp.text.encode()))
            preflight = row.get("prompt_preflight")
            if preflight is not None and comp.input_tokens is not None:
                row["native_input_token_difference"] = comp.input_tokens - preflight["input_tokens"]
                if abs(row["native_input_token_difference"]) > self.protocol.get("prompt_token_count_tolerance", 128):
                    raise failure("native prompt usage differs from frozen tokenizer beyond the frozen tolerance",
                                  "tokenizer_mismatch", binding_failure=True)
                if (comp.input_tokens + preflight.get("declared_max_output_tokens", 0)
                        > preflight.get("context_window_tokens", sys.maxsize)):
                    raise failure("native prompt plus reserved output exceeds configured context",
                                  "context_usage_mismatch", binding_failure=True)
            verify_inputs(self.out)
            return comp
        except BaseException as exc:
            row["error"] = {"type": type(exc).__name__, "message": str(exc),
                "diagnostics": [d.to_json() for d in getattr(exc, "diagnostics", [])]}
            raise
        finally:
            row["elapsed_ms"] = int((time.monotonic() - started) * 1000)
            with self.lock:
                self.save()


@contextmanager
def transport_environment(out: Path, transport: HybridTransport):
    old_call = Broker.call
    old_env = {k: os.environ.get(k) for k in ("VERISLOP_CONFIG_HOME", "VERISLOP_COLLABORATION_UNUSED")}
    os.environ["VERISLOP_CONFIG_HOME"] = str(out / "provider-home")
    os.environ["VERISLOP_COLLABORATION_UNUSED"] = SIMULATION_CREDENTIAL
    Broker.call = lambda broker, *args: transport.call(old_call, broker, *args)
    try:
        yield
    finally:
        Broker.call = old_call
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def pending(out: Path) -> dict | None:
    protocol = verify_inputs(out)
    active_path = out / "active-task.json"
    if not active_path.exists():
        return None
    active = canonical.load_file(active_path)
    if active.get("phase") != "generation":
        return None
    task = active["task"]
    if task not in protocol["tasks"]:
        raise ValueError("active task is outside frozen cohort")
    mailbox = out / "tasks" / task / "mailbox"
    for number, path in enumerate(sorted(mailbox.glob("request-*.json")), 1):
        request = canonical.load_file(path)
        rid = f"{number:04d}"
        if request.get("request_id") != rid or path.name != f"request-{rid}.json":
            raise ValueError("mailbox request sequence changed")
        if (mailbox / f"response-{rid}.json").exists():
            continue
        if request.get("requested_model") != MODEL or request.get("transport") != "collaboration":
            raise ValueError("mailbox does not request the explicit Sol transport")
        if any(marker in request["system"] or marker in request["user"] for marker in WITHHELD_MARKERS):
            raise ValueError("withheld evaluation material in mailbox")
        binding = _relay_binding(out, task, path, request, protocol, create_carrier=True)
        return {"task": task, "request_path": str(path), "request_id": rid,
            "request_sha256": canonical.digest_file(path), "protocol_sha256": canonical.digest_file(out / "protocol.json"),
            "model_override": MODEL, "fork_turns": "none", "model_identity_attested": False, **binding}
    return None


def respond(out: Path, envelope: dict) -> dict:
    current = pending(out)
    if current is None:
        raise ValueError("no pending Sol request")
    expected = {key: current[key] for key in ("task", "protocol_sha256", "carrier_path", "carrier_sha256",
        "spawn_message_sha256", "model_override", "fork_turns")}
    if any(envelope.get(key) != value for key, value in expected.items()) or envelope.get("model_identity_attested") is not False:
        raise ValueError("response lacks exact current carrier and protocol binding")
    if envelope.get("text") == "" and "transport_error" not in envelope:
        envelope = {**envelope, "transport_error": dict(EMPTY_FINAL_ERROR)}
    text, agent = validate_response(envelope, current["request_id"], current["request_sha256"])
    for path in (out / "tasks").glob("*/mailbox/response-*.json"):
        if not path.name.startswith("response-receipt-") and canonical.load_file(path).get("agent_task_id") == agent:
            raise ValueError("every Sol request requires a fresh agent")
    destination = Path(current["request_path"]).with_name(f"response-{current['request_id']}.json")
    # Atomic publication prevents the waiting worker from reading partial JSON.
    # A separate exclusive lock also refuses concurrent controller submissions.
    lock = destination.with_suffix(".lock")
    with lock.open("x"):
        if destination.exists():
            raise ValueError("response already exists")
        atomic_json(destination, envelope)
    return {"published": str(destination), "output_bytes": len(text.encode()), "agent_task_id": agent}


def run(out: Path) -> dict:
    protocol = verify_inputs(out)
    once(out / "run-started.json", {"started_at_utc": datetime.now(timezone.utc).isoformat()})
    # Do not rewrite the tokenizer freeze during execution.
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(protocol["tokenizer"], local_files_only=True, trust_remote_code=False)
    qwen_tokenizer = (AutoTokenizer.from_pretrained(protocol["qwen_tokenizer"], local_files_only=True,
        trust_remote_code=False) if protocol.get("qwen_tokenizer") is not None else None)
    results = []
    try:
        for task in protocol["tasks"]:
            verify_inputs(out)
            directory = out / "tasks" / task
            directory.mkdir(parents=True)
            argv = cli_argv(out, task, protocol)
            once(directory / "invocation.json", {"argv": argv, "positive_candidate_arguments": []})
            atomic_json(out / "active-task.json", {"task": task, "phase": "generation"})
            transport = HybridTransport(out, task, protocol, tokenizer, qwen_tokenizer)
            result = {"task": task, "status": "UNFINISHED", "native_pass": False}
            results.append(result)
            with (directory / "stdout.json").open("w") as stdout, (directory / "stderr.log").open("w") as stderr:
                with transport_environment(out, transport), redirect_stdout(stdout), redirect_stderr(stderr):
                    code = cli.main(argv)
            result["exit_code"] = code
            verify_inputs(out)
            result["calls"] = {"native_dispatched": transport.native_used,
                "sol_dispatched": transport.mailbox.state["calls"],
                "pyth_dispatched": sum(row["call_dispatched"] and row["agent"] == protocol["pyth_agent"] for row in transport.rows)}
            if code == EXIT_INTERRUPTED:
                # cli.main intentionally catches SIGINT and can return no JSON.
                # Preserve exact partial output and stop the cohort without parsing
                # it, invoking a checker or treating cancellation as a task failure.
                result.update(status="EXTERNALLY_STOPPED", native_result=None,
                    stdout_sha256=canonical.digest_file(directory / "stdout.json"))
                once(directory / "result.json", result)
                break
            result["native_result"] = canonical.load_file(directory / "stdout.json")
            root = Package(directory / "runs" / task.lower())
            if root.exists():
                active, _, _ = recovery.resolve_active(root)
                result["active_package"] = str(active.root)
                if active.path("report").is_file():
                    report = canonical.load_file(active.path("report"))
                    result["report_sha256"] = canonical.digest_file(active.path("report"))
                    result["terminal_status"] = report.get("terminal_status")
                    result["stages"] = report.get("stages")
                    result["obligations"] = report.get("obligations")
                    if protocol.get("trial_mode", "tier0-python") == "tier2-project":
                        from synthetic_dataset.tools.local_hybrid_tier2 import native_gate, constructor_coverage
                        result["native_audit"] = native_gate(out, task, active, report, result["native_result"], code)
                        result["native_pass"] = result["native_audit"]["status"] == "PASS"
                        if result["native_pass"]:
                            result["source_coverage"] = constructor_coverage(active)
                    else:
                        from synthetic_dataset.tools.check_data_pipeline_poc import native_tested_gate
                        result["native_pass"] = code == 0 and native_tested_gate(report)
            result["status"] = "VERIFIED" if result["native_pass"] else "INFRASTRUCTURE_FAILURE" if code == 3 else "BLOCKED"
            atomic_json(out / "active-task.json", {"task": task, "phase": "generation_complete"})
            if protocol["independent_check"] and result.get("active_package"):
                package = Path(result["active_package"])
                if (package / "implementation").is_dir():
                    command = [sys.executable, "-B", "-m", "synthetic_dataset.tools.check_data_pipeline_poc",
                        "--package", str(package), "--task", task, "--out", str(directory / "independent-check.json")]
                    with (directory / "checker.stdout").open("w") as stdout, (directory / "checker.stderr").open("w") as stderr:
                        checked = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, check=False)
                    result["independent_check_exit_code"] = checked.returncode
                    result["independent_check_receipt"] = str(directory / "independent-check.json")
            once(directory / "result.json", result)
        verify_inputs(out)
        stopped = any(r["status"] == "EXTERNALLY_STOPPED" for r in results)
        summary = {"format": FORMAT, "status": "EXTERNALLY_STOPPED" if stopped else "COMPLETE", "results": results,
            "native_passes": sum(r["native_pass"] for r in results), "tasks": len(protocol["tasks"]),
            "protocol_sha256": canonical.digest_file(out / "protocol.json")}
        atomic_json(out / "summary.json", summary)
        atomic_json(out / "active-task.json", {"phase": "stopped" if stopped else "complete"})
        return summary
    except BaseException as exc:
        atomic_json(out / "summary.json", {"format": FORMAT, "status": "EXTERNALLY_STOPPED" if isinstance(exc, KeyboardInterrupt) else "INFRASTRUCTURE_FAILURE",
            "results": results, "error": {"type": type(exc).__name__, "message": str(exc)}})
        atomic_json(out / "active-task.json", {"phase": "stopped"})
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--out", required=True, type=Path)
    prepare_parser.add_argument("--config", required=True, type=Path)
    prepare_parser.add_argument("--endpoint-profiles", required=True, type=Path)
    prepare_parser.add_argument("--pyth-tokenizer", required=True, type=Path)
    prepare_parser.add_argument("--qwen-tokenizer", type=Path,
        help="optional pinned local tokenizer for full Qwen prompt and output-budget preflight")
    prepare_parser.add_argument("--runtime-manifest", type=Path,
        help="optional JSON runtime settings/probe receipt, retained and hash-bound before inference")
    prepare_parser.add_argument("--pyth-agent", default="pythagoras")
    prepare_parser.add_argument("--trial-mode", choices=TRIAL_MODES, default="tier0-python")
    prepare_parser.add_argument("--tasks", nargs="+", choices=TASKS + PROJECT_TASKS)
    prepare_parser.add_argument("--native-limit", type=int, default=48)
    prepare_parser.add_argument("--sol-limit", type=int, default=8)
    prepare_parser.add_argument("--independent-check", action="store_true")
    for name in ("run", "pending", "respond"):
        command = sub.add_parser(name)
        command.add_argument("--out", required=True, type=Path)
        if name == "respond":
            command.add_argument("--envelope", required=True, type=Path)
        if name == "pending":
            command.add_argument("--metadata-out", type=Path)
    args = parser.parse_args(argv)
    out = args.out.absolute()
    if args.command == "prepare":
        result = prepare(out, args.config, args.endpoint_profiles, args.pyth_tokenizer, tasks=args.tasks,
            pyth_agent=args.pyth_agent, native_limit=args.native_limit, sol_limit=args.sol_limit,
            independent_check=args.independent_check, qwen_tokenizer=args.qwen_tokenizer,
            runtime_manifest=args.runtime_manifest, trial_mode=args.trial_mode)
    elif args.command == "run":
        result = run(out)
    elif args.command == "pending":
        result = pending(out)
        if args.metadata_out:
            once(args.metadata_out, result)
    else:
        result = respond(out, canonical.load_file(args.envelope))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return EXIT_INTERRUPTED if args.command == "run" and result.get("status") == "EXTERNALLY_STOPPED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
