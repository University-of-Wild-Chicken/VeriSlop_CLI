# Exact Tier 2 closure predicate dispatch

This correction is specified before implementation. The preliminary readable
pipeline actually accepted its semantic bridge and completed clean builds A/B,
then rejected final closure evidence because the shared determinism predicate
used the VSCore 0.1 output inventory. The frozen gate 014 was interrupted before
this correction; it supplies no qualification. Its inputs and logs are retained.

## Frozen authority

VSCore 0.1 retains `closure-determinism/0.2`, with its existing exact thirteen
comparison slots. VSCore 0.3 now registers `closure-determinism/0.3` in both its
implementation claim inventory and closure execution inventory. This predicate
requires the existing exact fourteen VSCore 0.3 slots, including
`readable_support`. The frozen supervisor claim chooses the predicate; the raw
result's keys, claimed backend, or support presence cannot select the inventory.
The raw result format must equal that frozen predicate. A cross-version result,
unknown predicate, missing slot or extra slot fails. All existing issuer,
verifier hash, root, integrity, exit code, two-build and prerequisite checks stay
in force. No semantic acceptance or lifecycle state comes from this dispatch.

## Nullable support

The new slot is mandatory even for a legacy VSCore 0.3 source without a selected
readable view. That source emits `readable_support: null`. Two present null values
compare equal. A missing key is different from a present null value and fails.
Null remains inadmissible for every other comparison slot. A selected support
descriptor must compare byte-for-byte, together with its complete artifact map;
one null and one selected descriptor differ. VSCore 0.1 behavior is unchanged.

## Qualification

Add pure, registered-evidence regression checks for both version predicates,
their exact positive inventories and both cross-version negatives. Add concrete
comparison controls for present null/null, omitted keys, null in an older slot,
descriptor/null, changed support bytes, and undeclared extra keys. These tests
do not claim a Lean proof or an executed build. The fresh frozen gate must also
execute the complete existing legacy VSCore 0.3 fixture and the new CHECKED-view
fixture through actual registered A/B closure, accepted-artifact verification,
retained review and post-cleanup verification. No task model is called during
engineering qualification. Prior failures are never replaced or rescored.
