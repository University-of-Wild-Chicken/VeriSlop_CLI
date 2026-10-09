import VSCore2.Decode

/-! Intrinsic typed denotation used by the checker. Successful compilation returns
an ordinary total Lean function from a typed environment to a typed result.
Checker budgets limit elaboration only; they never limit successful execution. -/
namespace VSCore2

inductive Shape where
  | nat | bool | unit | empty
  | enum (id : String) (ctors : List String)
  | result (error ok : Shape)
  | option (element : Shape)
  | list (element : Shape)
  | product (left right : Shape)
  | sum (left right : Shape)
  | record (id : String) (fields : List String) (payload : Shape)
  | variant (id : String) (ctors : List String) (payload : Shape)
  deriving DecidableEq

@[reducible] def Denote : Shape → Type
  | .nat => Nat
  | .bool => Bool
  | .unit => Unit
  | .empty => Empty
  | .enum _ cs => { c : String // c ∈ cs }
  | .result e o => Sum (Denote e) (Denote o)
  | .option t => Option (Denote t)
  | .list t => List (Denote t)
  | .product a b => Denote a × Denote b
  | .sum a b => Sum (Denote a) (Denote b)
  | .record _ _ t => Denote t
  | .variant _ _ t => Denote t

/-- Decidable equality of the intrinsic type. Source equality compares values at
one checked type; nominal identity is already fixed by that type. Unlike a derived
nested raw Value BEq, these instances are total and kernel-reducible. -/
def denoteDecidableEq : (t : Shape) → DecidableEq (Denote t)
  | .nat => inferInstance
  | .bool => inferInstance
  | .unit => inferInstance
  | .empty => inferInstance
  | .enum _ _ => inferInstance
  | .result a b | .product a b | .sum a b => by
    letI := denoteDecidableEq a
    letI := denoteDecidableEq b
    exact inferInstance
  | .option a | .list a => by
    letI := denoteDecidableEq a
    exact inferInstance
  | .record _ _ t | .variant _ _ t => denoteDecidableEq t

@[reducible] def Env : List Shape → Type
  | [] => Unit
  | t :: ts => Denote t × Env ts

abbrev Compiled (Γ : List Shape) := (t : Shape) × (Env Γ → Denote t)

def productOf : List Shape → Shape
  | [] => .unit
  | t :: ts => .product t (productOf ts)

def sumOf : List Shape → Shape
  | [] => .empty
  | t :: ts => .sum t (sumOf ts)

def envToProduct : (ts : List Shape) → Env ts → Denote (productOf ts)
  | [], _ => ()
  | _ :: ts, (v, vs) => (v, envToProduct ts vs)

def productToEnv : (ts : List Shape) → Denote (productOf ts) → Env ts
  | [], _ => ()
  | _ :: ts, (v, vs) => (v, productToEnv ts vs)

def envAppend : (as bs : List Shape) → Env as → Env bs → Env (as ++ bs)
  | [], _, _, b => b
  | _ :: as, bs, (v, vs), b => (v, envAppend as bs vs b)

def envReverseAux : (as bs : List Shape) → Env as → Env bs → Env (as.reverse ++ bs)
  | [], _, _, b => b
  | a :: as, bs, (v, vs), b => by
    simpa only [List.reverse_cons, List.append_assoc, List.singleton_append] using
      envReverseAux as (a :: bs) vs (v, b)

def envReverse (ts : List Shape) (env : Env ts) : Env ts.reverse := by
  simpa using envReverseAux ts [] env ()

def castCompiled {Γ : List Shape} (target : Shape) (c : Compiled Γ) : Except String (Env Γ → Denote target) :=
  if h : c.1 = target then .ok (fun env => h ▸ c.2 env)
  else .error "expression type differs from expected type"

def lookupVar : (Γ : List Shape) → Nat → Except String (Compiled Γ)
  | [], _ => .error "unbound variable index"
  | t :: _, 0 => .ok ⟨t, fun env => env.1⟩
  | t :: ts, i + 1 => do
    let c ← lookupVar ts i
    return ⟨c.1, fun env => c.2 env.2⟩

abbrev DataContext := List (String × Shape)

def resolveTy : Nat → Profile → DataContext → Ty → Except String Shape
  | 0, _, _, _ => .error "type resolution exceeds checker budget"
  | _ + 1, _, _, .nat => .ok .nat
  | _ + 1, _, _, .bool => .ok .bool
  | _ + 1, _, _, .unit => .ok .unit
  | _ + 1, p, _, .enum id =>
    match (p.enums.find? (·.1 == id)).map (·.2) with
    | some cs => .ok (.enum id cs)
    | none => .error "unknown enumeration"
  | _ + 1, _, ds, .record id =>
    match ((ds.find? (fun d => d.1 == id)).map (fun d => d.2) : Option Shape) with
    | some (.record i ns t) => .ok (.record i ns t)
    | _ => .error "unknown or unresolved record"
  | _ + 1, _, ds, .variant id =>
    match ((ds.find? (fun d => d.1 == id)).map (fun d => d.2) : Option Shape) with
    | some (.variant i ns t) => .ok (.variant i ns t)
    | _ => .error "unknown or unresolved variant"
  | f + 1, p, ds, .result e o => do
    return .result (← resolveTy f p ds e) (← resolveTy f p ds o)
  | f + 1, p, ds, .option t => do return .option (← resolveTy f p ds t)
  | f + 1, p, ds, .list t => do return .list (← resolveTy f p ds t)

structure CompiledFunction where
  id : String
  params : List Shape
  result : Shape
  run : Env params → Denote result

abbrev HelperContext := List CompiledFunction

def compileBin {Γ : List Shape} (op : BinOp) (a b : Compiled Γ) : Except String (Compiled Γ) := do
  match op with
  | .eq =>
    let f ← castCompiled a.1 b
    -- Equality is structural on the typed source representation, defined below.
    throw "eq compiled in compileExpr after representation is available"
  | .add | .sub | .mul | .lt | .le =>
    let x ← castCompiled .nat a
    let y ← castCompiled .nat b
    match op with
    | .add => return ⟨.nat, fun env => x env + y env⟩
    | .sub => return ⟨.nat, fun env => x env - y env⟩
    | .mul => return ⟨.nat, fun env => x env * y env⟩
    | .lt => return ⟨.bool, fun env => decide (x env < y env)⟩
    | .le => return ⟨.bool, fun env => decide (x env ≤ y env)⟩
    | _ => throw "unreachable operator"
  | .and | .or =>
    let x ← castCompiled .bool a
    let y ← castCompiled .bool b
    match op with
    | .and => return ⟨.bool, fun env => x env && y env⟩
    | .or => return ⟨.bool, fun env => x env || y env⟩
    | _ => throw "unreachable operator"

mutual
-- Recursive products/sums are private typed packing structures; record/variant
-- wrappers reconstruct exactly the ordered source field/constructor identities.
def encode : (t : Shape) → Denote t → Value
  | .nat, n => .nat n
  | .bool, b => .bool b
  | .unit, _ => .unit
  | .empty, e => nomatch e
  | .enum id _, c => .enum id c.1
  | .result e _, .inl x => .error (encode e x)
  | .result _ o, .inr x => .ok (encode o x)
  | .option _, none => .none
  | .option t, some x => .some (encode t x)
  | .list t, xs => xs.foldr (fun x tail => .cons (encode t x) tail) .nil
  | .product a b, (x, y) => .record "_internal_product" [("head", encode a x), ("tail", encode b y)]
  | .sum a _, .inl x => .variant "_internal_sum" "left" [encode a x]
  | .sum _ b, .inr x => .variant "_internal_sum" "right" [encode b x]
  | .record id ns t, x => .record id (encodeFields ns t x)
  | .variant id ns t, x => encodeVariant id ns t x
termination_by t _ => sizeOf t

def encodeFields : (ns : List String) → (t : Shape) → Denote t → List (String × Value)
  | n :: ns, .product a b, (x, y) => (n, encode a x) :: encodeFields ns b y
  | _, _, _ => []
termination_by _ t _ => sizeOf t

def encodeVariant : String → (ns : List String) → (t : Shape) → Denote t → Value
  | id, c :: _, .sum a _, .inl x => .variant id c (encodeArgs a x)
  | id, _ :: cs, .sum _ b, .inr y => encodeVariant id cs b y
  | _, _, .empty, e => nomatch e
  | _, _, _, _ => .unit
termination_by _ _ t _ => sizeOf t

def encodeArgs : (t : Shape) → Denote t → List Value
  | .product a b, (x, y) => encode a x :: encodeArgs b y
  | _, _ => []
termination_by t _ => sizeOf t
end

end VSCore2
