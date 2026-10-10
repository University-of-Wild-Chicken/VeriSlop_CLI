"""Closed optional-view metadata and exhaustive replay audit; no proof search."""
from __future__ import annotations

from typing import Callable

from .. import canonical, leanbridge, schemas, policy
from ..exprjson import canon, constants, decl_hash, name_str
from ..targets import vscore3_readable as R, vscore3_target as T


def fail(code, message):
    from .vscore3_checker import _fail
    raise _fail(code, message)


def checked_json(name, data):
    try:
        obj = canonical.loads(data)
    except Exception as exc:
        fail("INVALID_CANDIDATE", f"invalid readable metadata: {exc}")
    if canonical.dumps(obj) != data:
        fail("INVALID_CANDIDATE", "readable metadata must use exact canonical bytes")
    issues = schemas.validate(name, obj)
    if issues:
        fail("INVALID_CANDIDATE", "readable schema rejected: " + "; ".join(map(str, issues)))
    return obj


def ref(path, data):
    return {"path": path, "sha256": canonical.digest(data), "size": len(data)}


def candidate_metadata(selection: bytes, read_bytes: Callable[[str], bytes]) -> dict[str, bytes]:
    obj = checked_json("vscore-readable-selection", selection)
    out = {R.SELECTION_PATH: selection}
    for i, row in enumerate(obj["diagnostic_inputs"]):
        expected_path = f"support/readable/diagnostics/{i}.json"
        a = row["artifact"]
        if row["slot_id"] != f"vscore-readable-diagnostic-{i}" or a["path"] != expected_path:
            fail("INVALID_CANDIDATE", "readable diagnostic path/slot is not the fixed ordered inventory")
        try:
            data = read_bytes(expected_path)
        except (KeyError,OSError) as exc:
            fail("INPUT_MUTATION", f"missing frozen readable diagnostic {expected_path}: {exc}")
        if ref(expected_path, data) != a:
            fail("INPUT_MUTATION", f"readable diagnostic {expected_path} changed")
        out[expected_path] = data
    if obj["selected_mode"] == "CHECKED" and obj["diagnostic_inputs"]:
        fail("INVALID_CANDIDATE", "CHECKED selection cannot carry unavailable diagnostics")
    declared = {canonical.digest_json(x["artifact"]) for x in obj["diagnostic_inputs"]}
    used = {canonical.digest_json(x["diagnostic_artifact"]) for x in obj["reasons"] if x["diagnostic_artifact"]}
    if declared != used:
        fail("INVALID_CANDIDATE", "readable reasons and diagnostic inputs differ")
    return out


def bindings(ctx, spec, base):
    def input_hash(name, fallback):
        return canonical.digest(ctx.inputs[name][1]) if name in ctx.inputs else canonical.digest(fallback)
    return {"source": canonical.digest(spec.source_bytes),
            "source_registry": canonical.digest_json(R.source_registry({eid: cs for eid, cs, _, _ in spec.enums})),
            "profile": input_hash("profile", canonical.dumps(T.profile_descriptor(ctx.accepted_profile, ctx.accepted_profile_hash))),
            "accepted_profile": ctx.accepted_profile_hash,
            "accepted_ir": ctx.plan.get("accepted_ir", canonical.digest_json(ctx.accepted_ir)),
            "acceptance_certificate": ctx.plan.get("acceptance_certificate", canonical.digest_json(ctx.acceptance)),
            "relation": input_hash("relation", canonical.dumps(ctx.relation)),
            "adapters": canonical.digest_json([{"name": a.name, "shape": a.shape, "body": a.definition} for a in spec.adapters]),
            "toolchain_closure": base.observation["toolchain_olean_closure"],
            "policy": policy.policy_hash(ctx.policy)}


def renderer():
    return {**R.descriptor(), "kernel_tool_hash": leanbridge.kernel_tool_hash()}


