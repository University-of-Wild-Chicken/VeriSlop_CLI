"""Supervisor replay of closed review probes; agents supply values, never commands.

Exact decidable Python residuals and pinned VSCore 0.3 kernel probes are admitted. A
sampled residual, out-of-scope input, missing checker or failed execution cannot
confirm a rejection. Receipts are ordinary review outputs, not milestone evidence.
"""
from __future__ import annotations

import ast
import math
import re
import time
from typing import Any

from . import canonical, contract, dsl, fsutil, schemas, segment, testing
from .claimcheck import evaluate_claim
from .errors import VeriSlopError, blocked
from .evidence import Evidence
from .export import verified_ir
from .package import Package
from .targets import python_target as pt
from .verifiers import VERIFIERS, verifier_hash
from .bridges.manifest import InvalidPackage, PackageReader

VERIFIER = "verislop.review-counterexample"
RECEIPT_FORMAT = "verislop.review-counterexample-receipt/0.2"
SUPPORTED_PROPOSAL_KINDS = ("target_case", "source_violation", "missing_requirement", "mechanical_failure")
STATUSES = ("CONFIRMED", "NOT_REPRODUCED", "UNSUPPORTED", "INFRASTRUCTURE_FAILURE")
MAX_PROPOSAL_BYTES = 65536
MAX_CALLS = 32
CHECKPOINT_MILESTONES = {
    "interpretation": {"INTERPRETED"},
    "formal_contract": {"INTERPRETED", "FORMALIZED", "TYPECHECKED", "PROVED"},
    "implementation": {"INTERPRETED", "FORMALIZED", "TYPECHECKED", "PROVED", "IMPLEMENTED", "LINKED"},
    "release": {"INTERPRETED", "FORMALIZED", "TYPECHECKED", "PROVED", "IMPLEMENTED", "LINKED", "TESTED", "END_TO_END_VERIFIED"},
}
ROOTS = {"INTERPRETED": "interpretation_root", "FORMALIZED": "contract_input_root",
         "TYPECHECKED": "contract_input_root", "PROVED": "contract_input_root",
         "IMPLEMENTED": "implementation_root", "LINKED": "link_root", "TESTED": "test_root",
         "END_TO_END_VERIFIED": "closure_root"}


def bound_roots(pkg: Package, checkpoint: str) -> dict[str, str | None]:
    """Current roots belonging to this checkpoint; later-stage growth is unrelated."""
    names = {ROOTS[milestone] for milestone in CHECKPOINT_MILESTONES[checkpoint]} - {"closure_root"}
    return {name: getattr(pkg, name)() for name in sorted(names)}


def _wire_valid(value: Any, depth: int = 0) -> bool:
    try:
        pt.check_wire(value, limits={"depth": 32 - depth, "string_chars": 1024, "integer_digits": 1024})
        return True
    except (ValueError, TypeError, RecursionError):
        return False


def validate_proposal(obj: Any) -> list[str]:
    """Closed syntax only. Applicability, sort and claim checks belong to replay."""
    if not isinstance(obj, dict) or obj.get("kind") not in SUPPORTED_PROPOSAL_KINDS:
        return ["proposal must name one supported kind"]
    kind = obj["kind"]
    fields = {"target_case": {"kind", "obligation_id", "assignment"},
              "source_violation": {"kind", "obligation_id", "file", "ast_path", "rule"},
              "missing_requirement": {"kind", "start_byte", "end_byte", "quoted"},
              "mechanical_failure": {"kind", "claim_id"}}[kind]
    if set(obj) != fields:
        return [f"{kind} accepts exactly {', '.join(sorted(fields))}"]
    try:
        if len(canonical.dumps(obj)) > MAX_PROPOSAL_BYTES:
            return ["proposal exceeds byte budget"]
    except (ValueError, UnicodeError, RecursionError):
        return ["proposal is not bounded canonical JSON"]
    if kind == "target_case":
        if not isinstance(obj["obligation_id"], str) or not obj["obligation_id"] or len(obj["obligation_id"]) > 256:
            return ["obligation_id must be a bounded nonempty string"]
        if not isinstance(obj["assignment"], list) or len(obj["assignment"]) > 32 or not all(_wire_valid(v) for v in obj["assignment"]):
            return ["assignment must contain bounded strict tagged values"]
    elif kind == "source_violation":
        if (not all(type(obj[key]) is str and obj[key] for key in ("obligation_id", "file", "ast_path", "rule"))
                or len(obj["obligation_id"]) > 256 or len(obj["file"]) > 256 or len(obj["ast_path"]) > 4096
                or len(obj["rule"]) > 128 or not re.fullmatch(r"[A-Z][A-Z0-9_]*", obj["rule"])):
            return ["source_violation requires bounded exact source/AST/rule identifiers"]
    elif kind == "mechanical_failure":
        if not isinstance(obj["claim_id"], str) or not obj["claim_id"] or len(obj["claim_id"]) > 512:
            return ["claim_id must be a bounded nonempty string"]
    elif (type(obj["start_byte"]) is not int or type(obj["end_byte"]) is not int or
          not 0 <= obj["start_byte"] < obj["end_byte"] or
          not isinstance(obj["quoted"], str) or len(obj["quoted"].encode("utf-8")) > 16384):
        return ["missing_requirement needs a nonempty exact byte span and bounded UTF-8 quote"]
    return []


class _ReplayUnsupported(Exception):
    pass


class _AmbiguousClaims(_ReplayUnsupported):
    def __init__(self, claim_id: str):
        self.claim_id = claim_id
        super().__init__(f"duplicate claim ID in checkpoint inventory: {claim_id}")


class _Inputs:
    def __init__(self, pkg: Package):
        self.pkg = pkg
        self.reader = PackageReader(pkg.root)
        self.hashes: dict[str, str] = {}

    def bytes(self, path) -> bytes:
        rel = self.pkg.rel(path)
        item = self.reader.read(rel, keep=True)
        self.hashes[rel] = item.sha256
        return item.data

    def json(self, path) -> dict:
        obj = canonical.loads(self.bytes(path))
        if not isinstance(obj, dict):
            raise _ReplayUnsupported("bound input must be an object")
        return obj

    def bind(self, path, *, sha256: str, size: int) -> None:
        """Retain an inventory binding without retaining compiled artifact bytes."""
        item = self.reader.read(self.pkg.rel(path))
        self.hashes[item.path] = item.sha256
        if (item.sha256, item.size) != (sha256, size):
            raise _ReplayUnsupported("mechanical inventory artifact changed: " + item.path)


def _claim(c: dict) -> dict:
    return {"claim_id": c["claim_id"], "obligation_id": c.get("obligation"),
            "revision": c.get("revision"), "accepted_statement_hash": c.get("accepted_statement_hash"),
            "result_predicate": c.get("result_predicate", "milestone-pass/0.1")}


