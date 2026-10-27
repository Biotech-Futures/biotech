import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("services", "0014_system_email_settings_always_on"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailEngagementTracker",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("email_type", models.SlugField(max_length=64)),
                ("subject", models.CharField(blank=True, default="", max_length=255)),
                ("recipient_email", models.EmailField(blank=True, max_length=254, null=True)),
                ("recipient_count", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("first_opened_at", models.DateTimeField(blank=True, null=True)),
                ("last_opened_at", models.DateTimeField(blank=True, null=True)),
                ("open_count", models.PositiveIntegerField(default=0)),
                ("first_clicked_at", models.DateTimeField(blank=True, null=True)),
                ("last_clicked_at", models.DateTimeField(blank=True, null=True)),
                ("click_count", models.PositiveIntegerField(default=0)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "email_engagement_tracker",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="EmailEngagementEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("open", "Open"), ("click", "Click")], max_length=8)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tracker",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="services.emailengagementtracker",
                    ),
                ),
            ],
            options={
                "db_table": "email_engagement_event",
                "ordering": ["-occurred_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="emailengagementtracker",
            index=models.Index(fields=["created_at"], name="email_engagement_created_idx"),
        ),
        migrations.AddIndex(
            model_name="emailengagementtracker",
            index=models.Index(fields=["email_type", "created_at"], name="email_engagement_type_idx"),
        ),
        migrations.AddIndex(
            model_name="emailengagementevent",
            index=models.Index(fields=["event_type", "occurred_at"], name="email_engagement_event_idx"),
        ),
    ]
