"""Fresh-agent Sol 6.1 transport for a frozen paired data-pipeline comparison.

The requested collaboration override is explicit; actual provider identity, token
usage and read restrictions are unattested. Only broker transport is substituted.
Every strict interpretation, Lean, implementation, review and closure gate runs.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

from verislop import canonical, cli
from verislop.agents import extract_json
from verislop.errors import Diagnostic, InfrastructureError
from verislop.providers import config
from verislop.providers.adapters import Completion
from verislop.providers.broker import Broker
from synthetic_dataset.arm_worker import RAW_SYSTEM
from synthetic_dataset.tools import luna_worker as helpers
from synthetic_dataset.tools.data_pipeline_oracle import TASKS
from synthetic_dataset.tools.run_data_pipeline_poc import write_once

MODEL = "gpt-6.1-sol"
ARMS = ("raw", "strict")
MAX_CALLS = 128
MAX_RESPONSE_BYTES = helpers.MAX_RESPONSE_BYTES
MAX_ENVELOPE_BYTES = helpers.MAX_ENVELOPE_BYTES
EMPTY_FINAL_ERROR = helpers.EMPTY_FINAL_ERROR
atomic_json = helpers.atomic_json
endpoint_profiles = helpers.endpoint_profiles
SIMULATION_CREDENTIAL = "verislop-local-simulation-nonsecret-placeholder"


def configuration() -> dict:
    conf = copy.deepcopy(helpers.configuration())
    for row in conf["agents"].values():
        row["model_ref"] = MODEL
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


def cli_argv(cohort: Path, task: str) -> list[str]:
    from synthetic_dataset.tools.check_data_pipeline_poc import PROTOCOL
    if task not in TASKS:
        raise ValueError("Task is outside the fixed paired experiment")
    directory = cohort / "artifacts" / task / "strict"
    return ["run", "--runs-dir", str(directory / "runs"), "--run-id", task.lower(),
            "--prompt-file", str(PROTOCOL / f"{task}.txt"), "--request-ref", f"data-pipelines/{task}.txt",
            "--mode", "software", "--tier", "0", "--target", "python", "--endpoint", "test_campaign",
            "--require-state", "TESTED", "--require-tests", "--non-interactive", "--policy", "strict",
            "--config", str(cohort / "config.json"), "--budget-seconds", "0", "--repair-rounds", "2",
            "--seed", "20261008", "--cases", "32", "--json", "--quiet"]


def raw_artifact(text: str, directory: Path) -> Path:
    """Extract only exact model source bytes; never repair a direct response."""
    value = extract_json(text)
    if (not isinstance(value, dict) or set(value) != {"files"} or not isinstance(value["files"], dict)
            or set(value["files"]) != {"solution.py"} or not isinstance(value["files"]["solution.py"], str)):
        raise ValueError("raw response must contain exactly files.solution.py as a string")
    data = value["files"]["solution.py"].encode("utf-8", errors="strict")
    artifact = directory / "artifact"
    artifact.mkdir()
    with (artifact / "solution.py").open("xb") as stream:
        stream.write(data)
    return artifact


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--task", required=True, choices=TASKS)
    parser.add_argument("--arm", required=True, choices=ARMS)
    args = parser.parse_args(argv)
    from synthetic_dataset.tools.sol_data_pipeline_poc import verify_inputs
    from synthetic_dataset.tools.check_data_pipeline_poc import PROTOCOL
    cohort = args.cohort.absolute()
    verify_inputs(cohort)
    directory = cohort / "artifacts" / args.task / args.arm
    transport = MailboxTransport(directory / "mailbox", 1 if args.arm == "raw" else MAX_CALLS)
    invoked = cli_argv(cohort, args.task) if args.arm == "strict" else []
    write_once(directory / "cli-invocation.json", {"argv": invoked, "arm": args.arm,
        "transport": "collaboration-agent-simulation", "positive_candidate_arguments": []})
    original_call = Broker.call
    original_secret = os.environ.get("VERISLOP_COLLABORATION_UNUSED")
    os.environ["VERISLOP_COLLABORATION_UNUSED"] = SIMULATION_CREDENTIAL
    def simulated_call(broker, agent, instance, system, user, purpose):
        return transport.call(broker, agent, instance, system, user, purpose)
    Broker.call = simulated_call
    try:
        if args.arm == "raw":
            conf = config.load(cohort / "config.json")
            resolved = config.resolve(conf, config.load_user_profiles(None))
            broker = Broker(resolved, directory / "transcripts")
            completion = broker.call("author", "raw/1", RAW_SYSTEM, (PROTOCOL / f"{args.task}.txt").read_text(), "raw-coding")
            artifact = raw_artifact(completion.text, directory)
            result = {"status": "ARTIFACT", "artifact": str(artifact), "usage": transport.state}
            write_once(directory / "worker-result.json", result)
            print(canonical.dumps(result).decode())
            return 0
        code = cli.main(invoked)
        write_once(directory / "worker-result.json", {"status": "CLI_RETURNED", "exit_code": code,
            "usage": transport.state, "model_identity_attested": False})
        return code
    except KeyboardInterrupt:
        write_once(directory / "worker-result.json", {"status": "INTERRUPTED", "usage": transport.state})
        return 130
    except Exception as exc:
        result = {"status": "WORKER_ERROR", "usage": transport.state,
                  "error": {"type": type(exc).__name__, "message": str(exc)}}
        write_once(directory / "worker-result.json", result)
        print(canonical.dumps(result).decode(), file=sys.stderr)
        return 3
    finally:
        Broker.call = original_call
        if original_secret is None:
            os.environ.pop("VERISLOP_COLLABORATION_UNUSED", None)
        else:
            os.environ["VERISLOP_COLLABORATION_UNUSED"] = original_secret
        transport.save_usage()


if __name__ == "__main__":
    raise SystemExit(main())
