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
from ..exprjson import app, const, constants, instantiate1, loose_bvar_range, name_str, parse_name
from . import vscore3_target as target

MODULE = "VeriSlopReviewProbe"
THEOREM = MODULE + ".result"
STRATEGY = "kernel-ground-normalization/1"
PROOF = ("by\n  with_unfolding_all\n"
         "    simp only [eq_self, true_implies, implies_true, and_true, true_and, "
         "not_true_eq_false, not_false_eq_true]\n    all_goals decide +kernel")
DIAGNOSTIC_ROWS = 8
DIAGNOSTIC_ROW_BYTES = 512
DIAGNOSTIC_WIRE_BYTES = 16384
_LIBRARIES: dict[str, dict[str, dict[str, bytes]]] = {}
_LIBRARY_LOCK = threading.Lock()


class Unsupported(ValueError):
    def __init__(self, message: str, attempts: list[dict] | None = None):
        self.attempts = attempts or []
        # The supervisor retains exception text in its ordinary diagnostics field.
        # Keep failed compiler evidence there as well as in successful observations.
        if self.attempts:
            encoded = canonical.dumps(self.attempts)
            if len(encoded) > DIAGNOSTIC_WIRE_BYTES:
                raise ValueError("ground proof attempt diagnostics exceed their wire bound")
            message += "; proof_attempts=" + encoded.decode()
        super().__init__(message)


def _attempt(result, source: bytes, truth: bool, index: int) -> dict:
    """Bound explanatory rows independently of the fixed metadata wire reserve."""
    errors, retained, flags = result.errors, [], []
    for error in errors[:DIAGNOSTIC_ROWS]:
        original = error.encode("utf-8")
        clipped = original[:DIAGNOSTIC_ROW_BYTES].decode("utf-8", "ignore")
        retained.append(clipped)
        flags.append(len(clipped.encode("utf-8")) != len(original))
    process = result.process_evidence or {}
    output = {key: {field: process.get(key, {}).get(field) for field in ("byte_count", "sha256")}
              for key in ("stdout", "stderr")}
    attempt = {"strategy_id": STRATEGY, "polarity": truth, "attempt_index": index,
            "probe_source_hash": canonical.digest(source), "compiler_ok": result.ok,
            "compiler_exit_code": process.get("returncode"), "timed_out": result.timed_out,
            "sorry_positions": [{key: row.get(key) for key in ("line", "column")}
                                for row in result.sorry_positions[:DIAGNOSTIC_ROWS]],
            "sorry_positions_truncated": len(result.sorry_positions) > DIAGNOSTIC_ROWS,
            "errors": retained, "row_truncated": flags, "retained_rows": len(retained),
            "available_rows": len(errors),
            "retained_utf8_bytes": sum(len(row.encode("utf-8")) for row in retained),
            "available_utf8_bytes": sum(len(row.encode("utf-8")) for row in errors),
            "truncated": len(errors) > DIAGNOSTIC_ROWS or any(flags),
            "underlying_process_output_truncated": process.get("output_truncated"),
            "process_output": output}
    # JSON escaping can expand NUL/control characters sixfold. Bound the encoded
    # record, reserving the three list/separator bytes for two polarity records.
    per_attempt_wire = (DIAGNOSTIC_WIRE_BYTES - 3) // 2
    while len(canonical.dumps(attempt)) > per_attempt_wire and attempt["errors"]:
        attempt["errors"].pop()
        attempt["row_truncated"].pop()
        attempt["retained_rows"] = len(attempt["errors"])
        attempt["retained_utf8_bytes"] = sum(len(row.encode("utf-8")) for row in attempt["errors"])
        attempt["truncated"] = True
    if len(canonical.dumps(attempt)) > per_attempt_wire:
        raise Unsupported("ground proof diagnostic metadata exceeds its fixed wire reserve")
    return attempt


