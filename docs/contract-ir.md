# Contract expression IR, version 0.1

This document specifies the finite expression core used by [specification.md](specification.md) §§5 and 7. It is a design requirement, not an implemented exporter or evidence of acceptance. The existing Lean fixture uses ordinary propositions; migration to this DSL is future implementation work.

MUST and MUST NOT are normative. The core supports pure first-order contracts over natural numbers, Booleans, unit, finite enumerations, and explicit results. Sequences, products, arbitrary sums, state, traces, cost models, higher-order functions, and polymorphic terms require later extensions or an opaque Lean expression. An exporter MUST reject unsupported constructors rather than approximate them.

## 1. Typed syntax and binding

Use judgments `Γ ⊢ t : S` for terms and `Γ ⊢ p : Prop` for formulas. `Γ` is an ordered stack of sorts with the newest binder at index zero. Variables use de Bruijn indices; display names do not participate in identity. Every published obligation formula is closed: `[] ⊢ p : Prop`.

The finite grammar is:

```text
S ::= Nat | Bool | Unit | Enum(enumId) | Result(errorSort, okSort)
t ::= var(index) | nat(decimal) | bool(value) | unit
    | enum(enumId, constructor)
    | add(t,t) | sub(t,t) | mul(t,t)
    | call(symbolId, [t,...])
    | ok(errorSort,t) | error(okSort,t)
p ::= true | false | eq(t,t) | lt(t,t) | le(t,t) | holds(t)
    | not(p) | and(p,p) | or(p,p) | implies(p,p) | iff(p,p)
    | forall(S,p) | exists(S,p)
    | forall_range(lo,hi,p) | exists_range(lo,hi,p)
```

`Result(E,A)` denotes `Except E A`; error is the first sort parameter. Enumerations have a registered nonempty ordered list of unique constructors. Enumeration IDs and symbol IDs resolve only in the accepted profile registry. They are not URLs or instructions to load code.

Typing requirements:

- `var(i)` has sort `Γ[i]`; an out-of-range index is invalid.
- `nat` accepts canonical unsigned decimal strings: `0` or a nonzero digit followed by digits. Arithmetic operands and results are `Nat`; subtraction is truncated subtraction.
- `bool` contains a JSON Boolean; `unit` has sort `Unit`; an enumeration constructor must belong to its declared enumeration.
- `call(f,args)` uses the complete ordered signature registered for `f`. Argument count and sorts must match exactly; coercions and implicit arguments are forbidden in this DSL.
- `ok(E,t)` has sort `Result(E,A)` when `t : A`; `error(A,t)` has sort `Result(E,A)` when `t : E`.
- `eq` requires equal operand sorts. `lt` and `le` require `Nat` operands. `holds` converts a `Bool` term to a formula by asserting equality to `true`.
- Connectives take formulas. General quantifiers check their body under `S :: Γ`.
- Range bounds are `Nat` terms checked in the outer `Γ`; only the body receives the new `Nat` binder. The interval is half-open: `[lo, hi)`.

No free variables, metavariables, implicit coercions, implicit typeclass parameters, partially applied calls, or overloaded arithmetic survive export. The Lean implementation SHOULD use indexed inductive types for `Sort`, `Term Γ S`, and `Formula Γ` so malformed syntax has no typed inhabitant.

## 2. Exact JSON node shapes

The notation below describes object shapes: capitalized placeholders are recursively encoded values, not literal JSON strings. Every shown field is required; additional fields and duplicate keys are invalid. Arrays preserve their specified order.

```text
Sort:
  "Nat" | "Bool" | "Unit"
  {"enum": ID}
  {"result": {"error": Sort, "ok": Sort}}

Term:
  {"tag":"var", "index": Index}
  {"tag":"nat", "value": DecimalString}
  {"tag":"bool", "value": Boolean}
  {"tag":"unit"}
  {"tag":"enum", "sort": EnumId, "constructor": ConstructorId}
  {"tag": NatOp, "left": Term, "right": Term}
  {"tag":"call", "symbol": SymbolId, "args": [Term,...]}
  {"tag":"ok", "error_sort": Sort, "value": Term}
  {"tag":"error", "ok_sort": Sort, "value": Term}

Formula:
  {"tag":"true"} | {"tag":"false"}
  {"tag": Relation, "left": Term, "right": Term}
  {"tag":"holds", "term": Term}
  {"tag":"not", "body": Formula}
  {"tag": BinaryConnective, "left": Formula, "right": Formula}
  {"tag": Quantifier, "sort": Sort, "body": Formula}
  {"tag": RangeQuantifier, "lower": Term, "upper": Term, "body": Formula}

NatOp           = "add" | "sub" | "mul"
Relation        = "eq" | "lt" | "le"
BinaryConnective = "and" | "or" | "implies" | "iff"
Quantifier      = "forall" | "exists"
RangeQuantifier = "forall_range" | "exists_range"
Index           = a JSON integer in [0, 2147483647]
```

