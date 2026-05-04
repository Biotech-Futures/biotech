from typing import TypedDict, Optional, Union, Literal, List, Dict, Set, Tuple, Any
from enum import Enum

# ── Constants ──────────────────────────────────────────────────────────────

BASE_SCORE = 100
TRACK_MISMATCH_PENALTY = 40
INTEREST_OVERLAP_MAX_BONUS = 30
TIMEZONE_WEIGHT = 2
TIMEZONE_MAX_PENALTY = 18
CAPACITY_BONUS_PER_SLOT = 2

TRACK_UTC_OFFSET = {
    "AUS-NSW": 10,
    "AUS-QLD": 10,
    "AUS-VIC": 10,
    "AUS-WA": 8,
    "AUS-SA": 9.5,
    "BRA": -3,
    "GLOBAL": 0,
}

MatchMode = Literal["balanced", "strict", "coverage"]

# ── Type Definitions ───────────────────────────────────────────────────────

class MentorSource(TypedDict):
    mentorId: int
    firstName: str
    lastName: str
    trackCode: str
    institution: Optional[str]
    interests: List[str]
    maxGroupCount: int
    currentAcceptedCount: int


class GroupStudent(TypedDict, total=False):
    name: str
    interests: List[str]


class GroupSource(TypedDict, total=False):
    groupId: int
    groupName: str
    trackCode: str
    studentInterests: List[str]
    studentCount: int
    students: Optional[List[GroupStudent]]


class MentorScoreBreakdown(TypedDict):
    baseScore: float
    trackPenalty: float
    interestBonus: float
    timezonePenalty: float
    capacityBonus: float
    objectiveScore: float


class MentorGroupRecommendation(TypedDict):
    group: GroupSource
    recommendedMentor: Optional[Dict[str, Any]]
    reason: str
    score: float
    scoreBreakdown: MentorScoreBreakdown


class ScoreEntry(TypedDict):
    score: float
    breakdown: MentorScoreBreakdown
    reason: str


class GaleShapleyResult(TypedDict):
    assignment: Dict[int, int]
    tentative: Dict[int, Set[int]]


# ── Helper Functions ──────────────────────────────────────────────────────

def is_same_track_eligible(mentor: MentorSource, group: GroupSource) -> bool:
    return (
        mentor["trackCode"] == "GLOBAL"
        or group["trackCode"] == "GLOBAL"
        or mentor["trackCode"] == group["trackCode"]
    )


def compute_interest_bonus(mentor_interests: List[str], group_interests: List[str]) -> float:
    if not mentor_interests or not group_interests:
        return 0

    group_interest_set = {i.lower() for i in group_interests}
    overlap_count = sum(1 for i in mentor_interests if i.lower() in group_interest_set)
    overlap_ratio = overlap_count / max(len(mentor_interests), len(group_interests))

    return round(overlap_ratio * INTEREST_OVERLAP_MAX_BONUS)


