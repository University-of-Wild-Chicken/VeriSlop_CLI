# Generic Tier 2 proof support

## Specification fixed before implementation

This increment improves authoring support for the existing VSCore 0.3 exact-source
bridge. It does not change the accepted contract, source language, capability
boundary, obligation requiredness, source-facet policy, generated proposition,
adapter identity, refinement inventory, transfer rules, or proof/axiom policy.
Observed failure classes supplied by the coordinator motivate this generic
support. No retained task source, proof, case, carrier, or expected result is
inspected or supplied to new authors or tests, and this support does not generate
a task candidate. A failed refinement remains unresolved.

The verifier-owned `VSCore3.Transport` module will expose a finite catalog of
kernel-proved mathematical lemmas. The catalog is limited to applying a function
to a conditional, Bool/Prop conditional transport (including `decide`), identity
list maps, and Nat-to-Int cast normalization. Conditional and list lemmas quantify
over arbitrary types and functions; cast lemmas quantify over arbitrary naturals.
They contain no accepted symbol, program, reference body, proof strategy search,
or automatic task proof. They are not global simp rules. Catalog names and exact
Lean statements are supplied to proof authors from supervisor-owned code and
checked against the pinned Lean toolchain.

Proof guidance will explain that compiler-generated dependent casts can require
`with_unfolding_all` around a small `change`, `rfl`, or explicitly chosen step.
It will not recommend unfolding the entire compiler into every goal. Authors
must inspect the generated `source_fn_*`, `Refines_*`, and `edge_of_refines`
interfaces and prove exactly the declared refinement inventory. Restricted
`simp only` calls must name required transport lemmas. Closed decidable witness
preconditions may use `decide +kernel`; `native_decide` remains forbidden.

The implementer packet will explicitly describe the helper's relation interface:
exact keys `schema_version`, `format`, `template`, `source_slot`, `proof_slot`,
and `bindings`; exact registered 0.3 constants; `source_slot = vscore-source`;
`proof_slot = vscore-proof`; and bindings sorted by unique accepted symbol with
unique program entries. These are artifact slots, not filenames or theorem
names. Existing strict validation remains authoritative and unchanged.

## Complete diagnostics and binding

A VSCore 0.3 compile failure will carry every Lean error in its structured
diagnostic details, preserving the failed module, module-source hash, complete
parsed compiler messages, available stderr, timeout/sorry information, generated
goal hash, and hashes of the current source, relation, and proof inputs. Error
summaries may be compact, but no error is silently dropped. Existing failure
codes and blocking/infrastructure classification remain unchanged.

Agent attempts will durably retain complete diagnostic records, including
protocol and size failures, and identify the exact current source/relation/proof
hashes and the exact raw proposal response path/hash. Unparseable responses have
no source/relation hash; they cannot inherit those fields from an earlier
candidate. Prover repair context will contain a numbered compact entry for every
reported error, total counts, explicit compaction disclosure, and a path/hash
reference to the full-error artifact. No successful proof outcome is inferred
from source admission, a diagnostic summary, or an exhausted proof search.

## Acceptance checks and limits

Fresh generic tests will check catalog signatures by pinned Lean elaboration and
kernel replay, reject a false universal statement, check unchanged relation-slot
validation, and exercise failures with more than three and more than twenty
errors. They will confirm complete durable errors and exact hash binding in the
next repair context, including a replaced proof. Existing unrelated VSCore
workflow and kernel checks will run where appropriate. No live model call or
retained task replay is part of this increment.

This support does not establish any task-specific refinement or Tier 2 result.
It cannot guarantee that a model chooses a useful lemma or completes its proof.
Compiler messages remain limited to what the pinned compiler actually reports;
any available stderr truncation must be explicitly disclosed in its record.
