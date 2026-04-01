export const REGION_TRACKS = [
  "AUS-NSW",
  "AUS-QLD",
  "AUS-VIC",
  "AUS-WA",
  "BRA",
] as const;

export type RegionTrack = (typeof REGION_TRACKS)[number];
export type Track = RegionTrack | "GLOBAL";

export type StudentInput = {
  id: string;
  region: string;
  country: string;
  timezoneOffsetHours: number;
  yearLevel: number;
  interests: string[];
};

export type GroupScoreBreakdown = {
  baseScore: number;
  yearPenalty: number;
  countryPenalty: number;
  timezonePenalty: number;
  totalPenalty: number;
  sizeBonus: number;
  objectiveScore: number;
};

export type MatchGroup = {
  track: Track;
  studentIds: string[];
  groupSize: number;
  groupScore: number;
  scoreBreakdown: GroupScoreBreakdown;
};

export type StudentScoreBreakdown = {
  baseScore: number;
  yearPenalty: number;
  countryPenalty: number;
  timezonePenalty: number;
  totalPenalty: number;
};

export type StudentScore = {
  studentId: string;
  track: Track;
  groupStudentIds: string[];
  score: number;
  scoreBreakdown: StudentScoreBreakdown;
};

export type MatchResult = {
  groups: MatchGroup[];
  studentScores: StudentScore[];
  unmatchedStudentIds: string[];
  unmatchedStudentReasons: UnmatchedStudentReason[];
};

export type GroupScoreResult = {
  qualityScore: number;
  scoreBreakdown: GroupScoreBreakdown;
  yearSpread: number;
};

export type UnmatchedReasonCode =
  | "NO_SHARED_INTEREST_IN_TRACK"
  | "LEFTOVER_AFTER_GROUP_SELECTION";

export type UnmatchedStudentReason = {
  studentId: string;
  track: Track;
  reasonCode: UnmatchedReasonCode;
  reason: string;
  compatibleStudentIdsInTrack: string[];
  score: 0;
  scoreBreakdown: {
    baseScore: number;
    totalPenalty: number;
    explanation: string;
  };
};

