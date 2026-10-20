# P03 offline result recheck

Run from a checkout, with Python 3.10+ and no model service or network access:

```sh
python -B -m synthetic_dataset.tools.recheck_p03 /path/to/local-hybrid-live-20261014-005 --out /outside/evidence/recheck.json
```

For a repaired active package, pass `--package tasks/P03-unicode-labels/runs/<relative-active-package>` (relative to the trial root). Archived absolute package paths are never followed. The output must be new and outside the evidence tree. Exit 0 means finite checks completed (`RECHECKED`); exit 2 means incomplete, failed, missing, or unavailable checks. Read individual fields for cause. No ledger or milestone is updated. Do not run alongside a writer to the evidence directory.

## Reused facilities

- `run_local_hybrid.py` already freezes protocol, inputs, source inventory and a source archive. Its `verify_inputs` requires the original runtime and external tokenizer paths, so is inappropriate for relocated offline evidence. This tool checks retained bytes and archive members without extraction or executing archived code.
- `canonical` and `fsutil` already provide strict JSON, byte hashes, manifests and path validation.
- `check_data_pipeline_poc` already checks preregistration, accepted IR, source/contract links and 160 cases twice. Its `run_check`, `select_solve`, and `native_tested_gate` are reused. It may need the local Lean toolchain to check accepted artifacts; missing prerequisites remain incomplete.
- The existing Python Harness copies candidate bytes into a temporary staging directory and requires filesystem/network isolation. Production rechecks never disable those requirements.

The retained receipt's cases, expectations, two responses per case, counters, verdicts and observation hash are recomputed against the preregistered case file; source/link/report/package hashes are cross-checked. This establishes internal consistency, not authenticity or proof that historical execution occurred. Self-consistent forged records remain possible without an external trusted anchor. Source archives are not imported. External tokenizer and service state, ledger authenticity/schema, transcript completeness, proof execution and review execution are not independently certified here.

Five new cases have literal expected outputs from the public request: mixed decomposed/precomposed accents, whitespace, duplicates, empty prefix, all-empty labels, empty input, astral text and NUL. The existing wire encoder is reused, not the candidate's algorithm. Boundary observations can run even when historical checker evidence is missing. Current-checker reexecution is separately labeled and does not award an end-to-end guarantee.

## Validation in this environment

The target historical trial directory is absent. Therefore the claimed repairs, three rejected Pythagoras candidates, accepted Qwen revision, six TESTED guarantees, 320 historical observations, reviews, final validation and ledger-0010 cannot be independently confirmed here. The published report is a historical claim, not a substitute for these files.

`tests/test_recheck_p03.py` checks a correct synthetic implementation, five deliberate defects (trimming, normalization, deduplication, count, empty prefix), tampered observations, absent history and unsafe paths. This host lacks required namespace isolation: tests run only known handwritten fixtures through the real Harness with namespace requirements disabled in a test-local mock. These finite fixture observations validate comparison plumbing, not production isolation or historical execution. There is no production bypass flag.
