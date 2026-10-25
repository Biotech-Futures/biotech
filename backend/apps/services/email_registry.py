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

from apps.submissions.email_sections import GREEN, RED, presentation_section, section_html, times_section


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
    # Which of settings.EMAIL_SENDERS it goes from until System Emails picks
    # another.
    default_sender: str = "info"
    # Who an email for a whole group goes to, shown above "Send from".
    delivery: str = ""

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

# Each group's one email, as the send code addresses it (see
# apps.submissions.emails.to_and_cc and apps.management.services.delivery).
_GROUP_TO_AND_CC = "Each group gets one email: its students in To, and its mentors and supervisors in CC."

# The finalist confirmation's sections, built as the email builds them.
_SAMPLE_PRESENTATION = presentation_section(
    [{"label": "Presentation Slides", "submitted": True, "status": "Submitted", "detail": "2026_BTF01_Slides.pptx"}]
)
_SAMPLE_TIMES = times_section(["09:30 - 10:00 AEDT", "11:40 - 12:30 AEDT"], "Friday, 23 October 2026", "AEDT, UTC+11")
_SAMPLE_REMINDER = section_html(
    "Submission components",
    [
        {"label": "Presentation Slides", "status": "Uploaded", "detail": "2026_BTF01_Slides.pptx", "colour": GREEN},
        {"label": "Availability", "status": "Not submitted", "colour": RED},
    ],
    "Both are required: submit your availability, then press Submit.",
)

_FIRST_NAME = MergeTag("first_name", "Recipient's first name", "Alex", "First_Name")
# A student someone else registered: their link to set a password, for 14
# days (registration_password.emailed_password_url). Empty for anyone else.
_SET_PASSWORD_URL = MergeTag(
    "set_password_url",
    "Their link to set a password (students registered by someone else, without one)",
    "https://mentoring.biotechfutures.org/#/register/password?token=sample",
    "SET_PASSWORD_URL",
)

# The ticket emails' tags (apps.tickets.services.emails). Everything they
# say about an enquiry is a tag, the "is it assigned" sentence included, so
# wording saved on System Emails keeps every part of them.
_TICKET_NUMBER = MergeTag("ticket_number", "Enquiry number", "SUP-2026-00027", "TICKET_NUMBER")
_TICKET_SUBJECT = MergeTag(
    "ticket_subject", "Enquiry subject", "Where do I upload the science report", "TICKET_SUBJECT"
)
_TICKET_STATUS = MergeTag("status", "Where the enquiry stands", "Open", "STATUS_LABEL")
_TICKET_ASSIGNEE = MergeTag(
    "assignee", 'Who has it: "Assigned to" and a name, or "Unassigned"', "Unassigned", "ASSIGNEE_LINE"
)
_TICKET_ASSIGNMENT = MergeTag(
    "assignment", "Whether anyone has it yet, as a sentence", "It is not assigned to anyone yet.", "ASSIGNMENT"
)
_TICKET_CATEGORY = MergeTag("category", "Enquiry category", "General Question", "CATEGORY_LABEL")
_TICKET_PRIORITY = MergeTag("priority", "Priority in the support queue", "Normal", "PRIORITY_LABEL")
_TICKET_QUEUE_LINK = MergeTag(
    "queue_link",
    "Link that opens the enquiry in the support queue",
    "https://mentoring.biotechfutures.org/#/admin/tickets?ticket=27",
    "CTA_URL",
)
_TO_THE_SUPPORT_INBOX = "Goes to the support team's shared inbox (support@ unless set otherwise), not to a person."


def _status_pill(label, colours, tick=False):
    """A sample of the coloured status label the ticket emails show."""
    mark = '<span aria-hidden="true">&#10003;&nbsp;</span>' if tick else ""
    return f'<span style="display:inline-block; padding:3px 12px; {colours} border-radius:999px; font-weight:700;">{mark}{label}</span>'