def selection_record(ctx, spec, base, *, audit=None, reasons=None, diagnostics=None):
    return {"schema_version": "1", "format": "verislop.vscore-readable-selection/1",
            "selected_mode": "CHECKED" if audit else "BASE",
            "status": "CHECKED" if audit else "UNSUPPORTED", "inputs": bindings(ctx, spec, base),
            "renderer": renderer(), "budgets": R.BUDGETS,
            "base_goal_hash": canonical.digest((spec.base_text or spec.text).encode()),
            "base_proposition_hash": base.proposition_hash,
            "checked_descriptor": audit["checked_descriptor"] if audit else None,
            "reasons": reasons or [], "diagnostic_inputs": diagnostics or []}


def validate_binding(ctx, spec, base, selection):
    obj = checked_json("vscore-readable-selection", selection)
    metadata = candidate_metadata(selection, lambda p: ctx.readable_diagnostics[p])
    if set(metadata) - {R.SELECTION_PATH} != set(ctx.readable_diagnostics):
        fail("INVALID_CANDIDATE", "readable diagnostic map has missing/extra inputs")
    for key, value in (("inputs", bindings(ctx, spec, base)), ("renderer", renderer()),
                       ("budgets", R.BUDGETS), ("base_goal_hash", canonical.digest((spec.base_text or spec.text).encode())),
                       ("base_proposition_hash", base.proposition_hash)):
        if obj[key] != value:
            fail("INPUT_MUTATION", f"frozen readable selection {key} differs from current exact inputs")
    return obj


