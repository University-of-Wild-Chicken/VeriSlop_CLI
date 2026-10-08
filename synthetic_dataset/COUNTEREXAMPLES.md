# Recorded benchmark counterexamples

These examples come from the frozen dataset and recorded outputs of the local
Qwen benchmark's superseded 60-second experiment (`qwen-local-001`). They identify
specific failed cases; they do not establish a general reliability rate and are
not pooled into the new deadline-free experiment (`qwen-local-002`).

## G03: a reachable negative cycle affects descendants

Task G03 requires shortest-walk distances from the source. A vertex whose distance
is unbounded below because of a reachable negative cycle must be reported as
`"-inf"`; an unreachable vertex must be `null`.

Case: `G03-hidden-1`. Full input:

```json
{"edges":[[0,1,0],[1,1,-1],[1,2,0],[3,3,-1]],"n":4,"source":0}
```

Expected output:

```json
[0,"-inf","-inf",null]
```

Recorded raw Qwen output:

```json
["-inf","-inf",-4,null]
```

Vertex 1 has a reachable negative self-loop. Traversing it any number of times
before moving to vertex 2 makes both vertices' distances unbounded below. Vertex
0 remains at distance zero: there is no edge returning from that cycle to vertex
0. Vertex 3 is unreachable from the source. The artifact instead marks vertex 0
as unbounded and returns a finite distance for vertex 2. Its affected-vertex
propagation traverses the reverse graph, which explains these two incorrect
positions on this input.

Evidence: [raw artifact](runs/qwen-local-001/artifacts/G03/raw/artifact/solution.py),
[recorded score and observation](runs/qwen-local-001/artifacts/G03/raw/score.json),
and [frozen case inputs and expected outputs](tasks/G03/cases.json).
An independent sandbox replay reproduced this observation.

## G03: full CLI workflow timeout

This is a workflow failure, not a program counterexample. The paired full
VeriSlop CLI arm recorded `TIMEOUT` after 60.071 seconds, with its last model
purpose `interpret`. It recorded one attempted call, zero received native
responses, and one call with unknown token usage. No implementation artifact was
produced, so the task's test cases are recorded as failures.

The actual CLI diagnostic was:

```json
{"code":"INTERRUPTED","message":"the run was cancelled; required checks remain unresolved","severity":"blocking"}
```

Evidence: [full CLI score](runs/qwen-local-001/artifacts/G03/verislop/score.json),
[CLI invocation](runs/qwen-local-001/artifacts/G03/verislop/cli-invocation.json),
and [CLI report](runs/qwen-local-001/artifacts/G03/verislop/package/report.json).
