import { buildSessionHeaders, ensureCsrfCookie } from './csrf'
import { apiErrorFromResponse } from './apiError'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface AssistantLink {
  label: string
  to: string
}

export interface AssistantReply {
  answer: string
  links: AssistantLink[]
  matched: boolean
}

export async function askAssistant(question: string): Promise<AssistantReply> {
  if (!(await ensureCsrfCookie(API_BASE_URL))) {
    throw new Error('Could not initialize a secure session. Please refresh and try again.')
  }
  const response = await fetch(`${API_BASE_URL}/api/v1/assistant/ask/`, {
    method: 'POST',
    credentials: 'include',
    headers: buildSessionHeaders({
      includeCSRF: true,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    }),
    body: JSON.stringify({ question }),
  })
  if (!response.ok) {
    throw await apiErrorFromResponse(response, 'The assistant could not answer right now.')
  }
  return response.json()
}
