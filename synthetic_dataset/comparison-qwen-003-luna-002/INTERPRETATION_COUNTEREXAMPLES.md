# Concrete interpretation counterexample

This is an observer finding about an unaccepted interpreted proposal. It is separate from benchmark case scores and was not sent to any model role. No requirement or evidence was changed.

Qwen's accepted **interpretation** for G03 includes `O2`: “The element at index 'source' in the output list is 0.” The request instead says the source **starts** at distance zero, while vertices affected by a reachable negative cycle return `"-inf"`. Treating the initial distance as an unconditional final postcondition makes the interpretation inconsistent.

Concrete conforming input:

```json
{"n": 1, "source": 0, "edges": [[0, 0, -1]]}
```

Expected output is `["-inf"]`: traversing the negative self-loop repeatedly gives arbitrarily negative walk cost. The frozen corpus's `_g03` reference implementation was also executed on this input and returned `["-inf"]`. This falsifies interpreted `O2`'s unconditional zero requirement. The already frozen case `G03-hidden-2` also has a source affected by a negative cycle and expects `"-inf"` at that index.

Evidence: [Qwen G03 interpreted draft](../runs/qwen-local-003/artifacts/G03/verislop/package/draft.json), [original request](../tasks/G03/prompt.txt), [corpus cases](../tasks/G03/cases.json), [reference implementation](../generate_graph_systems.py).

This observation does not claim a false theorem was accepted by Lean. G03 never completed formalization, and its CLI arm ended with a provider infrastructure failure. It shows that interpretation acceptance checks structural clause coverage, while semantic faithfulness still needs proof and review.
