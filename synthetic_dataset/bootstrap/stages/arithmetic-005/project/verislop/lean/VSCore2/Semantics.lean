import VSCore2.Typing

/-! Total typed source semantics. The checker compiles each accepted expression into
a Lean function `Env Γ → Denote τ`; executing that function uses no evaluator fuel.
Unbounded mathematical natural folds and finite list folds use Lean's recursors.
Malformed raw arguments are a boundary fault, never a source-level Result.error. -/
namespace VSCore2

inductive EvalError where
  | invalidProgram | unknownEntry | invalidArguments
  deriving DecidableEq

def packArgs : List Value → Value
  | [] => .unit
  | x :: xs => .record "_internal_product" [("head", x), ("tail", packArgs xs)]

def packFields : List String → List (String × Value) → Option Value
  | [], [] => some .unit
  | n :: ns, (id, v) :: fs =>
    if n == id then (packFields ns fs).map (fun tail => .record "_internal_product" [("head", v), ("tail", tail)])
    else none
  | _, _ => none

def packVariant : List String → String → List Value → Option Value
  | [], _, _ => none
  | n :: ns, id, args =>
    if n == id then some (.variant "_internal_sum" "left" [packArgs args])
    else (packVariant ns id args).map (fun tail => .variant "_internal_sum" "right" [tail])

def decode : (t : Shape) → Value → Option (Denote t)
  | .nat, .nat n => some n
  | .bool, .bool b => some b
  | .unit, .unit => some ()
  | .enum id cs, .enum i c => if i == id then if h : c ∈ cs then some ⟨c, h⟩ else none else none
  | .result e _, .error x => (decode e x).map Sum.inl
  | .result _ o, .ok x => (decode o x).map Sum.inr
  | .option _, .none => some none
  | .option t, .some x => (decode t x).map some
  | .list t, v =>
    let element := decode t
    let rec go : Value → Option (List (Denote t))
      | .nil => some []
      | .cons h tail => do return (← element h) :: (← go tail)
      | _ => none
    go v
  | .product a b, .record "_internal_product" [("head", x), ("tail", y)] => do
    return (← decode a x, ← decode b y)
  | .sum a _, .variant "_internal_sum" "left" [x] => (decode a x).map Sum.inl
  | .sum _ b, .variant "_internal_sum" "right" [x] => (decode b x).map Sum.inr
  | .record id names t, .record i fields => if id == i then do decode t (← packFields names fields) else none
  | .variant id names t, .variant i ctor args => if id == i then do decode t (← packVariant names ctor args) else none
  | _, _ => none
termination_by t _ => sizeOf t

def decodeEnv : (ts : List Shape) → List Value → Option (Env ts)
  | [], [] => some ()
  | t :: ts, v :: vs => do return (← decode t v, ← decodeEnv ts vs)
  | _, _ => none

def findEntry (cp : CheckedProgram) (id : String) : Option CompiledFunction :=
  cp.entries.find? (fun e => e.id == id)

def evalCheckedEntry (e : CompiledFunction) (args : List Value) : Except EvalError Value :=
  match decodeEnv e.params args with
  | none => .error .invalidArguments
  | some env => .ok (encode e.result (e.run env))

def evalEntry (p : Profile) (prog : Program) (id : String) (args : List Value) : Except EvalError Value :=
  match compileProgram p prog with
  | .error _ => .error .invalidProgram
  | .ok cp =>
    match findEntry cp id with
    | none => .error .unknownEntry
    | some e => evalCheckedEntry e args

/-- Membership in the range of a checked source type's canonical representation. -/
def HasShape (t : Shape) (value : Value) : Prop := ∃ x : Denote t, encode t x = value

/-- Arguments have a typed decode under the exact checker-produced entry signature.
This relation deliberately excludes raw malformed values and incorrect argument lengths. -/
def ArgsTyped (e : CompiledFunction) (args : List Value) : Prop :=
  ∃ env : Env e.params, decodeEnv e.params args = some env

theorem evalCheckedEntry_sound {e : CompiledFunction} {args : List Value}
    (h : ArgsTyped e args) : ∃ value, evalCheckedEntry e args = .ok value ∧ HasShape e.result value := by
  obtain ⟨env, henv⟩ := h
  exact ⟨encode e.result (e.run env), by simp [evalCheckedEntry, henv], e.run env, rfl⟩

/-- Progress and preservation for every accepted entry: typed arguments cannot
produce a dynamic evaluator fault and the result has its intrinsic checked type.
Helper calls and both folds are included in `CompiledFunction.run`, with totality
established by Lean's own termination and type checking. -/
theorem checkProgram_sound {p : Profile} {prog : Program} {cp : CheckedProgram}
    (h : compileProgram p prog = .ok cp) {id : String} {e : CompiledFunction}
    (he : findEntry cp id = some e) {args : List Value} (ha : ArgsTyped e args) :
    ∃ value, evalEntry p prog id args = .ok value ∧ HasShape e.result value := by
  obtain ⟨value, hv, ht⟩ := evalCheckedEntry_sound ha
  exact ⟨value, by simp [evalEntry, h, he, hv], ht⟩

theorem evalEntry_deterministic {p : Profile} {prog : Program} {id : String}
    {args : List Value} {a b : Except EvalError Value}
    (ha : evalEntry p prog id args = a) (hb : evalEntry p prog id args = b) : a = b :=
  ha.symm.trans hb

theorem compiledExpression_sound {Γ : List Shape} {c : Compiled Γ} (env : Env Γ) :
    HasShape c.1 (encode c.1 (c.2 env)) := ⟨c.2 env, rfl⟩

/-- Checking returned signatures entails that a replayed intrinsic program exists. -/
theorem checkProgram_compiled {p : Profile} {prog : Program} {sigs : List EntrySig}
    (h : checkProgram p prog = .ok sigs) :
    ∃ cp, compileProgram p prog = .ok cp ∧ cp.signatures = sigs := by
  change (match compileProgram p prog with | .error m => Except.error m | .ok cp => Except.ok cp.signatures) = Except.ok sigs at h
  cases hc : compileProgram p prog with
  | error message => simp [hc] at h
  | ok cp => exact ⟨cp, rfl, by simpa [hc] using h⟩

end VSCore2
