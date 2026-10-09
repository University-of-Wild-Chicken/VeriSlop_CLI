"""Bounded, proof-producing critique of a candidate contract before it is frozen.

Search and critic expectations are untrusted.  Only a replayed Lean theorem proving the
closed negation of the exact reconstructed guarantee produces ``REFUTED``.  Exhausting
a finite search never proves a universal guarantee.  Reference-output probes prove the
candidate's actual output, but an AI's expected output is only semantic repair feedback.
"""
from __future__ import annotations

from itertools import islice, product
from pathlib import Path
from typing import Any

from . import contract_values, canonical, contract, dsl, fsutil, leanbridge, native_contract, policy, reify
from .exprjson import app, const, decl_hash, instantiate1, parse_name
from .errors import InfrastructureError
from .package import Package
from .targets import python_target as wire

VERSION = "verislop.contract-refutation/0.1"
MAX_CASES = 256
MAX_SORT_VALUES = 32
MAX_PROPOSALS = 32
MAX_PROOF_ATTEMPTS = 16
MAX_DEPTH = 16
MAX_VALUE_NODES = 4096
STRING_DEFAULTS = ("", "x", "p", "e\u0301")


def _analysis_identity(analysis: contract.Analysis) -> dict[str, Any]:
    return {"profile": analysis.profile, "statements": analysis.statements,
            "registry": analysis.registry, "defeq_requests": analysis.defeq_requests}


def _qualified(name: str | list) -> str:
    parts = parse_name(name) if isinstance(name, str) else name
    if not parts or any(not isinstance(x, str) or "«" in x or "»" in x for x in parts):
        raise ValueError("unsupported Lean name component")
    return "_root_." + ".".join("«" + x + "»" for x in parts)


def _expr_lean(expr: dict, names: tuple[str, ...] = ()) -> str:
    """Print the denoter's expression with explicit constants, levels and arguments.

    The printer is not an authority: every resulting theorem type is compared with the
    original expression by the separate kernel tool.
    """
    if "const" in expr:
        levels = expr.get("levels", [])
        if any(type(x) is not int or x < 0 for x in levels):
            raise ValueError("unsupported expression universe")
        suffix = ".{" + ",".join(str(x) for x in levels) + "}" if levels else ""
        return "@" + _qualified(expr["const"]) + suffix
    if "bvar" in expr:
        return names[expr["bvar"]]
    if "app" in expr:
        return "(" + " ".join(_expr_lean(x, names) for x in expr["app"]) + ")"
    if "lit" in expr:
        lit = expr["lit"]
        if set(lit) == {"nat"} and dsl.NAT_RE.fullmatch(lit["nat"]):
            return "(" + lit["nat"] + " : _root_.Nat)"
        if set(lit) == {"str"}:
            return contract.lean_string(lit["str"])
    if "sort" in expr and type(expr["sort"]) is int and expr["sort"] >= 0:
        return "Prop" if expr["sort"] == 0 else "Type " + str(expr["sort"] - 1)
    for key in ("lam", "pi"):
        if key in expr:
            row = expr[key]
            if row["bi"] != "default":
                raise ValueError("unsupported binder information")
            name = "_vr" + str(len(names))
            ty = _expr_lean(row["type"], names)
            body = _expr_lean(row["body"], (name,) + names)
            return f"(fun ({name} : {ty}) => {body})" if key == "lam" else f"(∀ ({name} : {ty}), {body})"
    raise ValueError("expression outside refutation printer")


def _literal(value: Any, sort: Any, profile: dsl.Profile) -> dict:
    if sort in ("Nat", "Int"):
        return {"tag": "nat" if sort == "Nat" else "int", "value": str(value)}
    if sort == "String":
        return {"tag": "string", "value": value}
    if sort == "Bool":
        return {"tag": "bool", "value": value}
    if sort == "Unit":
        return {"tag": "unit"}
    if "option" in sort:
        return ({"tag": "none", "element_sort": sort["option"]} if value == dsl.option_none_v() else
                {"tag": "some", "value": _literal(value[1], sort["option"], profile)})
    if "enum" in sort:
        return {"tag": "enum", "sort": sort["enum"], "constructor": value[2]}
    if "list" in sort:
        return {"tag": "list", "element_sort": sort["list"],
                "items": [_literal(x, sort["list"], profile) for x in value]}
    if "record" in sort:
        fields = profile.records[sort["record"]]["fields"]
        return {"tag": "record", "sort": sort["record"],
                "fields": [_literal(v, f["sort"], profile) for v, f in zip(value[2], fields)]}
    side, inner = value
    return {"tag": side, ("error_sort" if side == "ok" else "ok_sort"): sort["result"]["error" if side == "ok" else "ok"],
            "value": _literal(inner, sort["result"][side], profile)}


