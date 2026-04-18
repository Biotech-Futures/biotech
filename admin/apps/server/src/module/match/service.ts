import {
  buildGroups,
  formatRecommendationInput,
  recommendGroupsByTrack,
  type GroupStudentSource,
  type IndividualStudentSource,
  type MatchResult,
  type StudentInput,
  type StudentGroupRecommendation,
} from "@/algorithm/student.js";
import db from "@/lib/db.js";
import { and, desc, eq, inArray, isNull, notExists } from "drizzle-orm";
import {
  areasOfInterest,
  countries,
  countryStates,
  groupMembership,
  groups,
  matchRun,
  mentorProfile,
  studentInterest,
  studentProfile,
  tracks,
  users,
} from "@/drizzle/schema.js";

import type { ConfirmMatchAssignmentInput } from "./schema.js";

const DEFAULT_GROUP_MAX_SIZE = 5;

type MatchGroupSummary = {
  id: string | number;
  groupName: string;
  trackId: string | number;
  maxSize: number;
  tutor: {
    id: string | number;
    name: string;
  } | null;
  groupStudent: Array<{
    id: string | number;
    name: string;
    trackId?: string | number;
    country?: string;
    yearLevel?: number;
    interests?: string[];
  }>;
  studentCount: number;
  availableSeats: number;
};

type MatchStudentResult = {
  recommendations: StudentGroupRecommendation[];
  notFullGroups: MatchGroupSummary[];
};

type InterestRow = {
  userId: number;
  interestDesc: string;
};

function mapInterestsByUserId(rows: InterestRow[]): Map<number, string[]> {
  const interestsByUserId = new Map<number, string[]>();

  for (const row of rows) {
    const existing = interestsByUserId.get(row.userId);
    if (existing) {
      existing.push(row.interestDesc);
    } else {
      interestsByUserId.set(row.userId, [row.interestDesc]);
    }
  }

  return interestsByUserId;
}

function buildFormRecommendations(
  students: StudentInput[],
  groupedResult: MatchResult,
): {
  recommendations: StudentGroupRecommendation[];
  objectiveByStudentId: Map<string, number>;
} {
  const objectiveByStudentId = new Map<string, number>();
  const scoreByStudentId = new Map(
    groupedResult.studentScores.map(
      (item) => [String(item.studentId), item] as const,
    ),
  );
  const unmatchedByStudentId = new Map(
    groupedResult.unmatchedStudentReasons.map(
      (item) => [String(item.studentId), item] as const,
    ),
  );
  const studentById = new Map(
    students.map((student) => [String(student.id), student] as const),
  );
  const groupByStudentId = new Map<
    string,
    (typeof groupedResult.groups)[number]
  >();

  for (const group of groupedResult.groups) {
    for (const studentId of group.studentIds) {
      groupByStudentId.set(String(studentId), group);
      objectiveByStudentId.set(
        String(studentId),
        group.scoreBreakdown.objectiveScore,
      );
    }
  }

  for (const student of students) {
    const sid = String(student.id);
    if (!objectiveByStudentId.has(sid)) {
      objectiveByStudentId.set(sid, 0);
    }
  }

  const recommendations = students
    .map((student) => {
      const sid = String(student.id);
      const matchedGroup = groupByStudentId.get(sid);

      if (!matchedGroup) {
        const unmatched = unmatchedByStudentId.get(sid);
        return {
          student,
          recommendGroup: null,
          reason:
            unmatched?.reason ??
            "No valid 2-5 member score-based group found for this student.",
          score: 0,
          scoreBreakdown: {
            baseScore: 100,
            yearPenalty: 0,
            countryPenalty: 0,
            timezonePenalty: 0,
            sizeBonus: 0,
            totalPenalty: 100,
            objectiveScore: 0,
          },
        };
      }

      const studentScore = scoreByStudentId.get(sid);
      const virtualGroupId = `new-${matchedGroup.track}-${matchedGroup.studentIds.join("-")}`;

      return {
        student,
        recommendGroup: {
          id: virtualGroupId,
          groupName: `Suggested ${matchedGroup.track} Group`,
          trackId: matchedGroup.track,
          maxSize: 5,
          tutor: null,
          groupStudent: matchedGroup.studentIds
            .map((memberId) => studentById.get(String(memberId)))
            .filter((candidate): candidate is StudentInput =>
              Boolean(candidate),
            )
            .map((candidate) => ({
              id: candidate.id,
              name: candidate.name,
              trackId: candidate.trackId,
              country: candidate.country,
              yearLevel: candidate.yearLevel,
              interests: candidate.interests,
            })),
        },
        reason:
          "Assigned to highest score-based formed group considering interests, track, and compatibility.",
        score: studentScore?.score ?? matchedGroup.groupScore,
        scoreBreakdown: {
          baseScore: studentScore?.scoreBreakdown.baseScore ?? 100,
          yearPenalty: studentScore?.scoreBreakdown.yearPenalty ?? 0,
          countryPenalty: studentScore?.scoreBreakdown.countryPenalty ?? 0,
          timezonePenalty: studentScore?.scoreBreakdown.timezonePenalty ?? 0,
          sizeBonus: matchedGroup.scoreBreakdown.sizeBonus,
          totalPenalty: studentScore?.scoreBreakdown.totalPenalty ?? 100,
          objectiveScore: matchedGroup.scoreBreakdown.objectiveScore,
        },
      };
    })
    .sort((a, b) => String(a.student.id).localeCompare(String(b.student.id)));

  return {
    recommendations,
    objectiveByStudentId,
  };
}

