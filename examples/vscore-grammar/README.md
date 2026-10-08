# VSCore 0.2 grammar examples

The [VSCore 0.2 grammar](../../docs/vscore-generalized-grammar.md) and
[EBNF](../../grammar/vscore-0.2.ebnf) are implemented as an authoring frontend. `compile`
emits canonical JSON; `parse` checks a host proposal. Both are explicitly advisory.
`check` proves exact JSON decoding and source admission in Lean, reconstructs its AST and
signatures from replayed definitions, and requires two identical clean builds:

```bash
bin/verislop vscore compile --source examples/vscore-grammar/pure-data.vsc \
  --out /tmp/pure-data.vscore.json
bin/verislop vscore parse --source /tmp/pure-data.vscore.json
bin/verislop vscore check --source /tmp/pure-data.vscore.json \
  --out /tmp/pure-data-source-check
```

The check output directory must be new. It contains `report.json`, reconstructed
`implementation-ir.json`, the exact source-check goal and accepted Lean module parts.
Its endpoint is the delivered JSON. It does not certify the original `.vsc` text or bind an
accepted contract. No obligation milestone, `TESTED` campaign or `END_TO_END_VERIFIED` claim
is assigned. The accepted-contract bridge continues to support only `vscore/0.1`.

`pure-data.vsc` exercises nominal records/variants, options, lists, helpers and finite folds.
Its `pair_difference()` result is `3`; `sum(list[Nat](1, 2, 3))` is `6`;
`lookup_or_zero(variant Lookup.present(7))` is `7`; `head(nil[Nat])` is `none[Nat]`.

`ordering.vsc` fixes the implemented binder and evaluation conventions:

- `call_order()` returns `3`.
- `associativity()` returns `1`.
- `list_order()` returns `12`; reverse traversal would return `21`, and swapped fold binders `30`.
- `nat_order()` returns `12`, visiting indices `0, 1, 2`.
- `fold_scope()` returns `3`; a missing binder shift can return `0`.
- `shadowing(2, 7)` returns `15`.
- `result_payload(10)` returns `15`.
- `exact_natural()` returns `18446744073709551617` without word-size truncation.
- `@"legacy.id-with-hyphen"(9)` denotes the exact legacy entry ID and returns `9`.

[Frontend tests](../../tests/test_vscore2_frontend.py),
[CLI tests](../../tests/test_vscore2_cli.py) and
[kernel conformance tests](../../tests/test_vscore2_kernel.py) check concrete syntax,
binder, type and byte failures, plus exact normative Lean evaluation equations. The
[rejection examples](../../docs/vscore-generalized-grammar.md#7-concrete-design-checks) include
missing cases, cycles, reordered fields and unsupported effects. These finite tests do not
prove the Python frontend correct or create a registered VSCore campaign.
