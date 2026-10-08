"""Provider broker: owns credentials, enforces budgets, dispatches scoped tasks to agents.

* Agent prompts, packets and transcripts never contain credentials; outbound prompts are
  scanned for the resolved secret and refused if it appears (defense in depth).
* Budgets are finite: calls per agent instance, total tokens, bounded retries honouring
  retry-after. No silent fallback to a different provider or model.
* Every call is recorded (without secrets) in the run package's agent transcript log with the
  requested and returned model identities.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .. import canonical, fsutil
from ..errors import Diagnostic, InfrastructureError, UsageError
from .adapters import Completion, complete, ollama_model_digest
from .config import Resolved
from .http import ProviderError


@dataclass
class Budget:
    max_calls_per_instance: int = 8
    max_total_tokens: int = 200_000
    max_retries: int = 2
    used_tokens: int = 0
    calls: dict[str, int] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


class Broker:
    def __init__(self, resolved: Resolved, transcript_dir: Path | None, budget: Budget | None = None) -> None:
        self.r = resolved
        self.transcripts = transcript_dir
        b = resolved.conf["review"]["budgets"]
        self.budget = budget or Budget(b["max_calls_per_instance"], b["max_total_tokens"], b["max_provider_retries"])
        self._sem: dict[str, threading.Semaphore] = {
            name: threading.Semaphore(p["concurrency"]) for name, p in resolved.conf["providers"].items()}
        self._seq = 0
        self._lock = threading.Lock()

    def model_for(self, agent: str) -> str:
        ref = self.r.agent(agent)["model_ref"]
        if ref.startswith("env:"):
            val = os.environ.get(ref[4:])
            if not val:
                raise UsageError(f"agent {agent}: model reference {ref} is not set; model identifiers are explicit user configuration",
                                 [Diagnostic("CONFIGURATION_INVALID", f"{ref} unset")])
            return val
        return ref

    def _secret(self, provider: str) -> str:
        from ..auth import resolve

        if self.r.profiles[provider]["auth_scheme"] == "none":
            return ""
        ref = self.r.provider(provider)["credential_ref"]
        try:
            return resolve(ref)
        except LookupError as exc:
            raise InfrastructureError(f"provider {provider}: credential {ref} unavailable: {exc}",
                                      [Diagnostic("PROVIDER_FAILURE", f"credential {ref} unavailable: {exc}", severity="infrastructure")]) from None

    def call(self, agent: str, instance: str, system: str, user: str, purpose: str) -> Completion:
        if any(d.severity == "blocking" for d in self.r.diagnostics):
            raise UsageError("provider configuration has blocking diagnostics", self.r.diagnostics)
        conf = self.r.agent(agent)
        context_tokens = conf.get("context_window_tokens")
        context_options = ({"ollama_context_tokens": context_tokens}
                           if "context_window_tokens" in conf else {})
        provider = conf["provider"]
        prov = self.r.provider(provider)
        profile = self.r.profiles.get(provider)
        if profile is None or not profile.get("base_url"):
            raise UsageError(f"provider {provider} has no resolved endpoint profile")
        model = self.model_for(agent)
        with self.budget.lock:
            n = self.budget.calls.get(instance, 0)
            if n >= self.budget.max_calls_per_instance:
                raise InfrastructureError(f"call budget exhausted for {instance}",
                                          [Diagnostic("BUDGET_EXHAUSTED", f"{instance} reached {n} calls", severity="blocking")])
            if self.budget.used_tokens >= self.budget.max_total_tokens:
                raise InfrastructureError("total token budget exhausted",
                                          [Diagnostic("BUDGET_EXHAUSTED", "total token budget exhausted", severity="blocking")])
            self.budget.calls[instance] = n + 1
        secret = self._secret(provider)
        if secret and (secret in system or secret in user):
            raise InfrastructureError("credential material detected in an outbound prompt; refusing to send",
                                      [Diagnostic("PROVIDER_FAILURE", "credential material in outbound prompt", severity="infrastructure")])
        attempts = 0
        t0 = time.time()
        while True:
            attempts += 1
            try:
                with self._sem[provider]:
                    digest = None
                    if prov["api_family"] == "ollama_chat":
                        digest = ollama_model_digest(profile, model, prov["request_timeout_seconds"], secret)
                        expected = conf.get("model_identity", {}).get("model_digest_sha256")
                        if expected is not None and digest != expected:
                            raise ProviderError("bad_response", "installed Ollama model digest differs from the configured pin")
                    comp = complete(prov["api_family"], profile, secret, model, system, user,
                                    conf["max_output_tokens"], prov["request_timeout_seconds"], **context_options)
                    if digest is not None:
                        if ollama_model_digest(profile, model, prov["request_timeout_seconds"], secret) != digest:
                            raise ProviderError("bad_response", "Ollama model catalog changed during inference")
                        allowed_models = {model, model + ":latest"} if ":" not in model.rsplit("/", 1)[-1] else {model}
                        if comp.returned_model not in allowed_models:
                            raise ProviderError("bad_response", "Ollama returned a different model identifier")
                        comp.model_digest_sha256 = digest
                break
            except ProviderError as exc:
                if not exc.retryable or attempts > self.budget.max_retries:
                    del secret
                    self._log(agent, instance, purpose, model, None, system, user, None, attempts, str(exc),
                              context_window_tokens=context_tokens)
                    raise InfrastructureError(f"provider {provider} ({exc.kind}): {exc.message}",
                                              [Diagnostic("PROVIDER_FAILURE", f"{provider}: {exc}", severity="infrastructure",
                                                          details={"kind": exc.kind, "status": exc.status})]) from None
                time.sleep(min(30.0, exc.retry_after or 2.0 * attempts))
        del secret
        with self.budget.lock:
            self.budget.used_tokens += (comp.input_tokens or 0) + (comp.output_tokens or 0)
        self._log(agent, instance, purpose, model, comp, system, user, comp.text, attempts, None, int((time.time() - t0) * 1000),
                  context_window_tokens=context_tokens)
        return comp

    def _log(self, agent: str, instance: str, purpose: str, model: str, comp: Completion | None, system: str, user: str,
             text: str | None, attempts: int, error: str | None, wall_ms: int = 0,
             *, context_window_tokens: int | None = None) -> None:
        if self.transcripts is None:
            return
        with self._lock:
            self._seq += 1
            seq = self._seq
        entry = {
            "agent": agent, "instance": instance, "purpose": purpose, "requested_model": model,
            "returned_model": comp.returned_model if comp else None, "request_id": comp.request_id if comp else None,
            "model_digest_sha256": comp.model_digest_sha256 if comp else None,
            "attempts": attempts, "error": error, "wall_ms": wall_ms,
            "context_window_tokens": context_window_tokens,
            "system_sha256": canonical.digest(system.encode()), "user_sha256": canonical.digest(user.encode()),
            "system": system, "user": user, "response": text,
        }
        fsutil.write_json(self.transcripts / f"{int(time.time() * 1000)}-{seq:04d}-{instance.replace('/', '_')}.json", entry, pretty=True)
