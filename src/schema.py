"""
Canonical schema -th e "source of truth" target that every broker file maps into.

Modeled as explicit objects (Group -> Member -> Dependent) the way an underwriting
data layer thinks about the world, rather than loose columns. Underwriting and
pricing read from this shape, and never from raw broker files.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


# Canonical field names the underwriting API expects downstream.
CANONICAL_FIELDS = [
    "group_id",          # which employer group this census belongs to
    "employee_id",       # subscriber identifier
    "first_name",
    "last_name",
    "date_of_birth",     # ISO date
    "gender",            # M | F | U
    "relationship",      # employee | spouse | child
    "zip_code",          # 5-char string, leading zeros preserved
    "state",             # 2-char upper
]

# Allowed canonical values
GENDER_DOMAIN = {"M", "F", "U"}
RELATIONSHIP_DOMAIN = {"employee", "spouse", "child"}


@dataclass
class CanonicalMember:
    group_id: str
    employee_id: str
    first_name: str
    last_name: str
    date_of_birth: Optional[date]
    gender: str
    relationship: str
    zip_code: str
    state: str
    # provenance / quality
    source_file: str = ""
    issues: list = field(default_factory=list)

    def to_row(self):
        return {
            "group_id": self.group_id,
            "employee_id": self.employee_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "gender": self.gender,
            "relationship": self.relationship,
            "zip_code": self.zip_code,
            "state": self.state,
            "source_file": self.source_file,
            "issues": "; ".join(self.issues),
        }
