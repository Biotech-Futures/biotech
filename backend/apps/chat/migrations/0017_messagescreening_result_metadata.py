from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0016_alter_messagescreening_status"),
        ("tickets", "0007_backfill_awaiting_support_since"),
    ]

    operations = [
        migrations.AddField(
            model_name="messagescreening",
            name="attempt_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="messagescreening",
            name="categories",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="messagescreening",
            name="category_scores",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="messagescreening",
            name="last_attempt_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="messagescreening",
            name="ticket",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="message_screening",
                to="tickets.ticket",
            ),
        ),
    ]
