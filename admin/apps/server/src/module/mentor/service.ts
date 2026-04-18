import db from "@/lib/db.js";
import { and, eq, isNull, max, sql } from "drizzle-orm";
import {
  groupMembership,
  mentorInterest,
  areasOfInterest,
  mentorProfile,
  messages,
  tracks,
  users,
} from "@/drizzle/schema.js";

export async function getMentorList() {
  // 1. Count currently assigned groups per mentor
  const assignedCountRows = await db
    .select({ mentorUserId: groupMembership.userId })
    .from(groupMembership)
    .where(
      and(
        eq(groupMembership.membershipRole, "mentor"),
        isNull(groupMembership.leftAt),
      ),
    );

  const assignedCountByMentor = new Map<number, number>();
  for (const row of assignedCountRows) {
    assignedCountByMentor.set(
      row.mentorUserId,
      (assignedCountByMentor.get(row.mentorUserId) ?? 0) + 1,
    );
  }

  // 2. Fetch all mentor base info
  const mentorRows = await db
    .select({
      mentorId: mentorProfile.userId,
      firstName: users.firstName,
      lastName: users.lastName,
      email: users.email,
      isActive: users.isActive,
      institution: mentorProfile.institution,
      maxGroupCount: mentorProfile.maxGroupCount,
      trackCode: tracks.trackCode,
    })
    .from(mentorProfile)
    .innerJoin(users, eq(users.id, mentorProfile.userId))
    .innerJoin(tracks, eq(tracks.id, users.trackId));

  if (mentorRows.length === 0) return [];

  const mentorIds = mentorRows.map((m) => m.mentorId);

  // 3. Last message sent by each mentor (excluding deleted messages)
  const lastMessageRows = await db
    .select({
      senderUserId: messages.senderUserId,
      lastMessageAt: max(messages.sentAt),
    })
    .from(messages)
    .where(
      and(
        isNull(messages.deletedAt),
        sql`${messages.senderUserId} = ANY(${sql.raw(`ARRAY[${mentorIds.join(",")}]::bigint[]`)})`,
      ),
    )
    .groupBy(messages.senderUserId);

  const lastMessageByMentor = new Map(
    lastMessageRows.map((r) => [r.senderUserId, r.lastMessageAt]),
  );

  // 4. Interests per mentor
  const interestRows = await db
    .select({
      mentorUserId: mentorInterest.mentorUserId,
      interest: areasOfInterest.interestDesc,
    })
    .from(mentorInterest)
    .innerJoin(areasOfInterest, eq(areasOfInterest.id, mentorInterest.interestId))
    .where(
      sql`${mentorInterest.mentorUserId} = ANY(${sql.raw(`ARRAY[${mentorIds.join(",")}]::bigint[]`)})`,
    );

  const interestsByMentor = new Map<number, string[]>();
  for (const row of interestRows) {
    const list = interestsByMentor.get(row.mentorUserId) ?? [];
    list.push(row.interest);
    interestsByMentor.set(row.mentorUserId, list);
  }

  return mentorRows.map((m) => {
    const currentAssignedCount = assignedCountByMentor.get(m.mentorId) ?? 0;
    return {
      mentorId: m.mentorId,
      firstName: m.firstName,
      lastName: m.lastName,
      name: `${m.firstName} ${m.lastName}`.trim(),
      email: m.email,
      isActive: m.isActive,
      institution: m.institution,
      trackCode: m.trackCode,
      maxGroupCount: m.maxGroupCount,
      currentAssignedCount,
      remainingCapacity: m.maxGroupCount - currentAssignedCount,
      interests: interestsByMentor.get(m.mentorId) ?? [],
      lastMessageAt: lastMessageByMentor.get(m.mentorId) ?? null,
    };
  });
}

export async function setMentorActive(mentorId: number, isActive: boolean) {
  await db
    .update(users)
    .set({ isActive })
    .where(eq(users.id, mentorId));
  return { mentorId, isActive };
}