def audit(ctx, spec, base, selected):
    """Check all new goal declarations, including unused roots, after kernel replay."""
    baseline = {n: c for n, c in base.decls.items() if c.get("module") == [T.GOAL_MODULE]}
    current = {n: c for n, c in selected.decls.items() if c.get("module") == [T.GOAL_MODULE]}
    for n, c in baseline.items():
        if n not in current or decl_hash(current[n]) != decl_hash(c):
            fail("STATEMENT_MISMATCH", f"readable enrichment changed base declaration {n}")
    if selected.proposition_hash != base.proposition_hash:
        fail("STATEMENT_MISMATCH", "readable enrichment changed the universal base proposition")
    support = {n: c for n,c in current.items() if n not in baseline}
    if not support or len(support) > R.BUDGETS["support_declarations"]:
        fail("UNSUPPORTED_CAPABILITY", "readable support declaration inventory unavailable")
    exported = canonical.dumps(support)
    if len(exported) > R.BUDGETS["support_export_bytes"]:
        fail("UNSUPPORTED_CAPABILITY", "readable support export budget exceeded")
    from .vscore3_checker import _parts_digest
    module_hash = _parts_digest(selected.modules[T.GOAL_MODULE])
    baseline_axioms = sorted({name_str(a) for c in baseline.values() for a in c.get("axioms", [])})
    files, rows = {}, []
    for i, (n, c) in enumerate(sorted(support.items())):
        if not n.startswith((R.NAMESPACE + ".", T.GOAL_MODULE + ".Readable.")):
            fail("STATEMENT_MISMATCH", f"unregistered readable support declaration {n}")
        if c.get("kind") not in ("definition", "theorem") or c.get("safety") != "safe" or c.get("level_params"):
            fail("INADMISSIBLE_AXIOM", f"unsupported readable declaration kind/safety/levels {n}")
        if "axioms" not in c or "unresolved_constants" not in c or c["unresolved_constants"]:
            fail("UNDECLARED_DEPENDENCY", f"missing/incomplete readable axiom walk {n}")
        if c["kind"] == "theorem" and "value_constants" not in c:
            fail("KERNEL_REJECTION", f"missing actual theorem value references {n}")
        if c["kind"] == "definition" and "value" not in c:
            fail("KERNEL_REJECTION", f"missing exported readable definition body {n}")
        axs = sorted(name_str(a) for a in c["axioms"])
        if not set(axs) <= set(baseline_axioms) or any(policy.classify_axiom(a,ctx.policy) != "allowed" for a in axs):
            fail("INADMISSIBLE_AXIOM", f"readable declaration introduces logical assumptions {n}")
        type_refs = sorted(constants(c["type"]))
        body_refs = sorted(constants(c["value"])) if c["kind"] == "definition" else sorted(name_str(a) for a in c["value_constants"])
        todo, deps = list(type_refs + body_refs), set()
        while todo:
            dep = todo.pop()
            if dep in deps: continue
            deps.add(dep)
            d = selected.decls.get(dep)
            if d is None: continue  # pinned toolchain closure anchors unstaged constants
            if d.get("module") == [T.PROOF_MODULE]:
                fail("UNDECLARED_DEPENDENCY", "readable support depends on a candidate proof")
            todo.extend(constants(d["type"]))
            todo.extend(constants(d.get("value", {})))
            todo.extend(name_str(a) for a in d.get("value_constants", []))
        th = canonical.digest_json(canon(c["type"], []))
        bh = canonical.digest_json(canon(c["value"], [])) if c["kind"] == "definition" else None
        path = f"readable/kernel-records/{i}.json"; data = canonical.dumps(c); files[path] = data
        identity = {"regenerated_source_hash": canonical.digest(spec.text.encode()), "module_parts_hash": module_hash,
                    "type_hash": th}
        if bh is None:
            identity.update(kind="MODULE_BOUND_PROOF", proof_body_ast="UNAVAILABLE", individual_proof_body_digest="UNAVAILABLE",
                            direct_value_constants_hash=canonical.digest_json(body_refs), axiom_inventory_hash=canonical.digest_json(axs))
        else:
            identity.update(kind="EXPORTED_DEFINITION_BODY", exported_body_hash=bh)
        row = {"name": n, "module": T.GOAL_MODULE,
               "origin": "source_block" if n.startswith(R.NAMESPACE + ".") else "correspondence",
               "kind": c["kind"], "safety": "safe", "level_params": [], "type_hash": th, "body_hash": bh,
               "type_constants": type_refs, "body_constants": body_refs, "transitive_dependencies": sorted(deps),
               "axioms": axs, "unresolved_constants": [], "kernel_record": ref(path,data), "proof_identity": identity}
        row["identity_hash"] = canonical.digest_json(row); rows.append(row)
    inventory = []
    for f in spec.readable_view.functions:
        n, rn = f["name"], R.NAMESPACE + "." + f["name"]
        gn = T.GOAL_MODULE + ".Readable."
        for need in [gn + "lookup_" + n, gn + "signature_" + n, gn + "runEquals_" + n,
                     gn + n + "_compiled", rn + "_params", rn + "_result", rn + "_run", rn + "_named"]:
            if need not in support: fail("STATEMENT_MISMATCH", f"missing complete readable function inventory {need}")
        inventory.append({k:v for k,v in f.items() if k in ("role","source_id","source_index","compiled_index","source_declaration_hash","compilation_context_hash")})
        inventory[-1].update(params_shape_hash=decl_hash(support[rn+"_params"]), result_shape_hash=decl_hash(support[rn+"_result"]),
            lookup_theorem=gn+"lookup_"+n, signature_theorem=gn+"signature_"+n, compiled_decl=gn+n+"_compiled",
            readable_run_decl=rn+"_run", readable_named_decl=rn+"_named", run_equals_theorem=gn+"runEquals_"+n,
            run_equals_type_hash=canonical.digest_json(canon(support[gn+"RunEquals_"+n]["value"], [])))
    equalities = [{"name": n, "type_hash": canonical.digest_json(canon(c["type"],[]))}
                  for n,c in sorted(support.items()) if c["kind"] == "theorem"]
    deps = {r["name"]:r["transitive_dependencies"] for r in rows}; axs={r["name"]:r["axioms"] for r in rows}
    for path,obj in (("compiled-inventory",inventory),("declarations",rows),("equalities",equalities),
                     ("dependencies",deps),("axioms",axs),("kernel-export",support),("proof-identity",[r["proof_identity"] for r in rows])):
        files["readable/"+path+".json"] = canonical.dumps(obj)
    baseline_export=canonical.dumps(baseline)
    if len(baseline_export)>R.BUDGETS["support_export_bytes"]:
        fail("UNSUPPORTED_CAPABILITY","readable baseline export budget exceeded")
    files["readable/base-kernel-export.json"] = baseline_export
    files.update({"readable/source-block.lean":spec.readable_view.block,
                  "readable/standalone.lean":spec.readable_view.standalone,"readable/typed-ir.json":spec.readable_view.typed_ir,
                  "readable/correspondence.lean":spec.readable_correspondence})
    files["readable/kernel-receipt.json"] = canonical.dumps({"format":"verislop.readable-kernel-receipt/1",
        "replayed":True,"goal_module_parts_hash":module_hash,"toolchain_olean_closure":selected.observation["toolchain_olean_closure"],
        "kernel_tool_hash":leanbridge.kernel_tool_hash(),"support_export_hash":canonical.digest(exported)})
    checked = {"source_block_hash":canonical.digest(spec.readable_view.block),"typed_ir_hash":canonical.digest(spec.readable_view.typed_ir),
        "correspondence_hash":canonical.digest(spec.readable_correspondence),"selected_goal_hash":canonical.digest(spec.text.encode()),
        "compiled_inventory_hash":canonical.digest_json(inventory),"support_declarations_hash":canonical.digest_json(rows),
        "equalities_hash":canonical.digest_json(equalities),"dependency_inventory_hash":canonical.digest_json(deps),
        "axiom_inventory_hash":canonical.digest_json(axs),"goal_module_parts_hash":module_hash}
    return {"files":files,"checked_descriptor":checked,"compiled_inventory":inventory,"support_declarations":rows,
            "baseline_axioms":baseline_axioms,"actual_axioms":sorted({a for r in rows for a in r["axioms"]}),
            "base_identity_hash":canonical.digest_json({n:decl_hash(c) for n,c in sorted(baseline.items())})}


