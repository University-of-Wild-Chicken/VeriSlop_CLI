# Extracted failure patterns

The dominant bottleneck is constructing and repairing a faithful, executable formal
contract before implementation starts. The supported type/operation surface expanded,
but the measured data corpus still has only three distinct natural-language prompts.
One complete native numeric workflow cannot establish broad task coverage.

This extraction reads retained artifacts without model calls, candidate execution,
Lean reruns or historical rescoring. It adds diagnostic files; it changes no CLI code
or sealed experiment receipts. Evidence paths and byte hashes are recorded in the
[formal/proof catalog](FORMAL_PROOF_PATTERNS.json) and
[review/provider catalog](REVIEW_INFRA_PATTERNS.json).

## What was actually observed

The [task inventory](TASK_INVENTORY.json) contains24 cohort-task slots across eight
development cohorts:19 completed CLI executions,2 interrupted or transport-incomplete
slots, and3 never-started slots. These repeatedly attempt the same three tasks under
different source/configuration versions. They are not24 independent tasks.

Among the19 completed CLI executions, the first nonpassing stage was formalization
in12, proof in2, formal-contract review in2, generation in1, and release review in1.
One passed every native CLI stage. The
[counts](COUNTS.json) distinguish these execution outcomes from experiment accounting.
Stage counts use the recorded final active-package history; preceding failed repair
packages are examined separately in the catalogs.
Two slots produced Python and320 independent observations each; all640 passed.
The other22 slots produced no independent implementation observations. This does not
establish a general code-generation success rate: the earlier gates strongly select
which tasks reach implementation.

The stopped larger corpus corroborates the upstream bottleneck: Qwen's42 completed
strict arms first failed at formalization33times, interpretation5times and review4times;
Luna's18 first failed at interpretation9times, formalization7times, proof once and review
once. Those60 arms generated no implementation. Their failures are not60 demonstrated
wrong-software executions. See the separate
[stopped diagnosis](../stopped-experiments-003-002/DIAGNOSIS.json); neither experiment was restarted.

## Recurring mechanisms

1. **Ill-typed or malformed contract proposals.** Earlier raw Lean used incorrect
   quotation marks, reserved names, record syntax and projection precedence. The typed
   frontend removes those rendering hazards, but model proposals still confuse
   `Input` with a primitive sort, Boolean terms with propositions, record carriers and
   list arguments, or omit required lambda/binding fields. Native003–005 retain nine
   malformed initial Unicode responses with the invalid `Input` sort. These are model
   proposal/repair failures within an already-supported domain. Native005 row projection
   also accumulated such errors before its terminal provider failure. (F02–F03.)

2. **Obligations lose pipeline composition or request meaning.** Native005 Unicode O1
   requires final output to equal the unprefixed filtered input, while the reference
   function and O2 require prefix mapping. With `labels=["x"], prefix="p"`, O1 requires
   `["x"]` but the function yields `["px"]`. This is a false theorem, not a missing DSL
   operation. Separately, Luna003 proves a reference that retains empty labels: the
   same input produces `[]`, contrary to the requested `["px"]`. A proof can be sound
   while the modeled request is wrong. These concrete counterexamples are derived
   from retained expressions; no new execution observations are claimed. (F07, P4.)

3. **Semantic weakening instead of correction.** Earlier corpus contracts substituted
   `True`, `n=n`, or existence of an unchanged unsorted output for real requirements.
   Four native row responses each supplied nine literal-True guarantees. Current
   readiness rejects those vacuous/disconnected guarantees, correctly preventing
   misleading TESTED claims. That guard does not ensure that a nontrivial formula has
   the correct meaning, as the reversed Unicode filter demonstrates. (F04, P4.)

