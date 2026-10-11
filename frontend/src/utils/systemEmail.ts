/**
 * @file systemEmail.ts
 * @description Zod schemas for the admin system-email endpoints.
 *
 * These emails are the account-critical ones (login codes, password resets,
 * reminders). The boundary is therefore validated rather than trusted: if the
 * server ever sends a template without its merge tags or enabled flag, we want
 * the admin page to fail loudly instead of rendering a switch that posts
 * `undefined` and silently re-enables a login email.
 *
 * Shapes mirror the service serialisers in
 * `backend/apps/admin/services/system_email.py`.
 */
import { z } from 'zod'

// ---------------------------------------------------------------------------
// Merge tags
// ---------------------------------------------------------------------------

/**
 * One `{{ tag_name }}` an email type can fill. `html` marks tags whose sample
 * value contains markup, so the palette can show it as HTML rather than
 * escaping it.
 */
export const systemEmailMergeTagSchema = z.object({
  name: z.string().min(1),
  description: z.string(),
  sample: z.string(),
  html: z.boolean()
})

export type SystemEmailMergeTag = z.infer<typeof systemEmailMergeTagSchema>

// ---------------------------------------------------------------------------
// Templates
// ---------------------------------------------------------------------------

/**
 * A registry email type merged with its saved override. `subject`/`body` are
 * the saved wording and are empty when the email still uses its built-in
 * template file; `usingSavedContent` is the authoritative flag for that.
 * `defaultSubject`/`defaultBody` mirror the built-in wording with merge tags
 * left as `{{ tag }}` (and only the content, not the branded layout), so the
 * editor can pre-fill it and a saved edit still fills in each recipient's data.
 */
export const systemEmailTemplateSchema = z.object({
  key: z.string().min(1),
  name: z.string(),
  description: z.string(),
  enabled: z.boolean(),
  locked: z.boolean(),
  /** Who a whole group's email goes to, e.g. its students in To. Empty for an email to one person. */
  delivery: z.string().optional(),
  usingSavedContent: z.boolean(),
  defaultSubject: z.string(),
  defaultBody: z.string(),
  subject: z.string(),
  body: z.string(),
  updatedBy: z.string().nullable(),
  updatedAt: z.string().nullable(),
  mergeTags: z.array(systemEmailMergeTagSchema),
  /** The mailbox it goes from, e.g. "info". */
  sender: z.string(),
  /** The mailboxes it could go from: those the server can sign in to. */
  senders: z.array(z.object({ key: z.string(), address: z.string() }))
})

export type SystemEmailTemplate = z.infer<typeof systemEmailTemplateSchema>

export const systemEmailTemplateListSchema = z.object({
  items: z.array(systemEmailTemplateSchema)
})

// ---------------------------------------------------------------------------
// Global settings
// ---------------------------------------------------------------------------

export const systemEmailSettingsSchema = z.object({
  emailsEnabled: z.boolean(),
  updatedAt: z.string().nullable()
})

export type SystemEmailSettings = z.infer<typeof systemEmailSettingsSchema>

// ---------------------------------------------------------------------------
// Preview / test send
// ---------------------------------------------------------------------------

export const systemEmailPreviewSchema = z.object({
  key: z.string(),
  subject: z.string(),
  html: z.string(),
  text: z.string(),
  /** The files the one picked would get with it, as on Release Results. */
  attachments: z.array(z.string()).optional()
})

export type SystemEmailPreview = z.infer<typeof systemEmailPreviewSchema>

export const systemEmailTestSendSchema = z.object({
  key: z.string(),
  sentTo: z.string(),
  // The address it went from, where a test that can't be delivered comes back to.
  sentFrom: z.string().optional()
})

export type SystemEmailTestSend = z.infer<typeof systemEmailTestSendSchema>

// Who a test can be "of": the email's groups ("BTF01") or people ("(BTF01) Pat
// Lee"). Null when it has nothing of a person's own.
export const systemEmailTestRecipientsSchema = z.object({
  key: z.string(),
  recipients: z.array(z.object({ value: z.string(), label: z.string() })).nullable()
})

export type SystemEmailTestRecipient = NonNullable<
  z.infer<typeof systemEmailTestRecipientsSchema>['recipients']
>[number]

// The Log: each email's last send and who sent it, where mail it can't
// deliver comes back to, and who its latest sends couldn't reach, newest first
// ("amy@x.com (BTF07, Amy Chen)", as Notify Finalists lists them).
export const systemEmailLogSchema = z.array(
  z.object({
    key: z.string(),
    name: z.string(),
    lastSentAt: z.string().nullable(),
    lastSentBy: z.string(),
    sentFrom: z.string(),
    // One email per group, so the rest of a group still gets it.
    toGroups: z.boolean(),
    missed: z.array(
      z.object({
        at: z.string(),
        people: z.array(z.object({ who: z.string(), reason: z.string() }))
      })
    )
  })
)

export type SystemEmailLogEntry = z.infer<typeof systemEmailLogSchema>[number]

// How many people sends couldn't reach since an admin last looked at Failed
// Sending Emails: the red count on its button.
export const systemEmailUnseenSchema = z.object({ unseen: z.number() })

// ---------------------------------------------------------------------------
// Request payloads
// ---------------------------------------------------------------------------

/**
 * PATCH body for one email. Every field is optional so saving wording never
 * disturbs the enabled toggle, and vice versa.
 */
export interface SystemEmailTemplateUpdatePayload {
  subject?: string
  body?: string
  enabled?: boolean
  /** A key of the template's `senders`. */
  sender?: string
}

/** Optional unsaved wording for preview/test-send. */
export interface SystemEmailPreviewPayload {
  subject?: string
  body?: string
}

/**
 * A test send: the preview's unsaved wording, where it goes (the admin's own
 * address when absent) and whose details it carries (the samples when absent).
 */
export interface SystemEmailTestSendPayload extends SystemEmailPreviewPayload {
  to?: string
  /** A `value` from the email's test recipients. */
  of?: string
}

/**
 * An email's name split from who it goes to, when it ends with that, as in
 * "Guardian consent sent (to student)". That part is shown in normal weight.
 */
export const nameParts = (name: string): { title: string; to: string } => {
  const match = /^(.*\S)\s+(\(to [^)]*\))$/.exec(name)
  return match ? { title: match[1], to: match[2] } : { title: name, to: '' }
}

/**
 * Merge tags are stored and sent with the surrounding braces, e.g.
 * `"{{ first_name }}"`, so callers only ever hand the editor a complete token.
 */
export const mergeTagToken = (name: string): string => `{{ ${name} }}`