def _context_claims(pkg: Package, checkpoint: str, inputs: _Inputs) -> tuple[dict[str, dict], dict]:
    definitions: dict[str, dict] = {}
    contract_ids: set[str] = set()
    def insert(c: dict, *, inherited: bool = False) -> None:
        cid = c["claim_id"]
        if cid in definitions:
            original = definitions[cid]
            if not (inherited and cid in contract_ids
                    and original.get("milestone") in {"INTERPRETED", "FORMALIZED", "TYPECHECKED", "PROVED"}
                    and all(key in c for key in original)
                    and canonical.dumps({key: c[key] for key in original}) == canonical.dumps(original)):
                raise _AmbiguousClaims(cid)
        definitions[cid] = c

    parameters: dict = {}
    paths = []
    if checkpoint != "interpretation":
        paths.append(pkg.path("claims"))
    if checkpoint in ("implementation", "release"):
        paths.append(pkg.path("closure") / "implementation-claims.json")
    for path in paths:
        if path.is_file():
            document = inputs.json(path)
            is_implementation = path.name == "implementation-claims.json"
            if is_implementation:
                parameters = document.get("parameters", {})
            inherited = (is_implementation and document.get("schema_version") == "0.2"
                         and document.get("format") == "verislop.implementation-claims/0.2"
                         and document.get("backend") in ("verislop.backend.vscore/0.1", "verislop.backend.vscore/0.3"))
            seen: set[str] = set()
            for c in document.get("claims", []):
                if c["claim_id"] in seen:
                    raise _AmbiguousClaims(c["claim_id"])
                seen.add(c["claim_id"])
                insert(c, inherited=inherited)
            if not is_implementation:
                contract_ids.update(seen)
    if pkg.path("prompt").is_file():
        insert({"claim_id": "INTERPRETATION:request", "obligation": None,
            "milestone": "INTERPRETED", "required": True, "applicable": True,
            "verifier": "verislop.interpretation-recorder", "root_kind": "interpretation_root",
            "result_predicate": "interpretation-coverage/0.1"})
    return definitions, parameters


def _review_context(pkg: Package, checkpoint: str, definitions: dict[str, dict], parameters: dict) -> dict:
    from .backends import registry
    from .generate import CLOSURE_CLAIMS
    from .lifecycle import MILESTONES

    fields = ("tier", "target", "endpoint", "require_state", "require_tests", "tests_flag", "policy")
    request = pkg.meta().get("requested", {})
    requested = {k: request[k] for k in fields if k in request}
    resolved = {k: parameters[k] for k in fields if k in parameters} if parameters else dict(requested)
    policy_source = "frozen_implementation_parameters" if parameters else ("package_request" if requested else "unspecified")
    backend, backend_diags = registry.frozen_backend(pkg)
    if backend is None and not backend_diags:
        backend = registry.select(resolved.get("tier"), resolved.get("target"), resolved.get("endpoint"))
    native_release = (checkpoint == "release" and not backend_diags and backend is not None
                      and backend["id"] == registry.PYTHON_ID)
    phase = ("native_pre_finalization" if native_release else
             "vscore_post_mechanical" if checkpoint == "release" and backend is not None and backend["id"] in (registry.VSCORE_ID, registry.VSCORE3_ID) else
             "unresolved_release" if checkpoint == "release" else checkpoint)
    finalization = dict(CLOSURE_CLAIMS)
    scope = {}
    for cid, c in sorted(definitions.items()):
        milestone = c.get("milestone")
        required, applicable = c.get("required") is True, c.get("applicable") is True
        exact_final = (cid in finalization and c.get("verifier") == "verislop.closure"
                       and "obligation" in c and c["obligation"] is None
                       and "milestone" in c and milestone is None
                       and c.get("pass_predicate") == finalization[cid])
        producer = {"INTERPRETED": "interpret", "FORMALIZED": "formalize", "TYPECHECKED": "accept",
                    "PROVED": "accept", "IMPLEMENTED": "generate", "LINKED": "link",
                    "TESTED": "test", "END_TO_END_VERIFIED": "verify"}.get(milestone, "registered_internal_claim")
        if exact_final:
            producer = "verify"
        if not required or not applicable:
            disposition, reason = "OUT_OF_SCOPE", "claim is not both required and applicable"
        elif milestone in MILESTONES and milestone not in CHECKPOINT_MILESTONES[checkpoint]:
            disposition, reason = "FUTURE", "producer stage follows this checkpoint"
        elif exact_final and native_release:
            disposition, reason = "FUTURE", "native finalization follows release review; final verify must discharge this claim"
        elif milestone is None and checkpoint != "release":
            disposition, reason = "OUT_OF_SCOPE", "internal release claim is outside this checkpoint"
        else:
            disposition, reason = "CURRENT", "required applicable claim at the current producer phase"
        scope[cid] = {"disposition": disposition, "required": required, "applicable": applicable,
                      "milestone": milestone, "producer_stage": producer, "reason": reason}

    allowed = CHECKPOINT_MILESTONES[checkpoint]
    current = set(allowed)
    if checkpoint == "release":
        # Unknown policy keeps the broad historical scope. Neither absent evidence
        # nor an optional lifecycle PENDING outcome changes the producer schedule.
        state = resolved.get("require_state")
        if state in MILESTONES:
            current = set(MILESTONES[:MILESTONES.index(state) + 1])
            if resolved.get("require_tests") is False and state != "TESTED":
                current.discard("TESTED")
            if resolved.get("require_tests") is True or resolved.get("tests_flag") == "require_tests":
                current.add("TESTED")
            requested_state = requested.get("require_state")
            if requested_state in MILESTONES and MILESTONES.index(requested_state) > MILESTONES.index(state):
                current.update(MILESTONES[:MILESTONES.index(requested_state) + 1])
        current.update(s["milestone"] for s in scope.values()
                       if s["disposition"] == "CURRENT" and s["milestone"] in MILESTONES)
    return {"format": "verislop.review-context/0.1", "checkpoint": checkpoint, "review_phase": phase,
            "requested_assurance": requested, "resolved_assurance": resolved, "policy_source": policy_source,
            "current_milestones": [m for m in MILESTONES if m in current],
            "outside_checkpoint_milestones": [m for m in MILESTONES if m not in current],
            "claims": scope,
            "current_required_claim_ids": [cid for cid, s in scope.items() if s["disposition"] == "CURRENT"],
            "future_required_claim_ids": [cid for cid, s in scope.items() if s["disposition"] == "FUTURE"]}


def review_context(pkg: Package, checkpoint: str) -> dict:
    """Phase/assurance information; never a claim outcome or an acceptance vote."""
    inputs = _Inputs(pkg)
    try:
        definitions, parameters = _context_claims(pkg, checkpoint, inputs)
        return _review_context(pkg, checkpoint, definitions, parameters)
    except _AmbiguousClaims as exc:
        raise blocked("ORPHAN_CLAIM", str(exc), claims=[exc.claim_id]) from None
    finally:
        inputs.reader.close()


def _definitions(pkg: Package, checkpoint: str, inputs: _Inputs) -> dict[str, dict]:
    definitions, parameters = _context_claims(pkg, checkpoint, inputs)
    context = _review_context(pkg, checkpoint, definitions, parameters)
    return {cid: definitions[cid] for cid in context["current_required_claim_ids"]}


def mechanical_claim_ids(pkg: Package, checkpoint: str) -> list[str]:
    """Supervisor discovery for packets; returns only claims admitted at this checkpoint."""
    inputs = _Inputs(pkg)
    try:
        return sorted(_definitions(pkg, checkpoint, inputs))
    except _AmbiguousClaims as exc:
        raise blocked("ORPHAN_CLAIM", str(exc), claims=[exc.claim_id]) from None
    finally:
        inputs.reader.close()


