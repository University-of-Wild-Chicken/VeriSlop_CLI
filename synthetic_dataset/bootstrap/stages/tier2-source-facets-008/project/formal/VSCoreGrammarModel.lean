import Std

/-!
# VSCore 0.2 grammar: feature admission design model

This standalone syntax sketch is a design artifact. It enables no CLI parser, evaluator,
bridge, profile or backend. The production language remains `vscore/0.1`.

Feature requirements are computed from syntax, including declarations and function
signatures. An untrusted agent's claimed feature inventory is not an input to admission.
Repeated requirements are harmless: admission uses membership, not occurrence counts.

The theorems establish only finite feature admission, its monotonicity, and rejection of
missing features. They do not establish parsing, name resolution, well-formed nominal
declarations, acyclicity of calls, typing, termination, evaluation or bridge soundness.
In particular, the name `acyclicCalls` identifies a capability; a separate checked call
graph judgment must establish that a program using it actually has no recursive calls.

Locals and record fields use resolved indices. Variant branches are in the resolved
constructor order. Scope, index bounds, branch counts and exhaustiveness are additional
well-formedness checks, not consequences of this feature traversal.
Enum names refer to an accepted registry; source type declarations contain only records
and variants. Variant constructors have ordered payload lists, including the empty list.
-/

namespace VSCoreGrammarModel

inductive Feature where
  | base
  | nominalData
  | option
  | list
  | acyclicCalls
  | listFold
  | natFold
  deriving DecidableEq, Repr

inductive Ty where
  | nat | bool | unit
  | enum (id : String)
  | result (error ok : Ty)
  | record (id : String)
  | variant (id : String)
  | option (element : Ty)
  | list (element : Ty)
  deriving DecidableEq, Repr

def Ty.features : Ty → List Feature
  | .nat | .bool | .unit | .enum _ => [.base]
  | .result error ok => .base :: (error.features ++ ok.features)
  | .record _ | .variant _ => [.base, .nominalData]
  | .option element => .option :: element.features
  | .list element => .list :: element.features

structure Field where
  id : String
  ty : Ty
  deriving DecidableEq, Repr

structure Constructor where
  id : String
  payload : List Ty
  deriving DecidableEq, Repr

inductive TypeDecl where
  | record (id : String) (fields : List Field)
  | variant (id : String) (constructors : List Constructor)
  deriving DecidableEq, Repr

def TypeDecl.features : TypeDecl → List Feature
  | .record _ fields => [.base, .nominalData] ++ fields.flatMap (·.ty.features)
  | .variant _ constructors =>
      [.base, .nominalData] ++ constructors.flatMap (fun c => c.payload.flatMap Ty.features)

inductive BinOp where
  | add | sub | mul | lt | le | eq | and | or
  deriving DecidableEq, Repr

inductive Expr where
  | var (index : Nat)
  | nat (value : Nat)
  | bool (value : Bool)
  | unit
  | enum (id constructor : String)
  | bin (op : BinOp) (left right : Expr)
  | not (value : Expr)
  | ite (condition thenBranch elseBranch : Expr)
  | letE (value body : Expr)
  | ok (errorTy : Ty) (value : Expr)
  | error (okTy : Ty) (value : Expr)
  | matchResult (value onOk onError : Expr)
  | record (id : String) (fields : List Expr)
  | project (value : Expr) (fieldIndex : Nat)
  | variant (id constructor : String) (payload : List Expr)
  | matchVariant (value : Expr) (branches : List Expr)
  | none (element : Ty)
  | some (value : Expr)
  | matchOption (value onNone onSome : Expr)
  | nil (element : Ty)
  | cons (head tail : Expr)
  | matchList (value onNil onCons : Expr)
  | foldList (items initial step : Expr)
  | foldNat (count initial step : Expr)
  | call (id : String) (arguments : List Expr)
  deriving Repr

