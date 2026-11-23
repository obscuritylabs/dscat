# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Versioned collection intake labels and ordinary Excel guidance."""

COLUMN_SPECS: tuple[tuple[str, int, str], ...] = (
    (
        "Collection name *",
        28,
        (
            "Name this recurring collection once. Register it even when no "
            "generating process is known."
        ),
    ),
    (
        "Collection description",
        36,
        (
            "Briefly describe what this collection contains. Plain language is "
            "enough; do not include sensitive examples."
        ),
    ),
    (
        "Current location",
        28,
        (
            "System or storage label is enough. Avoid credentials and sensitive"
            " paths. Give separately stored copies distinct names if they need "
            "separate planning."
        ),
    ),
    (
        "Data owner / accountable team *",
        30,
        (
            "Who has authority to make decisions about this data? Give a "
            "person, role, or team. This is separate from the submitter and "
            "day-to-day custodian. If unknown enter Unknown."
        ),
    ),
    (
        "PII *",
        15,
        (
            "Personally identifiable information. Choose Yes, No, or Unknown "
            "based on what is reported or known. Do not paste sensitive "
            "examples."
        ),
    ),
    (
        "PHI *",
        15,
        (
            "Protected health information. Choose Yes, No, or Unknown; do not "
            "infer a formal legal determination merely from the presence of "
            "health-related data."
        ),
    ),
    (
        "CUI *",
        15,
        (
            "Controlled Unclassified Information. Choose Yes, No, or Unknown. "
            "Categories can overlap; ISVI is a CUI category. Record known "
            "designations, not a new formal designation."
        ),
    ),
    (
        "PCII *",
        15,
        (
            "Protected Critical Infrastructure Information. Choose Yes for a "
            "known applicable designation; choose Unknown if protection status "
            "is uncertain. This form does not perform PCII validation."
        ),
    ),
    (
        "ISVI *",
        15,
        (
            "Information Systems Vulnerability Information, a CUI category. "
            "Choose Yes, No, or Unknown based on known status. Do not include "
            "vulnerability details."
        ),
    ),
    (
        "Other sensitive data *",
        20,
        (
            "Choose Yes, No, or Unknown. Multiple sensitive categories can "
            "apply to the same collection. No in one category does not imply "
            "public release approval."
        ),
    ),
    (
        "Other category / uncertainty",
        30,
        (
            "If Other sensitive data is Yes, name the category or restriction "
            "without including sensitive content. Use this field for "
            "uncertainty or pending review, too."
        ),
    ),
    (
        "Submitted by / accountable for entry *",
        32,
        (
            "Person responsible for the correctness and completeness of this "
            "row. This is not necessarily the data owner. Repeat on copied rows"
            " and change where another person takes responsibility."
        ),
    ),
    (
        "Completed on *",
        20,
        (
            "Date this row was completed or its current answers were last "
            "reviewed. Enter an Excel date displayed as YYYY-MM-DD. This is not"
            " the data arrival date and does not start the retention clock."
        ),
    ),
    (
        "Amount held now",
        19,
        (
            "Existing amount held for this collection, separate from new "
            "production. Approximation is welcome. Leave blank if unknown. Zero"
            " means known zero."
        ),
    ),
    (
        "Current unit",
        15,
        (
            "Choose KB, MB, GB, TB, or PB. Storage units use decimal multiples:"
            " 1 GB = 1,000 MB. If storage size is unknown, leave the quantity "
            "blank and choose Unknown as its amount basis."
        ),
    ),
    (
        "Current amount basis",
        20,
        (
            "Estimate, Measured, or Unknown. Leave unknown amounts blank; never"
            " replace them with zero."
        ),
    ),
    (
        "Who uses this collection",
        27,
        (
            "Who uses this collection? Team, role, or consuming system. Leave "
            "blank if unknown."
        ),
    ),
    (
        "Used for",
        31,
        (
            "What do consumers do with this collection? Short phrases are "
            "enough. Explain Mixed or Other access patterns here."
        ),
    ),
    (
        "Access pattern",
        24,
        (
            "Closest known access pattern for this collection. This describes "
            "use, not access authorization."
        ),
    ),
    (
        "Retention days",
        18,
        (
            "Later follow-up. Whole days from each batch arriving at the "
            "destination. Each collection, including derived outputs, has its "
            "own rule. Blank means undetermined; zero means immediate expiry."
        ),
    ),
    (
        "Retention status",
        23,
        (
            "Not yet determined, Proposed, or Confirmed. Registration can be "
            "incomplete; storage acceptance needs a confirmed duration. This "
            "prototype does not enforce acceptance."
        ),
    ),
    (
        "Retention decision authorized by",
        34,
        (
            "Person who authorized the stated retention duration, or an accountable "
            "role with a named holder. Separate from owner and submitter. Leave "
            "blank if unknown, or record Unknown / Not yet authorized as appropriate. "
            "Reported attribution is not verified approval or permission to delete."
        ),
    ),
    (
        "Generating process",
        28,
        (
            "Optional. Name the recurring activity producing this collection. "
            "Leave blank if unknown or not applicable. For several generating "
            "processes, name them briefly and explain in How it is generated; "
            "keep one collection row."
        ),
    ),
    (
        "How it is generated",
        35,
        (
            "Optional. Brief explanation of how this collection is produced. "
            "Describe multiple generating processes here without duplicating "
            "the collection row."
        ),
    ),
    (
        "Source collections",
        32,
        (
            "Optional. Name known input collections in plain text, separated by"
            " semicolons. Match registered names where practical. Inputs do not"
            " need to be registered. If sources differ by process, explain "
            "under How it is generated."
        ),
    ),
    (
        "New amount per run",
        19,
        (
            "Typical amount of this collection newly produced per run of the "
            "named generating process, not consumed input or existing storage. "
            "Leave blank if unknown or several processes cannot be summarized "
            "meaningfully."
        ),
    ),
    (
        "Per-run unit",
        15,
        (
            "Choose KB, MB, GB, TB, or PB. Storage units use decimal multiples:"
            " 1 GB = 1,000 MB. If storage size is unknown, leave the quantity "
            "blank and choose Unknown as its amount basis."
        ),
    ),
    (
        "Per-run amount basis",
        20,
        "Estimate, Measured, or Unknown for New amount per run only.",
    ),
    (
        "Typical runs",
        17,
        (
            "Average number of runs of the named generating process in the "
            "selected period. Decimal averages are acceptable. Leave blank if "
            "unknown or multiple processes cannot be summarized meaningfully."
        ),
    ),
    (
        "Per",
        17,
        (
            "Frequency period for the optional generating process. Choose day, "
            "week, month, year, On demand, or Unknown. Leave blank if no "
            "generation details are supplied."
        ),
    ),
)

