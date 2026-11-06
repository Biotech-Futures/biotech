"""Create and remove a deterministic dataset through the real Django ORM."""

from __future__ import annotations

import os
import random
from datetime import time, timedelta

from django.db.models import Q

from dataset import (
    DATASET_NAME,
    DATASET_VERSION,
    SCENARIO_ANALYTICS_COVERAGE,
    DatasetConfig,
)

from verification import (
    EMAIL_DOMAIN,
    EMAIL_SUFFIX,
    LOGIN_ENTITY,
    MANIFEST_ENTITY,
    ROW_PREFIX,
    compute_fingerprint,
    dataset_exists,
    snapshot_counts,
    unmanaged_business_counts,
)


FIRST_NAMES = (
    "Ava", "Liam", "Mia", "Noah", "Zoe", "Ethan", "Aria", "Lucas",
    "Chloe", "Kai", "Isla", "Omar", "Priya", "Wei", "Sofia", "Diego",
    "Nina", "Arjun", "Leila", "Hiro", "Grace", "Mateo", "Yuki", "Amara",
)
LAST_NAMES = (
    "Nguyen", "Patel", "Kim", "Silva", "Okafor", "Zhang", "Rossi",
    "Haddad", "Novak", "Mensah", "Suzuki", "Costa", "Ali", "Ivanov",
    "Reyes", "Fischer", "Khan", "Larsen", "Mbeki", "Torres",
)
SCHOOLS = (
    "Harbourview High", "Northgate College", "Greenfield Academy",
    "Riverside High", "Westlake Secondary", "Summit Academy",
)
INSTITUTIONS = (
    "University of Sydney", "UNSW", "Monash University",
    "University of Melbourne", "ANU", "CSIRO",
)
INTERESTS = (
    "Genomics", "Bioinformatics", "Immunology", "Neuroscience",
    "Synthetic Biology", "Microbiology", "Biomedical Engineering", "Bioethics",
)
COUNTRIES = (
    ("Australia", ("NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT")),
    ("New Zealand", ()),
    ("Singapore", ()),
    ("United Kingdom", ()),
    ("United States", ()),
    ("India", ()),
)
TIMEZONES = ("Australia/Sydney", "Australia/Perth", "Pacific/Auckland", "Asia/Singapore", "UTC")
MESSAGE_TEXTS = (
    "Weekly update is ready for review.",
    "Can we confirm the next mentor meeting?",
    "I uploaded the revised research notes.",
    "The experiment results look promising.",
    "Please check the references before Friday.",
    "Thanks team, the presentation draft is much clearer.",
)
ANALYTICS_DELIVERY_HOUR_OFFSETS = {
    1: 1,
    2: 2,
    3: 3,
    5: 5,
    8: 8,
    13: 23,
    14: 24,
    15: 25,
}
ANALYTICS_EMAIL_ALERT_MIN_DELIVERIES = 60
ANALYTICS_EMAIL_ALERT_BURST_RANGE = range(9, 59)


class ExistingDatasetError(RuntimeError):
    pass


def _analytics_group_plan(config: DatasetConfig) -> dict[str, int | None]:
    """Return zero-based group slots reserved for deterministic edge states.

    Small configurations intentionally degrade instead of making configured row
    counts impossible.  In particular, a one-group dataset with messages keeps
    that group populated so message generation can still succeed.
    """

    plan = {"empty": None, "mentorless": None, "zero_messages": None}
    if config.scenario != SCENARIO_ANALYTICS_COVERAGE or not config.groups:
        return plan

    if config.groups >= 2 or not config.messages:
        plan["empty"] = 0

    member_slots = [
        index for index in range(config.groups) if index != plan["empty"]
    ]
    has_non_mentor_participant = bool(config.supervisors or config.students)
    if member_slots and (has_non_mentor_participant or not config.mentors):
        plan["mentorless"] = member_slots[0]

    potentially_populated = set()
    if config.supervisors:
        potentially_populated.update(member_slots)
    if config.mentors:
        potentially_populated.update(
            slot for slot in member_slots if slot != plan["mentorless"]
        )
    potentially_populated.update(member_slots[: config.students])

    if not config.messages and potentially_populated:
        plan["zero_messages"] = max(potentially_populated)
    elif len(potentially_populated) >= 2:
        zero_candidates = [
            slot
            for slot in member_slots
            if slot in potentially_populated and slot != plan["mentorless"]
        ]
        plan["zero_messages"] = (
            zero_candidates[0]
            if zero_candidates
            else sorted(potentially_populated)[-1]
        )
    return plan


