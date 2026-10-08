"""Supervisor replay of closed review probes; agents supply values, never commands.

Only exact decidable Python residuals are admitted for target counterexamples. A
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
from .errors import VeriSlopError
from .export import verified_ir
from .package import Package
from .targets import python_target as pt
from .verifiers import VERIFIERS, verifier_hash
from .bridges.manifest import InvalidPackage, PackageReader

VERIFIER = "verislop.review-counterexample"
RECEIPT_FORMAT = "verislop.review-counterexample-receipt/0.2"
SUPPORTED_PROPOSAL_KINDS = ("target_case", "missing_requirement", "mechanical_failure")
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
    if depth > 32 or not isinstance(value, dict) or len(value) != 1:
        return False
    if "int" in value:
        v = value["int"]
        return isinstance(v, str) and len(v) <= 1024 and re.fullmatch(r"0|[1-9][0-9]*", v) is not None
    if "bool" in value:
        return type(value["bool"]) is bool
    if "none" in value:
        return value["none"] is None
    if "str" in value:
        return isinstance(value["str"], str) and len(value["str"]) <= 1024
    if "tuple" in value:
        v = value["tuple"]
        return isinstance(v, list) and len(v) == 2 and all(_wire_valid(x, depth + 1) for x in v)
    return False


def validate_proposal(obj: Any) -> list[str]:
    """Closed syntax only. Applicability, sort and claim checks belong to replay."""
    if not isinstance(obj, dict) or obj.get("kind") not in SUPPORTED_PROPOSAL_KINDS:
        return ["proposal must name one supported kind"]
    kind = obj["kind"]
    fields = {"target_case": {"kind", "obligation_id", "assignment"},
              "missing_requirement": {"kind", "start_byte", "end_byte", "quoted"},
              "mechanical_failure": {"kind", "claim_id"}}[kind]
    if set(obj) != fields:
        return [f"{kind} accepts exactly {', '.join(sorted(fields))}"]
    try:
        if len(canonical.dumps(obj)) > MAX_PROPOSAL_BYTES:
            return ["proposal exceeds byte budget"]
    except (ValueError, UnicodeError):
        return ["proposal is not bounded canonical JSON"]
    if kind == "target_case":
        if not isinstance(obj["obligation_id"], str) or not obj["obligation_id"] or len(obj["obligation_id"]) > 256:
            return ["obligation_id must be a bounded nonempty string"]
        if not isinstance(obj["assignment"], list) or len(obj["assignment"]) > 32 or not all(_wire_valid(v) for v in obj["assignment"]):
            return ["assignment must contain bounded strict tagged values"]
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


def _claim(c: dict) -> dict:
    return {"claim_id": c["claim_id"], "obligation_id": c.get("obligation"),
            "revision": c.get("revision"), "accepted_statement_hash": c.get("accepted_statement_hash"),
            "result_predicate": c.get("result_predicate", "milestone-pass/0.1")}


def _definitions(pkg: Package, checkpoint: str, inputs: _Inputs) -> dict[str, dict]:
    definitions = {}
    paths = []
    if checkpoint != "interpretation":
        paths.append(pkg.path("claims"))
    if checkpoint in ("implementation", "release"):
        paths.append(pkg.path("closure") / "implementation-claims.json")
    for path in paths:
        if path.is_file():
            for c in inputs.json(path).get("claims", []):
                if (c.get("required") and c.get("applicable") and
                        (c.get("milestone") in CHECKPOINT_MILESTONES[checkpoint] or
                         (checkpoint == "release" and c.get("milestone") is None))):
                    definitions[c["claim_id"]] = c
    if pkg.path("prompt").is_file():
        definitions["INTERPRETATION:request"] = {"claim_id": "INTERPRETATION:request", "obligation": None,
            "milestone": "INTERPRETED", "required": True, "applicable": True,
            "verifier": "verislop.interpretation-recorder", "root_kind": "interpretation_root",
            "result_predicate": "interpretation-coverage/0.1"}
    return definitions


def mechanical_claim_ids(pkg: Package, checkpoint: str) -> list[str]:
    """Supervisor discovery for packets; returns only claims admitted at this checkpoint."""
    inputs = _Inputs(pkg)
    try:
        return sorted(_definitions(pkg, checkpoint, inputs))
    finally:
        inputs.reader.close()


def _mechanical(pkg: Package, checkpoint: str, proposal: dict, receipt: dict, inputs: _Inputs):
    c = _definitions(pkg, checkpoint, inputs).get(proposal["claim_id"])
    if c is None:
        raise _ReplayUnsupported("claim is not a required applicable claim at this checkpoint")
    roots = pkg.roots()
    from .closure import closure_input_root
    roots["closure_root"] = closure_input_root(pkg)
    default = c.get("root_kind", ROOTS.get(c.get("milestone"), "closure_root"))
    assessment = evaluate_claim(c, pkg.evidence.for_claim(c["claim_id"]), roots, default)
    receipt["claim"] = _claim(c)
    receipt["expected"] = {"outcome": "PASS", "root_kind": default, "root": roots.get(default)}
    receipt["observed"] = {"outcome": assessment.outcome, "reason": assessment.reason,
                           "evidence_id": assessment.evidence.id if assessment.evidence else None}
    if assessment.evidence:
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
    def budget(v, depth=0):
        if depth > 32 or (isinstance(v, str) and len(v) > 1024):
            raise dsl.BudgetExceeded("value exceeds replay decoding budget; not a target-profile counterexample")
        if isinstance(v, dict):
            for item in v.values():
                budget(item, depth + 1)
        elif isinstance(v, list):
            for item in v:
                budget(item, depth + 1)
    budget(value)
    if not _wire_valid(value):
        raise _ReplayUnsupported("wire value is not closed and canonical")
    decoded = pt.decode_result(value, sort, profile)
    if not dsl.value_has_sort(decoded, sort, profile):
        raise _ReplayUnsupported("assignment is outside the accepted binder sort")
    # Strict re-encoding closes permissive legacy decoder branches.
    if pt.encode_arg(decoded, sort) != value:
        raise _ReplayUnsupported("wire value differs from its accepted sort encoding")
    return decoded


def _decidable(formula: Any):
    if isinstance(formula, dict):
        if formula.get("tag") in dsl.QUANTIFIERS and not dsl.is_finite(formula["sort"]):
            raise _ReplayUnsupported("unbounded residual quantifiers cannot confirm counterexamples")
        for value in formula.values():
            _decidable(value)
    elif isinstance(formula, list):
        for value in formula:
            _decidable(value)


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
        if term["tag"] == "nat" and len(term["value"]) > 1024:
            raise dsl.BudgetExceeded("counterexample oracle numeral budget exhausted")
        if term["tag"] in dsl.NAT_OPS:
            self._tick()
            a, b = self.term(term["left"], env), self.term(term["right"], env)
            if term["tag"] == "mul" and a.bit_length() + b.bit_length() > 4096:
                raise dsl.BudgetExceeded("counterexample oracle arithmetic budget exhausted")
            result = a + b if term["tag"] == "add" else (max(0, a - b) if term["tag"] == "sub" else a * b)
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
        enc = [pt.encode_arg(a, s) for a, s in zip(args, spec["args"])]
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
            "obligations": covered, "serialization_profile": pt.PROFILE_ID})
    helpers = {(h["file"], h["qualname"]) for h in proposal["helpers"]}
    if any(o["public"] and (o["file"], o["qualname"]) not in objects | helpers for o in inventory.objects):
        raise _ReplayUnsupported("current executable inventory has an unaccounted public object")
    current = inputs.json(pkg.path("bridges") / "link.json")
    reconstructed = {"schema_version": "0.1", "artifact_kind": "link_record", "accepted_ir": digest,
        "implementation_root": pkg.implementation_root(), "serialization_profile": pt.PROFILE_DOC,
        "bindings": sorted(expected, key=lambda b: b["binding_id"]),
        "correspondence": "structural identity and coverage only; semantic correspondence is not established at this tier"}
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


def _admit_python(pkg, inventory, inputs):
    """Admit a pure syntax subset that cannot write or replace the harness channel.

    This is deliberately narrower than legacy campaigns. Unsupported imports,
    reflection, attributes and I/O must never furnish apparently faithful receipts.
    """
    allowed = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.If,
        ast.Assign, ast.Expr, ast.Raise, ast.Pass, ast.Name, ast.Load, ast.Store,
        ast.Constant, ast.Tuple, ast.List, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
        ast.IfExp, ast.Call, ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.Pow,
        ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt, ast.LtE,
        ast.Gt, ast.GtE, ast.Is, ast.IsNot)
    exceptions = {"ValueError", "TypeError", "RuntimeError", "ArithmeticError", "AssertionError"}
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
        for node in nodes:
            if not isinstance(node, allowed):
                raise _ReplayUnsupported(f"Python replay does not admit {type(node).__name__}")
            if isinstance(node, ast.Name) and node.id.startswith("__"):
                raise _ReplayUnsupported("Python replay does not admit runtime reflection names")
            if isinstance(node, ast.FunctionDef) and (node.decorator_list or node.returns or getattr(node, "type_params", []) or
                    node.args.defaults or any(value is not None for value in node.args.kw_defaults) or
                    any(arg.annotation for arg in ast.walk(node.args) if isinstance(arg, ast.arg))):
                raise _ReplayUnsupported("Python replay does not admit evaluated function metadata")
            if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.keywords or
                    (node.func.id not in functions and id(node) not in exception_calls)):
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
                        node.id not in functions | locals_ and id(node) not in exception_names):
                    raise _ReplayUnsupported(f"Python replay does not admit free name reference {node.id}")


def _target(pkg: Package, checkpoint: str, proposal: dict, receipt: dict, inputs: _Inputs, deadline: float):
    if checkpoint not in ("implementation", "release"):
        raise _ReplayUnsupported("target execution is outside this checkpoint's scope")
    from .backends.registry import frozen_backend, PYTHON_ID
    backend, problems = frozen_backend(pkg)
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
    if formal["representation"] != "contract_dsl":
        raise _ReplayUnsupported("opaque formulas have no admitted executable counterexample oracle")
    profile_data = contract.frozen_json(pkg, "profile.json")
    inputs.json(contract.challenge_dir(pkg) / "profile.json")
    profile = dsl.Profile.from_json(profile_data)
    formula_hash = formal["formula_ref"].rsplit("@", 1)[1]
    formula_path = pkg.path("accepted") / "expressions" / (formula_hash.split(":")[1] + ".json")
    package = inputs.json(formula_path)
    if inputs.hashes[pkg.rel(formula_path)] != formula_hash:
        raise _ReplayUnsupported("accepted formula package hash differs from actual bytes")
    dsl.check_package(package, profile)
    prefix, body = dsl.prefix(package["formula"])
    _decidable(body)
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
    _admit_python(pkg, inventory, inputs)
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
        if proposal["kind"] == "mechanical_failure":
            _mechanical(pkg, checkpoint, proposal, receipt, inputs)
        elif proposal["kind"] == "missing_requirement":
            _missing(pkg, checkpoint, proposal, receipt, inputs)
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
