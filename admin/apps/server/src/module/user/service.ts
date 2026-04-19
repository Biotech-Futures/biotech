import db from "@/lib/db.js";
import { and, asc, eq, ilike, isNull, or, sql } from "drizzle-orm";
import {
  areasOfInterest,
  groupMembership,
  groups,
  mentorProfile,
  roles,
  studentInterest,
  studentProfile,
  supervisorProfile,
  tracks,
  userRoleAssignment,
  users,
} from "@/drizzle/schema.js";
import type {
  BulkCreateUsersInput,
  CreateUserInput,
  QueryUsersInput,
  UpdateStatusInput,
  UpdateUserInput,
} from "./schema.js";
import { auth } from "@/lib/auth.js";

// ─── Types ───────────────────────────────────────────────────────────────────

export type User = {
  id: number;
  firstName: string;
  lastName: string;
  email: string;
  role: string | null;
  track: string | null;
  groupName: string | null;
  schoolName: string | null;
  yearLevel: number | null;
  joinPermissionReceived: boolean;
  interests: string[];
  isActive: boolean;
  accountStatus: string;
  invitedAt: string | null;
  activatedAt: string | null;
};

export type TrackOption = {
  id: number;
  trackCode: string;
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

// Use high-resolution timestamp to generate unique bigint IDs for admin-scale writes
const generateId = () => Date.now() * 1000 + Math.floor(Math.random() * 999);

const normalizeInterestDescriptions = (interests: string[] | undefined) =>
  Array.from(
    new Set((interests ?? []).map((item) => item.trim()).filter(Boolean)),
  );

async function resolveInterestIds(executor: any, interests: string[] | undefined) {
  const descriptions = normalizeInterestDescriptions(interests);
  const ids: number[] = [];

  for (const description of descriptions) {
    const existing = await executor
      .select({ id: areasOfInterest.id })
      .from(areasOfInterest)
      .where(sql`lower(${areasOfInterest.interestDesc}) = lower(${description})`);

    if (existing[0]) {
      ids.push(existing[0].id);
      continue;
    }

    const id = generateId();
    await executor.insert(areasOfInterest).values({
      id,
      interestDesc: description,
    });
    ids.push(id);
  }

  return ids;
}

async function syncStudentInterests(
  executor: any,
  userId: number,
  interests: string[] | undefined,
) {
  await executor
    .delete(studentInterest)
    .where(eq(studentInterest.studentUserId, userId));

  const interestIds = await resolveInterestIds(executor, interests);
  if (!interestIds.length) return;

  await executor.insert(studentInterest).values(
    interestIds.map((interestId) => ({
      id: generateId(),
      studentUserId: userId,
      interestId,
    })),
  );
}

async function upsertStudentProfile(
  executor: any,
  userId: number,
  input: Pick<
    CreateUserInput | UpdateUserInput,
    "schoolName" | "yearLevel" | "joinPermissionReceived"
  >,
) {
  const existing = await executor
    .select({ userId: studentProfile.userId })
    .from(studentProfile)
    .where(eq(studentProfile.userId, userId));

  const values = {
    schoolName: input.schoolName?.trim() || null,
    yearLevel: input.yearLevel ?? null,
    joinPermissionReceived: input.joinPermissionReceived ?? false,
    joinPermissionResponseId: null,
  };

  if (existing[0]) {
    await executor
      .update(studentProfile)
      .set(values)
      .where(eq(studentProfile.userId, userId));
    return;
  }

  await executor.insert(studentProfile).values({
    userId,
    supervisorUserId: null,
    ...values,
  });
}

async function deleteStudentDetails(executor: any, userId: number) {
  await executor
    .delete(studentInterest)
    .where(eq(studentInterest.studentUserId, userId));
  await executor.delete(studentProfile).where(eq(studentProfile.userId, userId));
}

const userSelect = {
  id: users.id,
  firstName: users.firstName,
  lastName: users.lastName,
  email: users.email,
  role: roles.slug,
  track: tracks.trackCode,
  groupName: groups.groupName,
  schoolName: sql<string | null>`COALESCE(${studentProfile.schoolName}, ${supervisorProfile.schoolName})`,
  yearLevel: studentProfile.yearLevel,
  joinPermissionReceived: studentProfile.joinPermissionReceived,
  interests: sql<string[]>`COALESCE(
    (SELECT array_agg(aoi.interest_desc) FROM student_interest si JOIN areas_of_interest aoi ON aoi.id = si.interest_id WHERE si.student_user_id = ${users.id}),
    (SELECT array_agg(aoi.interest_desc) FROM mentor_interest mi JOIN areas_of_interest aoi ON aoi.id = mi.interest_id WHERE mi.mentor_user_id = ${users.id}),
    ARRAY[]::text[]
  )`,
  isActive: users.isActive,
  accountStatus: users.accountStatus,
  invitedAt: users.invitedAt,
  activatedAt: users.activatedAt,
};

function baseUserQuery() {
  return db
    .select(userSelect)
    .from(users)
    .leftJoin(
      userRoleAssignment,
      and(
        eq(userRoleAssignment.userId, users.id),
        isNull(userRoleAssignment.validTo),
      ),
    )
    .leftJoin(roles, eq(roles.id, userRoleAssignment.roleId))
    .leftJoin(tracks, eq(tracks.id, users.trackId))
    .leftJoin(
      groupMembership,
      and(
        eq(groupMembership.userId, users.id),
        isNull(groupMembership.leftAt),
      ),
    )
    .leftJoin(groups, eq(groups.id, groupMembership.groupId))
    .leftJoin(studentProfile, eq(studentProfile.userId, users.id))
    .leftJoin(supervisorProfile, eq(supervisorProfile.userId, users.id));
}

async function fetchUserById(id: number): Promise<User | null> {
  const rows = await baseUserQuery().where(eq(users.id, id));
  return (rows[0] as User) ?? null;
}

// ─── Queries ─────────────────────────────────────────────────────────────────

export async function queryUsers(params: QueryUsersInput) {
  const { page, limit, search, role, track } = params;
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
  if (role) conditions.push(eq(roles.slug, role));
  if (track) conditions.push(eq(tracks.trackCode, track));

  const where = conditions.length > 0 ? and(...conditions) : undefined;

  const countQuery = db
    .select({ count: sql<number>`cast(count(*) as int)` })
    .from(users)
    .leftJoin(
      userRoleAssignment,
      and(
        eq(userRoleAssignment.userId, users.id),
        isNull(userRoleAssignment.validTo),
      ),
    )
    .leftJoin(roles, eq(roles.id, userRoleAssignment.roleId))
    .leftJoin(tracks, eq(tracks.id, users.trackId));

  const [items, countResult] = await Promise.all([
    where
      ? baseUserQuery().where(where).limit(limit).offset(offset)
      : baseUserQuery().limit(limit).offset(offset),
    where ? countQuery.where(where) : countQuery,
  ]);

  const total = countResult[0]?.count ?? 0;
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
    .select({
      id: tracks.id,
      trackCode: tracks.trackCode,
    })
    .from(tracks)
    .orderBy(asc(tracks.trackCode));

  return {
    msg: "Tracks retrieved successfully",
    data: items as TrackOption[],
  };
}

// ─── Mutations ───────────────────────────────────────────────────────────────

export async function createUser(input: CreateUserInput, adminUserId: string) {
  const existing = await db
    .select({ id: users.id })
    .from(users)
    .where(eq(users.email, input.email));
  if (existing.length > 0) return { msg: "Email already exists", data: null };

  if (!input.track) return { msg: "Track is required", data: null };
  if (input.role === "student") {
    if (!input.schoolName?.trim()) {
      return { msg: "School is required for student users", data: null };
    }
    if (!input.yearLevel) {
      return { msg: "Age / year level is required for student users", data: null };
    }
    if (!input.interests?.length) {
      return { msg: "At least one interest is required for student users", data: null };
    }
  }

  const trackRow = await db
    .select({ id: tracks.id })
    .from(tracks)
    .where(eq(tracks.trackCode, input.track));
  if (trackRow.length === 0)
    return { msg: `Track "${input.track}" not found`, data: null };

  const roleRow = await db
    .select({ id: roles.id })
    .from(roles)
    .where(eq(roles.slug, input.role));
  if (roleRow.length === 0)
    return { msg: `Role "${input.role}" not found`, data: null };

  const now = new Date().toISOString();
  const userId = generateId();

  await db.transaction(async (tx) => {
    await tx.insert(users).values({
      id: userId,
      email: input.email,
      firstName: input.firstName,
      lastName: input.lastName,
      isActive: input.active ?? true,
      trackId: trackRow[0].id,
      accountStatus: input.active === false ? "deactivated" : "active",
      invitedAt: now,
      adminUserId,
    });

    await tx.insert(userRoleAssignment).values({
      id: generateId(),
      userId,
      roleId: roleRow[0].id,
      validFrom: now,
      validTo: null,
    });

    if (input.role === "student") {
      await upsertStudentProfile(tx, userId, input);
      await syncStudentInterests(tx, userId, input.interests);
    }
  });

  const created = await fetchUserById(userId);
  return { msg: "User created successfully", data: created };
}

export async function bulkCreateUsers(
  input: BulkCreateUsersInput,
  adminUserId: string,
) {
  const created: User[] = [];
  const skipped: string[] = [];

  for (const u of input.users) {
    const result = await createUser(u, adminUserId);
    if (result.data) {
      created.push(result.data as User);
    } else {
      skipped.push(u.email);
    }
  }

  return {
    msg: `Bulk import complete: ${created.length} created, ${skipped.length} skipped`,
    data: { created, skipped },
  };
}

export async function updateUser(id: string, input: UpdateUserInput) {
  const userId = Number(id);
  const existing = await fetchUserById(userId);
  if (!existing) return { msg: "User not found", data: null };

  const now = new Date().toISOString();
  const userUpdates: Partial<typeof users.$inferInsert> = {};
  const nextRole = input.role ?? existing.role;

  if (input.firstName !== undefined) userUpdates.firstName = input.firstName;
  if (input.lastName !== undefined) userUpdates.lastName = input.lastName;
  if (input.email !== undefined) userUpdates.email = input.email;

  if (nextRole === "student") {
    const nextSchoolName = input.schoolName ?? existing.schoolName;
    const nextYearLevel = input.yearLevel ?? existing.yearLevel;
    const nextInterests = input.interests ?? existing.interests;

    if (!nextSchoolName?.trim()) {
      return { msg: "School is required for student users", data: null };
    }
    if (!nextYearLevel) {
      return { msg: "Age / year level is required for student users", data: null };
    }
    if (!nextInterests?.length) {
      return { msg: "At least one interest is required for student users", data: null };
    }
  }

  if (input.track !== undefined) {
    if (input.track === null)
      return { msg: "Track cannot be cleared", data: null };

    const trackRow = await db
      .select({ id: tracks.id })
      .from(tracks)
      .where(eq(tracks.trackCode, input.track));
    if (trackRow.length === 0)
      return { msg: `Track "${input.track}" not found`, data: null };
    userUpdates.trackId = trackRow[0].id;
  }

  try {
    await db.transaction(async (tx) => {
      if (Object.keys(userUpdates).length > 0) {
        await tx.update(users).set(userUpdates).where(eq(users.id, userId));
      }

      if (input.role !== undefined && input.role !== existing.role) {
        const roleRow = await tx
          .select({ id: roles.id })
          .from(roles)
          .where(eq(roles.slug, input.role));
        if (roleRow.length === 0) {
          throw new Error(`Role "${input.role}" not found`);
        }

        await tx
          .update(userRoleAssignment)
          .set({ validTo: now })
          .where(
            and(
              eq(userRoleAssignment.userId, userId),
              isNull(userRoleAssignment.validTo),
            ),
          );

        await tx.insert(userRoleAssignment).values({
          id: generateId(),
          userId,
          roleId: roleRow[0].id,
          validFrom: now,
          validTo: null,
        });
      }

      if (nextRole === "student") {
        await upsertStudentProfile(tx, userId, {
          schoolName: input.schoolName ?? existing.schoolName,
          yearLevel: input.yearLevel ?? existing.yearLevel,
          joinPermissionReceived:
            input.joinPermissionReceived ?? existing.joinPermissionReceived,
        });
        await syncStudentInterests(tx, userId, input.interests ?? existing.interests);
      } else if (existing.role === "student") {
        await deleteStudentDetails(tx, userId);
      }
    });
  } catch (error) {
    return {
      msg: error instanceof Error ? error.message : "Unable to update user",
      data: null,
    };
  }

  const updated = await fetchUserById(userId);
  return { msg: "User updated successfully", data: updated };
}

export async function updateStatus(id: string, input: UpdateStatusInput) {
  const userId = Number(id);
  const existing = await fetchUserById(userId);
  if (!existing) return { msg: "User not found", data: null };

  const accountStatus = input.isActive ? "active" : "deactivated";
  await db
    .update(users)
    .set({ isActive: input.isActive, accountStatus })
    .where(eq(users.id, userId));

  const updated = await fetchUserById(userId);
  return {
    msg: `User ${input.isActive ? "activated" : "deactivated"} successfully`,
    data: updated,
  };
}

export async function deleteUser(id: string) {
  const userId = Number(id);
  const existing = await fetchUserById(userId);
  if (!existing) return { msg: "User not found", data: null };

  await db
    .delete(userRoleAssignment)
    .where(eq(userRoleAssignment.userId, userId));
  await db.delete(studentInterest).where(eq(studentInterest.studentUserId, userId));
  await db.delete(mentorProfile).where(eq(mentorProfile.userId, userId));
  await db
    .delete(supervisorProfile)
    .where(eq(supervisorProfile.userId, userId));
  await db.delete(studentProfile).where(eq(studentProfile.userId, userId));
  await db.delete(users).where(eq(users.id, userId));

  return { msg: "User deleted successfully", data: null };
}

async function bulkCreateAdminUsers(users: CreateUserInput[]) {
  const success = [];
  const failed = [];
  const others = [];
  for (const user of users) {
    if (user.role === "admin") {
      try {
        const newUser = await auth.api.createUser({
          body: {
            email: user.email,
            name: `${user.firstName} ${user.lastName}`.trim(),
          },
        });
        if (newUser) {
          success.push(user);
        } else {
          failed.push(user);
        }
      } catch (error) {
        failed.push(user);
      }
    } else {
      others.push(user);
    }
  }

  return {
    success,
    failed,
    others,
  };
}