def _retained_mechanical_evidence(inputs: _Inputs, directory, row: dict, terminal: bool) -> Evidence | None:
    refs = row["evidence_refs"]
    if not refs:
        return None
    if len(refs) != 1 or not refs[0].startswith("evidence:"):
        raise _ReplayUnsupported("mechanical claim has ambiguous evidence references")
    eid = refs[0][len("evidence:"):]
    record_path = directory / ("evidence/" + eid + ".json" if terminal else "consumed/" + eid + "/record.json")
    record = inputs.json(record_path)
    raw_path = directory / (record["raw_result_ref"] if terminal else "consumed/" + eid + "/raw.json")
    raw_bytes = inputs.bytes(raw_path)
    raw = canonical.loads(raw_bytes)
    body = {k: v for k, v in record.items() if k != "evidence_id"}
    if (schemas.validate("evidence", record) or record.get("evidence_id") != eid
            or "ev-" + canonical.sha256_hex(canonical.dumps(body))[:32] != eid
            or canonical.digest(raw_bytes) != record.get("raw_result_hash")
            or not isinstance(raw, dict) or raw.get("claim_id") != row["claim_id"]
            or record.get("claim_id") != row["claim_id"]):
        raise _ReplayUnsupported("retained mechanical evidence is corrupt or assigned to another claim")
    return Evidence(record, raw, [])


def _post_mechanical_assessment(pkg: Package, cid: str, inputs: _Inputs, backend):
    """Replay a registered VSCore observation, never a report flag or projection."""
    pointer = inputs.json(pkg.path("closure") / "current.json")
    rel = pointer["mechanical_result"]
    fsutil.check_relpath(rel)
    manifest = inputs.json(pkg.path("closure") / "manifest.json")
    if schemas.validate("closure-manifest", manifest):
        raise _ReplayUnsupported("mechanical input manifest is invalid")
    for entry in manifest["entries"]:
        inputs.bind(pkg.root / entry["path"], sha256=entry["sha256"], size=entry["size"])
    retained = inputs.json(pkg.root / rel)
    directory = (pkg.root / rel).parent
    for entry in retained["execution_inventory"]:
        inputs.bind(directory / entry["path"], sha256=entry["sha256"], size=entry["size"])

    # Preserve infrastructure diagnostics which mechanical_snapshot otherwise
    # wraps as an unavailable frozen snapshot. Neither check performs a rebuild.
    problems = backend.validate_frozen(pkg)
    if any(d.severity == "infrastructure" for d in problems):
        raise VeriSlopError("mechanical input validation could not complete", problems)
    if problems:
        raise _ReplayUnsupported("mechanical inputs are stale: " + "; ".join(d.message for d in problems))
    try:
        snapshot = backend.mechanical_snapshot(pkg)
        if snapshot is None or snapshot["mechanical_result_path"] != rel:
            raise _ReplayUnsupported("no current registered mechanical execution")
        if retained != {k: v for k, v in snapshot.items() if k != "mechanical_result_path"}:
            raise _ReplayUnsupported("mechanical result changed during replay")
        claims = backend._claims(pkg)
        claim = next((c for c in claims if c["claim_id"] == cid), None)
        if claim is None or not claim["required"] or not claim["applicable"]:
            raise _ReplayUnsupported("claim is absent from the current required mechanical inventory")
        selection = backend._selection(pkg)
        roots = backend._roots(pkg, selection, snapshot["closure_root"])
        if not roots.get(claim["root_kind"]) or not snapshot["closure_root"]:
            raise _ReplayUnsupported("current mechanical claim root is unavailable")
        row = next((r for r in snapshot["claims"] if r["claim_id"] == cid), None)
        if row is None:
            raise _ReplayUnsupported("mechanical execution omits the selected registered claim")
        terminal = backend._terminal(claim)
        evidence = _retained_mechanical_evidence(inputs, directory, row, terminal)
        if terminal:
            # Closure failure records can reflect tooling failure rather than a
            # failed target predicate. Do not reinterpret that failure as a veto.
            if snapshot["mechanical_status"] == "INFRASTRUCTURE_FAILURE":
                raise VeriSlopError("mechanical execution failed in infrastructure")
            assessment = evaluate_claim(claim, [evidence] if evidence else [], roots, claim["root_kind"])
            if assessment.outcome != row["outcome"]:
                raise _ReplayUnsupported("mechanical claim outcome differs from its current typed evidence")
        else:
            selected = backend._selected_evidence(pkg, selection, claims, roots)
            current = selected.get(cid)
            if ((current is None) != (evidence is None) or current is not None
                    and (current.record != evidence.record or current.result != evidence.result)):
                raise _ReplayUnsupported("mechanical claim does not retain its exact current selected evidence")
            nonfinal, _ = backend._nonfinal(pkg, selection, claims, roots, selected)
            checked_row = next((r for r in nonfinal if r["claim_id"] == cid), None)
            if checked_row != row:
                raise _ReplayUnsupported("mechanical claim differs from its current registered observation")
            assessment = evaluate_claim(claim, [current] if current else [], roots, claim["root_kind"])
            if assessment.outcome == "PASS" and row["outcome"] != "PASS":
                outcomes = {r["claim_id"]: r["outcome"] for r in nonfinal}
                if any(outcomes[p] != "PASS" for p in claim["premises"]):
                    # _nonfinal marks a child FAIL even for a missing or stale
                    # prerequisite. That alone is not an observed failure.
                    assessment.outcome, assessment.authorized = "PENDING", False
                    assessment.reason = "a frozen prerequisite is unresolved; no direct authorized failure"
                else:
                    # Registered materializer/source and linker/record checks
                    # supplement the typed evidence predicate in _nonfinal.
                    assessment.outcome, assessment.reason = row["outcome"], row["reason"]
        return claim, roots, assessment
    except backend.checker.EdgeFailure as exc:
        if any(d.severity == "infrastructure" for d in exc.diagnostics):
            raise VeriSlopError(str(exc), exc.diagnostics) from None
        raise _ReplayUnsupported(str(exc)) from None


