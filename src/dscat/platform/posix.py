# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""POSIX address-space enforcement, with no resident-memory fallback."""

from dscat.intake.limits import DEFAULT_LIMITS, fail


class ResourceGuard:
    """Set both soft and hard address-space ceilings in the current process."""

    def install(self) -> None:
        """Refuse unavailable/refused controls; actual allocation probes follow."""
        import resource  # noqa: PLC0415 -- unavailable on Windows; native adapter only.

        maximum = DEFAULT_LIMITS.memory
        resource.setrlimit(resource.RLIMIT_AS, (maximum, maximum))
        if resource.getrlimit(resource.RLIMIT_AS) != (maximum, maximum):
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
