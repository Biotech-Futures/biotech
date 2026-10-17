/**
 * The public registration's progress (role, option, step and what's typed),
 * kept in this browser tab, so a refresh or a visit to another page loses
 * nothing. Session storage, not local: it goes when the tab closes, as many
 * register on shared school computers. Profile photos aren't kept (files
 * can't be). Cleared once the registration is submitted.
 */
import type { RegistrationForms, RegistrationJourney } from './registration'

const KEY = 'biotech.registration.draft'
// Bump when the forms' shape changes, so an older draft isn't restored into it.
// 2: group codes are numbers (held until a time). 3: a group's Support step.
// 4: a group's Support step gone (its guardian on Your profile, its
// supervisor on Group).
const VERSION = 4

export type RegistrationDraft = {
  version: number
  invitationToken?: string | null
  journey: RegistrationJourney | null
  selectionStage: string
  selectedRole: string | null
  currentStep: number
  maxReachedStep: number
  forms: Pick<RegistrationForms, 'studentIndividual' | 'studentTeam' | 'mentor'>
}

/** The draft for this invitation (or none), if there is one. */
export function readDraft(invitationToken?: string | null): RegistrationDraft | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return null
    const draft = JSON.parse(raw) as RegistrationDraft
    if (draft?.version !== VERSION || (draft.invitationToken ?? null) !== (invitationToken ?? null))
      return null
    return draft
  } catch {
    return null
  }
}

export function saveDraft(draft: Omit<RegistrationDraft, 'version'>) {
  try {
    sessionStorage.setItem(
      KEY,
      // Files (a profile photo) can't be kept: saved as none.
      JSON.stringify({ ...draft, version: VERSION }, (_key, value) =>
        typeof File !== 'undefined' && value instanceof File ? null : value,
      ),
    )
  } catch {
    // Storage unavailable (private mode, full): progress just isn't kept.
  }
}

export function clearDraft() {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // Nothing kept to clear.
  }
}
