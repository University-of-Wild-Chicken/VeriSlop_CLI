# Process evidence in release review projections

The release-review normalizer uses closed producer field sets. The additive
VSCore 0.3 compiler evidence must have a registered alternative before release
review can consume it. Preserve the legacy producer alternative and register
exact VSCore 0.3 alternatives with `compile_process_evidence`, `readable_support`,
or both. Do not extend VSCore 0.1 or accept arbitrary producer fields.

Retain the complete process inventory in the normalized semantic payload. It is
hash-bound evidence already frozen as an input, not a fresh build observation.
Do not recursively remove timestamps, paths or similarly named keys. Existing
top-level evidence wrapper normalization stays unchanged.

The optional deterministic `readable_support` clean-build output also needs an
explicit closed output-field alternative. Preserve all its descriptor and
artifact hashes. Register both exact output alternatives in the normalizer
inventory; unknown output fields still fail. A changed normalizer source hash
invalidates earlier registry identity rather than rewriting historical records.

Regression validation must pass actual VSCore 0.3 checker output through its
EvidenceStore and release normalizer, retain exact compiler inventories, preserve
legacy output acceptance, and reject concrete unknown-field mutations. Supported
readable output must be preserved verbatim through clean-build normalization.
