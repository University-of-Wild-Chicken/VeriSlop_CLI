# Carrier candidate002: independent source review

Status: NO_CONCRETE_FINDINGS_WITH_LIMITS_SOURCE_ONLY. Review complete; STOP after sealing this record. No candidate, control, model, actual channel, build or probe execution occurred.

The exact candidate001-to002 source diff preserves READER_SOURCE, inline_source, inline_command, inline_prefix, own_session_key, _closed_view, _VIEW_GUARD and initial_session_template. NEXT replaces the repeated JavaScript VIEW guard with _NEXT_EMIT (`bootstrap_tier2_carrier_view.py:263-279`). This emit fragment is the same command serialization, Python emit_view suffix, nested exec_command cap16384 and one actual-result text forward already used by FIRST. The fixed outer cap20000, exact own key load and typeof PREFIX string guard remain. No eval/function construction, helper read, loop, batch, concatenation of multiple outputs, or automatic cursor state is added.

The renderer still validates an exact inventory-three-key or field-five-key VIEW, allowed operation/selector, integer cap256..8192, integer reserve128..<cap and integer cursor0..2**53-1. Accepted literals have fixed ASCII operation/selector strings and safe integers, so JSON.stringify(JSON.stringify(VIEW)) produces a valid Python string literal containing JSON. Only the explicit VIEW literal changes between generated NEXT calls; the reader/reference prefix is loaded from the same immutable own session key. This review assumes that registered immutable state and surrounding code remain unchanged, as required by the author contract; it does not claim the template sandboxes arbitrary unauthorized JavaScript or session-state edits.

Python reader checks are unchanged. The rationale explicitly distinguishes its preexisting omitted-key defaults from renderer closure (`source-review-rationale.json:validation_layers`), and the defaults control at `test_candidate.py:246-251` makes the same distinction. The server retains checks for cap/object/reserve, unknown field names, original raw hash/request metadata/path/strict JSON, operation, field selector and exact decoded-length integer cursor, metadata reserve/content capacity, Unicode/UTF8 slice and EOF behavior. No claim that the removed JavaScript exact-key checks equal every Python default is made.

The 15 pure control definitions cover required001 reader/helper/prefix/FIRST identity, fixed short NEXT code, own-key isolation/missing-prefix refusal, renderer closure, exact command serialization, malformed Python-server inputs against001 raw output/status, preserved defaults, full finite Unicode/control/tail and empty EOF slices, original trust checks, same-cursor retry, own-draft JSON syntax guidance, and fresh fixture/protocol shape. The malformed-server control contains 19 cases and requires actual Python returncode2, exact001/002 stdout/stderr/status comparison, error/no-next when an error record is available, and no additional fixture files (`test_candidate.py:199-244`). These are source assertions; their reported execution outcome was not independently rerun by this review.

The prospective registration requires a newly materialized429112-codepoint unrelated user field with four new002 markers and exact final Unicode/whitespace tail; complete system-before-user contiguous reconstruction and both explicit EOF views; and a separate new own carrier with both fields empty (`prepare_unrelated_fixture.py:42-49,95-113`). Old001 sequence artifacts are neither inputs nor substitutes. The source review did not inspect the failed actual001 collector sequence or reinterpret its failure.

The four channel cases are explicitly distinct. AC002-001 uses the exact normal FIRST/NEXT recipe with caps20000/16384. AC002-002 preregisters the nested cap256 fault with outer20000; AC002-003 preregisters the outer cap256 fault with nested16384. Both use the exact /user start0 VIEW and require observed actual truncation, no advancement, and normal-cap same-selector/start retry with VIEW4096/reserve2048. AC002-004 requires separate normal-cap /system0 and /user0 outputs for the both-empty carrier with empty content, zero lengths/next and explicit EOF. These test-only fault budget changes are not production guidance. Full actual nested/outer envelopes and numeric completion status remain required; unresolved or unavailable envelopes cannot qualify a view (`prepared-qualification-protocol.json:19-52,68-82`). External capture of the complete nested envelope for the outer fault is a future required operation; its availability was not verified by source review.

FA002-001 is preregistered as exactly one unique gpt-6.1-sol fork-none author with only the exact candidate002 own-carrier message, evaluator-only expected roots/answers, full original inspection, own in-memory draft syntax validation, literal FINAL forwarding and retention of exposed drafts/failures. No replacement author, cleanup or resampling is allowed. Inspection assertions remain UNATTESTED. Materialization and every actual/model call are gated on root review/freeze/explicit followup and currently recorded as unexecuted.

No concrete counterexample was found within this inspected scope. The findings do not establish actual transport truncation/retry, full429112-character channel reconstruction, fresh-author progress, external nested-envelope capture, semantic consumption, production activation or whole-root qualification. No native/task artifact contents were read and no production/core/old sealed root was written. Only this new source-review directory was written.

Reviewed exact SHA256 identities:

- Candidate002: `9930beff878848b05c8d69245fff12c1388f14254b6630504b36748c4c294366`
- Candidate002 hash manifest: `b5dfdacd527aac0f5de6388793f1f0b23ca8847759b6e4379bbd7505db608328`
- Prospective protocol: `fe8f0f04ae5c110ec0f36b2b42cc8758c46d10b8d9a06069825110d11b6c2092`
- Pure control source: `be69ba79fe946aec9b103449bd4a670144b1b92af2b47c09e1cdf258a13c0cd0`
- Fixture materializer: `36b096b926bf55e861fab9787c4390a6f6a9b331a134ef51ef53be099032a4dc`
- Design002 specification: `9de3cb9bdd8fc8b9a851a4424b8b16d699f849c3c33b441e27fb8178da7989f2`
- Design002 qualification plan: `d9256a1bc9341550641a4a509922f1d1643f6b58f52e3199c29c68fa1b9347fc`
- Preserved candidate001: `278a7a1cfe5eb43a396d4aefe01b124cbbb93a29f871d9a052ed1a04313bb708`
- Preserved reader identity recorded by the frozen manifests:7689 UTF8 bytes, `53694b8a233837339a51d9888b3d6ffd81b0c9a065a9fc1564d8a4d7217bf383`

STOP. This record grants no execution, installation or qualification authority.
