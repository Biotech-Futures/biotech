from django.db import migrations
from django.db.models import Count, Q
from django.utils import timezone


def place_student_groups(apps, schema_editor):
    """Student groups formed while registering with two or more students go
    onto the Groups board, as registration now puts them there itself."""
    Groups = apps.get_model("groups", "Groups")
    ids = list(
        Groups.objects.filter(formed_by="members", placed_at__isnull=True, deleted_at__isnull=True)
        .annotate(students=Count(
            "groupmembership",
            filter=Q(groupmembership__left_at__isnull=True, groupmembership__membership_role="student"),
        ))
        .filter(students__gte=2)
        .values_list("id", flat=True)
    )
    Groups.objects.filter(id__in=ids).update(placed_at=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0016_groups_placed_at"),
    ]

    operations = [
        migrations.RunPython(place_student_groups, migrations.RunPython.noop),
    ]
