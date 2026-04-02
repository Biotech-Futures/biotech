import {
  formatRecommendationInput,
  recommendGroupsByTrack,
  type GroupStudentSource,
  type IndividualStudentSource,
} from "@/algorithm/student.js";
import db from "@/lib/db.js";
import { and, eq, inArray, isNull, notExists } from "drizzle-orm";
import {
  areasOfInterest,
  countries,
  countryStates,
  groupMembership,
  groups,
  studentInterest,
  studentProfile,
  tracks,
  users,
} from "drizzle/schema.js";

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

export async function matchStudent() {
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

  const userIds = [
    ...new Set([
      ...individualStudents.map((student) => student.userId),
      ...groupStudents.map((student) => student.userId),
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

  const formattedGroupStudents: GroupStudentSource[] = groupStudents.map(
    (student) => ({
      ...student,
      interests: interestsByUserId.get(student.userId) ?? [],
    }),
  );

  const input = formatRecommendationInput(
    formattedGroupStudents,
    formattedIndividualStudents,
  );

  return recommendGroupsByTrack(input);
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
