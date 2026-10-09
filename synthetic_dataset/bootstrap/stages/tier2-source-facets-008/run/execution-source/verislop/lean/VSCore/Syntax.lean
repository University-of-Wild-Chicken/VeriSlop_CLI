/-!
# VSCore 0.1 — abstract syntax (verifier-owned semantic library)

`vscore/0.1` is the restricted implementation language of VeriSlop Tier 2 (endpoint
`restricted_source`). Programs are finite sets of typed entry points over mathematical natural
numbers, Booleans, unit, the accepted contract's finite enumerations and explicit results.
There is no recursion, loop, mutation, I/O, FFI, concurrency, exception (outside `result`),
reflection or call between entries in this version.

Variables are de Bruijn indices: index 0 is the innermost binder. An entry with parameters
`[p₀, …, pₙ₋₁]` evaluates its body in the environment `[pₙ₋₁, …, p₀]`, so the last parameter is
`var 0` (the same convention as the contract DSL).
-/

namespace VSCore

/-- Value types. Enumerations are named by the accepted contract's enumeration IDs. -/
inductive Ty where
  | nat
  | bool
  | unit
  | enum (id : String)
  | result (error ok : Ty)
  deriving DecidableEq

/-- Runtime values. `nat` is a mathematical natural number (no machine width). -/
inductive Value where
  | nat (n : Nat)
  | bool (b : Bool)
  | unit
  | enum (id ctor : String)
  | ok (v : Value)
  | error (v : Value)
  deriving DecidableEq

/-- Binary operators. `sub` is truncated natural subtraction; `and`/`or` are strict. -/
inductive BinOp where
  | add | sub | mul | lt | le | eq | and | or
  deriving DecidableEq

inductive Expr where
  | var (index : Nat)
  | nat (n : Nat)
  | bool (b : Bool)
  | unit
  | enum (id ctor : String)
  | bin (op : BinOp) (lhs rhs : Expr)
  | not (e : Expr)
  | ite (cond thenBranch elseBranch : Expr)
  /-- `letE value body` binds `value` as `var 0` in `body`. -/
  | letE (value body : Expr)
  | ok (errorTy : Ty) (value : Expr)
  | error (okTy : Ty) (value : Expr)
  /-- Exhaustive result match; each branch binds the payload as `var 0`. -/
  | matchResult (scrutinee onOk onError : Expr)
  deriving DecidableEq

structure Entry where
  id : String
  params : List Ty
  result : Ty
  body : Expr
  deriving DecidableEq

structure Program where
  language : String
  entries : List Entry
  deriving DecidableEq

/-- The accepted type registry adapter: enumeration IDs with their ordered constructors. -/
structure Profile where
  enums : List (String × List String)
  deriving DecidableEq

/-- The checked interface of one entry point. -/
structure EntrySig where
  id : String
  params : List Ty
  result : Ty
  deriving DecidableEq

def languageId : String := "vscore/0.1"

end VSCore
