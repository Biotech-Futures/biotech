import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createRegistrationForms } from '@/registration/registration'
import {
  configuredRegistrationGateway,
  createHttpRegistrationGateway,
} from '@/registration/httpRegistrationGateway'
import { buildRegistrationRequest } from '@/registration/registrationGateway'
import {
  buildProductionRegistrationRequest,
  parseOverridePath,
  REGISTRATION_OVERRIDE_NAMES,
} from '@/registration/productionRegistration'
import { resetCsrfToken, setCsrfToken } from '@/utils/csrf'

const endpoint = 'https://api.example.test/api/v1/registration'
const checkEndpoint = 'https://api.example.test/api/v1/registration/email-check/'
const ensureCsrf = vi.fn(async () => true)

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const studentRequest = () => {
  const forms = createRegistrationForms()
  Object.assign(forms.studentIndividual.student, { email: 'alex@example.com' })
  Object.assign(forms.studentIndividual.student.guardian, { email: 'taylor@example.com' })
  return buildRegistrationRequest('student_individual', forms)
}

const noSleep = () => {
  vi.useFakeTimers({ toFake: ['setTimeout'] })
  return () => vi.useRealTimers()
}

beforeEach(() => {
  resetCsrfToken()
  setCsrfToken('csrf-test-token', endpoint)
  ensureCsrf.mockClear()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('the email check in the HTTP gateway', () => {
  it('is only there when the gateway is given where to check', () => {
    expect(createHttpRegistrationGateway({ endpoint, ensureCsrf }).checkEmails).toBeUndefined()
    expect(
      createHttpRegistrationGateway({ endpoint, ensureCsrf, emailCheckEndpoint: checkEndpoint })
        .checkEmails,
    ).toBeTypeOf('function')
  })

  it('is set up beside registration in the configured gateway', async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () => response({ status: 'disabled' }))
    vi.stubGlobal('fetch', fetchImpl)
    setCsrfToken('csrf-test-token', 'https://api.example.test')
    const gateway = configuredRegistrationGateway(undefined, 'https://api.example.test/')

    expect(gateway.checkEmails).toBeTypeOf('function')
    vi.unstubAllGlobals()
  })

  it('starts a check of the registration with CSRF and its late link, polls it, and reports progress', async () => {
    const restore = noSleep()
    const request = studentRequest()
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(response({ status: 'started', jobId: 'job-9', total: 2, done: 0 }, 202))
      .mockResolvedValueOnce(response({ status: 'queued', total: 2, done: 0, estimatedSecondsRemaining: null }))
      .mockResolvedValueOnce(response({ status: 'running', total: 2, done: 1, estimatedSecondsRemaining: 3 }))
      .mockResolvedValueOnce(response({ status: 'done', total: 2, done: 2, estimatedSecondsRemaining: 0 }))
    const gateway = createHttpRegistrationGateway({
      endpoint,
      fetchImpl,
      ensureCsrf,
      emailCheckEndpoint: checkEndpoint,
    })
    const onProgress = vi.fn()

    const outcome = gateway.checkEmails!(
      request,
      {
        invitationToken: 'signed-token',
        overrides: { 'students.0.overrides.ConfirmSchoolOverride': true },
      },
      onProgress,
    )
    await vi.runAllTimersAsync()

    expect(await outcome).toBe('checked')
    const [url, init] = fetchImpl.mock.calls[0]!
    expect(url).toBe(checkEndpoint)
    expect(init?.method).toBe('POST')
    expect(init?.credentials).toBe('include')
    const headers = init?.headers as Headers
    expect(headers.get('X-CSRFToken')).toBe('csrf-test-token')
    expect(headers.get('X-Registration-Invitation')).toBe('signed-token')
    expect(init?.body).toBe(
      JSON.stringify(
        buildProductionRegistrationRequest(request, {
          'students.0.overrides.ConfirmSchoolOverride': true,
        }),
      ),
    )
    expect(fetchImpl.mock.calls.slice(1).map(([pollUrl]) => pollUrl)).toEqual([
      `${checkEndpoint}job-9/`,
      `${checkEndpoint}job-9/`,
      `${checkEndpoint}job-9/`,
    ])
    expect(onProgress.mock.calls.map(([progress]) => progress)).toEqual([
      { phase: 'queued', done: 0, total: 2 },
      { phase: 'running', done: 1, total: 2, secondsRemaining: 3 },
    ])
    restore()
  })

  it.each([
    ['the check is switched off', response({ status: 'disabled' })],
    ['registration is closed', response({ status: 'closed' })],
    ['there are too many addresses', response({ status: 'too_many' })],
    ['the registration is refused', response({ error: 'Bad request' }, 400)],
    ['the server fails', response({ error: 'Server error' }, 500)],
  ])('skips the check without polling when %s', async (_, answer) => {
    const fetchImpl = vi.fn<typeof fetch>(async () => answer)
    const gateway = createHttpRegistrationGateway({
      endpoint,
      fetchImpl,
      ensureCsrf,
      emailCheckEndpoint: checkEndpoint,
    })

    expect(await gateway.checkEmails!(studentRequest(), {}, vi.fn())).toBe('skipped')
    expect(fetchImpl).toHaveBeenCalledTimes(1)
  })

  it('skips the check when the network is down', async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () => {
      throw new TypeError('Failed to fetch')
    })
    const gateway = createHttpRegistrationGateway({
      endpoint,
      fetchImpl,
      ensureCsrf,
      emailCheckEndpoint: checkEndpoint,
    })

    expect(await gateway.checkEmails!(studentRequest(), {}, vi.fn())).toBe('skipped')
  })

  it('skips the check when a secure session can’t be set up', async () => {
    const fetchImpl = vi.fn<typeof fetch>()
    const gateway = createHttpRegistrationGateway({
      endpoint,
      fetchImpl,
      ensureCsrf: vi.fn(async () => false),
      emailCheckEndpoint: checkEndpoint,
    })

    expect(await gateway.checkEmails!(studentRequest(), {}, vi.fn())).toBe('skipped')
    expect(fetchImpl).not.toHaveBeenCalled()
  })

  it('skips the check for a mentor, who has no students', async () => {
    const fetchImpl = vi.fn<typeof fetch>()
    const gateway = createHttpRegistrationGateway({
      endpoint,
      fetchImpl,
      ensureCsrf,
      emailCheckEndpoint: checkEndpoint,
    })
    const mentor = buildRegistrationRequest('mentor', createRegistrationForms())

    expect(await gateway.checkEmails!(mentor, {}, vi.fn())).toBe('skipped')
    expect(fetchImpl).not.toHaveBeenCalled()
  })

  it.each(['failed', 'stalled'])('skips the check when its job is %s', async (value) => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(response({ status: 'started', jobId: 'job-9' }, 202))
      .mockResolvedValueOnce(response({ status: value, total: 2, done: 1 }))
    const gateway = createHttpRegistrationGateway({
      endpoint,
      fetchImpl,
      ensureCsrf,
      emailCheckEndpoint: checkEndpoint,
    })

    expect(await gateway.checkEmails!(studentRequest(), {}, vi.fn())).toBe('skipped')
  })
})

