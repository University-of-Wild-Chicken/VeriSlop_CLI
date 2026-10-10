"""Fresh actual-Lean DEVELOPMENT_ONLY equality-refutation fixtures.

No native task inputs, retained answers, production writes, or model calls.
Every positive result executes the existing compiler and kernel tool.
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from verislop import canonical, contract, dsl, formal_frontend as ff, leanbridge, policy, reify, sandbox
from verislop.exprjson import app, const, decl_hash, closure
from verislop.package import Package

SPEC = importlib.util.spec_from_file_location(
    "verislop.contract_refutation_candidate", WORK / "contract_refutation_candidate.py")
cr = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cr
SPEC.loader.exec_module(cr)


def jsonable(obj):
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, bytes):
        return {"sha256": canonical.digest(obj), "bytes": len(obj)}
    if dataclasses.is_dataclass(obj):
        return jsonable(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    return obj


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(obj), sort_keys=True, indent=2) + "\n")


class Evidence:
    def __init__(self, directory):
        self.directory = directory
        self.processes = []
        self.compiles = []
        self.kernels = []
        self.original_run = sandbox.run
        self.original_compile = leanbridge.compile_module
        self.original_kernel = leanbridge.run_kernel_tool
        self.label = "initialization"

    def run(self, argv, cwd, **kwargs):
        result = self.original_run(argv, cwd, **kwargs)
        index = len(self.processes) + 1
        target = self.directory / "processes" / f"{index:05d}"
        target.mkdir(parents=True)
        kind = "kernel" if "--run" in argv else "compiler"
        row = {"id": index, "label": self.label, "kind": kind,
               "requested_argv": argv, "working_directory": str(cwd),
               "requested_options": kwargs, "result": result}
        (target / "stdout.bin").write_bytes(result.stdout)
        (target / "stderr.bin").write_bytes(result.stderr)
        save(target / "process.json", row)
        # All copied files were produced by this fresh generic invocation.
        if kind == "kernel":
            for name in ("request.json", "response.json", "VeriSlopKernel.lean"):
                path = Path(cwd) / name
                if path.is_file():
                    shutil.copyfile(path, target / name)
            stage = Path(cwd) / "stage"
            if stage.is_dir():
                shutil.copytree(stage, target / "stage")
        else:
            for path in Path(cwd).iterdir():
                if path.is_file() and path.name.startswith(leanbridge.MODULE + "."):
                    shutil.copyfile(path, target / path.name)
        self.processes.append(jsonable(row))
        return result

    def compile(self, *args, **kwargs):
        result = self.original_compile(*args, **kwargs)
        index = len(self.compiles) + 1
        row = {"id": index, "label": self.label, "source_sha256": canonical.digest(args[1]),
               "source_bytes": len(args[1]), "result": result}
        save(self.directory / "compiles" / f"{index:05d}.json", row)
        if result.olean is not None:
            target = self.directory / "compiled-artifacts" / f"{index:05d}"
            target.mkdir(parents=True)
            shutil.copyfile(result.olean, target / result.olean.name)
        self.compiles.append(jsonable(row))
        return result

    def kernel(self, *args, **kwargs):
        result = self.original_kernel(*args, **kwargs)
        index = len(self.kernels) + 1
        row = {"id": index, "label": self.label, "request": args[2], "options": kwargs,
               "response": result}
        save(self.directory / "kernels" / f"{index:05d}.json", row)
        self.kernels.append(jsonable(row))
        return result


def records():
    return [{"id": oid, "revision": 1, "kind": kind, "role": role,
             "statement": "Fresh unrelated equality support fixture", "required": True,
             "source_refs": [], "scope": ["generic-equality019"], "dependencies": [],
             "acceptance_criteria": [], "origin": "interpreted", "blocked_by": []}
            for oid, kind, role in (("D1", "entity", "declaration"),
                                    ("O1", "postcondition", "guarantee"))]


def raw_source(variant):
    token_derives = variant in {"enum", "inner", "all", "removed"}
    leaf_derives = variant in {"inner", "all", "removed"}
    parcel_derives = variant in {"all", "removed"}
    deriving = "  deriving DecidableEq\n"
    source = "import Std\nnamespace RefutationEquality019\n"
    source += "inductive Token where | amber | violet\n" + (deriving if token_derives else "")
    source += "structure ZLeaf where\n  token : Token\n  amount : Nat\n" + (deriving if leaf_derives else "")
    source += "structure AParcel where\n  leaf : ZLeaf\n  spare : Option Token\n  history : List ZLeaf\n  outcome : Except Token ZLeaf\n" + (deriving if parcel_derives else "")
    if variant == "removed":
        source += "attribute [-instance] instDecidableEqToken instDecidableEqZLeaf instDecidableEqAParcel\n"
    if variant == "ordinary":
        source += "def unusualEquality : DecidableEq Token := fun a b => by\n  cases a <;> cases b\n  · exact isTrue rfl\n  · exact isFalse (by intro h; cases h)\n  · exact isFalse (by intro h; cases h)\n  · exact isTrue rfl\n"
    if variant == "bad":
        source += "inductive Other where | one | two deriving DecidableEq\n"
        source += "def wrongNominal : DecidableEq Other := inferInstance\n"
        source += "def sorryEquality : DecidableEq Token := by sorry\n"
        source += "noncomputable def choiceEquality : DecidableEq Token := Classical.decEq Token\n"
        source += "unsafe def unsafeEquality : DecidableEq Token := fun _ _ => isTrue (unsafeCast True.intro)\n"
        source += "partial def partialEquality : DecidableEq Token := partialEquality\n"
    if variant == "collision":
        source += "def Token.ofNat (n : Nat) : Token := Token.amber\n"
    source += """def swap (t : Token) : Token :=
  match t with | .amber => .violet | .violet => .amber