def _defaults(sort: Any, profile: dsl.Profile, depth: int = 0) -> list[Any]:
    """Public sort-directed Cartesian seeds; field names and task names play no role."""
    if depth > MAX_DEPTH:
        raise ValueError("default generation depth exhausted")
    if sort == "Nat":
        return [0, 1, 2]
    if sort == "Int":
        return [-2, -1, 0, 1, 2]
    if sort == "String":
        return list(STRING_DEFAULTS)
    if sort == "Bool":
        return [False, True]
    if sort == "Unit":
        return [dsl.UNIT]
    if "option" in sort:
        return [dsl.option_none_v(), *[dsl.option_some_v(x) for x in
                _defaults(sort["option"], profile, depth + 1)[:MAX_SORT_VALUES - 1]]]
    if "enum" in sort:
        return [dsl.enum_v(sort["enum"], x) for x in profile.enums[sort["enum"]]["constructors"]][:MAX_SORT_VALUES]
    if "list" in sort:
        values = _defaults(sort["list"], profile, depth + 1)[:4]
        return [(), *((x,) for x in values), *((x, x) for x in values[:2])]
    if "record" in sort:
        fields = profile.records[sort["record"]]["fields"]
        domains = [_defaults(f["sort"], profile, depth + 1) for f in fields]
        return [dsl.record_v(sort["record"], xs) for xs in islice(product(*domains), MAX_SORT_VALUES)]
    if "result" in sort:
        return [(side, x) for side in ("error", "ok")
                for x in _defaults(sort["result"][side], profile, depth + 1)[:MAX_SORT_VALUES // 2]]
    raise ValueError("unsupported seed sort")


def _universal(formula: dict) -> tuple[list[Any], dict]:
    sorts = []
    while formula.get("tag") == "forall":
        sorts.append(formula["sort"])
        formula = formula["body"]
    return sorts, formula


def _wire_bound(value: Any) -> None:
    nodes = 0

    def visit(value: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_VALUE_NODES or depth > MAX_DEPTH:
            raise ValueError("critic wire exceeds checker node/depth bound")
        if isinstance(value, dict):
            for inner in value.values():
                visit(inner, depth + 1)
        elif isinstance(value, list):
            for inner in value:
                visit(inner, depth + 1)

    visit(value, 0)


def probe_interface(profile_json: dict | None, statements: dict) -> dict:
    """Describe this phase's strict contract-search wire, never a test oracle.

    Formal contract search uses the existing python-v0_2 value serialization even
    for VSCore deliverables. Generated-source review has its separate raw carrier.
    The interface contains type shapes and admitted IDs, not expected outputs.
    """
    out = {"serialization_profile": "python-v0_2", "targets": {},
           "functional_search_available": False, "milestone_authority": False}
    if profile_json is None:
        return out
    profile = dsl.Profile.from_json(profile_json)

    def shape(sort):
        if sort in ("Nat", "Int"):
            return {"int": "canonical decimal string; nonnegative for Nat"}
        if sort == "String":
            return {"str": "Unicode scalar string"}
        if sort == "Bool":
            return {"bool": "JSON boolean"}
        if sort == "Unit":
            return {"none": None}
        if "list" in sort:
            return {"list": {"elements": shape(sort["list"])}}
        if "option" in sort:
            return {"one_of": [{"none": None}, shape(sort["option"])]}
        if "enum" in sort:
            return {"str": {"one_of": profile.enums[sort["enum"]]["constructors"]}}
        if "record" in sort:
            return {"dict": {f["name"]: shape(f["sort"])
                             for f in profile.records[sort["record"]]["fields"]}}
        if "result" in sort:
            return {"one_of": [{"tuple": [{"str": side}, shape(sort["result"][side])]}
                               for side in ("ok", "error")]}
        raise ValueError("unsupported contract-search sort")

    for oid, st in statements.items():
        package = contract_values.statement_value_package(st)
        if st.get("role") != "guarantee" or package is None or "formula" not in package:
            continue
        sorts, _ = _universal(package["formula"])
        entries = {sid: {"lean_symbol": spec["lean_decl"], "input_sorts": spec["args"],
                         "inputs": [shape(s) for s in spec["args"]],
                         "result_sort": spec["result"], "expected": shape(spec["result"])}
                   for sid, spec in profile.symbols.items()
                   if spec["lean_decl"] in st.get("semantic_closure", [])}
        calls = sorted(dsl.calls(package["formula"]) & profile.symbols.keys())
        source_symbols = set()
        full_package = st.get("formula_package", {})
        if full_package.get("encoding") == "verislop.source-contract-facets/0.1":
            from .source_contract import symbols
            source_symbols = symbols(full_package)
        functional_symbols = sorted(source_symbols or (set(calls) | entries.keys()))
        if source_symbols:
            entries = {sid: spec for sid, spec in entries.items() if sid in source_symbols}
        functional = bool(calls or entries)
        out["targets"][oid] = {"universal_input_sorts": sorts,
            "universal_inputs": [shape(s) for s in sorts], "value_formula_calls": calls,
            "reference_entries": entries, "functional_symbols": functional_symbols, "functional": functional}
        out["functional_search_available"] |= functional
    return out


def validate_proposals(analysis: contract.Analysis, proposals: list[dict]) -> list[str]:
    """Validate a concrete search submission without Lean/model calls or proof claims.

    This only checks annotation shape, admitted entry/binder signatures and strict wire
    values against the supplied kernel-derived analysis. ``[]`` is not proof evidence.
    """
    if not isinstance(proposals, list) or len(proposals) > MAX_PROPOSALS:
        return ["proposal list exceeds the bounded checker interface"]
    if analysis.profile is None:
        return ["candidate analysis has no admitted profile"]
    errors = []
    try:
        profile = dsl.Profile.from_json(analysis.profile)
        for index, proposal in enumerate(proposals):
            try:
                if not isinstance(proposal, dict):
                    raise ValueError("critic proposal must be an object")
                probe = "entry_symbol" in proposal
                keys = {"obligation_id", "inputs", "entry_symbol", "exact_clause_id", "expected"} if probe else {"obligation_id", "inputs"}
                if set(proposal) != keys:
                    raise ValueError("critic proposal fields differ from the registered interface")
                oid = proposal["obligation_id"]
                if not isinstance(oid, str):
                    raise ValueError("obligation_id must be an exact string")
                st = analysis.statements.get(oid, {})
                value_package = contract_values.statement_value_package(st)
                if st.get("role") != "guarantee" or value_package is None:
                    raise ValueError("proposal does not identify an executable candidate guarantee")
                sorts, _ = _universal(value_package["formula"])
                if probe:
                    sid = proposal["entry_symbol"]
                    if not isinstance(sid, str):
                        raise ValueError("entry_symbol must be an exact string")
                    if sid not in profile.symbols:
                        sid = next((k for k, s in profile.symbols.items() if s["lean_decl"] == sid), "")
                    if sid not in profile.symbols or profile.symbols[sid]["lean_decl"] not in st["semantic_closure"]:
                        raise ValueError("reference entry must be admitted by this guarantee's semantic closure")
                    if not isinstance(proposal["exact_clause_id"], str) or not proposal["exact_clause_id"]:
                        raise ValueError("reference probe requires an exact clause annotation")
                    sorts = profile.symbols[sid]["args"]
                    _wire_bound(proposal["expected"])
                    expected = wire.decode_result(proposal["expected"], profile.symbols[sid]["result"], profile)
                    if canonical.dumps(wire.encode_arg(expected, profile.symbols[sid]["result"], profile)) != canonical.dumps(proposal["expected"]):
                        raise ValueError("expected wire is not canonical for its exact result sort")
                inputs = proposal["inputs"]
                if not isinstance(inputs, list) or len(inputs) != len(sorts):
                    raise ValueError("input wires do not match outer binder/entry arity")
                _wire_bound(inputs)
                values = [wire.decode_result(x, s, profile) for x, s in zip(inputs, sorts)]
                if canonical.dumps([wire.encode_arg(v, s, profile) for v, s in zip(values, sorts)]) != canonical.dumps(inputs):
                    raise ValueError("input wire is not canonical for its exact sort")
            except (ValueError, TypeError, KeyError) as exc:
                errors.append(f"proposal[{index}]: {exc}")
    except (ValueError, TypeError, KeyError) as exc:
        errors.append("candidate analysis cannot validate wire signatures: " + str(exc))
    return errors


def _closed_formula(formula: dict, values: list[Any], sorts: list[Any], profile: dsl.Profile) -> dict:
    expr = reify.denote_formula(formula, profile)
    denoter = reify._Denoter(profile)
    for value, sort in zip(values, sorts):
        literal, _ = denoter.term(_literal(value, sort, profile), [])
        expr = instantiate1(expr["pi"]["body"], literal)
    return expr


def _definition_bodies(profile: dsl.Profile, env: contract.Env) -> dict[str, dict]:
    out = {}
    for sid, spec in profile.symbols.items():
        expr = env.decls[spec["lean_decl"]].get("value")
        if expr is None:
            continue
        ctx = []
        for sort in spec["args"]:
            if "lam" not in expr:
                break
            row = expr["lam"]
            ctx.insert(0, ("var", sort))
            expr = row["body"]
        else:
            try:
                body = reify._Reifier(profile, env.decls, fuel=256).term(expr, ctx)
                if dsl.sort_eq(dsl.type_term(body, list(reversed(spec["args"])), profile), spec["result"]):
                    out[sid] = body
            except (ValueError, KeyError, reify.Unsupported):
                continue
    return out


def _evaluator(profile: dsl.Profile, bodies: dict[str, dict], executions: list[dict] | None = None) -> dsl.Evaluator:
    evaluator = dsl.Evaluator(profile, {}, lambda _body, _env: [], step_budget=50_000,
                              sample_candidates=lambda _sort, _body, _env: [])
    trace_bytes = 0
    def execute(sid: str, body: dict, args: list):
        nonlocal trace_bytes
        result = evaluator.term(body, list(reversed(args)))
        if executions is not None:
            signature = profile.symbols[sid]
            try:
                call = {"symbol": sid,
                    "inputs": [wire.encode_arg(v, s, profile) for v, s in zip(args, signature["args"])],
                    "actual": wire.encode_arg(result, signature["result"], profile)}
                _wire_bound(call)
                size = len(canonical.dumps(call))
                if trace_bytes + size > 1024 * 1024:
                    raise ValueError("trace byte limit")
                trace_bytes += size
            except (ValueError, TypeError, KeyError):
                # Instrumentation must not change formula evaluation or manufacture
                # an output. Keep completion with an explicit omitted-payload limit.
                call = {"symbol": sid, "completed": True, "payload_omitted": "bounded trace limit"}
            if len(executions) >= MAX_VALUE_NODES:
                # Completions are postorder. Preserve the most recent calls,
                # including the outer endpoint, rather than saturating on helpers.
                del executions[:MAX_VALUE_NODES // 2]
                call["preceding_trace_truncated"] = True
            executions.append(call)
        return result
    evaluator.symbols = {sid: (lambda args, sid=sid, body=body: execute(sid, body, args))
                         for sid, body in bodies.items()}
    return evaluator


def _clean_root(env: contract.Env, root: str, pol: dict) -> tuple[bool, list[str]]:
    row = env.decls.get(root, {})
    axs = env.axioms(root) if root in env.decls else []
    ok = (row.get("kind") == "theorem" and row.get("safety") == "safe"
          and isinstance(row.get("axioms"), list) and isinstance(row.get("unresolved_constants"), list)
          and not row.get("level_params") and not row.get("unresolved_constants")
          and all(policy.classify_axiom(x, pol) == "allowed" for x in axs))
    return ok, axs


def _kernel_options(pol: dict) -> dict:
    return {"timeout": pol["kernel_timeout_seconds"], "memory_mb": pol["memory_mb"],
            "require_network_isolation": pol["require_network_isolation"],
            "require_filesystem_isolation": pol["require_filesystem_isolation"]}


def _derivations(profile: dsl.Profile) -> str:
    """Derive concrete equality bottom-up for dependent record carriers."""
    names = [e["lean_decl"] for e in profile.enums.values()]
    done = set()

    def visit_sort(sort: Any) -> None:
        if isinstance(sort, dict):
            if "record" in sort:
                visit_record(sort["record"])
            elif "list" in sort:
                visit_sort(sort["list"])
            elif "option" in sort:
                visit_sort(sort["option"])
            elif "result" in sort:
                for inner in sort["result"].values():
                    visit_sort(inner)

    def visit_record(rid: str) -> None:
        if rid in done:
            return
        done.add(rid)  # Profile validation already excludes recursive carriers.
        row = profile.records[rid]
        for field in row["fields"]:
            visit_sort(field["sort"])
        names.append(row["lean_decl"])

    for rid in profile.records:
        visit_record(rid)
    return "\n".join("deriving instance DecidableEq for " + _qualified(name) for name in names)


def _compile(tc: leanbridge.Toolchain, pol: dict, source: bytes, directory: Path):
    return leanbridge.compile_module(tc, source, directory, timeout=pol["build_timeout_seconds"],
                                    memory_mb=pol["memory_mb"],
                                    require_network_isolation=pol["require_network_isolation"],
                                    require_filesystem_isolation=pol["require_filesystem_isolation"])


def _proof(pkg: Package, base: bytes, expr: dict, binding: dict, profile: dsl.Profile,
           tc: leanbridge.Toolchain, pol: dict, expected_env: contract.Env) -> dict:
    case_hash = canonical.digest_json({"binding": binding, "proposition": expr})
    ns = "VeriSlopRefutation_" + case_hash.split(":")[1][:24]
    root = ns + ".closed_check"
    if root in expected_env.decls:
        return {"ok": False, "reason": "generated proof name already exists"}
    # DecidableEq derivations are proof-producing and cannot alter the explicit denotation.
    # They permit concrete equality of record outputs without requiring the proposal to
    # have declared instances. Any derivation unsupported by Lean simply yields UNKNOWN.
    derives = _derivations(profile)
    extra = (f"\nnamespace {ns}\n{derives}\n"
             f"theorem closed_check : {_expr_lean(expr)} := by decide +kernel\nend {ns}\n").encode()
    source = base + extra
    target = pkg.path("contract") / "refutation" / case_hash.split(":")[1]
    with fsutil.temporary_directory(prefix="verislop-refutation-") as tmp:
        comp = _compile(tc, pol, source, Path(tmp) / "build")
        if not comp.ok:
            return {"ok": False, "reason": "closed proof did not elaborate", "errors": comp.errors[:4]}
        exported = leanbridge.run_kernel_tool(tc, comp.olean, {"export": True, "axioms": True,
            "defeq": [{"id": "closed_check", "theorem": parse_name(root), "expr": expr}]}, **_kernel_options(pol))
        env = contract.Env.from_export(exported, pol, "candidate refutation")
        same = all(env.hashes.get(name) == h for name, h in expected_env.hashes.items())
        clean, axs = _clean_root(env, root, pol)
        checked = exported.get("defeq", [])
        expected = {"ok": True, "typechecks": True, "defeq": True}
        if (env.diagnostics or not same or not clean or len(checked) != 1
                or checked[0].get("id") != "closed_check" or checked[0].get("result") != expected):
            return {"ok": False, "reason": "kernel identity, replay or proof closure check failed", "axioms": axs}
        # Candidate theorem holes are permitted; the refutation root has zero sorry
        # dependencies and the root proof was replayed by the kernel. Never use global
        # compilation warning counts as the refutation's proof status.
        olean_data = comp.olean.read_bytes()
        export_data = canonical.dumps(exported)
        module_name = "proof" + comp.olean.suffix
        artifacts = {"source": {"path": pkg.rel(target / "Refutation.lean"), "sha256": canonical.digest(source)},
                     "compiled_module": {"path": pkg.rel(target / module_name), "sha256": canonical.digest(olean_data)},
                     "kernel_export": {"path": pkg.rel(target / "kernel.json"), "sha256": canonical.digest(export_data)}}
        receipt = {"ok": True, "binding": binding, "lean_symbol": root,
                   "proposition_hash": canonical.digest_json(expr), "declaration_hash": decl_hash(env.decls[root]),
                   "axioms": axs, "refutation_sorry_dependencies": 0,
                   "candidate_sorry_warning_count": len(comp.sorry_positions),
                   "kernel_defeq": checked[0]["result"], "artifacts": artifacts,
                   "toolchain": tc.identity(), "kernel_tool_hash": leanbridge.kernel_tool_hash()}
        receipt["kernel_proof_hash"] = canonical.digest_json({"module": artifacts["compiled_module"]["sha256"],
            "declaration": receipt["declaration_hash"], "proposition": receipt["proposition_hash"],
            "kernel_export": artifacts["kernel_export"]["sha256"], "kernel_tool": receipt["kernel_tool_hash"],
            "toolchain": receipt["toolchain"]})
        fsutil.atomic_write(target / "Refutation.lean", source)
        fsutil.atomic_write(target / module_name, olean_data)
        fsutil.atomic_write(target / "kernel.json", export_data)
        return receipt


def check(pkg: Package, source: bytes, form: dict, records: list, analysis: contract.Analysis,
          *, proposals: list[dict] | None = None) -> dict:
    """Find concrete defects; this function never grants PROVED/TESTED/release states.

    Proposals use strict existing wire values in outermost-to-innermost binder order:
    ``{obligation_id, inputs}``. Reference probes additionally provide ``entry_symbol``,
    ``exact_clause_id`` and ``expected`` (the latter is an untrusted proposed wire output).
    A missing counterexample, an unsupported sort, or any failed check remains UNKNOWN.
    """
    proposals = [] if proposals is None else proposals
    report = {"schema_version": "0.1", "artifact_kind": "candidate_contract_refutation", "checker": VERSION,
              "status": "UNKNOWN", "candidate_source_hash": canonical.digest(source),
              "formalization_hash": canonical.digest_json(form), "records_hash": canonical.digest_json(records),
              "analysis_hash": canonical.digest_json(_analysis_identity(analysis)),
              "receipts": [], "diagnostics": [], "execution_observations": [], "bounded_scan": {"max_cases": MAX_CASES,
                  "max_sort_values": MAX_SORT_VALUES, "max_proof_attempts": MAX_PROOF_ATTEMPTS,
                  "string_defaults": list(STRING_DEFAULTS), "cases_evaluated": 0, "proof_attempts": 0,
                  "no_counterexample_is_not_a_proof": True}}
    if not isinstance(proposals, list) or len(proposals) > MAX_PROPOSALS:
        report["diagnostics"].append("proposal list exceeds the bounded checker interface")
        report["report_hash"] = canonical.digest_json(report)
        return report
    try:
        report["proposals_hash"] = canonical.digest_json(proposals)
        if analysis.profile is None or any(d.severity in ("blocking", "infrastructure") for d in analysis.diagnostics):
            raise ValueError("candidate analysis is absent or has unresolved blocking diagnostics")
        pol = policy.get("strict")
        tc = leanbridge.resolve_toolchain(form["lean_toolchain"])
        active = [r for r in records if not r["blocked_by"]]
        base, imports, problems = contract.compose_challenge(source,
            contract.registry_lean(active, contract.binding_names(form)))
        if problems or any(i.split(".")[0] not in pol["allowed_import_roots"] for i in imports):
            raise ValueError("candidate composition/import policy is invalid")
        with fsutil.temporary_directory(prefix="verislop-refutation-base-") as tmp:
            comp = _compile(tc, pol, base, Path(tmp) / "base")
            if not comp.ok:
                raise ValueError("candidate source does not compile: " + "; ".join(comp.errors[:3]))
            exp = leanbridge.run_kernel_tool(tc, comp.olean, {"export": True, "axioms": True}, **_kernel_options(pol))
            env = contract.Env.from_export(exp, pol, "candidate refutation base")
            if env.diagnostics:
                raise ValueError("candidate kernel replay/import policy rejected")
            fresh = contract.analyze(env, records, form, pol, form["lean_toolchain"].strip(), "candidate refutation base")
            if (any(d.severity in ("blocking", "infrastructure") for d in fresh.diagnostics)
                    or _analysis_identity(fresh) != _analysis_identity(analysis)):
                raise ValueError("source/form/records do not match the supplied kernel-derived analysis")
            if fresh.defeq_requests:
                denotations = leanbridge.run_kernel_tool(tc, comp.olean, {"defeq": fresh.defeq_requests}, **_kernel_options(pol))
                if (sorted(row.get("id", "") for row in denotations.get("defeq", []))
                        != sorted(row["id"] for row in fresh.defeq_requests)
                        or contract.defeq_diagnostics(denotations, "candidate refutation base")):
                    raise ValueError("candidate denotation identity was not accepted by the kernel")
        profile = dsl.Profile.from_json(fresh.profile)
        bodies = _definition_bodies(profile, env)
        binding = {key: report[key] for key in ("candidate_source_hash", "formalization_hash", "records_hash", "analysis_hash", "proposals_hash")}
        st_by_id = {oid: st for oid, st in fresh.statements.items() if st["role"] == "guarantee"
                    and contract_values.statement_value_package(st) is not None}
        for oid, st in fresh.statements.items():
            if st["role"] == "guarantee" and oid not in st_by_id:
                source_only = st.get("representation") in ("contract_facets", "source_facets")
                report["diagnostics"].append({"kind": "SOURCE_ONLY_SURFACE" if st.get("representation") == "source_facets" else "NATIVE_SOURCE_SURFACE" if source_only else "UNSUPPORTED_GUARANTEE",
                    "obligation_id": oid,
                    "message": ("source-only guarantee has no value refutation oracle; actual generated-source "
                                "conformance is checked separately" if source_only else
                                "opaque or unsupported statement cannot produce a counterexample proof")})
        done = set()

        def process(oid: str, inputs: list, origin: str, probe: dict | None = None) -> None:
            if oid not in st_by_id:
                raise ValueError("proposal does not identify an executable candidate guarantee")
            st = st_by_id[oid]
            value_package = contract_values.statement_value_package(st)
            formula = value_package["formula"]
            sorts, body = _universal(formula)
            if probe is not None:
                sid = probe["entry_symbol"]
                if sid not in profile.symbols:
                    sid = next((k for k, s in profile.symbols.items() if s["lean_decl"] == sid), "")
                if sid not in profile.symbols or profile.symbols[sid]["lean_decl"] not in st["semantic_closure"]:
                    raise ValueError("reference entry must be admitted by this guarantee's semantic closure")
                if not isinstance(probe["exact_clause_id"], str) or not probe["exact_clause_id"]:
                    raise ValueError("reference probe requires an exact clause annotation")
                sorts = profile.symbols[sid]["args"]
            if not isinstance(inputs, list) or len(inputs) != len(sorts):
                raise ValueError("input wires do not match outer binder/entry arity")
            _wire_bound(inputs)
            values = [wire.decode_result(x, s, profile) for x, s in zip(inputs, sorts)]
            normalized = [wire.encode_arg(v, s, profile) for v, s in zip(values, sorts)]
            if canonical.dumps(normalized) != canonical.dumps(inputs):
                raise ValueError("input wire is not canonical for its exact sort")
            key = canonical.digest_json({"obligation_id": oid, "inputs": inputs, "probe": probe})
            if key in done or report["bounded_scan"]["cases_evaluated"] >= MAX_CASES:
                return
            done.add(key)
            report["bounded_scan"]["cases_evaluated"] += 1
            executions = []
            evaluator = _evaluator(profile, bodies, executions)
            # These are observations of the bounded model search, never proof or
            # implementation test evidence. Record actual calls even when a later
            # quantified conjunct is undecidable, and distinguish vacuous cases.
            observation = {"obligation_id": oid, "inputs": inputs, "origin": origin,
                           "calls": executions, "milestone_authority": False}
            if origin == "critic_proposal":
                report["execution_observations"].append(observation)
            if probe is None:
                try:
                    truth = evaluator.formula(body, list(reversed(values)))
                except (ValueError, dsl.BudgetExceeded, dsl.TargetFault):
                    truth = dsl.UNKNOWN
                if truth.value is True and truth.exact:
                    return
                # An explicit concrete critic case may still be computable by Lean even
                # when the host search filter cannot reify a definition body. The host
                # evaluator is never a prerequisite for a kernel counterexample proof.
                if (truth.value is not False or not truth.exact) and origin != "critic_proposal":
                    return
                proposition = app(const("Not"), _closed_formula(formula, values, sorts, profile))
                info = {"kind": "guarantee_refutation", "status": "REFUTED", "obligation_id": oid,
                        "statement_hash": st["statement_hash"], "inputs": inputs, "origin": origin}
            else:
                if sid not in bodies:
                    raise ValueError("reference body cannot be reconstructed in the admitted DSL")
                actual = evaluator.symbols[sid](values)
                result_sort = profile.symbols[sid]["result"]
                expected = wire.decode_result(probe["expected"], result_sort, profile)
                actual_wire = wire.encode_arg(actual, result_sort, profile)
                expected_wire = wire.encode_arg(expected, result_sort, profile)
                if canonical.dumps(expected_wire) != canonical.dumps(probe["expected"]):
                    raise ValueError("expected wire is not canonical for the entry result sort")
                terms = [_literal(v, s, profile) for v, s in zip(values, sorts)]
                equality = {"tag": "eq", "left": {"tag": "call", "symbol": sid, "args": terms},
                            "right": _literal(actual, result_sort, profile)}
                proposition = reify.denote_formula(equality, profile)
                info = {"kind": "reference_case", "status": "SEMANTIC_MISMATCH" if actual != expected else "REFERENCE_MATCH",
                        "obligation_id": oid, "statement_hash": st["statement_hash"], "exact_clause_id": probe["exact_clause_id"],
                        "entry_symbol": profile.symbols[sid]["lean_decl"], "inputs": inputs, "actual": actual_wire,
                        "expected": expected_wire, "expectation_authority": "untrusted_critic_annotation",
                        "natural_language_clause_verified": False, "guarantee_refuted": False, "origin": origin}
            if report["bounded_scan"]["proof_attempts"] >= MAX_PROOF_ATTEMPTS:
                return
            report["bounded_scan"]["proof_attempts"] += 1
            if st.get("representation") in ("contract_facets", "source_facets"):
                # A false value instance refutes the required mixed conjunction;
                # it does not refute a delivery source fact. Bind the exact projected
                # surface and original conjunction rather than relabeling the proof.
                info.update({"facet": "value", "parent_package_hash": canonical.digest_json(st["formula_package"]),
                             "value_package_hash": canonical.digest_json(value_package),
                             "value_projection": st["formula_package"]["value_projection"]})
            proof = _proof(pkg, base, proposition, {**binding, **info}, profile, tc, pol, env)
            if not proof["ok"]:
                report["diagnostics"].append({"obligation_id": oid, "inputs": inputs, **proof})
                return
            receipt = {**info, **proof}
            receipt["receipt_hash"] = canonical.digest_json(receipt)
            report["receipts"].append(receipt)
            if info["status"] == "REFUTED":
                report["status"] = "REFUTED"
            elif info["status"] == "SEMANTIC_MISMATCH" and report["status"] != "REFUTED":
                report["status"] = "SEMANTIC_MISMATCH"

        for proposal in proposals:
            errors = validate_proposals(fresh, [proposal])
            if errors:
                report["diagnostics"].append({"origin": "critic_proposal", "kind": "INVALID_PROPOSAL", "message": "; ".join(errors)})
                continue
            try:
                if not isinstance(proposal, dict):
                    raise ValueError("critic proposal must be an object")
                is_probe = "entry_symbol" in proposal
                keys = {"obligation_id", "inputs", "entry_symbol", "exact_clause_id", "expected"} if is_probe else {"obligation_id", "inputs"}
                if set(proposal) != keys:
                    raise ValueError("critic proposal fields differ from the registered interface")
                process(proposal["obligation_id"], proposal["inputs"], "critic_proposal", proposal if is_probe else None)
            except (ValueError, KeyError, TypeError, dsl.BudgetExceeded, dsl.TargetFault) as exc:
                report["diagnostics"].append({"origin": "critic_proposal", "kind": "UNKNOWN_EVALUATION", "message": str(exc)})
        for oid, st in st_by_id.items():
            if any(r["obligation_id"] == oid and r["status"] == "REFUTED" for r in report["receipts"]):
                continue
            sorts, _ = _universal(contract_values.statement_value_package(st)["formula"])
            try:
                domains = [_defaults(s, profile) for s in sorts]
                for values in islice(product(*domains), MAX_CASES):
                    process(oid, [wire.encode_arg(v, s, profile) for v, s in zip(values, sorts)], "bounded_sort_scan")
                    if any(r["obligation_id"] == oid and r["status"] == "REFUTED" for r in report["receipts"]):
                        break
                    if report["bounded_scan"]["cases_evaluated"] >= MAX_CASES:
                        break
            except (ValueError, KeyError, TypeError, dsl.BudgetExceeded, dsl.TargetFault) as exc:
                report["diagnostics"].append({"obligation_id": oid, "origin": "bounded_sort_scan", "message": str(exc)})
    except (ValueError, KeyError, TypeError, InfrastructureError) as exc:
        report["diagnostics"].append({"message": str(exc)})
    report["report_hash"] = canonical.digest_json(report)
    return report
