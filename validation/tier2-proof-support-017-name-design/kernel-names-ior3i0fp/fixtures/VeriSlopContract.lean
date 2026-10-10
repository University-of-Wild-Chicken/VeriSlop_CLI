import Std
namespace NameFixture
def bump (x : Int) : Int := x + 5
theorem plain_law (x : Int) : bump x = x + 5 := by rfl
theorem «bump-law» (x : Int) : bump x = x + 5 := by rfl
theorem «bump.law» (x : Int) : bump x = x + 5 := by rfl
theorem «bump:law» (x : Int) : bump x = x + 5 := by rfl
theorem «7» (x : Int) : bump x = x + 5 := by rfl
end NameFixture
