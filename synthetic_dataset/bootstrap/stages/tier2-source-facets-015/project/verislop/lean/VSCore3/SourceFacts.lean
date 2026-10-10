import VSCore3.Transport

/-!
Exact restricted-source observations and admission-derived source facts. This
module deliberately does not import SourceBoundary: accepted contracts embed
that independently checked requirement algebra in their own module. The bridge
maps OperationalFacts into that algebra and retains SourceFactsAdequate alongside
every requirement discharge. No model witness or candidate fact table is used.
-/
namespace VSCore3

/-- Events excluded by the closed source language. Observations describe the
normative pure evaluator, not a host interpreter or operating system. -/
inductive EffectEvent where
  | externalIO (operation : String)
  | inputWrite (index : Nat) (value : Value)
  | floatingPoint

structure Observation where
  result : Except EvalError Value
  arguments : List Value
  effects : List EffectEvent

/-- The result is the actual normative evaluation. Immutable arguments are the
original snapshot, and no source construct can emit an external effect. -/
def observeEntry (p : Profile) (prog : Program) (id : String) (args : List Value) : Observation :=
  ⟨evalEntry p prog id args, args, []⟩

theorem observeEntry_result (p : Profile) (prog : Program) (id : String) (args : List Value) :
    (observeEntry p prog id args).result = evalEntry p prog id args := rfl

theorem observeEntry_inputPreserved (p : Profile) (prog : Program) (id : String) (args : List Value) :
    (observeEntry p prog id args).arguments = args := rfl

theorem observeEntry_emptyEffects (p : Profile) (prog : Program) (id : String) (args : List Value) :
    (observeEntry p prog id args).effects = [] := rfl

theorem observeEntry_noExternalIO (p : Profile) (prog : Program) (id : String)
    (args : List Value) (operation : String) :
    EffectEvent.externalIO operation ∉ (observeEntry p prog id args).effects := by simp [observeEntry]

theorem observeEntry_noFloatingPoint (p : Profile) (prog : Program) (id : String) (args : List Value) :
    EffectEvent.floatingPoint ∉ (observeEntry p prog id args).effects := by simp [observeEntry]

theorem observeEntry_deterministic {p : Profile} {prog : Program} {id : String}
    {args : List Value} {a b : Observation}
    (ha : observeEntry p prog id args = a) (hb : observeEntry p prog id args = b) : a = b :=
  ha.symm.trans hb

theorem observeEntry_typedTotal {p : Profile} {prog : Program} {cp : CheckedProgram}
    (hc : compileProgram p prog = .ok cp) {id : String} {e : CompiledFunction}
    (he : findEntry cp id = some e) (args : List Value) (ha : ArgsTyped e args) :
    ∃ value, (observeEntry p prog id args).result = .ok value ∧ HasShape e.result value :=
  checkProgram_sound hc he ha

/-- Every successful observation is a value in the checked mathematical data
carrier; this includes aggregates and does not depend on a host value encoding. -/
theorem observeEntry_pureData {p : Profile} {prog : Program} {cp : CheckedProgram}
    (hc : compileProgram p prog = .ok cp) {id : String} {e : CompiledFunction}
    (he : findEntry cp id = some e) (args : List Value) (value : Value)
    (hv : (observeEntry p prog id args).result = .ok value) : HasShape e.result value := by
  change evalEntry p prog id args = .ok value at hv
  simp only [evalEntry, hc, he, evalCheckedEntry] at hv
  cases hd : decodeEnv e.params args with
  | none => simp [hd] at hv
  | some env =>
    simp only [hd, Except.ok.injEq] at hv
    exact ⟨e.run env, hv⟩

structure OperationalEntry where
  file : String
  id : String
  arity : Nat
  deriving DecidableEq

structure OperationalFacts where
  entries : List OperationalEntry
  uniqueEntries : Bool
  typedTotal : Bool
  deterministic : Bool
  inputPreserved : Bool
  noExternalIO : Bool
  noFloatingPoint : Bool
  pureData : Bool
  restrictedRuntimeOnly : Bool

def rejectedSourceFacts : OperationalFacts :=
  ⟨[], false, false, false, false, false, false, false, false⟩

