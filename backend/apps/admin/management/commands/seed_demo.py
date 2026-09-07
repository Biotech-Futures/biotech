"""The dataset the manual test checklist is written against.

``.capstone/自测清单-工单系统.md`` opens by telling the reader to sign in as
``student@example.com``. Until this command existed that account came from
nowhere: it had been created by hand, months ago, in one person's local
database. Anybody else cloning the repository got a schema with no rows in
it, could not sign in, and could not run a single one of the checklist's
items. This command is the answer to "where does the data come from".

It is not ``seed_dummy_data``. That one manufactures three hundred
``@seed.biotech.test`` users to give the admin list something to paginate;
volume is the point and nothing in it is named. Here the opposite is true:
every account, group and ticket exists because some numbered item in the
checklist needs it, and the accounts are named so two people describing a bug
are describing the same row.

Design notes worth knowing before editing:

* **Tickets are made by calling the lifecycle service, never by inserting
  rows.** Slower, and the only way to get a database that behaves like a used
  one: the numbering counter advances, the timeline carries its system
  messages, and — the reason it actually matters — claim/assign/resolve/reopen
  write the audit rows that the p52 dashboard's Flow card counts. Insert the
  rows directly and that card reads zero on a database full of tickets.

* **The clock is wound back afterwards.** Everything a fresh call makes is
  stamped "now", and a dashboard whose window is "the last 30 days" would show
  one busy afternoon. The timestamps are rewritten to spread the same tickets
  over six weeks, which is also the only way to have anything genuinely
  overdue.

* **Idempotent.** Rerunning tops up what is missing and resets the passwords,
  so a database somebody has been clicking around in heals instead of
  accumulating a second copy of itself.

Usage:
    python manage.py seed_demo --settings=config.settings_local
    python manage.py seed_demo --settings=config.settings_local --wipe-tickets
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.announcements.models import Announcement
from apps.chat.models.messages import Messages
from apps.events.models import Events
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership
from apps.resources.models import (
    ResourceLabel, Resources, RoleAssignmentHistory, Roles,
)
from apps.tickets.models import (
    SupportScope, Ticket, TicketCategory, TicketMessage,
)
from apps.tickets.services import lifecycle
from apps.users.models.admin_scope import AdminScope

# Published on purpose: these accounts only ever exist in a DEBUG database,
# and the checklist prints the password next to every sign-in step.
PASSWORD = "Demo1234!"

# One account per role the checklist needs to distinguish between, plus three
# extra students abroad because the queue's region filter and the dashboard's
# region breakdown are both empty with a single country in the data.
PEOPLE = [
    # key            email                     first      last        role         country
    ("student",     "student@example.com",    "Ava",     "Nguyen",   "student",    "Australia"),
    ("student_vn",  "student2@example.com",   "Minh",    "Tran",     "student",    "Vietnam"),
    ("student_br",  "student3@example.com",   "Lucas",   "Silva",    "student",    "Brazil"),
    ("student_cn",  "student4@example.com",   "Wei",     "Zhang",    "student",    "China"),
    ("mentor",      "mentor@example.com",     "Priya",   "Patel",    "mentor",     "Australia"),
    ("mentor2",     "mentor2@example.com",    "Omar",    "Haddad",   "mentor",     "Australia"),
    ("supervisor",  "supervisor@example.com", "Grace",   "Okafor",   "supervisor", "Australia"),
    ("admin",       "admin@example.com",      "Dana",    "Ellis",    "admin",      "Australia"),
    # Support-capable and deliberately NOT an admin. The whole Support role
    # exists because the client asked for someone who works the queue without
    # being an administrator, and this is the only account that proves it.
    ("support",     "support@example.com",    "Sana",    "Reid",     "mentor",     "Australia"),
]

# The three Support Centre topic cards, worded exactly as SupportCentrePage.vue
# words them. The cards link to the resource library filtered by a label whose
# name matches the card title *exactly*, so these strings are load-bearing:
# change one here without changing the other and the card silently stops being
# a link — it keeps rendering, just as plain text, and nothing reports it.
#
# Three cards rather than one per category: these are a self-serve shortcut for
# the topics people actually look up, not a mirror of the eight-item dropdown.
# Eight cards would mean the client has to author eight labelled collections
# before any of them works.
HELP_LABELS = [
    "Account and access",
    "Registration",
    "Certificates and records",
]

# What each ticket becomes. Read as: who raised it, what it is about, how many
# days ago, and how far along it got.
#
#   open        nobody has touched it
#   overdue     open, old, and with support all that time — the red card
#   claimed     somebody owns it, no reply yet
#   replied     owned and answered, still in progress
#   pending     answered with a question, waiting on the requester
#   resolved    answered and closed
#   reopened    closed, then the requester came back
#   handed_off  claimed by one agent, passed to another
TICKETS = [
    ("student",    TicketCategory.ACCOUNT_ACCESS,       "Cannot sign in on my phone",                 40, "resolved"),
    ("student",    TicketCategory.CERTIFICATES_RECORDS, "Certificate has my name misspelled",         38, "resolved"),
    ("student_vn", TicketCategory.ACCOUNT_ACCESS,       "Login code email never arrives",             36, "resolved"),
    ("student_br", TicketCategory.REGISTRATION,         "I was placed in the wrong group",            35, "reopened"),
    ("mentor",     TicketCategory.HELP_STUDENT_GROUP,   "Two of my students cannot see the workspace", 33, "resolved"),
    ("student_cn", TicketCategory.ACCOUNT_ACCESS,       "Password reset link expired twice",          31, "resolved"),
    ("supervisor", TicketCategory.CERTIFICATES_RECORDS, "Bulk download of certificates fails",        29, "handed_off"),
    ("student",    TicketCategory.GENERAL_QUESTION,     "How do I change my project title",           27, "resolved"),
    ("student_vn", TicketCategory.CERTIFICATES_RECORDS, "No certificate after finishing",             25, "pending"),
    ("student_br", TicketCategory.ACCOUNT_ACCESS,       "Account says deactivated",                   24, "resolved"),
    ("mentor2",    TicketCategory.TECHNICAL_ISSUE,      "Cannot upload a resource to my group",       22, "resolved"),
    ("student_cn", TicketCategory.TECHNICAL_ISSUE,      "Group chat will not load images",            21, "replied"),
    ("student",    TicketCategory.ACCOUNT_ACCESS,       "Changed schools, need my email updated",     19, "resolved"),
    ("supervisor", TicketCategory.HELP_MENTOR,          "Our mentor has not replied in two weeks",    18, "resolved"),
    ("student_vn", TicketCategory.TECHNICAL_ISSUE,      "Deadline shown in the wrong timezone",       16, "reopened"),
    ("student_br", TicketCategory.CERTIFICATES_RECORDS, "Transcript request for my school",           15, "pending"),
    ("mentor",     TicketCategory.ACCOUNT_ACCESS,       "Two accounts with my address",               14, "handed_off"),
    ("student",    TicketCategory.OTHER,                "Feedback about the Symposium day",           12, "resolved"),
    ("student_cn", TicketCategory.CERTIFICATES_RECORDS, "Name shown in English only",                 11, "replied"),
    ("student_vn", TicketCategory.ACCOUNT_ACCESS,       "Cannot turn on notifications",               10, "claimed"),
    # Old, and the ball has been with support the whole time. These are the
    # overdue ones: the red card counts tickets awaiting a support reply for
    # longer than the window their priority allows — not tickets that have
    # never been answered, which is the rule the client replaced on
    # 2026-09-04.
    ("student_br", TicketCategory.REGISTRATION,         "Nobody replied about my group swap",          9, "overdue"),
    ("student",    TicketCategory.CERTIFICATES_RECORDS, "Still waiting on my certificate",             8, "overdue"),
    ("mentor2",    TicketCategory.ACCOUNT_ACCESS,       "Locked out since the weekend",                7, "overdue"),
    ("student_cn", TicketCategory.TECHNICAL_ISSUE,      "Submission page rejects my file",             5, "replied"),
    ("supervisor", TicketCategory.HELP_STUDENT_GROUP,   "Need to move three students",                 4, "claimed"),
    ("student_vn", TicketCategory.CERTIFICATES_RECORDS, "Certificate PDF will not open",               3, "pending"),
    # Raised in the last few hours, so they are genuinely waiting rather than
    # late. Fractional days on purpose: a normal-priority ticket is overdue
    # after 24 hours, so anything a whole day old would arrive already red and
    # the Overdue card would equal the Open card on a fresh database.
    ("student",    TicketCategory.GENERAL_QUESTION,     "Where do I upload the science report",     0.6, "open"),
    ("student_br", TicketCategory.ACCOUNT_ACCESS,       "Email address has a typo",                 0.4, "open"),
    ("mentor",     TicketCategory.HELP_STUDENT_GROUP,   "Student cannot join the meeting",          0.2, "open"),
    ("student_cn", TicketCategory.ACCOUNT_ACCESS,       "Reset code goes to my old address",       0.05, "open"),
]

BODY = (
    "Hi, I have been trying to sort this out on my own and have not managed "
    "it. Could someone take a look when you get a chance? Happy to send a "
    "screenshot if that helps. Thanks."
)
SUPPORT_REPLY = (
    "Thanks for getting in touch. I have had a look at your account and can "
    "see what is going on. I have made the change on our side, so it should "
    "work next time you sign in."
)
SUPPORT_QUESTION = (
    "Thanks for reporting this. Could you tell me which browser you are using "
    "and whether you see any error message on the screen? That will let me "
    "narrow it down."
)
USER_FOLLOW_UP = "That did not fix it, unfortunately. It is still doing the same thing."

# Four questions students actually asked in the group chat because there was
# nowhere else to ask them. They are here as the before picture: the demo is
# more convincing when somebody can see what the enquiry system replaced.
CHAT = [
    ("student",    "Morning everyone. Has anyone started on the poster yet?"),
    ("mentor",     "Not yet. I will put some notes together this week."),
    ("student",    "Quick one — does anyone know who I ask about my certificate? I cannot find anywhere to email."),
    ("student_vn", "Same, I have been trying to work out who to contact for two weeks."),
    ("mentor",     "I am not sure either, sorry. I think there is an address somewhere on the website?"),
    ("student",    "Found it, thanks. Will try that."),
    ("student_vn", "Also is the deadline midnight our time or Sydney time? It shows something different for me."),
    ("mentor",     "Sydney time I believe, but do not quote me on that."),
    ("student",    "Right, that is what I thought. Thanks."),
    ("supervisor", "Reminder that the draft is due at the end of next week."),
    ("student_vn", "Noted, thank you."),
    ("student",    "One more — my account said deactivated this morning and now it is fine. Is that normal?"),
    ("mentor",     "That does not sound normal. Might be worth reporting."),
    ("student",    "To who though? That is the bit I keep getting stuck on."),
    ("supervisor", "Let me find out and come back to you."),
    ("mentor",     "Good luck with the drafts everyone."),
    ("student_vn", "Thanks all."),
]


class Command(BaseCommand):
    help = "Seed the demo dataset the manual ticket checklist is written against."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wipe-tickets",
            action="store_true",
            help="Delete every ticket first, then seed a fresh set.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Run even with DEBUG off. There is no good reason to.",
        )

    def handle(self, *args, **opts):
        if not settings.DEBUG and not opts["force"]:
            # Every account below has the same published password.
            raise CommandError(
                "seed_demo refuses to run with DEBUG off. Pass --force only if "
                "you are certain this is not a real environment."
            )

        # Ticket creation, replies and resolutions each queue an email on
        # commit. None of them are wanted here, and on a machine with real SMTP
        # settings they would be genuine mail to addresses that do not exist.
        # Swapped rather than skipped so the send path still runs and a
        # traceback in it would still surface.
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

        if opts["wipe_tickets"]:
            count = Ticket.objects.count()
            Ticket.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"  removed {count} existing tickets"))

        countries = self._geography()
        people = self._people(countries)
        self._help_articles(people)
        group = self._group_and_chat(people)
        self._events(people)
        self._announcements(people)
        self._tickets(people)
        self._summary(people, group)

    # ------------------------------------------------------------ reference
    def _geography(self):
        """Countries first: User.country is PROTECT and not optional in practice.

        New South Wales is the only state created. The platform asks for one
        on Australian accounts and nothing in the checklist reads it.
        """
        countries = {}
        for name in ("Australia", "Vietnam", "Brazil", "China"):
            countries[name], _ = Countries.objects.get_or_create(country_name=name)
        CountryStates.objects.get_or_create(
            country=countries["Australia"], state_name="New South Wales",
        )
        return countries

    def _people(self, countries):
        """The nine accounts, their roles, and the two access rows.

        Passwords are reset on every run. A checklist that opens with a
        password is worthless if somebody changed it three weeks ago and the
        next person cannot get past the login screen.
        """
        User = get_user_model()
        now = timezone.now()
        people = {}

        for key, email, first, last, role, country in PEOPLE:
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "country": countries[country],
                },
            )
            user.first_name, user.last_name = first, last
            user.country = countries[country]
            user.set_password(PASSWORD)
            user.save()
            # activate() and not is_active=True: the model says the two status
            # fields are kept in step by this method and that new code must
            # not set either of them directly.
            user.activate()

            role_row, _ = Roles.objects.get_or_create(role_name=role)
            # valid_to NULL is what "currently holds this role" means, and the
            # ticket module snapshots the requester's role through it. Without
            # this the dashboard's User type breakdown is entirely Unknown.
            RoleAssignmentHistory.objects.get_or_create(
                user=user, role=role_row, valid_to=None,
                defaults={"valid_from": now - timedelta(days=90)},
            )
            people[key] = user

        AdminScope.objects.get_or_create(user=people["admin"])
        SupportScope.objects.get_or_create(user=people["support"])
        # Named for what it proves rather than who it is: an admin is
        # support-capable without a SupportScope row, and the roster screen
        # says so in as many words.
        return people

    def _help_articles(self, people):
        """One labelled resource per Support Centre card.

        The cards are links only when a label of the same name exists, and
        they fail silently when it does not — they simply render as plain
        text and nobody notices the help articles are unreachable. Seeding
        the labels is what makes that half of the page testable at all.
        """
        author = people["admin"]
        for label_name in HELP_LABELS:
            label, _ = ResourceLabel.objects.get_or_create(name=label_name)
            resource, created = Resources.objects.get_or_create(
                name=f"Getting started: {label_name}",
                defaults={
                    "description": f"A short guide covering {label_name.lower()}.",
                    "kind": Resources.ResourceKind.PAGE,
                    # Public, so a student sees it without any role or group
                    # rule having to line up first.
                    "visibility_scope": Resources.VisibilityScope.PUBLIC,
                    "uploaded_by": author,
                },
            )
            if created or not resource.labels.filter(pk=label.pk).exists():
                resource.labels.add(label)

    def _group_and_chat(self, people):
        group, _ = Groups.objects.get_or_create(group_name="Team Biosensor")
        second, _ = Groups.objects.get_or_create(group_name="Team Microplastics")

        memberships = [
            (group, "student", GroupMembership.MembershipRoleChoices.STUDENT),
            (group, "student_vn", GroupMembership.MembershipRoleChoices.STUDENT),
            (group, "mentor", GroupMembership.MembershipRoleChoices.MENTOR),
            (group, "supervisor", GroupMembership.MembershipRoleChoices.SUPERVISOR),
            (second, "student_br", GroupMembership.MembershipRoleChoices.STUDENT),
            (second, "student_cn", GroupMembership.MembershipRoleChoices.STUDENT),
            (second, "mentor2", GroupMembership.MembershipRoleChoices.MENTOR),
        ]
        for target, key, role in memberships:
            GroupMembership.objects.get_or_create(
                group=target, user=people[key],
                defaults={"membership_role": role},
            )

        if not Messages.objects.filter(group=group).exists():
            start = timezone.now() - timedelta(days=6)
            for index, (key, text) in enumerate(CHAT):
                Messages.objects.create(
                    group=group, sender_user=people[key], message_text=text,
                    sent_at=start + timedelta(minutes=17 * index),
                )
        return group

    def _events(self, people):
        now = timezone.now()
        schedule = [
            ("Project kick-off briefing", -20, 1),
            ("Poster design workshop", -6, 2),
            ("Mentor drop-in session", 3, 1),
            ("Submission Q&A", 9, 1),
            ("Symposium rehearsal", 16, 3),
        ]
        for name, day_offset, hours in schedule:
            start = now + timedelta(days=day_offset)
            Events.objects.get_or_create(
                event_name=name,
                defaults={
                    "description": f"{name}. Open to everyone in the program.",
                    "start_datetime": start,
                    "ends_datetime": start + timedelta(hours=hours),
                    "host_user": people["admin"],
                    "location": "Online",
                },
            )

    def _announcements(self, people):
        now = timezone.now()
        posts = [
            ("Welcome to the 2026 challenge", 21),
            ("Poster templates are now available", 9),
            ("Submission window opens next week", 2),
        ]
        for title, days_ago in posts:
            Announcement.objects.get_or_create(
                title=title,
                defaults={
                    "body": f"{title}. Full details are in the resources section.",
                    "author_user": people["admin"],
                    "published_at": now - timedelta(days=days_ago),
                },
            )

    # -------------------------------------------------------------- tickets
    def _tickets(self, people):
        """Thirty tickets, each driven through the real lifecycle service.

        Skipped entirely if tickets already exist. Running this twice would
        otherwise leave sixty, and the checklist's paging items count pages.
        """
        if Ticket.objects.exists():
            self.stdout.write(
                "  tickets already present, left alone "
                "(use --wipe-tickets to rebuild them)"
            )
            return

        agents = [people["support"], people["admin"]]
        made = []

        for index, (who, category, subject, days_ago, outcome) in enumerate(TICKETS):
            requester = people[who]
            agent = agents[index % len(agents)]
            other_agent = agents[(index + 1) % len(agents)]

            ticket = lifecycle.create_ticket(
                user=requester, category=category, subject=subject, body=BODY,
            )
            self._advance(ticket, outcome, agent, other_agent, requester)
            made.append((ticket.pk, days_ago, outcome))

        self._wind_back_the_clock(made)
        self.stdout.write(self.style.SUCCESS(f"  tickets created: {len(made)}"))

    def _advance(self, ticket, outcome, agent, other_agent, requester):
        """Walk one ticket to where its scenario says it should end up."""
        if outcome in ("open", "overdue"):
            return

        lifecycle.claim(ticket=ticket, actor=agent)
        ticket.refresh_from_db()
        if outcome == "claimed":
            return

        if outcome == "handed_off":
            lifecycle.assign(ticket=ticket, actor=agent, assignee=other_agent)
            return

        if outcome == "pending":
            # One action, not a reply followed by a status change: only this
            # path makes the email say it is waiting on the requester.
            lifecycle.add_support_reply(
                ticket=ticket, actor=agent, body=SUPPORT_QUESTION,
                move_to_pending=True,
            )
            return

        lifecycle.add_support_reply(ticket=ticket, actor=agent, body=SUPPORT_REPLY)
        ticket.refresh_from_db()
        if outcome == "replied":
            return

        lifecycle.resolve(ticket=ticket, actor=agent)
        ticket.refresh_from_db()
        if outcome == "resolved":
            return

        if outcome == "reopened":
            # The requester replying to a resolved ticket is what reopens it,
            # and it is the only thing that writes a reopen audit row.
            lifecycle.add_user_reply(
                ticket=ticket, user=requester, body=USER_FOLLOW_UP,
            )

    def _wind_back_the_clock(self, made):
        """Spread the tickets over six weeks.

        Every row above was written seconds ago. Left that way the dashboard
        shows a single spike, "average time to first reply" is a few
        milliseconds, and nothing is old enough to be overdue — the three
        things the p52 items actually look at.

        Done with one queryset update per ticket rather than through the
        service layer: these are timestamps being corrected, not events
        happening, and routing them through the lifecycle would write a second
        round of audit rows and system messages for changes that never
        occurred.

        The one rule this has to keep: **only write shapes the state machine
        can reach.** A column set here that no service call would have set is
        a row nothing in the product can produce, and every screen reading it
        then reports something impossible. Two of those were shipped in this
        method and are named where they were fixed below.
        """
        now = timezone.now()
        for pk, days_ago, outcome in made:
            created = now - timedelta(days=days_ago)
            # The moments this ticket actually passed through, named once.
            # The columns below and the timeline further down both read them,
            # so the ticket and its own messages cannot disagree about when
            # something happened.
            claimed_at = created + timedelta(hours=2)
            handed_off_at = created + timedelta(hours=3)
            replied_at = created + timedelta(hours=5)
            resolved_at = created + timedelta(days=1)
            reopened_at = now - timedelta(hours=6)

            # When each clock last moved. The requester's clock moves on the
            # events they can see; the support clock moves on those and on the
            # silent ones too, so they part company on exactly one outcome.
            #
            # Read off the last thing the lifecycle did rather than fixed at
            # "two hours after it was raised": a ticket whose newest timeline
            # entry is stamped three hours after its own "last activity" is
            # another shape no service call produces, and the queue sorts on
            # that column.
            last_activity = {
                "open": created,
                "overdue": created,
                "claimed": claimed_at,
                "handed_off": claimed_at,
                "replied": replied_at,
                "pending": replied_at,
                "resolved": resolved_at,
                "reopened": reopened_at,
            }[outcome]
            fields = {
                "created_at": created,
                "updated_at": last_activity,
                # The hand-off is silent on the requester's timeline
                # (03-state-machine.md §4), so it moves this one alone.
                "support_updated_at": (
                    handed_off_at if outcome == "handed_off" else last_activity
                ),
            }
            # An answered ticket needs its first reply to sit between being
            # raised and now, or "average time to first reply" comes out
            # negative.
            #
            # Listed by outcome rather than by exclusion, because the excluded
            # list had grown wrong: handed_off was getting a first-response
            # date and there is no reply anywhere on it. add_support_reply is
            # the only writer of that column, and an agent passing a ticket to
            # a colleague has not answered anybody. It also counted the ticket
            # into "average time to first reply" and, until 2026-09-04, took
            # it out of Overdue.
            if outcome in ("replied", "pending", "resolved", "reopened"):
                fields["first_response_at"] = replied_at
            # resolve() writes the status and the date in one update, so this
            # is the only outcome that ends up carrying one. handed_off was in
            # this branch as well and finishes in_progress, which left a
            # resolution date on a ticket the state machine says is still
            # being worked: the dashboard counted more resolved tickets than
            # the average it printed beside them was taken over.
            if outcome == "resolved":
                fields["resolved_at"] = resolved_at
            if outcome == "reopened":
                # Reopened after the fact, so it is live again and recent.
                fields["resolved_at"] = None

            # The Overdue clock has to move with the rest, or the red card
            # reads zero on a database that is meant to have a backlog in it.
            #
            # It is the anchor the badge is measured from — when the ball last
            # landed with support — so it is set for exactly the outcomes
            # where support owes an answer, and left null for the rest. The
            # lifecycle service already put the right shape in place while the
            # tickets were being built; this only ages the ones that carry a
            # value, and that is what makes the "overdue" rows actually red.
            if outcome in ("open", "overdue", "claimed", "handed_off"):
                # Nobody has answered, so the clock has been running since
                # they raised it. handed_off belongs here and was in the
                # "not our move" branch: claiming a ticket and passing it on
                # answers nobody, and nulling the anchor made a ticket that
                # had sat unanswered for a month one the badge could never
                # reach. That is the Overdue count under-reporting itself.
                fields["awaiting_support_since"] = created
            elif outcome == "reopened":
                # Live again, and with us since the requester came back.
                fields["awaiting_support_since"] = reopened_at
            else:
                # Answered, waiting on the requester, or done. Not our move.
                fields["awaiting_support_since"] = None

            Ticket.objects.filter(pk=pk).update(**fields)
            last_message = self._wind_back_the_timeline(pk, outcome, {
                "created": created,
                "claimed": claimed_at,
                "replied": replied_at,
                "resolved": resolved_at,
                "reopened": reopened_at,
            })
            # Messages sharing a moment are spread a second apart to fix their
            # order, so the last one can land just after the moment the clocks
            # above were set to. Carry the clocks up to it: a timeline entry
            # newer than the ticket's own last activity is the shape those
            # clocks were written to avoid, and the queue sorts on that column.
            if last_message is not None and last_message > last_activity:
                caught_up = {"updated_at": last_message}
                # The hand-off keeps its own support clock: it is the one
                # outcome where the two deliberately part company.
                if outcome != "handed_off":
                    caught_up["support_updated_at"] = last_message
                Ticket.objects.filter(pk=pk).update(**caught_up)

    # One moment per message the lifecycle writes, in the order it writes
    # them. Read it as the timeline the reader of a demo ticket should see.
    #
    # The pair on every row is T1: the requester's own words and the
    # automatic acknowledgement, both inside the creation transaction. After
    # that each outcome adds what its own service calls add — and a hand-off
    # adds nothing, because it is silent on the timeline by design.
    TIMELINE = {
        "open":       ("created", "created"),
        "overdue":    ("created", "created"),
        "claimed":    ("created", "created", "claimed"),
        "handed_off": ("created", "created", "claimed"),
        "replied":    ("created", "created", "claimed", "replied"),
        # The reply and the move to pending user are one transaction, so they
        # share a moment.
        "pending":    ("created", "created", "claimed", "replied", "replied"),
        "resolved":   ("created", "created", "claimed", "replied", "resolved"),
        # The requester's follow-up and the "reopened" line are also one.
        "reopened":   ("created", "created", "claimed", "replied", "resolved",
                       "reopened", "reopened"),
    }

    def _wind_back_the_timeline(self, pk, outcome, anchors):
        """Move the ticket's own messages back with it.

        Without this the ticket says it was raised forty days ago and every
        message on it is stamped the second the seed ran, which is the first
        thing anybody opening a demo ticket sees. It also puts the requester's
        opening message after the resolution of their own enquiry.

        ``created_at`` on TicketMessage is a plain default and not
        ``auto_now_add`` (DEC-014⑤), so an update writes it.

        Returns the stamp on the last message, which can be a few seconds
        past the moment it was anchored to. The caller carries the ticket's
        own clocks up to it.
        """
        moments = [anchors[name] for name in self.TIMELINE[outcome]]
        ids = list(
            TicketMessage.objects.filter(ticket_id=pk)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        if len(ids) != len(moments):
            # Said out loud rather than absorbed. A mismatch means the
            # lifecycle writes a message this table does not know about, and
            # the fix is a line here, not a silent guess.
            self.stdout.write(self.style.WARNING(
                f"  ticket {pk} ({outcome}): {len(ids)} messages but "
                f"{len(moments)} moments — update TIMELINE in seed_demo"
            ))
        # Messages written in one transaction share a moment, and both
        # timelines order by created_at alone, with no second key:
        # views.py _visible_messages() and views_admin.py _detail(). Given
        # equal stamps the database is free to return them either way round,
        # and it does: a seeded run put the automatic acknowledgement above
        # the requester's own question on four of thirty tickets, and the
        # "reopened" line above the reply that reopened it.
        #
        # A second apart is enough to fix the order and small enough to still
        # read as one action. The offset is per position, so the run stays
        # reproducible.
        for offset, (message_id, moment) in enumerate(zip(ids, moments)):
            TicketMessage.objects.filter(pk=message_id).update(
                created_at=moment + timedelta(seconds=offset)
            )
        # Anything past the end of the table lands on the last known moment,
        # which is still inside the ticket's own lifetime.
        if len(ids) > len(moments):
            for offset, message_id in enumerate(ids[len(moments):], len(moments)):
                TicketMessage.objects.filter(pk=message_id).update(
                    created_at=moments[-1] + timedelta(seconds=offset)
                )
        if not ids:
            return None
        return moments[min(len(ids), len(moments)) - 1] + timedelta(
            seconds=len(ids) - 1
        )

    # -------------------------------------------------------------- summary
    def _summary(self, people, group):
        rows = [
            ("Students", "student@ student2@ student3@ student4@"),
            ("Mentors", "mentor@ mentor2@"),
            ("Supervisor", "supervisor@"),
            ("Admin", "admin@"),
            ("Support only (not an admin)", "support@"),
        ]
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("")
        self.stdout.write(f"  All accounts use the password: {PASSWORD}")
        self.stdout.write("  All addresses end in @example.com")
        self.stdout.write("")
        for label, who in rows:
            self.stdout.write(f"  {label:<30} {who}")
        self.stdout.write("")
        self.stdout.write(
            f"  {Ticket.objects.count()} tickets, "
            f"{Groups.objects.count()} groups, "
            f"{Events.objects.count()} events, "
            f"{Announcement.objects.count()} announcements, "
            f"{Messages.objects.filter(group=group).count()} chat messages"
        )
        self.stdout.write("")
        self.stdout.write("  Next: sign in to the student site as student@example.com")
        self.stdout.write("  and check that Support appears in the left-hand navigation.")
