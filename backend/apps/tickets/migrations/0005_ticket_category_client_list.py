"""The client's own category list replaces the three we had guessed.

Asked on 2026-09-04 whether "Account & Access / Programs & Groups /
Certificates & Records" was the full list, the client answered "that was just
an AI byproduct haha" and gave eight categories instead. Two of ours survive
under new labels, five are new, and ``programs_groups`` has no home in the
new list.

Two steps, in this order:

1. ``RunPython`` rewrites every ``programs_groups`` row to ``other``. This is
   the only step that touches data. It runs first so that no row is left
   carrying a value the field no longer offers.
2. ``AlterField`` restates the choices. Django does not enforce ``choices`` in
   the database, so this step emits no DDL on PostgreSQL — it exists to keep
   the migration state in step with the model, which ``makemigrations
   --check`` in .github/workflows/backend-postgres.yml would otherwise fail
   on.

Why ``other`` and not ``general_question``: "Other" is honestly the bucket for
"we no longer have a name for this". "General Question" is a bucket the client
will read as meaningful on the p52 category breakdown, and quietly seeding it
with a retired category's rows would make that chart lie.

The rewrite is not reversible in any useful sense. Sending ``other`` back to
``programs_groups`` would sweep up every genuine "Other" ticket alongside the
rewritten ones, which is worse than leaving them where they are, so the
backwards step is a no-op and says so.
"""

from django.db import migrations, models


def retire_programs_groups(apps, schema_editor):
    Ticket = apps.get_model("tickets", "Ticket")
    # Includes soft-deleted rows on purpose: a deleted ticket can be restored,
    # and it must not come back carrying a category the form cannot render.
    Ticket.objects.filter(category="programs_groups").update(category="other")


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0004_alter_ticket_created_by"),
    ]

    operations = [
        migrations.RunPython(retire_programs_groups, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="ticket",
            name="category",
            field=models.CharField(
                choices=[
                    ("account_access", "Account and access"),
                    ("registration", "Registration"),
                    ("help_student_group", "Help with a student or group"),
                    ("help_mentor", "Help with a mentor"),
                    ("technical_issue", "Technical issue"),
                    ("certificates_records", "Certificates and records"),
                    ("general_question", "General Question"),
                    ("other", "Other"),
                    ("flagged_content", "Flagged content"),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
    ]
