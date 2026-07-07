from django.db import migrations


class Migration(migrations.Migration):

    # Tracks can only be dropped once every FK to it is gone. Depend on each
    # migration that removed one so the delete lands last regardless of app
    # migration interleaving.
    dependencies = [
        ("groups", "0005_group_names_globally_unique"),
        ("users", "0009_remove_user_track"),
        ("announcements", "0007_remove_announcementaudience_announcement_audience_requires_role_track_or_group_and_more"),
        ("resources", "0010_remove_resourceaudience_resource_audience_requires_role_or_track_and_more"),
        ("events", "0015_remove_eventtargettrack_event_and_more"),
        ("tasks", "0011_remove_task_track"),
        ("matching_runtime", "0003_remove_matchrun_match_run_track_i_060ec1_idx_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Tracks",
        ),
    ]
