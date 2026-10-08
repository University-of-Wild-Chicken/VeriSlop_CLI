import Std

namespace VeriSlop.D06

abbrev Lines := List String

structure Boundary where
  isBoolean : Bool
  isNegative : Bool
  magnitude : Nat
  deriving DecidableEq

structure Operation where
  at : Boundary
  remove : Lines
  insert : Lines
  deriving DecidableEq

abbrev Operations := List Operation

structure Input where
  lines : Lines
  operations : Operations
  deriving DecidableEq

inductive ErrorKind
  | range
  | context
  deriving DecidableEq

structure Failure where
  kind : ErrorKind
  operationIndex : Nat
  deriving DecidableEq

abbrev Result := Except Failure Lines

 def boundaryValue (at : Boundary) : Nat := at.magnitude

def boundaryInRange (at : Boundary) (currentLength : Nat) : Bool :=
  !at.isBoolean && !at.isNegative && at.magnitude ≤ currentLength

def matchesAt (at : Nat) (remove current : Lines) : Bool :=
  (current.drop at).take remove.length == remove

def replaceAt (at : Nat) (remove insert current : Lines) : Lines :=
  current.take at ++ insert ++ current.drop (at + remove.length)

def applyOne (current : Lines) (operation : Operation) (index : Nat) : Result :=
  if !boundaryInRange operation.at current.length then
    .error ⟨ErrorKind.range, index⟩
  else if matchesAt (boundaryValue operation.at) operation.remove current then
    .ok (replaceAt (boundaryValue operation.at) operation.remove operation.insert current)
  else
    .error ⟨ErrorKind.context, index⟩

def applyOperations (current : Lines) (operations : Operations) : Result :=
  operations.foldl (fun state indexed =>
    match state with
    | .error failure => .error failure
    | .ok lines => applyOne lines indexed.1 indexed.2)
    (.ok current) (operations.zipIdx)

def solve (data : Input) : Result :=
  applyOperations data.lines data.operations

theorem G1 (data : Input) :
    solve data = applyOperations data.lines data.operations := by sorry

theorem G2 (current : Lines) (operation : Operation) (index : Nat) :
    (!boundaryInRange operation.at current.length) →
    applyOne current operation index = .error ⟨ErrorKind.range, index⟩ := by sorry

theorem G3 (current : Lines) (operation : Operation) (index : Nat) :
    boundaryInRange operation.at current.length = true →
    matchesAt (boundaryValue operation.at) operation.remove current = false →
    applyOne current operation index = .error ⟨ErrorKind.context, index⟩ := by sorry

theorem G4 (current : Lines) (operation : Operation) (index : Nat) :
    boundaryInRange operation.at current.length = true →
    matchesAt (boundaryValue operation.at) operation.remove current = true →
    applyOne current operation index =
      .ok (current.take (boundaryValue operation.at) ++ operation.insert ++
        current.drop (boundaryValue operation.at + operation.remove.length)) := by sorry

theorem G5 (current inserted : Lines) (at : Boundary) :
    at.isBoolean = false → at.isNegative = false → at.magnitude = current.length →
    applyOne current ⟨at, [], inserted⟩ 0 = .ok (current ++ inserted) := by sorry

theorem G6 (current : Lines) (operation : Operation) (index : Nat) :
    applyOne current operation index = .error ⟨ErrorKind.range, index⟩ ∨
    applyOne current operation index = .error ⟨ErrorKind.context, index⟩ →
    ∃ failure, applyOne current operation index = .error failure ∧
      failure.operationIndex = index := by sorry

theorem G7 (data : Input) (finalLines : Lines) :
    solve data = .ok finalLines →
    ∃ resultLines, solve data = .ok resultLines ∧ resultLines = finalLines := by sorry

theorem G8 (line : String) (lines : Lines) :
    line :: lines = line :: lines := by sorry

theorem G9 (data : Input) : solve data = solve data := by sorry

theorem G10 (data : Input) : solve data = solve data := by sorry

theorem G11 :
    solve ⟨["a", "b"],
      [⟨⟨false, false, 1⟩, ["b"], ["x", "y"]⟩,
       ⟨⟨false, false, 2⟩, ["y"], []⟩]⟩ = .ok ["a", "x"] ∧
    solve ⟨["a"], [⟨⟨false, false, 1⟩, ["b"], []⟩]⟩ =
      .error ⟨ErrorKind.context, 0⟩ := by sorry

end VeriSlop.D06
