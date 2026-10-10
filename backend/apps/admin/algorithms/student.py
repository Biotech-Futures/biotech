from typing import Any, Callable, Dict, List, Literal, Optional, Set, Tuple, TypedDict, Union
from itertools import combinations as itertools_combinations
from functools import cmp_to_key
import math

from apps.common.matching_modes import MatchMode, resolve_match_mode
from apps.common.matching_weights import BASE_SCORE, ScoringWeights

# ── Constants ──────────────────────────────────────────────────────────────

# The scoring magnitudes (year/country/timezone/size) used to be module-level
# constants here; they now live in ``ScoringWeights`` so an admin can retune them
# through the matching config without a deploy (MA1). Their default values are the
# constants this module used to hardcode.

# ── Type Definitions ───────────────────────────────────────────────────────

class StudentInput(TypedDict, total=False):
    id: Union[str, int]
    name: Optional[str]
    country: Optional[str]
    timezoneOffsetHours: Optional[float]
    yearLevel: Optional[int]
    yearlevel: Optional[int]
    interests: Optional[List[str]]


class ExistingGroupMemberInput(TypedDict, total=False):
    id: Union[str, int]
    name: Optional[str]
    country: Optional[str]
    timezoneOffsetHours: Optional[float]
    yearLevel: Optional[int]
    yearlevel: Optional[int]
    interests: Optional[List[Dict[str, Optional[str]]]]


class GroupScoreBreakdown(TypedDict):
    baseScore: float
    yearPenalty: float
    timezonePenalty: float
    totalPenalty: float
    sizeBonus: float
    objectiveScore: float


class MatchGroup(TypedDict):
    country: str
    studentIds: List[Union[str, int]]
    groupSize: int
    groupScore: float
    scoreBreakdown: GroupScoreBreakdown


class StudentScoreBreakdown(TypedDict):
    baseScore: float
    yearPenalty: float
    timezonePenalty: float
    totalPenalty: float


class StudentScore(TypedDict):
    studentId: Union[str, int]
    country: str
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
    timezonePenalty: float
    sizeBonus: float
    totalPenalty: float
    objectiveScore: float


class ExistingGroupInput(TypedDict, total=False):
    id: Union[str, int]
    groupName: str
    groupStudent: List[ExistingGroupMemberInput]
    tutor: Optional[Dict[str, Union[str, int]]]
    maxSize: Optional[int]


class IndividualStudentSource(TypedDict, total=False):
    id: Union[str, int]
    userId: Union[str, int]
    name: Optional[str]
    firstName: Optional[str]
    lastName: Optional[str]
    country: Optional[str]
    countryName: Optional[str]
    timezoneOffsetHours: Optional[float]
    yearLevel: Optional[int]
    yearlevel: Optional[int]
    interests: Optional[List[Union[str, Dict[str, Optional[str]]]]]


class GroupStudentSource(IndividualStudentSource, total=False):
    groupId: Union[str, int]
    groupName: Optional[str]
    groupTutorId: Optional[Union[str, int]]
    groupTutorName: Optional[str]


class CountryRecommendationInput(TypedDict):
    students: List[StudentInput]
    groups: List[ExistingGroupInput]


RecommendationInputByCountry = Dict[str, CountryRecommendationInput]


class UnmatchedStudentReason(TypedDict):
    studentId: Union[str, int]
    reasonCode: Literal["NO_SHARED_INTEREST", "LEFTOVER_AFTER_GROUP_SELECTION"]
    reason: str
    compatibleStudentIds: List[Union[str, int]]
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


def resolve_weights(weights: Optional[ScoringWeights] = None) -> ScoringWeights:
    """Scoring weights for this run, defaulting to the built-in constants."""
    return weights if weights is not None else ScoringWeights()


def round2(value: float) -> float:
    return math.floor(value * 100 + 0.5) / 100


def normalize_interest(interest: str) -> str:
    return interest.strip().lower()


def stringify_id(value: Union[str, int]) -> str:
    return str(value)


