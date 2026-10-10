import VSCore.Typing

/-!
# VSCore 0.1 — dynamic semantics

`evalExpr` is a big-step evaluator defined by structural recursion on the expression, so it is
total and deterministic by construction (it is a Lean function). `if` evaluates only the
selected branch. Errors (`stuck`, `unknownEntry`, `arity`) are evaluator faults, not source
results: source-level failure is expressed with explicit `result` values.

`typeOf_sound` establishes static preservation and progress for the supported fragment: a
well-typed expression in a well-typed environment evaluates without a fault to a value of its
static type. `checkProgram_sound` lifts this to entry points of a checked program.
There is no step-count semantics in this version, so no time or memory bound is claimed.
-/

namespace VSCore

inductive EvalError where
  | stuck
  | unknownEntry
  | arity
  deriving DecidableEq

def evalBin : BinOp → Value → Value → Except EvalError Value
  | .add, .nat a, .nat b => .ok (.nat (a + b))
  | .sub, .nat a, .nat b => .ok (.nat (a - b))
  | .mul, .nat a, .nat b => .ok (.nat (a * b))
  | .lt, .nat a, .nat b => .ok (.bool (decide (a < b)))
  | .le, .nat a, .nat b => .ok (.bool (decide (a ≤ b)))
  | .and, .bool a, .bool b => .ok (.bool (a && b))
  | .or, .bool a, .bool b => .ok (.bool (a || b))
  | .eq, a, b => .ok (.bool (decide (a = b)))
  | _, _, _ => .error .stuck

def evalExpr : List Value → Expr → Except EvalError Value
  | env, .var i =>
    match env[i]? with
    | some v => .ok v
    | none => .error .stuck
  | _, .nat n => .ok (.nat n)
  | _, .bool b => .ok (.bool b)
  | _, .unit => .ok .unit
  | _, .enum id c => .ok (.enum id c)
  | env, .bin op a b =>
    match evalExpr env a, evalExpr env b with
    | .ok x, .ok y => evalBin op x y
    | .error m, _ => .error m
    | _, .error m => .error m
  | env, .not a =>
    match evalExpr env a with
    | .ok (.bool b) => .ok (.bool (!b))
    | .ok _ => .error .stuck
    | .error m => .error m
  | env, .ite c t e =>
    match evalExpr env c with
    | .ok (.bool true) => evalExpr env t
    | .ok (.bool false) => evalExpr env e
    | .ok _ => .error .stuck
    | .error m => .error m
  | env, .letE v b =>
    match evalExpr env v with
    | .ok x => evalExpr (x :: env) b
    | .error m => .error m
  | env, .ok _ v =>
    match evalExpr env v with
    | .ok x => .ok (.ok x)
    | .error m => .error m
  | env, .error _ v =>
    match evalExpr env v with
    | .ok x => .ok (.error x)
    | .error m => .error m
  | env, .matchResult s o e =>
    match evalExpr env s with
    | .ok (.ok x) => evalExpr (x :: env) o
    | .ok (.error x) => evalExpr (x :: env) e
    | .ok _ => .error .stuck
    | .error m => .error m

def findEntry (p : Program) (id : String) : Option Entry :=
  p.entries.find? (fun e => e.id == id)

/-- Evaluate entry `id` on arguments given in parameter order. -/
def evalEntry (p : Program) (id : String) (args : List Value) : Except EvalError Value :=
  match findEntry p id with
  | none => .error .unknownEntry
  | some e => if args.length = e.params.length then evalExpr args.reverse e.body else .error .arity

/-- Determinism, stated explicitly: an evaluation has at most one outcome. -/
theorem evalEntry_deterministic {p : Program} {id : String} {args : List Value} {r₁ r₂ : Except EvalError Value}
    (h₁ : evalEntry p id args = r₁) (h₂ : evalEntry p id args = r₂) : r₁ = r₂ := h₁.symm.trans h₂

/-! ## Soundness -/

theorem EnvTyped.lookup {p : Profile} : ∀ {env : List Value} {Γ : List Ty} {i : Nat} {t : Ty},
    EnvTyped p env Γ → Γ[i]? = some t → ∃ v, env[i]? = some v ∧ HasType p v t
  | _, _, _, _, .nil, h => by simp at h
  | _, _, 0, _, .cons hv _, h => by
      simp only [List.getElem?_cons_zero, Option.some.injEq] at h
      subst h
      exact ⟨_, rfl, hv⟩
  | _, _, i + 1, _, .cons _ hs, h => by
      simp only [List.getElem?_cons_succ] at h ⊢
      exact EnvTyped.lookup hs h

