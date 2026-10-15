import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  buildSessionHeaders,
  ensureCsrfCookie,
  getCSRFToken,
  resetCsrfToken,
  setCsrfToken,
} from '../csrf'

describe('registration CSRF origin isolation', () => {
  beforeEach(resetCsrfToken)
  afterEach(() => {
    resetCsrfToken()
    vi.unstubAllGlobals()
  })

  it('does not send another backend origin its cached token', async () => {
    setCsrfToken('first-token', 'https://first.example.test')
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"csrfToken":"second-token"}', { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    expect(await ensureCsrfCookie('https://second.example.test')).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith(
      'https://second.example.test/services/csrf/',
      { method: 'GET', credentials: 'include' },
    )
    expect(buildSessionHeaders({
      includeCSRF: true,
      csrfApiBaseUrl: 'https://second.example.test',
    }).get('X-CSRFToken')).toBe('second-token')
    expect(getCSRFToken('https://first.example.test')).toBe('first-token')
  })

  it('preserves the configured API path when fetching the token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"csrfToken":"prefixed-token"}', { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    expect(await ensureCsrfCookie('https://api.example.test/api/v1/')).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.example.test/api/v1/services/csrf/',
      { method: 'GET', credentials: 'include' },
    )
    expect(getCSRFToken('https://api.example.test')).toBe('prefixed-token')
  })

  it('invalidates origin caches when existing login callers rotate the token', async () => {
    setCsrfToken('before-login', 'https://override.example.test')
    setCsrfToken('after-login')
    expect(getCSRFToken()).toBe('after-login')
    expect(getCSRFToken('https://override.example.test')).toBeNull()
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"csrfToken":"after-login"}', { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    expect(await ensureCsrfCookie('https://override.example.test')).toBe(true)
    expect(getCSRFToken('https://override.example.test')).toBe('after-login')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('does not replace the application token when an override origin is initialized', async () => {
    setCsrfToken('application-token')
    setCsrfToken('override-token', 'https://override.example.test')
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    expect(await ensureCsrfCookie('https://override.example.test')).toBe(true)
    expect(buildSessionHeaders({ includeCSRF: true }).get('X-CSRFToken')).toBe('application-token')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('does not accept an invalid token response or reuse another origin token on failure', async () => {
    setCsrfToken('other-token', 'https://other.example.test')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 200 })))

    expect(await ensureCsrfCookie('https://api.example.test')).toBe(false)
    expect(buildSessionHeaders({
      includeCSRF: true,
      csrfApiBaseUrl: 'https://api.example.test',
    }).has('X-CSRFToken')).toBe(false)
  })
})