def _mechanical(pkg: Package, checkpoint: str, proposal: dict, receipt: dict, inputs: _Inputs):
    c = _definitions(pkg, checkpoint, inputs).get(proposal["claim_id"])
    if c is None:
        raise _ReplayUnsupported("claim is not a required applicable claim at this checkpoint")
    from .backends import registry
    backend, problems = registry.frozen_backend(pkg)
    if checkpoint == "release" and problems:
        raise _ReplayUnsupported("frozen mechanical backend is unavailable: " + "; ".join(d.message for d in problems))
    post_mechanical = bool(checkpoint == "release" and backend
                           and backend["id"] in (registry.VSCORE_ID, registry.VSCORE3_ID))
    if post_mechanical:
        c, roots, assessment = _post_mechanical_assessment(pkg, c["claim_id"], inputs, registry.closure_backend(pkg))
    else:
        roots = pkg.roots()
        from .closure import closure_input_root
        roots["closure_root"] = closure_input_root(pkg)
        default = c.get("root_kind", ROOTS.get(c.get("milestone"), "closure_root"))
        assessment = evaluate_claim(c, pkg.evidence.for_claim(c["claim_id"]), roots, default)
    default = c.get("root_kind", ROOTS.get(c.get("milestone"), "closure_root"))
    receipt["claim"] = _claim(c)
    receipt["expected"] = {"outcome": "PASS", "root_kind": default, "root": roots.get(default)}
    receipt["observed"] = {"outcome": assessment.outcome, "reason": assessment.reason,
                           "evidence_id": assessment.evidence.id if assessment.evidence else None}
    # A post-mechanical receipt binds the original and retained record/raw files
    # through the complete inventories. Legacy aliases resolve only in the
    # top-level EvidenceStore and cannot name a selected bridge-local record.
    if assessment.evidence and not post_mechanical:
        receipt["input_bindings"]["evidence:" + assessment.evidence.id] = canonical.digest_json(assessment.evidence.record)
        receipt["input_bindings"]["evidence-result:" + assessment.evidence.id] = canonical.digest_json(assessment.evidence.result)
    if assessment.outcome == "PASS":
        receipt["status"] = "NOT_REPRODUCED"
    elif assessment.authorized and assessment.outcome in ("FAIL", "UNSUPPORTED"):
        receipt["status"] = "CONFIRMED"
    elif any(d.severity == "infrastructure" for d in assessment.diagnostics):
        receipt["status"] = "INFRASTRUCTURE_FAILURE"
    else:
        raise _ReplayUnsupported("no current authorized observed failure; missing or stale evidence is unresolved")


def _missing(pkg: Package, checkpoint: str, proposal: dict, receipt: dict, inputs: _Inputs):
    if checkpoint not in ("interpretation", "formal_contract"):
        raise _ReplayUnsupported("request coverage probes apply only to interpretation/formal-contract review")
    prompt = inputs.bytes(pkg.path("prompt"))
    ledger = inputs.json(pkg.path("interpretation"))
    request = ledger["request"]
    if request["document_hash"] != canonical.digest(prompt) or request["byte_length"] != len(prompt):
        raise _ReplayUnsupported("ledger does not bind to exact request bytes")
    a, b = proposal["start_byte"], proposal["end_byte"]
    if (a, b) not in segment.segments(prompt) or prompt[a:b] != proposal["quoted"].encode("utf-8"):
        raise _ReplayUnsupported("probe is not an exact segmented request span and quote")
    spans = [(c["start_byte"], c["end_byte"]) for c in ledger["clauses"]]
    missing = (a, b) in segment.uncovered(prompt, spans)
    receipt["claim"] = {"claim_id": "INTERPRETATION:request", "obligation_id": None, "revision": None,
                        "accepted_statement_hash": None, "result_predicate": "interpretation-coverage/0.1"}
    receipt["expected"] = {"span_disposition_present": True}
    receipt["observed"] = {"span_disposition_present": not missing, "start_byte": a, "end_byte": b,
                           "quoted": proposal["quoted"], "limitation": "structural span coverage, not semantic interpretation fidelity"}
    receipt["status"] = "CONFIRMED" if missing else "NOT_REPRODUCED"


def _decode(value: dict, sort: Any, profile: dsl.Profile) -> Any:
    try:
        if isinstance(value, dict) and set(value) == {"encoding_budget"}:
            raise pt.WireBudgetExceeded("target value exceeds harness transport budget")
        pt.check_wire(value, limits={"string_chars": 1024, "integer_digits": 1024})
    except pt.WireBudgetExceeded as exc:
        raise dsl.BudgetExceeded(f"{exc}; not a target-profile counterexample") from None
    except ValueError as exc:
        raise _ReplayUnsupported(f"wire value is not closed and canonical: {exc}") from None
    decoded = pt.decode_result(value, sort, profile)
    if not dsl.value_has_sort(decoded, sort, profile):
        raise _ReplayUnsupported("assignment is outside the accepted binder sort")
    # Strict re-encoding closes permissive legacy decoder branches.
    if pt.encode_arg(decoded, sort, profile) != value:
        raise _ReplayUnsupported("wire value differs from its accepted sort encoding")
    return decoded


def _decidable(formula: Any, profile: dsl.Profile | None = None):
    if isinstance(formula, dict):
        if formula.get("tag") in dsl.QUANTIFIERS and not dsl.is_finite(formula["sort"], profile):
            raise _ReplayUnsupported("unbounded residual quantifiers cannot confirm counterexamples")
        for value in formula.values():
            _decidable(value, profile)
    elif isinstance(formula, list):
        for value in formula:
            _decidable(value, profile)


class _BoundedHarness(pt.Harness):
    def __init__(self, *args, deadline: float, **kwargs):
        self.deadline = deadline
        super().__init__(*args, **kwargs)

    def _recv(self, timeout):
        return super()._recv(min(timeout, max(0.0, self.deadline - time.monotonic())))


class _BoundedEvaluator(dsl.Evaluator):
    """Bound supervisor work as well as target calls; exhaustion proves no defect."""
    def __init__(self, *args, deadline: float, **kwargs):
        self.deadline = deadline
        super().__init__(*args, **kwargs)

    def _tick(self):
        if time.monotonic() >= self.deadline:
            raise dsl.BudgetExceeded("counterexample oracle deadline exhausted")
        super()._tick()

    def term(self, term, env):
        if term["tag"] in ("nat", "int") and len(term["value"].lstrip("-")) > 1024:
            raise dsl.BudgetExceeded("counterexample oracle numeral budget exhausted")
        if term["tag"] in dsl.NAT_OPS + dsl.INT_OPS:
            self._tick()
            a, b = self.term(term["left"], env), self.term(term["right"], env)
            if term["tag"] in ("mul", "int_mul") and a.bit_length() + b.bit_length() > 4096:
                raise dsl.BudgetExceeded("counterexample oracle arithmetic budget exhausted")
            result = (a + b if term["tag"] in ("add", "int_add") else
                      (max(0, a - b) if term["tag"] == "sub" else
                       (a - b if term["tag"] == "int_sub" else a * b)))
        else:
            result = super().term(term, env)
        if type(result) is int and result.bit_length() > 4096:
            raise dsl.BudgetExceeded("counterexample oracle arithmetic budget exhausted")
        return result


class _ObservedOracle(testing.Oracle):
    def __init__(self, harness, profile, bound, deadline):
        super().__init__(harness, profile, bound)
        self.deadline = deadline
        self.observations = []

    def _raw(self, sym, args):
        if self.calls >= MAX_CALLS:
            raise dsl.BudgetExceeded("target invocation budget exhausted")
        if time.monotonic() >= self.deadline:
            raise pt.HarnessError("timeout", "counterexample replay deadline exhausted")
        self.calls += 1
        spec = self.p.symbols[sym]
        try:
            enc = [pt.encode_arg(a, s, self.p) for a, s in zip(args, spec["args"])]
        except pt.WireBudgetExceeded as exc:
            raise dsl.BudgetExceeded(str(exc)) from None
        response = self.h.call(sym, enc)
        if (response.get("id") != self.h.calls or type(response.get("id")) is not int or
                response.get("op") not in ("result", "exception")):
            raise pt.HarnessError("protocol", "target response is not correlated to this invocation")
        self.observations.append({"symbol": sym, "arguments": enc, "response": response})
        if response["op"] == "exception":
            if set(response) != {"op", "id", "type", "message"}:
                raise pt.HarnessError("protocol", "target exception response has unknown fields")
            raise dsl.TargetFault("exception", f"target raised {response['type']}: {response['message']}")
        if set(response) != {"op", "id", "value"}:
            raise pt.HarnessError("protocol", "target result response has unknown fields")
        try:
            return _decode(response["value"], spec["result"], self.p)
        except (ValueError, TypeError, KeyError, _ReplayUnsupported) as exc:
            raise dsl.TargetFault("malformed", str(exc)) from None


