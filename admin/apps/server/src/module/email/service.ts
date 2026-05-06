import db from "@/lib/db.js";
import { sendEmail } from "@/lib/email.js";
import { and, eq, isNull } from "drizzle-orm";
import { groupMembership, groups, users } from "@/schema/index.js";

export type SendGroupEmailInput = {
  groupId: string | number;
  userId: string | number;
  subject: string;
};

export type GroupEmailRecipient = {
  id: number;
  name: string;
  email: string;
};

function parseId(value: string | number) {
  const id = Number(value);
  return Number.isFinite(id) ? id : null;
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderGroupEmailHtml(params: {
  groupName: string;
  subject: string;
  senderName: string;
}) {
  return `<!doctype html>
<html>
  <body style="margin:0;background:#f5f7fb;font-family:Arial,Helvetica,sans-serif;color:#172033;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f5f7fb;padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:#ffffff;border:1px solid #e3e8f2;border-radius:8px;overflow:hidden;">
            <tr>
              <td style="background:#17324d;color:#ffffff;padding:24px 28px;">
                <div style="font-size:13px;line-height:18px;opacity:.82;">${escapeHtml(params.groupName)}</div>
                <h1 style="margin:8px 0 0;font-size:24px;line-height:32px;font-weight:700;">${escapeHtml(params.subject)}</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:28px;font-size:15px;line-height:24px;">
                <p style="margin:0 0 16px;">Hello,</p>
                <p style="margin:0 0 16px;">${escapeHtml(params.senderName)} sent an update for ${escapeHtml(params.groupName)}.</p>
                <p style="margin:0;">Please sign in to view the latest group information.</p>
              </td>
            </tr>
            <tr>
              <td style="border-top:1px solid #e3e8f2;padding:18px 28px;color:#667085;font-size:12px;line-height:18px;">
                You are receiving this because you are part of ${escapeHtml(params.groupName)}.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>`;
}

export async function sendGroupEmail(input: SendGroupEmailInput) {
  const groupId = parseId(input.groupId);
  const userId = parseId(input.userId);
  const subject = input.subject.trim();

  if (!groupId) return { msg: "Group not found", data: null };
  if (!userId) return { msg: "Sender not found", data: null };
  if (!subject) return { msg: "Email subject is required", data: null };

  const groupRows = await db
    .select({ id: groups.id, name: groups.groupName })
    .from(groups)
    .where(and(eq(groups.id, groupId), isNull(groups.deletedAt)))
    .limit(1);

  const group = groupRows[0];
  if (!group) return { msg: "Group not found", data: null };

  const senderMembershipRows = await db
    .select({
      id: groupMembership.id,
      firstName: users.firstName,
      lastName: users.lastName,
    })
    .from(groupMembership)
    .innerJoin(users, eq(users.id, groupMembership.userId))
    .where(
      and(
        eq(groupMembership.groupId, groupId),
        eq(groupMembership.userId, userId),
        isNull(groupMembership.leftAt),
      ),
    )
    .limit(1);

  if (!senderMembershipRows[0]) {
    return { msg: "Sender is not an active group member", data: null };
  }

  const recipientConditions = [
    eq(groupMembership.groupId, groupId),
    isNull(groupMembership.leftAt),
    eq(users.isActive, true),
  ];

  const recipientRows = await db
    .select({
      id: users.id,
      firstName: users.firstName,
      lastName: users.lastName,
      email: users.email,
    })
    .from(groupMembership)
    .innerJoin(users, eq(users.id, groupMembership.userId))
    .where(and(...recipientConditions));

  const recipients: GroupEmailRecipient[] = recipientRows
    .filter((recipient) => recipient.id !== userId)
    .map((recipient) => ({
      id: recipient.id,
      name: `${recipient.firstName} ${recipient.lastName}`.trim(),
      email: recipient.email,
    }));

  if (recipients.length === 0) {
    return { msg: "No active group email recipients found", data: null };
  }

  const sender = senderMembershipRows[0];
  const senderName = `${sender.firstName} ${sender.lastName}`.trim();
  const text = [
    "Hello,",
    "",
    `${senderName} sent an update for ${group.name}.`,
    "Please sign in to view the latest group information.",
  ].join("\n");

  const sendResult = await sendEmail({
    to: recipients.map((recipient) => recipient.email),
    subject,
    text,
    html: renderGroupEmailHtml({
      groupName: group.name,
      subject,
      senderName,
    }),
  });

  return {
    msg: "Group email sent successfully",
    data: {
      groupId: String(group.id),
      groupName: group.name,
      emailMessageId: sendResult.messageId ?? null,
      recipientCount: recipients.length,
      recipients,
    },
  };
}