def score_mentor_for_group(
    mentor: MentorSource, group: GroupSource
) -> Tuple[float, MentorScoreBreakdown, str]:
    breakdown: MentorScoreBreakdown = {
        "baseScore": BASE_SCORE,
        "trackPenalty": 0,
        "interestBonus": 0,
        "timezonePenalty": 0,
        "capacityBonus": 0,
        "objectiveScore": 0,
    }

    mentor_track = mentor["trackCode"]
    group_track = group["trackCode"]
    is_global = mentor_track == "GLOBAL" or group_track == "GLOBAL"
    track_match = is_global or mentor_track == group_track

    if not track_match:
        breakdown["trackPenalty"] = TRACK_MISMATCH_PENALTY

    breakdown["interestBonus"] = compute_interest_bonus(
        mentor["interests"], group.get("studentInterests", [])
    )

    if not is_global:
        mentor_offset = TRACK_UTC_OFFSET.get(mentor_track, 0)
        group_offset = TRACK_UTC_OFFSET.get(group_track, 0)
        tz_dist = abs(mentor_offset - group_offset)
        breakdown["timezonePenalty"] = min(tz_dist * TIMEZONE_WEIGHT, TIMEZONE_MAX_PENALTY)

    remaining_capacity = mentor["maxGroupCount"] - mentor["currentAcceptedCount"]
    breakdown["capacityBonus"] = remaining_capacity * CAPACITY_BONUS_PER_SLOT

    breakdown["objectiveScore"] = (
        breakdown["baseScore"]
        - breakdown["trackPenalty"]
        + breakdown["interestBonus"]
        - breakdown["timezonePenalty"]
        + breakdown["capacityBonus"]
    )

    reasons: List[str] = []
    if track_match and not is_global:
        reasons.append(f"Track match: {mentor_track}")
    if is_global:
        reasons.append("GLOBAL track (flexible timezone)")
    if breakdown["interestBonus"] > 0:
        group_interest_set = {i.lower() for i in group.get("studentInterests", [])}
        overlapping = [i for i in mentor["interests"] if i.lower() in group_interest_set]
        reasons.append(f"Shared interests: {', '.join(overlapping[:3])}")
    if not track_match:
        reasons.append("Track mismatch penalty applied")

    reason = ". ".join(reasons) if reasons else "No matching criteria found."

    return breakdown["objectiveScore"], breakdown, reason


def build_score_matrix(
    groups: List[GroupSource], mentors: List[MentorSource]
) -> Dict[str, ScoreEntry]:
    matrix: Dict[str, ScoreEntry] = {}
    for group in groups:
        for mentor in mentors:
            key = f"{group['groupId']}:{mentor['mentorId']}"
            score, breakdown, reason = score_mentor_for_group(mentor, group)
            matrix[key] = {
                "score": score,
                "breakdown": breakdown,
                "reason": reason,
            }
    return matrix


def unmatched_reason(
    group: GroupSource,
    all_mentors: List[MentorSource],
    eligible_mentors: List[MentorSource],
    mode: MatchMode,
) -> str:
    if not all_mentors:
        return "No mentors are registered in the system."

    if not eligible_mentors:
        if mode == "strict":
            return f'No mentors are available for track "{group["trackCode"]}" (strict mode).'
        return "No mentors with remaining capacity are available."

    same_track_eligible = [m for m in eligible_mentors if is_same_track_eligible(m, group)]

    if mode == "strict" and not same_track_eligible:
        return f'No mentors are available for track "{group["trackCode"]}" (strict mode).'

    if same_track_eligible:
        return f'All compatible mentors for track "{group["trackCode"]}" are fully assigned to higher-scoring groups.'

    return "All available mentors are fully assigned to higher-scoring groups."


EMPTY_BREAKDOWN: MentorScoreBreakdown = {
    "baseScore": BASE_SCORE,
    "trackPenalty": 0,
    "interestBonus": 0,
    "timezonePenalty": 0,
    "capacityBonus": 0,
    "objectiveScore": 0,
}


