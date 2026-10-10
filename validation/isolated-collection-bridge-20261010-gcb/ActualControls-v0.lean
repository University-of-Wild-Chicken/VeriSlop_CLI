import VeriSlopBridgeGoal
import VSCore3
universe u v
namespace GenericUniversalControls
open VSCore3

-- Existing catalog: universal positive controls, no fixture parameters.
theorem catalog_apply_ite {α : Sort u} {β : Sort v} (f : α → β) (p : Prop)
    [Decidable p] (x y : α) : f (if p then x else y) = if p then f x else f y :=
  ProofSupport.apply_ite f p x y

theorem catalog_apply_bool_ite {α : Sort u} {β : Sort v} (f : α → β) (b : Bool)
    (x y : α) : f (if b then x else y) = if b then f x else f y :=
  ProofSupport.apply_bool_ite f b x y

theorem catalog_ite_decide {α : Sort u} (p : Prop) [Decidable p] (x y : α) :
    (if decide p then x else y) = if p then x else y := ProofSupport.ite_decide p x y

theorem catalog_map_identity {α : Type u} (xs : List α) :
    xs.map (fun x => x) = xs := ProofSupport.map_identity xs

theorem catalog_int_ofNat_eq_cast (n : Nat) : Int.ofNat n = (n : Int) :=
  ProofSupport.int_ofNat_eq_cast n

theorem catalog_int_ofNat_add (m n : Nat) :
    Int.ofNat (m + n) = Int.ofNat m + Int.ofNat n := ProofSupport.int_ofNat_add m n

-- Proposed universal signatures; these use the actual current Adapter type.
theorem to_eq_iff {t : Shape} {α : Type} (a : Adapter t α) (x y : α) :
    a.to x = a.to y ↔ x = y := by
  constructor
  · intro h
    have hi := congrArg a.inv h
    simpa only [a.from_to] using hi
  · intro h; cases h; rfl

theorem decide_to_eq {t : Shape} {α : Type} (a : Adapter t α)
    [DecidableEq α] [DecidableEq (Denote t)] (x y : α) :
    decide (a.to x = a.to y) = decide (x = y) := by
  apply Bool.eq_iff_iff.mpr
  simp only [decide_eq_true_eq]
  exact to_eq_iff a x y

theorem map_transport {t u : Shape} {α β : Type}
    (a : Adapter t α) (b : Adapter u β) (f : α → β) (g : Denote t → Denote u)
    (h : ∀ x, g (a.to x) = b.to (f x)) (xs : List α) :
    (listAdapter b).inv (List.map g ((listAdapter a).to xs)) = List.map f xs := by
  change List.map b.inv (List.map g (List.map a.to xs)) = List.map f xs
  induction xs with
  | nil => rfl
  | cons x xs ih => simp only [List.map_cons, h x, b.from_to, ih]

theorem filter_transport {t : Shape} {α : Type}
    (a : Adapter t α) (p : α → Bool) (q : Denote t → Bool)
    (h : ∀ x, q (a.to x) = p x) (xs : List α) :
    (listAdapter a).inv (List.filter q ((listAdapter a).to xs)) = List.filter p xs := by
  change List.map a.inv (List.filter q (List.map a.to xs)) = List.filter p xs
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    simp only [List.map_cons, List.filter_cons, h x]
    cases p x <;> simp_all [a.from_to]

theorem foldl_transport {t u : Shape} {α β : Type}
    (a : Adapter t α) (b : Adapter u β) (f : β → α → β)
    (g : Denote u → Denote t → Denote u)
    (h : ∀ z x, g (b.to z) (a.to x) = b.to (f z x))
    (z : β) (xs : List α) :
    b.inv (List.foldl g (b.to z) ((listAdapter a).to xs)) = List.foldl f z xs := by
  change b.inv (List.foldl g (b.to z) (List.map a.to xs)) = List.foldl f z xs
  induction xs generalizing z with
  | nil => exact b.from_to z
  | cons x xs ih => simp only [List.map_cons, List.foldl_cons, h z x, ih]

end GenericUniversalControls

namespace VeriSlopBridgeProof
open VeriSlopBridgeGoal GenericUniversalControls
set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

theorem ref_map : Refines_raiseBoxes := by
  intro xs
  rw [Readable.source_eq_raiseBoxes]
  with_unfolding_all
    apply map_transport adapter_4 adapter_4
    intro b
    rfl

theorem ref_filter : Refines_keepAtom := by
  intro xs needle
  rw [Readable.source_eq_keepAtom]
  with_unfolding_all
    apply filter_transport adapter_4
    intro b
    apply Bool.eq_iff_iff.mpr
    simp only [decide_eq_true_eq, Bool.and_eq_true]
    change adapter_2.to b.atom = adapter_2.to needle ↔ b.atom.tone = needle.tone ∧ b.atom.n = needle.n
    rw [to_eq_iff]
    constructor
    · intro h; cases h; exact ⟨rfl, rfl⟩
    · rintro ⟨ht, hn⟩
      cases b with
      | mk atom live =>
        cases atom with
        | mk tone n =>
          cases needle with
          | mk tone2 n2 => simp_all

theorem ref_fold : Refines_coldTotal := by
  intro xs
  rw [Readable.source_eq_coldTotal]
  with_unfolding_all
    apply foldl_transport adapter_4 adapter_1
    intro z b
    cases b with
    | mk atom live =>
      cases atom with
      | mk tone n => cases tone <;> rfl

theorem edge : EdgeProp := edge_of_refines ref_fold ref_filter ref_map
end VeriSlopBridgeProof
