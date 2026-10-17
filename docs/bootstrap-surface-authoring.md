# Selectable VSCore surface authoring for agents

This specification precedes implementation. Trial 003 reached Qwen generation
but produced malformed canonical JSON (missing helpers, named parameter objects
where sorts were required, and a string inside the entry list). The complete
correction request then required 26,067 input tokens plus 8,192 output tokens,
exceeding its 32,768 context. The rejected response remains unchanged.

## Interface and boundary

Add optional per-agent `vscore_authoring_format`, with values `canonical_json`
(the existing default) and `surface`. The latter applies only to the registered
VSCore 0.3 implementation role; an explicitly unsupported backend must fail
before dispatch. It is independent of provider/model selection. Other roles and
the ordinary default keep their existing protocols.

In surface mode the model returns exactly `program_source` (a UTF-8 string),
`relation` (the existing descriptor), and optional `proof_source`. Mixed surface
and canonical program fields are invalid. The complete source text is retained
verbatim as an attempt artifact. Compile it with the existing registered
`vscore3_source.compile_surface` and the exact accepted enumeration inventory,
then retain its canonical `program.vscore.json`. Run all existing schema, type,
source admission, refinement, readable-correspondence, bridge, review and closure
checks on those generated canonical bytes. Never repair the model's text or
silently switch modes. Compilation diagnostics enter the existing bounded
correction loop with the exact rejected response and complete diagnostic record.

The certified deliverable remains canonical `program.vscore.json` under
restricted-source semantics. Surface text is an authoring input and is not
itself certified; the host surface compiler is an explicit trusted translation.
No new semantic primitive, reference equation, implementation proof or task
solution is introduced by this increment.

## Model context

Surface authors receive the complete unchanged registered `grammar/vscore-0.3.ebnf`
and its exact binding instead of the canonical JSON source schema, because their
response is surface text. Retain the entire original fixed canonical-author
context once through the existing content-addressed memory, with its exact hash,
toolchain and selected grammar/compiler bindings. Restoration must authenticate
that retained snapshot and reconstruct the complete original context; no ambient
current file may substitute for a historical artifact.

All other fixed context fields remain exact, including accepted IR, accepted
formula packages, profile, parameters, required obligations, relation schema and
limits. The later author-only registry-display amendment below specifies the
sole additional display change to the accepted Lean reference. The full fixed context still drives
the checker and prover paths. The lossless inline codec compresses the selected
authoring context and the complete correction history already supplied by the
implementation loop. There is no context increase, output-budget reduction,
requirement deletion or positive example copied from the live task.

## Checks and qualification

Test configuration validation and unchanged defaults; exact grammar/snapshot
restoration and tamper rejection; surface-to-canonical dispatch with real parser
and checker inputs; accepted enum identity; invalid/mixed envelopes, malformed
source and complete correction feedback; legacy backend rejection. Structural
fixtures are engineering checks, never live model qualification.

Replay token counting on the retained G01 initial and actual failed-response
correction contexts with the same tokenizer and output reservation. Keep all
current failure evidence. After independent audit and relevant native checks,
freeze a new trial with the opt-in surface authoring configuration. Start from
the natural-language project request, with no supplied implementation or proof.
Report actual native results and constructor coverage only after full closure.

## Formalizer syntax reminder

Three retained G01 trials independently repeated the same invalid bare record
name at a type position before autonomous correction succeeded. Add a generic
reminder distinguishing declaration IDs from sort objects, with an unrelated
record signature example. This changes prompt guidance only; the accepted sort
grammar, validator, obligations and compiler remain unchanged. It must not supply
a project-specific formalization or proof.

## Author-only accepted-reference registry display

This amendment precedes production implementation. Surface-only
grammar selection still exceeds the retained trial003 source retry context by
1,040 tokens. Full ordered registry records and exact source segments reduce the
same retry to 23,484 input tokens; with unchanged 8,192 output and 128 margin,
31,804 of 32,768 tokens are required (964 spare). This fixes the measured request,
not every future correction request.

## Selected display

Apply only inside the opt-in surface-authoring view for the VSCore 0.3 implementation author. Canonical/default authoring remains unchanged. Keep original fixed
context, accepted source, checker/prover inputs and all acceptance gates intact.
The existing surface-authoring CAS checkpoint retains the original full context
once, including complete accepted Lean source.

Preserve accepted_reference.path and accepted_reference.sha256. Replace only
accepted_reference.lean_source in the selected author view with
accepted_reference.lean_source_display, a closed object containing:

