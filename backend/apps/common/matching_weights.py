"""Scoring weights for the student matching algorithm.

The algorithm used to read module-level constants. It now takes a
``ScoringWeights`` value, which ``apps.matching_runtime`` fills from the
admin-editable configuration, so the weights can be retuned without a
deployment (MA1). The dataclass defaults are those original constants, so a
deployment with no saved configuration keeps its previous scoring.

Weights are raw points off (or onto) the 100-point base score, not percentages:
a year weight of 8 costs 8 points per year of gap, and the weights are under no
obligation to add up to anything in particular. There is no budget to divide,
so a configuration is never rescaled or rejected for its total.

What is checked instead is how much score the penalties can take away. Each
penalty is capped per peer -- ``year_max_penalty`` and ``timezone_max_penalty``
-- so a large per-unit weight cannot run away with the score, and the two caps
together may not exceed ``BASE_SCORE``. Past that ceiling every distant pairing
bottoms out at zero and the algorithm can no longer tell them apart, which is
the one way raw weights can genuinely break ranking. Country is deliberately
absent: it stopped scoring in MA4 and only survives as a count-based tie-break,
so it carries no weight here.
"""

from dataclasses import dataclass
from typing import Any, Dict, Tuple

BASE_SCORE = 100

#: Resulting group size -> share of ``size_bonus_weight``. Keeps the shape of the
#: historical {2: 0, 3: 3, 4: 5, 5: 6} bonus, so the default weight of 6 still
#: yields exactly those points.
SIZE_BONUS_RATIO: Dict[int, float] = {2: 0.0, 3: 0.5, 4: 5 / 6, 5: 1.0}

#: The penalty caps may not add up to more than this. At the ceiling the worst
#: possible pairing scores exactly 0; beyond it a whole range of bad pairings
#: all score 0 and become indistinguishable.
MAX_TOTAL_PENALTY = BASE_SCORE

#: Config field name -> ``ScoringWeights`` attribute, so the model, the
#: serializer and the algorithm cannot drift apart on naming.
WEIGHT_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("year_weight", "year_weight"),
    ("year_max_weight", "year_max_penalty"),
    ("timezone_weight", "timezone_weight"),
    ("timezone_max_weight", "timezone_max_penalty"),
    ("size_bonus_weight", "size_bonus_weight"),
)

#: The two caps, as ``(config field, ScoringWeights attribute)``. The ceiling
#: rule is stated over these, so adding a third capped signal means adding it
#: here rather than editing the check.
PENALTY_CAP_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("year_max_weight", "year_max_penalty"),
    ("timezone_max_weight", "timezone_max_penalty"),
)


@dataclass(frozen=True)
class ScoringWeights:
    """Points of penalty (or bonus) applied by each matching signal."""

    year_weight: float = 8.0
    year_max_penalty: float = 24.0
    timezone_weight: float = 2.0
    timezone_max_penalty: float = 18.0
    size_bonus_weight: float = 6.0

    def year_penalty(self, year_gap: float) -> float:
        """Points off for one peer's year-level gap, capped.

        Year levels run 9-12, so a real gap is at most 3, and the default cap
        of 24 is exactly 3 years' worth: it leaves every registered pairing
        scoring as it always did. What it catches is a student whose year level
        is missing, which the algorithm reads as 0 -- without the cap that lone
        gap of up to 12 would charge more than the whole base score.
        """
        return min(self.year_max_penalty, year_gap * self.year_weight)

    def timezone_penalty(self, timezone_gap: float) -> float:
        """Points off for one peer's timezone gap, capped."""
        return min(self.timezone_max_penalty, timezone_gap * self.timezone_weight)

    def size_bonus(self, group_size: int) -> float:
        return round(SIZE_BONUS_RATIO.get(group_size, 0.0) * self.size_bonus_weight, 2)

    def max_total_penalty(self) -> float:
        """The most the penalties can take off a score, both caps binding."""
        return round(self.year_max_penalty + self.timezone_max_penalty, 2)

    def worst_case_score(self) -> float:
        """The quality score of the worst pairing this configuration allows."""
        return round(max(0.0, BASE_SCORE - self.max_total_penalty()), 2)

    def max_objective_score(self) -> float:
        """Ceiling for a size-bonused score: a perfect quality score plus the
        largest bonus this configuration can hand out."""
        return round(BASE_SCORE + self.size_bonus_weight, 2)

    def total(self) -> float:
        """The weights added up. Reported for information only: no rule is
        stated over it, and nothing is rescaled to reach any particular total."""
        return round(
            self.year_weight
            + self.year_max_penalty
            + self.timezone_weight
            + self.timezone_max_penalty
            + self.size_bonus_weight,
            2,
        )

    def as_dict(self) -> Dict[str, float]:
        return {
            "yearWeight": self.year_weight,
            "yearMaxPenalty": self.year_max_penalty,
            "timezoneWeight": self.timezone_weight,
            "timezoneMaxPenalty": self.timezone_max_penalty,
            "sizeBonusWeight": self.size_bonus_weight,
        }


#: What an admin panel should start from. These are the historical constants:
#: with no budget to divide there is no reason for the starting point to be
#: anything other than the scoring the project was tuned on.
DEFAULT_WEIGHT_VALUES: Dict[str, float] = {
    "year_weight": 8.0,
    "year_max_weight": 24.0,
    "timezone_weight": 2.0,
    "timezone_max_weight": 18.0,
    "size_bonus_weight": 6.0,
}


def weights_from_config(config: Any) -> ScoringWeights:
    """Build weights from any object exposing the five weight fields."""
    return ScoringWeights(
        **{attribute: float(getattr(config, field)) for field, attribute in WEIGHT_FIELDS}
    )
