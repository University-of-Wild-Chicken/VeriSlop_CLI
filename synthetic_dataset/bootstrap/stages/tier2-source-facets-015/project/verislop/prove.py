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

from . import contract_values, agent_memory, canonical, contract, dsl, fsutil, leanbridge, native_contract
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
    return n.rsplit(".", 1)[-1].removeprefix("«").removesuffix("»")


def _qualified(n: str) -> str:
    return "_root_." + ".".join("«" + part.removeprefix("«").removesuffix("»") + "»" for part in n.split("."))


def _witness_literal(sort: Any, profile: dict[str, Any], variant: int, budget: list[int], depth: int = 0) -> str:
    """Untrusted, sort-directed search literals; only the kernel can prove a witness."""
    budget[0] -= 1
    if budget[0] < 0 or depth > 32:
        raise ValueError("structured witness construction budget exhausted")
    if sort == "Nat":
        return f"({variant} : _root_.Nat)"
    if sort == "Int":
        return f"({(0, 1, -1, -2)[variant % 4]} : _root_.Int)"
    if sort == "Bool":
        return "_root_.Bool.true" if variant % 2 else "_root_.Bool.false"
    if sort == "Unit":
        return "_root_.Unit.unit"
    if sort == "String":
        return '""' if variant % 2 == 0 else '"x"'
    if not isinstance(sort, dict):
        raise ValueError("unsupported witness sort")
    if "option" in sort:
        return ("_root_.Option.none" if variant % 2 == 0 else
                "(_root_.Option.some " + _witness_literal(sort["option"], profile, variant, budget, depth + 1) + ")")
    if "list" in sort:
        return "[]" if variant % 2 == 0 else "[" + _witness_literal(sort["list"], profile, variant - 1, budget, depth + 1) + "]"
    if "record" in sort:
        row = profile["records"][sort["record"]]
        fields = [_witness_literal(f["sort"], profile, variant, budget, depth + 1) for f in row["fields"]]
        return "(" + _qualified(row["lean_constructor"]) + " " + " ".join(fields) + ")"
    if "enum" in sort:
        constructors = profile["enums"][sort["enum"]]["lean_constructors"]
        return _qualified(constructors[variant % len(constructors)])
    if "result" in sort:
        side = "ok" if variant % 2 == 0 else "error"
        return "(_root_.Except." + side + " " + _witness_literal(sort["result"][side], profile, variant, budget, depth + 1) + ")"
    raise ValueError("unsupported witness sort")


def _existential_tactic(formula: dict[str, Any], profile: dict[str, Any], defs: list[str],
                        budget: list[int], candidates: list[int]) -> str:
    if formula["tag"] == "and":
        left = _existential_tactic(formula["left"], profile, defs, budget, candidates)
        right = _existential_tactic(formula["right"], profile, defs, budget, candidates)
        return f"exact _root_.And.intro (by {left}) (by {right})"
    sorts = []
    while formula["tag"] == "exists":
        sorts.append(formula["sort"])
        formula = formula["body"]
    if not sorts or len(sorts) > 4:
        return "sorry"
    simp = ", ".join(defs)
    suffix = f"simp [{simp}]; done" if defs else "simp; done"
    alts = []
    for variants in itertools.product(range(4) if len(sorts) <= 3 else range(3), repeat=len(sorts)):
        if candidates[0] <= 0:
            break
        candidates[0] -= 1
        try:
            values = ", ".join(_witness_literal(sort, profile, variant, budget) for sort, variant in zip(sorts, variants))
        except (ValueError, KeyError, TypeError):
            break
        alts.append(f"(refine ⟨{values}, ?_⟩; {suffix})")
    return "first " + " ".join("| " + alt for alt in alts) + " | sorry" if alts else "sorry"


def _closed_reduction_eligible(formula: Any, profile: dict[str, Any]) -> bool:
    """Bounded search eligibility only; the kernel still decides every proof.

    `cbv` uses equation proofs to reduce well-founded library functions such as
    mergeSort. It needs no DecidableEq instance for the resulting record equality.
    Do not try it on logical quantifiers, malformed terms or oversized graphs.
    """
    pending = [(formula, 0)]
    visited = 0
    while pending:
        node, depth = pending.pop()
        visited += 1
        if visited > 4096 or depth > 64:
            return False
        if isinstance(node, dict):
            if node.get("tag") in dsl.QUANTIFIERS:
                return False
            if len(node) + len(pending) > 4096 - visited:
                return False
            pending.extend((value, depth + 1) for value in node.values())
        elif isinstance(node, list):
            if len(node) + len(pending) > 4096 - visited:
                return False
            pending.extend((value, depth + 1) for value in node)
    try:
        dsl.type_formula(formula, [], dsl.Profile.from_json(profile))
    except (dsl.DSLError, KeyError, TypeError, ValueError, RecursionError):
        return False
    return True


