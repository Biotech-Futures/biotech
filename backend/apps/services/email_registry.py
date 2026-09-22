"""Every system email the platform sends, and the merge tags each one supports.

This is the single source of truth shared by the send path
(apps.services.system_email) and the admin editor (apps.admin.services.system_email):
the editor only offers the tags listed here, and the send path only fills them.

Merge tags are written ``{{ tag_name }}`` in an admin's subject or body. Each tag
reads its value from ``context_key`` in the context the send point already builds,
so send points keep passing their existing context and only the renderer maps names.
"""

import re
from dataclasses import dataclass
from typing import Optional


# ``{{ tag_name }}`` with optional inner spaces. Lowercase snake_case only, so
# Django-style ``{{ settings.SECRET_KEY }}`` or ``{{ User }}`` never match a tag.
MERGE_TAG_RE = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")


@dataclass(frozen=True)
class MergeTag:
    name: str
    description: str
    sample: str
    context_key: str
    # True for snippets the code builds itself (e.g. a list of groups). Their
    # values are trusted HTML and are not escaped when filled into the body.
    html: bool = False


@dataclass(frozen=True)
class EmailType:
    key: str
    name: str
    description: str
    default_subject: str
    default_template: str
    merge_tags: tuple
    # Locked types can be edited but never switched off, including by the
    # global toggle, so nobody can lock every user out of the platform.
    locked: bool = False

    def tag(self, name: str) -> Optional[MergeTag]:
        for merge_tag in self.merge_tags:
            if merge_tag.name == name:
                return merge_tag
        return None

    @property
    def tag_names(self) -> frozenset:
        return frozenset(merge_tag.name for merge_tag in self.merge_tags)


# Available on every email type; values come from brand_context().
_BRAND_TAGS = (
    MergeTag("brand_name", "Programme name", "BIOTech Futures", "BRAND_NAME"),
    MergeTag("brand_connect", "Platform name", "BIOTech Connect", "BRAND_CONNECT"),
    MergeTag("contact_email", "Support email address", "support@biotechfutures.org", "CONTACT_EMAIL"),
)

_FIRST_NAME = MergeTag("first_name", "Recipient's first name", "Alex", "First_Name")


