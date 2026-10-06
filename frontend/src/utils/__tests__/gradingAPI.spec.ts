import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '@/utils/gradingAPI'
import { ApiError } from '@/utils/apiError'
import { ensureCsrfCookie } from '@/utils/csrf'

// The CSRF layer is mocked so requests need no /services/csrf/ round-trip and
// the "session could not initialise" branch can be forced per test.
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

describe('the JSON request core', () => {
  it('reads a payload without sending a CSRF token on GET', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ finalists: [] }))
    const list = await api.fetchFinalists()
    expect(list.finalists).toEqual([])
    const { url, init } = lastCall()
    expect(url).toContain('/api/v1/grading/finalists/')
    expect(init.credentials).toBe('include')
    expect((init.headers as Record<string, string>)['X-CSRFToken']).toBeUndefined()
  })

  it('sends the CSRF token on writes', async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await api.addFinalist(4)
    const { init } = lastCall()
    expect(init.method).toBe('POST')
    expect((init.headers as Record<string, string>)['X-CSRFToken']).toBe('csrf-test')
  })

  it('refuses to write when the secure session cannot be initialised', async () => {
    csrfMock.mockResolvedValue(false)
    await expect(api.addFinalist(4)).rejects.toThrow(/secure session/i)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('turns a non-ok response into an ApiError carrying the server message', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'Admins only.' }, 403))
    await expect(api.fetchFinalists()).rejects.toMatchObject({ status: 403 })
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'nope' }, 403))
    await expect(api.fetchFinalists()).rejects.toBeInstanceOf(ApiError)
  })

  it('treats an empty body as null instead of failing to parse', async () => {
    fetchMock.mockResolvedValueOnce(new Response('', { status: 200 }))
    await expect(api.removeFinalist(9)).resolves.toBeNull()
  })
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
    { name: 'fetchGroupMarking', call: () => api.fetchGroupMarking(7), reply: { components: [] }, url: '/api/v1/grading/groups/7/' },
    { name: 'fetchGroupMarking with year', call: () => api.fetchGroupMarking(7, 2026), reply: { components: [] }, url: '/api/v1/grading/groups/7/?year=2026' },
    {
      name: 'saveGradesBulk without comments',
      call: () => api.saveGradesBulk([{ submission: 1, criterion: 2, mark: '5', comment: '' }]),
      reply: [],
      url: '/api/v1/grading/grades/bulk/',
      method: 'POST',
      body: { items: [{ submission: 1, criterion: 2, mark: '5', comment: '' }] }
    },
    {
      name: 'saveGradesBulk with overall comments',
      call: () =>
        api.saveGradesBulk([], [{ submission: 1, component: 'POSTER', comment: 'Nice' }]),
      reply: [],
      url: '/api/v1/grading/grades/bulk/',
      method: 'POST',
      body: { items: [], overall_comments: [{ submission: 1, component: 'POSTER', comment: 'Nice' }] }
    },
    { name: 'fetchComponentRows', call: () => api.fetchComponentRows('SAQ'), reply: { rows: [] }, url: '/api/v1/grading/components/SAQ/' },
    { name: 'fetchComponentRows with year', call: () => api.fetchComponentRows('SAQ', 2026), reply: { rows: [] }, url: '/api/v1/grading/components/SAQ/?year=2026' },
    {
      name: 'startComponentDownload',
      call: () => api.startComponentDownload('SAQ', 'zip', [1, 2]),
      reply: { job_id: 11 },
      url: '/api/v1/grading/components/SAQ/download/',
      method: 'POST',
      body: { format: 'zip', group_ids: [1, 2] }
    },
    {
      name: 'startAllSubmissionsDownload',
      call: () => api.startAllSubmissionsDownload(),
      reply: { job_id: 12 },
      url: '/api/v1/grading/download-all/',
      method: 'POST',
      body: {}
    },
    { name: 'fetchJobStatus', call: () => api.fetchJobStatus(11), reply: { id: 11 }, url: '/api/v1/grading/jobs/11/' },
    { name: 'fetchGroupCategories', call: () => api.fetchGroupCategories(7), reply: {}, url: '/api/v1/grading/groups/7/categories/' },
    {
      name: 'saveGroupCategories',
      call: () =>
        api.saveGroupCategories(7, {
          product_categories: ['Other'],
          product_category_other: 'Bioinformatics',
          solution_category: '',
          solution_category_other: ''
        }),
      reply: {},
      url: '/api/v1/grading/groups/7/categories/',
      method: 'POST'
    },
    { name: 'fetchFinalistCandidates', call: () => api.fetchFinalistCandidates(), reply: { rows: [] }, url: '/api/v1/grading/finalists/candidates/' },
    { name: 'fetchFinalists', call: () => api.fetchFinalists(), reply: { finalists: [] }, url: '/api/v1/grading/finalists/' },
    { name: 'addFinalist', call: () => api.addFinalist(4), url: '/api/v1/grading/groups/4/finalist/', method: 'POST' },
    { name: 'removeFinalist', call: () => api.removeFinalist(4), url: '/api/v1/grading/groups/4/finalist/', method: 'DELETE' }
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

  it('bulkUploadMarks posts the file as multipart with the dry-run flag', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ summary: {} }))
    const file = new File(['x'], 'marks.csv', { type: 'text/csv' })
    await api.bulkUploadMarks('SAQ', file, true)
    const { url, init } = lastCall()
    expect(url).toContain('/api/v1/grading/components/SAQ/bulk-upload/')
    const form = init.body as FormData
    expect(form).toBeInstanceOf(FormData)
    expect(form.get('dry_run')).toBe('true')
    expect((form.get('file') as File).name).toBe('marks.csv')
    // Multipart requests must not carry a JSON content type.
    expect((init.headers as Record<string, string>)['Content-Type']).toBeUndefined()
  })
})