def to_display_name(first_name: Optional[str], last_name: Optional[str]) -> str:
    return " ".join(part for part in [first_name, last_name] if part).strip()


def nullish(value: Any, fallback: Any) -> Any:
    return fallback if value is None else value


def normalize_interests(
    interests: Optional[List[Union[str, Dict[str, Optional[str]]]]]
) -> List[str]:
    if not interests:
        return []

    normalized = []
    for interest in interests:
        if isinstance(interest, str):
            value = interest
        else:
            value = interest.get("interestDesc")
            if value is None:
                value = interest.get("name")
            if value is None:
                value = ""
        value = value.strip()
        if value:
            normalized.append(value)
    return normalized


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
            value = item.get("interestDesc")
            if value is None:
                value = item.get("name")
            interests.append(value or "")
    return {normalize_interest(i) for i in interests if i}


def get_student_year_level(student: StudentInput) -> int:
    year_level = student.get("yearLevel")
    if year_level is not None:
        return year_level
    yearlevel = student.get("yearlevel")
    return yearlevel if yearlevel is not None else 0


def get_member_year_level(member: ExistingGroupMemberInput) -> int:
    year_level = member.get("yearLevel")
    if year_level is not None:
        return year_level
    yearlevel = member.get("yearlevel")
    return yearlevel if yearlevel is not None else 0


def get_student_country(student: StudentInput) -> str:
    return nullish(student.get("country"), "")


def get_member_country(member: ExistingGroupMemberInput) -> str:
    return nullish(member.get("country"), "")


def get_student_timezone(student: StudentInput) -> float:
    return nullish(student.get("timezoneOffsetHours"), 0)


def get_member_timezone(member: ExistingGroupMemberInput) -> float:
    return nullish(member.get("timezoneOffsetHours"), 0)


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


def get_group_max_size(group: ExistingGroupInput) -> int:
    return nullish(group.get("maxSize"), 5)


def is_group_full(group: ExistingGroupInput) -> bool:
    return len(group.get("groupStudent", [])) >= get_group_max_size(group)


def get_group_country(group: List[StudentInput]) -> str:
    """Modal (most common) country among group members; '' when unknown."""
    counts: Dict[str, int] = {}
    for student in group:
        country = get_student_country(student)
        if country:
            counts[country] = counts.get(country, 0) + 1
    if not counts:
        return ""
    return max(sorted(counts.keys()), key=lambda country: counts[country])


def is_country_compatible(country_a: str, country_b: str) -> bool:
    """Same country, or one side unknown (unknown country acts as a wildcard)."""
    return not country_a or not country_b or country_a == country_b


def get_pair_country_mismatch_count(group: List[StudentInput]) -> int:
    """Cross-country pair count — a reported tie-breaker signal, never a penalty."""
    mismatch_count = 0
    for i in range(len(group)):
        for j in range(i + 1, len(group)):
            if not is_country_compatible(
                get_student_country(group[i]),
                get_student_country(group[j]),
            ):
                mismatch_count += 1
    return mismatch_count


def map_source_student(student: IndividualStudentSource) -> StudentInput:
    student_id = student.get("id", student.get("userId"))
    if student_id is None:
        raise ValueError("Student source is missing id/userId.")

    derived_name = to_display_name(student.get("firstName"), student.get("lastName"))
    country = student.get("country")
    if country is None:
        country = student.get("countryName")

    mapped = {
        "id": student_id,
        "name": nullish(student.get("name"), derived_name),
        "country": country,
        "timezoneOffsetHours": student.get("timezoneOffsetHours"),
        "yearLevel": student.get("yearLevel"),
        "yearlevel": student.get("yearlevel"),
        "interests": normalize_interests(student.get("interests")),
    }
    return {key: value for key, value in mapped.items() if value is not None}  # type: ignore


def get_shared_interests_with_group(student: StudentInput, group: ExistingGroupInput) -> List[str]:
    interest_sets = [to_interest_set(student)]
    for member in group.get("groupStudent", []):
        interest_sets.append(to_member_interest_set(member))
    return get_common_interests(interest_sets)


