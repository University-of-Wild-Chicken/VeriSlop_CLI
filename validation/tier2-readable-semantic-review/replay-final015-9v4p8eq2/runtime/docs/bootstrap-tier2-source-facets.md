# Typed source guarantees for the revised Tier 2 contracts

This specification precedes the next source-facet implementation. The revised
delivery has been explicitly selected by the user. Preserve every functional
requirement and required identity; retain the original Python contracts unchanged.
Changing the delivery boundary does not permit dropping its remaining source
guarantees or replacing them with reflexive value equalities.

## Closed authoring and accepted reconstruction

Add a distinct source_requirements authoring map and source theorem facets. Closed
requirements are entry(file, entry, arity), typed_total, deterministic,
input_preserved, no_external_io, no_floating_point, pure_data and
restricted_runtime_only. The sole supported file is program.vscore.json. Entry
names are valid VSCore identifiers and must bind the exact accepted endpoint and
arity. Unknown constructors/parameters, Python paths and unbound endpoints block.

Use a separately pinned SourceBoundary Lean requirement algebra, with closed
SourceDefinition(endpoint, requirements). Its Contract theorem proves requirement
checking soundness and model inhabitation; this is an abstract contract rule,
not evidence about delivered source. Preserve this distinction in the report.
Independently replay the normative library, compare all normative declaration
hashes, and reconstruct definitions, endpoint identity, requirements, source hashes
and value projections from accepted Lean constructors. Original author JSON has
no authority after acceptance. Do not share the Python NativeBoundary namespace,
encoding, version or source checker.

The accepted package encoding is verislop.source-contract-facets/0.1, with source
facets and an optional value package. Mixed statements retain the complete
accepted theorem, require its replayed value projection, and preserve every
required obligation ID. Readers dispatch explicitly on this encoding; unsupported
backends reject it. Its accepted IR representation is source_facets.

## Exact source discharge

Extend VSCore3's normative semantics with an observation containing the actual
evalEntry result, unchanged argument snapshot and an effect trace. The language
has no effect/state/float constructors; its observation trace is empty and its
argument snapshot is the original immutable value. Prove these exact observation
properties, deterministic evaluation and checked-entry total typed evaluation in
the pinned kernel. This models restricted-source execution; it says nothing about
an arbitrary host interpreter, compiler or OS that later executes the artifact.

The supervisor derives source facts from the exact parsed/admitted program,
checked entry/signature and these semantic laws. Candidate-supplied fact flags,
traces, input snapshots or source-policy assertions are forbidden. Each boolean
fact used by the requirement checker must be accompanied by the corresponding
exact semantic or admission theorem; a literal true table alone is insufficient.
Raw argument coverage and representation laws remain mandatory.

For every source facet, the edge proposition includes the requirement-holds
statement for these supervisor-derived facts, exact typed-entry/observation laws,
and its accepted Contract theorem applied as the checking transfer rule. For
mixed facets, additionally require universal source-function refinement and
binder-preserving value transfer. A shared semantic proof may discharge several
IDs, but the claim graph retains each ID, requiredness and accepted statement hash.
Source-only facets bind their endpoint even without a value formula. Their
operational requirements do not constrain an otherwise unconstrained reference
body. Require universal functional refinement for endpoints used by value
formulas; keep typed coverage, exact evaluation and source adequacy for every
source-only endpoint.

Entry path/identity/arity must agree with actual delivered source and materialized
bindings, then be independently rechecked by linkage and closure. No model witness
or source-admission certificate by itself establishes IMPLEMENTED, LINKED or
END_TO_END_VERIFIED. Release requires the complete current claim graph and configured
concrete adversarial review; TESTED remains a separate unsupported capability here.

## Ordered gates

