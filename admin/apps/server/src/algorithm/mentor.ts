const BASE_SCORE = 100;
const TRACK_MISMATCH_PENALTY = 40;
const INTEREST_OVERLAP_MAX_BONUS = 30;
const TIMEZONE_WEIGHT = 2;
const TIMEZONE_MAX_PENALTY = 18;
const CAPACITY_BONUS_PER_SLOT = 2;

const TRACK_UTC_OFFSET: Record<string, number> = {
  "AUS-NSW": 10,
  "AUS-QLD": 10,
  "AUS-VIC": 10,
  "AUS-WA": 8,
  "BRA": -3,
  "GLOBAL": 0, // neutral, skip timezone penalty
};

export type MentorSource = {
  mentorId: number;
  firstName: string;
  lastName: string;
  trackCode: string;
  institution: string | null;
  interests: string[];
  maxGroupCount: number;
  currentAcceptedCount: number;
};

export type GroupSource = {
  groupId: number;
  groupName: string;
  trackCode: string;
  studentInterests: string[]; // union of all member student interests
  studentCount: number;
};

export type MentorScoreBreakdown = {
  baseScore: number;
  trackPenalty: number;
  interestBonus: number;
  timezonePenalty: number;
  capacityBonus: number;
  objectiveScore: number;
};

export type MentorGroupRecommendation = {
  group: GroupSource;
  recommendedMentor: {
    mentorId: number;
    name: string;
    trackCode: string;
    institution: string | null;
    interests: string[];
    remainingCapacity: number;
  } | null;
  reason: string;
  score: number;
  scoreBreakdown: MentorScoreBreakdown;
};

function computeInterestBonus(
  mentorInterests: string[],
  groupInterests: string[],
): number {
  if (mentorInterests.length === 0 || groupInterests.length === 0) return 0;

  const groupInterestSet = new Set(groupInterests.map((i) => i.toLowerCase()));
  const overlapCount = mentorInterests.filter((i) =>
    groupInterestSet.has(i.toLowerCase()),
  ).length;
  const overlapRatio =
    overlapCount / Math.max(mentorInterests.length, groupInterests.length);

  return Math.round(overlapRatio * INTEREST_OVERLAP_MAX_BONUS);
}

function scoreMentorForGroup(
  mentor: MentorSource,
  group: GroupSource,
): { score: number; breakdown: MentorScoreBreakdown; reason: string } {
  const breakdown: MentorScoreBreakdown = {
    baseScore: BASE_SCORE,
    trackPenalty: 0,
    interestBonus: 0,
    timezonePenalty: 0,
    capacityBonus: 0,
    objectiveScore: 0,
  };

  const mentorTrack = mentor.trackCode;
  const groupTrack = group.trackCode;
  const isGlobal = mentorTrack === "GLOBAL" || groupTrack === "GLOBAL";
  const trackMatch = isGlobal || mentorTrack === groupTrack;

  if (!trackMatch) {
    breakdown.trackPenalty = TRACK_MISMATCH_PENALTY;
  }

  breakdown.interestBonus = computeInterestBonus(
    mentor.interests,
    group.studentInterests,
  );

  if (!isGlobal) {
    const mentorOffset = TRACK_UTC_OFFSET[mentorTrack] ?? 0;
    const groupOffset = TRACK_UTC_OFFSET[groupTrack] ?? 0;
    const tzDist = Math.abs(mentorOffset - groupOffset);
    breakdown.timezonePenalty = Math.min(
      tzDist * TIMEZONE_WEIGHT,
      TIMEZONE_MAX_PENALTY,
    );
  }

  const remainingCapacity = mentor.maxGroupCount - mentor.currentAcceptedCount;
  breakdown.capacityBonus = remainingCapacity * CAPACITY_BONUS_PER_SLOT;

  breakdown.objectiveScore =
    breakdown.baseScore -
    breakdown.trackPenalty +
    breakdown.interestBonus -
    breakdown.timezonePenalty +
    breakdown.capacityBonus;

  const reasons: string[] = [];
  if (trackMatch && !isGlobal) {
    reasons.push(`Track match: ${mentorTrack}`);
  }
  if (isGlobal) {
    reasons.push("GLOBAL track (flexible timezone)");
  }
  if (breakdown.interestBonus > 0) {
    const groupInterestSet = new Set(
      group.studentInterests.map((i) => i.toLowerCase()),
    );
    const overlapping = mentor.interests.filter((i) =>
      groupInterestSet.has(i.toLowerCase()),
    );
    reasons.push(`Shared interests: ${overlapping.slice(0, 3).join(", ")}`);
  }
  if (!trackMatch) {
    reasons.push("Track mismatch penalty applied");
  }

  const reason =
    reasons.length > 0 ? reasons.join(". ") : "No matching criteria found.";

  return { score: breakdown.objectiveScore, breakdown, reason };
}

export function matchMentors(
  groups: GroupSource[],
  mentors: MentorSource[],
): MentorGroupRecommendation[] {
  const availableMentors = mentors.filter(
    (m) => m.currentAcceptedCount < m.maxGroupCount,
  );

  return groups.map((group) => {
    if (availableMentors.length === 0) {
      return {
        group,
        recommendedMentor: null,
        reason: "No available mentors with remaining capacity.",
        score: 0,
        scoreBreakdown: {
          baseScore: BASE_SCORE,
          trackPenalty: 0,
          interestBonus: 0,
          timezonePenalty: 0,
          capacityBonus: 0,
          objectiveScore: 0,
        },
      };
    }

    let bestMentor: MentorSource | null = null;
    let bestScore = -Infinity;
    let bestBreakdown: MentorScoreBreakdown = {
      baseScore: BASE_SCORE,
      trackPenalty: 0,
      interestBonus: 0,
      timezonePenalty: 0,
      capacityBonus: 0,
      objectiveScore: 0,
    };
    let bestReason = "";

    for (const mentor of availableMentors) {
      const { score, breakdown, reason } = scoreMentorForGroup(mentor, group);
      if (score > bestScore) {
        bestScore = score;
        bestMentor = mentor;
        bestBreakdown = breakdown;
        bestReason = reason;
      }
    }

    return {
      group,
      recommendedMentor: bestMentor
        ? {
            mentorId: bestMentor.mentorId,
            name: `${bestMentor.firstName} ${bestMentor.lastName}`.trim(),
            trackCode: bestMentor.trackCode,
            institution: bestMentor.institution,
            interests: bestMentor.interests,
            remainingCapacity:
              bestMentor.maxGroupCount - bestMentor.currentAcceptedCount,
          }
        : null,
      reason: bestReason,
      score: bestScore === -Infinity ? 0 : bestScore,
      scoreBreakdown: bestBreakdown,
    };
  });
}
