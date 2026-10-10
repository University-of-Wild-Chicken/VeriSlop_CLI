# Source-only result

One concrete availability defect was found in two source positions. No other
concrete defect was found within the inspected source/specification/schema/
registration scope. No candidate, control, tool-channel, or model execution was
performed, and no native task artifact or actual channel evidence was inspected.

## Finding: valid own-reference path text is counted as executable code

`validation/tier2-carrier-context-support-019-implementation-002/capture-amendment-001/collector_templates.py:44`
counts the forwarding string anywhere in the serialized recipe, then line 50
replaces a substring. Lines 68–72 perform the same unrestricted count and
replacement for the nested fault budget. Quoted carrier path data is included
in both searches.

The unchanged candidate serializes the exact path into its session-key literal
and initial PREFIX (`bootstrap_tier2_carrier_view.py:197`, `:251`, `:269`). JSON
escaping does not remove the following ASCII substrings. These are ordinary
canonical absolute Linux paths with legal component characters:

```text
/unrelated/text(await tools.exec_command({cmd, max_output_tokens: 16384}));/own-carrier.json
/unrelated/await tools.exec_command({cmd, max_output_tokens: 16384})/own-carrier.json
```

Witness A: use the first path in a reference with any correctly bound carrier
SHA and request SHA. Call `initial_collector_template(reference)` or
`next_collector_template(reference)`. The initial plain recipe contains the
forwarding string three times: once in OWN_KEY data, once in PREFIX data, and
once as the sole forwarding statement. The next plain recipe contains it twice:
once in the load-key data and once as the sole forwarding statement. Line 44
therefore raises `ONE_FROZEN_FORWARDING_LINE_REQUIRED` even though each recipe
has exactly one executable nested call and forward.

Witness B: use the second path and call
`next_collector_template(reference, FAULT_VIEW, "AC002-002", fault=True)`.
This path lacks the complete `text(...);` forwarding string, so `_observe`
successfully produces the normal observer recipe. The nested-call substring at
line 68 now occurs three times: in the PREFIX load-key data, in the actual
ACTUAL_RESULT call, and in the collector store-key data. Line 70 raises
`ONE_NESTED_FAULT_BUDGET_POSITION_REQUIRED`. The requested registered fault has
exactly one executable budget position.

These witnesses follow directly from the string construction; they were not
executed. No path restriction in the reviewed candidate requires either path to
be rejected. The failure prevents an otherwise valid own-carrier collector from
being emitted. It does not establish any proof/semantic acceptance bypass.

The ten source controls use ordinary reference paths (`test_capture_controls.py:17`,
`:149`); their call/forward assertions at lines 92–95 also count raw substrings.
They do not cover these valid path collisions. This is a coverage limit attached
to the concrete factory defect, not a separate production acceptance defect.

## Remaining inspected scope

The observer source assigns the actual returned exec_command object, forwards
that object once, and stores that object beside the explicit VIEW under the
literal own case/path/rawSHA key. The schema and registration consistently call
the returned output a combined output string. Hidden native outer envelopes,
separate stdout/stderr, and PID remain explicitly UNAVAILABLE and outside the
claim. Runtime completion of the store after rendered truncation is explicitly
trusted. The schema forbids reusing a stale prior store if the current call
fails before storing.

The plain model author message is returned directly from the unchanged
candidate. Registration retains full 429112-character reconstruction, both
256-budget fault/same-cursor retry cases, both-empty EOF, and exactly one fresh
fork-none Sol author. Source checks and descriptive schema requirements are not
actual observations or a qualification result. I found no additional concrete
counterexample in these inspected mechanics; runtime behavior, actual evidence,
model behavior, and enforcement by a future qualification reader remain outside
this review.

## Exact inspected hashes

- Amendment specification: `2a855a3e1de4e167988696e5c24bc5a191a833196c5c9435c419be3c9f45b9cb`.
- Capture manifest: `7b9aa5d071e87127f17dd984fb3da44ab45ff71ff16db841fdff0d9330e24067`.
- Collector factory: `4c207c503eafd4c2f3803a0335ee6425017261ef3c137ea68dc5ce86f880c993`.
- Observable schema: `5a6141ea0aed23e9dbced635cf5e8e55e66ae66f17471559737aff6515072e9f`.
- Registration: `b9fa13812e14446818d6bc66869fe0342d93024dcfd44c7961d5b6c4111281ec`.
- Source controls: `bb778614d756bb0860c2894f1d802a56280ef999064049ff0d150e89c345dce2`.
- Unchanged candidate002: `9930beff878848b05c8d69245fff12c1388f14254b6630504b36748c4c294366`.
- Unchanged plain002 protocol: `fe8f0f04ae5c110ec0f36b2b42cc8758c46d10b8d9a06069825110d11b6c2092`.
- Unchanged plain002 controls: `be69ba79fe946aec9b103449bd4a670144b1b92af2b47c09e1cdf258a13c0cd0`.
- Unchanged plain002 manifest: `b5dfdacd527aac0f5de6388793f1f0b23ca8847759b6e4379bbd7505db608328`.

The review seal also binds the inspected review-only recipe source and
review-ready metadata. Producer pure-control receipt/log bytes were not opened
or rehashed by this review. Production and all preexisting frozen files remain
unchanged by this reviewer. FINAL/STOP.
