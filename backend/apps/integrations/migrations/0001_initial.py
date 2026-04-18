# Admin auth / session tables from target DDL (NextAuth-style).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AdminUser",
            fields=[
                ("id", models.TextField(primary_key=True, serialize=False)),
                ("name", models.TextField(blank=True, null=True)),
                ("email", models.TextField(blank=True, null=True)),
                ("email_verified", models.BooleanField(blank=True, null=True)),
                ("image", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "admin_user",
            },
        ),
        migrations.CreateModel(
            name="AdminOAuthAccount",
            fields=[
                ("id", models.TextField(primary_key=True, serialize=False)),
                ("account_id", models.TextField()),
                ("provider_id", models.TextField()),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="oauth_accounts",
                        to="integrations.adminuser",
                    ),
                ),
                ("access_token", models.TextField(blank=True, null=True)),
                ("refresh_token", models.TextField(blank=True, null=True)),
                ("access_token_expires_at", models.DateTimeField(blank=True, null=True)),
                ("refresh_token_expires_at", models.DateTimeField(blank=True, null=True)),
                ("scope", models.TextField(blank=True, null=True)),
                ("password", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "account",
            },
        ),
        migrations.CreateModel(
            name="AdminAuthSession",
            fields=[
                ("id", models.TextField(primary_key=True, serialize=False)),
                ("expires_at", models.DateTimeField()),
                ("token", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("ip_address", models.TextField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="auth_sessions",
                        to="integrations.adminuser",
                    ),
                ),
            ],
            options={
                "db_table": "session",
            },
        ),
        migrations.CreateModel(
            name="AdminMatchRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("run_type", models.CharField(max_length=100)),
                ("payload", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("result", models.JSONField(blank=True, null=True)),
                (
                    "admin_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="match_runs",
                        to="integrations.adminuser",
                    ),
                ),
            ],
            options={
                "db_table": "admin_match_run",
            },
        ),
        migrations.AddIndex(
            model_name="adminmatchrun",
            index=models.Index(fields=["admin_user"], name="admin_match_admin_u_idx"),
        ),
        migrations.AddIndex(
            model_name="adminmatchrun",
            index=models.Index(fields=["created_at"], name="admin_match_created_idx"),
        ),
    ]
