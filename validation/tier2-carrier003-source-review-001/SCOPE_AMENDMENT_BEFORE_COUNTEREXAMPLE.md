# Empty request identity source compatibility check (before isolated call)

{
  "affected_surface": "Declared identity-compatible availability checkpoint for a valid existing reader result; source compatibility only, not currentQ/task outcome",
  "checks": "Execute only fixed checkpoint runtime on unrelated own JSON; no reader/file/model/VIEW/Lean/qualification calls",
  "expected_observation": "ACTUAL_VIEW_IDENTITY_MISMATCH",
  "format": "verislop.carrier003-source-counterexample-specification/1",
  "input": "Unrelated canonical inventory with empty request_id, all carrier/reference/totals/output-cap metadata valid",
  "mode": "ISOLATED_GENERIC_SOURCE",
  "runtime_authority": false,
  "source_difference": "Unchanged reader admits request_id as any strict UTF8 string; new checkpointAdvance additionally requires length>0"
}
