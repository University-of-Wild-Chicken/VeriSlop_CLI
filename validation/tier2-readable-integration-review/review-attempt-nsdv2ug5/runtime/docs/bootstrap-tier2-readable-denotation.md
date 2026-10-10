# Tier 2 readable source denotation, milestone 1

This specification is frozen before implementation. It implements the accepted
design in `validation/tier2-readable-view-design-013/design-v2-module-bound-20261010T034049Z-790249cc`
(specification SHA-256 `27ebcb558b1c2dc63ca97ce8b1ef5c80b8368a58d59eb857cc433f7f7257cb09`),
the minimal recipe delta `42a1ddd138f3beaaacdb424c7cffcdc870db2b6316bcabb444f4c7a67393ce38`,
and the selection API delta `4dbdc1243080ec38efb1e690f28c74c491c314312139cce4d8fe4c5dfad4e943`.
Independent review discharged 272 design checks; it did not qualify an
implementation. The existing closure protocol and three-state lifecycle decision
rule are unchanged. Optional view statuses never assign a lifecycle outcome.

## Claim and preserved boundary

The optional view proposes readable total Lean functions from exact finalized
VSCore 0.3 source. A CHECKED view requires kernel replay of an exact universal
equality with every actual intrinsically compiled entry and helper. It proves
no accepted-reference behavior or guarantee. Existing source bytes, source and
proof slots, relation validation, profile, nominal identities, adapters,
`source_fn_*`, required universal `Refines_*`, source-only facet treatment,
`EdgeProp`, obligation-ID-specific accepted transfers, raw evaluator laws and
admitted raw coverage remain unchanged. There are no new axioms, import roots,
trust assumptions, source capabilities, runtime bounds or inference timeouts.

Observed generic compiler-normalization difficulties motivate this support.
No retained task source, proof, case, carrier, expected result or corpus history
is inspected or supplied to new authors or generic tests. The support never
generates a task program or accepted refinement proof. Changing accepted
reference or guarantee bodies with identical source and body-independent registry
must leave the readable source block and typed rendering metadata byte-identical;
full acceptance bindings must still change when their inputs change.

## Closed rendering surface

The first renderer covers 39 of the 41 current `VSCore3.Expr` constructors:

```
var nat int string bool unit enum bin not ite letE ok error matchResult
record project none some matchOption nil cons matchList call listFold natFold
intNeg intFdiv natToInt intToNat listLength listRange listGet listAppend
listReverse listSort listUnique listMap listFilter listSum
```

`variant`, `matchVariant`, variant-dependent types, future constructors and
unmappable carriers make the whole optional view unavailable. This does not
narrow base source admission. The view covers every entry and helper, including
unused helpers; there is no partial CHECKED inventory.

Supported types are mathematical Nat, Int, Bool, String, Unit, exact accepted
finite Enum, Result, Option, List, and acyclic nominal records with arbitrarily
nested supported fields within the view budget. Representations are the existing
`Shape`/`Denote` carriers. Records use their exact ordered product payload ending
Unit. Result uses Sum, with error on the left and ok on the right. Enum uses the
exact registered membership subtype; no second accepted identity is invented.

The renderer preserves compiler-selected operations: saturating Nat subtraction;
signed Int arithmetic and total `Int.fdiv`; `Int.ofNat`/`Int.toNat`; Bool-valued
`decide` comparisons and typed `denoteDecidableEq`; Unicode scalar construction
using `String.ofList` and `Char.ofNat`; `List.get?Internal`; ascending
`mergeSort (fun a b => decide (a ≤ b))` for Nat/Int/String; `eraseDups` on the
currently admitted scalar carriers; and the exact range, length, append, reverse,
map, Bool filter and Nat/Int sum operations. It applies no algebraic optimizer.

The per-constructor matrix in the sealed design fixes the precise operation,
type and binder rule for each of these constructors. It is a semantic checklist,
not a requirement to emit one theorem per source expression.

## Intrinsic and named interfaces

