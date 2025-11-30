from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from django.contrib.auth import get_user_model

from apps.groups.models import Groups, GroupMembers, Tracks, Countries, CountryStates
from apps.groups.services.get_group_name import generate_group_name
from apps.resources.models import Roles, RoleAssignmentHistory
from apps.users.models import (
    StudentProfile,
    AreasOfInterest,
    SupervisorProfile,
    RelationshipType,
    StudentSupervisor,
)


class Command(BaseCommand):
    help = "Seed groups, users, and memberships for local testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--groups",
            type=int,
            default=3,
            help="Number of groups to create (default: 3)",
        )
        parser.add_argument(
            "--students-per-group",
            type=int,
            default=2,
            help="Number of student users to add to each non-deleted group (default: 2)",
        )
        parser.add_argument(
            "--include-mentor",
            action="store_true",
            default=True,
            help="Include one mentor member in the second group (default: true)",
        )
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            default=False,
            help="Force-set demo password 'pass123' for seeded users (default: false)",
        )

    def ensure_minimal_track(self) -> Tracks:
        """Return the first Track, or create AUS/NSW with 'AUS-NSW'."""
        track = Tracks.objects.first()
        if track:
            return track

        au, _ = Countries.objects.get_or_create(
            country_name="Australia",
            defaults={"country_name_SHORT_FORM": "AUS"},
        )
        nsw, _ = CountryStates.objects.get_or_create(
            country=au,
            state_name="NSW",
            defaults={"state_name_SHORT_FORM": "NSW"},
        )
        track = Tracks.objects.filter(track_name="AUS-NSW").first()
        if not track:
            track = Tracks.objects.create(track_name="AUS-NSW", state=nsw)
        return track

    def ensure_users(self, reset_passwords: bool = False):
        """Create a handful of sample users if they don't exist."""
        User = get_user_model()
        users = {}
        # Admin (useful for Postman auth)
        users["admin"], _ = User.objects.get_or_create(
            email="seed_admin@example.com",
            defaults={"first_name": "Seed",
                      "last_name": "Admin", "is_staff": True},
        )
        # Students
        for i in range(1, 6):
            users[f"student{i}"], _ = User.objects.get_or_create(
                email=f"seed_student{i}@example.com",
                defaults={"first_name": f"Stu{i}", "last_name": "Dent"},
            )
        # Mentor
        users["mentor"], _ = User.objects.get_or_create(
            email="seed_mentor@example.com",
            defaults={"first_name": "Menty", "last_name": "McMentor"},
        )
        # Supervisor (for student profile linkage)
        users["supervisor"], _ = User.objects.get_or_create(
            email="seed_supervisor@example.com",
            defaults={"first_name": "Sue", "last_name": "Pervis"},
        )

        # Set demo password when missing or when --reset-passwords is provided
        for key, u in users.items():
            try:
                if reset_passwords or not u.has_usable_password():
                    u.set_password("pass123")
                    u.save(update_fields=["password"])
            except Exception:
                # Continue even if setting password fails for a user
                pass
        return users

    def ensure_student_profiles(self, users: dict):
        """Create basic student and supervisor profiles with interests."""
        supervisor_user = users.get("supervisor")
        if supervisor_user:
            SupervisorProfile.objects.get_or_create(
                user=supervisor_user,
                defaults={"school_name": "Seed School"},
            )
        rel, _ = RelationshipType.objects.get_or_create(
            relationship_type="Supervisor")
        biotech, _ = AreasOfInterest.objects.get_or_create(
            interest_desc="Biotech")
        chem, _ = AreasOfInterest.objects.get_or_create(
            interest_desc="Chemistry")
        interest_cycle = [biotech, chem]
        for i in range(1, 6):
            student = users.get(f"student{i}")
            if not student:
                continue
            sp, created = StudentProfile.objects.get_or_create(
                user=student,
                defaults={
                    "pg_first_name": "PG",
                    "pg_last_name": "One",
                    "parent_guardian_flag": True,
                    "supervisor": SupervisorProfile.objects.filter(user=supervisor_user).first() if supervisor_user else None,
                    "interest": interest_cycle[(i - 1) % len(interest_cycle)],
                    "school_name": f"Seed High #{i}",
                    "year_lvl": "10",
                    "has_join_permission": False,
                },
            )
            sup_prof = SupervisorProfile.objects.filter(
                user=supervisor_user).first() if supervisor_user else None
            if sup_prof:
                StudentSupervisor.objects.get_or_create(
                    student_user=sp,
                    supervisor_user=sup_prof,
                    defaults={"relationship_type": rel},
                )

    def create_groups_and_members(self, track: Tracks, users: dict, groups_count: int, students_per_group: int, include_mentor: bool):
        created_info = []
        current_year = timezone.now().year

        with transaction.atomic():
            for idx in range(1, groups_count + 1):
                group_name = generate_group_name(track, current_year)
                group, g_created = Groups.objects.get_or_create(
                    group_name=group_name,
                    track=track,
                    cohort_year=current_year,
                    deleted_flag=False,
                    defaults={
                        # group_number is auto-generated in model.save()
                    },
                )

                # Soft-delete the last group when creating >=3
                if groups_count >= 3 and idx == groups_count:
                    if not group.deleted_flag:
                        group.deleted_flag = True
                        group.deleted_datetime = timezone.now()
                        group.save(update_fields=[
                                   "deleted_flag", "deleted_datetime"])

                # Add members only for non-deleted groups
                if not group.deleted_flag:
                    added_students = []
                    for i in range(1, students_per_group + 1):
                        student_key = f"student{i}"
                        student = users.get(student_key)
                        if not student:
                            break
                        _, _mc = GroupMembers.objects.get_or_create(
                            group=group, user=student)
                        added_students.append(student.email)

                    # Attach a mentor to group #2 when requested
                    mentor_attached = False
                    if include_mentor and idx == 2:
                        mentor = users.get("mentor")
                        if mentor:
                            GroupMembers.objects.get_or_create(
                                group=group, user=mentor)
                            mentor_attached = True
                            # Mark mentor active
                            role, _ = Roles.objects.get_or_create(
                                role_name="Mentor")
                            RoleAssignmentHistory.objects.get_or_create(
                                user=mentor,
                                role=role,
                                valid_to=None,
                                defaults={"valid_from": timezone.now()},
                            )

                    created_info.append({
                        "group_number": group.group_number,
                        "group_name": group.group_name,
                        "deleted": group.deleted_flag,
                        "students": added_students,
                        "mentor": users["mentor"].email if mentor_attached else None,
                    })

        return created_info

    def handle(self, *args, **options):
        groups_count = int(options.get("groups") or 3)
        students_per_group = int(options.get("students_per_group") or 2)
        include_mentor = bool(options.get("include_mentor"))
        reset_passwords = bool(options.get("reset_passwords"))

        track = self.ensure_minimal_track()
        users = self.ensure_users(reset_passwords=reset_passwords)
        # Create profiles for demo data
        self.ensure_student_profiles(users)
        info = self.create_groups_and_members(
            track, users, groups_count, students_per_group, include_mentor)

        self.stdout.write(self.style.SUCCESS("Seeded groups and memberships:"))
        for row in info:
            status = "deleted" if row["deleted"] else "active"
            self.stdout.write(
                f"- {row['group_name']} ({row['group_number']}) [{status}]  "
                f"students={row['students']}  mentor={row['mentor']}"
            )

        self.stdout.write(self.style.SUCCESS("Done."))
