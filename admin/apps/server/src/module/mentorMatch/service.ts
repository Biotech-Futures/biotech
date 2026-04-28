import {
  matchMentors,
  type GroupSource,
  type MatchMode,
  type MentorSource,
} from "@/algorithm/mentor.js";
import db from "@/lib/db.js";
import { and, eq, inArray, isNull, notExists } from "drizzle-orm";
import {
  areasOfInterest,
  groupMembership,
  groups,
  matchRun,
  mentorProfile,
  userInterest,
  studentProfile,
  tracks,
  users,
} from "@/schema/index.js";
import type {
  ConfirmMentorAssignmentInput,
  ReplaceMentorInput,
} from "./schema.js";
import {
  demoGroups,
  demoMentors,
  initialDemoMatchedGroups,
  type DemoMatchedGroup,
} from "./demo.js";
import { create } from "domain";

// Mutable in-memory demo state for matched groups
let demoMatchedGroups: DemoMatchedGroup[] = [...initialDemoMatchedGroups];

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
  if (process.env.MATCH_USE_DEMO_DATA === "true") {
    const matchedGroupIds = new Set(demoMatchedGroups.map((g) => g.groupId));
    const unmatchedDemoGroups = demoGroups.filter(
      (g) => !matchedGroupIds.has(g.groupId),
    );
    return matchMentors(unmatchedDemoGroups, demoMentors, mode);
  }

  // 1. Find groups that have no mentor member
  const groupsWithoutMentor = await db
    .select({
      groupId: groups.id,
      groupName: groups.groupName,
      groupTrackCode: tracks.trackName,
    })
    .from(groups)
    .innerJoin(tracks, eq(tracks.id, groups.trackId))
    .where(
      and(
        isNull(groups.deletedAt),
        notExists(
          db
            .select({ one: groupMembership.id })
            .from(groupMembership)
            .innerJoin(
              mentorProfile,
              eq(mentorProfile.userId, groupMembership.userId),
            )
            .where(eq(groupMembership.groupId, groups.id)),
        ),
      ),
    );

  if (groupsWithoutMentor.length === 0) {
    return [];
  }

  const groupIds = groupsWithoutMentor.map((g) => g.groupId);

  // 2. Collect student interests per group
  const memberInterestRows = await db
    .select({
      groupId: groupMembership.groupId,
      interest: areasOfInterest.interestDesc,
    })
    .from(groupMembership)
    .innerJoin(
      studentProfile,
      eq(studentProfile.userId, groupMembership.userId),
    )
    .innerJoin(userInterest, eq(userInterest.userId, groupMembership.userId))
    .innerJoin(areasOfInterest, eq(areasOfInterest.id, userInterest.interestId))
    .where(inArray(groupMembership.groupId, groupIds));

  const interestsByGroupId = groupInterestsByKey(
    memberInterestRows.map((r) => ({ key: r.groupId, interest: r.interest })),
  );

  const memberCountRows = await db
    .select({ groupId: groupMembership.groupId })
    .from(groupMembership)
    .innerJoin(
      studentProfile,
      eq(studentProfile.userId, groupMembership.userId),
    )
    .where(inArray(groupMembership.groupId, groupIds));

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

  // 3. Fetch active mentors
  const acceptedCountRows = await db
    .select({ mentorUserId: groupMembership.userId })
    .from(groupMembership)
    .innerJoin(mentorProfile, eq(mentorProfile.userId, groupMembership.userId));

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
      maxGrpCnt: mentorProfile.maxGroupCount,
      trackCode: tracks.trackName,
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
            key: userInterest.userId,
            interest: areasOfInterest.interestDesc,
          })
          .from(userInterest)
          .innerJoin(
            areasOfInterest,
            eq(areasOfInterest.id, userInterest.interestId),
          )
          .where(inArray(userInterest.userId, mentorIds));

  const interestsByMentorId = groupInterestsByKey(mentorInterestRows);

  const mentorSources: MentorSource[] = mentorRows.map((m) => ({
    mentorId: m.mentorId,
    firstName: m.firstName,
    lastName: m.lastName,
    institution: m.institution,
    trackCode: m.trackCode,
    interests: interestsByMentorId.get(m.mentorId) ?? [],
    maxGroupCount: m.maxGrpCnt,
    currentAcceptedCount: acceptedCountByMentor.get(m.mentorId) ?? 0,
  }));

  // 4. Run algorithm
  const recommendations = matchMentors(groupSources, mentorSources, mode);

  // 5. Save matchRun record
  await db.insert(matchRun).values({
    adminUserId: adminUserId,
    runType: "mentor-match",
    payload: groupSources,
    result: recommendations,
    createdAt: new Date().toISOString(),
  });

  return recommendations;
}

// ─── getMentors ─────────────────────────────────────────────────────────────

