import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createRegistrationForms } from '@/registration/registration'
import {
  configuredRegistrationGateway,
  createHttpRegistrationGateway,
} from '@/registration/httpRegistrationGateway'
import { buildRegistrationRequest } from '@/registration/registrationGateway'
import { buildProductionRegistrationRequest } from '@/registration/productionRegistration'
import { resetCsrfToken, setCsrfToken } from '@/utils/csrf'

const endpoint = 'https://api.example.test/api/v1/registration'
const retryKey = 'a0840281-c717-447f-95e9-b23847a0b9e2'
const ensureCsrf = vi.fn(async () => true)

const response = (body: unknown, status = 200) =>
  new Response(typeof body === 'string' ? body : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'X-Request-ID': 'req-100' },
  })

beforeEach(() => {
  resetCsrfToken()
  setCsrfToken('csrf-test-token', endpoint)
  ensureCsrf.mockClear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('HTTP registration gateway', () => {
  it('sends actual photos, an invitation and a stable retry key', async () => {
    const request = buildRegistrationRequest('student_individual', createRegistrationForms())
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      response({
        reference_code: 'REG-PHOTO',
        journey: 'student_individual',
        student_count: 1,
        created_at: '2026-10-07T10:00:00Z',
      }),
    )
    const gateway = createHttpRegistrationGateway({ endpoint, fetchImpl, ensureCsrf })
    const photo = new File(['image bytes'], 'photo.png', { type: 'image/png' })
    const options = {
      attachments: { 'studentIndividual.student': photo },
      invitationToken: 'signed-token',
      idempotencyKey: retryKey,
    }
    await gateway.submit(request, options)
    await gateway.submit(request, options)
    for (const [, init] of fetchImpl.mock.calls) {
      expect(init?.body).toBeInstanceOf(FormData)
      const body = init?.body as FormData
      expect(body.get('request')).toBe(JSON.stringify(buildProductionRegistrationRequest(request)))
      expect(body.get('students.0')).toBeInstanceOf(File)
      const headers = init?.headers as Headers
      expect(headers.get('Content-Type')).toBeNull()
      expect(headers.get('Idempotency-Key')).toBe(retryKey)
      expect(headers.get('X-Registration-Invitation')).toBe('signed-token')
      const uploaded = body.get('students.0')
      if (!(uploaded instanceof File)) throw new Error('Expected uploaded image bytes')
      const reader = new FileReader()
      const contents = new Promise((resolve, reject) => {
        reader.onload = () => resolve(reader.result)
        reader.onerror = () => reject(reader.error)
      })
      reader.readAsText(uploaded)
      expect(await contents).toBe('image bytes')
    }
  })
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
    const fetchImpl = vi.fn<typeof fetch>(async () =>
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
    expect(headers.get('Idempotency-Key')).toMatch(/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i)
    expect(init.body).toBe(JSON.stringify(buildProductionRegistrationRequest(request)))
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

    // A group of two: Member 2 given (one left empty isn't registered).
    const forms = createRegistrationForms()
    forms.studentTeam.teammates[0]!.firstName = 'Jamie'
    const result = await gateway.submit(
      buildRegistrationRequest('data' in body ? 'student_team' : 'mentor', forms),
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

  it('returns structured warnings with safe canonical override paths', async () => {
    const gateway = createHttpRegistrationGateway({
      endpoint,
      ensureCsrf,
      fetchImpl: vi.fn(async () =>
        response(
          {
            error: 'Please confirm.',
            warnings: [
              {
                code: 'school_requires_confirmation',
                field: 'students.0.school',
                override_field: 'students.0.overrides.ConfirmSchoolOverride',
                message: 'Check this school.',
              },
            ],
          },
          400,
        ),
      ),
    })
    expect(
      await gateway.submit(
        buildRegistrationRequest('student_individual', createRegistrationForms()),
      ),
    ).toEqual({
      ok: false,
      message: 'Please confirm.',
      warnings: [
        {
          code: 'school_requires_confirmation',
          field: 'studentIndividual.student.school',
          overrideField: 'students.0.overrides.ConfirmSchoolOverride',
          message: 'Check this school.',
        },
      ],
    })
  })

  it.each([
    'students.0.overrides.ApproveGuardian',
    'students.9.overrides.ConfirmSchoolOverride',
    '__proto__.override',
  ])('rejects an invalid server override path %s', async (overrideField) => {
    const gateway = createHttpRegistrationGateway({
      endpoint,
      ensureCsrf,
      fetchImpl: vi.fn(async () =>
        response(
          {
            warnings: [
              {
                code: 'check',
                field: 'students.0.school',
                override_field: overrideField,
                message: 'Check this.',
              },
            ],
          },
          400,
        ),
      ),
    })
    const result = await gateway.submit(
      buildRegistrationRequest('student_individual', createRegistrationForms()),
    )
    expect(result.ok).toBe(false)
    expect(result).not.toHaveProperty('warnings')
  })

  it('maps normalized CSV fields back to the included row indexes', async () => {
    const gateway = createHttpRegistrationGateway({
      endpoint,
      ensureCsrf,
      fetchImpl: vi.fn(async () =>
        response(
          {
            error: 'Check the row.',
            fields: {
              'students.1.guardian.email': ['Invalid guardian email.'],
            },
          },
          400,
        ),
      ),
    })
    const forms = createRegistrationForms()
    forms.supervisorCsv.rows = [0, 1].map((index) => ({
      rowNumber: index + 10,
      category: 'valid',
      issues: [],
      values: {
        first_name: 'Alex',
        last_name: 'Student',
        email: `csv${index}@example.test`,
        school: 'High School',
        year_level: '10',
        country: 'Australia',
        state: 'NSW',
        interests: 'Biomedical Innovations',
        guardian_first_name: '',
        guardian_last_name: '',
        guardian_email: '',
        guardian_relationship: '',
        guardian_relationship_other: '',
        grouping_preference: '',
      },
    }))
    const result = await gateway.submit(buildRegistrationRequest('supervisor_csv', forms))
    expect(result).toMatchObject({
      ok: false,
      fieldErrors: {
        'supervisorCsv.rows.1.guardian.email': 'Invalid guardian email.',
      },
    })
  })

  it.each([
    { journey: 'mentor', student_count: 0.5, created_at: '2026-10-11T05:00:00Z' },
    { journey: 'student_individual', student_count: 1, created_at: '2026-10-11T05:00:00Z' },
    { journey: 'mentor', student_count: 0, created_at: 'not-a-date' },
  ])('rejects an uncorrelated or invalid receipt', async (receipt) => {
    const gateway = createHttpRegistrationGateway({
      endpoint,
      ensureCsrf,
      fetchImpl: vi.fn(async () => response({ reference_code: 'REG-1', ...receipt })),
    })
    expect(
      (await gateway.submit(buildRegistrationRequest('mentor', createRegistrationForms()))).ok,
    ).toBe(false)
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
      message:
        'The registration service could not be reached. Check your connection and try again.',
    })
  })

  it.each([undefined, '   '])(
    'uses the real same-origin route without endpoint overrides (%s)',
    async (override) => {
      setCsrfToken('same-origin-csrf', window.location.origin)
      const send = vi.fn<typeof fetch>(async () =>
        response(
          {
            reference_code: 'REG-DEFAULT',
            journey: 'mentor',
            student_count: 0,
            created_at: '2026-10-11T05:00:00Z',
          },
          201,
        ),
      )
      vi.stubGlobal('fetch', send)
      const gateway = configuredRegistrationGateway(override)
      expect(
        (await gateway.submit(buildRegistrationRequest('mentor', createRegistrationForms()))).ok,
      ).toBe(true)
      expect(send).toHaveBeenCalledWith(
        '/api/v1/registration',
        expect.objectContaining({
          credentials: 'include',
          method: 'POST',
        }),
      )
      expect((send.mock.calls[0]![1]?.headers as Headers).get('X-CSRFToken')).toBe(
        'same-origin-csrf',
      )
    },
  )

  it.each([
    [undefined, 'https://api.example.test/', endpoint],
    [
      ' https://api.example.test/custom/ ',
      'https://unused.example.test',
      'https://api.example.test/custom/',
    ],
  ])(
    'uses the deployed API origin or explicit endpoint without changing slash conventions',
    async (override, base, expected) => {
      vi.stubGlobal(
        'fetch',
        vi.fn<typeof fetch>(async () =>
          response({
            reference_code: 'REG-BASE',
            journey: 'mentor',
            student_count: 0,
            created_at: '2026-10-11T05:00:00Z',
          }),
        ),
      )
      const gateway = configuredRegistrationGateway(override, base)
      await gateway.submit(buildRegistrationRequest('mentor', createRegistrationForms()))
      expect(fetch).toHaveBeenCalledWith(expected, expect.anything())
    },
  )

  it.each([200, 201])('requires a real receipt for supported success status %s', async (status) => {
    const gateway = createHttpRegistrationGateway({
      endpoint,
      ensureCsrf,
      fetchImpl: vi.fn(async () =>
        response(
          {
            reference_code: 'REG-SAVED',
            journey: 'student_individual',
            student_count: 1,
            created_at: '2026-10-11T05:00:00Z',
          },
          status,
        ),
      ),
    })
    expect(
      (
        await gateway.submit(
          buildRegistrationRequest('student_individual', createRegistrationForms()),
        )
      ).ok,
    ).toBe(true)
  })

  it('does not mistake an accepted response for a saved registration', async () => {
    const gateway = createHttpRegistrationGateway({
      endpoint,
      ensureCsrf,
      fetchImpl: vi.fn(async () =>
        response(
          {
            reference_code: 'REG-PENDING',
            journey: 'mentor',
            student_count: 0,
            created_at: '2026-10-11T05:00:00Z',
          },
          202,
        ),
      ),
    })
    expect(
      (await gateway.submit(buildRegistrationRequest('mentor', createRegistrationForms()))).ok,
    ).toBe(false)
  })

  it('does not invent success from the legacy backend response', async () => {
    const gateway = createHttpRegistrationGateway({
      endpoint,
      ensureCsrf,
      fetchImpl: vi.fn(async () =>
        response({ Title: 'student@example.test', FirstName: 'Student' }),
      ),
    })
    expect(
      (
        await gateway.submit(
          buildRegistrationRequest('student_individual', createRegistrationForms()),
        )
      ).ok,
    ).toBe(false)
  })

  it('keeps hard validation errors non-overridable even if a server includes warnings', async () => {
    const gateway = createHttpRegistrationGateway({
      endpoint,
      ensureCsrf,
      fetchImpl: vi.fn(async () =>
        response(
          {
            error: 'Correct the email.',
            fields: { 'students.0.email': ['Invalid email.'] },
            warnings: [
              {
                code: 'check',
                field: 'students.0.email',
                override_field: 'students.0.overrides.ConfirmNameEmailOverride',
                message: 'Check this address.',
              },
            ],
          },
          400,
        ),
      ),
    })
    const result = await gateway.submit(
      buildRegistrationRequest('student_individual', createRegistrationForms()),
    )
    expect(result).toMatchObject({
      ok: false,
      fieldErrors: { 'studentIndividual.student.email': 'Invalid email.' },
    })
    expect(result).not.toHaveProperty('warnings')
  })

  it('rejects duplicate warning override paths instead of sharing acknowledgement', async () => {
    const warning = {
      code: 'check',
      field: 'students.0.school',
      override_field: 'students.0.overrides.ConfirmSchoolOverride',
      message: 'Check this school.',
    }
    const gateway = createHttpRegistrationGateway({
      endpoint,
      ensureCsrf,
      fetchImpl: vi.fn(async () => response({ warnings: [warning, warning] }, 400)),
    })
    const result = await gateway.submit(
      buildRegistrationRequest('student_individual', createRegistrationForms()),
    )
    expect(result.ok).toBe(false)
    expect(result).not.toHaveProperty('warnings')
  })

  it('reports invalid request options without calling them network failures or posting', async () => {
    const send = vi.fn<typeof fetch>()
    const gateway = createHttpRegistrationGateway({ endpoint, ensureCsrf, fetchImpl: send })
    const result = await gateway.submit(
      buildRegistrationRequest('student_individual', createRegistrationForms()),
      {
        idempotencyKey: 'not-a-uuid',
      },
    )
    expect(result).toEqual({ ok: false, message: 'Registration requires a UUID retry key.' })
    expect(send).not.toHaveBeenCalled()
  })
})
