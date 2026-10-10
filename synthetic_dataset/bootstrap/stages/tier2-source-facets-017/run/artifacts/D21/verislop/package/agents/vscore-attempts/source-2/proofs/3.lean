import VeriSlopBridgeGoal

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeProof

open VeriSlopBridgeGoal VSCore3 VeriSlopAST

private theorem cond_as_ite {α : Type} (b : Bool) (x y : α) :
    cond b x y = if b then x else y := by
  cases b <;> rfl

private def statsAdapter : Adapter VeriSlopReadableSource.helper_0_result Stats where
  to := fun s => (s.count, (s.sum, ()))
  inv := fun s => ⟨s.1, s.2.1⟩
  from_to := by intro s; cases s; rfl
  to_from := by
    intro s
    rcases s with ⟨c, v, u⟩
    cases u
    rfl

private def stateShape : Shape :=
  .record "State" ["previous", "rows"]
    (.product (.option .int)
      (.product (.list (.record "Row" ["group", "start", "count", "value"]
        (.product .string (.product .int (.product .nat (.product (.option .int) .unit))))))
        .unit))

private def stateAdapter : Adapter stateShape State where
  to := fun s => (s.previous, (adapter_9.to s.rows, ()))
  inv := fun s => ⟨s.1, adapter_9.inv s.2.1⟩
  from_to := by
    intro s
    cases s
    change State.mk _ (adapter_9.inv (adapter_9.to _)) = _
    rw [adapter_9.from_to]
  to_from := by
    intro s
    with_unfolding_all
      rcases s with ⟨p, r, u⟩
      cases u
      change (p, (adapter_9.to (adapter_9.inv r), ())) = (p, (r, ()))
      rw [adapter_9.to_from]

private theorem fold_encode
    {t u : Shape} {α β : Type}
    (a : Adapter t α) (b : Adapter u β)
    (f : β → α → β) (g : Denote u → Denote t → Denote u)
    (h : ∀ z x, g (b.to z) (a.to x) = b.to (f z x))
    (z : β) (xs : List α) :
    List.foldl g (b.to z) ((listAdapter a).to xs) =
      b.to (List.foldl f z xs) := by
  have ht := ProofSupport.foldl_transport a b f g h z xs
  have he := congrArg b.to ht
  simpa only [b.to_from] using he

private def aggregateStep (i : Input) (group : String) (start : Int)
    (s : Stats) (e : Event) : Stats :=
  cond
    (decide (e.group = group) &&
      (e.value.isSome &&
        decide (start ≤ e.time ∧ e.time < Int.add start i.width ∧ e.time < i.end)))
    ⟨Nat.add s.count 1, Int.add s.sum (e.value.getD (Int.ofNat 0))⟩ s

private def rawAggregateStep (i : Input) (group : String) (start : Int)
    (s : Denote VeriSlopReadableSource.helper_0_result)
    (e : Denote (.record "Event" ["group", "time", "value"]
      (.product .string (.product .int (.product (.option .int) .unit))))) :
    Denote VeriSlopReadableSource.helper_0_result :=
  if (letI := denoteDecidableEq .string; decide (e.1 = group)) &&
      ((Option.casesOn e.2.2.1 false (fun _ => true)) &&
        (decide (start ≤ e.2.1) &&
          (decide (e.2.1 < start + i.width) && decide (e.2.1 < i.end)))) then
    (s.1 + 1,
      (s.2.1 + Option.casesOn e.2.2.1 (Int.ofNat 0) (fun v => v), ()))
  else s

private theorem aggregate_step_agrees
    (i : Input) (group : String) (start : Int) (s : Stats) (e : Event) :
    rawAggregateStep i group start (statsAdapter.to s) (adapter_3.to e) =
      statsAdapter.to (aggregateStep i group start s e) := by
  cases hv : e.value <;>
    by_cases hg : e.group = group <;>
    by_cases hl : start ≤ e.time <;>
    by_cases hu : e.time < start + i.width <;>
    by_cases he : e.time < i.end <;>
    simp [rawAggregateStep, aggregateStep, statsAdapter,
      adapter_3, adapter_0, adapter_1, adapter_2,
      stringAdapter, intAdapter, optionAdapter, denoteDecidableEq,
      cond_as_ite, ProofSupport.ite_decide, hv, hg, hl, hu, he]

private theorem aggregate_eq (i : Input) (group : String) (start : Int) :
    VeriSlopReadableSource.helper_0_named (adapter_6.to i) group start =
      statsAdapter.to (aggregate i group start) := by
  have h := fold_encode adapter_3 statsAdapter
    (aggregateStep i group start) (rawAggregateStep i group start)
    (aggregate_step_agrees i group start) (Stats.mk 0 (Int.ofNat 0)) i.events
  with_unfolding_all
    change List.foldl (rawAggregateStep i group start)
      (statsAdapter.to (Stats.mk 0 (Int.ofNat 0))) ((listAdapter adapter_3).to i.events) =
      statsAdapter.to (aggregate i group start)
    exact h

private def groupStep (i : Input) (group : String) (s : State) (k : Nat) : State :=
  let start := Int.add i.start (Int.mul (Int.ofNat k) i.width)
  let a := aggregate i group start
  ⟨cond (decide (0 < a.count)) (some a.sum) s.previous,
    s.rows ++
      [⟨group, start, a.count,
        cond (decide (0 < a.count)) (some a.sum)
          (cond (decide (i.fill = Fill.previous)) s.previous none)⟩]⟩