def _resource_index_for_access(config: DatasetConfig, sequence: int) -> int:
    """Choose a zero-based resource index for a one-based access sequence."""

    if config.scenario != SCENARIO_ANALYTICS_COVERAGE or config.resources < 2:
        return ((sequence * 7) - 1) % config.resources

    # Keep the final resource untouched.  With at least three resources, put
    # approximately half of all events on the first resource and spread the
    # remainder across the middle resources.  Two-resource datasets safely
    # degrade to one hot and one zero-access resource.
    if config.resources == 2:
        return 0
    hotspot_count = (config.resource_accesses + 1) // 2
    if sequence <= hotspot_count:
        return 0
    return 1 + ((sequence - hotspot_count - 1) % (config.resources - 2))


def _student_group_slots(config: DatasetConfig) -> list[int]:
    """Order non-empty group slots so scarce students establish edge states."""

    plan = _analytics_group_plan(config)
    available = [
        slot for slot in range(config.groups) if slot != plan["empty"]
    ]
    priority = []
    for name in ("mentorless", "zero_messages"):
        slot = plan[name]
        if slot is not None and slot in available and slot not in priority:
            priority.append(slot)
    return priority + [slot for slot in available if slot not in priority]


def _student_has_missing_guardian(config: DatasetConfig, index: int) -> bool:
    """Reserve registration follow-up rows in the Analytics coverage scenario."""

    return config.scenario == SCENARIO_ANALYTICS_COVERAGE and index % 10 == 0


def _student_is_unassigned(config: DatasetConfig, index: int) -> bool:
    """Reserve students without a group for the overview attention panel."""

    return config.scenario == SCENARIO_ANALYTICS_COVERAGE and index % 12 == 0


def _audience_role_name(sequence: int) -> str:
    """Rotate role-audience rows independently of the visibility-scope cycle."""

    return ("student", "mentor", "supervisor")[sequence % 3]


def _delivery_started_at(config: DatasetConfig, index: int, published_at):
    """Return a deterministic delivery start, including boundary coverage."""

    if config.scenario == SCENARIO_ANALYTICS_COVERAGE:
        # Announcements 1/2/3 are respectively global, Student-only, and
        # group-only. Announcements 5 and 8 are Mentor-only and Supervisor-only.
        # The client now anchors its rolling window to the current clock.
        # Keep role coverage recent and reserve separate 23/24/25-hour cases.
        if index in ANALYTICS_DELIVERY_HOUR_OFFSETS:
            started_at = config.as_of_datetime - timedelta(
                hours=ANALYTICS_DELIVERY_HOUR_OFFSETS[index]
            )
        elif (
            config.deliveries >= ANALYTICS_EMAIL_ALERT_MIN_DELIVERIES
            and index in ANALYTICS_EMAIL_ALERT_BURST_RANGE
        ):
            # Large demo datasets need enough genuine delivery attempts in the
            # rolling window to exercise the overview mailbox-usage warning.
            # Keep the default dataset unchanged while placing 50 custom runs
            # across the preceding 22 hours.
            started_at = config.as_of_datetime - timedelta(
                hours=1 + ((index - ANALYTICS_EMAIL_ALERT_BURST_RANGE.start) % 22),
                minutes=index,
            )
        else:
            started_at = config.as_of_datetime - timedelta(
                days=index % 45,
                hours=index % 8,
            )
            # Non-burst custom rows remain outside the rolling window.
            started_at = min(
                started_at,
                config.as_of_datetime - timedelta(hours=48),
            )
    else:
        started_at = config.as_of_datetime - timedelta(
            days=index % 45,
            hours=index % 8,
        )
    if started_at <= published_at:
        started_at = published_at + timedelta(hours=1)
    return started_at


def _one_case_insensitive(model, field: str, value: str, **defaults):
    existing = model.objects.filter(**{f"{field}__iexact": value}).order_by("pk").first()
    if existing is not None:
        return existing
    return model.objects.create(**{field: value}, **defaults)


def _reference_data():
    from apps.groups.models import Countries, CountryStates
    from apps.resources.models import ResourceLabel, ResourceType, Roles
    from apps.users.models import AreasOfInterest

    roles = {
        name: _one_case_insensitive(Roles, "role_name", name)
        for name in ("admin", "supervisor", "mentor", "student")
    }
    locations = []
    for country_name, state_names in COUNTRIES:
        country = _one_case_insensitive(Countries, "country_name", country_name)
        if state_names:
            for state_name in state_names:
                state = (
                    CountryStates.objects.filter(
                        country=country, state_name__iexact=state_name
                    )
                    .order_by("pk")
                    .first()
                )
                if state is None:
                    state = CountryStates.objects.create(
                        country=country, state_name=state_name
                    )
                locations.append((country, state))
        else:
            locations.append((country, None))

    interests = [
        _one_case_insensitive(AreasOfInterest, "interest_desc", name)
        for name in INTERESTS
    ]
    resource_type = _one_case_insensitive(
        ResourceType,
        "type_name",
        "Guide",
        type_description="Synthetic local development guide",
    )
    labels = [
        _one_case_insensitive(ResourceLabel, "name", name)
        for name in ("Research", "Programme", "Mentoring")
    ]
    return roles, locations, interests, resource_type, labels


