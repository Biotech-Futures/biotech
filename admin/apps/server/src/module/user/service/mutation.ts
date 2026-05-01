import db from "@/lib/db.js";
import { and, eq, isNull } from "drizzle-orm";
import {
  mentorProfile,
  roleAssignmentHistory,
  studentProfile,
  supervisorProfile,
  tracks,
  userInterest,
  users,
} from "@/schema/index.js";
import type {
  BulkCreateUsersInput,
  CreateUserInput,
  UpdateStatusInput,
  UpdateUserInput,
} from "../schema.js";
import type { AddUsersByRoleResult, User } from "../type.js";
import { STATUS } from "../const.js";
import {
  createAdminRelation,
  deleteStudentDetails,
  deleteUserInterests,
  ensureAdminEmailAvailable,
  fetchUserById,
  resolveRoleId,
  rollbackCreatedUser,
  syncUserInterests,
  upsertMentorProfile,
  upsertStudentProfile,
  upsertSupervisorProfile,
} from "./shared.js";

async function addUsersByRole(
  inputs: CreateUserInput[],
): Promise<AddUsersByRoleResult[]> {
  const results: AddUsersByRoleResult[] = [];

  for (const input of inputs) {
    const existing = await db
      .select({ id: users.id })
      .from(users)
      .where(eq(users.email, input.email));
    if (existing.length > 0) {
      results.push({ input, msg: "Email already exists", data: null });
      continue;
    }

    const normalizedTrack = input.track?.trim();
    if (input.role !== "admin" && !normalizedTrack) {
      results.push({ input, msg: "Track is required", data: null });
      continue;
    }

    if (input.role === "admin") {
      const adminTracks = (input.adminTracks ?? [])
        .map((track) => track.trim())
        .filter(Boolean);
      if (!adminTracks.length) {
        results.push({
          input,
          msg: "At least one admin track is required for admin users",
          data: null,
        });
        continue;
      }
    }

    if (input.role === "student") {
      if (!input.schoolName?.trim()) {
        results.push({
          input,
          msg: "School is required for student users",
          data: null,
        });
        continue;
      }
      if (!input.yearLevel) {
        results.push({
          input,
          msg: "Year level is required for student users",
          data: null,
        });
        continue;
      }
    }

    if (input.role === "mentor") {
      if (!input.mentorInstitution?.trim()) {
        results.push({
          input,
          msg: "Institution is required for mentor users",
          data: null,
        });
        continue;
      }
      if (!input.mentorReason?.trim()) {
        results.push({
          input,
          msg: "Mentor reason is required for mentor users",
          data: null,
        });
        continue;
      }
      if (input.mentorMaxGroupCount === undefined) {
        results.push({
          input,
          msg: "Max group count is required for mentor users",
          data: null,
        });
        continue;
      }
    }

    if (input.role === "student" || input.role === "mentor") {
      if (!input.interests?.length) {
        results.push({
          input,
          msg: `At least one interest is required for ${input.role} users`,
          data: null,
        });
        continue;
      }
    }

    let trackId: number | null = null;
    if (normalizedTrack) {
      const trackRow = await db
        .select({ id: tracks.id })
        .from(tracks)
        .where(eq(tracks.trackName, normalizedTrack));
      if (trackRow.length === 0) {
        results.push({
          input,
          msg: `Track "${normalizedTrack}" not found`,
          data: null,
        });
        continue;
      }
      trackId = trackRow[0].id;
    }

    const roleId = await resolveRoleId(db, input.role);

    if (input.role === "admin") {
      const adminEmailError = await ensureAdminEmailAvailable(input.email);
      if (adminEmailError) {
        results.push({
          input,
          msg: adminEmailError,
          data: null,
        });
        continue;
      }
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
          accountStatus:
            (input.active ?? true) ? STATUS.ACTIVE : STATUS.INVITED,
          dateJoined: now,
          invitedAt: now,
          activatedAt: input.active ? now : null,
          lastLogin: null,
          trackId,
        })
        .returning({ id: users.id });

      const userId = newUser.id;

      newUserId = userId;

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
      }

      if (input.role === "supervisor") {
        await upsertSupervisorProfile(
          tx,
          userId,
          input.supervisorSchoolName?.trim() ?? "",
        );
      }

      if (input.role === "mentor") {
        await upsertMentorProfile(tx, userId, {
          background: input.mentorBackground?.trim() || null,
          institution: input.mentorInstitution?.trim() ?? "",
          mentorReason: input.mentorReason?.trim() ?? "",
          maxGroupCount: input.mentorMaxGroupCount ?? 0,
        });
      }

      if (input.role === "student" || input.role === "mentor") {
        await syncUserInterests(tx, userId, input.interests);
      }
    });

    if (!newUserId) {
      results.push({ input, msg: "Failed to create user", data: null });
      continue;
    }

    const createdPublicUserId = newUserId;

    if (input.role === "admin") {
      try {
        await createAdminRelation(input, createdPublicUserId);
      } catch (error) {
        await rollbackCreatedUser(createdPublicUserId);

        results.push({
          input,
          msg:
            error instanceof Error
              ? error.message
              : "Unable to create admin auth account",
          data: null,
        });
        continue;
      }
    }

    const created = await fetchUserById(newUserId);
    results.push({ input, msg: "User created successfully", data: created });
  }

  return results;
}

