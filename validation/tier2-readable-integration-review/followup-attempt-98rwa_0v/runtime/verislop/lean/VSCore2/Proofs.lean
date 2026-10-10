import VSCore2.Semantics

set_option linter.unusedSimpArgs false
set_option maxRecDepth 100000
set_option maxHeartbeats 20000000
namespace VSCore2

/-- Intrinsic compilation preserves the declared name, parameter types and result
resolution. This complements total typed evaluation with an explicit connection
back to the decoded declaration rather than to a host-proposed signature. -/
theorem compileFunction_signature {p : Profile} {ds : DataContext} {hs : HelperContext}
    {e : Entry} {c : CompiledFunction} (h : compileFunction p ds hs e = .ok c) :
    c.id = e.id ∧
    e.params.mapM (fun t => resolveTy (tyBudget t + 1) p ds t) = .ok c.params ∧
    resolveTy (tyBudget e.result + 1) p ds e.result = .ok c.result := by
  unfold compileFunction at h
  split at h
  · contradiction
  · cases hp : e.params.mapM (fun t => resolveTy (tyBudget t + 1) p ds t) with
    | error message => simp [hp, bind, Except.bind, pure, Except.pure] at h
    | ok params =>
      cases hr : resolveTy (tyBudget e.result + 1) p ds e.result with
      | error message => simp [hp, hr, bind, Except.bind, pure, Except.pure] at h
      | ok result =>
        cases hb : compileExpr (exprBudget e.body + 1) p ds hs params.reverse e.body with
        | error message => simp [hp, hr, hb, bind, Except.bind, pure, Except.pure] at h
        | ok body =>
          cases hc : castCompiled result body with
          | error message => simp [hp, hr, hb, hc, bind, Except.bind, pure, Except.pure] at h
          | ok run =>
            simp [hp, hr, hb, hc, bind, Except.bind, pure, Except.pure] at h
            cases h
            exact ⟨rfl, rfl, rfl⟩



theorem compileEntries_members {p : Profile} {ds : DataContext} {hs : HelperContext} :
    ∀ {es : List Entry} {cs : List CompiledFunction},
      es.mapM (compileFunction p ds hs) = .ok cs →
      ∀ c ∈ cs, ∃ e ∈ es, compileFunction p ds hs e = .ok c := by
  intro es
  induction es with
  | nil =>
    intro cs h c hc
    simp only [List.mapM_nil, pure, Except.pure, Except.ok.injEq] at h
    subst cs
    simp at hc
  | cons e es ih =>
    intro cs h c hc
    cases he : compileFunction p ds hs e with
    | error message => simp [List.mapM_cons, he, bind, Except.bind] at h
    | ok code =>
      cases ht : es.mapM (compileFunction p ds hs) with
      | error message => simp [List.mapM_cons, he, ht, bind, Except.bind] at h
      | ok tail =>
        simp [List.mapM_cons, he, ht, bind, Except.bind, pure, Except.pure] at h
        subst cs
        simp only [List.mem_cons] at hc
        rcases hc with rfl | hc
        · exact ⟨e, by simp, he⟩
        · obtain ⟨e', hm, hp⟩ := ih ht c hc
          exact ⟨e', by simp [hm], hp⟩

theorem except_bind_ok {α β : Type} {a : Except String α} {f : α → Except String β} {b : β}
    (h : a >>= f = .ok b) : ∃ x, a = .ok x ∧ f x = .ok b := by
  cases a with
  | error message => contradiction
  | ok x => exact ⟨x, rfl, h⟩

theorem guard_continuation_ok {β : Type} {condition : Prop} [Decidable condition]
    {message : String} {f : Unit → Except String β} {b : β}
    (h : (if condition then Except.bind (Except.error message) f else f ()) = .ok b) : f () = .ok b := by
  by_cases hc : condition
  · simp [hc, Except.bind] at h
  · simpa [hc] using h

theorem compileProgram_entries {p : Profile} {prog : Program} {cp : CheckedProgram}
    (h : compileProgram p prog = .ok cp) :
    prog.entries.mapM (compileFunction p cp.declarations cp.helpers) = .ok cp.entries := by
  unfold compileProgram at h
  have h := guard_continuation_ok h
  have h := guard_continuation_ok h
  have h := guard_continuation_ok h
  have h := guard_continuation_ok h
  have h := guard_continuation_ok h
  have h := guard_continuation_ok h
  obtain ⟨ds, _, h⟩ := except_bind_ok h
  obtain ⟨hs, _, h⟩ := except_bind_ok h
  obtain ⟨entries, hentries, h⟩ := except_bind_ok h
  change Except.ok ({ declarations := ds, helpers := hs, entries := entries, signatures := prog.entries.map (fun e => {id := e.id, params := e.params, result := e.result}) } : CheckedProgram) = Except.ok cp at h
  cases h
  exact hentries

/-- Every checker-produced entry is tied to a decoded source declaration, with
its exact raw parameter/result types resolved by the normative checker. -/
theorem checkedEntry_signature {p : Profile} {prog : Program} {cp : CheckedProgram}
    (h : compileProgram p prog = .ok cp) {c : CompiledFunction} (hc : c ∈ cp.entries) :
    ∃ e ∈ prog.entries, c.id = e.id ∧
      e.params.mapM (fun t => resolveTy (tyBudget t + 1) p cp.declarations t) = .ok c.params ∧
      resolveTy (tyBudget e.result + 1) p cp.declarations e.result = .ok c.result := by
  obtain ⟨e, he, hcompile⟩ := compileEntries_members (compileProgram_entries h) c hc
  exact ⟨e, he, compileFunction_signature hcompile⟩



/-- Value typing at an actual decoded nominal/source type, under the exact
checker-produced nominal context. -/
def HasType (p : Profile) (ds : DataContext) (value : Value) (ty : Ty) : Prop :=
  ∃ shape, resolveTy (tyBudget ty + 1) p ds ty = .ok shape ∧ HasShape shape value

/-- The full accepted-entry theorem connects total execution back to the
source declaration's result type, including nominal types and nested aggregates. -/
theorem checkProgram_source_sound {p : Profile} {prog : Program} {cp : CheckedProgram}
    (h : compileProgram p prog = .ok cp) {id : String} {c : CompiledFunction}
    (he : findEntry cp id = some c) {args : List Value} (ha : ArgsTyped c args) :
    ∃ source ∈ prog.entries, c.id = source.id ∧
      ∃ value, evalEntry p prog id args = .ok value ∧ HasType p cp.declarations value source.result := by
  obtain ⟨source, hm, hname, _, hresult⟩ := checkedEntry_signature h (List.mem_of_find?_eq_some he)
  obtain ⟨value, hv, htyped⟩ := checkProgram_sound h he ha
  exact ⟨source, hm, hname, value, hv, c.result, hresult, htyped⟩

end VSCore2