ROLES = {"readable/source-block.lean":"source_block", "readable/standalone.lean":"standalone_source",
         "readable/typed-ir.json":"typed_ir", "readable/correspondence.lean":"correspondence_source",
         "readable/base-goal.lean":"base_goal", "readable/selected-goal.lean":"selected_goal",
         "readable/declarations.json":"declarations", "readable/compiled-inventory.json":"compiled_inventory",
         "readable/equalities.json":"equalities", "readable/dependencies.json":"dependencies",
         "readable/axioms.json":"axioms", "readable/kernel-export.json":"kernel_export",
         "readable/base-kernel-export.json":"kernel_export",
         "readable/kernel-receipt.json":"kernel_receipt", "readable/proof-identity.json":"proof_identity",
         R.SELECTION_PATH:"selection"}


def artifact_role(path):
    if path in ROLES: return ROLES[path]
    if path.startswith("readable/kernel-records/") and path.endswith(".json") and path[24:-5].isdigit():
        return "kernel_export"
    if path.startswith("support/readable/diagnostics/") and path.endswith(".json") and path[29:-5].isdigit():
        return "diagnostics"
    fail("INVALID_CANDIDATE", f"unregistered readable artifact path {path}")


def attach(ctx, spec, base, build, selection, audited=None):
    obj = validate_binding(ctx,spec,base,selection)
    if obj["selected_mode"] == "CHECKED":
        if not audited or obj["checked_descriptor"] != audited["checked_descriptor"]:
            fail("INPUT_MUTATION", "frozen CHECKED readable inventory/module differs from fresh replay")
    files = dict(audited["files"]) if audited else {}
    files.update(candidate_metadata(selection, lambda p:ctx.readable_diagnostics[p]))
    files.update({"readable/base-goal.lean":(spec.base_text or spec.text).encode(),"readable/selected-goal.lean":spec.text.encode()})
    descriptor = obj["checked_descriptor"]
    proofdeps = sorted({name_str(a) for c in build.decls.values() if c.get("module") == [T.PROOF_MODULE]
                        for a in c.get("value_constants", []) if name_str(a).startswith((R.NAMESPACE+".",T.GOAL_MODULE+".Readable."))})
    manifest = {"schema_version":"1", "format":"verislop.vscore-readable-view/1",
        "selected_mode":obj["selected_mode"],"status":obj["status"],
        "selection":{"slot_id":R.SELECTION_SLOT,"role":R.SELECTION_ROLE,"sha256":canonical.digest(selection)},
        "inputs":obj["inputs"],"renderer":obj["renderer"],"budgets":obj["budgets"],
        "base_goal_hash":obj["base_goal_hash"],"selected_goal_hash":canonical.digest(spec.text.encode()),
        "base_proposition_hash":base.proposition_hash,"replayed_proposition_hash":build.proposition_hash,
        "support_inventory_hash":descriptor["support_declarations_hash"] if descriptor else None,
        "support_module_parts_hash":descriptor["goal_module_parts_hash"] if descriptor else None,
        "compiled_inventory":audited["compiled_inventory"] if audited else [],
        "support_declarations":audited["support_declarations"] if audited else [],
        "base_declaration_identity_hash":audited["base_identity_hash"] if audited else canonical.digest_json({n:decl_hash(c) for n,c in sorted(base.decls.items()) if c.get("module")==[T.GOAL_MODULE]}),
        "support_axiom_baseline_hash":canonical.digest_json(audited["baseline_axioms"] if audited else []),
        "actual_support_axioms":audited["actual_axioms"] if audited else [],
        "toolchain":{"pin":ctx.acceptance["toolchain"]["pin"],"kernel_tool_hash":leanbridge.kernel_tool_hash(),
            "import_closure_hash":build.observation["toolchain_olean_closure"]},
        "artifacts":[{"role":artifact_role(p),"artifact":ref(p,d)} for p,d in sorted(files.items())],
        "reasons":obj["reasons"],"checked_proof_support_dependencies":proofdeps}
    data = canonical.dumps(manifest)
    if len(data)>R.BUDGETS["manifest_bytes"]: fail("UNSUPPORTED_CAPABILITY","readable manifest budget exceeded")
    checked_json("vscore-readable-view",data)
    files[R.MANIFEST_PATH]=data
    support={"version":R.VERSION,"mode":obj["selected_mode"],"status":obj["status"],
        "selection":{"slot_id":R.SELECTION_SLOT,"sha256":canonical.digest(selection)},
        "manifest":{"path":R.MANIFEST_PATH,"sha256":canonical.digest(data)},
        "support_inventory_hash":manifest["support_inventory_hash"],"support_module_parts_hash":manifest["support_module_parts_hash"],
        "selected_goal_hash":manifest["selected_goal_hash"]}
    build.readable_support,build.readable_artifacts = support,files
    build.observation["readable_support"] = support
    return build


