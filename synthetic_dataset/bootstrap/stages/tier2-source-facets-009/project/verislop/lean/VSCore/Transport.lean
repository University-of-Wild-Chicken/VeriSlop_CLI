import VSCore.Semantics

/-!
# VSCore 0.1 — representation adapters and transport support

An `Adapter p α τ` relates a contract type `α` to VSCore values of type `τ`. Its laws are the
representation obligations of docs/tier-2-4.md §1.2 for the *selected* encoder:

* `enc_typed` — every contract value is encoded as a well-typed VSCore value;
* `dec_enc`   — decoding an encoding returns the original value (round trip);
* `enc_dec`   — a successful decode identifies the unique encoding (no aliasing);
* `covers`    — every well-typed VSCore value of type `τ` decodes to some contract value, so
                the frozen interface admits no target input outside the claimed domain.

Adapters for `Nat`, `Bool`, `Unit` and `Except` are generic. A contract enumeration gets its
adapter from `enumAdapter`, whose laws are proved here once; a bridge only supplies the
constructor naming, an exhaustive constructor list, name injectivity and the registry entry.
-/

namespace VSCore

structure Adapter (p : Profile) (α : Type) (τ : Ty) where
  enc : α → Value
  dec : Value → Option α
  enc_typed : ∀ a, HasType p (enc a) τ
  dec_enc : ∀ a, dec (enc a) = some a
  enc_dec : ∀ v a, dec v = some a → enc a = v
  covers : ∀ v, HasType p v τ → ∃ a, dec v = some a

theorem Adapter.enc_eq_iff {p : Profile} {α : Type} {τ : Ty} (A : Adapter p α τ) {a b : α} :
    A.enc a = A.enc b ↔ a = b := by
  constructor
  · intro h
    have := A.dec_enc a
    rw [h, A.dec_enc b] at this
    exact (Option.some.inj this).symm
  · intro h
    rw [h]

theorem Adapter.represents {p : Profile} {α : Type} {τ : Ty} (A : Adapter p α τ) {v : Value}
    (h : HasType p v τ) : ∃ a, A.enc a = v :=
  match A.covers v h with
  | ⟨a, ha⟩ => ⟨a, A.enc_dec v a ha⟩

def natAdapter (p : Profile) : Adapter p Nat .nat where
  enc n := .nat n
  dec | .nat n => some n | _ => none
  enc_typed n := .nat n
  dec_enc _ := rfl
  enc_dec v a h := by cases v <;> simp_all
  covers v h := by cases h; exact ⟨_, rfl⟩

def boolAdapter (p : Profile) : Adapter p Bool .bool where
  enc b := .bool b
  dec | .bool b => some b | _ => none
  enc_typed b := .bool b
  dec_enc _ := rfl
  enc_dec v a h := by cases v <;> simp_all
  covers v h := by cases h; exact ⟨_, rfl⟩

def unitAdapter (p : Profile) : Adapter p Unit .unit where
  enc _ := .unit
  dec | .unit => some () | _ => none
  enc_typed _ := .unit
  dec_enc _ := rfl
  enc_dec v a h := by cases v <;> simp_all
  covers v h := by cases h; exact ⟨(), rfl⟩

theorem wfTy_of_hasType {p : Profile} : ∀ {v : Value} {t : Ty}, HasType p v t → wfTy p t = true
  | _, _, .nat _ => rfl
  | _, _, .bool _ => rfl
  | _, _, .unit => rfl
  | _, _, .enum h _ => by simp [wfTy, h]
  | _, _, .ok hv hw => by simp [wfTy, wfTy_of_hasType hv, hw]
  | _, _, .error hv hw => by simp [wfTy, wfTy_of_hasType hv, hw]

