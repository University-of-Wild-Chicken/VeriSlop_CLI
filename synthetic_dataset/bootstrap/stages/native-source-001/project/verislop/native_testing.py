"""Finite actual-call observations for accepted native facets (Tier 0 only).

Static receipts and transfer theorems never supply an effective runtime case.
The sampling description below is an engineering plan, not a formal proposition.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import canonical, dsl
from .targets import python_target as pt


def accepted_packages(ir: dict, directory: Path) -> dict[str, dict]:
    packages = {}
    for oid, rec in ir["obligations"].items():
        ref = rec["formal"]["formula_ref"].rsplit("@", 1)[1]
        raw = (directory / (ref.split(":")[1] + ".json")).read_bytes()
        if canonical.digest(raw) != ref:
            raise ValueError(f"{oid}: accepted expression bytes changed")
        packages[oid] = canonical.loads(raw)
    return packages


def _value(package: dict) -> dict | None:
    if package.get("encoding") == "verislop.contract-facets/0.1":
        return package["value"]
    return package if "formula" in package else None


def sampling_plan(symbol: str, profile: dsl.Profile, ir: dict, packages: dict) -> dict:
    """Common accepted leading guards, with their authoritative package identities."""
    args = profile.symbols[symbol]["args"]
    candidates = []
    for oid, rec in sorted(ir["obligations"].items()):
        value = _value(packages[oid])
        if not value or not rec["required"] or rec["role"] != "guarantee":
            continue
        prefix, body = dsl.prefix(value["formula"])
        if prefix != args or symbol not in dsl.calls(value["formula"]):
            continue
        guards = []
        while body["tag"] == "implies":
            if not dsl.calls(body["left"]):
                guards.append(body["left"])
            body = body["right"]
        candidates.append((oid, guards))
    common = []
    if candidates:
        common = [node for node in candidates[0][1]
                  if all(node in guards for _, guards in candidates)]
    # A sampler's True leaf is never classified as a software success.
    body = {"tag": "true"}
    for guard in reversed(common):
        body = {"tag": "implies", "left": guard, "right": body}
    formula = body
    for sort in reversed(args):
        formula = {"tag": "forall", "sort": sort, "body": formula}
    return {"symbol": symbol, "argument_sorts": args, "guards": common,
            "guard_sources": [{"obligation": oid, "package": canonical.digest_json(packages[oid])}
                              for oid, _ in candidates], "sampling_formula": formula,
            "scope": "finite sample selection only; static source admission covers the whole artifact"}


def execute(facets: list[dict], profile: dsl.Profile, ir: dict, packages: dict, harness: pt.Harness,
            cfg: dict, seed: int, reference_bodies: dict | None) -> dict:
    from .testing import Campaign, Oracle, _js
    symbols = sorted({facet["symbol"] for facet in facets})
    entries = {}
    overall_codes = set()
    overall_counts = {key: 0 for key in ("generated", "effective", "discarded", "indeterminate", "timeouts", "failures")}
    channel_error = None
    for symbol in symbols:
        plan = sampling_plan(symbol, profile, ir, packages)
        sampler = Campaign(plan["sampling_formula"], profile, Oracle(harness, profile, set(symbols)),
                           cfg, seed, reference_bodies)
        counts = {key: 0 for key in overall_counts}
        hashes, counterexamples, reasons = [], [], {}
        calls = 0
        codes = set()
        for vals in sampler.assignments():
            if not sampler.exhaustive and (counts["effective"] >= cfg["cases_per_obligation"] or
                    counts["generated"] >= cfg["cases_per_obligation"] * cfg["max_generated_factor"]):
                break
            counts["generated"] += 1
            observed_calls = []
            try:
                evaluator = sampler._reference_evaluator() if cfg.get("reference_preflight") else dsl.Evaluator(profile, {}, lambda *_: [])
                truths = [evaluator.formula(guard, list(reversed(vals))) for guard in plan["guards"]]
                if any(t.value is False and t.exact for t in truths):
                    counts["discarded"] += 1
                    continue
                if any(t.value is not True or not t.exact for t in truths):
                    raise dsl.BudgetExceeded("native sample guard is indeterminate")
                spec = profile.symbols[symbol]
                encoded = [pt.encode_arg(val, sort, profile) for val, sort in zip(vals, spec["args"])]
                observations = []
                outcomes = []
                for _ in range(2):
                    calls += 1
                    response = harness.call(symbol, encoded, observe=True)
                    observed_calls.append(response)
                    obs = response["observation"]
                    if any("unavailable" in row for row in obs.values()):
                        raise dsl.BudgetExceeded("native in-harness snapshot unavailable")
                    observations.append(obs)
                    if obs["before"]["values"] != encoded or obs["after"] != obs["before"]:
                        raise dsl.TargetFault("frame", "target changed an input-reachable JSON value")
                    if response["op"] == "exception":
                        if response["type"] in ("SystemExit", "KeyboardInterrupt"):
                            raise dsl.TargetFault("exception", "target attempted to exit")
                        outcomes.append({"exception": response["type"], "message": response["message"]})
                    else:
                        result = pt.decode_result(response["value"], spec["result"], profile)
                        outcomes.append({"result": _js(result)})
                if outcomes[0] != outcomes[1]:
                    raise dsl.TargetFault("nondeterminism", "repeat invocations returned different outcomes")
                hashes.append(canonical.digest_json({"args": encoded, "outcomes": outcomes, "observations": observations}))
                counts["effective"] += 1
            except pt.HarnessError as exc:
                counts["timeouts" if exc.kind == "timeout" else "indeterminate"] += 1
                channel_error = {"kind": exc.kind, "message": str(exc)}
                codes.add("TEST_INCOMPLETE")
                break
            except (dsl.BudgetExceeded, pt.WireBudgetExceeded) as exc:
                counts["indeterminate"] += 1
                reasons[str(exc)] = reasons.get(str(exc), 0) + 1
            except (dsl.TargetFault, ValueError) as exc:
                counts["effective"] += 1
                counts["failures"] += 1
                codes.add("NONDETERMINISM" if getattr(exc, "kind", None) == "nondeterminism" else "TEST_FAILURE")
                counterexamples.append({"assignment": _js(tuple(vals)), "reason": str(exc),
                                        "observed_calls": observed_calls})
                break
        domain = None
        if sampler.exhaustive:
            accounted = counts["effective"] + counts["discarded"]
            complete = (sampler.assignments_exhausted and counts["generated"] == sampler.domain["cardinality"])
            domain = {**sampler.domain, "enumeration_complete": bool(complete),
                      "exact_completion": bool(complete and accounted == sampler.domain["cardinality"] and
                                                counts["effective"] > 0 and not counts["failures"])}
            if complete and counts["discarded"] == sampler.domain["cardinality"]:
                codes.add("EMPTY_TEST_CAMPAIGN")
            elif not domain["exact_completion"] and not counts["failures"]:
                codes.add("TEST_INCOMPLETE")
        elif counts["effective"] < cfg["min_effective_cases"] and not counts["failures"]:
            codes.add("EMPTY_TEST_CAMPAIGN")
        if sampler.generation_problem:
            codes.add("TEST_INCOMPLETE")
        entries[symbol] = {"sampling_plan": plan, "counts": counts, "actual_invocations": calls,
                           "observation_root": canonical.digest_json(hashes), "observation_hashes": hashes,
                           "counterexamples": counterexamples, "indeterminate_reasons": reasons,
                           "codes": sorted(codes), **({"domain": domain} if domain else {})}
        for key, count in counts.items():
            overall_counts[key] += count
        overall_codes.update(codes)
        if channel_error:
            break
    if not symbols:
        overall_codes.add("EMPTY_TEST_CAMPAIGN")
    return {"outcome": "FAIL" if overall_codes else "PASS", "codes": sorted(overall_codes),
            "detail": {"counts": overall_counts, "native_runtime": entries,
                       **({"harness_error": channel_error} if channel_error else {})}}