For each source function `f`, `P_f` contains resolved parameter Shapes in declared
order and `R_f` is its exact resolved result. `readable_run_f` has type
`Env P_f → Denote R_f`. Its body sees `Env P_f.reverse` through exactly
`envReverse P_f`. `readable_named_f` accepts named parameters in declared order
and constructs the exact right-nested Env tuple ending Unit. Zero arguments use
Unit. Named conversion is definitionally equal or universally kernel-checked.

The source de Bruijn environments remain:

* Entry/helper body: reversed declared parameters.
* Let and Option/Result payload branch: new value followed by the outer scope.
* List cons branch: tail, head, outer scope.
* Map/filter body: item, outer scope.
* List fold step: item, accumulator, outer scope; host foldl lambda is accumulator
  then item.
* Natural fold step: accumulator, Nat index, outer scope; host Nat.rec lambda is
  index then accumulator.

Captures remain immutable outer values. Helpers receive captures through explicit
source actual arguments only. Named helper definitions preserve sharing. Their
inventory records source index and normative compiler scheduling order/context;
the actual helper is found in `checkedProgram.helpers.find?`, never assumed equal
to a helper freshly recompiled under a different final context. Entries use the
actual `findEntry`. Lookup and signature equations bind the exact compiled run.

The required `RunEquals` interface permits only checked parameter/result equality
transport and quantifies every intrinsic environment:

```
∃ hp : compiled.params = P_f, ∃ hr : compiled.result = R_f,
  ∀ args : Env P_f,
    hr ▸ compiled.run (hp.symm ▸ args) = readable_run_f args
```

The generic library names this exact predicate `VSCore3.ReadableRunEquals`.
Each generated `RunEquals_*` definition applies it to the actual compiled lookup
and the readable parameter/result/run declarations; the independently derived
Expr expectation checks that complete application. This avoids relying on a
host reconstruction of Lean's elaborated equality-recursion proof terms.

Accepted-carrier readable wrappers use the original adapters and declared-order
Env tuple. Every bound symbol requires universal unchanged source_fn/readable_fn
equality and the same encoded raw-evaluator equality, derived through the existing
raw law. True, self-equality, missing binders, restricted domains, different
helpers and similar-but-different Shapes are rejected.

## Finite checked recipe

A single typed structural pass proposes Lean terms and explicit binder/layout
metadata from source and the body-independent source/enum registry. Its host type
inference is untrusted. The first universal recipe is fixed
`intro env; with_unfolding_all rfl` for each actual entry/helper function, with
closed constructors for the exact parameter/result witnesses where needed.
This is whole-function equality for every Env, not evaluation of runtime samples.

Kernel conversion reduces closed source/compiler scheduling, Shapes, casts and
environment administration to total symbolic functions. It can also reduce
source-closed mathematical terms under the existing frozen build/kernel policy;
successful unbounded normalization is not promised. No arbitrary search, model
tactics, broad cbv optimizer or manual task proof is used. Registered adapter/raw
laws have a deterministic wrapper recipe. A targeted generic helper-law variant
must have a closed term-generation rule and catalog hash before qualification.

Failure of the fixed universal recipe is explicit `OPTIONAL_UNAVAILABLE`, with
the underlying error/budget/resource reason. It never weakens the equality or
the declared coverage. No per-expression proof inventory is required when those
proof declarations are not emitted. Every declaration actually emitted is audited.
Compiler-expression normalization/prettyprinting is a separate deferred prototype.

## Two-phase selection and exact replay

First compile and kernel-admit the byte-identical base goal. Base failures retain
their existing codes/severity; INPUT_MUTATION and base/shared toolchain, library,
contract, sandbox or kernel infrastructure failures are hard. Only after base
admission may a separate isolated append-only enrichment be attempted. It keeps
the complete base text unchanged, adds the canonical source-only block and exact
correspondence wrappers, and must preserve original declaration identities and
the proposition hash. There is no new dynamic imported goal module.

Before proof authoring, freeze either CHECKED enrichment or BASE with explicit
unavailability. Optional-only coverage, generation, compile, correspondence,
inventory or resource failure may select the admitted base. All reported errors
receive a compact row and a bound full artifact; overflow is visibly incomplete
and never CHECKED. Once CHECKED is frozen, every proof preview, acceptance,
published verification, materialization, link and closure replay must regenerate
that exact selection. Failure is blocking/infrastructure; no silent BASE fallback
is permitted, even if the proof does not use support. BASE cannot name absent
readable helpers. Legacy no-sidecar candidates are strictly BASE.

