# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Observe installed metadata using only the target interpreter's standard library."""

import importlib.metadata
import json
import os
import platform
import re
import sys


def marker_environment() -> dict[str, str]:
    """Record the complete target PEP 508 context without borrowing the caller's OS."""
    implementation = sys.implementation.version
    version = ".".join(str(value) for value in implementation[:3])
    if implementation.releaselevel != "final":
        version += implementation.releaselevel[0] + str(implementation.serial)
    return {
        "implementation_name": sys.implementation.name,
        "implementation_version": version,
        "os_name": os.name,
        "platform_machine": platform.machine(),
        "platform_release": platform.release(),
        "platform_system": platform.system(),
        "platform_version": platform.version(),
        "python_full_version": platform.python_version(),
        "platform_python_implementation": platform.python_implementation(),
        "python_version": ".".join(platform.python_version_tuple()[:2]),
        "sys_platform": sys.platform,
    }


def observe() -> dict[str, object]:
    """Preserve actual requirements/licenses and exclude installation paths."""
    distributions: list[dict[str, object]] = []
    for installed in importlib.metadata.distributions():
        metadata = installed.metadata
        name, version = metadata.get("Name"), metadata.get("Version")
        if name is None or not name.strip() or version is None or not version.strip():
            msg = "Installed distribution identity metadata is incomplete."
            raise ValueError(msg)
        licenses = metadata.get_all("License-Expression") or []
        declared = metadata.get("License")
        if (
            not licenses
            and declared is not None
            and declared.strip() not in {"UNKNOWN", ""}
        ):
            licenses = [declared]
        if not licenses:
            licenses = [
                classifier
                for classifier in metadata.get_all("Classifier", [])
                if classifier.startswith("License ::")
            ]
        distributions.append(
            {
                "name": re.sub(r"[-_.]+", "-", name).lower(),
                "version": version,
                "requires": list(installed.requires or []),
                "licenses": licenses,
            }
        )
    distributions.sort(key=lambda item: str(item["name"]))
    return {
        "python_version": platform.python_version(),
        "marker_environment": marker_environment(),
        "distributions": distributions,
    }


def main() -> None:
    """Emit one metadata observation; no packages or descriptive URLs are imported."""
    sys.stdout.write(json.dumps(observe(), sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
