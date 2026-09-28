"""Convert every global/public resource to role-based visibility.

Resources are role-scoped only from here on (RS4). A resource that was visible
to everyone keeps that reach by getting an audience row for every role, so
nobody loses access. Also canonicalises the literal "role_based"/"global"
strings the admin write path used to save straight into visibility_scope.

Group- and scoped-visibility rows are left alone.

Not reversible: once converted, a resource with every role can't be told
apart from one an admin deliberately gave every role, so reverse is a no-op.
"""

from django.db import migrations

EVERYONE_SCOPES = ("public", "global")


def backfill_role_visibility(apps, schema_editor):
    Resources = apps.get_model("resources", "Resources")
    ResourceAudience = apps.get_model("resources", "ResourceAudience")
    Roles = apps.get_model("resources", "Roles")

    Resources.objects.filter(visibility_scope="role_based").update(visibility_scope="role")

    all_role_ids = list(Roles.objects.values_list("id", flat=True))
    if not all_role_ids:
        # No roles to grant (e.g. a fresh database): converting would make
        # these resources visible to no one, so leave them as they are.
        return
    everyone = Resources.objects.filter(visibility_scope__in=EVERYONE_SCOPES)

    new_rows = []
    for resource_id in everyone.values_list("id", flat=True):
        # (resource, role) is unique, so only add the roles it doesn't have yet.
        existing = set(
            ResourceAudience.objects.filter(resource_id=resource_id)
            .values_list("role_id", flat=True)
        )
        new_rows.extend(
            ResourceAudience(resource_id=resource_id, role_id=role_id)
            for role_id in all_role_ids
            if role_id not in existing
        )
    ResourceAudience.objects.bulk_create(new_rows)

    everyone.update(visibility_scope="role")


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0010_remove_resourceaudience_resource_audience_requires_role_or_track_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_role_visibility, migrations.RunPython.noop),
    ]
