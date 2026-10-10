import Std
namespace PrivateEqualityRevision019
inductive Palette where | ochre | teal
def swap (color : Palette) : Palette :=
  match color with | .ochre => .teal | .teal => .ochre
theorem wrongSwap (color : Palette) : swap color = color := by sorry
theorem rightSwap (color : Palette) : swap (swap color) = color := by
  cases color <;> rfl
end PrivateEqualityRevision019
