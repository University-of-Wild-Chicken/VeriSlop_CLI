# Tier 2 pipeline and restricted-source closure

**Status: implemented for the admitted Tier 2 restricted-source profile.** The CLI now dispatches generation, linking, semantic acceptance and complete mechanical closure to VSCore, with separate review release gates. Bounded increment and independent [checked subtraction](../examples/vscore-subtraction/README.md) are complete fixtures. Each actual `END_TO_END_VERIFIED` result still requires the exact frozen instance to pass its registered checks; implementation status alone is no evidence. Tier 3 and Tier 4 remain unsupported.

The finite release regressions are in `tests/test_vscore_pipeline.py`, `tests/test_vscore_closure.py`, `tests/test_vscore_review.py` and `tests/test_vscore_subtraction.py`. `formal/ClosureModel*.lean` supplies a design model, with finite admission/lifecycle conformance checks in `tests/test_closure_model.py`; its theorems do not prove the Python pipeline, hashes, isolation or provenance implementation correct.

The deliverable is one working pipeline from an accepted contract to a delivered `vscore/0.1` source artifact, with finite mechanical closure at `restricted_source`. The existing VSCore parser, evaluator, adapters, generated refinement goal and registered semantic checker are reused. The new work is dispatch, complete frozen claims and roots, lifecycle evidence, clean rebuild integration, reporting and release orchestration.

This specification follows the repository's [frozen closure and trust requirements](specification.md#10-frozen-closure-package-and-trust): a `VERIFIED` mechanical result means every required frozen claim passed its assigned registered verifier on the exact frozen inputs under the declared trusted computing base. It does not mean unrestricted application correctness. The detailed repository baseline remains [the main specification](specification.md), [the obligation states](obligation-states.md), [implementation notes](implementation.md) and [the Tier 2–4 design](tier-2-4.md).

## 1. Scope and admission

The first complete backend has the descriptor `verislop.backend.vscore/0.1`, with exactly:

- bridge tier `2`, target `vscore`, endpoint `restricted_source`;
- language `vscore/0.1`, semantics `vscore-semantics/0.1` and relation template `vscore.reference_refinement/0.1`;
- one delivered source file, one selected prepared bridge, one `restricted_source` node and one direct semantic edge from its imported `accepted_contract` node;
- the existing pinned Lean toolchain and exact registered strict acceptance policy;
- mathematical `Nat`, `Bool`, `Unit`, accepted finite enumerations and nested `Result`; no additional source constructs;
- functional postconditions, pure value invariants, pure safety properties and explicit error semantics in the accepted contract DSL, using the existing transfer rule.

Every program entry MUST bind one-to-one to an accepted function symbol. Every implementation symbol called by a covered formula MUST have a binding. The program may bind additional accepted function symbols, but every additional entry still needs its own total refinement conjunct; there are no unverified helper entries. The accepted reference may use internal pure definitions without separate target entries when the direct refinement theorem proves the complete referenced function.

The covered guarantee set is exactly every required guarantee for which the base lifecycle makes implementation milestones applicable. Derived `non_vacuity` obligations are excluded from that implementation set but remain required contract witness checks. This first pipeline profile offers no guarantee-subset selection, accepts no alternative competing bridges, and composes no semantic edges. Existing advisory `vscore goal --obligation` remains usable during bridge development, but its output cannot bypass complete required coverage in the pipeline. Optional guarantees remain visible with their actual outcomes; they do not receive E2E evidence from inclusion of a similarly named required guarantee. A later profile may add explicit optional-guarantee selection.

Admission MUST reject an unsupported required guarantee before invoking an implementer. Examples include opaque `lean_expr` statements, formulas with no implementation symbol, calls inside range bounds, reactive liveness and physical-resource claims. They remain applicable and `UNSUPPORTED`; absence of a supported translation is not `NOT_APPLICABLE`. A statement about arithmetic quantities does not acquire a physical-time or memory interpretation because its obligation is labelled a resource constraint.

Assumptions remain explicit hypotheses with their accepted suppliers and discharge locations. The implementation may not strengthen them. The current refinement template proves equality for every value of the accepted argument types, so a candidate cannot insert a narrower domain into its refinement goal. There is no machine-width conversion of unrestricted `Nat`.

The endpoint comprises the exact source bytes, their normative Lean decoding, checked types, actual representation adapters, evaluator result and transported accepted properties. It excludes any host interpreter, ordinary Lean code generation, VM, compiler, linker, loader, operating-system service or native executable that might later execute the source. General state, sequences, loops, entry-to-entry calls, I/O, concurrency, fairness, constant-time claims and physical resources remain unsupported. These exclusions MUST appear in every successful report and review packet.

## 2. A small backend boundary

Add a supervisor-owned backend registry. Selection uses the frozen tuple `(tier, target, endpoint, backend_version)`; neither filename extensions nor a candidate-provided verifier name select executable behavior. `capabilities` and the registry MUST use the same descriptor. Unknown versions or incompatible tuples fail closed.

The registry supplies the following operations. These are proposed internal interfaces, not existing callable APIs:

```text
admit(accepted_contract, resolved_parameters) -> Admission
materialize(accepted_contract, candidate_snapshot, admission) -> Materialization
link(accepted_contract, materialization, frozen_selection) -> LinkRecord
test(frozen_snapshot, campaign) -> CampaignResult | Unsupported
clean_build(frozen_snapshot, label) -> BuildObservation
check_endpoint(frozen_snapshot, checked_builds, checked_claims) -> EndpointAssessment
implementation_refs(checked_link_record) -> obligation-to-object references
```

