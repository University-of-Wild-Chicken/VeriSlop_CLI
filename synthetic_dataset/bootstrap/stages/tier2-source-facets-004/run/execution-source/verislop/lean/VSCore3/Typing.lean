import VSCore3.Typed

namespace VSCore3

structure Packed (Γ : List Shape) where
  types : List Shape
  run : Env Γ → Env types

def packCompiled {Γ : List Shape} : List (Compiled Γ) → Packed Γ
  | [] => ⟨[], fun _ => ()⟩
  | c :: cs =>
    let tail := packCompiled cs
    ⟨c.1 :: tail.types, fun env => (c.2 env, tail.run env)⟩

def castPacked {Γ : List Shape} (target : List Shape) (c : Packed Γ) : Except String (Env Γ → Env target) :=
  if h : c.types = target then .ok (fun env => h ▸ c.run env)
  else .error "argument types or arity differ"

def productTypes : Shape → Option (List Shape)
  | .unit => some []
  | .product t ts => (productTypes ts).map (t :: ·)
  | _ => none

structure Projection (t : Shape) where
  result : Shape
  run : Denote t → Denote result

def findField : (names : List String) → (t : Shape) → String → Except String (Projection t)
  | n :: ns, .product a b, id =>
    if n == id then .ok ⟨a, fun x => x.1⟩
    else do
      let r ← findField ns b id
      return ⟨r.result, fun x => r.run x.2⟩
  | _, _, _ => .error "unknown record field"

structure Injection (t : Shape) where
  source : Shape
  run : Denote source → Denote t

def findCtor : (names : List String) → (t : Shape) → String → Except String (Injection t)
  | n :: ns, .sum a b, id =>
    if n == id then .ok ⟨a, Sum.inl⟩
    else do
      let r ← findCtor ns b id
      return ⟨r.source, fun x => .inr (r.run x)⟩
  | _, _, _ => .error "unknown variant constructor"

def tyBudget : Ty → Nat
  | .result a b => 1 + tyBudget a + tyBudget b
  | .option t | .list t => 1 + tyBudget t
  | _ => 1

theorem expr_snd_size_lt (p : String × Expr) : sizeOf p.2 < sizeOf p := by
  rcases p with ⟨name, expr⟩
  simp
  omega

def exprBudget : Expr → Nat
  | .bin _ a b | .letE a b | .cons a b | .intFdiv a b | .listGet a b |
    .listAppend a b | .listMap a b | .listFilter a b => 1 + exprBudget a + exprBudget b
  | .not e | .ok _ e | .error _ e | .project e _ | .some e | .intNeg e |
    .natToInt e | .intToNat e | .listLength e | .listRange e | .listReverse e |
    .listSort e | .listUnique e | .listSum e => 1 + exprBudget e
  | .ite a b c | .matchResult a b c | .matchOption a b c | .matchList a b c |
    .listFold a b c | .natFold a b c => 1 + exprBudget a + exprBudget b + exprBudget c
  | .record _ fs => 1 + (fs.map (fun f => exprBudget f.2)).sum
  | .variant _ _ args | .call _ args => 1 + (args.map exprBudget).sum
  | .matchVariant e bs => 1 + exprBudget e + (bs.map (fun b => 1 + exprBudget b.2)).sum
  | _ => 1
termination_by e => sizeOf e
decreasing_by
  all_goals simp_wf
  all_goals first
    | omega
    | (apply Nat.lt_trans (List.sizeOf_lt_of_mem (by assumption)); omega)
    | (apply Nat.lt_trans (expr_snd_size_lt _); apply Nat.lt_trans (List.sizeOf_lt_of_mem (by assumption)); omega)

mutual

