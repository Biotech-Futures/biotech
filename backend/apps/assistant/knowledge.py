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
            "Admin > Users has tabs for Users, Students, Mentors and Supervisors. "
            "Search and filter the list, open someone to edit their details, and "
            "use Import Students CSV or Import Mentors CSV to add people in bulk."
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
            "Admin > Groups: Add Group creates a group, and opening a group lets you "
            "add students to it. The matching panels match mentors to groups, and "
            "Matched Groups lists the groups that already have a mentor."
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
            "certificate", "certificate template", "signature", "document setup", "visibility",
        ],
        "answer": (
            "Admin > Management runs the year: Registration and Late Registration; "
            "Challenge Start (when the challenge starts, and which pages students, "
            "mentors and supervisors see); Submission Deadline; the Symposium "
            "(notifying finalists, their presentations and submissions); Results, "
            "Release Results and Document Setup (the directors' signatures and the "
            "Mark Summary and certificate templates); and New Year."
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
        "answer": "Support queue in the menu holds users' support requests, with its audit log and analytics.",
        "links": [{"label": "Support queue", "to": "/admin/tickets"}],
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
            "Discussion Board. To schedule a meeting, switch from Tasks to Meetings "
            "on the group page and give it a title, start time, duration, join link "
            "and description. " + _BEFORE_START
        ),
        "links": [{"label": "Groups", "to": "/groups"}],
    },
    {
        "roles": {ROLE_MENTOR},
        "keywords": ["availability", "available", "weekly", "mentor details", "capacity"],
        "answer": "In My Profile, keep your Mentor Details and your Weekly Availability up to date.",
        "links": [{"label": "My Profile", "to": "/profile"}],
    },
    {
        "roles": PARTICIPANTS,
        "keywords": ["group", "task", "team", "meeting", "plan"],
        "answer": (
            "Open Groups to reach your group's page. Its tabs are Tasks and Chat "
            "(tasks, meetings and the Discussion Board), Plan (when your group has "
            "plan tasks), Submission, Finalist (finalist groups only) and Results "
            "(once released). " + _BEFORE_START
        ),
        "links": [{"label": "Groups", "to": "/groups"}],
    },
    {
        "roles": PARTICIPANTS,
        "keywords": ["submit", "submission", "upload", "deadline", "poster", "question", "report", "prototype"],
        "answer": (
            "Open your group's Submission tab. It has three steps: Questions, Poster "
            "and Additional materials. Your team fills it in together and it saves "
            "automatically. Submit before the submission deadline; after the "
            "deadline it can no longer be edited."
        ),
        "links": [{"label": "Groups", "to": "/groups"}],
    },
    {
        "roles": PARTICIPANTS,
        "keywords": ["certificate", "mark summary", "result", "grade", "mark", "score", "feedback"],
        "answer": (
            "Once results are released, your group's page gets a Results tab with "
            "the Mark Summary and your certificates."
        ),
        "links": [{"label": "Groups", "to": "/groups"}],
    },
    {
        "roles": PARTICIPANTS,
        "keywords": ["home", "dashboard", "today", "role task", "next event"],
        "answer": "Home shows your Role Tasks, the next event and your group. " + _BEFORE_START,
        "links": [{"label": "Home", "to": "/dashboard"}],
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
            "their group. Your guardian gets an email with a link to the consent "
            "form. In My Profile > Guardian Details you can see where it stands and "
            "send the email again. Changing your guardian clears the consent until "
            "the new guardian signs."
        ),
        "links": [
            {"label": "My Profile", "to": "/profile"},
            {"label": "Support", "to": "/support"},
        ],
    },
    {
        "roles": {ROLE_SUPERVISOR},
        "keywords": ["student", "group", "register", "registration", "result", "consent"],
        "answer": (
            "The Supervisor section of the menu has Registration (register your "
            "students), Students, Groups and, once released, Results."
        ),
        "links": [
            {"label": "Registration", "to": "/supervisor/registration"},
            {"label": "Students", "to": "/my-students"},
            {"label": "Groups", "to": "/my-groups"},
        ],
    },
    # --- Everyone --------------------------------------------------------------
    {
        "roles": EVERYONE,
        "keywords": ["profile", "photo", "avatar", "my details", "change my name", "timezone", "time zone"],
        "answer": (
            "My Profile holds your personal information and timezone and, depending "
            "on your role, your student, guardian, mentor or supervisor details."
        ),
        "links": [{"label": "My Profile", "to": "/profile"}],
    },
    {
        "roles": EVERYONE,
        "keywords": ["password", "log in", "login", "sign in", "magic link", "forgot"],
        "answer": (
            "On the sign-in page, choose Forgot password? to reset your password, or "
            "use Magic Link to get a sign-in link by email instead. If you still "
            "can't sign in, raise a ticket on the Support page or email {email}."
        ),
        "links": [{"label": "Support", "to": "/support"}],
    },
    {
        "roles": EVERYONE,
        "keywords": ["search", "find a page", "dark mode", "dark theme", "night mode", "light mode"],
        "answer": (
            "Search Program at the top of every page jumps to a page by name, such "
            "as events or resources. The moon button next to it switches dark mode "
            "on and off."
        ),
        "links": [],
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
            "programme, and Support queue holds users' requests. Ask me about any "
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
            "Open Support to raise an enquiry with the BIOTech Futures team: pick a "
            "category and how urgent it is, and attach files if they help. Replies "
            "appear under My support tickets. Find help quickly links to help "
            "articles in Resources. You can also email {email}."
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


def visible_entries(role):
    """The entries a user whose role is ``role`` may be told."""
    return [e for e in ENTRIES if e["roles"] is EVERYONE or role in e["roles"]]


def answer(question, role):
    """The reply to ``question`` for a user whose role is ``role``."""
    words = _words(question)
    best = max(visible_entries(role), key=lambda e: _score(e, words))
    matched = _score(best, words) > 0
    reply = best if matched else FALLBACK
    return {
        "answer": reply["answer"].format(email=settings.SUPPORT_EMAIL),
        "links": reply["links"],
        "matched": matched,
    }
