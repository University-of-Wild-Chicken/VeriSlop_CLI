import VeriSlopBridgeGoal

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeProof

open VeriSlopAST

abbrev EventRep := String × Int × Option Int × Unit
abbrev StatsRep := Nat × Int × Unit
abbrev OutputRep := String × Int × Nat × Option Int × Unit
abbrev StateRep := List OutputRep × Option Int × Unit

def eventRep (e : Event) : EventRep :=
  (e.group, (e.time, (e.value.map (fun v => v), ())))

def statsRep (s : Stats) : StatsRep :=
  (s.count, (s.sum, ()))

def outputRep (o : Output) : OutputRep :=
  (o.group, (o.start, (o.count, (o.value.map (fun v => v), ()))))

def outputInv (o : OutputRep) : Output :=
  ⟨o.1, o.2.1, o.2.2.1, o.2.2.2.1.map (fun v => v)⟩

def stateRep (s : State) : StateRep :=
  (s.rows.map outputRep, (s.previous.map (fun v => v), ()))

theorem cond_ite {α : Type} (b : Bool) (x y : α) :
    cond b x y = if b then x else y := by
  cases b <;> rfl

theorem fold_transport {α β γ δ : Type}
    (encodeElement : α → β) (encodeState : γ → δ)
    (sourceStep : δ → β → δ) (acceptedStep : γ → α → γ)
    (step : ∀ s e,
      sourceStep (encodeState s) (encodeElement e) =
        encodeState (acceptedStep s e))
    (xs : List α) (initial : γ) :
    (xs.map encodeElement).foldl sourceStep (encodeState initial) =
      encodeState (xs.foldl acceptedStep initial) := by
  induction xs generalizing initial with
  | nil => rfl
  | cons x xs ih =>
    simp only [List.map_cons, List.foldl_cons, step]
    exact ih (acceptedStep initial x)

def acceptedStatsStep (x : Input) (g : String) (b : Int)
    (s : Stats) (e : Event) : Stats :=
  cond
    (e.value.isSome &&
      decide (e.group = g ∧
        (b ≤ e.time ∧ (e.time < b + x.width ∧ e.time < x.«end»))))
    ⟨s.count + 1, s.sum + e.value.getD 0⟩ s

def sourceStatsStep (x : Input) (g : String) (b : Int)
    (s : StatsRep) (e : EventRep) : StatsRep :=
  if
    (match e.2.2.1 with | none => false | some _ => true) &&
      (decide (e.1 = g) &&
        (decide (b ≤ e.2.1) &&
          (decide (e.2.1 < b + x.width) &&
            decide (e.2.1 < x.«end»))))
  then
    (s.1 + 1,
      (s.2.1 + (match e.2.2.1 with | none => 0 | some v => v), ()))
  else s

def sourceStats (x : Input) (g : String) (b : Int) : StatsRep :=
  (x.events.map eventRep).foldl (sourceStatsStep x g b) (0, (0, ()))

theorem stats_step (x : Input) (g : String) (b : Int)
    (s : Stats) (e : Event) :
    sourceStatsStep x g b (statsRep s) (eventRep e) =
      statsRep (acceptedStatsStep x g b s e) := by
  cases hv : e.value <;>
    simp [sourceStatsStep, acceptedStatsStep, eventRep, statsRep, hv,
      cond_ite, decide_and,
      VSCore3.ProofSupport.apply_ite,
      VSCore3.ProofSupport.apply_bool_ite,
      VSCore3.ProofSupport.ite_decide]

theorem stats_eq (x : Input) (g : String) (b : Int) :
    sourceStats x g b = statsRep (stats x g b) := by
  exact fold_transport eventRep statsRep
    (sourceStatsStep x g b) (acceptedStatsStep x g b)
    (stats_step x g b) x.events ⟨0, 0⟩

def acceptedStateStep (x : Input) (g : String)
    (s : State) (b : Int) : State :=
  let t := stats x g b
  ⟨s.rows ++
      [⟨g, b, t.count,
        cond (decide (0 < t.count)) (some t.sum)
          (cond (decide (x.fill = "previous")) s.previous none)⟩],
    cond (decide (0 < t.count)) (some t.sum) s.previous⟩

def sourceStateStep (x : Input) (g : String)
    (s : StateRep) (b : Int) : StateRep :=
  let t := sourceStats x g b
  (s.1 ++
    [(g, (b, (t.1,
      ((if decide (0 < t.1) then some t.2.1
        else if decide (x.fill = "previous") then s.2.1 else none), ()))))],
    ((if decide (0 < t.1) then some t.2.1 else s.2.1), ()))

def sourceGroupRows (x : Input) (g : String) : List OutputRep :=
  ((buckets x).foldl (sourceStateStep x g)
    ([], (none, ()))).1

theorem state_step (x : Input) (g : String)
    (s : State) (b : Int) :
    sourceStateStep x g (stateRep s) b =
      stateRep (acceptedStateStep x g s b) := by
  simp [sourceStateStep, acceptedStateStep, stats_eq,
    stateRep, statsRep, outputRep, cond_ite,
    VSCore3.ProofSupport.apply_ite,
    VSCore3.ProofSupport.apply_bool_ite,
    VSCore3.ProofSupport.ite_decide]

theorem group_rows_eq (x : Input) (g : String) :
    sourceGroupRows x g = (group_rows x g).map outputRep := by
  have h := fold_transport (fun b : Int => b) stateRep
    (sourceStateStep x g) (acceptedStateStep x g)
    (state_step x g) (buckets x) ⟨[], none⟩
  simp only [VSCore3.ProofSupport.map_identity] at h
  have hp := congrArg (fun s : StateRep => s.1) h
  simpa [sourceGroupRows, stateRep, group_rows, acceptedStateStep,
    List.foldl_cons, List.foldl_nil] using hp

def sourceGroups (x : Input) : List String :=
  (((x.events.map eventRep).map (fun e => e.1)).eraseDups).mergeSort
    (fun a b => decide (a ≤ b))

theorem groups_eq (x : Input) : sourceGroups x = groups x := by
  simp [sourceGroups, groups, List.map_map, eventRep]

def sourceSolve (x : Input) : List OutputRep :=
  (sourceGroups x).foldl
    (fun rows g => rows ++ sourceGroupRows x g) []

theorem solve_eq (x : Input) :
    sourceSolve x = (solve x).map outputRep := by
  have h := fold_transport (fun g : String => g)
    (fun rows : List Output => rows.map outputRep)
    (fun rows g => rows ++ sourceGroupRows x g)
    (fun rows g => rows ++ group_rows x g)
    (by
      intro rows g
      simp [group_rows_eq, List.map_append])
    (groups x) []
  simpa [sourceSolve, groups_eq, solve,
    VSCore3.ProofSupport.map_identity] using h

theorem output_roundtrip (o : Output) :
    outputInv (outputRep o) = o := by
  cases o
  simp [outputInv, outputRep]

theorem refines_solve : VeriSlopBridgeGoal.Refines_solve := by
  intro x
  with_unfolding_all
    change (sourceSolve x).map outputInv = solve x
  rw [solve_eq]
  simp only [List.map_map, output_roundtrip,
    VSCore3.ProofSupport.map_identity]

theorem edge : VeriSlopBridgeGoal.EdgeProp :=
  VeriSlopBridgeGoal.edge_of_refines refines_solve

end VeriSlopBridgeProof
