import {
  matchMentors,
  type GroupSource,
  type MentorSource,
} from "@/algorithm/tutor.js";
import db from "@/lib/db.js";
import { and, eq, inArray, isNull, notExists } from "drizzle-orm";
import {
  areasOfInterest,
  groupMembership,
  groups,
  matchRecommendation,
  matchRun,
  mentorInterest,
  mentorProfile,
  studentInterest,
  tracks,
  users,
} from "drizzle/schema.js";
import type { ConfirmMentorAssignmentInput } from "./schema.js";

// ─── helpers ────────────────────────────────────────────────────────────────

function groupInterestsByKey<K>(
  rows: { key: K; interest: string }[],
): Map<K, string[]> {
  const map = new Map<K, string[]>();
  for (const { key, interest } of rows) {
    const existing = map.get(key);
    if (existing) {
      existing.push(interest);
    } else {
      map.set(key, [interest]);
    }
  }
  return map;
}

// ─── matchMentor ────────────────────────────────────────────────────────────

export async function matchMentor() {
  // 1. Find groups that have no accepted mentor recommendation
  const groupsWithMembers = await db
    .select({
      groupId: groups.id,
      groupName: groups.groupName,
      groupTrackCode: tracks.trackCode,
    })
    .from(groups)
    .innerJoin(tracks, eq(tracks.id, groups.trackId))
    .where(
      and(
        isNull(groups.deletedAt),
        notExists(
          db
            .select({ id: matchRecommendation.id })
            .from(matchRecommendation)
            .where(
              and(
                eq(matchRecommendation.groupId, groups.id),
                eq(matchRecommendation.accepted, true),
              ),
            ),
        ),
      ),
    );

  if (groupsWithMembers.length === 0) {
    return [];
  }

  const groupIds = groupsWithMembers.map((g) => g.groupId);

  // 2. Collect student interests per group (union of all members)
  const memberInterestRows = await db
    .select({
      groupId: groupMembership.groupId,
      interest: areasOfInterest.interestDesc,
    })
    .from(groupMembership)
    .innerJoin(
      studentInterest,
      eq(studentInterest.studentUserId, groupMembership.userId),
    )
    .innerJoin(
      areasOfInterest,
      eq(areasOfInterest.id, studentInterest.interestId),
    )
    .where(
      and(
        inArray(groupMembership.groupId, groupIds),
        isNull(groupMembership.leftAt),
      ),
    );

  const interestsByGroupId = groupInterestsByKey(
    memberInterestRows.map((r) => ({ key: r.groupId, interest: r.interest })),
  );

  const memberCountRows = await db
    .select({ groupId: groupMembership.groupId })
    .from(groupMembership)
    .where(
      and(
        inArray(groupMembership.groupId, groupIds),
        isNull(groupMembership.leftAt),
      ),
    );

  const memberCountByGroupId = new Map<number, number>();
  for (const row of memberCountRows) {
    memberCountByGroupId.set(
      row.groupId,
      (memberCountByGroupId.get(row.groupId) ?? 0) + 1,
    );
  }

  const groupSources: GroupSource[] = groupsWithMembers.map((g) => ({
    groupId: g.groupId,
    groupName: g.groupName,
    trackCode: g.groupTrackCode,
    studentInterests: interestsByGroupId.get(g.groupId) ?? [],
    studentCount: memberCountByGroupId.get(g.groupId) ?? 0,
  }));

  // 3. Fetch active mentors with capacity
  const acceptedCountRows = await db
    .select({ mentorUserId: matchRecommendation.mentorUserId })
    .from(matchRecommendation)
    .where(eq(matchRecommendation.accepted, true));

  const acceptedCountByMentor = new Map<number, number>();
  for (const row of acceptedCountRows) {
    acceptedCountByMentor.set(
      row.mentorUserId,
      (acceptedCountByMentor.get(row.mentorUserId) ?? 0) + 1,
    );
  }

  const mentorRows = await db
    .select({
      mentorId: mentorProfile.userId,
      firstName: users.firstName,
      lastName: users.lastName,
      institution: mentorProfile.institution,
      maxGroupCount: mentorProfile.maxGroupCount,
      trackCode: tracks.trackCode,
    })
    .from(mentorProfile)
    .innerJoin(users, eq(users.id, mentorProfile.userId))
    .innerJoin(tracks, eq(tracks.id, users.trackId))
    .where(eq(users.isActive, true));

  const mentorIds = mentorRows.map((m) => m.mentorId);

  const mentorInterestRows =
    mentorIds.length === 0
      ? []
      : await db
          .select({
            key: mentorInterest.mentorUserId,
            interest: areasOfInterest.interestDesc,
          })
          .from(mentorInterest)
          .innerJoin(
            areasOfInterest,
            eq(areasOfInterest.id, mentorInterest.interestId),
          )
          .where(inArray(mentorInterest.mentorUserId, mentorIds));

  const interestsByMentorId = groupInterestsByKey(mentorInterestRows);

  const mentorSources: MentorSource[] = mentorRows.map((m) => ({
    mentorId: m.mentorId,
    firstName: m.firstName,
    lastName: m.lastName,
    institution: m.institution,
    trackCode: m.trackCode,
    interests: interestsByMentorId.get(m.mentorId) ?? [],
    maxGroupCount: m.maxGroupCount,
    currentAcceptedCount: acceptedCountByMentor.get(m.mentorId) ?? 0,
  }));

  // 4. Run algorithm
  const recommendations = matchMentors(groupSources, mentorSources);

  // 5. Create matchRun record + insert all recommendations into DB
  const systemUser = await db
    .select({ id: users.id })
    .from(users)
    .limit(1)
    .then((rows) => rows[0]);

  if (!systemUser) {
    return [];
  }

  const matchRunRows = await db
    .insert(matchRun)
    .values({
      initiatedByUserId: systemUser.id,
      runType: "mentor-match",
      createdAt: new Date().toISOString(),
    })
    .returning({ id: matchRun.id });

  const matchRunId = matchRunRows[0]!.id;

  // Insert recommendation rows (only for groups that got a mentor recommendation)
  const toInsert = recommendations
    .filter((r) => r.recommendedMentor !== null)
    .map((r) => ({
      matchRunId,
      groupId: r.group.groupId,
      mentorUserId: r.recommendedMentor!.mentorId,
      score: String(r.score),
      explanation: {
        reason: r.reason,
        scoreBreakdown: r.scoreBreakdown,
      } as unknown as Parameters<
        typeof db.insert
      >[0] extends never ? never : object,
      accepted: false,
    }));

  const insertedRows =
    toInsert.length === 0
      ? []
      : await db
          .insert(matchRecommendation)
          .values(
            toInsert.map((item) => ({
              matchRunId: item.matchRunId,
              groupId: item.groupId,
              mentorUserId: item.mentorUserId,
              score: item.score,
              explanation: item.explanation,
              accepted: false,
            })),
          )
          .returning({ id: matchRecommendation.id });

  // Attach DB recommendation id to results
  let insertedIdx = 0;
  return recommendations.map((r) => {
    if (r.recommendedMentor === null) {
      return { ...r, recommendationId: null };
    }
    const dbRow = insertedRows[insertedIdx++];
    return { ...r, recommendationId: dbRow?.id ?? null };
  });
}

// ─── getUnmatchedGroups ──────────────────────────────────────────────────────

export async function getUnmatchedGroups() {
  const unmatchedGroups = await db
    .select({
      groupId: groups.id,
      groupName: groups.groupName,
      trackCode: tracks.trackCode,
    })
    .from(groups)
    .innerJoin(tracks, eq(tracks.id, groups.trackId))
    .where(
      and(
        isNull(groups.deletedAt),
        notExists(
          db
            .select({ id: matchRecommendation.id })
            .from(matchRecommendation)
            .where(
              and(
                eq(matchRecommendation.groupId, groups.id),
                eq(matchRecommendation.accepted, true),
              ),
            ),
        ),
      ),
    );

  return unmatchedGroups;
}

// ─── confirmMentorAssignments ────────────────────────────────────────────────

export async function confirmMentorAssignments(
  input: ConfirmMentorAssignmentInput,
) {
  const recommendationIds = input.assignments.map((a) => a.recommendationId);

  await db
    .update(matchRecommendation)
    .set({ accepted: true })
    .where(inArray(matchRecommendation.id, recommendationIds));

  return { confirmedCount: recommendationIds.length };
}
