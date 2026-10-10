"""Finite Lean-kernel conformance checks for the supervisor's admission decisions.

These tests compare Python outputs to evaluation of the independently written Lean model.
They do not prove the Python program or the byte, isolation and provenance checks correct.
Every model module is compiled, but only the functions exercised here have conformance tests.
"""

from __future__ import annotations

import itertools
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import REPO, TempDir
from verislop import leanbridge, lifecycle
from verislop.backends import admission, registry

ROLES = dict(zip(lifecycle.ROLES, ("guarantee", "assumption", "declaration", "exclusion", "openQuestion")))
KINDS = dict(zip(
    (*lifecycle.DRAFT_CATEGORIES.values(), "non_vacuity"),
    ("entity", "precondition", "postcondition", "invariant", "safetyProperty", "livenessProperty",
     "resourceConstraint", "errorSemantics", "explicitNonGoal", "ambiguity", "nonVacuity")))
MILESTONES = dict(zip(lifecycle.MILESTONES, (
    "interpreted", "formalized", "typechecked", "proved", "implemented", "linked", "tested", "endToEnd")))
ENDPOINTS = {"test_campaign": "testCampaign", "instrumented_runtime": "instrumentedRuntime",
             "restricted_source": "restrictedSource", "proof_bearing_source": "proofBearingSource",
             "extracted_language": "extractedLanguage", "native_binary": "nativeBinary"}
FLAGS = {"omitted": "omitted", "require_tests": "requireTests", "no_tests": "noTests"}
CODES = {"UNSUPPORTED_CAPABILITY": "unsupportedCapability", "CONFIGURATION_INVALID": "configurationInvalid",
         "ORPHAN_CLAIM": "orphanClaim"}


def boolean(value: bool) -> str:
    return "true" if value else "false"


def state(value: str | None) -> str:
    return "none" if value is None else "(some .tested)" if value == "TESTED" else "(some .endToEnd)"


def descriptor(value: dict) -> str:
    return (f"⟨{value['tier']}, .{value['target']}, .{ENDPOINTS[value['endpoint']]}, "
            f"{int(value['backend_version'].split('.')[1])}, {boolean(value['end_to_end_eligible'])}, "
            f"{boolean(value['testing'] == 'supported')}⟩")


def feature(oid: int, *, role: str = "guarantee", kind: str = "postcondition", required: bool = True,
            contract_dsl: bool = True, mentions_symbol: bool = True, call_in_range_bound: bool = False,
            representable_sorts: bool = True, decl_representable: bool = True) -> dict:
    app, _ = lifecycle.applicability({"id": str(oid), "role": role, "kind": kind})["END_TO_END_VERIFIED"]
    return {"id": str(oid), "role": role, "kind": kind, "required": required, "e2e_applicable": app,
            "contract_dsl": contract_dsl, "mentions_symbol": mentions_symbol,
            "call_in_range_bound": call_in_range_bound, "representable_sorts": representable_sorts,
            "decl_representable": decl_representable}


def lean_obligation(f: dict) -> str:
    return "⟨" + ", ".join((f["id"], "." + ROLES[f["role"]], "." + KINDS[f["kind"]],
                             *(boolean(f[k]) for k in ("required", "contract_dsl", "mentions_symbol",
                                                       "call_in_range_bound", "representable_sorts",
                                                       "decl_representable")))) + "⟩"


def lean_list(values) -> str:
    return "[" + ", ".join(values) + "]"


