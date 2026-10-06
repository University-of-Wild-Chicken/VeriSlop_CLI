"""Candidate implementation of the bounded increment contract.

Serialization profile python-v0_1: Nat is a non-negative int, an enumeration constructor is
its name as a str, and Result(IncrementError, Nat) is ("ok", n) or ("error", "limitReached").
This file is an ordinary candidate: VeriSlop links and tests it; it is not trusted.
"""


def increment(limit, input):
    if input < limit:
        return ("ok", input + 1)
    return ("error", "limitReached")
