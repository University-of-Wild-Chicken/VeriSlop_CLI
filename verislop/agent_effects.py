"""Finite, structured Agent Effect DSL v0.1. No model text grants authority."""
from __future__ import annotations

from dataclasses import dataclass
import re
from . import canonical


class EffectError(ValueError):
    pass


# Input kind, untrusted output kind, required host-configured profile, effects.
SIGNATURES = {
    'prove': ('lean_challenge', 'proof_proposal', 'proof_sandbox', frozenset({'read', 'infer', 'propose_proof'})),
    'prove-vscore': ('vscore_goal', 'proof_proposal', 'proof_sandbox', frozenset({'read', 'infer', 'propose_proof'})),
    'review': ('review_packet', 'ballot_proposal', 'review_readonly', frozenset({'read', 'infer', 'propose_ballot'})),
    'generate': ('accepted_contract', 'candidate_proposal', 'candidate_writer', frozenset({'read', 'infer', 'propose_candidate'})),
}


def natural(value, label, positive=False):
    if type(value) is not int or value < int(positive):
        raise EffectError(label + ': expected ' + ('positive' if positive else 'nonnegative') + ' integer')
    return value


def exact(obj, fields):
    if type(obj) is not dict or set(obj) != set(fields):
        raise EffectError('missing or unknown AST fields')


@dataclass(frozen=True)
class Artifact:
    kind: str
    identity: str
    sha256: str


@dataclass(frozen=True)
class Operation:
    op: str
    agent: str
    instance: str
    artifact: Artifact
    effects: frozenset[str]
    output_tokens: int
    retries: int


@dataclass(frozen=True)
class Plan:
    steps: tuple[Operation, ...]
    max_calls: int
    max_output_tokens: int
    max_attempts: int


def parse(data) -> Plan:
    """Strict JSON/structured AST parser; rejects unknown fields and duplicate JSON keys."""
    if isinstance(data, str):
        data = canonical.loads(data)
    exact(data, ('version', 'steps', 'limits'))
    if data['version'] != '0.1' or type(data['steps']) is not list or not data['steps']:
        raise EffectError('expected nonempty v0.1 sequential plan')
    exact(data['limits'], ('calls', 'output_tokens', 'attempts'))
    limits = [natural(data['limits'][k], k) for k in ('calls', 'output_tokens', 'attempts')]
    steps = []
    for row in data['steps']:
        exact(row, ('op', 'agent', 'instance', 'artifact', 'effects', 'output_tokens', 'retries'))
        exact(row['artifact'], ('kind', 'identity', 'sha256'))
        if type(row['effects']) is not list or any(type(e) is not str for e in row['effects']) or len(set(row['effects'])) != len(row['effects']):
            raise EffectError('effects must be distinct strings')
        steps.append(Operation(row['op'], row['agent'], row['instance'], Artifact(**row['artifact']),
                               frozenset(row['effects']), natural(row['output_tokens'], 'output_tokens', True),
                               natural(row['retries'], 'retries')))
    return Plan(tuple(steps), *limits)


def check(plan: Plan, conf: dict) -> frozenset[str]:
    """Rechecks even directly constructed dataclasses. Configuration is trusted authority.

    Sequence composes by effect union and additive calls/output/transport attempts.
    Outputs are proposals, never accepted artifacts or new capabilities.
    """
    if not isinstance(plan, Plan) or type(plan.steps) is not tuple or not plan.steps:
        raise EffectError('expected nonempty Plan')
    for value in (plan.max_calls, plan.max_output_tokens, plan.max_attempts):
        natural(value, 'plan limit')
    budget = conf['review']['budgets']
    calls, output, attempts, effects = {}, 0, 0, frozenset()
    for s in plan.steps:
        if not isinstance(s, Operation) or type(s.op) is not str or s.op not in SIGNATURES:
            raise EffectError('unknown operation')
        kind, _, profile, required = SIGNATURES[s.op]
        if not isinstance(s.artifact, Artifact):
            raise EffectError('artifact required')
        a = s.artifact
        if a.kind != kind or type(a.identity) is not str or not a.identity.strip() or type(a.sha256) is not str or not re.fullmatch('sha256:[0-9a-f]{64}', a.sha256):
            raise EffectError('missing identity, digest, or wrong artifact type')
        if type(s.agent) is not str or s.agent not in conf['agents'] or type(s.instance) is not str or not s.instance.strip():
            raise EffectError('unknown agent or empty instance')
        agent = conf['agents'][s.agent]
        if agent['tool_profile'] != profile or type(s.effects) is not frozenset or s.effects != required:
            raise EffectError('permission escalation or invalid effect signature')
        natural(s.output_tokens, 'output_tokens', True)
        natural(s.retries, 'retries')
        if s.output_tokens != agent['max_output_tokens'] or s.retries != budget['max_provider_retries']:
            raise EffectError('resource annotation must match actual Broker configuration')
        calls[s.instance] = calls.get(s.instance, 0) + 1
        output += s.output_tokens
        attempts += 1 + s.retries
        effects |= required
    if (len(plan.steps) > plan.max_calls or output > plan.max_output_tokens or attempts > plan.max_attempts
            or output > budget['max_total_tokens'] or max(calls.values()) > budget['max_calls_per_instance']):
        raise EffectError('budget exceeded')
    return effects


def review_call(broker, agent, instance, system, user, checkpoint, target_root, conf=None):
    """Opt-in lowering of one host-authored review operation to the unchanged Broker.

    Binds the exact outbound payload as data, not as an authority declaration.
    Does not execute tools or attest to the contents of the target root.
    """
    actual_conf = broker.r.conf
    if conf is not None and conf != actual_conf:
        raise EffectError('review configuration differs from the dispatch Broker')
    conf = actual_conf
    if conf.get('agent_effect_dsl', {}).get('enabled') is True:
        artifact = Artifact('review_packet', target_root, canonical.digest_json({'target': target_root, 'system': system, 'user': user}))
        # A caller can explicitly supply a shared/custom Budget to Broker. Check
        # its actual limits, including retries, rather than the config defaults.
        runtime_budget = broker.budget
        b = {**conf['review']['budgets'],
             'max_calls_per_instance': natural(runtime_budget.max_calls_per_instance, 'broker call limit'),
             'max_total_tokens': natural(runtime_budget.max_total_tokens, 'broker token limit'),
             'max_provider_retries': natural(runtime_budget.max_retries, 'broker retries')}
        effective_conf = {**conf, 'review': {**conf['review'], 'budgets': b}}
        n = conf['agents'][agent]['max_output_tokens']
        step = Operation('review', agent, instance, artifact, SIGNATURES['review'][3], n, b['max_provider_retries'])
        check(Plan((step,), 1, n, 1 + step.retries), effective_conf)
    return broker.call(agent, instance, system, user, f'review:{checkpoint}')
