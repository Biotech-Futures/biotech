import re
from typing import Iterable, Dict, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Dependencies: pandas/openpyxl
try:
    import pandas as pd
except Exception as e:
    raise CommandError("pandas/openpyxl required: pip install pandas openpyxl") from e

from matching.models import (
    Interest, Student, Mentor, MentorAvailability,
    Track, Experience
)

# --------- Normalization helpers ---------
def norm(s: Optional[str]) -> str:
    """Normalize a value to a trimmed string; None -> empty string."""
    if s is None:
        return ""
    return str(s).strip()


def titleish(s: str) -> str:
    """Normalize labels (e.g., interests) to Title Case and collapse spaces."""
    s = norm(s)
    if not s:
        return s
    return re.sub(r"\s+", " ", s.title())


def parse_interests(raw: str) -> Iterable[str]:
    """
    Parse an interest string into a list.
    Example: "AI, Robotics; biology / Bio" -> ["AI", "Robotics", "Biology"]
    """
    s = norm(raw)
    if not s:
        return []
    parts = re.split(r"[;,/|]", s)
    return [titleish(p) for p in parts if titleish(p)]


def map_track(country: str, region: str) -> str:
    """
    Map country/region to a Track.
    Rules:
    - AU + NSW/QLD/VIC/WA -> corresponding AUS-*
    - Brazil/BRA -> BRA
    - Otherwise -> GLOBAL
    """
    c = norm(country).upper()
    r = norm(region).upper()
    if not r:
        return Track.GLOBAL
    if c in {"AUSTRALIA", "AUS", "AU"}:
        if "NSW" in r:
            return Track.AUS_NSW
        if "QLD" in r:
            return Track.AUS_QLD
        if "VIC" in r:
            return Track.AUS_VIC
        if r in {"WA", "WESTERN AUSTRALIA"}:
            return Track.AUS_WA
        # Fallback for unrecognized AU state
        return Track.GLOBAL

    if c in {"BRAZIL", "BRA"}:
        return Track.BRA

    return Track.GLOBAL


def map_experience(raw: str) -> str:
    s = norm(raw).lower()
    if not s:
        return Experience.UG

    # Exact match for several Excel formats
    if "undergraduate" in s:
        return Experience.UG
    if "postgraduate" in s:
        return Experience.PG
    if "hdr" in s:
        return Experience.HDR
    if "academic" in s:
        return Experience.AC
    if "industry" in s:
        return Experience.IN

    if any(k in s for k in ["prof", "lectur", "faculty"]):
        return Experience.AC
    if any(k in s for k in ["phd", "doctoral", "doctorate", "research", "fellow"]):
        return Experience.HDR
    if any(k in s for k in ["engineer", "developer", "consultant", "company", "corp"]):
        return Experience.IN
    if any(k in s for k in ["post", "post-grad", "pg "]):
        return Experience.PG
    if any(k in s for k in ["under", "ug "]):
        return Experience.UG

    # Fallback
    return Experience.UG



# --------- Column alias helpers (tolerant to header variants) ---------
STUDENT_ALIASES = {

    # Students sheet headers may include "(Synthestic)/(Synthetic)" variants
    "first_name": ["First Name (Synthestic)", "First Name (Synthetic)", "First Name", "First", "Given Name"],
    "last_name":  ["Last Name (Synthestic)", "Last Name (Synthetic)", "Last Name", "Last", "Family Name", "Surname"],
    "email":      ["Email (Synthestic)", "Email (Synthetic)", "Email", "Email Address"],
    "year_level": ["Year Level *", "Year Level", "YEAR LEVEL *", "YEAR LEVEL", "Year", "YearLevel"],
    "country":    ["Country"],
    "region":     ["Region", "State"],
    # Interests sometimes appear in both new/old columns—either is accepted
    "interests":  ["Area(s) of Interest", "Area(s) of interest (old)", "Interests", "Interest Areas", "Areas of Interest"],
    "school":     ["School Name", "School"],
    "group_number": ["Group Number", "Group number", "Group", "Group #"]
}

