import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/utils/apiError'
import { resetCsrfToken } from '@/utils/csrf'
import {
  createMatchingConfig,
  fetchActiveMatchingConfig,
  fetchMatchingConfigDefaults,
  updateMatchingConfig
} from '@/utils/matchingAPI'
import { matchingConfigFieldErrors } from '@/utils/matchingConfig'

/**
 * The real csrf module runs here (only `fetch` is faked), so these tests prove
 * a write really fetches the token from /services/csrf/ and sends it as
 * X-CSRFToken — not just that a mocked header builder was called.
 */

const configRow = {
  id: 7,
  year_weight: '30.00',
  timezone_weight: '15.00',
  timezone_max_weight: '25.00',
  size_bonus_weight: '30.00',
  total_weight: '100.00',
  updated_by: 1,
  created_at: '2026-10-06T10:00:00Z',
  updated_at: '2026-10-06T10:05:00Z'
}

const defaultsBlock = {
  requiredTotal: '100.00',
  defaults: {
    year_weight: 20.0,
    timezone_weight: 30.0,
    timezone_max_weight: 25.0,
    size_bonus_weight: 25.0
  }
}

const weights = {
  yearWeight: 30,
  timezoneWeight: 15,
  timezoneMaxWeight: 25,
  sizeBonusWeight: 30
}

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

/** Routes /services/csrf/ itself; everything else gets `respond`. */
const stubFetch = (respond: () => Response, csrfStatus = 200) => {
  const fetchMock = vi.fn().mockImplementation((url: string) => {
    if (String(url).includes('/services/csrf/')) {
      return Promise.resolve(
        csrfStatus === 200
          ? jsonResponse({ csrfToken: 'csrf-test' })
          : jsonResponse({ error: 'down' }, csrfStatus)
      )
    }
    return Promise.resolve(respond())
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** The non-CSRF request: what actually reached the config API. */
const apiCall = (fetchMock: ReturnType<typeof stubFetch>) => {
  const call = fetchMock.mock.calls.find(([url]) => !String(url).includes('/services/csrf/'))!
  const init = call[1] as RequestInit
  return {
    url: String(call[0]),
    init,
    headers: new Headers(init.headers),
    body: init.body ? JSON.parse(init.body as string) : undefined
  }
}

const csrfFetches = (fetchMock: ReturnType<typeof stubFetch>) =>
  fetchMock.mock.calls.filter(([url]) => String(url).includes('/services/csrf/')).length

beforeEach(() => {
  // The token is cached per module; each test starts without one.
  resetCsrfToken()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('reads', () => {
  it('fetches the active config with the session cookie and no CSRF token', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse({
        data: null,
        weights: {
          yearWeight: 8.0,
          timezoneWeight: 2.0,
          timezoneMaxPenalty: 18.0,
          sizeBonusWeight: 6.0
        },
        ...defaultsBlock
      })
    )

    const active = await fetchActiveMatchingConfig()

    const { url, init, headers } = apiCall(fetchMock)
    expect(url).toMatch(/\/matching\/configs\/active\/$/)
    expect(url).not.toContain('/api/v1/admin')
    expect(init.method ?? 'GET').toBe('GET')
    expect(init.credentials).toBe('include')
    expect(headers.get('X-CSRFToken')).toBeNull()
    expect(csrfFetches(fetchMock)).toBe(0)

    expect(active.usingBuiltInWeights).toBe(true)
    expect(active.appliedWeights.sizeBonusWeight).toBe(6)
    expect(active.defaults.requiredTotal).toBe(100)
  })

  it('fetches the defaults', async () => {
    const fetchMock = stubFetch(() => jsonResponse({ data: defaultsBlock }))

    const defaults = await fetchMatchingConfigDefaults()

    expect(apiCall(fetchMock).url).toMatch(/\/matching\/configs\/defaults\/$/)
    expect(defaults.weights.timezoneWeight).toBe(30)
    expect(defaults.requiredTotal).toBe(100)
  })

  it('throws rather than returning defaults when the response shape is wrong', async () => {
    stubFetch(() => jsonResponse({ requiredTotal: '100.00' }))

    await expect(fetchMatchingConfigDefaults()).rejects.toThrow(/unexpected format/)
  })
})

describe('writes', () => {
  it('creates a config with a CSRF token and a snake_case body', async () => {
    const fetchMock = stubFetch(() => jsonResponse(configRow, 201))

    const created = await createMatchingConfig({ weights })

    const { url, init, headers, body } = apiCall(fetchMock)
    expect(url).toMatch(/\/matching\/configs\/$/)
    expect(init.method).toBe('POST')
    expect(init.credentials).toBe('include')
    expect(headers.get('X-CSRFToken')).toBe('csrf-test')
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(csrfFetches(fetchMock)).toBe(1)
    expect(body).toEqual({
      year_weight: 30,
      timezone_weight: 15,
      timezone_max_weight: 25,
      size_bonus_weight: 30
    })

    expect(created).toMatchObject({ id: 7, totalWeight: 100, weights })
  })

  it('updates a config with PATCH, sending only the given fields', async () => {
    const fetchMock = stubFetch(() =>
      jsonResponse({ ...configRow, year_weight: '40.00', timezone_weight: '5.00' })
    )

    const updated = await updateMatchingConfig(7, {
      weights: { yearWeight: 40, timezoneWeight: 5 }
    })

    const { url, init, headers, body } = apiCall(fetchMock)
    expect(url).toMatch(/\/matching\/configs\/7\/$/)
    expect(init.method).toBe('PATCH')
    expect(headers.get('X-CSRFToken')).toBe('csrf-test')
    expect(body).toEqual({ year_weight: 40, timezone_weight: 5 })
    expect(updated.weights.yearWeight).toBe(40)
  })

  it('does not send the write when no CSRF token can be obtained', async () => {
    const fetchMock = stubFetch(() => jsonResponse(configRow, 201), 503)

    await expect(createMatchingConfig({ weights })).rejects.toThrow(
      /secure session/
    )
    expect(fetchMock.mock.calls.every(([url]) => String(url).includes('/services/csrf/'))).toBe(
      true
    )
  })
})

describe('validation errors', () => {
  // The shape config.exception_handler gives a DRF ValidationError.
  const rejected = (fields: Record<string, string[]>) => () =>
    jsonResponse(
      { error: Object.values(fields)[0][0], code: 'invalid', request_id: 'req-1', fields },
      400
    )

  it('surfaces the weight total message from a rejected create', async () => {
    const message = 'Matching weights must total exactly 100.00% (currently 90.00%, 10.00% under).'
    stubFetch(rejected({ weight_total: [message] }))

    const error = await createMatchingConfig({
      weights: { ...weights, yearWeight: 20 }
    }).catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(400)
    expect((error as ApiError).message).toBe(message)
    expect(matchingConfigFieldErrors(error)?.weightTotal).toBe(message)
  })
})
