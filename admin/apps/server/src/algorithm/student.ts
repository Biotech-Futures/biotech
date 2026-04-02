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
  id: string | number;
  name?: string;
  region?: string;
  trackId?: string | number;
  country?: string;
  timezoneOffsetHours?: number;
  yearLevel?: number;
  yearlevel?: number;
  interests?: string[];
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
  studentIds: Array<string | number>;
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
  studentId: string | number;
  track: Track;
  groupStudentIds: Array<string | number>;
  score: number;
  scoreBreakdown: StudentScoreBreakdown;
};

export type MatchResult = {
  groups: MatchGroup[];
  studentScores: StudentScore[];
  unmatchedStudentIds: Array<string | number>;
  unmatchedStudentReasons: UnmatchedStudentReason[];
};

export type ExistingGroupMemberInput = {
  id: string | number;
  name?: string;
  trackId?: string | number;
  country?: string;
  timezoneOffsetHours?: number;
  yearLevel?: number;
  yearlevel?: number;
  interests?: string[];
};

export type ExistingGroupInput = {
  id: string | number;
  groupName: string;
  trackId: Track | string | number;
  groupStudent: ExistingGroupMemberInput[];
  tutor?: {
    id: string | number;
    name: string;
  } | null;
  maxSize?: number;
};

export type TrackRecommendationInput = {
  students: StudentInput[];
  groups: ExistingGroupInput[];
};

export type RecommendationInputByTrack = Partial<
  Record<Track, TrackRecommendationInput>
>;

export type RecommendationScoreBreakdown = {
  baseScore: number;
  yearPenalty: number;
  countryPenalty: number;
  timezonePenalty: number;
  sizeBonus: number;
  totalPenalty: number;
  objectiveScore: number;
};

export type StudentGroupRecommendation = {
  student: StudentInput;
  recommendGroup: ExistingGroupInput | null;
  reason: string;
  score: number;
  scoreBreakdown: RecommendationScoreBreakdown;
};

export type RawInterestInput =
  | string
  | {
      interestDesc?: string | null;
      name?: string | null;
    };

export type IndividualStudentSource = {
  id?: string | number;
  userId?: string | number;
  name?: string | null;
  firstName?: string | null;
  lastName?: string | null;
  region?: string | null;
  trackId?: string | number | null;
  trackCode?: string | null;
  country?: string | null;
  countryName?: string | null;
  timezoneOffsetHours?: number | null;
  yearLevel?: number | null;
  yearlevel?: number | null;
  interests?: RawInterestInput[] | null;
};

