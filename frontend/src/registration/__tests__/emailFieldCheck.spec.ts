import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useEmailFieldChecks, type EmailBox } from '@/registration/emailFieldCheck'
import { configuredRegistrationGateway } from '@/registration/httpRegistrationGateway'
import { resetCsrfToken } from '@/utils/csrf'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const soft = (message: string, overrideField: string) => ({
  ok: false, severity: 'soft',
  warnings: [{ code: 'email_invalid', message, field: 'x', override_field: overrideField }],
})

// The checks' requests, each one's body.
interface Sent {
  journey?: string
  fields: Array<Record<string, unknown> & { field: string }>
}
let sent: Sent[] = []
const serve = (...answers: unknown[]) => {
  const queue = [...answers]
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (String(url).includes('/services/csrf/')) return json({ csrfToken: 'csrf' })
    sent.push(JSON.parse(String(init?.body)) as Sent)
    const next = queue.length > 1 ? queue.shift() : queue[0]
    return next instanceof Response ? next : json({ results: { [sent.at(-1)!.fields[0]!.field]: next } })
  }))
}

const setup = () => {
  // The page's own gateway, over the stubbed network.
  const gateway = configuredRegistrationGateway(undefined, 'http://localhost:8000')
  return useEmailFieldChecks({
    request: (body) => gateway.checkEmailField!(body),
    journey: () => 'student_individual',
  })
}

const student = (email: string): EmailBox => ({
  field: 'studentIndividual.student.email', kind: 'student', email, student: 0, firstName: 'Jo', lastName: 'Lee',
})

beforeEach(() => {
  sent = []
  resetCsrfToken()
})

afterEach(() => vi.unstubAllGlobals())

describe('an email box checked as it is left', () => {
  it("sends the box as Submit would, and keeps a hard problem as the box's error", async () => {
    serve({ ok: false, severity: 'hard', code: 'invalid', message: 'Enter a valid email address.' })
    const checks = setup()

    await checks.check(student(' jo@ '))

    expect(sent).toEqual([{
      journey: 'student_individual',
      fields: [{
        field: 'studentIndividual.student.email', kind: 'student', email: 'jo@', student: 0,
        firstName: 'Jo', lastName: 'Lee',
      }],
    }])
    expect(checks.hardProblems(() => 'jo@')).toEqual({
      'studentIndividual.student.email': 'Enter a valid email address.',
    })
    // Corrected since: no longer its error.
    expect(checks.hardProblems(() => 'jo@example.test')).toEqual({})
  })

  it('asks once for an address left unchanged', async () => {
    serve({ ok: true })
    const checks = setup()

    await checks.check(student('jo@example.test'))
    await checks.check(student('jo@example.test'))

    expect(sent).toHaveLength(1)
    expect(checks.stateOf('studentIndividual.student.email', 'jo@example.test')?.status).toBe('ok')
  })

  it('shows a warning, with nothing to confirm here, and checks a new address again', async () => {
    serve(soft("This email address couldn't be verified.", 'students.0.overrides.ConfirmEmailInvalidOverride'), {
      ok: true,
    })
    const checks = setup()

    await checks.check(student('jo@example.test'))
    expect(checks.stateOf('studentIndividual.student.email', 'jo@example.test')).toEqual({
      email: 'jo@example.test', status: 'soft', message: "This email address couldn't be verified.",
    })

    await checks.check(student('jo.lee@example.test'))
    expect(sent).toHaveLength(2)
    expect(sent[1]!.fields[0]).not.toHaveProperty('overrides')
    expect(checks.stateOf('studentIndividual.student.email', 'jo.lee@example.test')?.status).toBe('ok')
  })

  it("sends a School box's school, not an address", async () => {
    serve(soft('This looks like a university, not a school.', 'students.0.overrides.ConfirmSchoolOverride'))
    const checks = setup()

    await checks.check({
      field: 'studentIndividual.student.school', kind: 'school', email: '', school: ' University of Sydney ', student: 0,
    })

    expect(sent[0]!.fields[0]).toEqual({
      field: 'studentIndividual.student.school', kind: 'school', email: '', school: 'University of Sydney', student: 0,
    })
    expect(checks.stateOf('studentIndividual.student.school', 'University of Sydney')?.status).toBe('soft')
  })

  it("says nothing when it can't check, and Submit still checks", async () => {
    serve(json({ detail: 'Too many' }, 429))
    const checks = setup()

    await checks.check(student('jo@example.test'))

    expect(checks.stateOf('studentIndividual.student.email', 'jo@example.test')).toBeUndefined()
  })
})
