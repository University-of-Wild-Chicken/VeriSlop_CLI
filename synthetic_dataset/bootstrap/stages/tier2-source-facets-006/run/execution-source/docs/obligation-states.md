# Obligation state model

Version 0.1 design candidate. Every obligation record contains all eight symbols below. A state describes evidence about a particular obligation revision and artifact scope; it is not a global guarantee about an application.

## 1. Required symbols and meanings

### INTERPRETED

The request has a recorded, explicit interpretation with a stable ID, kind, role, source provenance, scope, and acceptance criteria. Any selected defaults and unresolved ambiguities are visible. Evidence is an interpretation record and a schema/coverage check. This establishes what interpretation was recorded, not that an LLM captured the user's intent perfectly. An ambiguity record itself can be INTERPRETED while blocking other obligations.

### FORMALIZED

A candidate formal declaration, proposition, DSL term, or typed metadata record is bound to the obligation revision. Bound variables, types, hypotheses, outcomes, and semantic profile are explicit. A formalization mapping and exact source/statement reference are present. The formalization has not necessarily typechecked and is not necessarily true.

### TYPECHECKED

The declaration and its formal references pass the selected Lean validation boundary and match the frozen challenge. A proposition being a well-formed `Prop` is distinct from an admissible proof of that proposition. A proof containing an unauthorized axiom may have a well-formed type while failing the PROVED milestone. The report must expose that failure.

### PROVED

An accepted proof inhabits the exact formal proposition under the reported hypotheses and allowed logical axioms. Kernel replay, challenge comparison, dependency/axiom audit, and required witness checks pass. Its scope identifies whether this is a reference-model theorem or an implementation theorem.

A conditional theorem `∀ x, A x → P x` proves the implication. It does not establish `A x` for actual inputs. Preconditions are discharged separately at call/input boundaries. An axiom, assumption field, theorem-shaped declaration without an admissible proof, or proof of `P → P` cannot substitute for a demanded correctness theorem.

### IMPLEMENTED

A concrete implementation artifact exists for this obligation and passes the registered materialization/build check. The record names the source/object/binary hash and entry-point inventory. The implementation may still be wrong. An agent marking a to-do item done is insufficient. For changes to existing code, this milestone may occur independently of proof progress.

### LINKED

A deterministic structural binding uniquely connects the obligation, checked formal declaration, and implementation object(s), including their revisions/hashes. Many-to-many coverage is allowed through explicit binding records. A structural link resolves identity and coverage; it does not prove semantic equivalence. Declaration type acceptance is distinct from the whole-contract prove-before-generation gate. Semantic correspondence certificates are separate evidence required for END_TO_END_VERIFIED.

### TESTED

The registered target-artifact campaign actually ran and satisfied its frozen pass criteria. Evidence identifies the artifact, contract, harness, oracle, seeds/fixtures, effective case counts, results, and limitations. Empty, all-discarded, skipped, or reference-only campaigns cannot satisfy a required target campaign. A failed campaign records `TESTED: FAIL`; it does not mean the obligation reached a successful TESTED milestone.

The [TESTED campaign specification](tested-campaigns.md) supplies a proposed strict `0.2` acceptance rule and finite Lean design model, with explicit compatibility notes for the current Python campaign. Its proposed VSCore backend remains unsupported until implemented and registered.

### END_TO_END_VERIFIED

The exact accepted obligation is connected by checked semantic correspondence to the requested implementation endpoint, and all required assumptions, semantic adapters, build/provenance checks, and claim-specific preservation obligations are accounted for. Each included logical claim is proved or discharged by a registered sound certificate checker. No required semantic edge is merely an LLM judgment, a name match, a test, or an unproved translation assumption, even if that missing edge is disclosed as trusted. Residual logic/checker/environment trust remains separately declared.

Always display its endpoint, such as `END_TO_END_VERIFIED [restricted-source semantics]`, `END_TO_END_VERIFIED [extracted-language semantics]`, or `END_TO_END_VERIFIED [declared machine semantics]`. The endpoint cannot be chosen after the run merely to avoid a failed edge. Residual external environment/logic/checker trust is declared, not erased.

Tier 0 and ordinary Tier 1 are ineligible. Tier 2 and Tier 3 can qualify for their formally covered source/extraction endpoint. Tier 4 can qualify for an exact machine artifact under the declared machine model. A proof of source semantics cannot satisfy a request to verify delivered native bytes.

## 2. Milestones form a dependency graph

```text
INTERPRETED → FORMALIZED → TYPECHECKED → PROVED
     |                         |
     +→ IMPLEMENTED ───────────+→ LINKED
                |              |
                +──────────────+→ TESTED

PROVED + IMPLEMENTED + LINKED + semantic correspondence
       + required closure / endpoint obligations
                             |
                     END_TO_END_VERIFIED
```

