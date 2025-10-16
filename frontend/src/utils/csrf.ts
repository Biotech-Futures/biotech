/**
 * CSRF token helper for Django session-based authentication
 * Extracts CSRF token from cookies for API requests
 */

/**
 * Get CSRF token from cookies
 * Django sets csrftoken cookie that we need to send back in X-CSRFToken header
 */
export function getCSRFToken(): string | null {
  const name = 'csrftoken'
  let cookieValue: string | null = null

  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';')
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim()
      if (cookie.substring(0, name.length + 1) === name + '=') {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
        break
      }
    }
  }
  return cookieValue
}

/**
 * Create headers object with CSRF token for POST/PUT/DELETE requests
 */
export function getAuthHeaders(): HeadersInit {
  const headers: HeadersInit = {
    'Content-Type': 'application/json'
  }

  const csrfToken = getCSRFToken()
  if (csrfToken) {
    headers['X-CSRFToken'] = csrfToken
  }

  return headers
}
