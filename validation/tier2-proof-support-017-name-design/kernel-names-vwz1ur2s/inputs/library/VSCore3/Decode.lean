import VSCore.Decode
import VSCore3.Syntax

/-! Normative exact-byte closed VSCore 0.3 decoder. Canonical JSON machinery is
reused from the immutable 0.1 decoder; all new AST shapes are closed here. -/
namespace VSCore3
open VSCore (Json keysOf lookup decodeIdent decodeNatLiteral parseJson validIdent)

/-- Signed literals have no plus sign, negative zero or redundant leading zero. -/
def decodeIntLiteral (s : String) : Except String Int :=
  match s.toList with
  | '-' :: cs => do
    let n ← decodeNatLiteral (String.ofList cs)
    if n == 0 then throw "negative zero is not canonical" else return -(Int.ofNat n)
  | _ => do return Int.ofNat (← decodeNatLiteral s)

def validScalar (n : Nat) : Bool := n < 0xD800 || (0xDFFF < n && n < 0x110000)

def decodeCodepoints (js : List Json) : Except String (List Nat) :=
  js.mapM fun j => match j with
    | .num n => if validScalar n then .ok n else .error "invalid Unicode scalar value"
    | _ => .error "string codepoints must be canonical JSON integers"

def decodeTy : Nat → Json → Except String Ty
  | 0, _ => .error "type nesting exceeds decode budget"
  | _ + 1, .str "nat" => .ok .nat
  | _ + 1, .str "int" => .ok .int
  | _ + 1, .str "string" => .ok .string
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
  | _ + 1, .obj [("record", j)] => do return .record (← decodeIdent j)
  | _ + 1, .obj [("variant", j)] => do return .variant (← decodeIdent j)
  | fuel + 1, .obj [("option", j)] => do return .option (← decodeTy fuel j)
  | fuel + 1, .obj [("list", j)] => do return .list (← decodeTy fuel j)
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
      else if tag == "int" then do
        if keys != ["tag", "value"] then throw "int: unexpected or missing fields"
        let .str s ← field kvs "value" | throw "int: value must be a signed decimal string"
        return .int (← decodeIntLiteral s)
      else if tag == "string" then do
        if keys != ["tag", "value"] then throw "string: unexpected or missing fields"
        let .arr js ← field kvs "value" | throw "string: value must be a scalar array"
        return .string (← decodeCodepoints js)
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
      else if tag == "record" then do
        if keys != ["fields", "record", "tag"] then throw "record: unexpected or missing fields"
        let id ← decodeIdent (← field kvs "record")
        let .arr fields ← field kvs "fields" | throw "record fields must be an array"
        let fields ← fields.mapM fun j => do
          let .obj fs := j | throw "record field must be an object"
          if keysOf fs != ["id", "value"] then throw "record field: unexpected or missing fields"
          return (← decodeIdent (← field fs "id"), ← decodeExpr fuel (← field fs "value"))
        return .record id fields
      else if tag == "project" then do
        if keys != ["field", "tag", "value"] then throw "project: unexpected or missing fields"
        return .project (← sub "value") (← decodeIdent (← field kvs "field"))
      else if tag == "variant" then do
        if keys != ["args", "ctor", "tag", "variant"] then throw "variant: unexpected or missing fields"
        let .arr args ← field kvs "args" | throw "variant args must be an array"
        return .variant (← decodeIdent (← field kvs "variant"))
          (← decodeIdent (← field kvs "ctor")) (← args.mapM (decodeExpr fuel))
      else if tag == "match_variant" then do
        if keys != ["branches", "scrutinee", "tag"] then throw "match_variant: unexpected or missing fields"
        let .arr branches ← field kvs "branches" | throw "variant branches must be an array"
        let branches ← branches.mapM fun j => do
          let .obj bs := j | throw "variant branch must be an object"
          if keysOf bs != ["body", "ctor"] then throw "variant branch: unexpected or missing fields"
          return (← decodeIdent (← field bs "ctor"), ← decodeExpr fuel (← field bs "body"))
        return .matchVariant (← sub "scrutinee") branches
      else if tag == "none" then do
        if keys != ["element_type", "tag"] then throw "none: unexpected or missing fields"
        return .none (← ty "element_type")
      else if tag == "some" then do
        if keys != ["tag", "value"] then throw "some: unexpected or missing fields"
        return .some (← sub "value")
      else if tag == "match_option" then do
        if keys != ["none", "scrutinee", "some", "tag"] then throw "match_option: unexpected or missing fields"
        return .matchOption (← sub "scrutinee") (← sub "none") (← sub "some")
      else if tag == "nil" then do
        if keys != ["element_type", "tag"] then throw "nil: unexpected or missing fields"
        return .nil (← ty "element_type")
      else if tag == "cons" then do
        if keys != ["head", "tag", "tail"] then throw "cons: unexpected or missing fields"
        return .cons (← sub "head") (← sub "tail")
      else if tag == "match_list" then do
        if keys != ["cons", "nil", "scrutinee", "tag"] then throw "match_list: unexpected or missing fields"
        return .matchList (← sub "scrutinee") (← sub "nil") (← sub "cons")
      else if tag == "call" then do
        if keys != ["args", "helper", "tag"] then throw "call: unexpected or missing fields"
        let .arr args ← field kvs "args" | throw "call args must be an array"
        return .call (← decodeIdent (← field kvs "helper")) (← args.mapM (decodeExpr fuel))
      else if tag == "list_fold" || tag == "nat_fold" then do
        if keys != ["initial", "source", "step", "tag"] then throw "fold: unexpected or missing fields"
        let source ← sub "source"
        let initial ← sub "initial"
        let step ← sub "step"
        return if tag == "list_fold" then .listFold source initial step else .natFold source initial step
      else if tag == "int_fdiv" || tag == "list_append" then do
        if keys != ["left", "right", "tag"] then throw "binary primitive: unexpected or missing fields"
        let l ← sub "left"
        let r ← sub "right"
        return if tag == "int_fdiv" then .intFdiv l r else .listAppend l r
      else if tag == "list_get" then do
        if keys != ["index", "tag", "value"] then throw "list_get: unexpected or missing fields"
        return .listGet (← sub "value") (← sub "index")
      else if tag == "list_map" || tag == "list_filter" then do
        if keys != ["body", "tag", "value"] then throw "list binder: unexpected or missing fields"
        let v ← sub "value"
        let body ← sub "body"
        return if tag == "list_map" then .listMap v body else .listFilter v body
      else if tag == "int_neg" || tag == "nat_to_int" || tag == "int_to_nat" ||
          tag == "list_length" || tag == "list_range" || tag == "list_reverse" ||
          tag == "list_sort" || tag == "list_unique" || tag == "list_sum" then do
        if keys != ["tag", "value"] then throw "unary primitive: unexpected or missing fields"
        let v ← sub "value"
        if tag == "int_neg" then return .intNeg v
        else if tag == "nat_to_int" then return .natToInt v
        else if tag == "int_to_nat" then return .intToNat v
        else if tag == "list_length" then return .listLength v
        else if tag == "list_range" then return .listRange v
        else if tag == "list_reverse" then return .listReverse v
        else if tag == "list_sort" then return .listSort v
        else if tag == "list_unique" then return .listUnique v
        else return .listSum v
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



