from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import json

class PersonalInfo(BaseModel):
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    email: str = ""
    phone: str = ""
    phone_type: str = "Mobile"
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    state: str = ""
    state_abbr: str = ""
    postal_code: str = ""
    country: str = "United States"

    def get_full_name(self) -> str:
        if self.full_name:
            return self.full_name
        return f"{self.first_name} {self.last_name}".strip()

class ProfileLinks(BaseModel):
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    twitter: str = ""

class DocumentPaths(BaseModel):
    resume_path: str = ""
    cover_letter_path: str = ""

class WorkAuthorization(BaseModel):
    authorized_to_work_in_country: bool = True
    require_sponsorship: bool = False
    future_sponsorship: bool = False
    minimum_age_18: bool = True

class AvailabilityInfo(BaseModel):
    start_date: str = "05/17/2027"
    end_date: str = "08/20/2027"
    duration_months: int = 3
    full_time: bool = True
    thesis_or_report_required: bool = False

class EEOInfo(BaseModel):
    gender: str = ""
    race_ethnicity: str = ""
    veteran_status: str = ""
    disability_status: str = ""

class UserProfile(BaseModel):
    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    profiles: ProfileLinks = Field(default_factory=ProfileLinks)
    documents: DocumentPaths = Field(default_factory=DocumentPaths)
    work_authorization: WorkAuthorization = Field(default_factory=WorkAuthorization)
    availability: AvailabilityInfo = Field(default_factory=AvailabilityInfo)
    eeo: EEOInfo = Field(default_factory=EEOInfo)

    def get_nested_value(self, path: str) -> Any:
        """Retrieves a nested value from dot notation like 'personal.first_name'"""
        parts = path.split(".")
        val: Any = self
        for part in parts:
            if hasattr(val, part):
                val = getattr(val, part)
            elif isinstance(val, dict) and part in val:
                val = val[part]
            else:
                return None
        return val


def load_profile(path: Path | str) -> UserProfile:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Profile file not found at: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Error parsing JSON in '{file_path}' (Line {e.lineno}, Column {e.colno}): {e.msg}.\n"
            "Tip: Ensure all strings have closing double quotes and all trailing commas are valid."
        ) from e
    return UserProfile(**data)


def load_rules(path: Path | str) -> Dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Rules configuration not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
