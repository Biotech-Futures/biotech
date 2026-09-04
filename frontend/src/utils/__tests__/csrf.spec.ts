import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  buildSessionHeaders,
  ensureCsrfCookie,
  getCSRFToken,
  resetCsrfToken,
} from '@/utils/csrf'

beforeEach(() => {
  resetCsrfToken()
  vi.restoreAllMocks()
})

describe('CSRF token origins', () => {
  it('caches and builds headers independently for normalized API origins', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrfToken: 'token-a' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrfToken: 'token-b' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

    await expect(ensureCsrfCookie('https://api-a.example.test/v1/')).resolves.toBe(true)
    await expect(ensureCsrfCookie('https://api-b.example.test')).resolves.toBe(true)
    await expect(ensureCsrfCookie('https://api-a.example.test/other')).resolves.toBe(true)

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(getCSRFToken('https://api-a.example.test')).toBe('token-a')
    expect(getCSRFToken('https://api-b.example.test/path')).toBe('token-b')
    expect(
      buildSessionHeaders({
        includeCSRF: true,
        csrfApiBaseUrl: 'https://api-a.example.test/path',
      }).get('X-CSRFToken'),
    ).toBe('token-a')
    expect(
      buildSessionHeaders({
        includeCSRF: true,
        csrfApiBaseUrl: 'https://api-b.example.test',
      }).get('X-CSRFToken'),
    ).toBe('token-b')
    expect(
      buildSessionHeaders({
        includeCSRF: true,
        csrfApiBaseUrl: 'https://unknown.example.test',
      }).has('X-CSRFToken'),
    ).toBe(false)
  })

  it('clears tokens for every origin', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
      return new Response(JSON.stringify({ csrfToken: 'token' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    })
    await ensureCsrfCookie('https://api-a.example.test')
    await ensureCsrfCookie('https://api-b.example.test')

    resetCsrfToken()

    expect(getCSRFToken('https://api-a.example.test')).toBeNull()
    expect(getCSRFToken('https://api-b.example.test')).toBeNull()
  })
})
