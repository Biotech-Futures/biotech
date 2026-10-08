"""The wording of the participant consent form, versioned.

Every signed consent records the version its guardian saw. Changing what a
guardian agrees to means adding a new version (a new template and a new entry
below) and pointing CURRENT_VERSION at it; old versions stay so a signed
consent can always be shown with its own wording.
"""
from django.conf import settings
from django.template.loader import render_to_string

CURRENT_VERSION = "2026-09-16"

_VERSIONS = {
    "2026-09-16": {
        "template": "consent/participant_consent_2026-09-16.html",
        "media_yes": (
            "Yes – I provide media consent. I consent to the uses described above and "
            "understand that {student_name} may attend in-person {brand_name} events."
        ),
        "media_no": (
            "No – I do not provide media consent. I understand that {student_name} will not "
            "be permitted to attend any in-person {brand_name} event. Photographs, videos and "
            "other recordings may be captured at these events, and {brand_name} cannot "
            "guarantee that a participant attending in person will not be captured. The "
            "participant may continue to participate in the online components of the "
            "Challenge, subject to the Challenge Participant Terms and Conditions."
        ),
        "declaration": (
            "By signing below, I confirm that the information and consent choices I have "
            "provided are accurate and that I understand how the selected media-consent "
            "option affects participation in in-person events."
        ),
    },
}


def render_consent_form(student_name: str, version: str = CURRENT_VERSION) -> dict:
    """The form's wording for ``student_name``: its body as HTML (names escaped
    by the template engine) and the media options and declaration as text."""
    entry = _VERSIONS[version]
    names = {"student_name": student_name, "brand_name": settings.BRAND_NAME}
    return {
        "version": version,
        "body_html": render_to_string(
            entry["template"], {**names, "support_email": settings.SUPPORT_EMAIL},
        ),
        "media_yes": entry["media_yes"].format(**names),
        "media_no": entry["media_no"].format(**names),
        "declaration": entry["declaration"],
    }
