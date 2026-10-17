"""Explicit identity adapter for existing mocked transport-only workflow fixtures.

These tests already replace accepted-contract loading and native preview. Real
profile authentication, normalization and recording are tested separately in
``test_relation_authoring``; this helper must never be used in native fixtures.
"""
from contextlib import ExitStack
from unittest.mock import patch

from verislop import fsutil, relation_authoring


def mock_relation_authority():
    def identity(pkg, stage, authority, response, relation):
        fsutil.write_once(stage / "relation.json", relation)
        return relation
    scope = ExitStack()
    scope.enter_context(patch.object(relation_authoring, "prepare", return_value=object()))
    scope.enter_context(patch.object(relation_authoring, "normalize_attempt", side_effect=identity))
    return scope