describe('remembering that the check is switched off', () => {
  const checking = (fetchImpl: typeof fetch, csrf = ensureCsrf) =>
    createHttpRegistrationGateway({
      endpoint,
      fetchImpl,
      ensureCsrf: csrf,
      emailCheckEndpoint: checkEndpoint,
    })

  it('doesn’t ask again for the rest of the session once it answers “disabled”', async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () => response({ status: 'disabled' }))
    const csrf = vi.fn(async () => true)
    const gateway = checking(fetchImpl, csrf)

    expect(await gateway.checkEmails!(studentRequest(), {}, vi.fn())).toBe('skipped')
    expect(await gateway.checkEmails!(studentRequest(), {}, vi.fn())).toBe('skipped')
    expect(await gateway.checkEmails!(studentRequest(), {}, vi.fn())).toBe('skipped')

    expect(fetchImpl).toHaveBeenCalledOnce()
    expect(csrf).toHaveBeenCalledOnce()
  })

  it('remembers it when a job’s poll says so too', async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(response({ status: 'started', jobId: 'job-9' }, 202))
      .mockResolvedValueOnce(response({ status: 'disabled' }))
    const gateway = checking(fetchImpl)

    expect(await gateway.checkEmails!(studentRequest(), {}, vi.fn())).toBe('skipped')
    expect(await gateway.checkEmails!(studentRequest(), {}, vi.fn())).toBe('skipped')

    expect(fetchImpl).toHaveBeenCalledTimes(2)
  })

  it.each([
    ['closed', response({ status: 'closed' })],
    ['too many addresses', response({ status: 'too_many' })],
    ['an error', response({ error: 'Server error' }, 500)],
  ])('asks again next time after %s', async (_, answer) => {
    const fetchImpl = vi.fn<typeof fetch>(async () => answer.clone())
    const gateway = checking(fetchImpl)

    await gateway.checkEmails!(studentRequest(), {}, vi.fn())
    await gateway.checkEmails!(studentRequest(), {}, vi.fn())

    expect(fetchImpl).toHaveBeenCalledTimes(2)
  })

  it('asks again after a network error', async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () => {
      throw new TypeError('Failed to fetch')
    })
    const gateway = checking(fetchImpl)

    await gateway.checkEmails!(studentRequest(), {}, vi.fn())
    await gateway.checkEmails!(studentRequest(), {}, vi.fn())

    expect(fetchImpl).toHaveBeenCalledTimes(2)
  })

  it('is remembered per page session, not shared with a new one', async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () => response({ status: 'disabled' }))

    await checking(fetchImpl).checkEmails!(studentRequest(), {}, vi.fn())
    await checking(fetchImpl).checkEmails!(studentRequest(), {}, vi.fn())

    expect(fetchImpl).toHaveBeenCalledTimes(2)
  })

  it('still submits the registration itself while switched off', async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(response({ status: 'disabled' }))
      .mockResolvedValue(
        response(
          {
            reference_code: 'REG-1',
            journey: 'student_individual',
            student_count: 1,
            created_at: '2026-10-18T10:00:00Z',
          },
          201,
        ),
      )
    const gateway = checking(fetchImpl)

    await gateway.checkEmails!(studentRequest(), {}, vi.fn())
    const result = await gateway.submit(studentRequest())

    expect(result.ok).toBe(true)
    expect(fetchImpl.mock.calls.map(([url]) => url)).toEqual([checkEndpoint, endpoint])
  })
})