def _status_for(role: str, index: int) -> str:
    from apps.users.models import User

    if role == "admin":
        return User.AccountStatus.ACTIVE
    pattern = (
        User.AccountStatus.ACTIVE,
        User.AccountStatus.ACTIVE,
        User.AccountStatus.ACTIVE,
        User.AccountStatus.PENDING,
        User.AccountStatus.ACTIVE,
        User.AccountStatus.INVITED,
        User.AccountStatus.DEACTIVATED,
        User.AccountStatus.SUSPENDED,
    )
    return pattern[(index - 1) % len(pattern)]


def _synthetic_role_password_hash(role):
    """Hash once per role/run for disposable accounts sharing one demo password.

    Keep Django's configured password hasher and a fresh salt; only the local
    fixture accounts share the result. Production user creation is unchanged.
    """
    from django.contrib.auth.hashers import make_password

    password = os.environ.get(
        f"LOCAL_DB_{role.upper()}_PASSWORD",
        os.environ.get("LOCAL_DB_LOGIN_PASSWORD", "LocalOnly!2026"),
    )
    return make_password(password or None)


def _create_users(config, rng, roles, locations, interests):
    from apps.resources.models import RoleAssignmentHistory
    from apps.users.models import (
        AdminProfile,
        AdminScope,
        MentorAvailability,
        MentorProfile,
        StudentProfile,
        StudentSupervisor,
        SupervisorProfile,
        User,
        UserInterest,
    )

    as_of = config.as_of_datetime
    buckets = {"admin": [], "supervisor": [], "mentor": [], "student": []}
    profiles = {"supervisor": []}
    role_counts = (
        ("admin", config.admins),
        ("supervisor", config.supervisors),
        ("mentor", config.mentors),
        ("student", config.students),
    )

    serial = 0
    for role, count in role_counts:
        password_hash = _synthetic_role_password_hash(role) if count else None
        for index in range(1, count + 1):
            serial += 1
            status = _status_for(role, index)
            country, state = locations[(serial - 1) % len(locations)]
            joined_at = as_of - timedelta(days=30 + (serial * 7) % 330, hours=serial % 12)
            if config.email_mode == 'custom' and config.email_batches:
                joined_at = min(joined_at, config.email_start_datetime - timedelta(days=2))
            first_name = FIRST_NAMES[(serial - 1) % len(FIRST_NAMES)]
            last_name = LAST_NAMES[((serial - 1) * 3) % len(LAST_NAMES)]
            email = f"synthetic.{role}.{index:04d}@{EMAIL_DOMAIN}"
            # The synthetic address is already normalized, and all manager
            # defaults are explicit below. create() still runs User.save and
            # its post-save signals, without rehashing the same demo password.
            user = User.objects.create(
                email=email,
                password=password_hash,
                first_name=first_name,
                last_name=last_name,
                country=country,
                state=state,
                timezone=TIMEZONES[(serial - 1) % len(TIMEZONES)],
                account_status=status,
                is_active=status == User.AccountStatus.ACTIVE,
                is_staff=role == "admin",
                is_superuser=role == "admin",
                invited_at=joined_at,
                activated_at=(
                    joined_at + timedelta(days=1)
                    if status == User.AccountStatus.ACTIVE
                    else None
                ),
                date_joined=joined_at,
            )
            RoleAssignmentHistory.objects.create(
                user=user,
                role=roles[role],
                valid_from=joined_at,
                valid_to=None,
            )

            if role == "admin":
                AdminScope.objects.create(user=user)
                AdminProfile.objects.create(admin=user)
            elif role == "supervisor":
                profile = SupervisorProfile.objects.create(
                    user=user, school_name=SCHOOLS[(index - 1) % len(SCHOOLS)]
                )
                profiles["supervisor"].append(profile)
            elif role == "mentor":
                MentorProfile.objects.create(
                    user=user,
                    background=(
                        MentorProfile.BackgroundChoices.INDUSTRY
                        if index % 2
                        else MentorProfile.BackgroundChoices.PG
                    ),
                    institution=INSTITUTIONS[(index - 1) % len(INSTITUTIONS)],
                    mentor_reason="Synthetic mentor available for analytics testing.",
                    max_group_count=3,
                )
                MentorAvailability.objects.create(
                    mentor_user=user,
                    weekday=(index - 1) % 5,
                    start_time=time(hour=9 + index % 3),
                    end_time=time(hour=12 + index % 3),
                )
                MentorAvailability.objects.create(
                    mentor_user=user,
                    weekday=(index + 1) % 5,
                    start_time=time(hour=13),
                    end_time=time(hour=16),
                )
            else:
                supervisor = (
                    profiles["supervisor"][(index - 1) % len(profiles["supervisor"])]
                    if profiles["supervisor"]
                    else None
                )
                missing_guardian = _student_has_missing_guardian(config, index)
                permitted = not missing_guardian and index % 3 != 0
                student_profile = StudentProfile.objects.create(
                    user=user,
                    pg_first_name=f"Guardian{index}",
                    pg_last_name=last_name,
                    pg_email=(
                        None
                        if missing_guardian
                        else f"guardian.{index:04d}@{EMAIL_DOMAIN}"
                    ),
                    parent_guardian_flag=permitted,
                    supervisor=supervisor,
                    school_name=SCHOOLS[(index - 1) % len(SCHOOLS)],
                    year_lvl=str(9 + (index - 1) % 4),
                    has_join_permission=permitted,
                    joinperm_responseID=(f"SYNTH-{index:06d}" if permitted else None),
                )
                if supervisor is not None:
                    StudentSupervisor.objects.create(
                        student_user=student_profile,
                        supervisor_user=supervisor,
                        relationship_type=StudentSupervisor.RelationshipTypeChoices.TEACHER,
                    )

            if role in {"student", "mentor"}:
                chosen = rng.sample(interests, k=min(2, len(interests)))
                UserInterest.objects.bulk_create(
                    [UserInterest(user=user, interest=interest) for interest in chosen]
                )
            buckets[role].append(user)
    return buckets