The diagram is a prerequisite map, not a schedule. Existing code can be materialized before formalization; its evidence becomes useful to the formal pipeline when scoped and bound. Standard new-code generation waits until the contract acceptance gate passes.

Normative prerequisites:

- FORMALIZED requires INTERPRETED for the same obligation revision.
- TYPECHECKED requires FORMALIZED and declaration identity checks.
- PROVED requires TYPECHECKED, admissible proof evidence, and the applicable witness/assumption policy.
- IMPLEMENTED requires an interpreted obligation and a concrete artifact/build record; it does not require a proof.
- LINKED requires TYPECHECKED and IMPLEMENTED plus a unique binding record.
- TESTED requires IMPLEMENTED, TYPECHECKED for the referenced formal contract, a precise oracle/contract binding, and successful campaign evidence; it need not require a proof or a completed global LINKED inventory.
- END_TO_END_VERIFIED requires PROVED, IMPLEMENTED, LINKED, semantic correspondence, declared endpoint, and all required closure checks. TESTED is required only when release policy requires it.

For each symbol the outcome is exactly one of `PENDING`, `PASS`, `FAIL`, `STALE`, `UNSUPPORTED`, or `NOT_APPLICABLE`. Outcomes are scoped to immutable snapshots. FAIL is failed evidence; UNSUPPORTED is a missing backend capability; PENDING is not yet evaluated; STALE means prior evidence does not bind to current inputs. These outcomes are not extra state symbols.

## 3. A singular state for display

Every record also contains `state`, one of the eight symbols. It is derived from the successful applicable milestones using this fixed display precedence:

```text
END_TO_END_VERIFIED > TESTED > LINKED > IMPLEMENTED >
PROVED > TYPECHECKED > FORMALIZED > INTERPRETED
```

This is presentation order, not a ranking of assurance. A TESTED obligation may have `PROVED: PENDING` or `PROVED: FAIL`. Any UI that displays `state` MUST also expose the proof outcome, bridge outcome, and blocking result. An API consumer deciding assurance MUST inspect the evidence map and policy, never compare state ordinals.

An obligation record is created only after a minimal interpretation has been recorded, so INTERPRETED starts at PASS for that record/revision. Incoming unparsed text is an intake item, not yet an obligation. Revision changes create a fresh interpretation record; historical states remain in the old revision.

## 4. Different record roles

Guarantees normally have applicable proof and implementation milestones. Declarations may reach TYPECHECKED and may have implementation bindings without needing a proposition proof. Assumptions can be formalized/typechecked while PROVED remains NOT_APPLICABLE for the assumption record itself; separate guarantee obligations establish input validation or environment facts when required. A dependent conditional theorem explicitly references the assumption.

Exclusions and open questions normally mark proof/implementation milestones NOT_APPLICABLE with a policy reason. A resolved ambiguity records the selected interpretation and links resulting revised obligations; resolving a question is not proving a theorem. Metadata typechecking does not prove that an exclusion was appropriate or that a label is semantically correct.

Required guarantee milestones cannot become NOT_APPLICABLE just to obtain a passing report. Applicability is determined by the frozen role, acceptance criteria, endpoint, and policy. Changing it changes the claim surface and root.

## 5. Evidence, invalidation, and aggregation

Each PASS entry has evidence references and an explicit scope. Semantic milestones include exact contract/statement roots; implementation milestones include the artifact root and all roots they actually depend on. A bridge root is required for bridge-dependent milestones, not for an implementation materialized before linking exists. Interpretation/recording evidence is labeled provenance rather than mathematical proof.

Changes to a formal statement invalidate FORMALIZED onward for the revised claim. A proof-only change invalidates proof acceptance and dependent certificates even when its proposition stays identical. Implementation changes invalidate IMPLEMENTED, LINKED, TESTED, and END_TO_END_VERIFIED for that artifact, while an unchanged independent model proof can remain valid under its original contract root. Schema, semantics, compiler, instrumentation, generator, oracle, or verifier changes invalidate the affected transitive evidence. New evidence never rewrites historical entries.

The report derives aggregate counts from required obligations and applicable milestones. It MUST NOT use the maximum observed state as application assurance. A single failed required bridge blocks a public end-to-end claim that depends on it. No average, confidence score, or majority of successful obligations can discharge the missing one.

The run terminal result is separate from obligation state: `VERIFIED`, `BLOCKED`, or `INFRASTRUCTURE_FAILURE`. VERIFIED is always qualified by the frozen finite claim surface and explicit trust. It does not automatically assign END_TO_END_VERIFIED to any obligation.

Adversarial review decisions are also separate. User-configured review agents may accept a candidate at each review tier and escalate it, but consensus never assigns PROVED, TYPECHECKED, LINKED, or END_TO_END_VERIFIED. A release may require REVIEW_ACCEPTED in addition to the appropriate mechanical milestones.
