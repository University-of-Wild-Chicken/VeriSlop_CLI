"""Run one real raw call or the complete CLI dispatch with observational budget hooks."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from verislop import cli
from verislop.agents import extract_json
from verislop.errors import Diagnostic, InfrastructureError
from verislop.providers import adapters, config
from verislop.providers.broker import Broker, Budget

RAW_SYSTEM = ('You are a software engineering coding agent. Implement the entire requested task in Python 3. '
              'Return only one JSON object {"files":{"solution.py":"<complete source>"}}. '
              'Do not return explanations, tests or placeholders. Define solve(data) exactly as requested.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--arm", choices=["raw", "verislop"], required=True)
    p.add_argument("--task", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--config", required=True, type=Path)
    p.add_argument("--seconds", required=True, type=float)
    p.add_argument("--tokens", required=True, type=int)
    p.add_argument("--calls", required=True, type=int)
    args = p.parse_args()
    if args.seconds < 0:
        p.error("seconds must be nonnegative; 0 disables the generation deadline")
    args.out.mkdir(parents=True, exist_ok=True)
    conf = config.load(args.config)
    started = time.monotonic()
    shared = Budget(max_calls_per_instance=16, max_total_tokens=1_000_000, max_retries=0)
    original_call, original_inference = Broker.call, adapters._inference_request
    state = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "responses": 0,
             "reserved_output_tokens": 0, "unknown_usage_calls": 0}

    def save(name, value):
        (args.out / name).write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False))

    def observed_inference(*a, **kw):
        body, headers = original_inference(*a, **kw)
        state["responses"] += 1
        state["input_tokens"] += body.get("prompt_eval_count", 0) or 0
        state["output_tokens"] += body.get("eval_count", 0) or 0
        save(f"native-response-{state['responses']:02}.json", body)
        save("usage.json", state)
        return body, headers

    def bounded_call(self, agent, instance, system, user, purpose):
        remaining = args.seconds - (time.monotonic() - started) if args.seconds else None
        if state["calls"] >= args.calls or (remaining is not None and remaining <= 0) or state["reserved_output_tokens"] >= args.tokens:
            raise InfrastructureError("benchmark arm budget exhausted", [Diagnostic("BUDGET_EXHAUSTED", "fixed benchmark arm budget exhausted", severity="blocking")])
        state["calls"] += 1
        self.budget = shared
        provider = self.r.agent(agent)["provider"]
        configured_timeout = conf["providers"][provider]["request_timeout_seconds"]
        self.r.provider(provider)["request_timeout_seconds"] = (None if remaining is None else
            max(1, min(remaining, configured_timeout) if configured_timeout is not None else remaining))
        allocation = min(self.r.agent(agent)["max_output_tokens"], args.tokens - state["reserved_output_tokens"])
        self.r.agent(agent)["max_output_tokens"] = allocation
        state["reserved_output_tokens"] += allocation
        save(f"request-{state['calls']:02}.json", {"agent": agent, "instance": instance, "purpose": purpose, "system": system, "user": user})
        save("usage.json", state)
        before_responses, before_output = state["responses"], state["output_tokens"]
        try:
            return original_call(self, agent, instance, system, user, purpose)
        finally:
            if state["responses"] > before_responses:
                state["reserved_output_tokens"] -= max(0, allocation - (state["output_tokens"] - before_output))
            else:
                state["unknown_usage_calls"] += 1
            save("usage.json", state)

    adapters._inference_request = observed_inference
    Broker.call = bounded_call
    try:
        if args.arm == "raw":
            resolved = config.resolve(conf, config.load_user_profiles(None))
            broker = Broker(resolved, args.out / "transcripts", shared)
            comp = broker.call("author", "raw/1", RAW_SYSTEM, args.task.read_text(), "raw-coding")
            obj = extract_json(comp.text)
            files = obj.get("files")
            if not isinstance(files, dict) or set(files) != {"solution.py"} or not isinstance(files["solution.py"], str):
                raise ValueError("raw response must contain exactly files.solution.py as a string")
            artifact = args.out / "artifact"
            artifact.mkdir()
            (artifact / "solution.py").write_text(files["solution.py"])
            save("worker-result.json", {"status": "ARTIFACT", "artifact": str(artifact), "usage": state})
            return 0
        argv = ["run", "--runs-dir", str(args.out), "--run-id", "package", "--prompt-file", str(args.task),
                "--request-ref", args.task.name, "--mode", "software", "--tier", "0", "--target", "python",
                "--endpoint", "test_campaign", "--require-state", "TESTED", "--require-tests",
                "--non-interactive", "--policy", "strict", "--config", str(args.config),
                "--budget-seconds", str(int(args.seconds)), "--repair-rounds", "2",
                "--seed", "20261007", "--cases", "32", "--json", "--quiet"]
        save("cli-invocation.json", {"argv": argv})
        code = cli.main(argv)
        save("worker-result.json", {"status": "CLI_RETURNED", "exit_code": code, "usage": state})
        return code
    except Exception as exc:
        save("worker-result.json", {"status": "WORKER_ERROR", "error": {"type": type(exc).__name__, "message": str(exc)}, "usage": state})
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 2
    finally:
        save("usage.json", state)


if __name__ == "__main__":
    sys.exit(main())