def compileExpr : Nat → Profile → DataContext → HelperContext → (Γ : List Shape) → Expr → Except String (Compiled Γ)
  | 0, _, _, _, _, _ => .error "expression elaboration exceeds checker budget"
  | f + 1, p, ds, hs, Γ, e => do
    match e with
    | .var i => lookupVar Γ i
    | .nat n => return ⟨.nat, fun _ => n⟩
    | .int n => return ⟨.int, fun _ => n⟩
    | .string cs =>
      if !cs.all validScalar then throw "invalid Unicode scalar value"
      return ⟨.string, fun _ => String.ofList (cs.map Char.ofNat)⟩
    | .bool b => return ⟨.bool, fun _ => b⟩
    | .unit => return ⟨.unit, fun _ => ()⟩
    | .enum id ctor =>
      let .enum i cs ← resolveTy (tyBudget (Ty.enum id) + 1) p ds (.enum id) | throw "enum resolution failed"
      if h : ctor ∈ cs then return ⟨.enum i cs, fun _ => ⟨ctor, h⟩⟩
      else throw "unknown enumeration constructor"
    | .bin op a b =>
      let a ← compileExpr f p ds hs Γ a
      let b ← compileExpr f p ds hs Γ b
      match op with
      | .eq =>
        let b ← castCompiled a.1 b
        letI := denoteDecidableEq a.1
        return ⟨.bool, fun env => decide (a.2 env = b env)⟩
      | _ => compileBin op a b
    | .not a =>
      let a ← castCompiled .bool (← compileExpr f p ds hs Γ a)
      return ⟨.bool, fun env => !a env⟩
    | .ite c t e =>
      let c ← castCompiled .bool (← compileExpr f p ds hs Γ c)
      let t ← compileExpr f p ds hs Γ t
      let e ← castCompiled t.1 (← compileExpr f p ds hs Γ e)
      return ⟨t.1, fun env => if c env then t.2 env else e env⟩
    | .letE a b =>
      let a ← compileExpr f p ds hs Γ a
      let b ← compileExpr f p ds hs (a.1 :: Γ) b
      return ⟨b.1, fun env => b.2 (a.2 env, env)⟩
    | .ok ty a =>
      let ty ← resolveTy (tyBudget ty + 1) p ds ty
      let a ← compileExpr f p ds hs Γ a
      return ⟨.result ty a.1, fun env => .inr (a.2 env)⟩
    | .error ty a =>
      let ty ← resolveTy (tyBudget ty + 1) p ds ty
      let a ← compileExpr f p ds hs Γ a
      return ⟨.result a.1 ty, fun env => .inl (a.2 env)⟩
    | .matchResult s o e =>
      let s ← compileExpr f p ds hs Γ s
      match s with
      | ⟨.result te to, run⟩ =>
        let o ← compileExpr f p ds hs (to :: Γ) o
        let e ← castCompiled o.1 (← compileExpr f p ds hs (te :: Γ) e)
        return ⟨o.1, fun env => match run env with
          | .inl x => e (x, env)
          | .inr x => o.2 (x, env)⟩
      | _ => throw "match_result expects Result"
    | .record id fs =>
      let .record i names shape ← resolveTy (tyBudget (Ty.record id) + 1) p ds (.record id) | throw "record resolution failed"
      if fs.map Prod.fst != names then throw "record fields must match declaration order exactly"
      let cs ← fs.mapM (fun x => compileExpr f p ds hs Γ x.2)
      let packed := packCompiled cs
      let run ← castCompiled shape ⟨productOf packed.types, fun env => envToProduct packed.types (packed.run env)⟩
      return ⟨.record i names shape, run⟩
    | .project e id =>
      let e ← compileExpr f p ds hs Γ e
      match e with
      | ⟨.record _ names shape, run⟩ =>
        let field ← findField names shape id
        return ⟨field.result, fun env => field.run (run env)⟩
      | _ => throw "projection expects Record"
    | .variant id ctor args =>
      let .variant i names shape ← resolveTy (tyBudget (Ty.variant id) + 1) p ds (.variant id) | throw "variant resolution failed"
      let ctor ← findCtor names shape ctor
      let packed := packCompiled (← args.mapM (compileExpr f p ds hs Γ))
      let run ← castCompiled ctor.source ⟨productOf packed.types, fun env => envToProduct packed.types (packed.run env)⟩
      return ⟨.variant i names shape, fun env => ctor.run (run env)⟩
    | .matchVariant s branches =>
      let s ← compileExpr f p ds hs Γ s
      match s with
      | ⟨.variant _ names shape, run⟩ =>
        if branches.map Prod.fst != names then throw "variant match must cover constructors in declaration order"
        let .sum first _ := shape | throw "variant has no constructors"
        let some params := productTypes first | throw "invalid variant payload shape"
        let some branch := branches.head? | throw "variant match has no branches"
        let firstResult ← compileExpr f p ds hs (params.reverse ++ Γ) branch.2
        let select ← compileBranches f p ds hs Γ names shape branches firstResult.1
        return ⟨firstResult.1, fun env => select (run env) env⟩
      | _ => throw "match_variant expects Variant"
    | .none ty =>
      let t ← resolveTy (tyBudget ty + 1) p ds ty
      return ⟨.option t, fun _ => none⟩
    | .some e =>
      let e ← compileExpr f p ds hs Γ e
      return ⟨.option e.1, fun env => some (e.2 env)⟩
    | .matchOption s n v =>
      let s ← compileExpr f p ds hs Γ s
      match s with
      | ⟨.option t, run⟩ =>
        let n ← compileExpr f p ds hs Γ n
        let v ← castCompiled n.1 (← compileExpr f p ds hs (t :: Γ) v)
        return ⟨n.1, fun env => match run env with
          | none => n.2 env
          | some x => v (x, env)⟩
      | _ => throw "match_option expects Option"
    | .nil ty =>
      let t ← resolveTy (tyBudget ty + 1) p ds ty
      return ⟨.list t, fun _ => []⟩
    | .cons h t =>
      let h ← compileExpr f p ds hs Γ h
      let t ← castCompiled (.list h.1) (← compileExpr f p ds hs Γ t)
      return ⟨.list h.1, fun env => h.2 env :: t env⟩
    | .matchList s n c =>
      let s ← compileExpr f p ds hs Γ s
      match s with
      | ⟨.list t, run⟩ =>
        let n ← compileExpr f p ds hs Γ n
        let c ← castCompiled n.1 (← compileExpr f p ds hs (.list t :: t :: Γ) c)
        return ⟨n.1, fun env => match run env with
          | [] => n.2 env
          | x :: xs => c (xs, (x, env))⟩
      | _ => throw "match_list expects List"
    | .call id args =>
      let some helper := hs.find? (fun h => h.id == id) | throw "unknown or unresolved helper"
      let packed := packCompiled (← args.mapM (compileExpr f p ds hs Γ))
      let args ← castPacked helper.params packed
      return ⟨helper.result, fun env => helper.run (args env)⟩
    | .listFold s initial step =>
      let s ← compileExpr f p ds hs Γ s
      match s with
      | ⟨.list t, run⟩ =>
        let initial ← compileExpr f p ds hs Γ initial
        let step ← castCompiled initial.1 (← compileExpr f p ds hs (t :: initial.1 :: Γ) step)
        return ⟨initial.1, fun env => (run env).foldl (fun acc item => step (item, (acc, env))) (initial.2 env)⟩
      | _ => throw "list_fold expects List"
    | .natFold s initial step =>
      let s ← castCompiled .nat (← compileExpr f p ds hs Γ s)
      let initial ← compileExpr f p ds hs Γ initial
      let step ← castCompiled initial.1 (← compileExpr f p ds hs (initial.1 :: .nat :: Γ) step)
        return ⟨initial.1, fun env => Nat.rec (initial.2 env) (fun index acc => step (acc, (index, env))) (s env)⟩
    | .intNeg e =>
      let x ← castCompiled .int (← compileExpr f p ds hs Γ e)
      return ⟨.int, fun env => -(x env)⟩
    | .intFdiv a b =>
      let x ← castCompiled .int (← compileExpr f p ds hs Γ a)
      let y ← castCompiled .int (← compileExpr f p ds hs Γ b)
      return ⟨.int, fun env => Int.fdiv (x env) (y env)⟩
    | .natToInt e =>
      let x ← castCompiled .nat (← compileExpr f p ds hs Γ e)
      return ⟨.int, fun env => Int.ofNat (x env)⟩
    | .intToNat e =>
      let x ← castCompiled .int (← compileExpr f p ds hs Γ e)
      return ⟨.nat, fun env => Int.toNat (x env)⟩
    | .listRange e =>
      let x ← castCompiled .nat (← compileExpr f p ds hs Γ e)
      return ⟨.list .nat, fun env => List.range (x env)⟩
    | .listLength e =>
      let ⟨.list _, x⟩ ← compileExpr f p ds hs Γ e | throw "list_length expects List"
      return ⟨.nat, fun env => (x env).length⟩
    | .listGet e index =>
      let ⟨.list t, x⟩ ← compileExpr f p ds hs Γ e | throw "list_get expects List"
      let i ← castCompiled .nat (← compileExpr f p ds hs Γ index)
      return ⟨.option t, fun env => List.get?Internal (x env) (i env)⟩
    | .listAppend a b =>
      let ⟨.list t, x⟩ ← compileExpr f p ds hs Γ a | throw "list_append expects List"
      let y ← castCompiled (.list t) (← compileExpr f p ds hs Γ b)
      return ⟨.list t, fun env => x env ++ y env⟩
    | .listReverse e =>
      let ⟨.list t, x⟩ ← compileExpr f p ds hs Γ e | throw "list_reverse expects List"
      return ⟨.list t, fun env => (x env).reverse⟩
    | .listSort e =>
      let x ← compileExpr f p ds hs Γ e
      match x with
      | ⟨.list .nat, run⟩ => return ⟨.list .nat, fun env => (run env).mergeSort (fun a b => decide (a ≤ b))⟩
      | ⟨.list .int, run⟩ => return ⟨.list .int, fun env => (run env).mergeSort (fun a b => decide (a ≤ b))⟩
      | ⟨.list .string, run⟩ => return ⟨.list .string, fun env => (run env).mergeSort (fun a b => decide (a ≤ b))⟩
      | _ => throw "list_sort expects Nat, Int or String elements"
    | .listUnique e =>
      let x ← compileExpr f p ds hs Γ e
      match x with
      | ⟨.list .nat, run⟩ => return ⟨.list .nat, fun env => (run env).eraseDups⟩
      | ⟨.list .int, run⟩ => return ⟨.list .int, fun env => (run env).eraseDups⟩
      | ⟨.list .string, run⟩ => return ⟨.list .string, fun env => (run env).eraseDups⟩
      | ⟨.list .bool, run⟩ => return ⟨.list .bool, fun env => (run env).eraseDups⟩
      | _ => throw "list_unique expects primitive scalar elements"
    | .listMap e body =>
      let ⟨.list t, run⟩ ← compileExpr f p ds hs Γ e | throw "list_map expects List"
      let mapped ← compileExpr f p ds hs (t :: Γ) body
      return ⟨.list mapped.1, fun env => List.map (fun x => mapped.2 (x, env)) (run env)⟩
    | .listFilter e body =>
      let ⟨.list t, run⟩ ← compileExpr f p ds hs Γ e | throw "list_filter expects List"
      let predicate ← castCompiled .bool (← compileExpr f p ds hs (t :: Γ) body)
      return ⟨.list t, fun env => List.filter (fun x => predicate (x, env)) (run env)⟩
    | .listSum e =>
      let x ← compileExpr f p ds hs Γ e
      match x with
      | ⟨.list .nat, run⟩ => return ⟨.nat, fun env => List.sum (run env)⟩
      | ⟨.list .int, run⟩ => return ⟨.int, fun env => List.sum (run env)⟩
      | _ => throw "list_sum expects Nat or Int elements"

