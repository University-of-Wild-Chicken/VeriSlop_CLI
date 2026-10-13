import Lean
import Std

open Lean

/- Syntax validation only. No candidate elaboration, evaluation or module import.
   In particular, a term parser through EOF cannot admit a trailing command. -/
unsafe def main (args : List String) : IO UInt32 := do
  let [requestPath, responsePath] := args
    | IO.eprintln "usage: lean --run VeriSlopProofSyntax.lean request.json response.json"; return 64
  initSearchPath (← findSysroot)
  let request ← match Json.parse (← IO.FS.readFile requestPath) with
    | .ok value => pure value
    | .error message => IO.eprintln message; return 64
  let .ok terms := (request.getObjValD "terms").getArr?
    | IO.eprintln "terms must be an array"; return 64
  -- Only these fixed trusted toolchain imports initialize parser extensions.
  -- Candidate imports, initializers and proof bodies are never executed.
  enableInitializersExecution
  let environment ← importModules #[{module := `Lean}, {module := `Std}] {} 0
    (loadExts := true) (leakEnv := true)
  let mut results : Array Json := #[]
  for value in terms do
    let .ok text := value.getStr?
      | IO.eprintln "proof bodies must be strings"; return 64
    let result := match Parser.runParserCategory environment `term text "<proof-body>" with
      | .ok _ => Json.mkObj [("ok", Json.bool true)]
      | .error message => Json.mkObj [("ok", Json.bool false), ("error", Json.str message)]
    results := results.push result
  IO.FS.writeFile responsePath (Json.mkObj [("format", Json.str "verislop.proof-term-syntax/0.1"),
    ("results", Json.arr results)]).compress
  return 0
