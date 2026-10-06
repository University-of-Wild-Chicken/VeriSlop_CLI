# Checked subtraction in VSCore 0.1

This fixture has its own request, interpretation ledger, formal contract and proofs. It uses
mathematical `Nat` values without a machine-width bound and the one-constructor enumeration
`DebitError.insufficient`:

```text
subtractIfEnough(balance, amount) =
  if amount ≤ balance then ok(balance - amount) else error(insufficient)
```

The required guarantees are the success equation (`S1`), reconstruction after success
(`R1`: `remaining + amount = balance`), the output bound (`B1`: `remaining ≤ balance`), and
the exact error condition (`E1`: error iff `balance < amount`). The caller supplies natural
numbers; the fixture adds no upper bound or success-only precondition. The accepted contract
witnesses (`W1`) cover zero/zero success, positive equality success and underflow error.

`formalization/Contract.lean` supplies the reference definitions and contract proofs.
`program.vscore.json` contains the exact canonical source bytes; `relation.json` binds the
accepted `subtractIfEnough` symbol to the source entry. `Proof.lean` proves total refinement
against that reference and then the generated edge proposition. It also contains kernel
evaluation proofs for zero, equality, underflow and an input and output above `2^64`.
These concrete cases validate the fixture; they do not create runtime campaign evidence.
The candidates contain no `sorry`, custom axioms or native evaluation proofs.

Run the complete offline pipeline from the repository root:

```bash
bin/verislop run --prompt-file examples/vscore-subtraction/request.txt \
  --request-ref examples/vscore-subtraction/request.txt --mode software --tier 2 --target vscore \
  --draft-candidate examples/vscore-subtraction/draft.json \
  --ledger-candidate examples/vscore-subtraction/interpretation.json \
  --formalization-candidate examples/vscore-subtraction/formalization \
  --proof-candidate examples/vscore-subtraction/formalization/Contract.lean \
  --implementation-candidate examples/vscore-subtraction \
  --runs-dir .verislop/runs --run-id tier2-subtraction --non-interactive
```

Use a fresh run ID if that package already exists. The run independently interprets,
formalizes, accepts and reifies this contract, materializes and links its source, accepts
the semantic edge, and executes two complete closure builds. A successful run records
`END_TO_END_VERIFIED [restricted_source; vscore/0.1]` for the four required guarantees,
with applicable optional `TESTED` still `PENDING` and `release_status: NOT_REQUIRED`.
The report is `.verislop/runs/tier2-subtraction/report.json`; immutable mechanical attempts
and their exact inventories are under that package's `closure/executions/` directory.

```bash
bin/verislop verify --package .verislop/runs/tier2-subtraction
bin/verislop inspect report --package .verislop/runs/tier2-subtraction
```

`verify` performs fresh checks. Inspection reports recorded history only. Changed verifier
or schema hashes require a fresh run; changing source, proof or the frozen policy cannot
repair this selected implementation in place.

`tests/test_vscore_subtraction.py` exercises manual, prepared-bridge and one-command routes.
It rejects reversed subtraction, equality treated as an error, underflow incorrectly
returning success, and a nonexistent error constructor. The first three remain typed source
programs but cannot prove the exact refinement target. Materialization and structural
linking alone cannot give them semantic acceptance or E2E closure.

The endpoint covers the delivered VSCore source under its normative Lean decoder, type
checker and evaluator. Host execution, interpreters, compilation, native binaries, state,
I/O and physical or temporal guarantees remain outside it. Tier 2 has no runtime campaign
backend; explicitly requiring tests is rejected at admission.