theorem EnvTyped.length {p : Profile} : ∀ {env : List Value} {Γ : List Ty}, EnvTyped p env Γ → env.length = Γ.length
  | _, _, .nil => rfl
  | _, _, .cons _ hs => by simp [EnvTyped.length hs]

theorem evalBin_sound {p : Profile} {op : BinOp} {a b : Value} {ta tb t : Ty}
    (h : binType op ta tb = .ok t) (ha : HasType p a ta) (hb : HasType p b tb) :
    ∃ v, evalBin op a b = .ok v ∧ HasType p v t := by
  cases op
  case eq =>
    simp only [binType] at h
    split at h
    · cases h
      exact ⟨_, rfl, .bool _⟩
    · contradiction
  all_goals
    cases ha <;> cases hb <;> simp only [binType, Except.ok.injEq, reduceCtorEq] at h <;> subst h <;>
      first
      | exact ⟨_, rfl, .nat _⟩
      | exact ⟨_, rfl, .bool _⟩

/-! Typing inversion lemmas. -/

theorem typeOf_bin_inv {p : Profile} {Γ : List Ty} {op : BinOp} {a b : Expr} {t : Ty}
    (h : typeOf p Γ (.bin op a b) = .ok t) :
    ∃ ta tb, typeOf p Γ a = .ok ta ∧ typeOf p Γ b = .ok tb ∧ binType op ta tb = .ok t := by
  simp only [typeOf] at h
  cases ha : typeOf p Γ a <;> cases hb : typeOf p Γ b <;> simp_all

theorem typeOf_not_inv {p : Profile} {Γ : List Ty} {a : Expr} {t : Ty}
    (h : typeOf p Γ (.not a) = .ok t) : typeOf p Γ a = .ok .bool ∧ t = .bool := by
  simp only [typeOf] at h
  cases ha : typeOf p Γ a with
  | error m => simp [ha] at h
  | ok ta => cases ta <;> simp_all

theorem typeOf_ite_inv {p : Profile} {Γ : List Ty} {c th el : Expr} {t : Ty}
    (h : typeOf p Γ (.ite c th el) = .ok t) :
    typeOf p Γ c = .ok .bool ∧ typeOf p Γ th = .ok t ∧ typeOf p Γ el = .ok t := by
  simp only [typeOf] at h
  cases hc : typeOf p Γ c <;> cases ht : typeOf p Γ th <;> cases he : typeOf p Γ el <;> simp only [hc, ht, he] at h
  all_goals first
    | contradiction
    | skip
  rename_i tc tt te
  cases tc <;> simp only [reduceCtorEq] at h ⊢
  split at h
  · rename_i heq
    simp_all
  · contradiction

theorem typeOf_let_inv {p : Profile} {Γ : List Ty} {v b : Expr} {t : Ty}
    (h : typeOf p Γ (.letE v b) = .ok t) : ∃ tv, typeOf p Γ v = .ok tv ∧ typeOf p (tv :: Γ) b = .ok t := by
  simp only [typeOf] at h
  cases hv : typeOf p Γ v <;> simp_all

theorem typeOf_ok_inv {p : Profile} {Γ : List Ty} {et : Ty} {v : Expr} {t : Ty}
    (h : typeOf p Γ (.ok et v) = .ok t) : wfTy p et = true ∧ ∃ tv, typeOf p Γ v = .ok tv ∧ t = .result et tv := by
  simp only [typeOf] at h
  by_cases hw : wfTy p et = true
  · cases hv : typeOf p Γ v <;> simp_all
  · simp_all

theorem typeOf_error_inv {p : Profile} {Γ : List Ty} {ot : Ty} {v : Expr} {t : Ty}
    (h : typeOf p Γ (.error ot v) = .ok t) : wfTy p ot = true ∧ ∃ tv, typeOf p Γ v = .ok tv ∧ t = .result tv ot := by
  simp only [typeOf] at h
  by_cases hw : wfTy p ot = true
  · cases hv : typeOf p Γ v <;> simp_all
  · simp_all

theorem typeOf_match_inv {p : Profile} {Γ : List Ty} {s o e : Expr} {t : Ty}
    (h : typeOf p Γ (.matchResult s o e) = .ok t) :
    ∃ te ta, typeOf p Γ s = .ok (.result te ta) ∧ typeOf p (ta :: Γ) o = .ok t ∧ typeOf p (te :: Γ) e = .ok t := by
  simp only [typeOf] at h
  cases hs : typeOf p Γ s with
  | error m => simp [hs] at h
  | ok ts =>
    cases ts <;> simp only [hs, reduceCtorEq] at h
    rename_i te ta
    cases ho : typeOf p (ta :: Γ) o <;> cases he : typeOf p (te :: Γ) e <;> simp only [ho, he] at h
    all_goals first
      | contradiction
      | skip
    rename_i t1 t2
    split at h
    · rename_i heq
      simp only [Except.ok.injEq] at h
      subst h
      subst heq
      exact ⟨te, ta, rfl, ho, he⟩
    · contradiction

