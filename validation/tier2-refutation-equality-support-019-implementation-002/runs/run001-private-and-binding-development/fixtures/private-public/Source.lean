import Std
namespace PrivateEqualityRevision019
inductive Palette where | ochre | teal
private def hiddenEquality : DecidableEq Palette := fun a b => by
  cases a <;> cases b
  · exact isTrue rfl
  · exact isFalse (by intro equality; cases equality)
  · exact isFalse (by intro equality; cases equality)
  · exact isTrue rfl
def swap (color : Palette) : Palette :=
  match color with | .ochre => .teal | .teal => .ochre
theorem wrongSwap (color : Palette) : swap color = color := by sorry
theorem rightSwap (color : Palette) : swap (swap color) = color := by
  cases color <;> rfl
end PrivateEqualityRevision019
def zzUsableEquality : DecidableEq PrivateEqualityRevision019.Palette := fun a b => by
  cases a <;> cases b
  · exact isTrue rfl
  · exact isFalse (by intro equality; cases equality)
  · exact isFalse (by intro equality; cases equality)
  · exact isTrue rfl