def compileBranches : Nat → Profile → DataContext → HelperContext → (Γ : List Shape) →
    (names : List String) → (s : Shape) → List (String × Expr) → (result : Shape) →
    Except String (Denote s → Env Γ → Denote result)
  | 0, _, _, _, _, _, _, _, _ => .error "variant branches exceed checker budget"
  | _ + 1, _, _, _, _, [], .empty, [], _ => .ok (fun x _ => nomatch x)
  | f + 1, p, ds, hs, Γ, name :: names, .sum a b, (id, body) :: branches, result => do
    if id != name then throw "variant branch order differs"
    let some params := productTypes a | throw "invalid variant payload shape"
    if h : productOf params = a then
      let first ← castCompiled result (← compileExpr f p ds hs (params.reverse ++ Γ) body)
      let rest ← compileBranches f p ds hs Γ names b branches result
      return fun val env => match val with
        | .inl x => first (envAppend params.reverse Γ (envReverse params (productToEnv params (h.symm ▸ x))) env)
        | .inr x => rest x env
    else throw "variant payload shape differs"
  | _ + 1, _, _, _, _, _, _, _, _ => .error "variant match shape differs"
end



def validNames (names : List String) : Bool := names.all VSCore.validIdent && decide names.Nodup

def resolveDecl (p : Profile) (ds : DataContext) : DataDecl → Except String (String × Shape)
  | .record id fields => do
    if !validNames (fields.map Prod.fst) then throw "duplicate or invalid record field identifiers"
    let types ← fields.mapM (fun f => resolveTy (tyBudget f.2 + 1) p ds f.2)
    return (id, .record id (fields.map Prod.fst) (productOf types))
  | .variant id ctors => do
    if ctors.isEmpty || !validNames (ctors.map Prod.fst) then throw "variant needs distinct valid constructors"
    let types ← ctors.mapM (fun c => do return productOf (← c.2.mapM (fun t => resolveTy (tyBudget t + 1) p ds t)))
    return (id, .variant id (ctors.map Prod.fst) (sumOf types))

