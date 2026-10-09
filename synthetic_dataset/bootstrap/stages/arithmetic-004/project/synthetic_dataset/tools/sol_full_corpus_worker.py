"""One immutable full-corpus Sol arm; only model transport is substituted."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys
from synthetic_dataset.arm_worker import RAW_SYSTEM
from synthetic_dataset.tools import sol_data_pipeline_worker as transport
from verislop import cli
from verislop.providers import config
from verislop.providers.broker import Broker

MODEL = transport.MODEL
ARMS = ("raw", "verislop")
MAX_CALLS = transport.MAX_CALLS
configuration = transport.configuration
endpoint_profiles = transport.endpoint_profiles


def cli_argv(cohort: Path, task: dict) -> list[str]:
    from synthetic_dataset.build_dataset import ROOT
    directory = cohort / "artifacts" / task["id"] / "verislop"
    return ["run", "--runs-dir", str(directory), "--run-id", "package",
            "--prompt-file", str(ROOT / task["prompt_path"]), "--request-ref", task["prompt_path"],
            "--mode", "software", "--tier", "0", "--target", "python", "--endpoint", "test_campaign",
            "--require-state", "TESTED", "--require-tests", "--non-interactive", "--policy", "strict",
            "--config", str(cohort / "config.json"), "--budget-seconds", "0", "--repair-rounds", "2",
            "--seed", "20261008", "--cases", "32", "--json", "--quiet"]


def execute(cohort: Path, task: dict, arm: str) -> int:
    from synthetic_dataset.build_dataset import ROOT
    from synthetic_dataset.tools.sol_full_corpus import verify_inputs, write_once
    verify_inputs(cohort)
    directory = cohort / "artifacts" / task["id"] / arm
    mailbox = transport.MailboxTransport(directory / "mailbox", 1 if arm == "raw" else MAX_CALLS)
    invoked = cli_argv(cohort, task) if arm == "verislop" else []
    write_once(directory / "cli-invocation.json", {"argv": invoked, "arm": arm,
        "transport": "collaboration-agent-simulation", "positive_candidate_arguments": []})
    old_call = Broker.call
    old_secret = os.environ.get("VERISLOP_COLLABORATION_UNUSED")
    os.environ["VERISLOP_COLLABORATION_UNUSED"] = transport.SIMULATION_CREDENTIAL
    Broker.call = lambda broker, agent, instance, system, user, purpose: mailbox.call(broker, agent, instance, system, user, purpose)
    code, result = 3, {"status": "WORKER_ERROR"}
    try:
        if arm == "raw":
            resolved = config.resolve(config.load(cohort / "config.json"), config.load_user_profiles(None))
            broker = Broker(resolved, directory / "transcripts")
            completion = broker.call("author", "raw/1", RAW_SYSTEM,
                                     (ROOT / task["prompt_path"]).read_text(encoding="utf-8"), "raw-coding")
            try:
                artifact = transport.raw_artifact(completion.text, directory)
            except (ValueError, UnicodeError) as exc:
                code, result = 2, {"status": "INVALID_CANDIDATE", "error": {"type": type(exc).__name__, "message": str(exc)}}
                print(__import__("json").dumps(result), file=sys.stderr, flush=True)
            else:
                result = {"status": "ARTIFACT", "artifact": str(artifact)}
                print(__import__("json").dumps(result), flush=True)
                code = 0
        else:
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
        mailbox.save_usage()
        write_once(directory / "worker-result.json", {**result, "exit_code": code, "usage": mailbox.state,
            "model_identity_attested": False})
    return code


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--task", required=True)
    parser.add_argument("--arm", required=True, choices=ARMS)
    args = parser.parse_args(argv)
    from synthetic_dataset.tools.sol_full_corpus import task_inventory, verify_inputs
    cohort = args.cohort.absolute()
    verify_inputs(cohort)
    task = task_inventory().get(args.task)
    if task is None:
        raise ValueError("Task is outside the frozen original corpus")
    return execute(cohort, task, args.arm)


if __name__ == "__main__":
    raise SystemExit(main())