After the initial record/binder bridge gate, add generic map/filter/sum and test
their exact denotations. Then test this source-facet increment with unrelated pure
and mixed contracts, AST reconstruction, universal refinement, incorrect entry/
arity/requirements, forbidden host/native facets and mutation failures. Freeze
fresh sources before fresh A23 and D21 CLI runs. Record every attempted contract,
proof, diagnostic repair, review counterexample and terminal status. No old
positive program, hidden grader or oracle result enters author contexts.

## Native startup and failure records

Before any implementation inventory exists, a requested supported Tier 2 source
backend selects its own report schema. This selection describes the requested
capability only: it grants no state, accepted contract, implementation evidence or
established endpoint. Once implementation selection is frozen, that artifact
remains authoritative. Unknown versions produce an explicit capability diagnostic
and a valid blocked report rather than an internal schema exception.

The engineering gate must exercise the native CLI entry point, including its
initial closure report before the first interpreter call. Calling individual
stage APIs alone does not cover this boundary. Retain version and default-backend
regression checks alongside the full unrelated source-contract pipeline.

The simulated provider profile is an explicit frozen input at the production
configuration loader's canonical endpoint-profile filename. Resolve it through
the ordinary loader and broker configuration checks before publication. The
native startup regression must exercise that resolution and reach the exact
mailbox transport; a stubbed provider resolver does not cover this boundary.
Simulation identity and unavailable token usage remain explicitly reported.

A worker that exits before writing request/prompt.txt or creating model requests
still yields a durable INFRASTRUCTURE_FAILURE experiment result. Record its exact
worker receipt, stdout, stderr and observed zero calls. Missing artifacts are
diagnostics, never reconstructed accepted inputs or successful origin records.
Failure finalization must not replace the primary worker diagnostic with an
exception from an absent transcript. Earlier frozen attempts remain unchanged;
fixes require a fresh source freeze, engineering record and task stage.

## Required source facets and actionable criticism

The next increment adds an explicit specification input for required source
facets, keyed by obligation ID. Each row names the required canonical file, entry,
arity and closed source properties. Freeze and hash this input with the request;
it is a specification constraint, not accepted obligation IR or proof evidence.
For these revised tasks, every original required guarantee includes the globally
requested typed, total, pure source delivery for solve. Keep its complete value
formula wherever functional behavior is required. A mathematical result-existence
or equality theorem cannot replace the entry, effect or floating-point facets.
Do not infer absence of a value requirement from the obligation category: a safety
property or invariant can specify functional behavior. Default guarantees to value
plus source facets. Source-only rows require an explicit operational classification
in the revised request; for the retained tasks this covers their stated purity,
input preservation and exact-integer runtime guarantees.

Before proof generation, reconstruct source facets from the kernel-elaborated
contract and check every required policy row against the actual bound endpoint
and closed constructors. Missing or mismatched facets produce a specific
repairable diagnostic. Recheck the same constraint after acceptance and during
closure; changed policy bytes or omitted required IDs invalidate the result.
Ordinary CLI users can provide this policy for their declared interfaces. It
contains no candidate implementation, arithmetic algorithm or expected test value.
The accepted obligation JSON still comes from the accepted Lean artifact.

Critic packets must provide exact wire shapes for the current reconstructed
types and phase. Formal contract search encodes typed records with the existing
`python-v0_2` dict wire; generated VSCore source review uses its separate typed raw
record carrier. Retain and return
invalid-probe errors, including the required shape, to both the critic retry and
the formalizer repair. An unrelated non-vacuity theorem with an empty assignment
does not satisfy the requirement to construct a concrete software input. If
functional execution is available, require a well-typed functional input probe;
when a full statement is undecidable, permit an observable reference case citing
the exact public request clause. Unsupported searches retain their limitation
and cannot become evidence of a successful test or a counterexample.

Test this increment first on unrelated contracts: correct source facets, plain
value equations missing entry/effect requirements, alternate entry names, changed
policy bytes, correct record wires for each phase, malformed record wires, and vacuity
only searches. Then execute a fresh complete native gate and freeze a new task
stage. Retain the audited failed attempt and all its model artifacts unchanged.
