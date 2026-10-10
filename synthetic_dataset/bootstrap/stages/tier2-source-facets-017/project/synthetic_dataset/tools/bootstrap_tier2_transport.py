"""Oracle-free copy of the existing exact Sol mailbox transport algorithms.

The generic transport functions/classes are copied unchanged from
sol_data_pipeline_worker.py and luna_worker.py. Only configuration selects the
new Tier 2 restricted-source request. No API identity or token attestation is
claimed, and no inference/review wall deadline is imposed.
"""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from verislop import canonical
from verislop.errors import Diagnostic, InfrastructureError
from verislop.providers.adapters import Completion
from verislop.providers.broker import Broker

MODEL = "gpt-6.1-sol"
MAX_CALLS = 128
MAX_RESPONSE_BYTES = 1 << 20
MAX_ENVELOPE_BYTES = 8 * MAX_RESPONSE_BYTES
PROFILE_ID = "collaboration-simulation"
EMPTY_FINAL_ERROR = {"type": "InfrastructureError", "code": "EMPTY_AGENT_FINAL",
                     "message": "fresh collaboration agent returned an empty exact final"}
SIMULATION_CREDENTIAL = "verislop-local-simulation-nonsecret-placeholder"

def atomic_json(path: Path, value: dict) -> None:
    """Publish a complete JSON document; a reader never sees a partial write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def endpoint_profiles() -> dict:
    """Resolve provider scaffolding without a real service or secret."""
    return {"schema_version": "0.1", "artifact_kind": "endpoint_profiles", "profiles": {
        PROFILE_ID: {"adapter": "openai_compatible",
                     "base_url": "https://collaboration.invalid/v1",
                     "auth_scheme": "bearer", "families": ["chat_completions"],
                     "auth_check": None, "region": "simulation"},
    }}

def _base_configuration() -> dict:
    """The existing mock-compatible configuration pattern, with honest alias policy."""
    return {
        "schema_version": "0.1", "bridge_tier": 0, "endpoint": "test_campaign",
        "providers": {"simulation": {
            "adapter": "openai_compatible", "api_family": "chat_completions",
            "endpoint_profile": PROFILE_ID,
            "credential_ref": "env:VERISLOP_COLLABORATION_UNUSED",
            "concurrency": 1, "request_timeout_seconds": None,
        }},
        "agents": {
            "author": {"provider": "simulation", "model_ref": MODEL,
                       "tool_profile": "candidate_writer", "max_output_tokens": 8192},
            "critic": {"provider": "simulation", "model_ref": MODEL,
                       "tool_profile": "review_readonly", "max_output_tokens": 8192},
        },
        "roles": {role: "author" for role in
                  ("interpreter", "formalizer", "prover", "implementer", "repairer")},
        "review": {
            "checkpoints": ["formal_contract", "release"],
            "require_fixed_model_snapshot": False, "restart_after_repair": "first_tier",
            "budgets": {"max_repair_rounds": 2, "max_provider_retries": 0,
                        "max_calls_per_instance": 16, "max_total_tokens": 1_000_000,
                        "max_wall_seconds_per_tier": 0},
            "review_tiers": [{"id": "R0", "reviewers": [
                {"agent": "critic", "count": 1, "focus": "counterexamples"}],
                "consensus": {"mode": "unanimous", "require_all_responses": True,
                              "max_soft_rejects": 0, "max_abstentions": 0,
                              "blocking_findings_veto": True}}],
        },
        "release": {"require_mechanical_pass": True, "require_all_review_tiers": True,
                    "require_requested_bridge_tier": True},
    }

def configuration() -> dict:
    conf = copy.deepcopy(_base_configuration())
    conf.update(bridge_tier=2, endpoint="restricted_source")
    conf["review"]["budgets"].update(max_calls_per_instance=24, max_total_tokens=524288)
    return conf


def _failure(message: str, code: str = "PROVIDER_FAILURE") -> InfrastructureError:
    return InfrastructureError(message, [Diagnostic(code, message, severity="infrastructure")])

def validate_response(envelope: object, request_id: str, request_sha256: str) -> tuple[str, str]:
    if not isinstance(envelope, dict):
        raise _failure("mailbox response envelope must be an object")
    if envelope.get("transport") != "collaboration" or envelope.get("requested_model") != MODEL:
        raise _failure("mailbox response has the wrong transport or requested model")
    if envelope.get("request_id") != request_id:
        raise _failure("mailbox response belongs to a different request")
    if envelope.get("request_sha256") != request_sha256:
        raise _failure("simulation response request digest does not match")
    agent_task_id = envelope.get("agent_task_id")
    if not isinstance(agent_task_id, str) or not re.fullmatch(r"/root(?:/[a-z0-9_]+)+", agent_task_id):
        raise _failure("mailbox response needs a canonical collaboration agent task ID")
    text = envelope.get("text")
    if not isinstance(text, str):
        raise _failure("mailbox response needs nonempty exact agent final text")
    if "transport_error" in envelope:
        if text != "" or envelope["transport_error"] != EMPTY_FINAL_ERROR:
            raise _failure("mailbox transport error must describe only the exact empty agent final")
    elif not text:
        raise _failure("mailbox response needs nonempty exact agent final text")
    try:
        size = len(text.encode("utf-8", errors="strict"))
    except UnicodeEncodeError:
        raise _failure("mailbox response text is not valid Unicode") from None
    if size > MAX_RESPONSE_BYTES:
        raise _failure("mailbox response exceeds the 1 MiB UTF-8 response limit", "BUDGET_EXHAUSTED")
    return text, agent_task_id

def transport_error_message(envelope: dict) -> str:
    """Bind the native failure log to the exact empty-final receipt, without a Completion."""
    return (f"{EMPTY_FINAL_ERROR['code']}: {EMPTY_FINAL_ERROR['message']} (request {envelope['request_id']}; "
            f"agent {envelope['agent_task_id']}; request digest {envelope['request_sha256']})")

class MailboxTransport:
    """Share finite logical-call accounting across every CLI role and broker."""

    def __init__(self, directory: Path, max_calls: int, poll_seconds: float = 0.25):
        if type(max_calls) is not int or not 1 <= max_calls <= 128:
            raise ValueError("logical-call limit must be between 1 and 128")
        if not 0 < poll_seconds <= 1:
            raise ValueError("mailbox polling interval must be positive and at most one second")
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_calls, self.poll_seconds = max_calls, poll_seconds
        self.lock = threading.Lock()
        self.agent_task_ids: set[str] = set()
        self.state = {"calls": 0, "responses": 0, "transport_errors": 0, "output_bytes": 0,
                      "input_tokens": None, "output_tokens": None,
                      "unknown_usage_calls": 0, "token_usage_available": False,
                      "transport": "collaboration", "requested_model": MODEL,
                      "max_calls": max_calls, "max_response_bytes": MAX_RESPONSE_BYTES}

    def save_usage(self) -> None:
        atomic_json(self.directory / "usage.json", self.state)

    def call(self, broker: Broker, agent: str, instance: str,
             system: str, user: str, purpose: str) -> Completion:
        if any(d.severity == "blocking" for d in broker.r.diagnostics):
            raise _failure("mailbox broker configuration has blocking diagnostics", "CONFIGURATION_INVALID")
        requested_model = broker.model_for(agent)
        if requested_model != MODEL:
            raise _failure("simulation broker requested a model other than gpt-6.1-sol", "CONFIGURATION_INVALID")
        with self.lock:
            if self.state["calls"] >= self.max_calls:
                raise _failure("simulation logical-call budget exhausted", "BUDGET_EXHAUSTED")
            with broker.budget.lock:
                count = broker.budget.calls.get(instance, 0)
                if count >= broker.budget.max_calls_per_instance:
                    raise _failure("simulation instance call budget exhausted", "BUDGET_EXHAUSTED")
                broker.budget.calls[instance] = count + 1
            self.state["calls"] += 1
            self.state["unknown_usage_calls"] += 1
            request_id = f"{self.state['calls']:04d}"
            request_path = self.directory / f"request-{request_id}.json"
            response_path = self.directory / f"response-{request_id}.json"
            if request_path.exists():
                raise _failure("simulation request path already exists; runs cannot overwrite prior requests")
            request = {"format": "verislop.collaboration-request/0.1", "request_id": request_id,
                       "agent": agent, "instance": instance, "purpose": purpose,
                       "system": system, "user": user, "requested_model": MODEL,
                       "transport": "collaboration", "max_response_bytes": MAX_RESPONSE_BYTES,
                       "requested_max_output_tokens": broker.r.agent(agent)["max_output_tokens"],
                       "output_token_limit_enforced": False}
            atomic_json(request_path, request)
            request_bytes = request_path.read_bytes()
            self.save_usage()
        started = time.monotonic()
        try:
            while not response_path.is_file():
                time.sleep(self.poll_seconds)
            if response_path.stat().st_size > MAX_ENVELOPE_BYTES:
                raise _failure("simulation response envelope exceeds the byte limit", "BUDGET_EXHAUSTED")
            response_bytes = response_path.read_bytes()
            try:
                envelope = canonical.loads(response_bytes)
            except (ValueError, UnicodeError):
                raise _failure("simulation response envelope is invalid JSON") from None
            text, agent_task_id = validate_response(envelope, request_id, canonical.digest(request_bytes))
            text_bytes = text.encode("utf-8")
            failed_empty = "transport_error" in envelope
            with self.lock:
                if agent_task_id in self.agent_task_ids:
                    raise _failure("simulation response reused an agent; every call requires a fresh agent")
                self.agent_task_ids.add(agent_task_id)
                self.state["transport_errors" if failed_empty else "responses"] += 1
                self.state["output_bytes"] += len(text_bytes)
                self.save_usage()
            receipt = {
                "format": ("verislop.collaboration-transport-error-receipt/0.1" if failed_empty else
                           "verislop.collaboration-response-receipt/0.1"), "request_id": request_id,
                "request_sha256": canonical.digest(request_bytes),
                "response_sha256": canonical.digest(response_bytes),
                "text_sha256": canonical.digest(text_bytes), "output_bytes": len(text_bytes),
                "agent_task_id": agent_task_id, "requested_model": requested_model,
                "returned_model": None, "input_tokens": None, "output_tokens": None,
                "transport": "collaboration", "model_identity_attested": False,
            }
            if failed_empty:
                receipt["transport_error"] = dict(EMPTY_FINAL_ERROR)
                atomic_json(self.directory / f"transport-error-receipt-{request_id}.json", receipt)
                # Keep the native registered provider diagnostic; the exact subtype
                # is bound in the failure envelope/receipt and diagnostic message.
                raise _failure(transport_error_message(envelope))
            atomic_json(self.directory / f"response-receipt-{request_id}.json", receipt)
            comp = Completion(text, requested_model, None, agent_task_id, None, None)
            broker._log(agent, instance, purpose, requested_model, comp, system, user,
                        text, 1, None, int((time.monotonic() - started) * 1000))
            return comp
        except Exception as exc:
            broker._log(agent, instance, purpose, requested_model, None, system, user,
                        None, 1, str(exc), int((time.monotonic() - started) * 1000))
            raise