# The pill is built by the code and arrives finished, so its colour follows
# the status in saved wording too (apps/tickets/templates/emails/_ticket_status_pill.html).
_TICKET_STATUS_PILL = MergeTag(
    "status_pill", "Where the enquiry stands, as the coloured label the emails show",
    _status_pill("Open", "background:#D3ECE0; color:#017151;"), "STATUS_PILL", html=True,
)
# The three to whoever raised the enquiry: a student, a mentor or a supervisor.
_REQUESTER_GREETING = MergeTag(
    "greeting_name", 'First name of whoever raised it, or "there" if the account has none', "Ava", "GREETING_NAME"
)
_EXPECTED_REPLY = MergeTag("expected_reply", "How soon we usually reply", "one business day", "EXPECTED_REPLY")
_TICKET_LINK = MergeTag(
    "ticket_link", "Link to the enquiry in their Support Centre",
    "https://mentoring.biotechfutures.org/#/support/tickets/27", "TICKET_URL",
)


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
        locked=True,
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
        locked=True,
        merge_tags=(
            _FIRST_NAME,
            MergeTag("changed_at", "When the password was changed (UTC)", "18 Sep 2026, 10:30", "CHANGED_AT"),
            MergeTag("request_ip", "IP address the change came from", "203.0.113.7", "REQUEST_IP"),
            *_BRAND_TAGS,
        ),
    ),
    # Registration: sent once someone registers (apps.users.registration_emails).
    EmailType(
        key="registration_student",
        name="Registration confirmation (to student)",
        description=(
            "Sent to a student when they register on their own, including with a late link."
        ),
        default_subject="{{ brand_name }}: Registration",
        default_template="emails/registration_student.html",
        merge_tags=(
            _FIRST_NAME,
            MergeTag("year", "Competition year", "2026", "YEAR"),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="registration_group",
        name="Group registration confirmation (to students)",
        description=(
            "Sent to each student who registers as a team, each with their own copy, and to a "
            "student who joins a group by its code."
        ),
        default_subject="{{ brand_name }}: Registration",
        default_template="emails/registration_group.html",
        merge_tags=(
            _FIRST_NAME,
            MergeTag("year", "Competition year", "2026", "YEAR"),
            MergeTag("group_code", "The group's code, for teammates to join", "482913", "GROUP_CODE"),
            _SET_PASSWORD_URL,
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="registration_mentor",
        name="Registration confirmation (to mentor)",
        description="Sent to a mentor once they register on the registration page.",
        default_subject="{{ brand_name }}: Registration",
        default_template="emails/registration_mentor.html",
        merge_tags=(
            _FIRST_NAME,
            MergeTag("year", "Competition year", "2026", "YEAR"),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="registration_new_supervisor",
        name="Registration confirmation (to new supervisor)",
        description="Sent to a supervisor once they register on the registration page.",
        default_subject="{{ brand_name }}: Registration",
        default_template="emails/registration_new_supervisor.html",
        merge_tags=(
            _FIRST_NAME,
            MergeTag("year", "Competition year", "2026", "YEAR"),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="registration_named_supervisor",
        name="Named as supervisor (to new supervisor)",
        description=(
            "Sent to the supervisor a student names when registering, if that email had no account: "
            "one is created for them. Once per registration, naming every student in it."
        ),
        default_subject="{{ brand_name }}: You've been named as a supervisor",
        default_template="emails/registration_named_supervisor.html",
        merge_tags=(
            _FIRST_NAME,
            MergeTag("student_names", "The students who named them", "Jordan Lee and Alex Kim", "STUDENT_NAMES"),
            MergeTag("year", "Competition year", "2026", "YEAR"),
            MergeTag(
                "students_url", "Link to the supervisor's Students page",
                "https://biotechfutures.org/#/my-students", "STUDENTS_URL",
            ),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="registration_by_supervisor",
        name="Registered by supervisor (to student)",
        description=(
            "Sent to each student a supervisor registers: one student, a group, or an uploaded "
            "file. Not sent when an admin registers students."
        ),
        default_subject="{{ brand_name }}: Registration",
        default_template="emails/registration_by_supervisor.html",
        merge_tags=(
            _FIRST_NAME,
            MergeTag("supervisor_name", "The supervisor who registered them", "Sam Lee", "SUPERVISOR_NAME"),
            MergeTag("year", "Competition year", "2026", "YEAR"),
            _SET_PASSWORD_URL,
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="registration_supervisor",
        name="Registration confirmation (to supervisor)",
        description=(
            "Sent to a supervisor once they register students: one student, a group, or an "
            "uploaded file. Not sent when an admin registers students for them."
        ),
        default_subject="{{ brand_name }}: Registration",
        default_template="emails/registration_supervisor.html",
        merge_tags=(
            _FIRST_NAME,
            MergeTag("year", "Competition year", "2026", "YEAR"),
            MergeTag(
                "students_url", "Link to the supervisor's Students page",
                "https://biotechfutures.org/#/my-students", "STUDENTS_URL",
            ),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="supervisor_registration_status",
        name="Registration status (to supervisor)",
        description=(
            "Sent weekly to each supervisor with a student whose permission form isn't signed yet: "
            "how many of their students are complete, waiting for a signature, or waiting for "
            "guardian details. Stops once all their students are complete."
        ),
        default_subject="{{ brand_name }}: Student Registration Status",
        default_template="emails/supervisor_registration_status.html",
        merge_tags=(
            _FIRST_NAME,
            MergeTag("complete_count", "How many of their students are complete", "4", "COMPLETE_COUNT"),
            MergeTag(
                "pending_signature_count", "How many wait for their guardian's signature", "2",
                "PENDING_SIGNATURE_COUNT",
            ),
            MergeTag(
                "pending_contact_count", "How many wait for their guardian's details", "1",
                "PENDING_CONTACT_COUNT",
            ),
            MergeTag(
                "challenge_start", "The challenge start date (Management > Challenge Start)", "27 July",
                "CHALLENGE_START",
            ),
            MergeTag(
                "students_url", "Link to the supervisor's Students page",
                "https://biotechfutures.org/#/my-students", "STUDENTS_URL",
            ),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="registration_by_admin",
        name="Registered by admin (to student)",
        description=(
            "Sent to each student an admin registers on Management > Registration: one student, "
            "a group, or an uploaded file. Names the supervisor the admin chose."
        ),
        default_subject="{{ brand_name }}: Registration",
        default_template="emails/registration_by_admin.html",
        merge_tags=(
            _FIRST_NAME,
            MergeTag("supervisor_name", "The supervisor the admin chose", "Sam Lee", "SUPERVISOR_NAME"),
            MergeTag("year", "Competition year", "2026", "YEAR"),
            _SET_PASSWORD_URL,
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="guardian_details_request",
        name="Guardian details needed",
        description=(
            "Sent daily to a student with no parent or guardian email on file, "
            "until they add one on their profile."
        ),
        default_subject="Information Required: Parent/Guardian Contact",
        default_template="emails/guardian_details_request.html",
        merge_tags=(
            MergeTag("student_first_name", "Student's first name", "Alex", "STUDENT_FIRST_NAME"),
            MergeTag(
                "details_url",
                "Link to the student's profile to add their guardian",
                "https://biotechfutures.org/#/profile?guardian=edit",
                "DETAILS_URL",
            ),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="guardian_details_received",
        name="Guardian details received (to student)",
        description=(
            "Sent to a student when they add or change their parent or guardian on their profile "
            "and the consent form has gone to that guardian. Sent instead of Guardian consent sent."
        ),
        default_subject="Parent/Guardian Contact Received",
        default_template="emails/guardian_details_received.html",
        merge_tags=(
            MergeTag("student_first_name", "Student's first name", "Alex", "STUDENT_FIRST_NAME"),
            MergeTag("guardian_email", "Guardian's email the form went to", "pat@example.com", "GUARDIAN_EMAIL"),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="guardian_consent_student_notice",
        name="Guardian consent sent (to student)",
        description=(
            "Sent to a student when their parent or guardian is first emailed the consent form "
            "at registration, by an admin or by the daily run, asking them to remind their "
            "guardian. A student who added the guardian on their profile gets Guardian details "
            "received instead."
        ),
        default_subject="Parent/Guardian Action Required - Permission Form",
        default_template="emails/guardian_consent_student_notice.html",
        merge_tags=(
            MergeTag("student_first_name", "Student's first name", "Alex", "STUDENT_FIRST_NAME"),
            MergeTag("guardian_email", "Guardian's email the form went to", "pat@example.com", "GUARDIAN_EMAIL"),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="guardian_consent_request",
        name="Guardian consent request (to guardian)",
        description=(
            "Sent to a student's parent or guardian with the consent form: once the student is "
            "registered or adds them, when the student or an admin sends it, and every day until "
            "they sign."
        ),
        default_subject="Action Required: Sign parent/guardian permission form",
        default_template="emails/guardian_consent_request.html",
        merge_tags=(
            MergeTag("guardian_first_name", "Guardian's first name", "Pat", "GUARDIAN_FIRST_NAME"),
            MergeTag("student_first_name", "Student's first name", "Alex", "STUDENT_FIRST_NAME"),
            MergeTag("student_name", "Student's full name", "Alex Chen", "STUDENT_NAME"),
            MergeTag("consent_url", "Link to this guardian's consent form", "https://biotechfutures.org/#/consent/abc", "CONSENT_URL"),
            MergeTag("expiry_days", "Days until the link expires", "14", "EXPIRY_DAYS"),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="guardian_consent_received",
        name="Guardian permission received (to guardian)",
        description=(
            "Sent to a parent or guardian once they sign the consent form on the platform, "
            "thanking them. Not sent when an admin records consent."
        ),
        default_subject="Parent/Guardian Permission Received",
        default_template="emails/guardian_consent_received.html",
        merge_tags=(
            MergeTag("guardian_name", "Guardian's full name, as signed", "Pat Chen", "GUARDIAN_NAME"),
            MergeTag("student_name", "Student's full name", "Alex Chen", "STUDENT_NAME"),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="unread_messages",
        name="Unread messages digest",
        description="Scheduled summary of unread group chat messages.",
        default_subject="You have {{ unread_summary }} on {{ brand_connect }}",
        default_template="emails/unread_messages.html",
        # Its own mailbox, under its own sending limit.
        default_sender="connect",
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
            MergeTag("body", "Full announcement text", "<p>The poster session will run on Friday afternoon in the Great Hall.</p>", "body", html=True),
            MergeTag("excerpt", "Short plain-text preview of the announcement", "The poster session will run on Friday afternoon in the Great Hall.", "excerpt"),
            MergeTag("detail_url", "Link to the announcement on the platform", "https://biotechfutures.org/#/announcements/42", "detail_url"),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="submission_reminder",
        delivery=_GROUP_TO_AND_CC,
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
        key="submission_confirmation",
        delivery=_GROUP_TO_AND_CC,
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
        key="finalist_submission_confirmation",
        delivery=_GROUP_TO_AND_CC,
        name="Finalist submission confirmation",
        description="Sent to a finalist team when they submit their presentation.",
        default_subject="{{ brand_name }}: Presentation received for {{ group_name }}",
        default_template="emails/finalist_submission_confirmation.html",
        merge_tags=(
            MergeTag("group_name", "Group name", "CRISPR Research 01", "GROUP_NAME"),
            MergeTag("year", "Competition year", "2026", "YEAR"),
            MergeTag("submitted_by", "Who submitted the presentation", "Alex Chen", "SUBMITTED_BY"),
            MergeTag("slides_due", "Slides due date", "Friday, 16 October 2026", "SLIDES_DUE"),
            MergeTag("symposium_date", "Symposium date", "Friday, 23 October 2026", "SYMPOSIUM_DATE"),
            MergeTag("finalist_url", "Link to the finalist page", "https://biotechfutures.org/#/groups/12/finalist", "FINALIST_URL"),
            MergeTag("presentation", "The slides received, as a styled section", _SAMPLE_PRESENTATION, "PRESENTATION_SECTION", html=True),
            MergeTag("selected_times", "The times the team selected, as a styled section", _SAMPLE_TIMES, "TIMES_SECTION", html=True),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="finalist_submission_reminder",
        delivery=_GROUP_TO_AND_CC,
        name="Finalist submission reminder",
        description="Daily reminder in the final week before slides are due, until a finalist team submits.",
        default_subject="{{ brand_name }}: Presentation reminder for {{ group_name }}",
        default_template="emails/finalist_submission_reminder.html",
        merge_tags=(
            MergeTag("group_name", "Group name", "CRISPR Research 01", "GROUP_NAME"),
            MergeTag("year", "Competition year", "2026", "YEAR"),
            MergeTag("slides_due", "Slides due date", "Friday, 16 October 2026", "SLIDES_DUE"),
            MergeTag("finalist_url", "Link to the finalist page", "https://biotechfutures.org/#/groups/12/finalist", "FINALIST_URL"),
            MergeTag("submission_components", "Where the slides and times stand, as a styled section", _SAMPLE_REMINDER, "COMPONENTS_SECTION", html=True),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="finalist_notification",
        delivery=_GROUP_TO_AND_CC,
        name="Finalist notification",
        description="Sent to finalist teams from Notify Finalists.",
        default_subject="Congratulations – You’re a {{ brand_name }} Finalist!",
        default_template="emails/finalist_notification.html",
        merge_tags=(
            MergeTag("group_name", "Group name", "CRISPR Research 01", "GROUP_NAME"),
            MergeTag("symposium_date", "Symposium date", "Friday, 23 October 2026", "SYMPOSIUM_DATE"),
            MergeTag("confirm_by", "Confirm attendance by", "Sunday, 4 October 2026", "CONFIRM_BY"),
            MergeTag("slides_due", "Slides due", "Friday, 16 October 2026", "SLIDES_DUE"),
            MergeTag(
                "registration_url",
                "Symposium registration link",
                "https://events.humanitix.com/biotech-futures-symposium",
                "REGISTER_URL",
            ),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="nonfinalist_invitation",
        delivery=_GROUP_TO_AND_CC,
        name="Non-finalist invitation",
        description="Sent to teams not picked as finalists, from Notify Nonfinalist.",
        default_subject="Thank you for your submission – Invitation to the Symposium",
        default_template="emails/nonfinalist_invitation.html",
        merge_tags=(
            MergeTag("group_name", "Group name", "CRISPR Research 01", "GROUP_NAME"),
            MergeTag("symposium_date", "Symposium date", "Friday, 23 October 2026", "SYMPOSIUM_DATE"),
            MergeTag(
                "registration_url",
                "Symposium registration link",
                "https://events.humanitix.com/biotech-futures-symposium",
                "REGISTER_URL",
            ),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="nonsubmission_notice",
        delivery=_GROUP_TO_AND_CC,
        name="Non-submission notice",
        description="Sent to teams that didn't submit, from Notify Nonfinalist.",
        default_subject="{{ brand_name }} – No Submission Received",
        default_template="emails/nonsubmission_notice.html",
        merge_tags=(
            MergeTag("group_name", "Group name", "CRISPR Research 01", "GROUP_NAME"),
            MergeTag("symposium_date", "Symposium date", "Friday, 23 October 2026", "SYMPOSIUM_DATE"),
            MergeTag(
                "registration_url",
                "Symposium registration link",
                "https://events.humanitix.com/biotech-futures-symposium",
                "REGISTER_URL",
            ),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="results_team",
        # Its students and mentors each get the group's certificates.
        delivery="Each group gets one email: its students and mentors in To.",
        name="Results (to groups)",
        description="Sent to each group's students and mentors from Release Results.",
        default_subject="Your {{ year }} {{ brand_name }} Challenge results",
        default_template="emails/results_team.html",
        merge_tags=(
            MergeTag("group_name", "Group name", "CRISPR Research 01", "GROUP_NAME"),
            MergeTag("year", "Competition year", "2026", "YEAR"),
            MergeTag(
                "survey_url",
                "Feedback survey link",
                "https://sydney.au1.qualtrics.com/jfe/form/SV_cCKb80Gg7IhgBpA",
                "SURVEY_URL",
            ),
            MergeTag("survey_closes", "Survey closes", "30th of November", "SURVEY_CLOSES"),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="results_supervisor",
        name="Results (to supervisors)",
        description="Sent to their supervisors from Release Results.",
        default_subject="Your students’ {{ year }} {{ brand_name }} Challenge results",
        default_template="emails/results_supervisor.html",
        merge_tags=(
            MergeTag("supervisor_name", "Supervisor's name", "Dr Sam Lee", "SUPERVISOR_NAME"),
            MergeTag("year", "Competition year", "2026", "YEAR"),
            *_BRAND_TAGS,
        ),
    ),
    # The ticket system's six (apps.tickets.services.emails): three to whoever
    # raised the enquiry, three to the support inbox. The client asked on
    # 20 October for the support inbox's to be on System Emails ("Please
    # ensure this email is integrated into the Systems email feature"), and
    # Jinqi on 22 October for the requester's too.
    EmailType(
        key="ticket_submitted",
        name="Enquiry received (to the requester)",
        description=(
            "Sent to the student, mentor or supervisor who raised an enquiry, as soon as it is in: its "
            "number, that it is with the support team, and when to expect a reply."
        ),
        default_subject="{{ brand_connect }}: we have your enquiry ({{ ticket_number }})",
        default_template="emails/ticket_submitted.html",
        default_sender="support",
        merge_tags=(
            _REQUESTER_GREETING,
            _TICKET_NUMBER,
            _TICKET_SUBJECT,
            _TICKET_STATUS,
            _TICKET_STATUS_PILL,
            _EXPECTED_REPLY,
            _TICKET_LINK,
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="ticket_reply",
        name="Reply to an enquiry (to the requester)",
        description=(
            "Sent to whoever raised an enquiry when support replies on it. It never names who "
            "replied. What it says comes next depends on whether the reply asked them for something."
        ),
        default_subject="{{ brand_connect }}: an update on your enquiry ({{ ticket_number }})",
        default_template="emails/ticket_reply.html",
        default_sender="support",
        merge_tags=(
            _REQUESTER_GREETING,
            _TICKET_NUMBER,
            _TICKET_SUBJECT,
            _TICKET_STATUS,
            MergeTag(
                "status_pill", "Where the enquiry stands, as the coloured label the emails show",
                _status_pill("Pending user", "background:#FFF4D2; color:#7A5600;"), "STATUS_PILL", html=True,
            ),
            MergeTag(
                "next_step",
                "What happens next: whether the enquiry is waiting on their answer",
                '<p style="margin:14px 0 22px 0; color:#3d4b43; font-size:15px; line-height:1.65;">'
                "We have asked you for some more information. The enquiry is waiting on your answer, "
                "so nothing further will happen until you reply.</p>",
                "NEXT_STEP",
                html=True,
            ),
            _EXPECTED_REPLY,
            _TICKET_LINK,
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="ticket_resolved",
        name="Enquiry resolved (to the requester)",
        description=(
            "Sent to whoever raised an enquiry when it is resolved. If it cannot be delivered, a note "
            "goes onto the enquiry so support can follow up."
        ),
        default_subject="{{ brand_connect }}: your enquiry is resolved ({{ ticket_number }})",
        default_template="emails/ticket_resolved.html",
        default_sender="support",
        merge_tags=(
            _REQUESTER_GREETING,
            _TICKET_NUMBER,
            _TICKET_SUBJECT,
            MergeTag("status", "Where the enquiry stands", "Resolved", "STATUS_LABEL"),
            MergeTag(
                "status_pill", "Where the enquiry stands, as the coloured label the emails show",
                _status_pill("Resolved", "background:#E6E8E9; color:#4F575C;", tick=True), "STATUS_PILL", html=True,
            ),
            _EXPECTED_REPLY,
            _TICKET_LINK,
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="ticket_new_for_support",
        name="New enquiry (to the support inbox)",
        description=(
            "Sent to the support inbox when someone raises an enquiry in the Support Centre: who "
            "raised it, its category and urgency, and a link to it in the queue. The message itself "
            "is left out, since most people raising enquiries are students."
        ),
        default_subject="{{ brand_connect }}: a new enquiry has come in ({{ ticket_number }})",
        default_template="emails/ticket_new_for_support.html",
        default_sender="support",
        delivery=_TO_THE_SUPPORT_INBOX,
        merge_tags=(
            MergeTag("requester_name", "Who raised it", "Ava Nguyen", "REQUESTER_NAME"),
            _TICKET_NUMBER,
            _TICKET_SUBJECT,
            _TICKET_STATUS,
            _TICKET_STATUS_PILL,
            _TICKET_ASSIGNEE,
            _TICKET_ASSIGNMENT,
            _TICKET_CATEGORY,
            MergeTag(
                "urgency", 'How urgent the requester said it is, e.g. "I can keep working"',
                "I can keep working", "URGENCY_WORDS",
            ),
            _TICKET_PRIORITY,
            _TICKET_QUEUE_LINK,
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="ticket_flagged_for_support",
        name="Flagged chat message (to the support inbox)",
        description=(
            "Sent to the support inbox when the AI screening flags a chat message and opens an "
            "enquiry for it. The flagged message is left out; it is in the enquiry."
        ),
        default_subject="{{ brand_connect }}: a chat message was flagged ({{ ticket_number }})",
        default_template="emails/ticket_flagged_for_support.html",
        default_sender="support",
        delivery=_TO_THE_SUPPORT_INBOX,
        merge_tags=(
            _TICKET_NUMBER,
            MergeTag(
                "ticket_subject", "Enquiry subject, with the kind of message and the group",
                'AI screening: personal_contact — group "Team Photosynthesis"', "TICKET_SUBJECT",
            ),
            _TICKET_STATUS,
            _TICKET_STATUS_PILL,
            _TICKET_ASSIGNEE,
            _TICKET_ASSIGNMENT,
            MergeTag("category", "Enquiry category", "Flagged content", "CATEGORY_LABEL"),
            MergeTag("priority", "Priority in the support queue", "High", "PRIORITY_LABEL"),
            _TICKET_QUEUE_LINK,
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="ticket_digest",
        name="Open enquiries summary (to the support inbox)",
        description=(
            "Sent to the support inbox at 9am Sydney time every day, weekends included: how many "
            "enquiries are open, in progress and waiting on the requester, and how many of those "
            "are overdue. It goes on a day with none open as well."
        ),
        default_subject="{{ brand_connect }}: {{ headline }}",
        default_template="emails/ticket_digest.html",
        default_sender="support",
        delivery=_TO_THE_SUPPORT_INBOX,
        merge_tags=(
            MergeTag(
                "headline", 'The count as a sentence, e.g. "4 enquiries are still open"',
                "4 enquiries are still open", "HEADLINE",
            ),
            MergeTag("today", "The day it is sent, in Sydney", "Tuesday 20 October 2026", "TODAY"),
            MergeTag("open_total", "Enquiries not yet resolved", "4", "OPEN_TOTAL"),
            MergeTag("open_count", "Open: nobody has picked it up yet", "2", "OPEN_COUNT"),
            MergeTag("in_progress_count", "In progress: someone is working on it", "1", "IN_PROGRESS_COUNT"),
            MergeTag("pending_user_count", "Pending user: waiting on the requester", "1", "PENDING_USER_COUNT"),
            MergeTag("overdue", "Of those not resolved, how many are overdue", "1", "OVERDUE"),
            MergeTag(
                "queue_link", "Link to the support queue",
                "https://mentoring.biotechfutures.org/#/admin/tickets", "CTA_URL",
            ),
            *_BRAND_TAGS,
        ),
    ),
    EmailType(
        key="email_credits_low",
        name="Email verification credits low",
        description=(
            "Sent to QEV_ALERT_EMAIL (info@ by default) when the QuickEmailVerification account "
            "drops below 500, then 100, credits. Once per level, until it's topped up."
        ),
        default_subject="{{ brand_name }}: Email verification credits low ({{ remaining }} left)",
        default_template="emails/email_credits_low.html",
        # Running out of credits stops new addresses being checked, so this
        # alert can't be switched off.
        locked=True,
        merge_tags=(
            MergeTag("remaining", "Credits left", "450", "REMAINING"),
            MergeTag("threshold", "Alert level dropped below", "500", "THRESHOLD"),
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
