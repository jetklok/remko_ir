"""Pytest fixtures for the Remko IR custom integration."""

import pytest


@pytest.fixture(autouse=True)
def enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading integrations from custom_components."""
