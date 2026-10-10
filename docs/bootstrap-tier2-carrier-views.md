# Exact own-carrier views

The generic Tier 2 pending message embeds its complete standalone read-only
reader. A fresh author reads only its one exact absolute carrier; it does not
open a workspace helper, sibling request, history, or reference answer. The
source inventory includes `bootstrap_tier2_carrier_view.py`, and the existing
spawn-message hash binds the newly generated message in each new qualified run.
Original carrier bytes and native request/hash bindings remain authoritative.

The reader checks full raw SHA-256 and native request-hash metadata equality
before content output. Its strict JSON boundary matches the carrier parser:
duplicate keys, nonfinite/floating numbers, unsafe integers and lone surrogates
are unsupported. Supported exact field text consists of Unicode scalars, with
no normalization or replacement. One decoded character means one Unicode code
point, not a UTF-16 unit or grapheme. Separate byte offsets measure strict UTF-8
of the decoded field, never raw carrier escapes.

Start with the compact `/system` and `/user` inventory. Read the complete system
first, then the complete user, using exact original slices, explicit cursors and
EOF. This version uses full linear field navigation, preserving every nested
packet/evidence section and unknown prefix/suffix without reserialization or
summaries. Empty fields need an explicit zero-length EOF view. Content is one
JSON string that decodes once to the exact original slice.

Each complete encoded stdout record, including newline, is capped at 8192
UTF-8 bytes. Metadata/syntax reserve is 2048 bytes; escaped JSON content fits
the remaining 6144 bytes. The complete serialization is measured before output.
The author sets the actual tool budget explicitly to `max_output_tokens=16384`;
this setting is subject to a retained actual-channel fixture probe, not an
assumed byte-to-token equation. Truncated or inconsistent output cannot advance
the cursor. Retry the same selector/start at cap4096/reserve2048 and the full
tool budget; smaller bounds must retain viable metadata capacity. Errors stay
explicit and do not silently authorize another input or fallback tool.

Exact generation, tool-channel delivery, and LLM consumption are distinct.
Reconstruction and coverage can test availability on frozen unrelated fixtures;
neither an access log nor an LLM assertion mechanically proves consumption or
understanding. View completion grants no ACCEPT or lifecycle state. Existing
scope, full required inspection, semantic search, probe replay, acceptance,
literal FINAL forwarding, unique fresh authors and budgets remain binding.
There is no new deadline, lifecycle predicate or trust authority.

The specification-first design and finite eight-check/six-family/sixteen-control
plan live in `validation/tier2-carrier-view-support-018-design`. Actual local
results and channel adapters live in the separate implementation evidence
directory. Actual-channel CV-004 and unified new-root clean-build CV-008 remain
unresolved until their exact execution records exist. Sealed task runs and their
results are not rewritten or used as fixture payloads.
