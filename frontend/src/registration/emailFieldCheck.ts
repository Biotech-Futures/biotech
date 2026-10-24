/**
 * Each email box on the registration page, checked as it's left: what Submit
 * would refuse (a hard problem, shown as the box's error, which keeps its
 * step from going on) or warn about (soft, shown under it with a tick to
 * confirm the address; the tick is Submit's confirmation too, so it isn't
 * asked again). POST registration/email-check/field/ (email_field_check on the
 * backend): the address's format, the template's placeholder, whether its
 * mailbox exists, whether it's already used, a name that looks like a typo of
 * it, and a guardian or supervisor the same as the student. A student's
 * School box too: a warning when it looks like a university.
 *
 * A check that can't be done (no network, too many in a minute, a gateway
 * without it) says nothing: Submit still checks. It goes through the page's
 * registration gateway (checkEmailField), as Submit does.
 */
import { reactive } from 'vue'

/** student, guardian, supervisor (the one a student names), mentor,
 *  supervisor_self (a supervisor registering themselves), or school (a
 *  student's School box, not an email). */
export type EmailCheckKind = 'student' | 'guardian' | 'supervisor' | 'mentor' | 'supervisor_self' | 'school'

/** A student editor's checked boxes, by their fields under the student. */
export type StudentBoxField = 'email' | 'guardian.email' | 'school'

/** A box: ``field`` is the page's own path for it (its error's), ``student``
 *  the student's place in the registration as Submit sends it. */
export interface EmailBox {
  field: string
  kind: EmailCheckKind
  email: string
  student?: number
  studentEmail?: string
  firstName?: string
  lastName?: string
  /** A school box's school (its ``email`` is empty). */
  school?: string
}

type Result =
  | { ok: true }
  | { ok: false; severity: 'hard'; code: string; message: string }
  | {
      ok: false
      severity: 'soft'
      warnings: Array<{ code: string; message: string; field: string; override_field: string }>
    }

export interface EmailBoxState {
  /** The address (or school) it's about, as it was left. */
  email: string
  status: 'checking' | 'ok' | 'hard' | 'soft'
  message: string
  /** A warning's confirmation: its path among Submit's overrides. */
  overrideField: string
}

/** The gateway's check (RegistrationGateway.checkEmailField): the results by
 *  box, or null when it can't be done. */
export type EmailCheckRequest = (body: { journey?: string; fields: unknown[] }) => Promise<Record<string, unknown> | null>

// A box's confirmations: the overrides under its prefix, by their names.
const overridePrefix = (box: EmailBox) => {
  if (box.kind === 'mentor') return 'mentor.overrides.'
  if (box.kind === 'supervisor_self') return 'supervisor.overrides.'
  // The supervisor a student names is the registration's, on its first student.
  return `students.${box.kind === 'supervisor' ? 0 : (box.student ?? 0)}.overrides.`
}
// Which confirmations are a box's own: a student's mailbox and name, a
// guardian's mailbox and account, the named supervisor's mailbox and name,
// a student's school.
const OWN_OVERRIDES: Record<EmailCheckKind, string[]> = {
  student: ['ConfirmEmailInvalidOverride', 'ConfirmNameEmailOverride'],
  guardian: ['ConfirmGuardianEmailInvalidOverride', 'ConfirmGuardianEmailHasAccountOverride'],
  supervisor: ['ConfirmSupervisorEmailInvalidOverride', 'ConfirmSupervisorNameEmailOverride'],
  mentor: ['ConfirmEmailInvalidOverride', 'ConfirmNameEmailOverride'],
  supervisor_self: ['ConfirmEmailInvalidOverride', 'ConfirmNameEmailOverride'],
  school: ['ConfirmSchoolOverride'],
}

// What a box is checked for: its address, or a school box's school.
const valueOf = (box: EmailBox) => (box.kind === 'school' ? (box.school ?? '') : box.email).trim()

