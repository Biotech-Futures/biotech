from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0016_normalize_event_image_keys"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="events",
            name="check_event_format_location_consistency",
        ),
        migrations.AddConstraint(
            model_name="events",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(event_format="in_person")
                    | (
                        models.Q(event_format="virtual")
                        & models.Q(location__isnull=True)
                    )
                    | models.Q(event_format="hybrid")
                ),
                name="check_event_format_location_consistency",
            ),
        ),
    ]