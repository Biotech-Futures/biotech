from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.grading.models import Rubric, RubricCriterion
from apps.submissions.models import SubmissionComponent


PLACEHOLDER_CRITERIA = [
    ("Content",  Decimal("10.00"), 10),
    ("Clarity",  Decimal("5.00"),  20),
    ("Rigour",   Decimal("5.00"),  30),
]


class Command(BaseCommand):
    help = (
        "Seed a placeholder Rubric + RubricCriteria for every SubmissionComponent "
        "in the given year. Idempotent — re-running only fills gaps. Real criteria "
        "should be edited via the admin once the client hands over the rubric doc."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=date.today().year,
            help="Rubric year (default: current year).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        year = options["year"]
        components = SubmissionComponent.objects.all()
        if not components.exists():
            self.stderr.write(self.style.ERROR(
                "No SubmissionComponent rows found — run migrations first."
            ))
            return

        for component in components:
            rubric, created = Rubric.objects.get_or_create(
                component=component,
                year=year,
                defaults={"active": True},
            )
            verb = "created" if created else "exists"
            self.stdout.write(f"  Rubric {component.code} {year}: {verb}")

            for name, max_mark, order in PLACEHOLDER_CRITERIA:
                _, crit_created = RubricCriterion.objects.get_or_create(
                    rubric=rubric,
                    name=name,
                    defaults={"max_mark": max_mark, "order": order},
                )
                if crit_created:
                    self.stdout.write(f"    + criterion {name} ({max_mark})")

        self.stdout.write(self.style.SUCCESS(f"Seeded rubrics for {year}."))
