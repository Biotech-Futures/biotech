import {
  formatRecommendationInput,
  recommendGroupsByTrack,
  type GroupStudentSource,
  type IndividualStudentSource,
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
  userInAdminUser,
  users,
} from "@/db/schema/index.js";
import {
  demoIndividualStudents,
  demoMatchRecommendations,
  useMatchDemoData,
} from "./demo.js";
import type { ConfirmMatchAssignmentInput } from "./schema.js";

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

export async function matchStudent(uid: number) {
  if (useMatchDemoData()) {
    return demoMatchRecommendations;
  }

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
      ...individualStudents.map((student) => student.userId),
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
    individualStudents.map((student) => ({
      ...student,
      interests: interestsByUserId.get(student.userId) ?? [],
    }));

  const formattedGroupStudents: GroupStudentSource[] =
    groupStudentsWithTutors.map((student) => ({
      ...student,
      interests: interestsByUserId.get(student.userId) ?? [],
    }));

  const input = formatRecommendationInput(
    formattedGroupStudents,
    formattedIndividualStudents,
  );
  const recommendations = recommendGroupsByTrack(input);

  const systemAdminUser = await db
    .select({ userId: users.id, adminUserId: users.adminUserId })
    .from(users)
    .innerJoin(userInAdminUser, eq(users.adminUserId, userInAdminUser.id))
    .where(eq(users.id, uid))
    .limit(1)
    .then((rows) => rows[0]);

  if (systemAdminUser?.adminUserId) {
    const latestMatchRun = await db
      .select({ id: matchRun.id })
      .from(matchRun)
      .orderBy(desc(matchRun.id))
      .limit(1);

    await db.insert(matchRun).values({
      id: (latestMatchRun[0]?.id ?? 0) + 1,
      initiatedByUserId: systemAdminUser.userId,
      runType: "student-match",
      payload: input,
      result: recommendations,
      createdAt: new Date().toISOString(),
    });
  }

  return recommendations;
}

export async function getIndividualStudents() {
  if (useMatchDemoData()) {
    return demoIndividualStudents;
  }

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
  if (useMatchDemoData()) {
    return {
      assignedCount: input.assignments.length,
    };
  }

  const uniqueByStudent = new Map<number, number>();
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
          isNull(groupMembership.leftAt),
        ),
      );

    const latestMembership = await tx
      .select({ id: groupMembership.id })
      .from(groupMembership)
      .orderBy(desc(groupMembership.id))
      .limit(1);

    let nextId = (latestMembership[0]?.id ?? 0) + 1;
    const rows = assignments.map((item) => ({
      id: nextId++,
      groupId: item.groupId,
      userId: item.studentId,
      membershipRole: "student",
      joinedAt: now,
      leftAt: null as string | null,
    }));

    await tx.insert(groupMembership).values(rows);
  });

  return {
    assignedCount: assignments.length,
  };
}
