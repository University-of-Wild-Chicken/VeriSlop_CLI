# Generalizing VSCore: grammar and formal contract

Status: **implemented authoring and standalone source admission**, language `vscore/0.2`,
profile `pure-data/0.2`. The [surface EBNF](../grammar/vscore-0.2.ebnf) is implemented by the
Python authoring frontend; the [normative Lean modules](../verislop/lean/VSCore2.lean) decode
and admit its delivered canonical JSON. `vscore check` reconstructs that AST from replayed
Lean definitions and requires two identical clean builds.

The accepted-contract bridge still supports only `vscore/0.1`. Source admission assigns no
obligation milestone, `TESTED` campaign result or `END_TO_END_VERIFIED` claim. The
[examples](../examples/vscore-grammar/README.md) and
[Lean feature design model](../formal/VSCoreGrammarModel.lean) remain separate from those gates.

The language is a pure, monomorphic, first-order core. It generalizes the current
expression tree through data composition, helper composition and finite iteration. Each
extension has its own admission rules and proof obligations. Unrestricted recursion,
mutable state, external effects and concurrency belong to later semantic profiles.

## 1. Three layers

The **surface grammar** gives people and generation agents names, infix operators and
pattern syntax. The **resolved core AST** records explicit type/constructor identities,
de Bruijn local indices and fixed binder order. The **bridge profile** determines which
types and properties can cross from the accepted contract into that AST's semantics.

A successful parse establishes syntax. Static checking additionally establishes typing,
well-formed declarations, exhaustive matches, admissible features and acyclic dependencies.
A bridge additionally needs exact accepted reference correspondence and obligation transport.
These judgments have distinct evidence.

Canonical core JSON is the delivered source, interpreted by the closed `vscore-json/0.2`
decoder in Lean. The surface language is an authoring frontend whose output is that delivered
JSON. Certifying the original `.vsc` text requires a registered exact-byte surface parser and elaboration edge as described below.
The standalone source report names its exact scope and excludes the original surface text.

```bash
bin/verislop vscore compile --source examples/vscore-grammar/pure-data.vsc \
  --out /tmp/pure-data.vscore.json
bin/verislop vscore parse --source /tmp/pure-data.vscore.json       # advisory host check
bin/verislop vscore check --source /tmp/pure-data.vscore.json \
  --out /tmp/pure-data-source-check                            # new output directory
```

`compile` and `parse` explicitly report `authoritative: false`. `check` binds the exact
JSON bytes, supplied enum registry, registered library/checker hashes and pinned toolchain;
it checks parsing and admission equations in both builds, audits/replays their environments,
and reconstructs `implementation-ir.json`. Its `report.json` establishes source admission
only. The output directory must be new. Use `--profile PATH` to supply an enumeration
registry in the established authoring format, such as
`{"enums":{"Color":{"constructors":["red","blue"]}}}`. Without that flag, the CLI uses
the selected package's accepted profile when available, otherwise an empty enum registry.

## 2. Surface grammar

The implemented surface EBNF is in [vscore-0.2.ebnf](../grammar/vscore-0.2.ebnf). Its central productions are:

```ebnf
program = header, { type-declaration }, { helper-declaration },
          entry-declaration, { entry-declaration } ;
type = Nat | Bool | Unit | Enum(name) | Record(name) | Variant(name)
     | Result(error-type, ok-type) | Option(type) | List(type) ;
expression = existing-expressions
           | record-construction | field-projection
           | variant-construction | exhaustive-match
           | option-construction | list-construction
           | helper-call | list-fold | nat-fold ;
```

This excerpt is explanatory; the linked file supplies actual terminals, precedence and
lexical rules. For example:

```text
program "vscore/0.2" profile "pure-data/0.2";
record Pair { left: Nat; right: Nat; }
fn difference(p: Record(Pair)) -> Nat { p.left - p.right }
entry total(xs: List(Nat)) -> Nat {
  List.fold(xs, 0; acc, item => acc + item)
}
```

### Lexical rules and identity

- Surface files are ASCII. Space, tab, CR and LF separate tokens; `//` comments end at a
  line ending or EOF. Comments and whitespace are recognized only outside quoted tokens.
- Lexing takes the longest punctuation token (`->`, `=>`, `<=`, `==`, `&&`, `||` before
  their prefixes). Keywords match whole identifier tokens and are case-sensitive.
