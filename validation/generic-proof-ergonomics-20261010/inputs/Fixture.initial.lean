import VSCore3.Transport

namespace GenericErgonomicsProbe

inductive Tint where
  | ivory
  | ochre
  deriving DecidableEq

structure Capsule where
  tint : Tint
  depth : Nat

structure Bundle where
  payload : Capsule

def tintShape : VSCore3.Shape := .enum "ProbeTint" ["ivory", "ochre"]
def capsuleShape : VSCore3.Shape :=
  .record "ProbeCapsule" ["tint", "depth"] (.product tintShape (.product .nat .unit))
def bundleShape : VSCore3.Shape :=
  .record "ProbeBundle" ["payload"] (.product capsuleShape .unit)

-- These bodies match the current bridge's exact enum/record adapter recipes.
def tintAdapter : VSCore3.Adapter tintShape Tint where
  to := fun x => match x with
    | .ivory => ⟨"ivory", by decide +kernel⟩
    | .ochre => ⟨"ochre", by decide +kernel⟩
  inv := fun x => if x.val = "ivory" then Tint.ivory else Tint.ochre
  from_to := by intro x; cases x <;> rfl
  to_from := by
    intro x
    rcases x with ⟨x, h⟩
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl | rfl <;> rfl

def capsuleAdapter : VSCore3.Adapter capsuleShape Capsule where
  to := fun x => (tintAdapter.to x.tint, (VSCore3.natAdapter.to x.depth, ()))
  inv := fun x => Capsule.mk (tintAdapter.inv x.1) (VSCore3.natAdapter.inv x.2.1)
  from_to := by intro x; cases x; simp [tintAdapter.from_to, VSCore3.natAdapter.from_to]
  to_from := by
    intro x
    rcases x with ⟨a, b, u⟩
    cases u
    simp [tintAdapter.to_from, VSCore3.natAdapter.to_from]

def bundleAdapter : VSCore3.Adapter bundleShape Bundle where
  to := fun x => (capsuleAdapter.to x.payload, ())
  inv := fun x => Bundle.mk (capsuleAdapter.inv x.1)
  from_to := by intro x; cases x; simp [capsuleAdapter.from_to]
  to_from := by
    intro x
    rcases x with ⟨a, u⟩
    cases u
    simp [capsuleAdapter.to_from]

def representedIvory (x : VSCore3.Denote tintShape) : Bool :=
  letI := VSCore3.denoteDecidableEq tintShape
  decide (x = tintAdapter.to .ivory)

def ordinaryIvory (x : Tint) : Bool := decide (x = .ivory)

def mapped (xs : List Bundle) : List Tint :=
  (VSCore3.listAdapter tintAdapter).inv
    (((VSCore3.listAdapter bundleAdapter).to xs).map (fun x => x.1.1))

def filtered (xs : List Bundle) : List Bundle :=
  (VSCore3.listAdapter bundleAdapter).inv
    (((VSCore3.listAdapter bundleAdapter).to xs).filter (fun x => representedIvory x.1.1))

def folded (xs : List Bundle) : Nat :=
  (((VSCore3.listAdapter bundleAdapter).to xs).foldl
    (fun acc x => if representedIvory x.1.1 then acc + x.1.2.1 else acc) 0)

end GenericErgonomicsProbe
