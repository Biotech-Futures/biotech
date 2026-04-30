import db from "@/lib/db.js";
import { sendEmail } from "@/lib/email.js";
import {
  announcements,
  announcementAudience,
  roles,
  roleAssignmentHistory,
  tracks,
  users,
} from "@/schema/index.js";
import {
  and,
  asc,
  desc,
  eq,
  ilike,
  inArray,
  isNull,
  isNotNull,
  or,
  sql,
} from "drizzle-orm";
import type {
  QueryAnnouncementsInput,
  CreateAnnouncementInput,
  UpdateAnnouncementInput,
} from "./schema.js";

// ─── helpers ────────────────────────────────────────────────────────────────

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function stripHtml(html: string): string {
  return html
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function buildExcerpt(html: string, maxChars = 200): string {
  const text = stripHtml(html);
  return text.length > maxChars ? text.slice(0, maxChars) + "…" : text;
}

function renderAnnouncementEmailHtml(title: string, excerpt: string, detailUrl: string) {
  return `<!doctype html>
<html>
  <body style="margin:0;background:#f5f7fb;font-family:Arial,Helvetica,sans-serif;color:#172033;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f5f7fb;padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:#ffffff;border:1px solid #e3e8f2;border-radius:8px;overflow:hidden;">
            <tr>
              <td style="background:#17324d;color:#ffffff;padding:24px 28px;">
                <div style="font-size:13px;opacity:.82;">BioTech Platform</div>
                <h1 style="margin:8px 0 0;font-size:24px;line-height:32px;font-weight:700;">${escapeHtml(title)}</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:28px;font-size:15px;line-height:24px;">
                <p style="margin:0 0 16px;">${escapeHtml(excerpt)}</p>
                <p style="margin:0;"><a href="${escapeHtml(detailUrl)}" style="color:#17324d;">View full announcement →</a></p>
              </td>
            </tr>
            <tr>
              <td style="border-top:1px solid #e3e8f2;padding:18px 28px;color:#667085;font-size:12px;">
                You are receiving this because you are part of the BioTech platform.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>`;
}

async function resolveRecipientEmails(
  announcementId: number,
  visibilityScope: string,
): Promise<string[]> {
  if (visibilityScope === "global") {
    const rows = await db
      .select({ email: users.email })
      .from(users)
      .where(eq(users.isActive, true));
    return rows.map((r) => r.email);
  }

  const audienceRows = await db
    .select({ roleId: announcementAudience.roleId, trackId: announcementAudience.trackId })
    .from(announcementAudience)
    .where(eq(announcementAudience.announcementId, announcementId));

  if (audienceRows.length === 0) return [];

  if (visibilityScope === "track_based") {
    const trackIds = audienceRows
      .map((r) => r.trackId)
      .filter((id): id is number => id !== null);
    if (trackIds.length === 0) return [];
    const rows = await db
      .select({ email: users.email })
      .from(users)
      .where(
        and(
          eq(users.isActive, true),
          inArray(users.trackId, trackIds),
        ),
      );
    return rows.map((r) => r.email);
  }

  if (visibilityScope === "role_based") {
    const roleIds = audienceRows
      .map((r) => r.roleId)
      .filter((id): id is number => id !== null);
    if (roleIds.length === 0) return [];
    const now = new Date().toISOString();
    const rows = await db
      .select({ email: users.email })
      .from(users)
      .innerJoin(roleAssignmentHistory, eq(roleAssignmentHistory.userId, users.id))
      .where(
        and(
          eq(users.isActive, true),
          inArray(roleAssignmentHistory.roleId, roleIds),
          or(
            isNull(roleAssignmentHistory.validTo),
            sql`${roleAssignmentHistory.validTo} > ${now}`,
          ),
        ),
      );
    const unique = [...new Set(rows.map((r) => r.email))];
    return unique;
  }

  return [];
}

async function syncAudience(
  announcementId: number,
  visibilityScope: string,
  trackId: number | null | undefined,
  roleIds: number[] | undefined,
) {
  await db
    .delete(announcementAudience)
    .where(eq(announcementAudience.announcementId, announcementId));

  if (visibilityScope === "global") return;

  if (visibilityScope === "track_based" && trackId) {
    await db.insert(announcementAudience).values({
      announcementId,
      trackId,
      roleId: null,
    });
    return;
  }

  if (visibilityScope === "role_based" && roleIds?.length) {
    await db.insert(announcementAudience).values(
      roleIds.map((roleId) => ({
        announcementId,
        roleId,
        trackId: null,
      })),
    );
  }
}

// ─── queries ─────────────────────────────────────────────────────────────────

async function fetchAnnouncement(id: number) {
  const rows = await db
    .select({
      id: announcements.id,
      title: announcements.title,
      body: announcements.body,
      visibilityScope: announcements.visibilityScope,
      publishedAt: announcements.publishedAt,
      archivedAt: announcements.archivedAt,
      authorUserId: announcements.authorUserId,
      trackId: announcements.trackId,
      trackName: tracks.trackName,
    })
    .from(announcements)
    .leftJoin(tracks, eq(tracks.id, announcements.trackId))
    .where(eq(announcements.id, id))
    .limit(1);

  const row = rows[0];
  if (!row) return null;

  const audienceRows = await db
    .select({
      id: announcementAudience.id,
      roleId: announcementAudience.roleId,
      trackId: announcementAudience.trackId,
      roleName: roles.roleName,
    })
    .from(announcementAudience)
    .leftJoin(roles, eq(roles.id, announcementAudience.roleId))
    .where(eq(announcementAudience.announcementId, id));

  return { ...row, audiences: audienceRows };
}

export async function listAnnouncements(params: QueryAnnouncementsInput) {
  const { page, limit, search, archived } = params;
  const offset = (page - 1) * limit;

  const conditions = [];

  if (search) {
    conditions.push(
      or(
        ilike(announcements.title, `%${search}%`),
        ilike(announcements.body, `%${search}%`),
      ),
    );
  }

  if (archived === true) {
    conditions.push(isNotNull(announcements.archivedAt));
  } else if (archived === false || archived === undefined) {
    conditions.push(isNull(announcements.archivedAt));
  }

  const where = conditions.length ? and(...conditions) : undefined;

  const [rows, countResult] = await Promise.all([
    db
      .select({
        id: announcements.id,
        title: announcements.title,
        visibilityScope: announcements.visibilityScope,
        publishedAt: announcements.publishedAt,
        archivedAt: announcements.archivedAt,
        authorUserId: announcements.authorUserId,
        trackId: announcements.trackId,
        trackName: tracks.trackName,
      })
      .from(announcements)
      .leftJoin(tracks, eq(tracks.id, announcements.trackId))
      .where(where)
      .orderBy(desc(announcements.publishedAt))
      .limit(limit)
      .offset(offset),
    db
      .select({ count: sql<number>`cast(count(*) as int)` })
      .from(announcements)
      .where(where),
  ]);

  const allIds = rows.map((r) => r.id);
  const audienceRows =
    allIds.length === 0
      ? []
      : await db
          .select({
            announcementId: announcementAudience.announcementId,
            roleId: announcementAudience.roleId,
            trackId: announcementAudience.trackId,
            roleName: roles.roleName,
          })
          .from(announcementAudience)
          .leftJoin(roles, eq(roles.id, announcementAudience.roleId))
          .where(inArray(announcementAudience.announcementId, allIds));

  const audienceByAnnouncement = new Map<number, typeof audienceRows>();
  for (const a of audienceRows) {
    const list = audienceByAnnouncement.get(a.announcementId) ?? [];
    list.push(a);
    audienceByAnnouncement.set(a.announcementId, list);
  }

  const total = countResult[0]?.count ?? 0;
  const items = rows.map((r) => ({
    ...r,
    audiences: audienceByAnnouncement.get(r.id) ?? [],
  }));

  return {
    msg: "Announcements retrieved successfully",
    data: { items, total, page, limit, hasMore: offset + items.length < total },
  };
}

export async function getAnnouncementById(id: number) {
  const row = await fetchAnnouncement(id);
  if (!row) return { msg: "Announcement not found", data: null };
  return { msg: "Announcement retrieved successfully", data: row };
}

// ─── mutations ───────────────────────────────────────────────────────────────

export async function createAnnouncement(
  input: CreateAnnouncementInput,
  authorUserId: number,
) {
  const now = new Date().toISOString();

  const [inserted] = await db
    .insert(announcements)
    .values({
      title: input.title,
      body: input.body,
      visibilityScope: input.visibility_scope,
      publishedAt: now,
      authorUserId,
      trackId: input.track_id ?? null,
    })
    .returning({ id: announcements.id });

  if (!inserted) throw new Error("Failed to create announcement");

  await syncAudience(
    inserted.id,
    input.visibility_scope,
    input.track_id,
    input.role_ids,
  );

  if (input.send_email) {
    await sendAnnouncementEmail(inserted.id);
  }

  const row = await fetchAnnouncement(inserted.id);
  return { msg: "Announcement created successfully", data: row };
}

export async function updateAnnouncement(
  id: number,
  input: UpdateAnnouncementInput,
) {
  const existing = await fetchAnnouncement(id);
  if (!existing) return { msg: "Announcement not found", data: null };

  const updates: Partial<typeof announcements.$inferInsert> = {};
  if (input.title !== undefined) updates.title = input.title;
  if (input.body !== undefined) updates.body = input.body;
  if (input.visibility_scope !== undefined) updates.visibilityScope = input.visibility_scope;
  if (input.track_id !== undefined) updates.trackId = input.track_id;

  if (Object.keys(updates).length > 0) {
    await db.update(announcements).set(updates).where(eq(announcements.id, id));
  }

  const nextScope = input.visibility_scope ?? existing.visibilityScope;
  const nextTrackId = input.track_id !== undefined ? input.track_id : existing.trackId;

  if (
    input.visibility_scope !== undefined ||
    input.track_id !== undefined ||
    input.role_ids !== undefined
  ) {
    await syncAudience(id, nextScope, nextTrackId, input.role_ids);
  }

  if (input.send_email) {
    await sendAnnouncementEmail(id);
  }

  const row = await fetchAnnouncement(id);
  return { msg: "Announcement updated successfully", data: row };
}

export async function archiveAnnouncement(id: number) {
  const existing = await fetchAnnouncement(id);
  if (!existing) return { msg: "Announcement not found", data: null };
  if (existing.archivedAt) return { msg: "Announcement already archived", data: existing };

  await db
    .update(announcements)
    .set({ archivedAt: new Date().toISOString() })
    .where(eq(announcements.id, id));

  const row = await fetchAnnouncement(id);
  return { msg: "Announcement archived successfully", data: row };
}

export async function sendAnnouncementEmail(announcementId: number) {
  const row = await fetchAnnouncement(announcementId);
  if (!row) return { msg: "Announcement not found", sent: 0 };

  const emails = await resolveRecipientEmails(announcementId, row.visibilityScope);
  if (emails.length === 0) return { msg: "No recipients found", sent: 0 };

  const excerpt = buildExcerpt(row.body);

  const platformUrl = process.env.PLATFORM_URL ?? "";
  const detailUrl = `${platformUrl}/announcements/${announcementId}`;

  await sendEmail({
    to: emails,
    subject: `[BioTech] ${row.title}`,
    text: `${row.title}\n\n${excerpt}\n\nView on the platform: ${detailUrl}`,
    html: renderAnnouncementEmailHtml(row.title, excerpt, detailUrl),
  });

  return { msg: "Email sent successfully", sent: emails.length };
}

export async function listAnnouncementTracks() {
  const rows = await db
    .select({ id: tracks.id, name: tracks.trackName })
    .from(tracks)
    .orderBy(asc(tracks.trackName));
  return { msg: "Tracks retrieved successfully", data: rows };
}

export async function listAnnouncementRoles() {
  const rows = await db
    .select({ id: roles.id, name: roles.roleName })
    .from(roles)
    .orderBy(asc(roles.roleName));
  return { msg: "Roles retrieved successfully", data: rows };
}
