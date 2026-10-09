import VSCore.Syntax

/-! Resolved, closed VSCore 0.2 AST. Arrays preserve declaration/evaluation order. -/
namespace VSCore2

inductive Ty where
  | nat | bool | unit
  | enum (id : String)
  | result (error ok : Ty)
  | record (id : String)
  | variant (id : String)
  | option (element : Ty)
  | list (element : Ty)
  deriving DecidableEq

instance : BEq Ty := ⟨fun a b => decide (a = b)⟩

inductive Value where
  | nat (n : Nat) | bool (b : Bool) | unit
  | enum (id ctor : String)
  | ok (value : Value) | error (value : Value)
  | record (id : String) (fields : List (String × Value))
  | variant (id ctor : String) (args : List Value)
  | none | some (value : Value)
  | nil | cons (head tail : Value)

abbrev BinOp := VSCore.BinOp
instance : BEq BinOp := ⟨fun a b => decide (a = b)⟩
instance : LawfulBEq BinOp where
  eq_of_beq := by intro a b h; exact of_decide_eq_true h
  rfl := by intro a; exact decide_eq_true rfl

inductive Expr where
  | var (index : Nat) | nat (n : Nat) | bool (b : Bool) | unit
  | enum (id ctor : String)
  | bin (op : BinOp) (left right : Expr)
  | not (value : Expr)
  | ite (cond thenBranch elseBranch : Expr)
  | letE (value body : Expr)
  | ok (errorTy : Ty) (value : Expr)
  | error (okTy : Ty) (value : Expr)
  | matchResult (scrutinee onOk onError : Expr)
  | record (id : String) (fields : List (String × Expr))
  | project (value : Expr) (field : String)
  | variant (id ctor : String) (args : List Expr)
  | matchVariant (scrutinee : Expr) (branches : List (String × Expr))
  | none (element : Ty) | some (value : Expr)
  | matchOption (scrutinee onNone onSome : Expr)
  | nil (element : Ty) | cons (head tail : Expr)
  | matchList (scrutinee onNil onCons : Expr)
  | call (helper : String) (args : List Expr)
  | listFold (source initial step : Expr)
  | natFold (source initial step : Expr)

inductive DataDecl where
  | record (id : String) (fields : List (String × Ty))
  | variant (id : String) (constructors : List (String × List Ty))
  deriving DecidableEq

instance : BEq DataDecl := ⟨fun a b => decide (a = b)⟩

def DataDecl.id : DataDecl → String
  | .record id _ | .variant id _ => id

structure Entry where
  id : String
  params : List Ty
  result : Ty
  body : Expr

structure Program where
  language : String
  profile : String
  declarations : List DataDecl
  helpers : List Entry
  entries : List Entry

abbrev Profile := VSCore.Profile

structure EntrySig where
  id : String
  params : List Ty
  result : Ty
  deriving DecidableEq

def languageId := "vscore/0.2"
def profileId := "pure-data/0.2"
def maxSourceBytes : Nat := 1048576
def maxDecodeDepth : Nat := 256

end VSCore2