describe('small helpers', () => {
  it('resolveApiFileUrl leaves absolute URLs alone and resolves relative ones', () => {
    expect(api.resolveApiFileUrl(null)).toBeNull()
    expect(api.resolveApiFileUrl('https://blob.example/x.pdf')).toBe('https://blob.example/x.pdf')
    expect(api.resolveApiFileUrl('/media/x.pdf')).toMatch(/^http.*\/media\/x\.pdf$/)
  })

  it('overallCommentLabel names the box for every real component', () => {
    expect(api.overallCommentLabel('POSTER')).toBe('Overall Poster Comment')
    expect(api.overallCommentLabel('SAQ')).toBe('Overall SAQs Comment')
    expect(api.overallCommentLabel('NOPE')).toBeNull()
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

  it('names the saved file from Content-Disposition when the server offers one', async () => {
    fetchMock.mockResolvedValueOnce(blobResponse('attachment; filename="server-name.zip"'))
    await api.downloadGroupZip(7)
    expect(lastCall().url).toContain('/api/v1/grading/groups/7/download/')
    expect(clicks).toEqual(['server-name.zip'])
  })

  it('falls back to a built name when no filename is offered', async () => {
    fetchMock.mockResolvedValueOnce(blobResponse())
    await api.downloadGroupZip(7, 'SAQ')
    expect(lastCall().url).toContain('?component=SAQ')
    expect(clicks).toEqual(['group-7.zip'])
  })

  it('downloadSubmissionFile fetches cross-origin URLs with the session', async () => {
    fetchMock.mockResolvedValueOnce(blobResponse())
    await api.downloadSubmissionFile('https://blob.example/poster.pdf', 'poster.pdf')
    expect(lastCall().url).toBe('https://blob.example/poster.pdf')
    expect(clicks).toEqual(['poster.pdf'])
  })

  it('downloadJobResult refuses a job with no URL and saves one that has it', async () => {
    const job = {
      id: 11, kind: 'bulk_zip', status: 'done' as const, download_url: null,
      error: null, created_at: '', finished_at: null
    }
    await expect(api.downloadJobResult(job)).rejects.toThrow(/no download URL/i)

    fetchMock.mockResolvedValueOnce(blobResponse())
    await api.downloadJobResult({ ...job, download_url: '/api/v1/grading/jobs/11/download/' })
    expect(clicks).toEqual(['grading-job-11'])
  })

  it('a failed blob fetch surfaces as an ApiError, not a broken save', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'gone' }, 404))
    await expect(api.downloadGroupZip(7)).rejects.toBeInstanceOf(ApiError)
    expect(clicks).toEqual([])
  })

  it('blob requests also refuse to run without a secure session', async () => {
    csrfMock.mockResolvedValue(false)
    await expect(api.downloadGroupZip(7)).rejects.toThrow(/secure session/i)
  })
})