def _validated_link(pkg, ir, digest, rec, profile_data, inventory, inputs):
    """Reconstruct legacy link metadata and require its current registered association."""
    from .materialize import symbols_for
    proposal = inputs.json(pkg.path("bridges") / "bindings.json")
    if schemas.validate("implementation-bindings", proposal):
        raise _ReplayUnsupported("implementation binding proposal is invalid")
    claims = inputs.json(pkg.path("closure") / "implementation-claims.json")
    if claims.get("bound_to", {}).get("accepted_ir") != digest:
        raise _ReplayUnsupported("implementation claims do not bind to the accepted IR")
    statements_path = contract.challenge_dir(pkg) / "statements.json"
    statements = inputs.json(statements_path)
    linkable = {c["obligation"] for c in claims["claims"] if c["milestone"] == "LINKED" and c["applicable"]}
    expected = []
    symbols, objects, ids = set(), set(), set()
    for b in proposal["bindings"]:
        sid, key = b["symbol"], (b["object"]["file"], b["object"]["qualname"])
        if sid in symbols or key in objects or b["binding_id"] in ids or sid not in profile_data["symbols"]:
            raise _ReplayUnsupported("binding identities are missing or ambiguous")
        symbols.add(sid)
        objects.add(key)
        ids.add(b["binding_id"])
        obj, spec = inventory.find(*key), profile_data["symbols"][sid]
        arity = len(spec["args"])
        if (obj is None or obj["kind"] != "function" or obj["decorated"] or obj["varargs"] or
                obj["kwonly_required"] or not obj["positional"] - obj["defaults"] <= arity <= obj["positional"]):
            raise _ReplayUnsupported("proposed object is not a compatible exact top-level function")
        covered = sorted(oid for oid in ir["obligations"] if oid in linkable and
                         sid in symbols_for(oid, ir, profile_data, statements["statements"]))
        if set(b["obligations"]) - set(covered):
            raise _ReplayUnsupported("proposed binding claims unsupported obligation coverage")
        expected.append({"binding_id": b["binding_id"], "symbol": sid,
            "formal_declaration": {"lean_decl": spec["lean_decl"], "decl_hash": statements["declaration_hashes"][spec["lean_decl"]],
                                   "args": spec["args"], "result": spec["result"]},
            "implementation_object": {"file": obj["file"], "qualname": obj["qualname"], "source_hash": obj["source_hash"],
                                      "file_hash": inventory.files[obj["file"]], "lineno": obj["lineno"]},
            "obligations": covered, "serialization_profile": pt.profile_id(profile_data)})
    helpers = {(h["file"], h["qualname"]) for h in proposal["helpers"]}
    if any(o["public"] and (o["file"], o["qualname"]) not in objects | helpers for o in inventory.objects):
        raise _ReplayUnsupported("current executable inventory has an unaccounted public object")
    current = inputs.json(pkg.path("bridges") / "link.json")
    reconstructed = {"schema_version": "0.1", "artifact_kind": "link_record", "accepted_ir": digest,
        "implementation_root": pkg.implementation_root(), "serialization_profile": pt.profile_doc(profile_data),
        "bindings": sorted(expected, key=lambda b: b["binding_id"]),
        "correspondence": "structural identity and coverage only; semantic correspondence is not established at this tier"}
    from . import native_source
    packages = native_source.accepted_packages(ir, pkg.path("accepted") / "expressions")
    source = native_source.check_sources(
        {file: inputs.bytes(pkg.path("implementation") / file) for file in inventory.files},
        ir, profile_data, bindings=proposal, packages=packages)
    if source["enabled"]:
        reconstructed["native_source"] = source
        if not source["accepted"]:
            raise _ReplayUnsupported("current source does not satisfy the accepted native boundary")
    if current != reconstructed:
        raise _ReplayUnsupported("current link record differs from accepted declarations, proposal or exact source inventory")
    cid = f"LINKED:{rec['id']}@{rec['revision']}"
    claim = next((c for c in claims["claims"] if c["claim_id"] == cid and c["applicable"]), None)
    if claim is None or claim["verifier"] != "verislop.python-linker":
        raise _ReplayUnsupported("no registered link claim associates this guarantee with the target")
    assessment = evaluate_claim(claim, pkg.evidence.for_claim(cid), {"link_root": pkg.link_root()}, "link_root")
    if assessment.outcome != "PASS":
        raise _ReplayUnsupported("no current registered LINKED receipt establishes this target association")
    inputs.hashes["link-association:" + assessment.evidence.id] = canonical.digest_json(assessment.evidence.record)
    return {b["symbol"]: (b["implementation_object"]["file"], b["implementation_object"]["qualname"]) for b in current["bindings"]}


