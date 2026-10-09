import Std
namespace PrimitiveFixture
def shifted (offset : Int) (xs : List Int) : List Int := xs.map (fun x => x + offset)
def selected (limit : Int) (xs : List Int) : List Int := xs.filter (fun x => decide (x < limit))
def total (limit : Int) (xs : List Int) : Int :=
  ((xs.filter (fun x => decide (x < limit))).map (fun x => x + limit)).sum
theorem shifted_contract : forall offset xs, shifted offset xs = xs.map (fun x => x + offset) := by intros; rfl
theorem selected_contract : forall limit xs, selected limit xs = xs.filter (fun x => decide (x < limit)) := by intros; rfl
theorem total_contract : forall limit xs, total limit xs =
  ((xs.filter (fun x => decide (x < limit))).map (fun x => x + limit)).sum := by intros; rfl
end PrimitiveFixture
