"""`verislop test`: the frozen Tier 0 property campaign on the exact target artifact (TESTED).

* Inputs: accepted DSL formulas (opaque statements get no fabricated oracle), the structural
  links, and a frozen campaign configuration (seed, generator, counts).
* The target runs in the harness subprocess on hash-verified bytes; the oracle is the DSL
  evaluator (a declared trusted translation of the Lean predicate).
* Cases whose antecedents are false are discarded, not counted. Empty effective campaigns,
  timeouts, harness failures, disabled assertions and skipped obligations never yield PASS.
* Only exact counterexamples are failures; they are minimised and recorded with the seed.
* Finite sampling of an unbounded domain is not a proof; `TESTED` names this campaign only.
"""

from __future__ import annotations

import itertools
import random
from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION, canonical, contract as C, dsl, fsutil
from .errors import Diagnostic
from .events import EventSink
from .export import verified_ir
from .lifecycle import claim_id
from .package import Package
from .stage import StageResult, status_from
from .targets import python_target as pt

VERIFIER = "verislop.python-tier0-campaign"
GENERATOR_ID = "verislop.nat-sampler/0.1"
GENERATOR_ID_V2 = "verislop.data-sampler/0.2"
BOUNDARY = [0, 1, 2, 3, 7, 8, 15, 16, 255, 256, 65535, 65536, 2**31 - 1, 2**31, 2**32 - 1, 2**32,
            2**53, 2**63 - 1, 2**63, 2**64 - 1, 2**64, 2**64 + 1]
NONDETERMINISM_RECHECKS = 64
STRING_BOUNDARY = ["", "a", "é", "e\u0301", "漢字", "🙂", "\x00", "\n", "𝄞"]


def _contains_record(sort: Any) -> bool:
    if not isinstance(sort, dict):
        return False
    if "record" in sort:
        return True
    if "list" in sort:
        return _contains_record(sort["list"])
    if "option" in sort:
        return _contains_record(sort["option"])
    return "result" in sort and any(_contains_record(s) for s in sort["result"].values())


def campaign_config(seed: int, cases: int, timeout_ms: int, profile: dsl.Profile | None = None) -> dict[str, Any]:
    cfg = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "test_campaign",
        "generator": GENERATOR_ID_V2 if pt.profile_id(profile) == pt.PROFILE_ID_V2 else GENERATOR_ID,
        "seed": seed,
        "cases_per_obligation": cases,
        "grid": [0, 1, 2],
        "boundary": [str(b) for b in BOUNDARY],
        "random_mix": {"small_max": 32, "medium_max": 10000, "large_bits": 70, "weights": [60, 25, 15]},
        "hint_probability_percent": 75,
        "max_generated_factor": 20,
        "boundary_probability_percent": 20,
        "inner_samples": 8,
        "min_effective_cases": 20,
        "per_call_timeout_ms": timeout_ms,
        "nondeterminism_rechecks": NONDETERMINISM_RECHECKS,
        "shrink": True,
        "serialization_profile": pt.profile_id(profile),
    }
    if cfg["generator"] == GENERATOR_ID_V2:
        cfg["data_limits"] = {"max_list_length": 8, "max_string_length": 32, "max_field_grid_values": 8,
                              "max_record_grid_values": 20, "max_value_nodes": 4096, "max_value_depth": 32}
        cfg["signed_grid"] = [str(n) for n in (-2, -1, 0, 1, 2, -(2**63), 2**63)]
        cfg["signed_boundary"] = [str(x) for x in [-b for b in reversed(BOUNDARY) if b] + BOUNDARY]
        cfg["unicode_boundary"] = list(STRING_BOUNDARY)
    return cfg


def _js(v: Any) -> Any:
    if type(v) is int:
        return str(v)
    if isinstance(v, tuple):
        return [_js(x) for x in v]
    return v


