import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createRegistrationForms } from '@/registration/registration'
import {
  configuredRegistrationGateway,
  createHttpRegistrationGateway,
} from '@/registration/httpRegistrationGateway'
import { buildRegistrationRequest } from '@/registration/registrationGateway'
import { resetCsrfToken, setCsrfToken } from '@/utils/csrf'

const endpoint = 'https://api.example.test/api/v1/registration/intake/'
const ensureCsrf = vi.fn(async () => true)

const response = (body: unknown, status = 200) =>
  new Response(typeof body === 'string' ? body : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'X-Request-ID': 'req-100' },
  })

beforeEach(() => {
  resetCsrfToken()
  setCsrfToken('csrf-test-token')
  ensureCsrf.mockClear()
})

describe('HTTP registration gateway', () => {
  it('posts sanitized JSON with session and CSRF headers', async () => {
    const forms = createRegistrationForms()
    forms.studentIndividual.student.email = ' Student@Example.com '
    forms.studentIndividual.student.emailConfirm = ' Student@Example.com '
    forms.studentIndividual.student.profilePhoto = {
      name: 'profile.png',
      type: 'image/png',
      size: 100,
    }
    const request = buildRegistrationRequest('student_individual', forms)
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      response({
        reference_code: 'REG-1',
        journey: 'student_individual',
        student_count: 1,
        created_at: '2026-09-04T10:00:00Z',
      }),
    )
    const gateway = createHttpRegistrationGateway({ endpoint, fetchImpl, ensureCsrf })

    await gateway.submit(request)

    expect(ensureCsrf).toHaveBeenCalledWith('https://api.example.test')
    const [url, init] = fetchImpl.mock.calls[0]!
    expect(init).toBeDefined()
    if (!init) throw new Error('Expected registration request options.')
    expect(url).toBe(endpoint)
    expect(init.credentials).toBe('include')
    expect(init.method).toBe('POST')
    const headers = init.headers as Headers
    expect(headers.get('Accept')).toBe('application/json')
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('X-CSRFToken')).toBe('csrf-test-token')
    expect(init.body).toBe(JSON.stringify(request))
    expect(String(init.body)).not.toContain('emailConfirm')
    expect(String(init.body)).toContain('student@example.com')
  })

  it.each([
    [
      {
        reference_code: 'REG-SNAKE',
        journey: 'mentor',
        student_count: 0,
        created_at: '2026-09-04T10:00:00Z',
      },
      'REG-SNAKE',
    ],
    [
      {
        data: {
          referenceCode: 'REG-CAMEL',
          journey: 'student_team',
          studentCount: 2,
          submittedAt: '2026-09-04T10:00:00Z',
        },
      },
      'REG-CAMEL',
    ],
  ])('normalizes supported success receipts', async (body, referenceCode) => {
    const gateway = createHttpRegistrationGateway({
      endpoint,
      fetchImpl: vi.fn(async () => response(body)),
      ensureCsrf,
    })

    const result = await gateway.submit(
      buildRegistrationRequest('mentor', createRegistrationForms()),
    )

    expect(result.ok).toBe(true)
    if (result.ok) expect(result.receipt.referenceCode).toBe(referenceCode)
  })

  it('maps Django field arrays and strings to frontend field messages', async () => {
    const gateway = createHttpRegistrationGateway({
      endpoint,
      fetchImpl: vi.fn(async () =>
        response(
          {
            error: 'Review the highlighted information.',
            code: 'validation_error',
            request_id: 'req-101',
            fields: {
              'studentIndividual.student.email': ['Already registered.', 'Use another address.'],
              'studentIndividual.student.school': 'School is required.',
            },
          },
          400,
        ),
      ),
      ensureCsrf,
    })

    const result = await gateway.submit(
      buildRegistrationRequest('student_individual', createRegistrationForms()),
    )

    expect(result).toEqual({
      ok: false,
      message: 'Review the highlighted information.',
      fieldErrors: {
        'studentIndividual.student.email': 'Already registered. Use another address.',
        'studentIndividual.student.school': 'School is required.',
      },
    })
  })

  it('returns non-field server errors without inventing field state', async () => {
    const gateway = createHttpRegistrationGateway({
      endpoint,
      fetchImpl: vi.fn(async () =>
        response({ error: 'Registration is temporarily unavailable.', code: 'unavailable' }, 503),
      ),
      ensureCsrf,
    })

    await expect(
      gateway.submit(buildRegistrationRequest('mentor', createRegistrationForms())),
    ).resolves.toEqual({
      ok: false,
      message: 'Registration is temporarily unavailable.',
      fieldErrors: undefined,
    })
  })

  it('returns a clear failure for a non-JSON server error', async () => {
    const gateway = createHttpRegistrationGateway({
      endpoint,
      fetchImpl: vi.fn(async () => response('<html>Unavailable</html>', 502)),
      ensureCsrf,
    })

    await expect(
      gateway.submit(buildRegistrationRequest('mentor', createRegistrationForms())),
    ).resolves.toEqual({
      ok: false,
      message: 'Registration could not be submitted.',
      fieldErrors: undefined,
    })
  })

  it.each([
    ['non-JSON success', response('not-json')],
    ['incomplete success', response({ data: { reference_code: 'REG-1' } })],
  ])('rejects %s responses', async (_label, serverResponse) => {
    const gateway = createHttpRegistrationGateway({
      endpoint,
      fetchImpl: vi.fn(async () => serverResponse),
      ensureCsrf,
    })

    const result = await gateway.submit(
      buildRegistrationRequest('mentor', createRegistrationForms()),
    )

    expect(result.ok).toBe(false)
  })

  it('reports CSRF setup failure without posting', async () => {
    const fetchImpl = vi.fn()
    const gateway = createHttpRegistrationGateway({
      endpoint,
      fetchImpl,
      ensureCsrf: vi.fn(async () => false),
    })

    const result = await gateway.submit(
      buildRegistrationRequest('mentor', createRegistrationForms()),
    )

    expect(result).toEqual({
      ok: false,
      message: 'A secure registration session could not be initialized. Refresh and try again.',
    })
    expect(fetchImpl).not.toHaveBeenCalled()
  })

  it('reports network failure and leaves retry to the page', async () => {
    const gateway = createHttpRegistrationGateway({
      endpoint,
      fetchImpl: vi.fn(async () => {
        throw new TypeError('offline')
      }),
      ensureCsrf,
    })

    await expect(
      gateway.submit(buildRegistrationRequest('mentor', createRegistrationForms())),
    ).resolves.toEqual({
      ok: false,
      message: 'The registration service could not be reached. Check your connection and try again.',
    })
  })

  it('keeps production explicitly unconfigured when the environment value is empty', () => {
    expect(configuredRegistrationGateway(undefined)).toBeNull()
    expect(configuredRegistrationGateway('   ')).toBeNull()
    expect(configuredRegistrationGateway(endpoint)).not.toBeNull()
  })
})