export async function getMentors() {
  if (process.env.MATCH_USE_DEMO_DATA === "true") {
    return demoMentors.map((m) => ({
      mentorId: m.mentorId,
      name: `${m.firstName} ${m.lastName}`.trim(),
      trackCode: m.trackCode,
      institution: m.institution,
      interests: m.interests,
      maxGroupCount: m.maxGroupCount,
      currentAcceptedCount: m.currentAcceptedCount,
      remainingCapacity: m.maxGroupCount - m.currentAcceptedCount,
    }));
  }

  const acceptedCountRows = await db
    .select({ mentorUserId: groupMembership.userId })
    .from(groupMembership)
    .innerJoin(mentorProfile, eq(mentorProfile.userId, groupMembership.userId));

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
      maxGrpCnt: mentorProfile.maxGroupCount,
      trackCode: tracks.trackName,
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
            key: userInterest.userId,
            interest: areasOfInterest.interestDesc,
          })
          .from(userInterest)
          .innerJoin(
            areasOfInterest,
            eq(areasOfInterest.id, userInterest.interestId),
          )
          .where(inArray(userInterest.userId, mentorIds));

  const interestsByMentorId = groupInterestsByKey(mentorInterestRows);

  return mentorRows.map((m) => {
    const currentAcceptedCount = acceptedCountByMentor.get(m.mentorId) ?? 0;
    return {
      mentorId: m.mentorId,
      name: `${m.firstName} ${m.lastName}`.trim(),
      trackCode: m.trackCode,
      institution: m.institution,
      interests: interestsByMentorId.get(m.mentorId) ?? [],
      maxGroupCount: m.maxGrpCnt,
      currentAcceptedCount,
      remainingCapacity: m.maxGrpCnt - currentAcceptedCount,
    };
  });
}

// ─── getUnmatchedGroups ──────────────────────────────────────────────────────

export async function getUnmatchedGroups() {
  if (process.env.MATCH_USE_DEMO_DATA === "true") {
    const matchedGroupIds = new Set(demoMatchedGroups.map((g) => g.groupId));
    return demoGroups
      .filter((g) => !matchedGroupIds.has(g.groupId))
      .map((g) => ({
        groupId: g.groupId,
        groupName: g.groupName,
        trackCode: g.trackCode,
        studentInterests: g.studentInterests,
        studentCount: g.studentCount,
        students: g.students,
      }));
  }

  const unmatchedGroupsBase = await db
    .select({
      groupId: groups.id,
      groupName: groups.groupName,
      trackCode: tracks.trackName,
    })
    .from(groups)
    .innerJoin(tracks, eq(tracks.id, groups.trackId))
    .where(
      and(
        isNull(groups.deletedAt),
        notExists(
          db
            .select({ one: groupMembership.id })
            .from(groupMembership)
            .innerJoin(
              mentorProfile,
              eq(mentorProfile.userId, groupMembership.userId),
            )
            .where(eq(groupMembership.groupId, groups.id)),
        ),
      ),
    );

  if (unmatchedGroupsBase.length === 0) {
    return [];
  }

  const groupIds = unmatchedGroupsBase.map((g) => g.groupId);

  // Student interests keyed by both groupId (union) and userId (per-student)
  const memberInterestRows = await db
    .select({
      groupId: groupMembership.groupId,
      userId: groupMembership.userId,
      interest: areasOfInterest.interestDesc,
    })
    .from(groupMembership)
    .innerJoin(
      studentProfile,
      eq(studentProfile.userId, groupMembership.userId),
    )
    .innerJoin(userInterest, eq(userInterest.userId, groupMembership.userId))
    .innerJoin(areasOfInterest, eq(areasOfInterest.id, userInterest.interestId))
    .where(inArray(groupMembership.groupId, groupIds));

  const interestsByGroupId = new Map<number, string[]>();
  const interestsByUserId = new Map<number, string[]>();
  for (const row of memberInterestRows) {
    const gi = interestsByGroupId.get(row.groupId) ?? [];
    gi.push(row.interest);
    interestsByGroupId.set(row.groupId, gi);
    const ui = interestsByUserId.get(row.userId) ?? [];
    ui.push(row.interest);
    interestsByUserId.set(row.userId, ui);
  }

  // Student names
  const studentNameRows = await db
    .select({
      groupId: groupMembership.groupId,
      userId: users.id,
      firstName: users.firstName,
      lastName: users.lastName,
    })
    .from(groupMembership)
    .innerJoin(users, eq(users.id, groupMembership.userId))
    .innerJoin(
      studentProfile,
      eq(studentProfile.userId, groupMembership.userId),
    )
    .where(inArray(groupMembership.groupId, groupIds));

  const studentsByGroupId = new Map<
    number,
    Array<{ userId: number; name: string }>
  >();
  for (const row of studentNameRows) {
    const list = studentsByGroupId.get(row.groupId) ?? [];
    list.push({
      userId: row.userId,
      name: `${row.firstName} ${row.lastName}`.trim(),
    });
    studentsByGroupId.set(row.groupId, list);
  }

  return unmatchedGroupsBase.map((g) => {
    const groupStudents = studentsByGroupId.get(g.groupId) ?? [];
    return {
      groupId: g.groupId,
      groupName: g.groupName,
      trackCode: g.trackCode,
      studentInterests: interestsByGroupId.get(g.groupId) ?? [],
      studentCount: groupStudents.length,
      students: groupStudents.map((s) => ({
        name: s.name,
        interests: interestsByUserId.get(s.userId) ?? [],
      })),
    };
  });
}

