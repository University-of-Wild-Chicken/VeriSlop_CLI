"""VeriSlop CLI — Verify the Slop.

The package implements the contract-first verification pipeline described in
``docs/specification.md``. Candidate generators (LLM agents, humans, existing code) only
ever *propose* artifacts; registered verifiers in this package decide what has been
established and record immutable evidence.
"""

__version__ = "0.1.0"
SCHEMA_VERSION = "0.1"
