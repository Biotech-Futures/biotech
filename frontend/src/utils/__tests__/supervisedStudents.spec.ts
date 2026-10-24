import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/utils/apiError'
import { formatShortDateTime } from '@/utils/date'
import {
  classifyStudent,
  fetchConsentLinks,
  fetchConsentSignatures,
  fetchDetailsLinks,
  fetchStudentEditOptions,
  fetchSupervisedStudents,
  fullName,
  removeSupervisedStudentPhoto,
  saveGuardianDetails,
  sendSupervisedEmails,
  toStudentRow,
  updateSupervisedStudentProfile,
  uploadGuardianDetails,
  uploadSupervisedStudentPhoto,
  withConsentSignatures,
  type SupervisedStudent,
} from '@/utils/supervisedStudents'

// The CSRF layer is mocked so writes need no /services/csrf/ round-trip.
vi.mock('@/utils/csrf', () => ({
  ensureCsrfCookie: vi.fn(async () => true),
  buildSessionHeaders: ({ includeCSRF, headers }: { includeCSRF?: boolean; headers?: Record<string, string> }) => ({
    ...(headers || {}),
    ...(includeCSRF ? { 'X-CSRFToken': 'csrf-test' } : {}),
  }),
}))

const fetchMock = vi.fn()

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const lastCall = () => {
  const call = fetchMock.mock.calls.at(-1)!
  return { url: String(call[0]), init: (call[1] ?? {}) as RequestInit }
}

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

const student = (overrides: Partial<SupervisedStudent> = {}): SupervisedStudent => ({
  id: 1,
  first_name: 'Ava',
  last_name: 'Nguyen',
  email: 'ava@example.com',
  school_name: 'Eastwood College',
  year_lvl: '10',
  interests: [],
  // A student added without a guardian has their own name copied in, and the
  // flag on, as every student is saved.
  pg_first_name: 'Ava',
  pg_last_name: 'Nguyen',
  pg_email: null,
  parent_guardian_flag: true,
  has_join_permission: false,
  joinperm_response_id: null,
  joinperm_granted_at: null,
  group_id: null,
  group_name: null,
  ...overrides,
})

describe('classifyStudent', () => {
  it('puts a student with no guardian email in Pending Parent/Guardian Details', () => {
    expect(classifyStudent(student())).toBe('pendingDetails')
    expect(classifyStudent(student({ pg_email: '  ' }))).toBe('pendingDetails')
  })

  it('puts a student whose guardian has an email in Pending Parent/Guardian Permission', () => {
    const named = student({ pg_first_name: 'Pat', pg_last_name: 'Nguyen', pg_email: 'pat@example.com' })
    expect(classifyStudent(named)).toBe('pendingPermission')
  })

  it('puts a student with consent in Fully Registered, whatever the guardian details', () => {
    expect(classifyStudent(student({ has_join_permission: true }))).toBe('fullyRegistered')
    expect(
      classifyStudent(student({ has_join_permission: true, pg_email: 'pat@example.com' })),
    ).toBe('fullyRegistered')
  })
})

describe('fullName', () => {
  it('joins the parts, squeezing their spaces', () => {
    expect(fullName('  Ava ', 'van  der Berg')).toBe('Ava van der Berg')
  })

  it('falls back when there is no name', () => {
    expect(fullName('', null)).toBe('—')
    expect(fullName(undefined, ' ', 'ava@example.com')).toBe('ava@example.com')
  })
})

describe('toStudentRow', () => {
  it('lays a student out for the table, without permission yet', () => {
    const row = toStudentRow(
      student({ pg_first_name: 'Pat', pg_email: 'pat@example.com', interests: ['Space'], group_id: 4, group_name: 'BTF04' }),
    )
    expect(row).toMatchObject({
      id: 1,
      student: 'Ava Nguyen',
      parentGuardian: 'Pat Nguyen',
      pgEmail: 'pat@example.com',
      school: 'Eastwood College',
      yearLevel: '10',
      interests: ['Space'],
      permissionGiven: '—',
      groupId: 4,
      groupName: 'BTF04',
    })
  })

  it('names a student by their email when they have no name, and blanks a missing guardian email', () => {
    const row = toStudentRow(student({ first_name: '', last_name: '' }))
    expect(row.student).toBe('ava@example.com')
    expect(row.pgEmail).toBe('')
  })

  it('shows when permission was given, or just that it was', () => {
    const at = '2026-03-04T05:06:00Z'
    expect(toStudentRow(student({ has_join_permission: true, joinperm_granted_at: at })).permissionGiven).toBe(
      formatShortDateTime(at),
    )
    expect(toStudentRow(student({ has_join_permission: true })).permissionGiven).toBe('Recorded')
  })
})

