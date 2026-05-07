export interface ApiErrorBody {
  error: string
  code: string
  request_id: string
  fields?: Record<string, string[]>
  missing_user_ids?: number[]
  existing_roles?: string[]
  target_user_id?: number
  reason?: string
  [key: string]: unknown
}

export class ApiError extends Error {
  body: ApiErrorBody
  code: string
  requestId: string
  status?: number
  fields?: Record<string, string[]>

  constructor(body: ApiErrorBody, status?: number) {
    super(body.error)
    this.name = 'ApiError'
    this.body = body
    this.code = body.code
    this.requestId = body.request_id
    this.status = status
    this.fields = body.fields
  }
}

const FALLBACK_REQUEST_ID = 'n/a'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function normalizeFields(value: unknown): Record<string, string[]> | undefined {
  if (!isRecord(value)) return undefined

  return Object.fromEntries(
    Object.entries(value).map(([field, messages]) => [
      field,
      Array.isArray(messages) ? messages.map(String) : [String(messages)]
    ])
  )
}

export function normalizeApiErrorBody(
  data: unknown,
  fallback = 'Request failed.',
  requestId = FALLBACK_REQUEST_ID,
  status?: number
): ApiErrorBody {
  const source = isRecord(data) ? data : {}
  const legacyMessage =
    typeof source.message === 'string'
      ? source.message
      : typeof source.msg === 'string'
        ? source.msg
        : typeof source.detail === 'string'
          ? source.detail
          : undefined

  return {
    ...source,
    error: typeof source.error === 'string' ? source.error : legacyMessage || fallback,
    code: typeof source.code === 'string' ? source.code : status ? `http_${status}` : 'unknown_error',
    request_id:
      typeof source.request_id === 'string'
        ? source.request_id
        : typeof source.requestId === 'string'
          ? source.requestId
          : requestId,
    fields: normalizeFields(source.fields)
  }
}

export async function apiErrorFromResponse(response: Response, fallback?: string): Promise<ApiError> {
  const requestId = response.headers.get('X-Request-ID') || FALLBACK_REQUEST_ID
  const text = await response.text()
  let data: unknown = null

  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = text || null
  }

  return new ApiError(
    normalizeApiErrorBody(data, fallback || `Request failed: ${response.status}`, requestId, response.status),
    response.status
  )
}

export function apiErrorFromUnknown(error: unknown, fallback = 'Network error'): ApiError {
  if (error instanceof ApiError) return error

  if (error instanceof Error) {
    return new ApiError({
      error: error.message || fallback,
      code: error.name === 'AbortError' ? 'request_timeout' : 'network_error',
      request_id: FALLBACK_REQUEST_ID
    })
  }

  return new ApiError({
    error: fallback,
    code: 'network_error',
    request_id: FALLBACK_REQUEST_ID
  })
}

export function logApiError(context: string, error: unknown) {
  const apiError = apiErrorFromUnknown(error)

  console.warn('API error', {
    context,
    code: apiError.code,
    request_id: apiError.requestId,
    status: apiError.status
  })
}
