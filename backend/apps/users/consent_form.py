"""The wording of the participant consent form and its signed record, versioned.

Every signed consent records the version its guardian saw. Changing what a
guardian agrees to means adding a new version (a new template and a new entry
below) and pointing CURRENT_VERSION at it; old versions stay so a signed
consent can always be shown, and its PDF record rebuilt, with its own wording.

Text here uses {student_name}, {brand_name} and {support_email}.
"""
from django.conf import settings
from django.template.loader import render_to_string

CURRENT_VERSION = "2026-09-16"

_VERSIONS = {
    "2026-09-16": {
        "template": "consent/participant_consent_2026-09-16.html",
        # What the guardian confirms by signing: shown on the form, and in the
        # record as what they confirmed.
        "participation": [
            "I am the parent, guardian or other person authorised to provide consent for {student_name}.",
            "I give permission for {student_name} to participate in the {brand_name} Challenge and its "
            "related online activities, subject to the Challenge Participant Terms and Conditions.",
            "I understand that attendance at in-person {brand_name} events is permitted only where media "
            "consent is provided. This includes, but is not limited to, workshops, campus or laboratory "
            "visits, networking events and the Symposium.",
            "I have read and acknowledge the Challenge Participant Terms and Conditions, Child Safety Policy "
            "and Privacy Policy. I will support the participant to follow the applicable participation, "
            "conduct, communication and safety requirements.",
            "I understand that the Challenge may involve teamwork, approved online communication, mentor "
            "guidance, workshops, webinars, submissions, judging and the Symposium.",
            "I understand that particular activities, including laboratory visits, campus visits, travel or "
            "activities with additional safety requirements, may require further information or a separate "
            "activity-specific consent form.",
            "I consent to {brand_name} collecting and handling the participant’s personal information, "
            "including any emergency, medical or accessibility information provided, as described in the "
            "Privacy Policy and where reasonably necessary for program delivery and safety.",
            "I understand that the participant retains ownership of their pre-existing ideas and intellectual "
            "property. When Challenge materials are submitted, the team gives {brand_name} the non-exclusive "
            "permission described in section 15 of the Challenge Participant Terms and Conditions.",
            "I understand that the participant may withdraw from the Challenge by contacting {support_email}, "
            "subject to the arrangements for existing team submissions and previously published material "
            "explained in section 20 of the Challenge Participant Terms and Conditions.",
            "I understand that this consent does not waive any right or protection that cannot lawfully be "
            "excluded. It does not release {brand_name} or another party from liability for negligence, "
            "breach of law or other liability that cannot be excluded.",
        ],
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
        # The signed record (the PDF), from the 2026-09-16 Participant Consent template.
        "record": {
            "media_given": [
                "I consent to {brand_name} taking approved photographs, videos or recordings and using the "
                "participant’s image, voice, name, school name, project title and approved quotations for "
                "promotion, reporting, education and archival purposes.",
                "I understand that {student_name} may attend in-person {brand_name} events.",
            ],
            "media_not_given": [
                "I do not provide media consent.",
                "I understand that {student_name} will not be permitted to attend any in-person {brand_name} "
                "event. Photographs, videos and other recordings may be captured at these events, and "
                "{brand_name} cannot guarantee that a participant attending in person will not be captured.",
                "I understand that the participant may continue to participate in the online components of "
                "the Challenge, subject to the Challenge Participant Terms and Conditions.",
            ],
            "media_withdrawal": [
                "I understand that, where media consent has been provided, it may later be withdrawn by "
                "contacting {support_email}. If media consent is withdrawn, the participant will no longer be "
                "permitted to attend in-person {brand_name} events from the date the withdrawal takes effect.",
                "I understand that {brand_name} will take reasonable steps to stop future use and remove public "
                "media under its control following withdrawal. It may not be possible to remove material "
                "already printed, archived, cached, reposted by another person or included in a completed "
                "publication.",
            ],
            "declaration": (
                "By signing the consent form, I confirmed that the information and consent choices I provided "
                "were accurate and that I understood how the selected media-consent option affects "
                "participation in in-person events."
            ),
        },
    },
}


def _names(student_name: str) -> dict:
    return {
        "student_name": student_name,
        "brand_name": settings.BRAND_NAME,
        "support_email": settings.SUPPORT_EMAIL,
    }


def _fill(value, names: dict):
    if isinstance(value, str):
        return value.format(**names)
    if isinstance(value, list):
        return [_fill(item, names) for item in value]
    if isinstance(value, dict):
        return {key: _fill(item, names) for key, item in value.items() if key != "template"}
    return value


def render_consent_form(student_name: str, version: str = CURRENT_VERSION) -> dict:
    """The form's wording for ``student_name``: its body as HTML (names escaped
    by the template engine) and the media options and declaration as text."""
    entry = _VERSIONS[version]
    names = _names(student_name)
    filled = _fill(entry, names)
    return {
        "version": version,
        "body_html": render_to_string(
            entry["template"], {**names, "participation": filled["participation"]},
        ),
        "media_yes": filled["media_yes"],
        "media_no": filled["media_no"],
        "declaration": filled["declaration"],
    }


def consent_wording(student_name: str, version: str) -> dict:
    """Every part of version ``version``'s wording as plain text, for the
    signed record."""
    return _fill(_VERSIONS[version], _names(student_name))
