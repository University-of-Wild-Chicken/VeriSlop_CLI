# Bounded increment in VSCore 0.1 (Tier 2, `restricted_source`)

This directory holds candidate inputs for a Tier 2 bridge from the accepted bounded-increment
contract (`examples/formalization`) to a delivered VSCore program. Everything here is untrusted.
The registered checker `verislop.vscore-checker` derives the goal and decides acceptance.

| File | Role | Content |
|---|---|---|
| `program.vscore.json` | `source` | The delivered program: canonical `vscore-json/0.1` bytes with no whitespace and sorted keys. |
| `relation.json` | `relation` | Names the template `vscore.reference_refinement/0.1` and binds accepted symbol `increment` to entry `increment`. |
| `Proof.lean` | `proof_source` | Module `VeriSlopBridgeProof`, which proves `Refines_increment` and then `edge`. |

The program, written as nested JSON:

```text
increment(limit, input) =            -- params ["nat","nat"]; var 0 = input, var 1 = limit
  if input < limit then ok(input + 1) else error(IncrementError.limitReached)
```

## Workflow

```bash
P=.verislop/runs/<run-id>        # an accepted, exported bounded-increment run
verislop vscore goal --package $P --source examples/vscore/program.vscore.json \
  --relation examples/vscore/relation.json --proof examples/vscore/Proof.lean \
  --out /tmp/vscore-candidate --bridge-id bounded-increment-vscore
verislop bridge prepare --package $P --proposal /tmp/vscore-candidate/proposal.json \
  --candidate-dir /tmp/vscore-candidate
verislop bridge accept  --package $P --bridge-id bounded-increment-vscore
verislop bridge verify  --package $P --bridge-id bounded-increment-vscore
```

`vscore goal` is advisory and publishes nothing. It derives `VeriSlopBridgeGoal.lean` and the node's
model/profile descriptors, checks the proof in one isolated build, and prints the proposition hash
that the proposal must freeze. It then writes a complete candidate directory. `bridge accept` repeats
every step from the frozen bundle in two isolated builds. On success it publishes
`bridges/<bridge-id>/semantic/<edge-key>/` containing the certificate, `implementation-ir.json`, the
goal source, the accepted goal/proof modules, both build records and the evidence record.

## What acceptance establishes

The accepted theorem `VeriSlopBridgeProof.edge : VeriSlopBridgeGoal.EdgeProp` states:

- `VSCore.parseSource sourceBytes = .ok rawProgram`, where `sourceBytes` are the exact delivered bytes;
- `VSCore.checkProgram profile rawProgram = .ok signatures`, using the accepted enumeration registry;
- `InputsCover_increment`: every well-typed argument list is the encoding of contract inputs;
- `Refines_increment`: for all `limit input : Nat`, the entry returns exactly the encoded
  `VeriSlop.BoundedIncrement.increment limit input`;
- `Transfer_O17`, `Transfer_I2` and `Transfer_E1`: the accepted obligations, read through the
  implementation relation. They are proved inside the goal from the accepted theorems.

The certificate is scoped to the VSCore source and its Lean semantics. Running the program with a
host interpreter, or compiling it, is outside this edge. `END_TO_END_VERIFIED` is not assigned yet
(see `verislop capabilities`).
