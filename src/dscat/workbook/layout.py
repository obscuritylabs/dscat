# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Versioned worksheet headers, feedback coordinates and control vocabulary."""

DATASET_HEADERS = (
    "id",
    "title",
    "description",
    "core_party",
    "core_role",
    "core_email",
    "core_url",
    "dataset_version",
    "inventory_added",
    "metadata_reviewed",
    "dataset_modified",
    "update_frequency",
    "owner",
    "steward",
    "maintainer",
)
FIELD_HEADERS = (
    "dataset_id",
    "object_name",
    "field_name",
    "type",
    "description",
    "nullable",
    "semantic_reference",
)
DETAIL_HEADERS = (
    "dataset_id",
    "section",
    "entry_id",
    "property",
    "value",
    "unit",
    "reference",
)
SHEET_HEADERS = {
    "Datasets": DATASET_HEADERS,
    "Fields": FIELD_HEADERS,
    "Details_Quality": DETAIL_HEADERS,
}
FEEDBACK_HEADER = "feedback"
TEMPLATE_ROWS = 1000
SCHEMA_CELL = "B2"
KIND_CELL = "B3"
UNITS = ("B", "kB", "MB", "GB", "TB", "PB", "KiB", "MiB", "GiB", "TiB", "PiB")
ENUM_CHOICES = {
    ("role", "role"): ("accountable_owner", "steward", "contact", "maintainer"),
    ("role", "reference_kind"): ("local", "external"),
    ("service", "reference_kind"): ("local", "external"),
    ("service_dataset", "reference_kind"): ("local", "external"),
    ("commitment", "kind"): ("quality", "service"),
    ("access_determination", "state"): (
        "unknown",
        "partially_restricted",
        "fully_restricted",
        "unrestricted",
    ),
    ("disclosure_determination", "state"): (
        "unknown",
        "partially_restricted",
        "fully_restricted",
        "unrestricted",
    ),
    ("access_determination", "review_status"): (
        "not_reviewed",
        "in_review",
        "approved",
        "changes_requested",
    ),
    ("disclosure_determination", "review_status"): (
        "not_reviewed",
        "in_review",
        "approved",
        "changes_requested",
    ),
    ("metadata_review", "state"): (
        "not_reviewed",
        "in_review",
        "approved",
        "changes_requested",
    ),
    ("publication", "state"): ("unknown", "approved", "denied"),
    ("publication", "subject_kind"): ("canonical", "configuration", "derived_target"),
    ("publication", "target"): ("dcat-us-3", "odcs-3.2"),
    ("records", "hold_state"): ("unknown", "active", "inactive"),
    ("records", "review_state"): ("unknown", "active", "inactive"),
    ("capacity", "kind"): ("size", "average_ingestion", "peak_ingestion"),
    ("capacity", "state"): ("unknown", "known"),
    ("capacity", "unit"): UNITS,
    ("capacity", "basis"): ("logical", "physical"),
    ("capacity_retention", "state"): ("unknown", "indefinite", "known"),
}
DATE_PROPERTIES = (
    "inventory_added",
    "metadata_reviewed",
    "dataset_modified",
    "determined_on",
    "reviewed_on",
    "approved_on",
    "measured_on",
)


def date_valid(cell: str) -> str:
    """Return a Gregorian date feedback expression without evaluating it."""
    year, month, day = (
        f"VALUE(LEFT({cell},4))",
        f"VALUE(MID({cell},6,2))",
        f"VALUE(RIGHT({cell},2))",
    )
    leap = f"OR(MOD({year},400)=0,AND(MOD({year},4)=0,MOD({year},100)<>0))"
    maximum = f"CHOOSE({month},31,28+IF({leap},1,0),31,30,31,30,31,31,30,31,30,31)"
    return (
        f'IFERROR(AND(ISTEXT({cell}),LEN({cell})=10,MID({cell},5,1)="-",'
        f'MID({cell},8,1)="-",TEXT({year},"0000")=LEFT({cell},4),'
        f'TEXT({month},"00")=MID({cell},6,2),TEXT({day},"00")=RIGHT({cell},2),'
        f"{year}>0,{month}>0,{month}<13,{day}>0,{day}<={maximum}),FALSE)"
    )


def feedback_formula(sheet: str, row: int) -> str:
    """Produce only authored feedback formulas at reserved output coordinates."""
    if sheet == "Datasets":
        dates = ",".join(
            f'OR({col}{row}="",{date_valid(f"{col}{row}")})' for col in "IJK"
        )
        return (
            f'=IF(COUNTA(A{row}:O{row})=0,"",'
            f"IF(COUNTBLANK(A{row}:D{row})>0,"
            '"Complete id, title, description and core_party",'
            f"IF(SUMPRODUCT(--EXACT($A$2:$A${TEMPLATE_ROWS + 1},A{row}))>1,"
            '"Duplicate id; correct or use CLI guidance",'
            f'IF(NOT(AND({dates})),"Correct dates using YYYY-MM-DD",'
            '"Ready for CLI validation"))))'
        )
    if sheet == "Fields":
        return (
            f'=IF(COUNTA(A{row}:G{row})=0,"",'
            f"IF(COUNTBLANK(A{row}:D{row})>0,"
            '"Complete dataset_id, object_name, field_name and type",'
            f'IF(AND(F{row}<>"",F{row}<>"Yes",F{row}<>"No"),'
            '"Choose Yes or No for nullable",'
            '"Ready for CLI validation")))'
        )
    date_test = ",".join(f'D{row}="{prop}"' for prop in DATE_PROPERTIES)
    enum_test = (
        f'IFERROR(SUMPRODUCT(--EXACT(INDIRECT("dscat_"&B{row}&"_"&D{row}'
        f'&"_values"),E{row}))>0,TRUE)'
    )
    days_test = (
        f'IF(OR(D{row}="days",D{row}="duration_days"),'
        f"IFERROR(AND(VALUE(E{row})>=0,VALUE(E{row})<=2147483647,"
        f"MOD(VALUE(E{row}),1)=0),FALSE),TRUE)"
    )
    return (
        f'=IF(COUNTA(A{row}:G{row})=0,"",'
        f"IF(COUNTBLANK(A{row}:E{row})>0,"
        '"Complete dataset_id, section, entry_id, property and value",'
        f'IF(NOT({enum_test}),"Choose a supported value for this property",'
        f"IF(NOT(IF(OR({date_test}),{date_valid(f'E{row}')},TRUE)),"
        '"Correct date using YYYY-MM-DD",'
        f'IF(NOT({days_test}),"Use nonnegative whole days within the supported range",'
        '"Ready for CLI validation")))))'
    )
