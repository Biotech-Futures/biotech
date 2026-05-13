import { buildSessionHeaders, ensureCsrfCookie } from './csrf'
import { apiErrorFromResponse } from './apiError'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type EventWhen = 'upcoming' | 'past' | 'all'
export type EventRsvpStatus = 'pending' | 'accepted' | 'tentative' | 'declined'

export interface BackendEvent {
  id: number
  event_name?: string | null
  description?: string | null
  track?: number | null
  start_datetime?: string | null
  ends_datetime?: string | null
  location?: string | null
  location_link?: string | null
  event_type?: string | null
  event_image?: string | null
  is_virtual?: boolean | null
  accepted?: boolean
  target_groups?: number[]
  target_tracks?: number[]
  target_roles?: number[]
}

export interface EventListResponse {
  count?: number
  next?: string | null
  previous?: string | null
  results?: BackendEvent[]
}

export interface EventListParams {
  when?: EventWhen
  page?: number
  page_size?: number
  search?: string
  category?: string
  rsvp_status?: EventRsvpStatus | EventRsvpStatus[] | string
  user?: number
  group?: number
  track?: number
  ordering?: 'start_datetime' | '-start_datetime' | 'ends_datetime' | '-ends_datetime'
}

export interface EventRsvp {
  id: number
  event: number
  user: number
  rsvp_status: EventRsvpStatus
  responded_at?: string | null
}

export interface EventRsvpListResponse {
  count?: number
  next?: string | null
  previous?: string | null
  results?: EventRsvp[]
}

export interface EventRsvpResponse {
  event_id: number
  user_id: number
  rsvp_status: EventRsvpStatus
  responded_at?: string | null
}

const authHeaders = (options: { includeCSRF?: boolean } = {}) => {
  const headers = buildSessionHeaders({
    includeCSRF: options.includeCSRF,
    headers: {
      Accept: 'application/json'
    }
  })

  const token = localStorage.getItem('access_token')
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  return headers
}

const appendParam = (params: URLSearchParams, key: string, value: unknown) => {
  if (value === undefined || value === null || value === '') return

  params.set(
    key,
    Array.isArray(value)
      ? value.join(',')
      : String(value)
  )
}

const eventListUrl = (params: EventListParams = {}) => {
  const query = new URLSearchParams()

  appendParam(query, 'when', params.when || 'upcoming')
  appendParam(query, 'page', params.page)
  appendParam(query, 'page_size', params.page_size || 100)
  appendParam(query, 'search', params.search?.trim())
  appendParam(query, 'category', params.category)
  appendParam(query, 'rsvp_status', params.rsvp_status)
  appendParam(query, 'user', params.user)
  appendParam(query, 'group', params.group)
  appendParam(query, 'track', params.track)
  appendParam(query, 'ordering', params.ordering || 'start_datetime')

  return `${API_BASE_URL}/events/v1/?${query.toString()}`
}

export const fetchEvents = async (
  params: EventWhen | EventListParams = 'upcoming'
): Promise<EventListResponse> => {
  const requestParams =
    typeof params === 'string'
      ? { when: params }
      : params

  const res = await fetch(
    eventListUrl(requestParams),
    {
      method: 'GET',
      credentials: 'include',
      headers: authHeaders()
    }
  )

  if (!res.ok) {
    throw await apiErrorFromResponse(
      res,
      'Failed to fetch events'
    )
  }

  return res.json()
}

export const fetchMyEventRsvps = async (
  pageSize = 100
): Promise<EventRsvpListResponse> => {
  const res = await fetch(
    `${API_BASE_URL}/events/v1/rsvps/me/?page_size=${pageSize}`,
    {
      method: 'GET',
      credentials: 'include',
      headers: authHeaders()
    }
  )

  if (!res.ok) {
    throw await apiErrorFromResponse(
      res,
      'Failed to fetch your event RSVPs'
    )
  }

  return res.json()
}

export const setEventRsvp = async (
  eventId: number,
  rsvpStatus: Exclude<EventRsvpStatus, 'pending'>
): Promise<EventRsvpResponse> => {
  const csrfReady = await ensureCsrfCookie(API_BASE_URL)
  if (!csrfReady) {
    throw new Error('Could not initialize a secure session. Please refresh and try again.')
  }

  const res = await fetch(
    `${API_BASE_URL}/events/v1/${eventId}/rsvp/`,
    {
      method: 'POST',
      credentials: 'include',
      headers: authHeaders({ includeCSRF: true }),
      body: JSON.stringify({
        rsvp_status: rsvpStatus
      })
    }
  )

  if (!res.ok) {
    throw await apiErrorFromResponse(
      res,
      'Failed to update your RSVP'
    )
  }

  return res.json()
}

export const resolveEventUrl = (url?: string | null) => {
  if (!url) return ''
  if (/^(https?:|data:|blob:)/i.test(url)) return url
  if (url.startsWith('/')) return `${API_BASE_URL}${url}`
  return url
}
