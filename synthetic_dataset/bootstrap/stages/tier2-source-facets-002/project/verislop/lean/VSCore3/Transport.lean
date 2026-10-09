import VSCore3.Semantics

/-! Representation laws and conservative *syntactic* embedding. Aggregate ports
require exact adapters to the accepted registry, including canonical record layouts.
Embedding round trips do not by themselves prove whole evaluator correspondence. -/
namespace VSCore3
set_option linter.defProp false

def bridgePortSupported : Ty → Bool
  | .nat | .int | .string | .bool | .unit | .enum _ | .record _ => true
  | .result e o => bridgePortSupported e && bridgePortSupported o
  | .option t | .list t => bridgePortSupported t
  | _ => false

/-- An exact representation isomorphism into an intrinsic source type. -/
structure Adapter (t : Shape) (α : Type) where
  to : α → Denote t
  inv : Denote t → α
  from_to : ∀ a, inv (to a) = a
  to_from : ∀ v, to (inv v) = v

def Adapter.encode {t : Shape} {α : Type} (a : Adapter t α) (x : α) : Value :=
  VSCore3.encode t (a.to x)

theorem Adapter.encode_hasShape {t : Shape} {α : Type} (a : Adapter t α) (x : α) :
    HasShape t (a.encode x) := ⟨a.to x, rfl⟩

theorem Adapter.covers {t : Shape} {α : Type} (a : Adapter t α) {v : Value}
    (h : HasShape t v) : ∃ x, a.encode x = v := by
  obtain ⟨typed, rfl⟩ := h
  exact ⟨a.inv typed, by simp [Adapter.encode, a.to_from]⟩

