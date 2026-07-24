"""Shared fixtures / harness setup for the samsungwam test suite.

Runs against whichever checkout of the repo this tests/ directory lives in
(the all-fixes working tree, or a copy dropped into a `master` worktree), so
the same tests exercise both branches' `custom_components/samsungwam/`.
"""

from __future__ import annotations

import os
import sys

import pytest

# Make the checkout root importable so `import custom_components.samsungwam`
# resolves to THIS tree's integration code (differs per worktree/branch).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of custom integrations in every test (HA harness)."""
    yield
