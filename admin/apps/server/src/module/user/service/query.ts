import db from "@/lib/db.js";
import {
  and,
  asc,
  desc,
  eq,
  ilike,
  inArray,
  isNull,
  or,
  sql,
} from "drizzle-orm";
import {
  groupMembership,
  groups,
  roleAssignmentHistory,
  roles,
  tracks,
  users,
} from "@/schema/index.js";
import type { QueryUsersInput } from "../schema.js";
import type { TrackOption, User } from "../type.js";
import { baseUserQuery, fetchUserById } from "./shared.js";

export async function queryUsers(params: QueryUsersInput) {
  const { page, limit, search, role, track, active, sortBy, sortOrder } = params;
  const offset = (page - 1) * limit;

  const conditions = [];
  if (search) {
    const normalizedSearch = search.trim();
    conditions.push(
      or(
        ilike(users.firstName, `%${normalizedSearch}%`),
        ilike(users.lastName, `%${normalizedSearch}%`),
        ilike(users.email, `%${normalizedSearch}%`),
        ilike(groups.groupName, `%${normalizedSearch}%`),
        sql`${users.firstName} || ' ' || ${users.lastName} ilike ${`%${normalizedSearch}%`}`,
      ),
    );
  }
  if (role) conditions.push(eq(roles.roleName, role));
  if (track) conditions.push(eq(tracks.trackName, track));
  if (active !== undefined) conditions.push(eq(users.isActive, active));

  const where = conditions.length > 0 ? and(...conditions) : undefined;

  const countQuery = db
    .select({ count: sql<number>`cast(count(distinct ${users.id}) as int)` })
    .from(users)
    .leftJoin(
      roleAssignmentHistory,
      and(
        eq(roleAssignmentHistory.userId, users.id),
        isNull(roleAssignmentHistory.validTo),
      ),
    )
    .leftJoin(roles, eq(roles.id, roleAssignmentHistory.roleId))
    .leftJoin(tracks, eq(tracks.id, users.trackId))
    .leftJoin(
      groupMembership,
      and(eq(groupMembership.userId, users.id), isNull(groupMembership.leftAt)),
    )
    .leftJoin(
      groups,
      and(eq(groups.id, groupMembership.groupId), isNull(groups.deletedAt)),
    );

  const idsQuery = db
    .select({ id: users.id, dateJoined: users.dateJoined })
    .from(users)
    .leftJoin(
      roleAssignmentHistory,
      and(
        eq(roleAssignmentHistory.userId, users.id),
        isNull(roleAssignmentHistory.validTo),
      ),
    )
    .leftJoin(roles, eq(roles.id, roleAssignmentHistory.roleId))
    .leftJoin(tracks, eq(tracks.id, users.trackId))
    .leftJoin(
      groupMembership,
      and(eq(groupMembership.userId, users.id), isNull(groupMembership.leftAt)),
    )
    .leftJoin(
      groups,
      and(eq(groups.id, groupMembership.groupId), isNull(groups.deletedAt)),
    )
    .groupBy(users.id, users.dateJoined, users.firstName, users.lastName)
    .orderBy(
      ...(sortBy === "name"
        ? sortOrder === "asc"
          ? [asc(users.firstName), asc(users.lastName), asc(users.id)]
          : [desc(users.firstName), desc(users.lastName), asc(users.id)]
        : sortOrder === "asc"
          ? [asc(users.dateJoined), asc(users.id)]
          : [desc(users.dateJoined), asc(users.id)]),
    )
    .limit(limit)
    .offset(offset);

  const [pageRows, countResult] = await Promise.all([
    where ? idsQuery.where(where) : idsQuery,
    where ? countQuery.where(where) : countQuery,
  ]);

  const total = countResult[0]?.count ?? 0;
  const userIds = pageRows.map((row) => row.id);
  const detailRows = userIds.length
    ? await baseUserQuery().where(inArray(users.id, userIds))
    : [];
  const detailsById = new Map(detailRows.map((row) => [row.id, row]));
  const items = userIds.flatMap((id) => {
    const item = detailsById.get(id);
    return item ? [item] : [];
  });

  return {
    msg: "Users retrieved successfully",
    data: {
      items: items as User[],
      total,
      page,
      limit,
      hasMore: offset + items.length < total,
    },
  };
}

export async function queryUserById(id: string) {
  const user = await fetchUserById(Number(id));
  if (!user) return { msg: "User not found", data: null };
  return { msg: "User retrieved successfully", data: user };
}

export async function queryTracks() {
  const items = await db
    .select({ id: tracks.id, trackName: tracks.trackName })
    .from(tracks)
    .orderBy(asc(tracks.trackName));

  return { msg: "Tracks retrieved successfully", data: items as TrackOption[] };
}