const BASE_SCORE = 100;
const YEAR_WEIGHT_REGION = 8;
const YEAR_WEIGHT_GLOBAL = 6;
const COUNTRY_MISMATCH_PENALTY = 12;
const TIMEZONE_WEIGHT = 2;
const TIMEZONE_MAX_PENALTY = 18;
const SIZE_BONUS: Record<2 | 3 | 4 | 5, number> = {
  2: 0,
  3: 3,
  4: 5,
  5: 6,
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

function normalizeInterest(interest: string): string {
  return interest.trim().toLowerCase();
}

function toInterestSet(student: StudentInput): Set<string> {
  return new Set(student.interests.map(normalizeInterest).filter(Boolean));
}

export function assignTrack(region: string): Track {
  return REGION_TRACKS.includes(region as RegionTrack)
    ? (region as RegionTrack)
    : "GLOBAL";
}

function pairSharesInterest(a: StudentInput, b: StudentInput): boolean {
  const aInterests = toInterestSet(a);
  const bInterests = toInterestSet(b);

  for (const interest of aInterests) {
    if (bInterests.has(interest)) {
      return true;
    }
  }

  return false;
}

function groupHasMandatoryInterestOverlap(group: StudentInput[]): boolean {
  if (group.length < 2) {
    return false;
  }

  const hasMatchByStudent = new Map<string, boolean>(
    group.map((student) => [student.id, false]),
  );

  for (let i = 0; i < group.length; i++) {
    for (let j = i + 1; j < group.length; j++) {
      if (pairSharesInterest(group[i], group[j])) {
        hasMatchByStudent.set(group[i].id, true);
        hasMatchByStudent.set(group[j].id, true);
      }
    }
  }

  return [...hasMatchByStudent.values()].every(Boolean);
}

function computeYearSpread(group: StudentInput[]): number {
  const levels = group.map((student) => student.yearLevel);
  return Math.max(...levels) - Math.min(...levels);
}

function getPairCount(groupSize: number): number {
  return (groupSize * (groupSize - 1)) / 2;
}

function getSizeBonus(groupSize: number): number {
  if (groupSize < 2 || groupSize > 5) {
    return 0;
  }

  return SIZE_BONUS[groupSize as 2 | 3 | 4 | 5];
}

export function scoreGroup(
  group: StudentInput[],
  trackType: Track,
): GroupScoreResult | null {
  if (group.length < 2 || group.length > 5) {
    return null;
  }

  if (!groupHasMandatoryInterestOverlap(group)) {
    return null;
  }

  const pairCount = getPairCount(group.length);
  let yearPenaltySum = 0;
  let countryPenaltySum = 0;
  let timezonePenaltySum = 0;

  for (let i = 0; i < group.length; i++) {
    for (let j = i + 1; j < group.length; j++) {
      const a = group[i];
      const b = group[j];
      const yearGap = Math.abs(a.yearLevel - b.yearLevel);

      if (trackType === "GLOBAL") {
        yearPenaltySum += yearGap * YEAR_WEIGHT_GLOBAL;
        const isSameCountry = a.country === b.country;
        if (!isSameCountry) {
          countryPenaltySum += COUNTRY_MISMATCH_PENALTY;
          const timezoneGap = Math.abs(
            a.timezoneOffsetHours - b.timezoneOffsetHours,
          );
          timezonePenaltySum += Math.min(
            TIMEZONE_MAX_PENALTY,
            timezoneGap * TIMEZONE_WEIGHT,
          );
        }
      } else {
        yearPenaltySum += yearGap * YEAR_WEIGHT_REGION;
      }
    }
  }

  const yearPenalty = round2(yearPenaltySum / pairCount);
  const countryPenalty = round2(countryPenaltySum / pairCount);
  const timezonePenalty = round2(timezonePenaltySum / pairCount);
  const totalPenalty = round2(yearPenalty + countryPenalty + timezonePenalty);
  const qualityScore = round2(clamp(BASE_SCORE - totalPenalty, 0, 100));
  const sizeBonus = getSizeBonus(group.length);
  const objectiveScore = round2(clamp(qualityScore + sizeBonus, 0, 106));

  return {
    qualityScore,
    yearSpread: computeYearSpread(group),
    scoreBreakdown: {
      baseScore: BASE_SCORE,
      yearPenalty,
      countryPenalty,
      timezonePenalty,
      totalPenalty,
      sizeBonus,
      objectiveScore,
    },
  };
}

export function scoreStudentInGroup(
  student: StudentInput,
  group: StudentInput[],
  trackType: Track,
): StudentScore | null {
  if (group.length < 2 || group.length > 5) {
    return null;
  }

  if (!group.some((member) => member.id === student.id)) {
    return null;
  }

  if (!groupHasMandatoryInterestOverlap(group)) {
    return null;
  }

  const peers = group.filter((member) => member.id !== student.id);
  if (peers.length === 0) {
    return null;
  }

  let yearPenaltySum = 0;
  let countryPenaltySum = 0;
  let timezonePenaltySum = 0;

  for (const peer of peers) {
    const yearGap = Math.abs(student.yearLevel - peer.yearLevel);

    if (trackType === "GLOBAL") {
      yearPenaltySum += yearGap * YEAR_WEIGHT_GLOBAL;
      const isSameCountry = student.country === peer.country;
      if (!isSameCountry) {
        countryPenaltySum += COUNTRY_MISMATCH_PENALTY;
        const timezoneGap = Math.abs(
          student.timezoneOffsetHours - peer.timezoneOffsetHours,
        );
        timezonePenaltySum += Math.min(
          TIMEZONE_MAX_PENALTY,
          timezoneGap * TIMEZONE_WEIGHT,
        );
      }
    } else {
      yearPenaltySum += yearGap * YEAR_WEIGHT_REGION;
    }
  }

  const yearPenalty = round2(yearPenaltySum / peers.length);
  const countryPenalty = round2(countryPenaltySum / peers.length);
  const timezonePenalty = round2(timezonePenaltySum / peers.length);
  const totalPenalty = round2(yearPenalty + countryPenalty + timezonePenalty);
  const score = round2(clamp(BASE_SCORE - totalPenalty, 0, 100));

  return {
    studentId: student.id,
    track: trackType,
    groupStudentIds: group.map((member) => member.id).sort(),
    score,
    scoreBreakdown: {
      baseScore: BASE_SCORE,
      yearPenalty,
      countryPenalty,
      timezonePenalty,
      totalPenalty,
    },
  };
}

type ScoredCandidate = {
  members: StudentInput[];
  memberIds: string[];
  qualityScore: number;
  objectiveScore: number;
  yearSpread: number;
  scoreBreakdown: GroupScoreBreakdown;
};

function compareCandidate(a: ScoredCandidate, b: ScoredCandidate): number {
  if (b.objectiveScore !== a.objectiveScore) {
    return b.objectiveScore - a.objectiveScore;
  }

  if (b.qualityScore !== a.qualityScore) {
    return b.qualityScore - a.qualityScore;
  }

  if (a.yearSpread !== b.yearSpread) {
    return a.yearSpread - b.yearSpread;
  }

  const aKey = a.memberIds.join("|");
  const bKey = b.memberIds.join("|");
  return aKey.localeCompare(bKey);
}

function combinations<T>(items: T[], choose: number): T[][] {
  if (choose <= 0 || choose > items.length) {
    return [];
  }

  const result: T[][] = [];
  const current: T[] = [];

  const backtrack = (start: number) => {
    if (current.length === choose) {
      result.push([...current]);
      return;
    }

    for (let i = start; i < items.length; i++) {
      current.push(items[i]);
      backtrack(i + 1);
      current.pop();
    }
  };

  backtrack(0);
  return result;
}

function generateScoredCandidates(
  students: StudentInput[],
  track: Track,
): ScoredCandidate[] {
  const candidates: ScoredCandidate[] = [];
  const maxSize = Math.min(5, students.length);

  for (let size = 2; size <= maxSize; size++) {
    const combos = combinations(students, size);

    for (const combo of combos) {
      const scored = scoreGroup(combo, track);
      if (!scored) {
        continue;
      }

      candidates.push({
        members: combo,
        memberIds: combo.map((student) => student.id).sort(),
        qualityScore: scored.qualityScore,
        objectiveScore: scored.scoreBreakdown.objectiveScore,
        yearSpread: scored.yearSpread,
        scoreBreakdown: scored.scoreBreakdown,
      });
    }
  }

  return candidates.sort(compareCandidate);
}

function getCompatibleStudentIdsInTrack(
  student: StudentInput,
  trackStudents: StudentInput[],
): string[] {
  return trackStudents
    .filter((candidate) => candidate.id !== student.id)
    .filter((candidate) => pairSharesInterest(student, candidate))
    .map((candidate) => candidate.id)
    .sort();
}

function buildUnmatchedReason(
  student: StudentInput,
  track: Track,
  compatibleStudentIdsInTrack: string[],
): UnmatchedStudentReason {
  const hasCompatiblePeers = compatibleStudentIdsInTrack.length > 0;
  const reasonCode: UnmatchedReasonCode = hasCompatiblePeers
    ? "LEFTOVER_AFTER_GROUP_SELECTION"
    : "NO_SHARED_INTEREST_IN_TRACK";

  const reason = hasCompatiblePeers
    ? "Student has shared-interest peers in this track, but no valid 2-5 member group remained after higher-scoring groups were selected."
    : "Student does not share any area of interest with other students in this track, so mandatory interest matching cannot be satisfied.";

  return {
    studentId: student.id,
    track,
    reasonCode,
    reason,
    compatibleStudentIdsInTrack,
    score: 0,
    scoreBreakdown: {
      baseScore: BASE_SCORE,
      totalPenalty: BASE_SCORE,
      explanation:
        "Unmatched score is 0 (base 100 minus full 100 penalty) because mandatory shared-interest matching failed for placement.",
    },
  };
}

function buildGroupsForTrack(
  students: StudentInput[],
  track: Track,
): {
  groups: MatchGroup[];
  studentScores: StudentScore[];
  unmatchedStudentIds: string[];
  unmatchedStudentReasons: UnmatchedStudentReason[];
} {
  const groups: MatchGroup[] = [];
  const studentScores: StudentScore[] = [];
  const unmatchedStudentIds: string[] = [];
  const unmatchedStudentReasons: UnmatchedStudentReason[] = [];

  const remaining = [...students].sort((a, b) => a.id.localeCompare(b.id));

  while (remaining.length >= 2) {
    const candidates = generateScoredCandidates(remaining, track);
    if (candidates.length === 0) {
      unmatchedStudentIds.push(...remaining.map((student) => student.id));
      remaining.length = 0;
      break;
    }

    const best = candidates[0];
    const memberIdSet = new Set(best.memberIds);

    groups.push({
      track,
      studentIds: best.memberIds,
      groupSize: best.members.length,
      groupScore: best.qualityScore,
      scoreBreakdown: best.scoreBreakdown,
    });

    for (const member of best.members) {
      const score = scoreStudentInGroup(member, best.members, track);
      if (score) {
        studentScores.push(score);
      }
    }

    const nextRemaining = remaining.filter(
      (student) => !memberIdSet.has(student.id),
    );
    remaining.length = 0;
    remaining.push(...nextRemaining);
  }

  if (remaining.length === 1) {
    unmatchedStudentIds.push(remaining[0].id);
  }

  for (const unmatchedId of unmatchedStudentIds) {
    const unmatchedStudent = students.find((student) => student.id === unmatchedId);
    if (!unmatchedStudent) {
      continue;
    }

    const compatibleStudentIdsInTrack = getCompatibleStudentIdsInTrack(
      unmatchedStudent,
      students,
    );

    unmatchedStudentReasons.push(
      buildUnmatchedReason(unmatchedStudent, track, compatibleStudentIdsInTrack),
    );
  }

  unmatchedStudentReasons.sort((a, b) => a.studentId.localeCompare(b.studentId));

  return { groups, studentScores, unmatchedStudentIds, unmatchedStudentReasons };
}

export function buildGroups(students: StudentInput[]): MatchResult {
  const groups: MatchGroup[] = [];
  const studentScores: StudentScore[] = [];
  const unmatchedStudentIds: string[] = [];
  const unmatchedStudentReasons: UnmatchedStudentReason[] = [];

  const studentsByTrack = new Map<Track, StudentInput[]>();

  for (const student of students) {
    const track = assignTrack(student.region);
    const arr = studentsByTrack.get(track);
    if (arr) {
      arr.push(student);
    } else {
      studentsByTrack.set(track, [student]);
    }
  }

  for (const [track, members] of studentsByTrack) {
    const result = buildGroupsForTrack(members, track);
    groups.push(...result.groups);
    studentScores.push(...result.studentScores);
    unmatchedStudentIds.push(...result.unmatchedStudentIds);
    unmatchedStudentReasons.push(...result.unmatchedStudentReasons);
  }

  groups.sort((a, b) => {
    if (a.track !== b.track) {
      return a.track.localeCompare(b.track);
    }
    return a.studentIds.join("|").localeCompare(b.studentIds.join("|"));
  });
  studentScores.sort((a, b) => a.studentId.localeCompare(b.studentId));
  unmatchedStudentIds.sort((a, b) => a.localeCompare(b));
  unmatchedStudentReasons.sort((a, b) => a.studentId.localeCompare(b.studentId));

  return {
    groups,
    studentScores,
    unmatchedStudentIds,
    unmatchedStudentReasons,
  };
}