private def rawGroupStep (i : Input) (group : String)
    (s : Denote stateShape) (k : Nat) : Denote stateShape :=
  let start := i.start + Int.ofNat k * i.width
  let a := VeriSlopReadableSource.helper_0_named (adapter_6.to i) group start
  (if decide (0 < a.1) then some a.2.1 else s.1,
    (s.2.1 ++
      [(group, (start, (a.1,
        ((if decide (0 < a.1) then some a.2.1
          else if (letI := denoteDecidableEq (.enum "Fill" ["none", "previous"])
                   decide (adapter_5.to i.fill =
                     (⟨"previous", by decide +kernel⟩ :
                       Denote (.enum "Fill" ["none", "previous"]))))
            then s.1 else none), ()))))], ()))

private theorem group_step_agrees
    (i : Input) (group : String) (s : State) (k : Nat) :
    rawGroupStep i group (stateAdapter.to s) k =
      stateAdapter.to (groupStep i group s k) := by
  simp only [rawGroupStep, aggregate_eq, statsAdapter, groupStep, stateAdapter,
    cond_as_ite]
  simp only [ProofSupport.ite_decide]
  cases hf : i.fill <;>
    by_cases hc : 0 < (aggregate i group (i.start + Int.ofNat k * i.width)).count <;>
    simp [stateShape, adapter_9, adapter_8, adapter_7, adapter_5, adapter_2,
      adapter_1, adapter_0, listAdapter, optionAdapter,
      natAdapter, intAdapter, stringAdapter, denoteDecidableEq,
      ProofSupport.ite_decide, hf, hc, List.map_append]

private def bucketCount (i : Input) : Nat :=
  Int.toNat (Int.fdiv (Int.sub (Int.add (Int.sub i.end i.start) i.width)
    (Int.ofNat 1)) i.width)

private theorem group_rows_eq (i : Input) (group : String) :
    VeriSlopReadableSource.helper_1_named (adapter_6.to i) group =
      adapter_9.to (group_rows i group) := by
  have hg : group_rows i group =
      (List.foldl (groupStep i group) (State.mk none [])
        (List.range (bucketCount i))).rows := by
    simp only [group_rows, List.foldl_cons, List.foldl_nil]
    rfl
  have h := fold_encode natAdapter stateAdapter
    (groupStep i group) (rawGroupStep i group)
    (group_step_agrees i group) (State.mk none []) (List.range (bucketCount i))
  simp only [listAdapter, natAdapter, ProofSupport.map_identity] at h
  have hr := congrArg (fun s : Denote stateShape => s.2.1) h
  rw [hg]
  with_unfolding_all
    change (List.foldl (rawGroupStep i group) (stateAdapter.to (State.mk none []))
      (List.range (bucketCount i))).2.1 =
      adapter_9.to
        (List.foldl (groupStep i group) (State.mk none [])
          (List.range (bucketCount i))).rows
    exact hr

private theorem groups_eq (i : Input) :
    List.map (fun e => e.1) ((listAdapter adapter_3).to i.events) =
      List.map Event.group i.events := by
  have h := ProofSupport.map_transport adapter_3 stringAdapter Event.group
    (fun e => e.1) (by intro e; rfl) i.events
  simpa only [listAdapter, stringAdapter, ProofSupport.map_identity] using h

private theorem string_beq_agrees :
    (inferInstance : BEq String) =
      @instBEqOfDecidableEq String instDecidableEqString := by
  have h : (fun a b : String => a == b) =
      (fun a b : String => decide (a = b)) := by
    funext a b
    by_cases he : a = b <;> simp [he]
  exact congrArg BEq.mk h

private theorem solve_refines : Refines_solve := by
  intro i
  rw [Readable.source_eq_solve]
  let groups := @List.mergeSort String
    (@List.eraseDups String
      (@instBEqOfDecidableEq String instDecidableEqString)
      (List.map Event.group i.events))
    (fun a b => decide (a ≤ b))
  have h := fold_encode stringAdapter adapter_9
    (fun rows group => rows ++ group_rows i group)
    (fun rows group => rows ++
      VeriSlopReadableSource.helper_1_named (adapter_6.to i) group)
    (by
      intro rows group
      rw [group_rows_eq]
      simp only [adapter_9, listAdapter, List.map_append, stringAdapter])
    [] groups
  simp only [listAdapter, stringAdapter, ProofSupport.map_identity] at h
  have hi := congrArg adapter_9.inv h
  simp only [adapter_9.from_to] at hi
  with_unfolding_all
    change adapter_9.inv
      (List.foldl
        (fun rows group => rows ++
          VeriSlopReadableSource.helper_1_named (adapter_6.to i) group)
        []
        ((List.map (fun e => e.1) ((listAdapter adapter_3).to i.events)).eraseDups.mergeSort
          (fun a b => decide (a ≤ b)))) = solve i
    rw [groups_eq]
    rw [string_beq_agrees]
    exact hi

theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  exact VeriSlopBridgeGoal.edge_of_refines solve_refines

end VeriSlopBridgeProof
