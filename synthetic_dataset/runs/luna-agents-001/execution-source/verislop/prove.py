"""`verislop prove`: bounded, untrusted proof search against the frozen challenge.

Proof generators — the built-in deterministic tactic portfolio, an LLM prover role, or a
supplied candidate file — work in `contract/proofs/` and never touch the frozen challenge,
verifiers or evidence. Nothing here establishes PROVED: `verislop accept` decides. Budget
exhaustion leaves obligations unresolved (PROOF_UNRESOLVED); it is never a disproof and never
a weaker contract.
"""

from __future__ import annotations

import itertools
import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from . import canonical, contract, dsl, fsutil, leanbridge
from .errors import Diagnostic, UsageError
from .events import EventSink
from .package import Package
from .stage import StageResult, status_from

_IDENT_CHARS = re.compile(r"[A-Za-z0-9_'!?.À-￿]")
_DECL = re.compile(r"^\s*(?:@\[[^\]]*\]\s*)?(?:private\s+|protected\s+|noncomputable\s+)*(theorem|lemma|example|def|instance|abbrev)\s+([^\s:(\[{]*)", re.M)


def sorry_sites(src: str) -> list[int]:
    """Offsets of `sorry` tokens outside comments, strings and character literals."""
    out: list[int] = []
    i, n = 0, len(src)
    while i < n:
        if src.startswith("--", i):
            j = src.find("\n", i)
            i = n if j == -1 else j + 1
            continue
        if src.startswith("/-", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if src.startswith("/-", j):
                    depth, j = depth + 1, j + 2
                elif src.startswith("-/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            i = j
            continue
        ch = src[i]
        if ch == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            i = j + 1
            continue
        if ch == "'" and (i == 0 or not _IDENT_CHARS.match(src[i - 1])):
            if i + 2 < n and src[i + 2] == "'":
                i += 3
                continue
            if i + 3 < n and src[i + 1] == "\\" and src[i + 3] == "'":
                i += 4
                continue
        if src.startswith("sorry", i):
            before = src[i - 1] if i else " "
            after = src[i + 5] if i + 5 < n else " "
            if not _IDENT_CHARS.match(before) and not _IDENT_CHARS.match(after):
                out.append(i)
                i += 5
                continue
        i += 1
    return out


def enclosing_decl(src: str, offset: int) -> str | None:
    best = None
    for m in _DECL.finditer(src, 0, offset):
        best = m.group(2)
    return best


def _short(n: str) -> str:
    return n.rsplit(".", 1)[-1]


def portfolio_tactic(statement: dict[str, Any] | None, defs: list[str]) -> str:
    unfold = " ".join(defs)
    simp = ", ".join(defs)
    generic = [f"(grind [{simp}])" if defs else "grind", f"(simp_all [{simp}]; done)" if defs else "(simp_all; done)"]
    if defs:
        generic.append(f"(unfold {unfold} at *; simp_all; omega)")
    generic += ["omega", "decide"]
    if statement is not None and statement.get("representation") == "contract_dsl":
        f = statement["formula_package"]["formula"]
        if dsl.is_existential_shape(f):
            alts = []
            for depth in sorted(set(_exists_depths(f)), reverse=True):
                grid = range(4) if depth <= 3 else range(3) if depth == 4 else range(0)
                for vals in itertools.product(grid, repeat=depth):
                    v = ", ".join(map(str, vals))
                    alts.append(f"(refine ⟨{v}, ?_⟩; simp [{simp}]; done)" if defs else f"(refine ⟨{v}, ?_⟩; simp; done)")
            if alts:
                prefix = "refine ⟨?_, ?_⟩ <;> " if f["tag"] == "and" else ""
                # `sorry` last: an unproved goal stays an isolated PROOF_UNRESOLVED instead of
                # an elaboration error that would prevent checking independent obligations.
                return prefix + "first " + " ".join("| " + a for a in alts) + " | sorry"
    return "first " + " ".join("| " + g for g in generic) + " | sorry"


def _exists_depths(f: dict[str, Any]) -> list[int]:
    if f["tag"] == "and":
        return _exists_depths(f["left"]) + _exists_depths(f["right"])
    depth = 0
    while f["tag"] == "exists":
        depth += 1
        f = f["body"]
    return [depth]


def apply_portfolio(src: str, statements: dict[str, dict[str, Any]], profile: dict[str, Any]) -> str:
    by_short: dict[str, dict[str, Any]] = {}
    for st in statements.values():
        if st.get("role") == "guarantee":
            by_short.setdefault(_short(st["lean_symbol"]), st)
    defs = sorted({_short(x["lean_decl"]) for x in list(profile["symbols"].values()) + list(profile["predicates"].values())})
    out = src
    for off in reversed(sorry_sites(src)):
        name = enclosing_decl(src, off)
        st = by_short.get(_short(name)) if name else None
        tactic = portfolio_tactic(st, defs)
        prev = src[:off].rstrip()
        replacement = tactic if prev.endswith("by") else f"(by {tactic})"
        out = out[:off] + replacement + out[off + 5:]
    return out


def registry_block(challenge: str) -> str:
    a = challenge.index(contract.REGISTRY_BEGIN)
    b = challenge.index(contract.REGISTRY_END) + len(contract.REGISTRY_END)
    return challenge[a:b] + "\n"


def with_registry(candidate: str, challenge: str) -> str:
    if contract.REGISTRY_BEGIN in candidate:
        return candidate
    composed, _, problems = contract.compose_challenge(candidate.encode(), registry_block(challenge))
    if problems:
        raise UsageError("cannot compose proof candidate with the frozen registry: " + "; ".join(problems))
    return composed.decode()


def evaluate(tc: leanbridge.Toolchain, pol: dict[str, Any], src: str) -> dict[str, Any]:
    with fsutil.temporary_directory(prefix="verislop-prove-") as tmp:
        comp = leanbridge.compile_module(tc, src.encode(), Path(tmp), timeout=pol["build_timeout_seconds"],
                                         memory_mb=pol["memory_mb"], require_network_isolation=pol["require_network_isolation"])
    return {"ok": comp.ok, "errors": comp.errors, "sorries": len(comp.sorry_positions),
            "complete": comp.ok and not comp.sorry_positions, "wall_ms": int(comp.wall_seconds * 1000)}


def _better(a: dict[str, Any] | None, b: dict[str, Any]) -> bool:
    if a is None:
        return True
    key = lambda r: (r["ok"], -r["sorries"], -len(r["errors"]))  # noqa: E731
    return key(b) > key(a)


def run(
    pkg: Package,
    events: EventSink,
    *,
    contract: Path | None = None,
    candidate: Path | None = None,
    budget_seconds: int = 600,
    max_attempts: int = 4,
    portfolio: bool = True,
    agent: Callable[[dict[str, Any]], str] | None = None,
) -> StageResult:
    from . import contract as contractmod

    if type(budget_seconds) is not int or budget_seconds < 0:
        raise UsageError("proof-search budget_seconds must be a nonnegative integer; 0 disables the deadline")

    if contract is not None:
        pkg.set_path("contract", contract)
    events.emit("stage_started", "prove", "searching for proofs of the frozen challenge")
    result = StageResult("prove", "PASS", "a complete proof candidate exists (acceptance decides PROVED)")
    ch, fdiags = contractmod.load_frozen(pkg)
    if fdiags:
        result.diagnostics.extend(fdiags)
        result.status = "BLOCKED"
        return result
    chdir = contractmod.challenge_dir(pkg)
    challenge = (chdir / "Contract.lean").read_text()
    statements = contractmod.frozen_json(pkg, "statements.json")["statements"]
    profile = contractmod.frozen_json(pkg, "profile.json")
    pol = contractmod.frozen_json(pkg, "policy.json")
    tc = leanbridge.resolve_toolchain((chdir / "lean-toolchain").read_text())
    proofs = pkg.path("contract") / "proofs"
    proofs.mkdir(parents=True, exist_ok=True)
    log = proofs / "attempts.jsonl"
    deadline = None if budget_seconds == 0 else time.monotonic() + budget_seconds
    best: dict[str, Any] | None = None
    best_src: str | None = None

    def record(kind: str, src: str, res: dict[str, Any]) -> None:
        nonlocal best, best_src
        entry = {"generator": kind, "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "source_sha256": canonical.digest(src.encode()), **{k: res[k] for k in ("ok", "sorries", "complete", "wall_ms")},
                 "errors": res["errors"][:20]}
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        fsutil.atomic_write(proofs / "attempts" / f"{entry['source_sha256'].split(':')[1][:16]}.lean", src.encode())
        events.emit("candidate_proposal", "prove", f"{kind}: ok={res['ok']} remaining sorries={res['sorries']}",
                    details={"generator": kind, "complete": res["complete"]})
        if _better(best, res):
            best, best_src = res, src

    if candidate is not None:
        src = with_registry(Path(candidate).read_text(), challenge)
        record("candidate_file", src, evaluate(tc, pol, src))
    if (best is None or not best["complete"]) and portfolio and (deadline is None or time.monotonic() < deadline):
        base = best_src if best_src is not None and best and best["ok"] else challenge
        if sorry_sites(base):
            src = apply_portfolio(base, statements, profile)
            record("builtin_tactic_portfolio", src, evaluate(tc, pol, src))
        elif best is None:
            record("challenge_as_is", base, evaluate(tc, pol, base))
    attempts = 0
    while (agent is not None and (best is None or not best["complete"]) and attempts < max_attempts
           and (deadline is None or time.monotonic() < deadline)):
        attempts += 1
        proposal = agent({"challenge": challenge, "best": best_src or challenge,
                          "errors": (best or {}).get("errors", []), "statements": statements, "attempt": attempts})
        src = with_registry(proposal, challenge)
        record("agent:prover", src, evaluate(tc, pol, src))

    if best_src is None:
        result.diagnostics.append(Diagnostic("PROOF_UNRESOLVED", "no proof generator produced a candidate"))
        result.status = "BLOCKED"
        return result
    fsutil.atomic_write(proofs / "candidate.lean", best_src.encode())
    result.artifacts["proof_candidate"] = pkg.rel(proofs / "candidate.lean")
    result.summary = {"complete": best["complete"], "remaining_sorries": best["sorries"], "errors": best["errors"][:10],
                      "budget_seconds": budget_seconds}
    if not best["ok"]:
        result.diagnostics.append(Diagnostic("CANDIDATE_BUILD_FAILURE", "best proof candidate does not elaborate: " + "; ".join(best["errors"][:3])))
    elif best["sorries"]:
        code = "BUDGET_EXHAUSTED" if deadline is not None and time.monotonic() >= deadline else "PROOF_UNRESOLVED"
        result.diagnostics.append(Diagnostic(code, f"{best['sorries']} declaration(s) still use `sorry`; obligations remain unresolved (not disproved)"))
    result.status = status_from(result.diagnostics)
    result.lines.append(f"best candidate: {'complete' if best['complete'] else 'incomplete'}; remaining sorries: {best['sorries']}")
    return result