MENTOR_ALIASES = {
    # Mentors sheet headers also vary in spelling
    "first_name": ["First Name (Synthetic)", "First Name", "First", "Given Name"],
    "last_name":  ["Last Name (Synethtic)", "Last Name (Synthetic)", "Last Name", "Last", "Family Name", "Surname"],
    "email":      ["Email (Synthetic)", "Email", "Email Address"],
    "background": ["Background *", "Background"],
    "institution":["Institution/Company *", "Institution", "Organisation", "Organization", "Company"],
    "country":    ["Country"],
    "region":     ["Region", "State"],
    "track":      ["Track"],  # If missing, we derive from country/region
    "interests":  ["Area of Interest *", "Interests", "Interest", "Interest Area", "Interest Areas"],
    "max_groups": ["Maximum Number of Groups", "Max Groups", "Maximum number of groups", "Max Number Of Groups"]
}


def _norm_colname(s: str) -> str:
    # Normalize to lowercase, strip whitespace, remove common symbols and spaces
    return re.sub(r"[\s\*\(\)\-_/]+", "", str(s or "").strip().lower())

def pick(df: pd.DataFrame, key: str, alias_map: Dict[str, Iterable[str]], default=None):
    """
    Get column from DataFrame by alias (case-insensitive; ignores spaces and '*' symbols).
    Returns the column Series if found; returns default if not found.
    """
    norm_cols = {_norm_colname(c): c for c in df.columns}
    for alias in alias_map.get(key, []):
        nc = _norm_colname(alias)
        if nc in norm_cols:
            return df[norm_cols[nc]]
    return default

def cell(col, i):
    """Return a single cell value, compatible with Series or scalars."""
    import pandas as pd
    if isinstance(col, pd.Series):
        return col.iloc[i]
    return col

