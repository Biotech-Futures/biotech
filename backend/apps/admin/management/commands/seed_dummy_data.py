"""Seed a large, realistic dummy dataset for exercising the admin bulk features.

Creates >=300 namespaced users spread across every axis the admin user list
filters on (role / state / active-vs-deactivated / in-group-vs-not / searchable
names) plus related groups, memberships, tasks, resources, announcements, events,
RSVPs and chat messages so the whole admin surface has data to page through.

Everything it writes is namespaced so it can be removed again:
  * users   -> email ends with ``@seed.biotech.test``
  * groups / resources / announcements / events -> name starts with ``[SEED]``

Usage:
  python manage.py seed_dummy_data --settings=config.settings_local --yes
  python manage.py seed_dummy_data --users 400 --yes
  python manage.py seed_dummy_data --wipe --yes      # remove a prior seed, then reseed
  python manage.py seed_dummy_data --wipe-only --yes # remove a prior seed and stop

Users are created through the same building blocks the admin "add user" service
uses (create_user + RoleAssignmentHistory + role profile + interests + AdminScope)
so the rows are indistinguishable from real admin-created accounts.
"""
import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.users.models import (
    User, StudentProfile, SupervisorProfile, MentorProfile, UserInterest,
)
from apps.users.models.admin_scope import AdminScope
from apps.resources.models import (
    Roles, RoleAssignmentHistory, Resources, ResourceAudience,
)
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership
from apps.tasks.models import Task, TaskType, TaskStatus, CreatorRole
from apps.events.models import Events, EventRsvp, EventTargetRole, EventTargetGroup
from apps.announcements.models import Announcement, AnnouncementAudience
from apps.chat.models.messages import Messages, MessageType
from apps.admin.services.user import (
    _UNSET, upsert_student_profile, upsert_supervisor_profile,
    upsert_mentor_profile, sync_user_interests, resolve_role_id,
)

SEED_EMAIL_DOMAIN = "seed.biotech.test"
SEED_PREFIX = "[SEED]"