def artifact_refs(descriptor, read_bytes):
    obj = checked_json("vscore-readable-view", read_bytes(R.MANIFEST_PATH))
    data=read_bytes(R.MANIFEST_PATH)
    expected={"version":R.VERSION,"mode":obj["selected_mode"],"status":obj["status"],
        "selection":{"slot_id":R.SELECTION_SLOT,"sha256":obj["selection"]["sha256"]},
        "manifest":{"path":R.MANIFEST_PATH,"sha256":canonical.digest(data)},
        "support_inventory_hash":obj["support_inventory_hash"],"support_module_parts_hash":obj["support_module_parts_hash"],
        "selected_goal_hash":obj["selected_goal_hash"]}
    if descriptor!=expected: fail("INPUT_MUTATION","readable descriptor differs from exact accepted manifest")
    out={R.MANIFEST_PATH:canonical.digest(data)}
    for row in obj["artifacts"]:
        a=row["artifact"]; p=a["path"]
        if p in out or artifact_role(p)!=row["role"]: fail("INVALID_CANDIDATE","duplicate/redirected readable artifact")
        d=read_bytes(p)
        if ref(p,d)!=a: fail("INPUT_MUTATION",f"readable artifact {p} changed")
        out[p]=a["sha256"]
    selection=read_bytes(R.SELECTION_PATH); s=checked_json("vscore-readable-selection",selection)
    if canonical.digest(selection)!=obj["selection"]["sha256"] or any(s[k]!=obj[k] for k in ("inputs","renderer","budgets","base_goal_hash","base_proposition_hash","selected_mode","status","reasons")):
        fail("INPUT_MUTATION","readable manifest differs from frozen selection")
    metadata=candidate_metadata(selection,read_bytes)
    mandatory={R.SELECTION_PATH,"readable/base-goal.lean","readable/selected-goal.lean",*metadata}
    if out.get("readable/base-goal.lean")!=obj["base_goal_hash"] or out.get("readable/selected-goal.lean")!=obj["selected_goal_hash"]:
        fail("INPUT_MUTATION","readable goal artifacts are missing or differ from declared exact goals")
    if obj["base_proposition_hash"]!=obj["replayed_proposition_hash"]:
        fail("STATEMENT_MISMATCH","readable manifest changes the universal base proposition")
    if s["selected_mode"]=="CHECKED":
        mandatory.update(ROLES)
        try:
            baseline_export=read_bytes("readable/base-kernel-export.json")
            if len(baseline_export)>R.BUDGETS["support_export_bytes"]:
                fail("UNSUPPORTED_CAPABILITY","readable retained baseline export budget exceeded")
            baseline=canonical.loads(baseline_export)
            if not isinstance(baseline,dict) or any(not isinstance(c,dict) or not isinstance(c.get("type"),dict)
                or not isinstance(c.get("axioms"),list) or not isinstance(c.get("name"),list)
                or c.get("kind") not in ("definition","theorem") or c.get("safety")!="safe"
                or not isinstance(c.get("level_params"),list) or not isinstance(c.get("unresolved_constants"),list)
                or (c["kind"]=="definition" and not isinstance(c.get("value"),dict))
                for c in baseline.values()):
                fail("INVALID_CANDIDATE","readable baseline export has malformed declaration records")
            if any(name_str(c["name"])!=n or c.get("module")!=[T.GOAL_MODULE] for n,c in baseline.items()):
                fail("INPUT_MUTATION","readable baseline export has redirected declaration/module identity")
            if canonical.digest_json({n:decl_hash(c) for n,c in sorted(baseline.items())})!=obj["base_declaration_identity_hash"]:
                fail("INPUT_MUTATION","readable baseline declaration identity changed")
            baseline_axioms=sorted({name_str(a) for c in baseline.values() for a in c["axioms"]})
        except (KeyError,ValueError,TypeError) as exc:
            fail("INVALID_CANDIDATE",f"malformed readable baseline export: {exc}")
        actual_axioms=sorted({a for row in obj["support_declarations"] for a in row["axioms"]})
        policies=[p for p in policy.POLICIES.values() if policy.policy_hash(p)==obj["inputs"]["policy"] and p["gate"]=="accepted_and_proved"]
        if len(policies)!=1 or any(policy.classify_axiom(a,policies[0])!="allowed" for a in baseline_axioms+actual_axioms):
            fail("INADMISSIBLE_AXIOM","readable baseline/support axiom inventory violates exact registered strict policy")
        if canonical.digest_json(baseline_axioms)!=obj["support_axiom_baseline_hash"] or actual_axioms!=obj["actual_support_axioms"] or not set(actual_axioms)<=set(baseline_axioms):
            fail("INADMISSIBLE_AXIOM","readable actual support axioms differ from frozen admitted baseline")
        for i,row in enumerate(obj["support_declarations"]):
            path=f"readable/kernel-records/{i}.json"
            if row["kernel_record"]["path"]!=path:
                fail("INVALID_CANDIDATE","readable kernel record inventory is redirected or unordered")
            mandatory.add(path)
            c=canonical.loads(read_bytes(path))
            if ref(path,read_bytes(path))!=row["kernel_record"] or name_str(c["name"])!=row["name"] or c.get("module")!=[T.GOAL_MODULE]:
                fail("INPUT_MUTATION","readable declaration differs from exact exported kernel record")
            if row["identity_hash"]!=canonical.digest_json({k:v for k,v in row.items() if k!="identity_hash"}):
                fail("INPUT_MUTATION","readable declaration inventory identity changed")
            if c.get("kind")!=row["kind"] or c.get("safety")!="safe" or c.get("level_params") or c.get("unresolved_constants"):
                fail("INADMISSIBLE_AXIOM","readable declaration record kind/safety/levels/unknown mismatch")
            th=canonical.digest_json(canon(c["type"],[]))
            bh=canonical.digest_json(canon(c["value"],[])) if c["kind"]=="definition" else None
            refs=sorted(constants(c["value"])) if bh else sorted(name_str(a) for a in c["value_constants"])
            if th!=row["type_hash"] or bh!=row["body_hash"] or refs!=row["body_constants"] or sorted(constants(c["type"]))!=row["type_constants"] or sorted(name_str(a) for a in c["axioms"])!=row["axioms"]:
                fail("INPUT_MUTATION","readable exported declaration identity/reference inventory changed")
            proof=row["proof_identity"]
            if proof["regenerated_source_hash"]!=obj["selected_goal_hash"] or proof["module_parts_hash"]!=obj["support_module_parts_hash"] or proof["type_hash"]!=th:
                fail("INPUT_MUTATION","readable module-bound proof/definition identity changed")
            if (bh and proof["exported_body_hash"]!=bh) or (not bh and (proof["direct_value_constants_hash"]!=canonical.digest_json(refs) or proof["axiom_inventory_hash"]!=canonical.digest_json(row["axioms"]))):
                fail("INPUT_MUTATION","readable proof identity redirects actual exported value references")
        mapping={"source_block_hash":"readable/source-block.lean","typed_ir_hash":"readable/typed-ir.json",
            "correspondence_hash":"readable/correspondence.lean","selected_goal_hash":"readable/selected-goal.lean",
            "compiled_inventory_hash":"readable/compiled-inventory.json","support_declarations_hash":"readable/declarations.json",
            "equalities_hash":"readable/equalities.json","dependency_inventory_hash":"readable/dependencies.json","axiom_inventory_hash":"readable/axioms.json"}
        if any(out.get(p)!=s["checked_descriptor"][k] for k,p in mapping.items()) or s["checked_descriptor"]["goal_module_parts_hash"]!=obj["support_module_parts_hash"]:
            fail("INPUT_MUTATION","readable selected artifacts differ from kernel-qualified frozen inventory")
        if canonical.loads(read_bytes("readable/declarations.json"))!=obj["support_declarations"] or canonical.loads(read_bytes("readable/compiled-inventory.json"))!=obj["compiled_inventory"]:
            fail("INPUT_MUTATION","readable manifest redirects declaration/function inventory")
    if set(out)!={R.MANIFEST_PATH,*mandatory}:
        fail("INVALID_CANDIDATE","readable manifest omits/adds fixed subordinate artifacts")
    return out
