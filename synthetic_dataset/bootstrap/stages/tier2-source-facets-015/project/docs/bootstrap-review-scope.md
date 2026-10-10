# Specification: phase-bound adversarial review context

Written before implementation. The immutable `closed-computation-001` run passed
Lean acceptance, accepted-AST export, generation, linkage, all nine TESTED
campaigns, two clean builds and both original graders. Its release reviewer
abstained because the packet presented optional END_TO_END_VERIFIED as a current
PENDING milestone and offered CLOSURE:endpoint before native finalization. This
is a concrete control-context mismatch, not a reproduced behavioral failure.
Preserve that ballot, BLOCKED outcome and evidence seal.

Publish one deterministic review context, shared by packet presentation, trusted
checkpoint guidance, mechanical probe discovery and replay eligibility. It must
state the checkpoint, producer phase and normalized requested/resolved assurance:
tier, target, endpoint, required state and test policy. Prefer the frozen
implementation parameters for resolved policy; missing policy is explicit and
cannot invent a weaker assurance level. Keep actual recorded lifecycle outcomes.
Classify claims as CURRENT, FUTURE or OUT_OF_SCOPE separately from those outcomes.

Native release is a pre-finalization review checkpoint by workflow design. The
four exact, correctly shaped supervisor claims CLOSURE:clean-builds,
CLOSURE:determinism, CLOSURE:provenance and CLOSURE:endpoint belong to the subsequent
verify phase. Mark them FUTURE, retain required=true and disclose that final
verification must discharge them. This scheduling rule depends on their registered
producer and the backend's phase order, never merely on missing evidence. Invoking
native release after an earlier verification still reviews the artifact before
its next finalization; older closure observations do not replace that gate.
Do not exempt other internal/null-milestone claims, unknown CLOSURE identifiers or
malformed versions of these four definitions. VSCore release follows a validated
mechanical snapshot: its required closure and endpoint claims remain CURRENT.

Nonrequired or inapplicable milestone claims are OUT_OF_SCOPE for the decision,
with their observed outcomes retained as information. In particular optional
END_TO_END_VERIFIED is not a prerequisite for Tier 0 TESTED. Explicitly requested
END_TO_END_VERIFIED and every declared required applicable current claim remain
in scope, including unsupported requests and missing/stale current evidence.
The context must expose requested prerequisites even if corresponding stage
artifacts or claim inventories are absent. Earlier checkpoints retain their
producer-stage boundary. Unknown assurance policy preserves the existing broad
checkpoint scope; it cannot silently discard a current requirement.

Mechanical probe IDs admit only CURRENT required applicable claims and the
existing request-coverage probe. A future/out-of-scope probe is a bounded ballot
protocol error, allowing that same reviewer to construct a valid new probe; it is
never a counterexample. Current authorized failures still confirm, while missing
or stale current evidence remains unresolved. Concrete target/source/coverage
probe semantics stay unchanged. Hash the context into the review packet and bind
all source dependencies in registered verifier identities.
Claim identifiers must be unique within each inventory read by the checkpoint,
including the synthetic INTERPRETATION:request identifier. Reject conflicting
cross-inventory identities before classifying scope, regardless of row order or required/applicable flags:
an optional duplicate cannot conceal a required current failure. Packet/context
construction must expose a blocking ORPHAN_CLAIM diagnostic; replay must return
UNSUPPORTED for the ambiguous inventory and cannot confirm a selected winner.
Retain schema-valid duplicate counterexamples as unrelated regression fixtures.
VSCore's registered 0.2 implementation graph deliberately inherits contract
milestone claims with additional root/premise/statement metadata. Admit only
that explicit contract-to-VSCore inheritance, with every original claim field
unchanged and no repeated identity inside either inventory; use its enriched
record for replay. Field identity is canonical JSON identity, so true and 1 are
different. It cannot change requiredness, applicability, verifier, predicate or
any other original field. Other cross-inventory repetitions block. Every replay
kind checks inventory ambiguity before executing its particular probe.
Published probe templates must respect each kind's exact closed fields. A
source_violation rule illustration uses a syntactically valid registered rule
name, with the existing label that templates are not searches or observations.
Template tests must not add missing_requirement's byte/quote fields to that kind.

This change provides scope information, not an acceptance instruction. Valid
ABSTAIN and REJECT votes, reviewer membership, consensus denominators, higher-tier
escalation, receipt replay, artifact roots and all strict gates remain unchanged.
Final native verification still requires current provenance, endpoint capability,
two clean builds, reproducibility and every configured accepted review. No new
END_TO_END_VERIFIED capability or positive task artifact is introduced.

Use unrelated metadata/identity-function fixtures to check guidance/packet parity,
native future-claim discovery and replay, explicit unsupported requests, current
missing/failing claims, malformed/unknown internal claims, preserved abstentions,
kernel-bound full-pipeline closure and VSCore's post-mechanical pending-claim veto.
Retain failures and exact check results. Only after that and the preceding seal,
freeze a new source/specification root and run the original D21 prompt with fresh
roles, no prior answers or grader feedback, and every strict gate active.
