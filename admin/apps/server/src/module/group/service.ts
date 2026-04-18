import db from "@/lib/db.js";
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
import { groups, groupMembership, tracks, users } from "@/drizzle/schema.js";
import type { QueryGroupsInput, UpdateGroupInput } from "./schema.js";

export type Track = string;

export type GroupMember = {
  id: string;
  name: string;
  email: string;
  role: "student" | "mentor";
};

export type Group = {
  id: string;
  name: string;
  track: Track;
  members: GroupMember[];
  mentor: GroupMember | null;
  createdAt: string;
  updatedAt: string;
};

type GroupBaseRow = {
  id: number;
  name: string;
  track: string;
  createdAt: string;
};

function toGroupMember(row: {
  userId: number;
  firstName: string;
  lastName: string;
  email: string;
  membershipRole: string | null;
}): GroupMember | null {
  const role = row.membershipRole?.toLowerCase();
  if (role !== "student" && role !== "mentor") return null;

  return {
    id: String(row.userId),
    name: `${row.firstName} ${row.lastName}`.trim(),
    email: row.email,
    role,
  };
}

async function buildGroups(baseRows: GroupBaseRow[]): Promise<Group[]> {
  if (baseRows.length === 0) return [];

  const groupIds = baseRows.map((group) => group.id);
  const memberRows = await db
    .select({
      groupId: groupMembership.groupId,
      userId: users.id,
      firstName: users.firstName,
      lastName: users.lastName,
      email: users.email,
      membershipRole: groupMembership.membershipRole,
    })
    .from(groupMembership)
    .innerJoin(users, eq(users.id, groupMembership.userId))
    .where(
      and(
        inArray(groupMembership.groupId, groupIds),
        isNull(groupMembership.leftAt),
      ),
    )
    .orderBy(asc(groupMembership.groupId), asc(groupMembership.joinedAt));

  const membersByGroupId = new Map<number, GroupMember[]>();
  const mentorByGroupId = new Map<number, GroupMember>();

  for (const row of memberRows) {
    const member = toGroupMember(row);
    if (!member) continue;

    if (member.role === "mentor") {
      mentorByGroupId.set(row.groupId, member);
      continue;
    }

    const members = membersByGroupId.get(row.groupId) ?? [];
    members.push(member);
    membersByGroupId.set(row.groupId, members);
  }

  return baseRows.map((row) => ({
    id: String(row.id),
    name: row.name,
    track: row.track,
    members: membersByGroupId.get(row.id) ?? [],
    mentor: mentorByGroupId.get(row.id) ?? null,
    createdAt: row.createdAt,
    updatedAt: row.createdAt,
  }));
}

function buildGroupWhere(
  params: Pick<
    QueryGroupsInput,
    "searchName" | "searchGroup" | "track" | "mentorStatus"
  >,
) {
  const conditions = [isNull(groups.deletedAt)];

  if (params.track) conditions.push(eq(tracks.trackCode, params.track));
  if (params.searchGroup) {
    conditions.push(ilike(groups.groupName, `%${params.searchGroup}%`));
  }

  const activeMentorMembership = db
    .select({ id: groupMembership.id })
    .from(groupMembership)
    .where(
      and(
        eq(groupMembership.groupId, groups.id),
        eq(groupMembership.membershipRole, "mentor"),
        isNull(groupMembership.leftAt),
      ),
    );

  if (params.mentorStatus === "matched") {
    conditions.push(exists(activeMentorMembership));
  }

  if (params.mentorStatus === "unmatched") {
    conditions.push(notExists(activeMentorMembership));
  }

  if (params.searchName) {
    const search = `%${params.searchName}%`;
    const matchingMember = db
      .select({ id: groupMembership.id })
      .from(groupMembership)
      .innerJoin(users, eq(users.id, groupMembership.userId))
      .where(
        and(
          eq(groupMembership.groupId, groups.id),
          isNull(groupMembership.leftAt),
          or(
            ilike(users.firstName, search),
            ilike(users.lastName, search),
            ilike(users.email, search),
          ),
        ),
      );

    conditions.push(exists(matchingMember));
  }

  return and(...conditions);
}

async function fetchGroupBaseById(id: number): Promise<GroupBaseRow | null> {
  const rows = await db
    .select({
      id: groups.id,
      name: groups.groupName,
      track: tracks.trackCode,
      createdAt: groups.createdAt,
    })
    .from(groups)
    .innerJoin(tracks, eq(tracks.id, groups.trackId))
    .where(and(eq(groups.id, id), isNull(groups.deletedAt)))
    .limit(1);

  return rows[0] ?? null;
}

export async function queryGroups(params: QueryGroupsInput) {
  const { page, limit } = params;
  const offset = (page - 1) * limit;
  const where = buildGroupWhere(params);

  const [baseRows, countResult] = await Promise.all([
    db
      .select({
        id: groups.id,
        name: groups.groupName,
        track: tracks.trackCode,
        createdAt: groups.createdAt,
      })
      .from(groups)
      .innerJoin(tracks, eq(tracks.id, groups.trackId))
      .where(where)
      .orderBy(asc(groups.groupName), asc(groups.id))
      .limit(limit)
      .offset(offset),
    db
      .select({
        count: sql<number>`cast(count(distinct ${groups.id}) as int)`,
      })
      .from(groups)
      .innerJoin(tracks, eq(tracks.id, groups.trackId))
      .where(where),
  ]);

  const items = await buildGroups(baseRows);
  const total = countResult[0]?.count ?? 0;

  return {
    msg: "Groups retrieved successfully",
    data: {
      items,
      total,
      page,
      limit,
      hasMore: offset + items.length < total,
    },
  };
}

export async function queryGroupById(id: string) {
  const groupId = Number(id);
  if (!Number.isFinite(groupId)) {
    return { msg: "Group not found", data: null };
  }

  const baseRow = await fetchGroupBaseById(groupId);
  if (!baseRow) return { msg: "Group not found", data: null };

  const [group] = await buildGroups([baseRow]);
  return {
    msg: "Group retrieved successfully",
    data: group,
  };
}

export async function updateGroup(id: string, updates: UpdateGroupInput) {
  const groupId = Number(id);
  if (!Number.isFinite(groupId)) {
    return { msg: "Group not found", data: null };
  }

  const existing = await fetchGroupBaseById(groupId);
  if (!existing) return { msg: "Group not found", data: null };

  const groupUpdates: Partial<typeof groups.$inferInsert> = {};
  if (updates.name !== undefined) groupUpdates.groupName = updates.name;

  if (updates.track !== undefined) {
    const trackRows = await db
      .select({ id: tracks.id })
      .from(tracks)
      .where(eq(tracks.trackCode, updates.track))
      .limit(1);

    if (!trackRows[0]) {
      return { msg: `Track "${updates.track}" not found`, data: null };
    }

    groupUpdates.trackId = trackRows[0].id;
  }

  if (Object.keys(groupUpdates).length > 0) {
    await db.update(groups).set(groupUpdates).where(eq(groups.id, groupId));
  }

  return {
    msg: "Group updated successfully",
    data: (await queryGroupById(id)).data,
  };
}
