"""Optional, persisted three-proposal prelude; this module carries no proof authority."""
from __future__ import annotations

from typing import Any
from pathlib import Path

from . import agent_memory, canonical
from .errors import BlockedError, Diagnostic, InfrastructureError, UsageError, blocked

FORMAT = "verislop.proof-routing-state/0.1"
SERVICE_FAILURES = frozenset({"network", "timeout", "rate_limited", "provider_error", "not_found", "bad_response"})


def enabled(conf: dict) -> bool:
    return conf.get("proof_routing", {}).get("enabled") is True


def response_format(conf: dict, agent: str) -> str:
    return conf.get("agents", {}).get(agent, {}).get("proof_response_format", "complete_file")


class Router:
    """Allocate before dispatch, retain bounded current state through existing CAS memory.

    Dispatches with no completion stay consumed on resume. The package's existing
    run lock is the single-writer boundary, as for other authoring stages.
    """
    def __init__(self, broker: Any, conf: dict, pkg: Any, events: Any, job: dict, fallback_budget: int):
        if type(fallback_budget) is not int or fallback_budget < 0:
            raise UsageError("proof fallback budget must be a nonnegative integer")
        self.broker, self.conf, self.pkg, self.events = broker, conf, pkg, events
        self.fallback_budget = fallback_budget
        self.initial = conf["proof_routing"]["initial_agent"]
        self.fallback = conf["roles"]["prover"]
        self.job_hash = canonical.digest_json(job)
        self.stage = "proof-route/" + self.job_hash[7:]
        agents = {name: conf["agents"][name] for name in {self.initial, self.fallback}}
        providers = {}
        for agent in agents.values():
            name = agent["provider"]
            providers[name] = {k: v for k, v in conf["providers"][name].items() if k != "credential_ref"}
        binding = {"routing": conf["proof_routing"], "agents": agents, "providers": providers,
                   "models": {a: broker.model_for(a) for a in agents},
                   "profiles": {p: broker.r.profiles[p] for p in providers},
                   "fallback_budget": fallback_budget,
                   "implementation": {name: canonical.digest((Path(__file__).resolve().parent / name).read_bytes())
                       for name in ("proof_routing.py", "proof_fragments.py", "agents.py", "lean/VeriSlopProofSyntax.lean")}}
        self.binding_hash = canonical.digest_json(binding)
        ref = agent_memory.latest_snapshot(pkg, stage_prefix=self.stage)
        if ref:
            state = canonical.loads(agent_memory.restore(pkg, ref)["payload.json"])
            if (state.get("format") != FORMAT or state.get("job_sha256") != self.job_hash
                    or state.get("binding_sha256") != self.binding_hash):
                raise blocked("STALE_OR_UNBOUND_EVIDENCE", "retained proof-routing job/configuration binding differs")
            self.state = state
            for name, limit in (("initial_used", 3), ("fallback_used", fallback_budget)):
                value = state.get(name)
                if type(value) is not int or not 0 <= value <= limit:
                    raise blocked("STALE_OR_UNBOUND_EVIDENCE", "invalid retained proof-routing counter")
            if state.get("phase") not in {"initial", "fallback"} or type(state.get("pending")) is not bool:
                raise blocked("STALE_OR_UNBOUND_EVIDENCE", "invalid retained proof-routing state")
            if state.get("terminal_failure") is not None:
                failure = state["terminal_failure"]
                classes = {"UsageError": UsageError, "BlockedError": BlockedError,
                           "InfrastructureError": InfrastructureError}
                error_class = classes.get(failure["error_type"], InfrastructureError)
                raise error_class("retained terminal proof-routing failure: " + failure["message"],
                                  [Diagnostic.from_json(d) for d in failure["diagnostics"]])
            if state["pending"]:
                self.state["pending"] = False
                self.state["last_outcome"] = {"kind": "interrupted_dispatch", "attempt": state.get("last_dispatch")}
                self._save()
        else:
            self.state = {"format": FORMAT, "job_sha256": self.job_hash,
                          "binding_sha256": self.binding_hash, "initial_used": 0,
                          "fallback_used": 0, "phase": "initial", "pending": False,
                          "escalation_reason": None, "model_digests": {}}
            self._save()
        self.last_phase = self.state.get("last_dispatch", {}).get("phase")

    def _save(self) -> None:
        agent_memory.capture_context(self.pkg, self.stage, self.state)

    def available(self) -> bool:
        return self.fallback_budget > 0 and (self.state["phase"] == "initial" and self.state["initial_used"] < 3
                or self.state["fallback_used"] < self.fallback_budget)

    def escalate(self, reason: str) -> None:
        if self.state["phase"] == "initial":
            self.state["phase"] = "fallback"
            self.state["escalation_reason"] = reason
            self._save()
            if self.events:
                self.events.emit("progress", "prove", "optional initial prover escalated to configured prover",
                                 details={"job_sha256": self.job_hash, "reason": reason})

    def next(self) -> tuple[str, dict]:
        if self.state["phase"] == "initial" and self.state["initial_used"] >= 3:
            self.escalate("initial_attempts_exhausted")
        if not self.available():
            raise blocked("BUDGET_EXHAUSTED", "proof-routing attempts exhausted")
        phase = self.state["phase"]
        key = phase + "_used"
        self.state[key] += 1
        agent = self.initial if phase == "initial" else self.fallback
        dispatch = {"phase": phase, "ordinal": self.state[key], "agent": agent,
                    "requested_model": self.broker.model_for(agent)}
        self.state["last_dispatch"] = dispatch
        self.state["pending"] = True
        self.last_phase = phase
        self._save()
        return agent, dispatch

    def completion(self, comp: Any) -> None:
        dispatch = self.state["last_dispatch"]
        digest = getattr(comp, "model_digest_sha256", None)
        if digest is not None:
            previous = self.state["model_digests"].get(dispatch["agent"])
            if previous is not None and previous != digest:
                raise blocked("STALE_OR_UNBOUND_EVIDENCE", "proof-routing model digest changed between attempts")
            self.state["model_digests"][dispatch["agent"]] = digest
        self.state["pending"] = False
        self.state["last_outcome"] = {"kind": "response", "response_sha256": canonical.digest(comp.text.encode()),
                                      "returned_model": getattr(comp, "returned_model", None),
                                      "model_digest_sha256": digest,
                                      "input_tokens": getattr(comp, "input_tokens", None),
                                      "output_tokens": getattr(comp, "output_tokens", None)}
        self._save()

    def failure(self, exc: Exception) -> bool:
        diags = getattr(exc, "diagnostics", [])
        outcome = {"kind": "failure", "error_type": type(exc).__name__,
                   "diagnostics": [d.to_json() for d in diags], "message": str(exc)}
        if self.state.get("terminal_failure") == outcome:
            return False
        self.state["pending"] = False
        self.state["last_outcome"] = outcome
        fallback = (self.last_phase == "initial" and isinstance(exc, InfrastructureError)
                    and bool(diags) and all(d.code == "PROVIDER_FAILURE"
                    and d.details.get("kind") in SERVICE_FAILURES
                    and d.details.get("binding_failure") is not True for d in diags))
        if not fallback:
            self.state["terminal_failure"] = dict(self.state["last_outcome"])
        self._save()
        if fallback:
            self.escalate("initial_provider_failure")
        return fallback

    def context_rejected(self, message: str) -> None:
        self.state["pending"] = False
        self.state["last_outcome"] = {"kind": "context_protocol_rejected", "message": message,
                                      "call_dispatched": False}
        self._save()

    def evaluation(self, complete: bool, diagnostics: Any = None) -> None:
        self.state["last_evaluation"] = {"complete": complete, "diagnostics_sha256":
                                          canonical.digest_json(diagnostics if diagnostics is not None else [])}
        self._save()

    def summary(self) -> dict:
        return {"job_sha256": self.job_hash, "initial_attempts": self.state["initial_used"],
                "fallback_attempts": self.state["fallback_used"],
                "escalation_reason": self.state["escalation_reason"]}


def create(broker: Any, conf: dict, pkg: Any, events: Any, job: dict, fallback_budget: int) -> Router | None:
    if not enabled(conf) or fallback_budget == 0:
        return None
    return Router(broker, conf, pkg, events, job, fallback_budget)
