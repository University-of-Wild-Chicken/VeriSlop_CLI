"""Kernel-checked VSCore 0.3 source admission and accepted-AST reconstruction.

This finite source check binds decoding and typing to delivered canonical JSON. It assigns
no obligation milestone and establishes no accepted-contract refinement or execution endpoint.
Both clean builds replay all supplied Lean modules; candidate host ASTs remain proposals.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

from .. import canonical, fsutil, leanbridge, policy, schemas
from ..errors import Diagnostic, VeriSlopError
from ..exprjson import app, const, name_str
from ..stage import StageResult, status_from
from ..verifiers import host_environment, trusted_dependencies, verifier_hash
from ..bridges.manifest import InvalidPackage
from . import vscore_source as old, vscore_target as base, vscore3_source as src

VERIFIER = "verislop.vscore3-source-checker"
MODULE = "VSCore3SourceCheck"
LIB_MODULES = ("VSCore.Syntax", "VSCore.Decode", "VSCore3.Syntax", "VSCore3.Equality", "VSCore3.Decode", "VSCore3.Typed",
               "VSCore3.Typing", "VSCore3.Semantics", "VSCore3.Proofs", "VSCore3.Transport", "VSCore3.SourceFacts", "VSCore3")
MAX_SOURCE_BYTES = 16 * 1024
MAX_TOTAL_SECONDS = 1800
CLAIMS = [
    {"id": "exact_source_decoding", "pass_condition": "kernel replay accepts source_parses for frozen bytes and AST"},
    {"id": "program_admission", "pass_condition": "kernel replay accepts source_checks for frozen profile, AST and signatures"},
    {"id": "accepted_ast_reconstruction", "pass_condition": "replayed constructor values re-encode to exact frozen bytes and profile"},
    {"id": "two_clean_builds", "pass_condition": "both isolated clean compilations and complete supplied-module replays succeed"},
    {"id": "determinism", "pass_condition": "normalized build observations and reconstructed IR are identical"},
]


class UnsupportedSource(old.SourceError):
    code = "UNSUPPORTED_CAPABILITY"


def library_sources() -> dict[str, bytes]:
    return {m: (base.LIB_ROOT / base.module_path(m)).read_bytes() for m in LIB_MODULES}


def source_module(data: bytes):
    """Version dispatch after strict canonical lexical parsing; never fall back on failure."""
    value = old.parse_json(data)
    if not isinstance(value, dict):
        raise old.SourceError("source must be a program object")
    language = value.get("language")
    if language == old.LANGUAGE:
        return old
    if language == src.LANGUAGE:
        return src
    raise UnsupportedSource(f"unsupported VSCore language {language!r}")


class Reify(base._Reify):
    """Only bounded constructor reduction; no trusted evaluation of candidate functions."""

    def ty(self, x):
        e, env = self.whnf(*x)
        for tag in ("nat", "int", "bool", "string", "unit"):
            if e == const("VSCore3.Ty." + tag):
                return tag
        for tag in ("enum", "record", "variant"):
            if (a := self.head(e, env, "VSCore3.Ty." + tag, 1)) is not None:
                return (tag, self.string(a[0]))
        for tag in ("option", "list"):
            if (a := self.head(e, env, "VSCore3.Ty." + tag, 1)) is not None:
                return (tag, self.ty(a[0]))
        if (a := self.head(e, env, "VSCore3.Ty.result", 2)) is not None:
            return ("result", self.ty(a[0]), self.ty(a[1]))
        raise self.fail("VSCore 0.3 type")

    def pair(self, x, first, second):
        a = self.head(*x, "Prod.mk", 4)
        if a is None:
            raise self.fail("ordered pair")
        return (first(a[2]), second(a[3]))

    def pairs(self, x, second_type, second):
        pair_type = app(const("Prod", [0, 0]), const("String"), second_type)
        return self.list(x, pair_type, lambda p: self.pair(p, self.string, second))

    def expr(self, x):
        e, env = self.whnf(*x)
        if (a := self.head(e, env, "VSCore3.Expr.int", 1)) is not None:
            value, scope = self.whnf(*a[0])
            if (n := self.head(value, scope, "Int.ofNat", 1)) is not None:
                return ("int", self.nat(n[0]))
            if (n := self.head(value, scope, "Int.negSucc", 1)) is not None:
                return ("int", -self.nat(n[0]) - 1)
            raise self.fail("canonical Int constructor")
        if (a := self.head(e, env, "VSCore3.Expr.string", 1)) is not None:
            return ("string", tuple(self.list(a[0], const("Nat"), self.nat)))
        for tag, ctor, arity in (("int_fdiv", "intFdiv", 2), ("int_neg", "intNeg", 1),
                                 ("nat_to_int", "natToInt", 1), ("int_to_nat", "intToNat", 1),
                                 ("list_length", "listLength", 1), ("list_range", "listRange", 1),
                                 ("list_reverse", "listReverse", 1), ("list_sort", "listSort", 1),
                                 ("list_unique", "listUnique", 1), ("list_get", "listGet", 2),
                                 ("list_append", "listAppend", 2), ("list_map", "listMap", 2),
                                 ("list_filter", "listFilter", 2), ("list_sum", "listSum", 1)):
            if (a := self.head(e, env, "VSCore3.Expr." + ctor, arity)) is not None:
                return (tag, *(self.expr(v) for v in a))
        for tag in ("var", "nat", "bool"):
            if (a := self.head(e, env, "VSCore3.Expr." + tag, 1)) is not None:
                return (tag, (self.bool if tag == "bool" else self.nat)(a[0]))
        if e == const("VSCore3.Expr.unit"):
            return ("unit",)
        if (a := self.head(e, env, "VSCore3.Expr.enum", 2)) is not None:
            return ("enum", self.string(a[0]), self.string(a[1]))
        if (a := self.head(e, env, "VSCore3.Expr.bin", 3)) is not None:
            op = next((o for o in src.BIN_OPS if self.closed(a[0]) == const("VSCore.BinOp." + o)), None)
            if op is None:
                raise self.fail("binary operator")
            return ("bin", op, self.expr(a[1]), self.expr(a[2]))
        for tag, ctor, arity in (("not", "not", 1), ("ite", "ite", 3), ("let", "letE", 2),
                                 ("match", "matchResult", 3), ("some", "some", 1),
                                 ("match_option", "matchOption", 3), ("cons", "cons", 2),
                                 ("match_list", "matchList", 3), ("list_fold", "listFold", 3),
                                 ("nat_fold", "natFold", 3)):
            if (a := self.head(e, env, "VSCore3.Expr." + ctor, arity)) is not None:
                return (tag, *(self.expr(v) for v in a))
        for tag in ("ok", "error"):
            if (a := self.head(e, env, "VSCore3.Expr." + tag, 2)) is not None:
                return (tag, self.ty(a[0]), self.expr(a[1]))
        for tag in ("nil", "none"):
            if (a := self.head(e, env, "VSCore3.Expr." + tag, 1)) is not None:
                return (tag, self.ty(a[0]))
        if (a := self.head(e, env, "VSCore3.Expr.record", 2)) is not None:
            return ("record", self.string(a[0]), self.pairs(a[1], const("VSCore3.Expr"), self.expr))
        if (a := self.head(e, env, "VSCore3.Expr.project", 2)) is not None:
            return ("project", self.expr(a[0]), self.string(a[1]))
        if (a := self.head(e, env, "VSCore3.Expr.variant", 3)) is not None:
            return ("variant", self.string(a[0]), self.string(a[1]), self.list(a[2], const("VSCore3.Expr"), self.expr))
        if (a := self.head(e, env, "VSCore3.Expr.matchVariant", 2)) is not None:
            return ("match_variant", self.expr(a[0]), self.pairs(a[1], const("VSCore3.Expr"), self.expr))
        if (a := self.head(e, env, "VSCore3.Expr.call", 2)) is not None:
            return ("call", self.string(a[0]), self.list(a[1], const("VSCore3.Expr"), self.expr))
        raise self.fail("VSCore 0.3 expression")

    def declaration(self, x):
        for tag in ("record", "variant"):
            if (a := self.head(*x, "VSCore3.DataDecl." + tag, 2)) is not None:
                if tag == "record":
                    return {"tag": tag, "id": self.string(a[0]), "fields": self.pairs(a[1], const("VSCore3.Ty"), self.ty)}
                ts = app(const("List", [0]), const("VSCore3.Ty"))
                return {"tag": tag, "id": self.string(a[0]), "constructors":
                        self.pairs(a[1], ts, lambda y: self.list(y, const("VSCore3.Ty"), self.ty))}
        raise self.fail("VSCore 0.3 declaration")

    def entry(self, x):
        a = self.head(*x, "VSCore3.Entry.mk", 4)
        if a is None:
            raise self.fail("VSCore 0.3 function")
        return {"id": self.string(a[0]), "params": self.list(a[1], const("VSCore3.Ty"), self.ty),
                "result": self.ty(a[2]), "body": self.expr(a[3])}

    def signature(self, x):
        a = self.head(*x, "VSCore3.EntrySig.mk", 3)
        if a is None:
            raise self.fail("VSCore 0.3 entry signature")
        return {"id": self.string(a[0]), "params": self.list(a[1], const("VSCore3.Ty"), self.ty), "result": self.ty(a[2])}

    def program(self, x):
        a = self.head(*x, "VSCore3.Program.mk", 5)
        if a is None:
            raise self.fail("VSCore 0.3 program")
        return {"language": self.string(a[0]), "profile": self.string(a[1]),
                "declarations": self.list(a[2], const("VSCore3.DataDecl"), self.declaration),
                "helpers": self.list(a[3], const("VSCore3.Entry"), self.entry),
                "entries": self.list(a[4], const("VSCore3.Entry"), self.entry)}


_Reify = Reify


def goal_source(data: bytes, program: dict, signatures: list, enums: dict) -> bytes:
    pairs = ", ".join(f"({src.lean_string(k)}, {src.lean_list([src.lean_string(c) for c in cs])})"
                      for k, cs in sorted(enums.items()))
    return ("import VSCore3\nset_option maxRecDepth 100000\nset_option maxHeartbeats 20000000\n"
            f"namespace {MODULE}\n"
            f"def sourceBytes : List Nat := {src.lean_list([str(b) for b in data])}\n"
            f"def profile : VSCore3.Profile := {{ enums := [{pairs}] }}\n"
            f"def rawProgram : VSCore3.Program := {src.lean_program(program)}\n"
            f"def signatures : List VSCore3.EntrySig := {src.lean_signatures(signatures)}\n"
            "theorem source_parses : VSCore3.parseSource sourceBytes = .ok rawProgram := by rfl\n"
            "theorem source_checks : VSCore3.checkProgram profile rawProgram = .ok signatures :=\n"
            "  VSCore3.checkProgram_of_check (by decide +kernel)\n"
            f"end {MODULE}\n").encode()


def _require(condition, message, code="KERNEL_REJECTION"):
    if not condition:
        raise base.BridgeInvalid(message, code)


@dataclass
class Build:
    observation: dict
    ir: dict
    modules: dict


def run_build(tc, data: bytes, proposed: dict, signatures: list, enums: dict, sources: dict, goal: bytes,
              deadline: float | None = None) -> Build:
    pol = policy.get("strict")
    opts = {"timeout": pol["build_timeout_seconds"], "memory_mb": pol["memory_mb"],
            "require_network_isolation": True, "require_filesystem_isolation": True}
    modules, deps, compiles = {}, {}, {}
    def remaining(limit):
        seconds = limit if deadline is None else min(limit, deadline - time.monotonic())
        if seconds <= 0:
            raise base.BridgeInvalid("source-check time budget exhausted", "BUDGET_EXHAUSTED")
        return seconds
    with fsutil.temporary_directory(prefix="verislop-vscore3-check-") as tmp:
        root = Path(tmp)
        for module, source in [*sources.items(), (MODULE, goal)]:
            opts["timeout"] = remaining(pol["build_timeout_seconds"])
            res, parts = leanbridge.compile_named_module(tc, root, module, source, dict(deps), read_only=[], **opts)
            _require(res.ok and not res.sorry_positions, f"{module}: {res.errors[:3]}", "CANDIDATE_BUILD_FAILURE")
            modules[module] = parts
            deps[module] = {s: str(root / (leanbridge.module_relpath(module) + s)) for s in parts}
            compiles[module] = {"ok": res.ok, "sorries": len(res.sorry_positions)}
        isolation = dict(res.isolation)
        isolation["read_only_paths"] = ["<build>/" + str(Path(p).relative_to(root))
                                        if Path(p).is_relative_to(root) else p
                                        for p in isolation.get("read_only_paths", [])]
    resp = leanbridge.run_kernel_tool_modules(tc, modules, MODULE, {"export": True, "axioms": True},
              timeout=remaining(pol["kernel_timeout_seconds"]), memory_mb=pol["memory_mb"],
              require_network_isolation=True, require_filesystem_isolation=True)
    imp, replay = resp.get("import", {}), resp.get("replay", {})
    _require(imp.get("ok") and replay.get("ok"), f"kernel replay failed: {imp.get('error') or replay.get('error')}")
    staged = {name_str(m["name"]) for m in imp.get("modules", []) if m.get("staged")}
    _require(staged == set(modules), "replayed dependency inventory differs", "UNDECLARED_DEPENDENCY")
    external = [m for m in imp["modules"] if not m.get("staged")]
    _require(all(m["name"] and m["name"][0] in pol["allowed_import_roots"] for m in external),
             "unregistered toolchain import", "UNDECLARED_DEPENDENCY")
    identity, diags = leanbridge.olean_closure_identity(tc, external)
    if diags:
        raise VeriSlopError("toolchain identity failed", diags)
    skipped = {name_str(n) for n in replay.get("not_replayed_unsafe_or_partial", [])}
    _require(all(n.endswith("._unsafe_rec") for n in skipped), "unsafe or partial declaration was not replayed")
    decls = {}
    for c in resp.get("constants", []):
        name = name_str(c["name"])
        if c.get("kind") == "missing_after_replay" and name in skipped:
            continue
        _require("export_error" not in c and c.get("kind") != "missing_after_replay", f"cannot re-export {name}")
        _require(c.get("kind") != "axiom", f"source library declares axiom {name}", "INADMISSIBLE_AXIOM")
        decls[name] = c
    theorem_axioms = {}
    for theorem in ("source_parses", "source_checks"):
        c = decls.get(MODULE + "." + theorem, {})
        _require(c.get("kind") == "theorem", f"missing checked theorem {theorem}")
        _require(not c.get("unresolved_constants"), f"unresolved dependency in {theorem}", "UNDECLARED_DEPENDENCY")
        _require(all(policy.classify_axiom(name_str(n), pol) == "allowed" for n in c.get("axioms", [])),
                 f"inadmissible axiom in {theorem}", "INADMISSIBLE_AXIOM")
        theorem_axioms[theorem] = sorted(name_str(n) for n in c.get("axioms", []))
    r = Reify()
    def value(component):
        c = decls.get(MODULE + "." + component, {})
        _require(c.get("kind") == "definition" and "value" in c, f"missing definition {component}")
        return c["value"], None
    reconstructed = r.program(value("rawProgram"))
    raw_bytes = bytes(r.list(value("sourceBytes"), const("Nat"), r.nat))
    sigs = r.list(value("signatures"), const("VSCore3.EntrySig"), r.signature)
    registry = r.profile(value("profile"))
    _require(raw_bytes == data and src.source_bytes(reconstructed) == data, "accepted AST fails exact-byte reconstruction", "IR_REIFICATION_MISMATCH")
    _require(reconstructed == proposed and sigs == signatures and registry == [[k, cs] for k, cs in sorted(enums.items())],
             "replayed proposals differ from frozen source/profile", "IR_REIFICATION_MISMATCH")
    ir = {"program": src.program_json(reconstructed),
          "signatures": [{"id": s["id"], "params": [src.ty_json(t) for t in s["params"]], "result": src.ty_json(s["result"])} for s in sigs],
          "enums": [{"id": k, "constructors": cs} for k, cs in registry],
          "required_features": src.required_features(reconstructed)}
    observation = {"format": "verislop.vscore3-source-build/0.1", "toolchain": tc.identity(),
          "toolchain_olean_closure": identity, "kernel_tool_hash": leanbridge.kernel_tool_hash(),
          "compiles": compiles, "modules": {m: canonical.digest_json({s: canonical.digest(b) for s, b in ps.items()}) for m, ps in modules.items()},
          "kernel_export_hash": canonical.digest_json(resp.get("constants", [])),
          "replayed_constants": replay.get("constants"), "implementation_ir_hash": canonical.digest_json(ir),
          "theorem_axioms": theorem_axioms, "isolation": isolation}
    return Build(observation, ir, modules)


def check(data: bytes, enums: dict[str, list[str]], out: Path | None = None) -> StageResult:
    result = StageResult("vscore check", "PASS", "exact 0.3 canonical-source admission and reconstructed AST; two kernel replays")
    try:
        # Caller-owned registries can change concurrently; only this private snapshot
        # participates in validation, goal generation, input hashing and publication.
        enums = canonical.loads(canonical.dumps(enums))
        deadline = time.monotonic() + MAX_TOTAL_SECONDS
        if out is not None:
            _require(not out.exists(), "check output already exists; select a new output directory", "INPUT_MUTATION")
        if len(data) > MAX_SOURCE_BYTES:
            raise base.BridgeUnsupported(f"source exceeds frozen {MAX_SOURCE_BYTES}-byte kernel-check budget")
        program = src.parse_source(data)
        sigs = src.check_program(enums, program)
        issues = schemas.validate("vscore-source-v3", src.program_json(program))
        _require(not issues, f"source schema: {issues[:1]}", "INVALID_CANDIDATE")
        sources = library_sources()
        goal = goal_source(data, program, sigs, enums)
        leanbridge._identity.cache_clear()
        tc = leanbridge.resolve_toolchain()
        verifier_hash.cache_clear()
        frozen = {"source": canonical.digest(data), "enums": enums,
                  "library": {m: canonical.digest(s) for m, s in sources.items()},
                  "goal": canonical.digest(goal), "verifier": verifier_hash(VERIFIER),
                  "toolchain": tc.identity(), "claims": CLAIMS,
                  "host_environment": host_environment(), "trusted_dependencies": trusted_dependencies(VERIFIER),
                  "policy": policy.get("strict"), "total_timeout_seconds": MAX_TOTAL_SECONDS,
                  "permitted_nondeterminism": ["temporary build directory prefixes in isolation metadata"]}
        root = canonical.digest_json(frozen)
        a = run_build(tc, data, program, sigs, enums, sources, goal, deadline)
        b = run_build(tc, data, program, sigs, enums, sources, goal, deadline)
        _require(a.observation == b.observation and a.ir == b.ir, "two clean source checks differ", "NONDETERMINISM")
        verifier_hash.cache_clear()
        leanbridge._identity.cache_clear()
        _require(frozen["verifier"] == verifier_hash(VERIFIER) and sources == library_sources(), "verifier changed while checking", "INPUT_MUTATION")
        _require(frozen["toolchain"] == tc.identity(), "pinned toolchain changed while checking", "INPUT_MUTATION")
        _require(root == canonical.digest_json(frozen), "frozen input manifest changed while checking", "INPUT_MUTATION")
        closure_id = "vscore3-source-" + root
        claims = [{**c, "status": "PASS", "closure_id": closure_id, "input_root": root, "verifier_id": VERIFIER,
                   "verifier_hash": frozen["verifier"], "exit_code": 0,
                   "execution_environment": {"toolchain": a.observation["toolchain"], "host": frozen["host_environment"]},
                   "build_indices": [0, 1]} for c in CLAIMS]
        report = {"format": "verislop.vscore3-source-check/0.1", "status": "VERIFIED", "closure_id": closure_id, "input_root": root,
            "inputs": frozen, "verifier": VERIFIER, "toolchain": tc.identity(),
            "claims": claims, "claim_counts": {"total": len(claims), "passed": len(claims), "blocked": 0, "unresolved": 0},
            "builds": [a.observation, b.observation], "assigns_obligation_milestones": False,
            "determinism": {"required": True, "status": "PASS"},
            "provenance": {"public_claims": len(claims), "fully_bound": len(claims), "orphan_claims": 0},
            "correspondence": {"boundary": "replayed source bytes, program, profile and signatures", "status": "PASS"},
            "blocking_reasons": [], "infrastructure_errors": [],
            "assigns_end_to_end_verified": False,
            "scope": "delivered vscore-json/0.3 source admission under its normative Lean checker",
            "trusted": frozen["trusted_dependencies"],
            "dependencies": {"verified": [c["id"] for c in claims], "trusted": frozen["trusted_dependencies"], "undeclared": []},
            "excluded": ["natural-language fidelity", "accepted-contract refinement and obligation transfer", "surface text semantics", "host execution and native compilation", "TESTED campaigns"]}
        ir = {"format": "verislop.vscore3-source-ir/0.1", "language": src.LANGUAGE,
              "source_hash": canonical.digest(data), "input_root": root, **a.ir}
        result.summary.update({"report": report, "implementation_ir": ir, "authoritative_for": "source admission only"})
        result.lines = ["Kernel-checked exact source and program admission; accepted AST reconstructed in two identical builds.",
                        "No accepted-contract bridge or obligation milestone is assigned."]
        if out is not None:
            with fsutil.temporary_directory(prefix="verislop-vscore3-output-") as tmp:
                stage = Path(tmp)
                fsutil.atomic_write(stage / "report.json", canonical.dumps(report))
                fsutil.atomic_write(stage / "implementation-ir.json", canonical.dumps(ir))
                fsutil.atomic_write(stage / "source.vscore.json", data)
                fsutil.atomic_write(stage / "enums.json", canonical.dumps(enums))
                for label, build in (("A", a), ("B", b)):
                    fsutil.atomic_write(stage / "builds" / (label + ".json"), canonical.dumps(build.observation))
                fsutil.atomic_write(stage / (MODULE + ".lean"), goal)
                for m, parts in a.modules.items():
                    leanbridge.write_module_parts(stage / "accepted", m, parts)
                out.parent.mkdir(parents=True, exist_ok=True)
                from ..bridges.publish import publish_into
                files = {p.relative_to(stage).as_posix(): p.read_bytes() for p in stage.rglob("*") if p.is_file()}
                publish_into(out.parent, [], out.name, files)
    except (old.SourceError, base.BridgeInvalid) as exc:
        result.diagnostics.append(Diagnostic(getattr(exc, "code", "INVALID_CANDIDATE"), str(exc)))
    except base.BridgeUnsupported as exc:
        result.diagnostics.append(Diagnostic("UNSUPPORTED_CAPABILITY", str(exc)))
    except VeriSlopError as exc:
        result.diagnostics.extend(exc.diagnostics or [Diagnostic("VERIFIER_FAILURE", str(exc), severity="infrastructure")])
    except InvalidPackage as exc:
        result.diagnostics.append(Diagnostic(exc.code, str(exc)))
    except (OSError, ValueError) as exc:
        result.diagnostics.append(Diagnostic("VERIFIER_FAILURE", str(exc), severity="infrastructure"))
    result.status = status_from(result.diagnostics)
    return result
