# Generated manually to allow NULL for state and track fields

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_add_abstractuser_fields'),
    ]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE users ALTER COLUMN state_id DROP NOT NULL;",
            reverse_sql="ALTER TABLE users ALTER COLUMN state_id SET NOT NULL;"
        ),
        migrations.RunSQL(
            "ALTER TABLE users ALTER COLUMN track_id DROP NOT NULL;",
            reverse_sql="ALTER TABLE users ALTER COLUMN track_id SET NOT NULL;"
        ),
    ]