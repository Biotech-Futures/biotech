"""Add recording_url to Resources (RS1).

Recorded Sessions can either upload the meeting recording as a file or link to
the recording where it is hosted. ``recording_url`` stores the latter.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0016_merge_0015_merge_20261017_0752_0015_release_resources"),
    ]

    operations = [
        migrations.AddField(
            model_name="resources",
            name="recording_url",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
    ]