4. **Repairs consume calls without changing the cause.** Native005 Unicode's two
   repair packages have identical proposals, challenges and false O1 statements.
   Each uses four prover calls. All eight USER payload hashes differ and include
   updated errors, yet the first package repeats one invalid proof four times; the
   second repeats another three times, including an unknown `List.map_filter` lemma.
   This is current proof stagnation despite feedback. It differs from the older
   missing-feedback bug, where D06 had eight identical prover input hashes.
   Closure absence messages and derivative legacy-manifest errors also obscure the
   primary defect. One checked placeholder has one actual typing diagnostic and eight
   derivative schema diagnostics. (F05, F08, F10, P8.)

5. **Concrete semantic review findings have no suitable replay/repair route.** Luna003's
   critic finds the reversed filter, but binds it to a `mechanical_failure` probe on a
   PROVED claim. That proof is valid, so replay returns NOT_REPRODUCED and REJECT becomes
   ABSTAIN. The current formal review probes check proof/claim mechanics or exact
   missing-clause coverage; they do not execute the reference against a scoped request
   example. Recovery requires a confirmed contract-claim defect and does not revise
   interpretation through this route. Earlier ballot/probe envelope confusion also
   exhausted six correction attempts across two review campaigns. (P4–P5.)

6. **Scaffolding is lost or its authority is misunderstood.** The original reviews
   showed pre-proof source in four of five inspected packets while claiming acceptance.
   Accepted-source packets now fix that mismatch, but Luna003 still treated an unused
   fallback `sorry` branch as evidence of an unresolved accepted proof; its replay
   disproved that allegation. Large packets also exceeded the native context:
   implementation22367tokens and release19667 were each truncated to8194. The
   [historical service warnings](native004-context-truncation.log) were newly captured
   during this extraction; the original archive is unchanged. Larger explicit context
   and lossless package sharing mitigate truncation, while latest native failures
   show they do not establish semantic correction. (P2–P3.)

7. **Provider and transport failures stop otherwise-progressing paths.** There are
   seven native provider-error transcript entries: one HTTP500, five abnormal stops,
   and one unfinished/error completion. The adapter discards the actual stop reason,
   token counts and partial body; terminal broker logs record null response and zero
   elapsed time. These receipts cannot distinguish output-limit exhaustion from other
   non-normal stops. The stopped corpus has two separately matched GPU-crash excerpts;
   that evidence does not explain every service failure. Luna's long inline relay and
   empty-final handling left two interrupted slots and three unvisited slots. (P1, P6.)

8. **Measurement errors can hide success but do not explain low task coverage.** The
   scalar/object tier mismatch falsely rejects exactly the native005 numeric result
   after its CLI and tests pass. The fix is present and regression-tested, but original
   receipts stay unchanged. Fixing that observer does not repair the row contract,
   false Unicode theorem, semantic review gap or provider failures. (F09, P7.)

## What is fixed and what remains

Historical missing Nat-to-Int/fold reification, raw source rendering, structured
witness construction, accepted-source review packets, prover error feedback, transport
receipts, lossless context sharing, placeholder diagnostics and tier accounting have
implementation fixes or mitigations. The catalogs distinguish the applicable source
versions and authored regressions from measured native outcomes. There was no new
native cohort after the final post-seal fixes.

The highest-priority unresolved work is:

- Refute false candidate contracts with concrete inputs and kernel-checked refutation
  evidence before spending universal-proof attempts; return that evidence to formalization.
- Add a reference/request conformance probe with exact requirement binding, concrete
  input and independently justified expected behavior. Natural-language correspondence
  needs an explicit evidence authority; proof failure is an unsuitable proxy.
- Detect repeated candidate/proof/error hashes and route repairs to the responsible
  stage, retaining immutable failed artifacts and every acceptance gate.
- Provide sort-directed AST correction and retain actual provider rejection metadata
  and elapsed time. Broader remeasurement should use fresh whole cohorts afterward.

These are suggested milestones, not implemented changes or new measured results.
The extraction trusts the retained host/provider records; Luna identity and read/tool
enforcement remain unattested. It proves neither universal Python refinement nor
END_TO_END_VERIFIED.
