import db from "@/lib/db.js";
import { and, asc, eq, ilike, isNull, or, sql } from "drizzle-orm";
import {
  adminUser,
  areasOfInterest,
  groupMembership,
  groups,
  mentorProfile,
  roleAssignmentHistory,
  roles,
  userInterest,
  studentProfile,
  supervisorProfile,
  tracks,
  users,
} from "@/schema/index.js";
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
  trackName: string;
};

const STATUS = {
  INVITED: "invited",
  PENDING: "pending",
  ACTIVE: "active",
  SUSPENDED: "suspended",
  DEACTIVATED: "deactivated",
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

const normalizeInterestDescriptions = (interests: string[] | undefined) =>
  Array.from(
    new Set((interests ?? []).map((item) => item.trim()).filter(Boolean)),
  );

async function resolveRoleId(executor: any, roleName: string): Promise<number> {
  const normalizedRole = roleName.trim();
  const existing = await executor
    .select({ id: roles.id })
    .from(roles)
    .where(sql`lower(${roles.roleName}) = lower(${normalizedRole})`)
    .limit(1);

  if (existing[0]) return existing[0].id;

  const inserted = await executor
    .insert(roles)
    .values({ roleName: normalizedRole })
    .returning({ id: roles.id });

  return inserted[0].id;
}

async function resolveInterestIds(
  executor: any,
  interests: string[] | undefined,
) {
  const descriptions = normalizeInterestDescriptions(interests);
  const ids: number[] = [];

  for (const description of descriptions) {
    const existing = await executor
      .select({ id: areasOfInterest.id })
      .from(areasOfInterest)
      .where(
        sql`lower(${areasOfInterest.interestDesc}) = lower(${description})`,
      );

    if (existing[0]) {
      ids.push(existing[0].id);
      continue;
    }

    const inserted = await executor
      .insert(areasOfInterest)
      .values({ interestDesc: description })
      .returning({ id: areasOfInterest.id });
    ids.push(inserted[0].id);
  }

  return ids;
}

async function syncStudentInterests(
  executor: any,
  userId: number,
  interests: string[] | undefined,
) {
  await executor.delete(userInterest).where(eq(userInterest.userId, userId));

  const interestIds = await resolveInterestIds(executor, interests);
  if (!interestIds.length) return;

  await executor
    .insert(userInterest)
    .values(interestIds.map((interestId) => ({ userId, interestId })));
}

async function upsertStudentProfile(
  executor: any,
  userId: number,
  firstName: string,
  lastName: string,
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
    pgFirstName: firstName,
    pgLastName: lastName,
    parentGuardianFlag: true,
    schoolName: input.schoolName?.trim() || "",
    yearLvl: String(input.yearLevel ?? ""),
    hasJoinPermission: input.joinPermissionReceived ?? false,
    joinpermResponseId: null,
    supervisorId: null,
  };

  if (existing[0]) {
    await executor
      .update(studentProfile)
      .set(values)
      .where(eq(studentProfile.userId, userId));
    return;
  }

  await executor.insert(studentProfile).values({ userId, ...values });
}

async function upsertSupervisorProfile(
  executor: any,
  userId: number,
  schoolName: string,
) {
  const existing = await executor
    .select({ userId: supervisorProfile.userId })
    .from(supervisorProfile)
    .where(eq(supervisorProfile.userId, userId));

  if (existing[0]) {
    await executor
      .update(supervisorProfile)
      .set({ schoolName })
      .where(eq(supervisorProfile.userId, userId));
    return;
  }

  await executor.insert(supervisorProfile).values({ userId, schoolName });
}

async function deleteStudentDetails(executor: any, userId: number) {
  await executor.delete(userInterest).where(eq(userInterest.userId, userId));
  await executor
    .delete(studentProfile)
    .where(eq(studentProfile.userId, userId));
}

const userSelect = {
  id: users.id,
  firstName: users.firstName,
  lastName: users.lastName,
  email: users.email,
  role: roles.roleName,
  track: tracks.trackName,
  groupName: groups.groupName,
  schoolName: sql<
    string | null
  >`COALESCE(${studentProfile.schoolName}, ${supervisorProfile.schoolName})`,
  yearLevel: sql<number | null>`NULLIF(${studentProfile.yearLvl}, '')::int`,
  joinPermissionReceived: studentProfile.hasJoinPermission,
  interests: sql<
    string[]
  >`COALESCE((SELECT array_agg(aoi.interest_desc) FROM user_interest ui JOIN areas_of_interest aoi ON aoi.id = ui.interest_id WHERE ui.user_id = ${users.id}), ARRAY[]::text[])`,
  isActive: users.isActive,
  accountStatus: sql<string>`CASE WHEN ${users.isActive} THEN 'active' ELSE 'deactivated' END`,
  invitedAt: users.dateJoined,
  activatedAt: users.lastLogin,
};

