import VeriSlopBridgeGoal

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeProof

open VeriSlopAST

private abbrev RawEvent := String × Int × Option Int × Unit
private abbrev RawOutput := String × Int × Nat × Option Int × Unit
private abbrev RawStats := Nat × Int × Unit
private abbrev RawState := Option Int × List RawOutput × Unit

private def packEvent (e : Event) : RawEvent :=
  (e.group, e.time, e.value, ())

private def packOutput (o : Output) : RawOutput :=
  (o.group, o.start, o.count, o.value, ())

private def unpackOutput (o : RawOutput) : Output :=
  ⟨o.1, o.2.1, o.2.2.1, o.2.2.2.1⟩

private def packStats (s : Stats) : RawStats :=
  (s.count, s.sum, ())

private def packState (s : State) : RawState :=
  (s.previous, s.rows.map packOutput, ())

private def rawStats (x : Input) (g : String) (k : Nat) : RawStats :=
  (x.events.map packEvent).foldl
    (fun a e =>
      if decide (e.1 = g) &&
          (decide (x.start + Int.ofNat k * x.width ≤ e.2.1) &&
            (decide (e.2.1 < x.start + Int.ofNat k * x.width + x.width) &&
              decide (e.2.1 < x.«end»))) then
        match e.2.2.1 with
        | none => a
        | some v => (a.1 + 1, a.2.1 + v, ())
      else a)
    (0, 0, ())

private def rawStep (x : Input) (g : String) (k : Nat)
    (a : RawState) : RawState :=
  let s := rawStats x g k
  (if decide (0 < s.1) then some s.2.1 else a.1,
    a.2.1 ++
      [(g, x.start + Int.ofNat k * x.width, s.1,
        if decide (0 < s.1) then some s.2.1
        else if decide (x.fill = "previous") then a.1 else none, ())],
    ())

private def rawGroup (x : Input) (g : String) : List RawOutput :=
  ((List.range ((x.«end» - x.start + x.width - 1).fdiv x.width).toNat).foldl
    (fun a k => rawStep x g k a) (none, [], ())).2.1

private def rawSolve (x : Input) : List RawOutput :=
  (groups x).foldl (fun a g => a ++ rawGroup x g) []

private theorem foldl_transport {α β γ δ : Type}
    (f : α → β) (g : γ → δ)
    (step : α → γ → α) (step' : β → δ → β)
    (h : ∀ a e, f (step a e) = step' (f a) (g e))
    (xs : List γ) (a : α) :
    f (xs.foldl step a) = (xs.map g).foldl step' (f a) := by
  induction xs generalizing a with
  | nil => rfl
  | cons e es ih =>
    simp only [List.foldl_cons, List.map_cons, ih, h]

private theorem foldl_map_input {α β γ : Type}
    (f : α → β) (step : γ → β → γ) (xs : List α) (a : γ) :
    (xs.map f).foldl step a =
      xs.foldl (fun acc e => step acc (f e)) a := by
  induction xs generalizing a with
  | nil => rfl
  | cons e es ih =>
    simp only [List.map_cons, List.foldl_cons, ih]

private theorem rawStats_eq (x : Input) (g : String) (k : Nat) :
    rawStats x g k = packStats (stats x g k) := by
  unfold rawStats stats
  symm
  apply foldl_transport packStats packEvent
  intro a e
  cases hv : e.value with
  | none =>
    simp [packStats, packEvent, hv, Bool.and_eq_true,
      decide_eq_true_eq]
  | some v =>
    by_cases h :
      e.group = g ∧
        x.start + Int.ofNat k * x.width ≤ e.time ∧
        e.time < x.start + Int.ofNat k * x.width + x.width ∧
        e.time < x.«end»
    · simp [packStats, packEvent, hv, h, Bool.and_eq_true,
        decide_eq_true_eq]
    · simp [packStats, packEvent, hv, h, Bool.and_eq_true,
        decide_eq_true_eq]

private theorem rawStep_eq (x : Input) (g : String) (k : Nat) (a : State) :
    rawStep x g k (packState a) = packState (step x g k a) := by
  rw [rawStep, rawStats_eq]
  simp [step, packStats, packState, packOutput,
    List.foldl_cons, List.foldl_nil, List.map_append]
  <;> first
    | rfl
    | (split <;> simp_all [packOutput])

private theorem rawGroup_eq (x : Input) (g : String) :
    rawGroup x g = (group_rows x g).map packOutput := by
  have h := foldl_transport packState (fun k : Nat => k)
    (fun a k => step x g k a)
    (fun a k => rawStep x g k a)
    (fun a k => (rawStep_eq x g k a).symm)
    (List.range (bucket_count x)) (State.mk none [])
  simp only [List.map_id] at h
  have hp := congrArg (fun a : RawState => a.2.1) h
  simpa [rawGroup, group_rows, bucket_count, packState] using hp.symm

private theorem rawSolve_eq (x : Input) :
    rawSolve x = (solve x).map packOutput := by
  unfold rawSolve solve
  symm
  have h := foldl_transport (List.map packOutput) (fun g : String => g)
    (fun a g => a ++ group_rows x g)
    (fun a g => a ++ rawGroup x g)
    (by
      intro a g
      simp only [List.map_append, rawGroup_eq])
    (groups x) []
  simpa only [List.map_id, List.map_nil] using h

private theorem source_eq_raw (x : Input) :
    VeriSlopBridgeGoal.source_fn_solve x =
      (rawSolve x).map unpackOutput := by
  with_unfolding_all
    dsimp [VeriSlopBridgeGoal.source_fn_solve,
      VeriSlopBridgeGoal.entry_solve,
      VeriSlopBridgeGoal.checkedProgram,
      VeriSlopBridgeGoal.rawProgram,
      VeriSlopBridgeGoal.profile,
      VeriSlopBridgeGoal.adapter_0,
      VeriSlopBridgeGoal.adapter_1,
      VeriSlopBridgeGoal.adapter_2,
      VeriSlopBridgeGoal.adapter_3,
      VeriSlopBridgeGoal.adapter_4,
      VeriSlopBridgeGoal.adapter_5,
      VeriSlopBridgeGoal.adapter_6,
      VeriSlopBridgeGoal.adapter_7,
      VeriSlopBridgeGoal.adapter_8,
      VSCore3.stringAdapter, VSCore3.intAdapter,
      VSCore3.natAdapter, VSCore3.optionAdapter,
      VSCore3.listAdapter,
      VSCore3.compileProgram, VSCore3.findEntry]
    simp only [rawSolve, rawGroup, rawStep, rawStats,
      packEvent, unpackOutput, groups, foldl_map_input,
      List.map_map]
    rfl

theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  intro x
  rw [source_eq_raw, rawSolve_eq]
  simp only [List.map_map]
  have h : unpackOutput ∘ packOutput = id := by
    funext o
    cases o
    rfl
  rw [h, List.map_id]

end VeriSlopBridgeProof