theorem typeOf_sound {p : Profile} :
    ∀ (e : Expr) (Γ : List Ty) (env : List Value) (t : Ty),
      typeOf p Γ e = .ok t → EnvTyped p env Γ → ∃ v, evalExpr env e = .ok v ∧ HasType p v t := by
  intro e
  induction e with
  | var i =>
    intro Γ env t h henv
    simp only [typeOf] at h
    cases ht : Γ[i]? with
    | none => simp [ht] at h
    | some t' =>
      simp only [ht, Except.ok.injEq] at h
      subst h
      obtain ⟨v, hv, hty⟩ := henv.lookup ht
      exact ⟨v, by simp [evalExpr, hv], hty⟩
  | nat n =>
    intro Γ env t h _
    simp only [typeOf, Except.ok.injEq] at h
    subst h
    exact ⟨_, rfl, .nat n⟩
  | bool b =>
    intro Γ env t h _
    simp only [typeOf, Except.ok.injEq] at h
    subst h
    exact ⟨_, rfl, .bool b⟩
  | unit =>
    intro Γ env t h _
    simp only [typeOf, Except.ok.injEq] at h
    subst h
    exact ⟨_, rfl, .unit⟩
  | enum id c =>
    intro Γ env t h _
    simp only [typeOf] at h
    cases hcs : lookupEnum p id with
    | none => simp [hcs] at h
    | some cs =>
      simp only [hcs] at h
      by_cases hc : c ∈ cs
      · simp only [hc, ite_true, Except.ok.injEq] at h
        subst h
        exact ⟨_, rfl, .enum hcs hc⟩
      · simp [hc] at h
  | bin op a b iha ihb =>
    intro Γ env t h henv
    obtain ⟨ta, tb, hta, htb, hbin⟩ := typeOf_bin_inv h
    obtain ⟨va, hva, htya⟩ := iha Γ env ta hta henv
    obtain ⟨vb, hvb, htyb⟩ := ihb Γ env tb htb henv
    obtain ⟨v, hv, hty⟩ := evalBin_sound hbin htya htyb
    exact ⟨v, by simp [evalExpr, hva, hvb, hv], hty⟩
  | not a iha =>
    intro Γ env t h henv
    obtain ⟨hta, rfl⟩ := typeOf_not_inv h
    obtain ⟨va, hva, htya⟩ := iha Γ env .bool hta henv
    cases htya with
    | bool b => exact ⟨.bool (!b), by simp [evalExpr, hva], .bool _⟩
  | ite c th el ihc iht ihe =>
    intro Γ env t h henv
    obtain ⟨hc, ht, he⟩ := typeOf_ite_inv h
    obtain ⟨vc, hvc, htyc⟩ := ihc Γ env .bool hc henv
    cases htyc with
    | bool b =>
      cases b
      · obtain ⟨v, hv, hty⟩ := ihe Γ env t he henv
        exact ⟨v, by simp [evalExpr, hvc, hv], hty⟩
      · obtain ⟨v, hv, hty⟩ := iht Γ env t ht henv
        exact ⟨v, by simp [evalExpr, hvc, hv], hty⟩
  | letE v b ihv ihb =>
    intro Γ env t h henv
    obtain ⟨tv, hv, hb⟩ := typeOf_let_inv h
    obtain ⟨x, hx, htyx⟩ := ihv Γ env tv hv henv
    obtain ⟨r, hr, htyr⟩ := ihb (tv :: Γ) (x :: env) t hb (.cons htyx henv)
    exact ⟨r, by simp [evalExpr, hx, hr], htyr⟩
  | ok et v ihv =>
    intro Γ env t h henv
    obtain ⟨hw, tv, htv, rfl⟩ := typeOf_ok_inv h
    obtain ⟨x, hx, htyx⟩ := ihv Γ env tv htv henv
    exact ⟨.ok x, by simp [evalExpr, hx], .ok htyx hw⟩
  | error ot v ihv =>
    intro Γ env t h henv
    obtain ⟨hw, tv, htv, rfl⟩ := typeOf_error_inv h
    obtain ⟨x, hx, htyx⟩ := ihv Γ env tv htv henv
    exact ⟨.error x, by simp [evalExpr, hx], .error htyx hw⟩
  | matchResult s o e ihs iho ihe =>
    intro Γ env t h henv
    obtain ⟨te, ta, hs, ho, he⟩ := typeOf_match_inv h
    obtain ⟨vs, hvs, htys⟩ := ihs Γ env (.result te ta) hs henv
    cases htys with
    | ok hx _ =>
      obtain ⟨r, hr, htyr⟩ := iho (ta :: Γ) (_ :: env) t ho (.cons hx henv)
      exact ⟨r, by simp [evalExpr, hvs, hr], htyr⟩
    | error hx _ =>
      obtain ⟨r, hr, htyr⟩ := ihe (te :: Γ) (_ :: env) t he (.cons hx henv)
      exact ⟨r, by simp [evalExpr, hvs, hr], htyr⟩

