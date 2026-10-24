import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'

import { useEmailFieldChecks, type EmailBox } from '@/registration/emailFieldCheck'
import { configuredRegistrationGateway } from '@/registration/httpRegistrationGateway'
import { resetCsrfToken } from '@/utils/csrf'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const soft = (message: string, overrideField: string) => ({
  ok: false, severity: 'soft',
  warnings: [{ code: 'email_invalid', message, field: 'x', override_field: overrideField }],
})

// The checks' requests, each one's body.
let sent: Array<Record<string, any>> = []
const serve = (...answers: unknown[]) => {
  const queue = [...answers]
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (String(url).includes('/services/csrf/')) return json({ csrfToken: 'csrf' })
    sent.push(JSON.parse(String(init?.body)))
    const next = queue.length > 1 ? queue.shift() : queue[0]
    return next instanceof Response ? next : json({ results: { [sent.at(-1)!.fields[0].field]: next } })
  }))
}

const setup = () => {
  const overrides = reactive<Record<string, boolean>>({})
  // The page's own gateway, over the stubbed network.
  const gateway = configuredRegistrationGateway(undefined, 'http://localhost:8000')
  const checks = useEmailFieldChecks({
    request: (body) => gateway.checkEmailField!(body),
    overrides: () => overrides,
    setOverride: (path, confirmed) => {
      if (confirmed) overrides[path] = true
      else delete overrides[path]
    },
    journey: () => 'student_individual',
  })
  return { checks, overrides }
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
    const { checks } = setup()

    await checks.check(student(' jo@ '))

    expect(sent).toEqual([{
      journey: 'student_individual',
      fields: [{
        field: 'studentIndividual.student.email', kind: 'student', email: 'jo@', student: 0,
        firstName: 'Jo', lastName: 'Lee', overrides: {},
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
    const { checks } = setup()

    await checks.check(student('jo@example.test'))
    await checks.check(student('jo@example.test'))

    expect(sent).toHaveLength(1)
    expect(checks.stateOf('studentIndividual.student.email', 'jo@example.test')?.status).toBe('ok')
  })

  it('a warning confirmed is the next check\'s and Submit\'s, and another address drops it', async () => {
    const path = 'students.0.overrides.ConfirmEmailInvalidOverride'
    serve(soft("This email address couldn't be verified.", path), { ok: true })
    const { checks, overrides } = setup()

    await checks.check(student('jo@example.test'))
    expect(checks.stateOf('studentIndividual.student.email', 'jo@example.test')).toMatchObject({
      status: 'soft', overrideField: path,
    })

    await checks.confirm(student('jo@example.test'), true)
    expect(overrides).toEqual({ [path]: true })
    expect(sent[1]!.fields[0].overrides).toEqual({ ConfirmEmailInvalidOverride: true })
    expect(checks.stateOf('studentIndividual.student.email', 'jo@example.test')?.status).toBe('ok')

    await checks.check(student('jo.lee@example.test'))
    expect(overrides).toEqual({})
    expect(sent[2]!.fields[0].overrides).toEqual({})
  })

  it("says nothing when it can't check, and Submit still checks", async () => {
    serve(json({ detail: 'Too many' }, 429))
    const { checks } = setup()

    await checks.check(student('jo@example.test'))

    expect(checks.stateOf('studentIndividual.student.email', 'jo@example.test')).toBeUndefined()
  })

  it("a mentor's or supervisor's confirmations are their own", async () => {
    serve(soft('Check it.', 'supervisor.overrides.ConfirmNameEmailOverride'), { ok: true })
    const { checks, overrides } = setup()
    const box: EmailBox = {
      field: 'supervisor.email', kind: 'supervisor_self', email: 'samteachr@example.test',
      firstName: 'Sam', lastName: 'Teacher',
    }

    await checks.check(box)
    await checks.confirm(box, true)

    expect(overrides).toEqual({ 'supervisor.overrides.ConfirmNameEmailOverride': true })
    expect(sent[1]!.fields[0].overrides).toEqual({ ConfirmNameEmailOverride: true })
  })
})
