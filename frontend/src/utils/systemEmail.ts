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
  usingSavedContent: z.boolean(),
  defaultSubject: z.string(),
  defaultBody: z.string(),
  subject: z.string(),
  body: z.string(),
  updatedBy: z.string().nullable(),
  updatedAt: z.string().nullable(),
  mergeTags: z.array(systemEmailMergeTagSchema)
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
  text: z.string()
})

export type SystemEmailPreview = z.infer<typeof systemEmailPreviewSchema>

export const systemEmailTestSendSchema = z.object({
  key: z.string(),
  sentTo: z.string()
})

export type SystemEmailTestSend = z.infer<typeof systemEmailTestSendSchema>

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
}

/** Optional unsaved wording for preview/test-send. */
export interface SystemEmailPreviewPayload {
  subject?: string
  body?: string
}

/**
 * Merge tags are stored and sent with the surrounding braces, e.g.
 * `"{{ first_name }}"`, so callers only ever hand the editor a complete token.
 */
export const mergeTagToken = (name: string): string => `{{ ${name} }}`
