# Bound release-review display and explicit reviewer capacity

This specification precedes production changes. It addresses the closed trial006
release-review preflight failure: 91,176 input tokens plus 2,048 output exceeded
the configured 40,960. No release reviewer was dispatched. Mechanical verification
does not substitute for the missing release ballot.

## Scope and authority

Change only the model display for an already natively validated VSCore 0.3
post-mechanical release packet. Preserve the complete original `packet.json`,
mechanical execution and deterministic review-target projection. The native
validators, verifier inputs, registered concrete probes, mechanical veto, ballot
parser, configured reviewer identities and membership, consensus rules and final
release gates remain unchanged. No displayed receipt assigns a milestone or
review acceptance. Earlier checkpoints, Python and older VSCore backends retain
their existing prompt behavior.

The accepted Lean source remains complete and byte-exact, including its registry,
all function definitions, theorem statements and proof bodies. This increment
introduces no accepted-source or registry projection.

## Versioned display

Use `verislop.vscore-release-review-view/0.2`, retaining the existing top-level
packet reference, canonical packet hash and byte count, authority declaration,
explicit omitted-detail declaration, and projected packet. Preserve restoration
of historical 0.1 views using their original closed projection rule, without
imposing new 0.2 row requirements on those historical inputs. Emit 0.2
only for the eligible release scope.

Continue the existing references for
`mechanical_snapshot.execution_inventory` and
`mechanical_snapshot.builds[i].outputs`.
Add these exact display operations:

1. Replace `vscore.goal` with an exact packet-value reference. The complete
   generated native bridge module remains in the authenticated packet and native
   checker inputs. The visible accepted Lean source, delivered VSCore source,
   binding inventories, certificate and semantic interface remain unchanged.
2. Replace the opaque top-level `evidence` ID list with one exact packet-value
   reference.
3. For each `mechanical_snapshot.claims` row, display exactly `claim_id`,
   `outcome`, `required`, `premises`, `reason`, `root_kind`, and `verifier`, in the
   original row order. Add a single sibling `claims_details_ref` bound to the
   complete original `/mechanical_snapshot/claims` table. The only undisplayed
   row fields are `input_root` and `evidence_refs`.
4. Apply the same row projection to `required_mechanical_claims`, retaining every
   original row and its order. Add sibling `required_mechanical_claims_details_ref`
   bound to the complete original table. Do not derive or change membership from
   a model response. Validate equality with the original required-row filter.
5. For `mechanical_snapshot.provenance`, retain exact `claim_id`, `outcome`,
   `reason`, and `verifier` in the original row order. Add a single sibling
   `provenance_details_ref` bound to the complete original provenance table.
   Only its `evidence` field is undisplayed. Validate that these four visible
   fields equal the matching complete mechanical claim row.

All references retain the existing closed packet-value-reference fields:
`format`, `packet_ref`, exact JSON `pointer`, canonical value `sha256`, and
`utf8_bytes`. Use one reference per complete table, not one per row or hash.
Reference-shaped objects at other paths remain ordinary data. Reject unknown or
missing mechanical/provenance row fields before projecting, duplicate claim IDs,
missing matching claims, or inconsistent required/provenance inventories. Never
silently discard new fields.

Keep every other field exact: request, ledger and ambiguities, obligations and
formal statements, complete accepted source, actual implementation source and
materialization, scope, claim identities and dispositions, current review policy,
binder shapes, wire syntax and probe limits, build statuses and errors,
determinism, dependencies, trust and excluded surfaces, certificate and checked
binding inventory. Full registered predicates and trusted-dependency records
remain in native validated artifacts; displaying claim rows does not independently
validate those records.

## Supervisor context pointer

The current checkpoint guidance separately serializes the same complete
`review_context` already displayed in `packet.review_context` and
`packet.counterexample_policy.review_context`. For this bound 0.2 release display
only, replace that third value with a closed exact pointer to the fully displayed
`/packet/review_context`, including its canonical hash and byte count. This is a distinct closed
`verislop.review-view-value-ref/0.1` with `view_ref` equal to
`prompt-view.json` and `pointer` equal to `/packet/review_context`; it must
never claim that this pointer is relative to `packet.json`. Bind the complete
display hash and the selected context value hash/size. Require
canonical equality of the original two packet values and supervisor-selected
context before rendering.

