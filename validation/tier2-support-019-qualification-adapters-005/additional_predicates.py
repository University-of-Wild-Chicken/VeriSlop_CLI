"""Finite additional raw artifact predicates; never run a model/compiler/viewer.

The runtime and additional witness contracts were registered before this source.
The independent reader implements its own checks rather than importing this file.
"""
import ast
import base64
import copy
import hashlib
import json
import math
from pathlib import Path
import re

ADDITIONAL_GROUPS = {
    "Q019-01": "equality_original", "Q019-02": "equality_private",
    "Q019-03": "carrier_pure", "Q019-04": "carrier_full",
    "Q019-05": "carrier_faults", "Q019-06": "carrier_empty",
    "Q019-07": "fresh_author", "Q019-08": "authority_boundary",
    "Q019-09": "whole_audit",
}
UNAVAILABLE = {"hidden_native_outer_http_mcp_envelope": "UNAVAILABLE",
               "separated_stdout": "UNAVAILABLE", "separated_stderr": "UNAVAILABLE", "pid": "UNAVAILABLE"}
BINDING_DIAGNOSTIC = [{"message": "source/form/records do not match the supplied kernel-derived analysis"}]


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def transport_parse(raw):
    """Parse retained tool transport JSON; formal identities use canonical separately."""
    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, "PURE_TRANSPORT_DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    def finite_float(value):
        number = float(value)
        require(math.isfinite(number), "PURE_TRANSPORT_NONFINITE_JSON_NUMBER")
        return number
    def invalid_constant(value):
        raise ValueError("PURE_TRANSPORT_NONFINITE_JSON_CONSTANT:" + value)
    return json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=unique,
                      parse_float=finite_float, parse_constant=invalid_constant)


def transport_wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8", "strict")


