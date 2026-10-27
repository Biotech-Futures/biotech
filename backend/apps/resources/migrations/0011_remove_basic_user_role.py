# Migration to remove the unused "basic_user" role type from the system.
from django.db import migrations


def remove_basic_user_role(apps, schema_editor):
    Roles = apps.get_model("resources", "Roles")
    Group = apps.get_model("auth", "Group")
    Roles.objects.filter(role_name__iexact="basic_user").delete()
    Group.objects.filter(name__iexact="basic_user").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0010_remove_resourceaudience_resource_audience_requires_role_or_track_and_more"),
    ]

    operations = [
        migrations.RunPython(remove_basic_user_role, migrations.RunPython.noop),
    ]