The concrete API is:

```
preview(pkg, source, relation_bytes, proof=None, obligations=None, *,
        readable_selection: bytes | None = None, select_readable: bool = False,
        readable_diagnostics: dict[str, bytes] | None = None)
```

Selection is allowed only on the first proof-free source preview with
`select_readable=True`. Default missing metadata preserves legacy BASE. Every
later call passes identical selection bytes and `select_readable=False`.
Returned info preserves original fields and telemetry, and adds
`readable_selection`, `readable_source_view`, `readable_artifacts`, and
`readable_candidate_artifacts`. The agent retains the files, attaches the bounded
packet, and carries exact candidate metadata through successful or exhausted proof
search. Backend repackaging replays those bytes; it never reselects support.

Unavailable BASE selections can reference volatile preview diagnostics. Replay
copies the exact frozen bytes instead of regenerating them. The shared loader
`readable_candidate_metadata(selection: bytes, read_bytes: Callable[[str], bytes])`
validates canonical closed selection schema, fixed diagnostic paths/slots/roles,
independent hashes and sizes, then returns exactly selection and declared
diagnostics. CLI/backend use regular-file PackageReader and recheck it. They pass
the diagnostic map, excluding selection, as `readable_diagnostics`; missing, extra
or mutated bytes are rejected. Agents preserve the map across proof retries.

CLI selection is explicit and advisory: mutually exclusive `.3`-only
`--readable-view` selects on a source-only call and rejects `--proof`;
`--readable-selection PATH` replays exact metadata and can check a proof. No flag
preserves legacy BASE. CLI persists artifact/candidate maps, excludes bytes/maps
from JSON summaries, and exposes the bounded packet and selection ref/hash.
Adjacent diagnostic reading uses the candidate root derived from the fixed
`support/readable/selection.json` suffix and the shared loader.

Context stores selection and `readable_diagnostics` separately from the original
five inputs. GoalSpec
retains `base_text` and selected `text`. Build stores canonical `readable_support`
and exact `readable_artifacts` separately from volatile process evidence. Existing
derive_goal/run_build interfaces reproduce frozen selected support for all callers.

## Identity, schemas and durable evidence

Fixed metadata identities are slot `vscore-readable-selection`, role
`readable_selection`, path `support/readable/selection.json`, format
`verislop.vscore-readable-selection/1`. The closed schema is
`urn:verislop:schema:vscore-readable-selection:1`. Its status is an untrusted
request until independently reconstructed and replayed. Plan/artifact roots bind
it before acceptance; source/proof slots and relation remain unchanged.

The authoritative accepted sidecar is `readable/manifest.json`, format
`verislop.vscore-readable-view/1`, closed schema
`urn:verislop:schema:vscore-readable-view:1`. Both schemas use closed named objects,
exact version/budget/identity fields, unique ordered inventories, CHECKED/BASE
consistency and safe nonredirectable refs. Schema validity alone is not evidence.
The source-only key excludes accepted bodies; a separate binding inventory covers
full source/profile/accepted IR/certificate/relation/adapter/renderer/recipe/goal/
policy/toolchain identity. The CHECKED descriptor binds full goal module parts.

Every emitted support definition/theorem/auxiliary, even unused, has exact
name/module/kind/safety/universe/type/dependency/axiom inventory. Unknown or missing
declarations, unsafe/partial/skipped support, opaque/new axioms, unresolved refs,
extra levels, sorry/native_decide/extern/implemented_by and unregistered imports
are rejected. Definitions require exact existing exported body/type hashes.

Theorems use honest `MODULE_BOUND_PROOF`: exact independently expected type,
actual complete value_constants, safety/levels/kind, staged dependency inventory,
toolchain closure anchors, actual transitive axiom/unknown walk, exact regenerated
source and full compiled module parts. The pinned kernel replays their actual
bodies. Individual theorem proof-body AST/digest is UNAVAILABLE and `body_hash`
is null; decl_hash is never described as hashing a proof value. No exporter
expansion is required. A same-type proof substitution must fail source/module/
inventory binding. Missing actual refs or module binding cannot pass. Actual
support axioms must be allowed and within the frozen admitted-base baseline,
including unused support roots; no new logical assumption is introduced.