class ClosureModelConformance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.tc = leanbridge.resolve_toolchain()
        cls.model = cls.tmp.path / "model"
        shutil.copytree(REPO / "formal", cls.model)
        for module in ("Lifecycle", "Admission", "ClaimGraph", "Decision", "Projection", "Roots"):
            cls.compile(cls.model / "ClosureModel" / (module + ".lean"), output=True)
        cls.compile(cls.model / "ClosureModel.lean", output=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def compile(cls, path: Path, *, output: bool = False):
        args = [str(cls.tc.lean)]
        if output:
            args += ["-o", str(path.with_suffix(".olean"))]
        result = subprocess.run([*args, str(path)], cwd=cls.model,
                                env={**os.environ, "LEAN_PATH": str(cls.model)},
                                capture_output=True, text=True, timeout=60)
        if result.returncode or "declaration uses `sorry`" in result.stdout:
            raise AssertionError(result.stdout + result.stderr)

    def check(self, name: str, assertions: list[str]):
        path = self.model / (name + ".lean")
        path.write_text("import ClosureModel\nopen ClosureModel\n\n" + "\n".join(assertions) + "\n")
        self.compile(path)

    def test_lifecycle_and_prerequisites_match_model(self):
        checks = []
        for role, kind in itertools.product(ROLES, KINDS):
            actual = lifecycle.applicability({"id": "0", "role": role, "kind": kind})
            for milestone, (applicable, _) in actual.items():
                checks.append(f"example : applicable .{ROLES[role]} .{KINDS[kind]} .{MILESTONES[milestone]} "
                              f"= {boolean(applicable)} := by decide")
        for milestone, prerequisites in lifecycle.PREREQUISITES.items():
            expected = lean_list("." + MILESTONES[m] for m in prerequisites)
            checks.append(f"example : Milestone.prerequisites .{MILESTONES[milestone]} = {expected} := by decide")
        self.check("LifecycleConformance", checks)

    def test_registry_tuple_and_parameter_resolution_match_model(self):
        checks = []
        for tier, target, endpoint, version in itertools.product(range(5), ("python", "vscore"), ENDPOINTS, (1, 2)):
            got = registry.select(tier, target, endpoint, f"0.{version}")
            expected = "none" if got is None else "(some " + descriptor(got) + ")"
            call = f"{tier} .{target} .{ENDPOINTS[endpoint]} {version}"
            checks.append(f"example : select {call} = {expected} := by decide")
            for requested, flag in itertools.product((None, "TESTED", "END_TO_END_VERIFIED"), FLAGS):
                err, got = admission.resolve_params(tier, target, endpoint, f"0.{version}", requested, flag)
                expected = ("(.error ." + CODES[err] + ")" if err else
                            f"(.ok ⟨{descriptor(got['descriptor'])}, {state(got['state'])}, "
                            f"{boolean(got['require_tests'])}⟩)")
                checks.append(f"example : resolveParams {call} {state(requested)} .{FLAGS[flag]} "
                              f"= {expected} := by rfl")
        self.check("RegistryConformance", checks)

    def test_admission_exact_required_coverage_and_unsupported_fragments_match_model(self):
        cases = []
        # Every role/kind/requiredness combination; non-vacuity and optional guarantees stay out.
        for role, kind, required in itertools.product(ROLES, KINDS, (False, True)):
            cases.append([feature(0, role=role, kind=kind, required=required)])
        # Every combination of accepted DSL/symbol/range/sort facts for each required kind.
        for kind, facts in itertools.product(KINDS, itertools.product((False, True), repeat=4)):
            cases.append([feature(0, kind=kind, contract_dsl=facts[0], mentions_symbol=facts[1],
                                  call_in_range_bound=facts[2], representable_sorts=facts[3])])
        # A supported guarantee cannot hide an unrepresentable required declaration.
        for required, representable in itertools.product((False, True), repeat=2):
            cases.append([feature(1), feature(2, role="declaration", kind="entity", required=required,
                                             decl_representable=representable)])
        cases += [[feature(1), feature(2, required=False, contract_dsl=False),
                   feature(3, kind="non_vacuity"), feature(4, role="assumption", kind="precondition")],
                  [feature(3), feature(1), feature(2)], []]
        checks = []
        for i, fs in enumerate(cases):
            os_ = lean_list(lean_obligation(f) for f in fs)
            actual = admission.admit(2, None, "omitted", fs)
            cov = lean_list(admission.covered(fs))
            bad = lean_list(admission.unsupported(fs))
            result = (f"(.admitted {lean_list(actual[2])})" if actual[0] == "admitted" else
                      f"(.rejected .{CODES[actual[1]]} {lean_list(actual[2])})")
            checks += [f"-- case {i}: {fs}", f"example : coveredSet {os_} = {cov} := by decide",
                       f"example : unsupportedSet {os_} = {bad} := by decide",
                       f"example : admit 2 none .omitted {os_} = {result} := by decide"]
        for tier, requested, flag in itertools.product(range(5), (None, "TESTED", "END_TO_END_VERIFIED"), FLAGS):
            actual = admission.admit(tier, requested, flag, [feature(1)])
            expected = (f"(.admitted {lean_list(actual[2])})" if actual[0] == "admitted" else
                        f"(.rejected .{CODES[actual[1]]} {lean_list(actual[2])})")
            checks.append(f"example : admit {tier} {state(requested)} .{FLAGS[flag]} "
                          f"[{lean_obligation(feature(1))}] = {expected} := by decide")
        self.check("AdmissionConformance", checks)


if __name__ == "__main__":
    unittest.main()