- Bare identifiers match `[A-Za-z_][A-Za-z0-9_]*`. Word terminals in the EBNF's syntactic
  productions (through `field-initializer`) are reserved, including `fold` and builtin type
  names. The character terminals in the lexical productions are not keywords. A reserved
  identifier needs quotation. Names and natural literals are indivisible lexical tokens.
- `@"legacy.id-with-hyphen"` denotes the exact opaque ID inside the quotes, matching
  `[A-Za-z_][A-Za-z0-9_.-]*`. There are no escapes, normalization, case folding or module
  path interpretation. Bare `x` and `@"x"` resolve to the same ID.
- Names are nonempty and at most 128 bytes. Natural literals are `0` or `[1-9][0-9]*`,
  at most 1024 digits. There are no signs, leading zeros, decimals or exponents.
- The host authoring frontend bounds source bytes at 1 MiB, names at 128 bytes, naturals
  at 1024 digits, declarations at 1024, expression nodes at 65536 and nesting at 256.
  Canonical decoding retains the 1 MiB/depth-256 limits. The standalone kernel source
  checker additionally limits delivered JSON to 16 KiB and uses the strict policy's build
  limits. A budget failure leaves verification incomplete; it never becomes a successful
  source-level result.

Bare `p.left` means field projection. The single opaque ID `p.left` is written `@"p.left"`.
There is no implicit application: `call helper(...)` is a first-order helper call, while
`variant Type.Constructor(...)` is a constructor. Function values and lambdas are absent.

### Operator and expression rules

Precedence, from lowest to highest, is `let`/`if`/`match`, `||`, `&&`, `==`, `<`/`<=`,
`+`/`-`, `*`, `not`, field projection. Repeated arithmetic and Boolean operators associate
left. Equality and comparison each permit one operator; `1 < 2 < 3` is rejected.
Parentheses permit a compound expression as an operator operand. Every `if` has an `else`,
so nested conditionals associate with their complete branches.

`let x = value; body` is an expression; `x` is in scope only in `body`. Branches end in
semicolons, and function bodies contain a single expression. There are no implicit statement
returns. Fold binder blocks bind names only in the step expression.

`list[T](e0, ..., en)` is explicit typed sugar for nested `cons` ending in `nil[T]`.
The desugaring must preserve left-to-right element evaluation. All other constructs below
remain explicit core nodes. Helper calls are preserved rather than textually inlined.

## 3. Resolved core grammar and canonical bytes

Here `Id` is a validated opaque ID, `Index` is a local de Bruijn index, and brackets denote
ordered AST arrays. These are constructor signatures, not surface syntax:

```text
Ty ::= nat | bool | unit | enum(Id)
     | record(Id) | variant(Id)
     | result(errorTy, okTy) | option(Ty) | list(Ty)

DataDecl ::= record(Id, [(fieldId, Ty)])
           | variant(Id, [(ctorId, [Ty])])

Function ::= (Id, [parameterTy], resultTy, Expr)
Program  ::= (language, profile, [DataDecl], [Helper], [Entry])

Value ::= nat(Nat) | bool(Bool) | unit | enum(Id, ctorId)
        | ok(Value) | error(Value)
        | record(Id, [(fieldId, Value)]) | variant(Id, ctorId, [Value])
        | none | some(Value) | nil | cons(Value, Value)

Expr ::= var(Index) | nat(decimalString) | bool(Bool) | unit | enum(Id, ctorId)
       | bin(Op, Expr, Expr) | not(Expr) | if(Expr, Expr, Expr) | let(Expr, Expr)
       | ok(errorTy, Expr) | error(okTy, Expr)
       | matchResult(Expr, onOk, onError)
       | record(Id, [(fieldId, Expr)]) | project(Expr, fieldId)
       | variant(Id, ctorId, [Expr]) | matchVariant(Expr, [(ctorId, Expr)])
       | none(Ty) | some(Expr) | matchOption(Expr, onNone, onSome)
       | nil(Ty) | cons(Expr, Expr) | matchList(Expr, onNil, onCons)
       | call(helperId, [Expr])
       | listFold(listExpr, initialExpr, stepExpr)
       | natFold(countExpr, initialExpr, stepExpr)

Op ::= add | sub | mul | lt | le | eq | and | or
```