export type GroupStudentSource = IndividualStudentSource & {
  groupId: string | number;
  groupName?: string | null;
  groupTrackId?: string | number | null;
  groupTrackCode?: string | null;
  groupTutorId?: string | number | null;
  groupTutorName?: string | null;
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
  studentId: string | number;
  track: Track;
  reasonCode: UnmatchedReasonCode;
  reason: string;
  compatibleStudentIdsInTrack: Array<string | number>;
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

function toDisplayName(
  firstName?: string | null,
  lastName?: string | null,
): string {
  return [firstName, lastName].filter(Boolean).join(" ").trim();
}

function normalizeInterests(interests?: RawInterestInput[] | null): string[] {
  if (!interests) {
    return [];
  }

  return interests
    .map((interest) => {
      if (typeof interest === "string") {
        return interest;
      }

      return interest.interestDesc ?? interest.name ?? "";
    })
    .map((interest) => interest.trim())
    .filter(Boolean);
}

function toInterestSet(student: StudentInput): Set<string> {
  return new Set(
    (student.interests ?? []).map(normalizeInterest).filter(Boolean),
  );
}

function toMemberInterestSet(member: ExistingGroupMemberInput): Set<string> {
  return new Set(
    (member.interests ?? []).map(normalizeInterest).filter(Boolean),
  );
}

function getStudentYearLevel(student: StudentInput): number {
  return student.yearLevel ?? student.yearlevel ?? 0;
}

function getMemberYearLevel(member: ExistingGroupMemberInput): number {
  return member.yearLevel ?? member.yearlevel ?? 0;
}

function getStudentCountry(student: StudentInput): string {
  return student.country ?? "";
}

function getMemberCountry(member: ExistingGroupMemberInput): string {
  return member.country ?? "";
}

function getStudentTimezone(student: StudentInput): number {
  return student.timezoneOffsetHours ?? 0;
}

function getMemberTimezone(member: ExistingGroupMemberInput): number {
  return member.timezoneOffsetHours ?? 0;
}

function resolveStudentTrack(student: StudentInput): Track {
  if (
    student.trackId &&
    REGION_TRACKS.includes(student.trackId as RegionTrack)
  ) {
    return student.trackId as Track;
  }

  if (student.trackId === "GLOBAL") {
    return "GLOBAL";
  }

  return assignTrack(student.region ?? "");
}

function resolveTrackFromSource(source: {
  trackCode?: string | null;
  trackId?: string | number | null;
  region?: string | null;
}): Track {
  if (
    source.trackCode &&
    REGION_TRACKS.includes(source.trackCode as RegionTrack)
  ) {
    return source.trackCode as Track;
  }

  if (source.trackCode === "GLOBAL") {
    return "GLOBAL";
  }

  if (
    typeof source.trackId === "string" &&
    REGION_TRACKS.includes(source.trackId as RegionTrack)
  ) {
    return source.trackId as Track;
  }

  if (source.trackId === "GLOBAL") {
    return "GLOBAL";
  }

  return assignTrack(source.region ?? "");
}

function mapSourceStudent(student: IndividualStudentSource): StudentInput {
  const id = student.id ?? student.userId;
  if (id === undefined) {
    throw new Error("Student source is missing id/userId.");
  }

  const derivedName = toDisplayName(student.firstName, student.lastName);

  return {
    id,
    name: student.name ?? derivedName ?? undefined,
    region: student.region ?? undefined,
    trackId: student.trackCode ?? student.trackId ?? undefined,
    country: student.country ?? student.countryName ?? undefined,
    timezoneOffsetHours: student.timezoneOffsetHours ?? undefined,
    yearLevel: student.yearLevel ?? undefined,
    yearlevel: student.yearlevel ?? undefined,
    interests: normalizeInterests(student.interests),
  };
}

function stringifyId(value: string | number): string {
  return String(value);
}

function sameTrackId(
  left: Track | string | number | undefined,
  right: Track | string | number | undefined,
): boolean {
  if (left === undefined || right === undefined) {
    return false;
  }

  return stringifyId(left) === stringifyId(right);
}

function groupTrackToOutputTrack(group: ExistingGroupInput): Track {
  if (typeof group.trackId === "string" && group.trackId === "GLOBAL") {
    return "GLOBAL";
  }

  if (
    typeof group.trackId === "string" &&
    REGION_TRACKS.includes(group.trackId as RegionTrack)
  ) {
    return group.trackId as Track;
  }

  const firstStudent = group.groupStudent[0];
  return firstStudent
    ? resolveStudentTrack(firstStudent as StudentInput)
    : "GLOBAL";
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

function studentSharesInterestWithMember(
  student: StudentInput,
  member: ExistingGroupMemberInput,
): boolean {
  const studentInterests = toInterestSet(student);
  const memberInterests = toMemberInterestSet(member);

  for (const interest of studentInterests) {
    if (memberInterests.has(interest)) {
      return true;
    }
  }

  return false;
}

function getSharedInterestsWithGroup(
  student: StudentInput,
  group: ExistingGroupInput,
): string[] {
  const shared = new Set<string>();
  const studentInterests = toInterestSet(student);

  for (const member of group.groupStudent) {
    const memberInterests = toMemberInterestSet(member);
    for (const interest of studentInterests) {
      if (memberInterests.has(interest)) {
        shared.add(interest);
      }
    }
  }

  return [...shared].sort();
}

function groupHasMandatoryInterestOverlap(group: StudentInput[]): boolean {
  if (group.length < 2) {
    return false;
  }

  const hasMatchByStudent = new Map<string, boolean>(
    group.map((student) => [stringifyId(student.id), false]),
  );

  for (let i = 0; i < group.length; i++) {
    for (let j = i + 1; j < group.length; j++) {
      if (pairSharesInterest(group[i], group[j])) {
        hasMatchByStudent.set(stringifyId(group[i].id), true);
        hasMatchByStudent.set(stringifyId(group[j].id), true);
      }
    }
  }

  return [...hasMatchByStudent.values()].every(Boolean);
}

function computeYearSpread(group: StudentInput[]): number {
  const levels = group.map((student) => getStudentYearLevel(student));
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

function getGroupMaxSize(group: ExistingGroupInput): number {
  return group.maxSize ?? 5;
}

function isGroupFull(group: ExistingGroupInput): boolean {
  return group.groupStudent.length >= getGroupMaxSize(group);
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
      const yearGap = Math.abs(getStudentYearLevel(a) - getStudentYearLevel(b));

      if (trackType === "GLOBAL") {
        yearPenaltySum += yearGap * YEAR_WEIGHT_GLOBAL;
        const isSameCountry = getStudentCountry(a) === getStudentCountry(b);
        if (!isSameCountry) {
          countryPenaltySum += COUNTRY_MISMATCH_PENALTY;
          const timezoneGap = Math.abs(
            getStudentTimezone(a) - getStudentTimezone(b),
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
    const yearGap = Math.abs(
      getStudentYearLevel(student) - getStudentYearLevel(peer),
    );

    if (trackType === "GLOBAL") {
      yearPenaltySum += yearGap * YEAR_WEIGHT_GLOBAL;
      const isSameCountry =
        getStudentCountry(student) === getStudentCountry(peer);
      if (!isSameCountry) {
        countryPenaltySum += COUNTRY_MISMATCH_PENALTY;
        const timezoneGap = Math.abs(
          getStudentTimezone(student) - getStudentTimezone(peer),
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
    groupStudentIds: group
      .map((member) => member.id)
      .sort((a, b) => stringifyId(a).localeCompare(stringifyId(b))),
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

type RecommendationCandidate = {
  group: ExistingGroupInput;
  score: number;
  scoreBreakdown: RecommendationScoreBreakdown;
  averageYearGap: number;
  averageTimezoneGap: number;
  sharedInterests: string[];
};

function isStudentEligibleForGroup(
  student: StudentInput,
  group: ExistingGroupInput,
): boolean {
  const studentTrack = resolveStudentTrack(student);

  if (!sameTrackId(student.trackId ?? studentTrack, group.trackId)) {
    return false;
  }

  if (isGroupFull(group)) {
    return false;
  }

  return group.groupStudent.some((member) =>
    studentSharesInterestWithMember(student, member),
  );
}

function scoreStudentForExistingGroup(
  student: StudentInput,
  group: ExistingGroupInput,
): RecommendationCandidate | null {
  if (!isStudentEligibleForGroup(student, group)) {
    return null;
  }

  const sharedInterests = getSharedInterestsWithGroup(student, group);
  if (sharedInterests.length === 0) {
    return null;
  }

  const trackType = groupTrackToOutputTrack(group);
  let yearPenaltySum = 0;
  let countryPenaltySum = 0;
  let timezonePenaltySum = 0;
  let timezoneGapSum = 0;

  for (const member of group.groupStudent) {
    const yearGap = Math.abs(
      getStudentYearLevel(student) - getMemberYearLevel(member),
    );
    yearPenaltySum +=
      yearGap *
      (trackType === "GLOBAL" ? YEAR_WEIGHT_GLOBAL : YEAR_WEIGHT_REGION);

    if (trackType === "GLOBAL") {
      const timezoneGap = Math.abs(
        getStudentTimezone(student) - getMemberTimezone(member),
      );

      if (getStudentCountry(student) !== getMemberCountry(member)) {
        countryPenaltySum += COUNTRY_MISMATCH_PENALTY;
        timezonePenaltySum += Math.min(
          TIMEZONE_MAX_PENALTY,
          timezoneGap * TIMEZONE_WEIGHT,
        );
      }

      timezoneGapSum += timezoneGap;
    }
  }

  const peerCount = group.groupStudent.length;
  const yearPenalty = round2(yearPenaltySum / peerCount);
  const countryPenalty = round2(countryPenaltySum / peerCount);
  const timezonePenalty = round2(timezonePenaltySum / peerCount);
  const totalPenalty = round2(yearPenalty + countryPenalty + timezonePenalty);
  const score = round2(clamp(BASE_SCORE - totalPenalty, 0, 100));
  const resultingGroupSize = group.groupStudent.length + 1;
  const sizeBonus = getSizeBonus(resultingGroupSize);
  const objectiveScore = round2(clamp(score + sizeBonus, 0, 106));

  return {
    group,
    score,
    averageYearGap: round2(
      group.groupStudent.reduce(
        (sum, member) =>
          sum +
          Math.abs(getStudentYearLevel(student) - getMemberYearLevel(member)),
        0,
      ) / peerCount,
    ),
    averageTimezoneGap:
      trackType === "GLOBAL" ? round2(timezoneGapSum / peerCount) : 0,
    sharedInterests,
    scoreBreakdown: {
      baseScore: BASE_SCORE,
      yearPenalty,
      countryPenalty,
      timezonePenalty,
      sizeBonus,
      totalPenalty,
      objectiveScore,
    },
  };
}

function compareRecommendationCandidate(
  a: RecommendationCandidate,
  b: RecommendationCandidate,
): number {
  if (b.scoreBreakdown.objectiveScore !== a.scoreBreakdown.objectiveScore) {
    return b.scoreBreakdown.objectiveScore - a.scoreBreakdown.objectiveScore;
  }

  if (b.score !== a.score) {
    return b.score - a.score;
  }

  if (a.averageYearGap !== b.averageYearGap) {
    return a.averageYearGap - b.averageYearGap;
  }

  if (
    groupTrackToOutputTrack(a.group) === "GLOBAL" ||
    groupTrackToOutputTrack(b.group) === "GLOBAL"
  ) {
    if (a.averageTimezoneGap !== b.averageTimezoneGap) {
      return a.averageTimezoneGap - b.averageTimezoneGap;
    }
  }

  return stringifyId(a.group.id).localeCompare(stringifyId(b.group.id));
}

function buildMatchedRecommendationReason(
  candidate: RecommendationCandidate,
): string {
  const sharedInterest = candidate.sharedInterests[0];

  if (groupTrackToOutputTrack(candidate.group) !== "GLOBAL") {
    return `Shares interest '${sharedInterest}' with the group and has a close year level match.`;
  }

  if (candidate.scoreBreakdown.countryPenalty === 0) {
    return `Shares interest '${sharedInterest}' with the group and matches the same country.`;
  }

  if (candidate.scoreBreakdown.timezonePenalty === 0) {
    return `Shares interest '${sharedInterest}' with the group and avoids extra timezone penalty.`;
  }

  return `Shares interest '${sharedInterest}' with the group and is relatively close in timezone.`;
}

function buildUnmatchedRecommendation(
  student: StudentInput,
  track: Track,
  groups: ExistingGroupInput[],
): StudentGroupRecommendation {
  const sameTrackGroups = groups.filter((group) =>
    sameTrackId(group.trackId, track),
  );
  const nonFullGroups = sameTrackGroups.filter((group) => !isGroupFull(group));
  const hasInterestMatch = nonFullGroups.some((group) =>
    group.groupStudent.some((member) =>
      studentSharesInterestWithMember(student, member),
    ),
  );

  let reason = "No eligible group found in this track.";
  if (sameTrackGroups.length === 0) {
    reason = "No existing groups are available in this track.";
  } else if (nonFullGroups.length === 0) {
    reason = "All existing groups in this track are already full.";
  } else if (!hasInterestMatch) {
    reason =
      "No existing non-full group in this track shares a common interest with the student.";
  }

  return {
    student,
    recommendGroup: null,
    reason,
    score: 0,
    scoreBreakdown: {
      baseScore: BASE_SCORE,
      yearPenalty: 0,
      countryPenalty: 0,
      timezonePenalty: 0,
      sizeBonus: 0,
      totalPenalty: BASE_SCORE,
      objectiveScore: 0,
    },
  };
}

export function formatRecommendationInput(
  groupStudents: GroupStudentSource[],
  individualStudents: IndividualStudentSource[],
): RecommendationInputByTrack {
  const formatted: RecommendationInputByTrack = {};
  const groupsById = new Map<string, ExistingGroupInput>();

  for (const row of groupStudents) {
    const groupIdKey = stringifyId(row.groupId);
    const groupTrack = resolveTrackFromSource({
      trackCode: row.groupTrackCode,
      trackId: row.groupTrackId,
      region: row.region,
    });

    let group = groupsById.get(groupIdKey);
    if (!group) {
      group = {
        id: row.groupId,
        groupName: row.groupName ?? groupIdKey,
        trackId: row.groupTrackCode ?? row.groupTrackId ?? groupTrack,
        groupStudent: [],
        tutor:
          row.groupTutorId !== undefined && row.groupTutorId !== null
            ? {
                id: row.groupTutorId,
                name: row.groupTutorName ?? "",
              }
            : null,
      };
      groupsById.set(groupIdKey, group);
    }

    if (
      !group.tutor &&
      row.groupTutorId !== undefined &&
      row.groupTutorId !== null
    ) {
      group.tutor = {
        id: row.groupTutorId,
        name: row.groupTutorName ?? "",
      };
    }

    group.groupStudent.push(mapSourceStudent(row));

    const trackBucket = groupTrack;
    const existingBucket = formatted[trackBucket];
    if (!existingBucket) {
      formatted[trackBucket] = {
        students: [],
        groups: [group],
      };
    } else if (
      !existingBucket.groups.some((candidate) => candidate === group)
    ) {
      existingBucket.groups.push(group);
    }
  }

  for (const row of individualStudents) {
    const student = mapSourceStudent(row);
    const track = resolveTrackFromSource({
      trackCode:
        typeof student.trackId === "string" ? student.trackId : row.trackCode,
      trackId: row.trackId,
      region: row.region,
    });

    const existingBucket = formatted[track];
    if (!existingBucket) {
      formatted[track] = {
        students: [student],
        groups: [],
      };
    } else {
      existingBucket.students.push(student);
    }
  }

  return formatted;
}

export function recommendGroupsByTrack(
  input: RecommendationInputByTrack,
): StudentGroupRecommendation[] {
  const recommendations: StudentGroupRecommendation[] = [];
  const tracks = Object.entries(input) as [Track, TrackRecommendationInput][];

  for (const [track, trackInput] of tracks) {
    for (const student of trackInput.students) {
      const studentTrack = resolveStudentTrack(student);
      const candidates = trackInput.groups
        .filter((group) => sameTrackId(group.trackId, track))
        .map((group) => scoreStudentForExistingGroup(student, group))
        .filter(
          (candidate): candidate is RecommendationCandidate =>
            candidate !== null,
        )
        .sort(compareRecommendationCandidate);

      if (studentTrack !== track || candidates.length === 0) {
        recommendations.push(
          buildUnmatchedRecommendation(
            student,
            studentTrack,
            trackInput.groups,
          ),
        );
        continue;
      }

      const best = candidates[0];
      recommendations.push({
        student,
        recommendGroup: best.group,
        reason: buildMatchedRecommendationReason(best),
        score: best.score,
        scoreBreakdown: best.scoreBreakdown,
      });
    }
  }

  return recommendations.sort((a, b) =>
    stringifyId(a.student.id).localeCompare(stringifyId(b.student.id)),
  );
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
        memberIds: combo
          .map((student) => stringifyId(student.id))
          .sort((a, b) => a.localeCompare(b)),
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
): Array<string | number> {
  return trackStudents
    .filter(
      (candidate) => stringifyId(candidate.id) !== stringifyId(student.id),
    )
    .filter((candidate) => pairSharesInterest(student, candidate))
    .map((candidate) => candidate.id)
    .sort((a, b) => stringifyId(a).localeCompare(stringifyId(b)));
}

function buildUnmatchedReason(
  student: StudentInput,
  track: Track,
  compatibleStudentIdsInTrack: Array<string | number>,
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
  unmatchedStudentIds: Array<string | number>;
  unmatchedStudentReasons: UnmatchedStudentReason[];
} {
  const groups: MatchGroup[] = [];
  const studentScores: StudentScore[] = [];
  const unmatchedStudentIds: Array<string | number> = [];
  const unmatchedStudentReasons: UnmatchedStudentReason[] = [];

  const remaining = [...students].sort((a, b) =>
    stringifyId(a.id).localeCompare(stringifyId(b.id)),
  );

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
      (student) => !memberIdSet.has(stringifyId(student.id)),
    );
    remaining.length = 0;
    remaining.push(...nextRemaining);
  }

  if (remaining.length === 1) {
    unmatchedStudentIds.push(remaining[0].id);
  }

  for (const unmatchedId of unmatchedStudentIds) {
    const unmatchedStudent = students.find(
      (student) => stringifyId(student.id) === stringifyId(unmatchedId),
    );
    if (!unmatchedStudent) {
      continue;
    }

    const compatibleStudentIdsInTrack = getCompatibleStudentIdsInTrack(
      unmatchedStudent,
      students,
    );

    unmatchedStudentReasons.push(
      buildUnmatchedReason(
        unmatchedStudent,
        track,
        compatibleStudentIdsInTrack,
      ),
    );
  }

  unmatchedStudentReasons.sort((a, b) =>
    stringifyId(a.studentId).localeCompare(stringifyId(b.studentId)),
  );

  return {
    groups,
    studentScores,
    unmatchedStudentIds,
    unmatchedStudentReasons,
  };
}

export function buildGroups(students: StudentInput[]): MatchResult {
  const groups: MatchGroup[] = [];
  const studentScores: StudentScore[] = [];
  const unmatchedStudentIds: Array<string | number> = [];
  const unmatchedStudentReasons: UnmatchedStudentReason[] = [];

  const studentsByTrack = new Map<Track, StudentInput[]>();

  for (const student of students) {
    const track = resolveStudentTrack(student);
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
  studentScores.sort((a, b) =>
    stringifyId(a.studentId).localeCompare(stringifyId(b.studentId)),
  );
  unmatchedStudentIds.sort((a, b) =>
    stringifyId(a).localeCompare(stringifyId(b)),
  );
  unmatchedStudentReasons.sort((a, b) =>
    stringifyId(a.studentId).localeCompare(stringifyId(b.studentId)),
  );

  return {
    groups,
    studentScores,
    unmatchedStudentIds,
    unmatchedStudentReasons,
  };
}
