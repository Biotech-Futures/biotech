"""Pure, repeatable size presets for the local demo GUI; never writes data."""

from __future__ import annotations

import math
import random
import re

from dataset import DatasetConfig, parse_as_of


BASELINE_STUDENTS = 120
MIN_STUDENTS = 1
MAX_STUDENTS = 10_000
MAX_VARIATION_PERCENT = 50
SCALED_FIELDS = (
    "supervisors", "mentors", "groups", "messages", "login_events", "tasks",
    "resources", "resource_accesses", "announcements", "deliveries", "events", "rsvps",
)


def scale_preview(payload: object) -> dict:
    """Validate two scale inputs plus replay seed/time, then return normal config."""
    required = {"students", "variation_percent", "seed", "as_of"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("Scale preview requires students, variation_percent, seed and as_of only.")
    students = payload["students"]
    if isinstance(students, bool) or not isinstance(students, int) or not MIN_STUDENTS <= students <= MAX_STUDENTS:
        raise ValueError("Preset student count must be a whole number from 1 to 10,000.")
    variation = payload["variation_percent"]
    if isinstance(variation, bool) or not isinstance(variation, (int, float)) or not 0 <= variation <= MAX_VARIATION_PERCENT or not math.isfinite(variation):
        raise ValueError("Random variation must be a number from 0 to 50 percent.")
    seed = payload["seed"]
    if isinstance(seed, bool) or not isinstance(seed, (int, str)):
        raise ValueError("Preset seed must be a whole decimal number of at most 200 characters.")
    seed_text = str(seed)
    if not 0 < len(seed_text) <= 200 or re.fullmatch(r"-?(?:0|[1-9][0-9]*)", seed_text) is None:
        raise ValueError("Preset seed must be a whole decimal number of at most 200 characters.")
    as_of = payload["as_of"]
    if not isinstance(as_of, str) or not as_of.strip() or len(as_of) > 80:
        raise ValueError("Preset clock must be a timezone-aware ISO-8601 value.")
    instant = parse_as_of(as_of)
    baseline = DatasetConfig(seed=int(seed_text), as_of=instant.isoformat())
    multiplier = students / BASELINE_STUDENTS
    rng = random.Random(int(seed_text))
    spread = variation / 100
    values = {
        name: max(1, math.floor(getattr(baseline, name) * multiplier * (1 + rng.uniform(-spread, spread)) + 0.5))
        for name in SCALED_FIELDS
    }
    total_users = 2 + students + values["supervisors"] + values["mentors"]
    values["rsvps"] = min(values["rsvps"], values["events"] * total_users)
    # Keep the two demo administrators, and keep the user's student count exact.
    # Minimum one for related entities keeps very small presets usable.
    config = DatasetConfig(
        **values, admins=2, students=students, seed=int(seed_text),
        as_of=instant.isoformat(), email_batches=values["deliveries"] * 2,
    ).validate()
    # A coverage batch may address the whole population. Bound that upper
    # estimate before generation, without querying or creating any DB rows.
    if config.email_metric_count * config.total_users > 2_000_000:
        raise ValueError("Preset email recipient estimate exceeds 2,000,000 rows. Reduce the student count or random variation.")
    manifest = config.to_manifest()
    manifest["seed"] = seed_text
    return {
        "config": manifest,
        "scale": {
            "students": students,
            "variation_percent": variation,
            "baseline_students": BASELINE_STUDENTS,
            "multiplier": multiplier,
        },
    }
