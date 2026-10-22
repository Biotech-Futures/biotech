import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_announcement_metrics(apps, schema_editor):
    AnnouncementDelivery = apps.get_model("announcements", "AnnouncementDelivery")
    EmailDeliveryMetric = apps.get_model("services", "EmailDeliveryMetric")

    rows = []
    for delivery in AnnouncementDelivery.objects.all().iterator(chunk_size=500):
        rows.append(
            EmailDeliveryMetric(
                email_type="announcement",
                source_mailbox="info@biotechfutures.org",
                attempted_count=delivery.recipient_count,
                delivered_count=delivery.success_count,
                failed_count=delivery.failure_count,
                status=delivery.status,
                initiated_by_id=delivery.initiated_by_id,
                started_at=delivery.started_at,
                completed_at=delivery.completed_at or delivery.started_at,
            )
        )
        if len(rows) == 500:
            EmailDeliveryMetric.objects.bulk_create(rows)
            rows = []
    if rows:
        EmailDeliveryMetric.objects.bulk_create(rows)


class Migration(migrations.Migration):
    dependencies = [
        ("announcements", "0008_announcement_audience_user"),
        ("services", "0007_system_email_failures_seen"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailDeliveryMetric",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email_type", models.SlugField(max_length=64)),
                ("source_mailbox", models.EmailField(max_length=254)),
                ("attempted_count", models.PositiveIntegerField(default=0)),
                ("delivered_count", models.PositiveIntegerField(default=0)),
                ("failed_count", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(choices=[("success", "Success"), ("partial", "Partial"), ("failed", "Failed")], max_length=16)),
                ("started_at", models.DateTimeField(default=timezone.now)),
                ("completed_at", models.DateTimeField(default=timezone.now)),
                ("initiated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "email_delivery_metric",
                "ordering": ["-started_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="emaildeliverymetric",
            index=models.Index(fields=["source_mailbox", "started_at"], name="email_metric_mail_started_idx"),
        ),
        migrations.AddIndex(
            model_name="emaildeliverymetric",
            index=models.Index(fields=["email_type", "started_at"], name="email_metric_type_started_idx"),
        ),
        migrations.RunPython(backfill_announcement_metrics, migrations.RunPython.noop),
    ]
