"""Pages Visibility's first date, set once when this is deployed: the pages
are now kept back from students, mentors and supervisors until it comes
(apps.management.pages_visibility), and with none set nobody but admins would
see Home, Groups, Events, Announcements or Resources. This year's Challenge
Start if it's set, else the moment it's deployed. A date already set stays."""

from django.db import migrations
from django.utils import timezone


def _challenge_year(apps) -> int:
    """The year in progress, as ``current_cohort`` works it out."""
    ChallengeYear = apps.get_model("management", "ChallengeYear")
    started = ChallengeYear.objects.order_by("-year").values_list("year", flat=True).first()
    if started is not None:
        return started
    Deadline = apps.get_model("submissions", "Deadline")
    deadline = Deadline.objects.filter(is_active=True).order_by("-created_at", "-id").first()
    if deadline is not None:
        return timezone.localtime(deadline.closes_at).year
    return timezone.localtime().year


def default_shown_from(apps, schema_editor):
    Setting = apps.get_model("management", "SupervisorPagesSetting")
    setting = Setting.objects.filter(pk=1).first()
    if setting is not None and setting.shown_from is not None:
        return
    ChallengeStart = apps.get_model("management", "ChallengeStart")
    starts_at = (
        ChallengeStart.objects.filter(year=_challenge_year(apps)).values_list("starts_at", flat=True).first()
    )
    Setting.objects.update_or_create(pk=1, defaults={"shown_from": starts_at or timezone.now()})


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0022_presentation_slot_for_all_years"),
        ("submissions", "0025_finalist_reminder"),
    ]

    operations = [
        migrations.RunPython(default_shown_from, migrations.RunPython.noop),
    ]
