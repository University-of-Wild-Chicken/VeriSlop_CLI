"""Optional, persisted local proof/refinement stages; no proof authority."""
from __future__ import annotations

from typing import Any
from pathlib import Path

from . import agent_memory, canonical
from .errors import BlockedError, Diagnostic, InfrastructureError, UsageError, blocked

FORMAT = "verislop.proof-routing-state/0.2"
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
        self.refinement = conf["proof_routing"].get("refinement_agent")
        self.refinement_budget = conf["proof_routing"].get("refinement_attempts", 0)
        self.limits = {"initial": 3, "refinement": self.refinement_budget, "fallback": fallback_budget}
        self.fallback = conf["roles"]["prover"]
        self.job_hash = canonical.digest_json(job)
        self.stage = "proof-route/" + self.job_hash[7:]
        agents = {name: conf["agents"][name] for name in {self.initial, self.refinement, self.fallback} if name is not None}
        providers = {}
        for agent in agents.values():
            name = agent["provider"]
            providers[name] = {k: v for k, v in conf["providers"][name].items() if k != "credential_ref"}
        binding = {"routing": conf["proof_routing"], "agents": agents, "providers": providers,
                   "models": {a: broker.model_for(a) for a in agents},
                   "profiles": {p: broker.r.profiles[p] for p in providers},
                   "fallback_budget": fallback_budget,
                   "implementation": {name: canonical.digest((Path(__file__).resolve().parent / name).read_bytes())
                       for name in ("proof_routing.py", "proof_fragments.py", "proof_focus.py", "agents.py", "lean/VeriSlopProofSyntax.lean")}}
        self.binding_hash = canonical.digest_json(binding)
        self._feedback = None
        ref = agent_memory.latest_snapshot(pkg, stage_prefix=self.stage)
        if ref:
            retained = agent_memory.restore(pkg, ref)
            state = canonical.loads(retained["payload.json"])
            if (state.get("format") != FORMAT or state.get("job_sha256") != self.job_hash
                    or state.get("binding_sha256") != self.binding_hash):
                raise blocked("STALE_OR_UNBOUND_EVIDENCE", "retained proof-routing job/configuration binding differs")
            self.state = state
            for name, limit in ((phase + "_used", limit) for phase, limit in self.limits.items()):
                value = state.get(name)
                if type(value) is not int or not 0 <= value <= limit:
                    raise blocked("STALE_OR_UNBOUND_EVIDENCE", "invalid retained proof-routing counter")
            if state.get("phase") not in self.limits or type(state.get("pending")) is not bool:
                raise blocked("STALE_OR_UNBOUND_EVIDENCE", "invalid retained proof-routing state")
            if state.get("feedback_sha256") is not None:
                data = retained.get("feedback.json")
                if data is None or canonical.digest(data) != state["feedback_sha256"]:
                    raise blocked("STALE_OR_UNBOUND_EVIDENCE", "retained proof feedback is missing or changed")
                self._feedback = canonical.loads(data)
                if self._feedback.get("job_sha256") != self.job_hash:
                    raise blocked("STALE_OR_UNBOUND_EVIDENCE", "retained proof feedback belongs to another job")
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
                          "refinement_used": 0, "fallback_used": 0, "phase": "initial", "pending": False,
                          "escalation_reason": None, "transitions": [], "model_digests": {}, "feedback_sha256": None}
            self._save()
        self.last_phase = self.state.get("last_dispatch", {}).get("phase")

    def _save(self) -> None:
        extra = {"feedback.json": canonical.dumps(self._feedback)} if self._feedback is not None else {}
        agent_memory.capture_context(self.pkg, self.stage, self.state, extra_artifacts=extra)

    @property
    def proposal_limit(self) -> int:
        return sum(self.limits.values())

    def feedback(self) -> dict | None:
        """Latest actual rejection, restored with the immutable job, never a critique vote."""
        return self._feedback

    def available(self) -> bool:
        phases = list(self.limits)
        remaining = phases[phases.index(self.state["phase"]):]
        return self.fallback_budget > 0 and any(self.state[p + "_used"] < self.limits[p] for p in remaining)

    def escalate(self, reason: str) -> None:
        previous = self.state["phase"]
        if previous != "fallback":
            self.state["phase"] = "refinement" if previous == "initial" and self.refinement_budget else "fallback"
            self.state["escalation_reason"] = reason
            self.state["transitions"].append({"from": previous, "to": self.state["phase"], "reason": reason})
            self._save()
            if self.events:
                self.events.emit("progress", "prove", "proof route advanced to " + self.state["phase"],
                                 details={"job_sha256": self.job_hash, "reason": reason, "phase": self.state["phase"]})

    def next(self) -> tuple[str, dict]:
        while self.state["phase"] != "fallback" and self.state[self.state["phase"] + "_used"] >= self.limits[self.state["phase"]]:
            self.escalate(self.state["phase"] + "_attempts_exhausted")
        if not self.available():
            raise blocked("BUDGET_EXHAUSTED", "proof-routing attempts exhausted")
        phase = self.state["phase"]
        key = phase + "_used"
        self.state[key] += 1
        agent = {"initial": self.initial, "refinement": self.refinement, "fallback": self.fallback}[phase]
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
        context_failure = bool(diags) and all(d.code == "PROVIDER_FAILURE"
            and d.details.get("kind") == "context_budget_exceeded"
            and d.details.get("call_dispatched") is False for d in diags)
        if context_failure:
            outcome["call_dispatched"] = False
        if self.state.get("terminal_failure") == outcome:
            return False
        self.state["pending"] = False
        self.state["last_outcome"] = outcome
        fallback = (self.last_phase in {"initial", "refinement"} and isinstance(exc, InfrastructureError)
                    and bool(diags) and all(d.details.get("binding_failure") is not True for d in diags)
                    and (context_failure or all(d.code == "PROVIDER_FAILURE"
                    and d.details.get("kind") in SERVICE_FAILURES for d in diags)))
        if not fallback:
            self.state["terminal_failure"] = dict(self.state["last_outcome"])
        self._save()
        if fallback:
            self.escalate(self.last_phase + ("_context_budget_exceeded" if context_failure else "_provider_failure"))
        return fallback

    def context_rejected(self, message: str) -> None:
        self.state["pending"] = False
        self.state["last_outcome"] = {"kind": "context_protocol_rejected", "message": message,
                                      "call_dispatched": False}
        self._save()

    def evaluation(self, complete: bool, diagnostics: Any = None, *, candidate: str | None = None,
                   response: str | None = None) -> None:
        self.state["last_evaluation"] = {"complete": complete, "diagnostics_sha256":
                                          canonical.digest_json(diagnostics if diagnostics is not None else [])}
        if not complete and candidate is not None:
            self._feedback = {"job_sha256": self.job_hash, "dispatch": self.state.get("last_dispatch"),
                              "candidate": candidate, "raw_response": response,
                              "diagnostics": diagnostics if diagnostics is not None else []}
            self.state["feedback_sha256"] = canonical.digest_json(self._feedback)
        self._save()

    def summary(self) -> dict:
        return {"job_sha256": self.job_hash, "initial_attempts": self.state["initial_used"],
                "refinement_attempts": self.state["refinement_used"],
                "fallback_attempts": self.state["fallback_used"],
                "escalation_reason": self.state["escalation_reason"], "transitions": self.state["transitions"]}


def create(broker: Any, conf: dict, pkg: Any, events: Any, job: dict, fallback_budget: int) -> Router | None:
    if not enabled(conf) or fallback_budget == 0:
        return None
    return Router(broker, conf, pkg, events, job, fallback_budget)