def resolveDeclPass (p : Profile) : List DataDecl → DataContext → List DataDecl × DataContext
  | [], ds => ([], ds)
  | d :: rest, ds =>
    match resolveDecl p ds d with
    | .ok result => resolveDeclPass p rest (ds ++ [result])
    | .error _ =>
      let (pending, resolved) := resolveDeclPass p rest ds
      (d :: pending, resolved)

def resolveDeclarations : Nat → Profile → List DataDecl → DataContext → Except String DataContext
  | 0, _, _, _ => .error "nominal dependency resolution exceeds checker budget"
  | _ + 1, _, [], ds => .ok ds
  | fuel + 1, p, pending, ds =>
    let (remaining, next) := resolveDeclPass p pending ds
    if remaining.length < pending.length then resolveDeclarations fuel p remaining next
    else .error "nominal dependency cycle, unknown type, or invalid declaration"

def compileFunction (p : Profile) (ds : DataContext) (hs : HelperContext) (e : Entry) : Except String CompiledFunction := do
  if !VSCore.validIdent e.id then throw "invalid function identifier"
  let params ← e.params.mapM (fun t => resolveTy (tyBudget t + 1) p ds t)
  let result ← resolveTy (tyBudget e.result + 1) p ds e.result
  let body ← castCompiled result (← compileExpr (exprBudget e.body + 1) p ds hs params.reverse e.body)
  return ⟨e.id, params, result, fun args => body (envReverse params args)⟩

