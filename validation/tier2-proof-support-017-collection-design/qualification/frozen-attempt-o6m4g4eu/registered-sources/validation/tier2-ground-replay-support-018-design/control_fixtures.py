"""One predeclared construction-failure mutation of the original bounded fixture."""
import copy
from verislop import canonical, dsl
from verislop.reify import _Denoter
from verislop.targets import vscore3_target as target


def construction_failure(explore):
    identity, _, _ = explore.fixture('identity')
    bounded, _, _ = explore.fixture('bounded')
    formula = copy.deepcopy(bounded.obligations[0].formula)
    formula['body']['right']['body'] = {'tag': 'le', 'left': {'tag': 'var', 'index': 0},
                                      'right': {'tag': 'nat', 'value': '3'}}
    profile = {'profile_id': 'ground018-unrelated', 'dsl': dsl.ENCODING_V2,
               'symbols': {'transform': {'lean_decl': 'VeriSlopContract.reference', 'args': ['Int'], 'result': 'Int'}}}
    spec = target.build_goal(identity.source_bytes, {'bindings': [{'symbol': 'transform', 'entry': 'transform'}]},
        profile, {'GENERIC': {'formula': formula, 'source_facets': [],
        'lean_symbol': 'VeriSlopContract.guarantee', 'statement_hash': canonical.digest_json(formula)}})
    exact = target.Printer().term(_Denoter(dsl.Profile.from_json(profile)).formula(formula, []))
    contract = ('import VSCore3\nnamespace VeriSlopContract\ndef reference (x : Int) : Int := x\n'
        'theorem guarantee : ' + exact + ' := by\n  intro x\n  constructor\n  · rfl\n'
        '  · intro n hlo hhi\n    exact Nat.le_of_lt hhi\nend VeriSlopContract\n')
    return spec, contract
