import VeriSlopBridgeGoal

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeProof

open VeriSlopBridgeGoal

private abbrev E := String × Int × Option Int × Unit
private abbrev B := String × Int × Nat × Option Int × Unit
private abbrev S := Option Int × List B × Unit

private def epack (e : VeriSlopAST.Event) : E :=
  (e.group, e.time, e.value.map (fun z => z), ())

private def bpack (b : VeriSlopAST.Bucket) : B :=
  (b.group, b.start, b.count, b.value.map (fun z => z), ())

private def bunpack (b : B) : VeriSlopAST.Bucket :=
  ⟨b.1, b.2.1, b.2.2.1, b.2.2.2.1.map (fun z => z)⟩

private def spack (s : VeriSlopAST.Scan) : S :=
  (s.previous, s.rows.map bpack, ())

private theorem bunpack_bpack (b : VeriSlopAST.Bucket) :
    bunpack (bpack b) = b := by
  cases b
  simp [bunpack, bpack]

private theorem fold_encode
    {A A' C C' : Type}
    (xs : List C) (f : A → C → A) (f' : A' → C' → A')
    (pa : A → A') (pc : C → C')
    (h : ∀ a c, f' (pa a) (pc c) = pa (f a c))
    (a : A) :
    (xs.map pc).foldl f' (pa a) = pa (xs.foldl f a) := by
  induction xs generalizing a with
  | nil => rfl
  | cons c cs ih =>
    simp only [List.map_cons, List.foldl_cons, h]
    exact ih (f a c)

private def rawStep (x : VeriSlopAST.Input) (g : String) (b : B) (e : E) : B :=
  if decide (e.1 = g) &&
      ((match e.2.2.1 with | none => false | some _ => true) &&
        (decide (b.2.1 ≤ e.2.1) &&
          (decide (e.2.1 < b.2.1 + x.width) &&
            decide (e.2.1 < x.end))))
  then
    (b.1, b.2.1, b.2.2.1 + 1,
      some ((match b.2.2.2.1 with | none => 0 | some z => z) +
        (match e.2.2.1 with | none => 0 | some z => z)), ())
  else b

private def bucketStep
    (x : VeriSlopAST.Input) (g : String)
    (b : VeriSlopAST.Bucket) (e : VeriSlopAST.Event) : VeriSlopAST.Bucket :=
  cond
    (decide (e.group = g) &&
      (e.value.isSome &&
        decide (b.start ≤ e.time ∧
          (e.time < b.start + x.width ∧ e.time < x.end))))
    ⟨b.group, b.start, b.count + 1,
      some (b.value.getD 0 + e.value.getD 0)⟩
    b

private theorem rawStep_pack
    (x : VeriSlopAST.Input) (g : String)
    (b : VeriSlopAST.Bucket) (e : VeriSlopAST.Event) :
    rawStep x g (bpack b) (epack e) = bpack (bucketStep x g b e) := by
  cases hb : b.value <;> cases he : e.value <;>
    by_cases hg : e.group = g <;>
    by_cases h₁ : b.start ≤ e.time <;>
    by_cases h₂ : e.time < b.start + x.width <;>
    by_cases h₃ : e.time < x.end <;>
    simp [rawStep, bucketStep, bpack, epack, hb, he, hg, h₁, h₂, h₃,
      Option.isSome, Option.getD, cond]

private def rawAggregate (x : VeriSlopAST.Input) (g : String) (n : Nat) : B :=
  (x.events.map epack).foldl (rawStep x g)
    (g, x.start + (n : Int) * x.width, 0, some 0, ())

private theorem rawAggregate_pack
    (x : VeriSlopAST.Input) (g : String) (n : Nat) :
    rawAggregate x g n = bpack (VeriSlopAST.aggregate x g n) := by
  simpa only [rawAggregate, VeriSlopAST.aggregate, bucketStep, bpack,
    Option.map_some] using
    fold_encode x.events (bucketStep x g) (rawStep x g) bpack epack
      (rawStep_pack x g)
      (VeriSlopAST.Bucket.mk g (x.start + (n : Int) * x.width) 0 (some 0))

private def rawScan (x : VeriSlopAST.Input) (s : S) (b : B) : S :=
  (if decide (0 < b.2.2.1) then b.2.2.2.1 else s.1,
    s.2.1 ++
      [(b.1, b.2.1, b.2.2.1,
        if decide (0 < b.2.2.1) then b.2.2.2.1
        else if decide (x.fill = "previous") then s.1 else none, ())],
    ())

private def scanStep
    (x : VeriSlopAST.Input) (s : VeriSlopAST.Scan)
    (b : VeriSlopAST.Bucket) : VeriSlopAST.Scan :=
  ⟨cond (decide (0 < b.count)) b.value s.previous,
    s.rows ++
      [⟨b.group, b.start, b.count,
        cond (decide (0 < b.count)) b.value
          (cond (decide (x.fill = "previous")) s.previous none)⟩]⟩

private theorem rawScan_pack
    (x : VeriSlopAST.Input) (s : VeriSlopAST.Scan)
    (b : VeriSlopAST.Bucket) :
    rawScan x (spack s) (bpack b) = spack (scanStep x s b) := by
  by_cases hc : 0 < b.count <;>
    by_cases hf : x.fill = "previous" <;>
    simp [rawScan, scanStep, spack, bpack, hc, hf, cond, List.map_append]

private def bucketCount (x : VeriSlopAST.Input) : Nat :=
  ((x.end - x.start + x.width - 1).fdiv x.width).toNat

private def rawGroup (x : VeriSlopAST.Input) (g : String) : List B :=
  ((List.range (bucketCount x)).foldl
    (fun s n => rawScan x s (rawAggregate x g n))
    (none, [], ())).2.1

private theorem rawGroup_pack (x : VeriSlopAST.Input) (g : String) :
    rawGroup x g = (VeriSlopAST.group_rows x g).map bpack := by
  have h :=
    fold_encode (List.range (bucketCount x))
      (fun s n => scanStep x s (VeriSlopAST.aggregate x g n))
      (fun s n => rawScan x s (rawAggregate x g n))
      spack (fun n => n)
      (by
        intro s n
        rw [rawAggregate_pack]
        exact rawScan_pack x s (VeriSlopAST.aggregate x g n))
      (VeriSlopAST.Scan.mk none [])
  have hp := congrArg (fun s : S => s.2.1) h
  simpa only [rawGroup, bucketCount, VeriSlopAST.group_rows,
    scanStep, spack, List.map_nil, List.foldl_cons, List.foldl_nil,
    VSCore3.ProofSupport.map_identity] using hp

private def rawSolve (x : VeriSlopAST.Input) : List B :=
  (((x.events.map epack).map (fun e => e.1)).eraseDups.mergeSort
    (fun a b => decide (a ≤ b))).foldl
      (fun acc g => acc ++ rawGroup x g) []

private theorem rawSolve_pack (x : VeriSlopAST.Input) :
    rawSolve x = (VeriSlopAST.solve x).map bpack := by
  have h :=
    fold_encode
      ((x.events.map VeriSlopAST.Event.group).eraseDups.mergeSort
        (fun a b => decide (a ≤ b)))
      (fun acc g => acc ++ VeriSlopAST.group_rows x g)
      (fun acc g => acc ++ rawGroup x g)
      (List.map bpack) (fun g => g)
      (by
        intro acc g
        simp only [rawGroup_pack, List.map_append])
      []
  simpa only [rawSolve, VeriSlopAST.solve, List.map_map, epack,
    Function.comp_def, List.map_nil,
    VSCore3.ProofSupport.map_identity] using h

theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  intro x
  with_unfolding_all
    change (rawSolve x).map bunpack = VeriSlopAST.solve x
  rw [rawSolve_pack]
  simp only [List.map_map, bunpack_bpack, VSCore3.ProofSupport.map_identity]

end VeriSlopBridgeProof