# --------- Management command ---------
class Command(BaseCommand):
    help = "Import P11 students & mentors from an Excel file into the local DB."

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", type=str, help="Path to the Excel (.xlsx) file")
        parser.add_argument("--students-sheet", type=str, default="Students",
                            help="Sheet name containing students (default: Students)")
        parser.add_argument("--mentors-sheet", type=str, default="Mentors",
                            help="Sheet name containing mentors (default: Mentors)")

    @transaction.atomic
    def handle(self, *args, **opts):
        xlsx_path = opts["xlsx_path"]
        st_name = opts["students_sheet"]
        mt_name = opts["mentors_sheet"]

        try:
            xls = pd.ExcelFile(xlsx_path)
        except Exception as e:
            raise CommandError(f"Failed to open Excel: {xlsx_path}\n{e}")

        # Read students sheet
        if st_name not in xls.sheet_names:
            raise CommandError(f"Students sheet not found: {st_name} (available: {xls.sheet_names})")
        df_stu = pd.read_excel(xls, st_name).fillna("")

        # Read mentors sheet
        if mt_name not in xls.sheet_names:
            raise CommandError(f"Mentors sheet not found: {mt_name} (available: {xls.sheet_names})")
        df_men = pd.read_excel(xls, mt_name).fillna("")

        # Preload Interest cache to reduce DB roundtrips
        interest_cache: Dict[str, Interest] = {
            i.name: i for i in Interest.objects.all()
        }

        def get_interest(name: str) -> Interest:
            """Return Interest object (create if needed), using a local cache."""
            name2 = titleish(name)
            if not name2:
                return None  # ignore empty values
            if name2 in interest_cache:
                return interest_cache[name2]
            obj, _ = Interest.objects.get_or_create(name=name2)
            interest_cache[name2] = obj
            return obj

        # ---------- Import Students ----------
        created_stu, updated_stu = 0, 0

        st_first = pick(df_stu, "first_name", STUDENT_ALIASES, "")
        st_last = pick(df_stu, "last_name", STUDENT_ALIASES, "")
        st_email = pick(df_stu, "email", STUDENT_ALIASES, "")
        st_year = pick(df_stu, "year_level", STUDENT_ALIASES, "")
        st_country = pick(df_stu, "country", STUDENT_ALIASES, "")
        st_region = pick(df_stu, "region", STUDENT_ALIASES, "")
        st_interests = pick(df_stu, "interests", STUDENT_ALIASES, "")
        st_school = pick(df_stu, "school", STUDENT_ALIASES, "")
        st_group_number = pick(df_stu, "group_number", STUDENT_ALIASES, "")

        for i in range(len(df_stu)):
            email = norm(str(cell(st_email, i)))
            if not email:
                continue

            first = norm(cell(st_first, i))
            last = norm(cell(st_last, i))
            y = cell(st_year, i)
            year = 9
            if y is not None and str(y).strip():
                try:
                    year = int(float(y))  # Compatible with 10.0 / "10.0" / 10
                except Exception:
                    import re
                    m = re.search(r"\d+", str(y))
                    if m:
                        year = int(m.group())

            # Optional: limit year level to 7-12 (based on business requirements)
            year = max(7, min(12, year))

            country = norm(cell(st_country, i))
            region = norm(cell(st_region, i))
            track = map_track(country, region)
            school = norm(cell(st_school, i))
            group_no = norm(cell(st_group_number, i))

            defaults = dict(
                first_name=first, last_name=last,
                school=school, year_level=year,
                country=country, region=region, track=track,
                preassigned_group=group_no,
            )
            stu, created = Student.objects.update_or_create(email=email, defaults=defaults)
            if created:
                created_stu += 1
            else:
                updated_stu += 1

            raw_interests = cell(st_interests, i)
            names = parse_interests(str(raw_interests))
            if names:
                stu.interests.clear()
                for n in names:
                    inter = get_interest(n)
                    if inter:
                        stu.interests.add(inter)

        # ---------- Import Mentors ----------
        created_m, updated_m = 0, 0

        m_first = pick(df_men, "first_name", MENTOR_ALIASES, "")
        m_last  = pick(df_men, "last_name",  MENTOR_ALIASES, "")
        m_email = pick(df_men, "email",      MENTOR_ALIASES, "")
        m_bg    = pick(df_men, "background", MENTOR_ALIASES, "")
        m_inst  = pick(df_men, "institution",MENTOR_ALIASES, "")
        m_country = pick(df_men, "country",  MENTOR_ALIASES, "")
        m_region  = pick(df_men, "region",   MENTOR_ALIASES, "")
        m_track   = pick(df_men, "track",    MENTOR_ALIASES, "")
        m_interests = pick(df_men, "interests", MENTOR_ALIASES, "")
        m_max   = pick(df_men, "max_groups", MENTOR_ALIASES, 1)

        for i in range(len(df_men)):
            email = norm(str(cell(m_email, i)))
            if not email:
                continue

            first = norm(cell(m_first, i))
            last = norm(cell(m_last, i))
            bg = norm(cell(m_bg, i))
            country = norm(cell(m_country, i))
            region = norm(cell(m_region, i))
            track_raw = norm(str(cell(m_track, i)))
            track = track_raw if track_raw in dict(Track.choices) else map_track(country, region)

            try:
                max_groups = int(str(cell(m_max, i)).strip())
            except Exception:
                max_groups = 1

            defaults = dict(
                first_name=first, last_name=last, background=bg,
                institution=norm(cell(m_inst, i)),
                country=country, region=region, track=track, max_groups=max_groups
            )
            mentor, created = Mentor.objects.update_or_create(email=email, defaults=defaults)
            if created:
                created_m += 1
            else:
                updated_m += 1

            raw_interests = cell(m_interests, i)
            names = parse_interests(str(raw_interests))
            if names:
                mentor.interests.clear()
                for n in names:
                    inter = get_interest(n)
                    if inter:
                        mentor.interests.add(inter)

        self.stdout.write(self.style.SUCCESS(
            f"Import completed: Students created={created_stu}, updated={updated_stu}; "
            f"Mentors created={created_m}, updated={updated_m}"
        ))