def _create_groups(config, buckets):
    from apps.groups.models import GroupMembership, Groups
    from apps.users.models import MentorProfile

    as_of = config.as_of_datetime
    coverage_plan = _analytics_group_plan(config)
    groups = []
    group_members = {}
    for index in range(1, config.groups + 1):
        created_at = as_of - timedelta(days=150 - index % 45)
        group = Groups.objects.create(
            group_name=f"{ROW_PREFIX} Group {index:04d}",
            year=as_of.year,
            created_at=created_at,
        )
        groups.append(group)
        group_members[group.pk] = []
        group_slot = index - 1
        if group_slot == coverage_plan["empty"]:
            continue
        if buckets["mentor"] and group_slot != coverage_plan["mentorless"]:
            mentor = buckets["mentor"][(index - 1) % len(buckets["mentor"])]
            GroupMembership.objects.create(
                group=group,
                user=mentor,
                membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
                joined_at=created_at + timedelta(days=2),
            )
            group_members[group.pk].append(mentor)
        if buckets["supervisor"]:
            supervisor = buckets["supervisor"][(index - 1) % len(buckets["supervisor"])]
            GroupMembership.objects.create(
                group=group,
                user=supervisor,
                membership_role=GroupMembership.MembershipRoleChoices.SUPERVISOR,
                joined_at=created_at + timedelta(days=3),
            )
            group_members[group.pk].append(supervisor)

    student_groups = [groups[slot] for slot in _student_group_slots(config)]
    for index, student in enumerate(buckets["student"], start=1):
        if _student_is_unassigned(config, index):
            continue
        if not student_groups:
            break
        group = student_groups[(index - 1) % len(student_groups)]
        GroupMembership.objects.create(
            group=group,
            user=student,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
            joined_at=group.created_at + timedelta(days=4 + (index - 1) % 7),
        )
        group_members[group.pk].append(student)

    for mentor_index, mentor in enumerate(buckets["mentor"], start=1):
        assigned = sum(mentor in members for members in group_members.values())
        MentorProfile.objects.filter(user=mentor).update(
            max_group_count=max(assigned + (mentor_index % 3), 1)
        )
    return groups, group_members