def _admit_python(pkg, inventory, inputs, profile: dsl.Profile | None = None):
    """Admit a pure syntax subset that cannot write or replace the harness channel.

    This is deliberately narrower than legacy campaigns. Unsupported imports,
    reflection, attributes and I/O must never furnish apparently faithful receipts.
    """
    if pt.profile_id(profile) == pt.PROFILE_ID_V2:
        from . import python_boundary
        sources = {path: inputs.bytes(pkg.path("implementation") / path) for path in inventory.files}
        proposal = inputs.json(pkg.path("bridges") / "bindings.json")
        typed = {b["object"]["file"] + ":" + b["object"]["qualname"]: profile.symbols[b["symbol"]]["args"]
                 for b in proposal["bindings"] if b["symbol"] in profile.symbols}
        checked = python_boundary.check_sources(sources, typed_args=typed, profile=profile.raw)
        if not checked["accepted"]:
            raise _ReplayUnsupported("current source failed registered ownership/closed-source admission: " +
                                     canonical.dumps(checked["diagnostics"]).decode())
        return
    allowed = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.If,
        ast.Assign, ast.Expr, ast.Raise, ast.Pass, ast.Name, ast.Load, ast.Store,
        ast.Constant, ast.Tuple, ast.List, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
        ast.IfExp, ast.Call, ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.Pow,
        ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt, ast.LtE,
        ast.Gt, ast.GtE, ast.Is, ast.IsNot)
    exceptions = {"ValueError", "TypeError", "RuntimeError", "ArithmeticError", "AssertionError"}
    data_profile = pt.profile_id(profile) == pt.PROFILE_ID_V2
    builtins = {"len", "sum", "list", "range"} if data_profile else set()
    if data_profile:
        allowed += (ast.Dict, ast.Subscript, ast.Slice, ast.ListComp, ast.comprehension,
                    ast.For, ast.AugAssign, ast.Break, ast.Continue, ast.Attribute)
    for path in inventory.files:
        if not path.endswith(".py"):
            continue
        source = inputs.bytes(pkg.path("implementation") / path)
        if len(source) > 2 * 1024 * 1024:
            raise _ReplayUnsupported("source exceeds narrow Python replay budget")
        tree = ast.parse(source, filename=path)
        functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        if functions & exceptions:
            raise _ReplayUnsupported("source shadows an admitted exception constructor")
        for node in tree.body:
            if not (isinstance(node, ast.FunctionDef) or
                    (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))):
                raise _ReplayUnsupported("narrow Python replay admits only pure top-level functions and docstrings")
        nodes = list(ast.walk(tree))
        if len(nodes) > 100000:
            raise _ReplayUnsupported("source exceeds narrow Python replay node budget")
        exception_calls = {id(node.exc) for node in nodes if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)
                           and isinstance(node.exc.func, ast.Name) and node.exc.func.id in exceptions
                           and not node.exc.keywords and all(isinstance(a, ast.Constant) for a in node.exc.args)}
        append_calls = {id(node) for node in nodes if data_profile and isinstance(node, ast.Call) and
                        isinstance(node.func, ast.Attribute) and node.func.attr == "append" and
                        isinstance(node.func.value, ast.Name) and not node.keywords and len(node.args) == 1}
        append_attributes = {id(node.func) for node in nodes if isinstance(node, ast.Call) and id(node) in append_calls}
        for node in nodes:
            if not isinstance(node, allowed):
                raise _ReplayUnsupported(f"Python replay does not admit {type(node).__name__}")
            if isinstance(node, ast.Name) and node.id.startswith("__"):
                raise _ReplayUnsupported("Python replay does not admit runtime reflection names")
            if isinstance(node, ast.FunctionDef) and (node.decorator_list or node.returns or getattr(node, "type_params", []) or
                    node.args.defaults or any(value is not None for value in node.args.kw_defaults) or
                    any(arg.annotation for arg in ast.walk(node.args) if isinstance(arg, ast.arg))):
                raise _ReplayUnsupported("Python replay does not admit evaluated function metadata")
            if isinstance(node, ast.Attribute) and id(node) not in append_attributes:
                raise _ReplayUnsupported("Python replay admits only a local list.append call; other attributes are unavailable")
            if isinstance(node, ast.Call) and id(node) not in append_calls and (not isinstance(node.func, ast.Name) or node.keywords or
                    (node.func.id not in functions | builtins and id(node) not in exception_calls)):
                raise _ReplayUnsupported("Python replay admits only direct pure-function calls and literal exceptions")
        exception_names = {id(node.func) for node in nodes if isinstance(node, ast.Call) and id(node) in exception_calls}
        for function in (node for node in tree.body if isinstance(node, ast.FunctionDef)):
            body_nodes = [node for statement in function.body for node in ast.walk(statement)]
            if any(isinstance(node, ast.FunctionDef) for node in body_nodes):
                raise _ReplayUnsupported("Python replay does not admit nested function scopes")
            locals_ = {arg.arg for arg in ast.walk(function.args) if isinstance(arg, ast.arg)}
            locals_.update(node.id for node in body_nodes if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store))
            for node in body_nodes:
                if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and
                        node.id not in functions | builtins | locals_ and id(node) not in exception_names):
                    raise _ReplayUnsupported(f"Python replay does not admit free name reference {node.id}")
            if any(isinstance(node, ast.comprehension) and node.is_async for node in body_nodes):
                raise _ReplayUnsupported("Python replay does not admit asynchronous comprehensions")
            if any(isinstance(node, ast.Call) and id(node) in append_calls and node.func.value.id not in locals_ for node in body_nodes):
                raise _ReplayUnsupported("append receiver must be a local variable")


def _source(pkg: Package, checkpoint: str, proposal: dict, receipt: dict, inputs: _Inputs):
    if checkpoint not in ("implementation", "release"):
        raise _ReplayUnsupported("source probes apply only to current Python implementation/release artifacts")
    from . import native_source
    from .backends.registry import frozen_backend, PYTHON_ID
    backend, problems = frozen_backend(pkg)
    if problems or not backend or backend["id"] != PYTHON_ID:
        raise _ReplayUnsupported("no registered Python source surface is available")
    ir, digest, _, problems = verified_ir(pkg)
    if problems or ir is None:
        raise _ReplayUnsupported("source replay requires a current accepted IR/certificate")
    inputs.json(pkg.path("accepted_ir"))
    inputs.json(pkg.root / ir["acceptance_certificate_ref"])
    rec = ir["obligations"].get(proposal["obligation_id"])
    if not rec or not rec["required"] or rec["role"] != "guarantee" or rec["kind"] == "non_vacuity":
        raise _ReplayUnsupported("source probe must name a required implementation guarantee")
    profile = inputs.json(contract.challenge_dir(pkg) / "profile.json")
    packages = native_source.accepted_packages(ir, pkg.path("accepted") / "expressions")
    for row in ir["obligations"].values():
        if row["formal"]["representation"] in ("contract_dsl", "contract_facets"):
            package_hash = row["formal"]["formula_ref"].rsplit("@", 1)[1]
            inputs.bytes(pkg.path("accepted") / "expressions" / (package_hash[7:] + ".json"))
    bindings = inputs.json(pkg.path("bridges") / "bindings.json")
    sources = {file: inputs.bytes(pkg.path("implementation") / file) for file in fsutil.list_files(pkg.path("implementation"))}
    checked = native_source.check_sources(sources, ir, profile, bindings=bindings, packages=packages)
    if not checked["enabled"] or rec["id"] not in checked["obligations"]:
        raise _ReplayUnsupported("this accepted guarantee has no admitted native source-check surface")
    scoped = checked["obligations"][rec["id"]]
    site = {"file": proposal["file"], "ast_path": proposal["ast_path"], "code": proposal["rule"]}
    matches = [row for row in scoped["diagnostics"] if all(row.get(key) == value for key, value in site.items())]
    if any(row["code"] in ("ANALYSIS_INCOMPLETE", "ANALYSIS_LIMIT", "SYNTAX_LIMIT", "SOURCE_LIMIT") for row in matches):
        raise _ReplayUnsupported("source analysis is incomplete; no concrete source-policy violation established")
    receipt["claim"] = {"claim_id": f"IMPLEMENTATION:{rec['id']}@{rec['revision']}",
        "obligation_id": rec["id"], "revision": rec["revision"],
        "accepted_statement_hash": rec["formal"]["statement_hash"], "result_predicate": "native-source-conformance/0.1"}
    receipt["expected"] = {"accepted_ir_hash": digest, "site": site, "source_conformance": True}
    receipt["observed"] = {"source_receipt": checked, "matching_diagnostics": matches}
    receipt["status"] = "CONFIRMED" if matches else "NOT_REPRODUCED"


