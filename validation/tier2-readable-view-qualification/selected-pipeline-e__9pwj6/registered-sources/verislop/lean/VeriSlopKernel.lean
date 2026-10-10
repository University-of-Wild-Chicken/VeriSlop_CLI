import Lean

/-!
# VeriSlop trusted kernel tool (v0.1)

This program is part of the VeriSlop verifier trusted computing base. Its source hash is
recorded in every certificate and evidence record that depends on it.

It is run by the VeriSlop supervisor, never by candidate generators:

    lean --run VeriSlopKernel.lean <request.json> <response.json>

It imports an already-compiled candidate module **without executing candidate initializers**,
replays every constant of that module through the Lean kernel on top of an environment built
from the module's (toolchain-only) imports, and then works exclusively on the replayed kernel
environment. With `replay_modules`, the constants of every listed module (for example a frozen
semantic library, the accepted contract, a verifier-generated goal and a candidate proof) are
replayed together on top of the toolchain-only imports of that set; the supervisor checks that
every other module in the import closure resolves inside the pinned toolchain:

* `export`    — canonical JSON of every replayed constant (types, definition values, inductive
                shapes). Proof terms are not exported; only the constants they use.
* `axioms`    — transitive axiom dependencies computed by walking the replayed environment
                directly. The precomputed axiom data stored inside candidate `.olean` files is
                never consulted, because a tampered `.olean` could misreport it.
* `witnesses` — bounded kernel head-normalisation of non-vacuity proofs to read off concrete
                `Exists.intro` witnesses. A non-constructive proof yields no witness.
* `defeq`     — kernel type checking of a supplied closed `Prop` expression and a kernel
                definitional-equality check against a replayed theorem's type.

Everything it reports is data for the supervisor's registered checks; it assigns no lifecycle
outcome itself.
-/

open Lean

namespace VeriSlopKernel

def toolVersion : String := "0.4"

/-! ## Names, levels, binder infos -/

partial def nameToJson (n : Name) : Json :=
  let rec go : Name → List Json → List Json
    | .anonymous, acc => acc
    | .str p s, acc => go p (Json.str s :: acc)
    | .num p k, acc => go p ((Json.num (JsonNumber.fromNat k)) :: acc)
  Json.arr (go n []).toArray

def nameOfJson (j : Json) : Except String Name := do
  let comps ← j.getArr?
  let mut n := Name.anonymous
  for c in comps do
    match c with
    | .str s => n := Name.mkStr n s
    | .num k =>
      match k.mantissa.toNat?, k.exponent with
      | some m, 0 => n := Name.mkNum n m
      | _, _ => throw "invalid numeric name component"
    | _ => throw "invalid name component"
  return n

