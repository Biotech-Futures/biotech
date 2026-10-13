from django.db import migrations

# Frozen here rather than imported, so later changes to the model can't change
# what this migration did. Keys are matched case- and whitespace-insensitively.
CANONICAL_KEYS = {"academic", "industry", "undergraduate", "postgraduate", "hdr"}

# The labels the model itself used before AM2.
OLD_LABELS = {
    "university student - undergraduate": "undergraduate",
    "university student - postgraduate": "postgraduate",
    "university student - hdr": "hdr",
}


def normalized_background(value):
    """The value to store, or ``value`` itself when it isn't recognised.

    Only unambiguous values move: a key in another case, one of the model's
    old labels, or a blank (which already meant "not set"). Anything else,
    e.g. "Research" or "HDR candidate", is left for an admin to review.
    """
    stripped = value.strip()
    if not stripped:
        return None
    key = stripped.lower()
    if key in CANONICAL_KEYS:
        return key
    return OLD_LABELS.get(key, value)


def normalize_backgrounds(apps, schema_editor):
    MentorProfile = apps.get_model("users", "MentorProfile")
    rows = MentorProfile.objects.filter(background__isnull=False).values_list("user_id", "background")
    for user_id, background in rows:
        target = normalized_background(background)
        if target != background:
            MentorProfile.objects.filter(user_id=user_id).update(background=target)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0023_alter_mentorprofile_background"),
    ]

    operations = [
        # Not reversible in data terms: the original case/spacing is not kept.
        migrations.RunPython(normalize_backgrounds, migrations.RunPython.noop),
    ]