FIELD_NAMES: tuple[str, ...] = (
    "name",
    "description",
    "location_label",
    "owner",
    "pii",
    "phi",
    "cui",
    "pcii",
    "isvi",
    "other",
    "other_explanation",
    "submitted_by",
    "completed_on",
    "current_value",
    "current_unit",
    "current_basis",
    "consumers",
    "use",
    "access_pattern",
    "retention_days",
    "retention_status",
    "retention_authorized_by",
    "process",
    "explanation",
    "source_names",
    "per_run_value",
    "per_run_unit",
    "per_run_basis",
    "typical_runs",
    "period",
)

HEADERS = tuple(c[0] for c in COLUMN_SPECS)
LEGACY_HEADERS = tuple(h for h in HEADERS if h != "Retention decision authorized by")
HEADER_FIELDS = dict(zip(HEADERS, FIELD_NAMES, strict=True))
GROUPS: tuple[tuple[int, int, str, str], ...] = (
    (1, 3, "COLLECTION", "17354A"),
    (4, 11, "AUTHORITY & SENSITIVITY · FIRST PASS", "8A5822"),
    (12, 13, "ENTRY RESPONSIBILITY", "635480"),
    (14, 16, "CURRENT VOLUME", "147D80"),
    (17, 19, "COLLECTION USE", "315B84"),
    (20, 22, "RETENTION · FOLLOW-UP", "687563"),
    (23, 30, "HOW IT IS GENERATED · OPTIONAL", "526575"),
)

