/**
 * @file csrf.ts
 * @description csrf.ts provides CSRF-related helper utilities for the frontend application. It is designed for Django session-based authentication and is responsible for reading the CSRF token from browser cookies and building request headers for authenticated API calls that require CSRF protection.
 * @author Shiqi Fang
 * @author Jiachen Ding
 * @author Qin Chen
 * @version 1.1.0
 *
 * Project: Group Based 5703 Capstone Project
 * Group: CS17-1
 * Team: CS17-1 Frontend Team
 *
 * Component Type: Frontend Utility Module
 * File Role: CSRF token and session header helper
 * Purpose: Provide reusable helper functions for extracting the CSRF token from cookies and generating safe request headers for session-based backend communication.
 * Scope: Shared by API modules, authentication logic, and any frontend request that needs CSRF-protected communication with the Django backend.
 *
 * Responsibilities:
 * - Read the CSRF token stored in browser cookies
 * - Support Django session-based authentication workflows
 * - Build consistent request headers for fetch requests
 * - Automatically attach Content-Type when appropriate
 * - Optionally attach X-CSRFToken for unsafe HTTP methods such as POST, PATCH, PUT, and DELETE
 *
 * Dependencies:
 * - Browser document.cookie
 * - Browser Headers API
 * - Django CSRF cookie strategy
 *
 * Revision Summary:
 * - Major revisions: 1
 * - Minor revisions: 1
 *
 * Last Modified: 2026-04-04
 * Modified By: CS17-1 Frontend Team
 */

// Cross-origin note:
// When the FE runs on a different origin from the BE (e.g. azurestaticapps.net <-> azurewebsites.net),
// document.cookie cannot read cookies set for the BE's domain (same-origin policy, separate from third-party
// cookie blocking). We fetch the CSRF token from a JSON endpoint and cache it in module scope. The browser
// still attaches the csrftoken cookie automatically (credentials: 'include' + SameSite=None; Secure) so
// Django's CsrfViewMiddleware can validate the X-CSRFToken header against it.
let cachedCsrfToken: string | null = null

export function getCSRFToken(): string | null {
  return cachedCsrfToken
}

export async function ensureCsrfCookie(apiBaseUrl: string): Promise<boolean> {
  if (cachedCsrfToken) return true

  try {
    const response = await fetch(`${apiBaseUrl}/services/csrf/`, {
      method: 'GET',
      credentials: 'include'
    })
    if (response.ok) {
      const data = await response.json()
      cachedCsrfToken = data?.csrfToken ?? null
    }
  } catch (error) {
    console.error('Failed to fetch CSRF token:', error)
  }

  return Boolean(cachedCsrfToken)
}

// Clear the cached token. Call after login (Django rotates the CSRF token on login)
// and after logout so the next unsafe request re-fetches a fresh value.
export function resetCsrfToken(): void {
  cachedCsrfToken = null
}

interface BuildHeadersOptions {
  includeCSRF?: boolean
  headers?: HeadersInit
  isFormData?: boolean
}

export function buildSessionHeaders(options: BuildHeadersOptions = {}): Headers {
  const {
    includeCSRF = false,
    headers: initHeaders,
    isFormData = false
  } = options

  const headers = new Headers(initHeaders)

  if (!isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  if (includeCSRF) {
    const csrfToken = getCSRFToken()
    if (csrfToken) {
      headers.set('X-CSRFToken', csrfToken)
    }
  }

  return headers
}
