import { apiErrorFromResponse } from './apiError'
import { buildSessionHeaders, ensureCsrfCookie } from './csrf'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Kept in step with the backend's TicketCategory. The three the requester can
// pick are spelled out rather than fetched, because the backend also carries
// categories it raises tickets under itself, and those must not appear here.
export const TICKET_CATEGORIES = [
  { value: 'account_access', label: 'Account & Access' },
  { value: 'programs_groups', label: 'Programs & Groups' },
  { value: 'certificates_records', label: 'Certificates & Records' }
] as const

export type TicketCategory = (typeof TICKET_CATEGORIES)[number]['value']
export type TicketStatus = 'open' | 'in_progress' | 'pending_user' | 'resolved'
export type TicketMessageType = 'user_message' | 'support_reply' | 'system'

export const MAX_BODY_LENGTH = 2000
export const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
export const MAX_ATTACHMENTS = 5
export const ATTACHMENT_HINT = 'Max file size 10 MB (PDF, PNG, JPG, DOCX)'

export interface TicketAttachment {
  id: number
  filename: string
  mimeType: string
  size: number
}

export interface TicketMessage {
  id: number
  messageType: TicketMessageType
  body: string
  // A role, not a person: support replies come back as "Support".
  author: string | null
  createdAt: string
  attachments: TicketAttachment[]
}

export interface TicketRow {
  id: number
  ticketNumber: string
  subject: string
  category: TicketCategory
  status: TicketStatus
  lastUpdated: string
}

export interface TicketDetail extends Omit<TicketRow, 'lastUpdated'> {
  body: string
  createdAt: string
  lastUpdated: string
  messages: TicketMessage[]
}

export interface PaginatedTickets {
  items: TicketRow[]
  total: number
  page: number
  limit: number
  hasMore: boolean
}

export interface SubmitTicketPayload {
  category: TicketCategory
  subject: string
  body: string
  files?: File[]
}

// Every ticket endpoint answers {msg, data}. Callers only ever want `data`,
// so the envelope is opened here rather than at each call site.
interface Envelope<T> {
  msg: string
  data: T
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = String(options.method || 'GET').toUpperCase()
  const isFormData = options.body instanceof FormData
  const includeCSRF = !['GET', 'HEAD', 'OPTIONS'].includes(method)

  if (includeCSRF) {
    const csrfReady = await ensureCsrfCookie(API_BASE_URL)
    if (!csrfReady) {
      throw new Error('Could not initialize a secure session. Please refresh and try again.')
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    ...options,
    headers: buildSessionHeaders({
      includeCSRF,
      isFormData,
      headers: {
        Accept: 'application/json',
        ...(options.headers || {})
      }
    })
  })

  if (!response.ok) {
    throw await apiErrorFromResponse(response)
  }

  const text = await response.text()
  const payload = (text ? JSON.parse(text) : null) as Envelope<T> | null
  return (payload ? payload.data : null) as T
}

function ticketFormData(fields: Record<string, string>, files: File[] = []): FormData {
  const form = new FormData()
  Object.entries(fields).forEach(([key, value]) => form.set(key, value))
  // Repeated under one key: the backend reads request.FILES.getlist("files").
  files.forEach((file) => form.append('files', file))
  return form
}

export function fetchMyTickets(page = 1, limit = 10) {
  return requestJson<PaginatedTickets>(`/api/v1/tickets/?page=${page}&limit=${limit}`)
}

export function fetchTicket(ticketId: number | string) {
  return requestJson<TicketDetail>(`/api/v1/tickets/${ticketId}/`)
}

export function submitTicket(payload: SubmitTicketPayload) {
  return requestJson<TicketDetail>('/api/v1/tickets/', {
    method: 'POST',
    body: ticketFormData(
      { category: payload.category, subject: payload.subject, body: payload.body },
      payload.files
    )
  })
}

export function replyToTicket(ticketId: number | string, body: string, files: File[] = []) {
  return requestJson<TicketDetail>(`/api/v1/tickets/${ticketId}/messages/`, {
    method: 'POST',
    body: ticketFormData({ body }, files)
  })
}

// A plain URL rather than a fetch: the browser follows it with the session
// cookie attached, and the backend either streams the file or redirects to a
// signed one.
export function attachmentUrl(ticketId: number | string, attachmentId: number | string) {
  return `${API_BASE_URL}/api/v1/tickets/${ticketId}/attachments/${attachmentId}/`
}

export function categoryLabel(value: string): string {
  return TICKET_CATEGORIES.find((c) => c.value === value)?.label || value
}

export function statusLabel(value: TicketStatus | string): string {
  const labels: Record<string, string> = {
    open: 'Open',
    in_progress: 'In progress',
    pending_user: 'Pending user',
    resolved: 'Resolved'
  }
  return labels[value] || value
}
