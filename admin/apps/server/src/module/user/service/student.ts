import {
  and,
  asc,
  eq,
  exists,
  ilike,
  inArray,
  isNull,
  notExists,
  or,
  sql,
} from "drizzle-orm";
import type { QueryStudentsInput } from "../schema.js";
import db from "@/lib/db.js";
import {
  areasOfInterest,
  groups,
  groupMembership,
  studentInterest,
  studentProfile,
  tracks,
  users,
} from "@/old/drizzle/schema.js";

type StudentListItem = {
  id: number;
  name: string;
  firstName: string;
  lastName: string;
  email: string;
  role: "student";
  track: string | null;
  isActive: boolean;
  accountStatus: string;
  invitedAt: string | null;
  activatedAt: string | null;
  basicInfo: {
    id: number;
    name: string;
    firstName: string;
    lastName: string;
    email: string;
    track: string | null;
    isActive: boolean;
    accountStatus: string;
  };
  studentInfo: {
    schoolName: string | null;
    yearLevel: number | null;
    joinPermissionReceived: boolean;
    joinPermissionResponseId: string | null;
  };
  groupInfo: {
    id: number;
    name: string;
    membershipId: number;
    membershipRole: string | null;
    joinedAt: string;
  } | null;
  groupId: string | null;
  groupName: string | null;
  interests: Array<{
    id: number;
    description: string;
  }>;
};

export async function queryStudents(params: QueryStudentsInput) {
  const { page, limit, search, age, track, interest, inGroup } = params;
  const offset = (page - 1) * limit;

  const conditions = [];

  if (search) {
    conditions.push(
      or(
        ilike(users.firstName, `%${search}%`),
        ilike(users.lastName, `%${search}%`),
        ilike(users.email, `%${search}%`),
      ),
    );
  }
  if (age) conditions.push(eq(studentProfile.yearLevel, age));
  if (track) conditions.push(eq(tracks.trackCode, track));

  if (interest) {
    const matchingInterest = db
      .select({ id: studentInterest.id })
      .from(studentInterest)
      .innerJoin(
        areasOfInterest,
        eq(areasOfInterest.id, studentInterest.interestId),
      )
      .where(
        and(
          eq(studentInterest.studentUserId, users.id),
          ilike(areasOfInterest.interestDesc, `%${interest}%`),
        ),
      );

    conditions.push(exists(matchingInterest));
  }

  const activeMembership = db
    .select({ id: groupMembership.id })
    .from(groupMembership)
    .where(
      and(eq(groupMembership.userId, users.id), isNull(groupMembership.leftAt)),
    );

  if (inGroup === "yes") {
    conditions.push(exists(activeMembership));
  } else if (inGroup === "no") {
    conditions.push(notExists(activeMembership));
  }

  const where = conditions.length > 0 ? and(...conditions) : undefined;

  const filteredBase = () =>
    db
      .select({ id: users.id })
      .from(users)
      .innerJoin(studentProfile, eq(studentProfile.userId, users.id))
      .leftJoin(tracks, eq(tracks.id, users.trackId));

  const countBase = db
    .select({ count: sql<number>`cast(count(distinct ${users.id}) as int)` })
    .from(users)
    .innerJoin(studentProfile, eq(studentProfile.userId, users.id))
    .leftJoin(tracks, eq(tracks.id, users.trackId))
    .$dynamic();

  const [pageRows, countResult] = await Promise.all([
    filteredBase()
      .where(where)
      .orderBy(asc(users.lastName), asc(users.firstName), asc(users.id))
      .limit(limit)
      .offset(offset),
    where ? countBase.where(where) : countBase,
  ]);

  const total = countResult[0]?.count ?? 0;
  const studentIds = pageRows.map((row) => row.id);

  const detailRows =
    studentIds.length === 0
      ? []
      : await db
          .select({
            id: users.id,
            firstName: users.firstName,
            lastName: users.lastName,
            email: users.email,
            isActive: users.isActive,
            accountStatus: users.accountStatus,
            invitedAt: users.invitedAt,
            activatedAt: users.activatedAt,
            track: tracks.trackCode,
            schoolName: studentProfile.schoolName,
            yearLevel: studentProfile.yearLevel,
            joinPermissionReceived: studentProfile.joinPermissionReceived,
            joinPermissionResponseId: studentProfile.joinPermissionResponseId,
            membershipId: groupMembership.id,
            groupId: groups.id,
            groupName: groups.groupName,
            membershipRole: groupMembership.membershipRole,
            joinedAt: groupMembership.joinedAt,
            interestId: areasOfInterest.id,
            interestDesc: areasOfInterest.interestDesc,
          })
          .from(users)
          .innerJoin(studentProfile, eq(studentProfile.userId, users.id))
          .leftJoin(tracks, eq(tracks.id, users.trackId))
          .leftJoin(
            groupMembership,
            and(
              eq(groupMembership.userId, users.id),
              isNull(groupMembership.leftAt),
            ),
          )
          .leftJoin(groups, eq(groups.id, groupMembership.groupId))
          .leftJoin(
            studentInterest,
            eq(studentInterest.studentUserId, users.id),
          )
          .leftJoin(
            areasOfInterest,
            eq(areasOfInterest.id, studentInterest.interestId),
          )
          .where(inArray(users.id, studentIds))
          .orderBy(asc(users.lastName), asc(users.firstName), asc(users.id));

  const itemsById = new Map<number, StudentListItem>();

  for (const row of detailRows) {
    const name = `${row.firstName} ${row.lastName}`.trim();
    let item = itemsById.get(row.id);

    if (!item) {
      item = {
        id: row.id,
        name,
        firstName: row.firstName,
        lastName: row.lastName,
        email: row.email,
        role: "student",
        track: row.track,
        isActive: row.isActive,
        accountStatus: row.accountStatus,
        invitedAt: row.invitedAt,
        activatedAt: row.activatedAt,
        basicInfo: {
          id: row.id,
          name,
          firstName: row.firstName,
          lastName: row.lastName,
          email: row.email,
          track: row.track,
          isActive: row.isActive,
          accountStatus: row.accountStatus,
        },
        studentInfo: {
          schoolName: row.schoolName,
          yearLevel: row.yearLevel,
          joinPermissionReceived: row.joinPermissionReceived,
          joinPermissionResponseId: row.joinPermissionResponseId,
        },
        groupInfo:
          row.groupId && row.membershipId && row.joinedAt
            ? {
                id: row.groupId,
                name: row.groupName ?? String(row.groupId),
                membershipId: row.membershipId,
                membershipRole: row.membershipRole,
                joinedAt: row.joinedAt,
              }
            : null,
        groupId: row.groupId ? String(row.groupId) : null,
        groupName: row.groupName,
        interests: [],
      };

      itemsById.set(row.id, item);
    }

    if (
      row.interestId &&
      row.interestDesc &&
      !item.interests.some((entry) => entry.id === row.interestId)
    ) {
      item.interests.push({
        id: row.interestId,
        description: row.interestDesc,
      });
    }
  }

  const items = studentIds.flatMap((id) => {
    const item = itemsById.get(id);
    return item ? [item] : [];
  });

  return {
    msg: "Students retrieved successfully",
    data: {
      items,
      total,
      page,
      limit,
      hasMore: offset + items.length < total,
    },
  };
}