// ─── getMatchedGroups ─────────────────────────────────────────────────────────

export async function getMatchedGroups() {
  if (process.env.MATCH_USE_DEMO_DATA === "true") {
    return demoMatchedGroups;
  }

  const rows = await db
    .select({
      membershipId: groupMembership.id,
      groupId: groups.id,
      groupName: groups.groupName,
      groupTrackId: groups.trackId,
      mentorId: users.id,
      mentorFirstName: users.firstName,
      mentorLastName: users.lastName,
      isActive: users.isActive,
      institution: mentorProfile.institution,
      mentorTrackId: users.trackId,
    })
    .from(groupMembership)
    .innerJoin(groups, eq(groups.id, groupMembership.groupId))
    .innerJoin(mentorProfile, eq(mentorProfile.userId, groupMembership.userId))
    .innerJoin(users, eq(users.id, groupMembership.userId))
    .where(isNull(groups.deletedAt));

  if (rows.length === 0) return [];

  const groupIds = rows.map((r) => r.groupId);

  const allTrackIds = [
    ...new Set([
      ...rows.map((r) => r.groupTrackId),
      ...rows
        .map((r) => r.mentorTrackId)
        .filter((id): id is number => id !== null),
    ]),
  ];

  const trackRows = await db
    .select({ id: tracks.id, trackName: tracks.trackName })
    .from(tracks)
    .where(inArray(tracks.id, allTrackIds));

  const trackNameById = new Map(trackRows.map((t) => [t.id, t.trackName]));

  // Student names per group
  const studentNameRows = await db
    .select({
      groupId: groupMembership.groupId,
      userId: users.id,
      firstName: users.firstName,
      lastName: users.lastName,
    })
    .from(groupMembership)
    .innerJoin(users, eq(users.id, groupMembership.userId))
    .innerJoin(
      studentProfile,
      eq(studentProfile.userId, groupMembership.userId),
    )
    .where(inArray(groupMembership.groupId, groupIds));

  // Student interests per group
  const memberInterestRows = await db
    .select({
      groupId: groupMembership.groupId,
      userId: groupMembership.userId,
      interest: areasOfInterest.interestDesc,
    })
    .from(groupMembership)
    .innerJoin(
      studentProfile,
      eq(studentProfile.userId, groupMembership.userId),
    )
    .innerJoin(userInterest, eq(userInterest.userId, groupMembership.userId))
    .innerJoin(areasOfInterest, eq(areasOfInterest.id, userInterest.interestId))
    .where(inArray(groupMembership.groupId, groupIds));

  const interestsByUserId = new Map<number, string[]>();
  for (const row of memberInterestRows) {
    const list = interestsByUserId.get(row.userId) ?? [];
    list.push(row.interest);
    interestsByUserId.set(row.userId, list);
  }

  const studentsByGroupId = new Map<
    number,
    Array<{ name: string; interests: string[] }>
  >();
  for (const row of studentNameRows) {
    const list = studentsByGroupId.get(row.groupId) ?? [];
    list.push({
      name: `${row.firstName} ${row.lastName}`.trim(),
      interests: interestsByUserId.get(row.userId) ?? [],
    });
    studentsByGroupId.set(row.groupId, list);
  }

  return rows.map((r) => {
    const students = studentsByGroupId.get(r.groupId) ?? [];
    return {
      membershipId: r.membershipId,
      groupId: r.groupId,
      groupName: r.groupName,
      trackCode: trackNameById.get(r.groupTrackId) ?? "",
      studentCount: students.length,
      students,
      mentor: {
        mentorId: r.mentorId,
        name: `${r.mentorFirstName} ${r.mentorLastName}`.trim(),
        isActive: r.isActive,
        trackCode:
          r.mentorTrackId !== null
            ? (trackNameById.get(r.mentorTrackId) ?? "")
            : "",
        institution: r.institution,
      },
    };
  });
}

// ─── replaceMentor ────────────────────────────────────────────────────────────

