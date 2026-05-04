from typing import TypedDict, Optional, Union, Literal, Set, List, Dict, Any
from itertools import combinations as itertools_combinations
import math

# ── Constants ──────────────────────────────────────────────────────────────

BASE_SCORE = 100
YEAR_WEIGHT_REGION = 8
YEAR_WEIGHT_GLOBAL = 6
COUNTRY_MISMATCH_PENALTY = 12
TIMEZONE_WEIGHT = 2
TIMEZONE_MAX_PENALTY = 18
SIZE_BONUS = {
    2: 0,
    3: 3,
    4: 5,
    5: 6,
}

REGION_TRACKS = ("AUS-NSW", "AUS-QLD", "AUS-VIC", "AUS-WA", "BRA")
RegionTrack = Literal["AUS-NSW", "AUS-QLD", "AUS-VIC", "AUS-WA", "BRA"]
Track = Union[RegionTrack, Literal["GLOBAL"], str]

# ── Type Definitions ───────────────────────────────────────────────────────

class StudentInput(TypedDict, total=False):
    id: Union[str, int]
    name: Optional[str]
    region: Optional[str]
    trackId: Optional[Union[str, int]]
    country: Optional[str]
    timezoneOffsetHours: Optional[float]
    yearLevel: Optional[int]
    yearlevel: Optional[int]
    interests: Optional[List[str]]


class ExistingGroupMemberInput(TypedDict, total=False):
    id: Union[str, int]
    name: Optional[str]
    trackId: Optional[Union[str, int]]
    country: Optional[str]
    timezoneOffsetHours: Optional[float]
    yearLevel: Optional[int]
    yearlevel: Optional[int]
    interests: Optional[List[Dict[str, Optional[str]]]]


class GroupScoreBreakdown(TypedDict):
    baseScore: float
    yearPenalty: float
    countryPenalty: float
    timezonePenalty: float
    totalPenalty: float
    sizeBonus: float
    objectiveScore: float


class MatchGroup(TypedDict):
    track: Track
    studentIds: List[Union[str, int]]
    groupSize: int
    groupScore: float
    scoreBreakdown: GroupScoreBreakdown


class StudentScoreBreakdown(TypedDict):
    baseScore: float
    yearPenalty: float
    countryPenalty: float
    timezonePenalty: float
    totalPenalty: float


class StudentScore(TypedDict):
    studentId: Union[str, int]
    track: Track
    groupStudentIds: List[Union[str, int]]
    score: float
    scoreBreakdown: StudentScoreBreakdown


class GroupScoreResult(TypedDict):
    qualityScore: float
    scoreBreakdown: GroupScoreBreakdown
    yearSpread: int


class StudentGroupRecommendation(TypedDict):
    student: StudentInput
    recommendGroup: Optional["ExistingGroupInput"]
    reason: str
    score: float
    scoreBreakdown: "RecommendationScoreBreakdown"


class RecommendationScoreBreakdown(TypedDict):
    baseScore: float
    yearPenalty: float
    countryPenalty: float
    timezonePenalty: float
    sizeBonus: float
    totalPenalty: float
    objectiveScore: float


class ExistingGroupInput(TypedDict, total=False):
    id: Union[str, int]
    groupName: str
    trackId: Union[Track, str, int]
    groupStudent: List[ExistingGroupMemberInput]
    tutor: Optional[Dict[str, Union[str, int]]]
    maxSize: Optional[int]


class UnmatchedStudentReason(TypedDict):
    studentId: Union[str, int]
    track: Track
    reasonCode: Literal["NO_SHARED_INTEREST_IN_TRACK", "LEFTOVER_AFTER_GROUP_SELECTION"]
    reason: str
    compatibleStudentIdsInTrack: List[Union[str, int]]
    score: int
    scoreBreakdown: Dict[str, Any]


class MatchResult(TypedDict):
    groups: List[MatchGroup]
    studentScores: List[StudentScore]
    unmatchedStudentIds: List[Union[str, int]]
    unmatchedStudentReasons: List[UnmatchedStudentReason]


# ── Helper Functions ──────────────────────────────────────────────────────

def clamp(value: float, min_val: float, max_val: float) -> float:
    return min(max_val, max(min_val, value))


def round2(value: float) -> float:
    return round(value * 100) / 100


def normalize_interest(interest: str) -> str:
    return interest.strip().lower()


def stringify_id(value: Union[str, int]) -> str:
    return str(value)


def assign_track(region: str) -> Track:
    return region if region in REGION_TRACKS else "GLOBAL"


def to_interest_set(student: StudentInput) -> Set[str]:
    interests = student.get("interests") or []
    return {normalize_interest(i) for i in interests if i}