def natAdapter : Adapter .nat Nat := ⟨(fun x => x), (fun x => x), fun _ => rfl, fun _ => rfl⟩
def intAdapter : Adapter .int Int := ⟨(fun x => x), (fun x => x), fun _ => rfl, fun _ => rfl⟩
def stringAdapter : Adapter .string String := ⟨(fun x => x), (fun x => x), fun _ => rfl, fun _ => rfl⟩
def boolAdapter : Adapter .bool Bool := ⟨(fun x => x), (fun x => x), fun _ => rfl, fun _ => rfl⟩
def unitAdapter : Adapter .unit Unit := ⟨(fun x => x), (fun x => x), fun _ => rfl, fun _ => rfl⟩
def enumAdapter (id : String) (cs : List String) : Adapter (.enum id cs) { c : String // c ∈ cs } :=
  ⟨(fun x => x), (fun x => x), fun _ => rfl, fun _ => rfl⟩

def resultAdapter {te to : Shape} {E O : Type} (err : Adapter te E) (ok : Adapter to O) :
    Adapter (.result te to) (Except E O) where
  to := fun x => match x with | .error e => .inl (err.to e) | .ok o => .inr (ok.to o)
  inv := fun x => match x with | .inl e => .error (err.inv e) | .inr o => .ok (ok.inv o)
  from_to := by intro x; cases x <;> simp [err.from_to, ok.from_to]
  to_from := by intro x; cases x <;> simp [err.to_from, ok.to_from]

def optionAdapter {t : Shape} {α : Type} (a : Adapter t α) : Adapter (.option t) (Option α) where
  to := Option.map a.to
  inv := Option.map a.inv
  from_to := by intro x; cases x <;> simp [a.from_to]
  to_from := by intro x; cases x <;> simp [a.to_from]

def listAdapter {t : Shape} {α : Type} (a : Adapter t α) : Adapter (.list t) (List α) where
  to := List.map a.to
  inv := List.map a.inv
  from_to := by intro x; induction x <;> simp_all [a.from_to]
  to_from := by intro x; induction x <;> simp_all [a.to_from]

def productAdapter {a b : Shape} {α β : Type} (x : Adapter a α) (y : Adapter b β) :
    Adapter (.product a b) (α × β) where
  to := fun v => (x.to v.1, y.to v.2)
  inv := fun v => (x.inv v.1, y.inv v.2)
  from_to := by intro v; simp [x.from_to, y.from_to]
  to_from := by intro v; simp [x.to_from, y.to_from]

def recordAdapter {payload : Shape} {α : Type} (id : String) (names : List String)
    (a : Adapter payload α) : Adapter (.record id names payload) α :=
  ⟨a.to, a.inv, a.from_to, a.to_from⟩

/-- Raw representation laws are supplied only for a canonical shape. They are
not asserted for arbitrary malformed Shape.record/Shape.variant values. -/
structure RawLaws (t : Shape) : Prop where
  decode_encode : ∀ x : Denote t, decode t (encode t x) = some x
  encode_decode : ∀ {v : Value} {x : Denote t}, decode t v = some x → encode t x = v

theorem RawLaws.encode_injective {t : Shape} (h : RawLaws t) : Function.Injective (encode t) := by
  intro x y he
  have := congrArg (decode t) he
  simpa only [h.decode_encode, Option.some.injEq] using this

theorem Adapter.encode_eq_iff {t : Shape} {α : Type} (a : Adapter t α) (h : RawLaws t)
    {x y : α} : a.encode x = a.encode y ↔ x = y := by
  constructor
  · intro he
    have ht := h.encode_injective he
    have := congrArg a.inv ht
    simpa only [a.from_to] using this
  · intro he; cases he; rfl

theorem Adapter.decode_encode {t : Shape} {α : Type} (a : Adapter t α) (h : RawLaws t) (x : α) :
    decode t (a.encode x) = some (a.to x) := h.decode_encode _

theorem Adapter.represents {t : Shape} {α : Type} (a : Adapter t α) (h : RawLaws t)
    {v : Value} {x : Denote t} (hx : decode t v = some x) : ∃ y, a.encode y = v := by
  exact ⟨a.inv x, by simpa only [Adapter.encode, a.to_from] using h.encode_decode hx⟩

def natRawLaws : RawLaws .nat := ⟨by intro x; simp [decode, encode], by intro v x h; cases v <;> simp_all [decode, encode]⟩
def intRawLaws : RawLaws .int := ⟨by intro x; simp [decode, encode], by intro v x h; cases v <;> simp_all [decode, encode]⟩
def stringRawLaws : RawLaws .string := ⟨by intro x; simp [decode, encode], by intro v x h; cases v <;> simp_all [decode, encode]⟩
def boolRawLaws : RawLaws .bool := ⟨by intro x; simp [decode, encode], by intro v x h; cases v <;> simp_all [decode, encode]⟩
def unitRawLaws : RawLaws .unit := ⟨by intro x; simp [decode, encode], by intro v x h; cases v <;> simp_all [decode, encode]⟩

def enumRawLaws (id : String) (cs : List String) : RawLaws (.enum id cs) where
  decode_encode := by intro x; simp [decode, encode, x.property]
  encode_decode := by
    intro v x h
    cases v <;> simp only [decode, reduceCtorEq] at h
    rename_i i c
    split at h
    · split at h
      · simp only [Option.some.injEq] at h
        cases h
        simp_all [encode]
      · contradiction
    · contradiction

def optionRawLaws {t : Shape} (h : RawLaws t) : RawLaws (.option t) where
  decode_encode := by intro x; cases x <;> simp [encode, decode, h.decode_encode]
  encode_decode := by
    intro v x hx
    cases v <;> simp only [decode, reduceCtorEq] at hx
    · cases hx; simp [encode]
    · rename_i v
      cases hv : decode t v with
      | none => simp [hv] at hx
      | some y => simp [hv] at hx; cases hx; simp [encode, h.encode_decode hv]

def resultRawLaws {e o : Shape} (he : RawLaws e) (ho : RawLaws o) : RawLaws (.result e o) where
  decode_encode := by intro x; cases x <;> simp [encode, decode, he.decode_encode, ho.decode_encode]
  encode_decode := by
    intro v x hx
    cases v <;> simp only [decode, reduceCtorEq] at hx
    · rename_i v
      cases hv : decode o v with
      | none => simp [hv] at hx
      | some y => simp [hv] at hx; cases hx; simp [encode, ho.encode_decode hv]
    · rename_i v
      cases hv : decode e v with
      | none => simp [hv] at hx
      | some y => simp [hv] at hx; cases hx; simp [encode, he.encode_decode hv]

theorem decodeList_encodeList {t : Shape} (h : RawLaws t) (xs : List (Denote t)) :
    decodeList (decode t) (encodeList (encode t) xs) = some xs := by
  induction xs with
  | nil => rfl
  | cons x xs ih => simp [decodeList, encodeList, h.decode_encode, ih]

theorem encodeList_decodeList {t : Shape} (h : RawLaws t) (v : Value) (xs : List (Denote t))
    (hx : decodeList (decode t) v = some xs) : encodeList (encode t) xs = v := by
  cases v <;> simp only [decodeList, reduceCtorEq] at hx
  · cases hx; rfl
  · rename_i head tail
    cases hh : decode t head with
    | none => simp [hh] at hx
    | some a =>
      cases ht : decodeList (decode t) tail with
      | none => simp [hh, ht] at hx
      | some as =>
        simp [hh, ht] at hx
        cases hx
        simp [encodeList, h.encode_decode hh, encodeList_decodeList h tail as ht]
termination_by sizeOf v

def listRawLaws {t : Shape} (h : RawLaws t) : RawLaws (.list t) where
  decode_encode := by intro xs; simpa only [decode, encode] using decodeList_encodeList h xs
  encode_decode := by
    intro v xs hx
    simpa only [encode] using encodeList_decodeList h v xs (by simpa only [decode] using hx)

theorem unpackProduct_ok {v : Value} {x y : Value} (h : unpackProduct v = some (x, y)) :
    v = .record "_internal_product" [("head", x), ("tail", y)] := by
  unfold unpackProduct at h
  split at h <;> simp_all

def productRawLaws {a b : Shape} (ha : RawLaws a) (hb : RawLaws b) : RawLaws (.product a b) where
  decode_encode := by intro x; rcases x with ⟨x, y⟩; simp [encode, decode, unpackProduct, ha.decode_encode, hb.decode_encode]
  encode_decode := by
    intro v x hx
    simp only [decode] at hx
    cases hu : unpackProduct v with
    | none => simp [hu] at hx
    | some pair =>
      rcases pair with ⟨p, q⟩
      cases hp : decode a p with
      | none => simp [hu, hp] at hx
      | some y =>
        cases hq : decode b q with
        | none => simp [hu, hp, hq] at hx
        | some z =>
          simp [hu, hp, hq] at hx
          cases hx
          simp [encode, ha.encode_decode hp, hb.encode_decode hq, unpackProduct_ok hu]

/-- Exact field-count and product layout; no law is inferred merely from nominal syntax. -/
inductive RecordLayout : List String → Shape → Prop where
  | nil : RecordLayout [] .unit
  | cons {names : List String} {a b : Shape} (name : String)
      (tail : RecordLayout names b) : RecordLayout (name :: names) (.product a b)

theorem packFields_encodeFields {names : List String} {t : Shape} (h : RecordLayout names t)
    (x : Denote t) : packFields names (encodeFields names t x) = some (encode t x) := by
  induction h with
  | nil => simp [encodeFields, packFields, encode]
  | cons name tail ih =>
    rcases x with ⟨x, y⟩
    simp [encodeFields, packFields, encode, ih]

theorem packFields_injective (names : List String) {fs gs : List (String × Value)} {v : Value}
    (hf : packFields names fs = some v) (hg : packFields names gs = some v) : fs = gs := by
  induction names generalizing fs gs v with
  | nil => cases fs <;> cases gs <;> simp_all [packFields]
  | cons n ns ih =>
    cases fs with
    | nil => simp [packFields] at hf
    | cons f fs =>
      cases gs with
      | nil => simp [packFields] at hg
      | cons g gs =>
        rcases f with ⟨fn, fv⟩
        rcases g with ⟨gn, gv⟩
        simp only [packFields] at hf hg
        split at hf <;> try contradiction
        split at hg <;> try contradiction
        cases ht : packFields ns fs with
        | none => simp [ht] at hf
        | some ft =>
          cases hu : packFields ns gs with
          | none => simp [hu] at hg
          | some gt =>
            simp [ht] at hf
            simp [hu] at hg
            have he := hf.trans hg.symm
            simp only [Value.record.injEq, List.cons.injEq, Prod.mk.injEq, and_true, true_and] at he
            obtain ⟨hv, ht_eq⟩ := he
            have hs := ih ht (ht_eq ▸ hu)
            simp_all

def recordRawLaws {names : List String} {t : Shape} (id : String)
    (layout : RecordLayout names t) (h : RawLaws t) : RawLaws (.record id names t) where
  decode_encode := by intro x; simp [encode, decode, packFields_encodeFields layout, h.decode_encode]
  encode_decode := by
    intro v x hx
    cases v <;> simp only [decode, reduceCtorEq] at hx
    rename_i i fs
    split at hx
    · rename_i hi
      cases hp : packFields names fs with
      | none => simp [hp] at hx
      | some packed =>
        simp [hp] at hx
        have he := h.encode_decode hx
        have hf := packFields_injective names (packFields_encodeFields layout x) (he ▸ hp)
        simp_all [encode]
    · contradiction

def encodeEnv : (ts : List Shape) → Env ts → List Value
  | [], _ => []
  | t :: ts, (x, xs) => encode t x :: encodeEnv ts xs

theorem decodeEnv_encodeEnv (ts : List Shape) (laws : ∀ t ∈ ts, RawLaws t) (env : Env ts) :
    decodeEnv ts (encodeEnv ts env) = some env := by
  induction ts with
  | nil => rfl
  | cons t ts ih =>
    rcases env with ⟨x, xs⟩
    simp [decodeEnv, encodeEnv, (laws t (by simp)).decode_encode,
      ih (fun u hu => laws u (by simp [hu])) xs]

theorem encodeEnv_decodeEnv (ts : List Shape) (laws : ∀ t ∈ ts, RawLaws t)
    (values : List Value) (env : Env ts) (h : decodeEnv ts values = some env) :
    encodeEnv ts env = values := by
  induction ts generalizing values with
  | nil => cases values <;> simp_all [decodeEnv, encodeEnv]
  | cons t ts ih =>
    cases values with
    | nil => simp [decodeEnv] at h
    | cons v vs =>
      cases hv : decode t v with
      | none => simp [decodeEnv, hv] at h
      | some x =>
        cases ht : decodeEnv ts vs with
        | none => simp [decodeEnv, hv, ht] at h
        | some xs =>
          simp [decodeEnv, hv, ht] at h
          cases h
          simp [encodeEnv, (laws t (by simp)).encode_decode hv,
            ih (fun u hu => laws u (by simp [hu])) vs xs ht]

theorem evalEntry_encoded {p : Profile} {prog : Program} {cp : CheckedProgram}
    (hc : compileProgram p prog = .ok cp) {id : String} {e : CompiledFunction}
    (he : findEntry cp id = some e) (laws : ∀ t ∈ e.params, RawLaws t) (env : Env e.params) :
    evalEntry p prog id (encodeEnv e.params env) = .ok (encode e.result (e.run env)) := by
  simp only [evalEntry, hc, he, evalCheckedEntry, decodeEnv_encodeEnv e.params laws env]

theorem encodedArgs_cover {e : CompiledFunction} (laws : ∀ t ∈ e.params, RawLaws t)
    {args : List Value} (h : ArgsTyped e args) : ∃ env, encodeEnv e.params env = args := by
  obtain ⟨env, he⟩ := h
  exact ⟨env, encodeEnv_decodeEnv e.params laws args env he⟩

def embedTy : VSCore.Ty → Ty
  | .nat => .nat | .bool => .bool | .unit => .unit | .enum id => .enum id
  | .result e o => .result (embedTy e) (embedTy o)

def eraseTy : Ty → Option VSCore.Ty
  | .nat => some .nat | .bool => some .bool | .unit => some .unit | .enum id => some (.enum id)
  | .result e o => do return .result (← eraseTy e) (← eraseTy o)
  | _ => none

theorem erase_embedTy (t : VSCore.Ty) : eraseTy (embedTy t) = some t := by
  induction t <;> simp_all [embedTy, eraseTy]

theorem embedTy_injective {a b : VSCore.Ty} (h : embedTy a = embedTy b) : a = b := by
  have := congrArg eraseTy h
  simpa [erase_embedTy] using this

def embedValue : VSCore.Value → Value
  | .nat n => .nat n | .bool b => .bool b | .unit => .unit | .enum id c => .enum id c
  | .ok x => .ok (embedValue x) | .error x => .error (embedValue x)

def eraseValue : Value → Option VSCore.Value
  | .nat n => some (.nat n) | .bool b => some (.bool b) | .unit => some .unit | .enum id c => some (.enum id c)
  | .ok x => (eraseValue x).map VSCore.Value.ok
  | .error x => (eraseValue x).map VSCore.Value.error
  | _ => none

theorem erase_embedValue (v : VSCore.Value) : eraseValue (embedValue v) = some v := by
  induction v <;> simp_all [embedValue, eraseValue]

theorem embedValue_injective {a b : VSCore.Value} (h : embedValue a = embedValue b) : a = b := by
  have := congrArg eraseValue h
  simpa [erase_embedValue] using this

def embedExpr : VSCore.Expr → Expr
  | .var i => .var i | .nat n => .nat n | .bool b => .bool b | .unit => .unit
  | .enum id c => .enum id c
  | .bin op a b => .bin op (embedExpr a) (embedExpr b)
  | .not a => .not (embedExpr a)
  | .ite c t e => .ite (embedExpr c) (embedExpr t) (embedExpr e)
  | .letE a b => .letE (embedExpr a) (embedExpr b)
  | .ok t a => .ok (embedTy t) (embedExpr a)
  | .error t a => .error (embedTy t) (embedExpr a)
  | .matchResult s o e => .matchResult (embedExpr s) (embedExpr o) (embedExpr e)

def eraseExpr : Expr → Option VSCore.Expr
  | .var i => some (.var i) | .nat n => some (.nat n) | .bool b => some (.bool b) | .unit => some .unit
  | .enum id c => some (.enum id c)
  | .bin op a b => do return .bin op (← eraseExpr a) (← eraseExpr b)
  | .not a => (eraseExpr a).map VSCore.Expr.not
  | .ite c t e => do return .ite (← eraseExpr c) (← eraseExpr t) (← eraseExpr e)
  | .letE a b => do return .letE (← eraseExpr a) (← eraseExpr b)
  | .ok t a => do return .ok (← eraseTy t) (← eraseExpr a)
  | .error t a => do return .error (← eraseTy t) (← eraseExpr a)
  | .matchResult s o e => do return .matchResult (← eraseExpr s) (← eraseExpr o) (← eraseExpr e)
  | _ => none

theorem erase_embedExpr (e : VSCore.Expr) : eraseExpr (embedExpr e) = some e := by
  induction e <;> simp_all [embedExpr, eraseExpr, erase_embedTy]

theorem embedExpr_injective {a b : VSCore.Expr} (h : embedExpr a = embedExpr b) : a = b := by
  have := congrArg eraseExpr h
  simpa [erase_embedExpr] using this

def embedEntry (e : VSCore.Entry) : Entry :=
  { id := e.id, params := e.params.map embedTy, result := embedTy e.result, body := embedExpr e.body }

def embedProgram (p : VSCore.Program) : Program :=
  { language := languageId, profile := profileId, declarations := [], helpers := [], entries := p.entries.map embedEntry }

theorem embedded_program_has_no_helpers (p : VSCore.Program) : (embedProgram p).helpers = [] := rfl

theorem embedded_program_has_no_nominal_declarations (p : VSCore.Program) : (embedProgram p).declarations = [] := rfl

end VSCore3
