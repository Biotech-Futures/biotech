import { and, eq, ilike, isNull, or, sql } from "drizzle-orm";
import type { QueryStudentsInput } from "../schema.js";
import db from "@/lib/db.js";
import {
  areasOfInterest,
  groupMembership,
  studentInterest,
  studentProfile,
  tracks,
  users,
} from "@/drizzle/schema.js";
import type { User } from "../service.js";

export async function queryStudents(params: QueryStudentsInput) {
  const { page, limit, search, track, interest, inGroup } = params;
  const offset = (page - 1) * limit;

  const conditions = [];

  if (search) {
    conditions.push(
      or(
        ilike(users.firstName, `%${search}%`),
        ilike(users.lastName, `%${search}%`),
        ilike(users.email, `%${search}%`),
      ) as ReturnType<typeof eq>,
    );
  }
  if (track) conditions.push(eq(tracks.trackCode, track));

  const where = and(...conditions);

  let query = db
    .select()
    .from(users)
    .leftJoin(tracks, eq(tracks.id, users.trackId))
    .leftJoin(studentProfile, eq(studentProfile.userId, users.id));

  if (interest) {
    query = (query as any)
      .innerJoin(studentInterest, eq(studentInterest.studentUserId, users.id))
      .innerJoin(
        areasOfInterest,
        and(
          eq(areasOfInterest.id, studentInterest.interestId),
          ilike(areasOfInterest.interestDesc, `%${interest}%`),
        ),
      );
  }

  if (inGroup === "yes") {
    query = (query as any).innerJoin(
      groupMembership,
      and(eq(groupMembership.userId, users.id), isNull(groupMembership.leftAt)),
    );
  } else if (inGroup === "no") {
    const activeMembership = db
      .select({ userId: groupMembership.userId })
      .from(groupMembership)
      .where(
        and(
          eq(groupMembership.userId, users.id),
          isNull(groupMembership.leftAt),
        ),
      );

    conditions.push(
      sql`NOT EXISTS (${activeMembership})` as unknown as ReturnType<typeof eq>,
    );
  }

  const countQuery = db
    .select({ count: sql<number>`cast(count(*) as int)` })
    .from(users)
    .leftJoin(tracks, eq(tracks.id, users.trackId))
    .where(where);

  const [items, countResult] = await Promise.all([
    (query as any).where(where).limit(limit).offset(offset),
    countQuery,
  ]);

  const total = countResult[0]?.count ?? 0;
  return {
    msg: "Students retrieved successfully",
    data: {
      items: items as User[],
      total,
      page,
      limit,
      hasMore: offset + items.length < total,
    },
  };
}
