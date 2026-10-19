"""The poster checklist a team confirms before submitting; the poster checks tick what they can detect."""
from .poster_checks import A2_SIZE, SUPERVISOR_EMAIL, TEAM_CODE, PosterCheckResult

# Stored on the submission, so these keys are a contract.
CHECKLIST_ITEMS = ("supervisor_email", "btf_logo", "school_logo", "team_code", "page_size")


def blank_checklist() -> dict:
    return {item: False for item in CHECKLIST_ITEMS}


def detected_checklist(result: PosterCheckResult | None) -> dict:
    """Starting ticks for a new poster: only what the checks found for certain."""
    ticks = blank_checklist()
    if result is None:
        return ticks
    found = {check.code: check for check in result.content}

    def passed(code: str) -> bool:
        check = found.get(code)
        return bool(check and check.passed)

    ticks["team_code"] = passed(TEAM_CODE)
    # Only an email at the foot, where the template's supervisor panel sits.
    email = found.get(SUPERVISOR_EMAIL)
    ticks["supervisor_email"] = bool(email and email.passed and not email.message)
    ticks["page_size"] = passed(A2_SIZE)
    return ticks


def is_confirmed(checklist: dict | None) -> bool:
    return all((checklist or {}).get(item) for item in CHECKLIST_ITEMS)
