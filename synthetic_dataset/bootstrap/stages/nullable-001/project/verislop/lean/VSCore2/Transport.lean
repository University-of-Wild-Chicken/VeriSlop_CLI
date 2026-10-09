import VSCore2.Semantics

/-! Representation laws and conservative *syntactic* embedding. The 0.2 bridge
initially admits scalar/enumeration/Result ports; aggregate transport requires an
accepted contract registry and is deliberately not inferred inv syntax support.
Embedding round trips do not by themselves prove whole evaluator correspondence. -/
namespace VSCore2

def bridgePortSupported : Ty → Bool
  | .nat | .bool | .unit | .enum _ => true
  | .result e o => bridgePortSupported e && bridgePortSupported o
  | _ => false

/-- An exact representation isomorphism into an intrinsic source type. -/
structure Adapter (t : Shape) (α : Type) where
  to : α → Denote t
  inv : Denote t → α
  from_to : ∀ a, inv (to a) = a
  to_from : ∀ v, to (inv v) = v

def Adapter.encode {t : Shape} {α : Type} (a : Adapter t α) (x : α) : Value :=
  VSCore2.encode t (a.to x)

theorem Adapter.encode_hasShape {t : Shape} {α : Type} (a : Adapter t α) (x : α) :
    HasShape t (a.encode x) := ⟨a.to x, rfl⟩

theorem Adapter.covers {t : Shape} {α : Type} (a : Adapter t α) {v : Value}
    (h : HasShape t v) : ∃ x, a.encode x = v := by
  obtain ⟨typed, rfl⟩ := h
  exact ⟨a.inv typed, by simp [Adapter.encode, a.to_from]⟩

def natAdapter : Adapter .nat Nat := ⟨(fun x => x), (fun x => x), fun _ => rfl, fun _ => rfl⟩
def boolAdapter : Adapter .bool Bool := ⟨(fun x => x), (fun x => x), fun _ => rfl, fun _ => rfl⟩
def unitAdapter : Adapter .unit Unit := ⟨(fun x => x), (fun x => x), fun _ => rfl, fun _ => rfl⟩
def enumAdapter (id : String) (cs : List String) : Adapter (.enum id cs) { c : String // c ∈ cs } :=
  ⟨(fun x => x), (fun x => x), fun _ => rfl, fun _ => rfl⟩

def resultAdapter {te to : Shape} {E O : Type} (err : Adapter te E) (ok : Adapter to O) :
    Adapter (.result te to) (Except E O) where
  to := fun x => match x with | .error e => .inl (err.to e) | .ok o => .inr (ok.to o)
  inv := fun x => match x with | .inl e => .error (err.inv e) | .inr o => .ok (ok.inv o)
  from_to := by intro x; cases x <;> simp [err.from_to, ok.from_to]
  to_from := by intro x; cases x <;> simp [err.to_from, ok.to_from]

def embedTy : VSCore.Ty → Ty
  | .nat => .nat | .bool => .bool | .unit => .unit | .enum id => .enum id
  | .result e o => .result (embedTy e) (embedTy o)

def eraseTy : Ty → Option VSCore.Ty
  | .nat => some .nat | .bool => some .bool | .unit => some .unit | .enum id => some (.enum id)
  | .result e o => do return .result (← eraseTy e) (← eraseTy o)
  | _ => none

theorem erase_embedTy (t : VSCore.Ty) : eraseTy (embedTy t) = some t := by
  induction t <;> simp_all [embedTy, eraseTy]

theorem embedTy_injective {a b : VSCore.Ty} (h : embedTy a = embedTy b) : a = b := by
  have := congrArg eraseTy h
  simpa [erase_embedTy] using this

def embedValue : VSCore.Value → Value
  | .nat n => .nat n | .bool b => .bool b | .unit => .unit | .enum id c => .enum id c
  | .ok x => .ok (embedValue x) | .error x => .error (embedValue x)

def eraseValue : Value → Option VSCore.Value
  | .nat n => some (.nat n) | .bool b => some (.bool b) | .unit => some .unit | .enum id c => some (.enum id c)
  | .ok x => (eraseValue x).map VSCore.Value.ok
  | .error x => (eraseValue x).map VSCore.Value.error
  | _ => none

theorem erase_embedValue (v : VSCore.Value) : eraseValue (embedValue v) = some v := by
  induction v <;> simp_all [embedValue, eraseValue]

theorem embedValue_injective {a b : VSCore.Value} (h : embedValue a = embedValue b) : a = b := by
  have := congrArg eraseValue h
  simpa [erase_embedValue] using this

def embedExpr : VSCore.Expr → Expr
  | .var i => .var i | .nat n => .nat n | .bool b => .bool b | .unit => .unit
  | .enum id c => .enum id c
  | .bin op a b => .bin op (embedExpr a) (embedExpr b)
  | .not a => .not (embedExpr a)
  | .ite c t e => .ite (embedExpr c) (embedExpr t) (embedExpr e)
  | .letE a b => .letE (embedExpr a) (embedExpr b)
  | .ok t a => .ok (embedTy t) (embedExpr a)
  | .error t a => .error (embedTy t) (embedExpr a)
  | .matchResult s o e => .matchResult (embedExpr s) (embedExpr o) (embedExpr e)

def eraseExpr : Expr → Option VSCore.Expr
  | .var i => some (.var i) | .nat n => some (.nat n) | .bool b => some (.bool b) | .unit => some .unit
  | .enum id c => some (.enum id c)
  | .bin op a b => do return .bin op (← eraseExpr a) (← eraseExpr b)
  | .not a => (eraseExpr a).map VSCore.Expr.not
  | .ite c t e => do return .ite (← eraseExpr c) (← eraseExpr t) (← eraseExpr e)
  | .letE a b => do return .letE (← eraseExpr a) (← eraseExpr b)
  | .ok t a => do return .ok (← eraseTy t) (← eraseExpr a)
  | .error t a => do return .error (← eraseTy t) (← eraseExpr a)
  | .matchResult s o e => do return .matchResult (← eraseExpr s) (← eraseExpr o) (← eraseExpr e)
  | _ => none

theorem erase_embedExpr (e : VSCore.Expr) : eraseExpr (embedExpr e) = some e := by
  induction e <;> simp_all [embedExpr, eraseExpr, erase_embedTy]

theorem embedExpr_injective {a b : VSCore.Expr} (h : embedExpr a = embedExpr b) : a = b := by
  have := congrArg eraseExpr h
  simpa [erase_embedExpr] using this

def embedEntry (e : VSCore.Entry) : Entry :=
  { id := e.id, params := e.params.map embedTy, result := embedTy e.result, body := embedExpr e.body }

def embedProgram (p : VSCore.Program) : Program :=
  { language := languageId, profile := profileId, declarations := [], helpers := [], entries := p.entries.map embedEntry }

theorem embedded_program_has_no_helpers (p : VSCore.Program) : (embedProgram p).helpers = [] := rfl

theorem embedded_program_has_no_nominal_declarations (p : VSCore.Program) : (embedProgram p).declarations = [] := rfl

end VSCore2