describe('consent signatures', () => {
  it('asks for nothing when there are no students', async () => {
    expect(await fetchConsentSignatures([])).toEqual({})
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('reads the signatures for the students asked for', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ signatures: { '3': 'data:image/png;base64,AA' } }))
    expect(await fetchConsentSignatures([3, 5])).toEqual({ '3': 'data:image/png;base64,AA' })
    const { url, init } = lastCall()
    expect(url).toContain('/api/v1/users/supervised-students/signatures/?ids=3%2C5')
    expect(init.credentials).toBe('include')
  })

  it('takes a reply without signatures as none', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}))
    expect(await fetchConsentSignatures([3])).toEqual({})
  })

  it('throws the API error when they cannot be read', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'Not yours.' }, 403))
    await expect(fetchConsentSignatures([3])).rejects.toBeInstanceOf(ApiError)
  })

  it('adds each row its signature, asking once per student and skipping bad ids', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ signatures: { '3': 'sig-3', '5': null } }))
    const rows = await withConsentSignatures([{ id: 3 }, { id: 3 }, { id: 5 }, { id: 'x' }, { id: 0 }])
    expect(rows.map((row) => row.signature)).toEqual(['sig-3', 'sig-3', '', '', ''])
    expect(lastCall().url).toContain('ids=3%2C5')
  })
})

describe('student writes', () => {
  it('saves guardian details with a CSRF token', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([student({ pg_email: 'pat@example.com' })]))
    const saved = await saveGuardianDetails({
      student_ids: [1],
      pg_first_name: 'Pat',
      pg_last_name: 'Nguyen',
      pg_email: 'pat@example.com',
      clear_permission: true,
    })
    expect(saved[0].pg_email).toBe('pat@example.com')
    const { url, init } = lastCall()
    expect(url).toMatch(/\/api\/v1\/users\/supervised-students\/$/)
    expect(init.method).toBe('PATCH')
    expect((init.headers as Record<string, string>)['X-CSRFToken']).toBe('csrf-test')
    expect(JSON.parse(String(init.body))).toMatchObject({ student_ids: [1], clear_permission: true })
  })

  it('updates a student profile', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(student({ school_name: 'Westwood' })))
    const payload = { first_name: 'Ava', last_name: 'Nguyen', email: 'ava@example.com', school_name: 'Westwood', year_lvl: '11' }
    expect((await updateSupervisedStudentProfile(1, payload)).school_name).toBe('Westwood')
    const { url, init } = lastCall()
    expect(url).toContain('/api/v1/users/supervised-students/1/')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(String(init.body))).toEqual(payload)
  })

  it('uploads and removes a student photo', async () => {
    const file = new File(['png'], 'face.png', { type: 'image/png' })
    fetchMock.mockResolvedValueOnce(jsonResponse(student({ profile_image_url: '/media/face.png' })))
    expect((await uploadSupervisedStudentPhoto(1, file)).profile_image_url).toBe('/media/face.png')
    let call = lastCall()
    expect(call.url).toContain('/api/v1/users/supervised-students/1/profile-image/')
    expect(call.init.method).toBe('POST')
    expect((call.init.body as FormData).get('image')).toBeInstanceOf(File)

    fetchMock.mockResolvedValueOnce(jsonResponse(student({ profile_image_url: null })))
    expect((await removeSupervisedStudentPhoto(1)).profile_image_url).toBeNull()
    call = lastCall()
    expect(call.init.method).toBe('DELETE')
  })

  it('throws the API error when a write is refused', async () => {
    const refused = () => jsonResponse({ detail: 'No.' }, 400)
    const file = new File(['png'], 'face.png', { type: 'image/png' })
    const payload = { first_name: 'A', last_name: 'B', email: 'a@b.c', school_name: 'S', year_lvl: '9' }
    fetchMock.mockImplementation(async () => refused())
    await expect(saveGuardianDetails({ student_ids: [1], pg_first_name: 'P', pg_last_name: 'N' })).rejects.toBeInstanceOf(ApiError)
    await expect(updateSupervisedStudentProfile(1, payload)).rejects.toBeInstanceOf(ApiError)
    await expect(uploadSupervisedStudentPhoto(1, file)).rejects.toBeInstanceOf(ApiError)
    await expect(removeSupervisedStudentPhoto(1)).rejects.toBeInstanceOf(ApiError)
    await expect(uploadGuardianDetails(file, true)).rejects.toBeInstanceOf(ApiError)
    await expect(fetchStudentEditOptions()).rejects.toBeInstanceOf(ApiError)
    await expect(fetchSupervisedStudents({})).rejects.toBeInstanceOf(ApiError)
  })
})

