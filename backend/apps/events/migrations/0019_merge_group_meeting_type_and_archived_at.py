# Joins the two migrations that both follow 0017: the group meetings' 0018
# (event_type gains "Group Meeting", from team2-submission) and main's 0018
# (archived_at, for Start new year). Neither touches the other's column, so
# there is nothing to do but join them; with two leaves Django refuses to
# migrate at all, and the deploy runs migrate first. Added when main
# (aae30421) was merged into features/enquiry_system on 2026-10-24.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0018_alter_events_event_type"),
        ("events", "0018_events_archived_at"),
    ]

    operations = []
