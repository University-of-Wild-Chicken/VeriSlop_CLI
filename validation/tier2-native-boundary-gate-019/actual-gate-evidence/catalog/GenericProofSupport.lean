import VSCore3
universe u v
namespace GenericProofSupport
theorem signature_0 : ∀ {α : Sort u} {β : Sort v} (f : α → β) (p : Prop) [Decidable p] (x y : α), f (if p then x else y) = if p then f x else f y := @VSCore3.ProofSupport.apply_ite
theorem signature_1 : ∀ {α : Sort u} {β : Sort v} (f : α → β) (b : Bool) (x y : α), f (if b then x else y) = if b then f x else f y := @VSCore3.ProofSupport.apply_bool_ite
theorem signature_2 : ∀ {α : Sort u} (p : Prop) [Decidable p] (x y : α), (if decide p then x else y) = if p then x else y := @VSCore3.ProofSupport.ite_decide
theorem signature_3 : ∀ {α : Type u} (xs : List α), xs.map (fun x => x) = xs := @VSCore3.ProofSupport.map_identity
theorem signature_4 : ∀ (n : Nat), Int.ofNat n = (n : Int) := @VSCore3.ProofSupport.int_ofNat_eq_cast
theorem signature_5 : ∀ (m n : Nat), Int.ofNat (m + n) = Int.ofNat m + Int.ofNat n := @VSCore3.ProofSupport.int_ofNat_add
theorem signature_6 : ∀ {t : VSCore3.Shape} {α : Type} (a : VSCore3.Adapter t α) (x y : α), a.to x = a.to y ↔ x = y := @VSCore3.ProofSupport.to_eq_iff
theorem signature_7 : ∀ {t : VSCore3.Shape} {α : Type} (a : VSCore3.Adapter t α) [DecidableEq α] [DecidableEq (VSCore3.Denote t)] (x y : α), decide (a.to x = a.to y) = decide (x = y) := @VSCore3.ProofSupport.decide_to_eq
theorem signature_8 : ∀ {t u : VSCore3.Shape} {α β : Type} (a : VSCore3.Adapter t α) (b : VSCore3.Adapter u β) (f : α → β) (g : VSCore3.Denote t → VSCore3.Denote u) (h : ∀ x, g (a.to x) = b.to (f x)) (xs : List α), (VSCore3.listAdapter b).inv (List.map g ((VSCore3.listAdapter a).to xs)) = List.map f xs := @VSCore3.ProofSupport.map_transport
theorem signature_9 : ∀ {t : VSCore3.Shape} {α : Type} (a : VSCore3.Adapter t α) (p : α → Bool) (q : VSCore3.Denote t → Bool) (h : ∀ x, q (a.to x) = p x) (xs : List α), (VSCore3.listAdapter a).inv (List.filter q ((VSCore3.listAdapter a).to xs)) = List.filter p xs := @VSCore3.ProofSupport.filter_transport
theorem signature_10 : ∀ {t u : VSCore3.Shape} {α β : Type} (a : VSCore3.Adapter t α) (b : VSCore3.Adapter u β) (f : β → α → β) (g : VSCore3.Denote u → VSCore3.Denote t → VSCore3.Denote u) (h : ∀ z x, g (b.to z) (a.to x) = b.to (f z x)) (z : β) (xs : List α), b.inv (List.foldl g (b.to z) ((VSCore3.listAdapter a).to xs)) = List.foldl f z xs := @VSCore3.ProofSupport.foldl_transport

-- The element and result/accumulator carriers differ; neither list nor initial
-- accumulator is bounded or specialized to a sample.
theorem map_nat_to_int (xs : List Nat) :
    (VSCore3.listAdapter VSCore3.intAdapter).inv
      (List.map Int.ofNat ((VSCore3.listAdapter VSCore3.natAdapter).to xs)) =
      List.map Int.ofNat xs :=
  VSCore3.ProofSupport.map_transport VSCore3.natAdapter VSCore3.intAdapter
    Int.ofNat Int.ofNat (by intro n; rfl) xs

theorem fold_nat_to_int (z : Int) (xs : List Nat) :
    VSCore3.intAdapter.inv
      (List.foldl (fun acc n => acc + Int.ofNat n) (VSCore3.intAdapter.to z)
        ((VSCore3.listAdapter VSCore3.natAdapter).to xs)) =
      List.foldl (fun acc n => acc + Int.ofNat n) z xs :=
  VSCore3.ProofSupport.foldl_transport VSCore3.natAdapter VSCore3.intAdapter
    (fun acc n => acc + Int.ofNat n) (fun acc n => acc + Int.ofNat n)
    (by intro acc n; rfl) z xs

theorem closed_precondition : (2 : Nat) < 5 := by decide +kernel
end GenericProofSupport
