import Std

namespace VeriSlop.D06

abbrev Lines := List String

structure Boundary where
  isBoolean : Bool
  isNegative : Bool
  magnitude : Nat
  deriving DecidableEq

structure Operation where
  boundary : Boundary
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

def boundaryInRange (boundary : Boundary) (currentLength : Nat) : Bool :=
  !boundary.isBoolean && !boundary.isNegative && boundary.magnitude ≤ currentLength

def matchesAt (position : Nat) (remove current : Lines) : Bool :=
  (current.drop position).take remove.length == remove

def replaceAt (position : Nat) (remove insert current : Lines) : Lines :=
  current.take position ++ insert ++ current.drop (position + remove.length)

def applyOne (current : Lines) (operation : Operation) (index : Nat) : Result :=
  if !boundaryInRange operation.boundary current.length then
    .error ⟨ErrorKind.range, index⟩
  else if matchesAt operation.boundary.magnitude operation.remove current then
    .ok (replaceAt operation.boundary.magnitude operation.remove operation.insert current)
  else
    .error ⟨ErrorKind.context, index⟩

def applyOperations (current : Lines) (operations : Operations) : Result :=
  operations.zipIdx.foldl
    (fun accumulated indexedOperation =>
      match accumulated with
      | .error failure => .error failure
      | .ok currentLines =>
          applyOne currentLines indexedOperation.1 indexedOperation.2)
    (.ok current)

def solve (data : Input) : Result :=
  applyOperations data.lines data.operations

theorem G1 (data : Input) :
    solve data = applyOperations data.lines data.operations := by sorry

theorem G2 (current : Lines) (operation : Operation) (index : Nat) :
    boundaryInRange operation.boundary current.length = false →
    applyOne current operation index = .error ⟨ErrorKind.range, index⟩ := by sorry

theorem G3 (current : Lines) (operation : Operation) (index : Nat) :
    boundaryInRange operation.boundary current.length = true →
    matchesAt operation.boundary.magnitude operation.remove current = false →
    applyOne current operation index = .error ⟨ErrorKind.context, index⟩ := by sorry

theorem G4 (current : Lines) (operation : Operation) (index : Nat) :
    boundaryInRange operation.boundary current.length = true →
    matchesAt operation.boundary.magnitude operation.remove current = true →
    applyOne current operation index =
      .ok (current.take operation.boundary.magnitude ++ operation.insert ++
        current.drop (operation.boundary.magnitude + operation.remove.length)) := by sorry

theorem G5 (current inserted : Lines) (boundary : Boundary) :
    boundary.isBoolean = false → boundary.isNegative = false →
    boundary.magnitude = current.length →
    applyOne current ⟨boundary, [], inserted⟩ 0 = .ok (current ++ inserted) := by sorry

theorem G6 (current : Lines) (operations : Operations) (failure : Failure) :
    applyOperations current operations = .error failure →
    ∃ firstFailure, applyOperations current operations = .error firstFailure ∧
      firstFailure = failure := by sorry

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
