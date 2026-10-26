"""What the help assistant knows, and how a question picks an answer.

Each entry is the answer to one kind of question, for the roles it applies
to. A question gets the entry whose keywords it mentions most; on a tie the
earlier entry wins, so topic entries come before the general "what should I
do" / "what can I do" ones, and "how do I get help" comes last. A question
that mentions none of the keywords gets ``FALLBACK``.

Keywords match at the start of a word, so "group" also matches "groups".
"""

import re

from django.conf import settings

from apps.common.role_names import ROLE_ADMIN, ROLE_MENTOR, ROLE_STUDENT, ROLE_SUPERVISOR

ADMIN = {ROLE_ADMIN}
PARTICIPANTS = {ROLE_STUDENT, ROLE_MENTOR}
MEMBERS = {ROLE_STUDENT, ROLE_MENTOR, ROLE_SUPERVISOR}
EVERYONE = None  # any signed-in user, whatever their role

# The pages a student, mentor or supervisor sees open up when the challenge
# starts; before that their menu holds only Profile and Support.
_BEFORE_START = (
    "If your menu only shows My Profile and Support, the challenge hasn't "
    "started yet; the other pages appear on the day it starts."
)

ENTRIES = [
    # --- Admin ---------------------------------------------------------------
    {
        "roles": ADMIN,
        "keywords": ["user", "account", "import", "csv", "add student", "add mentor", "role"],
        "answer": (
            "Admin > Users lists every account. You can search and filter it, open a "
            "user to edit their details, and use Import Students CSV or Import "
            "Mentors CSV to add people in bulk."
        ),
        "links": [{"label": "Users", "to": "/admin/users"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["guardian", "parent", "consent"],
        "answer": (
            "Admin > Guardians shows each student's guardian details and whether "
            "consent has been given. Students under 18 need guardian consent "
            "before they can post in their group."
        ),
        "links": [{"label": "Guardians", "to": "/admin/guardians"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["group", "match", "assign", "allocate"],
        "answer": (
            "Admin > Groups is where groups are created, students and mentors "
            "are assigned, and mentor matching is done."
        ),
        "links": [{"label": "Groups", "to": "/admin/groups"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["task", "checklist", "role task"],
        "answer": (
            "Admin > Tasks sets the tasks groups work through. Admin > Role Tasks "
            "sets the tasks for a role, such as all mentors."
        ),
        "links": [
            {"label": "Tasks", "to": "/admin/tasks"},
            {"label": "Role Tasks", "to": "/admin/role-tasks"},
        ],
    },
    {
        "roles": ADMIN,
        "keywords": ["plan", "progress"],
        "answer": "Admin > Group Plans shows each group's plan and how far along it is.",
        "links": [{"label": "Group Plans", "to": "/admin/plan"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["view", "query", "saved", "export", "report"],
        "answer": (
            "Admin > Views holds saved queries over users and groups: build one with "
            "conditions and columns, run it, and act on or export the results."
        ),
        "links": [{"label": "Views", "to": "/admin/views"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["email", "template", "notification", "bounce"],
        "answer": (
            "Admin > System Emails holds the emails the platform sends. Analytics > "
            "Email Monitoring shows what was sent and what bounced."
        ),
        "links": [
            {"label": "System Emails", "to": "/admin/emails"},
            {"label": "Email Monitoring", "to": "/analytics/email"},
        ],
    },
    {
        "roles": ADMIN,
        "keywords": ["announcement", "announce", "notice", "broadcast"],
        "answer": "Open Announcements to post a new announcement and choose who it goes to.",
        "links": [{"label": "Announcements", "to": "/announcements"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["event", "rsvp", "invite", "workshop"],
        "answer": "Open Events to create an event, invite people and follow the RSVPs.",
        "links": [{"label": "Events", "to": "/events"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["resource", "upload", "material", "document"],
        "answer": "Open Resources to add a resource and choose which roles can see it.",
        "links": [{"label": "Resources", "to": "/resources"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["grade", "grading", "mark", "rubric", "score", "finalist"],
        "answer": (
            "Admin > Grading marks submissions by component or by group, and "
            "Select Finalists picks the groups that go through."
        ),
        "links": [
            {"label": "Grading", "to": "/grading"},
            {"label": "Select Finalists", "to": "/grading/finalists"},
        ],
    },
    {
        "roles": ADMIN,
        "keywords": [
            "registration", "register", "deadline", "challenge start", "symposium",
            "result", "release", "new year", "management", "university",
        ],
        "answer": (
            "Admin > Management runs the year: Registration and Late Registration, "
            "Challenge Start, Submission Deadline, the Symposium (finalists), "
            "Results and releasing them, and New Year."
        ),
        "links": [{"label": "Management", "to": "/management"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["analytics", "statistic", "stats", "dashboard", "chart"],
        "answer": (
            "Analytics has pages for users, registration, groups, mentors, activity, "
            "messages, resources and email monitoring."
        ),
        "links": [{"label": "Analytics", "to": "/analytics"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["ticket", "queue", "enquiry", "inquiry"],
        "answer": "Support Tickets is the queue of users' support requests, with its audit log and analytics.",
        "links": [{"label": "Support Tickets", "to": "/admin/tickets"}],
    },
    # --- Students, mentors, supervisors --------------------------------------
    {
        "roles": {ROLE_STUDENT},
        "keywords": ["mentor", "contact", "message", "chat", "talk"],
        "answer": (
            "Open Groups and go to your group: your mentor is one of its members. "
            "Write to them on the group's Discussion Board, or see the Meetings "
            "your mentor has scheduled. " + _BEFORE_START
        ),
        "links": [{"label": "Groups", "to": "/groups"}],
    },
    {
        "roles": {ROLE_MENTOR},
        "keywords": ["my student", "contact", "message", "chat", "talk", "meeting", "schedule"],
        "answer": (
            "Open Groups and go to your group. Write to your students on its "
            "Discussion Board, and use Meetings to schedule a meeting with them. "
            + _BEFORE_START
        ),
        "links": [{"label": "Groups", "to": "/groups"}],
    },
    {
        "roles": PARTICIPANTS,
        "keywords": ["group", "task", "team", "meeting", "plan"],
        "answer": (
            "Open Groups to reach your group's page: its Tasks and Meetings, the "
            "Discussion Board, the group's Plan and its Submission. " + _BEFORE_START
        ),
        "links": [{"label": "Groups", "to": "/groups"}],
    },
    {
        "roles": PARTICIPANTS,
        "keywords": ["submit", "submission", "upload", "deadline", "result"],
        "answer": (
            "Your group submits its work from the Submission section of the group's "
            "page, before the submission deadline. Results appear there once they "
            "are released."
        ),
        "links": [{"label": "Groups", "to": "/groups"}],
    },
    {
        "roles": MEMBERS,
        "keywords": ["resource", "material", "document", "guide", "file"],
        "answer": "Open Resources in the menu to see the materials shared with you. " + _BEFORE_START,
        "links": [{"label": "Resources", "to": "/resources"}],
    },
    {
        "roles": MEMBERS,
        "keywords": ["event", "workshop", "rsvp", "calendar"],
        "answer": "Open Events to see upcoming events and RSVP to them. " + _BEFORE_START,
        "links": [{"label": "Events", "to": "/events"}],
    },
    {
        "roles": MEMBERS,
        "keywords": ["announcement", "news", "update", "notice"],
        "answer": "Open Announcements for the latest news from the BIOTech Futures team.",
        "links": [{"label": "Announcements", "to": "/announcements"}],
    },
    {
        "roles": {ROLE_STUDENT},
        "keywords": ["guardian", "parent", "consent", "can't post", "cannot post"],
        "answer": (
            "Students under 18 need a guardian's consent before they can post in "
            "their group. Your guardian is sent an email with a consent link; if "
            "it hasn't arrived, raise a ticket on the Support page."
        ),
        "links": [{"label": "Support", "to": "/support"}],
    },
    {
        "roles": {ROLE_SUPERVISOR},
        "keywords": ["student", "group", "register", "registration", "result", "consent"],
        "answer": (
            "The Supervisor section of the menu has Registration (register your "
            "students), Students, Groups and, once released, Results."
        ),
        "links": [
            {"label": "Students", "to": "/my-students"},
            {"label": "Groups", "to": "/my-groups"},
        ],
    },
    # --- Everyone --------------------------------------------------------------
    {
        "roles": EVERYONE,
        "keywords": ["profile", "photo", "avatar", "my details", "change my name"],
        "answer": "Open My Profile to see and update your details and photo.",
        "links": [{"label": "My Profile", "to": "/profile"}],
    },
    {
        "roles": EVERYONE,
        "keywords": ["password", "log in", "login", "sign in"],
        "answer": (
            "To reset your password, sign out and choose Forgot password on the "
            "sign-in page. If you still can't sign in, raise a ticket on the "
            "Support page."
        ),
        "links": [{"label": "Support", "to": "/support"}],
    },
    # --- The three questions the assistant leads with --------------------------
    {
        "roles": ADMIN,
        "keywords": ["what should i do", "what do i do", "where do i start", "get started", "getting started", "next step"],
        "answer": (
            "Start at Admin for an overview. A year usually runs: open Registration "
            "in Management, check accounts in Users, form groups in Groups, set "
            "Tasks, start the challenge in Management, then mark in Grading and "
            "release Results."
        ),
        "links": [
            {"label": "Admin", "to": "/admin"},
            {"label": "Management", "to": "/management"},
        ],
    },
    {
        "roles": PARTICIPANTS,
        "keywords": ["what should i do", "what do i do", "where do i start", "get started", "getting started", "next step"],
        "answer": (
            "Check Home for what's coming up, then open Groups to see your group's "
            "tasks and talk to your group. Keep an eye on Announcements and Events. "
            + _BEFORE_START + " Meanwhile, make sure your profile is up to date."
        ),
        "links": [
            {"label": "Home", "to": "/dashboard"},
            {"label": "Groups", "to": "/groups"},
        ],
    },
    {
        "roles": {ROLE_SUPERVISOR},
        "keywords": ["what should i do", "what do i do", "where do i start", "get started", "getting started", "next step"],
        "answer": (
            "Use Registration in the Supervisor section to register your students, "
            "then follow them in Students and Groups."
        ),
        "links": [{"label": "Students", "to": "/my-students"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["feature", "what can i do", "what can", "function", "overview", "page"],
        "answer": (
            "Admin covers Users, Guardians, Views, Groups, Tasks, Role Tasks, Group "
            "Plans, System Emails, Grading and Management. Analytics reports on the "
            "programme, and Support Tickets holds users' requests. Ask me about any "
            "of them."
        ),
        "links": [
            {"label": "Admin", "to": "/admin"},
            {"label": "Analytics", "to": "/analytics"},
        ],
    },
    {
        "roles": MEMBERS,
        "keywords": ["feature", "what can i do", "what can", "function", "overview", "page"],
        "answer": (
            "BIOTech Connect has Home (what's coming up), Groups (your group's tasks, "
            "meetings, discussion and submission), Events, Announcements, Resources, "
            "My Profile and Support. " + _BEFORE_START
        ),
        "links": [{"label": "Home", "to": "/dashboard"}],
    },
    {
        "roles": EVERYONE,
        "keywords": ["help", "support", "ticket", "contact", "admin", "stuck", "problem", "issue", "bug", "error"],
        "answer": (
            "Raise a ticket on the Support page and the BIOTech Futures team will "
            "reply there. You can also email {email}."
        ),
        "links": [{"label": "Support", "to": "/support"}],
    },
]

FALLBACK = {
    "answer": (
        "Sorry, I can only help with using BIOTech Connect and I don't have an "
        "answer for that. Try asking about groups, resources, events or your "
        "profile, or raise a ticket on the Support page. You can also email {email}."
    ),
    "links": [{"label": "Support", "to": "/support"}],
}


def _words(text):
    return " ".join(re.findall(r"[a-z0-9']+", text.lower()))


def _score(entry, words):
    return sum(1 for keyword in entry["keywords"] if re.search(r"\b" + re.escape(keyword), words))


def answer(question, role):
    """The reply to ``question`` for a user whose role is ``role``."""
    words = _words(question)
    visible = [e for e in ENTRIES if e["roles"] is EVERYONE or role in e["roles"]]
    best = max(visible, key=lambda e: _score(e, words))
    matched = _score(best, words) > 0
    reply = best if matched else FALLBACK
    return {
        "answer": reply["answer"].format(email=settings.SUPPORT_EMAIL),
        "links": reply["links"],
        "matched": matched,
    }
