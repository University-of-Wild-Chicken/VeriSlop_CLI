# Why the strict corpus experiments failed

**Experiments stopped by the user. These are partial observations, not completed 100-task results.**

## qwen-local-003

42 complete pairs; 85 completed arm records. Raw successful tasks 35/43; strict CLI 0/42. Raw calls 43; CLI calls 317.

First failing stage: {"formalize": 33, "interpret": 5, "review:formal_contract": 4}.

Primary failure codes: {"CANDIDATE_BUILD_FAILURE": 20, "INVALID_CANDIDATE": 1, "MISSING_WITNESS": 2, "PROVIDER_FAILURE": 12, "REVIEW_INCOMPLETE": 3, "UNSUPPORTED_SEMANTICS": 4}.

## luna-agents-002

18 complete pairs; 37 completed arm records. Raw successful tasks 18/19; strict CLI 0/18. Raw calls 19; CLI calls 119.

First failing stage: {"formalize": 7, "interpret": 9, "prove": 1, "review:formal_contract": 1}.

Primary failure codes: {"CANDIDATE_BUILD_FAILURE": 3, "INVALID_CANDIDATE": 9, "KERNEL_REJECTION": 1, "MISSING_WITNESS": 2, "PROOF_UNRESOLVED": 1, "REVIEW_INCOMPLETE": 1, "UNSUPPORTED_SEMANTICS": 1}.

## Concrete causes

1. **Interpretation schema failures:** Luna had nine terminal interpretation failures; Qwen had one schema failure and four provider failures there. Luna G03 repeatedly used slash-containing kinds; G32 ended with unknown obligation IDs; A29 used a non-ambiguity disposition for ambiguity obligations. Exact stage feedback and response hashes remain recorded.

2. **Formalization failures:** Qwen had 20 terminal Lean elaboration failures and six unsupported-semantics failures. Examples include nonexistent `List.get!` (G24/G05), String indexing instances (A05/D18), reserved `end`/`at` identifiers (D09/G23), and unsupported custom-domain assumptions (G13/D19). Luna had three elaboration failures, three unsupported domains and one kernel-replay failure. These are actual stopped paths, not a blanket forecast about model capability.

3. **Generated recursion helper replay:** Luna G23's final candidate compilation succeeded (`compile.ok=true`, no compile errors), but the statement check rejected missing `VeriSlop.ValidRequests._unsafe_rec` and `VeriSlop.simulate._unsafe_rec` after kernel replay. Both ordinary recursive definitions are visible in the candidate. This isolates a kernel-replay/export boundary failure; it does not establish the generated contract's semantic correctness.

4. **Prover repair received no new information:** Luna D06 issued eight prover calls with one identical user-payload hash, despite recorded compile errors including an unterminated identifier and failed `Decidable` synthesis. Six proof holes remained; prove and accept were blocked. Luna D19 similarly sent three identical prover payloads before eventually proving its weaker contract. Compiler failures were saved in attempts.jsonl but did not enter the subsequent recorded prover prompts.

5. **Semantic weakness passed Lean gates:** Qwen D07's 16 purported CSV guarantees were `∀n:Nat,n=n`; D02's eight guarantees were `True`; G09 used `size=size`, `pairs=pairs` and `True`. D26 proved only existence of an output with matching length/membership, admitting `output=input` without sorting. Luna D19 defined eight join/safety predicates constantly `True`. All five reached export PASS. Lean proved the actual weak statements; the failure is their correspondence to requested behavior. No implementation artifact was generated.

6. **Review packet showed stale proof bodies:** Four of those five packets displayed the frozen challenge containing `sorry` while announcing `accepted_and_proved`, rather than the accepted proof source. Luna D19's critic reported REJECT because G1 appeared to contain `sorry`; its mechanical probe was NOT_REPRODUCED, giving replayed ABSTAIN. Qwen D07/G09 exhausted three protocol corrections each with unknown ballot fields. Qwen D02 produced a valid ABSTAIN that explicitly identified constant-True semantics and an unusable title-only missing-requirement template. Genuine abstentions remain unsuccessful.

7. **Provider failures are separately observed:** Qwen recorded 12 primary provider failures (nine HTTP500 and three abnormal completion stops). Preserved G03 and D21 service excerpts show CUDA launch timeout, aborted llama-server and matching HTTP500. Those two crashes are observed infrastructure causes; the remaining service failures are not all attributed to GPU crashes without matching evidence.

## Evidence and limits

[Machine-readable diagnosis](DIAGNOSIS.json) lists every completed CLI failure, exact primary diagnostic, active package, calls and stage history. It also records prover payload hashes/attempt logs, accepted weak declarations, review packet and ballot references, and GPU excerpts. [Stopped comparison](comparison.json) retains every exact saved score and case observation; [offline viewer](viewer.html) compares only common completed pairs across models.

All 142 Qwen and 144 Luna measured source hashes matched their captured copies and current runtime at STOP_SOURCE_AUDIT.json's stop boundary. Later runtime repairs are reported separately and do not alter historical execution bytes. Both stopped manifests are hash-audited; no case or candidate was rerun. Qwen D12 CLI and Luna G17 CLI were unfinished and remain unscored. Their completed raw arms remain individual records, excluded from paired denominators.

Finite recorded-evidence analysis trusts saved observations, frozen expectations and host/transport records. It neither proves the dataset oracles nor authenticates Luna's actual model identity. No Tier 0 result establishes END_TO_END_VERIFIED. Earlier stopped experiments remain separate.