class RecommendationCandidate(TypedDict):
    group: ExistingGroupInput
    score: float
    averageYearGap: float
    averageTimezoneGap: float
    #: Peers whose country differs from the student's. MA4 ranks on this only
    #: after every scored signal has tied, so it is a pure count with no weight
    #: in the scoring configuration.
    countryMismatchCount: int
    sharedInterests: List[str]
    scoreBreakdown: RecommendationScoreBreakdown


def is_student_eligible_for_group(
    student: StudentInput,
    group: ExistingGroupInput,
    mode: MatchMode = "balanced",
) -> bool:
    if is_group_full(group):
        return False

    if len(get_shared_interests_with_group(student, group)) == 0:
        return False

    # Strict mode requires the student's country to match every group member's
    # country. An unknown country on either side is a wildcard, mirroring
    # mentor matching (see ``mentor.is_same_country_eligible``).
    if mode == "strict":
        student_country = get_student_country(student)
        for member in group.get("groupStudent", []):
            if not is_country_compatible(student_country, get_member_country(member)):
                return False

    return True


def score_student_for_existing_group(
    student: StudentInput,
    group: ExistingGroupInput,
    mode: MatchMode = "balanced",
    weights: Optional[ScoringWeights] = None,
) -> Optional[RecommendationCandidate]:
    if not is_student_eligible_for_group(student, group, mode):
        return None

    scoring = resolve_weights(weights)
    shared_interests = get_shared_interests_with_group(student, group)
    year_penalty_sum = 0.0
    country_mismatch_count = 0
    timezone_penalty_sum = 0.0
    timezone_gap_sum = 0.0

    group_students = group.get("groupStudent", [])
    if not group_students:
        return None

    for member in group_students:
        year_gap = abs(get_student_year_level(student) - get_member_year_level(member))
        year_penalty_sum += year_gap * scoring.year_weight

        timezone_gap = abs(get_student_timezone(student) - get_member_timezone(member))
        if get_student_country(student) != get_member_country(member):
            country_mismatch_count += 1
        timezone_penalty_sum += min(
            scoring.timezone_max_penalty,
            timezone_gap * scoring.timezone_weight,
        )
        timezone_gap_sum += timezone_gap

    peer_count = len(group_students)
    year_penalty = round2(year_penalty_sum / peer_count)
    timezone_penalty = round2(timezone_penalty_sum / peer_count)
    # MA4: the timezone penalty is earned by a real time gap whether or not a
    # border is crossed. Country does not score at all - it only breaks an
    # otherwise exact tie, via the count below, and is never part of this.
    total_penalty = round2(year_penalty + timezone_penalty)
    score = round2(clamp(BASE_SCORE - total_penalty, 0, 100))
    resulting_group_size = len(group_students) + 1
    size_bonus = scoring.size_bonus(resulting_group_size)
    objective_score = round2(clamp(score + size_bonus, 0, scoring.max_objective_score()))

    return {
        "group": group,
        "score": score,
        "averageYearGap": round2(
            sum(
                abs(get_student_year_level(student) - get_member_year_level(member))
                for member in group_students
            )
            / peer_count
        ),
        "averageTimezoneGap": round2(timezone_gap_sum / peer_count),
        "countryMismatchCount": country_mismatch_count,
        "sharedInterests": shared_interests,
        "scoreBreakdown": {
            "baseScore": BASE_SCORE,
            "yearPenalty": year_penalty,
            "timezonePenalty": timezone_penalty,
            "sizeBonus": size_bonus,
            "totalPenalty": total_penalty,
            "objectiveScore": objective_score,
        },
    }