Certificate, implementation IR, evidence result and deterministic build schemas
receive explicit readable_support descriptors. Outputs persist source block,
standalone source, typed metadata, correspondence, current exports, inventories,
proof-identity records, full diagnostics and selected goal. Existing accepted
module parts bind the support embedded in the goal. Current `verify_published`
is the accepted semantic verification path; no nonexistent verify_accepted API
is assumed. No-rebuild verification checks all bindings; rebuild verification
freshly repeats selected support twice. Closure freezes exact selection files,
freshly regenerates all support from source, retains every artifact and compares
the complete readable_support output alongside existing deterministic outputs.

Compiler telemetry is separately qualified and owned. Preserve its actual argv,
returncode, timeout/resource and stream digest observations; missing measurements
are unavailable. View work does not weaken build policy or overlap telemetry
helpers. Volatile process observations remain outside deterministic descriptors.
For multiple phases, preserve completed compiler records under phase-qualified
keys such as `BASE::<module>` and `SELECTED::<module>`; each record retains its
actual input.module. Never overwrite repeated invocations. Preview and raw
evidence retain the full combined map, including optional-failure records. These
volatile observations never enter readable_artifacts or deterministic descriptors.
Legacy single-phase inventory keys are unchanged. No kernel telemetry is invented.

Closure's `readable_support` comparison slot is null for legacy; otherwise it is
the closed object `{descriptor: Build.readable_support, artifacts: {path: sha256}}`
for the complete exact Build artifact map. `readable_artifact_refs(descriptor,
read_bytes)` validates the accepted manifest/ref set and returns exact path/hash
bindings, including manifest itself. The selected BASE artifact map still binds
its manifest, selection and declared frozen diagnostics. Original materialization,
link and implementation-selection schemas remain unchanged: their existing bridge
roots and selected goal/module replay already bind support. The implementation
folder keeps source plus the original materialization record.

## View-only numeric budget

```
source_ast_nodes=4096 source_ast_depth=128 helpers=128 entries=64
type_depth=64 total_record_fields=4096 max_call_arity=64
generation_steps=2000000 source_block_bytes=2097152
correspondence_bytes=8388608 typed_ir_bytes=16777216
support_declarations=65536 support_export_bytes=67108864
manifest_bytes=4194304 optional_stdout_bytes=16777216
optional_stderr_bytes=16777216 optional_kernel_response_bytes=67108864
diagnostic_display_chars_per_row=240
```

Count before emission and preserve helper sharing. These limits constrain only
optional generation/audit, not admitted execution. Existing frozen compile/kernel
timeouts, memory and isolation remain unchanged. OOM requires actual resource
evidence; unexplained process exits are tool failures. Output truncation is never
represented as complete diagnostics or CHECKED support.

## Qualification before a fresh task run

Fresh unrelated generic fixtures must kernel-pass universal correspondence for
all 39 constructors, supported scalar/nominal/nested types, captures, matches,
lets, list/natural folds and shared acyclic helpers. Variant/matchVariant must
explicitly fall back to BASE. Meaningful negatives include typable same-sort
parameter/helper argument swaps, list-fold item/accumulator swaps and Nat-fold
index/accumulator swaps; stale source/profile/adapter/renderer/goal/module refs;
weakened theorem types; unused forbidden support; and same-type module-bound proof
substitution. Accepted-body independence is checked separately from full binding.

Test source-preview→proof retries→candidate return→backend repackaging selection
identity, optional initial fallback, hard base/mutation failures, and frozen
CHECKED no-downgrade across every replay path. Validate closed schema negatives,
durable full-error artifacts and original obligations/transfers/raw coverage.
Two clean isolated builds/replays must reproduce every selected support artifact
and inventory. Passing readable syntax, schemas or finite samples does not qualify
this milestone. No fresh task/model run is authorized by an incomplete generic
qualification. Reports distinguish design, implementation, kernel checks and the
future task outcome; historic frozen runs are never rescored.