class AdditionalPredicates:
    def additional_operations(self):
        return [(name, getattr(self, name)) for name in ADDITIONAL_GROUPS.values()]

    def additional_ref(self, identity):
        root = self.gate.parents[1]
        name = identity["path"]
        require(any(name.startswith(prefix.rstrip("/") + "/") for prefix in self.config["fresh_evidence_prefixes"]),
                "ADDITIONAL_EVIDENCE_NOT_FRESH:" + name)
        path = self.path(name)
        raw = self.read(path, identity["sha256"])
        if not path.is_relative_to(self.gate):
            require(self.hashes.get(name) == identity["sha256"], "EXTERNAL_FRESH_FIXTURE_NOT_EXACT_FROZEN_INPUT")
        if "byte_count" in identity:
            require(type(identity["byte_count"]) is int and len(raw) == identity["byte_count"], "ADDITIONAL_SIZE_MISMATCH")
        return raw

    def additional_doc(self, identity):
        self.additional_ref(identity)
        return self.document(self.path(identity["path"]))

    def additional_index(self, kind):
        path = self.path(self.config["additional_evidence_paths"][kind])
        raw = self.read(path, self.index_hashes[kind])
        require(any(path.relative_to(self.gate.parents[1]).as_posix().startswith(prefix.rstrip("/") + "/")
                    for prefix in self.config["fresh_evidence_prefixes"]), "ADDITIONAL_INDEX_NOT_FRESH")
        index = self.document(path)
        require(index["source_root"] == self.freeze["source_root"] and
                index["input_root"] == self.canonical.digest_json(self.hashes), "ADDITIONAL_INDEX_STALE")
        if "closure_id" in index:
            require(index["closure_id"] == self.spec["closure_id"], "ADDITIONAL_CLOSURE_STALE")
        return index

    def witness(self, case, role):
        require(role in case["witness_refs"], "MISSING_REGISTERED_CASE_WITNESS:" + case["label"] + ":" + role)
        identity = case["witness_refs"][role]
        raw = self.additional_ref(identity)
        value = raw if identity.get("encoding") == "raw" else self.additional_doc(identity)
        if "select" in identity:
            require(isinstance(value, dict) and isinstance(identity["select"], list) and
                    all(isinstance(key, str) and key in value for key in identity["select"]), "WITNESS_SELECTED_IDENTITY_UNBOUND")
            value = {key: value[key] for key in identity["select"]}
        return value

    def query(self, case, selector):
        value = self.witness(case, selector["role"])
        for component in selector.get("path", []):
            require(type(component) in (str, int), "WITNESS_QUERY_NOT_LITERAL")
            value = value[component]
        return value

    def predicates(self, case, contract):
        for predicate in contract["predicates"]:
            left = self.query(case, predicate["left"])
            right = self.query(case, predicate["right"]) if "right" in predicate else predicate.get("value")
            op = predicate["op"]
            if op == "eq": accepted = type(left) is type(right) and left == right
            elif op == "ne": accepted = type(left) is not type(right) or left != right
            elif op == "length": accepted = len(left) == right
            elif op == "seteq": accepted = sorted(left) == sorted(right) and len(left) == len(set(left))
            elif op == "contains": accepted = right in left
            elif op == "empty": accepted = left == [] or left == {} or left == ""
            elif op == "positive": accepted = type(left) is int and left > 0
            elif op == "positive_length": accepted = len(left) > 0
            elif op == "count_kind": accepted = sum(row.get("kind") == right["kind"] for row in left) == right["count"]
            elif op == "any_field_eq": accepted = any(row.get(right["field"]) == right["value"] for row in left)
            else: raise ValueError("UNREGISTERED_WITNESS_PREDICATE")
            require(accepted, "RAW_WITNESS_PREDICATE_FAILED:" + case["label"] + ":" + op)

    def equality_observations(self):
        if hasattr(self, "_equality"):
            for name, digest in self._equality[0]["files"].items():
                self.read(self.path(name), digest)
            return self._equality
        index = self.additional_index("equality")
        require(index["format"] == "verislop.support019-equality-observations/1" and index["status"] == "OBSERVED" and
                index["models_called"] == 0 and index["task_inputs"] is False and index["qualification_authority"] is False,
                "EQUALITY_REAL_PRODUCER_SCHEMA_OR_SCOPE")
        installed = self.registered(self.path("verislop/contract_refutation.py"))
        require(index["installed_source_sha256"] == sha(self.read(installed)) ==
                "sha256:e539b2c7ab0c6aa2295dad45dc361481240106c678cc0aefbe08eeff6e7b6828", "EQUALITY_INSTALLED_SOURCE_CHANGED")
        files = index["files"]
        require(files and all(name.startswith(self.gate.relative_to(self.gate.parents[1]).as_posix() + "/equality/")
                              for name in files), "EQUALITY_OUTPUT_MAP_NOT_OWN_CURRENT_ROOT")
        for name, digest in files.items():
            self.read(self.path(name), digest)
        current_files = {path.relative_to(self.gate.parents[1]).as_posix() for path in
                         (self.gate / "equality").rglob("*") if path.is_file()}
        require(current_files == set(files) | {self.config["additional_evidence_paths"]["equality"]},
                "EQUALITY_ACTUAL_OUTPUT_TREE_OMITTED_OR_AMENDED")
        names = ("original-main", "original-additional", "private-binding")
        require(list(index["reports"]) == list(names) or set(index["reports"]) == set(names), "EQUALITY_THREE_REPORTS_MISSING")
        require(len(index["processes"]) == 3, "EQUALITY_THREE_ACTUAL_PROCESSES_MISSING")
        previous = self.freeze["created_at_utc"]
        cases, process_rows, kernel_rows, compile_rows = {}, [], [], []
        for label, receipt in zip(names, index["processes"]):
            expected = self.config["equality_processes"][label]
            require(receipt["argv"] == expected["argv"] and receipt["cwd"] == str(self.gate.parents[1]) and
                    type(receipt["pid"]) is int and receipt["pid"] > 0 and type(receipt["returncode"]) is int and
                    receipt["returncode"] == 0 and receipt["timed_out"] is False and receipt["timeout_seconds"] is None and
                    receipt["source_root"] == self.freeze["source_root"] and receipt["input_root"] == self.canonical.digest_json(self.hashes)
                    and previous <= receipt["started_utc"] <= receipt["completed_utc"], "EQUALITY_CHILD_PROCESS_NOT_CURRENT_SUCCESS")
            previous = receipt["completed_utc"]
            for stream in ("stdout", "stderr"):
                self.additional_ref(receipt[stream])
            result = self.additional_doc(index["reports"][label])
            require(result["failed"] == 0 and result["models_called"] == 0 and
                    result["passed"] == len(result["cases"]) and all(c["status"] == "PASS" for c in result["cases"]),
                    "EQUALITY_CASE_EXECUTION_FAILED_OR_FILTERED")
            for case in result["cases"]:
                require(case["label"] not in cases, "DUPLICATE_EQUALITY_LABEL")
                cases[case["label"]] = dict(case, run_id=label)
            for name in files:
                if name.startswith(expected["output_directory"].rstrip("/") + "/processes/") and name.endswith("/process.json"):
                    row = self.document(self.path(name), files[name])
                    rawdir = self.path(name).parent
                    require(type(row["result"]["returncode"]) is int and row["result"]["timed_out"] is False,
                            "EQUALITY_LEAN_PROCESS_UNRESOLVED")
                    for stream in ("stdout", "stderr"):
                        raw = self.read(rawdir / (stream + ".bin"))
                        require(sha(raw) == row["result"][stream]["sha256"] and
                                len(raw) == row["result"][stream]["bytes"], "EQUALITY_RAW_LEAN_PROCESS_BYTES_MISMATCH")
                    process_rows.append(row)
                    if row["kind"] == "kernel":
                        response = self.document(rawdir / "response.json")
                        normalized = copy.deepcopy(response)
                        for module in normalized.get("import", {}).get("modules", []):
                            if module.get("name") == [self.leanbridge.MODULE]:
                                module["olean"] = "<staged candidate module>"
                        kernel_rows.append({"label": row["label"], "response": normalized,
                                            "request": self.document(rawdir / "request.json"),
                                            "process": row, "directory": rawdir})
                elif name.startswith(expected["output_directory"].rstrip("/") + "/compiles/") and name.endswith(".json"):
                    compile_rows.append((self.document(self.path(name), files[name]), self.path(name).parent.parent))
        controls = self.document(self.path(self.config["control_registration"]))
        required = controls["equality_original44"] + controls["equality_new11"]
        require(set(cases) == set(required) and len(cases) == 55 and process_rows and kernel_rows, "EQUALITY_44_PLUS11_FLOOR_OR_RAW_PROCESSES_MISSING")
        require(set(self.config["equality_case_contracts"]) == set(required), "EQUALITY_FINITE_CASE_CONTRACT_OMISSION")
        self._equality_compiles = compile_rows
        self._equality = index, cases, process_rows, kernel_rows
        return self._equality

    def equality_case(self, label):
        index, executed, processes, kernels = self.equality_observations()
        contract = self.config["equality_case_contracts"][label]
        case = dict(contract["witness_case"], label=label, run_id=executed[label]["run_id"])
        if "witness_paths" in case:
            def actual_identity(row):
                if isinstance(row, str): row = {"path": row}
                require(row["path"] in index["files"], "EQUALITY_REGISTERED_FUTURE_OUTPUT_MISSING:" + row["path"])
                return dict(row, sha256=index["files"][row["path"]])
            case["witness_refs"] = {role: actual_identity(row) for role, row in case["witness_paths"].items()}
            case["result_ref"] = actual_identity(case["result_path"])
        require(set(contract["required_witness_roles"]).issubset(case["witness_refs"]), "EQUALITY_REQUIRED_WITNESS_OMISSION")
        require(index["files"].get(case["result_ref"]["path"]) == case["result_ref"]["sha256"], "EQUALITY_RESULT_NOT_ACTUAL_PRODUCER_OUTPUT")
        for identity in case["witness_refs"].values():
            require(index["files"].get(identity["path"]) == identity["sha256"], "EQUALITY_WITNESS_NOT_AUTHENTICATED_BY_ACTUAL_PRODUCER")
        result = self.additional_doc(case["result_ref"])
        if contract["expected_status"] is not None:
            require(result["status"] == contract["expected_status"], "EQUALITY_SEMANTIC_DISPOSITION_MISMATCH:" + label)
        if "report_hash" in result:
            stripped = dict(result); stripped.pop("report_hash")
            require(self.canonical.digest_json(stripped) == result["report_hash"], "EQUALITY_SEMANTIC_REPORT_HASH_CHANGED")
        if "source" in case["witness_refs"]:
            require(result["candidate_source_hash"] == sha(self.additional_ref(case["witness_refs"]["source"])) and
                    result["formalization_hash"] == self.canonical.digest_json(self.witness(case, "formalization")) and
                    result["records_hash"] == self.canonical.digest_json(self.witness(case, "records")) and
                    result["analysis_hash"] == self.canonical.digest_json(self.witness(case, "analysis_identity")) and
                    result["proposals_hash"] == self.canonical.digest_json(self.witness(case, "proposals")), "EQUALITY_EXACT_SUPPLIED_INPUTS_NOT_BOUND")
        self.predicates(case, contract)
        if "required_structural_control" in contract:
            self.equality_structural_control(case, contract, result, kernels)
        if contract["require_actual_processes"]:
            require(any(row["label"] == label for row in processes), "EQUALITY_CASE_HAS_NO_ACTUAL_LEAN_PROCESS")
        if "receipts" in result:
            if contract["expected_receipt_status"] is None:
                require(result["receipts"] == [], "EQUALITY_NEGATIVE_CREATED_RECEIPT")
            else:
                require(result["receipts"] and all(row["status"] == contract["expected_receipt_status"] for row in result["receipts"]),
                        "EQUALITY_RECEIPT_DISPOSITION_MISMATCH")
                self.equality_receipts(case, result, kernels)
        return case, result

    def equality_structural_control(self, case, contract, result, kernels):
        kind = contract["required_structural_control"]
        if kind == "ordered-carrier-prelude-ledger":
            ledger = self.witness(case, "result")
            names = ["_root_.«RefutationEquality019».«" + name + "»" for name in ("Token", "ZLeaf", "AParcel")]
            prelude = ledger["prelude_none"]
            require(prelude.index(names[0]) < prelude.index(names[1]) < prelude.index(names[2]) and
                    "deriving instance" not in ledger["prelude_all"] and
                    ledger["prelude_all"] == ledger["prelude_before_stale_metadata"] == ledger["prelude_after_stale_metadata"] and
                    "decidable_eq" not in ledger["profile_before"]["enums"]["Token"], "EQUALITY_ORDERING_OR_STALE_METADATA_CONTROL")
            altered = copy.deepcopy(ledger["profile_after"]); altered["enums"]["Token"].pop("decidable_eq")
            require(altered == ledger["profile_before"], "EQUALITY_STALE_METADATA_CHANGED_SEMANTICS")
            return
        ledger = self.witness(case, "structural_ledger")
        from verislop import contract as env_contract
        from verislop.exprjson import app, const
        baseline = ledger["baseline_export"]
        require(any(row["response"] == baseline for row in kernels), "EQUALITY_SYNTHETIC_BASELINE_NOT_ACTUAL")
        env = env_contract.Env.from_export(baseline, self.policy.get("strict"), "support019 synthetic control")
        require(not env.diagnostics, "EQUALITY_SYNTHETIC_BASELINE_REJECTED")
        if kind == "collision-environment-ledger":
            namespace = "VeriSlopRefutation_" + self.canonical.digest_json({"binding": ledger["binding"], "proposition": ledger["expr"]}).split(":")[1][:24]
            suffix = ".closed_check" if case["label"].startswith("existing-root") else "._vr_eq_0"
            require(ledger["generated_name"] == namespace + suffix and ledger["generated_name"] not in env.decls and
                    ledger["modified_declarations"] == dict(env.decls, **{ledger["generated_name"]:{"name":[namespace,suffix[1:]]}}) and
                    ledger["process_ids_before"] == ledger["process_ids_after"], "EQUALITY_COLLISION_ENVIRONMENT_OR_PROCESS_CONTROL")
        elif kind == "stale-equality-environment-ledger":
            name = ledger["equality_name"]
            require(ledger["hashes_before"] == env.hashes and name in env.decls and
                    env.decls[name]["type"] == app(const("DecidableEq", [1]), const("RefutationEquality019.Token")) and
                    ledger["hashes_after"] == dict(env.hashes, **{name:sha(ledger["stale_bytes"].encode("utf-8"))}),
                    "EQUALITY_STALE_CLOSURE_HASH_NOT_DISCRIMINATING")
            from verislop import dsl, contract_refutation
            modified = copy.deepcopy(env); modified.hashes = ledger["hashes_after"]
            require(contract_refutation._derivations(dsl.Profile.from_json(ledger["profile"]), modified, namespace="FreshHashNegative019") == ledger["prelude"],
                    "EQUALITY_STALE_PRELUDE_NOT_RECOMPUTED")
        elif kind == "direct-false-proof-ledger":
            require(ledger["binding"] == {"fixture":"false closed proposition"} and result["ok"] is False and
                    result["reason"] == "closed proof did not elaborate" and
                    len(ledger["process_ids_after"]) > len(ledger["process_ids_before"]), "EQUALITY_FALSE_PROOF_NOT_ACTUALLY_ATTEMPTED")
            failed = [row for row, _ in self._equality_compiles if row["label"] == case["label"] and row["result"]["ok"] is False]
            require(failed and any(type(row["result"]["process_evidence"]["returncode"]) is int and
                    row["result"]["process_evidence"]["returncode"] != 0 and row["result"]["process_evidence"]["timed_out"] is False and
                    row["source_sha256"] == row["result"]["process_evidence"]["input"]["module_source_sha256"] for row in failed),
                    "EQUALITY_FALSE_PROOF_ACTUAL_COMPILER_FAILURE_MISSING")
        else:
            raise ValueError("UNREGISTERED_STRUCTURAL_EQUALITY_CONTROL")

    def equality_receipts(self, case, result, actual_kernels):
        from verislop import contract, exprjson
        from verislop.exprjson import closure, decl_hash, parse_name
        source = self.additional_ref(case["witness_refs"]["source"])
        require(result["candidate_source_hash"] == sha(source), "EQUALITY_EXACT_SOURCE_BYTES_NOT_BOUND")
        base = contract.Env.from_export(self.witness(case, "baseline_export"), self.policy.get("strict"), "support019 actual equality base")
        require(not base.diagnostics, "EQUALITY_BASE_EXPORT_REJECTED")
        for receipt in result["receipts"]:
            package = self.gate.parents[1] / case["package_root"]
            binding = receipt["binding"]
            analysis = self.witness(case, "analysis")
            identity = {key: analysis[key] for key in ("profile", "statements", "registry", "defeq_requests")}
            require(binding["candidate_source_hash"] == sha(source) and
                    binding["formalization_hash"] == self.canonical.digest_json(self.witness(case, "formalization")) and
                    binding["records_hash"] == self.canonical.digest_json(self.witness(case, "records")) and
                    binding["analysis_hash"] == self.canonical.digest_json(identity) and
                    binding["proposals_hash"] == self.canonical.digest_json(self.witness(case, "proposals")), "EQUALITY_RECEIPT_INPUT_BINDING")
            for artifact in receipt["artifacts"].values():
                self.read(self.path(artifact["path"], package), artifact["sha256"])
            exported = self.document(self.path(receipt["artifacts"]["kernel_export"]["path"], package))
            matches = [row for row in actual_kernels if row["response"] == exported and
                       row["process"]["result"]["returncode"] == 0]
            require(matches, "EQUALITY_PROOF_EXPORT_NOT_ACTUAL_KERNEL_RESULT")
            artifact_source = self.read(self.path(receipt["artifacts"]["source"]["path"], package), receipt["artifacts"]["source"]["sha256"])
            module_raw = self.read(self.path(receipt["artifacts"]["compiled_module"]["path"], package), receipt["artifacts"]["compiled_module"]["sha256"])
            connected = []
            for row, directory in self._equality_compiles:
                if row["source_sha256"] != sha(artifact_source) or row["result"]["ok"] is not True:
                    continue
                proc = self.compile_process(row["result"]["process_evidence"], artifact_source, self.leanbridge.MODULE,
                    timeout_max=self.policy.get("strict")["build_timeout_seconds"], memory_mb=self.policy.get("strict")["memory_mb"])
                require(proc["returncode"] == 0 and proc["timed_out"] is False, "EQUALITY_PROOF_COMPILER_FAILED")
                module_path = directory / "compiled-artifacts" / ("%05d" % row["id"]) / Path(row["result"]["olean"]).name
                if self.read(module_path) == module_raw:
                    connected.append(row)
            require(connected, "EQUALITY_PROOF_MODULE_SOURCE_COMPILE_CONNECTION_MISSING")
            for kernel in matches:
                request = kernel["request"]
                require(request["module"] == self.leanbridge.MODULE and request["export"] is True and request["axioms"] is True
                        and len(request["defeq"]) == 1 and request["defeq"][0]["id"] == "closed_check" and
                        self.canonical.digest_json(request["defeq"][0]["expr"]) == receipt["proposition_hash"] and
                        request["defeq"][0]["theorem"] == parse_name(receipt["lean_symbol"]), "EQUALITY_PROPOSITION_NOT_ACTUAL_REQUEST")
                if module_raw.startswith(self.leanbridge.MODULE_BUNDLE_MAGIC):
                    bundle = self.canonical.loads(module_raw[len(self.leanbridge.MODULE_BUNDLE_MAGIC):])
                    require(bundle["format"] == "verislop.lean-module/1" and bundle["module"] == self.leanbridge.MODULE and
                            [part["name"] for part in bundle["files"]] == list(self.leanbridge.MODULE_PARTS), "EQUALITY_MODULE_BUNDLE_SCHEMA")
                    for part in bundle["files"]:
                        decoded = base64.b64decode(part["content_b64"], validate=True)
                        require(sha(decoded) == part["sha256"] and self.read(kernel["directory"] / "stage" / part["name"]) == decoded,
                                "EQUALITY_KERNEL_STAGE_NOT_RECEIPT_MODULE")
                else:
                    require(self.read(kernel["directory"] / "stage" / self.leanbridge.MODULE_PARTS[0]) == module_raw,
                            "EQUALITY_KERNEL_STAGE_NOT_RECEIPT_MODULE")
            env = contract.Env.from_export(exported, self.policy.get("strict"), "support019 actual equality proof")
            require(not env.diagnostics and all(env.hashes.get(name) == value for name, value in base.hashes.items()), "EQUALITY_BASE_DECLARATION_MUTATION")
            root = receipt["lean_symbol"]
            declaration = env.decls[root]
            deps = closure({root}, env.decls)
            require(declaration["kind"] == "theorem" and declaration["safety"] == "safe" and
                    declaration["level_params"] == [] and declaration["unresolved_constants"] == [] and
                    all(env.decls[name].get("safety") == "safe" and not env.decls[name].get("unresolved_constants") for name in deps) and
                    all(self.policy.classify_axiom(name, self.policy.get("strict")) == "allowed" for name in env.axioms(root)) and
                    "sorryAx" not in env.axioms(root) and receipt["refutation_sorry_dependencies"] == 0,
                    "EQUALITY_PROOF_CLOSURE_NOT_CLEAN")
            require(len(exported["defeq"]) == 1 and exported["defeq"][0]["id"] == "closed_check" and
                    exported["defeq"][0]["result"] == receipt["kernel_defeq"] == {"ok": True, "typechecks": True, "defeq": True} and
                    receipt["declaration_hash"] == decl_hash(declaration) and receipt["toolchain"] == self.spec["toolchain"] and
                    receipt["kernel_tool_hash"] == self.spec["kernel_tool_hash"], "EQUALITY_EXACT_KERNEL_THEOREM_BINDING")
            require(not any(name.startswith("_private.") and name.endswith(".hiddenEquality") for name in deps), "EQUALITY_PRIVATE_NAME_REUSED")
            proof_hash = self.canonical.digest_json({"module": receipt["artifacts"]["compiled_module"]["sha256"],
                "declaration": receipt["declaration_hash"], "proposition": receipt["proposition_hash"],
                "kernel_export": receipt["artifacts"]["kernel_export"]["sha256"], "kernel_tool": receipt["kernel_tool_hash"],
                "toolchain": receipt["toolchain"]})
            stripped = dict(receipt); stripped.pop("receipt_hash")
            require(proof_hash == receipt["kernel_proof_hash"] and self.canonical.digest_json(stripped) == receipt["receipt_hash"],
                    "EQUALITY_RECEIPT_RECOMPUTATION_FAILED")

    def equality_original(self):
        controls = self.document(self.path(self.config["control_registration"]))
        for label in controls["equality_original44"]:
            self.equality_case(label)
        return {"original44_exact": controls["equality_original44"], "actual_receipt_and_process_recheck": True}

    def equality_private(self):
        controls = self.document(self.path(self.config["control_registration"]))
        cases = {label: self.equality_case(label) for label in controls["equality_new11"]}
        for label in ("mismatched-semantic-analysis-exact-rejection", "changed-source-semantics-exact-binding-rejection"):
            _, result = cases[label]
            require(result["status"] == "UNKNOWN" and result["diagnostics"] == BINDING_DIAGNOSTIC and
                    type(result["bounded_scan"]["proof_attempts"]) is int and result["bounded_scan"]["proof_attempts"] == 0 and
                    result["receipts"] == [], "EQUALITY_BINDING_GUARD_NOT_EXACT")
            _, _, _, kernels = self.equality_observations()
            require(not any(row["label"] == label and any(request.get("id") == "closed_check" for request in
                        row["request"].get("defeq", [])) for row in kernels), "EQUALITY_GUARDED_CASE_STARTED_PROOF_PROCESS")
        case, result = cases["comment-only-source-semantic-equivalence"]
        require(result["status"] == "REFUTED" and self.witness(case, "semantic_identity_before") == self.witness(case, "semantic_identity_after") and
                self.additional_ref(case["witness_refs"]["before_source"]) != self.additional_ref(case["witness_refs"]["after_source"]), "EQUALITY_COMMENT_EQUIVALENCE_CONTROL_INVALID")
        grouped, _ = self.equality_case("source-analysis-wire-binding-negatives")
        mismatch = self.witness(grouped, "binding_result")
        mutant = self.witness(grouped, "mutant_result")
        changed = self.witness(grouped, "changed_result")
        invalid = self.witness(grouped,"invalid_result")
        require(mismatch["diagnostics"] == changed["diagnostics"] == BINDING_DIAGNOSTIC and
                mismatch["status"] == changed["status"] == "UNKNOWN" and
                mismatch["bounded_scan"]["proof_attempts"] == changed["bounded_scan"]["proof_attempts"] == 0 and
                mismatch["bounded_scan"]["cases_evaluated"] == changed["bounded_scan"]["cases_evaluated"] == 0 and
                mismatch["receipts"] == changed["receipts"] == [] and mutant["status"] == "REFUTED" and mutant["receipts"] and
                self.witness(grouped, "comment_result")["status"] == "REFUTED" and
                invalid["status"] == "UNKNOWN" and invalid["receipts"] == [] and
                sum(row.get("kind") == "INVALID_PROPOSAL" for row in invalid["diagnostics"]) == 4,
                "GROUPED_BINDING_NOT_DISCRIMINATING")
        index, _, _, kernels = self.equality_observations()
        subcase = copy.deepcopy(grouped)
        subcase["package_root"] = subcase["package_root"].replace("/comment-source-equivalence","/grouped-analysis-guard-mutant")
        for role in ("source","formalization","records","analysis","analysis_identity","proposals","checker","result"):
            identity = subcase["witness_refs"][role]
            identity["path"] = identity["path"].replace("/comment-source-equivalence/","/grouped-analysis-guard-mutant/").replace("/comment-source-equivalence.json","/grouped-analysis-guard-mutant.json")
            require(identity["path"] in index["files"],"GROUPED_MUTANT_ACTUAL_INPUT_WITNESS_MISSING")
            identity["sha256"] = index["files"][identity["path"]]
        self.equality_receipts(subcase,mutant,kernels)
        return {"new11_exact": controls["equality_new11"], "grouped_binding_discriminates": True}

    def source_pair(self, pair):
        left, right = self.read(self.path(pair["left"]["path"]), pair["left"]["sha256"]), self.read(self.path(pair["right"]["path"]), pair["right"]["sha256"])
        for side in ("left", "right"):
            require(self.hashes.get(pair[side]["path"]) == pair[side]["sha256"], "PURE_SOURCE_PAIR_NOT_CURRENT_INPUT")
        if "symbol" in pair:
            def select(raw):
                content = raw.decode("utf-8", "strict"); nodes = ast.parse(content).body
                found = [node for node in nodes if getattr(node, "name", None) == pair["symbol"] or
                    isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == pair["symbol"] for t in node.targets)]
                require(len(found) == 1, "PURE_SOURCE_SYMBOL_AMBIGUOUS")
                if pair.get("comparison") == "bytes": return ast.get_source_segment(content, found[0]).encode("utf-8")
                return ast.literal_eval(found[0].value) if isinstance(found[0], ast.Assign) else ast.dump(found[0], include_attributes=False)
            left, right = select(left), select(right)
        require(pair["relation"] == "equal" and type(left) is type(right) and left == right, "PURE_SOURCE_IDENTITY_FAILED")
        return {"left": pair["left"]["path"], "right": pair["right"]["path"], "symbol": pair.get("symbol")}

    def carrier_pure(self):
        observed = self.additional_index("pure")
        expected = self.config["exact_pure_test_ids"]
        require(observed["format"] == "verislop.support019-carrier-pure-observations/1" and observed["status"] == "OBSERVED" and
                observed["installed_source_sha256"] == "sha256:9930beff878848b05c8d69245fff12c1388f14254b6630504b36748c4c294366" and
                observed["registered_test_ids"] == observed["started_ids"] == expected and observed["cases"] ==
                [{"test_id": name, "status": "PASS"} for name in expected] and observed["tests_run"] == len(expected) == 30 and
                len(set(expected)) == 30 and all(type(observed[key]) is int and observed[key] == 0 for key in
                    ("failures", "errors", "skipped", "expected_failures", "unexpected_successes", "models_called")) and
                observed["task_inputs"] is False and observed["qualification_authority"] is False, "PURE_REAL_PRODUCER_SCHEMA_OR_OUTCOMES")
        pure = self.config["pure_evidence"]
        receipt = self.document(self.path(pure["actual_process_receipt_path"]))
        require(type(receipt["pid"]) is int and receipt["pid"] > 0 and type(receipt["returncode"]) is int and
                receipt["returncode"] == 0 and receipt["source_root"] == self.freeze["source_root"] and
                receipt["input_root"] == self.canonical.digest_json(self.hashes) and
                receipt["argv"] == pure["process_contract"]["argv"] and receipt["cwd"] == str(self.gate.parents[1]) and
                receipt["timed_out"] is False and receipt["timeout_seconds"] is None and
                self.freeze["created_at_utc"] <= receipt["started_utc"] <= receipt["completed_utc"], "PURE_ACTUAL_PROCESS_MISSING")
        for stream in ("stdout", "stderr"): self.additional_ref(receipt[stream])
        witnesses = self.additional_doc(observed["semantic_witnesses_ref"])
        schema = self.document(self.registered(self.path(pure["schema_path"])))
        require(witnesses["format"] == "verislop.support019-carrier-semantic-witnesses/1" and
                witnesses["source_root"] == self.freeze["source_root"] and witnesses["input_root"] == self.canonical.digest_json(self.hashes) and
                witnesses["registered_test_ids"] == expected and witnesses["producer"]["path"] == pure["producer_path"] and
                witnesses["schema"]["path"] == pure["schema_path"], "PURE_SEMANTIC_WITNESS_SCHEMA_OR_BINDING")
        def source_ref(identity):
            require(self.hashes.get(identity["path"]) == identity["sha256"], "PURE_SOURCE_NOT_CURRENT_INPUT")
            raw = self.read(self.path(identity["path"]), identity["sha256"])
            require(type(identity["byte_count"]) is int and len(raw) == identity["byte_count"], "PURE_SOURCE_SIZE")
            return raw
        for identity in witnesses["source_refs"] + [witnesses["producer"], witnesses["schema"]]: source_ref(identity)
        def decode(value):
            if isinstance(value, list): return [decode(item) for item in value]
            if isinstance(value, dict):
                if value.get("encoding") == "base64":
                    raw = base64.b64decode(value["data"], validate=True)
                    require(sha(raw) == value["sha256"] and type(value["byte_count"]) is int and len(raw) == value["byte_count"], "PURE_FRAME_RAW_BYTE_IDENTITY")
                    return raw
                if value.get("encoding") == "path": return Path(value["value"])
                return {key: decode(item) for key, item in value.items()}
            return value
        pairs = decode(witnesses["source_pairs"])
        for pair in pairs:
            raw = source_ref(pair["source_ref"]); text = raw.decode("utf-8", "strict"); tree = ast.parse(text)
            for fragment in pair["fragments"]:
                symbol = fragment["symbol"]
                if symbol == "FILE_BYTES": actual = raw
                else:
                    found = [node for node in tree.body if getattr(node, "name", None) == symbol or
                        isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == symbol for t in node.targets)]
                    require(len(found) == 1, "PURE_FRAGMENT_SYMBOL_AMBIGUOUS")
                    actual = (ast.literal_eval(found[0].value).encode("utf-8") if fragment["kind"] == "constant_bytes"
                              else ast.get_source_segment(text, found[0]).encode("utf-8"))
                require(fragment["value"] == actual, "PURE_RETAINED_FRAGMENT_NOT_SOURCE_BYTES")
        by_role = {pair["role"]:{fragment["symbol"]:fragment["value"] for fragment in pair["fragments"]} for pair in pairs}
        for left, right in (("candidate.candidate","candidate.original"),("candidate.candidate","candidate.previous")):
            for symbol in ("READER_SOURCE","inline_source","inline_command"):
                require(by_role[left][symbol] == by_role[right][symbol], "PURE_EXISTING_HELPER_BYTE_IDENTITY")
        contracts = {case["case_id"]:case for case in schema["case_contracts"]}
        require(set(contracts) == set(expected) and [case["case_id"] for case in witnesses["cases"]] == list(contracts), "PURE_EXACT30_CASE_CONTRACT_OMISSION")
        frames = decode(witnesses["frames"])
        require([frame["sequence"] for frame in frames] == list(range(1,len(frames)+1)) and all(type(frame["sequence"]) is int for frame in frames), "PURE_FRAME_SEQUENCE")
        modules, checked = {}, []
        for case in witnesses["cases"]:
            contract = contracts[case["case_id"]]; own = [frame for frame in frames if frame["case_id"] == case["case_id"]]
            require(all(case[key] == contract[key] for key in ("exact_symbol","source_only","required_roles","independent_predicates","source_only_obligations")) and
                    set(contract["required_roles"]).issubset({frame["role"] for frame in own}), "PURE_REGISTERED_ROLE_OR_CONTRACT_MISSING")
            source = source_ref(case["source_ref"]).decode("utf-8"); method = contract["exact_symbol"].split(".")[-1]
            nodes = [node for node in ast.walk(ast.parse(source)) if isinstance(node,ast.FunctionDef) and node.name == method]
            require(len(nodes) == 1 and decode(case["case_ast"]) == ast.get_source_segment(source,nodes[0]).encode("utf-8"), "PURE_FROZEN_CASE_AST")
            role_index = {}
            for frame in own: role_index.setdefault(frame["role"],[]).append(frame["sequence"])
            require(case["frame_sequences"] == [frame["sequence"] for frame in own] and case["role_index"] == role_index, "PURE_CASE_FRAME_BINDING")
            for obligation in contract["source_only_obligations"]: self.pure_source_obligation(obligation)
            for frame in own:
                source_ref(frame["source_ref"])
                args, kwargs = frame["arguments"]["positional"], frame["arguments"]["keyword"]
                returned = frame["returned_value"]
                if frame["kind"] == "source_function":
                    path = frame["source_ref"]["path"]
                    if path not in modules: modules[path] = self.module("pure_registered_function_"+str(len(modules)),self.path(path))
                    require(frame["symbol"] in schema["source_functions"] + schema["factory_source_functions"], "PURE_UNREGISTERED_SOURCE_FUNCTION")
                    try: expected_return = getattr(modules[path],frame["symbol"])(*args,**kwargs)
                    except (ValueError,TypeError) as error:
                        require(frame["exception"] is not None and frame["exception"]["python_type"] == type(error).__module__+"."+type(error).__qualname__ and
                                frame["exception"]["arguments"] == list(error.args), "PURE_SOURCE_EXCEPTION_MISMATCH")
                    else: require(frame["exception"] is None and self.canonical.dumps(expected_return) == self.canonical.dumps(returned), "PURE_SOURCE_RETURN_MISMATCH")
                elif frame["kind"] == "carrier":
                    reference, document = returned
                    carrier_source = source_ref(frame["source_ref"]).decode("utf-8")
                    methods = [node for node in ast.walk(ast.parse(carrier_source)) if isinstance(node,ast.FunctionDef) and node.name == frame["symbol"].split(".")[-1]]
                    require(len(methods) == 1,"PURE_CARRIER_SIGNATURE_AMBIGUOUS")
                    parameters = [item.arg for item in methods[0].args.args]
                    require(parameters[0] == "self" and "raw" in parameters,"PURE_CARRIER_BOUND_SIGNATURE")
                    raw_index = parameters.index("raw")-1
                    raw = kwargs.get("raw", args[raw_index] if len(args)>raw_index else None)
                    if raw is None: raw = (json.dumps(document,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n").encode("utf-8")
                    require(reference["sha256"] == sha(raw) and reference["request_sha256"] == document["request_sha256"], "PURE_RAW_CARRIER_BINDING")
                elif frame["kind"] in ("node_templates","inert_node"):
                    successful = sum(error is None for error in returned["errors"])
                    require(len(returned["errors"]) == len(args[0]) and len(returned["calls"]) == len(returned["forwarded"]) == successful and
                            all(item["same_actual"] is True for item in returned["forwarded"]), "PURE_EXACT_FORWARD_OR_ERRORS")
                    if frame["kind"] == "inert_node":
                        require(len(returned["resultStores"]) == successful and all(item["same_actual"] is True for item in returned["resultStores"]) and
                                returned["events"] == ["call","forward","result_store"]*successful, "PURE_OBSERVER_STORE_FORWARD_ORDER")
                elif frame["kind"] == "subprocess":
                    if frame["exception"] is None:
                        text_mode = kwargs.get("text") is True
                        require(type(returned["returncode"]) is int and type(returned["stdout"]) is (str if text_mode else bytes) and
                                type(returned["stderr"]) is (str if text_mode else bytes), "PURE_ACTUAL_SUBPROCESS_OUTPUT_TYPES")
                        parent = next((item for item in own if item["sequence"] == frame["parent_sequence"]),None)
                        if parent is not None and parent["kind"] in ("node_templates","inert_node"):
                            program = self.pure_node_program(parent)
                            require(args[0] == returned["argv"] == ["node","--input-type=module","-e",program] and
                                    returned["returncode"] == 0 and transport_wire(transport_parse(returned["stdout"].encode("utf-8", "strict"))) ==
                                    transport_wire(parent["returned_value"]), "PURE_NODE_PROGRAM_OR_RAW_SUBPROCESS_PARENT_MISMATCH")
                    else:
                        require(frame["exception"]["python_type"] in ("subprocess.CalledProcessError","subprocess.TimeoutExpired"), "PURE_UNREGISTERED_SUBPROCESS_EXCEPTION")
                elif frame["kind"] == "read":
                    require(frame["exception"] is None and type(returned) is bytes and
                            isinstance(self.canonical.loads(returned),dict), "PURE_ACTUAL_READER_OUTPUT")
            require(own or contract["source_only"], "PURE_CONTROL_HAS_NO_ACTUAL_WITNESS")
            checked.append({"test_id":case["case_id"],"actual_frame_count":len(own),"source_only_obligations":len(contract["source_only_obligations"])})
        return {"exact30":checked,"registered_source_fragments_rechecked":True,"mock_renderer_is_not_actual_channel":True}

    def pure_node_program(self, frame):
        source = self.read(self.path(frame["source_ref"]["path"]),frame["source_ref"]["sha256"]).decode("utf-8")
        functions = [node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name == frame["symbol"]]
        require(len(functions) == 1, "PURE_NODE_SOURCE_FUNCTION_MISSING")
        positional, keyword = frame["arguments"]["positional"], frame["arguments"]["keyword"]
        env = {"scripts":positional[0],"recipes":positional[0],"initial_state":positional[1] if len(positional)>1 else keyword.get("initial_state"),
               "simulate_rendered_truncation":keyword.get("simulate_rendered_truncation",False)}
        def evaluate(node, scope):
            if isinstance(node,ast.Constant): return node.value
            if isinstance(node,ast.Name): return scope[node.id]
            if isinstance(node,ast.Dict): return {evaluate(key,scope):evaluate(value,scope) for key,value in zip(node.keys,node.values)}
            if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Add): return evaluate(node.left,scope)+evaluate(node.right,scope)
            if isinstance(node,ast.BoolOp) and isinstance(node.op,ast.Or):
                values=[evaluate(value,scope) for value in node.values]
                return next((value for value in values if value),values[-1])
            if isinstance(node,ast.GeneratorExp):
                require(len(node.generators)==1 and not node.generators[0].ifs and isinstance(node.generators[0].target,ast.Name),"PURE_NODE_GENERATOR_GRAMMAR")
                generator=node.generators[0]
                return [evaluate(node.elt,dict(scope,**{generator.target.id:value})) for value in evaluate(generator.iter,scope)]
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                require(not node.keywords,"PURE_NODE_CALL_KEYWORD_GRAMMAR")
                values=[evaluate(value,scope) for value in node.args]
                if isinstance(node.func.value,ast.Name) and node.func.value.id=="json" and node.func.attr=="dumps": return json.dumps(*values)
                if node.func.attr=="join": return evaluate(node.func.value,scope).join(*values)
            raise ValueError("UNREGISTERED_PURE_NODE_PROGRAM_EXPRESSION")
        for statement in functions[0].body:
            if isinstance(statement,ast.Assign) and len(statement.targets)==1 and isinstance(statement.targets[0],ast.Name) and statement.targets[0].id=="program":
                env["program"]=evaluate(statement.value,env)
            elif isinstance(statement,ast.AugAssign) and isinstance(statement.target,ast.Name) and statement.target.id=="program":
                require(isinstance(statement.op,ast.Add),"PURE_NODE_PROGRAM_AUGMENT_GRAMMAR")
                env["program"] += evaluate(statement.value,env)
        require(type(env.get("program")) is str,"PURE_NODE_PROGRAM_NOT_RECONSTRUCTED")
        return env["program"]

    def pure_source_obligation(self, obligation):
        path = self.registered(self.path(obligation["path"]))
        if obligation["kind"] == "manifest_contract":
            document = self.document(path,obligation["expected_sha256"])
            for name,identity in document[obligation["entry_map"]].items():
                require(self.hashes.get(name) == identity["sha256"], "PURE_FROZEN_MANIFEST_ENTRY_NOT_REGISTERED")
        elif obligation["kind"] == "json_contract":
            document = self.document(path)
            for key,value in obligation["required_values"].items(): require(self.canonical.dumps(document[key]) == self.canonical.dumps(value),"PURE_SOURCE_JSON_CONTRACT")
            if "actual_channel_cases" in document:
                cases = {case["id"]:case for case in document["actual_channel_cases"]}; author = document["fresh_author_case"]
                require(set(cases) == {"AC002-001","AC002-002","AC002-003","AC002-004"} and
                    cases["AC002-002"]["registered_fault_budgets"] == {"outer_max_output_tokens":20000,"nested_max_output_tokens":256} and
                    cases["AC002-003"]["registered_fault_budgets"] == {"outer_max_output_tokens":256,"nested_max_output_tokens":16384} and
                    author["inspection_assertions"] == "UNATTESTED", "PURE_SOURCE_CHANNEL_FAULT_REGISTRATION")
                for case in ("AC002-002","AC002-003"):
                    require(self.canonical.dumps(cases[case]["registered_fault_view"]) == self.canonical.dumps({"operation":"field","selector":"/user","start_char":0,"output_cap_bytes":8192,"metadata_reserve_bytes":2048}) and
                        "SAME selector/start" in cases[case]["retry"] and "outer20000/nested16384" in cases[case]["retry"], "PURE_SOURCE_SAME_CURSOR_RETRY")
            else:
                cases = {case["id"]:case for case in document["cases"]}; author = cases["FA002-001"]
                require(set(cases) == {"AC002-001","AC002-002","AC002-003","AC002-004","FA002-001"} and
                    document["fresh_pure_controls"]["count"] == 15 and document["fresh_pure_controls"]["prior_controls_rerun_with_new_bindings"] == 10 and
                    "Exact whole LF-delimited source-line equality" in document["replacement_scope"] and
                    document["unavailable"]["never_fabricate_or_relabel"] is True and
                    all(value == "UNAVAILABLE" for key,value in document["unavailable"].items() if key != "never_fabricate_or_relabel") and
                    "Observable byte availability" in document["claim_scope"] and "no hidden outer-envelope identity or LLM consumption" in document["claim_scope"], "PURE_SOURCE_CAPTURE_CONTROL_REGISTRATION")
            require(type(author["exact_count"]) is int and author["exact_count"] == 1 and author["model"] == "gpt-6.1-sol" and author["fork_turns"] == "none", "PURE_SOURCE_ONE_AUTHOR_REGISTRATION")
        elif obligation["kind"] == "python_fixture_contract":
            module = self.module("pure_registered_unrelated_fixture",path); system,user = module.fixture()
            require(len(user) == 429112 and user.endswith("UNRELATED_019_002_FINAL_TAIL🙂\t ") and
                    "é🙂e\u0301" in user and '\x00\t\r\n\\"/' in user and list(module.MARKERS) == sorted(module.MARKERS,key=user.index) and
                    "syntactically valid JSON" in system and "strict UTF-8" in system and "complete reconstructed decoded field" in system and
                    "tools.exec_command" not in module.__doc__,
                    "PURE_PREPARED_FIXTURE_CONTRACT")
        else: raise ValueError("UNREGISTERED_PURE_SOURCE_OBLIGATION")

    def carrier_capture(self):
        index = self.additional_index("carrier")
        require(index["format"] == "verislop.support019-observable-channel-capture/1" and
                index["unavailable"] == UNAVAILABLE, "OBSERVABLE_CAPTURE_SCHEMA_OR_UNAVAILABLE_FIELDS")
        return index

    def carrier_fixture(self, identity):
        raw = self.additional_ref(identity["identity"])
        fixture = self.additional_doc(identity["identity"])
        reference = identity["reference"]
        require(reference["path"] == str(self.path(identity["identity"]["path"])) and reference["sha256"] == sha(raw) and
                fixture["request_sha256"] == reference["request_sha256"] and fixture["format"] == "verislop.collaboration-carrier/0.1",
                "FRESH_CARRIER_REFERENCE_BINDING")
        for field in ("system", "user"):
            require(isinstance(fixture[field], str), "CARRIER_FIELD_NOT_TEXT"); fixture[field].encode("utf-8", "strict")
        return fixture, reference

    def carrier_call(self, call, fixture, reference, fault=False):
        factory = self.module("support019_capture_factory", self.path(self.config["capture_factory"]))
        view, case = call["view"], call["case_id"]
        recipe = (factory.initial_collector_template(reference, case) if view["operation"] == "inventory" else
                  factory.next_collector_template(reference, view, case, fault=fault))
        require(self.additional_ref(call["submitted_code_ref"]) == recipe.encode("utf-8", "strict"), "EXACT_CAPTURE002_RECIPE_MISMATCH")
        key = factory.collector_result_key(reference, case)
        require(call["own_result_key"] == key, "OWN_COLLECTOR_KEY_MISMATCH")
        retained = self.additional_doc(call["retained_record_ref"])
        result = retained["result"]
        require(retained["view"] == view and call["unavailable"] == UNAVAILABLE and type(result.get("exit_code")) is int
                and result["exit_code"] == 0 and "session_id" not in result, "ACTUAL_NESTED_RESULT_OR_VIEW_INCOMPLETE")
        raw = self.additional_ref(call["returned_output_ref"])
        require(result["output"].encode("utf-8", "strict") == raw, "ACTUAL_RETURNED_OUTPUT_BYTES_CHANGED")
        if fault:
            require(call["decision"] == "REJECT" and call["cursor_before"] == call["cursor_after"] == view["start_char"],
                    "TRUNCATED_CURSOR_ADVANCEMENT")
            return result
        record = self.document(self.path(call["returned_output_ref"]["path"]))
        wire = lambda obj: json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8", "strict")
        require(raw == wire(record) + b"\n" and len(raw) <= view["output_cap_bytes"] and record["status"] == "ok" and
                record["format"] == "verislop.exact-carrier-view/0.1" and record["carrier_path"] == reference["path"] and
                record["carrier_sha256"] == reference["sha256"] and record["request_sha256"] == reference["request_sha256"] and
                record["request_id"] == fixture["request_id"] and record["char_unit"] == "decoded_unicode_code_points" and
                record["byte_unit"] == "decoded_field_utf8" and record["output_cap_bytes"] == view["output_cap_bytes"] and
                record["metadata_reserve_bytes"] == view["metadata_reserve_bytes"], "ORIGINAL_VIEW_WIRE_OR_IDENTITY_MISMATCH")
        if view["operation"] == "inventory":
            require(record["operation"] == "inventory" and len(raw) <= view["metadata_reserve_bytes"] and
                    record["fields"] == [{"selector": "/" + name, "field_chars": len(fixture[name]),
                         "field_utf8_bytes": len(fixture[name].encode("utf-8")), "start_char": 0, "end_char": len(fixture[name])}
                         for name in ("system", "user")], "EXACT_FIELD_INVENTORY_MISMATCH")
            return record
        selector, start, end = view["selector"], view["start_char"], record["end_char"]
        text = fixture[selector[1:]]
        require(type(start) is int and type(end) is int and 0 <= start <= end <= len(text) and
                record["operation"] == "field" and record["selector"] == selector and record["start_char"] == start and
                record["content"] == text[start:end] and record["field_chars"] == len(text) and
                record["field_utf8_bytes"] == len(text.encode("utf-8")) and record["content_chars"] == end - start and
                record["content_utf8_bytes"] == len(text[start:end].encode("utf-8")) and
                record["start_utf8_byte"] == len(text[:start].encode("utf-8")) and record["end_utf8_byte"] == len(text[:end].encode("utf-8")) and
                record["next_char"] == end and record["field_eof"] is (end == len(text)) and (end > start or start == len(text)),
                "EXACT_ORIGINAL_SLICE_UTF8_TAIL_EOF_MISMATCH")
        token = len(wire(record["content"]))
        require(token <= view["output_cap_bytes"] - view["metadata_reserve_bytes"] and len(raw) - token + 2 <= view["metadata_reserve_bytes"] and
                call["decision"] == "ACCEPT" and call["cursor_before"] == start and call["cursor_after"] == end, "VIEW_CAP_OR_CURSOR_MISMATCH")
        return record

    def carrier_full(self):
        index = self.carrier_capture(); fixture, reference = self.carrier_fixture(index["fresh_fixture"])
        require(len(fixture["user"]) > 400000, "WHOLE_USER_FIELD_NOT_LARGE")
        calls = [call for call in index["calls"] if call["case_id"] == "AC002-001"]
        require(calls and calls[0]["view"]["operation"] == "inventory", "ACTUAL_FULL_FIELD_INVENTORY_MISSING")
        require(calls[0]["outer_max_output_tokens"] == 20000 and calls[0]["nested_max_output_tokens"] == 16384 and
                calls[0]["view"] == {"operation": "inventory", "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048},
                "FULL_FIELD_INITIAL_NORMAL_CAPS_CHANGED")
        self.carrier_call(calls[0], fixture, reference)
        selector, start, finished = "/system", 0, []
        for call in calls[1:]:
            require(call["view"]["selector"] == selector and call["view"]["start_char"] == start and
                    call["outer_max_output_tokens"] == 20000 and call["nested_max_output_tokens"] == 16384 and
                    call["view"]["output_cap_bytes"] == 8192 and call["view"]["metadata_reserve_bytes"] == 2048,
                    "FULL_FIELD_CALL_ORDER_OR_NORMAL_CAPS_CHANGED")
            record = self.carrier_call(call, fixture, reference)
            start = record["next_char"]
            if record["field_eof"]:
                finished.append(selector); selector, start = "/user", 0
        require(finished == ["/system", "/user"], "WHOLE_FIELD_COVERAGE_OR_EXPLICIT_EOF_MISSING")
        return {"actual_both_fields_exact": finished, "user_decoded_chars": len(fixture["user"]),
                "field_utf8_roots": {"/" + key: sha(fixture[key].encode("utf-8")) for key in ("system", "user")}}

    def carrier_faults(self):
        index = self.carrier_capture(); fixture, reference = self.carrier_fixture(index["fresh_fixture"])
        for case, nested, outer in (("AC002-002", 256, 20000), ("AC002-003", 16384, 256)):
            calls = [call for call in index["calls"] if call["case_id"] == case]
            require(len(calls) == 2, "ACTUAL_FAULT_AND_RETRY_PAIR_MISSING")
            fault, retry = calls
            require(fault["view"] == {"operation": "field", "selector": "/user", "start_char": 0,
                                      "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048} and
                    fault["outer_max_output_tokens"] == outer and fault["nested_max_output_tokens"] == nested,
                    "REGISTERED_ACTUAL_FAULT_BUDGET_OR_VIEW_CHANGED")
            result = self.carrier_call(fault, fixture, reference, fault=True)
            if case == "AC002-002":
                require(type(result.get("original_token_count")) is int and result["original_token_count"] > nested and
                        "Warning: truncated output" in result["output"], "ACTUAL_NESTED_TRUNCATION_NOT_OBSERVED")
            else:
                observed = self.additional_ref(fault["rendered_observation_ref"])
                require(fault["rendered_outer_truncation_observed"] is True and b"truncat" in observed.lower() and
                        fault["observation_scope"] == "rendered_items_only", "ACTUAL_OUTER_RENDERED_TRUNCATION_NOT_OBSERVED")
            require(retry["view"] == {"operation": "field", "selector": "/user", "start_char": 0,
                                      "output_cap_bytes": 4096, "metadata_reserve_bytes": 2048} and
                    retry["outer_max_output_tokens"] == 20000 and retry["nested_max_output_tokens"] == 16384,
                    "SAME_CURSOR_NORMAL_RETRY_NOT_EXACT")
            self.carrier_call(retry, fixture, reference)
        return {"actual_nested_and_rendered_outer_faults": True, "same_cursor_retries_validated": True, "unavailable": UNAVAILABLE}

    def carrier_empty(self):
        index = self.carrier_capture(); fixture, reference = self.carrier_fixture(index["empty_fixture"])
        require(fixture["system"] == fixture["user"] == "", "EMPTY_ORIGINAL_FIELDS_NOT_EMPTY")
        calls = [call for call in index["calls"] if call["case_id"] == "AC002-004"]
        require(len(calls) == 3 and calls[0]["view"]["operation"] == "inventory", "EMPTY_INVENTORY_AND_TWO_ACTUAL_VIEWS_MISSING")
        self.carrier_call(calls[0], fixture, reference)
        for call, selector in zip(calls[1:], ("/system", "/user")):
            require(call["view"]["selector"] == selector and call["view"]["start_char"] == 0 and
                    call["outer_max_output_tokens"] == 20000 and call["nested_max_output_tokens"] == 16384 and
                    call["view"]["output_cap_bytes"] == 8192 and call["view"]["metadata_reserve_bytes"] == 2048, "EMPTY_FIELD_VIEW_ORDER")
            record = self.carrier_call(call, fixture, reference)
            require(record["content"] == "" and record["next_char"] == record["field_chars"] == record["field_utf8_bytes"] == 0 and
                    record["field_eof"] is True, "EMPTY_EXPLICIT_EOF_MISSING")
        return {"actual_empty_system_user_explicit_EOF": True}

    def fresh_author(self):
        index = self.additional_index("author")
        require(index["format"] == "verislop.support019-single-fresh-author-evidence/1" and
                type(index["spawn_count"]) is int and index["spawn_count"] == 1 and
                index["requested_model"] == "gpt-6.1-sol" and index["fork_turns"] == "none" and
                index["model_identity"] == index["semantic_consumption"] == "UNATTESTED" and
                type(index["observed_author_requests"]) is list and len(index["observed_author_requests"]) == 1 and
                index["replacement_author_or_resampling"] is False and
                index["evaluator_expectations_sent_to_author"] is False, "FRESH_AUTHOR_COUNT_OR_AUTHORITY_BOUNDARY")
        fixture, reference = self.carrier_fixture(index["fresh_fixture"])
        viewer = self.module("support019_installed_plain_viewer", self.path("synthetic_dataset/tools/bootstrap_tier2_carrier_view.py"))
        message = self.additional_ref(index["submitted_message_ref"])
        require(message == self.additional_ref(index["expected_literal_message_ref"]) ==
                viewer.agent_message(reference).encode("utf-8", "strict"), "ORIGINAL_PLAIN_AUTHOR_MESSAGE_NOT_EXACT")
        request = self.additional_doc(index["spawn_request_ref"])
        actual_spawn = self.additional_doc(index["spawn_result_ref"])
        observed = index["observed_author_requests"][0]
        require(type(actual_spawn) is dict and set(actual_spawn) == {"task_name"} and
                type(actual_spawn["task_name"]) is str and re.fullmatch(r"/root(?:/[a-z0-9_]+)+", actual_spawn["task_name"]) is not None and
                type(request["task_name"]) is str and re.fullmatch(r"[a-z0-9_]+", request["task_name"]) is not None and
                actual_spawn["task_name"].rsplit("/", 1)[1] == request["task_name"], "ACTUAL_FRESH_AUTHOR_CANONICAL_TASK_NAME_NOT_BOUND")
        require(request["model"] == "gpt-6.1-sol" and request["fork_turns"] == "none" and
                type(request["message"]) is str and request["message"].encode("utf-8", "strict") == message and
                type(index["author_agent_id"]) is str and actual_spawn["task_name"] == index["author_agent_id"] and
                type(observed) is dict and set(observed) == {"spawn_request_ref", "spawn_result_ref", "agent_id"} and
                self.canonical.dumps(observed["spawn_request_ref"]) == self.canonical.dumps(index["spawn_request_ref"]) and
                self.canonical.dumps(observed["spawn_result_ref"]) == self.canonical.dumps(index["spawn_result_ref"]) and
                observed["agent_id"] == actual_spawn["task_name"], "ACTUAL_SINGLE_SPAWN_REQUEST_BINDING")
        final = self.additional_doc(index["literal_final_ref"])
        expected = {"markers": list(dict.fromkeys(re.findall(r"UNRELATED_019_002_[A-Za-z0-9_]+", fixture["user"]))),
                    "field_roots": {"/" + key: sha(fixture[key].encode("utf-8")) for key in ("system", "user")},
                    "field_eof": {"/system": True, "/user": True},
                    "field_chars": {"/" + key: len(fixture[key]) for key in ("system", "user")}}
        require(self.canonical.dumps(final) == self.canonical.dumps(expected) and
                self.canonical.dumps(self.additional_doc(index["evaluator_expectations_ref"])) == self.canonical.dumps(expected),
                "FRESH_LITERAL_FINAL_MARKERS_ROOTS_COUNTS_EOF_MISMATCH")
        require(index["exposed_responses_refs"], "EXPOSED_AUTHOR_RESPONSES_NOT_RETAINED")
        for response in index["exposed_responses_refs"]:
            self.additional_ref(response)
        return {"requested_model": "gpt-6.1-sol", "actual_spawn_count": 1, "fork_turns": "none",
                "model_identity": "UNATTESTED", "semantic_consumption": "UNATTESTED", "literal_FINAL_sha256": index["literal_final_ref"]["sha256"]}

    def authority_boundary(self):
        require(self.spec["core_model_calls"] == 0 and self.spec["ancillary_fresh_author_calls"] == 1 and
                all(self.spec[key] is None for key in ("inference_timeout", "retrieval_timeout", "review_timeout")) and
                self.spec["strict_implementation_proof_release_unchanged"] is True, "MODEL_DEADLINE_OR_STRICT_AUTHORITY_DELTA")
        baseline = self.document(self.path(self.config["policy_baseline"]))
        require(self.spec["policy_hash"] == baseline["policy_hash"] and self.spec["kernel_tool_hash"] == baseline["kernel_tool_hash"] and
                self.spec["toolchain"] == baseline["toolchain"], "STRICT_POLICY_KERNEL_TOOLCHAIN_DELTA")
        for name, digest in self.config["unchanged_authority_source_bindings"].items():
            require(self.hashes.get(name) == digest, "STRICT_AUTHORITY_IMPLEMENTATION_CHANGED")
            self.read(self.path(name), digest)
        return {"strict_implementation_proof_release_unchanged": True, "core_model_calls": 0,
                "ancillary_author_calls": 1, "inference_retrieval_review_deadlines": None, "semantic_TCB_delta": [],
                "observable_forwarding_trust": "TCB-TOOL-FORWARDING", "unavailable": UNAVAILABLE}

    def whole_audit(self):
        required = list(self.results)
        require(all(self.results[name]["status"] == "VERIFIED" for name in required), "WHOLE_CURRENT_ROOT_REQUIRED_GROUP_BLOCKED")
        require(self.phase_receipts and len(self.phase_receipts) == 4 and self.snapshot is not None and self.pkg is not None,
                "WHOLE_CURRENT_ROOT_FRESH_PHASE_COLLECTION_BUILD_EVIDENCE_MISSING")
        for name, identity in list(self.evidence.items()):
            self.read(Path(name), identity["sha256"])
        self.guard()
        return {"original18_raw_groups_and_added8_verified": True, "original4_actual_phases": 4,
                "exact_current_input_source_test_maps_rehashed": True, "prior_PASS_inheritance": False,
                "fresh_independent_reader_required_after_this_reconciler": True}
