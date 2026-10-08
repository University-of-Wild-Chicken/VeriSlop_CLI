"""Explicitly opted-in, bounded inference probes through the real provider broker.

This checks a single plain-text JSON challenge, not general agent reliability, native
structured-output/tool capabilities, model alias equivalence, or formal correctness.
No call is made without ``live=True``. Probe completions are never written to transcripts.
"""

from __future__ import annotations

import copy
import secrets
from pathlib import Path
from typing import Any

from .. import auth, canonical
from ..errors import Diagnostic, InfrastructureError, UsageError
from ..stage import StageResult, status_from
from . import config as cfg
from .adapters import Completion, _contains_secret
from .broker import Broker, Budget

MAX_AGENTS = 16
MAX_OUTPUT_TOKENS = 1024
MAX_TIMEOUT_SECONDS = 30
SYSTEM_PROMPT = (
    "You are checking a text-generation API connection. Reply with exactly the JSON "
    "object supplied by the user. Do not call tools, add Markdown, or add explanation."
)


def _problem(agent: str, provider: str, kind: str, message: str, *,
             severity: str = "blocking", configuration: bool = False) -> Diagnostic:
    return Diagnostic("CONFIGURATION_INVALID" if configuration else "PROVIDER_FAILURE",
                      f"agent {agent}, provider {provider}: {message}", severity=severity,
                      details={"agent": agent, "provider": provider, "kind": kind})


def _check(comp: Completion, challenge: str, output_limit: int) -> tuple[str | None, str | None]:
    try:
        value = canonical.loads(comp.text)
    except (canonical.CanonicalJSONError, ValueError, RecursionError):
        return "invalid_json", "completion was not one strict JSON value; response body suppressed"
    if (not isinstance(value, dict) or set(value) != {"ok", "challenge"}
            or value.get("ok") is not True or value.get("challenge") != challenge):
        return "challenge_mismatch", "completion did not match the supplied JSON challenge; response body suppressed"
    if not comp.returned_model:
        return "model_metadata_missing", "provider omitted returned model identity"
    if comp.input_tokens is None or comp.output_tokens is None:
        return "usage_metadata_missing", "provider omitted input or output token usage"
    if comp.output_tokens > output_limit:
        return "output_budget_exceeded", "provider reported output usage above the requested bound"
    return None, None


