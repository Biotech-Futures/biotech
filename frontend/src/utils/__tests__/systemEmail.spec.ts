import { describe, expect, it } from 'vitest'
import {
  mergeTagToken,
  systemEmailPreviewSchema,
  systemEmailSettingsSchema,
  systemEmailTemplateListSchema,
  systemEmailTemplateSchema
} from '@/utils/systemEmail'

const template = {
  key: 'password_reset',
  name: 'Password reset',
  description: 'Sent when a user asks to reset their password.',
  enabled: true,
  locked: false,
  usingSavedContent: false,
  defaultSubject: 'Reset your password',
  defaultBody: '<p>Hi Alex, reset your password.</p>',
  subject: '',
  body: '',
  updatedBy: null,
  updatedAt: null,
  mergeTags: [
    { name: 'first_name', description: 'Recipient first name', sample: 'Alex', html: false }
  ]
}

describe('systemEmail schemas', () => {
  it('accepts a well-formed template list', () => {
    const parsed = systemEmailTemplateListSchema.parse({ items: [template] })
    expect(parsed.items).toHaveLength(1)
    expect(parsed.items[0].key).toBe('password_reset')
  })

  it('rejects a template missing the enabled flag rather than defaulting it', () => {
    const withoutEnabled: Record<string, unknown> = { ...template }
    delete withoutEnabled.enabled
    const result = systemEmailTemplateSchema.safeParse(withoutEnabled)
    expect(result.success).toBe(false)
  })

  it('rejects a merge tag without an html marker', () => {
    const result = systemEmailTemplateSchema.safeParse({
      ...template,
      mergeTags: [{ name: 'first_name', description: 'x', sample: 'Alex' }]
    })
    expect(result.success).toBe(false)
  })

  it('treats an unknown extra field as harmless', () => {
    const parsed = systemEmailTemplateSchema.parse({ ...template, extra: true })
    expect(parsed.key).toBe('password_reset')
  })

  it('parses settings and preview payloads', () => {
    expect(systemEmailSettingsSchema.parse({ emailsEnabled: false, updatedAt: null }).emailsEnabled).toBe(
      false
    )
    expect(
      systemEmailPreviewSchema.parse({
        key: 'password_reset',
        subject: 'Hi Alex',
        html: '<!doctype html><html></html>',
        text: 'Hi Alex'
      }).subject
    ).toBe('Hi Alex')
  })

  it('renders merge tag tokens with braces', () => {
    expect(mergeTagToken('first_name')).toBe('{{ first_name }}')
  })
})
