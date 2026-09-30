import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def one_answer_per_team(apps, schema_editor):
    """Each team's students' answers become the team's one answer, holding
    every time any of them could make, not yet submitted: the team checks
    them and submits for everyone. The table itself changes in 0023: Postgres
    won't alter a table in the transaction that deleted rows from it."""
    PresentationAvailability = apps.get_model("grading", "PresentationAvailability")
    by_team = {}
    for answer in PresentationAvailability.objects.order_by("group_id", "id"):
        by_team.setdefault(answer.group_id, []).append(answer)
    for answers in by_team.values():
        kept, *others = answers
        times = set()
        for answer in answers:
            times.update(answer.slots.values_list("id", flat=True))
        kept.slots.set(times)
        for answer in others:
            answer.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('grading', '0021_email_send_run_missed'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='presentationavailability',
            name='submitted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='presentationavailability',
            name='submitted_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(one_answer_per_team, migrations.RunPython.noop),
    ]
