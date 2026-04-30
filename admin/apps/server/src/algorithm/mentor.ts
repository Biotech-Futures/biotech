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
  "AUS-SA": 9.5,
  "BRA": -3,
  "GLOBAL": 0, // neutral, skip timezone penalty
};

export type MatchMode = "balanced" | "strict" | "coverage";

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

export type GroupStudent = {
  name: string;
  interests: string[];
};

export type GroupSource = {
  groupId: number;
  groupName: string;
  trackCode: string;
  studentInterests: string[]; // union of all member student interests
  studentCount: number;
  students?: GroupStudent[]; // display-only, not used by the algorithm
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

// ── Helpers ───────────────────────────────────────────────────────────────────

function isSameTrackEligible(mentor: MentorSource, group: GroupSource): boolean {
  return (
    mentor.trackCode === "GLOBAL" ||
    group.trackCode === "GLOBAL" ||
    mentor.trackCode === group.trackCode
  );
}

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

// ── Score matrix ──────────────────────────────────────────────────────────────

type ScoreEntry = { score: number; breakdown: MentorScoreBreakdown; reason: string };

function buildScoreMatrix(
  groups: GroupSource[],
  mentors: MentorSource[],
): Map<string, ScoreEntry> {
  const matrix = new Map<string, ScoreEntry>();
  for (const group of groups) {
    for (const mentor of mentors) {
      matrix.set(
        `${group.groupId}:${mentor.mentorId}`,
        scoreMentorForGroup(mentor, group),
      );
    }
  }
  return matrix;
}

// ── Gale-Shapley (College Admissions) ────────────────────────────────────────
// Groups propose to mentors; mentors accept by descending score.
// A mentor holds at most `slots[mentorId]` groups and displaces the worst when full.
// Returns: assignment map (groupId → mentorId) and tentative map (mentorId → Set<groupId>).

type GaleShapleyResult = {
  assignment: Map<number, number>;
  tentative: Map<number, Set<number>>;
};

function galeShapley(
  groups: GroupSource[],
  mentors: MentorSource[],
  scoreMatrix: Map<string, ScoreEntry>,
  slotsOverride?: Map<number, number>, // if omitted, uses maxGroupCount - currentAcceptedCount
): GaleShapleyResult {
  const slots = slotsOverride ??
    new Map(mentors.map((m) => [m.mentorId, m.maxGroupCount - m.currentAcceptedCount]));

  const tentative = new Map<number, Set<number>>(
    mentors.map((m) => [m.mentorId, new Set()]),
  );
  const assignment = new Map<number, number>();
  const nextIdx = new Map<number, number>(groups.map((g) => [g.groupId, 0]));

  // Build each group's ranked mentor preference list (descending score)
  const groupPreferences = new Map<number, MentorSource[]>();
  for (const group of groups) {
    const ranked = mentors.slice().sort((a, b) => {
      const sa = scoreMatrix.get(`${group.groupId}:${a.mentorId}`)?.score ?? -Infinity;
      const sb = scoreMatrix.get(`${group.groupId}:${b.mentorId}`)?.score ?? -Infinity;
      return sb - sa;
    });
    groupPreferences.set(group.groupId, ranked);
  }

  let unmatched: GroupSource[] = [...groups];
  const maxIterations = groups.length * mentors.length + 1;
  let iterations = 0;

  while (unmatched.length > 0) {
    if (++iterations > maxIterations) break; // safety guard against infinite loop
    const nextRound: GroupSource[] = [];

    for (const group of unmatched) {
      const prefs = groupPreferences.get(group.groupId)!;
      const idx = nextIdx.get(group.groupId)!;

      if (idx >= prefs.length) {
        // Exhausted all available mentors — permanently unmatched
        continue;
      }

      const mentor = prefs[idx];
      nextIdx.set(group.groupId, idx + 1);

      const accepted = tentative.get(mentor.mentorId)!;
      const capacity = slots.get(mentor.mentorId)!;
      const incomingScore = scoreMatrix.get(
        `${group.groupId}:${mentor.mentorId}`,
      )!.score;

      if (accepted.size < capacity) {
        // Free slot: tentatively accept
        accepted.add(group.groupId);
        assignment.set(group.groupId, mentor.mentorId);
      } else {
        // Full: compare against the worst currently held group
        let worstId: number | null = null;
        let worstScore = Infinity;

        for (const heldId of accepted) {
          const s = scoreMatrix.get(`${heldId}:${mentor.mentorId}`)?.score ?? -Infinity;
          if (s < worstScore) {
            worstScore = s;
            worstId = heldId;
          }
        }

        if (worstId !== null && incomingScore > worstScore) {
          // Displace the worst held group
          accepted.delete(worstId);
          accepted.add(group.groupId);
          assignment.set(group.groupId, mentor.mentorId);
          assignment.delete(worstId);
          const displaced = groups.find((g) => g.groupId === worstId)!;
          nextRound.push(displaced);
        } else {
          // Incoming group rejected — try next mentor next round
          nextRound.push(group);
        }
      }
    }

    unmatched = nextRound;
  }

  return { assignment, tentative };
}

// ── Unmatched reason builders ─────────────────────────────────────────────────

function unmatchedReason(
  group: GroupSource,
  allMentors: MentorSource[],
  eligibleMentors: MentorSource[],
  mode: MatchMode,
): string {
  if (allMentors.length === 0) {
    return "No mentors are registered in the system.";
  }

  if (eligibleMentors.length === 0) {
    if (mode === "strict") {
      return `No mentors are available for track "${group.trackCode}" (strict mode).`;
    }
    return "No mentors with remaining capacity are available.";
  }

  // Eligible mentors exist but the group was still unmatched (all were full after Gale-Shapley)
  const sameTrackEligible = eligibleMentors.filter((m) =>
    isSameTrackEligible(m, group),
  );

  if (mode === "strict" && sameTrackEligible.length === 0) {
    return `No mentors are available for track "${group.trackCode}" (strict mode).`;
  }

  if (sameTrackEligible.length > 0) {
    return `All compatible mentors for track "${group.trackCode}" are fully assigned to higher-scoring groups.`;
  }

  return "All available mentors are fully assigned to higher-scoring groups.";
}

// ── EMPTY_BREAKDOWN ───────────────────────────────────────────────────────────

const EMPTY_BREAKDOWN: MentorScoreBreakdown = {
  baseScore: BASE_SCORE,
  trackPenalty: 0,
  interestBonus: 0,
  timezonePenalty: 0,
  capacityBonus: 0,
  objectiveScore: 0,
};

// ── Result builder ────────────────────────────────────────────────────────────

function buildResults(
  groups: GroupSource[],
  availableMentors: MentorSource[],
  scoreMatrix: Map<string, ScoreEntry>,
  assignment: Map<number, number>,
  tentative: Map<number, Set<number>>,
  eligibleMentorsByGroup: Map<number, MentorSource[]>,
  mode: MatchMode,
): MentorGroupRecommendation[] {
  return groups.map((group) => {
    const mentorId = assignment.get(group.groupId);

    if (mentorId === undefined) {
      const eligible = eligibleMentorsByGroup.get(group.groupId) ?? [];
      return {
        group,
        recommendedMentor: null,
        reason: unmatchedReason(group, availableMentors, eligible, mode),
        score: 0,
        scoreBreakdown: { ...EMPTY_BREAKDOWN },
      };
    }

    const mentor = availableMentors.find((m) => m.mentorId === mentorId)!;
    const { score, breakdown, reason } = scoreMatrix.get(
      `${group.groupId}:${mentorId}`,
    )!;

    const assignmentsThisRun = tentative.get(mentorId)?.size ?? 0;
    const remainingCapacity = Math.max(
      0,
      mentor.maxGroupCount - mentor.currentAcceptedCount - assignmentsThisRun,
    );

    return {
      group,
      recommendedMentor: {
        mentorId: mentor.mentorId,
        name: `${mentor.firstName} ${mentor.lastName}`.trim(),
        trackCode: mentor.trackCode,
        institution: mentor.institution,
        interests: mentor.interests,
        remainingCapacity,
      },
      reason,
      score,
      scoreBreakdown: breakdown,
    };
  });
}

// ── Public API ────────────────────────────────────────────────────────────────

export function matchMentors(
  groups: GroupSource[],
  mentors: MentorSource[],
  mode: MatchMode = "balanced",
): MentorGroupRecommendation[] {
  const availableMentors = mentors.filter(
    (m) => m.currentAcceptedCount < m.maxGroupCount,
  );

  if (groups.length === 0) return [];

  if (availableMentors.length === 0) {
    return groups.map((group) => ({
      group,
      recommendedMentor: null,
      reason: "No available mentors with remaining capacity.",
      score: 0,
      scoreBreakdown: { ...EMPTY_BREAKDOWN },
    }));
  }

  // ── Balanced: pre-filter poor pairs, then run Gale-Shapley on valid ones ──
  if (mode === "balanced") {
    const scoreMatrix = buildScoreMatrix(groups, availableMentors);

    // Only allow mentor-group pairs that have shared interests and an acceptable timezone gap.
    // This prevents displacing a good match in favour of a mentor that would later be nullified.
    const eligibleByGroup = new Map<number, MentorSource[]>(
      groups.map((g) => [
        g.groupId,
        availableMentors.filter((m) => {
          const entry = scoreMatrix.get(`${g.groupId}:${m.mentorId}`);
          if (!entry) return false;
          return (
            entry.breakdown.interestBonus > 0 &&
            entry.breakdown.timezonePenalty < TIMEZONE_MAX_PENALTY
          );
        }),
      ]),
    );

    const { assignment, tentative } = galeShapleyPerGroup(
      groups,
      availableMentors,
      scoreMatrix,
      eligibleByGroup,
    );
    return buildResults(groups, availableMentors, scoreMatrix, assignment, tentative, eligibleByGroup, mode);
  }

  // ── Strict: same-track / GLOBAL only ─────────────────────────────────────
  if (mode === "strict") {
    const eligibleByGroup = new Map<number, MentorSource[]>(
      groups.map((g) => [
        g.groupId,
        availableMentors.filter((m) => isSameTrackEligible(m, g)),
      ]),
    );

    // Collect the union of mentors that appear in at least one group's list
    const eligibleMentorIds = new Set(
      [...eligibleByGroup.values()].flatMap((ms) => ms.map((m) => m.mentorId)),
    );
    const eligibleMentors = availableMentors.filter((m) =>
      eligibleMentorIds.has(m.mentorId),
    );

    // Build score matrix only for eligible pairs
    const scoreMatrix = buildScoreMatrix(groups, eligibleMentors);

    // For each group, only propose to its eligible mentors
    // We achieve this by giving each group a custom preference list restricted to eligible mentors
    const perGroupMentors = new Map<number, MentorSource[]>(
      groups.map((g) => [g.groupId, eligibleByGroup.get(g.groupId)!]),
    );

    // Run Gale-Shapley using per-group eligible lists
    const { assignment, tentative } = galeShapleyPerGroup(
      groups,
      eligibleMentors,
      scoreMatrix,
      perGroupMentors,
    );

    return buildResults(groups, availableMentors, scoreMatrix, assignment, tentative, eligibleByGroup, mode);
  }

  // ── Coverage: phase 1 (same-track) → phase 2 (cross-track fallback) ──────
  // Phase 1: same-track / GLOBAL Gale-Shapley
  const phase1EligibleByGroup = new Map<number, MentorSource[]>(
    groups.map((g) => [
      g.groupId,
      availableMentors.filter((m) => isSameTrackEligible(m, g)),
    ]),
  );

  const phase1MentorsForMatrix = availableMentors.filter((m) =>
    groups.some((g) => isSameTrackEligible(m, g)),
  );

  const phase1ScoreMatrix = buildScoreMatrix(groups, phase1MentorsForMatrix);
  const phase1PerGroupMentors = phase1EligibleByGroup;

  const phase1 = galeShapleyPerGroup(
    groups,
    phase1MentorsForMatrix,
    phase1ScoreMatrix,
    phase1PerGroupMentors,
  );

  const unmatchedAfterPhase1 = groups.filter(
    (g) => !phase1.assignment.has(g.groupId),
  );

  if (unmatchedAfterPhase1.length === 0) {
    const eligibleByGroup = new Map(groups.map((g) => [g.groupId, availableMentors]));
    return buildResults(groups, availableMentors, phase1ScoreMatrix, phase1.assignment, phase1.tentative, eligibleByGroup, mode);
  }

  // Phase 2: remaining groups propose to cross-track mentors using remaining slots
  // Remaining slots = maxGroupCount - currentAcceptedCount - phase1 tentative assignments
  const phase2Slots = new Map<number, number>();
  for (const m of availableMentors) {
    const usedInPhase1 = phase1.tentative.get(m.mentorId)?.size ?? 0;
    const remaining = m.maxGroupCount - m.currentAcceptedCount - usedInPhase1;
    if (remaining > 0) {
      phase2Slots.set(m.mentorId, remaining);
    }
  }

  // Only mentors with remaining slots participate in phase 2
  const phase2Mentors = availableMentors.filter(
    (m) => (phase2Slots.get(m.mentorId) ?? 0) > 0,
  );

  // Phase 2 score matrix: cross-track only (already penalised by TRACK_MISMATCH_PENALTY in scoring)
  const phase2ScoreMatrix = buildScoreMatrix(unmatchedAfterPhase1, phase2Mentors);

  const phase2 = galeShapley(
    unmatchedAfterPhase1,
    phase2Mentors,
    phase2ScoreMatrix,
    phase2Slots,
  );

  // Merge assignments
  const mergedAssignment = new Map([...phase1.assignment, ...phase2.assignment]);

  // Merge tentative (phase2 mentors might overlap phase1)
  const mergedTentative = new Map<number, Set<number>>();
  for (const m of availableMentors) {
    const p1 = phase1.tentative.get(m.mentorId) ?? new Set<number>();
    const p2 = phase2.tentative.get(m.mentorId) ?? new Set<number>();
    mergedTentative.set(m.mentorId, new Set([...p1, ...p2]));
  }

  // Merged score matrix for result building
  const mergedScoreMatrix = new Map([...phase1ScoreMatrix, ...phase2ScoreMatrix]);

  // Eligible-by-group for unmatched reason: phase1 eligible for phase1 groups; all for phase2 groups
  const coverageEligibleByGroup = new Map<number, MentorSource[]>(
    groups.map((g) => {
      const wasUnmatchedAfterP1 = unmatchedAfterPhase1.some((ug) => ug.groupId === g.groupId);
      return [g.groupId, wasUnmatchedAfterP1 ? phase2Mentors : phase1EligibleByGroup.get(g.groupId)!];
    }),
  );

  return buildResults(groups, availableMentors, mergedScoreMatrix, mergedAssignment, mergedTentative, coverageEligibleByGroup, mode);
}

// ── Gale-Shapley variant with per-group mentor eligibility ───────────────────
// Like galeShapley() but each group only proposes to its own eligible list.

function galeShapleyPerGroup(
  groups: GroupSource[],
  mentors: MentorSource[],
  scoreMatrix: Map<string, ScoreEntry>,
  perGroupMentors: Map<number, MentorSource[]>,
  slotsOverride?: Map<number, number>,
): GaleShapleyResult {
  const slots = slotsOverride ??
    new Map(mentors.map((m) => [m.mentorId, m.maxGroupCount - m.currentAcceptedCount]));

  const tentative = new Map<number, Set<number>>(
    mentors.map((m) => [m.mentorId, new Set()]),
  );
  const assignment = new Map<number, number>();
  const nextIdx = new Map<number, number>(groups.map((g) => [g.groupId, 0]));

  const groupPreferences = new Map<number, MentorSource[]>();
  for (const group of groups) {
    const eligible = perGroupMentors.get(group.groupId) ?? [];
    const ranked = eligible.slice().sort((a, b) => {
      const sa = scoreMatrix.get(`${group.groupId}:${a.mentorId}`)?.score ?? -Infinity;
      const sb = scoreMatrix.get(`${group.groupId}:${b.mentorId}`)?.score ?? -Infinity;
      return sb - sa;
    });
    groupPreferences.set(group.groupId, ranked);
  }

  let unmatched: GroupSource[] = [...groups];
  const maxIterationsPerGroup = groups.length * mentors.length + 1;
  let iterationsPerGroup = 0;

  while (unmatched.length > 0) {
    if (++iterationsPerGroup > maxIterationsPerGroup) break; // safety guard against infinite loop
    const nextRound: GroupSource[] = [];

    for (const group of unmatched) {
      const prefs = groupPreferences.get(group.groupId)!;
      const idx = nextIdx.get(group.groupId)!;

      if (idx >= prefs.length) continue;

      const mentor = prefs[idx];
      nextIdx.set(group.groupId, idx + 1);

      const accepted = tentative.get(mentor.mentorId)!;
      const capacity = slots.get(mentor.mentorId)!;
      const incomingScore = scoreMatrix.get(
        `${group.groupId}:${mentor.mentorId}`,
      )!.score;

      if (accepted.size < capacity) {
        accepted.add(group.groupId);
        assignment.set(group.groupId, mentor.mentorId);
      } else {
        let worstId: number | null = null;
        let worstScore = Infinity;

        for (const heldId of accepted) {
          const s = scoreMatrix.get(`${heldId}:${mentor.mentorId}`)?.score ?? -Infinity;
          if (s < worstScore) {
            worstScore = s;
            worstId = heldId;
          }
        }

        if (worstId !== null && incomingScore > worstScore) {
          accepted.delete(worstId);
          accepted.add(group.groupId);
          assignment.set(group.groupId, mentor.mentorId);
          assignment.delete(worstId);
          const displaced = groups.find((g) => g.groupId === worstId)!;
          nextRound.push(displaced);
        } else {
          nextRound.push(group);
        }
      }
    }

    unmatched = nextRound;
  }

  return { assignment, tentative };
}
