import VeriSlopBridgeGoal

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeProof

open VeriSlopBridgeGoal

private abbrev B := String × Int × Nat × Option Int × Unit
private abbrev E := String × Int × Option Int × Unit
private abbrev S := Option Int × List B × Unit

private def eb (b : VeriSlopAST.Bucket) : B :=
  (b.group, b.start, b.count, b.value, ())
private def ee (e : VeriSlopAST.Event) : E :=
  (e.group, e.time, e.value, ())
private def es (s : VeriSlopAST.Scan) : S :=
  (s.previous, s.rows.map eb, ())

private theorem fold_transport
    {A A' C C' : Type}
    (encodeA : A → A') (encodeC : C → C')
    (f : A → C → A) (g : A' → C' → A')
    (h : ∀ a c, g (encodeA a) (encodeC c) = encodeA (f a c))
    (xs : List C) (a : A) :
    (xs.map encodeC).foldl g (encodeA a) =
      encodeA (xs.foldl f a) := by
  induction xs generalizing a with
  | nil => rfl
  | cons c cs ih =>
      simp only [List.map_cons, List.foldl_cons]
      rw [h, ih]

private def zero (x : Option Int) : Int :=
  match x with
  | none => 0
  | some v => v

private theorem zero_eq (x : Option Int) : zero x = x.getD 0 := by
  cases x <;> rfl

private def astep (x : VeriSlopAST.Input) (group : String)
    (b : B) (e : E) : B :=
  if decide (e.1 = group) &&
      ((match e.2.2.1 with | none => false | some _ => true) &&
        (decide (b.2.1 ≤ e.2.1) &&
          (decide (e.2.1 < b.2.1 + x.width) &&
            decide (e.2.1 < x.end)))) then
    (b.1, b.2.1, b.2.2.1 + 1,
      some (zero b.2.2.2.1 + zero e.2.2.1), ())
  else b

private def aggregate (x : VeriSlopAST.Input) (group : String)
    (index : Nat) : B :=
  (x.events.map ee).foldl (astep x group)
    (group, x.start + Int.ofNat index * x.width, 0, some 0, ())

private theorem aggregate_eq (x : VeriSlopAST.Input)
    (group : String) (index : Nat) :
    aggregate x group index = eb (VeriSlopAST.aggregate x group index) := by
  unfold aggregate VeriSlopAST.aggregate
  refine fold_transport eb ee _ (astep x group) ?_ x.events
    (VeriSlopAST.Bucket.mk group
      (x.start + Int.ofNat index * x.width) 0 (some 0))
  intro b e
  cases e with
  | mk eg et ev =>
      cases ev <;>
        simp [astep, eb, ee, zero_eq, cond,
          Bool.decide_and, VSCore3.ProofSupport.ite_decide,
          VSCore3.ProofSupport.apply_ite,
          VSCore3.ProofSupport.apply_bool_ite]

private def sstep (x : VeriSlopAST.Input) (s : S) (b : B) : S :=
  (if decide (0 < b.2.2.1) then b.2.2.2.1 else s.1,
    s.2.1 ++
      [(b.1, b.2.1, b.2.2.1,
        if decide (0 < b.2.2.1) then b.2.2.2.1
        else if decide (x.fill = "previous") then s.1 else none, ())],
    ())

private def rows (x : VeriSlopAST.Input) (group : String) : List B :=
  ((List.range
      (Int.toNat
        (Int.fdiv ((x.end - x.start + x.width) - 1) x.width))).foldl
      (fun s index => [aggregate x group index].foldl (sstep x) s)
      (none, [], ())).2.1

private theorem rows_eq (x : VeriSlopAST.Input) (group : String) :
    rows x group = (VeriSlopAST.group_rows x group).map eb := by
  unfold rows VeriSlopAST.group_rows
  have h :
      (List.range
        (Int.toNat
          (Int.fdiv ((x.end - x.start + x.width) - 1) x.width))).foldl
        (fun s index => [aggregate x group index].foldl (sstep x) s)
        (es ⟨none, []⟩) =
      es
        ((List.range
          (Int.toNat
            (Int.fdiv ((x.end - x.start + x.width) - 1) x.width))).foldl
          (fun s index =>
            [VeriSlopAST.aggregate x group index].foldl
              (fun s b =>
                ⟨cond (decide (0 < b.count)) b.value s.previous,
                  s.rows ++
                    [⟨b.group, b.start, b.count,
                      cond (decide (0 < b.count)) b.value
                        (cond (decide (x.fill = "previous")) s.previous none)⟩]⟩)
              s)
          ⟨none, []⟩) := by
    let indices :=
      List.range
        (Int.toNat
          (Int.fdiv ((x.end - x.start + x.width) - 1) x.width))
    change indices.foldl _ (es ⟨none, []⟩) = es (indices.foldl _ ⟨none, []⟩)
    have ht := fold_transport es (fun n : Nat => n)
      (fun (s : VeriSlopAST.Scan) index =>
        [VeriSlopAST.aggregate x group index].foldl
          (fun s b =>
            ⟨cond (decide (0 < b.count)) b.value s.previous,
              s.rows ++
                [⟨b.group, b.start, b.count,
                  cond (decide (0 < b.count)) b.value
                    (cond (decide (x.fill = "previous")) s.previous none)⟩]⟩)
          s)
      (fun s index => [aggregate x group index].foldl (sstep x) s)
      (by
        intro s index
        rw [aggregate_eq]
        simp [List.foldl, sstep, es, eb, List.map_append, cond,
          VSCore3.ProofSupport.ite_decide,
          VSCore3.ProofSupport.apply_ite,
          VSCore3.ProofSupport.apply_bool_ite])
      indices ⟨none, []⟩
    simpa only [VSCore3.ProofSupport.map_identity] using ht
  exact congrArg (fun s : S => s.2.1) h

private def run (x : VeriSlopAST.Input) : List B :=
  (((x.events.map ee).map (fun e => e.1)).eraseDups.mergeSort
    (fun a b => decide (a ≤ b))).foldl
    (fun acc group => acc ++ rows x group) []

private theorem run_eq (x : VeriSlopAST.Input) :
    run x = (VeriSlopAST.solve x).map eb := by
  unfold run VeriSlopAST.solve
  simp only [List.map_map]
  have h := fold_transport (List.map eb) (fun g : String => g)
    (fun acc group => acc ++ VeriSlopAST.group_rows x group)
    (fun acc group => acc ++ rows x group)
    (by
      intro acc group
      simp only [rows_eq, List.map_append])
    ((x.events.map VeriSlopAST.Event.group).eraseDups.mergeSort
      (fun a b => decide (a ≤ b))) []
  simpa only [ee, VSCore3.ProofSupport.map_identity] using h

theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  intro x
  with_unfolding_all
    change
      (run x).map
        (fun b => VeriSlopAST.Bucket.mk
          b.1 b.2.1 b.2.2.1
          (b.2.2.2.1.map (fun v => v))) =
      VeriSlopAST.solve x
  rw [run_eq]
  simp [List.map_map, eb, VSCore3.ProofSupport.map_identity]

end VeriSlopBridgeProof
