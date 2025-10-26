const DEFAULT_API_BASE_URL = 'http://localhost:8000'

interface RequestOptions extends RequestInit {
  authenticate?: boolean
}

/**
 * Lazily read the API base URL so it can be configured via Vite envs while
 * still working during tests that don't inject import.meta.
 */
function getApiBaseUrl() {
  const envBase = import.meta?.env?.VITE_API_BASE_URL as string | undefined
  const base = envBase || DEFAULT_API_BASE_URL
  return base.endsWith('/') ? base.slice(0, -1) : base
}

function getCsrfToken(): string | null {
  const name = 'csrftoken'
  const cookies = document.cookie.split(';')
  for (const cookie of cookies) {
    const trimmed = cookie.trim()
    if (trimmed.startsWith(name + '=')) {
      return decodeURIComponent(trimmed.substring(name.length + 1))
    }
  }
  return null
}

/**
 * Core fetch wrapper that ensures consistent headers, CSRF handling, and
 * credentials for every backend request.
 */
export async function apiRequest<TResponse = unknown>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<TResponse> {
  const { authenticate = true, headers: initHeaders, ...fetchOptions } = options
  const headers = new Headers(initHeaders as HeadersInit | undefined)

  if (!headers.has('Content-Type') && fetchOptions.body) {
    headers.set('Content-Type', 'application/json')
  }

  if (authenticate && fetchOptions.method && fetchOptions.method !== 'GET') {
    const csrfToken = getCsrfToken()
    if (csrfToken) {
      headers.set('X-CSRFToken', csrfToken)
    }
  }

  const url = `${getApiBaseUrl()}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`

  const response = await fetch(url, {
    ...fetchOptions,
    headers,
    credentials: 'include',
  })

  if (!response.ok) {
    let message = `HTTP ${response.status}: ${response.statusText}`
    try {
      const data = await response.json()
      if (data?.error) {
        message = data.error
      }
    } catch {
      // Ignore JSON parse errors and use default message.
    }

    if (response.status === 403) {
      message = 'Access denied. Please make sure you are logged in.'
    }

    throw new Error(message)
  }

  // Some endpoints may return no body (204). Guard against that.
  if (response.status === 204) {
    return undefined as TResponse
  }

  return response.json() as Promise<TResponse>
}

export const apiClient = {
  request: apiRequest,
}

export type { RequestOptions }
