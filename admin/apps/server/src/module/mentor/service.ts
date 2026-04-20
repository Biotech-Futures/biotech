import db from "@/lib/db.js";
import { and, eq, isNull, max, sql } from "drizzle-orm";
import {
  groupMembers,
  mentorProfile,
  mentorCertificate,
  certificateType,
  messages,
  tracks,
  users,
  background,
  studentInterest,
  areasOfInterest,
} from "@/schema/index.js";

export async function getMentorList() {
  // 1. Count currently assigned groups per mentor
  const assignedCountRows = await db
    .select({ mentorUserId: groupMembers.userId })
    .from(groupMembers)
    .innerJoin(mentorProfile, eq(mentorProfile.userId, groupMembers.userId));

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
      maxGrpCnt: mentorProfile.maxGrpCnt,
      trackCode: tracks.trackName,
      backgroundDesc: background.backgroundDescUniqueField,
    })
    .from(mentorProfile)
    .innerJoin(users, eq(users.id, mentorProfile.userId))
    .innerJoin(tracks, eq(tracks.id, users.trackId))
    .innerJoin(background, eq(background.id, mentorProfile.backgroundId));

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

  // 4. Certificates per mentor
  const certificateRows = await db
    .select({
      mentorProfileId: mentorCertificate.mentorProfileId,
      certificateTypeName: certificateType.certificateType,
      certificateNumber: mentorCertificate.certificateNumber,
      issuedBy: mentorCertificate.issuedBy,
      issuedAt: mentorCertificate.issuedAt,
      expiresAt: mentorCertificate.expiresAt,
      fileUrl: mentorCertificate.fileUrl,
      verified: mentorCertificate.verified,
    })
    .from(mentorCertificate)
    .innerJoin(certificateType, eq(certificateType.id, mentorCertificate.certificateTypeId))
    .where(
      sql`${mentorCertificate.mentorProfileId} = ANY(${sql.raw(`ARRAY[${mentorIds.join(",")}]::bigint[]`)})`,
    );

  const certificatesByMentor = new Map<number, typeof certificateRows>();
  for (const row of certificateRows) {
    const list = certificatesByMentor.get(row.mentorProfileId) ?? [];
    list.push(row);
    certificatesByMentor.set(row.mentorProfileId, list);
  }

  // 5. Interests per mentor
  const interestRows = await db
    .select({
      userId: studentInterest.userId,
      interestDesc: areasOfInterest.interestDesc,
    })
    .from(studentInterest)
    .innerJoin(areasOfInterest, eq(areasOfInterest.id, studentInterest.interestId))
    .where(
      sql`${studentInterest.userId} = ANY(${sql.raw(`ARRAY[${mentorIds.join(",")}]::bigint[]`)})`,
    );

  const interestsByMentor = new Map<number, string[]>();
  for (const row of interestRows) {
    const list = interestsByMentor.get(row.userId) ?? [];
    list.push(row.interestDesc);
    interestsByMentor.set(row.userId, list);
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
      background: m.backgroundDesc,
      maxGroupCount: m.maxGrpCnt,
      currentAssignedCount,
      remainingCapacity: m.maxGrpCnt - currentAssignedCount,
      interests: interestsByMentor.get(m.mentorId) ?? [],
      lastMessageAt: lastMessageByMentor.get(m.mentorId) ?? null,
      availability: [],
      certificates: certificatesByMentor.get(m.mentorId) ?? [],
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
