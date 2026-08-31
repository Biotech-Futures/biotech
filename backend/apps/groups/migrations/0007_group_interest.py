from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0006_delete_tracks"),
        ("users", "0011_user_country"),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupInterest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_interests",
                        to="groups.groups",
                    ),
                ),
                (
                    "interest",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="users.areasofinterest",
                    ),
                ),
            ],
            options={
                "verbose_name": "Group Interest",
                "verbose_name_plural": "Group Interests",
                "db_table": "group_interest",
            },
        ),
        migrations.AddIndex(
            model_name="groupinterest",
            index=models.Index(fields=["group"], name="group_inter_group_i_idx"),
        ),
        migrations.AddIndex(
            model_name="groupinterest",
            index=models.Index(fields=["interest"], name="group_inter_interes_idx"),
        ),
        migrations.AddConstraint(
            model_name="groupinterest",
            constraint=models.UniqueConstraint(fields=("group", "interest"), name="unique_group_interest"),
        ),
    ]
