/**
 * The public guardian consent page's API. No login: the token in the emailed
 * link is the only credential, so these calls send no session or auth header.
 */
import { apiErrorFromResponse } from './apiError'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface ConsentFormWording {
  version: string
  /** Trusted HTML rendered by the backend from its own template. */
  body_html: string
  media_yes: string
  media_no: string
  declaration: string
}

export interface ConsentFormData {
  studentName: string
  guardianFirstName: string
  guardianLastName: string
  expiresAt: string
  supportEmail: string
  form: ConsentFormWording
}

export interface ConsentSignature {
  guardianFullName: string
  mediaConsent: boolean
  signature: string
  agreed: boolean
  consentVersion: string
}

export interface ConsentSigned {
  reference: string
  mediaConsent: boolean
}

const consentUrl = (token: string) => `${API_BASE_URL}/api/v1/consent/${encodeURIComponent(token)}/`

async function request<T>(token: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(consentUrl(token), {
    ...init,
    credentials: 'omit',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' }
  })
  if (!res.ok) throw await apiErrorFromResponse(res, 'Something went wrong. Please try again.')
  return (await res.json()) as T
}

export const fetchConsentForm = (token: string) => request<ConsentFormData>(token)

export const signConsentForm = (token: string, body: ConsentSignature) =>
  request<ConsentSigned>(token, { method: 'POST', body: JSON.stringify(body) })