export async function matchStudent(uid: string) {
  const activeMembershipSubquery = db
    .select({ userId: groupMembership.userId })
    .from(groupMembership)
    .where(
      and(eq(groupMembership.userId, users.id), isNull(groupMembership.leftAt)),
    );

  const standaloneStudents = await db
    .select({
      userId: users.id,
      firstName: users.firstName,
      lastName: users.lastName,
      trackId: users.trackId,
      trackCode: tracks.trackCode,
      yearLevel: studentProfile.yearLevel,
      countryName: countries.countryName,
    })
    .from(studentProfile)
    .innerJoin(users, eq(users.id, studentProfile.userId))
    .innerJoin(tracks, eq(tracks.id, users.trackId))
    .innerJoin(countryStates, eq(countryStates.id, tracks.stateId))
    .innerJoin(countries, eq(countries.id, countryStates.countryId))
    .where(notExists(activeMembershipSubquery));

  const groupMembershipRows = await db
    .select({
      groupId: groups.id,
      userId: users.id,
      firstName: users.firstName,
      lastName: users.lastName,
      trackId: users.trackId,
      trackCode: tracks.trackCode,
      yearLevel: studentProfile.yearLevel,
      countryName: countries.countryName,
    })
    .from(groupMembership)
    .innerJoin(groups, eq(groups.id, groupMembership.groupId))
    .innerJoin(users, eq(users.id, groupMembership.userId))
    .innerJoin(studentProfile, eq(studentProfile.userId, users.id))
    .innerJoin(tracks, eq(tracks.id, users.trackId))
    .innerJoin(countryStates, eq(countryStates.id, tracks.stateId))
    .innerJoin(countries, eq(countries.id, countryStates.countryId))
    .where(isNull(groupMembership.leftAt));

  const groupIds = [
    ...new Set(groupMembershipRows.map((student) => student.groupId)),
  ];

  const groupMetaRows =
    groupIds.length === 0
      ? []
      : await db
          .select({
            groupId: groups.id,
            groupName: groups.groupName,
            groupTrackId: groups.trackId,
            groupTrackCode: tracks.trackCode,
          })
          .from(groups)
          .innerJoin(tracks, eq(tracks.id, groups.trackId))
          .where(inArray(groups.id, groupIds));

  const groupMetaById = new Map(
    groupMetaRows.map((group) => [group.groupId, group] as const),
  );

  const groupStudents = groupMembershipRows.flatMap((student) => {
    const groupMeta = groupMetaById.get(student.groupId);
    if (!groupMeta) {
      return [];
    }

    return [
      {
        ...student,
        groupName: groupMeta.groupName,
        groupTrackId: groupMeta.groupTrackId,
        groupTrackCode: groupMeta.groupTrackCode,
      },
    ];
  });

  const groupMentorRows =
    groupIds.length === 0
      ? []
      : await db
          .select({
            groupId: groups.id,
            tutorUserId: users.id,
            tutorFirstName: users.firstName,
            tutorLastName: users.lastName,
          })
          .from(groupMembership)
          .innerJoin(groups, eq(groups.id, groupMembership.groupId))
          .innerJoin(
            mentorProfile,
            eq(mentorProfile.userId, groupMembership.userId),
          )
          .innerJoin(users, eq(users.id, mentorProfile.userId))
          .where(
            and(inArray(groups.id, groupIds), isNull(groupMembership.leftAt)),
          );

  const tutorByGroupId = new Map<
    number,
    { tutorUserId: number; tutorName: string }
  >();
  for (const row of groupMentorRows) {
    if (tutorByGroupId.has(row.groupId)) {
      continue;
    }

    tutorByGroupId.set(row.groupId, {
      tutorUserId: row.tutorUserId,
      tutorName: `${row.tutorFirstName} ${row.tutorLastName}`.trim(),
    });
  }

  const groupStudentsWithTutors = groupStudents.map((student) => {
    const tutor = tutorByGroupId.get(student.groupId);
    return {
      ...student,
      groupTutorId: tutor?.tutorUserId,
      groupTutorName: tutor?.tutorName,
    };
  });

  const userIds = [
    ...new Set([
      ...standaloneStudents.map((student) => student.userId),
      ...groupStudentsWithTutors.map((student) => student.userId),
    ]),
  ];

  const interestRows =
    userIds.length === 0
      ? []
      : await db
          .select({
            userId: studentInterest.studentUserId,
            interestDesc: areasOfInterest.interestDesc,
          })
          .from(studentInterest)
          .innerJoin(
            areasOfInterest,
            eq(areasOfInterest.id, studentInterest.interestId),
          )
          .where(inArray(studentInterest.studentUserId, userIds));

  const interestsByUserId = mapInterestsByUserId(interestRows);

  const formattedIndividualStudents: IndividualStudentSource[] =
    standaloneStudents.map((student) => ({
      ...student,
      interests: interestsByUserId.get(student.userId) ?? [],
    }));

  const formattedGroupStudents: GroupStudentSource[] =
    groupStudentsWithTutors.map((student) => ({
      ...student,
      interests: interestsByUserId.get(student.userId) ?? [],
    }));

  let recommendations: StudentGroupRecommendation[];
  let payload: unknown;

  const ungroupedStudents: StudentInput[] = formattedIndividualStudents
    .filter(
      (
        student,
      ): student is IndividualStudentSource & { userId: string | number } =>
        student.userId !== undefined,
    )
    .map((student) => ({
      id: student.userId,
      name: `${student.firstName ?? ""} ${student.lastName ?? ""}`.trim(),
      trackId: student.trackCode ?? student.trackId ?? undefined,
      country: student.countryName ?? undefined,
      yearLevel: student.yearLevel ?? undefined,
      interests:
        typeof student.userId === "number"
          ? (interestsByUserId.get(student.userId) ?? [])
          : [],
    }));

  const joinInput = formatRecommendationInput(
    formattedGroupStudents,
    formattedIndividualStudents,
  );
  const joinRecommendations = recommendGroupsByTrack(joinInput);

  const baselineForm = buildGroups(ungroupedStudents);
  const baselineFormRecommendations = buildFormRecommendations(
    ungroupedStudents,
    baselineForm,
  );

  const availableSeatsByGroupId = new Map<string, number>();
  for (const recommendation of joinRecommendations) {
    const group = recommendation.recommendGroup;
    if (!group) {
      continue;
    }

    const groupKey = String(group.id);
    if (availableSeatsByGroupId.has(groupKey)) {
      continue;
    }

    const maxSize = group.maxSize ?? 5;
    const existingCount = group.groupStudent.length;
    availableSeatsByGroupId.set(groupKey, Math.max(0, maxSize - existingCount));
  }

  const joinCandidates = joinRecommendations
    .filter(
      (
        recommendation,
      ): recommendation is StudentGroupRecommendation & {
        recommendGroup: NonNullable<
          StudentGroupRecommendation["recommendGroup"]
        >;
      } => recommendation.recommendGroup !== null,
    )
    .map((recommendation) => {
      const sid = String(recommendation.student.id);
      const joinObjective = recommendation.scoreBreakdown.objectiveScore;
      const formObjective =
        baselineFormRecommendations.objectiveByStudentId.get(sid) ?? 0;

      return {
        recommendation,
        studentId: sid,
        groupId: String(recommendation.recommendGroup.id),
        joinObjective,
        formObjective,
        delta: joinObjective - formObjective,
      };
    })
    .sort((a, b) => {
      if (b.delta !== a.delta) {
        return b.delta - a.delta;
      }
      if (b.joinObjective !== a.joinObjective) {
        return b.joinObjective - a.joinObjective;
      }
      return a.studentId.localeCompare(b.studentId);
    });

  const selectedJoinStudentIds = new Set<string>();
  for (const candidate of joinCandidates) {
    if (candidate.delta <= 0) {
      continue;
    }

    if (selectedJoinStudentIds.has(candidate.studentId)) {
      continue;
    }

    const remainingSeats = availableSeatsByGroupId.get(candidate.groupId) ?? 0;
    if (remainingSeats <= 0) {
      continue;
    }

    selectedJoinStudentIds.add(candidate.studentId);
    availableSeatsByGroupId.set(candidate.groupId, remainingSeats - 1);
  }

  const formPool = ungroupedStudents.filter(
    (student) => !selectedJoinStudentIds.has(String(student.id)),
  );
  const finalForm = buildGroups(formPool);
  const finalFormRecommendations = buildFormRecommendations(
    formPool,
    finalForm,
  );

  const selectedJoinRecommendations = joinCandidates
    .filter((candidate) => selectedJoinStudentIds.has(candidate.studentId))
    .map((candidate) => candidate.recommendation);

  recommendations = [
    ...selectedJoinRecommendations,
    ...finalFormRecommendations.recommendations,
  ].sort((a, b) => String(a.student.id).localeCompare(String(b.student.id)));

  payload = {
    strategy: "hybrid-join-or-form",
    studentCount: ungroupedStudents.length,
    joinInput,
    baselineForm,
    finalForm,
    selectedJoinStudentIds: [...selectedJoinStudentIds],
  };

  await db.insert(matchRun).values({
    id: Math.floor(Math.random() * 1000000),
    adminUserId: uid,
    runType: "student-match",
    payload,
    result: recommendations,
    createdAt: new Date().toISOString(),
  });

  const allGroups = await db
    .select({
      groupId: groups.id,
      groupName: groups.groupName,
      trackId: groups.trackId,
      trackCode: tracks.trackCode,
    })
    .from(groups)
    .innerJoin(tracks, eq(tracks.id, groups.trackId))
    .where(isNull(groups.deletedAt));

  const allGroupIds = allGroups.map((group) => group.groupId);

  const activeStudentRows =
    allGroupIds.length === 0
      ? []
      : await db
          .select({
            groupId: groupMembership.groupId,
            userId: users.id,
            firstName: users.firstName,
            lastName: users.lastName,
            trackCode: tracks.trackCode,
            yearLevel: studentProfile.yearLevel,
            countryName: countries.countryName,
          })
          .from(groupMembership)
          .innerJoin(users, eq(users.id, groupMembership.userId))
          .innerJoin(studentProfile, eq(studentProfile.userId, users.id))
          .innerJoin(tracks, eq(tracks.id, users.trackId))
          .innerJoin(countryStates, eq(countryStates.id, tracks.stateId))
          .innerJoin(countries, eq(countries.id, countryStates.countryId))
          .where(
            and(
              inArray(groupMembership.groupId, allGroupIds),
              isNull(groupMembership.leftAt),
            ),
          );

  const allStudentIds = [
    ...new Set(activeStudentRows.map((student) => student.userId)),
  ];

  const activeStudentInterestRows =
    allStudentIds.length === 0
      ? []
      : await db
          .select({
            userId: studentInterest.studentUserId,
            interestDesc: areasOfInterest.interestDesc,
          })
          .from(studentInterest)
          .innerJoin(
            areasOfInterest,
            eq(areasOfInterest.id, studentInterest.interestId),
          )
          .where(inArray(studentInterest.studentUserId, allStudentIds));

  const studentInterestsByUserId = mapInterestsByUserId(
    activeStudentInterestRows,
  );

  const activeTutorRows =
    allGroupIds.length === 0
      ? []
      : await db
          .select({
            groupId: groups.id,
            tutorUserId: users.id,
            tutorFirstName: users.firstName,
            tutorLastName: users.lastName,
          })
          .from(groupMembership)
          .innerJoin(groups, eq(groups.id, groupMembership.groupId))
          .innerJoin(
            mentorProfile,
            eq(mentorProfile.userId, groupMembership.userId),
          )
          .innerJoin(users, eq(users.id, mentorProfile.userId))
          .where(
            and(
              inArray(groups.id, allGroupIds),
              isNull(groupMembership.leftAt),
            ),
          );

  const allTutorByGroupId = new Map<
    number,
    {
      id: number;
      name: string;
    }
  >();

  for (const row of activeTutorRows) {
    if (allTutorByGroupId.has(row.groupId)) {
      continue;
    }

    allTutorByGroupId.set(row.groupId, {
      id: row.tutorUserId,
      name: `${row.tutorFirstName} ${row.tutorLastName}`.trim(),
    });
  }

  const studentsByGroupId = new Map<
    number,
    MatchGroupSummary["groupStudent"]
  >();
  for (const row of activeStudentRows) {
    const existing = studentsByGroupId.get(row.groupId) ?? [];
    existing.push({
      id: row.userId,
      name: `${row.firstName ?? ""} ${row.lastName ?? ""}`.trim(),
      trackId: row.trackCode,
      country: row.countryName ?? undefined,
      yearLevel: row.yearLevel ?? undefined,
      interests: studentInterestsByUserId.get(row.userId) ?? [],
    });
    studentsByGroupId.set(row.groupId, existing);
  }

  const notFullGroups: MatchGroupSummary[] = allGroups
    .map((group) => {
      const groupStudents = studentsByGroupId.get(group.groupId) ?? [];
      const studentCount = groupStudents.length;
      const availableSeats = Math.max(0, DEFAULT_GROUP_MAX_SIZE - studentCount);

      return {
        id: group.groupId,
        groupName: group.groupName,
        trackId: group.trackCode ?? group.trackId,
        maxSize: DEFAULT_GROUP_MAX_SIZE,
        tutor: allTutorByGroupId.get(group.groupId) ?? null,
        groupStudent: groupStudents,
        studentCount,
        availableSeats,
      };
    })
    .filter((group) => group.availableSeats > 0)
    .sort((a, b) => String(a.id).localeCompare(String(b.id)));

  return {
    recommendations,
    notFullGroups,
  } satisfies MatchStudentResult;
}

