"""Seed one test account per role.

Idempotent: re-running upserts users, role assignments, profiles, and admin
scopes without creating duplicates. Intended for local/dev use only.

Run:
    venv/Scripts/python.exe manage.py seed_test_users
"""

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.groups.models import Countries, CountryStates, Tracks
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import (
    AdminProfile,
    AdminScope,
    MentorProfile,
    StudentProfile,
    SupervisorProfile,
    User,
)


DEFAULT_PASSWORD = "TestPass123!"

ACCOUNTS = [
    {"role": "student", "email": "student@test.local", "first": "Test", "last": "Student"},
    {"role": "mentor", "email": "mentor@test.local", "first": "Test", "last": "Mentor"},
    {"role": "supervisor", "email": "supervisor@test.local", "first": "Test", "last": "Supervisor"},
    {"role": "track-admin", "email": "track-admin@test.local", "first": "Test", "last": "TrackAdmin"},
    {"role": "global-admin", "email": "global-admin@test.local", "first": "Test", "last": "GlobalAdmin"},
]


class Command(BaseCommand):
    help = "Seed one test user per role (student, mentor, supervisor, track-admin, global-admin)."

    @transaction.atomic
    def handle(self, *args, **opts):
        track = self._ensure_track()
        roles = {
            name: Roles.objects.get_or_create(role_name=name)[0]
            for name in ("student", "mentor", "supervisor", "admin")
        }
        for name in roles:
            Group.objects.get_or_create(name=name)

        results = []
        for spec in ACCOUNTS:
            user = self._upsert_user(spec, track)
            self._apply_role(user, spec["role"], roles, track)
            results.append((spec["role"], user.email))

        self.stdout.write(self.style.SUCCESS("\nSeeded test accounts (password: %s):" % DEFAULT_PASSWORD))
        for role, email in results:
            self.stdout.write(f"  {role:<14} {email}")

    def _ensure_track(self) -> Tracks:
        country, _ = Countries.objects.get_or_create(country_name="Test Country")
        state, _ = CountryStates.objects.get_or_create(country=country, state_name="Test State")
        track, _ = Tracks.objects.get_or_create(track_name="Test Track", defaults={"state": state})
        return track

    def _upsert_user(self, spec: dict, track: Tracks) -> User:
        email = spec["email"].lower()
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(
                email=email,
                password=DEFAULT_PASSWORD,
                first_name=spec["first"],
                last_name=spec["last"],
                track=track,
            )
            self.stdout.write(f"  created  {email}")
        else:
            user.set_password(DEFAULT_PASSWORD)
            user.first_name = spec["first"]
            user.last_name = spec["last"]
            user.track = track
            user.account_status = User.AccountStatus.ACTIVE
            user.is_active = True
            user.save()
            self.stdout.write(f"  updated  {email}")
        return user

    def _apply_role(self, user: User, role_key: str, roles: dict, track: Tracks) -> None:
        if role_key == "student":
            self._assign_role(user, roles["student"])
            StudentProfile.objects.update_or_create(
                user=user,
                defaults={
                    "pg_first_name": "Parent",
                    "pg_last_name": "Guardian",
                    "school_name": "Test School",
                    "year_lvl": "10",
                },
            )
        elif role_key == "mentor":
            self._assign_role(user, roles["mentor"])
            MentorProfile.objects.update_or_create(
                user=user,
                defaults={
                    "institution": "Test University",
                    "mentor_reason": "seed account",
                    "max_group_count": 3,
                },
            )
        elif role_key == "supervisor":
            self._assign_role(user, roles["supervisor"])
            SupervisorProfile.objects.update_or_create(
                user=user,
                defaults={"school_name": "Test School"},
            )
        elif role_key == "track-admin":
            self._assign_role(user, roles["admin"])
            AdminProfile.objects.get_or_create(admin=user)
            AdminScope.objects.filter(user=user).delete()
            AdminScope.objects.create(user=user, track=track, is_global=False)
        elif role_key == "global-admin":
            self._assign_role(user, roles["admin"])
            AdminProfile.objects.get_or_create(admin=user)
            AdminScope.objects.filter(user=user).delete()
            AdminScope.objects.create(user=user, is_global=True, track=None)
        else:
            raise ValueError(f"unknown role key: {role_key}")

    def _assign_role(self, user: User, role: Roles) -> None:
        now = timezone.now()
        RoleAssignmentHistory.objects.filter(
            user=user, valid_to__isnull=True
        ).exclude(role=role).update(valid_to=now)
        if not RoleAssignmentHistory.objects.filter(
            user=user, role=role, valid_to__isnull=True
        ).exists():
            RoleAssignmentHistory.objects.create(user=user, role=role, valid_from=now)
        group, _ = Group.objects.get_or_create(name=role.role_name)
        user.groups.add(group)
