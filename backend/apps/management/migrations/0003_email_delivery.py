"""Each copy of a team's bulk email that goes is recorded, so a retry emails
only the people a run missed. For the runs already made, the last run of each
team email listed who it missed: everyone else on those teams got it then,
and is recorded here."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q

# The team emails, and who on a team each goes to (None: every member).
TEAM_EMAILS = {
    "finalist_notification": None,
    "nonfinalist_invitation": None,
    "nonsubmission_notice": None,
    "results_team": ("student", "mentor"),
}


def _team_done(apps, key: str, group) -> bool:
    """The team is already recorded as having the email."""
    if key == "finalist_notification":
        FinalistFlag = apps.get_model("grading", "FinalistFlag")
        return FinalistFlag.objects.filter(group=group, notified=True).exists()
    record = {
        "nonfinalist_invitation": "NonFinalistEmail",
        "nonsubmission_notice": "NonSubmissionEmail",
        "results_team": "ResultsTeamEmail",
    }[key]
    return apps.get_model("management", record).objects.filter(group=group).exists()


def record_last_runs(apps, schema_editor):
    """For each team the last run missed someone on: its other members as
    they were then, the ones it reached, as having the email."""
    EmailSendRun = apps.get_model("management", "EmailSendRun")
    EmailDelivery = apps.get_model("management", "EmailDelivery")
    Groups = apps.get_model("groups", "Groups")
    GroupMembership = apps.get_model("groups", "GroupMembership")
    for run in EmailSendRun.objects.filter(key__in=TEAM_EMAILS, started_at__isnull=False):
        missed = {entry for entry in run.missed if isinstance(entry, str)}
        # "(BTF07) Amy Chen": the team's name, then the person's.
        team_names = {entry[1:entry.index(") ")] for entry in missed if entry.startswith("(") and ") " in entry}
        for team_name in team_names:
            group = Groups.objects.filter(group_name=team_name, deleted_at__isnull=True).order_by("-year").first()
            if group is None or _team_done(apps, run.key, group):
                continue
            members = GroupMembership.objects.filter(group=group, joined_at__lte=run.started_at).filter(
                Q(left_at__isnull=True) | Q(left_at__gt=run.started_at)
            ).select_related("user")
            if TEAM_EMAILS[run.key]:
                members = members.filter(membership_role__in=TEAM_EMAILS[run.key])
            for membership in members:
                user = membership.user
                if not (user and user.email and user.is_active):
                    continue
                name = f"{user.first_name} {user.last_name}".strip() or user.email
                if f"({team_name}) {name}" not in missed:
                    EmailDelivery.objects.get_or_create(email=run.key, group=group, address=user.email.lower())


class Migration(migrations.Migration):

    dependencies = [
        ('grading', '0025_finalist_flag_presentation_time_moved'),
        ('groups', '0011_presentation_availability'),
        ('management', '0002_presentation_allocation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.CharField(max_length=64)),
                ('address', models.EmailField(max_length=254)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='groups.groups')),
            ],
            options={
                'db_table': 'email_delivery',
                'constraints': [models.UniqueConstraint(fields=('email', 'group', 'address'), name='uniq_email_delivery')],
            },
        ),
        migrations.RunPython(record_last_runs, migrations.RunPython.noop),
    ]