/-- This table is available only after exact admission and lookup. Its adequacy
theorem below supplies an exact semantic/admission law for each asserted flag. -/
def admittedSourceFacts (e : CompiledFunction) : OperationalFacts :=
  ⟨[⟨"program.vscore.json", e.id, e.params.length⟩], true, true, true, true, true, true, true, true⟩

def exactSourceFacts (p : Profile) (prog : Program) (id : String) : OperationalFacts :=
  match compileProgram p prog with
  | .error _ => rejectedSourceFacts
  | .ok cp =>
    match findEntry cp id with
    | none => rejectedSourceFacts
    | some e => admittedSourceFacts e

theorem exactSourceFacts_admitted {p : Profile} {prog : Program} {cp : CheckedProgram}
    (hc : compileProgram p prog = .ok cp) {id : String} {e : CompiledFunction}
    (he : findEntry cp id = some e) :
    exactSourceFacts p prog id = admittedSourceFacts e := by simp only [exactSourceFacts, hc, he]

def TypedCoverage (e : CompiledFunction) : Prop :=
  ∀ args, ArgsTyped e args → ∃ env : Env e.params, encodeEnv e.params env = args

theorem typedCoverage_of_rawLaws {e : CompiledFunction} (laws : ∀ t ∈ e.params, RawLaws t) :
    TypedCoverage e := by
  intro args ha
  exact encodedArgs_cover laws ha

/-- A compiler-bound adequacy interface, not an abstract fact-model witness.
Every true flag is paired with an exact law; raw shape laws and coverage are
retained even for facets that have no functional value formula. -/
structure SourceFactsAdequate (p : Profile) (prog : Program) (id : String)
    (cp : CheckedProgram) (e : CompiledFunction) : Prop where
  compiled : compileProgram p prog = .ok cp
  found : findEntry cp id = some e
  facts : exactSourceFacts p prog id = admittedSourceFacts e
  parameterRepresentation : ∀ t ∈ e.params, RawLaws t
  resultRepresentation : RawLaws e.result
  typedCoverage : TypedCoverage e
  typedTotal : ∀ args, ArgsTyped e args →
    ∃ value, (observeEntry p prog id args).result = .ok value ∧ HasShape e.result value
  deterministic : ∀ args a b, observeEntry p prog id args = a → observeEntry p prog id args = b → a = b
  inputPreserved : ∀ args, (observeEntry p prog id args).arguments = args
  noExternalIO : ∀ args operation, EffectEvent.externalIO operation ∉ (observeEntry p prog id args).effects
  noFloatingPoint : ∀ args, EffectEvent.floatingPoint ∉ (observeEntry p prog id args).effects
  pureData : ∀ args value, (observeEntry p prog id args).result = .ok value → HasShape e.result value
  restrictedRuntimeOnly : ∀ args, (observeEntry p prog id args).result = evalEntry p prog id args
  emptyEffectTrace : ∀ args, (observeEntry p prog id args).effects = []

theorem exactSourceFacts_adequate {p : Profile} {prog : Program} {cp : CheckedProgram}
    (hc : compileProgram p prog = .ok cp) {id : String} {e : CompiledFunction}
    (he : findEntry cp id = some e) (laws : ∀ t ∈ e.params, RawLaws t) (resultLaw : RawLaws e.result) :
    SourceFactsAdequate p prog id cp e where
  compiled := hc
  found := he
  facts := exactSourceFacts_admitted hc he
  parameterRepresentation := laws
  resultRepresentation := resultLaw
  typedCoverage := typedCoverage_of_rawLaws laws
  typedTotal := observeEntry_typedTotal hc he
  deterministic := fun _ _ _ => observeEntry_deterministic
  inputPreserved := observeEntry_inputPreserved p prog id
  noExternalIO := observeEntry_noExternalIO p prog id
  noFloatingPoint := observeEntry_noFloatingPoint p prog id
  pureData := observeEntry_pureData hc he
  restrictedRuntimeOnly := observeEntry_result p prog id
  emptyEffectTrace := observeEntry_emptyEffects p prog id

end VSCore3