def compileHelperPass (p : Profile) (ds : DataContext) : List Entry → HelperContext → List Entry × HelperContext
  | [], hs => ([], hs)
  | e :: rest, hs =>
    match compileFunction p ds hs e with
    | .ok result => compileHelperPass p ds rest (hs ++ [result])
    | .error _ =>
      let (pending, compiled) := compileHelperPass p ds rest hs
      (e :: pending, compiled)

def compileHelpers : Nat → Profile → DataContext → List Entry → HelperContext → Except String HelperContext
  | 0, _, _, _, _ => .error "helper dependency resolution exceeds checker budget"
  | _ + 1, _, _, [], hs => .ok hs
  | fuel + 1, p, ds, pending, hs =>
    let (remaining, next) := compileHelperPass p ds pending hs
    if remaining.length < pending.length then compileHelpers fuel p ds remaining next
    else .error "helper dependency cycle, unknown helper, or ill-typed helper"

structure CheckedProgram where
  declarations : DataContext
  helpers : HelperContext
  entries : List CompiledFunction
  signatures : List EntrySig

def compileProgram (p : Profile) (prog : Program) : Except String CheckedProgram := do
  if prog.language != languageId then throw "unsupported language version"
  if prog.profile != profileId then throw "unsupported semantic profile"
  if prog.entries.isEmpty then throw "a program needs at least one entry"
  if !validNames (p.enums.map Prod.fst) ||
      !p.enums.all (fun e => !e.2.isEmpty && validNames e.2) then throw "invalid accepted enumeration registry"
  if !validNames ((p.enums.map Prod.fst) ++ prog.declarations.map DataDecl.id) then
    throw "duplicate or invalid nominal type IDs"
  if !validNames ((prog.helpers ++ prog.entries).map Entry.id) then
    throw "duplicate or invalid function IDs"
  let declarations ← resolveDeclarations (prog.declarations.length + 1) p prog.declarations []
  let helpers ← compileHelpers (prog.helpers.length + 1) p declarations prog.helpers []
  let entries ← prog.entries.mapM (compileFunction p declarations helpers)
  let signatures := prog.entries.map (fun e => ({ id := e.id, params := e.params, result := e.result } : EntrySig))
  return ⟨declarations, helpers, entries, signatures⟩

def checkProgram (p : Profile) (prog : Program) : Except String (List EntrySig) :=
  match compileProgram p prog with
  | .error message => .error message
  | .ok cp => .ok cp.signatures

def checkCheck (p : Profile) (prog : Program) (expected : List EntrySig) : Bool :=
  match checkProgram p prog with
  | .ok sigs => decide (sigs = expected)
  | .error _ => false