def to_member_interest_set(member: ExistingGroupMemberInput) -> Set[str]:
    interests_raw = member.get("interests") or []
    interests = []
    for item in interests_raw:
        if isinstance(item, str):
            interests.append(item)
        elif isinstance(item, dict):
            interests.append(item.get("interestDesc") or item.get("name") or "")
    return {normalize_interest(i) for i in interests if i}


def get_student_year_level(student: StudentInput) -> int:
    return student.get("yearLevel") or student.get("yearlevel") or 0


def get_member_year_level(member: ExistingGroupMemberInput) -> int:
    return member.get("yearLevel") or member.get("yearlevel") or 0


def get_student_country(student: StudentInput) -> str:
    return student.get("country") or ""


def get_member_country(member: ExistingGroupMemberInput) -> str:
    return member.get("country") or ""


def get_student_timezone(student: StudentInput) -> float:
    return student.get("timezoneOffsetHours") or 0


def get_member_timezone(member: ExistingGroupMemberInput) -> float:
    return member.get("timezoneOffsetHours") or 0


def pair_shares_interest(a: StudentInput, b: StudentInput) -> bool:
    a_interests = to_interest_set(a)
    b_interests = to_interest_set(b)
    return bool(a_interests & b_interests)


def get_common_interests(interest_sets: List[Set[str]]) -> List[str]:
    if not interest_sets:
        return []
    common = set(interest_sets[0])
    for interest_set in interest_sets[1:]:
        common &= interest_set
    return sorted(list(common))


def group_has_mandatory_interest_overlap(group: List[StudentInput]) -> bool:
    if len(group) < 2:
        return False
    return len(get_common_interests([to_interest_set(s) for s in group])) > 0


def compute_year_spread(group: List[StudentInput]) -> int:
    if not group:
        return 0
    levels = [get_student_year_level(s) for s in group]
    return max(levels) - min(levels)


def get_pair_count(group_size: int) -> int:
    return group_size * (group_size - 1) // 2


def get_size_bonus(group_size: int) -> float:
    return SIZE_BONUS.get(group_size, 0)


def get_group_max_size(group: ExistingGroupInput) -> int:
    return group.get("maxSize") or 5


def is_group_full(group: ExistingGroupInput) -> bool:
    return len(group.get("groupStudent", [])) >= get_group_max_size(group)


def same_track_id(left: Optional[Union[Track, str, int]], right: Optional[Union[Track, str, int]]) -> bool:
    if left is None or right is None:
        return False
    return stringify_id(left) == stringify_id(right)


def resolve_student_track(student: StudentInput) -> Track:
    if student.get("trackId") is not None:
        return stringify_id(student["trackId"])
    return assign_track(student.get("region") or "")


def group_track_to_output_track(group: ExistingGroupInput) -> Track:
    if group.get("trackId") is not None:
        return stringify_id(group["trackId"])
    first_student = group.get("groupStudent", [{}])[0]
    if first_student:
        return resolve_student_track(first_student)  # type: ignore
    return "GLOBAL"


def get_shared_interests_with_group(student: StudentInput, group: ExistingGroupInput) -> List[str]:
    interest_sets = [to_interest_set(student)]
    for member in group.get("groupStudent", []):
        interest_sets.append(to_member_interest_set(member))
    return get_common_interests(interest_sets)


# ── Main Scoring Functions ────────────────────────────────────────────────

def score_group(group: List[StudentInput], track_type: Track) -> Optional[GroupScoreResult]:
    if len(group) < 2 or len(group) > 5:
        return None

    if not group_has_mandatory_interest_overlap(group):
        return None

    pair_count = get_pair_count(len(group))
    year_penalty_sum = 0.0
    country_penalty_sum = 0.0
    timezone_penalty_sum = 0.0

    for i in range(len(group)):
        for j in range(i + 1, len(group)):
            a = group[i]
            b = group[j]
            year_gap = abs(get_student_year_level(a) - get_student_year_level(b))

            if track_type == "GLOBAL":
                year_penalty_sum += year_gap * YEAR_WEIGHT_GLOBAL
                is_same_country = get_student_country(a) == get_student_country(b)
                if not is_same_country:
                    country_penalty_sum += COUNTRY_MISMATCH_PENALTY
                    timezone_gap = abs(get_student_timezone(a) - get_student_timezone(b))
                    timezone_penalty_sum += min(TIMEZONE_MAX_PENALTY, timezone_gap * TIMEZONE_WEIGHT)
            else:
                year_penalty_sum += year_gap * YEAR_WEIGHT_REGION

    year_penalty = round2(year_penalty_sum / pair_count)
    country_penalty = round2(country_penalty_sum / pair_count)
    timezone_penalty = round2(timezone_penalty_sum / pair_count)
    total_penalty = round2(year_penalty + country_penalty + timezone_penalty)
    quality_score = round2(clamp(BASE_SCORE - total_penalty, 0, 100))
    size_bonus = get_size_bonus(len(group))
    objective_score = round2(clamp(quality_score + size_bonus, 0, 106))

    return {
        "qualityScore": quality_score,
        "yearSpread": compute_year_spread(group),
        "scoreBreakdown": {
            "baseScore": BASE_SCORE,
            "yearPenalty": year_penalty,
            "countryPenalty": country_penalty,
            "timezonePenalty": timezone_penalty,
            "totalPenalty": total_penalty,
            "sizeBonus": size_bonus,
            "objectiveScore": objective_score,
        },
    }


