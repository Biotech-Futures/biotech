from django.db import migrations


class Migration(migrations.Migration):
    # A signed record's PDF is now found by its name ("2026_318_BTF_1.pdf"),
    # so where it was stored no longer needs keeping.
    dependencies = [
        ("users", "0017_merge_guardian_details_and_reminders"),
    ]

    operations = [
        migrations.RemoveField(model_name="guardianconsent", name="record_pdf_key"),
    ]