def _create_messages(config, rng, groups, group_members):
    from apps.chat.models import MessageType, Messages

    populated = [group for group in groups if group_members[group.pk]]
    coverage_plan = _analytics_group_plan(config)
    if coverage_plan["zero_messages"] is not None:
        zero_message_group = groups[coverage_plan["zero_messages"]]
        message_groups = [group for group in populated if group != zero_message_group]
        # A very small custom dataset may not have enough users/groups to keep
        # the reserved group populated while also satisfying the message count.
        if message_groups:
            populated = message_groups
    rows = []
    for index in range(1, config.messages + 1):
        group = populated[(index - 1) % len(populated)]
        members = group_members[group.pk]
        sender = members[(index * 5 + rng.randrange(len(members))) % len(members)]
        sent_at = config.as_of_datetime - timedelta(
            days=(index * 7) % 120,
            hours=(index * 3) % 24,
            minutes=index % 60,
        )
        edited_at = sent_at + timedelta(minutes=5) if index % 17 == 0 else None
        deleted_at = sent_at + timedelta(minutes=8) if index % 29 == 0 else None
        rows.append(
            Messages(
                sender_user=sender,
                group=group,
                message_text=(
                    f"{ROW_PREFIX} message {index:07d}: "
                    f"{MESSAGE_TEXTS[(index - 1) % len(MESSAGE_TEXTS)]}"
                ),
                message_type=MessageType.TEXT,
                sent_at=sent_at,
                edited_at=edited_at,
                deleted_at=deleted_at,
                deleted_by=sender if deleted_at else None,
            )
        )
    if rows:
        Messages.objects.bulk_create(rows, batch_size=2000)


def _create_login_events(config, users):
    from apps.audit.models import AuditLog
    from apps.users.models import User

    active_users = [user for user in users if user.is_active]
    latest = {}
    rows = []
    for index in range(1, config.login_events + 1):
        user = active_users[(index * 11 - 1) % len(active_users)]
        created_at = config.as_of_datetime - timedelta(
            days=(index * 13) % 300,
            hours=(index * 7) % 24,
            minutes=index % 60,
        )
        if created_at <= user.date_joined:
            created_at = user.date_joined + timedelta(days=1, minutes=index % 60)
        rows.append(
            AuditLog(
                actor_user=user,
                entity_type=LOGIN_ENTITY,
                entity_id=user.pk,
                action=AuditLog.ActionChoices.LOGIN,
                after_state={"dataset": DATASET_NAME, "sequence": index},
                created_at=created_at,
            )
        )
        if user.pk not in latest or created_at > latest[user.pk]:
            latest[user.pk] = created_at
    if rows:
        AuditLog.objects.bulk_create(rows, batch_size=2000)
    for user_id, last_login in latest.items():
        User.objects.filter(pk=user_id).update(last_login=last_login)


def _creator_role(user, buckets):
    from apps.tasks.models import CreatorRole

    if user in buckets["admin"]:
        return CreatorRole.GLOBAL_ADMIN
    if user in buckets["mentor"]:
        return CreatorRole.MENTOR
    if user in buckets["supervisor"]:
        return CreatorRole.SUPERVISOR
    return CreatorRole.STUDENT


def _create_tasks(config, buckets, groups):
    from apps.tasks.models import Task, TaskStatus, TaskType

    all_users = sum((buckets[name] for name in ("admin", "mentor", "supervisor", "student")), [])
    creator = all_users[0] if all_users else None
    rows = []
    statuses = tuple(TaskStatus.values)
    for index in range(1, config.tasks + 1):
        use_group = bool(groups) and (not all_users or index % 2 == 1)
        status = statuses[(index - 1) % len(statuses)]
        rows.append(
            Task(
                name=f"{ROW_PREFIX} Task {index:06d}",
                description="Deterministic local analytics task.",
                due_date=config.as_of_datetime + timedelta(days=(index % 61) - 30),
                status=status,
                completed=status == TaskStatus.DONE,
                task_type=TaskType.GROUP if use_group else TaskType.INDIVIDUAL,
                group=groups[(index - 1) % len(groups)] if use_group else None,
                assigned_user=(
                    None if use_group else all_users[(index - 1) % len(all_users)]
                ),
                created_by=creator,
                creator_role=_creator_role(creator, buckets) if creator else "global_admin",
                created_at=config.as_of_datetime - timedelta(days=index % 90),
            )
        )
    if rows:
        Task.objects.bulk_create(rows, batch_size=2000)


def _create_resources(config, roles, labels, resource_type, buckets, groups):
    from apps.resources.models import ResourceAudience, Resources

    if not config.resources:
        return []
    uploader = buckets["admin"][0]
    resources = []
    role_audience_sequence = 0
    for index in range(1, config.resources + 1):
        mode = (index - 1) % 3
        if mode == 0:
            scope = Resources.VisibilityScope.PUBLIC
            group = None
        elif mode == 1 or not groups:
            scope = Resources.VisibilityScope.ROLE
            group = None
        else:
            scope = Resources.VisibilityScope.GROUP
            group = groups[(index - 1) % len(groups)]
        resource = Resources.objects.create(
            name=f"{ROW_PREFIX} Resource {index:05d}",
            description="Synthetic resource metadata; no external file is stored.",
            type=resource_type,
            kind=Resources.ResourceKind.PAGE,
            group=group,
            visibility_scope=scope,
            uploaded_at=config.as_of_datetime - timedelta(days=index % 100),
            uploaded_by=uploader,
        )
        resource.labels.add(labels[(index - 1) % len(labels)])
        if scope == Resources.VisibilityScope.ROLE:
            ResourceAudience.objects.create(
                resource=resource,
                role=roles[_audience_role_name(role_audience_sequence)],
            )
            role_audience_sequence += 1
        resources.append(resource)
    return resources