def Expr.features : Expr → List Feature
  | .var _ | .nat _ | .bool _ | .unit | .enum _ _ => [.base]
  | .bin _ left right => .base :: (left.features ++ right.features)
  | .not value => .base :: value.features
  | .ite condition thenBranch elseBranch =>
      .base :: (condition.features ++ thenBranch.features ++ elseBranch.features)
  | .letE value body => .base :: (value.features ++ body.features)
  | .ok errorTy value => .base :: (errorTy.features ++ value.features)
  | .error okTy value => .base :: (okTy.features ++ value.features)
  | .matchResult value onOk onError =>
      .base :: (value.features ++ onOk.features ++ onError.features)
  | .record _ fields => [.base, .nominalData] ++ fields.flatMap features
  | .project value _ => [.base, .nominalData] ++ value.features
  | .variant _ _ payload => [.base, .nominalData] ++ payload.flatMap features
  | .matchVariant value branches =>
      [.base, .nominalData] ++ value.features ++ branches.flatMap features
  | .none element => [.base, .option] ++ element.features
  | .some value => [.base, .option] ++ value.features
  | .matchOption value onNone onSome =>
      [.base, .option] ++ value.features ++ onNone.features ++ onSome.features
  | .nil element => [.base, .list] ++ element.features
  | .cons head tail => [.base, .list] ++ head.features ++ tail.features
  | .matchList value onNil onCons =>
      [.base, .list] ++ value.features ++ onNil.features ++ onCons.features
  | .foldList items initial step =>
      [.base, .list, .listFold] ++ items.features ++ initial.features ++ step.features
  | .foldNat count initial step =>
      [.base, .natFold] ++ count.features ++ initial.features ++ step.features
  | .call _ arguments => [.base, .acyclicCalls] ++ arguments.flatMap features

structure Function where
  id : String
  params : List Ty
  result : Ty
  body : Expr
  deriving Repr

def Function.features (function : Function) : List Feature :=
  function.params.flatMap Ty.features ++ function.result.features ++ function.body.features

structure Program where
  declarations : List TypeDecl
  helpers : List Function
  entries : List Function
  deriving Repr

/-- Includes unused declarations and helpers: a feature cannot be hidden in dead syntax.
An elaborator that removes syntax must bind admission to the resulting accepted artifact. -/
def requiredFeatures (program : Program) : List Feature :=
  [.base] ++ program.declarations.flatMap TypeDecl.features ++
    program.helpers.flatMap Function.features ++ program.entries.flatMap Function.features

structure Profile where
  enabled : List Feature
  deriving DecidableEq, Repr

/-- A capability check only; this does not imply any semantic well-formedness judgment. -/
def Admitted (profile : Profile) (program : Program) : Prop :=
  ∀ feature ∈ requiredFeatures program, feature ∈ profile.enabled

def Extends (larger smaller : Profile) : Prop :=
  ∀ feature ∈ smaller.enabled, feature ∈ larger.enabled

def checkAdmission (profile : Profile) (program : Program) : Bool :=
  (requiredFeatures program).all (fun feature => profile.enabled.contains feature)

theorem admission_monotone (small large : Profile) (program : Program)
    (extension : Extends large small) (accepted : Admitted small program) :
    Admitted large program := by
  intro feature required
  exact extension feature (accepted feature required)

theorem missing_feature_rejected (profile : Profile) (program : Program) (feature : Feature)
    (required : feature ∈ requiredFeatures program) (missing : feature ∉ profile.enabled) :
    ¬ Admitted profile program := by
  intro accepted
  exact missing (accepted feature required)

theorem checkAdmission_iff (profile : Profile) (program : Program) :
    checkAdmission profile program = true ↔ Admitted profile program := by
  simp [checkAdmission, Admitted, List.all_eq_true]

theorem missing_feature_check_false (profile : Profile) (program : Program) (feature : Feature)
    (required : feature ∈ requiredFeatures program) (missing : feature ∉ profile.enabled) :
    checkAdmission profile program = false := by
  cases h : checkAdmission profile program
  · rfl
  · exact False.elim ((missing_feature_rejected profile program feature required missing)
      ((checkAdmission_iff profile program).mp h))

def baseProfile : Profile := ⟨[.base]⟩

def dataOnlyProfile : Profile := ⟨[.base, .nominalData, .option, .list]⟩

def pureDataProfile : Profile :=
  ⟨[.base, .nominalData, .option, .list, .acyclicCalls, .listFold, .natFold]⟩

theorem dataOnly_extends_base : Extends dataOnlyProfile baseProfile := by
  intro feature required
  cases feature <;> simp_all [baseProfile, dataOnlyProfile]

