"""Bridge between the matching algorithms and the stored scoring config (MA1).

The algorithm module stays free of database access, so anything that wants the
admin-tuned weights resolves them here and passes them in. A run should also
record which weights it used: :func:`build_scoring_rules_snapshot` produces the
block to store on ``MatchRun.rules_snapshot``.
"""

from typing import Any, Dict, NamedTuple, Optional

from apps.common.matching_weights import (
    DEFAULT_WEIGHT_VALUES,
    REQUIRED_WEIGHT_TOTAL,
    ScoringWeights,
)

from .models import MatchingConfig


class ResolvedScoringRules(NamedTuple):
    """The weights a run is scored with, plus the config they came from.

    The two travel together so the run can record what it scored with even
    though only the weights end up on ``rules_snapshot``. Re-reading the stored
    config at save time would be wrong: an admin could change it mid-run and the
    snapshot would describe weights the run never applied.
    """

    weights: ScoringWeights
    config: Optional[MatchingConfig]

    def to_snapshot(self, mode: str) -> Dict[str, Any]:
        return {
            "mode": mode,
            "weights": self.weights.as_dict(),
            "totalWeight": str(self.weights.total()),
        }


def resolve_scoring_rules() -> ResolvedScoringRules:
    """Weights for the current run: the stored config, or the built-in defaults."""
    config = MatchingConfig.get_singleton()
    if config:
        return ResolvedScoringRules(config.to_scoring_weights(), config)
    return ResolvedScoringRules(ScoringWeights(), None)


def resolve_scoring_weights() -> ScoringWeights:
    """Convenience for callers that only need the weights, not the snapshot."""
    return resolve_scoring_rules().weights


def build_scoring_rules_snapshot(mode: str, rules: ResolvedScoringRules) -> Dict[str, Any]:
    """The applied mode and weights, for ``MatchRun.rules_snapshot``."""
    return rules.to_snapshot(mode)


def matching_config_defaults() -> Dict[str, Any]:
    """A complete, valid weight split for an admin panel to start from."""
    return {
        "requiredTotal": REQUIRED_WEIGHT_TOTAL,
        "defaults": dict(DEFAULT_WEIGHT_VALUES),
    }