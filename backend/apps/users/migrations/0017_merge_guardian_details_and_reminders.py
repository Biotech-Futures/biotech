from django.db import migrations


class Migration(migrations.Migration):
    # Joins main's guardian reminders with the guardian details email's
    # reminder date: both followed 0015_guardian_consent_record_pdf.
    dependencies = [
        ("users", "0016_merge_dashboards_guardian_consent"),
        ("users", "0016_student_guardian_details_reminded_on"),
    ]

    operations = []