describe('the email warnings', () => {
  it('accepts a warning for each address found not to exist, on the right field', async () => {
    const request = studentRequest()
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      response(
        {
          error: 'Please check these registration warnings.',
          warnings: [
            {
              code: 'email_invalid',
              field: 'students.0.email',
              override_field: 'students.0.overrides.ConfirmEmailInvalidOverride',
              message: "This email address doesn't appear to exist.",
            },
            {
              code: 'guardian_email_invalid',
              field: 'students.0.guardian.email',
              override_field: 'students.0.overrides.ConfirmGuardianEmailInvalidOverride',
              message: "The guardian's email address doesn't appear to exist.",
            },
          ],
        },
        400,
      ),
    )
    const gateway = createHttpRegistrationGateway({ endpoint, fetchImpl, ensureCsrf })

    const result = await gateway.submit(request)

    expect(result.ok).toBe(false)
    expect(!result.ok && result.warnings).toEqual([
      {
        code: 'email_invalid',
        field: 'studentIndividual.student.email',
        overrideField: 'students.0.overrides.ConfirmEmailInvalidOverride',
        message: "This email address doesn't appear to exist.",
      },
      {
        code: 'guardian_email_invalid',
        field: 'studentIndividual.student.guardian.email',
        overrideField: 'students.0.overrides.ConfirmGuardianEmailInvalidOverride',
        message: "The guardian's email address doesn't appear to exist.",
      },
    ])
  })

  it('accepts a warning for the supervisor the student named, on the supervisor field', async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      response(
        {
          warnings: [
            {
              code: 'supervisor_email_invalid',
              field: 'supervisor.email',
              override_field: 'students.0.overrides.ConfirmSupervisorEmailInvalidOverride',
              message: "The supervisor's email address doesn't appear to exist.",
            },
          ],
        },
        400,
      ),
    )
    const gateway = createHttpRegistrationGateway({ endpoint, fetchImpl, ensureCsrf })

    const result = await gateway.submit(studentRequest())

    expect(!result.ok && result.warnings).toEqual([
      {
        code: 'supervisor_email_invalid',
        field: 'studentIndividual.supervisor.email',
        overrideField: 'students.0.overrides.ConfirmSupervisorEmailInvalidOverride',
        message: "The supervisor's email address doesn't appear to exist.",
      },
    ])
  })

  it('refuses a guardian warning placed on the student’s own email', async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      response(
        {
          warnings: [
            {
              code: 'guardian_email_invalid',
              field: 'students.0.email',
              override_field: 'students.0.overrides.ConfirmGuardianEmailInvalidOverride',
              message: 'Mismatched.',
            },
          ],
        },
        400,
      ),
    )
    const gateway = createHttpRegistrationGateway({ endpoint, fetchImpl, ensureCsrf })

    const result = await gateway.submit(studentRequest())

    expect(result).not.toHaveProperty('warnings')
  })

  it('sends the two new confirmations with the student they belong to', () => {
    const production = buildProductionRegistrationRequest(studentRequest(), {
      'students.0.overrides.ConfirmEmailInvalidOverride': true,
      'students.0.overrides.ConfirmGuardianEmailInvalidOverride': true,
    })

    const { students } = production.payload as { students: Array<{ overrides: unknown }> }
    expect(students[0]!.overrides).toEqual({
      ConfirmEmailInvalidOverride: true,
      ConfirmGuardianEmailInvalidOverride: true,
    })
  })

  it('knows all five overrides and nothing else', () => {
    expect(REGISTRATION_OVERRIDE_NAMES).toEqual([
      'ConfirmSchoolOverride',
      'ConfirmNameEmailOverride',
      'ConfirmEmailInvalidOverride',
      'ConfirmGuardianEmailInvalidOverride',
      'ConfirmSupervisorEmailInvalidOverride',
    ])
    expect(parseOverridePath('students.2.overrides.ConfirmGuardianEmailInvalidOverride')).toEqual({
      index: 2,
      name: 'ConfirmGuardianEmailInvalidOverride',
    })
    for (const path of [
      'students.0.overrides.toString',
      'students.0.overrides.constructor',
      'students.0.overrides.ConfirmSomethingElse',
      'students.x.overrides.ConfirmSchoolOverride',
    ]) {
      expect(parseOverridePath(path)).toBeNull()
    }
  })
})