theorem checkProgram_of_check {p : Profile} {prog : Program} {expected : List EntrySig}
    (h : checkCheck p prog expected = true) : checkProgram p prog = .ok expected := by
  unfold checkCheck at h
  split at h
  · rename_i sigs hs
    rw [hs]
    simp only [decide_eq_true_eq] at h
    rw [h]
  · contradiction

def featuresTy : Ty → List String
  | .nat | .bool | .unit | .enum _ => ["base"]
  | .int => ["int"]
  | .string => ["string"]
  | .result e o => "base" :: (featuresTy e ++ featuresTy o)
  | .record _ | .variant _ => ["nominalData"]
  | .option t => "option" :: featuresTy t
  | .list t => "list" :: featuresTy t

theorem snd_size_lt (p : String × Expr) : sizeOf p.2 < sizeOf p := by
  rcases p with ⟨name, expr⟩
  simp
  omega

def featuresExpr : Expr → List String
  | .var _ | .nat _ | .bool _ | .unit | .enum _ _ => ["base"]
  | .int _ => ["int"]
  | .string _ => ["string"]
  | .intNeg e | .natToInt e | .intToNat e => "int" :: featuresExpr e
  | .intFdiv a b => "int" :: (featuresExpr a ++ featuresExpr b)
  | .listLength e | .listRange e | .listReverse e | .listSort e | .listUnique e | .listSum e =>
    "pureList" :: "list" :: featuresExpr e
  | .listGet a b => "pureList" :: "list" :: "option" :: (featuresExpr a ++ featuresExpr b)
  | .listAppend a b => "pureList" :: "list" :: (featuresExpr a ++ featuresExpr b)
  | .listMap a b | .listFilter a b => "pureList" :: "list" :: (featuresExpr a ++ featuresExpr b)
  | .bin _ a b | .letE a b => "base" :: (featuresExpr a ++ featuresExpr b)
  | .not e => "base" :: featuresExpr e
  | .ite a b c | .matchResult a b c => "base" :: (featuresExpr a ++ featuresExpr b ++ featuresExpr c)
  | .ok t e | .error t e => "base" :: (featuresTy t ++ featuresExpr e)
  | .record _ fields => "nominalData" :: fields.flatMap (fun f => featuresExpr f.2)
  | .project e _ => "nominalData" :: featuresExpr e
  | .variant _ _ args => "nominalData" :: args.flatMap featuresExpr
  | .matchVariant e branches => "nominalData" :: (featuresExpr e ++ branches.flatMap (fun b => featuresExpr b.2))
  | .none t => "option" :: featuresTy t
  | .some e => "option" :: featuresExpr e
  | .matchOption a b c => "option" :: (featuresExpr a ++ featuresExpr b ++ featuresExpr c)
  | .nil t => "list" :: featuresTy t
  | .cons a b => "list" :: (featuresExpr a ++ featuresExpr b)
  | .matchList a b c => "list" :: (featuresExpr a ++ featuresExpr b ++ featuresExpr c)
  | .call _ args => "acyclicCalls" :: args.flatMap featuresExpr
  | .listFold a b c => "listFold" :: (featuresExpr a ++ featuresExpr b ++ featuresExpr c)
  | .natFold a b c => "natFold" :: (featuresExpr a ++ featuresExpr b ++ featuresExpr c)
termination_by e => sizeOf e
decreasing_by
  all_goals simp_wf
  all_goals first
    | omega
    | (apply Nat.lt_trans (List.sizeOf_lt_of_mem (by assumption)); omega)
    | (apply Nat.lt_trans (snd_size_lt _); apply Nat.lt_trans (List.sizeOf_lt_of_mem (by assumption)); omega)

def featuresDecl : DataDecl → List String
  | .record _ fs => "nominalData" :: fs.flatMap (fun f => featuresTy f.2)
  | .variant _ cs => "nominalData" :: cs.flatMap (fun c => c.2.flatMap featuresTy)

def allowedFeatures : List String := ["base", "nominalData", "option", "list", "acyclicCalls", "listFold", "natFold", "int", "string", "pureList"]

def requiredFeatures (prog : Program) : List String :=
  let all := prog.declarations.flatMap featuresDecl ++
    (prog.helpers ++ prog.entries).flatMap (fun e => e.params.flatMap featuresTy ++ featuresTy e.result ++ featuresExpr e.body)
  allowedFeatures.filter (fun f => all.contains f)

end VSCore3
