import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '@/utils/managementAPI'
import { ensureCsrfCookie } from '@/utils/csrf'

// The CSRF layer is mocked so requests need no /services/csrf/ round-trip.
// The request core the wrappers share is covered in gradingAPI.spec.ts.
vi.mock('@/utils/csrf', () => ({
  ensureCsrfCookie: vi.fn(async () => true),
  buildSessionHeaders: ({
    includeCSRF,
    headers
  }: {
    includeCSRF?: boolean
    headers?: Record<string, string>
  }) => ({ ...(headers || {}), ...(includeCSRF ? { 'X-CSRFToken': 'csrf-test' } : {}) })
}))
const csrfMock = vi.mocked(ensureCsrfCookie)

const fetchMock = vi.fn()

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const lastCall = () => {
  const call = fetchMock.mock.calls.at(-1)!
  return { url: String(call[0]), init: (call[1] ?? {}) as RequestInit }
}

beforeEach(() => {
  fetchMock.mockReset()
  csrfMock.mockReset()
  csrfMock.mockResolvedValue(true)
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('endpoint wrappers hit their routes with the right payloads', () => {
  type Case = {
    name: string
    call: () => Promise<unknown>
    reply?: unknown
    url: string
    method?: string
    body?: unknown
  }
  const cases: Case[] = [
    { name: 'fetchGroupResults', call: () => api.fetchGroupResults(7), reply: {}, url: '/api/v1/management/groups/7/results/' },
    { name: 'fetchCertificatesRelease', call: () => api.fetchCertificatesRelease(), reply: {}, url: '/api/v1/management/certificates-release/' },
    {
      name: 'toggleCertificatesRelease',
      call: () => api.toggleCertificatesRelease(false),
      reply: {},
      url: '/api/v1/management/certificates-release/',
      method: 'POST',
      body: { release: false }
    },
    {
      name: 'setCertificatesFinalistExclusion',
      call: () => api.setCertificatesFinalistExclusion(true),
      reply: {},
      url: '/api/v1/management/certificates-release/',
      method: 'POST',
      body: { exclude_finalists: true }
    },
    { name: 'fetchGroupExtensions', call: () => api.fetchGroupExtensions(), reply: { extensions: [] }, url: '/api/v1/management/deadline/extensions/' },
    {
      name: 'saveGroupExtension',
      call: () => api.saveGroupExtension(4, '2026-11-05T13:00:00Z', 2, 'Flood'),
      reply: { extension: {} },
      url: '/api/v1/management/deadline/extensions/',
      method: 'POST',
      body: { group_id: 4, extended_until: '2026-11-05T13:00:00Z', grace_hours: 2, reason: 'Flood' }
    },
    { name: 'removeGroupExtension', call: () => api.removeGroupExtension(4), url: '/api/v1/management/deadline/extensions/4/', method: 'DELETE' },
    { name: 'fetchSubmissionDeadline', call: () => api.fetchSubmissionDeadline(), reply: { deadline: null }, url: '/api/v1/management/deadline/' },
    {
      name: 'saveSubmissionDeadline',
      call: () => api.saveSubmissionDeadline('2026-10-30T13:00:00Z', 6),
      reply: { deadline: null },
      url: '/api/v1/management/deadline/',
      method: 'POST',
      body: { closes_at: '2026-10-30T13:00:00Z', grace_hours: 6 }
    },
    { name: 'fetchTemplateScan', call: () => api.fetchTemplateScan('certificate'), reply: {}, url: '/api/v1/management/settings/template-scan/certificate/' },
    { name: 'fetchGradingSettings', call: () => api.fetchGradingSettings(), reply: {}, url: '/api/v1/management/settings/' },
    {
      name: 'updateGradingSettings with JSON',
      call: () => api.updateGradingSettings({ director_1_name: 'Ada' }),
      reply: {},
      url: '/api/v1/management/settings/',
      method: 'PATCH',
      body: { director_1_name: 'Ada' }
    },
    {
      name: 'notifyFinalists targeted',
      call: () => api.notifyFinalists([4]),
      reply: { sent: 1, pending: 0 },
      url: '/api/v1/management/finalists/notify/',
      method: 'POST',
      body: { group_ids: [4] }
    },
    {
      name: 'notifyFinalists all',
      call: () => api.notifyFinalists(),
      reply: { sent: 0, pending: 0 },
      url: '/api/v1/management/finalists/notify/',
      method: 'POST',
      body: {}
    }
  ]

  it.each(cases)('$name', async (c) => {
    fetchMock.mockResolvedValueOnce(
      c.reply === undefined ? new Response(null, { status: 204 }) : jsonResponse(c.reply)
    )
    await c.call()
    const { url, init } = lastCall()
    expect(url.endsWith(c.url)).toBe(true)
    expect(String(init.method || 'GET')).toBe(c.method ?? 'GET')
    if (c.body !== undefined) expect(JSON.parse(String(init.body))).toEqual(c.body)
  })

  it('scanTemplateCandidate posts the picked file without saving semantics', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ uploaded: false }))
    await api.scanTemplateCandidate('marks-summary', new File(['x'], 'draft.docx'))
    const { url, init } = lastCall()
    expect(url).toContain('/settings/template-scan/marks-summary/')
    expect(init.body).toBeInstanceOf(FormData)
  })

  it('updateGradingSettings passes FormData through untouched for file uploads', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}))
    const fd = new FormData()
    fd.append('director_1_signature', new File(['x'], 'sig.png'))
    await api.updateGradingSettings(fd)
    expect(lastCall().init.body).toBe(fd)
  })
})

describe('blob downloads', () => {
  let clicks: string[]

  beforeEach(() => {
    clicks = []
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:fake'),
      revokeObjectURL: vi.fn()
    })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      clicks.push(this.download)
    })
  })

  const blobResponse = (disposition?: string) =>
    new Response(new Blob([new Uint8Array([80, 75])]), {
      status: 200,
      headers: disposition ? { 'Content-Disposition': disposition } : {}
    })

  it('template test renders download for both the stored and a candidate file', async () => {
    fetchMock.mockResolvedValueOnce(blobResponse('attachment; filename="render.docx"'))
    await api.downloadTemplateTestRender('certificate')
    expect(lastCall().init.method ?? 'GET').toBe('GET')

    fetchMock.mockResolvedValueOnce(blobResponse())
    await api.downloadCandidateTestRender('certificate', new File(['x'], 'draft.docx'))
    expect(lastCall().init.method).toBe('POST')
    expect(lastCall().init.body).toBeInstanceOf(FormData)
    expect(clicks).toEqual(['render.docx', 'test-certificate.docx'])
  })
})