def compare_recommendation_candidate(
    a: RecommendationCandidate,
    b: RecommendationCandidate,
) -> int:
    a_breakdown = a["scoreBreakdown"]
    b_breakdown = b["scoreBreakdown"]
    if b_breakdown["objectiveScore"] != a_breakdown["objectiveScore"]:
        return -1 if b_breakdown["objectiveScore"] < a_breakdown["objectiveScore"] else 1
    if b["score"] != a["score"]:
        return -1 if b["score"] < a["score"] else 1
    if a["averageYearGap"] != b["averageYearGap"]:
        return -1 if a["averageYearGap"] < b["averageYearGap"] else 1
    if a["averageTimezoneGap"] != b["averageTimezoneGap"]:
        return -1 if a["averageTimezoneGap"] < b["averageTimezoneGap"] else 1
    # MA4: country never scores, so it can only break an otherwise exact tie —
    # reached only when year and timezone distance have both been found equal.
    a_country_mismatch = a["countryMismatchCount"] > 0
    b_country_mismatch = b["countryMismatchCount"] > 0
    if a_country_mismatch != b_country_mismatch:
        return -1 if b_country_mismatch else 1
    a_id = stringify_id(a["group"]["id"])
    b_id = stringify_id(b["group"]["id"])
    return (a_id > b_id) - (a_id < b_id)


def build_matched_recommendation_reason(candidate: RecommendationCandidate) -> str:
    shared_interest = candidate["sharedInterests"][0]

    if candidate["countryMismatchCount"] == 0:
        return f"Shares interest '{shared_interest}' with the group and matches the same country."

    if candidate["scoreBreakdown"]["timezonePenalty"] == 0:
        return f"Shares interest '{shared_interest}' with the group and avoids extra timezone penalty."

    return f"Shares interest '{shared_interest}' with the group and is relatively close in timezone."


def build_unmatched_recommendation(
    student: StudentInput,
    groups: List[ExistingGroupInput],
) -> StudentGroupRecommendation:
    non_full_groups = [group for group in groups if not is_group_full(group)]
    has_interest_match = any(
        len(get_shared_interests_with_group(student, group)) > 0
        for group in non_full_groups
    )

    reason = "No eligible group found."
    if len(groups) == 0:
        reason = "No existing groups are available."
    elif len(non_full_groups) == 0:
        reason = "All existing groups are already full."
    elif not has_interest_match:
        reason = "No existing non-full group shares a common interest with the student."

    return {
        "student": student,
        "recommendGroup": None,
        "reason": reason,
        "score": 0,
        "scoreBreakdown": {
            "baseScore": BASE_SCORE,
            "yearPenalty": 0,
            "timezonePenalty": 0,
            "sizeBonus": 0,
            "totalPenalty": BASE_SCORE,
            "objectiveScore": 0,
        },
    }


# ── Main Scoring Functions ────────────────────────────────────────────────

def score_group(
    group: List[StudentInput],
    weights: Optional[ScoringWeights] = None,
) -> Optional[GroupScoreResult]:
    if len(group) < 2 or len(group) > 5:
        return None

    if not group_has_mandatory_interest_overlap(group):
        return None

    scoring = resolve_weights(weights)
    pair_count = get_pair_count(len(group))
    year_penalty_sum = 0.0
    timezone_penalty_sum = 0.0

    for i in range(len(group)):
        for j in range(i + 1, len(group)):
            a = group[i]
            b = group[j]
            year_gap = abs(get_student_year_level(a) - get_student_year_level(b))
            year_penalty_sum += year_gap * scoring.year_weight

            timezone_gap = abs(get_student_timezone(a) - get_student_timezone(b))
            timezone_penalty_sum += min(
                scoring.timezone_max_penalty,
                timezone_gap * scoring.timezone_weight,
            )

    year_penalty = round2(year_penalty_sum / pair_count)
    timezone_penalty = round2(timezone_penalty_sum / pair_count)
    # MA4: the timezone penalty is earned by a real time gap whether or not the
    # pair crosses a border. Country never scores - it only decides ties later.
    total_penalty = round2(year_penalty + timezone_penalty)
    quality_score = round2(clamp(BASE_SCORE - total_penalty, 0, 100))
    size_bonus = scoring.size_bonus(len(group))
    objective_score = round2(clamp(quality_score + size_bonus, 0, scoring.max_objective_score()))

    return {
        "qualityScore": quality_score,
        "yearSpread": compute_year_spread(group),
        "scoreBreakdown": {
            "baseScore": BASE_SCORE,
            "yearPenalty": year_penalty,
            "timezonePenalty": timezone_penalty,
            "totalPenalty": total_penalty,
            "sizeBonus": size_bonus,
            "objectiveScore": objective_score,
        },
    }