`accepted_contract` contains the revalidated accepted IR, acceptance certificate, profile, accepted formula packages and declaration inventory. It is not the original interpreted JSON. `candidate_snapshot` contains exact bytes and proposed bindings, never accepted states. Each returned object has a closed versioned schema, input bindings and a finite diagnostic list. A backend operation cannot assign its own claim ID, root kind, verifier identity or pass predicate: the frozen supervisor inventory supplies them.

Keep Python Tier 0/1 behavior behind a Python backend adapter. Remove target-specific branching from the shared orchestration after dispatch: VSCore MUST NOT reach `python_target.inventory`, Python byte compilation, the Python harness, Python result serialization or Tier 1 monitor generation. Target-specific rendering is also dispatched; `view._implementation_refs` must not assume `file/qualname/source_hash` objects.

Register these proposed producers with their complete runtime/schema dependency hashes:

- `verislop.vscore-materializer`: `IMPLEMENTED`; a kernel-checked exact-byte parse/typing result and reconstructed entry inventory.
- `verislop.vscore-linker`: `LINKED`; unique structural bindings, accepted declaration identity, complete required coverage and the actual adapter/profile identity.
- existing `verislop.vscore-checker`: the internal semantic-edge claim only, using its existing template; it still does not publish lifecycle E2E evidence.
- existing `verislop.closure`: final clean-build, determinism, provenance, endpoint and per-obligation E2E claims.

No VSCore test verifier is registered in this milestone. The testing operation has the explicit unsupported behavior in §8. Registry entries must hash imported helper modules, the dispatcher, the relevant schemas, the Lean library, goal generator, expression exporter, policy, kernel tool and environment-binding code. Updating any of these invalidates dependent evidence; a package cannot select an older implementation hash merely to preserve a pass.

## 3. Candidate acquisition and materialization

There are two equivalent inputs to `generate` for this backend:

1. A candidate directory containing exactly the semantic inputs `program.vscore.json`, `relation.json` and `Proof.lean`. The relation uses the existing `vscore-source` and `vscore-proof` slots. Files from `vscore goal` such as `proposal.json`, `model.json`, `profile.json` and a displayed goal may be present as advice; the supervisor re-derives them and rejects a conflicting selected proposal rather than trusting it.
2. An explicitly selected prepared bridge in the same run, identified by `--bridge-id`. The supervisor revalidates its import, plan, artifacts and exact admission scope before adopting it. No automatic choice among discovered directories is permitted.

Candidate directory and prepared-bridge selection are mutually exclusive. For the first route the default bridge ID is `implementation`; an explicit `--bridge-id` names the new bridge only when `--candidate` is also given. The implementation must distinguish those modes in argument validation. Existing `run --bridge-proposal --bridge-candidate-dir` becomes an explicit preparation input that is adopted by its proposal ID; it cannot be combined with a separate implementation candidate.

For both routes the supervisor derives the covered obligations, revisions and statement hashes; model/profile descriptors; source and proof byte identities; relation assignment; exact goal and expected proposition hash. A supplied proposition hash is only a proposal and MUST equal the independently derived hash. Selected bridge obligations MUST match the required guarantee set exactly.

Source and proof search happens before freezing the chosen implementation candidate. Each attempt is bounded and retained separately. A failed proof search can leave a source materialized and structurally linked, but cannot create a semantic acceptance. Once the selected bridge and implementation claims are frozen, changing source, proof, bindings, tier, endpoint, test policy or guarantee coverage requires a new implementation candidate in a new run package. `resume` continues checks of unchanged inputs; it is not an in-place repair command.

`materialize` uses the existing goal build without the candidate proof to kernel-check source parsing and typing. It re-exports the entry/type inventory from replayed declarations. That inventory establishes well-formed artifact existence, not refinement. Candidate proof failure must not be reported as failure of a separately established `IMPLEMENTED` fact.

Publish `implementation/program.vscore.json` as an exact-byte copy of the selected bridge source. Its byte equality is a required binding, checked again during closure; neither copy may silently become authoritative over the other. The proof, generated goal, descriptors and certificates remain in the bridge bundle. The first profile permits no other executable source file under `implementation/`.

## 4. Versioned implementation artifacts

Preserve all current contract, VSCore language and semantic-edge formats at their current versions. Introduce separate strict `0.2` implementation-phase formats; do not widen the meaning of an existing Python-only `0.1` record. New documents use `schema_version: "0.2"` and a `format` discriminator:

- `verislop.implementation-claims/0.2` at `closure/implementation-claims.json`;
- `verislop.implementation-bindings/0.2` at `bridges/bindings.json`;
- `verislop.link-record/0.2` at `bridges/link.json`;
- `verislop.closure-plan/0.2` and `verislop.closure-manifest/0.2` at `closure/plan.json` and `closure/manifest.json`;
- `verislop.mechanical-result/0.2` and `verislop.run-report/0.2` for immutable mechanical results and their current run rendering.

All new schemas are closed. Missing version fields do not mean VSCore; they select only the explicit legacy reader in §11. Retain current `artifact_kind` values where existing readers require them, but require the new format and backend discriminators for `0.2`.

Implementation parameters are a closed record containing `tier`, `target`, `endpoint`, `backend`, `language`, `semantics`, `require_state`, `require_tests`, `bridge_id` and `tier_default_applied`. For this backend, the language and semantics fields replace the Python serialization profile. The endpoint is normalized to `restricted_source` before hashing. Missing Tier 2 `require_state` resolves to `END_TO_END_VERIFIED`; requesting `TESTED` adds the independent test requirement rather than weakening endpoint closure.

The binding proposal contains `backend`, the exact accepted IR hash, selected bridge ID, source slot and an array of `{binding_id, symbol, entry}`. The supervisor derives obligation lists. It checks a bijection between program entries and relation bindings, and exact argument/result sorts against accepted declarations.

