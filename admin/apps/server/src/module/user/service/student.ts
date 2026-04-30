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
  groupMembership,
  groups,
  userInterest,
  studentProfile,
  tracks,
  users,
} from "@/schema/index.js";

type StudentListItem = {
  id: number;
  firstName: string;
  lastName: string;
  email: string;
  role: "student";
  track: string | null;
  isActive: boolean;
  accountStatus: string;
  schoolName: string | null;
  yearLevel: number | null;
  hasJoinPermission: boolean;
  joinpermResponseId: string | null;
  groupId: number | null;
  groupName: string | null;
  interests: Array<{ id: number; description: string }>;
};

export async function queryStudents(params: QueryStudentsInput) {
  const { page, limit, search, yearLevel, track, interest, inGroup } = params;
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

  if (yearLevel) {
    conditions.push(eq(studentProfile.yearLvl, String(yearLevel)));
  }

  if (track) {
    conditions.push(eq(tracks.trackName, track));
  }

  if (interest) {
    const matchingInterest = db
      .select({ id: userInterest.id })
      .from(userInterest)
      .innerJoin(
        areasOfInterest,
        eq(areasOfInterest.id, userInterest.interestId),
      )
      .where(
        and(
          eq(userInterest.userId, users.id),
          ilike(areasOfInterest.interestDesc, `%${interest}%`),
        ),
      );
    conditions.push(exists(matchingInterest));
  }

  // inGroup filter: check existence in group_members table
  const membershipSubq = db
    .select({ id: groupMembership.id })
    .from(groupMembership)
    .where(eq(groupMembership.userId, users.id));

  if (inGroup === "yes") conditions.push(exists(membershipSubq));
  else if (inGroup === "no") conditions.push(notExists(membershipSubq));

  const where = conditions.length > 0 ? and(...conditions) : undefined;

  const baseQ = () =>
    db
      .select({ id: users.id })
      .from(users)
      .innerJoin(studentProfile, eq(studentProfile.userId, users.id))
      .leftJoin(tracks, eq(tracks.id, users.trackId))
      .$dynamic();

  const countQ = db
    .select({ count: sql<number>`cast(count(distinct ${users.id}) as int)` })
    .from(users)
    .innerJoin(studentProfile, eq(studentProfile.userId, users.id))
    .leftJoin(tracks, eq(tracks.id, users.trackId))
    .$dynamic();

  const [pageRows, countResult] = await Promise.all([
    (where ? baseQ().where(where) : baseQ())
      .orderBy(asc(users.lastName), asc(users.firstName), asc(users.id))
      .limit(limit)
      .offset(offset),
    where ? countQ.where(where) : countQ,
  ]);

  const total = countResult[0]?.count ?? 0;
  const studentIds = pageRows.map((row) => row.id);

  if (studentIds.length === 0) {
    return {
      msg: "Students retrieved successfully",
      data: { items: [], total, page, limit, hasMore: false },
    };
  }

  const detailRows = await db
    .select({
      id: users.id,
      firstName: users.firstName,
      lastName: users.lastName,
      email: users.email,
      isActive: users.isActive,
      track: tracks.trackName,
      schoolName: studentProfile.schoolName,
      yearLvl: studentProfile.yearLvl,
      hasJoinPermission: studentProfile.hasJoinPermission,
      joinpermResponseId: studentProfile.joinpermResponseId,
      groupId: groups.id,
      groupName: groups.groupName,
      interestId: areasOfInterest.id,
      interestDesc: areasOfInterest.interestDesc,
    })
    .from(users)
    .innerJoin(studentProfile, eq(studentProfile.userId, users.id))
    .leftJoin(tracks, eq(tracks.id, users.trackId))
    .leftJoin(groupMembership, eq(groupMembership.userId, users.id))
    .leftJoin(
      groups,
      and(eq(groups.id, groupMembership.groupId), isNull(groups.deletedAt)),
    )
    .leftJoin(userInterest, eq(userInterest.userId, users.id))
    .leftJoin(areasOfInterest, eq(areasOfInterest.id, userInterest.interestId))
    .where(inArray(users.id, studentIds))
    .orderBy(asc(users.lastName), asc(users.firstName), asc(users.id));

  type DetailRow = {
    id: number;
    firstName: string;
    lastName: string;
    email: string;
    isActive: boolean;
    track: string | null;
    schoolName: string | null;
    yearLvl: string | null;
    hasJoinPermission: boolean;
    joinpermResponseId: string | null;
    groupId: number | null;
    groupName: string | null;
    interestId: number | null;
    interestDesc: string | null;
  };

  const itemsById = new Map<number, StudentListItem>();

  for (const row of detailRows as DetailRow[]) {
    let item = itemsById.get(row.id);

    if (!item) {
      item = {
        id: row.id,
        firstName: row.firstName,
        lastName: row.lastName,
        email: row.email,
        role: "student",
        track: row.track ?? null,
        isActive: row.isActive,
        accountStatus: row.isActive ? "active" : "deactivated",
        schoolName: row.schoolName ?? null,
        yearLevel: row.yearLvl ? parseInt(row.yearLvl, 10) : null,
        hasJoinPermission: row.hasJoinPermission,
        joinpermResponseId: row.joinpermResponseId ?? null,
        groupId: row.groupId ?? null,
        groupName: row.groupName ?? null,
        interests: [],
      };
      itemsById.set(row.id, item);
    }

    if (
      row.interestId &&
      row.interestDesc &&
      !item.interests.some((e) => e.id === row.interestId)
    ) {
      item.interests.push({
        id: row.interestId,
        description: row.interestDesc,
      });
    }
  }

  const items = studentIds.flatMap((id: number) => {
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
