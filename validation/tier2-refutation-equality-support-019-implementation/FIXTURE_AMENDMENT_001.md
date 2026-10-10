# Frozen fixture amendment 019-001

This is a DEVELOPMENT_ONLY generic fixture prerequisite, not production result-support behavior or ROOT003 qualification. The candidate production copy remains limited to audited equality reuse, alias hygiene, fallback and the existing dependency order.

Run001 failed because the pinned Lean 4.34.1 Std environment does not provide inferred DecidableEq for Except. The newly authored AParcel contains Except Token ZLeaf. Its equality derivation therefore failed even when Token and ZLeaf equality were available. Existing all-profile equality preparation also blocked a token-only proof because it attempted the unrelated AParcel derivation. This is a preexisting coverage limitation; it is not fixed or verified by the candidate.

The complete available run001 process/compiler/kernel receipts and failed case results are retained. Run001 was deliberately interrupted during a kernel invocation; no result was returned for that incomplete call. It has no PASS rescore, no reuse, and no qualification authority. Interruption-facts.json records exact completed counts and the unavailable incomplete receipt.

The revised positive fixture bases explicitly add `deriving instance DecidableEq for Except` as an authored safe proof-producing generic prerequisite. Positive proof receipts must bind this declaration through the fresh actual Env, preserve its hash, inspect its safe computable closure and axioms, and retain actual compiler/kernel receipts. A separate unchanged missing-prerequisite fixture remains UNKNOWN with no receipt. This amendment claims no production expansion of equality for results.

A revised fixture draft had been edited but not executed when root's request to freeze this amendment arrived. That draft was reverted before this amendment was written; revised fixture edits follow this immutable amendment. The original run001 harness is retained as a explicitly reconstructed snapshot. Fresh run002 gets a contemporaneous candidate/test source snapshot before any invocation.

Additional harness corrections use the existing exact DSL projection shape (tag/ sort/ field/ value), capture an invocation receipt before sandbox entry, and label any interruptions honestly. No compiler/kernel caps, source/global timers, model behavior, native task inputs, production source, or policy checks change.
