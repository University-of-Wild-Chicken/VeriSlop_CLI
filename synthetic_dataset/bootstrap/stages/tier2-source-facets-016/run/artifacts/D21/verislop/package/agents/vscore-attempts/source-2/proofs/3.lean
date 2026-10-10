import VeriSlopBridgeGoal

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000
set_option smartUnfolding false

namespace VeriSlopBridgeProof

open VeriSlopBridgeGoal VeriSlopAST VeriSlopReadableSource

private theorem decide_conj (p q : Prop) [Decidable p] [Decidable q] :
    decide (p ∧ q) = (decide p && decide q) := by
  by_cases hp : p <;> by_cases hq : q <;> simp [hp, hq]

private theorem map_filter_transport {α β : Type}
    (f : α → β) (p : α → Bool) (q : β → Bool)
    (h : ∀ x, q (f x) = p x) (xs : List α) :
    (xs.map f).filter q = (xs.filter p).map f := by
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    simp only [List.map_cons, List.filter_cons, h x]
    cases p x <;> simp_all

private theorem fold_transport {α β γ : Type}
    (f : α → β) (s : α → γ → α) (t : β → γ → β)
    (h : ∀ a x, t (f a) x = f (s a x))
    (xs : List γ) (a : α) :
    xs.foldl t (f a) = f (xs.foldl s a) := by
  induction xs generalizing a with
  | nil => rfl
  | cons x xs ih =>
    simp only [List.foldl_cons, h, ih]

private def selected (i : Input) (g : String) (t : Int) (e : Event) : Bool :=
  decide (e.group = g) &&
    (e.value.isSome &&
      decide (t ≤ e.time ∧ e.time < t + i.width ∧ e.time < i.end))

private def stats (i : Input) (g : String) (t : Int) : Stats :=
  let es := i.events.filter (selected i g t)
  ⟨es.length, (es.map (fun e => e.value.getD 0)).sum⟩

private def step (i : Input) (g : String) (s : State) (n : Nat) : State :=
  let t := i.start + Int.ofNat n * i.width
  let b := stats i g t
  ⟨s.rows ++ [⟨g, t, b.count,
      cond (decide (0 < b.count)) (some b.sum)
        (cond (decide (i.fill = Fill.previous)) s.previous none)⟩],
    cond (decide (0 < b.count)) (some b.sum) s.previous⟩

private def indices (i : Input) : List Nat :=
  List.range ((i.end - i.start + i.width - 1).fdiv i.width).toNat

private def rows (i : Input) (g : String) : List Row :=
  ((indices i).foldl (step i g) ⟨[], none⟩).rows

private def stateTo (s : State) :
    VSCore3.Denote
      (.record "State" ["rows", "previous"]
        (.product helper_1_result (.product (.option .int) .unit))) :=
  (adapter_9.to s.rows, (s.previous, ()))

private theorem helper_stats (i : Input) (g : String) (t : Int) :
    helper_0_named (adapter_6.to i) g t =
      ((stats i g t).count, ((stats i g t).sum, ())) := by
  let q : (String × (Int × (Option Int × Unit))) → Bool :=
    fun e =>
      decide (e.1 = g) &&
        ((match e.2.2.1 with | none => false | some _ => true) &&
          (decide (t ≤ e.2.1) &&
            (decide (e.2.1 < t + i.width) && decide (e.2.1 < i.end))))
  have hp : ∀ e : Event, q (adapter_3.to e) = selected i g t e := by
    intro e
    cases hv : e.value <;>
      simp [q, selected, adapter_3, adapter_0, adapter_1, adapter_2,
        VSCore3.stringAdapter, VSCore3.intAdapter, VSCore3.optionAdapter,
        hv, decide_conj]
  have hf := map_filter_transport adapter_3.to (selected i g t) q hp i.events
  have her :
      VSCore3.envReverse helper_0_params (adapter_6.to i, (g, (t, ()))) =
        (t, (g, (adapter_6.to i, ()))) := by
    with_unfolding_all rfl
  unfold helper_0_named helper_0_run
  rw [her]
  with_unfolding_all
    change
      (((i.events.map adapter_3.to).filter q).length,
        (((((i.events.map adapter_3.to).filter q).map
          (fun (e : String × (Int × (Option Int × Unit))) =>
            (match e.2.2.1 with | none => (0 : Int) | some v => v))).sum), ())) = _
  rw [hf]
  simp only [List.length_map, List.map_map]
  have hm :
      (fun e : Event =>
        (match (adapter_3.to e).2.2.1 with
          | none => (0 : Int)
          | some v => v)) =
      (fun e : Event => e.value.getD 0) := by
    funext e
    cases hv : e.value <;>
      simp [adapter_3, adapter_2, adapter_1,
        VSCore3.optionAdapter, VSCore3.intAdapter, hv]
  rw [hm]
  rfl