describe('sendSupervisedEmails', () => {
  it('sends the kind of email asked for and reports the counts', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ sent: 2, failed: 1, skipped: 0, msg: 'Sent 2.', messages: ['One bounced.'] }))
    expect(await sendSupervisedEmails([1, 2, 3], 'guardian_consent')).toEqual({
      sent: 2,
      failed: 1,
      skipped: 0,
      msg: 'Sent 2.',
      messages: ['One bounced.'],
    })
    const { url, init } = lastCall()
    expect(url).toContain('/api/v1/users/supervised-students/email/')
    expect(JSON.parse(String(init.body))).toEqual({ student_ids: [1, 2, 3], kind: 'guardian_consent' })
  })

  it('fills in what a reply leaves out', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}))
    expect(await sendSupervisedEmails([1], 'guardian_details')).toEqual({
      sent: 0,
      failed: 0,
      skipped: 0,
      msg: 'Emails sent.',
      messages: [],
    })
  })

  it('throws the reason given, or a plain one', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ msg: 'Too many at once.' }, 429))
    await expect(sendSupervisedEmails([1], 'guardian_details')).rejects.toThrow('Too many at once.')
    fetchMock.mockResolvedValueOnce(jsonResponse({ error: 'Mail server down.' }, 503))
    await expect(sendSupervisedEmails([1], 'guardian_details')).rejects.toThrow('Mail server down.')
    fetchMock.mockResolvedValueOnce(new Response('<html>', { status: 500 }))
    await expect(sendSupervisedEmails([1], 'guardian_details')).rejects.toThrow('Emails could not be sent.')
  })
})

describe('guardian links', () => {
  it('makes consent and details links for the students asked for', async () => {
    const links = [{ studentId: 1, link: 'https://example.com/consent/abc', msg: '' }]
    fetchMock.mockResolvedValueOnce(jsonResponse({ links }))
    expect(await fetchConsentLinks([1])).toEqual(links)
    expect(lastCall().url).toContain('/api/v1/users/supervised-students/consent-links/')

    fetchMock.mockResolvedValueOnce(jsonResponse({}))
    expect(await fetchDetailsLinks([1])).toEqual([])
    expect(lastCall().url).toContain('/api/v1/users/supervised-students/details-links/')
    expect(JSON.parse(String(lastCall().init.body))).toEqual({ student_ids: [1] })
  })

  it('throws the reason given, or a plain one', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ msg: 'Consent already given.' }, 400))
    await expect(fetchConsentLinks([1])).rejects.toThrow('Consent already given.')
    fetchMock.mockResolvedValueOnce(jsonResponse({ error: 'Not yours.' }, 403))
    await expect(fetchDetailsLinks([1])).rejects.toThrow('Not yours.')
    fetchMock.mockResolvedValueOnce(new Response('', { status: 500 }))
    await expect(fetchDetailsLinks([1])).rejects.toThrow('Links could not be made.')
  })
})

describe('reads', () => {
  it('previews or saves a guardian sheet', async () => {
    const file = new File(['csv'], 'guardians.csv', { type: 'text/csv' })
    const result = { checks: {}, creates: [], updates: [], unchanged: [], summary: { creates: 0, updates: 0, unchanged: 0, errors: 0 } }
    fetchMock.mockResolvedValue(jsonResponse(result))
    await uploadGuardianDetails(file, true)
    expect((lastCall().init.body as FormData).get('dry_run')).toBe('true')
    fetchMock.mockResolvedValue(jsonResponse({ ...result, saved: 2 }))
    expect((await uploadGuardianDetails(file, false)).saved).toBe(2)
    expect((lastCall().init.body as FormData).get('dry_run')).toBe('false')
    expect(lastCall().url).toContain('/api/v1/users/supervised-students/guardian-upload/')
  })

  it('reads the edit options and the roster', async () => {
    const options = { countries: [{ id: 1, country_name: 'Australia' }], regions: [], interests: ['Space'] }
    fetchMock.mockResolvedValueOnce(jsonResponse(options))
    expect(await fetchStudentEditOptions()).toEqual(options)
    expect(lastCall().url).toContain('/api/v1/users/supervised-students/options/')

    fetchMock.mockResolvedValueOnce(jsonResponse([student()]))
    expect(await fetchSupervisedStudents({ Accept: 'application/json' })).toHaveLength(1)
    expect(lastCall().init.headers).toEqual({ Accept: 'application/json' })
  })
})