def portfolio_tactic(statement: dict[str, Any] | None, defs: list[str], profile: dict[str, Any] | None = None) -> str:
    unfold = " ".join(defs)
    simp = ", ".join(defs)
    generic = [f"(grind [{simp}])" if defs else "grind", f"(simp_all [{simp}]; done)" if defs else "(simp_all; done)"]
    if defs:
        generic.append(f"(unfold {unfold} at *; simp_all; omega)")
    generic += ["omega", "decide"]
    package = contract_values.statement_value_package(statement) if statement is not None else None
    if package is not None:
        formula = package["formula"]
        if _closed_reduction_eligible(formula, profile or {}):
            generic.append("(cbv <;> simp_all <;> done)")
        if dsl.is_existential_shape(formula):
            # Finite search is a heuristic, not evidence of satisfiability or completeness.
            value_tactic = _existential_tactic(formula, profile or {}, defs, [4096], [256])
            if statement.get("representation") in ("contract_facets", "source_facets"):
                # Split only the exact compiler/reifier conjunction. No native
                # instance proof is manufactured: its hole remains for ordinary
                # kernel-checked proof search or agent authoring.
                fallback = "first " + " ".join("| " + g for g in generic) + " | sorry"
                return f"first | (refine And.intro ?_ ?_; all_goals first | ({value_tactic}) | ({fallback})) | ({fallback})"
            return value_tactic
    return "first " + " ".join("| " + g for g in generic) + " | sorry"


