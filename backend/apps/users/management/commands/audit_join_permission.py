"""List students marked as having guardian consent with no consent response on record.

Consent is recorded by the join-permission webhook or an admin import, and both
store the consent form's response id. Until the fix in ``upsert_student_profile``,
admin create and edit granted consent with no response id as a side effect, so a
consented student without one most likely never had a guardian consent. Run this
before turning on ``ENFORCE_JOIN_PERMISSION``.

Read-only: it reports and changes nothing.

Usage:
  python manage.py audit_join_permission
  python manage.py audit_join_permission --csv > unverified_consent.csv
"""
import csv

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.users.models import StudentProfile

CSV_COLUMNS = [
    "user_id",
    "email",
    "first_name",
    "last_name",
    "school_name",
    "account_status",
    "consent_recorded_at",
]


def unverified_consent_profiles():
    """Students marked as consented with no consent response id on record."""
    return (
        StudentProfile.objects
        .select_related("user")
        .filter(has_join_permission=True)
        .filter(Q(joinperm_responseID__isnull=True) | Q(joinperm_responseID=""))
        .order_by("user_id")
    )


class Command(BaseCommand):
    help = "List students marked as consented with no consent response on record. Read-only."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            action="store_true",
            help="Write the affected students as CSV to stdout instead of a summary.",
        )

    def handle(self, *args, **options):
        profiles = unverified_consent_profiles()

        if options["csv"]:
            writer = csv.writer(self.stdout)
            writer.writerow(CSV_COLUMNS)
            for profile in profiles:
                writer.writerow(self._row(profile))
            return

        students = StudentProfile.objects.all()
        consented = students.filter(has_join_permission=True)
        unverified = profiles.count()
        self.stdout.write(f"Students:                        {students.count()}")
        self.stdout.write(f"Marked as consented:             {consented.count()}")
        self.stdout.write(f"  with a consent response:       {consented.count() - unverified}")
        self.stdout.write(f"  with no consent response:      {unverified}")
        self.stdout.write(f"Not consented:                   {students.filter(has_join_permission=False).count()}")

        if not unverified:
            self.stdout.write(self.style.SUCCESS("Every consented student has a consent response on record."))
            return

        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            f"{unverified} student(s) are marked as consented with no consent response on record:"
        ))
        for profile in profiles:
            user_id, email, first_name, last_name, school, status, recorded_at = self._row(profile)
            self.stdout.write(
                f"  {user_id:>6}  {email}  {first_name} {last_name}  "
                f"({school or 'no school'}, {status}, recorded {recorded_at or 'unknown'})"
            )
        self.stdout.write("")
        self.stdout.write("Re-run with --csv for a spreadsheet. Nothing has been changed.")

    @staticmethod
    def _row(profile):
        user = profile.user
        return [
            user.id,
            user.email,
            user.first_name,
            user.last_name,
            profile.school_name,
            user.account_status,
            profile.joinperm_granted_at.isoformat() if profile.joinperm_granted_at else "",
        ]