export async function createUser(input: CreateUserInput) {
  const [result] = await addUsersByRole([input]);
  return { msg: result.msg, data: result.data };
}

export async function bulkCreateUsers(
  input: BulkCreateUsersInput,
  _adminUserId: string,
) {
  const created: User[] = [];
  const skipped: string[] = [];

  const results = await addUsersByRole(input.users);

  for (const result of results) {
    if (result.data) {
      created.push(result.data as User);
    } else {
      skipped.push(result.input.email);
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
  if (
    input.email !== undefined &&
    input.email.trim().toLowerCase() !== existing.email.trim().toLowerCase()
  ) {
    return { msg: "Email cannot be changed", data: null };
  }

  const nextInterests = input.interests ?? existing.interests;

  if (nextRole === "student") {
    const nextSchoolName = input.schoolName ?? existing.schoolName;
    const nextYearLevel = input.yearLevel ?? existing.yearLevel;
    if (!nextSchoolName?.trim())
      return { msg: "School is required for student users", data: null };
    if (!nextYearLevel)
      return { msg: "Year level is required for student users", data: null };
  }

  if (
    (nextRole === "student" || nextRole === "mentor") &&
    !nextInterests.length
  )
    return {
      msg: `At least one interest is required for ${nextRole} users`,
      data: null,
    };

  if (nextRole === "mentor") {
    const nextInstitution =
      input.mentorInstitution ?? existing.mentorInstitution;
    const nextReason = input.mentorReason ?? existing.mentorReason;
    const nextMaxGroupCount =
      input.mentorMaxGroupCount ?? existing.mentorMaxGroupCount;
    if (!nextInstitution?.trim())
      return { msg: "Institution is required for mentor users", data: null };
    if (!nextReason?.trim())
      return { msg: "Mentor reason is required for mentor users", data: null };
    if (nextMaxGroupCount === null || nextMaxGroupCount === undefined)
      return { msg: "Max group count is required for mentor users", data: null };
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
      } else if (existing.role === "student") {
        await deleteStudentDetails(tx, userId);
      }

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

      if (nextRole === "mentor") {
        await upsertMentorProfile(tx, userId, {
          background:
            input.mentorBackground !== undefined
              ? input.mentorBackground?.trim() || null
              : existing.mentorBackground,
          institution:
            input.mentorInstitution?.trim() ??
            existing.mentorInstitution ??
            "",
          mentorReason:
            input.mentorReason?.trim() ?? existing.mentorReason ?? "",
          maxGroupCount:
            input.mentorMaxGroupCount ?? existing.mentorMaxGroupCount ?? 0,
        });
      } else if (existing.role === "mentor" && nextRole !== "mentor") {
        await tx.delete(mentorProfile).where(eq(mentorProfile.userId, userId));
      }

      if (nextRole === "student" || nextRole === "mentor") {
        await syncUserInterests(tx, userId, nextInterests);
      } else if (existing.role === "student" || existing.role === "mentor") {
        await deleteUserInterests(tx, userId);
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