def _create_resource_accesses(config, resources, users):
    from apps.resources.models import ResourceAccessEvent

    if not config.resource_accesses:
        return
    active_users = [user for user in users if user.is_active]
    rows = []
    for index in range(1, config.resource_accesses + 1):
        rows.append(
            ResourceAccessEvent(
                resource=resources[_resource_index_for_access(config, index)],
                user=active_users[(index - 1) % len(active_users)],
                created_at=config.as_of_datetime
                - timedelta(
                    days=(index * 11) % 120,
                    hours=(index * 5) % 24,
                    minutes=index % 60,
                ),
            )
        )
    ResourceAccessEvent.objects.bulk_create(rows, batch_size=2000)


def _create_announcements(config, roles, buckets, groups, group_members):
    from apps.announcements.models import Announcement, AnnouncementAudience

    if not config.announcements:
        return []
    author = buckets["admin"][0]
    announcements = []
    role_audience_sequence = 0
    active_role_available = {
        role_name: any(user.is_active for user in buckets[role_name])
        for role_name in ("student", "mentor", "supervisor")
    }
    populated_groups = [
        group
        for group in groups
        if any(user.is_active for user in group_members.get(group.pk, []))
    ]
    for index in range(1, config.announcements + 1):
        mode = (index - 1) % 3
        audience_role = None
        audience_group = None
        if mode == 0:
            visibility = Announcement.VisibilityScope.GLOBAL
            audience_key = ("global",)
        elif mode == 1:
            role_name = _audience_role_name(role_audience_sequence)
            role_audience_sequence += 1
            if active_role_available[role_name]:
                visibility = Announcement.VisibilityScope.ROLE_BASED
                audience_role = roles[role_name]
                audience_key = ("role", role_name)
            else:
                # A real notify call skips empty audiences. Preserve the
                # requested announcement/delivery counts by degrading to a
                # resolvable global audience instead of fabricating role
                # recipients that do not exist in a small custom dataset.
                visibility = Announcement.VisibilityScope.GLOBAL
                audience_key = ("global",)
        elif populated_groups:
            visibility = Announcement.VisibilityScope.ROLE_BASED
            audience_group = populated_groups[(index - 1) % len(populated_groups)]
            audience_key = ("group", audience_group.pk)
        else:
            visibility = Announcement.VisibilityScope.GLOBAL
            audience_key = ("global",)
        published_at = config.as_of_datetime - timedelta(days=index * 2)
        reserved_email_coverage = (
            config.scenario == SCENARIO_ANALYTICS_COVERAGE
            and (
                index in ANALYTICS_DELIVERY_HOUR_OFFSETS
                or (
                    config.deliveries >= ANALYTICS_EMAIL_ALERT_MIN_DELIVERIES
                    and any(
                        ((delivery_index - 1) % config.announcements) + 1 == index
                        for delivery_index in ANALYTICS_EMAIL_ALERT_BURST_RANGE
                        if delivery_index <= config.deliveries
                    )
                )
            )
        )
        announcement = Announcement.objects.create(
            author_user=author,
            title=f"{ROW_PREFIX} Announcement {index:05d}",
            body="Synthetic announcement content for local reporting tests.",
            visibility_scope=visibility,
            published_at=published_at,
            archived_at=(
                published_at + timedelta(days=7)
                if index % 5 == 0 and not reserved_email_coverage
                else None
            ),
        )
        if audience_role is not None:
            AnnouncementAudience.objects.create(
                announcement=announcement,
                role=audience_role,
            )
        elif audience_group is not None:
            AnnouncementAudience.objects.create(
                announcement=announcement,
                group=audience_group,
            )
        # Ephemeral generation metadata only; it is never persisted. Deliveries
        # with the same current audience can reuse one production resolver read.
        announcement._synthetic_audience_key = audience_key
        announcements.append(announcement)
    return announcements


