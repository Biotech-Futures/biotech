"""Seed the Recorded Session ResourceType row (RS1)."""

from django.db import migrations

RECORDED_SESSION_TYPE_NAME = "Recorded Session"
RECORDED_SESSION_TYPE_DESCRIPTION = "Recorded session video and presentation slides"


def seed_recorded_session_type(apps, schema_editor):
    ResourceType = apps.get_model("resources", "ResourceType")
    ResourceType.objects.get_or_create(
        type_name=RECORDED_SESSION_TYPE_NAME,
        defaults={"type_description": RECORDED_SESSION_TYPE_DESCRIPTION},
    )


def remove_recorded_session_type(apps, schema_editor):
    ResourceType = apps.get_model("resources", "ResourceType")
    ResourceType.objects.filter(type_name=RECORDED_SESSION_TYPE_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0011_backfill_role_visibility"),
    ]

    operations = [
        migrations.RunPython(seed_recorded_session_type, remove_recorded_session_type),
    ]
