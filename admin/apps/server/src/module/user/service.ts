import db from "@/lib/db.js";
import { and, eq, ilike, isNull, or, sql } from "drizzle-orm";
import {
  mentorProfile,
  roles,
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
  isActive: boolean;
  accountStatus: string;
  invitedAt: string | null;
  activatedAt: string | null;
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

// Use high-resolution timestamp to generate unique bigint IDs for admin-scale writes
const generateId = () => Date.now() * 1000 + Math.floor(Math.random() * 999);

const userSelect = {
  id: users.id,
  firstName: users.firstName,
  lastName: users.lastName,
  email: users.email,
  role: roles.slug,
  track: tracks.trackCode,
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
    .leftJoin(tracks, eq(tracks.id, users.trackId));
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

// ─── Mutations ───────────────────────────────────────────────────────────────

export async function createUser(input: CreateUserInput, adminUserId: string) {
  const existing = await db
    .select({ id: users.id })
    .from(users)
    .where(eq(users.email, input.email));
  if (existing.length > 0) return { msg: "Email already exists", data: null };

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

  await db.insert(users).values({
    id: userId,
    email: input.email,
    firstName: input.firstName,
    lastName: input.lastName,
    isActive: true,
    trackId: trackRow[0].id,
    accountStatus: "active",
    invitedAt: now,
    adminUserId,
  });

  await db.insert(userRoleAssignment).values({
    id: generateId(),
    userId,
    roleId: roleRow[0].id,
    validFrom: now,
    validTo: null,
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

  if (input.firstName !== undefined) userUpdates.firstName = input.firstName;
  if (input.lastName !== undefined) userUpdates.lastName = input.lastName;
  if (input.email !== undefined) userUpdates.email = input.email;

  if (input.track !== undefined) {
    const trackRow = await db
      .select({ id: tracks.id })
      .from(tracks)
      .where(eq(tracks.trackCode, input.track));
    if (trackRow.length === 0)
      return { msg: `Track "${input.track}" not found`, data: null };
    userUpdates.trackId = trackRow[0].id;
  }

  if (Object.keys(userUpdates).length > 0) {
    await db.update(users).set(userUpdates).where(eq(users.id, userId));
  }

  if (input.role !== undefined && input.role !== existing.role) {
    const roleRow = await db
      .select({ id: roles.id })
      .from(roles)
      .where(eq(roles.slug, input.role));
    if (roleRow.length === 0)
      return { msg: `Role "${input.role}" not found`, data: null };

    await db
      .update(userRoleAssignment)
      .set({ validTo: now })
      .where(
        and(
          eq(userRoleAssignment.userId, userId),
          isNull(userRoleAssignment.validTo),
        ),
      );

    await db.insert(userRoleAssignment).values({
      id: generateId(),
      userId,
      roleId: roleRow[0].id,
      validFrom: now,
      validTo: null,
    });
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
            name: user.name,
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
