"""Raw-point weights: a year penalty cap, and points wording on the rest.

Weights stopped being percentages of a 100-point budget, so nothing has to add
up to 100 any more. The safety that replaces that rule is the penalty ceiling,
and it needs the year penalty to be capped the way the timezone penalty already
was -- year was the one signal that could charge without limit.

Existing rows get 24.00, three years of the default 8-point year weight, which
is the largest gap real year levels (9-12) can produce.
"""

from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("matching_runtime", "0007_remove_matchingconfig_is_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="matchingconfig",
            name="year_max_weight",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("24.00"),
                help_text="Cap on the year penalty, in points, however far apart two students are.",
                max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("100")),
                ],
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="matchingconfig",
            name="year_weight",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Points charged per year of year-level gap between two students.",
                max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("100")),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="matchingconfig",
            name="timezone_weight",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Points charged per hour of timezone gap between two students.",
                max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("100")),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="matchingconfig",
            name="timezone_max_weight",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Cap on the timezone penalty, in points, however far apart two students are.",
                max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("100")),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="matchingconfig",
            name="size_bonus_weight",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Points added for forming a full-sized group.",
                max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("100")),
                ],
            ),
        ),
    ]