class Oracle:
    """Binds profile symbols to harness calls with strict python-v0_1 decoding."""

    def __init__(self, harness: pt.Harness, profile: dsl.Profile, bound: set[str]) -> None:
        self.h = harness
        self.p = profile
        self.bound = bound
        self.cache: dict[tuple, Any] = {}
        self.calls = 0
        self.rechecks = 0
        self.nondeterminism: list[dict[str, Any]] = []

    def _raw(self, sym: str, args: list[Any]) -> Any:
        spec = self.p.symbols[sym]
        try:
            enc = [pt.encode_arg(a, s, self.p) for a, s in zip(args, spec["args"])]
        except pt.WireBudgetExceeded as exc:
            raise dsl.BudgetExceeded(str(exc)) from None
        self.calls += 1
        try:
            resp = self.h.call(sym, enc)
        except pt.HarnessError as exc:
            raise dsl.TargetFault("timeout" if exc.kind == "timeout" else "harness", str(exc)) from None
        if resp.get("op") == "exception":
            raise dsl.TargetFault("exception", f"{sym}{tuple(args)} raised {resp['type']}: {resp['message']}")
        try:
            return pt.decode_result(resp["value"], spec["result"], self.p)
        except pt.WireBudgetExceeded as exc:
            raise dsl.BudgetExceeded(str(exc)) from None
        except ValueError as exc:
            raise dsl.TargetFault("malformed", f"{sym}{tuple(args)} returned a value outside {pt.profile_id(self.p)}: {exc}") from None

    def symbols(self) -> dict[str, Any]:
        def make(sym: str):
            def fn(args: list[Any]) -> Any:
                key = (sym, tuple(args))
                if key in self.cache:
                    return self.cache[key]
                v = self._raw(sym, args)
                if self.rechecks < NONDETERMINISM_RECHECKS:
                    self.rechecks += 1
                    again = self._raw(sym, args)
                    if again != v:
                        self.nondeterminism.append({"symbol": sym, "args": _js(tuple(args)), "first": _js(v), "second": _js(again)})
                        raise dsl.TargetFault("nondeterminism", f"{sym}{tuple(args)} returned {v!r} then {again!r}")
                self.cache[key] = v
                return v
            return fn
        return {s: make(s) for s in self.bound}