def _vscore_target(pkg: Package, proposal: dict, receipt: dict, inputs: _Inputs, deadline: float):
    from . import leanbridge
    from .backends import vscore3
    from .bridges import vscore3_checker as checker
    from .targets import vscore3_replay as kernel, vscore3_target as target

    ir, digest, certificate, problems = verified_ir(pkg)
    if problems or ir is None or certificate is None:
        raise _ReplayUnsupported("VSCore target replay requires current accepted IR and certificate bindings")
    inputs.json(pkg.path("accepted_ir"))
    inputs.json(pkg.root / ir["acceptance_certificate_ref"])
    rec = ir["obligations"].get(proposal["obligation_id"])
    if (not rec or rec["role"] != "guarantee" or not rec["required"] or
            rec["kind"] in ("non_vacuity", "liveness_property", "resource_constraint")):
        raise _ReplayUnsupported("target probe must name a required functional implementation guarantee")
    formal = rec["formal"]
    if formal["representation"] not in ("contract_dsl", "source_facets"):
        raise _ReplayUnsupported("this accepted representation has no VSCore 0.3 value replay")
    expression_hash = formal["formula_ref"].rsplit("@", 1)[1]
    expression_path = pkg.path("accepted") / "expressions" / (expression_hash[7:] + ".json")
    package = inputs.json(expression_path)
    if inputs.hashes[pkg.rel(expression_path)] != expression_hash:
        raise _ReplayUnsupported("accepted formula package hash differs from actual bytes")
    from . import contract_values
    value = contract_values.value_package(package)
    if value is None:
        raise _ReplayUnsupported("source-only obligation has no value counterexample predicate")
    profile_ref = certificate["artifacts"]["profile"]
    profile_data = inputs.json(pkg.root / profile_ref["path"])
    if inputs.hashes[profile_ref["path"]] != profile_ref["sha256"]:
        raise _ReplayUnsupported("accepted carrier profile changed")
    profile = dsl.Profile.from_json(profile_data)
    dsl.check_package(value, profile)
    prefix, residual = dsl.prefix(value["formula"])
    _decidable(residual, profile)
    if len(prefix) != len(proposal["assignment"]):
        raise _ReplayUnsupported("assignment arity differs from accepted universal prefix")
    values = [_decode(v, sort, profile) for v, sort in zip(proposal["assignment"], prefix)]
    if not dsl.calls(residual):
        raise _ReplayUnsupported("accepted residual mentions no source-call symbol")
    try:
        selected = vscore3.selection(pkg)
        inputs.json(pkg.path("closure") / vscore3.SELECTION_FILE)
        inputs.json(pkg.path("bridges") / "bindings.json")
        bundle = pkg.path("bridges") / selected["bridge_id"]
        inputs.json(bundle / "plan.json")
        inputs.json(bundle / "artifacts.json")
        ctx = checker.load_context(bundle, selected["bridge_id"], selected["edge_id"])
        if (ctx.accepted_ir != ir or ctx.acceptance != certificate or ctx.accepted_profile != profile_data or
                rec["id"] not in ctx.obligations):
            raise _ReplayUnsupported("selected source is not associated with the current accepted guarantee")
        for artifact in ctx.slots.values():
            data = inputs.bytes(bundle / artifact["path"])
            if canonical.digest(data) != artifact["sha256"]:
                raise _ReplayUnsupported("selected bridge artifact differs from its exact manifest binding")
        source = inputs.bytes(pkg.path("implementation") / vscore3.SOURCE_FILE)
        if source != ctx.inputs["source"][1]:
            raise _ReplayUnsupported("delivered source differs from the exact selected source")
        spec = checker.derive_goal(ctx)
        transferred = kernel.ground(spec, value["formula"], values)
        goal_parts = None
        semantic = bundle / checker.SEMANTIC_DIR / checker.edge_key(selected["edge_id"])
        if semantic.exists():
            accepted, pending, diags = checker.verify_published(pkg, selected["bridge_id"], rebuild=False)
            if diags or pending or not any(row["edge_id"] == selected["edge_id"] for row in accepted):
                raise _ReplayUnsupported("published semantic modules are stale or unbound")
            cert = inputs.json(semantic / checker.CERTIFICATE)
            for reference in (cert["goal"], cert["implementation_ir"], *cert["builds"], *cert["accepted_modules"]):
                data = inputs.bytes(semantic / reference["path"])
                if canonical.digest(data) != reference["sha256"]:
                    raise _ReplayUnsupported("published semantic module input changed")
            goal_parts = {row["path"][len("accepted/" + target.GOAL_MODULE):]:
                          inputs.bytes(semantic / row["path"])
                          for row in cert["accepted_modules"] if row["module"] == target.GOAL_MODULE}
        receipt["claim"] = {"claim_id": "IMPLEMENTATION:" + rec["id"] + "@" + str(rec["revision"]),
            "obligation_id": rec["id"], "revision": rec["revision"],
            "accepted_statement_hash": formal["statement_hash"], "result_predicate": "accepted-functional-guarantee/0.1"}
        receipt["expected"] = {"accepted_ir_hash": digest, "assignment": proposal["assignment"], "predicate": True,
                               "semantics": target.SEMANTICS}
        tc = leanbridge.resolve_toolchain(certificate["toolchain"]["pin"])
        observed = kernel.check(tc, ctx, spec, transferred, deadline=deadline, goal_parts=goal_parts)
        receipt["observed"] = observed
        receipt["status"] = "NOT_REPRODUCED" if observed["predicate"] else "CONFIRMED"
    except checker.EdgeFailure as exc:
        if any(d.severity == "infrastructure" for d in exc.diagnostics):
            raise VeriSlopError(str(exc), exc.diagnostics) from None
        raise _ReplayUnsupported(str(exc)) from None
    except (target.BridgeInvalid, target.BridgeUnsupported) as exc:
        raise _ReplayUnsupported(str(exc)) from None


def replay_probe(pkg: Package, checkpoint: str, proposal: dict) -> dict:
    """Registered caller budgets: VSCore 0.3 uses 30 seconds; legacy targets use 5."""
    from .backends import registry
    backend, problems = registry.frozen_backend(pkg)
    if not problems and backend and backend["id"] == registry.VSCORE3_ID:
        return replay(pkg, checkpoint, proposal, timeout_seconds=30)
    return replay(pkg, checkpoint, proposal)