Keep the guidance itself outside the untrusted packet. Compute all surrounding
supervisor fields from the ORIGINAL context, particularly `current_milestones`
and `outside_checkpoint_milestones`; a pointer is not the context object used by
those computations. Preserve checkpoint restrictions, allowed proposal templates,
producer phase, scope prose and final ballot-shape reminder. Use an explicit
pointer description that says the complete supervisor-selected value remains
inline; never ask the model to fetch an unavailable file.

Select a release-specific system variant only for the eligible 0.2 view; legacy
checkpoints/backends retain their exact existing system and user bytes. Bind the
ACTUAL dispatched system variant hash in `reviewer_configuration_hash`, both at
campaign creation and deterministic release-reuse reconstruction, and retain its
normal dispatch provenance. Do not hash only the unused base system template.

The release-specific system guidance must disclose that the generated native goal
and listed mechanical identity details are retained but not inline. The reviewer
must not claim to have inspected these omitted details. It can challenge current
mechanical claims through the unchanged independently replayed probes, and must
retain ABSTAIN when it cannot complete the current scoped review. All functional
source and required claim meanings remain visible.

## Binding and restoration

Projection follows existing full native snapshot validation. Its input remains
the already bound complete packet. Restoration receives the caller-authenticated
full packet, checks the global canonical digest, recomputes the exact expected
versioned projection and compares canonical bytes. Never resolve a filesystem
path chosen by a view. Check exact pointer, value hash and byte count; reject
coherently changed references, malformed view fields, and Boolean/integer identity
substitutions. A valid outer hash alone cannot authorize a changed projection.

Retain complete `packet.json` and deterministic `prompt-view.json`. Bind the
updated display implementation in the existing reviewer-configuration identity;
no model-resolution substitution is introduced. Do not mutate the full packet
while constructing the view, including nested rows.

The lossless exact-inline codec remains unchanged. Preserve raw rejected ballot
bytes and every actual validator diagnostic during protocol correction. The
projection does not guarantee that every future correction fits.

## Explicit next-trial capacity

The conservative display still exceeds the prior 40,960 reviewer context. Its
measured fit must not be described as a fix within that original capacity.
For the next fresh bounded qualification only, explicitly configure
`qwen-reviewer.context_window_tokens = 65536`, after checking the installed
model's declared capacity. Keep its model identity, 2,048 output allowance,
reviewer count and tier policy unchanged. Keep Qwen author/refiner and Pythagoras
contexts at 32,768 and all other budgets unchanged. This is an explicit run
configuration choice; do not widen defaults or other users' configuration.
No ordinary release-review Sol substitution is introduced.

Keep exact preflight and the 128-token safety margin. Measure the final production
system plus user serialization with the frozen tokenizer and chat template,
including output reservation and at least one exact retained malformed-ballot
response plus its real diagnostic. A previous unrelated release response may be
used only as representative context load, clearly labeled, never as this trial's
probe or evidence. New overflows remain explicit failures. Record observed
runtime GPU/CPU placement and resource behavior in fresh qualification; do not
infer full GPU execution or claim that advertised context capacity alone assures
performance.

## Required validation

- Reproduce trial006's recorded system, user and rendered-prompt hashes and its
  exact 91,176-token input count before comparing the new production prompt.
- Verify full-packet restoration and nonmutation, all preserved fields and exact
  row order, including Unicode and literal reference-shaped input.
- Reject changed paths/hashes/sizes, unknown/missing fields, duplicate IDs,
  mismatched provenance/required tables, altered scope/outcomes/premises,
  Boolean/integer substitutions and changed authenticated packet inputs.
- Preserve historical 0.1 restoration and legacy backend/checkpoint prompts.
- Exercise actual recording/dispatch with a fake transport: initial ballot,
  malformed-ballot correction, exact raw response and complete diagnostics,
  unchanged reviewer identity and full packet consumed by native replay.
- Retain meaningful unrelated native replay controls: confirmed concrete
  violations, nonreproduced probes, stale source/invalid binders unsupported,
  and source-only guarantees not converted into value oracles.
- Keep strict preflight rejection above an explicit configured capacity. Measure
  the final production initial and representative retry prompts under both the
  old and explicitly selected new capacity. Report measured headroom honestly.
- Run a fresh qualification under new source/configuration roots. Do not resume,
  re-label, or overwrite the closed trial006 result.
