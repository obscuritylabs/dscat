# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Target assessments remain separate from intake validity and supplied authority."""

from typing import TYPE_CHECKING

from dscat.export.dcat_us_3 import assess_dcat
from dscat.models.diagnostics import TargetReadiness

if TYPE_CHECKING:
    from dscat.models.catalog import Catalog
    from dscat.models.configuration import ExportConfiguration


def assess_targets(
    catalog: Catalog | None, configuration: ExportConfiguration
) -> list[TargetReadiness]:
    """Evaluate implemented adapters without claiming pending target support."""
    return [
        assess_dcat(catalog, configuration),
        TargetReadiness(target="odcs-3.2", state="unexamined"),
    ]
