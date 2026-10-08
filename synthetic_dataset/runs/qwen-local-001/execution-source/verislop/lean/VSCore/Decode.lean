import VSCore.Syntax

/-!
# VSCore 0.1 — normative source decoder

`parseSource` is the normative interpretation of delivered source bytes. The source format
`vscore-json/0.1` is a strict subset of RFC 8785 canonical JSON:

* bytes are ASCII; there is no whitespace anywhere and nothing after the top-level value;
* strings contain only printable ASCII (0x20–0x7E) other than `"` and `\` (no escapes);
* numbers are canonical non-negative integers `0 | [1-9][0-9]*`, at most 2^53 − 1;
* `null`, negative numbers, fractions and exponents are rejected;
* object keys are strictly increasing (sorted, hence unique);
* every node has exactly the fields of its schema; unknown or missing fields are rejected;
* identifiers match `[A-Za-z_][A-Za-z0-9_.-]*` (≤ 128 bytes); naturals are canonical decimal
  strings (≤ 1024 digits), so unbounded literals never pass through a bounded JSON number.

All functions are structurally recursive on explicit fuel bounded by the input length, so the
Lean kernel evaluates them directly (`decide +kernel`): a host parser can only *propose* the
decoded program; the kernel-checked equation `parseSource bytes = .ok program` binds it.
-/

namespace VSCore

/-- Generic canonical-JSON value (subset). -/
inductive Json where
  | str (s : String)
  | num (n : Nat)
  | bool (b : Bool)
  | arr (xs : List Json)
  | obj (kvs : List (String × Json))

def maxSafeInteger : Nat := 9007199254740991

def isDigit (b : Nat) : Bool := 48 ≤ b && b ≤ 57

def strByte (b : Nat) : Bool := 32 ≤ b && b ≤ 126 && b != 34 && b != 92

/-- Strict lexicographic order on byte lists (ASCII keys: equals UTF-16 code-unit order). -/
def bytesLt : List Nat → List Nat → Bool
  | [], [] => false
  | [], _ :: _ => true
  | _ :: _, [] => false
  | a :: as, b :: bs => if a < b then true else if a == b then bytesLt as bs else false

def bytesToString (bs : List Nat) : String := String.ofList (bs.map Char.ofNat)

/-- Read string bytes up to the closing quote. -/
def parseStrBytes : Nat → List Nat → List Nat → Except String (List Nat × List Nat)
  | 0, _, _ => .error "string exceeds parse budget"
  | _ + 1, [], _ => .error "unterminated string"
  | fuel + 1, b :: rest, acc =>
    if b == 34 then .ok (acc.reverse, rest)
    else if strByte b then parseStrBytes fuel rest (b :: acc)
    else .error "string contains an escape, control or non-ASCII byte"

def parseDigits : Nat → List Nat → Nat → Nat × List Nat
  | 0, bs, n => (n, bs)
  | _ + 1, [], n => (n, [])
  | fuel + 1, b :: rest, n => if isDigit b then parseDigits fuel rest (n * 10 + (b - 48)) else (n, b :: rest)

mutual
def parseValue : Nat → List Nat → Except String (Json × List Nat)
  | 0, _ => .error "JSON exceeds parse budget"
  | _ + 1, [] => .error "unexpected end of input"
  | fuel + 1, b :: rest =>
    if b == 34 then
      match parseStrBytes (rest.length + 1) rest [] with
      | .ok (s, r) => .ok (.str (bytesToString s), r)
      | .error m => .error m
    else if b == 123 then
      match rest with
      | 125 :: r => .ok (.obj [], r)
      | _ =>
        match parseMembers fuel rest [] with
        | .ok (kvs, r) => .ok (.obj kvs, r)
        | .error m => .error m
    else if b == 91 then
      match rest with
      | 93 :: r => .ok (.arr [], r)
      | _ =>
        match parseElems fuel rest with
        | .ok (xs, r) => .ok (.arr xs, r)
        | .error m => .error m
    else if b == 116 then
      match rest with
      | 114 :: 117 :: 101 :: r => .ok (.bool true, r)
      | _ => .error "invalid literal"
    else if b == 102 then
      match rest with
      | 97 :: 108 :: 115 :: 101 :: r => .ok (.bool false, r)
      | _ => .error "invalid literal"
    else if b == 48 then
      match rest with
      | c :: _ => if isDigit c then .error "non-canonical integer (leading zero)" else .ok (.num 0, rest)
      | [] => .ok (.num 0, rest)
    else if isDigit b then
      let (n, r) := parseDigits (rest.length) rest (b - 48)
      if n ≤ maxSafeInteger then .ok (.num n, r) else .error "integer exceeds 2^53 - 1"
    else .error "unexpected byte (whitespace, null, sign, or non-JSON)"

/-- Members after `{`; `prev` is the previous key (keys must strictly increase). -/
def parseMembers : Nat → List Nat → List Nat → Except String (List (String × Json) × List Nat)
  | 0, _, _ => .error "JSON exceeds parse budget"
  | fuel + 1, bs, prev =>
    match bs with
    | 34 :: rest =>
      match parseStrBytes (rest.length + 1) rest [] with
      | .error m => .error m
      | .ok (k, r) =>
        if !prev.isEmpty && !bytesLt prev k then .error "object keys are not strictly sorted"
        else if prev.isEmpty && k.isEmpty then .error "empty object key"
        else
          match r with
          | 58 :: r2 =>
            match parseValue fuel r2 with
            | .error m => .error m
            | .ok (v, r3) =>
              match r3 with
              | 44 :: r4 =>
                match parseMembers fuel r4 k with
                | .ok (more, r5) => .ok ((bytesToString k, v) :: more, r5)
                | .error m => .error m
              | 125 :: r4 => .ok ([(bytesToString k, v)], r4)
              | _ => .error "expected ',' or '}'"
          | _ => .error "expected ':'"
    | _ => .error "expected an object key"

def parseElems : Nat → List Nat → Except String (List Json × List Nat)
  | 0, _ => .error "JSON exceeds parse budget"
  | fuel + 1, bs =>
    match parseValue fuel bs with
    | .error m => .error m
    | .ok (v, r) =>
      match r with
      | 44 :: r2 =>
        match parseElems fuel r2 with
        | .ok (more, r3) => .ok (v :: more, r3)
        | .error m => .error m
      | 93 :: r2 => .ok ([v], r2)
      | _ => .error "expected ',' or ']'"
end

/-- Parse a complete canonical-JSON document (no trailing bytes). -/
def parseJson (bytes : List Nat) : Except String Json :=
  match parseValue (bytes.length + 1) bytes with
  | .ok (v, []) => .ok v
  | .ok (_, _ :: _) => .error "trailing bytes after the JSON value"
  | .error m => .error m

/-! ## Closed schema decoder -/

def isIdentStart (c : Char) : Bool := c.isAlpha || c == '_'
def isIdentChar (c : Char) : Bool := c.isAlphanum || c == '_' || c == '.' || c == '-'

def validIdent (s : String) : Bool :=
  match s.toList with
  | [] => false
  | c :: cs => s.length ≤ 128 && isIdentStart c && cs.all isIdentChar

def decimalDigits : List Char → Bool
  | [] => false
  | ['0'] => true
  | '0' :: _ => false
  | cs => cs.all Char.isDigit

def decimalValue (cs : List Char) : Nat :=
  cs.foldl (fun n c => n * 10 + (c.toNat - 48)) 0

def decodeNatLiteral (s : String) : Except String Nat :=
  if decimalDigits s.toList && s.length ≤ 1024 then .ok (decimalValue s.toList)
  else .error "natural literal must be a canonical decimal string"

def keysOf (kvs : List (String × Json)) : List String := kvs.map (·.1)

def lookup (kvs : List (String × Json)) (k : String) : Option Json :=
  (kvs.find? (·.1 == k)).map (·.2)

def decodeIdent : Json → Except String String
  | .str s => if validIdent s then .ok s else .error "invalid identifier"
  | _ => .error "expected an identifier string"

def decodeTy : Nat → Json → Except String Ty
  | 0, _ => .error "type nesting exceeds decode budget"
  | _ + 1, .str "nat" => .ok .nat
  | _ + 1, .str "bool" => .ok .bool
  | _ + 1, .str "unit" => .ok .unit
  | _ + 1, .obj [("enum", j)] =>
    match decodeIdent j with
    | .ok id => .ok (.enum id)
    | .error m => .error m
  | fuel + 1, .obj [("result", .obj [("error", e), ("ok", o)])] =>
    match decodeTy fuel e, decodeTy fuel o with
    | .ok te, .ok to => .ok (.result te to)
    | .error m, _ => .error m
    | _, .error m => .error m
  | _ + 1, _ => .error "invalid type"

def decodeBinOp : String → Option BinOp
  | "add" => some .add | "sub" => some .sub | "mul" => some .mul
  | "lt" => some .lt | "le" => some .le | "eq" => some .eq
  | "and" => some .and | "or" => some .or
  | _ => none

def field (kvs : List (String × Json)) (k : String) : Except String Json :=
  match lookup kvs k with
  | some j => .ok j
  | none => .error s!"missing field {k}"

def decodeExpr : Nat → Json → Except String Expr
  | 0, _ => .error "expression nesting exceeds decode budget"
  | fuel + 1, .obj kvs =>
    match lookup kvs "tag" with
    | some (.str tag) =>
      let keys := keysOf kvs
      let sub (k : String) : Except String Expr :=
        match field kvs k with
        | .ok j => decodeExpr fuel j
        | .error m => .error m
      let ty (k : String) : Except String Ty :=
        match field kvs k with
        | .ok j => decodeTy fuel j
        | .error m => .error m
      if tag == "var" then
        if keys != ["index", "tag"] then .error "var: unexpected or missing fields" else
        match lookup kvs "index" with
        | some (.num i) => .ok (.var i)
        | _ => .error "var: index must be a canonical integer"
      else if tag == "nat" then
        if keys != ["tag", "value"] then .error "nat: unexpected or missing fields" else
        match lookup kvs "value" with
        | some (.str s) =>
          match decodeNatLiteral s with
          | .ok n => .ok (.nat n)
          | .error m => .error m
        | _ => .error "nat: value must be a decimal string"
      else if tag == "bool" then
        if keys != ["tag", "value"] then .error "bool: unexpected or missing fields" else
        match lookup kvs "value" with
        | some (.bool b) => .ok (.bool b)
        | _ => .error "bool: value must be true or false"
      else if tag == "unit" then
        if keys != ["tag"] then .error "unit: unexpected fields" else .ok .unit
      else if tag == "enum" then
        if keys != ["ctor", "enum", "tag"] then .error "enum: unexpected or missing fields" else
        match field kvs "enum", field kvs "ctor" with
        | .ok e, .ok c =>
          match decodeIdent e, decodeIdent c with
          | .ok id, .ok ctor => .ok (.enum id ctor)
          | .error m, _ => .error m
          | _, .error m => .error m
        | .error m, _ => .error m
        | _, .error m => .error m
      else if tag == "not" then
        if keys != ["tag", "value"] then .error "not: unexpected or missing fields" else
        match sub "value" with
        | .ok e => .ok (.not e)
        | .error m => .error m
      else if tag == "if" then
        if keys != ["cond", "else", "tag", "then"] then .error "if: unexpected or missing fields" else
        match sub "cond", sub "then", sub "else" with
        | .ok c, .ok t, .ok e => .ok (.ite c t e)
        | .error m, _, _ => .error m
        | _, .error m, _ => .error m
        | _, _, .error m => .error m
      else if tag == "let" then
        if keys != ["body", "tag", "value"] then .error "let: unexpected or missing fields" else
        match sub "value", sub "body" with
        | .ok v, .ok b => .ok (.letE v b)
        | .error m, _ => .error m
        | _, .error m => .error m
      else if tag == "ok" then
        if keys != ["error_type", "tag", "value"] then .error "ok: unexpected or missing fields" else
        match ty "error_type", sub "value" with
        | .ok t, .ok v => .ok (.ok t v)
        | .error m, _ => .error m
        | _, .error m => .error m
      else if tag == "error" then
        if keys != ["ok_type", "tag", "value"] then .error "error: unexpected or missing fields" else
        match ty "ok_type", sub "value" with
        | .ok t, .ok v => .ok (.error t v)
        | .error m, _ => .error m
        | _, .error m => .error m
      else if tag == "match_result" then
        if keys != ["error", "ok", "scrutinee", "tag"] then .error "match_result: unexpected or missing fields" else
        match sub "scrutinee", sub "ok", sub "error" with
        | .ok s, .ok o, .ok e => .ok (.matchResult s o e)
        | .error m, _, _ => .error m
        | _, .error m, _ => .error m
        | _, _, .error m => .error m
      else
        match decodeBinOp tag with
        | some op =>
          if keys != ["left", "right", "tag"] then .error s!"{tag}: unexpected or missing fields" else
          match sub "left", sub "right" with
          | .ok l, .ok r => .ok (.bin op l r)
          | .error m, _ => .error m
          | _, .error m => .error m
        | none => .error s!"unsupported expression tag {tag}"
    | _ => .error "expression object needs a string tag"
  | _ + 1, _ => .error "expression must be an object"

def decodeTys (fuel : Nat) : List Json → Except String (List Ty)
  | [] => .ok []
  | j :: js =>
    match decodeTy fuel j, decodeTys fuel js with
    | .ok t, .ok ts => .ok (t :: ts)
    | .error m, _ => .error m
    | _, .error m => .error m

def decodeEntry (fuel : Nat) : Json → Except String Entry
  | .obj kvs =>
    if keysOf kvs != ["body", "id", "params", "result"] then .error "entry: unexpected or missing fields" else
    match field kvs "id", field kvs "params", field kvs "result", field kvs "body" with
    | .ok idj, .ok (.arr ps), .ok rj, .ok bj =>
      match decodeIdent idj, decodeTys fuel ps, decodeTy fuel rj, decodeExpr fuel bj with
      | .ok id, .ok params, .ok result, .ok body => .ok { id, params, result, body }
      | .error m, _, _, _ => .error m
      | _, .error m, _, _ => .error m
      | _, _, .error m, _ => .error m
      | _, _, _, .error m => .error m
    | _, _, _, _ => .error "entry: id, params (array), result and body are required"
  | _ => .error "entry must be an object"

def decodeEntries (fuel : Nat) : List Json → Except String (List Entry)
  | [] => .ok []
  | j :: js =>
    match decodeEntry fuel j, decodeEntries fuel js with
    | .ok e, .ok es => .ok (e :: es)
    | .error m, _ => .error m
    | _, .error m => .error m

def decodeProgram (fuel : Nat) : Json → Except String Program
  | .obj kvs =>
    if keysOf kvs != ["entries", "language"] then .error "program: unexpected or missing fields" else
    match lookup kvs "language", lookup kvs "entries" with
    | some (.str lang), some (.arr es) =>
      if lang != languageId then .error "unsupported language version" else
      match decodeEntries fuel es with
      | .ok entries => .ok { language := lang, entries }
      | .error m => .error m
    | _, _ => .error "program: language string and entries array are required"
  | _ => .error "program must be an object"

/-- Normative interpretation of exact source bytes. -/
def parseSource (bytes : List Nat) : Except String Program :=
  match parseJson bytes with
  | .ok j => decodeProgram (bytes.length + 1) j
  | .error m => .error m

/-- Boolean form used for kernel evaluation (`decide +kernel`). -/
def parseCheck (bytes : List Nat) (expected : Program) : Bool :=
  match parseSource bytes with
  | .ok p => decide (p = expected)
  | .error _ => false

theorem parseSource_of_check {bytes : List Nat} {expected : Program}
    (h : parseCheck bytes expected = true) : parseSource bytes = .ok expected := by
  unfold parseCheck at h
  split at h
  · rename_i p hp
    rw [hp]
    simp only [decide_eq_true_eq] at h
    rw [h]
  · contradiction

end VSCore
