import Fixture
namespace GenericErgonomicsProbe

theorem decisionControl (x : Tint) : representedIvory (tintAdapter.to x) = ordinaryIvory x := by
  cases x <;> rfl

theorem mapControl (xs : List Bundle) : mapped xs = xs.map (fun x => x.payload.tint) := by
  simp only [mapped, VSCore3.listAdapter, List.map_map, Function.comp_def,
    bundleAdapter, capsuleAdapter, tintAdapter.from_to]

theorem filterControl (xs : List Bundle) : filtered xs = xs.filter (fun x => ordinaryIvory x.payload.tint) := by
  change List.map bundleAdapter.inv
    (List.filter (fun x => representedIvory x.1.1) (List.map bundleAdapter.to xs)) = _
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    simp only [List.map_cons, List.filter_cons]
    have hc : representedIvory (bundleAdapter.to x).1.1 = ordinaryIvory x.payload.tint :=
      decisionControl x.payload.tint
    rw [hc]
    cases h : ordinaryIvory x.payload.tint <;>
      simp [h, bundleAdapter.from_to, ih]

theorem foldControlGeneral (xs : List Bundle) (initial : Nat) :
    ((VSCore3.listAdapter bundleAdapter).to xs).foldl
      (fun acc x => if representedIvory x.1.1 then acc + x.1.2.1 else acc) initial =
    xs.foldl (fun acc x => if ordinaryIvory x.payload.tint then acc + x.payload.depth else acc) initial := by
  induction xs generalizing initial with
  | nil => rfl
  | cons x xs ih =>
    simp only [VSCore3.listAdapter, List.map_cons, List.foldl_cons,
      bundleAdapter, capsuleAdapter, VSCore3.natAdapter, decisionControl]
    exact ih _

theorem foldControl (xs : List Bundle) : folded xs =
    xs.foldl (fun acc x => if ordinaryIvory x.payload.tint then acc + x.payload.depth else acc) 0 :=
  foldControlGeneral xs 0

end GenericErgonomicsProbe
