"""Supervisor-owned implementation backends (docs/tier-2-closure-milestone.md §2).

A backend is selected only from the frozen tuple `(tier, target, endpoint, backend_version)`.
Backends never assign claim IDs, root kinds, verifier identities or pass predicates; the frozen
supervisor inventory supplies them.
"""
