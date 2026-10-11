"""Shared direct-mode test configuration for Quantyra."""

import pytest


@pytest.fixture(autouse=True)
def _reset_contract_registry():
    """Allow every direct test to deploy the contract independently."""
    yield
    try:
        import genlayer.gl.genvm_contracts as contracts
    except ImportError:
        return
    contracts.__known_contract__ = None