def _create_deliveries(config, announcements, buckets):
    if not config.deliveries:
        return
    try:
        from apps.admin.services.announcement import resolve_announcement_recipient_emails
    except ImportError:
        # The client baseline keeps the same read-only production resolver
        # under its original private name; the school baseline exposes it.
        from apps.admin.services.announcement import (
            _resolve_recipient_emails as resolve_announcement_recipient_emails,
        )
    from apps.announcements.models import AnnouncementDelivery

    rows = []
    initiator = buckets["admin"][0]
    statuses = (
        AnnouncementDelivery.Status.SUCCESS,
        AnnouncementDelivery.Status.PARTIAL,
        AnnouncementDelivery.Status.FAILED,
    )
    recipient_emails_by_audience = {}
    for index in range(1, config.deliveries + 1):
        requested_status = statuses[(index - 1) % len(statuses)]
        announcement = announcements[(index - 1) % len(announcements)]
        audience_key = getattr(
            announcement,
            "_synthetic_audience_key",
            ("announcement", announcement.pk),
        )
        if audience_key not in recipient_emails_by_audience:
            recipient_emails_by_audience[audience_key] = sorted(
                set(
                    resolve_announcement_recipient_emails(
                        announcement.pk,
                        announcement.visibility_scope,
                    )
                )
            )
        recipient_emails = recipient_emails_by_audience[audience_key]
        recipient_count = len(recipient_emails)
        if not recipient_count:
            raise RuntimeError(
                "synthetic announcement audience resolved to zero recipients: "
                f"announcement={announcement.pk}"
            )
        status = requested_status
        if status == AnnouncementDelivery.Status.PARTIAL and recipient_count < 2:
            status = AnnouncementDelivery.Status.SUCCESS
        if status == AnnouncementDelivery.Status.SUCCESS:
            success_count, failure_count = recipient_count, 0
        elif status == AnnouncementDelivery.Status.PARTIAL:
            failure_count = min(2 + index % 3, recipient_count - 1)
            success_count = recipient_count - failure_count
        else:
            success_count, failure_count = 0, recipient_count
        started_at = _delivery_started_at(config, index, announcement.published_at)
        failed = [
            {
                "email": email,
                "error": "Synthetic local delivery failure",
            }
            for email in recipient_emails[: min(failure_count, 3)]
        ]
        rows.append(
            AnnouncementDelivery(
                announcement=announcement,
                initiated_by=initiator,
                started_at=started_at,
                completed_at=started_at + timedelta(seconds=20 + index),
                status=status,
                recipient_count=recipient_count,
                success_count=success_count,
                failure_count=failure_count,
                failed_recipients=failed,
                error_summary=(
                    "" if not failure_count else f"{failure_count} synthetic failure(s)"
                ),
            )
        )
    if rows:
        AnnouncementDelivery.objects.bulk_create(rows, batch_size=2000)


def _create_events(config, roles, buckets, groups):
    from apps.events.models import EventTargetGroup, EventTargetRole, Events

    host = buckets["admin"][0] if buckets["admin"] else None
    events = []
    formats = tuple(Events.EventFormat.values)
    types = tuple(Events.EventTypeChoices.values)
    for index in range(1, config.events + 1):
        start = config.as_of_datetime + timedelta(days=(index * 5) - 35, hours=index % 6)
        fmt = formats[(index - 1) % len(formats)]
        location = "Sydney Programme Centre" if fmt in {"in_person", "hybrid"} else None
        link = "https://example.invalid/team4-event" if fmt in {"virtual", "hybrid"} else None
        event = Events.objects.create(
            event_name=f"{ROW_PREFIX} Event {index:05d}",
            description="Synthetic local programme event.",
            event_type=types[(index - 1) % len(types)],
            start_datetime=start,
            ends_datetime=start + timedelta(hours=2),
            event_timezone="Australia/Sydney",
            location=location,
            location_link=link,
            event_format=fmt,
            host_user=host,
            max_attendees=50,
        )
        if index % 2 and groups:
            EventTargetGroup.objects.create(
                event=event, group=groups[(index - 1) % len(groups)]
            )
        else:
            EventTargetRole.objects.create(event=event, role=roles["student"])
        events.append(event)
    return events


