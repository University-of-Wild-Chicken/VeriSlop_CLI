# Providers and hierarchical adversarial review

Version 0.1 design candidate · 2026-10-05

VeriSlop MUST let users provide API credentials for multiple model services, assign named models to agent roles, and configure the number and composition of adversarial reviewers at each review tier. Acceptance consensus at a lower review tier advances the same candidate to the next tier. The final tier's acceptance completes the review hierarchy.

This document specifies the provider and review interface, including requirements beyond the current implementation. See [the implementation notes](implementation.md#7-providers-and-review) for registered adapters and limitations. Automated conformance tests use loopback mock services; implemented protocol support is not a claim of live-provider conformance.

## 1. Two independent kinds of tier

Use `bridge_tier` for implementation assurance Tiers 0–4. Use `review_tiers` for the user-configured adversarial hierarchy, with arbitrary stable IDs such as `R0`, `R1`, and `R2`. The number of review tiers and number of agents are user choices subject to explicit operational limits, not fixed to five.

Three review tiers do not mean implementation Tier 3. Ten reviewers do not create stronger mathematical evidence than a checked proof. Review agents search for defects, challenge assumptions, propose counterexamples, and assess interpretation and engineering adequacy. Their consensus controls review workflow; registered checkers control formal milestones.

When review is enabled, final release requires BOTH all required mechanical checks and acceptance through the final review tier. Review may block a release even when the formal proofs pass, for example because the theorem fails to capture the request. Review acceptance cannot override a failing verifier.

## 2. Provider registry and user credentials

The registry MUST support adapters for these requested services: OpenAI; Anthropic/Claude; Google/Gemini; DeepSeek; Alibaba/Qwen; GLM through the selected Z.ai/Zhipu service; Moonshot/Kimi; xAI/Grok; and Muse through an explicitly identified provider. For Muse, the initial documented candidate is Meta's Muse service; a different intended Muse service uses a separately configured adapter rather than a guessed endpoint.

Provider family, service region, base URL, API protocol, model ID, auth method, and capabilities are distinct fields. Qwen and GLM deployments may require service/region-specific endpoints and credentials. Google direct API-key authentication and Google Cloud/Vertex credentials are separate auth profiles. A token for one product/region MUST NOT be forwarded to another by inference.

Support native adapters where required and an extensible `openai_compatible` adapter for services advertising compatible protocols. Compatible syntax does not imply identical structured-output, tool-call, streaming, reasoning, caching, token-limit, or error semantics. Adapter capability negotiation must precede role assignment. Unsupported required features cause a configuration diagnostic, never fabricated tool calls or silently truncated context.

An endpoint-profile registry ships with the built-in adapters and allows explicit user-defined profiles. A profile resolves to HTTPS base URL, allowed origin, region/workspace, auth-header scheme, API version, protocol family, and capability manifest. Configuration references the profile by ID; unresolved IDs fail validation. Custom base URLs come from user configuration, never a model response. The Qwen endpoint profile in the example is intentionally user-selected because region/workspace cannot be inferred from a token.

Model identifiers are explicit user configuration. Resolve floating aliases before a frozen review when possible; record both requested and returned model versions. If a provider exposes no immutable snapshot, record that limitation. LLM replay need not be deterministic; mechanical acceptance and stored transcript provenance remain reproducible independently of the model.

Users may configure any subset of providers. Only providers assigned to required roles, review slots, or explicitly selected fallbacks require credentials/capability checks. Unused registry entries must not force the user to obtain tokens for every service. The example includes all requested families to show available choices, not to require nine accounts.

The provider broker owns credentials. Agent prompts, candidate code, generated Lean tactics, review artifacts, and verifier subprocesses MUST NOT receive raw tokens. Repository configuration stores only references such as `env:OPENAI_API_KEY`, `keyring:verislop/claude-review`, or `secret-manager:team/provider-key`.

Proposed credential operations:

```bash
verislop auth add --provider openai --credential-id primary
verislop auth add --provider anthropic --credential-id claude-review
verislop auth list
verislop auth check --credential-id primary
verislop auth remove --credential-id primary
```

`auth add` uses a masked interactive prompt or a documented secret input channel; it MUST NOT require a token in a command-line argument. Tokens MUST NOT be committed, printed, included in manifests, placed in review transcripts, or used in hashes that expose the credential value. Credential metadata can record the logical ID, provider, auth profile, and rotation event without storing the secret in the run package.

The default local credential store is an OS-backed keyring where available; a headless installation uses environment/secret-manager references. The CLI does not invent an insecure plaintext fallback without an explicit user storage choice. Tokens are sent only to the configured authenticated endpoint, with no credential forwarding across host redirects. Custom endpoints are explicit configuration. Model-provider calls are networked operations isolated from offline verification.

`auth check` or `providers check` makes only the documented minimal authenticated check and reports whether it may incur a model call. Normal configuration parsing makes no unsolicited inference requests. Invalid credentials, rate limits, quota exhaustion, network errors, and model-not-found are distinct diagnostics.

A data policy controls which source files, prompts, proof terms, logs, and artifacts may be sent to each configured provider. Reviewers receive the scoped immutable review packet through the broker. Secret filtering is a defense in depth; precise file allowlists and exclusion of the credential store are the primary controls.

## 3. Agent assignments

Define named agent profiles once, then refer to them from roles and review tiers. Each effective profile resolves provider reference, model reference, sampling parameters, optional reasoning settings, context/output budgets, permitted tools, and request timeout/retry policy. The compact v0.1 configuration inherits unspecified settings from the pinned adapter/policy; the fully resolved manifest records them before dispatch. Provider-specific settings must be capability-validated rather than accepted as arbitrary agent instructions.

Roles include interpreter, formalizer, prover, implementer, repairer, reviewer, and review-report assembler. Users may assign one model to several roles or use different providers. A reviewer profile can be instantiated multiple times; each instance has a distinct identity, conversation, and ballot.

Every review tier contains one or more reviewer groups, each with `agent`, `count`, and `focus`. The configured tier total is the sum of all counts, verified before the run. Optional constraints include minimum distinct providers/models and prohibiting the author from reviewing its own candidate. Such diversity constraints are user policy; multiple instances of the same model do not imply statistically independent judgments.

Do not send a reviewer another reviewer's conclusion before its initial ballot. Parallel initial reviews reduce anchoring. A later explicit reconciliation pass may reveal findings, but both initial and revised ballots are preserved. Higher tiers receive the candidate, frozen scope, mechanical evidence, and lower-tier findings/dispositions, while forming their own verdicts.

Candidate source comments, repository instructions, retrieved documents, and previous model outputs are review data. They cannot override the review task, alter consensus policy, request credentials, or grant tool permissions. The broker supplies the review policy separately from untrusted packet contents.

## 4. Consensus and escalation

The default consensus policy is unanimity of every configured reviewer instance. An acceptance ballot is `ACCEPT`, rejection is `REJECT`, and inability to judge is `ABSTAIN`. Provider/runtime errors are execution outcomes, not ballots. A missing response, malformed ballot, timeout, or exhausted retry does not count as acceptance and cannot reduce the denominator.

Users MAY configure a fixed quorum policy, such as three accepts from four configured reviewers. It MUST explicitly define minimum accepts, whether every reviewer must respond, allowable soft rejections, and abstention handling before the run. Default `require_all_responses` is true. In all policies, unresolved blocking findings and any required mechanical failure veto acceptance; a vote cannot erase a counterexample accepted by a verifier.

Consensus is a deterministic calculation over immutable ballots, membership, target root, and policy. The mechanical consensus checker proves only that the configured voting rule was satisfied. It does not validate the technical truth of reviewers' opinions.

The tier state machine is:

```text
WAITING → RUNNING → TIER_ACCEPTED → next review tier
                    | final tier
                    └────────────→ REVIEW_ACCEPTED

RUNNING → CHANGES_REQUESTED → repair/new candidate → first review tier
RUNNING → INCOMPLETE         → bounded retry or blocked review
```

Every ACCEPT ballot MUST name the same `review_target_root` and exact review-scope ID. Every configured tier MUST reach TIER_ACCEPTED for that root. A reviewer passing only a subset cannot be counted as accepting the whole required scope unless the tier's frozen membership/coverage design explicitly composes those subsets.

A later-tier rejection never counts as final acceptance because lower tiers accepted. The repairer receives specific findings, proposes a change, reruns affected mechanical checks, creates a new immutable candidate root, and restarts review at the first tier. Even a change made only to satisfy the highest reviewer invalidates prior acceptance for the changed candidate. Reusing prior ballots across changed inputs is forbidden.

Within an unchanged candidate, a reconciliation round may add findings, discussion, and reasoned dispositions to this campaign's append-only review transcript. This transcript is excluded from the review target root, so ordinary escalation and rebuttal do not change the candidate being accepted. Each invocation records the exact transcript-prefix hash it received. New candidate bytes, formal claims, policy, or newly executed mechanical evidence change the base review target and restart the hierarchy. References to already-frozen evidence do not.

Ballots are keyed by campaign, checkpoint, tier, round, and reviewer slot. Exactly one active ballot per slot counts in a consensus round. A policy-authorized reconciliation round may supersede a prior ballot with an explicit prior-ballot reference; preserve both, and never choose the most favorable historical vote. Transport retries retain an idempotent request/slot identity and are permitted only for failed or malformed attempts. A valid REJECT cannot be retried away. An escalation certificate binds the active ballot set, round, findings dispositions, and transcript prefix; later acceptance-changing discussion requires a new consensus decision under the same frozen policy.

## 5. Review timing and contents

Users may attach the hierarchy to `interpretation`, `formal_contract`, `implementation`, or `release` checkpoints. Each checkpoint has its own finite scope and target root. Reviewing a draft's interpretation is not a review of later code. The default pipeline reviews the formal contract before downstream implementation generation and reviews the completed implementation/evidence before release.

Review packets include request provenance; explicit non-goals; obligation/state inventory; hypotheses and axioms; formal statement/dependency inventory; exact implementation changes when present; bridges; test coverage/results; evidence hashes; unresolved findings; and the claimed assurance boundary. Large packets use hashed retrieval with access logs; inability to inspect required material produces ABSTAIN/incomplete review, not ACCEPT on a summary alone.

Required packet sections and focus templates are checkpoint-aware. A formal-contract review inspects the contract and its acceptance evidence; it does not pretend to have reviewed an implementation that has not yet been generated. The release checkpoint adds the exact implementation, bridge, test, and closure evidence required by its endpoint policy.

Suggested escalating focus, configurable by the user:

- R0: requirement omissions, edge cases, error semantics, contradictions, and concrete counterexamples.
- R1: formalization fidelity, vacuity, hidden assumptions, theorem/implementation correspondence, and test/monitor adequacy.
- R2: complete artifact chain, trust/endpoint claims, cross-component failures, and remaining blocking findings.

Agent count is per tier, not a shared pool whose unfilled slots disappear. Tasks may be split by obligation, but the required claim coverage and final aggregation rule must be frozen. Review agents have read access plus sandboxed analysis tools. They submit patches or counterexamples as proposals; only the orchestrator admits changes through a new candidate.

## 6. Findings and repair

Every tier and reviewer MUST follow [concrete-counterexample review](adversarial-counterexamples.md). The CLI's v0.2 policy requires every instance, including an accepting reviewer, to construct at least one closed probe and record its finite search. `ACCEPT` requires `NO_COUNTEREXAMPLE_FOUND` and all probes independently replayed as `NOT_REPRODUCED`. This is bounded review completion, not a proof of the candidate. The full rich finding format remains proposed; the implemented subset admits typed target cases, exact missing request spans and named current mechanical failures.

A technical `REJECT` requires a finding tied to a constructed probe that the supervisor independently confirms against the named frozen claim and exact current inputs. Free-form reliability concerns and candidate-supplied observations or receipts cannot authorize rejection. Unsupported replay, infrastructure failure or an unreproduced rejection produces effective `ABSTAIN`; unanimity then remains incomplete, while a frozen quorum policy may allow configured abstentions. A current required mechanical failure still vetoes release regardless of reviewer votes.

The supervisor preserves the raw response and registered replay receipts, and rechecks both when tallying stored ballots. Historical v0.1 findings and votes retain their provenance but cannot satisfy the new review gates. A repair creates a new candidate/root and new checks; it does not erase an immutable failed claim or rewrite the earlier receipt.

The repairer MUST NOT weaken the contract, change assumptions, reduce reviewer counts, alter the quorum, replace difficult models, lower the bridge tier, or remove evidence to pass the existing run. Such proposals are explicit configuration/interpretation revisions with new roots. No silent fallbacks to a different provider/model are allowed. A user may predeclare fallback profiles; using one updates the reviewer identity and review target/configuration and is recorded before evaluating votes.

Proof search and review use finite budgets: maximum candidates, repair rounds, calls, per-call tokens, total tokens, concurrency, wall time, and optionally cost based on a pinned pricing snapshot. Unknown pricing cannot support an enforceable monetary guarantee; hard request/token limits still apply. Default retries are bounded and respect provider rate-limit guidance. Review does not spin indefinitely waiting for consensus.

A review budget exhausted with unresolved findings yields blocked review and no release acceptance. If an unavailable service or provider failure prevents required reviewers from running, the top-level run reports INFRASTRUCTURE_FAILURE when that is the reason evaluation cannot complete. If votes complete and reject the candidate, the top-level result is BLOCKED. Both categories preserve partial ballots and diagnostics.

## 7. Review target identity and determinism

`review_target_root` hashes the candidate artifact root, checkpoint scope, frozen mechanical evidence-package root available to reviewers, public claims, frozen review configuration, agent profiles, resolved model identities available before the campaign, prompt-template versions, and adapter versions. It excludes credentials and this campaign's ballots, findings, discussion, and dispositions, avoiding self-reference and root changes on ordinary escalation. Each reviewer invocation separately binds the exact append-only transcript prefix it can inspect. Returned model identity, request ID, and attempts are execution provenance; unexplained required-model mismatch blocks the affected slot.

The final closure inputs may include the completed review transcript and consensus certificate as immutable inputs. The registered review-policy verifier deterministically checks membership, coverage, roots, ballot validity, thresholds, no unresolved blockers, and all-tier acceptance. This check is a provenance/workflow claim. Its existence never promotes subjective review into semantic proof.

Clean-build determinism does not require a live LLM to produce identical ballots twice. Recheck the frozen stored ballots and mechanical artifacts. A new live review campaign gets a new campaign identity and preserves previous outcomes. The UI reports review status separately from the eight formal/implementation milestones.

## 8. Proposed configuration

The full machine-readable example is [review-config.json](../examples/review-config.json). Model references resolve through the user's environment; no current model name or API key is embedded in the example.

```json
{
  "bridge_tier": 2,
  "review": {
    "checkpoints": ["formal_contract", "release"],
    "review_tiers": [
      { "id": "R0", "reviewers": [
        { "agent": "fast-critic", "count": 3, "focus": "requirements_and_errors" }
      ], "consensus": { "mode": "unanimous" } },
      { "id": "R1", "reviewers": [
        { "agent": "formal-critic", "count": 2, "focus": "formalization_and_correspondence" },
        { "agent": "independent-critic", "count": 1, "focus": "counterexamples" }
      ], "consensus": { "mode": "unanimous" } },
      { "id": "R2", "reviewers": [
        { "agent": "final-critic", "count": 1, "focus": "complete_artifact_chain" }
      ], "consensus": { "mode": "unanimous" } }
    ]
  }
}
```

This gives three lower-tier reviewers, three intermediate reviewers, and one final reviewer per checkpoint. Reviewers within a tier run concurrently subject to provider limits. Tiers run sequentially. Agent profiles can point to any compatible configured provider, including repeated or different models.

## 9. Required acceptance cases

The future implementation MUST verify: credentials never enter agent prompts/logs; incompatible region/auth profiles fail explicitly; review counts equal configured membership; malformed/missing/duplicate ballots cannot pass consensus; lower-tier rejection prevents escalation; acceptance moves to exactly the next tier; final acceptance requires every tier; late rejection triggers repair/restart; artifact changes invalidate old votes; author/reviewer separation and diversity rules are enforced when configured; budgets terminate repair loops; unavailable models do not silently substitute; and unanimous ACCEPT cannot turn a failed Lean/bridge checker into PASS.

Provider-specific authentication and capability references are maintained in [provider-sources.md](provider-sources.md). Adapter compatibility tests against the pinned service/protocol are required before advertising support.
