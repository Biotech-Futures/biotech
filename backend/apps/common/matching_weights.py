"""Scoring weights for the student matching algorithm.

The algorithm used to read module-level constants. It now takes a
``ScoringWeights`` value, which ``apps.matching_runtime`` fills from the
admin-editable configuration, so the weights can be retuned without a
deployment (MA1). The dataclass defaults are those original constants, so a
deployment with no saved configuration keeps its previous scoring.

Each weight is a percentage of the 100-point base score, so a weight of 8 costs
8 points. ``BASE_SCORE`` itself is the scale the percentages are measured
against rather than one of the tunables. A stored configuration must total
exactly 100 across all four weights: the percentages describe how the whole
scoring budget is divided, so anything else is rejected at save time rather
than silently normalised. Country is deliberately absent: it stopped scoring in
MA4 and only survives as a count-based tie-break, so it no longer belongs in the
weight budget.
"""

from dataclasses import dataclass
from typing import Any, Dict, Tuple

BASE_SCORE = 100

#: Resulting group size -> share of ``size_bonus_weight``. Keeps the shape of the
#: historical {2: 0, 3: 3, 4: 5, 5: 6} bonus, so the default weight of 6 still
#: yields exactly those points.
SIZE_BONUS_RATIO: Dict[int, float] = {2: 0.0, 3: 0.5, 4: 5 / 6, 5: 1.0}

#: Percentage weights must add up to exactly this before a config can be saved.
REQUIRED_WEIGHT_TOTAL = "100.00"

#: Config field name -> ``ScoringWeights`` attribute, so the model, the
#: serializer and the algorithm cannot drift apart on naming.
WEIGHT_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("year_weight", "year_weight"),
    ("timezone_weight", "timezone_weight"),
    ("timezone_max_weight", "timezone_max_penalty"),
    ("size_bonus_weight", "size_bonus_weight"),
)


@dataclass(frozen=True)
class ScoringWeights:
    """Points of penalty (or bonus) applied by each matching signal."""

    year_weight: float = 8.0
    timezone_weight: float = 2.0
    timezone_max_penalty: float = 18.0
    size_bonus_weight: float = 6.0

    def size_bonus(self, group_size: int) -> float:
        return round(SIZE_BONUS_RATIO.get(group_size, 0.0) * self.size_bonus_weight, 2)

    def max_objective_score(self) -> float:
        """Ceiling for a size-bonused score: a perfect quality score plus the
        largest bonus this configuration can hand out."""
        return round(BASE_SCORE + self.size_bonus_weight, 2)

    def total(self) -> float:
        return round(
            self.year_weight
            + self.timezone_weight
            + self.timezone_max_penalty
            + self.size_bonus_weight,
            2,
        )

    def as_dict(self) -> Dict[str, float]:
        return {
            "yearWeight": self.year_weight,
            "timezoneWeight": self.timezone_weight,
            "timezoneMaxPenalty": self.timezone_max_penalty,
            "sizeBonusWeight": self.size_bonus_weight,
        }


#: What an admin panel should start from: a complete, valid split of the budget
#: with roughly the same emphasis as the historical constants. Timezone now owns
#: the whole geography slice, so it carries the share country used to take.
DEFAULT_WEIGHT_VALUES: Dict[str, float] = {
    "year_weight": 20.0,
    "timezone_weight": 30.0,
    "timezone_max_weight": 25.0,
    "size_bonus_weight": 25.0,
}


def weights_from_config(config: Any) -> ScoringWeights:
    """Build weights from any object exposing the four weight fields."""
    return ScoringWeights(
        **{attribute: float(getattr(config, field)) for field, attribute in WEIGHT_FIELDS}
    )