def _create_rsvps(config, events, buckets):
    from apps.events.models import EventRsvp

    users = sum((buckets[name] for name in ("student", "mentor", "supervisor", "admin")), [])
    statuses = tuple(EventRsvp.RsvpStatus.values)
    rows = []
    for index in range(config.rsvps):
        event = events[index // len(users)]
        user = users[index % len(users)]
        status = statuses[index % len(statuses)]
        responded_at = (
            None
            if status == EventRsvp.RsvpStatus.PENDING
            else event.start_datetime - timedelta(days=2, minutes=index % 60)
        )
        rows.append(
            EventRsvp(
                event=event,
                user=user,
                rsvp_status=status,
                responded_at=responded_at,
            )
        )
    if rows:
        EventRsvp.objects.bulk_create(rows, batch_size=2000)


def generate_dataset(
    config: DatasetConfig, *, replace: bool, allow_existing_data: bool = False
) -> dict:
    from apps.audit.models import AuditLog

    config.validate()
    unmanaged = unmanaged_business_counts()
    if unmanaged and not allow_existing_data:
        raise ExistingDatasetError(
            "the database already contains non-generator business data "
            f"{unmanaged}; use a clean local database for identical team totals, or pass "
            "--allow-existing-data to preserve and combine it intentionally"
        )
    if dataset_exists():
        if not replace:
            raise ExistingDatasetError(
                "a Team 4 synthetic dataset already exists; pass --replace or run reset"
            )
        wipe_dataset()

    rng = random.Random(config.seed)
    roles, locations, interests, resource_type, labels = _reference_data()
    buckets = _create_users(config, rng, roles, locations, interests)
    groups, group_members = _create_groups(config, buckets)
    _create_messages(config, rng, groups, group_members)
    all_users = sum(
        (buckets[name] for name in ("admin", "supervisor", "mentor", "student")),
        [],
    )
    _create_login_events(config, all_users)
    _create_tasks(config, buckets, groups)
    resources = _create_resources(
        config, roles, labels, resource_type, buckets, groups
    )
    _create_resource_accesses(config, resources, all_users)
    announcements = _create_announcements(
        config,
        roles,
        buckets,
        groups,
        group_members,
    )
    if config.email_mode == 'coverage':
        _create_deliveries(config, announcements, buckets)
    from email_samples import create_email_samples
    create_email_samples(config, buckets, announcements)
    events = _create_events(config, roles, buckets, groups)
    _create_rsvps(config, events, buckets)

    fingerprint = compute_fingerprint()
    expected = snapshot_counts()
    expected["manifests"] = 1
    actor = (
        buckets["admin"][0]
        if buckets["admin"]
        else (all_users[0] if all_users else None)
    )
    manifest = {
        "dataset": DATASET_NAME,
        "version": DATASET_VERSION,
        "config": config.to_manifest(),
        "expected_counts": expected,
        "fingerprint": fingerprint,
        "unmanaged_counts_at_generation": unmanaged,
    }
    AuditLog.objects.create(
        actor_user=actor,
        entity_type=MANIFEST_ENTITY,
        entity_id=actor.pk if actor else 0,
        action=AuditLog.ActionChoices.IMPORT,
        after_state=manifest,
        created_at=config.as_of_datetime,
    )
    return manifest


def wipe_dataset() -> dict[str, int]:
    """Delete only rows owned by this generator; shared catalogues remain."""

    from apps.announcements.models import Announcement
    from apps.audit.models import AuditLog
    from apps.chat.models import Messages
    from apps.events.models import EventRsvp, Events
    from apps.groups.models import GroupMembership, Groups
    from apps.resources.models import (
        ResourceAccessEvent,
        Resources,
        RoleAssignmentHistory,
    )
    from apps.tasks.models import Task
    from apps.users.models import User

    users = User.objects.filter(email__endswith=EMAIL_SUFFIX)
    groups = Groups.objects.filter(group_name__startswith=ROW_PREFIX)
    resources = Resources.objects.filter(
        Q(name__startswith=ROW_PREFIX) | Q(uploaded_by__in=users)
    )
    counts = snapshot_counts()

    # Metrics have no dataset column; explicit audit markers own only the
    # synthetic rows, including their recipient children.
    from email_samples import owned_metrics, EMAIL_METRIC_ENTITY
    owned_metrics().delete()
    AuditLog.objects.filter(entity_type=EMAIL_METRIC_ENTITY).delete()

    AuditLog.objects.filter(
        Q(entity_type=MANIFEST_ENTITY)
        | Q(
            action=AuditLog.ActionChoices.LOGIN,
            actor_user__in=users,
            after_state__dataset=DATASET_NAME,
        )
        | Q(actor_user__in=users)
    ).delete()
    Messages.objects.filter(Q(group__in=groups) | Q(sender_user__in=users)).delete()
    EventRsvp.objects.filter(user__in=users).delete()
    ResourceAccessEvent.objects.filter(
        Q(resource__in=resources) | Q(user__in=users)
    ).delete()
    Events.objects.filter(
        Q(event_name__startswith=ROW_PREFIX) | Q(host_user__in=users)
    ).delete()
    resources.delete()
    Announcement.objects.filter(
        Q(title__startswith=ROW_PREFIX) | Q(author_user__in=users)
    ).delete()
    Task.objects.filter(
        Q(name__startswith=ROW_PREFIX)
        | Q(group__in=groups)
        | Q(assigned_user__in=users)
        | Q(created_by__in=users)
    ).delete()
    GroupMembership.objects.filter(Q(group__in=groups) | Q(user__in=users)).delete()
    groups.delete()
    RoleAssignmentHistory.objects.filter(user__in=users).delete()
    users.delete()
    return counts
