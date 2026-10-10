"""One fresh native Tier 2 run; replace only the model transport, never gates."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from synthetic_dataset.tools import bootstrap_tier2_transport as transport
from verislop import cli
from verislop.providers.broker import Broker

MODEL = transport.MODEL


def cli_argv(cohort: Path, task: dict) -> list[str]:
    directory = cohort / "artifacts" / task["id"] / "verislop"
    return ["run", "--runs-dir", str(directory), "--run-id", "package",
            "--prompt-file", str(cohort / task["revised_prompt_path"]),
            "--source-policy", str(cohort / task["source_policy_path"]),
            "--request-ref", task["revised_request_ref"], "--mode", "software",
            "--tier", "2", "--target", "vscore", "--backend-version", "0.3",
            "--endpoint", "restricted_source", "--require-state", "END_TO_END_VERIFIED",
            "--no-tests", "--non-interactive", "--policy", "strict",
            "--config", str(cohort / "config.json"), "--budget-seconds", "0",
            "--repair-rounds", "2", "--json", "--quiet"]


def execute(cohort: Path, task: dict) -> int:
    from synthetic_dataset.tools import bootstrap_tier2 as bootstrap

    bootstrap.verify_inputs(cohort)
    if task not in bootstrap.load(cohort / "protocol.json")["tasks"]:
        raise ValueError("Task is outside the frozen Tier 2 selection")
    directory = cohort / "artifacts" / task["id"] / "verislop"
    mailbox = transport.MailboxTransport(directory / "mailbox", transport.MAX_CALLS)
    invoked = cli_argv(cohort, task)
    bootstrap.write_once(directory / "cli-invocation.json", {
        "argv": invoked, "arm": "verislop", "transport": "collaboration-agent-simulation",
        "positive_candidate_arguments": [], "python_runtime_campaign": False})
    old_call = Broker.call
    old_secret = os.environ.get("VERISLOP_COLLABORATION_UNUSED")
    old_config_home = os.environ.get("VERISLOP_CONFIG_HOME")
    os.environ["VERISLOP_CONFIG_HOME"] = str(cohort / "provider-home")
    os.environ["VERISLOP_COLLABORATION_UNUSED"] = transport.SIMULATION_CREDENTIAL
    Broker.call = lambda broker, agent, instance, system, user, purpose: mailbox.call(
        broker, agent, instance, system, user, purpose)
    code, result = 3, {"status": "WORKER_ERROR"}
    try:
        code = cli.main(invoked)
        result = {"status": "CLI_RETURNED"}
    except KeyboardInterrupt:
        code, result = 130, {"status": "INTERRUPTED"}
    except Exception as exc:
        result = {"status": "WORKER_ERROR", "error": {"type": type(exc).__name__, "message": str(exc)}}
        print(__import__("json").dumps(result), file=sys.stderr, flush=True)
    finally:
        Broker.call = old_call
        if old_secret is None:
            os.environ.pop("VERISLOP_COLLABORATION_UNUSED", None)
        else:
            os.environ["VERISLOP_COLLABORATION_UNUSED"] = old_secret
        if old_config_home is None:
            os.environ.pop("VERISLOP_CONFIG_HOME", None)
        else:
            os.environ["VERISLOP_CONFIG_HOME"] = old_config_home
        mailbox.save_usage()
        bootstrap.write_once(directory / "worker-result.json", {
            **result, "exit_code": code, "usage": mailbox.state,
            "model_identity_attested": False})
    return code


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--task", required=True)
    args = parser.parse_args(argv)
    from synthetic_dataset.tools import bootstrap_tier2 as bootstrap

    cohort = args.cohort.absolute()
    protocol = bootstrap.verify_inputs(cohort)
    task = next((row for row in protocol["tasks"] if row["id"] == args.task), None)
    if task is None:
        raise ValueError("Task is outside the frozen Tier 2 selection")
    return execute(cohort, task)


if __name__ == "__main__":
    raise SystemExit(main())
