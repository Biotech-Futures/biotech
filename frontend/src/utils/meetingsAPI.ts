import { buildSessionHeaders, ensureCsrfCookie } from './csrf'
import { apiErrorFromResponse } from './apiError'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const MEETINGS_API_BASE =
  `${API_BASE_URL}/api/v1/meetings/meetings`

export type MeetingWhen = 'upcoming' | 'past'

export interface MeetingNote {
  body: string
  revision: number
  updated_by?: number | null
  updated_at?: string | null
}

export interface MeetingSummary {
  body: string
  author?: number | null
  published_at?: string | null
  is_published: boolean
  updated_at?: string | null
}

export interface GroupMeeting {
  id: number
  event_id: number
  group: number
  organiser: number
  agenda: string

  title: string
  description: string
  start_datetime: string
  ends_datetime: string
  timezone_name: string
  join_link: string
  cancelled_at?: string | null

  note?: MeetingNote | null
  summary?: MeetingSummary | null
  can_manage: boolean

  created_at?: string
  updated_at?: string
}

export interface MeetingListResponse {
  count?: number
  next?: string | null
  previous?: string | null
  results?: GroupMeeting[]
}

export interface MeetingListParams {
  group?: number | string
  when?: MeetingWhen
  include_cancelled?: boolean
  page?: number
  page_size?: number
}

export interface CreateMeetingPayload {
  group: number
  title: string
  description?: string
  agenda?: string
  start_datetime: string
  ends_datetime: string
  timezone_name?: string
  join_link: string
}

export interface UpdateMeetingPayload {
  title?: string
  description?: string
  agenda?: string
  start_datetime?: string
  ends_datetime?: string
  timezone_name?: string
  join_link?: string
}

const authHeaders = (
  options: { includeCSRF?: boolean } = {}
) => {
  const headers = buildSessionHeaders({
    includeCSRF: options.includeCSRF,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
  })

  const token = localStorage.getItem('access_token')

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  return headers
}

const ensureCsrf = async () => {
  const ready = await ensureCsrfCookie(API_BASE_URL)

  if (!ready) {
    throw new Error(
      'Could not initialize a secure session. Please refresh and try again.'
    )
  }
}

export const fetchMeetings = async (
  params: MeetingListParams = {}
): Promise<MeetingListResponse> => {
  const query = new URLSearchParams()

  if (params.group !== undefined) {
    query.set('group', String(params.group))
  }

  if (params.when) {
    query.set('when', params.when)
  }

  if (params.include_cancelled !== undefined) {
    query.set(
      'include_cancelled',
      String(params.include_cancelled)
    )
  }

  if (params.page !== undefined) {
    query.set('page', String(params.page))
  }

  query.set(
    'page_size',
    String(params.page_size ?? 100)
  )

  const url =
    `${MEETINGS_API_BASE}/?${query.toString()}`

  const response = await fetch(url, {
    method: 'GET',
    credentials: 'include',
    headers: authHeaders(),
  })

  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      'Failed to fetch meetings'
    )
  }

  return response.json()
}

export const fetchMeetingById = async (
  meetingId: number
): Promise<GroupMeeting> => {
  const response = await fetch(
    `${MEETINGS_API_BASE}/${meetingId}/`,
    {
      method: 'GET',
      credentials: 'include',
      headers: authHeaders(),
    }
  )

  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      'Failed to fetch meeting'
    )
  }

  return response.json()
}

export const createMeeting = async (
  payload: CreateMeetingPayload
): Promise<GroupMeeting> => {
  await ensureCsrf()

  const response = await fetch(
    `${MEETINGS_API_BASE}/`,
    {
      method: 'POST',
      credentials: 'include',
      headers: authHeaders({
        includeCSRF: true,
      }),
      body: JSON.stringify(payload),
    }
  )

  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      'Failed to create meeting'
    )
  }

  return response.json()
}

export const updateMeeting = async (
  meetingId: number,
  payload: UpdateMeetingPayload
): Promise<GroupMeeting> => {
  await ensureCsrf()

  const response = await fetch(
    `${MEETINGS_API_BASE}/${meetingId}/`,
    {
      method: 'PATCH',
      credentials: 'include',
      headers: authHeaders({
        includeCSRF: true,
      }),
      body: JSON.stringify(payload),
    }
  )

  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      'Failed to update meeting'
    )
  }

  return response.json()
}

export const cancelMeeting = async (
  meetingId: number
): Promise<void> => {
  await ensureCsrf()

  const response = await fetch(
    `${MEETINGS_API_BASE}/${meetingId}/`,
    {
      method: 'DELETE',
      credentials: 'include',
      headers: authHeaders({
        includeCSRF: true,
      }),
    }
  )

  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      'Failed to cancel meeting'
    )
  }
}

export const fetchMeetingNote = async (
  meetingId: number
): Promise<MeetingNote> => {
  const response = await fetch(
    `${MEETINGS_API_BASE}/${meetingId}/note/`,
    {
      method: 'GET',
      credentials: 'include',
      headers: authHeaders(),
    }
  )

  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      'Failed to fetch meeting note'
    )
  }

  return response.json()
}

export const updateMeetingNote = async (
  meetingId: number,
  body: string,
  revision?: number
): Promise<MeetingNote> => {
  await ensureCsrf()

  const payload: {
    body: string
    revision?: number
  } = { body }

  if (revision !== undefined) {
    payload.revision = revision
  }

  const response = await fetch(
    `${MEETINGS_API_BASE}/${meetingId}/note/`,
    {
      method: 'PATCH',
      credentials: 'include',
      headers: authHeaders({
        includeCSRF: true,
      }),
      body: JSON.stringify(payload),
    }
  )

  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      'Failed to update meeting note'
    )
  }

  return response.json()
}

export const fetchMeetingSummary = async (
  meetingId: number
): Promise<MeetingSummary> => {
  const response = await fetch(
    `${MEETINGS_API_BASE}/${meetingId}/summary/`,
    {
      method: 'GET',
      credentials: 'include',
      headers: authHeaders(),
    }
  )

  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      'Failed to fetch meeting summary'
    )
  }

  return response.json()
}

export const updateMeetingSummary = async (
  meetingId: number,
  body: string,
  publish?: boolean
): Promise<MeetingSummary> => {
  await ensureCsrf()

  const payload: {
    body: string
    publish?: boolean
  } = { body }

  if (publish !== undefined) {
    payload.publish = publish
  }

  const response = await fetch(
    `${MEETINGS_API_BASE}/${meetingId}/summary/`,
    {
      method: 'PUT',
      credentials: 'include',
      headers: authHeaders({
        includeCSRF: true,
      }),
      body: JSON.stringify(payload),
    }
  )

  if (!response.ok) {
    throw await apiErrorFromResponse(
      response,
      'Failed to update meeting summary'
    )
  }

  return response.json()
}