def score_student_in_group(
    student: StudentInput, group: List[StudentInput], track_type: Track
) -> Optional[StudentScore]:
    if len(group) < 2 or len(group) > 5:
        return None

    if not any(m["id"] == student["id"] for m in group):
        return None

    if not group_has_mandatory_interest_overlap(group):
        return None

    peers = [m for m in group if m["id"] != student["id"]]
    if not peers:
        return None

    year_penalty_sum = 0.0
    country_penalty_sum = 0.0
    timezone_penalty_sum = 0.0

    for peer in peers:
        year_gap = abs(get_student_year_level(student) - get_student_year_level(peer))

        if track_type == "GLOBAL":
            year_penalty_sum += year_gap * YEAR_WEIGHT_GLOBAL
            is_same_country = get_student_country(student) == get_student_country(peer)
            if not is_same_country:
                country_penalty_sum += COUNTRY_MISMATCH_PENALTY
                timezone_gap = abs(get_student_timezone(student) - get_student_timezone(peer))
                timezone_penalty_sum += min(TIMEZONE_MAX_PENALTY, timezone_gap * TIMEZONE_WEIGHT)
        else:
            year_penalty_sum += year_gap * YEAR_WEIGHT_REGION

    year_penalty = round2(year_penalty_sum / len(peers))
    country_penalty = round2(country_penalty_sum / len(peers))
    timezone_penalty = round2(timezone_penalty_sum / len(peers))
    total_penalty = round2(year_penalty + country_penalty + timezone_penalty)
    score = round2(clamp(BASE_SCORE - total_penalty, 0, 100))

    return {
        "studentId": student["id"],
        "track": track_type,
        "groupStudentIds": sorted(
            [stringify_id(m["id"]) for m in group],
            key=lambda x: x.lower() if isinstance(x, str) else str(x),
        ),
        "score": score,
        "scoreBreakdown": {
            "baseScore": BASE_SCORE,
            "yearPenalty": year_penalty,
            "countryPenalty": country_penalty,
            "timezonePenalty": timezone_penalty,
            "totalPenalty": total_penalty,
        },
    }


def get_compatible_student_ids_in_track(
    student: StudentInput, track_students: List[StudentInput]
) -> List[Union[str, int]]:
    compatible = [
        s["id"]
        for s in track_students
        if stringify_id(s["id"]) != stringify_id(student["id"])
        and pair_shares_interest(student, s)
    ]
    return sorted(compatible, key=lambda x: stringify_id(x))


def get_pair_shared_interest_count(a: StudentInput, b: StudentInput) -> int:
    a_interests = to_interest_set(a)
    b_interests = to_interest_set(b)
    return len(a_interests & b_interests)


def compute_interest_cohesion(group: List[StudentInput]) -> float:
    if len(group) < 2:
        return 0.0

    shared_interest_pair_count = 0
    for i in range(len(group)):
        for j in range(i + 1, len(group)):
            shared_interest_pair_count += get_pair_shared_interest_count(group[i], group[j])

    return round2(shared_interest_pair_count / get_pair_count(len(group)))


def combinations(items: List[Any], choose: int) -> List[List[Any]]:
    """Generate all combinations of items choosing 'choose' elements."""
    if choose <= 0 or choose > len(items):
        return []
    return [list(combo) for combo in itertools_combinations(items, choose)]


class ScoredCandidate(TypedDict):
    members: List[StudentInput]
    memberIds: List[str]
    qualityScore: float
    objectiveScore: float
    interestCohesion: float
    yearSpread: int
    scoreBreakdown: GroupScoreBreakdown


def generate_scored_candidates(students: List[StudentInput], track: Track) -> List[ScoredCandidate]:
    candidates: List[ScoredCandidate] = []
    max_size = min(5, len(students))

    for size in range(2, max_size + 1):
        combos = combinations(students, size)
        for combo in combos:
            scored = score_group(combo, track)
            if not scored:
                continue

            member_ids = sorted([stringify_id(s["id"]) for s in combo])
            candidates.append({
                "members": combo,
                "memberIds": member_ids,
                "qualityScore": scored["qualityScore"],
                "objectiveScore": scored["scoreBreakdown"]["objectiveScore"],
                "interestCohesion": compute_interest_cohesion(combo),
                "yearSpread": scored["yearSpread"],
                "scoreBreakdown": scored["scoreBreakdown"],
            })

    return sorted(
        candidates,
        key=lambda c: (
            -c["objectiveScore"],
            -c["qualityScore"],
            -c["interestCohesion"],
            c["yearSpread"],
            "|".join(c["memberIds"]),
        ),
    )


