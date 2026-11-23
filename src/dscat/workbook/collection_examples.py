# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Fixed synthetic metadata using public tool names; never real source records."""

from datetime import date

ExampleValue = str | int | float | date


def example_rows() -> list[dict[str, ExampleValue]]:
    """Return the fixed seven-row scenario with invented metadata."""
    base: dict[str, ExampleValue] = {
        "Data owner / accountable team *": "Example evidence team",
        "PII *": "Yes",
        "PHI *": "Unknown",
        "CUI *": "Unknown",
        "PCII *": "Unknown",
        "ISVI *": "Unknown",
        "Other sensitive data *": "Unknown",
        "Submitted by / accountable for entry *": "Example Contributor A",
        "Completed on *": date(2026, 1, 15),
        "Retention status": "Proposed",
        "Retention decision authorized by": "Not yet authorized",
        "Current amount basis": "Estimate",
        "Per-run amount basis": "Estimate",
        "Typical runs": 5,
        "Per": "week",
        "Access pattern": "Bulk or batch",
    }
    return [
        base
        | {
            "Collection name *": "Windows forensic disk images",
            "Collection description": (
                "E01 dead-box disk images of Windows computers; recurring "
                "collection, not individual devices or investigations."
            ),
            "Current location": "Example evidence image store",
            "Amount held now": 5000,
            "Current unit": "GB",
            "Retention days": 30,
            "Retention status": "Confirmed",
            "Retention decision authorized by": "Example Approver A (fictional)",
            "Who uses this collection": "Example artifact processing team",
            "Used for": "Preserve source material and extract selected artifacts",
            "Generating process": "FTK Imager acquisition",
            "How it is generated": (
                "Create an E01 image from source media. Invented workload: five "
                "images per week, averaging 250 GB of stored image output each. "
                "Source media are the physical origin, not a registered collection "
                "here."
            ),
            "New amount per run": 250,
            "Per-run unit": "GB",
        },
        base
        | {
            "Collection name *": "Extracted Windows event logs",
            "Collection description": (
                "EVTX files exported from Windows images; original artifact files, "
                "not normalized timeline events."
            ),
            "Current location": "Example artifact store",
            "Amount held now": 20,
            "Current unit": "GB",
            "Retention days": 90,
            "Who uses this collection": "Example timeline processing team",
            "Used for": "Parse event timestamps and activity into a combined timeline",
            "Generating process": "FTK Imager selected-file export",
            "How it is generated": (
                "Select and export Windows event-log files from each image without "
                "changing the image. One export batch per processed image."
            ),
            "Source collections": "Windows forensic disk images",
            "New amount per run": 1,
            "Per-run unit": "GB",
        },
        base
        | {
            "Collection name *": "Extracted registry artifacts",
            "Collection description": (
                "Windows registry hive files exported from disk images for "
                "subsequent event parsing."
            ),
            "Current location": "Example artifact store",
            "Amount held now": 10,
            "Current unit": "GB",
            "Retention days": 90,
            "Who uses this collection": "Example timeline processing team",
            "Used for": "Contribute registry-derived activity to timeline analysis",
            "Generating process": "FTK Imager selected-file export",
            "How it is generated": (
                "Select and export relevant registry hive files from each image. "
                "Same export activity as the other artifact collections; quantities"
                " describe only this output."
            ),
            "Source collections": "Windows forensic disk images",
            "New amount per run": 0.5,
            "Per-run unit": "GB",
        },
        base
        | {
            "Collection name *": "Extracted browser-history artifacts",
            "Collection description": (
                "Browser-history database files and relevant companion files "
                "exported from disk images."
            ),
            "Data owner / accountable team *": "Unknown",
            "PHI *": "Unknown",
            "Current location": "Example artifact store",
            "Amount held now": 2,
            "Current unit": "GB",
            "Retention days": 90,
            "Who uses this collection": "Example timeline processing team",
            "Used for": "Add browsing activity to timeline analysis",
            "Generating process": "FTK Imager selected-file export",
            "How it is generated": (
                "Export selected browser-history artifacts. Accountable ownership "
                "and typical output volume still need clarification. Existing "
                "holdings are estimated separately."
            ),
            "Source collections": "Windows forensic disk images",
            "Per-run amount basis": "Unknown",
        },
        base
        | {
            "Collection name *": "Indicator-reference snapshots",
            "Collection description": (
                "Versioned MISP CSV exports of curated domain, IP-address and hash "
                "indicators with reference identifiers; no underlying sample "
                "records are included."
            ),
            "Data owner / accountable team *": "Example reference curation team",
            "PII *": "No",
            "PHI *": "No",
            "CUI *": "No",
            "PCII *": "No",
            "ISVI *": "No",
            "Other sensitive data *": "Yes",
            "Other category / uncertainty": (
                "Fictional source-sharing restriction on the curated reference set;"
                " not a claim about MISP exports generally."
            ),
            "Submitted by / accountable for entry *": "Example Contributor B",
            "Current location": "Example reference snapshot store",
            "Amount held now": 250,
            "Current unit": "MB",
            "Retention days": 365,
            "Who uses this collection": "Example timeline analysis team",
            "Used for": (
                "Reproduce which reference indicators were available when events "
                "were annotated"
            ),
            "Generating process": "MISP reference export",
            "How it is generated": (
                "Export a curated indicator snapshot from MISP as CSV. One "
                "fictional snapshot per week; stored CSV sizes are illustrative "
                "byte-size estimates, not conversions from indicator counts. Retain"
                " the snapshot identifier used during analysis."
            ),
            "New amount per run": 50,
            "Per-run unit": "MB",
            "Typical runs": 1,
            "Per": "week",
        },
        base
        | {
            "Collection name *": "Plaso timeline events",
            "Collection description": (
                "Parsed timestamped events in Plaso storage, combining event logs, "
                "registry artifacts and browser history."
            ),
            "Data owner / accountable team *": "Example analysis team",
            "Current location": "Example parsed timeline store",
            "Amount held now": 40,
            "Current unit": "GB",
            "Retention days": 180,
            "Who uses this collection": "Example timeline analysis team",
            "Used for": (
                "Provide a unified chronological event collection "
                "for import and analysis"
            ),
            "Generating process": "Plaso log2timeline parsing",
            "How it is generated": (
                "Parse selected extracted artifacts into Plaso event storage. One "
                "combined parsing batch per original image, using each available "
                "artifact collection. Output amount is illustrative, not a parser "
                "expansion guarantee."
            ),
            "Source collections": (
                "Extracted Windows event logs; Extracted registry artifacts; "
                "Extracted browser-history artifacts"
            ),
            "New amount per run": 2,
            "Per-run unit": "GB",
        },
        base
        | {
            "Collection name *": "Timesketch annotated timeline",
            "Collection description": (
                "Indexed timeline events with event-level indicator-match tags and "
                "analyst comments, plus the reference snapshot identity used."
            ),
            "Data owner / accountable team *": "Example analysis team",
            "Other sensitive data *": "Yes",
            "Other category / uncertainty": (
                "Fictional internal analyst notes; sensitivity is not reduced "
                "merely because the collection is derived."
            ),
            "Submitted by / accountable for entry *": "Example Contributor B",
            "Current location": "Example timeline analysis store",
            "Current amount basis": "Unknown",
            "Retention days": 365,
            "Who uses this collection": "Example investigation analysts",
            "Used for": (
                "Review event chronology and indicator-match annotations together"
            ),
            "Access pattern": "Interactive search",
            "Generating process": "Timesketch import and analyst-assisted annotation",
            "How it is generated": (
                "Import Plaso events; analysts search against a saved MISP "
                "reference snapshot and tag/comment matching events. Snapshot "
                "identity provides reference lineage. No automatic connector is "
                "assumed. Five new timeline batches per week; annotation reruns do "
                "not create new batches. Indexed size and expansion are unknown."
            ),
            "Source collections": (
                "Plaso timeline events; Indicator-reference snapshots"
            ),
            "Per-run amount basis": "Unknown",
        },
    ]