function baseUserQuery() {
  return db
    .select(userSelect)
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
    .leftJoin(groupMembership, eq(groupMembership.userId, users.id))
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
  if (role) conditions.push(eq(roles.roleName, role));
  if (track) conditions.push(eq(tracks.trackName, track));

  const where = conditions.length > 0 ? and(...conditions) : undefined;

  const countQuery = db
    .select({ count: sql<number>`cast(count(*) as int)` })
    .from(users)
    .leftJoin(
      roleAssignmentHistory,
      and(
        eq(roleAssignmentHistory.userId, users.id),
        isNull(roleAssignmentHistory.validTo),
      ),
    )
    .leftJoin(roles, eq(roles.id, roleAssignmentHistory.roleId))
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
    .select({ id: tracks.id, trackName: tracks.trackName })
    .from(tracks)
    .orderBy(asc(tracks.trackName));

  return { msg: "Tracks retrieved successfully", data: items as TrackOption[] };
}

// ─── Mutations ───────────────────────────────────────────────────────────────

export async function createUser(input: CreateUserInput) {
  const existing = await db
    .select({ id: users.id })
    .from(users)
    .where(eq(users.email, input.email));
  if (existing.length > 0) return { msg: "Email already exists", data: null };

  const normalizedTrack = input.track?.trim();
  if (input.role !== "admin" && !normalizedTrack) {
    return { msg: "Track is required", data: null };
  }

  if (input.role === "student") {
    if (!input.schoolName?.trim())
      return { msg: "School is required for student users", data: null };
    if (!input.yearLevel)
      return { msg: "Year level is required for student users", data: null };
    if (!input.interests?.length)
      return {
        msg: "At least one interest is required for student users",
        data: null,
      };
  }

  let trackId: number | null = null;
  if (normalizedTrack) {
    const trackRow = await db
      .select({ id: tracks.id })
      .from(tracks)
      .where(eq(tracks.trackName, normalizedTrack));
    if (trackRow.length === 0)
      return { msg: `Track "${normalizedTrack}" not found`, data: null };
    trackId = trackRow[0].id;
  }

  const roleId = await resolveRoleId(db, input.role);

  if (input.role === "admin") {
    const existingAdmin = await db
      .select({ id: adminUser.id })
      .from(adminUser)
      .where(eq(adminUser.email, input.email));
    if (existingAdmin.length > 0)
      return { msg: "Admin account email already exists", data: null };
  }

  const now = new Date().toISOString();
  let newUserId: number | undefined;

  await db.transaction(async (tx) => {
    const [newUser] = await tx
      .insert(users)
      .values({
        password: "TEMP_PASSWORD_PLACEHOLDER",
        isSuperuser: input.role === "admin",
        isStaff: input.role === "admin",
        email: input.email,
        firstName: input.firstName,
        lastName: input.lastName,
        isActive: input.active ?? true,
        accountStatus: (input.active ?? true) ? STATUS.ACTIVE : STATUS.INVITED,
        dateJoined: now,
        lastLogin: null,
        trackId,
      })
      .returning({ id: users.id });

    const userId = newUser.id;
    newUserId = userId;

    if (input.role === "admin") {
      const createdAuthUser = await auth.api.createUser({
        body: {
          email: input.email,
          name: `${input.firstName} ${input.lastName}`.trim(),
          role: "admin",
        },
      });
      const createdAuthUserId =
        (createdAuthUser as any)?.user?.id ?? (createdAuthUser as any)?.id;
      if (!createdAuthUserId) throw new Error("Failed to create auth user");

      await tx
        .update(adminUser)
        .set({ emailVerified: true, userid: userId })
        .where(eq(adminUser.id, String(createdAuthUserId)));
    }

    await tx.insert(roleAssignmentHistory).values({
      userId,
      roleId,
      validFrom: now,
      validTo: null,
    });

    if (input.role === "student") {
      await upsertStudentProfile(
        tx,
        userId,
        input.firstName,
        input.lastName,
        input,
      );
      await syncStudentInterests(tx, userId, input.interests);
    }

    if (input.role === "supervisor") {
      await upsertSupervisorProfile(
        tx,
        userId,
        input.supervisorSchoolName?.trim() ?? "",
      );
    }
  });

  if (!newUserId) return { msg: "Failed to create user", data: null };
  const created = await fetchUserById(newUserId);
  return { msg: "User created successfully", data: created };
}

