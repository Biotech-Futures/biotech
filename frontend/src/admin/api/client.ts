/**
 * Shared HTTP client for the admin section.
 *
 * One fetch wrapper, two facades:
 *   api      -> `${VITE_API_BASE_URL}/api/v1`        (general endpoints)
 *   adminApi -> `${VITE_API_BASE_URL}/api/v1/admin`  (admin endpoints)
 *
 * Built on the app's existing session/CSRF model (utils/csrf.ts) and error
 * normalization (utils/apiError.ts). Ports the two interceptor behaviors the
 * old admin SPA relied on:
 *   - trailing-slash enforcement (Django requires it)
 *   - `{msg, data}` envelope unwrapping (default on adminApi only)
 *
 * Every admin screen talks to the backend through this module — no per-file
 * fetch wrappers.
 */
import { buildSessionHeaders, ensureCsrfCookie } from '@/utils/csrf'
import { apiErrorFromResponse, apiErrorFromUnknown } from '@/utils/apiError'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

const UNSAFE_METHODS = new Set<Method>(['POST', 'PATCH', 'PUT', 'DELETE'])

type QueryValue = string | number | boolean | null | undefined

export interface AdminRequestOptions {
  /** Query params; null/undefined entries are dropped. */
  query?: Record<string, QueryValue>
  headers?: HeadersInit
  signal?: AbortSignal
  /** Unwrap a `{msg, data}` envelope to its `data`. Defaults per facade. */
  unwrap?: boolean
}

/** Django rejects slash-less paths; enforce it without touching the query string. */
function withTrailingSlash(path: string): string {
  const [pathname, search] = path.split('?', 2)
  const slashed = pathname.endsWith('/') ? pathname : `${pathname}/`
  return search ? `${slashed}?${search}` : slashed
}

function buildQueryString(query?: Record<string, QueryValue>): string {
  if (!query) return ''
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined) continue
    params.set(key, String(value))
  }
  const encoded = params.toString()
  return encoded ? `?${encoded}` : ''
}

/** The admin API answers `{msg, data}`; hand callers the payload inside. */
function unwrapEnvelope(payload: unknown): unknown {
  if (
    payload !== null &&
    typeof payload === 'object' &&
    !Array.isArray(payload) &&
    'data' in payload &&
    'msg' in payload
  ) {
    return (payload as { data: unknown }).data
  }
  return payload
}

async function coreRequest<T>(
  basePath: string,
  method: Method,
  path: string,
  body: unknown,
  options: AdminRequestOptions & { unwrap: boolean },
): Promise<T> {
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData
  const includeCSRF = UNSAFE_METHODS.has(method)

  if (includeCSRF) await ensureCsrfCookie(API_BASE_URL)

  const url =
    API_BASE_URL + basePath + withTrailingSlash(path) + buildQueryString(options.query)

  let response: Response
  try {
    response = await fetch(url, {
      method,
      credentials: 'include',
      headers: buildSessionHeaders({ includeCSRF, isFormData, headers: options.headers }),
      body: isFormData ? (body as FormData) : body !== undefined ? JSON.stringify(body) : undefined,
      signal: options.signal,
    })
  } catch (error) {
    throw apiErrorFromUnknown(error)
  }

  if (!response.ok) throw await apiErrorFromResponse(response)

  if (response.status === 204) return undefined as T

  const text = await response.text()
  const payload: unknown = text ? JSON.parse(text) : null
  return (options.unwrap ? unwrapEnvelope(payload) : payload) as T
}

function createFacade(basePath: string, unwrapByDefault: boolean) {
  const run = <T>(method: Method, path: string, body?: unknown, options: AdminRequestOptions = {}) =>
    coreRequest<T>(basePath, method, path, body, { unwrap: unwrapByDefault, ...options })

  return {
    get: <T>(path: string, options?: AdminRequestOptions) => run<T>('GET', path, undefined, options),
    post: <T>(path: string, body?: unknown, options?: AdminRequestOptions) =>
      run<T>('POST', path, body, options),
    patch: <T>(path: string, body?: unknown, options?: AdminRequestOptions) =>
      run<T>('PATCH', path, body, options),
    put: <T>(path: string, body?: unknown, options?: AdminRequestOptions) =>
      run<T>('PUT', path, body, options),
    delete: <T>(path: string, body?: unknown, options?: AdminRequestOptions) =>
      run<T>('DELETE', path, body, options),
  }
}

/** General endpoints (`/api/v1`). Responses returned as-is. */
export const api = createFacade('/api/v1', false)

/** Admin endpoints (`/api/v1/admin`). `{msg, data}` envelopes unwrap to `data`. */
export const adminApi = createFacade('/api/v1/admin', true)