GUIDANCE: tuple[tuple[str, str], ...] = (
    ("COLLECTION INTAKE", "One collection per row • {mode}"),
    (
        "Example assumptions",
        (
            "All numbers are invented teaching values, not measured data, tool "
            "benchmarks, or capacity guarantees. Five images per week at 250 GB"
            " per image; every image is processed once in this scenario. "
            "Current holdings are separate snapshots, not calculated retention "
            "targets."
        ),
    ),
    (
        "Example retention and sensitivity",
        (
            "The first example duration is fictionally Confirmed; the others are "
            "Proposed. Durations illustrate "
            "independent rules, not forensic retention recommendations or "
            "deletion authority. Sensitivity responses describe fictional "
            "scenarios; never infer them from a tool or file type."
        ),
    ),
    (
        "Start with the collection",
        (
            "Use Intake only. Each row describes one recurring collection: "
            "name, contents, location, authority, sensitivity, amount, use, and"
            " retention. No process information is required to register it."
        ),
    ),
    (
        "First pass · required *",
        (
            "Supply collection name, accountable data owner/team, six "
            "sensitivity responses, submitter, and completion date. Unknown is "
            "acceptable for authority and sensitivity. Other fields can be "
            "enriched later."
        ),
    ),
    (
        "Row responsibility",
        (
            "Submitted by / accountable for entry identifies the person "
            "responsible for these answers. Completed on is when the row was "
            "completed or reviewed. Both are distinct from the data owner and "
            "data arrival time."
        ),
    ),
    (
        "One collection, one row",
        (
            "A shared collection appears once even if several processes use it."
            " Give separately stored copies distinct names if they need "
            "separate planning. Copy a row only to start a different "
            "collection, then update all relevant values."
        ),
    ),
    (
        "How it is generated · optional",
        (
            "The last group asks for a generating process, how it works, source"
            " collections, new output amount per run, and frequency. Leave this"
            " entire group blank when unknown or not applicable."
        ),
    ),
    (
        "Sources and several processes",
        (
            "Source collections is optional plain text: separate known names "
            "with semicolons. Match existing names when practical; no linking "
            "is required. For multiple generating processes, describe them "
            "briefly in the same row. Leave per-run quantities blank if one "
            "meaningful average cannot describe them."
        ),
    ),
    (
        "Sensitivity",
        (
            "All six categories need Yes, No, or Unknown. Multiple Yes "
            "responses are valid. Other sensitive data = Yes needs a category "
            "description. Do not include actual sensitive records or examples."
        ),
    ),
    (
        "Reported, not certified",
        (
            "Sensitivity answers report known or suspected status; they do not "
            "establish formal designation, PCII validation, permission to "
            "disclose, or storage authorization. ISVI is a CUI category. No or "
            "blank never means approved for public release."
        ),
    ),
    (
        "Current versus new volume",
        (
            "Amount held now is existing storage for this collection. New "
            "amount per run is newly produced output of its optional generating"
            " process. Do not record consumed input volume there. Do not add "
            "duplicate collection rows for downstream uses."
        ),
    ),
    (
        "Units and uncertainty",
        (
            "Choose a unit and Measured, Estimate, or Unknown for each supplied"
            " quantity. Leave unknown quantities blank. Decimal storage units: "
            "KB, MB, GB, TB, PB. No automatic conversions or forecasts."
        ),
    ),
    (
        "Collection use",
        (
            "Record who uses this collection, what they use it for, and how "
            "they access it. Short phrases are enough. Access pattern describes"
            " use, not access authorization."
        ),
    ),
    (
        "Retention · follow-up",
        (
            "Record whole days from each batch arriving at the destination. "
            "Derived collections have independent rules. Not yet determined or "
            "Proposed can be registered; acceptance for storage needs a "
            "confirmed duration. The form does not enforce that gate or "
            "authorize deletion."
        ),
    ),
    (
        "Navigation",
        (
            "Color bands separate topics. Row 5 has filterable headers with "
            "help in comments; entry starts at row 6. Collection name stays "
            "visible while scrolling. All entry cells remain editable."
        ),
    ),
    (
        "Worked example",
        (
            "Seven collections follow FTK Imager acquisition and file export, "
            "Plaso timeline parsing, a separate MISP indicator snapshot, and "
            "Timesketch annotation. Source collections names show lineage. "
            "Quantities and all people, teams, locations, sensitivity "
            "responses, dates, and retention decisions are fictional."
        ),
    ),
    (
        "Example lineage",
        (
            "Windows forensic disk images → three extracted artifact "
            "collections → Plaso timeline events → Timesketch annotated "
            "timeline. Indicator-reference snapshots are an additional parent "
            "of the annotated timeline; references are inputs, not generated "
            "matches."
        ),
    ),
    (
        "Example process boundaries",
        (
            "FTK Imager exports selected artifact files; Plaso parses event "
            "records. Timesketch matching in this example is analyst-assisted "
            "search, event tagging and comments against a saved MISP export. No"
            " automatic MISP-to-Timesketch connector is assumed."
        ),
    ),
    (
        "Example storage boundaries",
        (
            "Plaso event storage and Timesketch indexed analysis storage are "
            "distinct holdings. A Timesketch sketch references timeline data: "
            "annotation does not imply another complete copied index. "
            "Index/storage expansion is Unknown; annotation reruns are not new "
            "incoming batches."
        ),
    ),
    (
        "FTK Imager reference",
        (
            "Official file-export documentation: "
            "https://d1kpmuwb7gvu1i.cloudfront.net/Imager/8.2/Exterro%20FTK%20Imager%208.2%20-%20User%20Guide%20.pdf"
        ),
    ),
    (
        "Plaso reference",
        (
            "Official event-extraction documentation: "
            "https://plaso.readthedocs.io/en/latest/sources/user/Using-log2timeline.html"
        ),
    ),
    (
        "MISP reference",
        "Official export capabilities: https://www.misp-project.org/features/",
    ),
    (
        "Timesketch reference",
        (
            "Official event tags/comments: "
            "https://timesketch.org/guides/user/basic-concepts/"
        ),
    ),
    (
        "Validation",
        (
            "Run dscat validate on completed workbooks. Dropdowns can be "
            "bypassed by pasting; the CLI independently checks every supplied "
            "row. Missing export facts can block a target without invalidating "
            "registration."
        ),
    ),
    (
        "Retention authorizer",
        (
            "Retention decision authorized by identifies who authorized the duration, "
            "not a calendar expiry date. Do not infer the authorizer from the owner "
            "or submitter. Unknown and Not yet authorized are descriptive answers. "
            "All authorizer names in the worked example are fictional."
        ),
    ),
    (
        "Identity",
        (
            "Collection identity is derived from its case-sensitive normalized "
            "name. Renaming a collection creates a new identity. Reuse names "
            "consistently; conflicting duplicate records require correction."
        ),
    ),
    (
        "Completion",
        (
            "Use the blank copy or remove all example rows before submitting "
            "other metadata. Example rows are ordinary records, never silently "
            "discarded. Date and submitter describe this entry, not data "
            "ownership or batch arrival."
        ),
    ),
)

TEMPLATE_ROWS = 200
HEADER_ROW = 5
FIRST_ROW = 6
UNITS = ("KB", "MB", "GB", "TB", "PB")
