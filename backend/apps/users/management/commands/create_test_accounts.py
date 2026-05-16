from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.groups.models import Countries, CountryStates, Tracks
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import (
    AdminProfile,
    AdminScope,
    MentorProfile,
    SupervisorProfile,
    User,
)


@dataclass(frozen=True)
class AccountSpec:
    key: str
    email: str
    first_name: str
    last_name: str
    role_name: str


DEFAULT_ACCOUNTS = (
    AccountSpec("global_admin", "global.admin@example.com", "Global", "Admin", "admin"),
    AccountSpec("track_admin", "track.admin@example.com", "Track", "Admin", "admin"),
    AccountSpec("mentor", "mentor@example.com", "Maya", "Mentor", "mentor"),
    AccountSpec("supervisor", "supervisor@example.com", "Sam", "Supervisor", "supervisor"),
    AccountSpec("user", "user@example.com", "Uma", "User", "basic_user"),
)


class Command(BaseCommand):
    help = "Create local test accounts: global admin, track admin, mentor, supervisor, and user."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="Password123!",
            help="Password used for newly created accounts. Default: Password123!",
        )
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Also reset passwords for accounts that already exist.",
        )
        parser.add_argument(
            "--email-domain",
            default="example.com",
            help="Override the email domain for default accounts.",
        )
        parser.add_argument(
            "--track",
            default="AUS-NSW",
            help="Track name used for track admin, mentor, supervisor, and user.",
        )
        parser.add_argument(
            "--country",
            default="Australia",
            help="Country name to create when the target track does not exist.",
        )
        parser.add_argument(
            "--state",
            default="NSW",
            help="State name to create when the target track does not exist.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        reset_password = options["reset_password"]
        email_domain = options["email_domain"].strip().lower()
        track = self._get_or_create_track(
            track_name=options["track"],
            country_name=options["country"],
            state_name=options["state"],
        )

        accounts = self._account_specs(email_domain=email_domain)
        created_users: list[tuple[AccountSpec, User, bool]] = []

        for spec in accounts:
            role = self._get_or_create_role(spec.role_name)
            user, created = self._get_or_create_user(
                spec=spec,
                password=password,
                reset_password=reset_password,
                track=track,
            )
            self._assign_role(user=user, role=role)
            self._ensure_profile_and_scope(spec=spec, user=user, track=track)
            created_users.append((spec, user, created))

        self.stdout.write(self.style.SUCCESS("Test accounts ready."))
        self.stdout.write(f"Password for new accounts: {password}")
        if not reset_password:
            self.stdout.write(
                "Existing account passwords were not changed. Use --reset-password to overwrite them."
            )
        self.stdout.write("")
        for spec, user, created in created_users:
            status = "created" if created else "updated"
            self.stdout.write(f"{spec.key:13} {user.email:32} {status}")

    def _account_specs(self, *, email_domain: str) -> tuple[AccountSpec, ...]:
        if email_domain == "example.com":
            return DEFAULT_ACCOUNTS

        specs = []
        for spec in DEFAULT_ACCOUNTS:
            local_part = spec.email.split("@", 1)[0]
            specs.append(
                AccountSpec(
                    key=spec.key,
                    email=f"{local_part}@{email_domain}",
                    first_name=spec.first_name,
                    last_name=spec.last_name,
                    role_name=spec.role_name,
                )
            )
        return tuple(specs)

    def _get_or_create_track(self, *, track_name: str, country_name: str, state_name: str) -> Tracks:
        country, _ = Countries.objects.get_or_create(country_name=country_name)
        state, _ = CountryStates.objects.get_or_create(country=country, state_name=state_name)
        track, _ = Tracks.objects.get_or_create(track_name=track_name, defaults={"state": state})
        return track

    def _get_or_create_role(self, role_name: str) -> Roles:
        role, _ = Roles.objects.get_or_create(role_name=role_name)
        return role

    def _get_or_create_user(
        self,
        *,
        spec: AccountSpec,
        password: str,
        reset_password: bool,
        track: Tracks,
    ) -> tuple[User, bool]:
        user, created = User.objects.get_or_create(
            email=spec.email.lower(),
            defaults={
                "first_name": spec.first_name,
                "last_name": spec.last_name,
                "track": track,
                "account_status": User.AccountStatus.ACTIVE,
                "is_active": True,
                "activated_at": timezone.now(),
            },
        )

        update_fields = []
        for field_name, value in (
            ("first_name", spec.first_name),
            ("last_name", spec.last_name),
            ("track", track),
        ):
            if getattr(user, field_name) != value:
                setattr(user, field_name, value)
                update_fields.append(field_name)

        if spec.key in {"global_admin", "track_admin"}:
            if not user.is_staff:
                user.is_staff = True
                update_fields.append("is_staff")
        elif user.is_staff:
            user.is_staff = False
            update_fields.append("is_staff")

        if not user.is_active or user.account_status != User.AccountStatus.ACTIVE:
            user.account_status = User.AccountStatus.ACTIVE
            user.is_active = True
            update_fields.extend(["account_status", "is_active"])
            if user.activated_at is None:
                user.activated_at = timezone.now()
                update_fields.append("activated_at")

        if created or reset_password:
            user.set_password(password)
            update_fields.append("password")

        if created:
            user.save()
        elif update_fields:
            user.save(update_fields=sorted(set(update_fields)))

        return user, created

    def _assign_role(self, *, user: User, role: Roles):
        now = timezone.now()
        future = now + timedelta(days=3650)

        RoleAssignmentHistory.objects.filter(
            user=user,
            valid_from__lte=now,
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=now)
        ).exclude(role=role).update(valid_to=now)

        active_assignment = RoleAssignmentHistory.objects.filter(
            user=user,
            role=role,
            valid_from__lte=now,
        ).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=now)).first()

        if active_assignment:
            return

        RoleAssignmentHistory.objects.get_or_create(
            user=user,
            role=role,
            valid_from=now,
            defaults={"valid_to": future},
        )

    def _ensure_profile_and_scope(self, *, spec: AccountSpec, user: User, track: Tracks):
        if spec.key == "global_admin":
            AdminProfile.objects.get_or_create(admin=user, defaults={"tracks": None})
            AdminScope.objects.get_or_create(user=user, is_global=True, track=None)
            AdminScope.objects.filter(user=user, is_global=False).delete()
            return

        if spec.key == "track_admin":
            AdminProfile.objects.get_or_create(admin=user, defaults={"tracks": [track.track_name]})
            AdminScope.objects.get_or_create(user=user, is_global=False, track=track)
            return

        if spec.key == "mentor":
            MentorProfile.objects.get_or_create(
                user=user,
                defaults={
                    "background": MentorProfile.BackgroundChoices.INDUSTRY,
                    "institution": "Biotech Futures Test Institute",
                    "mentor_reason": "Local functionality testing",
                    "max_group_count": 3,
                },
            )
            return

        if spec.key == "supervisor":
            SupervisorProfile.objects.get_or_create(
                user=user,
                defaults={"school_name": "Biotech Futures Test School"},
            )