def exceptAdapter {p : Profile} {ε α : Type} {te ta : Ty}
    (E : Adapter p ε te) (A : Adapter p α ta) (hwe : wfTy p te = true) (hwa : wfTy p ta = true) :
    Adapter p (Except ε α) (.result te ta) where
  enc
    | .ok a => .ok (A.enc a)
    | .error e => .error (E.enc e)
  dec
    | .ok v => (A.dec v).map .ok
    | .error v => (E.dec v).map .error
    | _ => none
  enc_typed
    | .ok a => .ok (A.enc_typed a) hwe
    | .error e => .error (E.enc_typed e) hwa
  dec_enc
    | .ok a => by simp [A.dec_enc]
    | .error e => by simp [E.dec_enc]
  enc_dec v x h := by
    cases v with
    | ok w =>
      cases hw : A.dec w with
      | none => simp [hw] at h
      | some a =>
        simp only [hw, Option.map_some, Option.some.injEq] at h
        subst h
        simp [A.enc_dec w a hw]
    | error w =>
      cases hw : E.dec w with
      | none => simp [hw] at h
      | some e =>
        simp only [hw, Option.map_some, Option.some.injEq] at h
        subst h
        simp [E.enc_dec w e hw]
    | _ => simp at h
  covers v h := by
    cases h with
    | ok hv _ =>
      obtain ⟨a, ha⟩ := A.covers _ hv
      exact ⟨.ok a, by simp [ha]⟩
    | error hv _ =>
      obtain ⟨e, he⟩ := E.covers _ hv
      exact ⟨.error e, by simp [he]⟩

/-! ## Enumerations -/

theorem find?_name {α : Type} (name : α → String) (inj : ∀ a b, name a = name b → a = b) :
    ∀ (all : List α) (a : α), a ∈ all → all.find? (fun b => name b == name a) = some a
  | [], _, h => by simp at h
  | x :: xs, a, h => by
    simp only [List.find?_cons]
    by_cases hx : name x = name a
    · have hb : (name x == name a) = true := beq_iff_eq.mpr hx
      rw [hb, inj x a hx]
    · have hb : (name x == name a) = false := by simpa using hx
      have hmem : a ∈ xs := by
        rcases List.mem_cons.mp h with rfl | hm
        · exact absurd rfl hx
        · exact hm
      simp only [hb, find?_name name inj xs a hmem]

/-- Adapter for a contract enumeration `α` registered as `id` with constructor names `all.map name`. -/
def enumAdapter {p : Profile} {α : Type} (id : String) (name : α → String) (all : List α)
    (complete : ∀ a, a ∈ all) (inj : ∀ a b, name a = name b → a = b)
    (registry : lookupEnum p id = some (all.map name)) : Adapter p α (.enum id) where
  enc a := .enum id (name a)
  dec
    | .enum i c => if i = id then all.find? (fun b => name b == c) else none
    | _ => none
  enc_typed a := .enum registry (List.mem_map.mpr ⟨a, complete a, rfl⟩)
  dec_enc a := by simp [find?_name name inj all a (complete a)]
  enc_dec v a h := by
    cases v with
    | enum i c =>
      by_cases hi : i = id
      · simp only [hi, ite_true] at h
        have := List.find?_some h
        simp only [beq_iff_eq] at this
        subst hi
        rw [this]
      · simp [hi] at h
    | _ => simp at h
  covers v h := by
    cases h with
    | enum hl hc =>
      rw [registry] at hl
      cases hl
      obtain ⟨a, ha, rfl⟩ := List.mem_map.mp hc
      exact ⟨a, by simp [find?_name name inj all a ha]⟩

/-! ## Argument lists in parameter order -/

inductive ArgsTypedIn (p : Profile) : List Value → List Ty → Prop
  | nil : ArgsTypedIn p [] []
  | cons {v : Value} {t : Ty} {vs : List Value} {ts : List Ty} :
      HasType p v t → ArgsTypedIn p vs ts → ArgsTypedIn p (v :: vs) (t :: ts)

theorem ArgsTypedIn.toEnv {p : Profile} : ∀ {args : List Value} {ts : List Ty},
    ArgsTypedIn p args ts → ArgsTyped p args ts
  | _, _, .nil => .nil
  | _, _, .cons hv hs => by
    unfold ArgsTyped
    simp only [List.reverse_cons]
    exact EnvTyped.append (ArgsTypedIn.toEnv hs) (.cons hv .nil)

end VSCore
