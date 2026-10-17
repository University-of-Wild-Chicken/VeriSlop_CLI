"""Bounded exact proof-body search-state retention; never proof authority."""
from __future__ import annotations

import base64
import copy
import time
from pathlib import Path
from typing import Any, Callable

from . import agent_memory, canonical, leanbridge, proof_fragments, proof_focus
from .errors import InfrastructureError, blocked

FORMAT = "verislop.proof-retention/0.1"
NATIVE_FORMAT = "verislop.proof-retention-native/0.1"
AUTHORITY = "Mechanical search state only; no proof, acceptance, TESTED or Tier 2 authority."
CAPS = {"per_proposal": 2, "per_job": 4}


class Ineligible(ValueError):
    """The optional search optimization cannot use this exact observation."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise Ineligible(reason)


def identity() -> dict:
    root = Path(__file__).resolve().parent
    return {"format": FORMAT, "caps": CAPS.copy(), "implementation": {
        name: canonical.digest((root / name).read_bytes()) for name in
        ("proof_retention.py", "prove.py", "proof_fragments.py", "proof_focus.py",
         "leanbridge.py", "agents.py", "agent_memory.py", "lean/VeriSlopProofSyntax.lean")}}


def _bytes(value: Any) -> bytes:
    _require(isinstance(value, dict) and set(value) == {"byte_count", "sha256", "content_b64"},
             "missing exact compiler stream")
    try:
        raw = base64.b64decode(value["content_b64"], validate=True)
    except (ValueError, TypeError):
        raise Ineligible("invalid compiler stream encoding") from None
    _require(type(value["byte_count"]) is int and value["byte_count"] == len(raw)
             and value["sha256"] == canonical.digest(raw), "compiler stream binding mismatch")
    return raw


def _native(source: str, result: dict, toolchain: dict, policy: dict) -> tuple[list[dict], list[dict]]:
    """Check complete raw JSONL, exact formatter inventory and evaluation bindings.

    Called with current-process evaluate results during search. Historical records
    can be checked structurally, but never replace the fresh baseline compilation.
    """
    obs = result.get("native_observation")
    _require(isinstance(obs, dict) and obs.get("format") == NATIVE_FORMAT,
             "no structured native observation")
    _require(obs.get("source_sha256") == canonical.digest(source.encode())
             and obs.get("policy_sha256") == canonical.digest_json(policy)
             and canonical.dumps(obs.get("toolchain")) == canonical.dumps(toolchain),
             "stale native source, policy or toolchain")
    process = obs.get("process")
    _require(isinstance(process, dict) and process.get("format") == leanbridge.COMPILE_PROCESS_FORMAT,
             "no exact native process observation")
    _require(process.get("input", {}).get("module") == leanbridge.MODULE
             and process["input"].get("module_source_sha256") == canonical.digest(source.encode()),
             "native process source binding mismatch")
    _require(obs.get("timed_out") is False and process.get("timed_out") is False
             and process.get("reported_stderr_panics") == [] and _bytes(process.get("stderr")) == b"",
             "native timeout or process anomaly")
    limits = process.get("requested_limits", {})
    try:
        timeout = float(limits["wall_timeout_seconds"])
        _require(0 < timeout <= policy["build_timeout_seconds"] and
                 type(limits["lean_heap_mb"]) is int and limits["lean_heap_mb"] == policy["memory_mb"],
                 "native limits differ from frozen policy")
    except (ValueError, TypeError, KeyError, OverflowError):
        raise Ineligible("invalid native limits") from None
    raw = _bytes(process.get("stdout"))
    messages = []
    try:
        for line in raw.split(b"\n"):
            if not line.strip():
                continue
            msg = canonical.loads(line)
            _require(isinstance(msg, dict) and msg.get("severity") in ("error", "warning", "information")
                     and isinstance(msg.get("data"), str), "malformed native message")
            messages.append(msg)
    except (ValueError, UnicodeError, TypeError):
        raise Ineligible("native stdout is not complete strict JSONL") from None
    _require(canonical.dumps(messages) == canonical.dumps(obs.get("messages")),
             "native message inventory differs from raw stdout")
    errors = [m for m in messages if m["severity"] == "error"]
    warnings = [m for m in messages if m["severity"] == "warning" and m.get("kind") == "hasSorry"]
    for msg in errors + warnings:
        _require(msg.get("fileName") == leanbridge.MODULE + ".lean", "native location is outside submitted module")
        start = _offset(source, msg.get("pos"))
        if msg.get("endPos") is not None:
            _require(_offset(source, msg["endPos"], allow_end=True) >= start, "native end position precedes start")
    formatted = [f"{m['pos']['line']}:{m['pos']['column']}: {m['data']}" for m in errors]
    _require(result.get("errors") == formatted, "formatted errors do not exhaust native errors")
    _require(type(result.get("ok")) is bool and obs.get("ok") is result["ok"]
             and type(process.get("returncode")) is int
             and process["returncode"] == (0 if result["ok"] else 1), "native outcome mismatch or process failure")
    _require((not errors and obs.get("olean_present") is True) if result["ok"] else bool(errors),
             "native success lacks artifact or native failure lacks errors")
    positions = [{"line": m["pos"]["line"], "column": m["pos"]["column"]} for m in warnings]
    expected = {"source_sha256": canonical.digest(source.encode()), "policy_sha256": canonical.digest_json(policy),
                "toolchain": toolchain, "sorry_positions": positions}
    _require(canonical.dumps(result.get("native_diagnostics")) == canonical.dumps(expected)
             and type(result.get("sorries")) is int and result["sorries"] == len(warnings)
             and result.get("complete") is (result["ok"] and not warnings), "inconsistent unresolved native inventory")
    return errors, warnings


def native(source: str, result: dict, toolchain: dict, policy: dict) -> tuple[list[dict], list[dict]]:
    try:
        return _native(source, result, toolchain, policy)
    except Ineligible:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, RecursionError) as exc:
        raise Ineligible("malformed native observation: " + type(exc).__name__) from None


def _offset(source: str, pos: Any, *, allow_end: bool = False) -> int:
    _require(isinstance(pos, dict) and set(pos) == {"line", "column"}
             and type(pos["line"]) is int and type(pos["column"]) is int,
             "malformed native position")
    lines = source.split("\n")
    _require(1 <= pos["line"] <= len(lines) and 0 <= pos["column"] < len(lines[pos["line"] - 1]) + int(allow_end),
             "native position outside source")
    return sum(len(s) + 1 for s in lines[:pos["line"] - 1]) + pos["column"]


def unresolved(frozen: str, source: str, result: dict, tc: dict, policy: dict) -> list[str]:
    _, warnings = native(source, result, tc, policy)
    _require(result["ok"], "baseline did not compile successfully")
    original = proof_fragments._frozen_declarations(frozen)
    names = [t.name for t in original if t.hole]
    mapped = proof_focus._mapped_names(source, proof_fragments.declarations(source), set(names), [m["pos"] for m in warnings])
    _require(mapped is not None, "native unresolved warning is not an original hole")
    return [name for name in names if name in mapped]


def reversion(baseline: str, working: str, errors: list[dict], allowed: list[str]) -> tuple[str, list[dict]]:
    before = {t.name: t for t in proof_fragments.declarations(baseline)}
    current = proof_fragments.declarations(working)
    selected = set()
    for msg in errors:
        offset = _offset(working, msg.get("pos"))
        matches = [t for t in current if t.body_start <= offset < t.body_end]
        _require(len(matches) == 1 and matches[0].name in allowed, "error is outside an eligible proof body")
        t = matches[0]
        b = before[t.name]
        _require(working[t.body_start:t.body_end] != baseline[b.body_start:b.body_end],
                 "error belongs to an unchanged body")
        selected.add(t.name)
    _require(bool(selected), "no error-bearing changed body")
    rows, out = [], working
    for t in current:
        if t.name not in selected:
            continue
        b = before[t.name]
        old, new = working[t.body_start:t.body_end], baseline[b.body_start:b.body_end]
        rows.append({"name": t.name,
            "candidate_span": [len(working[:t.body_start].encode()), len(working[:t.body_end].encode())],
            "baseline_span": [len(baseline[:b.body_start].encode()), len(baseline[:b.body_end].encode())],
            "candidate_body_sha256": canonical.digest(old.encode()), "baseline_body_sha256": canonical.digest(new.encode())})
    for t in reversed(current):
        if t.name in selected:
            b = before[t.name]
            out = out[:t.body_start] + baseline[b.body_start:b.body_end] + out[t.body_end:]
    return out, rows


def _ref(artifacts: dict[str, bytes], name: str, value: bytes) -> dict:
    artifacts[name] = value
    return {"name": name, "sha256": canonical.digest(value), "size": len(value)}


def _read(artifacts: dict, ref: dict) -> bytes:
    _require(isinstance(ref, dict) and set(ref) == {"name", "sha256", "size"}, "invalid evidence reference")
    raw = artifacts.get(ref["name"])
    _require(isinstance(raw, bytes) and type(ref["size"]) is int and len(raw) == ref["size"]
             and canonical.digest(raw) == ref["sha256"], "retention evidence is missing or changed")
    return raw


class Search:
    """One frozen-job counter with append-only CAS transitions before dispatch.

    The package run lock is the existing single-writer boundary. Resumed state
    never supplies a native baseline; the caller must recompile its retained file.
    """
    def __init__(self, pkg: Any, job: dict, frozen: str, tc: dict, policy: dict):
        self.pkg, self.frozen, self.tc, self.policy = pkg, frozen, tc, policy
        self.job = {"frozen_job": job, "retention": identity(), "source_sha256": canonical.digest(frozen.encode()),
                    "toolchain": tc, "policy_sha256": canonical.digest_json(policy)}
        self.job_hash = canonical.digest_json(self.job)
        self.stage = "proof-retention/" + canonical.digest_json(job)[7:]
        self.history = agent_memory.snapshot_refs(pkg, stage=self.stage)
        self.ref = self.history[-1] if self.history else None
        self.used = 0
        self.last_receipt = None
        self.last_proposal_id = 0
        self.promoted_source = None
        if self.ref:
            self._restore()

    def _restore(self) -> None:
        chain, ref, seen = [], self.ref, set()
        try:
            while ref is not None:
                marker = canonical.digest_json(ref)
                _require(marker not in seen and len(seen) < agent_memory.MAX_SNAPSHOTS, "cyclic retention history")
                seen.add(marker)
                artifacts = agent_memory.restore(self.pkg, ref)
                state = canonical.loads(artifacts["payload.json"])
                index = len(self.history) - len(chain) - 1
                _require(index >= 0 and ref == self.history[index]
                         and state.get("previous") == (self.history[index - 1] if index else None),
                         "retention history abandons committed journal predecessors")
                _require(set(state) == {"format", "job", "job_sha256", "used", "previous", "receipt"}
                         and state["format"] == FORMAT and canonical.dumps(state["job"]) == canonical.dumps(self.job)
                         and state["job_sha256"] == self.job_hash and type(state["used"]) is int
                         and 0 <= state["used"] <= CAPS["per_job"], "retention job or counter mismatch")
                self._validate_receipt(state["receipt"], artifacts)
                if self.promoted_source is None and state["receipt"]["status"] == "promoted":
                    self.promoted_source = _read(artifacts, state["receipt"]["rounds"][-1]["output"]).decode()
                chain.append(state)
                ref = state["previous"]
            _require(len(chain) == len(self.history), "retention history omits committed snapshots")
            used, previous, proposals = 0, None, {}
            for state in reversed(chain):
                receipt = state["receipt"]
                pending = receipt["status"] == "pending"
                proposal_id = receipt["proposal_id"]
                _require(type(proposal_id) is int and proposal_id > 0, "invalid model proposal ordinal")
                if previous is not None and proposal_id != previous["proposal_id"]:
                    _require(proposal_id > previous["proposal_id"], "model proposal ordinal was replayed")
                if previous is not None and proposal_id == previous["proposal_id"]:
                    stable = ("raw_response", "proposal", "baseline", "original_result", "baseline_result", "selected", "old_unresolved")
                    _require(all(canonical.dumps(receipt[k]) == canonical.dumps(previous[k]) for k in stable),
                             "same-proposal evidence changed")
                    old_rounds, new_rounds = previous["rounds"], receipt["rounds"]
                    _require(len(new_rounds) == len(old_rounds) + (1 if pending else 0), "round inventory changed")
                    for old_row, new_row in zip(old_rounds, new_rounds):
                        _require(all(canonical.dumps(old_row[k]) == canonical.dumps(new_row[k])
                                     for k in old_row if k != "result"), "dispatched round input changed")
                        if old_row["result"] is not None:
                            _require(old_row["result"] == new_row["result"], "completed result changed")
                if pending:
                    proposals[proposal_id] = proposals.get(proposal_id, 0) + 1
                    _require(proposals[proposal_id] <= CAPS["per_proposal"], "proposal recheck cap exceeded")
                _require(state["used"] == used + (1 if pending else 0), "retention counter was refunded or skipped")
                if pending:
                    _require(receipt["rounds"][-1]["ordinal"] == state["used"], "dispatch ordinal mismatch")
                if previous and previous["status"] == "pending":
                    _require(not pending and receipt["proposal_id"] == previous["proposal_id"], "pending dispatch replaced")
                used, previous = state["used"], receipt
            self.used, self.last_receipt = chain[0]["used"], chain[0]["receipt"]
            self.last_proposal_id = self.last_receipt["proposal_id"]
            # An interrupted dispatch remains consumed. No mechanical result is
            # inferred; a fresh provider proposal can continue with the old B.
            if self.last_receipt["status"] == "pending":
                artifacts = agent_memory.restore(self.pkg, self.ref)
                artifacts.pop("payload.json")
                receipt = copy.deepcopy(self.last_receipt)
                receipt.update(status="infrastructure_failure", reason="interrupted native dispatch; budget consumed")
                self._save(receipt, artifacts)
        except (Ineligible, KeyError, TypeError, ValueError, AttributeError, IndexError, RecursionError, proof_fragments.FragmentError) as exc:
            raise blocked("STALE_OR_UNBOUND_EVIDENCE", "proof retention: " + str(exc)) from None

    def _validate_receipt(self, receipt: dict, artifacts: dict) -> None:
        _require(receipt.get("format") == FORMAT and receipt.get("job_sha256") == self.job_hash
                 and canonical.dumps(receipt.get("caps")) == canonical.dumps(CAPS)
                 and receipt.get("authority") == AUTHORITY, "invalid receipt identity")
        status = receipt.get("status")
        _require(status in {"pending", "promoted", "ineligible", "no_progress", "budget_exhausted", "infrastructure_failure"},
                 "invalid receipt outcome")
        raw = _read(artifacts, receipt["raw_response"])
        proposal = _read(artifacts, receipt["proposal"]).decode()
        baseline = _read(artifacts, receipt["baseline"]).decode()
        original_result = canonical.loads(_read(artifacts, receipt["original_result"]))
        baseline_result = canonical.loads(_read(artifacts, receipt["baseline_result"]))
        _require(isinstance(raw.decode(), str), "invalid raw response")
        rounds = receipt["rounds"]
        _require(isinstance(rounds, list) and len(rounds) <= CAPS["per_proposal"], "invalid proposal recheck count")
        if not rounds:
            _require(status in {"ineligible", "budget_exhausted", "infrastructure_failure"}, "receipt lacks required native dispatch")
            return
        selected = receipt["selected"]
        old = unresolved(self.frozen, baseline, baseline_result, self.tc, self.policy)
        _require(receipt["old_unresolved"] == old and isinstance(selected, list) and bool(selected)
                 and selected == [n for n in old if n in selected], "receipt selected set is not native unresolved")
        # The same exact scaffold/body validation used before dispatch is replayed.
        proof_fragments.validate_focused_candidate(proposal, self.frozen, baseline, selected, self.tc["pin"])
        working, result, reverted = proposal, original_result, set()
        for index, row in enumerate(rounds):
            _require(type(row["ordinal"]) is int and 1 <= row["ordinal"] <= CAPS["per_job"]
                     and (index == 0 or row["ordinal"] == rounds[index - 1]["ordinal"] + 1), "bad persistent ordinal")
            _require(_read(artifacts, row["input"]).decode() == working
                     and canonical.dumps(canonical.loads(_read(artifacts, row["input_result"]))) == canonical.dumps(result),
                     "round input changed")
            errors, _ = native(working, result, self.tc, self.policy)
            _require(result["ok"] is False, "reversion input is not a native failure")
            output, copied = reversion(baseline, working, errors, [n for n in selected if n not in reverted])
            _require(canonical.dumps(copied) == canonical.dumps(row["reverted"])
                     and _read(artifacts, row["output"]).decode() == output, "round is not exact authorized slice copying")
            reverted.update(r["name"] for r in copied)
            working = output
            if row["result"] is None:
                _require(index == len(rounds) - 1 and status in {"pending", "infrastructure_failure", "budget_exhausted"}, "missing round result")
                break
            result = canonical.loads(_read(artifacts, row["result"]))
            if index + 1 < len(rounds):
                _require(result.get("ok") is False, "continued after successful native result")
        if status == "promoted":
            new = unresolved(self.frozen, working, result, self.tc, self.policy)
            _require(receipt["new_unresolved"] == new and set(new) < set(old), "receipt promotion lacks strict native progress")
            proof_fragments.validate_focused_candidate(working, self.frozen, baseline, selected, self.tc["pin"])

    def _save(self, receipt: dict, artifacts: dict) -> None:
        state = {"format": FORMAT, "job": self.job, "job_sha256": self.job_hash,
                 "used": self.used, "previous": self.ref, "receipt": receipt}
        saved = agent_memory.capture_context(self.pkg, self.stage, state, extra_artifacts=artifacts)
        self.ref, self.last_receipt = saved["snapshot_ref"], copy.deepcopy(receipt)
        self.history.append(self.ref)
        if receipt["status"] == "promoted":
            self.promoted_source = _read(artifacts, receipt["rounds"][-1]["output"]).decode()

    def summary(self) -> dict:
        receipt = self.last_receipt
        return {"format": FORMAT, "authority": AUTHORITY, "job_sha256": self.job_hash,
                "rechecks_used": self.used, "caps": CAPS.copy(), "receipt_snapshot": self.ref,
                "last": None if receipt is None else {k: receipt[k] for k in
                    ("proposal_id", "status", "reason", "selected", "old_unresolved", "new_unresolved")},
                "reverted": [] if receipt is None else [r["name"] for row in receipt["rounds"] for r in row["reverted"]]}

    def attempt(self, *, baseline: str, baseline_result: dict, proposal: str, raw_response: str,
                failed_result: dict, selected: list[str] | None, proposal_id: int,
                evaluate: Callable[[str, float], dict], deadline: float | None = None) -> tuple[str, dict] | None:
        if type(proposal_id) is not int or proposal_id <= self.last_proposal_id:
            raise blocked("STALE_OR_UNBOUND_EVIDENCE", "proof retention model proposal ordinal was replayed")
        self.last_proposal_id = proposal_id
        artifacts = {}
        receipt = {"format": FORMAT, "authority": AUTHORITY, "job_sha256": self.job_hash, "caps": CAPS.copy(),
            "proposal_id": proposal_id, "status": "ineligible", "reason": "not evaluated", "selected": selected,
            "old_unresolved": None, "new_unresolved": None, "rounds": [],
            "raw_response": _ref(artifacts, "raw-response.txt", raw_response.encode()),
            "proposal": _ref(artifacts, "original-proposal.lean", proposal.encode()),
            "original_result": _ref(artifacts, "original-result.json", canonical.dumps(failed_result)),
            "baseline": _ref(artifacts, "baseline.lean", baseline.encode()),
            "baseline_result": _ref(artifacts, "baseline-result.json", canonical.dumps(baseline_result))}
        working, result, reverted = proposal, failed_result, set()
        try:
            old = unresolved(self.frozen, baseline, baseline_result, self.tc, self.policy)
            receipt["old_unresolved"] = old
            if selected is None:
                selected = old
                receipt["selected"] = selected
            _require(bool(selected) and selected == [n for n in old if n in selected], "selection is not currently unresolved")
            proof_fragments.validate_focused_candidate(proposal, self.frozen, baseline, selected, self.tc["pin"])
            for round_number in range(CAPS["per_proposal"]):
                if self.used >= CAPS["per_job"] or (deadline is not None and time.monotonic() >= deadline):
                    receipt.update(status="budget_exhausted", reason="native recheck job cap or deadline reached")
                    break
                errors, _ = native(working, result, self.tc, self.policy)
                _require(result["ok"] is False, "original candidate is not a failed native build")
                output, copied = reversion(baseline, working, errors, [n for n in selected if n not in reverted])
                row = {"ordinal": self.used + 1, "reverted": copied,
                    "input": _ref(artifacts, f"round-{round_number}-input.lean", working.encode()),
                    "input_result": _ref(artifacts, f"round-{round_number}-input.json", canonical.dumps(result)),
                    "output": _ref(artifacts, f"round-{round_number}-output.lean", output.encode()), "result": None}
                receipt["rounds"].append(row)
                receipt.update(status="pending", reason="native recheck dispatched; counter consumed before execution")
                self.used += 1
                self._save(receipt, artifacts)
                timeout = self.policy["build_timeout_seconds"]
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        receipt.update(status="budget_exhausted", reason="deadline expired while reserving native recheck; counter consumed")
                        break
                    timeout = min(timeout, remaining)
                result = evaluate(output, timeout)
                row["result"] = _ref(artifacts, f"round-{round_number}-result.json", canonical.dumps(result))
                working = output
                reverted.update(r["name"] for r in copied)
                if result.get("ok") is True:
                    new = unresolved(self.frozen, working, result, self.tc, self.policy)
                    receipt["new_unresolved"] = new
                    proof_fragments.validate_focused_candidate(working, self.frozen, baseline, selected, self.tc["pin"])
                    if set(new) < set(old):
                        receipt.update(status="promoted", reason="fresh whole-module success with strictly fewer native unresolved declarations")
                        self._save(receipt, artifacts)
                        return working, result
                    receipt.update(status="no_progress", reason="successful native rebuild did not strictly reduce unresolved set")
                    break
                # Commit the observed failure before another dispatch; never
                # overwrite the pending transition or refund its budget.
                receipt.update(status="ineligible", reason="native recheck failed; further mapping required")
                self._save(receipt, artifacts)
            else:
                receipt.update(status="budget_exhausted", reason="two native rechecks consumed for this model proposal")
        except (Ineligible, proof_fragments.FragmentError) as exc:
            receipt.update(status="ineligible", reason=str(exc))
        except InfrastructureError as exc:
            receipt.update(status="infrastructure_failure", reason=str(exc))
            _ref(artifacts, "infrastructure-error.json", canonical.dumps({"message": str(exc),
                 "diagnostics": [d.to_json() for d in exc.diagnostics]}))
            self._save(receipt, artifacts)
            raise
        self._save(receipt, artifacts)
        return None