private def rawStep (i : Input) (g : String)
    (s : VSCore3.Denote
      (.record "State" ["rows", "previous"]
        (.product helper_1_result (.product (.option .int) .unit))))
    (n : Nat) :=
  let t := i.start + Int.ofNat n * i.width
  let b := helper_0_named (adapter_6.to i) g t
  (s.1 ++ [(g, (t, (b.1,
    ((if decide (0 < b.1) then some b.2.1
      else if decide (adapter_5.to i.fill =
        (⟨"previous", by decide +kernel⟩ :
          VSCore3.Denote (.enum "Fill" ["none", "previous"])))
        then s.2.1 else none), ()))))],
    ((if decide (0 < b.1) then some b.2.1 else s.2.1), ()))

private theorem raw_step (i : Input) (g : String) (s : State) (n : Nat) :
    rawStep i g (stateTo s) n = stateTo (step i g s n) := by
  simp only [rawStep, helper_stats]
  by_cases hc : 0 < (stats i g (i.start + Int.ofNat n * i.width)).count
  · simp [stateTo, step, hc, adapter_9, adapter_8, adapter_7,
      adapter_2, adapter_1, adapter_0,
      VSCore3.listAdapter, VSCore3.natAdapter, VSCore3.optionAdapter,
      VSCore3.intAdapter, VSCore3.stringAdapter,
      VSCore3.ProofSupport.map_identity]
  · cases hf : i.fill <;>
      simp [stateTo, step, hc, adapter_9, adapter_8, adapter_7,
        adapter_2, adapter_1, adapter_0, adapter_5,
        VSCore3.listAdapter, VSCore3.natAdapter, VSCore3.optionAdapter,
        VSCore3.intAdapter, VSCore3.stringAdapter, hf,
        VSCore3.ProofSupport.map_identity]

private theorem helper_rows (i : Input) (g : String) :
    helper_1_named (adapter_6.to i) g = adapter_9.to (rows i g) := by
  have h := fold_transport stateTo (step i g) (rawStep i g)
    (raw_step i g) (indices i) (⟨[], none⟩ : State)
  have hp := congrArg (fun s => s.1) h
  have her :
      VSCore3.envReverse helper_1_params (adapter_6.to i, (g, ())) =
        (g, (adapter_6.to i, ())) := by
    with_unfolding_all rfl
  unfold helper_1_named helper_1_run
  rw [her]
  with_unfolding_all
    change
      ((indices i).foldl (rawStep i g)
        (stateTo (⟨[], none⟩ : State))).1 =
      adapter_9.to (rows i g)
  exact hp

private theorem group_names (i : Input) :
    (adapter_6.to i).1.map (fun e => e.1) =
      i.events.map Event.group := by
  simp [adapter_6, adapter_4, adapter_3, adapter_0,
    VSCore3.listAdapter, VSCore3.stringAdapter, List.map_map]

private theorem readable_refines (i : Input) :
    VeriSlopBridgeGoal.Readable.readable_fn_solve i = solve i := by
  let gs := (i.events.map Event.group).eraseDups.mergeSort
    (fun a b => decide (a ≤ b))
  have hfold :
      gs.foldl
        (fun acc g => acc ++ helper_1_named (adapter_6.to i) g)
        (adapter_9.to []) =
      adapter_9.to (gs.foldl (fun acc g => acc ++ rows i g) []) := by
    apply fold_transport
    intro acc g
    rw [helper_rows]
    simp [adapter_9, VSCore3.listAdapter, List.map_append]
  have hsolve :
      gs.foldl (fun acc g => acc ++ rows i g) [] = solve i := by
    rfl
  have hr :
      entry_0_run (adapter_6.to i, ()) = adapter_9.to (solve i) := by
    have her :
        VSCore3.envReverse entry_0_params (adapter_6.to i, ()) =
          (adapter_6.to i, ()) := by
      with_unfolding_all rfl
    unfold entry_0_run
    rw [her]
    with_unfolding_all
      change
        (((adapter_6.to i).1.map (fun e => e.1)).eraseDups.mergeSort
          (fun a b => decide (a ≤ b))).foldl
          (fun acc g => acc ++ helper_1_named (adapter_6.to i) g)
          (adapter_9.to []) = adapter_9.to (solve i)
    rw [group_names]
    exact hfold.trans (congrArg adapter_9.to hsolve)
  unfold VeriSlopBridgeGoal.Readable.readable_fn_solve
  rw [hr]
  exact adapter_9.from_to (solve i)

theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  intro i
  rw [VeriSlopBridgeGoal.Readable.source_eq_solve]
  exact readable_refines i

end VeriSlopBridgeProof