Variant branch arities come from the checked declaration; a supplied arity is never trusted.
Projection resolves its record identity from the receiver's type. Constructors carry nominal
identity, so structurally identical declarations remain distinct types. Existing enumerations
come from the supplied registry (or the selected package's accepted profile); the program
cannot redeclare their constructors.
Values are finite trees. A typing relation checks field identities, payloads and homogeneous
list spines; raw malformed values are not admitted arguments. Empty option/list value types
come from the checked interface, while expression constructors carry their explicit type
annotations. The standalone Lean feature model abstracts field/branch IDs by resolved order;
it is not yet the normative core AST, value typing or evaluator.

The [wire schema](../schemas/vscore-source-v2.schema.json) supplies exact, closed fields
for every tag; the normative [Lean decoder](../verislop/lean/VSCore2/Decode.lean) preserves
this constructor structure. The canonical discipline is ASCII JSON, no whitespace, no escapes,
sorted unique object keys, no trailing bytes, natural literals as decimal strings, and JSON
indices restricted to canonical nonnegative integers at most `2^53 - 1`. Declarations,
parameters, fields, constructor payloads, branches and argument lists use arrays whose order
is semantic. A JSON object's sorted key order cannot stand in for field or parameter order.

Nominal declarations, helpers and entries retain source declaration order. Forward references
are resolved against the complete checked registry. Record initializers and variant branches
must occur in declaration order; the checker rejects reorderings, omissions and duplicates.
This avoids silently changing evaluation order during normalization. Header identifiers,
closed JSON shapes and source budgets are part of the versioned decoder specification.
The program has exactly `declarations`, `entries`, `helpers`, `language` and `profile` keys.
Record fields, variant payloads/branches and helper arguments are ordered arrays.
`none`/`nil` nodes use `element_type`; both fold nodes use `source`, `initial` and `step`.

## 4. Static admission

Write `D; F; Γ ⊢ e : τ` for typing under checked data declarations `D`, helper signatures `F`
and a local type context `Γ`. Program admission is:

```text
Admitted(P, profile) :=
  WellFormedDeclarations(P, suppliedEnumRegistry)
  ∧ TypeChecks(P)
  ∧ AcyclicNominalDependencies(P)
  ∧ AcyclicHelperCalls(P)
  ∧ RequiredFeatures(P) ⊆ AllowedFeatures(profile)
  ∧ ResourceAdmission(P, profile)
```

Compute `RequiredFeatures` from the entire resolved AST, including signatures, nested type
annotations, data declarations, unused helpers and all branches. Candidate feature lists
are advisory. A `List(Nat)` parameter requires `list` even when its body returns `0`.

The initial feature names are `base`, `nominalData`, `option`, `list`, `acyclicCalls`,
`listFold`, `natFold`. The implemented `pure-data/0.2` profile contains all seven. `base` retains
the existing scalar/enumeration/Result fragment. Features are permissions; a permission
for calls does not prove the call graph acyclic. Every feature's checker and semantics must
be registered before admission. The [Lean design model](../formal/VSCoreGrammarModel.lean)
formalizes feature derivation and finite profile admission only.

### Declarations, calls and binders

- Type IDs are globally unique across records, variants and accepted enums. Helper/entry IDs
  share a separate function namespace and must be unique. Local names, field IDs and
  constructor IDs have their own scopes. Duplicate decoded IDs are rejected, including
  collisions between a bare spelling and its quoted spelling.
- Record fields and variant constructors are unique within their declaration. Empty records
  are allowed; variants have at least one constructor. Parameter/pattern/fold binder groups
  have distinct names. A nested `let` may shadow an outer binding.
- Reject every cycle in the nominal type dependency graph, including dependencies through
  `Option`, `List` and `Result`. The finite recursive structure of builtin lists has its own
  semantics. User-defined recursive datatypes need a later positivity/termination design.
- `call` targets a helper, with exact arity and argument types in declaration order. Entries
  are external roots and cannot be called from expressions. The supervisor derives every
  helper-call edge, including edges in branches and fold bodies, and computes a topological
  rank. No caller-supplied rank or hidden branch can authorize recursion.
- An entry/helper body uses `Γ = reverse(parameterTypes)`. Named elaboration resolves the
  nearest binder, yielding the same index convention as VSCore 0.1.
- `let` pushes its value at index 0. Constructor-pattern binders in written order
  `[x0, ..., xk]` push `[xk, ..., x0]` before the outer environment.

### Data and match typing

Record construction supplies every field exactly once, in declaration order, with its exact
declared type. Projection accepts only fields of that nominal record. Variant construction
has the declared payload count/types. Variant matches cover every constructor exactly once,
in declaration order; each branch binds exactly its payload count. Nested patterns, guards
and wildcard branches are absent in this version.

Builtin matches have these exact branch orders: `ok, error`; `none, some`; `nil, cons`.
All branches have the same result type. Both Result branches bind one payload. `some` binds
one element; `cons(head, tail)` binds two values, making `tail` index 0 and `head` index 1.
Enum matching is not added; enum equality and `if` remain available.

`ok[E](v)` has type `Result(E, type(v))`. `error[T](e)` has type `Result(type(e), T)`.
`none[T]` has type `Option(T)`, and `nil[T]` has type `List(T)`. `cons(h, t)` requires
`h : T` and `t : List(T)`. The explicit annotations avoid guessing a missing payload type.

### Finite fold typing

```text
Γ ⊢ xs : List(A)       Γ ⊢ initial : B       [A, B] ++ Γ ⊢ step : B
----------------------------------------------------------------------------
Γ ⊢ listFold(xs, initial, step) : B

Γ ⊢ n : Nat           Γ ⊢ initial : B       [B, Nat] ++ Γ ⊢ step : B
----------------------------------------------------------------------------
Γ ⊢ natFold(n, initial, step) : B
```

For `List.fold(xs, initial; acc, item => step)`, `item` is index 0 and `acc` index 1.
For `Nat.fold(n, initial; index, acc => step)`, `acc` is index 0 and `index` index 1.
The different written binder orders are intentional and frozen. These binder blocks do not
create runtime closures or permit unrestricted self-calls.

## 5. Evaluation and termination

Use mathematical `Nat`, with truncated subtraction and no overflow. Equality is structural
value equality at a single checked type, including nominal identities and finite list contents.
Boolean `&&`/`||` are strict. `if` evaluates its condition and selected branch only; matches
evaluate their scrutinee and selected branch only. `let` evaluates its initializer before its
body. Constructors, binary operands and call arguments evaluate left to right. Record fields
evaluate in declaration order. There are no source exceptions, implicit coercions, division,
unchecked indexing, mutation or external effects.

Helper calls evaluate argument values in declaration order, then execute the helper body in
the reversed argument environment. A helper's context contains its parameters, not its
caller's locals. Fold steps retain the lexical outer environment of the fold expression.

For a typed fold step, let `stepρ` denote evaluation in that environment:

```text
listFold([], initial, stepρ) = initial
listFold(item :: rest, initial, stepρ) =
  listFold(rest, stepρ([item, initial] ++ ρ), stepρ)

natFold(n, initial, stepρ) = iterate(0, n, initial)
iterate(i, 0, acc) = acc
iterate(i, remaining + 1, acc) =
  iterate(i + 1, remaining, stepρ([acc, i] ++ ρ))
```

Evaluate the list/count expression first and the initial expression second, once each.
The list traversal follows its original immutable spine, even if the accumulator contains
lists. Nat iteration visits exactly `0 .. n-1`. Nested folds are allowed.

The checker resolves nominal declarations and helpers in dependency order, rejecting a
pass that makes no progress. It compiles accepted expressions into intrinsically typed Lean
functions `Env Γ → Denote τ`. Helper calls invoke previously resolved functions; finite list
and Nat folds use Lean's total recursors. Checker budgets are derived from the expression/type
size. Execution does not use evaluator fuel or turn budget exhaustion into a source value.

`evalEntry` first checks the program and decodes arguments against the compiled entry
signature. Its boundary faults are `invalidProgram`, `unknownEntry` and `invalidArguments`.
The latter covers incorrect arity and malformed values. Typed, successfully decoded arguments
execute the total function and produce an encoded result. The normative module proves
`evalCheckedEntry_sound`, `checkProgram_sound` and `evalEntry_deterministic`. The
`checkProgram_source_sound` theorem additionally connects the compiled entry and encoded
result back to its actual source declaration/result type; the structural value comparison
module proves `valueEq_eq_true` and provides a lawful equality instance.

`Result.error` is an ordinary typed source value. Parse failures, type errors, unknown
entries, arity faults, unsupported capabilities and infrastructure failures are separate
outcomes. Well-typed execution must be proved free of evaluator faults. Source totality
does not establish wall-clock time, physical memory bounds or arithmetic bit complexity.

## 6. Formal obligations and accepted-artifact authority

The source gate proves `ExactCoreBytes` and `CheckedProgram` for each checked artifact.
The normative library supplies progress/preservation for checker-produced entries and typed
decoded arguments, plus determinism. `EntryRefinement` below remains a required future bridge
proof; standalone source admission does not establish it.

```text
ExactCoreBytes:
  VSCore2.parseSource exactDeliveredBytes = ok rawProgram

CheckedProgram:
  VSCore2.checkProgram suppliedEnumRegistry rawProgram = ok entrySignatures

CheckerSound:
  Checked(P) ∧ TypedArguments(P, entry, args)
  → ∃ v, evalEntry(P, entry, args) = ok v ∧ HasType(v, resultType(entry))

Deterministic:
  Eval(P, entry, args, v1) ∧ Eval(P, entry, args, v2) → v1 = v2

EntryRefinement:
  ∀ x, AcceptedPre(x) →
    evalEntry(P, entry, encodeArgs(x)) = ok(encodeResult(reference(x)))
```

The intrinsic evaluator's Lean termination/type checks cover folds and helper calls.
`checkProgram_compiled` derives existence of a compiled program from the successful checker
equation. `CheckerSound` requires `ArgsTyped` for that exact checker-produced entry; arbitrary
raw argument values remain outside this premise. These model results do not prove host
execution, compiler correctness, physical resource bounds or a contract refinement.

If the delivered artifact is surface text, add exact equations and frontend preservation:

```text
parseSurface exactDeliveredBytes = ok surfaceProgram
elaborate acceptedRegistry surfaceProgram = ok rawProgram
SurfaceTyped(Γ, e, τ) → CoreTyped(elaborate(e), τ)
evalSurface(e, namedEnvironment) = evalCore(elaborate(e), indexedEnvironment)
```

Surface parsing, name resolution and sugar expansion are then part of the semantic edge.
Elaboration must be capture-free. Reading `.vsc` in Python and hashing a lowered JSON file
alone cannot establish the original text's meaning.

### Conservative embedding of 0.1

The [transport module](../verislop/lean/VSCore2/Transport.lean) implements constructor-wise
`embedTy`, `embedValue`, `embedExpr`, `embedEntry` and `embedProgram`. It proves type/value/
expression erasure round trips and injectivity, and that embedded programs have no new
nominal declarations or helpers. New version identifiers are explicit.

These are **syntactic embedding laws**. The following typing/evaluator correspondence targets
remain unproved; their statements must reuse the same enum registry:

```text
Typed₁(Γ, e, τ) → Typed₂(map embedTy Γ, embedExpr(e), embedTy(τ))

Checked₁(P) ∧ TypedArguments₁(P, id, args) →
  evalEntry₂(embedProgram(P), id, map embedValue args)
    = mapOutcome embedValue (evalEntry₁(P, id, args))
```

Preserve old parameter/binder ordering, nominal enum identity, error-first Result types,
truncated subtraction, strict Boolean operators and lazy selected branches. Identifier
well-formedness must come from the new successful decoder or checker: the current 0.1
`checkProgram` alone accepts some manually constructed invalid IDs. Existing 0.1 certificates
continue to bind their original source, semantics and version; they are not rewritten.

### Aggregate interface adapters

An internal record/list can be used to compute a scalar result before aggregate contract
types are supported. Each new aggregate entry port additionally needs an accepted Lean type
registry, representation and checked transport rule:

```text
HasType(encode(x), targetTy)
decode(encode(x)) = some(x)
HasType(v, targetTy) → ∃ x, encode(x) = v
Represents(v, x) → decode(v) = some(x)
```

These laws cover both accepted inputs and every target input admitted by the interface.
Field IDs, constructor tags, payload order and list structure are part of the representation.
Restricting the interface to a subset requires an explicit accepted boundary and invalid-input
semantics. Syntax does not enlarge the accepted contract DSL or create test oracles for opaque
terms. Every exact accepted obligation still needs a mechanically derived transfer theorem.

The implemented source checker reifies `rawProgram`, signatures and the supplied enum
profile from replayed Lean definitions; declarations and helpers are part of that accepted
AST. It derives feature requirements from the complete reconstructed AST rather than a
candidate feature list. The resulting normalized implementation IR binds its source hash and
frozen source-check root. It does not reconstruct executable Lean closures or bind an accepted
contract root, refinement theorem or obligation transfer. Those additional bindings belong to
the future registered 0.2 bridge. Candidate AST/JSON and reviewer agreement supply no lifecycle
milestone by themselves.

## 7. Concrete design checks

The [ordering examples](../examples/vscore-grammar/ordering.vsc) give exact expected values.
These additional examples expose errors the implemented frontend/checker and reviewers
must reproduce:

```text
// Syntax rejection: chained comparison has no production.
entry bad_chain() -> Bool { 1 < 2 < 3 }

// Exhaustiveness rejection: the missing case is witnessed by none[Nat].
entry missing_case(x: Option(Nat)) -> Nat {
  match x { some(value) => value; }
}

// Binder rejection: head and tail cannot both resolve to the same local ID.
entry duplicate_binder(xs: List(Nat)) -> Nat {
  match xs { nil => 0; cons(x, x) => x; }
}

// Type rejection: initial accumulator is Nat, but each step returns Bool.
entry wrong_step() -> Nat {
  List.fold(list[Nat](1), 0; acc, item => true)
}

// Call-graph rejection: evaluating f(0) would never return.
fn f(n: Nat) -> Nat { call f(n) }
entry recursive() -> Nat { call f(0) }

// Nominal graph rejection, including dependencies under builtin containers.
record Node { children: List(Record(Node)); }

// Identity rejection: these spellings decode to the same entry ID.
entry duplicate() -> Nat { 0 }
entry @"duplicate"() -> Nat { 1 }

// Capability rejection: no primitive, rule or profile permits file I/O.
entry effect() -> Nat { call read_file(0) }
```

Treat each snippet in its own otherwise well-formed header/declaration context. The I/O example
fails helper resolution; merely naming a helper `read_file` supplies no primitive behavior.
Also reject mutual helper cycles, references to entries, unknown/duplicate record fields,
incorrect variant payload arities, missing branches and undecoded quoted IDs.

A review rejection must identify exact bytes/AST nodes, the violated rule or exact accepted
predicate, and a reproducible checker failure or input with expected/actual output. Speculation
about a parser's reliability is not a counterexample. A bounded search without a counterexample
does not prove the grammar, checker or semantics sound. The finite frontend and kernel
conformance tests check concrete rejection cases and expected evaluation results; they do not
assign `TESTED` to a generated implementation or prove the Python frontend correct.

## 8. Implementation sequence and later profiles

Implemented: closed 0.2 AST/schema; exact Lean canonical decoding; static checking of nominal
and helper dependency DAGs; intrinsically typed records/variants/options/lists and finite folds;
progress/preservation and determinism; Python surface authoring; accepted-AST reconstruction
and two isolated source-check builds; syntactic 0.1 embedding round trips. Finite tests include
malformed bytes, dead-branch recursion, binder order, declaration/branch order, arithmetic above
`2^64` and structural equality of nested data.

The next registered bridge milestone must:

1. Bind exact accepted reference symbols and source entries, construct scalar/enumeration/
   Result adapters, prove input coverage and extensional refinement, and derive/verify each
   covered accepted obligation's transport statement.
2. Prove the full 0.1 typing/evaluator embedding correspondence above. Aggregate contract
   entry ports additionally need their accepted registry and representation/transport laws.
3. Bind all contract, source, statement and environment identities into frozen bridge/closure
   evidence. Register the new backend only after the full gate and rejection suite work;
   source admission alone must not enable obligation milestones or `END_TO_END_VERIFIED`.
4. Add exact surface parsing/elaboration and preservation proofs if `.vsc` is to become a
   certified endpoint. A VSCore `TESTED` campaign backend remains separate work.

Later profiles can extend the grammar through separately checked constructs: well-founded
recursion with explicit measures; local state and loops with state/trace semantics, invariants
and ranking functions; external effects with environmental contracts; concurrency with schedule
and fairness assumptions. Machine integers, allocation and cost primitives need representation
and resource semantics. A `while` syntax or a supplied invariant alone does not justify adding
any of these features to `pure-data/0.2`.

The registered Tier 2 bridge for `vscore/0.1` certifies its declared restricted-source
semantics; standalone 0.2 admission supplies no implementation assurance tier. Tier 3 needs its lowering
correspondence for every admitted constructor, call and fold; Tier 4 needs its machine and
environment chain. The existing [Tiers 2–4 specification](tier-2-4.md) continues to govern those
endpoints. Unsupported features or endpoints produce explicit capability failure throughout
the workflow; no downgrade, reviewer consensus or source-level proof closes a stronger endpoint.