def score_student_in_group(
    student: StudentInput,
    group: List[StudentInput],
    weights: Optional[ScoringWeights] = None,
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

    scoring = resolve_weights(weights)
    year_penalty_sum = 0.0
    timezone_penalty_sum = 0.0

    for peer in peers:
        year_gap = abs(get_student_year_level(student) - get_student_year_level(peer))
        year_penalty_sum += year_gap * scoring.year_weight

        timezone_gap = abs(get_student_timezone(student) - get_student_timezone(peer))
        timezone_penalty_sum += min(
            scoring.timezone_max_penalty,
            timezone_gap * scoring.timezone_weight,
        )

    year_penalty = round2(year_penalty_sum / len(peers))
    timezone_penalty = round2(timezone_penalty_sum / len(peers))
    # MA4: timezone distance is scored on its own for every pair, country or
    # not. Country is never part of this score.
    total_penalty = round2(year_penalty + timezone_penalty)
    score = round2(clamp(BASE_SCORE - total_penalty, 0, 100))

    return {
        "studentId": student["id"],
        "country": get_student_country(student),
        "groupStudentIds": sorted(
            [stringify_id(m["id"]) for m in group],
        ),
        "score": score,
        "scoreBreakdown": {
            "baseScore": BASE_SCORE,
            "yearPenalty": year_penalty,
            "timezonePenalty": timezone_penalty,
            "totalPenalty": total_penalty,
        },
    }


def get_compatible_student_ids(
    student: StudentInput, pool_students: List[StudentInput]
) -> List[Union[str, int]]:
    compatible = [
        s["id"]
        for s in pool_students
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


def compute_average_pair_gap(
    group: List[StudentInput],
    value_of: Callable[[StudentInput], float],
) -> float:
    """Mean absolute difference of ``value_of`` across every pair in the group."""
    if len(group) < 2:
        return 0.0
    gap_sum = 0.0
    for i in range(len(group)):
        for j in range(i + 1, len(group)):
            gap_sum += abs(value_of(group[i]) - value_of(group[j]))
    return round2(gap_sum / get_pair_count(len(group)))


class CandidateSortKey(TypedDict):
    objectiveScore: float
    qualityScore: float
    memberCount: int
    interestCohesion: float
    yearSpread: int
    strandedStudentCount: int
    averageTimezoneGap: float
    averageYearGap: float
    countryMismatchCount: int
    memberIds: List[str]


def candidate_sort_key(
    candidate: CandidateSortKey,
    mode: MatchMode = "balanced",
) -> Tuple[Any, ...]:
    """Rank formed-group candidates.

    ``balanced`` optimises group quality: score first, then cohesion, then the
    smallest year spread. ``coverage`` optimises the number of students placed:
    a candidate that leaves a student with no interest-compatible peer left is
    ranked behind one that does not, so capacity is spent only when the pool has
    nothing safer to spend it on. Both modes end on the same tie-breaker tail,
    which is where country acts (MA4): it separates candidates only once
    timezone distance and year spread are equally close, so fewer cross-country
    pairs wins any remaining exact tie instead of outranking a real time gap.
    """
    if mode == "coverage":
        primary_key: Tuple[Any, ...] = (
            candidate["strandedStudentCount"],
            -candidate["memberCount"],
            -candidate["objectiveScore"],
        )
    else:
        primary_key = (
            -candidate["objectiveScore"],
            -candidate["qualityScore"],
            -candidate["interestCohesion"],
            candidate["yearSpread"],
        )

    return primary_key + (
        candidate["averageTimezoneGap"],
        candidate["averageYearGap"],
        candidate["countryMismatchCount"],
        "|".join(candidate["memberIds"]),
    )


# Exhaustive C(n, 2..5) enumeration is only tractable for small pools. When a
# single country bucket is larger than this, generate_scored_candidates
# considers just a sorted window of this many students per pass — the greedy
# loop still slides the window forward so every student is eventually grouped,
# but peak work stays at C(cap, 5) instead of C(n, 5) (which OOMs/hangs at n~100).
CANDIDATE_POOL_CAP = 24


def combinations(items: List[Any], choose: int):
    """Yield all combinations of items choosing 'choose' elements."""
    if choose <= 0 or choose > len(items):
        return
    yield from (list(combo) for combo in itertools_combinations(items, choose))


class ScoredCandidate(CandidateSortKey):
    members: List[StudentInput]
    scoreBreakdown: GroupScoreBreakdown


def build_interest_peers_by_id(students: List[StudentInput]) -> Dict[str, Set[str]]:
    """id -> ids of pool peers that share at least one interest."""
    interest_sets = {stringify_id(s["id"]): to_interest_set(s) for s in students}
    return {
        student_id: {
            other_id
            for other_id, other_interests in interest_sets.items()
            if other_id != student_id and other_interests & interest_sets[student_id]
        }
        for student_id, interests in interest_sets.items()
    }


def count_stranded_students(
    peers_by_id: Dict[str, Set[str]],
    member_id_set: Set[str],
) -> int:
    """Pool students left with no interest-compatible peer once the group is taken."""
    stranded = 0
    for student_id, peers in peers_by_id.items():
        if student_id in member_id_set:
            continue
        if not peers - member_id_set:
            stranded += 1
    return stranded


def generate_scored_candidates(
    students: List[StudentInput],
    mode: MatchMode = "balanced",
    weights: Optional[ScoringWeights] = None,
) -> List[ScoredCandidate]:
    scoring = resolve_weights(weights)
    candidates: List[ScoredCandidate] = []
    # Bound the exhaustive enumeration: a huge single-country bucket would
    # otherwise build C(n, 5) combinations and hang/OOM. The caller's greedy
    # loop re-invokes this after removing each chosen group, so windowing the
    # (deterministically sorted) pool still lets every student be grouped.
    pool = students if len(students) <= CANDIDATE_POOL_CAP else students[:CANDIDATE_POOL_CAP]
    max_size = min(5, len(pool))
    # Only coverage mode ranks on stranding, so only it pays for the peer index.
    peers_by_id = build_interest_peers_by_id(pool) if mode == "coverage" else {}

    for size in range(2, max_size + 1):
        combos = combinations(pool, size)
        for combo in combos:
            scored = score_group(combo, scoring)
            if not scored:
                continue

            # Strict mode keeps every group inside one country bucket; unknown
            # country stays a wildcard, exactly like mentor strict matching.
            if mode == "strict" and get_pair_country_mismatch_count(combo) > 0:
                continue

            member_ids = sorted([stringify_id(s["id"]) for s in combo])
            candidates.append({
                "members": combo,
                "memberIds": member_ids,
                "memberCount": len(member_ids),
                "qualityScore": scored["qualityScore"],
                "objectiveScore": scored["scoreBreakdown"]["objectiveScore"],
                "interestCohesion": compute_interest_cohesion(combo),
                "yearSpread": scored["yearSpread"],
                "strandedStudentCount": (
                    count_stranded_students(peers_by_id, set(member_ids))
                    if peers_by_id
                    else 0
                ),
                "averageYearGap": compute_average_pair_gap(combo, get_student_year_level),
                "averageTimezoneGap": compute_average_pair_gap(combo, get_student_timezone),
                "countryMismatchCount": get_pair_country_mismatch_count(combo),
                "scoreBreakdown": scored["scoreBreakdown"],
            })

    return sorted(candidates, key=lambda c: candidate_sort_key(c, mode))


def build_unmatched_reason(
    student: StudentInput,
    compatible_student_ids: List[Union[str, int]],
) -> UnmatchedStudentReason:
    has_compatible_peers = len(compatible_student_ids) > 0
    reason_code = "LEFTOVER_AFTER_GROUP_SELECTION" if has_compatible_peers else "NO_SHARED_INTEREST"

    reason = (
        "Student has shared-interest peers, but no valid 2-5 member group remained after higher-scoring groups were selected."
        if has_compatible_peers
        else "Student does not share any area of interest with other students, so mandatory interest matching cannot be satisfied."
    )

    return {
        "studentId": student["id"],
        "reasonCode": reason_code,  # type: ignore
        "reason": reason,
        "compatibleStudentIds": compatible_student_ids,
        "score": 0,
        "scoreBreakdown": {
            "baseScore": BASE_SCORE,
            "totalPenalty": BASE_SCORE,
            "explanation": "Unmatched score is 0 (base 100 minus full 100 penalty) because mandatory shared-interest matching failed for placement.",
        },
    }


def build_groups_for_country(
    students: List[StudentInput],
    mode: MatchMode = "balanced",
    weights: Optional[ScoringWeights] = None,
) -> Dict[str, Any]:
    groups: List[MatchGroup] = []
    student_scores: List[StudentScore] = []
    unmatched_student_ids: List[Union[str, int]] = []

    remaining = sorted(students, key=lambda s: stringify_id(s["id"]))

    while len(remaining) >= 2:
        candidates = generate_scored_candidates(remaining, mode, weights)
        if not candidates:
            unmatched_student_ids.extend([s["id"] for s in remaining])
            remaining = []
            break

        best = candidates[0]
        member_id_set = set(best["memberIds"])

        groups.append({
            "country": get_group_country(best["members"]),
            "studentIds": best["memberIds"],  # type: ignore
            "groupSize": len(best["members"]),
            "groupScore": best["qualityScore"],
            "scoreBreakdown": best["scoreBreakdown"],
        })

        for member in best["members"]:
            score = score_student_in_group(member, best["members"], weights)
            if score:
                student_scores.append(score)

        remaining = [
            s for s in remaining if stringify_id(s["id"]) not in member_id_set
        ]

    if len(remaining) == 1:
        unmatched_student_ids.append(remaining[0]["id"])

    return {
        "groups": groups,
        "studentScores": student_scores,
        "unmatchedStudentIds": unmatched_student_ids,
    }


def build_groups(
    students: List[StudentInput],
    mode: Union[MatchMode, str] = "balanced",
    weights: Optional[ScoringWeights] = None,
) -> MatchResult:
    """Form new groups from standalone students.

    Mirrors the three mentor matching levels rather than redefining them for
    students:

    - ``balanced`` (default) groups within a country first, then fills the
      remaining seats cross-country.
    - ``strict`` only forms groups whose members share a country (an unknown
      country on any member is a wildcard), so cross-country students stay
      unmatched instead of being dropped into a weaker group.
    - ``coverage`` runs the same two phases as ``balanced`` but prefers the
      group that places the most students, so leftovers are used as capacity
      allows.

    An unknown ``mode`` is normalised to ``balanced`` on entry, matching
    ``match_mentors``.
    """
    mode = resolve_match_mode(mode)

    groups: List[MatchGroup] = []
    student_scores: List[StudentScore] = []

    students_by_country: Dict[str, List[StudentInput]] = {}
    for student in students:
        country = get_student_country(student)
        if country not in students_by_country:
            students_by_country[country] = []
        students_by_country[country].append(student)

    # First pass: group within each country bucket.
    leftover_students: List[StudentInput] = []
    for country in sorted(students_by_country.keys()):
        members = students_by_country[country]
        result = build_groups_for_country(members, mode, weights)
        groups.extend(result["groups"])
        student_scores.extend(result["studentScores"])

        unmatched_ids = {stringify_id(sid) for sid in result["unmatchedStudentIds"]}
        leftover_students.extend(
            m for m in members if stringify_id(m["id"]) in unmatched_ids
        )

    # Second pass: cross-country grouping for students with no same-country
    # peers. Strict mode keeps the country gate here too, so the only pairs it
    # still allows are the ones an unknown country makes compatible.
    final_result = build_groups_for_country(leftover_students, mode, weights)
    groups.extend(final_result["groups"])
    student_scores.extend(final_result["studentScores"])
    unmatched_student_ids: List[Union[str, int]] = list(final_result["unmatchedStudentIds"])

    unmatched_student_reasons: List[UnmatchedStudentReason] = []
    for unmatched_id in unmatched_student_ids:
        unmatched_student = next(
            (s for s in students if stringify_id(s["id"]) == stringify_id(unmatched_id)),
            None,
        )
        if not unmatched_student:
            continue

        compatible_ids = get_compatible_student_ids(unmatched_student, students)
        unmatched_student_reasons.append(
            build_unmatched_reason(unmatched_student, compatible_ids)
        )

    # Sort results
    groups.sort(key=lambda g: (g["country"], "|".join(str(sid) for sid in g["studentIds"])))
    student_scores.sort(key=lambda s: stringify_id(s["studentId"]))
    unmatched_student_ids.sort(key=stringify_id)
    unmatched_student_reasons.sort(key=lambda r: stringify_id(r["studentId"]))

    return {
        "groups": groups,
        "studentScores": student_scores,
        "unmatchedStudentIds": unmatched_student_ids,
        "unmatchedStudentReasons": unmatched_student_reasons,
    }


def format_recommendation_input(
    group_students: List[GroupStudentSource],
    individual_students: List[IndividualStudentSource],
) -> RecommendationInputByCountry:
    # Joining an existing group has no country gate (country only affects the
    # score), so all students and groups share a single bucket.
    students: List[StudentInput] = []
    groups: List[ExistingGroupInput] = []
    groups_by_id: Dict[str, ExistingGroupInput] = {}

    for row in group_students:
        group_id = row.get("groupId")
        if group_id is None:
            continue

        group_id_key = stringify_id(group_id)
        group = groups_by_id.get(group_id_key)
        if not group:
            group = {
                "id": group_id,
                "groupName": nullish(row.get("groupName"), group_id_key),
                "groupStudent": [],
                "tutor": (
                    {
                        "id": row.get("groupTutorId"),
                        "name": nullish(row.get("groupTutorName"), ""),
                    }
                    if row.get("groupTutorId") is not None
                    else None
                ),
            }
            groups_by_id[group_id_key] = group
            groups.append(group)

        if not group.get("tutor") and row.get("groupTutorId") is not None:
            group["tutor"] = {
                "id": row.get("groupTutorId"),
                "name": nullish(row.get("groupTutorName"), ""),
            }

        group["groupStudent"].append(map_source_student(row))  # type: ignore

    for row in individual_students:
        students.append(map_source_student(row))

    return {"": {"students": students, "groups": groups}}


def recommend_groups_by_country(
    input_by_country: RecommendationInputByCountry,
    mode: Union[MatchMode, str] = "balanced",
    weights: Optional[ScoringWeights] = None,
) -> List[StudentGroupRecommendation]:
    """Rank existing groups for each student.

    ``mode`` is normalised on entry, so an unknown value behaves as
    ``balanced`` rather than silently taking the permissive path.
    """
    mode = resolve_match_mode(mode)

    recommendations: List[StudentGroupRecommendation] = []

    for _, bucket in input_by_country.items():
        for student in bucket["students"]:
            candidates = [
                candidate
                for group in bucket["groups"]
                for candidate in [score_student_for_existing_group(student, group, mode, weights)]
                if candidate is not None
            ]
            candidates.sort(key=cmp_to_key(compare_recommendation_candidate))

            if len(candidates) == 0:
                recommendations.append(
                    build_unmatched_recommendation(student, bucket["groups"])
                )
                continue

            best = candidates[0]
            recommendations.append({
                "student": student,
                "recommendGroup": best["group"],
                "reason": build_matched_recommendation_reason(best),
                "score": best["score"],
                "scoreBreakdown": best["scoreBreakdown"],
            })

    return sorted(
        recommendations,
        key=lambda recommendation: stringify_id(recommendation["student"]["id"]),
    )