theorem pureData_extends_dataOnly : Extends pureDataProfile dataOnlyProfile := by
  intro feature required
  cases feature <;> simp_all [dataOnlyProfile, pureDataProfile]

/-- Even an unused list parameter requires list support; the body is only a Nat literal. -/
def listSignatureProgram : Program := {
  declarations := []
  helpers := []
  entries := [{ id := "ignore", params := [.list .nat], result := .nat, body := .nat 0 }]
}

theorem list_signature_requires_list : .list ∈ requiredFeatures listSignatureProgram := by decide

theorem list_signature_base_rejected : checkAdmission baseProfile listSignatureProgram = false :=
  missing_feature_check_false baseProfile listSignatureProgram .list
    list_signature_requires_list (by decide)

/-- An empty list still requires support for both lists and its element type. -/
def emptyOptionListProgram : Program := {
  declarations := []
  helpers := []
  entries := [{ id := "empty", params := [], result := .list (.option .nat), body := .nil (.option .nat) }]
}

theorem empty_list_requires_option :
    .option ∈ requiredFeatures emptyOptionListProgram := by decide

theorem empty_list_requires_list :
    .list ∈ requiredFeatures emptyOptionListProgram := by decide

theorem empty_list_dataOnly_admitted : checkAdmission dataOnlyProfile emptyOptionListProgram = true :=
  by simp [checkAdmission, dataOnlyProfile, requiredFeatures, emptyOptionListProgram,
    Function.features, Ty.features, Expr.features]

/-- A list field in an unused declaration is also inspected. -/
def unusedRecordProgram : Program := {
  declarations := [.record "Bag" [{ id := "items", ty := .list .nat }]]
  helpers := []
  entries := [{ id := "zero", params := [], result := .nat, body := .nat 0 }]
}

theorem unused_record_requires_list : .list ∈ requiredFeatures unusedRecordProgram := by decide

def foldedListProgram : Program := {
  declarations := []
  helpers := []
  entries := [{ id := "sum", params := [.list .nat], result := .nat, body := .foldList (.var 0) (.nat 0) (.bin .add (.var 1) (.var 0)) }]
}

theorem list_fold_requires_iteration : .listFold ∈ requiredFeatures foldedListProgram := by
  simp [requiredFeatures, foldedListProgram, Function.features, Ty.features, Expr.features]

theorem list_fold_dataOnly_rejected : checkAdmission dataOnlyProfile foldedListProgram = false :=
  missing_feature_check_false dataOnlyProfile foldedListProgram .listFold
    list_fold_requires_iteration (by decide)

theorem list_fold_data_admitted : checkAdmission pureDataProfile foldedListProgram = true :=
  by simp [checkAdmission, pureDataProfile, requiredFeatures, foldedListProgram,
    Function.features, Ty.features, Expr.features]

/-- Requirements in a list match's cons branch cannot be hidden by a nil scrutinee. -/
def hiddenConsBranchProgram : Program := {
  declarations := []
  helpers := [{ id := "zero", params := [], result := .nat, body := .nat 0 }]
  entries := [{
    id := "hidden"
    params := []
    result := .nat
    body := .matchList (.nil .nat) (.nat 0) (.foldNat (.nat 1) (.nat 0) (.call "zero" []))
  }]
}

theorem cons_branch_requires_natFold :
    .natFold ∈ requiredFeatures hiddenConsBranchProgram := by
  simp [requiredFeatures, hiddenConsBranchProgram, Function.features, Ty.features, Expr.features]

theorem cons_branch_requires_calls :
    .acyclicCalls ∈ requiredFeatures hiddenConsBranchProgram := by
  simp [requiredFeatures, hiddenConsBranchProgram, Function.features, Ty.features, Expr.features]

/-- Feature admission deliberately cannot detect a recursive helper call.
A separately checked acyclic-call-graph premise must reject this program. -/
def cyclicCallProgram : Program := {
  declarations := []
  helpers := [{ id := "loop", params := [], result := .nat, body := .call "loop" [] }]
  entries := [{ id := "run", params := [], result := .nat, body := .call "loop" [] }]
}

theorem cyclic_calls_pass_feature_check : checkAdmission pureDataProfile cyclicCallProgram = true :=
  by simp [checkAdmission, pureDataProfile, requiredFeatures, cyclicCallProgram,
    Function.features, Ty.features, Expr.features]

end VSCoreGrammarModel