IDs are case-sensitive ASCII identifiers matching `[A-Za-z_][A-Za-z0-9_.-]*`. User prose and display labels are separate metadata. Parsers impose registered byte, nesting, node-count, and index limits before allocation; exceeding a limit is a diagnostic, never a partial successful parse.

A referenced formula package has exactly these fields:

```text
{"encoding":"verislop.contract-dsl/0.1",
 "semantic_profile": ProfileId,
 "formula": Formula}
```

The enclosing accepted-IR envelope binds that profile to its hashed registry, accepted environment, acceptance certificate, and toolchain. A profile registry has an ID, numeric/result semantics, enumeration declarations, and symbol declarations. Each symbol declaration contains its ID, ordered argument sorts, result sort, Lean declaration reference, and all explicitly instantiated type/universe parameters where applicable. No mutable name lookup may replace those accepted declarations.

Formula packages carry no lifecycle state, proof assertion, implementation status, or test result. Obligation IDs/kinds and theorem bindings belong to the typed obligation registry; evidence belongs to the separate obligation view. Schema validity alone establishes none of those claims.

## 3. Lean denotation

Interpret each sort as its pinned Lean type. An environment supplies one value per binder. Interpret terms through total Lean functions and the accepted symbol registry:

```text
evalTerm : Term Γ S → Env Γ → SortDenote S
denote   : Formula Γ → Env Γ → Prop
denote (forall S p) ρ = ∀ x : SortDenote S, denote p (x :: ρ)
denote (exists S p) ρ = ∃ x : SortDenote S, denote p (x :: ρ)
denote (forall_range lo hi p) ρ =
  ∀ n : Nat, evalTerm lo ρ ≤ n → n < evalTerm hi ρ → denote p (n :: ρ)
denote (exists_range lo hi p) ρ =
  ∃ n : Nat, evalTerm lo ρ ≤ n ∧ n < evalTerm hi ρ ∧ denote p (n :: ρ)
```

These signatures/equations are specification notation, not purported compiling Lean code. Equality denotes Lean equality; connectives denote their ordinary Lean propositions. `holds` means `evalTerm t ρ = true`. A range with `hi ≤ lo` is empty: its universal formula is true and existential formula false. Required non-vacuity witnesses remain separate obligations.

Symbol interpretations MUST resolve to the exact safe total declarations frozen in the challenge, with transitive semantic dependencies and instantiated arguments included. A partial implementation, effectful operation, external call, or native runtime replacement requires a separately modeled semantics and bridge; it cannot silently serve as a pure DSL interpretation.

## 4. General formulas versus executable checks

General `forall` and `exists` over `Nat` or a result containing `Nat` are permitted logical syntax. They do not imply an executable decision procedure. A `Classical.propDecidable` instance does not make such a formula a runtime checker or an input generator.

The executable fragment contains terms whose registered implementations are computable, decidable atomic predicates, connectives, range quantifiers, and general quantifiers over structurally finite sorts. Finite sorts are `Bool`, `Unit`, enumerations, and results whose two component sorts are finite. Execution requires a registered checker and a checked correspondence theorem relating its Boolean output to `denote`.

Bounded quantification is finite but may still exceed execution budgets. Exhaustion returns `UNKNOWN`/timeout to the test or monitor subsystem, never `true`. Runtime instrumentation reports checked inputs and scope. Property testing may instantiate a universally quantified variable with generated values, but passing those samples cannot prove the universal formula. Constructive existential witnesses may seed tests; a logical existence proof alone does not supply a runtime search algorithm.

## 5. Bounded increment example

This formula proposal matches `O17` in [BoundedIncrement.lean](../examples/lean/BoundedIncrement.lean). It is not accepted IR, and no acceptance result or digest is supplied here.

The profile `bounded-increment-nat.v0_1` fixes arbitrary-precision mathematical `Nat`, exact addition, explicit `Except`, and pure total functions. It declares `IncrementError = {limitReached}` and `increment : (Nat, Nat) → Result(IncrementError,Nat)`, binding its two ordered arguments to `limit` and `input` in the fixture's fully qualified `increment` declaration. This notation describes a two-argument signature, not a product sort in the DSL.

The reference returns `ok(input + 1)` if `input < limit`, otherwise `error(limitReached)`. There is no target-language, machine-width, physical-resource, or temporal profile in this example. The caller domain for the full request is `input ≤ limit`; O17 itself holds for every natural input, so its theorem does not need that premise.

With every binder displayed, the four fixture claims are:

```text
O17: ∀ limit : Nat, ∀ input : Nat, ∀ output : Nat,
       increment(limit,input) = ok(output) → output = input + 1
I2:  ∀ limit : Nat, ∀ input : Nat, ∀ output : Nat,
       increment(limit,input) = ok(output) → output ≤ limit
E1:  ∀ limit : Nat, ∀ input : Nat, input ≤ limit →
       (increment(limit,input) = error(limitReached) ↔ input = limit)
W1:  (∃ limit : Nat, ∃ input : Nat, ∃ output : Nat,
        input ≤ limit ∧ increment(limit,input) = ok(output)) ∧
     (∃ limit : Nat, ∃ input : Nat,
        input ≤ limit ∧ increment(limit,input) = error(limitReached))
```

The proposed O17 formula package is:

```json
{
  "encoding": "verislop.contract-dsl/0.1",
  "semantic_profile": "bounded-increment-nat.v0_1",
  "formula": {
    "tag": "forall", "sort": "Nat", "body": {
      "tag": "forall", "sort": "Nat", "body": {
        "tag": "forall", "sort": "Nat", "body": {
          "tag": "implies",
          "left": {
            "tag": "eq",
            "left": {"tag":"call", "symbol":"increment", "args":[
              {"tag":"var", "index":2}, {"tag":"var", "index":1}
            ]},
            "right": {"tag":"ok", "error_sort":{"enum":"IncrementError"},
              "value":{"tag":"var", "index":0}}
          },
          "right": {
            "tag":"eq", "left":{"tag":"var", "index":0},
            "right":{"tag":"add", "left":{"tag":"var", "index":1},
              "right":{"tag":"nat", "value":"1"}}
          }
        }
      }
    }
  }
}
```

Inside the implication, index `0` is output, `1` input, and `2` limit. A bounded variant `∀ limit : Nat, ∀ input ∈ [0, limit+1), ...` uses `forall_range`; its bounds see only the outer limit binder, while its body additionally sees input. This is an explicit change of formula, not an automatic rewrite of the fixture theorem.

## 6. Reification and acceptance conditions

The candidate formalizer creates a closed typed DSL value `q` and a theorem of `denote q []`, or a theorem `T` plus a proof `T ↔ denote q []`. The frozen challenge fixes both the intended theorem and profile. Equivalence proves agreement between those formal statements; it does not prove correspondence to natural-language intent.

After isolated proof acceptance, the trusted reifier reads `q` from the accepted declaration graph. It may perform only registered, bounded structural reduction to expose closed constructors. It MUST NOT execute candidate exporter plugins or trust an LLM-authored JSON attachment as the recovered value.

Acceptance of the formula package requires all of the following:

1. Decode and typecheck the emitted package under the exact accepted registry; reject missing/unknown fields, tags, symbols, constructors, or sorts.
2. Verify `decode(encode(q)) = q` for this value, using a registered mechanically checked round-trip procedure or checked certificate. The procedure and serializer are declared trust dependencies unless separately verified.
3. Check that the reconstructed denotation matches the accepted theorem target by trusted definitional equality or by an admissible replayed equivalence proof. Audit both the original proof and any equivalence proof.
4. Match obligation ID/revision, required registry coverage, theorem binding, hypotheses, and semantic dependency closure against the acceptance certificate and frozen challenge.
5. Canonicalize using the JSON rules in the main specification and bind the actual package/registry bytes to generated hashes. Attach operational statuses only through external evidence.

These checks establish artifact-to-IR correspondence under the declared trust boundary. Failed decoding, timeout, unsupported syntax, statement drift, registry mismatch, or an unproved equivalence blocks export. Canonical hashes identify a representation; they do not decide arbitrary mathematical equivalence.

## 7. Opaque accepted Lean expressions

An opaque expression package uses `encoding = "verislop.lean-export-ref/0.1"` with required fields `lean_toolchain`, `export_format`, `export_format_version`, `environment_ref`, `declaration`, `component` (`"type"` or `"value"`), and `dependency_closure_ref`. Artifact references MUST be content-addressed and resolve within the acceptance certificate's immutable export; filesystem paths or mutable URLs alone are insufficient. This package identifies an accepted term, not a JSON paraphrase of its proposition. Export-format support is toolchain-specific and registered before the run.

The referenced lossless format MUST preserve core expression constructors, binder structure, universe levels/parameters, constant identities and instantiations, declaration types/bodies, and required dependency closure. A validator must resolve and replay it without candidate-controlled notation or pretty printers. Unresolved metavariables/free variables or incomplete exports are invalid. Lossless means relative to that declared core-export format; it does not mean preserving source comments, notation, or tactic scripts.

No generic normalizer or runtime monitor is implied. A later adapter may provide a typed DSL expression and an accepted equivalence certificate; until then the expression remains opaque with explicit bridge limitations. The existing JSON envelope schemas do not implement this exporter or its semantic validator.
