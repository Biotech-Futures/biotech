// Pronouns as registering asks for them: a listed choice, or Other with
// their own words. Used where a student's pronouns are edited later.
import { PRONOUN_OPTIONS } from '@/registration/registration'

/** The choices. None saved shows as Not set, emptied again with the box's ×. */
export const PRONOUN_SELECT_OPTIONS = PRONOUN_OPTIONS.map((pronoun) => ({ value: pronoun, label: pronoun }))
export const PRONOUN_PLACEHOLDER = 'Not set'

/** The choice is null once cleared with the ×. */
export type PronounDraft = { choice: string | null; other: string }

/** Saved pronouns as a choice: their own words come back under Other. */
export function pronounDraft(pronouns: string | null | undefined): PronounDraft {
  const value = (pronouns || '').trim()
  return !value || (PRONOUN_OPTIONS as readonly string[]).includes(value)
    ? { choice: value, other: '' }
    : { choice: 'Other', other: value }
}

/** The pronouns to save, or null when Other is chosen with nothing typed. */
export function pronounsToSave({ choice, other }: PronounDraft): string | null {
  if (choice !== 'Other') return choice || ''
  return other.trim() || null
}