def apply_portfolio(src: str, statements: dict[str, dict[str, Any]], profile: dict[str, Any]) -> str:
    by_short: dict[str, dict[str, Any]] = {}
    for st in statements.values():
        if st.get("role") == "guarantee":
            by_short.setdefault(_short(st["lean_symbol"]), st)
    defs = sorted({_qualified(x["lean_decl"]) for x in list(profile["symbols"].values()) + list(profile["predicates"].values())})
    out = src
    for off in reversed(sorry_sites(src)):
        name = enclosing_decl(src, off)
        st = by_short.get(_short(name)) if name else None
        tactic = portfolio_tactic(st, defs, profile)
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
    critic: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
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
    latest_src: str | None = None
    latest_result: dict[str, Any] | None = None
    previous_critique = None
    retained = agent_memory.latest_snapshot(pkg, stage_prefix="prove/attempt")
    saved = canonical.loads(agent_memory.restore(pkg, retained)["payload.json"]) if retained else None
    agent_serial = saved.get("agent_attempt", 0) if saved else 0
    if saved and saved["challenge_hash"] != canonical.digest(challenge.encode()):
        raise UsageError("retained proof context does not match the frozen challenge",
                         [Diagnostic("STALE_OR_UNBOUND_EVIDENCE", "proof memory challenge identity mismatch")])
    seen_failures: set[str] = set()
    if log.is_file():
        for line in log.read_bytes().splitlines():
            entry = canonical.loads(line)
            if not entry["complete"]:
                seen_failures.add(canonical.digest_json({k: entry[k] for k in ("source_sha256", "errors", "sorries")}))

    def record(kind: str, src: str, res: dict[str, Any], proposal: str | None = None,
               *, update_latest: bool = True) -> None:
        nonlocal best, best_src, latest_src, latest_result
        entry = {"generator": kind, "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "source_sha256": canonical.digest(src.encode()), **{k: res[k] for k in ("ok", "sorries", "complete", "wall_ms")},
                 "errors": res["errors"]}
        # Keep the generator's exact submission separately from the compiled file, which may
        # include the supervisor's frozen registry. Neither source is rewritten to repair it.
        submitted = src if proposal is None else proposal
        entry["proposal_sha256"] = canonical.digest(submitted.encode())
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        fsutil.atomic_write(proofs / "attempts" / f"{entry['source_sha256'].split(':')[1][:16]}.lean", src.encode())
        fsutil.atomic_write(proofs / "proposals" / f"{entry['proposal_sha256'].split(':')[1][:16]}.lean", submitted.encode())
        if update_latest:
            latest_src, latest_result = submitted, dict(entry)
        events.emit("candidate_proposal", "prove", f"{kind}: ok={res['ok']} remaining sorries={res['sorries']}",
                    details={"generator": kind, "complete": res["complete"]})
        if _better(best, res):
            best, best_src = res, src
        agent_memory.capture_context(pkg, "prove/attempt", {
            "challenge_hash": canonical.digest(challenge.encode()), "candidate": latest_src,
            "best": best_src, "result": latest_result, "recorded_evaluation": entry,
            "critique": previous_critique, "agent_attempt": agent_serial}, extra_artifacts={
                "proposal.lean": submitted.encode(), "Contract.lean": src.encode(),
                "latest-proposal.lean": latest_src.encode(), "latest-diagnostics.json": canonical.dumps(latest_result),
                "profile.json": canonical.dumps(profile), "statements.json": canonical.dumps(statements),
                "diagnostics.json": canonical.dumps(res)})

    if saved is not None:
        previous_critique = saved.get("critique")
        src = with_registry(saved["best"], challenge)
        record("retained_best", src, evaluate(tc, pol, src))
        if saved["candidate"] != saved["best"]:
            src = with_registry(saved["candidate"], challenge)
            record("retained_latest", src, evaluate(tc, pol, src), saved["candidate"])

    if candidate is not None:
        submitted = Path(candidate).read_text()
        src = with_registry(submitted, challenge)
        record("candidate_file", src, evaluate(tc, pol, src), submitted)
    if (best is None or not best["complete"]) and portfolio and (deadline is None or time.monotonic() < deadline):
        base = best_src if best_src is not None and best and best["ok"] else challenge
        if sorry_sites(base):
            src = apply_portfolio(base, statements, profile)
            record("builtin_tactic_portfolio", src, evaluate(tc, pol, src), update_latest=latest_src is None)
        elif best is None:
            record("challenge_as_is", base, evaluate(tc, pol, base))
    attempts = 0
    repeated = 0
    critic_needed = True
    while (agent is not None and (best is None or not best["complete"]) and attempts < max_attempts
           and (deadline is None or time.monotonic() < deadline)):
        attempts += 1
        agent_serial += 1
        if critic is not None and critic_needed:
            from .formalize import require_interpretation, _records
            draft, ledger, idiags = require_interpretation(pkg)
            if idiags:
                result.diagnostics.extend(idiags)
                break
            diags = [Diagnostic("CANDIDATE_BUILD_FAILURE", error) for error in (latest_result or {}).get("errors", [])]
            if not diags:
                diags = [Diagnostic("PROOF_UNRESOLVED", "the current candidate contains unresolved proof holes")]
            previous_critique = critic({"phase": "prove", "attempt": agent_serial, "source": (latest_src or challenge).encode(),
                "form": contractmod.frozen_json(pkg, "formalization.json"), "records": _records(draft, ledger, None),
                "draft": draft, "ledger": ledger, "analysis": None, "profile": profile,
                "statements": statements, "diagnostics": diags, "previous_critique": previous_critique})
            result.diagnostics.extend(Diagnostic.from_json(d) for d in previous_critique.get("diagnostics", []))
            if previous_critique["status"] == "INCOMPLETE":
                break
        proposal = agent({"challenge": challenge, "best": best_src or challenge,
                          "errors": (latest_result or {}).get("errors", []), "statements": statements, "attempt": agent_serial,
                          "previous_candidate": latest_src, "previous_result": latest_result, "critique": previous_critique})
        src = with_registry(proposal, challenge)
        evaluated = evaluate(tc, pol, src)
        signature = canonical.digest_json({"source_sha256": canonical.digest(src.encode()),
                                           "errors": evaluated["errors"], "sorries": evaluated["sorries"]})
        duplicate = not evaluated["complete"] and signature in seen_failures
        repeated = repeated + 1 if duplicate else 0
        record("agent:prover", src, evaluated, proposal)
        if not evaluated["complete"]:
            seen_failures.add(signature)
        critic_needed = duplicate
        if repeated >= 2:
            result.diagnostics.append(Diagnostic("NO_PROGRESS",
                "the prover repeated the same failed candidate and diagnostics; a fresh contract repair is required"))
            break

    if best_src is None:
        result.diagnostics.append(Diagnostic("PROOF_UNRESOLVED", "no proof generator produced a candidate"))
        result.status = "BLOCKED"
        return result
    fsutil.atomic_write(proofs / "candidate.lean", best_src.encode())
    result.artifacts["proof_candidate"] = pkg.rel(proofs / "candidate.lean")
    result.summary = {"complete": best["complete"], "remaining_sorries": best["sorries"], "errors": best["errors"][:10],
                      "budget_seconds": budget_seconds, "agent_attempts": attempts, "repeated_failures": repeated}
    if not best["ok"]:
        result.diagnostics.append(Diagnostic("CANDIDATE_BUILD_FAILURE", "best proof candidate does not elaborate: " + "; ".join(best["errors"][:3])))
    elif best["sorries"]:
        code = "BUDGET_EXHAUSTED" if deadline is not None and time.monotonic() >= deadline else "PROOF_UNRESOLVED"
        result.diagnostics.append(Diagnostic(code, f"{best['sorries']} declaration(s) still use `sorry`; obligations remain unresolved (not disproved)"))
    result.status = status_from(result.diagnostics)
    result.lines.append(f"best candidate: {'complete' if best['complete'] else 'incomplete'}; remaining sorries: {best['sorries']}")
    return result
