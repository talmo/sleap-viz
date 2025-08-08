"""Very small smoke test to ensure package imports and CLI wiring."""

from __future__ import annotations

import importlib


def test_import() -> None:
    mod = importlib.import_module("sleap_viz")
    assert hasattr(mod, "__version__")