EMAIL_TYPES = (
    EmailType(
        key="login_code",
        name="Login code",
        description="Sent when a user signs in with their email address.",
        default_subject="{{ brand_name }}: Log in securely",
        default_template="emails/login.html",
        locked=True,
        merge_tags=(
            _FIRST_NAME,
            MergeTag("magic_link", "One-click sign-in link", "https://api.biotechfutures.org/services/magic/?code=123456", "MAGIC_LINK"),
            MergeTag("otp_code", "Six-digit sign-in code", "123456", "OTP_CODE"),
            MergeTag("expiry_minutes", "Minutes until the code expires", "10", "EXPIRY_MINUTES"),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="password_reset",
        name="Password reset",
        description="Sent when a user asks to reset their password.",
        default_subject="{{ brand_name }}: Update your password",
        default_template="emails/password_reset.html",
        merge_tags=(
            _FIRST_NAME,
            MergeTag("reset_link", "Link to set a new password", "https://biotechfutures.org/#/auth/reset-password?token=abc", "RESET_PASSWORD_LINK"),
            MergeTag("expiry_minutes", "Minutes until the link expires", "30", "EXPIRY_MINUTES"),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="password_changed",
        name="Password changed",
        description="Sent after a user's password is successfully changed.",
        default_subject="{{ brand_name }}: Your password was changed",
        default_template="emails/password_changed.html",
        merge_tags=(
            _FIRST_NAME,
            MergeTag("changed_at", "When the password was changed (UTC)", "18 Sep 2026, 10:30", "CHANGED_AT"),
            MergeTag("request_ip", "IP address the change came from", "203.0.113.7", "REQUEST_IP"),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="unread_messages",
        name="Unread messages digest",
        description="Scheduled summary of unread group chat messages.",
        default_subject="You have {{ unread_summary }} on {{ brand_connect }}",
        default_template="emails/unread_messages.html",
        merge_tags=(
            _FIRST_NAME,
            MergeTag("unread_summary", "Unread count with wording, e.g. \"3 unread messages\"", "3 unread messages", "UNREAD_SUMMARY"),
            MergeTag("total_unread", "Total number of unread messages", "3", "TOTAL_UNREAD"),
            MergeTag("group_count", "Number of groups with unread messages", "2", "GROUP_COUNT"),
            MergeTag("platform_url", "Link to the platform", "https://biotechfutures.org", "PLATFORM_URL"),
            MergeTag("unread_group_list", "List of groups and their unread counts", "<ul><li>CRISPR Research: 2</li><li>Protein Folding: 1</li></ul>", "UNREAD_GROUP_LIST", html=True),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="rsvp_reminder",
        name="Event RSVP reminder",
        description=(
            "Scheduled reminders before an event: a day-before reminder, a "
            "day-before request to respond, and a starting-soon reminder."
        ),
        default_subject="{{ reminder_subject }}",
        default_template="emails/rsvp_reminder.html",
        merge_tags=(
            _FIRST_NAME,
            MergeTag("reminder_subject", "Subject for this reminder, e.g. \"Reminder: BIOTech Symposium\"", "Reminder: BIOTech Symposium", "REMINDER_SUBJECT"),
            MergeTag("headline", "Heading for this reminder, e.g. \"Starting soon\"", "Your event is tomorrow", "HEADLINE"),
            MergeTag("intro", "Opening line for this reminder", "This is a friendly reminder that you have an upcoming event tomorrow.", "INTRO"),
            MergeTag("closing", "Closing line for this reminder", "We look forward to seeing you there!", "CLOSING"),
            MergeTag("event_name", "Event name", "BIOTech Symposium", "EVENT_NAME"),
            MergeTag("event_when", "Full date and time in the recipient's timezone", "Friday, 18 September 2026 at 10:00 AM AEST", "EVENT_WHEN_TEXT"),
            MergeTag("event_date", "Event date", "Friday, 18 September 2026", "EVENT_DATE"),
            MergeTag("event_time", "Event start time", "10:00 AM AEST", "EVENT_TIME"),
            MergeTag("event_location", "Event location", "Room 201, Science Building", "EVENT_LOCATION_TEXT"),
            MergeTag("event_map_url", "Map link for the location", "https://maps.google.com/?q=Science+Building", "EVENT_LOCATION_MAP_URL"),
            MergeTag("event_description", "Event description", "An afternoon of student project presentations.", "EVENT_DESCRIPTION"),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="event_promotion",
        name="Waitlist promotion",
        description="Sent when someone cancels and a waitlisted user gets their spot.",
        default_subject="You're in: {{ event_name }}",
        default_template="emails/event_promotion.html",
        merge_tags=(
            _FIRST_NAME,
            MergeTag("event_name", "Event name", "BIOTech Symposium", "EVENT_NAME"),
            MergeTag("event_when", "Full date and time in the recipient's timezone", "Friday, 18 September 2026 at 10:00 AM AEST", "EVENT_WHEN_TEXT"),
            MergeTag("event_location", "Event location", "Room 201, Science Building", "EVENT_LOCATION_TEXT"),
            MergeTag("event_join_link", "Online joining link", "https://zoom.us/j/123456789", "EVENT_JOIN_LINK"),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="announcement",
        name="Announcement notification",
        description="Sent when an admin clicks Notify on an announcement.",
        default_subject="[{{ brand_name }}] {{ title }}",
        default_template="emails/announcement.html",
        merge_tags=(
            MergeTag("title", "Announcement title", "Poster session scheduled", "title"),
            MergeTag("excerpt", "Short plain-text preview of the announcement", "The poster session will run on Friday afternoon in the Great Hall.", "excerpt"),
            MergeTag("detail_url", "Link to the full announcement", "https://biotechfutures.org/#/announcements/42", "detail_url"),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="submission_confirmation",
        name="Submission confirmation",
        description="Sent to a group when they submit their entry.",
        default_subject="{{ brand_name }}: Submission received for {{ group_name }}",
        default_template="emails/submission_confirmation.html",
        merge_tags=(
            MergeTag("group_name", "Group name", "CRISPR Research 01", "GROUP_NAME"),
            MergeTag("year", "Competition year", "2026", "YEAR"),
            MergeTag("deadline", "Submission deadline", "Friday, 25 September 2026 at 11:59 PM AEST", "DEADLINE"),
            MergeTag("submitted_by", "Who submitted the entry", "Alex Chen", "SUBMITTED_BY"),
            MergeTag("submission_url", "Link to the submission page", "https://biotechfutures.org/#/submission/12", "SUBMISSION_URL"),
            MergeTag("required_components_list", "Required components and whether each was submitted", "<ul><li>Scientific report: submitted</li><li>A2 poster: missing</li></ul>", "REQUIRED_COMPONENTS_LIST", html=True),
            MergeTag("optional_components_list", "Optional components and whether each was submitted", "<ul><li>Prototype: submitted</li></ul>", "OPTIONAL_COMPONENTS_LIST", html=True),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="submission_reminder",
        name="Submission reminder",
        description="Daily reminder in the final week before a group's deadline.",
        default_subject="{{ brand_name }}: Submission reminder for {{ group_name }}",
        default_template="emails/submission_reminder.html",
        merge_tags=(
            MergeTag("group_name", "Group name", "CRISPR Research 01", "GROUP_NAME"),
            MergeTag("year", "Competition year", "2026", "YEAR"),
            MergeTag("deadline", "Submission deadline", "Friday, 25 September 2026 at 11:59 PM AEST", "DEADLINE"),
            MergeTag("submission_url", "Link to the submission page", "https://biotechfutures.org/#/submission/12", "SUBMISSION_URL"),
            MergeTag("required_components_list", "Required components and whether each was submitted", "<ul><li>Scientific report: submitted</li><li>A2 poster: missing</li></ul>", "REQUIRED_COMPONENTS_LIST", html=True),
            MergeTag("optional_components_list", "Optional components and whether each was submitted", "<ul><li>Prototype: submitted</li></ul>", "OPTIONAL_COMPONENTS_LIST", html=True),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="finalist_notification",
        name="Finalist notification",
        description="Sent to a group's members when an admin marks the group as a finalist.",
        default_subject="Congratulations — {{ group_name }} is a {{ brand_name }} finalist",
        default_template="emails/finalist_notification.html",
        merge_tags=(
            MergeTag("group_name", "Group name", "CRISPR Research 01", "GROUP_NAME"),
            *_BRAND_TAGS,
        ),
    ),
)

EMAIL_REGISTRY = {email_type.key: email_type for email_type in EMAIL_TYPES}


def get_email_type(key: str) -> EmailType:
    """Return the registry entry for ``key``. Raises KeyError for unknown keys."""
    return EMAIL_REGISTRY[key]


def is_known_email_type(key: str) -> bool:
    return key in EMAIL_REGISTRY


def extract_merge_tags(text: str) -> set:
    """Every ``{{ tag_name }}`` used in ``text``, whether or not it's allowed."""
    return set(MERGE_TAG_RE.findall(text or ""))


def unknown_merge_tags(key: str, text: str) -> set:
    """Tags used in ``text`` that the email type ``key`` doesn't support."""
    return extract_merge_tags(text) - get_email_type(key).tag_names