The checked link record additionally includes the source path and hash, decoded program hash, materialization inventory hash, accepted declaration/hash/signature, actual adapter/profile hash, selected bridge/node/edge identities, plan/artifact hashes, and covered `{id, revision, accepted_statement_hash}` records. It states `correspondence: structural`; only the separate semantic edge establishes refinement. Function references render as `vscore:<source-path>#entry/<entry-id>@<source-hash>`, with escaped components. Required declaration objects use explicit accepted type/enum/adapter references instead of invented function entries.

The final `implementation-ir.json` remains the existing VSCore implementation-IR format and stays paired with its semantic certificate. It is reconstructed from replayed `sourceBytes`, `rawProgram`, `signatures` and `profile` declarations. The materialization inventory and the candidate AST never substitute for this accepted implementation IR. Closure requires the rebuilt IR to match both the stored accepted IR bytes and the exact source re-encoding.

## 5. Lifecycle applicability and the frozen claim graph

Retain all eight symbols and their [existing prerequisites](obligation-states.md#2-milestones-form-a-dependency-graph). In particular, `END_TO_END_VERIFIED` requires `PROVED`, `IMPLEMENTED` and `LINKED`; it does not require `TESTED` unless the frozen release policy independently requires a campaign. This is the existing lifecycle rule, not an exception introduced for VSCore.

- Required implementation guarantees have applicable `IMPLEMENTED`, `LINKED` and `END_TO_END_VERIFIED` claims. A missing symbol, unsupported formula or absent proof is a blocked/unsupported applicable claim, not a reason to erase it.
- Required declarations that participate in the interface have applicable materialization/link claims for their types, constructors and adapters. Required declarations outside the representable profile block admission. Their `PROVED`, `TESTED` and E2E states remain `NOT_APPLICABLE` as in the base lifecycle.
- Assumptions, exclusions and open questions retain the base applicability rules. An unresolved question may still block dependent guarantees. Assumptions must appear in the final hypothesis inventory.
- Non-vacuity remains a contract-only witness obligation, including concrete accepted success/error witnesses where required. It never receives an implementation or E2E pass.
- Omitted applicable tests remain `PENDING` with the reason `campaign not required by frozen policy`; proof acceptance cannot create `TESTED` evidence.

The new implementation-claim format retains IDs such as `IMPLEMENTED:O17@1` and adds explicit `root_kind`, `result_predicate`, `premises`, `scope` and `trusted_dependencies`. Every claim has one assigned `verifier`, one typed predicate, exact obligation/revision or null for an internal claim, and frozen requiredness/applicability. Free-form `pass_predicate` text is explanatory only. Claim IDs, typed predicates and premise edges are derived by the supervisor, then frozen before execution.

Keep the four final claim IDs, with precise meanings:

- `CLOSURE:clean-builds`: two complete isolated builds succeeded from the frozen contract and VSCore inputs.
- `CLOSURE:determinism`: both builds reproduce the expected contract/implementation artifacts, inventories, correspondence, provenance inputs and non-final claim outcomes.
- `CLOSURE:provenance`: all required non-final claims have current assigned evidence, every frozen public claim has a complete planned provenance path, every relevant dependency is classified, and the final output plan is complete.
- `CLOSURE:endpoint`: the selected direct registered edge covers the complete required guarantee set, its source is the delivered artifact, and the exact `restricted_source` boundary and representations hold.

The graph contains all contract claims, required declaration materialization/link claims, the structural preparation claim, the semantic edge and the implementation milestones. Required internal claims with no obligation ID are evaluated normally. The structural claim is a premise of the semantic edge, but a structural `PASS` cannot satisfy its semantic predicate. No generic `milestone-pass` result may discharge a new semantic or closure predicate.

For each covered guarantee, the E2E claim depends on its exact accepted proof, applicable materialization/link claims, the selected semantic edge and all four final closure claims. Required tests, if admitted by a future campaign backend, are additional ordinary premises. The verifier computes each E2E outcome from those prerequisite outcomes; it never asks for a pre-existing E2E record. A successful record remains staged until **all required mechanical claims in this closure**, including the staged final claims, pass complete final validation. Optional unrelated guarantees do not become required accidentally.

The four final claims and E2E claims are produced in a terminal evaluation phase, not consumed as prerequisites of their own verifiers. In particular `CLOSURE:provenance` does not require the not-yet-produced E2E record or its own record. Its planned provenance edges are validated first; after terminal records are produced, the supervisor validates the complete output graph and publishes the result atomically. Missing or inconsistent terminal outputs prevent a `VERIFIED` publication. This removes the existing temptation to either require final evidence too early or exempt every `CLOSURE:*` claim.

## 6. Roots and the closure plan

Let `H(bytes)` mean SHA-256 over exact stored bytes, and `J(object)` mean SHA-256 over the repository's canonical JSON encoding. File reformatting changes `H`. No hashing rule strips whitespace, resolves an alternate path, or uses a supplied digest in place of reading the selected file.

Freeze `implementation-claims.json` and a supervisor selection record before publishing materialization/link evidence. The selection identifies the backend descriptor hash; accepted IR/certificate/profile/statement-inventory hashes; selected bridge ID, source and endpoint nodes, edge and claim IDs; exact plan/artifact hashes; source/proof/relation/model/profile slots and hashes; covered obligation revisions/statements; test policy; and build policy. It has no self hash and contains no outcomes.

The new root definitions are:

```text
implementation_root = J({
  format: "verislop.vscore-materialization-root/0.1",
  selection_hash, implementation_claims_hash,
  delivered_source_hash, backend_descriptor_hash
})

link_root = J({
  format: "verislop.vscore-link-root/0.1",
  implementation_root, bindings_hash, materialization_inventory_hash
})

closure_root = J({
  format: "verislop.closure-root/0.2",
  closure_id, plan_hash, manifest_hash,
  verifier_registry_hash, schema_registry_hash, tcb_hash
})
```

The materialization inventory is an output of the implementation-root check and an input to linking; the link record is not an input to its own link root. The existing semantic-edge root retains its registered definition over the exact bridge plan, artifact manifest and selected edge. The root names in claims are selected by these phase rules; evidence may only repeat them as consistency assertions.

`closure/plan.json` contains exactly: format/version, `closure_id`, the resolved backend/endpoint tuple, selection reference/hash, claim-inventory references/hashes, the sorted expanded claim IDs and premise graph, public-claim mappings, test policy, build recipe and resource limits, expected reproducible output slots, permitted nondeterministic fields, selected verifier IDs/hashes, schema IDs/hashes and TCB reference/hash. Output slots identify their assigned producer and expected format; they do not contain their future output digest. This plan has no own hash, manifest hash, outcomes or final report reference.

`closure/manifest.json` contains exactly its format/version, closure ID and sorted unique `{path, role, size, sha256}` entries. Include the exact plan bytes, all frozen contract sources/proofs/challenges/policies, accepted contract artifacts/IR/expression packages/witness inputs, imported contract receipt, complete selected bridge input manifest, source/proof/relation/model/profile bytes, delivered source, binding/link/materialization inputs, pre-existing semantic certificate and its complete artifact/evidence inventory, resolved test policy, toolchain/dependency locks, verifier/schema/TCB snapshots and any configuration that affects mechanical checks. Verifier/toolchain identities include their transitive relevant files, not just human-readable version names. Membership is checked as well as individual hashes.

Pre-existing certificate metadata is an input to compare against fresh execution, never a substitute for executing the checker. Its input/output references, theorem identity, coverage, declared builds and IR must agree with the rebuilt result. This includes fields that do not affect the manifest root themselves but make public correctness claims.

Closure build logs, newly generated evidence, mechanical/release results, reviews, transcripts, mutable package indices and event timestamps are not closure inputs. They live in declared output locations. If an earlier evidence record is actually consumed as an input, its exact record and raw result must instead be enumerated in the manifest. This rule prevents an unlisted output from becoming a hidden input and avoids self-referential hashes.

The TCB snapshot separately names the pinned Lean kernel and allowed axioms, pinned standard-library import closure, executed kernel/export tools, codecs and host orchestration, hash implementation, sandbox/OS and hardware. Natural-language-to-contract fidelity remains a declared interpretation boundary. The VSCore normative semantics define the endpoint; the correspondence to those semantics is proved, not silently listed as trusted. Required translation edges cannot be waived by adding them to the TCB.

The frozen closure ID is unique within a run. An interrupted infrastructure attempt on the same inputs may use a new execution attempt ID; changing any mechanical claim, source, proof, mechanical policy or registered dependency requires a new closure ID and new run package. A change confined to reviewer configuration invalidates its separate release target as specified in §10. Old reports remain historical results for their roots.

## 7. Two fresh builds and finalization

`verify` MUST dispatch to the backend's complete clean-build operation. A Python byte-compilation success, a previously stored build record or two imports of one cached `.olean` cannot satisfy this claim.

Build A and build B each start in a separate fresh directory from the same frozen snapshot and pinned environment. Each performs all of the following:

1. Compile the original accepted contract source, replay its complete declarations, check frozen statements/definitions/axioms/witnesses, reconstruct accepted contract IR and require equality to the selected accepted artifacts. Use this freshly rebuilt module in subsequent steps.
2. Compile all verifier-owned VSCore library modules from their frozen sources. Derive the model/profile and goal from the accepted contract and exact source bytes. Kernel-check parse/typing equations, adapters and input coverage.
3. Compile the candidate proof and independently replay the library, fresh contract, goal and proof together. Check import closure, complete inventories, exact goal/theorem identity, allowed transitive axioms, total refinement and every transferred obligation.
4. Re-export the implementation IR from replayed declarations. Reconstruct the complete entry/binding/adapter inventory and exact obligation coverage. Check equality to the delivered source and to all pre-existing certificate/output claims.
5. Recompute the non-final claim outcomes and deterministic provenance input graph. Execute any admitted required campaign; this milestone admits none. Record all observations with the closure root and registered producer identity.

The build policy includes the accepted policy's existing per-process time/memory limits and a total wall-clock bound per build. The initial default total is 1,800 seconds per build; there are exactly two required builds and no unbounded verification retry loop. Agent proof search has its own finite budget and is not a clean build. Tightening a budget may block an attempt; weakening the accepted proof/import/axiom policy is not permitted.

Compare, between A and B and against applicable accepted expectations: contract module parts and environment export, accepted IR and witness inventory, VSCore module parts, generated goal bytes and proposition/declaration closure, proof inventory and axiom list, source/decoded-program/type inventory, implementation IR, actual adapter/binding records, obligation transfer identities, semantic certificate semantic fields, non-final claim outcome set, correspondence and provenance input graph. Freeze this comparison projection in the plan; an absent expected output is a failure, not an omitted comparison.

Only execution timestamps, elapsed durations, execution attempt/evidence IDs and normalized temporary-directory locations may vary. Their semantic payloads and all artifact bytes remain compared. Do not drop arbitrary fields named `time` or `id` recursively. Scope each excluded path in the build schema before execution.

The standalone `bridge accept` result remains useful but its earlier builds do not replace closure builds. The initial implementation may therefore perform two semantic-acceptance builds and then two complete closure builds. This is deliberate: closure additionally rebuilds the accepted contract from source and checks final dispatch, delivery, coverage and provenance. Optimization may reuse work only inside one current registered execution with identical frozen inputs and the same full build recipe, never by accepting package-supplied success records.

After evaluating the non-final claims, compute the four final verifier outcomes and stage their records from the checked observations. Then compute and stage the per-guarantee E2E outcomes from their exact prerequisite records, bound to `closure_root` and scoped `restricted_source; vscore/0.1`. Validate the complete staged claim/evidence/provenance graph, including these new records and every required output. No stage consumes its own outcome as a prerequisite.

Only now apply the mechanical decision in this order: infrastructure failure; any required claim not `PASS`; undeclared dependency; unresolved correspondence; invalid/missing witness; failed clean build; nondeterminism; incomplete provenance; otherwise `VERIFIED`. Atomically publish the staged E2E PASS records only with a successfully validated `VERIFIED` mechanical result, then derive the view from that committed inventory. Failed final validation or publication must not expose staged E2E PASS as current evidence; preserve diagnostics and ordinary valid evidence without promoting the failed attempt.

Publish an immutable mechanical result and complete evidence inventory together. A current `report.json` may point to it but cannot replace it as evidence. `resume`, standalone `verify` and any path that would present current E2E success must execute the relevant semantic/closure checks again from current bytes; historical outcomes may be displayed as historical without implying a fresh pass. A stored lifecycle flag, completed-stage index or matching digest alone is insufficient.

## 8. Optional tests

Tier 0 retains mandatory tests; Python Tier 1 retains its current default. For the new Tier 2 profile, omitted test flags resolve to `require_tests: false`. Add mutually exclusive `--require-tests` and `--no-tests` to both `run` and `generate`, and preserve the resolved Boolean through `resume`. An explicit `--require-state TESTED` requires tests; combining it with `--no-tests` is `CONFIGURATION_INVALID`.

There is no VSCore execution-campaign backend in this milestone. Therefore:

- A Tier 2 run with tests not required skips the campaign stage, keeps applicable `TESTED` outcomes `PENDING`, and can reach mechanical E2E closure after its independent required claims pass.
- A Tier 2 request with tests required is rejected at admission with `UNSUPPORTED_CAPABILITY`, before agent work. It cannot silently drop the requested campaign.
- An explicit `verislop test` on a Tier 2 package reports `UNSUPPORTED`/`UNSUPPORTED_CAPABILITY`, creates no test PASS and calls no Python harness. The diagnostic concerns that separate test request; it does not invalidate a correctly bound proof already established for an unchanged closure whose test policy omits tests.
- Parser examples, kernel reductions, proof attempts and build reproducibility checks are verification checks, not a property-test campaign and not `TESTED` evidence.

Thus `END_TO_END_VERIFIED: PASS` and `TESTED: PENDING` is intentional and valid: one is a proof-backed endpoint claim, the other records whether an independent campaign ran. The report must display both. If a later release configuration adds required tests, it requires a new frozen policy/closure and cannot reuse the old result as satisfying that new requirement.

## 9. CLI and pipeline behavior

The commands in this section describe the implemented Tier 2 workflow for the admitted profile. Unsupported required obligations, campaigns and stronger endpoints still block admission.

For a run whose contract is already accepted, the manual workflow is:

```sh
verislop generate --package RUN --tier 2 --target vscore \
  --endpoint restricted-source --require-state END_TO_END_VERIFIED --no-tests \
  --candidate examples/vscore --bridge-id implementation
verislop link --package RUN
verislop bridge accept --package RUN --bridge-id implementation
verislop verify --package RUN --endpoint restricted-source \
  --require-state END_TO_END_VERIFIED
```

`generate` derives and prepares the bridge in this workflow; no manually copied hash is necessary. Existing `vscore goal`, `bridge prepare`, `bridge accept` and `bridge verify` remain available for separate bridge development. To adopt an already prepared bridge, use `generate ... --bridge-id ID` without `--candidate` or `--bindings`. An existing Python-style `--bindings` proposal is invalid for this backend; bindings come from the selected VSCore relation.

The one-command release fixture is:

```sh
verislop run --runs-dir .verislop/runs --run-id bounded-vscore \
  --prompt-file examples/request.txt --request-ref examples/request.txt \
  --tier 2 --target vscore --endpoint restricted-source \
  --require-state END_TO_END_VERIFIED --no-tests \
  --draft-candidate examples/draft.json \
  --ledger-candidate examples/interpretation.json \
  --formalization-candidate examples/formalization \
  --implementation-candidate examples/vscore --non-interactive
```

With no bridge ID argument, this pipeline selects `implementation`. Use `run --bridge-id` for an explicitly named new candidate; it must agree with a supplied bridge proposal ID. Capability rejection happens before generation; the command never silently changes tier, target or endpoint.

The Tier 2 stage order is:

```text
interpret → configured interpretation review
→ formalize/freeze → prove → accept → export
→ configured formal-contract review
→ generate/materialize → link → bridge accept
→ configured implementation review
→ campaign skipped by admitted policy (TESTED PENDING)
→ freeze closure → mechanical verification and snapshot
→ configured release review → release finalization → report
```

There is one implementation selection for the run, frozen in the implementation claim inventory. Package metadata may index it for navigation but cannot remove it from closure or redirect verification. Every selected bundle must be accounted for even if an index is absent. `_proceed`, resume validation and status rendering use backend stage results and current checked artifacts, not Python file existence conventions.

Every failed or interrupted pipeline produces a report with completed evidence and unresolved claims. A source may remain `IMPLEMENTED` or `LINKED` when proof search fails. It cannot acquire E2E because the pipeline proceeded to reporting. `bridge accept` and `bridge verify` alone continue to assign no lifecycle E2E state.

## 10. Agents and independent review release gates

Reuse the existing providers, credential references, broker, agent assignments, counts and user-configured review tiers. No new provider service or live call is required to validate the implementation. Review tiers remain unrelated to bridge tier `2`.

Make the implementer role target-aware. For VSCore it receives accepted IR, exact accepted formula packages, accepted profile/declaration identities, source grammar, supported feature limits, relation format and frozen parameters. It proposes source and relation; the supervisor generates the exact Lean goal. The configured prover may then propose `VeriSlopBridgeProof.edge` against that goal in a separate candidate attempt. The implementer may supply an initial proof, but neither role supplies authoritative goal hashes, imported contracts, evidence, lifecycle fields or final IR. Send bounded checker diagnostics to subsequent attempts, preserving the fixed target.

Review packets for implementation/release contain the checked link inventory, exact source, generated goal, semantic certificate, re-exported implementation IR, accepted assumptions/witnesses, proof/build outcomes and the scoped endpoint boundary. They must not retain the current blanket wording that all implementation assurance is Python testing.

Mechanical closure and release approval are separate fields:

- `mechanical_status` is exactly `VERIFIED`, `BLOCKED` or `INFRASTRUCTURE_FAILURE` and controls mechanical E2E evidence.
- `release_status` is `NOT_REQUIRED`, `ACCEPTED`, `BLOCKED` or `INFRASTRUCTURE_FAILURE`, derived from the frozen configured checkpoints and their current consensus results.
- The existing terminal status is `VERIFIED` only when mechanics are verified and release is accepted/not required. A rejected or missing required review makes the terminal status `BLOCKED`; an unavailable required review service makes it `INFRASTRUCTURE_FAILURE`. Neither rewrites valid mechanical E2E evidence to failure.

Release review runs only after a mechanical snapshot exists. Distinguish two inventories: the **exact execution inventory** retains every selected evidence record, raw result, log and output with its path and exact byte hash; the **deterministic review projection** records the checked meaning of that execution. The raw inventory is independently validated and retained for each execution. Its digest is not substituted for the projection digest in the review target, because fresh timestamps and evidence IDs legitimately change the raw digest.

Define the closed projection format `verislop.review-mechanical-projection/0.1`. It contains `closure_id`, `closure_root`, `mechanical_status`, `backend`, `endpoint`, `normalizer_registry_hash`, sorted required claim IDs, and a sorted claim array. Each projected claim contains its exact claim ID, premise IDs, obligation/revision/statement identity when applicable, assigned verifier ID/hash, root kind and input root, typed predicate/result-format ID, outcome/status/exit code, complete typed semantic result, scope, declared trust, execution-environment identity and normalized invocation. Include the complete correspondence, witness and deterministic A/B comparison results. A separate sorted artifact array retains stable role/producer/relative-path identities, sizes and **exact nonvolatile artifact hashes**, including source, modules, goal, IR, adapters and bindings. A certificate envelope that contains volatile evidence references has both its exact envelope in the raw inventory and its complete checked semantic payload in the corresponding projected claim result; a payload digest is not represented as the exact byte hash of that envelope.

Each registered result format supplies a versioned, hashed normalizer before review begins. The normalizer validates its complete raw schema and maps every field either into the typed semantic payload or into one of the explicit execution metadata paths below. Unknown fields, unmapped data, an unavailable normalizer or a changed normalizer hash block reuse. Existing `0.1` evidence needs an explicit registered adapter to this format; it cannot use an ad hoc dictionary filter. A dependency's changing evidence reference maps to its stable claim ID, assigned issuer and root plus the corresponding projected claim, after validating the original exact reference. This changes the reference representation without discarding the dependency.

The normalized envelope used by this projection has `record`, `raw` and `execution` objects. The only excluded JSON Pointer paths are:

- `/record/evidence_id`, `/record/raw_result_ref` and `/record/raw_result_hash`;
- `/raw/sequence` and `/raw/recorded_at` from the evidence-store wrapper;
- `/execution/attempt_id`, `/execution/started_at`, `/execution/finished_at`, `/execution/wall_ms` and `/execution/work_directory`.

The `execution` object is closed to exactly those fields. Fields from current producer formats may reach it only through the normalizer's explicit source-path mappings frozen with its schema/hash; fields elsewhere named `id`, `time`, `sequence` or `path` are not excluded. Semantic result fields have no general exclusion mechanism. In invocation arguments and environment fields, a temporary/package path may be converted to a frozen logical input/output-slot reference only at schema-declared path positions and only after validating the concrete path and artifact binding. Retain all other execution-environment fields, including toolchain/runtime/OS identities and verifier/isolation settings; a meaningful environment change changes the projection. Do not recursively omit fields by name or normalize arbitrary text by string replacement.

The reviewer configuration is redacted only for secrets and includes membership, counts, consensus policy, agent assignments and endpoint-profile identities. Before generating the target or requesting any ballot, freeze a model-resolution manifest. For a pinned immutable model, or a provider that supports prior resolution, record and bind the resolved model identity then; returned identities must satisfy that frozen expectation. Otherwise record the configured alias, provider/endpoint identity and an explicit trust statement that the provider selects the model at request time. A policy that requires a fixed snapshot must reject this unresolved-alias mode before review. Observed model IDs remain in the ballots and execution provenance and are checked against this admission policy. Identities first learned from ballots MUST NOT be inserted into those ballots' own target; choosing a different identity policy starts a new campaign.

The review target is the canonical hash of exactly:

```text
{
  format: "verislop.review-target/0.2",
  checkpoint, closure_root, mechanical_projection_hash,
  reviewer_configuration_hash, model_resolution_manifest_hash
}
```

Review outputs, transcripts, ballot timestamps, raw execution inventory digests and the final release report are excluded from that target. The campaign still binds and retains the exact original packet/raw-inventory digest as audit provenance alongside the target. Changing the projected semantics, artifact bytes, environment, reviewer policy or frozen model-resolution policy invalidates the relevant consensus even if the source root is unchanged.

During a single `run`, finalization rechecks that all frozen inputs still match the mechanically checked snapshot before applying consensus. A standalone `verify` performs fresh mechanical checks and can report `mechanical_status: VERIFIED`, `release_status: BLOCKED` with `REVIEW_NOT_RUN`. The user may then run `review --checkpoint release --config CONFIG` and `verify` again. Reuse requires validation of both the original and current exact execution inventories, fresh registered execution for the current result, and byte equality of their canonical projections under the same normalizer version/hash. The final report records both raw-inventory digests and the shared projection/target digest. Only the explicitly excluded execution metadata may differ; a fresh semantic mismatch or changed nonvolatile artifact invalidates reuse. Matching projections alone cannot authorize mechanical success without those fresh checks.

Every required internal mechanical claim participates in release readiness. `PENDING`, `STALE`, `UNSUPPORTED`, failed and missing claims cannot be hidden by a review checkpoint that looks only at user-obligation rows. Unanimous votes do not discharge them. Conversely, review rejection may request a new candidate while the old candidate's current proof remains a true historical/mechanical result.

The current Python repair path must not rewrite a frozen VSCore bundle. A source/proof repair creates a new candidate/run and restarts the affected review hierarchy on its new root; reuse of an unchanged formal-contract result is allowed only through the normal accepted-contract replay and matching checkpoint identity. There is no in-place weakening of an accepted obligation or a manual conversion of `BLOCKED` to `PASS`.

## 11. Compatibility, reports and capability gates

Legacy `0.1` implementation bindings/claims retain Python meaning and their existing root formulas. Add explicit format dispatch; do not reinterpret an old Python package as VSCore because `package.json` was edited. Existing Tier 0/1 regression fixtures must preserve their assurance and E2E ineligibility. Existing VSCore edge certificates remain semantic-edge certificates; adopting one into a new pipeline requires fresh admission, claims, roots and complete closure checks, not a version-label change.

The new report separates model proof, implementation proof, finite tests, assumptions and trust. It contains exact closure/backend/language/semantics IDs, roots, required/passed/unresolved claim counts, covered obligation revisions, direct edge and theorem identity, mappings and input coverage, witnesses, two build records, deterministic comparisons, complete provenance, trusted dependencies, excluded surfaces, mechanical status, release status and typed diagnostics. A successful result is rendered:

```text
VERIFIED closure; END_TO_END_VERIFIED [restricted_source; vscore/0.1]
TESTED: PENDING — campaign not required by frozen policy
```

That rendering is permitted only when the selected instance passed. Reports must not infer two passing builds from one successful build, infer semantic acceptance from the presence of a certificate, or describe an optional test campaign as executed when it was skipped. `endpoint.established` is null when the requested endpoint was not mechanically established. A mechanical success with rejected review explicitly displays `release blocked` without obscuring either fact.

`capabilities` publishes the single admitted E2E combination with tier/target/endpoint/backend/language/semantics/template, supported property fragment, limitations and `testing: unsupported`; §14 remains its finite regression gate. The internal capability/admission API checks test requirements and the complete required obligation set, not merely the numeric tier; this does not add a public CLI subset-selection option. A required campaign, unsupported obligation or stronger endpoint still blocks this combination. Tier 3 and Tier 4 remain unsupported, and no `restricted_source` result can satisfy either.

## 12. Second complete fixture

The independent `examples/vscore-subtraction/` fixture supplies a separate accepted contract and VSCore source for checked subtraction:

```text
subtractIfEnough(balance, amount) =
  if amount ≤ balance then ok(balance - amount) else error(insufficient)
```

Use a one-constructor `DebitError` enumeration and explicit `Result(DebitError, Nat)`. Required guarantees include the successful result equation under `amount ≤ balance`, reconstruction `remaining + amount = balance` after success, output bound `remaining ≤ balance`, and the exact error condition `error(insufficient) ↔ balance < amount`. Include accepted concrete non-vacuity witnesses for zero/equality success and an underflow error.

The example must be independently interpreted, formalized, accepted, reified, generated, linked, proved and closed; do not copy the bounded-increment certificate. Exercise zero, equal operands, an underflow case, and a value above `2^64`. These are fixture validation cases, not a claim that a runtime campaign exists. Negative variants subtract in the wrong order, accept equality as an error, and return the wrong result/error constructor. Each must fail its exact refinement/transfer target without narrowing assumptions.

## 13. Failure semantics

Keep claim outcomes distinct from command terminal states. Every unresolved required mechanical claim blocks; unknown verifier predicates never default to success.

- `UNSUPPORTED_CAPABILITY`: unsupported endpoint/backend combination, required campaign, property kind or feature. `UNSUPPORTED_SEMANTICS` may identify a specific unsupported required obligation in the derived view.
- `CONFIGURATION_INVALID`: contradictory flags, multiple implementation selections or a changed frozen policy.
- `INVALID_CANDIDATE` / `CANDIDATE_BUILD_FAILURE`: malformed source/relation/proof or a candidate that does not elaborate. Malformed input must produce a structured diagnostic, not an uncaught numeric-conversion exception.
- `STATEMENT_MISMATCH`, `IR_REIFICATION_MISMATCH`, `PROOF_UNRESOLVED`, `INADMISSIBLE_AXIOM`, `KERNEL_REJECTION`: the corresponding exact semantic check failed. A proof-search timeout/budget exhaustion remains unresolved (`BUDGET_EXHAUSTED`), not success.
- `UNMAPPED_IMPLEMENTATION_OBJECT`, `AMBIGUOUS_CORRESPONDENCE`, `NON_MECHANICAL_CORRESPONDENCE`, `ORPHAN_CLAIM`: missing/nonunique identities, missing transfer coverage, unknown/missing claims or incomplete provenance.
- `INPUT_MUTATION`, `CLAIM_MUTATION`, `STALE_OR_UNBOUND_EVIDENCE`: changed bytes/scope or evidence from another root, checker or policy.
- `MISSING_WITNESS`, `WITNESS_INVALID`, `UNDECLARED_DEPENDENCY`, `SCOPE_LEAK`, `UNDEFINED_BEHAVIOR_DEPENDENCY`: incomplete assumptions, witnesses or endpoint boundary.
- `CLEAN_BUILD_FAILURE` and `NONDETERMINISM`: a required build fails for a candidate reason or its declared outputs disagree.
- `REVIEW_NOT_RUN`, `REVIEW_REJECTED` and stale-review diagnostics affect release gating, not the truth of a separately current semantic proof.

Unavailable Lean, failed required isolation, filesystem failure and a crashed verifier are `INFRASTRUCTURE_FAILURE` with the operation and preserved observations. An observed counterexample or rejected theorem remains a claim failure even if another operation also suffers infrastructure failure. All diagnostics name affected claim/obligation IDs where available. No automatic downgrade or manual override is permitted.

## 14. Implementation sequence and finite release tests

Implement in this order, with capability disabled until the last step:

1. Add the backend descriptor/dispatcher and strict versioned implementation artifacts. Route existing Python paths through their adapter without changing their roots or semantics.
2. Add Tier 2 admission, candidate acquisition, proof-goal workflow, materializer and linker. Freeze selected bridge, complete applicable claims, actual bindings and roots; support independent materialization/link results before proof success.
3. Integrate the existing semantic checker and accepted implementation-IR exporter. Compare the complete published semantic result to fresh checked observations.
4. Implement the finite closure plan/manifest/TCB and two complete clean builds, typed final predicates and non-circular E2E finalization.
5. Dispatch run/resume/test/view/report, add optional-test policy, and split mechanical verification from review/release finalization. Preserve historical outputs and require fresh checks before current success.
6. Add checked subtraction and execute the finite release suite below. Then publish only the exact admitted capability.

The release suite is finite and local. It requires no provider credentials or paid inference. Each negative case must identify a frozen claim or boundary whose outcome it changes; additional subjective review rounds are not release tests.

Required cases:

1. Bounded increment completes the one-command pipeline with required guarantees at E2E, declarations with correct applicability, non-vacuity checked, two complete builds, no required unresolved claims and optional `TESTED: PENDING`.
2. Checked subtraction independently completes the same pipeline and its wrong-order, wrong-boundary and wrong-error variants fail.
3. Candidate-directory and explicitly prepared-bridge routes produce equivalent semantic observations for the same bytes, notwithstanding declared IDs/paths. Manual stage commands and `run` establish the same scoped guarantees.
4. Tests-required and `require-state TESTED` requests block before generation; `no-tests` plus `require-state TESTED` is a configuration error. An explicit VSCore test invokes no Python harness and records no PASS.
5. Required opaque/no-symbol/range-bound/liveness/resource obligations remain required and unsupported; optional unsupported guarantees do not acquire E2E. Removing a required guarantee, declaration representation or symbol binding blocks.
6. A source type-checks and links but has an incorrect result: those independent milestones may pass, while semantic acceptance/E2E and overall mechanics fail. Proof failure cannot be replaced by materialization or structural preparation.
7. Exact byte/argument/result/enum/adaptor bindings are checked. Source mutation, a proof for another program, wrong mappings, narrowed assumptions, weak/copied-model statements, unsupported source constructs, `sorry`, native evaluation and unauthorized axioms fail the appropriate registered check.
8. A complete metadata-only PASS/certificate without the corresponding successful execution cannot establish current semantic acceptance or E2E. Every semantic certificate public field and referenced artifact is compared to the actual checked result.
9. Missing, stale, wrong-issuer or unknown-predicate evidence, missing internal claims, cyclic premises, duplicate IDs and a detached selected endpoint all block. Deleting a mutable package index does not delete the required selected bridge.
10. Both builds really rebuild contract and VSCore sources. A failed A or B, missing expected output, changed proof inventory/IR/adapter/provenance/outcome or non-whitelisted difference blocks. Permitted timestamp/temporary-path differences do not.
11. Delivered source and selected bundle source differ: closure blocks even if either copy separately has a valid proof. Re-exported implementation IR is reconstructed from replays and must match source bytes and the stored accepted output.
12. Resume after interruption on unchanged inputs revalidates and completes; changed source, proof, test policy, claims, backend, schema, Lean/semantic dependency or selected endpoint invalidates dependent evidence. Historical reports cannot be mistaken for current acceptance.
13. Review mocks establish that unanimous review cannot fix a mechanical failure; mechanical success survives review rejection as a mechanical fact while release is blocked; changed review policy/snapshot invalidates votes; review finalization has no self-referential root. Fresh timestamps/attempt IDs change the raw inventory but preserve a review target only after both raw inventories validate and the registered projections match. Changing a semantic field, scope, trust, verifier, environment or nonvolatile artifact changes that target; unknown fields cannot be dropped. Pre-resolved model identities and explicitly trusted aliases obey their respective frozen policies, and returned model IDs never retroactively enter their own target.
14. Legacy Python Tier 0/1 fixtures retain their outcomes and root semantics. Old VSCore edge artifacts are not silently upgraded. Tier 3/4 or native-endpoint requests remain unsupported.
15. Reports/status/inspect expose the same complete claim outcomes, exact endpoint, hypotheses, witnesses and TCB as the authoritative mechanical result. No display derives a stronger state from a filename, a partial build, a review vote or the highest state symbol alone.

Stop after this suite and the frozen decision rule. When it passes, the next implementation milestone is the separately specified `vscore → vsstack` Tier 3 lowering; it must not be folded into this closure change.