def carry (p : AParcel) : AParcel :=
  { p with leaf := { p.leaf with token := swap p.leaf.token } }
theorem wrongToken (t : Token) : swap t = t := by sorry
theorem rightToken (t : Token) : swap (swap t) = t := by cases t <;> rfl
theorem wrongParcel (p : AParcel) : carry p = p := by sorry
theorem rightParcel (p : AParcel) : carry (carry p) = p := by
  cases p with
  | mk leaf spare history outcome =>
    cases leaf with
    | mk token amount => cases token <;> rfl
end RefutationEquality019
"""
    return source.encode()


TOKEN = {"enum": "Token"}
LEAF = {"record": "ZLeaf"}
PARCEL = {"record": "AParcel"}
v = lambda i: {"tag": "var", "index": i}
enum = lambda c: {"tag": "enum", "sort": "Token", "constructor": c}
eq = lambda a, b: {"tag": "eq", "left": a, "right": b}
call = lambda n, x: {"tag": "call", "symbol": n, "args": [x]}
proj = lambda r, f, x: {"tag": "project", "sort": r, "field": f, "record": x}


def structured_source(theorem):
    swap = {"tag": "ite", "condition": {"tag": "bool_eq", "left": v(0), "right": enum("amber")},
            "then": enum("violet"), "else": enum("amber")}
    # Projection syntax is obtained directly from the current generic DSL schema.
    leaf = {"tag": "field", "record": v(0), "field": "leaf"}
    token = {"tag": "field", "record": leaf, "field": "token"}
    carry = {"tag": "record", "sort": "AParcel", "fields": [
        {"tag": "record", "sort": "ZLeaf", "fields": [call("swap", token),
             {"tag": "field", "record": leaf, "field": "amount"}]},
        *[{"tag": "field", "record": v(0), "field": f} for f in ("spare", "history", "outcome")]]}
    formulas = {
        "wrongToken": {"tag": "forall", "sort": TOKEN, "body": eq(call("swap", v(0)), v(0))},
        "rightToken": {"tag": "forall", "sort": TOKEN, "body": eq(call("swap", call("swap", v(0))), v(0))},
        "wrongParcel": {"tag": "forall", "sort": PARCEL, "body": eq(call("carry", v(0)), v(0))},
        "rightParcel": {"tag": "forall", "sort": PARCEL, "body": eq(call("carry", call("carry", v(0))), v(0))}}
    obj = {"encoding": ff.VERSION_V2, "enums": {"Token": {"constructors": ["amber", "violet"]}},
           "records": {"ZLeaf": {"fields": [{"name": "token", "sort": TOKEN}, {"name": "amount", "sort": "Nat"}]},
                       "AParcel": {"fields": [{"name": "leaf", "sort": LEAF},
                            {"name": "spare", "sort": {"option": TOKEN}},
                            {"name": "history", "sort": {"list": LEAF}},
                            {"name": "outcome", "sort": {"result": {"error": TOKEN, "ok": LEAF}}}]}},
           "symbols": {"swap": {"args": [TOKEN], "result": TOKEN, "body": swap},
                       "carry": {"args": [PARCEL], "result": PARCEL, "body": carry}},
           "predicates": {}, "theorems": {n: {"formula": f} for n, f in formulas.items()},
           "obligations": {"D1": {"declarations": [{"kind": "enum", "name": "Token"},
                {"kind": "record", "name": "ZLeaf"}, {"kind": "record", "name": "AParcel"},
                {"kind": "symbol", "name": "swap"}, {"kind": "symbol", "name": "carry"}]},
                "O1": {"theorem": theorem}}, "witness_obligations": {}}
    result = ff.compile_response(canonical.dumps(obj), records(), "equality019.structured")
    return result.source, result.formalization


AMBER = {"str": "amber"}
VIOLET = {"str": "violet"}
LEAF_WIRE = {"dict": {"token": AMBER, "amount": {"int": "1"}}}
PARCEL_WIRE = {"dict": {"leaf": LEAF_WIRE, "spare": {"none": None},
                          "history": {"list": [LEAF_WIRE]},
                          "outcome": {"tuple": [{"str": "ok"}, LEAF_WIRE]}}}


class Harness:
    def __init__(self, output, evidence):
        self.output, self.evidence = output, evidence
        self.tc = leanbridge.resolve_toolchain()
        self.pol = policy.get("strict")
        self.cache = {}
        self.results = []
        self.tmp = tempfile.TemporaryDirectory(prefix="fresh-equality019-development-")
        self.directory = Path(self.tmp.name)
        save(output / "environment.json", {"status": "DEVELOPMENT_ONLY", "toolchain": self.tc.identity(),
             "kernel_tool_hash": leanbridge.kernel_tool_hash(), "policy": self.pol,
             "design_hash": canonical.digest_file(WORK.parent / "tier2-refutation-equality-support-019-design/SPEC.md")})

    def prepare(self, variant, theorem):
        key = (variant, theorem)
        if key in self.cache:
            return self.cache[key]
        if variant == "structured":
            source, form = structured_source(theorem)
        else:
            source = raw_source(variant)
            form = {"schema_version": "0.1", "artifact_kind": "formalization_candidate",
                    "profile_id": "equality019.raw", "lean_toolchain": self.tc.pin,
                    "lean_file": "Contract.lean", "internal_obligations": [],
                    "bindings": [{"obligation": "D1", "declarations": ["RefutationEquality019.Token",
                      "RefutationEquality019.ZLeaf", "RefutationEquality019.AParcel", "RefutationEquality019.swap", "RefutationEquality019.carry"]},
                      {"obligation": "O1", "theorem": "RefutationEquality019." + theorem}]}
        base, _, problems = contract.compose_challenge(source, contract.registry_lean(records(), contract.binding_names(form)))
        assert not problems, problems
        compiled = leanbridge.compile_module(self.tc, base, self.directory / (variant + "-" + theorem),
                                            timeout=self.pol["build_timeout_seconds"], memory_mb=self.pol["memory_mb"],
                                            require_network_isolation=self.pol["require_network_isolation"],
                                            require_filesystem_isolation=self.pol["require_filesystem_isolation"])
        assert compiled.ok, compiled.errors
        exported = leanbridge.run_kernel_tool(self.tc, compiled.olean, {"export": True, "axioms": True}, **cr._kernel_options(self.pol))
        env = contract.Env.from_export(exported, self.pol, "fresh equality019")
        assert not env.diagnostics, env.diagnostics
        analysis = contract.analyze(env, records(), form, self.pol, self.tc.pin, "fresh equality019")
        assert not analysis.diagnostics, analysis.diagnostics
        profile = dsl.Profile.from_json(analysis.profile)
        target = self.output / "fixtures" / (variant + "-" + theorem)
        target.mkdir(parents=True)
        (target / "Source.lean").write_bytes(source)
        (target / "Base.lean").write_bytes(base)
        save(target / "formalization.json", form)
        save(target / "records.json", records())
        save(target / "analysis.json", analysis)
        save(target / "kernel.json", exported)
        result = (source, form, base, env, analysis, profile)
        self.cache[key] = result
        return result

    def check(self, label, variant, theorem, proposals=None, **kwargs):
        source, form, base, env, analysis, profile = self.prepare(variant, theorem)
        pkg = Package(self.output / "packages" / label)
        pkg.ensure()
        result = cr.check(pkg, kwargs.get("source", source), form, records(), kwargs.get("analysis", analysis), proposals=proposals)
        save(self.output / "reports" / (label + ".json"), result)
        for receipt in result["receipts"]:
            assert receipt["refutation_sorry_dependencies"] == 0
            assert receipt["kernel_defeq"] == {"ok": True, "typechecks": True, "defeq": True}
            assert receipt["binding"]["candidate_source_hash"] == canonical.digest(source)
            assert receipt["binding"]["formalization_hash"] == canonical.digest_json(form)
            assert receipt["binding"]["records_hash"] == canonical.digest_json(records())
            assert receipt["binding"]["analysis_hash"] == canonical.digest_json(cr._analysis_identity(analysis))
            assert receipt["binding"]["proposals_hash"] == canonical.digest_json([] if proposals is None else proposals)
            for artifact in receipt["artifacts"].values():
                assert canonical.digest_file(pkg.root / artifact["path"]) == artifact["sha256"]
            proof_export = json.loads((pkg.root / receipt["artifacts"]["kernel_export"]["path"]).read_text())
            proof_env = contract.Env.from_export(proof_export, self.pol, "fresh receipt validation")
            assert not proof_env.diagnostics
            assert all(proof_env.hashes.get(n) == digest for n, digest in env.hashes.items())
            clean, _ = cr._clean_root(proof_env, receipt["lean_symbol"], self.pol)
            assert clean
            assert decl_hash(proof_env.decls[receipt["lean_symbol"]]) == receipt["declaration_hash"]
            assert receipt["kernel_proof_hash"] == canonical.digest_json({
                "module": receipt["artifacts"]["compiled_module"]["sha256"], "declaration": receipt["declaration_hash"],
                "proposition": receipt["proposition_hash"], "kernel_export": receipt["artifacts"]["kernel_export"]["sha256"],
                "kernel_tool": receipt["kernel_tool_hash"], "toolchain": receipt["toolchain"]})
            stripped = dict(receipt)
            del stripped["receipt_hash"]
            assert canonical.digest_json(stripped) == receipt["receipt_hash"]
            appended = (pkg.root / receipt["artifacts"]["source"]["path"]).read_text()[len(base.decode()):]
            expected_prelude = cr._derivations(profile, env, namespace=receipt["lean_symbol"].rsplit(".", 1)[0])
            assert expected_prelude in appended
            for carrier in [e["lean_decl"] for e in profile.enums.values()] + [r["lean_decl"] for r in profile.records.values()]:
                matches = []
                for n, row in env.decls.items():
                    if row.get("type") == app(const("DecidableEq", [1]), const(carrier)):
                        try:
                            reify._enum_equality_declaration(n, carrier, env.decls, env.hashes)
                            matches.append(n)
                        except reify.Unsupported:
                            pass
                if matches:
                    assert "deriving instance _root_.DecidableEq for " + cr._qualified(carrier) not in appended
                    assert cr._qualified(sorted(matches)[0]) in appended
            if variant == "bad":
                dependencies = closure({receipt["lean_symbol"]}, proof_env.decls)
                assert not any(n in dependencies for n in ["RefutationEquality019." + k for k in
                    ("sorryEquality", "choiceEquality", "unsafeEquality", "partialEquality", "wrongNominal")])
        return result

    def test(self, label, function):
        self.evidence.label = label
        started = time.monotonic()
        before = len(self.evidence.processes)
        try:
            function()
            result = {"label": label, "status": "PASS"}
        except Exception as error:
            result = {"label": label, "status": "FAIL", "error": repr(error), "traceback": traceback.format_exc()}
        result.update({"elapsed_seconds": time.monotonic() - started,
                       "actual_processes": len(self.evidence.processes) - before})
        self.results.append(result)
        save(self.output / "case-results" / (label + ".json"), result)
        print(json.dumps(result), flush=True)


def assert_status(result, status, receipt_status=None):
    assert result["status"] == status, result
    if receipt_status is None:
        assert not result["receipts"], result
    else:
        assert any(r["status"] == receipt_status for r in result["receipts"]), result


def main():
    run = WORK / "runs" / os.environ.get("EQUALITY019_RUN", "run001")
    run.mkdir(parents=True, exist_ok=False)
    evidence = Evidence(run)
    harness = Harness(run, evidence)
    with patch.object(sandbox, "run", side_effect=evidence.run), patch.object(leanbridge, "compile_module", side_effect=evidence.compile), patch.object(leanbridge, "run_kernel_tool", side_effect=evidence.kernel):
        for variant in ("none", "enum", "inner", "all", "removed", "ordinary", "structured"):
            for theorem, inp in (("wrongToken", AMBER), ("wrongParcel", PARCEL_WIRE)):
                label = variant + "-" + theorem
                harness.test(label, lambda variant=variant, theorem=theorem, inp=inp, label=label:
                    assert_status(harness.check(label, variant, theorem, [{"obligation_id": "O1", "inputs": [inp]}]), "REFUTED", "REFUTED"))
        for variant in ("none", "all", "structured"):
            for theorem, inp in (("rightToken", AMBER), ("rightParcel", PARCEL_WIRE)):
                label = variant + "-" + theorem
                harness.test(label, lambda variant=variant, theorem=theorem, inp=inp, label=label:
                    assert_status(harness.check(label, variant, theorem, [{"obligation_id": "O1", "inputs": [inp]}]), "UNKNOWN"))

        def direct_false(theorem, inp):
            source, form, base, env, analysis, profile = harness.prepare("all", theorem)
            formula = analysis.statements["O1"]["formula_package"]["formula"]
            sorts, _ = cr._universal(formula)
            from verislop.targets import python_target as wire
            values = [wire.decode_result(inp, sorts[0], profile)]
            expr = app(const("Not"), cr._closed_formula(formula, values, sorts, profile))
            pkg = Package(run / "packages" / ("direct-false-" + theorem)); pkg.ensure()
            result = cr._proof(pkg, base, expr, {"fixture": "false closed proposition"}, profile, harness.tc, harness.pol, env)
            save(run / "reports" / ("direct-false-" + theorem + ".json"), result)
            assert not result["ok"], result
        for theorem, inp in (("rightToken", AMBER), ("rightParcel", PARCEL_WIRE)):
            harness.test("direct-false-" + theorem, lambda theorem=theorem, inp=inp: direct_false(theorem, inp))

        def ordering_and_metadata():
            _, _, _, env, analysis, profile = harness.prepare("none", "wrongParcel")
            prelude = cr._derivations(profile, env, namespace="FreshOrdering019")
            assert prelude.index(cr._qualified("RefutationEquality019.Token")) < prelude.index(cr._qualified("RefutationEquality019.ZLeaf")) < prelude.index(cr._qualified("RefutationEquality019.AParcel"))
            _, _, _, env, analysis, profile = harness.prepare("all", "wrongParcel")
            assert "decidable_eq" not in profile.enums["Token"], profile.raw
            prelude = cr._derivations(profile, env, namespace="FreshOrdering019")
            assert "deriving instance" not in prelude, prelude
            changed = copy.deepcopy(profile.raw)
            changed["enums"]["Token"]["decidable_eq"] = {"lean_decl": "RefutationEquality019.fake", "decl_hash": canonical.digest(b"stale")}
            assert prelude == cr._derivations(dsl.Profile.from_json(changed), env, namespace="FreshOrdering019")
        harness.test("ordering-full-env-and-stale-metadata", ordering_and_metadata)

        harness.test("bad-equality-never-reused", lambda: assert_status(harness.check("bad-equality-never-reused", "bad", "wrongToken", [{"obligation_id": "O1", "inputs": [AMBER]}]), "REFUTED", "REFUTED"))
        harness.test("enum-helper-name-collision", lambda: assert_status(harness.check("enum-helper-name-collision", "collision", "wrongToken", [{"obligation_id": "O1", "inputs": [AMBER]}]), "UNKNOWN"))

        def alias_collision():
            _, _, base, env, analysis, profile = harness.prepare("all", "wrongToken")
            expr = app(const("Not"), app(const("Eq", [1]), const("RefutationEquality019.Token"), const("RefutationEquality019.Token.amber"), const("RefutationEquality019.Token.violet")))
            binding = {"fixture": "generated alias collision"}
            ns = "VeriSlopRefutation_" + canonical.digest_json({"binding": binding, "proposition": expr}).split(":")[1][:24]
            modified = copy.deepcopy(env)
            modified.decls[ns + "._vr_eq_0"] = {"name": [ns, "_vr_eq_0"]}
            before = len(evidence.processes)
            pkg = Package(run / "packages/alias-collision"); pkg.ensure()
            result = cr._proof(pkg, base, expr, binding, profile, harness.tc, harness.pol, modified)
            assert not result["ok"] and result["reason"] == "generated equality alias name already exists", result
            assert len(evidence.processes) == before
            save(run / "reports/alias-collision.json", result)
        harness.test("generated-alias-name-collision-synthetic-env", alias_collision)

        def probe(symbol, inp, expected, mismatch):
            label = f"reference-{symbol}-{'mismatch' if mismatch else 'match'}"
            result = harness.check(label, "structured", "rightParcel" if symbol == "carry" else "rightToken",
                [{"obligation_id": "O1", "entry_symbol": symbol, "exact_clause_id": "fresh-authored-clause", "inputs": [inp], "expected": expected}])
            assert_status(result, "SEMANTIC_MISMATCH" if mismatch else "UNKNOWN", "SEMANTIC_MISMATCH" if mismatch else "REFERENCE_MATCH")
            for receipt in result["receipts"]:
                assert receipt["expectation_authority"] == "untrusted_critic_annotation"
                assert not receipt["guarantee_refuted"] and not receipt["natural_language_clause_verified"]
        carried = copy.deepcopy(PARCEL_WIRE); carried["dict"]["leaf"]["dict"]["token"] = VIOLET
        for symbol, inp, good, bad in (("swap", AMBER, VIOLET, AMBER), ("carry", PARCEL_WIRE, carried, PARCEL_WIRE)):
            for mismatch, expected in ((False, good), (True, bad)):
                harness.test(f"reference-{symbol}-{'mismatch' if mismatch else 'match'}", lambda symbol=symbol, inp=inp, expected=expected, mismatch=mismatch: probe(symbol, inp, expected, mismatch))

        for kind in ("defeq", "base_hash", "safety", "levels", "unresolved", "sorry", "axiom"):
            def tamper(kind=kind):
                original = evidence.kernel
                def changed(*args, **kwargs):
                    result = original(*args, **kwargs)
                    if args[2].get("defeq", [{}])[0].get("id") == "closed_check":
                        result = copy.deepcopy(result)
                        if kind == "defeq":
                            result["defeq"][0]["result"]["defeq"] = False
                        else:
                            for declaration in result["constants"]:
                                name = ".".join(declaration["name"])
                                if kind == "base_hash" and name == "VeriSlopAST.swap":
                                    declaration["value"] = const("Bool.false")
                                if name.endswith(".closed_check"):
                                    if kind == "safety": declaration["safety"] = "unsafe"
                                    if kind == "levels": declaration["level_params"] = [["injected"]]
                                    if kind == "unresolved": declaration["unresolved_constants"] = [["missing"]]
                                    if kind in ("sorry", "axiom"): declaration["axioms"] = [["sorryAx" if kind == "sorry" else "forbiddenFixtureAxiom"]]
                        save(run / "tampered-exports" / f"{kind}-{len(evidence.kernels):05d}.json", result)
                    return result
                with patch.object(leanbridge, "run_kernel_tool", side_effect=changed):
                    result = harness.check("tamper-" + kind, "structured", "wrongToken", [{"obligation_id": "O1", "inputs": [AMBER]}])
                assert_status(result, "UNKNOWN")
            harness.test("tamper-" + kind, tamper)

        def binding_and_wires():
            source, _, _, _, analysis, _ = harness.prepare("structured", "rightToken")
            changed = source.replace(b"import Std", b"import Std\n-- changed source identity", 1)
            assert_status(harness.check("changed-source", "structured", "rightToken", [], source=changed), "UNKNOWN")
            forged = copy.deepcopy(analysis)
            forged.statements["O1"]["formula_package"]["formula"] = {"tag": "false"}
            assert_status(harness.check("forged-analysis", "structured", "rightToken", [], analysis=forged), "UNKNOWN")
            invalid = [
                {"obligation_id": "O1", "inputs": [{"str": "missing"}]},
                {"obligation_id": "O1", "inputs": [AMBER], "extra": True},
                {"obligation_id": "O1", "inputs": [AMBER], "entry_symbol": "unadmitted", "exact_clause_id": "fresh", "expected": AMBER},
                {"obligation_id": "O1", "inputs": [AMBER], "entry_symbol": "swap", "exact_clause_id": "", "expected": AMBER}]
            result = harness.check("invalid-wires", "structured", "rightToken", invalid)
            assert_status(result, "UNKNOWN")
            assert sum(d.get("kind") == "INVALID_PROPOSAL" for d in result["diagnostics"]) == len(invalid), result
        harness.test("source-analysis-wire-binding-negatives", binding_and_wires)

    results = {"format": "verislop.equality-support-019-candidate-results/1", "status": "DEVELOPMENT_ONLY",
               "qualification_authority": False, "root003_reusable": False, "models_called": 0,
               "native_tasks_read": 0, "cases": harness.results,
               "passed": sum(r["status"] == "PASS" for r in harness.results),
               "failed": sum(r["status"] == "FAIL" for r in harness.results),
               "actual_processes": len(evidence.processes), "actual_compiler_calls": len(evidence.compiles),
               "actual_kernel_calls": len(evidence.kernels),
               "process_returncodes": {str(k): sum(p["result"]["returncode"] == k for p in evidence.processes) for k in sorted({p["result"]["returncode"] for p in evidence.processes})},
               "timed_out_processes": sum(p["result"]["timed_out"] for p in evidence.processes),
               "actual_wall_seconds": sum(p["result"]["wall_seconds"] for p in evidence.processes)}
    save(run / "results.json", results)
    harness.tmp.cleanup()
    print(json.dumps({k: value for k, value in results.items() if k != "cases"}), flush=True)
    return 0 if not results["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