export async function replaceMentor(input: ReplaceMentorInput) {
  if (process.env.MATCH_USE_DEMO_DATA === "true") {
    const idx = demoMatchedGroups.findIndex(
      (g) => g.membershipId === input.membershipId,
    );
    if (idx === -1) return { replaced: 0 };
    const newMentor = demoMentors.find(
      (m) => m.mentorId === input.newMentorUserId,
    );
    if (!newMentor) return { replaced: 0 };
    demoMatchedGroups[idx] = {
      ...demoMatchedGroups[idx],
      mentor: {
        mentorId: newMentor.mentorId,
        name: `${newMentor.firstName} ${newMentor.lastName}`.trim(),
        isActive: true,
        trackCode: newMentor.trackCode,
        institution: newMentor.institution,
      },
    };
    return { replaced: 1 };
  }

  await db
    .delete(groupMembership)
    .where(
      and(
        eq(groupMembership.id, input.membershipId),
        eq(groupMembership.groupId, input.groupId),
      ),
    );

  await db.insert(groupMembership).values({
    groupId: input.groupId,
    userId: input.newMentorUserId,
    membershipRole: "mentor",
    joinedAt: new Date().toISOString(),
  });

  return { replaced: 1 };
}

// ─── bulkReplaceInactiveMentors ───────────────────────────────────────────────

export async function bulkReplaceInactiveMentors() {
  if (process.env.MATCH_USE_DEMO_DATA === "true") {
    const before = demoMatchedGroups.length;
    demoMatchedGroups = demoMatchedGroups.filter((g) => g.mentor.isActive);
    return { removedCount: before - demoMatchedGroups.length };
  }

  const inactive = await db
    .select({ id: groupMembership.id })
    .from(groupMembership)
    .innerJoin(mentorProfile, eq(mentorProfile.userId, groupMembership.userId))
    .innerJoin(users, eq(users.id, groupMembership.userId))
    .where(eq(users.isActive, false));

  if (inactive.length === 0) return { removedCount: 0 };

  await db.delete(groupMembership).where(
    inArray(
      groupMembership.id,
      inactive.map((m) => m.id),
    ),
  );

  return { removedCount: inactive.length };
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

  if (process.env.MATCH_USE_DEMO_DATA === "true") {
    const maxId = demoMatchedGroups.reduce(
      (max, g) => Math.max(max, g.membershipId),
      1000,
    );
    let nextMembershipId = maxId + 1;
    let confirmedCount = 0;
    for (const { groupId, mentorUserId } of assignments) {
      const group = demoGroups.find((g) => g.groupId === groupId);
      const mentor = demoMentors.find((m) => m.mentorId === mentorUserId);
      if (!group || !mentor) continue;
      demoMatchedGroups = demoMatchedGroups.filter(
        (g) => g.groupId !== groupId,
      );
      demoMatchedGroups.push({
        membershipId: nextMembershipId++,
        groupId: group.groupId,
        groupName: group.groupName,
        trackCode: group.trackCode,
        studentCount: group.studentCount,
        students: (group.students ?? []).map((s) => ({
          name: s.name,
          interests: s.interests,
        })),
        mentor: {
          mentorId: mentor.mentorId,
          name: `${mentor.firstName} ${mentor.lastName}`.trim(),
          isActive: true,
          trackCode: mentor.trackCode,
          institution: mentor.institution,
        },
      });
      confirmedCount++;
    }
    return { confirmedCount };
  }

  const groupIds = assignments.map((a) => a.groupId);

  // Hard-delete any existing mentor membership for these groups
  const existingMentorRows = await db
    .select({ id: groupMembership.id })
    .from(groupMembership)
    .innerJoin(mentorProfile, eq(mentorProfile.userId, groupMembership.userId))
    .where(inArray(groupMembership.groupId, groupIds));

  if (existingMentorRows.length > 0) {
    await db.delete(groupMembership).where(
      inArray(
        groupMembership.id,
        existingMentorRows.map((r) => r.id),
      ),
    );
  }

  await db.insert(groupMembership).values(
    assignments.map((item) => ({
      groupId: item.groupId,
      userId: item.mentorUserId,
      membershipRole: "mentor",
      joinedAt: new Date().toISOString(),
    })),
  );

  return { confirmedCount: assignments.length };
}

// ─── unassignMentors ──────────────────────────────────────────────────────────

export async function unassignMentors(groupIds: number[]) {
  const mentorRows = await db
    .select({ id: groupMembership.id })
    .from(groupMembership)
    .innerJoin(mentorProfile, eq(mentorProfile.userId, groupMembership.userId))
    .where(inArray(groupMembership.groupId, groupIds));

  if (mentorRows.length === 0) return { unassignedCount: 0 };

  await db.delete(groupMembership).where(
    inArray(
      groupMembership.id,
      mentorRows.map((r) => r.id),
    ),
  );

  return { unassignedCount: mentorRows.length };
}