- format: versioned author-reference-display identifier.
- authority: explicitly says display-only, not complete compilable source.
- before_registry and after_registry: exact UTF-8 slices around the generated
  registry; no whitespace normalization or reformatting.
- retained_registry: exact source field/path, byte start/end, byte count and
  digest, and bound certificate/environment references.
- registry_metadata.ordered_entries: every complete decoded native registry
  record in original order, with exact binding order and metadata values.

The full records matter: ten of fourteen trial003 registry dependency arrays
differ from accepted IR, because export mechanically reconstructs dependencies.
Binding lists and registry order also contain information absent from the IR's
single lean_symbol/dictionary order. Nothing is discarded or reconstructed by
assuming these values agree. Existing exact_context sharing removes only exact
repeated values. All other fixed fields and raw rejected responses/diagnostics
remain exact.

## Projection authentication

Read the accepted certificate and environment export using bound snapshot reads.
Verify certificate reference/content identity, gate accepted_and_proved, source
path and digest equality with fixed accepted_reference, environment digest equal
to both certificate artifact and accepted_ir.accepted_environment_hash, and
toolchain pin equal to fixed context and accepted IR. Fail closed on binding,
identity, malformed artifact or missing retained-artifact errors.

Decode ordered registry records from the accepted native environment using
contract.decode_registry. Require unique registry IDs and complete inventory
agreement with accepted_ir. Preserve their metadata verbatim; dependency equality
with exported IR is expressly not required. Check other applicable accepted
metadata identities without treating the registry as a new obligation source.

Regenerate the entire registry with contract.registry_lean(records, exact binding
lists). Projection requires byte-identical matching to exactly one full source
span. Marker text alone is insufficient. Retain the exact generated span and
bind the renderer source identity in the checkpoint. Preserve every byte outside
that span as the two display segments.

Conservatively inspect type/value constant references of native declarations
outside VeriSlop.Registry. If they reference registry declarations, keep the full
source author view with an explicit not-projected reason; the optimization must
not hide operative registry definitions. Legitimate unusual registry formatting,
multiple matches, unavailable supported registry shape or nonstandard placement
likewise retain the full view with an explicit reason. Corrupt bound inputs are
errors, not a reason to silently substitute current files. Full-view fallback
continues to obey the ordinary context budget and may explicitly overflow.

## Historical restoration

Extend the authoring snapshot with exact certificate, environment, decoded record
and renderer-binding artifacts as needed. References authenticate the closed
artifact inventory, digest and toolchain. Restoration reads only those retained
artifacts and original fixed context; it never substitutes a current package
environment file, source or current grammar. Verify complete record identity,
span offsets/digest and source slices against retained bytes. Reconstruct original
source from before + exact retained registry + after and require byte equality
with the original source and its accepted digest. Return the exact original full
fixed context, including all unknown fields; reject changed display fields,
records, extra/missing fields, stale references or changed artifacts.

## Engineering checks

Test actual retained initial/retry renderings with unchanged tokenizer/output
reservation; exact complete restoration; differing dependency/binding/order
records; malformed certificate/env/source/toolchain bindings; replaced native
registry spans; tampered prefixes/suffixes/records; operative native registry
references and legitimate unsupported shapes retaining the full source; historical
restore without ambient file reads; unchanged checker/prover bytes; defaults and
other roles unchanged. These are engineering fixtures, not live qualification.

## Alternatives measured

Generic repeated-object-layout arrays save at most 640 retry tokens and still do
not fit alone. A bespoke IR-plus-residual registry representation saves 3,205
tokens with 2,165 retry headroom, but adds a second metadata decoding language.
Prefer full ordered records and the measured 964 headroom. No output reduction,
context increase, semantic deletion or candidate implementation was used.

## Historical renderer and retention bounds

Optimized restoration reruns the installed pure registry renderer on the retained
ordered native records. It requires exact equality to the retained registry,
unique occurrence and supported header placement. A renderer whose output has
changed rejects that optimized historical view explicitly; retained executable
code is never run and current package artifacts never replace historical bytes.
Earlier surface-context format 0.1 retains its original restoration behavior.

Use the existing PackageReader artifact/package bounds to authenticate source,
certificate and environment inputs before considering display optimization. Keep
the existing agent-memory limits (2 MiB per artifact and 8 MiB per checkpoint).
If required display artifacts exceed those retention limits, retain a bound
size/limit/reason receipt and show the complete original accepted reference,
byte-for-byte unchanged. Do not retain a truncated environment, enlarge storage
limits, or describe an unretained environment as historically reconstructed or
authenticated. Corrupt or missing inputs remain errors, never size fallbacks.
The complete-source fallback remains subject to normal context admission.