def _target(pkg: Package, checkpoint: str, proposal: dict, receipt: dict, inputs: _Inputs, deadline: float):
    if checkpoint not in ("implementation", "release"):
        raise _ReplayUnsupported("target execution is outside this checkpoint's scope")
    from .backends.registry import frozen_backend, PYTHON_ID, VSCORE3_ID
    backend, problems = frozen_backend(pkg)
    if not problems and backend and backend["id"] == VSCORE3_ID:
        return _vscore_target(pkg, proposal, receipt, inputs, deadline)
    if problems or not backend or backend["id"] != PYTHON_ID:
        raise _ReplayUnsupported("only the registered Python target has an admitted concrete replay here")
    ir, digest, _, problems = verified_ir(pkg)
    if problems or ir is None:
        raise _ReplayUnsupported("target replay requires current accepted IR and certificate bindings")
    inputs.json(pkg.path("accepted_ir"))
    inputs.json(pkg.root / ir["acceptance_certificate_ref"])
    rec = ir["obligations"].get(proposal["obligation_id"])
    if not rec or rec["role"] != "guarantee" or not rec["required"] or rec["kind"] in ("non_vacuity", "liveness_property", "resource_constraint"):
        raise _ReplayUnsupported("target probe must name a required functional implementation guarantee")
    formal = rec["formal"]
    if formal["representation"] not in ("contract_dsl", "contract_facets"):
        raise _ReplayUnsupported("opaque formulas have no admitted executable counterexample oracle")
    profile_data = contract.frozen_json(pkg, "profile.json")
    inputs.json(contract.challenge_dir(pkg) / "profile.json")
    profile = dsl.Profile.from_json(profile_data)
    formula_hash = formal["formula_ref"].rsplit("@", 1)[1]
    formula_path = pkg.path("accepted") / "expressions" / (formula_hash.split(":")[1] + ".json")
    package = inputs.json(formula_path)
    if inputs.hashes[pkg.rel(formula_path)] != formula_hash:
        raise _ReplayUnsupported("accepted formula package hash differs from actual bytes")
    if formal["representation"] == "contract_facets":
        from . import native_contract
        package = native_contract.value_package(package)
        if package is None:
            raise _ReplayUnsupported("native-only source facet has no value counterexample oracle")
    dsl.check_package(package, profile)
    prefix, body = dsl.prefix(package["formula"])
    _decidable(body, profile)
    if len(prefix) != len(proposal["assignment"]):
        raise _ReplayUnsupported("assignment arity differs from accepted universal prefix")
    try:
        values = [_decode(v, s, profile) for v, s in zip(proposal["assignment"], prefix)]
    except (ValueError, TypeError, KeyError) as exc:
        raise _ReplayUnsupported(f"invalid assignment: {exc}") from None
    inventory = pt.inventory(pkg.path("implementation"))
    for path in inventory.files:
        inputs.bytes(pkg.path("implementation") / path)
    bound = _validated_link(pkg, ir, digest, rec, profile_data, inventory, inputs)
    _admit_python(pkg, inventory, inputs, profile)
    if not dsl.calls(body) or dsl.calls(body) - set(bound):
        raise _ReplayUnsupported("accepted predicate lacks a complete concrete target-call binding")
    receipt["input_bindings"]["runtime:python"] = pt.python_identity()["executable_sha256"]
    receipt["claim"] = {"claim_id": "IMPLEMENTATION:" + rec["id"] + "@" + str(rec["revision"]),
        "obligation_id": rec["id"], "revision": rec["revision"], "accepted_statement_hash": formal["statement_hash"],
        "result_predicate": "accepted-functional-guarantee/0.1"}
    receipt["expected"] = {"accepted_ir_hash": digest, "assignment": proposal["assignment"], "guard": True, "predicate": True}
    harness = _BoundedHarness(pkg.path("implementation"), {f: h for f, h in inventory.files.items() if f.endswith(".py")},
                              bound, deadline=deadline, per_call_timeout=min(2.0, max(0.001, deadline - time.monotonic())))
    oracle = _ObservedOracle(harness, profile, set(bound), deadline)
    evaluator = _BoundedEvaluator(profile, oracle.symbols(), lambda *_: [], deadline=deadline)
    env = list(reversed(values))
    guard_complete = False
    try:
        while body["tag"] == "implies":
            guard = evaluator.formula(body["left"], env)
            if not guard.exact or guard.value is None:
                raise _ReplayUnsupported("guard is indeterminate; no admissible witness established")
            if guard.value is False:
                receipt["status"] = "NOT_REPRODUCED"
                receipt["observed"] = {"guard": False, "predicate": None, "calls": oracle.observations}
                return
            body = body["right"]
        guard_complete = True
        actual = evaluator.formula(body, env)
        if not actual.exact or actual.value is None:
            raise _ReplayUnsupported("residual predicate is indeterminate; sampled truth has no authority")
        if not oracle.observations:
            raise _ReplayUnsupported("predicate check did not observe a contributing target invocation")
        receipt["status"] = "NOT_REPRODUCED" if actual.value else "CONFIRMED"
        receipt["observed"] = {"guard": True, "predicate": actual.value, "calls": oracle.observations}
    except dsl.TargetFault as exc:
        receipt["status"] = "CONFIRMED" if guard_complete else "UNSUPPORTED"
        receipt["claim"]["result_predicate"] = "total-target-profile/0.1"
        receipt["expected"]["target_profile_valid"] = True
        receipt["observed"] = {"guard": True if guard_complete else None, "predicate": None,
                               "target_profile_valid": False, "target_fault": exc.kind,
                               "detail": exc.detail, "calls": oracle.observations}
        if not guard_complete:
            receipt["diagnostics"] = ["target profile fault observed while establishing guard; covered assumptions remain unresolved"]
    finally:
        if receipt["observed"] is None:
            receipt["observed"] = {"calls": oracle.observations, "completed": False}
        harness.close()


def replay(pkg: Package, checkpoint: str, proposal: Any, *, timeout_seconds: float = 5.0) -> dict:
    """Execute one supervisor-owned bounded probe and return its immutable-ready receipt."""
    issues = validate_proposal(proposal)
    receipt = {"schema_version": "0.2", "format": RECEIPT_FORMAT, "status": "UNSUPPORTED",
        "proposal": proposal, "proposal_hash": canonical.digest_json(proposal) if not issues else None,
        "checkpoint": checkpoint, "checker": {"id": VERIFIER, "sha256": verifier_hash(VERIFIER) if VERIFIER in VERIFIERS else None},
        "input_bindings": {}, "claim": None, "expected": None, "observed": None, "diagnostics": []}
    if issues or checkpoint not in CHECKPOINT_MILESTONES or VERIFIER not in VERIFIERS:
        receipt["diagnostics"] = issues or ["checkpoint or replay checker is not registered"]
        return receipt
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 30:
        receipt["diagnostics"] = ["replay timeout must be finite and within (0, 30] seconds"]
        return receipt
    inputs = _Inputs(pkg)
    receipt["input_bindings"] = inputs.hashes
    try:
        roots_before = bound_roots(pkg, checkpoint)
        receipt["input_bindings"]["binding:roots"] = canonical.digest_json(roots_before)
        # All probes share the packet's unambiguous inventory boundary, including
        # probes that do not themselves select a mechanical claim.
        _context_claims(pkg, checkpoint, inputs)
        if proposal["kind"] == "mechanical_failure":
            _mechanical(pkg, checkpoint, proposal, receipt, inputs)
        elif proposal["kind"] == "missing_requirement":
            _missing(pkg, checkpoint, proposal, receipt, inputs)
        elif proposal["kind"] == "source_violation":
            _source(pkg, checkpoint, proposal, receipt, inputs)
        else:
            _target(pkg, checkpoint, proposal, receipt, inputs, time.monotonic() + timeout_seconds)
        inputs.reader.recheck()
        if bound_roots(pkg, checkpoint) != roots_before:
            raise _ReplayUnsupported("current scope roots changed during counterexample replay")
    except (_ReplayUnsupported, dsl.BudgetExceeded, dsl.DSLError, KeyError, ValueError, TypeError, SyntaxError, InvalidPackage) as exc:
        receipt["status"] = "UNSUPPORTED"
        receipt["diagnostics"] = [str(exc)]
    except (pt.HarnessError, OSError, VeriSlopError) as exc:
        receipt["status"] = "INFRASTRUCTURE_FAILURE"
        receipt["diagnostics"] = [f"{type(exc).__name__}: {exc}"]
    finally:
        inputs.reader.close()
    return receipt
