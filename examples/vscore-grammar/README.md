# Proposed VSCore grammar examples

These are authoring examples for the [VSCore 0.2 proposal](../../docs/vscore-generalized-grammar.md)
and [EBNF](../../grammar/vscore-0.2.ebnf). The registered CLI still accepts only `vscore/0.1`.
These files have no implementation certificate and do not constitute a TESTED campaign.

`pure-data.vsc` exercises nominal records/variants, options, lists, helpers and finite folds.
Its `pair_difference()` result is `3`; `sum(list[Nat](1, 2, 3))` is `6`;
`lookup_or_zero(variant Lookup.present(7))` is `7`; `head(nil[Nat])` is `none[Nat]`.

`ordering.vsc` fixes observable conventions for a future implementation:

- `call_order()` returns `3`.
- `associativity()` returns `1`.
- `list_order()` returns `12`; reverse traversal would return `21`, and swapped fold binders `30`.
- `nat_order()` returns `12`, visiting indices `0, 1, 2`.
- `fold_scope()` returns `3`; a missing binder shift can return `0`.
- `shadowing(2, 7)` returns `15`.
- `result_payload(10)` returns `15`.
- `exact_natural()` returns `18446744073709551617` without word-size truncation.
- `@"legacy.id-with-hyphen"(9)` denotes the exact legacy entry ID and returns `9`.

The proposal also supplies [concrete rejection fixtures](../../docs/vscore-generalized-grammar.md#concrete-design-checks)
for malformed binders, missing cases, cycles and unsupported effects. Their diagnoses must be
confirmed by the future registered checker before they become acceptance evidence.