export async function getIndividualStudents() {
  const activeMembershipSubquery = db
    .select({ userId: groupMembership.userId })
    .from(groupMembership)
    .where(
      and(eq(groupMembership.userId, users.id), isNull(groupMembership.leftAt)),
    );

  const individualStudents = await db
    .select({
      userId: users.id,
      firstName: users.firstName,
      lastName: users.lastName,
      trackId: users.trackId,
      trackCode: tracks.trackCode,
      yearLevel: studentProfile.yearLevel,
      countryName: countries.countryName,
    })
    .from(studentProfile)
    .innerJoin(users, eq(users.id, studentProfile.userId))
    .innerJoin(tracks, eq(tracks.id, users.trackId))
    .innerJoin(countryStates, eq(countryStates.id, tracks.stateId))
    .innerJoin(countries, eq(countries.id, countryStates.countryId))
    .where(notExists(activeMembershipSubquery));

  return individualStudents;
}

export async function confirmStudentAssignments(
  input: ConfirmMatchAssignmentInput,
) {
  const uniqueByStudent = new Map<number, number | string>();
  for (const item of input.assignments) {
    uniqueByStudent.set(item.studentId, item.groupId);
  }

  const assignments = Array.from(uniqueByStudent.entries()).map(
    ([studentId, groupId]) => ({
      studentId,
      groupId,
    }),
  );

  if (assignments.length === 0) {
    return { assignedCount: 0 };
  }

  const studentIds = assignments.map((item) => item.studentId);
  const now = new Date().toISOString();

  await db.transaction(async (tx) => {
    await tx
      .update(groupMembership)
      .set({ leftAt: now })
      .where(
        and(
          inArray(groupMembership.userId, studentIds),
          eq(groupMembership.membershipRole, "student"),
          isNull(groupMembership.leftAt),
        ),
      );

    let resolvedAssignments = assignments.map((item) => ({
      studentId: item.studentId,
      groupId: item.groupId,
    }));

    if (assignments.some((item) => typeof item.groupId === "string")) {
      const syntheticGroups = new Map<string, number[]>();
      for (const item of assignments) {
        if (
          typeof item.groupId !== "string" ||
          !item.groupId.startsWith("new-")
        ) {
          continue;
        }

        const studentList = syntheticGroups.get(item.groupId);
        if (studentList) {
          studentList.push(item.studentId);
        } else {
          syntheticGroups.set(item.groupId, [item.studentId]);
        }
      }

      const usersForAssignments =
        studentIds.length === 0
          ? []
          : await tx
              .select({ id: users.id, trackId: users.trackId })
              .from(users)
              .where(inArray(users.id, studentIds));

      const trackByStudentId = new Map(
        usersForAssignments.map((row) => [row.id, row.trackId] as const),
      );

      const latestGroup = await tx
        .select({ id: groups.id })
        .from(groups)
        .orderBy(desc(groups.id))
        .limit(1);

      let nextGroupId = (latestGroup[0]?.id ?? 0) + 1;
      const createdGroupIdBySyntheticId = new Map<string, number>();
      const newGroupRows: Array<{
        id: number;
        groupName: string;
        trackId: number;
        createdAt: string;
        deletedAt: null;
      }> = [];

      for (const [syntheticId, members] of syntheticGroups) {
        const firstTrack = members
          .map((studentId) => trackByStudentId.get(studentId))
          .find((trackId): trackId is number => trackId !== undefined);

        if (firstTrack === undefined) {
          continue;
        }

        const groupId = nextGroupId++;
        createdGroupIdBySyntheticId.set(syntheticId, groupId);
        newGroupRows.push({
          id: groupId,
          groupName: `Auto Group ${groupId}`,
          trackId: firstTrack,
          createdAt: now,
          deletedAt: null,
        });
      }

      if (newGroupRows.length > 0) {
        await tx.insert(groups).values(newGroupRows);
      }

      resolvedAssignments = assignments
        .map((item) => {
          if (typeof item.groupId === "number") {
            return item;
          }

          const mappedGroupId = createdGroupIdBySyntheticId.get(item.groupId);
          if (mappedGroupId === undefined) {
            return null;
          }

          return {
            studentId: item.studentId,
            groupId: mappedGroupId,
          };
        })
        .filter(
          (item): item is { studentId: number; groupId: number } =>
            item !== null,
        );
    }

    const latestMembership = await tx
      .select({ id: groupMembership.id })
      .from(groupMembership)
      .orderBy(desc(groupMembership.id))
      .limit(1);

    let nextId = (latestMembership[0]?.id ?? 0) + 1;
    const rows = resolvedAssignments
      .filter(
        (item): item is { studentId: number; groupId: number } =>
          typeof item.groupId === "number",
      )
      .map((item) => ({
        id: nextId++,
        groupId: item.groupId,
        userId: item.studentId,
        membershipRole: "student",
        joinedAt: now,
        leftAt: null as string | null,
      }));

    if (rows.length > 0) {
      await tx.insert(groupMembership).values(rows);
    }
  });

  return {
    assignedCount: assignments.length,
  };
}
