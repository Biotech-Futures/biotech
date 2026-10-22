"""Pages Visibility by a date and time (shown_from) rather than a switch
(shown): a switch that was on is shown from now, one that was off stays
hidden with no date set."""
from django.db import migrations, models
from django.utils import timezone


def switch_to_date(apps, schema_editor):
    Setting = apps.get_model("management", "SupervisorPagesSetting")
    Setting.objects.filter(shown=True).update(shown_from=timezone.now())


def date_to_switch(apps, schema_editor):
    Setting = apps.get_model("management", "SupervisorPagesSetting")
    Setting.objects.filter(shown_from__lte=timezone.now()).update(shown=True)


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0018_email_send_run_connections"),
    ]

    operations = [
        migrations.AddField(
            model_name="supervisorpagessetting",
            name="shown_from",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(switch_to_date, date_to_switch),
        migrations.RemoveField(
            model_name="supervisorpagessetting",
            name="shown",
        ),
    ]
