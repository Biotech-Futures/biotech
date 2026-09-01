from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.grading.models import Grade, Rubric, RubricCriterion
from apps.submissions.models import SubmissionComponent


FIVE = Decimal("5.00")

# The real BTF rubric, mirroring the client's 2025 marks release template:
# POSTER criteria map to <<[P1]>>..<<[P10]>> (/5 each, /50 total) and SAQ to
# <<[S1]>>..<<[S4]>> (/5 each, /20 total) — order here IS the template order.
REAL_CRITERIA = {
    "POSTER": [
        ("Identifies problem/research question", FIVE, 10),
        ("Justifies and quantifies the problem/research question", FIVE, 20),
        ("Provides details of solution to problem", FIVE, 30),
        ("Justifies solution by relating to their team’s research", FIVE, 40),
        ("Addresses extent solution solves problem & technological feasibility", FIVE, 50),
        ("Identifies future/required research to improve solution", FIVE, 60),
        ("Well organised and easy to follow", FIVE, 70),
        ("Visually appealing (no text blocks) and minimal jargon", FIVE, 80),
        ("Includes diagrams/images", FIVE, 90),
        ("Includes data obtained by team or referenced (tables/graphs)", FIVE, 100),
    ],
    "SAQ": [
        ("Addresses the question with a clear claim and maintains focus", FIVE, 10),
        ("Is reflective, provides evidence and explains how it supports the claim/topic", FIVE, 20),
        ("Presents a logical structure and uses formal language", FIVE, 30),
        ("Includes data obtained by team or otherwise referenced (tables/graphs)", FIVE, 40),
    ],
}

# Components without an official rubric (REPORT/PROTOTYPE — their marks are
# never released) get no criteria: markers leave an overall comment only.


class Command(BaseCommand):
    help = (
        "Seed Rubric + RubricCriteria for every SubmissionComponent in the given "
        "year. POSTER and SAQ get the real BTF criteria (P1–P10 / S1–S4); other "
        "components get no criteria. Idempotent — re-running only fills gaps. "
        "Use --replace to wipe a year's existing criteria (AND their grades) and "
        "reseed from scratch."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=date.today().year,
            help="Rubric year (default: current year).",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete the year's existing criteria and their grades first.",
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

            if options["replace"] and not created:
                grades = Grade.objects.filter(criterion__rubric=rubric)
                n_grades = grades.count()
                grades.delete()
                n_crit, _ = rubric.criteria.all().delete()
                if n_grades or n_crit:
                    self.stdout.write(self.style.WARNING(
                        f"    - replaced: deleted {n_crit} criteria and {n_grades} grades"
                    ))

            criteria = REAL_CRITERIA.get(component.code, [])
            for name, max_mark, order in criteria:
                _, crit_created = RubricCriterion.objects.get_or_create(
                    rubric=rubric,
                    name=name,
                    defaults={"max_mark": max_mark, "order": order},
                )
                if crit_created:
                    self.stdout.write(f"    + criterion {name} ({max_mark})")

        self.stdout.write(self.style.SUCCESS(f"Seeded rubrics for {year}."))
