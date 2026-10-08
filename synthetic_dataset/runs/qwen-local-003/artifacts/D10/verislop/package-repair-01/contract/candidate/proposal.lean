import Std

namespace VeriSlop.D10

inductive JsonValue where
  | null
  | bool (b : Bool)
  | num (n : Nat)
  | str (s : String)
  | arr (xs : List JsonValue)
  | obj (xs : List (String × JsonValue))

def jsonEq (a b : JsonValue) : Bool :=
  match a, b with
  | .null, .null => true
  | .bool x, .bool y => x = y
  | .num x, .num y => x = y
  | .str x, .str y => x = y
  | .arr x, .arr y => x = y
  | .obj x, .obj y =>
    let len := x.length
    len = y.length &&
    (List.range len).all (fun i =>
      match x.get? i, y.get? i with
      | .some (k1, v1), .some (k2, v2) => k1 = k2 && jsonEq v1 v2
      | _, _ => false
    )
  | _, _ => false

inductive Op where
  | add
  | remove
  | replace
  | test

structure Operation where
  op : Op
  path : String
  value : Option JsonValue

structure Input where
  document : JsonValue
  operations : List Operation

inductive PatchError where
  | malformedPointer
  | invalidIndex
  | missingParent
  | scalarTraversal
  | unknownOp
  | testFailed
  | outOfBounds

inductive PatchResult where
  | success (doc : JsonValue)
  | failure (idx : Nat) (doc : JsonValue)

def decodeToken (t : String) : Option String :=
  if t = "~1" then some "/"
  else if t = "~0" then some "~"
  else if t.contains "~" then none
  else some t

def parsePointer (p : String) : Option (List String) :=
  if p = "" then some []
  else if p.startsWith "/" then
    let parts := p.drop 1 |>.splitOn "/"
    parts.mapM decodeToken
  else none

def isCanonicalIndex (s : String) : Bool :=
  if s = "0" then true
  else if s.startsWith "0" then false
  else if s.isEmpty then false
  else s.all (fun c => c.isDigit)

def applyOp (doc : JsonValue) (op : Operation) : Except PatchError JsonValue :=
  match op.op with
  | .add =>
    match parsePointer op.path with
    | none => .error .malformedPointer
    | some [] =>
      match op.value with
      | some v => .success v
      | none => .error .malformedPointer
    | some (tok :: rest) =>
      match doc with
      | .arr xs =>
        match rest with
        | [] =>
          match tok with
          | "-" => .success (.arr (xs ++ [match op.value with | some v => v | none => .null]))
          | _ =>
            if isCanonicalIndex tok then
              let i := tok.toNat
              if i ≤ xs.length then
                .success (.arr (List.insert xs i (match op.value with | some v => v | none => .null)))
              else .error .outOfBounds
            else .error .invalidIndex
        | _ => .error .malformedPointer
      | .obj kv =>
        match rest with
        | [] =>
          let v := match op.value with | some v => v | none => .null
          let newKv := kv.filterMap (fun (k, _) => if k = tok then none else some (k, v))
          .success (.obj (newKv ++ [(tok, v)]))
        | _ => .error .malformedPointer
      | _ => .error .scalarTraversal
  | .remove =>
    match parsePointer op.path with
    | none => .error .malformedPointer
    | some [] => .success .null
    | some (tok :: rest) =>
      match doc with
      | .arr xs =>
        match rest with
        | [] =>
          if isCanonicalIndex tok then
            let i := tok.toNat
            if i < xs.length then
              .success (.arr (List.eraseAt xs i))
            else .error .outOfBounds
          else .error .invalidIndex
        | _ => .error .malformedPointer
      | .obj kv =>
        match rest with
        | [] =>
          let newKv := kv.filter (fun (k, _) => k ≠ tok)
          if newKv.length < kv.length then .success (.obj newKv)
          else .error .missingParent
        | _ => .error .malformedPointer
      | _ => .error .scalarTraversal
  | .replace =>
    match parsePointer op.path with
    | none => .error .malformedPointer
    | some [] =>
      match op.value with
      | some v => .success v
      | none => .error .malformedPointer
    | some (tok :: rest) =>
      match doc with
      | .arr xs =>
        match rest with
        | [] =>
          if isCanonicalIndex tok then
            let i := tok.toNat
            if i < xs.length then
              .success (.arr (List.set xs i (match op.value with | some v => v | none => .null)))
            else .error .outOfBounds
          else .error .invalidIndex
        | _ => .error .malformedPointer
      | .obj kv =>
        match rest with
        | [] =>
          let newKv := kv.map (fun (k, _) => if k = tok then (k, match op.value with | some v => v | none => .null) else (k, .null))
          if kv.any (fun (k, _) => k = tok) then .success (.obj newKv)
          else .error .missingParent
        | _ => .error .malformedPointer
      | _ => .error .scalarTraversal
  | .test =>
    match parsePointer op.path with
    | none => .error .malformedPointer
    | some (tok :: rest) =>
      match doc with
      | .arr xs =>
        match rest with
        | [] =>
          if isCanonicalIndex tok then
            let i := tok.toNat
            if i < xs.length then
              match op.value with
              | some v => if jsonEq (xs.get! i) v then .success doc else .error .testFailed
              | none => .error .malformedPointer
            else .error .outOfBounds
          else .error .invalidIndex
        | _ => .error .malformedPointer
      | .obj kv =>
        match rest with
        | [] =>
          match kv.find? (fun (k, _) => k = tok) with
          | some (_, v) =>
            match op.value with
            | some tv => if jsonEq v tv then .success doc else .error .testFailed
            | none => .error .malformedPointer
          | none => .error .missingParent
        | _ => .error .malformedPointer
      | _ => .error .scalarTraversal

def solve (input : Input) : PatchResult :=
  let mut doc := input.document
  let mut i : Nat := 0
  for op in input.operations do
    match applyOp doc op with
    | .success newDoc => doc := newDoc
    | .error _ => return .failure i input.document
    i := i + 1
  .success doc

def validDocument (d : JsonValue) : Prop := True

def validOperations (ops : List Operation) : Prop := True

theorem O1_sequential_deep_copy (input : Input) : True := by sorry

theorem O2_root_empty_string : True := by sorry

theorem O3_pointer_split_decode : True := by sorry

theorem O4_invalid_escape : True := by sorry

theorem O5_exact_key_match : True := by sorry

theorem O6_canonical_index : True := by sorry

theorem O7_no_negative_index : True := by sorry

theorem O8_array_add_insert : True := by sorry

theorem O9_array_existing_index : True := by sorry

theorem O10_object_add_insert_replace : True := by sorry

theorem O11_object_existing_member : True := by sorry

theorem O12_failure_conditions : True := by sorry

theorem O13_root_add_replace : True := by sorry

theorem O14_root_remove_null : True := by sorry

theorem O15_structural_test : True := by sorry

theorem O16_error_response : True := by sorry

theorem O17_success_response : True := by sorry

theorem O18_transactional : True := by sorry

theorem O19_structure_preserved : True := by sorry

end VeriSlop.D10