def gale_shapley(
    groups: List[GroupSource],
    mentors: List[MentorSource],
    score_matrix: Dict[str, ScoreEntry],
    slots_override: Optional[Dict[int, int]] = None,
) -> GaleShapleyResult:
    """Gale-Shapley stable matching with groups proposing to mentors."""
    if not slots_override:
        slots = {
            m["mentorId"]: m["maxGroupCount"] - m["currentAcceptedCount"]
            for m in mentors
        }
    else:
        slots = slots_override

    tentative: Dict[int, Set[int]] = {m["mentorId"]: set() for m in mentors}
    assignment: Dict[int, int] = {}
    next_idx: Dict[int, int] = {g["groupId"]: 0 for g in groups}

    # Build preference lists
    group_preferences: Dict[int, List[MentorSource]] = {}
    for group in groups:
        ranked = sorted(
            mentors,
            key=lambda m: score_matrix.get(f"{group['groupId']}:{m['mentorId']}", {}).get(
                "score", float("-inf")
            ),
            reverse=True,
        )
        group_preferences[group["groupId"]] = ranked

    unmatched = list(groups)
    max_iterations = len(groups) * len(mentors) + 1
    iterations = 0

    while unmatched:
        if iterations > max_iterations:
            break
        iterations += 1
        next_round: List[GroupSource] = []

        for group in unmatched:
            prefs = group_preferences[group["groupId"]]
            idx = next_idx[group["groupId"]]

            if idx >= len(prefs):
                continue

            mentor = prefs[idx]
            next_idx[group["groupId"]] = idx + 1

            accepted = tentative[mentor["mentorId"]]
            capacity = slots[mentor["mentorId"]]
            incoming_score = score_matrix.get(
                f"{group['groupId']}:{mentor['mentorId']}", {}
            ).get("score", float("-inf"))

            if len(accepted) < capacity:
                accepted.add(group["groupId"])
                assignment[group["groupId"]] = mentor["mentorId"]
            else:
                worst_id = None
                worst_score = float("inf")

                for held_id in accepted:
                    s = score_matrix.get(f"{held_id}:{mentor['mentorId']}", {}).get(
                        "score", float("-inf")
                    )
                    if s < worst_score:
                        worst_score = s
                        worst_id = held_id

                if worst_id is not None and incoming_score > worst_score:
                    accepted.discard(worst_id)
                    accepted.add(group["groupId"])
                    assignment[group["groupId"]] = mentor["mentorId"]
                    assignment.pop(worst_id, None)
                    displaced = next(g for g in groups if g["groupId"] == worst_id)
                    next_round.append(displaced)
                else:
                    next_round.append(group)

        unmatched = next_round

    return {"assignment": assignment, "tentative": tentative}


def gale_shapley_per_group(
    groups: List[GroupSource],
    mentors: List[MentorSource],
    score_matrix: Dict[str, ScoreEntry],
    per_group_mentors: Dict[int, List[MentorSource]],
    slots_override: Optional[Dict[int, int]] = None,
) -> GaleShapleyResult:
    """Gale-Shapley variant where each group only proposes to eligible mentors."""
    if not slots_override:
        slots = {
            m["mentorId"]: m["maxGroupCount"] - m["currentAcceptedCount"]
            for m in mentors
        }
    else:
        slots = slots_override

    tentative: Dict[int, Set[int]] = {m["mentorId"]: set() for m in mentors}
    assignment: Dict[int, int] = {}
    next_idx: Dict[int, int] = {g["groupId"]: 0 for g in groups}

    group_preferences: Dict[int, List[MentorSource]] = {}
    for group in groups:
        eligible = per_group_mentors.get(group["groupId"], [])
        ranked = sorted(
            eligible,
            key=lambda m: score_matrix.get(f"{group['groupId']}:{m['mentorId']}", {}).get(
                "score", float("-inf")
            ),
            reverse=True,
        )
        group_preferences[group["groupId"]] = ranked

    unmatched = list(groups)
    max_iterations = len(groups) * len(mentors) + 1
    iterations = 0

    while unmatched:
        if iterations > max_iterations:
            break
        iterations += 1
        next_round: List[GroupSource] = []

        for group in unmatched:
            prefs = group_preferences[group["groupId"]]
            idx = next_idx[group["groupId"]]

            if idx >= len(prefs):
                continue

            mentor = prefs[idx]
            next_idx[group["groupId"]] = idx + 1

            accepted = tentative[mentor["mentorId"]]
            capacity = slots[mentor["mentorId"]]
            incoming_score = score_matrix.get(
                f"{group['groupId']}:{mentor['mentorId']}", {}
            ).get("score", float("-inf"))

            if len(accepted) < capacity:
                accepted.add(group["groupId"])
                assignment[group["groupId"]] = mentor["mentorId"]
            else:
                worst_id = None
                worst_score = float("inf")

                for held_id in accepted:
                    s = score_matrix.get(f"{held_id}:{mentor['mentorId']}", {}).get(
                        "score", float("-inf")
                    )
                    if s < worst_score:
                        worst_score = s
                        worst_id = held_id

                if worst_id is not None and incoming_score > worst_score:
                    accepted.discard(worst_id)
                    accepted.add(group["groupId"])
                    assignment[group["groupId"]] = mentor["mentorId"]
                    assignment.pop(worst_id, None)
                    displaced = next(g for g in groups if g["groupId"] == worst_id)
                    next_round.append(displaced)
                else:
                    next_round.append(group)

        unmatched = next_round

    return {"assignment": assignment, "tentative": tentative}


