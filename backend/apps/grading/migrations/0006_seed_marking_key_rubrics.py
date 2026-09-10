"""Seed the 2026 rubrics from the client's marking keys PDF.

Poster (10 criteria, /50), SAQ (4, /20), Scientific Report (13, /65) and
Prototype (5, /25). Every criterion is out of 5; no scale text is shown
under the criterion names.

Existing criteria are renamed in place by position: grades reference
criterion ids (PROTECT), so rows are never deleted, and criteria beyond the
marking key are left untouched.
"""
from decimal import Decimal

from django.db import migrations

YEAR = 2026

FIVE_POINT = ""
THREE_POINT = ""

RUBRICS = {
    "SAQ": (FIVE_POINT, [
        "Addresses the question with a clear claim on the topic and maintains a focus throughout",
        "Is reflective, provides evidence and explains how it supports the claim/topic",
        "Presents a logical structure and communicates ideas using formal language and correct grammar",
        "Includes data obtained by team or otherwise referenced (tables/graphs)",
    ]),
    "POSTER": (FIVE_POINT, [
        "Identifies problem/research question",
        "Justifies and quantifies the problem/research question",
        "Provides a detailed solution to problem",
        "Justifies solution by relating to their team's research",
        "Addresses the extent to which solution solves the problem and its technological feasibility",
        "Identifies any future/required research for the solution/to improve upon the solution",
        "Well organised and easy to follow",
        "Visually appealing (no blocks of text have been used) and no jargon",
        "Includes diagrams/images",
        "Includes data obtained by team or otherwise referenced (tables/graphs)",
    ]),
    "REPORT": (THREE_POINT, [
        "Literature review has a range of credible sources including most recent papers",
        "Research question/problem identified with reference to literature review",
        "Evidence of design development/steps taken in developing a solution",
        "Identifies a solution to question/problem",
        "Justifies solution with detailed description of how it will solve the question/problem",
        "Degree of innovation",
        "Justifies feasibility of solution (in relation to problem category e.g. engineering/best practice policy)",
        "Addresses the extent to which solution solves the question/problem",
        "Identifies any future/required research to continue to improve a solution to the question/problem",
        "Includes diagrams/images developed by team or otherwise referenced",
        "Includes data obtained by team or otherwise referenced",
        "Report is structured as advised, or in a clear and logical manner. Report is well written and concise.",
        "Provides in text referencing that corresponds to reference list",
    ]),
    "PROTOTYPE": (THREE_POINT, [
        "Originality",
        "Visual Design",
        "Complexity",
        "Construction",
        "Appropriate representation of design",
    ]),
}


def seed(apps, schema_editor):
    Rubric = apps.get_model("grading", "Rubric")
    RubricCriterion = apps.get_model("grading", "RubricCriterion")
    SubmissionComponent = apps.get_model("grading", "SubmissionComponent")

    for code, (scale, names) in RUBRICS.items():
        component = SubmissionComponent.objects.filter(code=code).first()
        if component is None:
            continue
        rubric, _ = Rubric.objects.get_or_create(
            component=component, year=YEAR, defaults={"active": True}
        )
        if not rubric.active:
            rubric.active = True
            rubric.save(update_fields=["active"])

        existing = list(rubric.criteria.order_by("order", "id"))
        for index, name in enumerate(names):
            order = (index + 1) * 10
            if index < len(existing):
                criterion = existing[index]
                criterion.name = name
                criterion.description = scale
                criterion.max_mark = Decimal("5.00")
                criterion.order = order
                criterion.save(update_fields=["name", "description", "max_mark", "order"])
            else:
                RubricCriterion.objects.create(
                    rubric=rubric,
                    name=name,
                    description=scale,
                    max_mark=Decimal("5.00"),
                    order=order,
                )


class Migration(migrations.Migration):

    dependencies = [
        ("grading", "0005_exclude_finalists_default_true"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