def run(config_path: Path, agents: list[str], *, live: bool = False,
        profiles: Path | None = None, max_output_tokens: int = 128) -> StageResult:
    """Probe exactly the selected agent profiles, once each, with no transport retries.

    ``live`` must be explicitly true; this operation may incur inference charges. All
    selected configuration/model/credential references are checked before the first call.
    Unselected providers need no credentials or endpoint and cannot incur requests.
    """
    if not live:
        raise UsageError("providers probe requires --live: this explicitly opts in to bounded inference calls that may incur charges")
    if (not agents or len(agents) > MAX_AGENTS or len(set(agents)) != len(agents)
            or any(not isinstance(agent, str) or not agent for agent in agents)):
        raise UsageError(f"select between 1 and {MAX_AGENTS} distinct agents with --agent")
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= MAX_OUTPUT_TOKENS:
        raise UsageError(f"--max-output-tokens must be between 1 and {MAX_OUTPUT_TOKENS}")

    conf = cfg.load(config_path)
    for agent in agents:
        if agent not in conf["agents"]:
            raise UsageError(f"unknown probe agent {agent!r}")
        if conf["agents"][agent]["provider"] not in conf["providers"]:
            raise UsageError(f"agent {agent!r} references an unknown provider")

    # cfg.resolve consumes an internal configuration projection. Synthetic role labels
    # mark every explicitly selected agent as used; no release/reviewer roles are run.
    scoped = copy.deepcopy(conf)
    scoped["agents"] = {a: scoped["agents"][a] for a in agents}
    selected_providers = {a["provider"] for a in scoped["agents"].values()}
    scoped["providers"] = {p: scoped["providers"][p] for p in selected_providers}
    scoped["roles"] = {f"probe-{i}": a for i, a in enumerate(agents)}
    scoped["review"]["review_tiers"] = []
    for agent in scoped["agents"].values():
        agent["max_output_tokens"] = min(agent["max_output_tokens"], max_output_tokens)
    for provider in scoped["providers"].values():
        provider["request_timeout_seconds"] = min(provider["request_timeout_seconds"], MAX_TIMEOUT_SECONDS)
    resolved = cfg.resolve(scoped, cfg.load_user_profiles(profiles))
    result = StageResult("providers probe", "PASS", "selected agents pass one bounded JSON inference/metadata probe; no formal or general agent assurance")
    result.diagnostics.extend(resolved.diagnostics)
    entries: dict[str, Any] = {}
    result.summary = {
        "probe_kind": "bounded_json_inference", "live": True, "may_incur_model_call": True,
        "inference_calls_attempted": 0, "completed_responses": 0, "max_retries": 0,
        "max_output_tokens": max_output_tokens, "timeout_cap_seconds": MAX_TIMEOUT_SECONDS,
        "response_recording": "metadata only; response bodies are not retained",
        "asserts_model_alias_equivalence": False, "asserts_agent_task_correctness": False,
        "agents": entries,
    }
    broker = Broker(resolved, transcript_dir=None, budget=Budget(
        max_calls_per_instance=1, max_total_tokens=len(agents) * (MAX_OUTPUT_TOKENS + 1024), max_retries=0))
    # Credentials stay in this process and are never copied into any result or hash.
    # Retaining the selected set during the probe also detects cross-provider echoes.
    probe_secrets: set[str] = set()
    try:
        for name in agents:
            agent = resolved.agent(name)
            provider = agent["provider"]
            prov = resolved.provider(provider)
            entry: dict[str, Any] = {
                "provider": provider, "adapter": prov["adapter"], "api_family": prov["api_family"],
                "endpoint_profile": prov["endpoint_profile"], "credential_ref": prov.get("credential_ref", "none"),
                "effective_max_output_tokens": agent["max_output_tokens"],
                "effective_timeout_seconds": prov["request_timeout_seconds"],
                "inference_check": "NOT_RUN",
            }
            entries[name] = entry
            try:
                unauthenticated = resolved.profiles.get(provider, {}).get("auth_scheme") == "none"
                secret = "" if unauthenticated else auth.resolve(prov.get("credential_ref", "none"))
                if secret:
                    probe_secrets.add(secret)
                entry["credential"] = "not required (unauthenticated Ollama server)" if unauthenticated else "resolves"
                del secret
            except (LookupError, InfrastructureError):
                entry["credential"] = "unavailable"
                result.diagnostics.append(_problem(name, provider, "credential_unavailable", "credential reference does not resolve", configuration=True))
            try:
                entry["requested_model"] = broker.model_for(name)
            except UsageError:
                result.diagnostics.append(_problem(name, provider, "model_unavailable", "explicit model reference does not resolve", configuration=True))
        # Reject accidental use of a credential as a model or other public configuration
        # value before transmitting a request or exposing that value in diagnostics.
        if any(_contains_secret(result.to_json(), secret) for secret in probe_secrets):
            raise UsageError("credential material found in probe configuration metadata; no inference request was made")
        if any(d.severity in {"blocking", "infrastructure"} for d in result.diagnostics):
            result.status = status_from(result.diagnostics)
            result.lines = ["inference probe not run: selected configuration, models, or credentials are unresolved"]
            return result

        for name in agents:
            entry = entries[name]
            provider = entry["provider"]
            challenge = secrets.token_hex(8)
            user = "Return only this JSON object:\n" + canonical.dumps({"ok": True, "challenge": challenge}).decode()
            result.summary["inference_calls_attempted"] += 1
            try:
                comp = broker.call(name, f"conformance-{name}", SYSTEM_PROMPT, user, "provider-inference-conformance")
            except InfrastructureError as exc:
                # Never pass through provider-controlled exception text. Stable category
                # and numeric HTTP status are enough to diagnose this narrow probe.
                detail = next((d.details for d in exc.diagnostics if d.details), {})
                kind = detail.get("kind", "provider_failure")
                safe_kinds = {"auth_invalid", "rate_limited", "quota_exhausted", "not_found", "provider_error",
                              "network", "timeout", "bad_response", "bad_request", "credential_leak"}
                kind = kind if kind in safe_kinds else "provider_failure"
                entry.update({"inference_check": "FAIL", "failure_kind": kind})
                if type(detail.get("status")) is int:
                    entry["http_status"] = detail["status"]
                result.diagnostics.append(_problem(name, provider, kind, f"inference request failed ({kind}); response body suppressed", severity="infrastructure"))
                continue
            result.summary["completed_responses"] += 1
            if any(_contains_secret(vars(comp), secret) for secret in probe_secrets):
                entry.update({"inference_check": "FAIL", "failure_kind": "credential_leak"})
                result.diagnostics.append(_problem(name, provider, "credential_leak", "credential material detected in completion; all response metadata suppressed"))
                continue
            entry.update({"returned_model": comp.returned_model, "request_id": comp.request_id,
                          "usage": {"input_tokens": comp.input_tokens, "output_tokens": comp.output_tokens}})
            if comp.model_digest_sha256 is not None:
                entry["model_digest_sha256"] = comp.model_digest_sha256
            kind, message = _check(comp, challenge, entry["effective_max_output_tokens"])
            if kind:
                entry.update({"inference_check": "FAIL", "failure_kind": kind})
                result.diagnostics.append(_problem(name, provider, kind, message or "probe did not pass"))
                continue
            entry["inference_check"] = "PASS"
            entry["model_identity"] = "exact" if comp.returned_model == entry["requested_model"] else "different; alias equivalence unverified"
            if comp.returned_model != entry["requested_model"]:
                result.diagnostics.append(_problem(name, provider, "model_alias_unverified",
                    "returned model differs from requested identifier; both are recorded, but alias/snapshot equivalence is not established", severity="warning"))
        result.status = status_from(result.diagnostics)
        result.lines = [f"{name}: {entry['provider']}/{entry['api_family']} inference={entry['inference_check']}"
                        for name, entry in entries.items()]
        return result
    finally:
        probe_secrets.clear()