def decodeEntries (fuel : Nat) (js : List Json) : Except String (List Entry) :=
  js.mapM (decodeEntry fuel)

def decodeDecl (fuel : Nat) : Json → Except String DataDecl
  | .obj kvs => do
    let .str tag ← field kvs "tag" | throw "declaration tag must be a string"
    if tag == "record" then
      if keysOf kvs != ["fields", "id", "tag"] then throw "record declaration: unexpected or missing fields"
      let .arr fs ← field kvs "fields" | throw "record declaration fields must be an array"
      let fs ← fs.mapM fun j => do
        let .obj kvs := j | throw "field declaration must be an object"
        if keysOf kvs != ["id", "type"] then throw "field declaration: unexpected or missing fields"
        return (← decodeIdent (← field kvs "id"), ← decodeTy fuel (← field kvs "type"))
      return .record (← decodeIdent (← field kvs "id")) fs
    else if tag == "variant" then
      if keysOf kvs != ["constructors", "id", "tag"] then throw "variant declaration: unexpected or missing fields"
      let .arr cs ← field kvs "constructors" | throw "constructors must be an array"
      let cs ← cs.mapM fun j => do
        let .obj kvs := j | throw "constructor declaration must be an object"
        if keysOf kvs != ["id", "params"] then throw "constructor declaration: unexpected or missing fields"
        let .arr ps ← field kvs "params" | throw "constructor params must be an array"
        return (← decodeIdent (← field kvs "id"), ← decodeTys fuel ps)
      return .variant (← decodeIdent (← field kvs "id")) cs
    else throw "unsupported declaration tag"
  | _ => .error "declaration must be an object"

def decodeProgram (fuel : Nat) : Json → Except String Program
  | .obj kvs => do
    if keysOf kvs != ["declarations", "entries", "helpers", "language", "profile"] then
      throw "program: unexpected or missing fields"
    let .str language ← field kvs "language" | throw "language must be a string"
    let .str profile ← field kvs "profile" | throw "profile must be a string"
    if language != languageId then throw "unsupported language version"
    if profile != profileId then throw "unsupported semantic profile"
    let .arr ds ← field kvs "declarations" | throw "declarations must be an array"
    let .arr hs ← field kvs "helpers" | throw "helpers must be an array"
    let .arr es ← field kvs "entries" | throw "entries must be an array"
    let declarations ← ds.mapM (decodeDecl fuel)
    let helpers ← decodeEntries fuel hs
    let entries ← decodeEntries fuel es
    return { language := language, profile := profile, declarations := declarations,
             helpers := helpers, entries := entries }
  | _ => .error "program must be an object"

def parseSource (bytes : List Nat) : Except String Program := do
  if bytes.length > maxSourceBytes then throw "source exceeds byte budget"
  decodeProgram maxDecodeDepth (← parseJson bytes)

end VSCore3