# --- content pools (Faker is not installed; stdlib random + curated lists) ----
FIRST_NAMES = [
    "Ava", "Liam", "Mia", "Noah", "Zoe", "Ethan", "Aria", "Lucas", "Chloe", "Kai",
    "Isla", "Omar", "Priya", "Wei", "Sofia", "Diego", "Nina", "Arjun", "Leila", "Hiro",
    "Grace", "Mateo", "Yuki", "Amara", "Ravi", "Elena", "Tariq", "Freya", "Jin", "Nadia",
    "Oscar", "Ingrid", "Sanjay", "Maya", "Felix", "Aisha", "Bruno", "Lena", "Idris", "Tara",
]
LAST_NAMES = [
    "Nguyen", "Patel", "Kim", "Silva", "Okafor", "Zhang", "Rossi", "Haddad", "Novak", "Mensah",
    "Suzuki", "Costa", "Ali", "Ivanov", "Reyes", "Fischer", "Khan", "Larsen", "Mbeki", "Torres",
    "Chen", "Dubois", "Owusu", "Bianchi", "Sharma", "Kowalski", "Yamada", "Ahmed", "Petrov", "Cruz",
]
SCHOOLS = [
    "Riverside High", "Northgate College", "St. Aloysius", "Greenfield Academy",
    "Harbourview High", "Kingsley Grammar", "Westlake Secondary", "Eastwood College",
    "Meridian High", "Summit Academy", "Brookvale High", "Cardinal College",
]
INSTITUTIONS = [
    "University of Sydney", "Monash University", "UNSW", "University of Melbourne",
    "ANU", "University of Queensland", "CSIRO", "Garvan Institute",
    "Walter and Eliza Hall Institute", "QIMR Berghofer", "Baker Institute",
]
INTERESTS = [
    "Genomics", "Bioinformatics", "Immunology", "Neuroscience", "Molecular Biology",
    "Synthetic Biology", "Biochemistry", "Microbiology", "Cell Biology", "Data Science",
    "Robotics", "Genetics", "Ecology", "Biomedical Engineering", "Pharmacology",
    "Marine Biology", "Epidemiology", "Nanotechnology", "Bioethics", "Structural Biology",
]
GROUP_TOPICS = [
    "CRISPR Research", "Cancer Genomics", "Neural Interfaces", "Vaccine Design",
    "Bioinformatics Pipeline", "Marine Ecology", "Synthetic Cells", "Protein Folding",
    "Microbiome Study", "Gene Therapy", "Antibiotic Resistance", "Stem Cell Biology",
    "Climate Genomics", "Biosensors", "Immunotherapy", "Plant Genetics",
    "Metabolic Engineering", "Viral Evolution", "Tissue Engineering", "Drug Discovery",
]
TASK_TITLES = [
    "Draft the literature review", "Prepare weekly progress update", "Run the PCR assay",
    "Analyse sequencing results", "Design the survey instrument", "Book lab time",
    "Write the abstract", "Peer-review a teammate's section", "Clean the dataset",
    "Build the poster", "Rehearse the presentation", "Submit ethics form",
    "Calibrate the instrument", "Summarise the findings", "Plan next sprint",
]
RESOURCE_NAMES = [
    "Lab Safety Handbook", "Intro to Bioinformatics", "Gel Electrophoresis Guide",
    "Citation & Referencing Cheatsheet", "Poster Design Template", "Statistics Primer",
    "Consent Form Template", "Reading List: Genomics", "Presentation Rubric",
    "Data Management Plan", "Mentor Expectations", "Weekly Report Template",
]
ANNOUNCEMENT_TITLES = [
    "Welcome to the program!", "Submission deadline reminder", "Guest lecture next week",
    "Lab access hours updated", "Mid-program check-in", "Poster session scheduled",
    "Mentor matching complete", "Holiday break notice", "New resources available",
    "Feedback survey open", "Showcase event details", "Code of conduct refresher",
]
MESSAGE_SNIPPETS = [
    "Hey team, how's everyone going with their sections?",
    "I pushed the latest results to the shared drive.",
    "Can we move our meeting to Thursday?", "Great work on the assay today!",
    "Does anyone have the reference for that paper?", "I'll take the intro section.",
    "The sequencing came back — looks promising.", "Reminder: draft due Friday.",
    "Should we add a control group?", "Nice, that figure looks much clearer now.",
    "I'm stuck on the stats, could use a hand.", "Booked the lab for 2pm tomorrow.",
    "Let's sync before the presentation.", "Uploaded the poster draft for review.",
    "Thanks everyone, really solid progress this week.",
]
STATES_BY_COUNTRY = {
    "Australia": ["New South Wales", "Victoria", "Queensland", "Western Australia",
                  "South Australia", "Tasmania", "Australian Capital Territory"],
    "Singapore": ["Central Region", "East Region", "West Region"],
    "United Kingdom": ["England", "Scotland", "Wales"],
    "United States": ["California", "New York", "Texas", "Massachusetts"],
    "India": ["Maharashtra", "Karnataka", "Delhi"],
    "New Zealand": ["Auckland", "Wellington"],
}


