"""Three-task supplemental collaboration transport for the strict native CLI.

This worker substitutes only Broker.call with the existing mailbox simulation.
It does not call a provider API, claim model attestation, construct positive
artifacts or bypass any interpretation/Lean/implementation/review/closure gate.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from verislop import canonical, cli
from verislop.providers.broker import Broker
from synthetic_dataset.tools.data_pipeline_oracle import TASKS
from synthetic_dataset.tools.luna_worker import MailboxTransport
from synthetic_dataset.tools.run_data_pipeline_poc import write_once

MAX_CALLS = 32


def cli_argv(cohort: Path, task: str) -> list[str]:
    from synthetic_dataset.tools.check_data_pipeline_poc import PROTOCOL
    if task not in TASKS:
        raise ValueError("Task is outside the fixed three-task supplemental experiment")
    return ["run", "--runs-dir", str(cohort / task / "runs"), "--run-id", task.lower(),
            "--prompt-file", str(PROTOCOL / f"{task}.txt"), "--request-ref", f"data-pipelines/{task}.txt",
            "--mode", "software", "--tier", "0", "--target", "python", "--endpoint", "test_campaign",
            "--require-state", "TESTED", "--require-tests", "--non-interactive", "--policy", "strict",
            "--config", str(cohort / "config.json"), "--budget-seconds", "0", "--repair-rounds", "2",
            "--seed", "20261008", "--cases", "32", "--json", "--quiet"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--task", required=True, choices=TASKS)
    args = parser.parse_args(argv)
    from synthetic_dataset.tools.luna_data_pipeline_poc import verify_inputs
    cohort = args.cohort.absolute()
    verify_inputs(cohort)
    directory = cohort / args.task
    transport = MailboxTransport(directory / "mailbox", MAX_CALLS)
    invoked = cli_argv(cohort, args.task)
    write_once(directory / "cli-invocation.json", {"argv": invoked,
        "transport": "collaboration-agent-simulation", "positive_candidate_arguments": []})
    original_call = Broker.call

    def simulated_call(broker, agent, instance, system, user, purpose):
        return transport.call(broker, agent, instance, system, user, purpose)

    Broker.call = simulated_call
    try:
        code = cli.main(invoked)
        write_once(directory / "worker-result.json", {"status": "CLI_RETURNED", "exit_code": code,
            "usage": transport.state, "model_identity_attested": False})
        return code
    except KeyboardInterrupt:
        write_once(directory / "worker-result.json", {"status": "INTERRUPTED", "usage": transport.state})
        return 130
    except Exception as exc:
        write_once(directory / "worker-result.json", {"status": "WORKER_ERROR", "usage": transport.state,
            "error": {"type": type(exc).__name__, "message": str(exc)}})
        print(canonical.dumps({"error": type(exc).__name__, "message": str(exc)}).decode(), file=sys.stderr)
        return 3
    finally:
        Broker.call = original_call
        transport.save_usage()


if __name__ == "__main__":
    raise SystemExit(main())
