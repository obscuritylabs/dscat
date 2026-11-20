# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Target assessments remain separate from intake validity and supplied authority."""

from typing import TYPE_CHECKING

from dscat.export.dcat_us_3 import assess_dcat
from dscat.export.odcs_3_2 import assess_odcs

if TYPE_CHECKING:
    from dscat.models.catalog import Catalog
    from dscat.models.configuration import ExportConfiguration
    from dscat.models.diagnostics import TargetReadiness


def assess_targets(
    catalog: Catalog | None, configuration: ExportConfiguration
) -> list[TargetReadiness]:
    """Evaluate implemented adapters without claiming pending target support."""
    return [
        assess_dcat(catalog, configuration),
        assess_odcs(catalog, configuration),
    ]