/**
 * The page's boxes, by their paths. ``overrides`` is the page's own map of
 * confirmed warnings (Submit's): a tick under a box goes in it, and a box
 * whose address changes takes its own back out.
 */
export function useEmailFieldChecks(options: {
  request: EmailCheckRequest
  overrides: () => Record<string, boolean>
  setOverride: (path: string, confirmed: boolean) => void
  journey: () => string | null
}) {
  const boxes = reactive<Record<string, EmailBoxState>>({})
  const pending = new Set<Promise<void>>()
  // What each box was last checked with, so leaving it unchanged asks nothing.
  const asked: Record<string, string> = {}

  const ownOverrides = (box: EmailBox) => {
    const prefix = overridePrefix(box)
    return Object.fromEntries(
      OWN_OVERRIDES[box.kind]
        .filter((name) => options.overrides()[`${prefix}${name}`])
        .map((name) => [name, true]),
    )
  }

  const run = async (box: EmailBox) => {
    const email = valueOf(box)
    const overrides = ownOverrides(box)
    boxes[box.field] = { email, status: 'checking', message: '', overrideField: '' }
    const journey = options.journey()
    const results = await options
      .request({
        ...(journey ? { journey } : {}),
        fields: [{ ...box, ...(box.kind === 'school' ? { school: email } : { email }), overrides }],
      })
      .catch(() => null)
    const result = (results?.[box.field] ?? null) as Result | null
    // Changed while it was checked: the newer check says.
    if (boxes[box.field]?.email !== email) return
    if (!result) {
      delete boxes[box.field]
    } else if (result.ok) {
      boxes[box.field] = { email, status: 'ok', message: '', overrideField: '' }
    } else if (result.severity === 'hard') {
      boxes[box.field] = { email, status: 'hard', message: result.message, overrideField: '' }
    } else {
      const warning = result.warnings[0]!
      boxes[box.field] = { email, status: 'soft', message: warning.message, overrideField: warning.override_field }
    }
  }

  /** Left, or a warning confirmed: checked again when anything it's
   *  checked with changed. */
  const check = (box: EmailBox) => {
    const email = valueOf(box)
    const before = boxes[box.field]
    // Another address: the old one's confirmations don't carry over.
    if (before && before.email !== email) {
      const prefix = overridePrefix(box)
      OWN_OVERRIDES[box.kind].forEach((name) => options.setOverride(`${prefix}${name}`, false))
    }
    if (!email) {
      delete boxes[box.field]
      delete asked[box.field]
      return Promise.resolve()
    }
    const signature = JSON.stringify([box, ownOverrides(box)])
    if (asked[box.field] === signature && before && before.email === email) return Promise.resolve()
    asked[box.field] = signature
    const job = run(box).finally(() => pending.delete(job))
    pending.add(job)
    return job
  }

  /** A box's state, while it's about the address there now. */
  const stateOf = (field: string, email: string) => {
    const state = boxes[field]
    return state && state.email === email.trim() ? state : undefined
  }

  /** The hard problems, by the boxes' paths, while their address is there. */
  const hardProblems = (current: (field: string) => string) =>
    Object.fromEntries(
      Object.entries(boxes)
        .filter(([field, state]) => state.status === 'hard' && state.email === current(field).trim())
        .map(([field, state]) => [field, state.message]),
    )

  /** A warning confirmed or not, then checked again for the next one. */
  const confirm = (box: EmailBox, confirmed: boolean) => {
    const state = boxes[box.field]
    if (!state?.overrideField) return Promise.resolve()
    options.setOverride(state.overrideField, confirmed)
    return check(box)
  }

  /** Whether any check is under way. */
  const checking = () => pending.size > 0

  /** Every check under way, done: before a step goes on. */
  const settled = () => Promise.allSettled([...pending]).then(() => undefined)

  const reset = () => {
    Object.keys(boxes).forEach((key) => delete boxes[key])
    Object.keys(asked).forEach((key) => delete asked[key])
  }

  return { boxes, check, stateOf, hardProblems, confirm, checking, settled, reset }
}
