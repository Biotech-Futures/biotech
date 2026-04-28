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
import {
  groupMembership,
  groups,
  mentorProfile,
  messages,
  studentProfile,
  tracks,
  users,
} from "@/schema/index.js";
import type {
  QueryGroupMessagesInput,
  QueryGroupsInput,
  UpdateGroupInput,
} from "./schema.js";

export type Track = string;

export type GroupMember = {
  id: string;
  name: string;
  email: string;
  role: "student" | "mentor";
  membershipId?: number;
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

export type GroupMessage = {
  id: string;
  groupId: string;
  sender: {
    id: string;
    name: string;
    email: string;
    role: "student" | "mentor" | null;
  };
  text: string;
  sentAt: string;
  editedAt: string | null;
};

type GroupBaseRow = {
  id: number;
  name: string;
  track: string;
  createdAt: string;
};

async function buildGroups(baseRows: GroupBaseRow[]): Promise<Group[]> {
  if (baseRows.length === 0) return [];

  const groupIds = baseRows.map((g) => g.id);

  const memberRows = await db
    .select({
      groupId: groupMembership.groupId,
      membershipId: groupMembership.id,
      userId: users.id,
      firstName: users.firstName,
      lastName: users.lastName,
      email: users.email,
      isMentor: sql<boolean>`(${mentorProfile.userId} IS NOT NULL)`,
      isStudent: sql<boolean>`(${studentProfile.userId} IS NOT NULL)`,
    })
    .from(groupMembership)
    .innerJoin(users, eq(users.id, groupMembership.userId))
    .leftJoin(mentorProfile, eq(mentorProfile.userId, groupMembership.userId))
    .leftJoin(studentProfile, eq(studentProfile.userId, groupMembership.userId))
    .where(inArray(groupMembership.groupId, groupIds))
    .orderBy(asc(groupMembership.groupId), asc(groupMembership.id));

  const membersByGroupId = new Map<number, GroupMember[]>();
  const mentorByGroupId = new Map<number, GroupMember>();

  for (const row of memberRows) {
    const role = row.isMentor ? "mentor" : row.isStudent ? "student" : null;
    if (!role) continue;

    const member: GroupMember = {
      id: String(row.userId),
      name: `${row.firstName} ${row.lastName}`.trim(),
      email: row.email,
      role,
      membershipId: row.membershipId,
    };

    if (role === "mentor") {
      mentorByGroupId.set(row.groupId, member);
      continue;
    }

    const list = membersByGroupId.get(row.groupId) ?? [];
    list.push(member);
    membersByGroupId.set(row.groupId, list);
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

  if (params.track) conditions.push(eq(tracks.trackName, params.track));
  if (params.searchGroup) {
    conditions.push(ilike(groups.groupName, `%${params.searchGroup}%`));
  }

  const mentorMembership = db
    .select({ id: groupMembership.id })
    .from(groupMembership)
    .innerJoin(mentorProfile, eq(mentorProfile.userId, groupMembership.userId))
    .where(eq(groupMembership.groupId, groups.id));

  if (params.mentorStatus === "matched") {
    conditions.push(exists(mentorMembership));
  }
  if (params.mentorStatus === "unmatched") {
    conditions.push(notExists(mentorMembership));
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
      track: tracks.trackName,
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
        track: tracks.trackName,
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

export async function queryGroupMessages(
  id: string,
  params: QueryGroupMessagesInput,
) {
  const groupId = Number(id);
  if (!Number.isFinite(groupId)) {
    return { msg: "Group not found", data: null };
  }

  const existing = await fetchGroupBaseById(groupId);
  if (!existing) return { msg: "Group not found", data: null };

  const { page, limit } = params;
  const offset = (page - 1) * limit;

  const where = and(eq(messages.groupId, groupId), isNull(messages.deletedAt));

  const [messageRows, countResult] = await Promise.all([
    db
      .select({
        id: messages.id,
        groupId: messages.groupId,
        senderUserId: users.id,
        senderFirstName: users.firstName,
        senderLastName: users.lastName,
        senderEmail: users.email,
        isMentor: sql<boolean>`(${mentorProfile.userId} IS NOT NULL)`,
        isStudent: sql<boolean>`(${studentProfile.userId} IS NOT NULL)`,
        text: messages.messageText,
        sentAt: messages.sentAt,
        editedAt: messages.editedAt,
      })
      .from(messages)
      .innerJoin(users, eq(users.id, messages.senderUserId))
      .leftJoin(mentorProfile, eq(mentorProfile.userId, messages.senderUserId))
      .leftJoin(
        studentProfile,
        eq(studentProfile.userId, messages.senderUserId),
      )
      .where(where)
      .orderBy(asc(messages.sentAt), asc(messages.id))
      .limit(limit)
      .offset(offset),
    db
      .select({
        count: sql<number>`cast(count(${messages.id}) as int)`,
      })
      .from(messages)
      .where(where),
  ]);

  const items: GroupMessage[] = messageRows.map((row) => {
    const role = row.isMentor ? "mentor" : row.isStudent ? "student" : null;
    return {
      id: String(row.id),
      groupId: String(row.groupId),
      sender: {
        id: String(row.senderUserId),
        name: `${row.senderFirstName} ${row.senderLastName}`.trim(),
        email: row.senderEmail,
        role,
      },
      text: row.text,
      sentAt: row.sentAt,
      editedAt: row.editedAt,
    };
  });

  const total = countResult[0]?.count ?? 0;

  return {
    msg: "Group messages retrieved successfully",
    data: {
      items,
      total,
      page,
      limit,
      hasMore: offset + items.length < total,
    },
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
      .where(eq(tracks.trackName, updates.track))
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