def build_results(
    groups: List[GroupSource],
    available_mentors: List[MentorSource],
    score_matrix: Dict[str, ScoreEntry],
    assignment: Dict[int, int],
    tentative: Dict[int, Set[int]],
    eligible_mentors_by_group: Dict[int, List[MentorSource]],
    mode: MatchMode,
) -> List[MentorGroupRecommendation]:
    results: List[MentorGroupRecommendation] = []

    for group in groups:
        mentor_id = assignment.get(group["groupId"])

        if mentor_id is None:
            eligible = eligible_mentors_by_group.get(group["groupId"], [])
            results.append({
                "group": group,
                "recommendedMentor": None,
                "reason": unmatched_reason(group, available_mentors, eligible, mode),
                "score": 0,
                "scoreBreakdown": dict(EMPTY_BREAKDOWN),
            })
        else:
            mentor = next(m for m in available_mentors if m["mentorId"] == mentor_id)
            entry = score_matrix[f"{group['groupId']}:{mentor_id}"]
            score = entry["score"]
            breakdown = entry["breakdown"]
            reason = entry["reason"]

            assignments_this_run = len(tentative.get(mentor_id, set()))
            remaining_capacity = max(
                0,
                mentor["maxGroupCount"]
                - mentor["currentAcceptedCount"]
                - assignments_this_run,
            )

            results.append({
                "group": group,
                "recommendedMentor": {
                    "mentorId": mentor["mentorId"],
                    "name": f"{mentor['firstName']} {mentor['lastName']}".strip(),
                    "trackCode": mentor["trackCode"],
                    "institution": mentor["institution"],
                    "interests": mentor["interests"],
                    "remainingCapacity": remaining_capacity,
                },
                "reason": reason,
                "score": score,
                "scoreBreakdown": breakdown,
            })

    return results


