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
        "keywords": ["resource usage", "resource analytics", "resource statistics", "daily usage", "资源统计", "资源使用", "资源分析"],
        "answer": (
            "Open Analytics > Resources. It shows recorded clicks, unique users and active resources. "
            "Use the date controls and resource selections to explore usage; search and audience filters "
            "narrow the details table. Export CSV offers Summary, Details and Daily usage by resource. "
            "Summary covers figures and charts; Details follows the table filters; Daily usage provides "
            "per-resource daily facts. Audience means who can access a resource, not who clicked it."
        ),
        "links": [{"label": "Resources Analytics", "to": "/analytics/resources"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["export csv", "analytics export", "export statistics", "export analytics", "导出统计", "统计导出", "导出 csv"],
        "answer": (
            "Open the relevant Analytics page and select its year, dates and filters before Export CSV. "
            "Summary includes the page's figures and charts with scope notes; Details, where offered, "
            "exports the filtered records. Groups also exports students without a group; Resources "
            "offers daily usage by resource. Email Logs has per-send recipient CSV downloads. "
            "Read each export's dates and availability notes; unavailable values are not zero."
        ),
        "links": [{"label": "Analytics", "to": "/analytics"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["email monitoring", "email analytics", "delivery status", "recipient csv", "opened", "quota", "邮件统计", "邮件分析", "收件人", "打开率"],
        "answer": (
            "Analytics > Email Monitoring shows attempted, delivered and failed recipients in a rolling "
            "24-hour window, with separate mailbox usage. Email Logs keeps the latest 100 sends per "
            "email type; filter or search it and use a send's CSV to inspect captured recipients. "
            "Opened, clicked and spam metrics are unavailable without provider events. "
            "Role attribution uses an announcement's current single-role audience, not historical roles."
        ),
        "links": [{"label": "Email Monitoring", "to": "/analytics/email"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["activity analytics", "daily active", "weekly active", "monthly active", "dau", "wau", "mau", "活跃用户", "活跃度"],
        "answer": (
            "Analytics > Activity uses recorded login events. Daily, weekly and monthly active counts "
            "are unique users over 1, 7 and 30 days ending on the selected date. Change dates, interval, "
            "role or activity status to explore the records. These are login measures, not every kind "
            "of platform engagement. Account deactivation is separate from login inactivity."
        ),
        "links": [{"label": "Activity Analytics", "to": "/analytics/activity"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["groups analytics", "group statistics", "without a mentor", "unassigned students", "分组统计", "未分组", "缺少导师"],
        "answer": (
            "Analytics > Groups shows group status, mentor coverage, student assignment and group sizes. "
            "Its follow-up lists identify students without a group and groups without mentors. "
            "Export CSV offers Summary, group Details and Students without a group. "
            "Use the year control and read scope notes: current membership and historical activity "
            "are different facts."
        ),
        "links": [{"label": "Groups Analytics", "to": "/analytics/groups"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["mentors analytics", "mentor statistics", "mentor utilisation", "mentor capacity", "导师统计", "导师容量"],
        "answer": (
            "Analytics > Mentors shows assignment, utilisation, available capacity and engagement. "
            "Select the analytics year, inspect mentors with available capacity, and compare login "
            "or message activity. Account status, group allocation and activity are distinct measures. "
            "Export CSV offers a page Summary and one Details row per mentor with capacity, groups "
            "and messages."
        ),
        "links": [{"label": "Mentors Analytics", "to": "/analytics/mentors"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["registration analytics", "registration statistics", "registration completion", "registration follow up", "注册统计", "注册完成", "监护人审批统计"],
        "answer": (
            "Analytics > Registration shows account creation trends, guardian completion and follow-up "
            "records. Set trend dates and interval; choose Missing guardian details or Awaiting guardian "
            "approval to filter the follow-up table. Clicking an age bucket also filters follow-up. "
            "Summary exports page figures; Details exports the filtered students. Fully registered "
            "here means guardian permission has been received."
        ),
        "links": [{"label": "Registration Analytics", "to": "/analytics/registration"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["messages analytics", "message analytics", "message statistics", "messages over time", "消息统计", "消息分析"],
        "answer": (
            "Analytics > Messages reports recorded messages by date, group and user. Set the date "
            "range and interval, switch Groups or Users, and apply group or role filters. "
            "Details and its CSV follow their selected scope. Read chart labels: all-time totals "
            "and selected-period counts can differ. Current roles and memberships are not historical snapshots."
        ),
        "links": [{"label": "Messages Analytics", "to": "/analytics/messages"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["users analytics", "user statistics", "participant statistics", "users by role", "用户统计", "参与者统计"],
        "answer": (
            "Analytics > Users shows participant counts by role, login distribution, registration "
            "trends, interests and regions. Choose a year and use Export CSV for Summary or Details. "
            "Current account status and login recency are different measures; a past-year filter "
            "does not reconstruct every historical role or group attribute."
        ),
        "links": [{"label": "Users Analytics", "to": "/analytics/users"}],
    },
    {
        "roles": ADMIN,
        "keywords": ["how many", "current count", "live data", "real time", "目前有多少", "实时数据", "查询数据库"],
        "answer": (
            "I explain how to use BIOTech Connect but cannot query its live database or read the "
            "current dashboard figures. Open Analytics and the relevant page to see the recorded "
            "counts, dates and last-updated time. I can explain the available filters, metrics and exports."
        ),
        "links": [{"label": "Analytics", "to": "/analytics"}],
    },
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
    return " ".join(re.findall(r"[\w']+", text.lower()))


def _score(entry, words):
    return sum(
        1 for keyword in entry["keywords"]
        if re.search((r"\b" if keyword.isascii() else "") + re.escape(keyword), words)
    )


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
