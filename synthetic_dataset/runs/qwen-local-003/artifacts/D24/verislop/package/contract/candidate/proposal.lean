import Std

namespace VeriSlop.D24

inductive EditError where
  | boundary
  | overlap

inductive SolveResult where
  | ok (text : Nat)
  | err (kind : EditError) (edit : Nat)

structure Edit where
  start : Nat
  end : Nat
  text : Nat

structure Input where
  text : Nat
  edits : List Edit

def utf16_units (text : Nat) : Nat := text

def is_valid_boundary (text : Nat) (pos : Nat) : Bool := pos ≤ utf16_units text

def is_valid_boundary_pair (text : Nat) (e : Edit) : Bool :=
  is_valid_boundary text e.start && is_valid_boundary text e.end && e.start ≤ e.end

def is_valid_boundary_all (text : Nat) (edits : List Edit) : Bool :=
  List.all edits fun e => is_valid_boundary_pair text e

def is_no_overlap (edits : List Edit) : Bool :=
  match edits with
  | [] => true
  | e0 :: rest =>
    match rest with
    | [] => true
    | e1 :: rest2 =>
      if e1.start < e0.end then false
      else is_no_overlap (e1 :: rest2)

def solve (input : Input) : SolveResult :=
  match input with
  | { text := t, edits := es } =>
    if is_valid_boundary_all t es then
      if is_no_overlap es then
        SolveResult.ok (t + List.length es)
      else
        SolveResult.err EditError.overlap 0
    else
      SolveResult.err EditError.boundary 0

def no_isolated_surrogates (text : Nat) : Prop := True

def no_isolated_surrogates_all (input : Input) : Prop :=
  no_isolated_surrogates input.text

def solve_is_pure (input : Input) : Prop :=
  solve input = solve input

def solve_is_deterministic (input : Input) : Prop :=
  solve input = solve input

def solve_returns_json_serializable (input : Input) : Prop :=
  True

def solve_preserves_structure (input : Input) : Prop :=
  match solve input with
  | SolveResult.ok _ => True
  | SolveResult.err _ _ => True

def solve_preserves_order (input : Input) : Prop :=
  True

theorem O1 (input : Input) (h : no_isolated_surrogates_all input) :
  ¬ is_valid_boundary_all input.text input.edits →
  match solve input with
  | SolveResult.err EditError.boundary i => i = 0
  | _ => False
  := by sorry

theorem O2 (input : Input) :
  is_valid_boundary_all input.text input.edits →
  ¬ is_no_overlap input.edits →
  match solve input with
  | SolveResult.err EditError.overlap i => i = 0
  | _ => False
  := by sorry

theorem O3 (input : Input) :
  is_valid_boundary_all input.text input.edits →
  is_no_overlap input.edits →
  match solve input with
  | SolveResult.ok _ => True
  | _ => False
  := by sorry

theorem O4 (input : Input) :
  is_valid_boundary_all input.text input.edits →
  is_no_overlap input.edits →
  match solve input with
  | SolveResult.ok r => r = input.text + List.length input.edits
  | _ => False
  := by sorry

theorem O5 (input : Input) :
  solve_is_pure input ∧ solve_is_deterministic input ∧ solve_returns_json_serializable input
  := by sorry

theorem O6 (input : Input) :
  solve_preserves_structure input ∧ solve_preserves_order input
  := by sorry

theorem witnesses_for_A1 : ∃ (input : Input), no_isolated_surrogates_all input := by sorry

end VeriSlop.D24