/-- Arguments listed in parameter order are typed by the parameter types. -/
def ArgsTyped (p : Profile) (args : List Value) (params : List Ty) : Prop :=
  EnvTyped p args.reverse params.reverse

theorem EnvTyped.append {p : Profile} : ∀ {a b : List Value} {ta tb : List Ty},
    EnvTyped p a ta → EnvTyped p b tb → EnvTyped p (a ++ b) (ta ++ tb)
  | _, _, _, _, .nil, hb => hb
  | _, _, _, _, .cons hv hs, hb => .cons hv (EnvTyped.append hs hb)

theorem checkEntry_sound {p : Profile} {e : Entry} {s : EntrySig} (h : checkEntry p e = .ok s) :
    s = { id := e.id, params := e.params, result := e.result } ∧
    ∀ args, ArgsTyped p args e.params → ∃ v, evalExpr args.reverse e.body = .ok v ∧ HasType p v e.result := by
  unfold checkEntry at h
  by_cases h1 : (e.params.all (wfTy p)) = true
  · by_cases h2 : wfTy p e.result = true
    · simp only [h1, h2, Bool.not_true, Bool.false_eq_true, ite_false] at h
      cases ht : typeOf p e.params.reverse e.body with
      | error m => simp [ht] at h
      | ok t =>
        simp only [ht] at h
        by_cases heq : t = e.result
        · simp only [heq, ite_true, Except.ok.injEq] at h
          subst h
          refine ⟨rfl, fun args hargs => ?_⟩
          rw [heq] at ht
          exact typeOf_sound e.body e.params.reverse args.reverse e.result ht hargs
        · simp [heq] at h
    · simp [h1, h2] at h
  · simp [h1] at h

theorem checkEntries_sound {p : Profile} : ∀ {es : List Entry} {ss : List EntrySig},
    checkEntries p es = .ok ss →
    ∀ e ∈ es, ∀ args, ArgsTyped p args e.params → ∃ v, evalExpr args.reverse e.body = .ok v ∧ HasType p v e.result
  | [], _, _, e, he, _, _ => by simp at he
  | e :: es, ss, h, e', he', args, hargs => by
    simp only [checkEntries] at h
    split at h
    · rename_i s ss' hs hss
      simp only [List.mem_cons] at he'
      rcases he' with rfl | hmem
      · exact (checkEntry_sound hs).2 args hargs
      · exact checkEntries_sound hss e' hmem args hargs
    · contradiction
    · contradiction

theorem findEntry_mem {p : Program} {id : String} {e : Entry} (h : findEntry p id = some e) : e ∈ p.entries :=
  List.mem_of_find?_eq_some h

/-- Entry-level progress and preservation for a checked program. -/
theorem checkProgram_sound {p : Profile} {prog : Program} {sigs : List EntrySig}
    (h : checkProgram p prog = .ok sigs) {id : String} {e : Entry} (he : findEntry prog id = some e)
    {args : List Value} (hargs : ArgsTyped p args e.params) :
    ∃ v, evalEntry prog id args = .ok v ∧ HasType p v e.result := by
  unfold checkProgram at h
  by_cases h1 : (prog.language != languageId) = true
  · simp [h1] at h
  · by_cases h2 : prog.entries.isEmpty = true
    · simp [h1, h2] at h
    · by_cases h3 : (!(prog.entries.map (·.id)).Nodup) = true
      · simp [h1, h2, h3] at h
      · simp only [h1, h2, h3, Bool.false_eq_true, ite_false] at h
        obtain ⟨v, hv, hty⟩ := checkEntries_sound h e (findEntry_mem he) args hargs
        have hlen : args.length = e.params.length := by
          have := EnvTyped.length hargs
          simpa using this
        exact ⟨v, by simp [evalEntry, he, hlen, hv], hty⟩

end VSCore
