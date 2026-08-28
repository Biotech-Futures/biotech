import { afterEach, describe, expect, it, vi } from 'vitest'
import { buildAdminQuery, fetchAdminSummary } from '@/utils/adminAPI'

describe('buildAdminQuery', () => {
  it('serializes params and skips empties', () => {
    const qs = buildAdminQuery({ page: 2, search: '  ', role: 'admin' })
    expect(qs).toContain('page=2')
    expect(qs).toContain('role=admin')
    expect(qs).not.toContain('search')
  })

  it('joins array values with commas', () => {
    const qs = buildAdminQuery({ role: ['admin', 'mentor'] })
    expect(qs).toBe('?role=admin%2Cmentor')
  })

  it('returns empty string when nothing to serialize', () => {
    expect(buildAdminQuery({ search: '', page: undefined })).toBe('')
  })
})

describe('fetchAdminSummary', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests the admin summary endpoint and resolves its JSON', async () => {
    const payload = { active_users: 5, upcoming_events: 3 }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchAdminSummary()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/admin/summary/'),
      expect.objectContaining({ credentials: 'include' })
    )
    expect(result).toEqual(payload)
  })

  it('rejects with an ApiError on a failed response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('boom', { status: 500 })))

    const error = await fetchAdminSummary().catch((e) => e)
    expect(error).toBeInstanceOf(Error)
    expect((error as { message?: string }).message).toBeTruthy()
  })
})