def match_mentors(
    groups: List[GroupSource],
    mentors: List[MentorSource],
    mode: MatchMode = "balanced",
) -> List[MentorGroupRecommendation]:
    """Main API for mentor-to-group matching."""
    available_mentors = [m for m in mentors if m["currentAcceptedCount"] < m["maxGroupCount"]]

    if not groups:
        return []

    if not available_mentors:
        return [
            {
                "group": g,
                "recommendedMentor": None,
                "reason": "No available mentors with remaining capacity.",
                "score": 0,
                "scoreBreakdown": dict(EMPTY_BREAKDOWN),
            }
            for g in groups
        ]

    # ── Balanced mode ──────────────────────────────────────────────────────
    if mode == "balanced":
        score_matrix = build_score_matrix(groups, available_mentors)

        eligible_by_group: Dict[int, List[MentorSource]] = {}
        for g in groups:
            eligible_by_group[g["groupId"]] = [
                m
                for m in available_mentors
                if (
                    score_matrix.get(f"{g['groupId']}:{m['mentorId']}", {}).get("breakdown", {}).get("interestBonus", 0) > 0
                    and score_matrix.get(f"{g['groupId']}:{m['mentorId']}", {}).get("breakdown", {}).get("timezonePenalty", 0) < TIMEZONE_MAX_PENALTY
                )
            ]

        assignment, tentative = gale_shapley_per_group(
            groups, available_mentors, score_matrix, eligible_by_group
        )
        return build_results(
            groups, available_mentors, score_matrix, assignment, tentative, eligible_by_group, mode
        )

    # ── Strict mode ────────────────────────────────────────────────────────
    if mode == "strict":
        eligible_by_group = {
            g["groupId"]: [m for m in available_mentors if is_same_track_eligible(m, g)]
            for g in groups
        }

        eligible_mentor_ids = set()
        for eligible_list in eligible_by_group.values():
            eligible_mentor_ids.update(m["mentorId"] for m in eligible_list)

        eligible_mentors = [m for m in available_mentors if m["mentorId"] in eligible_mentor_ids]

        score_matrix = build_score_matrix(groups, eligible_mentors)

        assignment, tentative = gale_shapley_per_group(
            groups, eligible_mentors, score_matrix, eligible_by_group
        )
        return build_results(
            groups, available_mentors, score_matrix, assignment, tentative, eligible_by_group, mode
        )

    # ── Coverage mode ──────────────────────────────────────────────────────
    # Phase 1: same-track / GLOBAL
    phase1_eligible_by_group = {
        g["groupId"]: [m for m in available_mentors if is_same_track_eligible(m, g)]
        for g in groups
    }

    phase1_mentors_for_matrix = [
        m for m in available_mentors
        if any(is_same_track_eligible(m, g) for g in groups)
    ]

    phase1_score_matrix = build_score_matrix(groups, phase1_mentors_for_matrix)
    phase1_result = gale_shapley_per_group(
        groups, phase1_mentors_for_matrix, phase1_score_matrix, phase1_eligible_by_group
    )

    unmatched_after_phase1 = [g for g in groups if g["groupId"] not in phase1_result["assignment"]]

    if not unmatched_after_phase1:
        coverage_eligible_by_group = phase1_eligible_by_group
        return build_results(
            groups,
            available_mentors,
            phase1_score_matrix,
            phase1_result["assignment"],
            phase1_result["tentative"],
            coverage_eligible_by_group,
            mode,
        )

    # Phase 2: cross-track fallback
    phase2_slots: Dict[int, int] = {}
    for m in available_mentors:
        used_in_phase1 = len(phase1_result["tentative"].get(m["mentorId"], set()))
        remaining = m["maxGroupCount"] - m["currentAcceptedCount"] - used_in_phase1
        if remaining > 0:
            phase2_slots[m["mentorId"]] = remaining

    phase2_mentors = [m for m in available_mentors if phase2_slots.get(m["mentorId"], 0) > 0]

    phase2_score_matrix = build_score_matrix(unmatched_after_phase1, phase2_mentors)
    phase2_result = gale_shapley(
        unmatched_after_phase1, phase2_mentors, phase2_score_matrix, phase2_slots
    )

    merged_assignment = {**phase1_result["assignment"], **phase2_result["assignment"]}

    merged_tentative: Dict[int, Set[int]] = {}
    for m in available_mentors:
        p1 = phase1_result["tentative"].get(m["mentorId"], set())
        p2 = phase2_result["tentative"].get(m["mentorId"], set())
        merged_tentative[m["mentorId"]] = p1 | p2

    merged_score_matrix = {**phase1_score_matrix, **phase2_score_matrix}

    coverage_eligible_by_group: Dict[int, List[MentorSource]] = {}
    for g in groups:
        was_unmatched_after_p1 = any(ug["groupId"] == g["groupId"] for ug in unmatched_after_phase1)
        coverage_eligible_by_group[g["groupId"]] = (
            phase2_mentors if was_unmatched_after_p1 else phase1_eligible_by_group.get(g["groupId"], [])
        )

    return build_results(
        groups,
        available_mentors,
        merged_score_matrix,
        merged_assignment,
        merged_tentative,
        coverage_eligible_by_group,
        mode,
    )