def build_unmatched_reason(
    student: StudentInput,
    track: Track,
    compatible_student_ids: List[Union[str, int]],
) -> UnmatchedStudentReason:
    has_compatible_peers = len(compatible_student_ids) > 0
    reason_code = "LEFTOVER_AFTER_GROUP_SELECTION" if has_compatible_peers else "NO_SHARED_INTEREST_IN_TRACK"

    reason = (
        "Student has shared-interest peers in this track, but no valid 2-5 member group remained after higher-scoring groups were selected."
        if has_compatible_peers
        else "Student does not share any area of interest with other students in this track, so mandatory interest matching cannot be satisfied."
    )

    return {
        "studentId": student["id"],
        "track": track,
        "reasonCode": reason_code,  # type: ignore
        "reason": reason,
        "compatibleStudentIdsInTrack": compatible_student_ids,
        "score": 0,
        "scoreBreakdown": {
            "baseScore": BASE_SCORE,
            "totalPenalty": BASE_SCORE,
            "explanation": "Unmatched score is 0 (base 100 minus full 100 penalty) because mandatory shared-interest matching failed for placement.",
        },
    }


def build_groups_for_track(
    students: List[StudentInput], track: Track
) -> Dict[str, Any]:
    groups: List[MatchGroup] = []
    student_scores: List[StudentScore] = []
    unmatched_student_ids: List[Union[str, int]] = []
    unmatched_student_reasons: List[UnmatchedStudentReason] = []

    remaining = sorted(students, key=lambda s: stringify_id(s["id"]))

    while len(remaining) >= 2:
        candidates = generate_scored_candidates(remaining, track)
        if not candidates:
            unmatched_student_ids.extend([s["id"] for s in remaining])
            remaining = []
            break

        best = candidates[0]
        member_id_set = set(best["memberIds"])

        groups.append({
            "track": track,
            "studentIds": best["memberIds"],  # type: ignore
            "groupSize": len(best["members"]),
            "groupScore": best["qualityScore"],
            "scoreBreakdown": best["scoreBreakdown"],
        })

        for member in best["members"]:
            score = score_student_in_group(member, best["members"], track)
            if score:
                student_scores.append(score)

        remaining = [
            s for s in remaining if stringify_id(s["id"]) not in member_id_set
        ]

    if len(remaining) == 1:
        unmatched_student_ids.append(remaining[0]["id"])

    for unmatched_id in unmatched_student_ids:
        unmatched_student = next(
            (s for s in students if stringify_id(s["id"]) == stringify_id(unmatched_id)),
            None,
        )
        if not unmatched_student:
            continue

        compatible_ids = get_compatible_student_ids_in_track(unmatched_student, students)
        unmatched_student_reasons.append(
            build_unmatched_reason(unmatched_student, track, compatible_ids)
        )

    unmatched_student_reasons.sort(
        key=lambda r: stringify_id(r["studentId"])
    )

    return {
        "groups": groups,
        "studentScores": student_scores,
        "unmatchedStudentIds": unmatched_student_ids,
        "unmatchedStudentReasons": unmatched_student_reasons,
    }


def build_groups(students: List[StudentInput]) -> MatchResult:
    groups: List[MatchGroup] = []
    student_scores: List[StudentScore] = []
    unmatched_student_ids: List[Union[str, int]] = []
    unmatched_student_reasons: List[UnmatchedStudentReason] = []

    students_by_track: Dict[Track, List[StudentInput]] = {}
    for student in students:
        track = resolve_student_track(student)
        if track not in students_by_track:
            students_by_track[track] = []
        students_by_track[track].append(student)

    for track, members in students_by_track.items():
        result = build_groups_for_track(members, track)
        groups.extend(result["groups"])
        student_scores.extend(result["studentScores"])
        unmatched_student_ids.extend(result["unmatchedStudentIds"])
        unmatched_student_reasons.extend(result["unmatchedStudentReasons"])

    # Sort results
    groups.sort(key=lambda g: (g["track"], "|".join(str(sid) for sid in g["studentIds"])))
    student_scores.sort(key=lambda s: stringify_id(s["studentId"]))
    unmatched_student_ids.sort(key=stringify_id)
    unmatched_student_reasons.sort(key=lambda r: stringify_id(r["studentId"]))

    return {
        "groups": groups,
        "studentScores": student_scores,
        "unmatchedStudentIds": unmatched_student_ids,
        "unmatchedStudentReasons": unmatched_student_reasons,
    }