class Campaign:
    def __init__(self, formula: dict[str, Any], profile: dsl.Profile, oracle: Oracle, cfg: dict[str, Any], seed: int) -> None:
        self.formula = formula
        self.prefix, self.body = dsl.prefix(formula)
        self.p = profile
        self.cfg = cfg
        self.rng = random.Random(seed)
        self.generation_problem: str | None = None
        kwargs = {"sample_candidates": self._sample_candidates} if pt.profile_id(profile) == pt.PROFILE_ID_V2 else {}
        self.ev = dsl.Evaluator(profile, oracle.symbols(), self._inner_candidates, **kwargs)

    def _random_nat(self) -> int:
        mix = self.cfg["random_mix"]
        r = self.rng.randrange(100)
        w = mix["weights"]
        if r < w[0]:
            return self.rng.randint(0, mix["small_max"])
        if r < w[0] + w[1]:
            return self.rng.randint(0, mix["medium_max"])
        return self.rng.getrandbits(mix["large_bits"])

    def _inner_candidates(self, body: dict[str, Any], env: list[Any]) -> list[int]:
        hints = dsl.nat_hints(body, env, self.ev)
        rnd = [self._random_nat() for _ in range(self.cfg["inner_samples"])]
        return hints + [0, 1, 2] + rnd

    def _sample_candidates(self, sort: Any, body: dict[str, Any], env: list[Any]) -> list[Any]:
        if sort == "Nat":
            return self._inner_candidates(body, env)
        values = self._grid_values(sort)
        values.extend(self._value(sort, 0, env) for _ in range(self.cfg["inner_samples"]))
        return list(dict.fromkeys(values))

    def _grid_values(self, sort: Any, depth: int = 0, budget: list[int] | None = None) -> list[Any]:
        """Small deterministic boundary families, never a universal enumeration of data."""
        budget = [self.cfg["data_limits"]["max_value_nodes"]] if budget is None else budget
        budget[0] -= 1
        if budget[0] < 0 or depth > self.cfg["data_limits"]["max_value_depth"]:
            raise dsl.BudgetExceeded("data sampling exceeds its frozen node or depth budget")
        if not _contains_record(sort) and dsl.is_finite(sort, self.p):
            return dsl.finite_values(sort, self.p)
        if sort == "Nat":
            return list(self.cfg["grid"])
        if sort == "Int":
            return [int(n) for n in self.cfg["signed_grid"]]
        if sort == "String":
            return list(self.cfg["unicode_boundary"])
        if "option" in sort:
            return [dsl.option_none_v(), *[dsl.option_some_v(v) for v in
                    self._grid_values(sort["option"], depth + 1, budget)[:4]]]
        if "list" in sort:
            inner = self._grid_values(sort["list"], depth + 1, budget)[:3]
            if not inner:
                return [()]
            a, b = inner[0], inner[-1]
            return list(dict.fromkeys([(), (a,), (b,), (a, a), (a, b), (b, a), (a, b, a), (b, b)]))
        if "record" in sort:
            fields = self.p.records[sort["record"]]["fields"]
            grids = [self._grid_values(f["sort"], depth + 1, budget)[:self.cfg["data_limits"]["max_field_grid_values"]] for f in fields]
            values = [dsl.record_v(sort["record"], [g[i % len(g)] for g in grids]) for i in range(8)]
            # Equal/adjacent numeric fields exercise correlated bounds without inventing a precondition.
            numeric = [i for i, f in enumerate(fields) if f["sort"] in ("Nat", "Int")]
            for anchor in (-1, 0, 1, 2):
                for delta in (0, 1, -1):
                    row = [g[0] for g in grids]
                    for offset, i in enumerate(numeric):
                        n = anchor if offset == 0 else anchor + delta
                        row[i] = max(0, n) if fields[i]["sort"] == "Nat" else n
                    values.append(dsl.record_v(sort["record"], row))
            return list(dict.fromkeys(values))[:self.cfg["data_limits"]["max_record_grid_values"]]
        return [(side, v) for side in ("error", "ok") for v in self._grid_values(sort["result"][side], depth + 1, budget)[:4]]

    def _sub(self, j: int) -> dict[str, Any]:
        f = self.body
        for s in reversed(self.prefix[j + 1:]):
            f = {"tag": "forall", "sort": s, "body": f}
        return f

    def _value(self, sort: Any, j: int, env: list[Any], depth: int = 0, budget: list[int] | None = None) -> Any:
        if pt.profile_id(self.p) == pt.PROFILE_ID_V2:
            budget = [self.cfg["data_limits"]["max_value_nodes"]] if budget is None else budget
            budget[0] -= 1
            if budget[0] < 0 or depth > self.cfg["data_limits"]["max_value_depth"]:
                raise dsl.BudgetExceeded("data sampling exceeds its frozen node or depth budget")
        if not _contains_record(sort) and dsl.is_finite(sort, self.p):
            return self.rng.choice(dsl.finite_values(sort, self.p))
        if sort == "Nat":
            r = self.rng.randrange(100)
            if r < self.cfg["hint_probability_percent"]:
                try:
                    hints = dsl.nat_hints(self._sub(j), env, self.ev)
                except (dsl.TargetFault, dsl.BudgetExceeded):
                    hints = []
                if hints:
                    return self.rng.choice(hints)
            if r < self.cfg["hint_probability_percent"] + self.cfg["boundary_probability_percent"]:
                return self.rng.choice(BOUNDARY)
            return self._random_nat()
        if sort == "Int":
            if self.rng.randrange(100) < self.cfg["boundary_probability_percent"]:
                return int(self.rng.choice(self.cfg["signed_boundary"]))
            else:
                n = self._random_nat()
            return n if self.rng.randrange(2) else -n
        if sort == "String":
            if self.rng.randrange(2):
                return self.rng.choice(self.cfg["unicode_boundary"])
            size = self.rng.choice([n for n in [0, 1, 2, 5, 16, 32] if n <= self.cfg["data_limits"]["max_string_length"]])
            return "".join(self.rng.choice("abé漢🙂\x00") for _ in range(size))
        if "option" in sort:
            return (dsl.option_none_v() if self.rng.randrange(2) == 0 else
                    dsl.option_some_v(self._value(sort["option"], j, env, depth + 1, budget)))
        if "list" in sort:
            if depth >= 8:
                return ()
            size = self.rng.choice([n for n in [0, 1, 2, 3, 4, 8] if n <= self.cfg["data_limits"]["max_list_length"]])
            values = tuple(self._value(sort["list"], j, env, depth + 1, budget) for _ in range(size))
            if values and self.rng.randrange(3) == 0:
                values = (values[0],) * size
            return values
        if "record" in sort:
            fields = self.p.records[sort["record"]]["fields"]
            row = [self._value(f["sort"], j, env, depth + 1, budget) for f in fields]
            numeric = [i for i, f in enumerate(fields) if f["sort"] in ("Nat", "Int")]
            if len(numeric) > 1 and self.rng.randrange(2):
                anchor = row[numeric[0]]
                for i in numeric[1:]:
                    n = anchor + self.rng.choice([-1, 0, 1])
                    row[i] = max(0, n) if fields[i]["sort"] == "Nat" else n
            return dsl.record_v(sort["record"], row)
        side = self.rng.choice(["ok", "error"])
        inner = sort["result"][side]
        return (side, self._value(inner, j, env, depth + 1, budget))

    def assignments(self):
        """Grid first, then seeded random/hint-guided cases; ends when the space is exhausted.

        The caller stops after enough effective cases or when the discard budget is spent.
        """
        seen: set[tuple] = set()
        limit = self.cfg["cases_per_obligation"] * self.cfg["max_generated_factor"]
        grid_sets = []
        try:
            for s in self.prefix:
                grid_sets.append(self._grid_values(s) if pt.profile_id(self.p) == pt.PROFILE_ID_V2 else
                                 (dsl.finite_values(s, self.p) if dsl.is_finite(s) else (list(self.cfg["grid"]) if s == "Nat" else [])))
        except dsl.BudgetExceeded as exc:
            self.generation_problem = str(exc)
            return
        if not self.prefix:
            yield []
            return
        if all(grid_sets):
            for combo in itertools.product(*grid_sets):
                if combo not in seen:
                    seen.add(combo)
                    yield list(combo)
                    if len(seen) >= limit:
                        return
        duplicates = 0
        while duplicates < 1000:
            vals: list[Any] = []
            try:
                for j, s in enumerate(self.prefix):
                    vals.append(self._value(s, j, list(reversed(vals))))
            except dsl.BudgetExceeded as exc:
                self.generation_problem = str(exc)
                return
            key = tuple(vals)
            if key in seen:
                duplicates += 1
                continue
            duplicates = 0
            seen.add(key)
            yield vals
            if len(seen) >= limit:
                return

    def classify(self, vals: list[Any]) -> tuple[str, str]:
        env = list(reversed(vals))
        f = self.body
        try:
            while f["tag"] == "implies":
                a = self.ev.formula(f["left"], env)
                if a.value is False and a.exact:
                    return "discarded", "antecedent false"
                if a.value is not True or not a.exact:
                    return "indeterminate", f"antecedent {a}"
                f = f["right"]
            t = self.ev.formula(f, env)
        except dsl.TargetFault as exc:
            if exc.kind == "timeout":
                return "timeout", exc.detail
            return "fail", exc.detail
        except dsl.BudgetExceeded as exc:
            return "indeterminate", str(exc)
        if t.value is True and t.exact:
            return "pass", str(t)
        if t.value is False and t.exact:
            return "fail", "consequent is false"
        return "indeterminate", f"consequent {t}"

    def shrink(self, vals: list[Any]) -> list[Any]:
        """Minimise each Nat binder (others fixed): try 0, then binary-search the failure threshold."""
        best = list(vals)
        for _ in range(4):
            changed = False
            for j, s in enumerate(self.prefix):
                if s != "Nat" and pt.profile_id(self.p) == pt.PROFILE_ID_V2:
                    for small in itertools.islice(self._shrinks(best[j], s), 32):
                        trial = list(best)
                        trial[j] = small
                        if small != best[j] and self.classify(trial)[0] == "fail":
                            best, changed = trial, True
                            break
                    continue
                if s != "Nat" or best[j] == 0:
                    continue
                trial = list(best)
                trial[j] = 0
                if self.classify(trial)[0] == "fail":
                    best, changed = trial, True
                    continue
                lo, hi = 0, best[j]  # classify(lo) passes (or is not a failure), classify(hi) fails
                for _ in range(80):
                    if hi - lo <= 1:
                        break
                    mid = (lo + hi) // 2
                    trial = list(best)
                    trial[j] = mid
                    if self.classify(trial)[0] == "fail":
                        hi = mid
                    else:
                        lo = mid
                if hi < best[j]:
                    best[j], changed = hi, True
            if not changed:
                break
        return best

    def _shrinks(self, value: Any, sort: Any):
        if sort in ("Nat", "Int"):
            yield 0
            yield abs(value) // 2 * (-1 if value < 0 else 1)
        elif sort == "String":
            yield ""
            yield value[:len(value) // 2]
        elif isinstance(sort, dict) and "option" in sort:
            if value != dsl.option_none_v():
                yield dsl.option_none_v()
                for small in self._shrinks(value[1], sort["option"]):
                    yield dsl.option_some_v(small)
        elif isinstance(sort, dict) and "list" in sort:
            yield ()
            yield value[:len(value) // 2]
            yield value[:-1]
            if value:
                for small in self._shrinks(value[0], sort["list"]):
                    yield (small,) + value[1:]
        elif isinstance(sort, dict) and "record" in sort:
            for i, field in enumerate(self.p.records[sort["record"]]["fields"]):
                for small in self._shrinks(value[2][i], field["sort"]):
                    row = list(value[2])
                    row[i] = small
                    yield dsl.record_v(sort["record"], row)
        elif isinstance(sort, dict) and "result" in sort:
            for small in self._shrinks(value[1], sort["result"][value[0]]):
                yield (value[0], small)


def execute(impl: Path, link: dict[str, Any], claims: dict[str, Any], irj: dict[str, Any], profile: dsl.Profile,
            cfg: dict[str, Any], expressions_dir: Path, prerequisites: dict[str, list[str]]) -> dict[str, Any]:
    """Run the frozen campaign on an implementation directory; no evidence is written here."""
    inv = pt.inventory(impl)
    bound = {b["symbol"]: (b["implementation_object"]["file"], b["implementation_object"]["qualname"]) for b in link["bindings"]}
    required = [c for c in claims["claims"] if c["milestone"] == "TESTED" and c["applicable"]]
    out: dict[str, Any] = {"obligations": {}, "harness_error": None, "files": inv.files}
    try:
        harness = pt.Harness(impl, {f: h for f, h in inv.files.items() if f.endswith(".py")}, bound,
                             per_call_timeout=cfg["per_call_timeout_ms"] / 1000)
    except pt.HarnessError as exc:
        harness = None
        out["harness_error"] = {"kind": exc.kind, "message": str(exc)}
    oracle = Oracle(harness, profile, set(bound)) if harness else None
    try:
        for c in required:
            oid = c["obligation"]
            formal = irj["obligations"][oid]["formal"]
            prereq = prerequisites.get(oid, [])
            outcome, codes, detail = "PASS", [], {}
            if harness is None:
                outcome, codes = "FAIL", ["TEST_INCOMPLETE"]
                detail = {"harness_error": out["harness_error"]}
            elif prereq:
                outcome, codes = "FAIL", ["VERIFIER_NOT_RUN"]
                detail = {"prerequisites_not_passed": prereq}
            elif irj["obligations"][oid]["kind"] == "liveness_property":
                outcome, codes = "UNSUPPORTED", ["UNSUPPORTED_SEMANTICS"]
                detail = {"reason": "a finite test campaign cannot discharge an unbounded liveness property"}
            elif irj["obligations"][oid]["kind"] == "resource_constraint":
                outcome, codes = "UNSUPPORTED", ["UNSUPPORTED_SEMANTICS"]
                detail = {"reason": "sampled executions cannot establish a physical resource or wall-time bound"}
            elif formal["representation"] != "contract_dsl":
                outcome, codes = "UNSUPPORTED", ["UNSUPPORTED_SEMANTICS"]
                detail = {"reason": f"{formal['representation']} statements have no executable oracle; none is fabricated"}
            else:
                pkg_hash = formal["formula_ref"].rsplit("@", 1)[1]
                package = canonical.load_file(expressions_dir / f"{pkg_hash.split(':')[1]}.json")
                formula = package["formula"]
                missing = sorted(dsl.calls(formula) - set(bound))
                if missing:
                    outcome, codes = "UNSUPPORTED", ["UNMAPPED_IMPLEMENTATION_OBJECT"]
                    detail = {"unbound_symbols": missing}
                else:
                    ob_seed = int(canonical.sha256_hex(f"{cfg['seed']}:{oid}".encode())[:8], 16)
                    camp = Campaign(formula, profile, oracle, cfg, ob_seed)
                    counts = {"generated": 0, "effective": 0, "discarded": 0, "indeterminate": 0, "timeouts": 0, "failures": 0}
                    failures: list[dict[str, Any]] = []
                    reasons: dict[str, int] = {}
                    budget = cfg["cases_per_obligation"] * cfg["max_generated_factor"]
                    for vals in camp.assignments():
                        if counts["effective"] >= cfg["cases_per_obligation"] or counts["generated"] >= budget:
                            break
                        counts["generated"] += 1
                        kind, why = camp.classify(vals)
                        if kind == "pass":
                            counts["effective"] += 1
                        elif kind == "discarded":
                            counts["discarded"] += 1
                        elif kind in ("timeout", "indeterminate"):
                            counts["timeouts" if kind == "timeout" else "indeterminate"] += 1
                            reasons[why] = reasons.get(why, 0) + 1
                        else:
                            counts["effective"] += 1
                            counts["failures"] += 1
                            if len(failures) < 5:
                                small = camp.shrink(vals) if cfg["shrink"] else vals
                                failures.append({"assignment": _js(tuple(vals)), "minimized": _js(tuple(small)),
                                                 "reason": camp.classify(small)[1]})
                    detail = {"seed": ob_seed, "counts": counts, "counterexamples": failures,
                              "indeterminate_reasons": dict(sorted(reasons.items())[:10]),
                              "formula": dsl.render(formula),
                              "oracle_hash": canonical.digest_json({"formula_package": pkg_hash,
                                                                    "evaluator": canonical.digest(Path(dsl.__file__).read_bytes())})}
                    if camp.generation_problem:
                        detail["generation_problem"] = camp.generation_problem
                    if oracle and oracle.nondeterminism:
                        outcome, codes = "FAIL", ["NONDETERMINISM"]
                        detail["nondeterminism"] = oracle.nondeterminism[:5]
                    elif counts["failures"]:
                        outcome, codes = "FAIL", ["TEST_FAILURE"]
                    elif counts["timeouts"]:
                        outcome, codes = "FAIL", ["TEST_INCOMPLETE"]
                    elif counts["effective"] < cfg["min_effective_cases"]:
                        outcome, codes = "FAIL", ["EMPTY_TEST_CAMPAIGN"]
            out["obligations"][oid] = {"outcome": outcome, "codes": codes, "detail": detail}
        out["coverage"] = harness.coverage() if harness else {}
        out["harness"] = {"sha256": canonical.digest(pt.HARNESS.read_bytes()), **(harness.ready if harness else {}),
                          "isolation": harness.isolation if harness else {}}
    finally:
        if harness:
            harness.close()
    return out


def _messages(oid: str, codes: list[str], detail: dict[str, Any], cfg: dict[str, Any]) -> list[Diagnostic]:
    ce = (detail.get("counterexamples") or [{}])[0]
    msgs = {
        "TEST_FAILURE": f"{oid}: counterexample {ce.get('minimized')} ({ce.get('reason')})",
        "TEST_INCOMPLETE": f"{oid}: the campaign could not complete (timeouts or harness failure: {detail.get('harness_error')})",
        "EMPTY_TEST_CAMPAIGN": f"{oid}: only {detail.get('counts', {}).get('effective', 0)} effective cases (minimum {cfg['min_effective_cases']})",
        "UNSUPPORTED_SEMANTICS": f"{oid}: {detail.get('reason')}",
        "UNMAPPED_IMPLEMENTATION_OBJECT": f"{oid}: unbound symbols {detail.get('unbound_symbols')}",
        "VERIFIER_NOT_RUN": f"{oid}: TESTED requires {', '.join(detail.get('prerequisites_not_passed', []))} to pass first",
        "NONDETERMINISM": f"{oid}: the target returned different results for identical inputs: {(detail.get('nondeterminism') or [None])[0]}",
    }
    return [Diagnostic(code, msgs.get(code, f"{oid}: {code}"), obligations=[oid]) for code in codes]


def load_inputs(pkg: Package) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, list[Diagnostic]]:
    irj, ir_hash, cert, diags = verified_ir(pkg)
    claims_path = pkg.path("closure") / "implementation-claims.json"
    link_path = pkg.path("bridges") / "link.json"
    if not claims_path.is_file() or not link_path.is_file():
        diags.append(Diagnostic("VERIFIER_NOT_RUN", "no implementation claims or link record; run `verislop generate` and `verislop link`"))
        return None, None, None, diags
    return irj, canonical.load_file(claims_path), canonical.load_file(link_path), diags


def run(pkg: Package, events: EventSink, *, seed: int | None = None, cases: int | None = None, timeout: float = 120.0) -> StageResult:
    from .backends.registry import frozen_backend, VSCORE_ID

    backend, diagnostics = frozen_backend(pkg)
    if diagnostics or (backend and backend["id"] == VSCORE_ID):
        result = StageResult("test", "BLOCKED", "no independent VSCore campaign is registered")
        result.diagnostics = diagnostics or [Diagnostic("UNSUPPORTED_CAPABILITY",
            "VSCore TESTED is unsupported: kernel checks and proof acceptance are not a target campaign")]
        return result
    events.emit("stage_started", "test", "running the frozen Tier 0 campaign on the target artifact")
    result = StageResult("test", "PASS", "the required target campaign passed its frozen criteria (test evidence, not proof)")
    irj, claims, link, diags = load_inputs(pkg)
    if diags:
        result.diagnostics = diags
        result.status = status_from(diags)
        return result
    assert irj is not None and claims is not None and link is not None
    profile = dsl.Profile.from_json(C.frozen_json(pkg, "profile.json"))
    tests_dir = pkg.path("tests")
    cfg_path = tests_dir / "campaign.json"
    if cfg_path.is_file():
        cfg = canonical.load_file(cfg_path)
        if (seed is not None and seed != cfg["seed"]) or (cases is not None and cases != cfg["cases_per_obligation"]):
            result.diagnostics.append(Diagnostic(
                "CLAIM_MUTATION", "the campaign configuration is frozen for this package; a different seed or size is a new candidate run"))
            result.status = "BLOCKED"
            return result
    else:
        if seed is None:
            seed = int(canonical.sha256_hex((pkg.implementation_root() or "").encode())[:8], 16)
        cfg = campaign_config(seed, cases or 300, 5000, profile)
        fsutil.write_json(cfg_path, cfg, once=True)
    if cfg["serialization_profile"] != pt.profile_id(profile):
        result.diagnostics.append(Diagnostic("CLAIM_MUTATION", "the frozen campaign serialization profile differs from the accepted contract"))
        result.status = "BLOCKED"
        return result
    root = pkg.test_root()
    from . import view

    current = view.derive(pkg)["obligations"]
    prereqs = {oid: [m for m in ("IMPLEMENTED", "TYPECHECKED") if rec["lifecycle"][m]["outcome"] != "PASS"]
               for oid, rec in current.items()}
    out = execute(pkg.path("implementation"), link, claims, irj, profile, cfg, pkg.path("accepted") / "expressions", prereqs)
    if out["harness_error"] and out["harness_error"]["kind"] in ("timeout", "crash"):
        diags.append(Diagnostic("VERIFIER_FAILURE", f"the target harness could not start: {out['harness_error']['message']}", severity="infrastructure"))
    cov = {f: {"executed": len(v["executed"]), "executable": len(v["executable"])} for f, v in out.get("coverage", {}).items()}
    summary: dict[str, Any] = {}
    for oid, r in out["obligations"].items():
        rec = irj["obligations"][oid]
        outcome, codes, detail = r["outcome"], r["codes"], r["detail"]
        diags.extend(_messages(oid, codes, detail, cfg))
        summary[oid] = {"outcome": outcome, "codes": codes, **{k: detail[k] for k in ("counts", "counterexamples") if k in detail}}
        ev = pkg.evidence.record(
            claim_id=claim_id("TESTED", oid, rec["revision"]), verifier_id=VERIFIER,
            status="PASS" if outcome == "PASS" else "BLOCK",
            scope=[f"test root {root}", f"campaign {cfg['generator']} seed {cfg['seed']}",
                   "finite sampling of the target artifact; not a proof of the universal statement"],
            input_root=root,
            result={"milestone_outcome": outcome, "codes": codes, **detail,
                    "artifact": {"implementation_root": pkg.implementation_root(), "files": out["files"]},
                    "harness": out.get("harness", {}),
                    "coverage": {"lines": cov, "branch_coverage": "not measured (line coverage only)"},
                    "obligation_coverage": [oid],
                    "limitations": ["finite sampling cannot establish an unbounded universal claim",
                                    "the DSL oracle translation is trusted, not proved equivalent to the Lean predicate",
                                    f"{pt.profile_id(profile)} adapters are trusted"]},
            invocation=["verislop", "test", "--seed", str(cfg["seed"]), "--cases", str(cfg["cases_per_obligation"])])
        c = detail.get("counts")
        events.emit("verifier_decision", "test", f"{oid} TESTED {outcome}" + (f" ({', '.join(codes)})" if codes else
                    f" ({c['effective']} effective, {c['discarded']} discarded)" if c else ""),
                    obligation_id=oid, milestone="TESTED", outcome=outcome, evidence_ref=f"evidence:{ev.id}")
    fsutil.write_json(tests_dir / "results.json", {"schema_version": SCHEMA_VERSION, "artifact_kind": "test_results",
                                                   "test_root": root, "campaign": cfg, "obligations": summary,
                                                   "line_coverage": cov}, pretty=True)
    view.write(pkg)
    result.diagnostics = diags
    result.status = status_from(diags)
    result.artifacts.update({"campaign": pkg.rel(cfg_path), "results": pkg.rel(tests_dir / "results.json")})
    result.summary = {"test_root": root, "seed": cfg["seed"], "obligations": summary, "line_coverage": cov}
    for oid, s in summary.items():
        c = s.get("counts", {})
        result.lines.append(f"{oid}: {s['outcome']}" + (f" — {c.get('effective', 0)} effective / {c.get('generated', 0)} generated, "
                                                         f"{c.get('discarded', 0)} discarded, {c.get('failures', 0)} counterexamples" if c else f" {s['codes']}"))
    return result
