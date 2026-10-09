"""Explicit value projection dispatch for independently accepted facet packages.

This supplies only a value DSL surface for critics/refutation. It establishes no
source facts and never turns a source-only guarantee into an executable oracle.
"""
from __future__ import annotations
from . import native_contract, source_contract


def value_package(package: dict) -> dict | None:
    if package.get("encoding") == native_contract.ENCODING:
        return native_contract.value_package(package)
    if package.get("encoding") == source_contract.ENCODING:
        return source_contract.value_package(package)
    return package


def statement_value_package(statement: dict) -> dict | None:
    if statement.get("representation") not in ("contract_dsl", "contract_facets", "source_facets"):
        return None
    return value_package(statement.get("formula_package", {}))