partial def levelToJson : Level → Except String Json
  | .zero => pure (Json.num 0)
  | .succ l => do
    -- compress closed numerals
    match (Level.succ l).toNat with
    | some k => pure (Json.num (JsonNumber.fromNat k))
    | none => return Json.mkObj [("succ", ← levelToJson l)]
  | .max a b => do return Json.mkObj [("max", Json.arr #[← levelToJson a, ← levelToJson b])]
  | .imax a b => do return Json.mkObj [("imax", Json.arr #[← levelToJson a, ← levelToJson b])]
  | .param n => pure (Json.mkObj [("param", nameToJson n)])
  | .mvar _ => throw "universe metavariable in exported expression"

partial def levelOfJson (j : Json) : Except String Level := do
  match j with
  | .num k =>
    match k.mantissa.toNat?, k.exponent with
    | some m, 0 => return Level.ofNat m
    | _, _ => throw "invalid level numeral"
  | .obj _ =>
    if let .ok l := j.getObjVal? "succ" then return Level.succ (← levelOfJson l)
    if let .ok a := j.getObjVal? "max" then
      let xs ← a.getArr?
      if xs.size != 2 then throw "max expects two levels"
      return Level.max (← levelOfJson xs[0]!) (← levelOfJson xs[1]!)
    if let .ok a := j.getObjVal? "imax" then
      let xs ← a.getArr?
      if xs.size != 2 then throw "imax expects two levels"
      return Level.imax (← levelOfJson xs[0]!) (← levelOfJson xs[1]!)
    if let .ok p := j.getObjVal? "param" then return Level.param (← nameOfJson p)
    throw "unknown level node"
  | _ => throw "invalid level"

def biToString : BinderInfo → String
  | .default => "default"
  | .implicit => "implicit"
  | .strictImplicit => "strict_implicit"
  | .instImplicit => "inst_implicit"

def biOfString : String → Except String BinderInfo
  | "default" => pure .default
  | "implicit" => pure .implicit
  | "strict_implicit" => pure .strictImplicit
  | "inst_implicit" => pure .instImplicit
  | s => throw s!"unknown binder info {s}"

/-! ## Expressions

Expressions are exported as trees with a node budget. `mdata` is stripped because it carries no
kernel meaning. Applications are flattened: `{"app": [f, a₁, …, aₙ]}`.
-/

abbrev ExportM := StateT Nat (Except String)

def tick : ExportM Unit := do
  let n ← get
  if n == 0 then throw "export node budget exhausted"
  set (n - 1)

partial def exprToJson (e : Expr) : ExportM Json := do
  tick
  match e with
  | .bvar i => return Json.mkObj [("bvar", Json.num (JsonNumber.fromNat i))]
  | .fvar _ => throw "free variable in exported expression"
  | .mvar _ => throw "metavariable in exported expression"
  | .sort u => return Json.mkObj [("sort", ← liftM (levelToJson u))]
  | .const n us =>
    let ls ← us.toArray.mapM fun u => liftM (levelToJson u)
    return Json.mkObj [("const", nameToJson n), ("levels", Json.arr ls)]
  | .app .. =>
    let fn := e.getAppFn
    let args := e.getAppArgs
    let mut out := #[← exprToJson fn]
    for a in args do
      out := out.push (← exprToJson a)
    return Json.mkObj [("app", Json.arr out)]
  | .lam n t b bi =>
    return Json.mkObj [("lam", Json.mkObj [("name", nameToJson n), ("bi", Json.str (biToString bi)),
      ("type", ← exprToJson t), ("body", ← exprToJson b)])]
  | .forallE n t b bi =>
    return Json.mkObj [("pi", Json.mkObj [("name", nameToJson n), ("bi", Json.str (biToString bi)),
      ("type", ← exprToJson t), ("body", ← exprToJson b)])]
  | .letE n t v b nondep =>
    return Json.mkObj [("let", Json.mkObj [("name", nameToJson n), ("type", ← exprToJson t),
      ("value", ← exprToJson v), ("body", ← exprToJson b), ("nondep", Json.bool nondep)])]
  | .lit (.natVal k) => return Json.mkObj [("lit", Json.mkObj [("nat", Json.str (toString k))])]
  | .lit (.strVal s) => return Json.mkObj [("lit", Json.mkObj [("str", Json.str s)])]
  | .mdata _ inner => exprToJson inner
  | .proj s i x =>
    return Json.mkObj [("proj", Json.mkObj [("struct", nameToJson s),
      ("idx", Json.num (JsonNumber.fromNat i)), ("expr", ← exprToJson x)])]
where
  liftM {α} (x : Except String α) : ExportM α := StateT.lift x

def getNatField (j : Json) (k : String) : Except String Nat := do
  (← j.getObjVal? k).getNat?

partial def exprOfJson (j : Json) : Except String Expr := do
  if let .ok i := j.getObjVal? "bvar" then return .bvar (← i.getNat?)
  if let .ok u := j.getObjVal? "sort" then return .sort (← levelOfJson u)
  if let .ok n := j.getObjVal? "const" then
    let ls ← (← j.getObjVal? "levels").getArr?
    return .const (← nameOfJson n) (← ls.toList.mapM levelOfJson)
  if let .ok a := j.getObjVal? "app" then
    let xs ← a.getArr?
    if xs.size < 2 then throw "app needs a function and at least one argument"
    let mut e ← exprOfJson xs[0]!
    for x in xs[1:] do
      e := .app e (← exprOfJson x)
    return e
  if let .ok b := j.getObjVal? "lam" then
    return .lam (← nameOfJson (← b.getObjVal? "name")) (← exprOfJson (← b.getObjVal? "type"))
      (← exprOfJson (← b.getObjVal? "body")) (← biOfString (← (← b.getObjVal? "bi").getStr?))
  if let .ok b := j.getObjVal? "pi" then
    return .forallE (← nameOfJson (← b.getObjVal? "name")) (← exprOfJson (← b.getObjVal? "type"))
      (← exprOfJson (← b.getObjVal? "body")) (← biOfString (← (← b.getObjVal? "bi").getStr?))
  if let .ok l := j.getObjVal? "lit" then
    if let .ok s := l.getObjVal? "nat" then
      let s ← s.getStr?
      match s.toNat? with
      | some k => return .lit (.natVal k)
      | none => throw "invalid nat literal"
    if let .ok s := l.getObjVal? "str" then return .lit (.strVal (← s.getStr?))
    throw "unknown literal"
  if let .ok p := j.getObjVal? "proj" then
    return .proj (← nameOfJson (← p.getObjVal? "struct")) (← getNatField p "idx")
      (← exprOfJson (← p.getObjVal? "expr"))
  throw "unsupported expression node (let/fvar/mvar are not accepted as input)"

/-! ## Axiom collection on the replayed environment -/

def usedConstsOf (ci : ConstantInfo) : Array Name :=
  match ci with
  | .axiomInfo v => v.type.getUsedConstants
  | .defnInfo v => v.type.getUsedConstants ++ v.value.getUsedConstants
  | .thmInfo v => v.type.getUsedConstants ++ v.value.getUsedConstants
  | .opaqueInfo v => v.type.getUsedConstants ++ v.value.getUsedConstants
  | .quotInfo v => v.type.getUsedConstants
  | .ctorInfo v => v.type.getUsedConstants.push v.induct
  | .recInfo v => v.type.getUsedConstants ++ (v.rules.toArray.flatMap fun r => r.rhs.getUsedConstants)
  | .inductInfo v => v.type.getUsedConstants ++ v.ctors.toArray

/-- Exact reachability walk: returns (axioms, unknown constants). Fresh visited set per root. -/
def axiomsOf (env : Kernel.Environment) (root : Name) : Array Name × Array Name := Id.run do
  let mut visited : NameSet := {}
  let mut stack : Array Name := #[root]
  let mut axs : NameSet := {}
  let mut unknown : NameSet := {}
  while h : stack.size > 0 do
    let c := stack[stack.size - 1]
    stack := stack.pop
    if visited.contains c then continue
    visited := visited.insert c
    match env.find? c with
    | none => unknown := unknown.insert c
    | some ci =>
      if ci matches .axiomInfo _ then axs := axs.insert c
      for d in usedConstsOf ci do
        if !visited.contains d then stack := stack.push d
  return (axs.toArray.qsort Name.lt, unknown.toArray.qsort Name.lt)

/-! ## Constant export -/

def kindOf : ConstantInfo → String
  | .axiomInfo _ => "axiom"
  | .defnInfo _ => "definition"
  | .thmInfo _ => "theorem"
  | .opaqueInfo _ => "opaque"
  | .quotInfo _ => "quot"
  | .inductInfo _ => "inductive"
  | .ctorInfo _ => "constructor"
  | .recInfo _ => "recursor"

def safetyOf : ConstantInfo → String
  | .defnInfo v => match v.safety with
    | .safe => "safe" | .unsafe => "unsafe" | .partial => "partial"
  | ci => if ci.isUnsafe then "unsafe" else "safe"

def namesJson (ns : Array Name) : Json := Json.arr (ns.map nameToJson)

/-- A recursive definition can have an executable `_unsafe_rec` companion that replay
deliberately omits. Recognise only an unsafe/partial companion whose parent was independently
replayed as a safe definition. The companion is never exported as a semantic declaration, and
its imported type/value are never used to justify a contract or proof. A matching name alone
does not establish that the companion is safe or that its implementation is correct. -/
def omittedRuntimeHelper (env : Kernel.Environment)
    (inventory : Std.HashMap Name ConstantInfo) (n : Name) : Option (Name × String) := do
  let parent ← Compiler.isUnsafeRecName? n
  let ci ← inventory[n]?
  let .defnInfo _ := ci | none
  if !ci.isUnsafe && !ci.isPartial then none else do
    match env.find? parent with
    | some (.defnInfo p) =>
      if p.safety == .safe then some (parent, safetyOf ci) else none
    | _ => none

def constToJson (env : Kernel.Environment) (ci : ConstantInfo) (wantAxioms : Bool) : ExportM Json := do
  let mut fields : List (String × Json) := [
    ("name", nameToJson ci.name),
    ("kind", Json.str (kindOf ci)),
    ("safety", Json.str (safetyOf ci)),
    ("level_params", namesJson ci.levelParams.toArray),
    ("type", ← exprToJson ci.type)]
  match ci with
  | .defnInfo v =>
    fields := fields ++ [("value", ← exprToJson v.value)]
  | .opaqueInfo v =>
    fields := fields ++ [("value", ← exprToJson v.value)]
  | .thmInfo v =>
    -- Proof terms are not exported; their constant dependencies are.
    let used := (v.value.getUsedConstants.qsort Name.lt)
    fields := fields ++ [("value_constants", namesJson used)]
  | .inductInfo v =>
    fields := fields ++ [("inductive", Json.mkObj [
      ("num_params", Json.num (JsonNumber.fromNat v.numParams)),
      ("num_indices", Json.num (JsonNumber.fromNat v.numIndices)),
      ("all", namesJson v.all.toArray),
      ("ctors", namesJson v.ctors.toArray),
      ("num_nested", Json.num (JsonNumber.fromNat v.numNested)),
      ("is_rec", Json.bool v.isRec),
      ("is_reflexive", Json.bool v.isReflexive)])]
  | .ctorInfo v =>
    fields := fields ++ [("constructor", Json.mkObj [
      ("induct", nameToJson v.induct),
      ("cidx", Json.num (JsonNumber.fromNat v.cidx)),
      ("num_params", Json.num (JsonNumber.fromNat v.numParams)),
      ("num_fields", Json.num (JsonNumber.fromNat v.numFields))])]
  | _ => pure ()
  if wantAxioms then
    let (axs, unknown) := axiomsOf env ci.name
    fields := fields ++ [("axioms", namesJson axs), ("unresolved_constants", namesJson unknown)]
  return Json.mkObj fields

/-! ## Witness extraction -/

def kwhnf (env : Kernel.Environment) (e : Expr) : Except String Expr :=
  match Kernel.whnf (Environment.ofKernelEnv env) {} e with
  | .ok r => .ok r
  | .error _ => .error "kernel whnf failed"

/-- Head-normalise, additionally unfolding theorem constants (bounded by `fuel`). -/
partial def headNormalize (env : Kernel.Environment) (e : Expr) (fuel : Nat) : Except String Expr := do
  if fuel == 0 then throw "witness normalisation fuel exhausted"
  let e ← kwhnf env e
  match e.getAppFn with
  | .const n us =>
    match env.find? n with
    | some (.thmInfo v) =>
      let body := v.value.instantiateLevelParams v.levelParams us
      headNormalize env (body.beta e.getAppArgs) (fuel - 1)
    | _ => return e
  | _ => return e

/-- Normalise a witness value to constructors and literals. -/
partial def normalizeValue (env : Kernel.Environment) (e : Expr) (fuel : Nat) : Except String Expr := do
  if fuel == 0 then throw "witness value fuel exhausted"
  let e ← kwhnf env e
  match e with
  | .lit _ => return e
  | _ =>
    match e.getAppFn with
    | .const n _ =>
      match env.find? n with
      | some (.ctorInfo cv) =>
        let args := e.getAppArgs
        let mut out := e.getAppFn
        for i in [0:args.size] do
          let a := args[i]!
          -- parameters are types; fields are values to normalise
          out := .app out (← if i < cv.numParams then pure a else normalizeValue env a (fuel - 1))
        return out
      | _ => throw s!"witness value is not a constructor or literal: head {n}"
    | _ => throw "witness value is not a constructor or literal"

partial def extractWitness (env : Kernel.Environment) (e : Expr) (fuel : Nat) : ExportM Json := do
  if fuel == 0 then throw "witness extraction fuel exhausted"
  let e ← StateT.lift (headNormalize env e fuel)
  let args := e.getAppArgs
  match e.getAppFn with
  | .const ``And.intro _ =>
    if args.size != 4 then throw "malformed And.intro"
    return Json.mkObj [("and", Json.arr #[← extractWitness env args[2]! (fuel - 1),
                                          ← extractWitness env args[3]! (fuel - 1)])]
  | .const ``Exists.intro _ =>
    if args.size != 4 then throw "malformed Exists.intro"
    let w ← StateT.lift (normalizeValue env args[2]! fuel)
    return Json.mkObj [("exists", Json.mkObj [("witness", ← exprToJson w),
                                               ("rest", ← extractWitness env args[3]! (fuel - 1))])]
  | _ => return Json.mkObj [("proof", Json.bool true)]

/-! ## Request handling -/

def errJson (msg : String) : Json := Json.mkObj [("ok", Json.bool false), ("error", Json.str msg)]

def runExport {α} (budget : Nat) (x : ExportM α) : Except String α :=
  (x.run budget).map (·.1)

def handle (req : Json) : IO Json := do
  let some dir := (req.getObjValD "search_dir").getStr?.toOption
    | return errJson "request.search_dir missing"
  let some modS := (req.getObjValD "module").getStr?.toOption
    | return errJson "request.module missing"
  let budget := ((req.getObjValD "node_budget").getNat?.toOption).getD 2000000
  let fuel := ((req.getObjValD "witness_fuel").getNat?.toOption).getD 256
  let mod := modS.toName
  -- Toolchain library first; the staged directory contains only the candidate module.
  let sysroot ← match (req.getObjValD "sysroot").getStr? with
    | .ok s => pure (System.FilePath.mk s)
    | .error _ => findSysroot
  initSearchPath sysroot
  searchPathRef.modify fun sp => sp ++ [System.FilePath.mk dir]
  -- Import without executing initializers (`enableInitializersExecution` is never called).
  -- `.private` loads the complete module-system data, including theorem bodies and hidden
  -- declarations. Public-only imports can replace theorems/definitions with axiom stubs and
  -- are never sufficient for acceptance. Missing .server/.private parts fail the import.
  let env ← try importModules #[{module := mod}] {} (loadExts := false) (level := .private)
    catch ex => return Json.mkObj [("import", errJson (toString ex))]
  let some idx := env.header.moduleNames.idxOf? mod
    | return Json.mkObj [("import", errJson "module not present after import")]
  let md := env.header.moduleData[idx]!
  let mut modules : Array Json := #[]
  for mi in [:env.header.moduleNames.size] do
    let m := env.header.moduleNames[mi]!
    let path ← try pure (toString (← findOLean m)) catch _ => pure ""
    modules := modules.push (Json.mkObj [("name", nameToJson m), ("olean", Json.str path),
      ("is_module_system", Json.bool env.header.moduleData[mi]!.isModule)])
  let importJson := Json.mkObj [("ok", Json.bool true),
    ("direct_imports", Json.arr (md.imports.map fun i => nameToJson i.module)),
    ("modules", Json.arr modules),
    ("is_module_system", Json.bool md.isModule), ("load_level", Json.str "private")]
  -- The replayed module set: the root module alone, or an explicit supervisor-chosen list.
  let multi := (req.getObjValD "replay_modules").getArr?.toOption.isSome
  let mut replayNames : Array Name := #[mod]
  if let .ok xs := (req.getObjValD "replay_modules").getArr? then
    replayNames := #[]
    for x in xs do
      let .ok s := x.getStr? | return Json.mkObj [("import", importJson), ("replay", errJson "replay_modules must be module names")]
      if replayNames.contains s.toName then
        return Json.mkObj [("import", importJson), ("replay", errJson "duplicate module in replay_modules")]
      replayNames := replayNames.push s.toName
    if !replayNames.contains mod then
      return Json.mkObj [("import", importJson), ("replay", errJson "replay_modules must contain the root module")]
  -- Replay every constant of the replayed modules through the kernel on top of their other imports only.
  let mut newConsts : Std.HashMap Name ConstantInfo := {}
  let mut skipped : Array Name := #[]
  let mut baseImports : Array Import := #[]
  let mut replayRows : Array Json := #[]
  for r in replayNames do
    let some ri := env.header.moduleNames.idxOf? r
      | return Json.mkObj [("import", importJson), ("replay", errJson s!"replayed module {r} is not in the import closure")]
    let rd := env.header.moduleData[ri]!
    if rd.constNames != rd.constants.map (·.name) then
      return Json.mkObj [("import", importJson), ("replay", errJson "inconsistent complete declaration inventory")]
    for c in rd.constants do
      if newConsts.contains c.name then
        return Json.mkObj [("import", importJson), ("replay", errJson "duplicate declaration in module inventory")]
      newConsts := newConsts.insert c.name c
      if c.isUnsafe || c.isPartial then skipped := skipped.push c.name
    for i in rd.imports do
      if !replayNames.contains i.module && !(baseImports.any (·.module == i.module)) then
        baseImports := baseImports.push i
    replayRows := replayRows.push (Json.mkObj [("name", nameToJson r),
      ("constants", Json.num (JsonNumber.fromNat rd.constants.size))])
  let base ← try importModules baseImports {} (loadExts := false) (level := .private)
    catch ex => return Json.mkObj [("import", importJson), ("replay", errJson s!"base import failed: {ex}")]
  let kenv ← try base.toKernelEnv.replay newConsts
    catch ex => return Json.mkObj [("import", importJson), ("replay", errJson (toString ex))]
  let mut replayFields : List (String × Json) := [("ok", Json.bool true),
    ("constants", Json.num (JsonNumber.fromNat newConsts.size)),
    ("not_replayed_unsafe_or_partial", namesJson skipped)]
  if multi then
    replayFields := replayFields ++ [("modules", Json.arr replayRows),
      ("base_imports", Json.arr (baseImports.map fun i => nameToJson i.module))]
  let replayJson := Json.mkObj replayFields
  let mut fields : List (String × Json) := [
    ("tool", Json.str "verislop-kernel"), ("tool_version", Json.str toolVersion),
    ("lean_version", Json.str Lean.versionString), ("lean_githash", Json.str Lean.githash),
    ("import", importJson), ("replay", replayJson)]
  -- Export replayed constants (read back from the replayed environment, not the .olean).
  if (req.getObjValD "export").getBool?.toOption.getD false then
    let wantAx := (req.getObjValD "axioms").getBool?.toOption.getD true
    let mut exportNames : Array Name := #[mod]
    if let .ok xs := (req.getObjValD "export_modules").getArr? then
      exportNames := #[]
      for x in xs do
        let .ok s := x.getStr? | return errJson "export_modules must be module names"
        if !replayNames.contains s.toName then return errJson "export_modules must be replayed modules"
        exportNames := exportNames.push s.toName
    else if multi then
      exportNames := replayNames
    let mut out : Array Json := #[]
    for em in exportNames do
      let some ei := env.header.moduleNames.idxOf? em | return errJson "export module missing"
      let names := (env.header.moduleData[ei]!.constNames.qsort Name.lt)
      for n in names do
        let tag : List (String × Json) := if multi then [("module", nameToJson em)] else []
        match kenv.find? n with
        | none =>
          match omittedRuntimeHelper kenv newConsts n with
          | some (parent, safety) =>
            out := out.push (Json.mkObj ([("name", nameToJson n),
              ("kind", Json.str "missing_after_replay"),
              ("replay_exclusion", Json.str "runtime_auxiliary"),
              ("omitted_kind", Json.str "definition"), ("safety", Json.str safety),
              ("replayed_parent", nameToJson parent)] ++ tag))
          | none =>
            out := out.push (Json.mkObj ([("name", nameToJson n), ("kind", Json.str "missing_after_replay")] ++ tag))
        | some ci =>
          match runExport budget (constToJson kenv ci wantAx) with
          | .ok j => out := out.push (if multi then j.setObjVal! "module" (nameToJson em) else j)
          | .error msg => out := out.push (Json.mkObj ([("name", nameToJson n), ("export_error", Json.str msg)] ++ tag))
    fields := fields ++ [("constants", Json.arr out)]
  -- Witnesses
  if let .ok ws := (req.getObjValD "witnesses").getArr? then
    let mut out : Array Json := #[]
    for w in ws do
      match nameOfJson w with
      | .error e => out := out.push (errJson e)
      | .ok n =>
        match kenv.find? n with
        | some (.thmInfo v) =>
          match runExport budget (extractWitness kenv v.value fuel) with
          | .ok j => out := out.push (Json.mkObj [("theorem", nameToJson n), ("ok", Json.bool true), ("shape", j)])
          | .error e => out := out.push (Json.mkObj [("theorem", nameToJson n), ("ok", Json.bool false), ("error", Json.str e)])
        | _ => out := out.push (Json.mkObj [("theorem", nameToJson n), ("ok", Json.bool false), ("error", Json.str "not a replayed theorem")])
    fields := fields ++ [("witnesses", Json.arr out)]
  -- Denotation checks
  if let .ok cs := (req.getObjValD "defeq").getArr? then
    let mut out : Array Json := #[]
    let mut i := 0
    for c in cs do
      i := i + 1
      let cid := (c.getObjValD "id")
      let res : Json := Id.run do
        let .ok tn := (c.getObjValD "theorem") |> nameOfJson | return errJson "bad theorem name"
        let some tci := kenv.find? tn | return errJson "theorem not found in replayed environment"
        if !tci.levelParams.isEmpty then return errJson "universe-polymorphic statements are not supported"
        let .ok e := exprOfJson (c.getObjValD "expr") | return errJson "malformed expression"
        let declName := Name.mkNum `_verislop_denotation_check i
        let decl := Declaration.defnDecl {
          name := declName, levelParams := [], type := .sort .zero, value := e,
          hints := .opaque, safety := .safe, all := [declName] }
        match kenv.addDeclCore 0 0 decl (cancelTk? := none) with
        | .error _ => return Json.mkObj [("ok", Json.bool true), ("typechecks", Json.bool false), ("defeq", Json.bool false)]
        | .ok kenv2 =>
          match Kernel.isDefEq (Environment.ofKernelEnv kenv2) {} e tci.type with
          | .ok b => return Json.mkObj [("ok", Json.bool true), ("typechecks", Json.bool true), ("defeq", Json.bool b)]
          | .error _ => return errJson "kernel isDefEq raised an exception"
      out := out.push (Json.mkObj [("id", cid), ("result", res)])
    fields := fields ++ [("defeq", Json.arr out)]
  return Json.mkObj fields

end VeriSlopKernel

def main (args : List String) : IO UInt32 := do
  let [reqPath, outPath] := args
    | IO.eprintln "usage: lean --run VeriSlopKernel.lean <request.json> <response.json>"; return 64
  let reqText ← IO.FS.readFile reqPath
  let req ← match Json.parse reqText with
    | .ok j => pure j
    | .error e => IO.eprintln s!"invalid request: {e}"; return 64
  let resp ← VeriSlopKernel.handle req
  IO.FS.writeFile outPath resp.compress
  return 0
