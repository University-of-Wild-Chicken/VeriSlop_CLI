import VSCore.Syntax

/-!
# VSCore 0.1 — static semantics

`checkProgram profile program` accepts a program only if its language tag is `vscore/0.1`, its
entry IDs are unique and nonempty, every type mentions only registered enumerations, and every
entry body has exactly its declared result type in the context of its parameters. Enumeration
constructors are resolved against the accepted contract's ordered registry (`Profile`).

`HasType` is the value typing relation used by the soundness theorem in `VSCore.Semantics`.
-/

namespace VSCore

def lookupEnum (p : Profile) (id : String) : Option (List String) :=
  (p.enums.find? (fun e => e.1 == id)).map (·.2)

/-- A type is well formed when every enumeration it mentions is registered. -/
def wfTy (p : Profile) : Ty → Bool
  | .nat => true
  | .bool => true
  | .unit => true
  | .enum id => (lookupEnum p id).isSome
  | .result e o => wfTy p e && wfTy p o

def binType : BinOp → Ty → Ty → Except String Ty
  | .add, .nat, .nat => .ok .nat
  | .sub, .nat, .nat => .ok .nat
  | .mul, .nat, .nat => .ok .nat
  | .lt, .nat, .nat => .ok .bool
  | .le, .nat, .nat => .ok .bool
  | .and, .bool, .bool => .ok .bool
  | .or, .bool, .bool => .ok .bool
  | .eq, a, b => if a = b then .ok .bool else .error "eq: operand types differ"
  | _, _, _ => .error "operator applied to operands of the wrong type"

def typeOf (p : Profile) : List Ty → Expr → Except String Ty
  | Γ, .var i =>
    match Γ[i]? with
    | some t => .ok t
    | none => .error "unbound variable index"
  | _, .nat _ => .ok .nat
  | _, .bool _ => .ok .bool
  | _, .unit => .ok .unit
  | _, .enum id c =>
    match lookupEnum p id with
    | some cs => if c ∈ cs then .ok (.enum id) else .error "unknown enumeration constructor"
    | none => .error "unknown enumeration"
  | Γ, .bin op a b =>
    match typeOf p Γ a, typeOf p Γ b with
    | .ok ta, .ok tb => binType op ta tb
    | .error m, _ => .error m
    | _, .error m => .error m
  | Γ, .not a =>
    match typeOf p Γ a with
    | .ok .bool => .ok .bool
    | .ok _ => .error "not: operand must be bool"
    | .error m => .error m
  | Γ, .ite c t e =>
    match typeOf p Γ c, typeOf p Γ t, typeOf p Γ e with
    | .ok .bool, .ok tt, .ok te => if tt = te then .ok tt else .error "if: branch types differ"
    | .ok _, .ok _, .ok _ => .error "if: condition must be bool"
    | .error m, _, _ => .error m
    | _, .error m, _ => .error m
    | _, _, .error m => .error m
  | Γ, .letE v b =>
    match typeOf p Γ v with
    | .ok tv => typeOf p (tv :: Γ) b
    | .error m => .error m
  | Γ, .ok et v =>
    if wfTy p et then
      match typeOf p Γ v with
      | .ok tv => .ok (.result et tv)
      | .error m => .error m
    else .error "ok: ill-formed error type"
  | Γ, .error ot v =>
    if wfTy p ot then
      match typeOf p Γ v with
      | .ok tv => .ok (.result tv ot)
      | .error m => .error m
    else .error "error: ill-formed ok type"
  | Γ, .matchResult s o e =>
    match typeOf p Γ s with
    | .ok (.result te ta) =>
      match typeOf p (ta :: Γ) o, typeOf p (te :: Γ) e with
      | .ok t1, .ok t2 => if t1 = t2 then .ok t1 else .error "match_result: branch types differ"
      | .error m, _ => .error m
      | _, .error m => .error m
    | .ok _ => .error "match_result: scrutinee must have a result type"
    | .error m => .error m

def checkEntry (p : Profile) (e : Entry) : Except String EntrySig :=
  if !(e.params.all (wfTy p)) then .error s!"entry {e.id}: ill-formed parameter type"
  else if !(wfTy p e.result) then .error s!"entry {e.id}: ill-formed result type"
  else
    match typeOf p e.params.reverse e.body with
    | .ok t => if t = e.result then .ok { id := e.id, params := e.params, result := e.result }
               else .error s!"entry {e.id}: body type differs from the declared result type"
    | .error m => .error s!"entry {e.id}: {m}"

def checkEntries (p : Profile) : List Entry → Except String (List EntrySig)
  | [] => .ok []
  | e :: es =>
    match checkEntry p e, checkEntries p es with
    | .ok s, .ok ss => .ok (s :: ss)
    | .error m, _ => .error m
    | _, .error m => .error m

def checkProgram (p : Profile) (prog : Program) : Except String (List EntrySig) :=
  if prog.language != languageId then .error "unsupported language version"
  else if prog.entries.isEmpty then .error "a program needs at least one entry"
  else if !(prog.entries.map (·.id)).Nodup then .error "duplicate entry IDs"
  else checkEntries p prog.entries

/-- Boolean form used for kernel evaluation (`decide +kernel`). -/
def checkCheck (p : Profile) (prog : Program) (expected : List EntrySig) : Bool :=
  match checkProgram p prog with
  | .ok s => decide (s = expected)
  | .error _ => false

theorem checkProgram_of_check {p : Profile} {prog : Program} {expected : List EntrySig}
    (h : checkCheck p prog expected = true) : checkProgram p prog = .ok expected := by
  unfold checkCheck at h
  split at h
  · rename_i s hs
    rw [hs]
    simp only [decide_eq_true_eq] at h
    rw [h]
  · contradiction

/-! ## Value typing -/

inductive HasType (p : Profile) : Value → Ty → Prop
  | nat (n : Nat) : HasType p (.nat n) .nat
  | bool (b : Bool) : HasType p (.bool b) .bool
  | unit : HasType p .unit .unit
  | enum {id c : String} {cs : List String} (h : lookupEnum p id = some cs) (hc : c ∈ cs) :
      HasType p (.enum id c) (.enum id)
  | ok {v : Value} {ta te : Ty} (hv : HasType p v ta) (hw : wfTy p te = true) :
      HasType p (.ok v) (.result te ta)
  | error {v : Value} {ta te : Ty} (hv : HasType p v te) (hw : wfTy p ta = true) :
      HasType p (.error v) (.result te ta)

/-- An environment whose values have the context's types (pointwise). -/
inductive EnvTyped (p : Profile) : List Value → List Ty → Prop
  | nil : EnvTyped p [] []
  | cons {v : Value} {t : Ty} {vs : List Value} {ts : List Ty} :
      HasType p v t → EnvTyped p vs ts → EnvTyped p (v :: vs) (t :: ts)

end VSCore