export async function bulkCreateUsers(
  input: BulkCreateUsersInput,
  _adminUserId: string,
) {
  const created: User[] = [];
  const skipped: string[] = [];

  for (const u of input.users) {
    const result = await createUser(u);
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
  const nextRole = input.role ?? existing.role ?? "student";

  if (input.firstName !== undefined) userUpdates.firstName = input.firstName;
  if (input.lastName !== undefined) userUpdates.lastName = input.lastName;
  if (input.email !== undefined) userUpdates.email = input.email;

  if (nextRole === "student") {
    const nextSchoolName = input.schoolName ?? existing.schoolName;
    const nextYearLevel = input.yearLevel ?? existing.yearLevel;
    const nextInterests = input.interests ?? existing.interests;

    if (!nextSchoolName?.trim())
      return { msg: "School is required for student users", data: null };
    if (!nextYearLevel)
      return { msg: "Year level is required for student users", data: null };
    if (!nextInterests?.length)
      return {
        msg: "At least one interest is required for student users",
        data: null,
      };
  }

  if (input.track !== undefined) {
    if (nextRole === "admin") {
      if (input.track === null) userUpdates.trackId = null;
    } else {
      if (input.track === null)
        return { msg: "Track cannot be cleared", data: null };

      const trackRow = await db
        .select({ id: tracks.id })
        .from(tracks)
        .where(eq(tracks.trackName, input.track));
      if (trackRow.length === 0)
        return { msg: `Track "${input.track}" not found`, data: null };
      userUpdates.trackId = trackRow[0].id;
    }
  }

  try {
    await db.transaction(async (tx) => {
      if (Object.keys(userUpdates).length > 0) {
        await tx.update(users).set(userUpdates).where(eq(users.id, userId));
      }

      if (input.role !== undefined && input.role !== existing.role) {
        const roleId = await resolveRoleId(tx, input.role);

        await tx
          .update(roleAssignmentHistory)
          .set({ validTo: now })
          .where(
            and(
              eq(roleAssignmentHistory.userId, userId),
              isNull(roleAssignmentHistory.validTo),
            ),
          );

        await tx.insert(roleAssignmentHistory).values({
          userId,
          roleId,
          validFrom: now,
          validTo: null,
        });
      }

      // Student profile
      if (nextRole === "student") {
        await upsertStudentProfile(
          tx,
          userId,
          input.firstName ?? existing.firstName,
          input.lastName ?? existing.lastName,
          {
            schoolName: input.schoolName ?? existing.schoolName,
            yearLevel: input.yearLevel ?? existing.yearLevel,
            joinPermissionReceived:
              input.joinPermissionReceived ?? existing.joinPermissionReceived,
          },
        );
        await syncStudentInterests(
          tx,
          userId,
          input.interests ?? existing.interests,
        );
      } else if (existing.role === "student") {
        await deleteStudentDetails(tx, userId);
      }

      // Supervisor profile
      if (nextRole === "supervisor") {
        const schoolName =
          input.supervisorSchoolName?.trim() ??
          (existing.role === "supervisor" ? (existing.schoolName ?? "") : "");
        await upsertSupervisorProfile(tx, userId, schoolName);
      } else if (existing.role === "supervisor" && nextRole !== "supervisor") {
        await tx
          .delete(supervisorProfile)
          .where(eq(supervisorProfile.userId, userId));
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

  await db
    .update(users)
    .set({
      isActive: input.isActive,
      accountStatus: input.isActive ? STATUS.ACTIVE : STATUS.DEACTIVATED,
    })
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
    .delete(roleAssignmentHistory)
    .where(eq(roleAssignmentHistory.userId, userId));
  await db.delete(userInterest).where(eq(userInterest.userId, userId));
  await db.delete(mentorProfile).where(eq(mentorProfile.userId, userId));
  await db
    .delete(supervisorProfile)
    .where(eq(supervisorProfile.userId, userId));
  await db.delete(studentProfile).where(eq(studentProfile.userId, userId));
  await db.delete(users).where(eq(users.id, userId));

  return { msg: "User deleted successfully", data: null };
}
