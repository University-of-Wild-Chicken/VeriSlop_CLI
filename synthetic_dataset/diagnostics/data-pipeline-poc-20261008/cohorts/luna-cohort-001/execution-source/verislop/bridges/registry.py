"""Supervisor-owned relation capabilities.

Registration in the general verifier inventory authenticates a *declared issuer*; a relation
template additionally needs an implemented checker that independently checks the actual
module, complete dependency closure, exact proposition, allowed axioms and already checked
premises. Package JSON cannot add entries: a relation artifact only *names* a template, and
the supervisor assigns the registered checker during preparation.

* `vscore.reference_refinement/0.1` -> `verislop.vscore-checker` (bridges/vscore_checker.py):
  exact VSCore source parse/typing, extensional refinement of accepted reference functions,
  input coverage and mechanically derived transfer of the covered accepted obligations.
"""

from types import MappingProxyType

from .. import canonical

SEMANTIC_CHECKERS = MappingProxyType({
    "vscore.reference_refinement/0.1": MappingProxyType({
        "verifier_id": "verislop.vscore-checker",
        "relation_format": "verislop.vscore-relation/0.1",
        "tier": 2,
        "endpoint": "restricted_source",
    }),
})


def semantic_checker(template_id: str):
    """Return the registered checker descriptor of a relation template, or None."""
    return SEMANTIC_CHECKERS.get(template_id)


def relation_checker(relation_bytes: bytes) -> str | None:
    """Registered verifier assigned to a relation artifact, or None (never raises).

    The artifact must be canonical JSON naming a registered template in that template's own
    relation format. Anything else stays with the unavailable semantic verifier.
    """
    try:
        value = canonical.loads(relation_bytes)
    except Exception:  # noqa: BLE001 - an unparseable relation names no template
        return None
    if not isinstance(value, dict) or not isinstance(value.get("template"), str):
        return None
    entry = SEMANTIC_CHECKERS.get(value["template"])
    if entry is None or value.get("format") != entry["relation_format"]:
        return None
    return entry["verifier_id"]
