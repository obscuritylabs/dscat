# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Package metadata and internal version consistency checks."""

from importlib.metadata import metadata, version

from dscat import __version__


def test_package_metadata() -> None:
    """Installed metadata retains the declared version and proprietary license."""
    assert version("dscat") == __version__ == "0.1.0"
    assert metadata("dscat")["License-Expression"] == "LicenseRef-Proprietary"
    assert metadata("dscat")["License-File"] == "LICENSE"
