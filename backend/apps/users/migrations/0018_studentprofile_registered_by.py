from django.db import migrations, models


class Migration(migrations.Migration):
    # Who registered a student, and when a supervisor last edited them: either
    # locks the student's own details. Existing students are left blank, so
    # they stay free to edit.
    dependencies = [
        ("users", "0017_merge_guardian_details_and_reminders"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentprofile",
            name="registered_by",
            field=models.CharField(
                blank=True,
                choices=[
                    ("self", "The student"),
                    ("peer", "Another student"),
                    ("supervisor", "Their supervisor"),
                    ("admin", "An admin"),
                ],
                default="",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="supervisor_edited_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
