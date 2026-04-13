import {
  matchMentors,
  type GroupSource,
  type MatchMode,
  type MentorSource,
} from "@/algorithm/mentor.js";
import db from "@/lib/db.js";
import { and, desc, eq, inArray, isNull, notExists } from "drizzle-orm";
import {
  areasOfInterest,
  groupMembership,
  groups,
  matchRun,
  mentorInterest,
  mentorProfile,
  studentInterest,
  tracks,
  users,
} from "@/drizzle/schema.js";
import type { ConfirmMentorAssignmentInput } from "./schema.js";
import { demoGroups, demoMentors } from "./demo.js";

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

export async function matchMentor(
  adminUserId: string,
  mode: MatchMode = "balanced",
) {
  // Demo mode: skip DB, run algorithm on static demo data
  if (process.env.MATCH_USE_DEMO_DATA === "true") {
    return matchMentors(demoGroups, demoMentors, mode);
  }

  // 1. Find groups that have no active mentor membership
  const groupsWithoutMentor = await db
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
            .select({ id: groupMembership.id })
            .from(groupMembership)
            .where(
              and(
                eq(groupMembership.groupId, groups.id),
                eq(groupMembership.membershipRole, "mentor"),
                isNull(groupMembership.leftAt),
              ),
            ),
        ),
      ),
    );

  if (groupsWithoutMentor.length === 0) {
    return [];
  }

  const groupIds = groupsWithoutMentor.map((g) => g.groupId);

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

  const groupSources: GroupSource[] = groupsWithoutMentor.map((g) => ({
    groupId: g.groupId,
    groupName: g.groupName,
    trackCode: g.groupTrackCode,
    studentInterests: interestsByGroupId.get(g.groupId) ?? [],
    studentCount: memberCountByGroupId.get(g.groupId) ?? 0,
  }));

  // 3. Fetch active mentors — count capacity from groupMembership
  const acceptedCountRows = await db
    .select({ mentorUserId: groupMembership.userId })
    .from(groupMembership)
    .where(
      and(
        eq(groupMembership.membershipRole, "mentor"),
        isNull(groupMembership.leftAt),
      ),
    );

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
  const recommendations = matchMentors(groupSources, mentorSources, mode);

  // 5. Save matchRun record
  const latestMatchRun = await db
    .select({ id: matchRun.id })
    .from(matchRun)
    .orderBy(desc(matchRun.id))
    .limit(1);

  await db.insert(matchRun).values({
    id: (latestMatchRun[0]?.id ?? 0) + 1,
    adminUserId: adminUserId,
    runType: "mentor-match",
    payload: groupSources,
    result: recommendations,
    createdAt: new Date().toISOString(),
  });

  return recommendations;
}

// ─── getUnmatchedGroups ──────────────────────────────────────────────────────

export async function getUnmatchedGroups() {
  // Demo mode: return all demo groups (none are matched in DB)
  if (process.env.MATCH_USE_DEMO_DATA === "true") {
    return demoGroups.map((g) => ({
      groupId: g.groupId,
      groupName: g.groupName,
      trackCode: g.trackCode,
    }));
  }

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
            .select({ id: groupMembership.id })
            .from(groupMembership)
            .where(
              and(
                eq(groupMembership.groupId, groups.id),
                eq(groupMembership.membershipRole, "mentor"),
                isNull(groupMembership.leftAt),
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
  // Deduplicate: one mentor assignment per group
  const uniqueByGroup = new Map<number, number>();
  for (const item of input.assignments) {
    uniqueByGroup.set(item.groupId, item.mentorUserId);
  }

  const assignments = Array.from(uniqueByGroup.entries()).map(
    ([groupId, mentorUserId]) => ({ groupId, mentorUserId }),
  );

  if (assignments.length === 0) {
    return { confirmedCount: 0 };
  }

  const now = new Date().toISOString();

  const latestMembership = await db
    .select({ id: groupMembership.id })
    .from(groupMembership)
    .orderBy(desc(groupMembership.id))
    .limit(1);

  let nextId = (latestMembership[0]?.id ?? 0) + 1;
  const rows = assignments.map((item) => ({
    id: nextId++,
    groupId: item.groupId,
    userId: item.mentorUserId,
    membershipRole: "mentor",
    joinedAt: now,
    leftAt: null as string | null,
  }));

  await db.insert(groupMembership).values(rows);

  return { confirmedCount: assignments.length };
}