class Command(BaseCommand):
    help = "Seed a large realistic dummy dataset to exercise admin bulk features."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=320,
                            help="Number of seed users to create (default 320).")
        parser.add_argument("--wipe", action="store_true",
                            help="Remove any prior seed data before seeding.")
        parser.add_argument("--wipe-only", action="store_true",
                            help="Remove prior seed data and exit (no reseed).")
        parser.add_argument("--yes", action="store_true",
                            help="Skip the interactive confirmation.")
        parser.add_argument("--force", action="store_true",
                            help="Allow running when DEBUG is False (guard override).")

    # ------------------------------------------------------------------ handle
    def handle(self, *args, **opts):
        if not settings.DEBUG and not opts["force"]:
            raise CommandError(
                "Refusing to run with DEBUG=False. Pass --force if you really "
                "mean to seed this environment."
            )

        db = settings.DATABASES["default"]
        target = f"{db.get('NAME')} @ {db.get('HOST', 'local')}"
        self.stdout.write(self.style.WARNING(f"Target database: {target}"))

        if not opts["yes"]:
            confirm = input("This writes/removes dummy data. Type 'yes' to continue: ")
            if confirm.strip().lower() != "yes":
                raise CommandError("Aborted.")

        random.seed(42)

        if opts["wipe"] or opts["wipe_only"]:
            self._wipe()
            if opts["wipe_only"]:
                self.stdout.write(self.style.SUCCESS("Wipe complete."))
                return

        self._resolve_roles()
        state_ids = self._ensure_states()
        buckets = self._create_users(opts["users"], state_ids)
        groups = self._create_groups(buckets)
        self._create_tasks(groups, buckets)
        self._create_resources_and_announcements(groups, buckets)
        self._create_events_and_rsvps(groups, buckets)
        self._create_chat(groups)
        self._summary(buckets, groups)

    # ------------------------------------------------------- reference data
    def _resolve_roles(self):
        self.role_ids = {name: resolve_role_id(name)
                         for name in ("student", "mentor", "supervisor", "admin")}

    def _ensure_states(self):
        """Create a clean set of CountryStates and return a list of their ids."""
        ids = []
        for country_name, states in STATES_BY_COUNTRY.items():
            country, _ = Countries.objects.get_or_create(country_name=country_name)
            for state_name in states:
                state, _ = CountryStates.objects.get_or_create(
                    country=country, state_name=state_name)
                ids.append(state.id)
        self.stdout.write(f"  states available: {len(ids)}")
        return ids

    # ------------------------------------------------------------- users
    def _create_users(self, total, state_ids):
        n_admin = round(total * 0.06)
        n_sup = round(total * 0.14)
        n_mentor = round(total * 0.20)
        n_student = total - n_admin - n_sup - n_mentor

        buckets = {"admin": [], "supervisor": [], "mentor": [], "student": []}
        counter = 0

        def name():
            return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)

        # order matters: supervisors before students so supervisor links resolve
        plan = (
            [("admin", n_admin), ("supervisor", n_sup),
             ("mentor", n_mentor), ("student", n_student)]
        )
        for role, count in plan:
            for _ in range(count):
                counter += 1
                fn, ln = name()
                email = f"seed.{role}.{counter}@{SEED_EMAIL_DOMAIN}"
                is_active = random.random() < 0.65
                # admins may be geography-less; everyone else needs a state
                state_id = (random.choice(state_ids)
                            if role != "admin" or random.random() < 0.5 else None)
                try:
                    user = self._create_one(
                        role=role, email=email, first_name=fn, last_name=ln,
                        state_id=state_id, is_active=is_active,
                        supervisors=buckets["supervisor"],
                    )
                    buckets[role].append(user)
                except Exception as exc:  # keep going; report at the end
                    self.stderr.write(f"  skip {email}: {exc}")
                if counter % 50 == 0:
                    self.stdout.write(f"  users created: {counter}/{total}")

        made = sum(len(v) for v in buckets.values())
        self.stdout.write(self.style.SUCCESS(f"  users created: {made}"))
        return buckets

    def _create_one(self, *, role, email, first_name, last_name, state_id,
                    is_active, supervisors):
        now = timezone.now()
        account_status = "active" if is_active else "deactivated"
        interests = random.sample(INTERESTS, k=random.randint(2, 4))
        with transaction.atomic():
            user = User.objects.create_user(
                email=email, first_name=first_name, last_name=last_name,
                password=None, state_id=state_id, is_active=is_active,
                account_status=account_status,
                is_staff=(role == "admin"), is_superuser=(role == "admin"),
                invited_at=now, activated_at=now if is_active else None,
            )
            RoleAssignmentHistory.objects.create(
                user_id=user.id, role_id=self.role_ids[role],
                valid_from=now, valid_to=None,
            )
            if role == "student":
                sup_email = _UNSET
                if supervisors and random.random() < 0.4:
                    sup_email = random.choice(supervisors).email
                upsert_student_profile(
                    user.id, first_name, last_name,
                    random.choice(SCHOOLS), random.randint(9, 12),
                    supervisor_email=sup_email,
                )
                sync_user_interests(user.id, interests)
            elif role == "mentor":
                upsert_mentor_profile(
                    user.id, background="Seed mentor background.",
                    institution=random.choice(INSTITUTIONS),
                    mentor_reason="Keen to support young researchers.",
                    max_group_count=random.randint(2, 4),
                )
                sync_user_interests(user.id, interests)
            elif role == "supervisor":
                upsert_supervisor_profile(user.id, random.choice(SCHOOLS))
            elif role == "admin":
                AdminScope.objects.get_or_create(user_id=user.id)
        return user

    # ------------------------------------------------------------ groups
    def _create_groups(self, buckets):
        """~40 groups. One mentor each, a few supervisors, 3-6 students. Leaves
        ~30% of students ungrouped and a couple of groups empty so the
        in-group / not-in-group filter has both sides."""
        mentors = buckets["mentor"]
        supervisors = buckets["supervisor"]
        students = buckets["student"][:]
        random.shuffle(students)
        # hold back ~30% of students as ungrouped
        groupable = students[: int(len(students) * 0.7)]

        groups = []
        n_groups = 40
        si = 0
        base = timezone.now() - timedelta(days=120)
        for i in range(n_groups):
            topic = GROUP_TOPICS[i % len(GROUP_TOPICS)]
            created = base + timedelta(days=random.randint(0, 60))
            group = Groups.objects.create(
                group_name=f"{SEED_PREFIX} {topic} {i + 1:02d}",
                created_at=created,
            )
            members = {"mentor": None, "supervisors": [], "students": []}

            # a couple of intentionally empty groups
            if i >= n_groups - 2:
                groups.append((group, members))
                continue

            if mentors:
                mentor = mentors[i % len(mentors)]
                GroupMembership.objects.create(
                    group=group, user=mentor,
                    membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
                    joined_at=created + timedelta(days=1),
                )
                members["mentor"] = mentor
            if supervisors and random.random() < 0.5:
                sup = random.choice(supervisors)
                GroupMembership.objects.create(
                    group=group, user=sup,
                    membership_role=GroupMembership.MembershipRoleChoices.SUPERVISOR,
                    joined_at=created + timedelta(days=1),
                )
                members["supervisors"].append(sup)

            size = random.randint(3, 6)
            for _ in range(size):
                if si >= len(groupable):
                    break
                student = groupable[si]
                si += 1
                GroupMembership.objects.create(
                    group=group, user=student,
                    membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
                    joined_at=created + timedelta(days=random.randint(2, 10)),
                )
                members["students"].append(student)
            groups.append((group, members))

        self.stdout.write(self.style.SUCCESS(f"  groups created: {len(groups)}"))
        return groups

    # ------------------------------------------------------------- tasks
    def _create_tasks(self, groups, buckets):
        admins = buckets["admin"]
        n_tasks = 0
        now = timezone.now()

        def rand_due():
            return now + timedelta(days=random.randint(-30, 45))

        def rand_status():
            status = random.choice(list(TaskStatus.values))
            return status, status == TaskStatus.DONE

        for group, members in groups:
            mentor = members["mentor"]
            author = mentor or (random.choice(admins) if admins else None)
            crole = CreatorRole.MENTOR if mentor else CreatorRole.GLOBAL_ADMIN
            for t in range(random.randint(2, 4)):
                status, completed = rand_status()
                parent = Task.objects.create(
                    name=f"{random.choice(TASK_TITLES)}",
                    description="Seed group task.",
                    task_type=TaskType.GROUP, group=group, assigned_user=None,
                    creator_role=crole, created_by=author,
                    status=status, completed=completed, due_date=rand_due(),
                )
                n_tasks += 1
                # subtasks on ~40% of group tasks
                if random.random() < 0.4:
                    for _ in range(random.randint(1, 3)):
                        s_status, s_done = rand_status()
                        Task.objects.create(
                            name=f"Subtask: {random.choice(TASK_TITLES)}",
                            description="Seed subtask.", parent=parent,
                            task_type=TaskType.GROUP, group=group, assigned_user=None,
                            creator_role=crole, created_by=author,
                            status=s_status, completed=s_done, due_date=rand_due(),
                        )
                        n_tasks += 1
            # individual tasks for grouped students
            for student in members["students"]:
                if random.random() < 0.6:
                    for _ in range(random.randint(1, 3)):
                        status, completed = rand_status()
                        Task.objects.create(
                            name=f"{random.choice(TASK_TITLES)}",
                            description="Seed individual task.",
                            task_type=TaskType.INDIVIDUAL, assigned_user=student,
                            group=None, creator_role=crole, created_by=author,
                            status=status, completed=completed, due_date=rand_due(),
                        )
                        n_tasks += 1
        self.stdout.write(self.style.SUCCESS(f"  tasks created: {n_tasks}"))

    # ------------------------------------------- resources & announcements
    def _create_resources_and_announcements(self, groups, buckets):
        admins = buckets["admin"]
        if not admins:
            self.stdout.write("  (no admin users; skipping resources/announcements)")
            return
        author = admins[0]
        role_objs = list(Roles.objects.filter(
            role_name__in=["student", "mentor", "supervisor"]))
        active_groups = [g for g, _ in groups if not g.deleted_at]

        n_res = 0
        for i, res_name in enumerate(RESOURCE_NAMES):
            mode = i % 3  # 0 global, 1 role_based, 2 group-attached
            group = None
            scope = "global"
            if mode == 1:
                scope = "role_based"
            elif mode == 2 and active_groups:
                group = random.choice(active_groups)
                scope = "role_based" if random.random() < 0.5 else "global"
            resource = Resources.objects.create(
                name=f"{SEED_PREFIX} {res_name}",
                description=f"Seed resource: {res_name}.",
                kind=Resources.ResourceKind.PAGE,
                visibility_scope=scope, group=group,
                uploaded_by=author,
                uploaded_at=timezone.now() - timedelta(days=random.randint(0, 60)),
            )
            n_res += 1
            if scope == "role_based" and role_objs:
                for role in random.sample(role_objs, k=random.randint(1, len(role_objs))):
                    ResourceAudience.objects.create(resource=resource, role=role)

        n_ann = 0
        for i, title in enumerate(ANNOUNCEMENT_TITLES):
            mode = i % 3  # 0 global, 1 role_based, 2 group-targeted
            published = timezone.now() - timedelta(days=random.randint(0, 45))
            scope = "global" if mode == 0 else "role_based"
            archived = (published + timedelta(days=random.randint(1, 10))
                        if random.random() < 0.25 else None)
            ann = Announcement.objects.create(
                author_user=author, title=f"{SEED_PREFIX} {title}",
                body=f"{title}\n\nThis is seed announcement content for testing.",
                visibility_scope=scope, published_at=published, archived_at=archived,
            )
            n_ann += 1
            if mode == 1 and role_objs:
                for role in random.sample(role_objs, k=random.randint(1, len(role_objs))):
                    AnnouncementAudience.objects.create(announcement=ann, role=role)
            elif mode == 2 and active_groups:
                for group in random.sample(active_groups,
                                           k=min(2, len(active_groups))):
                    AnnouncementAudience.objects.create(announcement=ann, group=group)

        self.stdout.write(self.style.SUCCESS(
            f"  resources created: {n_res}; announcements created: {n_ann}"))

    # -------------------------------------------------- events & rsvps
    def _create_events_and_rsvps(self, groups, buckets):
        admins = buckets["admin"]
        host = admins[0] if admins else None
        all_users = (buckets["student"] + buckets["mentor"]
                     + buckets["supervisor"])
        role_objs = list(Roles.objects.filter(
            role_name__in=["student", "mentor", "supervisor"]))
        active_groups = [g for g, _ in groups if not g.deleted_at]
        formats = list(Events.EventFormat.values)
        responded = ["accepted", "tentative", "declined", "waitlisted"]

        n_events = 0
        n_rsvps = 0
        for i in range(16):
            past = i % 2 == 0
            start = timezone.now() + timedelta(
                days=random.randint(-40, -2) if past else random.randint(2, 40),
                hours=random.randint(0, 8))
            end = start + timedelta(hours=random.randint(1, 3))
            fmt = formats[i % len(formats)]
            location = None
            location_link = None
            if fmt == "in_person":
                location = "Building 42, Room 101"
            elif fmt == "virtual":
                location_link = "https://example.zoom.us/j/seed"
            else:  # hybrid
                location = "Main Auditorium"
                location_link = "https://example.zoom.us/j/seed"
            event = Events.objects.create(
                event_name=f"{SEED_PREFIX} {random.choice(GROUP_TOPICS)} Workshop {i + 1}",
                description="Seed event for testing.",
                event_type=random.choice(list(Events.EventTypeChoices.values)),
                start_datetime=start, ends_datetime=end,
                event_format=fmt, location=location, location_link=location_link,
                host_user=host, max_attendees=random.choice([None, 20, 50]),
            )
            n_events += 1

            # targeting: ~60% untargeted, else role- or group-targeted
            roll = random.random()
            if roll < 0.2 and role_objs:
                EventTargetRole.objects.create(
                    event=event, role=random.choice(role_objs))
            elif roll < 0.4 and active_groups:
                EventTargetGroup.objects.create(
                    event=event, group=random.choice(active_groups))

            # RSVPs from a distinct sample of users
            if all_users:
                sample = random.sample(all_users, k=min(random.randint(4, 12),
                                                        len(all_users)))
                for user in sample:
                    status = random.choice(["pending"] + responded)
                    EventRsvp.objects.create(
                        event=event, user=user, rsvp_status=status,
                        responded_at=None if status == "pending"
                        else start - timedelta(days=1),
                    )
                    n_rsvps += 1
        self.stdout.write(self.style.SUCCESS(
            f"  events created: {n_events}; rsvps created: {n_rsvps}"))

    # ------------------------------------------------------------- chat
    def _create_chat(self, groups):
        n_msgs = 0
        for group, members in groups:
            participants = ([members["mentor"]] if members["mentor"] else []) \
                + members["supervisors"] + members["students"]
            participants = [p for p in participants if p is not None]
            if len(participants) < 2:
                continue
            base = (group.created_at or timezone.now()) + timedelta(days=2)
            count = random.randint(5, 15)
            for m in range(count):
                sender = random.choice(participants)
                sent = base + timedelta(days=m, minutes=random.randint(0, 600))
                if sent > timezone.now():
                    sent = timezone.now() - timedelta(minutes=random.randint(1, 60))
                edited_at = None
                deleted_at = None
                deleted_by = None
                if random.random() < 0.1:
                    edited_at = sent + timedelta(minutes=random.randint(1, 30))
                elif random.random() < 0.08:
                    deleted_at = sent + timedelta(minutes=random.randint(1, 30))
                    deleted_by = sender
                Messages.objects.create(
                    sender_user=sender, group=group,
                    message_text=random.choice(MESSAGE_SNIPPETS),
                    message_type=MessageType.TEXT, sent_at=sent,
                    edited_at=edited_at, deleted_at=deleted_at, deleted_by=deleted_by,
                )
                n_msgs += 1
        self.stdout.write(self.style.SUCCESS(f"  chat messages created: {n_msgs}"))

    # ------------------------------------------------------------- wipe
    def _wipe(self):
        """Remove a prior seed run. Order respects PROTECT FKs: messages
        (sender PROTECT) and resources (uploader PROTECT) go before users."""
        self.stdout.write(self.style.WARNING("Wiping prior seed data..."))
        seed_users = User.objects.filter(email__endswith=f"@{SEED_EMAIL_DOMAIN}")
        seed_groups = Groups.objects.filter(group_name__startswith=SEED_PREFIX)
        with transaction.atomic():
            Messages.objects.filter(group__in=seed_groups).delete()
            Messages.objects.filter(sender_user__in=seed_users).delete()
            Events.objects.filter(event_name__startswith=SEED_PREFIX).delete()  # cascades rsvps/targets
            EventRsvp.objects.filter(user__in=seed_users).delete()
            Resources.objects.filter(name__startswith=SEED_PREFIX).delete()      # cascades audiences
            Resources.objects.filter(uploaded_by__in=seed_users).delete()
            Announcement.objects.filter(title__startswith=SEED_PREFIX).delete()  # cascades audiences
            Announcement.objects.filter(author_user__in=seed_users).delete()
            Task.objects.filter(group__in=seed_groups).delete()
            Task.objects.filter(assigned_user__in=seed_users).delete()
            GroupMembership.objects.filter(group__in=seed_groups).delete()
            GroupMembership.objects.filter(user__in=seed_users).delete()
            seed_groups.delete()
            # user-owned rows that would orphan or block the delete
            UserInterest.objects.filter(user__in=seed_users).delete()
            RoleAssignmentHistory.objects.filter(user__in=seed_users).delete()
            MentorProfile.objects.filter(user__in=seed_users).delete()
            SupervisorProfile.objects.filter(user__in=seed_users).delete()
            StudentProfile.objects.filter(user__in=seed_users).delete()
            AdminScope.objects.filter(user__in=seed_users).delete()
            deleted, _ = seed_users.delete()
        self.stdout.write(self.style.SUCCESS(f"  wipe complete (removed {deleted} user-related rows)"))

    # ---------------------------------------------------------- summary
    def _summary(self, buckets, groups):
        self.stdout.write(self.style.SUCCESS("\nSeed complete. Distribution:"))
        for role in ("admin", "supervisor", "mentor", "student"):
            users = buckets[role]
            active = sum(1 for u in users if u.is_active)
            self.stdout.write(
                f"  {role:11s}: {len(users):4d}  "
                f"(active {active}, deactivated {len(users) - active})")
        total = sum(len(v) for v in buckets.values())
        active_total = sum(1 for v in buckets.values() for u in v if u.is_active)
        self.stdout.write(
            f"  {'TOTAL':11s}: {total:4d}  "
            f"(active {active_total}, deactivated {total - active_total})")
        self.stdout.write(f"  groups: {len(groups)}")
        self.stdout.write(self.style.SUCCESS(
            "\nUse the admin user list filters (role / state / status / in-group) "
            "and the bulk activate-deactivate + select-all-matching actions to test."))
