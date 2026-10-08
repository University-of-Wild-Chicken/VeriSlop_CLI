# Concrete interpreter prompt failure

This observer note records a failure of the frozen CLI prompt/output protocol. It does not alter any model response or counted attempt.

The interpreter system prompt says:

> Use exactly these kinds and normal roles: entity/declaration, precondition/assumption, postcondition/guarantee

The intended notation pairs two separate fields (`kind` and `role`). It does not explicitly tell the model that the slash is a separator rather than part of a literal field value. The complete JSON example illustrates only a postcondition and contains no declaration or assumption record.

Luna G03's first response used `"kind":"entity/declaration","role":"normal"` and assumption metadata `supplier` / `where_discharged`. The CLI returned exact schema diagnostics with the previous proposal. The third attempt still used slash-containing kinds (`entity/declaration` and `precondition/assumption`), so the interpretation stage exhausted its three attempts and blocked before Lean. This is a concrete output/schema failure with ambiguous system-prompt notation; it is not evidence that Lean rejected a valid contract.

The second response also contained malformed JSON near the quoted public examples. The controller compared the displayed primary responder final text with the published envelope and reported the same malformed excerpt and parse offset 9211. Complete response fidelity is not independently attested by the collaboration transport; this limitation is preserved with the simulation provenance. No response was rewritten.

Evidence: [exact first request](../runs/luna-agents-002/artifacts/G03/verislop/request-0001.json), [first response](../runs/luna-agents-002/artifacts/G03/verislop/response-0001.json), [third response](../runs/luna-agents-002/artifacts/G03/verislop/response-0003.json), [scored strict arm](../runs/luna-agents-002/artifacts/G03/verislop/score.json).

A follow-up prompt revision should list each allowed `kind` and `role` as separate literal fields and include complete declaration and assumption examples. It requires a new source snapshot and experiment. The current experiment continues with its frozen sources.
