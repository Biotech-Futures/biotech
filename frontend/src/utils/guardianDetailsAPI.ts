/**
 * The public guardian details form's API, opened from a supervisor's Copy
 * Details Link. No login: the token in the link is the only credential, so
 * these calls send no session or auth header.
 */
import { apiErrorFromResponse } from './apiError'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface GuardianDetailsForm {
  studentName: string
}

export interface GuardianDetails {
  firstName: string
  lastName: string
  email: string
}

export interface GuardianDetailsSaved {
  studentName: string
  /** Where the consent form was emailed. */
  email: string
}

const formUrl = (token: string) => `${API_BASE_URL}/api/v1/guardian-details/${encodeURIComponent(token)}/`

async function request<T>(token: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(formUrl(token), {
    ...init,
    credentials: 'omit',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
  })
  if (!res.ok) throw await apiErrorFromResponse(res, 'Something went wrong. Please try again.')
  return (await res.json()) as T
}

export const fetchGuardianDetailsForm = (token: string) => request<GuardianDetailsForm>(token)

export const saveGuardianDetailsForm = (token: string, body: GuardianDetails) =>
  request<GuardianDetailsSaved>(token, { method: 'POST', body: JSON.stringify(body) })
