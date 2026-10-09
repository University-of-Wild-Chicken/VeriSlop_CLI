"""Bounded kernel replay of concrete assignments to exact VSCore 0.3 goals.

Source functions and adapters come from the ordinary supervisor goal. A review
probe supplies only typed values; neither a host evaluator nor a candidate proof
can determine the result. Cached library parts are supervisor compiled and are
replayed in the kernel again for every probe.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from .. import canonical, dsl, fsutil, leanbridge, policy
from ..errors import InfrastructureError
from ..exprjson import app, const, constants, instantiate1, loose_bvar_range, name_str
from . import vscore3_target as target

MODULE = "VeriSlopReviewProbe"
THEOREM = MODULE + ".result"
_LIBRARIES: dict[str, dict[str, dict[str, bytes]]] = {}
_LIBRARY_LOCK = threading.Lock()


class Unsupported(ValueError):
    pass


def remaining(deadline: float) -> float:
    budget = deadline - time.monotonic()
    if budget <= 0:
        raise dsl.BudgetExceeded("VSCore 0.3 kernel replay deadline exhausted")
    return budget


def literal(value, sort, profile: dsl.Profile):
    """Construct accepted-carrier expressions after strict sort-directed decoding."""
    from ..reify import _Denoter
    denoter = _Denoter(profile)
    if sort in ("Nat", "Int", "Bool", "String", "Unit"):
        tag = {"Nat": "nat", "Int": "int", "Bool": "bool", "String": "string", "Unit": "unit"}[sort]
        term = {"tag": tag}
        if sort != "Unit":
            term["value"] = str(value) if sort in ("Nat", "Int") else value
        return denoter.term(term, [])[0]
    if "enum" in sort:
        row = profile.enums[sort["enum"]]
        return const(row["lean_constructors"][row["constructors"].index(value[2])])
    if "record" in sort:
        row = profile.records[sort["record"]]
        return app(const(row["lean_constructor"]), *(literal(v, f["sort"], profile)
                    for v, f in zip(value[2], row["fields"])))
    if "list" in sort:
        ty = denoter.sort(sort["list"])
        result = app(const("List.nil", [0]), ty)
        for item in reversed(value):
            result = app(const("List.cons", [0]), ty, literal(item, sort["list"], profile), result)
        return result
    if "option" in sort:
        ty = denoter.sort(sort["option"])
        if value == dsl.OPTION_NONE:
            return app(const("Option.none", [0]), ty)
        return app(const("Option.some", [0]), ty, literal(value[1], sort["option"], profile))
    side, payload = value
    return app(const("Except." + side, [0, 0]), denoter.sort(sort["result"]["error"]),
               denoter.sort(sort["result"]["ok"]), literal(payload, sort["result"][side], profile))


def ground(spec: target.GoalSpec, formula: dict, values: list):
    """Instantiate outermost universals without moving calls across local binders."""
    sorts, _ = dsl.prefix(formula)
    if len(values) != len(sorts):
        raise Unsupported("assignment arity differs from accepted universal prefix")
    expr = target.transfer_expr(formula, spec.profile, {s.symbol: s for s in spec.symbols})
    for value, sort in zip(values, sorts):
        if "pi" not in expr:
            raise Unsupported("transferred universal prefix differs from accepted binder inventory")
        expr = instantiate1(expr["pi"]["body"], literal(value, sort, spec.profile))
    if loose_bvar_range(expr):
        raise Unsupported("assignment did not close the accepted residual")
    if not any(n.startswith(target.GOAL_MODULE + ".source_fn_") for n in constants(expr)):
        raise Unsupported("ground predicate mentions no contributing source function")
    return expr


def _options(pol: dict, deadline: float) -> dict:
    return {"timeout": remaining(deadline), "memory_mb": pol["memory_mb"],
            "require_network_isolation": pol["require_network_isolation"],
            "require_filesystem_isolation": pol["require_filesystem_isolation"]}


def _library_parts(tc, pol, deadline, sources):
    key = canonical.digest_json({"toolchain": tc.identity(), "sources": {
        name: canonical.digest(source) for name, source in sources.items()}})
    if not _LIBRARY_LOCK.acquire(timeout=remaining(deadline)):
        raise dsl.BudgetExceeded("VSCore 0.3 library preparation deadline exhausted")
    try:
        remaining(deadline)
        if key in _LIBRARIES:
            return _LIBRARIES[key]
        modules = {}
        with fsutil.temporary_directory(prefix="verislop-review-vscore-library-") as tmp:
            root, deps = Path(tmp), {}
            for name, source in sources.items():
                result, parts = leanbridge.compile_named_module(tc, root, name, source, deps,
                    read_only=[], **_options(pol, deadline))
                if result.timed_out:
                    raise dsl.BudgetExceeded("VSCore 0.3 normative library build exceeded the replay deadline")
                if not result.ok or result.sorry_positions:
                    raise InfrastructureError(f"registered VSCore library {name} failed: {result.errors[:3]}")
                modules[name] = parts
                deps[name] = {s: str(root / (leanbridge.module_relpath(name) + s)) for s in parts}
        _LIBRARIES[key] = modules
        return modules
    finally:
        _LIBRARY_LOCK.release()


def check(tc, ctx, spec: target.GoalSpec, expression: dict, *, deadline: float,
          goal_parts: dict[str, bytes] | None = None) -> dict:
    """Return only a kernel-proved closed truth value, otherwise leave it unresolved."""
    pol, sources = ctx.policy, target.library_sources()
    modules = dict(_library_parts(tc, pol, deadline, sources))
    with fsutil.temporary_directory(prefix="verislop-review-vscore-") as tmp:
        root = Path(tmp)
        dependencies, imported = {}, root / "imports"
        imported.mkdir()
        for name, parts in modules.items():
            dependencies[name] = leanbridge.write_module_parts(imported, name, parts)
        accepted = root / "contract"
        accepted.mkdir()
        bundle = accepted / "module.vslean"
        bundle.write_bytes(ctx.contract_module)
        leanbridge._stage_module(bundle, accepted)
        bundle.unlink()
        modules[target.CONTRACT_MODULE] = leanbridge.module_parts(accepted, target.CONTRACT_MODULE)
        dependencies[target.CONTRACT_MODULE] = leanbridge.write_module_parts(imported, target.CONTRACT_MODULE,
                                                                           modules[target.CONTRACT_MODULE])
        if goal_parts is None:
            result, goal_parts = leanbridge.compile_named_module(tc, root / "goal", target.GOAL_MODULE,
                spec.text.encode(), dependencies, read_only=[imported], **_options(pol, deadline))
            if result.timed_out:
                raise dsl.BudgetExceeded("VSCore 0.3 goal build exceeded the replay deadline")
            if not result.ok or result.sorry_positions:
                raise Unsupported(f"exact source goal failed admission: {result.errors[:3]}")
        modules[target.GOAL_MODULE] = goal_parts
        dependencies[target.GOAL_MODULE] = leanbridge.write_module_parts(imported, target.GOAL_MODULE, goal_parts)
        result_expr = None
        # Successful proof construction determines polarity; a failed attempt never
        # constitutes a counterexample. Both outcomes are replayed independently.
        for truth in (False, True):
            expected = expression if truth else app(const("Not"), expression)
            source = (f"import {target.GOAL_MODULE}\nset_option maxRecDepth 100000\n"
                      "set_option maxHeartbeats 2000000\nnamespace " + MODULE + "\n"
                      "theorem result : " + target.Printer().term(expected) + " := by decide +kernel\n"
                      "end " + MODULE + "\n").encode()
            result, parts = leanbridge.compile_named_module(tc, root / ("positive" if truth else "negative"),
                MODULE, source, dependencies, read_only=[imported], **_options(pol, deadline))
            if result.timed_out:
                raise dsl.BudgetExceeded("VSCore 0.3 ground proof exceeded the replay deadline")
            if result.ok and not result.sorry_positions:
                result_expr = expected
                modules[MODULE] = parts
                break
        if result_expr is None:
            raise Unsupported("closed residual has no kernel-decidable result within the admitted replay surface")
        request = {"export": True, "export_modules": [target.GOAL_MODULE, MODULE], "axioms": True, "defeq": [
            {"id": "ground-result", "theorem": [MODULE, "result"], "expr": result_expr}]}
        try:
            response = leanbridge.run_kernel_tool_modules(tc, modules, MODULE, request, **_options(pol, deadline))
        except InfrastructureError as exc:
            if "timed out" in str(exc):
                raise dsl.BudgetExceeded("VSCore 0.3 kernel exceeded the replay deadline") from None
            raise
        remaining(deadline)
        imported_response, replay = response.get("import", {}), response.get("replay", {})
        if not imported_response.get("ok") or not replay.get("ok"):
            raise Unsupported("pinned kernel rejected the complete module replay")
        staged = {name_str(row["name"]) for row in imported_response.get("modules", []) if row.get("staged")}
        if staged != set(modules):
            raise Unsupported("kernel imported a different staged dependency inventory")
        toolchain_modules = [row for row in imported_response["modules"] if not row.get("staged")]
        if any(not row["name"] or str(row["name"][0]) not in pol["allowed_import_roots"]
               for row in toolchain_modules):
            raise Unsupported("kernel imported a dependency outside the accepted toolchain policy")
        closure_id, diagnostics = leanbridge.olean_closure_identity(tc, toolchain_modules)
        if diagnostics:
            raise InfrastructureError("kernel toolchain import bytes could not be bound", diagnostics)
        if any(not name or name[-1] != "_unsafe_rec" for name in replay.get("not_replayed_unsafe_or_partial", [])):
            raise Unsupported("complete kernel replay omitted a non-runtime unsafe or partial declaration")
        decls = {}
        for row in response.get("constants", []):
            if row.get("kind") == "missing_after_replay" or "export_error" in row:
                raise Unsupported("a ground or goal declaration could not be exported after kernel replay")
            decls[name_str(row["name"])] = row
        goal_decls = {name: row for name, row in decls.items() if row.get("module") == [target.GOAL_MODULE]}
        if target.statement_mismatches(spec, goal_decls):
            raise Unsupported("replayed source goal differs from the supervisor-derived statements")
        for obligation in spec.obligations:
            transfer = goal_decls.get(target.GOAL_MODULE + ".transfer_" + obligation.oid)
            if (not transfer or transfer.get("kind") != "theorem" or
                    obligation.lean_symbol not in {name_str(n) for n in transfer.get("value_constants", [])}):
                raise Unsupported("value/source transfer does not depend on the original accepted theorem")
        reconstructed = target.reexport(spec, goal_decls)
        if canonical.dumps(reconstructed["program"]) != spec.source_bytes:
            raise Unsupported("replayed source AST differs from delivered bytes")
        rows = response.get("defeq", [])
        if (len(rows) != 1 or rows[0].get("id") != "ground-result" or
                rows[0].get("result") != {"ok": True, "typechecks": True, "defeq": True}):
            raise Unsupported("kernel result theorem differs from the exact grounded accepted expression")
        theorem = decls.get(THEOREM)
        if (not theorem or theorem.get("kind") != "theorem" or theorem.get("level_params") or
                theorem.get("module") != [MODULE] or theorem.get("safety") != "safe" or
                theorem.get("unresolved_constants") or
                not target.same_expr(theorem["type"], result_expr)):
            raise Unsupported("ground result is not an exact safe replayed theorem")
        axioms = sorted(name_str(n) for n in theorem.get("axioms", []))
        if any(policy.classify_axiom(name, pol) != "allowed" for name in axioms):
            raise Unsupported("ground result depends on an inadmissible axiom")
        if target.library_sources() != sources:
            raise Unsupported("registered normative library sources changed during replay")
        remaining(deadline)
        return {"predicate": truth, "ground_expression_hash": canonical.digest_json(expression),
                "result_theorem": THEOREM, "result_type_hash": canonical.digest_json(result_expr), "axioms": axioms,
                "toolchain": tc.identity(), "kernel_tool_hash": leanbridge.kernel_tool_hash(),
                "toolchain_olean_closure": closure_id,
                "modules": {name: canonical.digest_json({suffix: canonical.digest(data) for suffix, data in parts.items()})
                            for name, parts in sorted(modules.items())}, "kernel_replay": True}
