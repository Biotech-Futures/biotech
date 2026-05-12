import { buildSessionHeaders } from './csrf'
import { apiErrorFromResponse } from './apiError'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface BackendEvent {
  id: number
  event_name?: string | null
  description?: string | null
  start_datetime?: string | null
  ends_datetime?: string | null
  location?: string | null
  event_type?: string | null
  event_image?: string | null
  is_virtual?: boolean | null
}

export interface EventListResponse {
  count?: number
  next?: string | null
  previous?: string | null
  results?: BackendEvent[]
}

export const fetchEvents = async (
  when: 'upcoming' | 'past' | 'all' = 'upcoming'
): Promise<EventListResponse> => {

  const token = localStorage.getItem('access_token')

  const res = await fetch(
    `${API_BASE_URL}/events/v1/?when=${when}&page_size=100`,
    {
      method: 'GET',

      credentials: 'include',

      headers: {
        ...buildSessionHeaders({
          headers: {
            Accept: 'application/json'
          }
        }),

        ...(token
          ? { Authorization: `Bearer ${token}` }
          : {})
      }
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