def _proof_dependencies(spec, decls: dict[str, dict], theorem: str, modules: set[str]) -> dict:
    """Audit actual staged proof/definition dependencies, including wrappers.

    All staged declarations are exported after complete kernel replay. A reference
    outside that complete inventory is a pinned toolchain leaf; toolchain modules
    cannot refer forward to a contract, goal or probe compiled afterwards.
    """
    forbidden = {tuple(parse_name(ob.lean_symbol)) for ob in spec.obligations}
    goal_name, proof_name = tuple(parse_name(target.GOAL_MODULE)), tuple(parse_name(target.PROOF_MODULE))
    leaf_prefixes = ("Refines_", "Transfer_", "transfer_", "edge_of_refines")
    staged_roots = {module.split(".", 1)[0] for module in modules}
    pending, visited, leaves = [theorem], set(), set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        components = tuple(parse_name(name))
        generated_oracle = (components[:len(goal_name)] == goal_name and len(components) > len(goal_name)
                            and isinstance(components[len(goal_name)], str)
                            and components[len(goal_name)].startswith(leaf_prefixes))
        if components in forbidden or generated_oracle or components[:len(proof_name)] == proof_name:
            raise Unsupported("ground observation depends on a refinement, transfer or accepted guarantee oracle")
        row = decls.get(name)
        if row is None:
            if name.split(".", 1)[0] in staged_roots:
                raise Unsupported("ground proof dependency lacks its staged declaration export")
            leaves.add(name)
            continue
        if row.get("kind") == "theorem" and "value_constants" not in row:
            raise Unsupported("ground proof dependency lacks exported proof references")
        references = constants(row.get("type", {})) | constants(row.get("value", {}))
        references.update(name_str(n) for n in row.get("value_constants", []))
        pending.extend(sorted(references - visited))
    return {"root": theorem, "staged_declarations": sorted(visited - leaves),
            "toolchain_leaves": sorted(leaves), "forbidden_dependencies": [],
            "inventory_hash": canonical.digest_json(sorted(visited))}


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
    attempts = []
    try:
        return _check(tc, ctx, spec, expression, deadline=deadline, goal_parts=goal_parts, attempts=attempts)
    except dsl.BudgetExceeded as exc:
        # Exhaustion may happen before a later compiler call or after construction
        # during kernel replay. Keep its original classification and prior evidence.
        raise dsl.BudgetExceeded(str(Unsupported(str(exc), attempts))) from None
    except Unsupported as exc:
        if attempts and not exc.attempts:
            raise Unsupported(str(exc), attempts) from None
        raise


def _check(tc, ctx, spec: target.GoalSpec, expression: dict, *, deadline: float,
           goal_parts: dict[str, bytes] | None, attempts: list[dict]) -> dict:
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
        for index, truth in enumerate((False, True), 1):
            expected = expression if truth else app(const("Not"), expression)
            source = (f"import {target.GOAL_MODULE}\nset_option maxRecDepth 100000\n"
                      "set_option maxHeartbeats 2000000\nset_option smartUnfolding false\nnamespace " + MODULE + "\n"
                      "theorem result : " + target.Printer().term(expected) + " := " + PROOF + "\n"
                      "end " + MODULE + "\n").encode()
            result, parts = leanbridge.compile_named_module(tc, root / ("positive" if truth else "negative"),
                MODULE, source, dependencies, read_only=[imported], **_options(pol, deadline))
            attempts.append(_attempt(result, source, truth, index))
            if result.timed_out:
                raise dsl.BudgetExceeded("VSCore 0.3 ground proof exceeded the replay deadline")
            if result.ok and not result.sorry_positions:
                result_expr = expected
                modules[MODULE] = parts
                break
        if result_expr is None:
            raise Unsupported("closed residual has no kernel-decidable result within the admitted replay surface", attempts)
        request = {"export": True, "export_modules": list(modules), "axioms": True, "defeq": [
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
            if (row.get("kind") == "missing_after_replay" and row.get("replay_exclusion") == "runtime_auxiliary"
                    and row.get("name", [""])[-1] == "_unsafe_rec"):
                continue
            if row.get("kind") == "missing_after_replay" or "export_error" in row:
                raise Unsupported("a ground or goal declaration could not be exported after kernel replay")
            decls[name_str(row["name"])] = row
        goal_decls = {name: row for name, row in decls.items() if row.get("module") == [target.GOAL_MODULE]}
        if target.statement_mismatches(spec, goal_decls):
            raise Unsupported("replayed source goal differs from the supervisor-derived statements")
        for obligation in spec.obligations:
            transfer = goal_decls.get(name_str(target.gname("transfer_" + obligation.oid)))
            if (not transfer or transfer.get("kind") != "theorem" or
                    not target.references_theorem(transfer, obligation.lean_symbol)):
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
        proof_dependencies = _proof_dependencies(spec, decls, THEOREM, set(modules))
        if target.library_sources() != sources:
            raise Unsupported("registered normative library sources changed during replay")
        remaining(deadline)
        return {"predicate": truth, "ground_expression_hash": canonical.digest_json(expression),
                "result_theorem": THEOREM, "result_type_hash": canonical.digest_json(result_expr), "axioms": axioms,
                "toolchain": tc.identity(), "kernel_tool_hash": leanbridge.kernel_tool_hash(),
                "toolchain_olean_closure": closure_id,
                "modules": {name: canonical.digest_json({suffix: canonical.digest(data) for suffix, data in parts.items()})
                            for name, parts in sorted(modules.items())}, "kernel_replay": True,
                "strategy_id": STRATEGY, "proof_attempts": attempts, "proof_dependencies": proof_dependencies}
