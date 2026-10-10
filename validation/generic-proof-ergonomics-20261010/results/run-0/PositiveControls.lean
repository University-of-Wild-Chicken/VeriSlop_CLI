import Fixture
namespace GenericErgonomicsProbe

theorem decisionControl (x : Tint) : representedIvory (tintAdapter.to x) = ordinaryIvory x := by
  cases x <;> rfl

theorem mapControl (xs : List Bundle) : mapped xs = xs.map (fun x => x.payload.tint) := by
  simp only [mapped, VSCore3.listAdapter, List.map_map, Function.comp_def,
    bundleAdapter, capsuleAdapter, tintAdapter.from_to]

theorem filterControl (xs : List Bundle) : filtered xs = xs.filter (fun x => ordinaryIvory x.payload.tint) := by
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    change (VSCore3.listAdapter bundleAdapter).inv
      ((bundleAdapter.to x :: (VSCore3.listAdapter bundleAdapter).to xs).filter
        (fun x => representedIvory x.1.1)) = _
    simp only [List.filter_cons, bundleAdapter, capsuleAdapter, decisionControl]
    cases h : ordinaryIvory x.payload.tint <;>
      simp [h, VSCore3.listAdapter, bundleAdapter.from_to, ih, filtered] at *

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
