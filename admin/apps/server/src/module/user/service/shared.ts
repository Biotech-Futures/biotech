import db from "@/lib/db.js";
import { desc, eq, sql } from "drizzle-orm";
import {
  adminUser,
  areasOfInterest,
  mentorProfile,
  roleAssignmentHistory,
  roles,
  studentProfile,
  supervisorProfile,
  tracks,
  userInterest,
  users,
} from "@/schema/index.js";
import { auth } from "@/lib/auth.js";
import type { CreateUserInput, UpdateUserInput } from "../schema.js";
import type { User } from "../type.js";
import { DEFAULT_MENTOR_PROFILE } from "../const.js";

const normalizeInterestDescriptions = (interests: string[] | undefined) =>
  Array.from(
    new Set((interests ?? []).map((item) => item.trim()).filter(Boolean)),
  );

export async function resolveRoleId(
  executor: any,
  roleName: string,
): Promise<number> {
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

export async function syncUserInterests(
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

export async function upsertStudentProfile(
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

export async function upsertSupervisorProfile(
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

export async function upsertMentorProfile(
  executor: any,
  userId: number,
  values: Partial<typeof mentorProfile.$inferInsert> = {},
) {
  const existing = await executor
    .select({ userId: mentorProfile.userId })
    .from(mentorProfile)
    .where(eq(mentorProfile.userId, userId));

  const nextValues = { ...DEFAULT_MENTOR_PROFILE, ...values };

  if (existing[0]) {
    await executor
      .update(mentorProfile)
      .set(nextValues)
      .where(eq(mentorProfile.userId, userId));
    return;
  }

  await executor
    .insert(mentorProfile)
    .values({ userId, ...nextValues });
}

export async function ensureAdminEmailAvailable(
  email: string,
): Promise<string | null> {
  const existingAdmin = await db
    .select({ id: adminUser.id })
    .from(adminUser)
    .where(eq(adminUser.email, email));

  return existingAdmin.length > 0 ? "Admin account email already exists" : null;
}

export async function createAdminRelation(
  input: CreateUserInput,
  userId: number,
) {
  const adminTracks = Array.from(
    new Set(
      (input.adminTracks ?? []).map((track) => track.trim()).filter(Boolean),
    ),
  );
  const createdAuthUser = await auth.api.createUser({
    body: {
      email: input.email,
      name: `${input.firstName} ${input.lastName}`.trim(),
      role: "admin",
      data: {
        userId,
        tracks: adminTracks,
      },
    },
  });
  const createdAuthUserId =
    (createdAuthUser as any)?.user?.id ?? (createdAuthUser as any)?.id;
  if (!createdAuthUserId) throw new Error("Failed to create auth user");

  await db
    .update(adminUser)
    .set({ emailVerified: true, tracks: adminTracks })
    .where(eq(adminUser.id, String(createdAuthUserId)));
}

export async function rollbackCreatedUser(userId: number) {
  await db.transaction(async (tx) => {
    await tx
      .delete(roleAssignmentHistory)
      .where(eq(roleAssignmentHistory.userId, userId));
    await tx.delete(users).where(eq(users.id, userId));
  });
}

export async function deleteStudentDetails(executor: any, userId: number) {
  await executor
    .delete(studentProfile)
    .where(eq(studentProfile.userId, userId));
}

export async function deleteUserInterests(executor: any, userId: number) {
  await executor.delete(userInterest).where(eq(userInterest.userId, userId));
}

export const userSelect = {
  id: users.id,
  firstName: users.firstName,
  lastName: users.lastName,
  email: users.email,
  role: sql<
    string | null
  >`(SELECT r.role_name FROM role_assignment_history rah JOIN roles r ON r.id = rah.role_id WHERE rah.user_id = ${users.id} AND rah.valid_to IS NULL ORDER BY rah.valid_from DESC, rah.id DESC LIMIT 1)`,
  track: tracks.trackName,
  groupName: sql<
    string | null
  >`(SELECT g.group_name FROM group_membership gm JOIN groups g ON g.id = gm.group_id WHERE gm.user_id = ${users.id} AND gm.left_at IS NULL AND g.deleted_at IS NULL ORDER BY gm.joined_at DESC, gm.id DESC LIMIT 1)`,
  schoolName: sql<
    string | null
  >`COALESCE(${studentProfile.schoolName}, ${supervisorProfile.schoolName})`,
  mentorBackground: mentorProfile.background,
  mentorInstitution: mentorProfile.institution,
  mentorReason: mentorProfile.mentorReason,
  mentorMaxGroupCount: mentorProfile.maxGroupCount,
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

export function baseUserQuery() {
  return db
    .select(userSelect)
    .from(users)
    .leftJoin(tracks, eq(tracks.id, users.trackId))
    .leftJoin(studentProfile, eq(studentProfile.userId, users.id))
    .leftJoin(supervisorProfile, eq(supervisorProfile.userId, users.id))
    .leftJoin(mentorProfile, eq(mentorProfile.userId, users.id))
    .orderBy(desc(users.dateJoined));
}

export async function fetchUserById(id: number): Promise<User | null> {
  const rows = await baseUserQuery().where(eq(users.id, id));
  return (rows[0] as User) ?? null;
}
