# Candidate 019 revision 002: specification before repair and execution

Status DEVELOPMENT_ONLY_SPECIFICATION_FROZEN. This is a separate candidate revision, not a production installation or current-root/ROOT003 qualification. Sealed implementation 001, its failed/interrupted attempts, and source review 001 remain unchanged.

The independent review (SHA-256 6dce3f33f977ad79bcdd37192acd63c748f6ec0df07233353d35ba672db7b0fa) found an availability regression: a safe private exact-type equality definition has a numeric Lean name component, so _qualified cannot print it. Candidate 001 currently selects it and then returns UNKNOWN instead of considering printable alternatives or safe deriving. The review also found an assertion gap in the old semantic-Analysis binding control: a true guarantee and empty proposals remain UNKNOWN even with the guard removed; a comment-only source edit can correctly preserve semantic Analysis identity.

Minimal repair registered before code changes:
1. Preserve sorted exact-type equality candidate discovery and the full existing audited computable closure/hash/axiom check.
2. Before selecting each equality definition, attempt _qualified(equality_name). If this exact name cannot be represented by the existing printer, skip only that candidate and continue the other candidates. Do not broaden the printer, trust private source spellings, use guessed names, discard the audit, or suppress unrelated errors.
3. Reuse the cached printable name only after its actual definition passes the existing audit. If every candidate is unactionable or rejected, retain the existing proof-producing deriving fallback for that carrier.
4. Preserve carrier traversal, deterministic alias collision guard, theorem construction, original-declaration hashes, exact kernel replay/defeq/root/axiom acceptance, receipts, policy and resource caps. The code from the theorem construction through file end remains identical to candidate 001/production except fixture-only counterfactual experiments.

Fresh unrelated actual-Lean fixture plan:
- Namespace PrivateEqualityRevision019, public two-constructor Palette (ochre/teal), constructor-case swap, and false swap(t)=t guarantee with a candidate theorem hole. No record, native task, retained answer, model, probe, or timing shortcut is needed.
- Private-only ordinary safe DecidableEq definition: actual Env contains its numeric private name and audit accepts it, printer rejects that name, production baseline genuinely refutes the concrete false guarantee, candidate 001 demonstrates UNKNOWN, and revised candidate falls back to safe deriving and REFUTED with a clean kernel root.
- Private plus public ordinary safe equality definition: place the public definition at root as zzUsableEquality so the private actual name sorts first. Revised candidate skips the private name and aliases the printable audited public definition, avoiding unnecessary deriving.
- No equality definition: revised candidate retains safe deriving and genuine REFUTED behavior.
- Correct closed proposition negation remains unprovable despite the repair.

Improved semantic binding controls:
- Use an actually falsifiable fresh guarantee and explicit concrete input. First establish a real revised-candidate REFUTED receipt with its exact Analysis.
- Supply a genuinely mismatched semantic Analysis (for example replacing the false guarantee formula package with True), without changing the actual fresh source. Require exact binding diagnostic `source/form/records do not match the supplied kernel-derived analysis`, UNKNOWN, zero proof attempts and zero receipts.
- Create a clearly labeled fixture-only counterfactual source copy replacing only the fresh-versus-supplied Analysis identity comparison with False. With the same mismatched Analysis, require genuine REFUTED behavior; this proves the improved control detects removal of that guard. The mutant is not installable candidate code and grants no authority.
- Label a comment-only source edit as semantically equivalent: the same falsifiable guarantee can correctly be refuted and its receipt must bind the exact newly supplied source bytes/hash. Do not require rejection solely for comments.
- Change actual source semantics while supplying the original Analysis and require the exact binding diagnostic, UNKNOWN and no proof attempts/receipts.

All 44 original control requirements stay registered in ORIGINAL_CONTROL_REQUIREMENTS.json with RERUN_REQUIRED status. Prior candidate 001 PASS counts are not current revision results or final qualification. Preserve the original fixture requirements; revise the copied grouped binding control to be discriminating. Execute only the private/binding regressions now; a later whole-root run must rerun the complete control set under separately frozen current inputs.

Evidence requirements and stop condition:
- Write this specification and control registration before any candidate mutation or execution.
- Capture complete actual process invocation/result receipts, raw stdout/stderr, compiler process evidence, fresh staged sources/module parts, kernel requests/responses and proof artifacts. Preserve failures and source snapshots without rescoring old attempts.
- Audit final diff and exact source/hash preservation of production, sealed 001 and review 001. Seal candidate/tests/spec/actual evidence read-only with SHA-256 manifests.
- No production/docs/tests mutation, native task/candidate/proof/benchmark content, old task answers, native builds, models, probes, inference deadlines or new resource caps. Stop for separate root/source review before installation or whole-root qualification.
