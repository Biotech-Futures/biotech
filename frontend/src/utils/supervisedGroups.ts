import { apiErrorFromResponse } from './apiError'
import { buildSessionHeaders, ensureCsrfCookie } from './csrf'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type GroupPerson = {
  id: number
  first_name: string
  last_name: string
  email: string
  role: string
  /** A student's areas of interest, when the page knows them. */
  interests?: string[]
}

export type SupervisedGroup = {
  id: number
  group_name: string
  members: GroupPerson[]
  interests: string[]
  /** Formed while registering: by the supervisor, or by its students; "" (or
   *  none) for groups made later. My Groups' Waiting Area keeps its students'
   *  places, a line each, even once it's made a BIOTech group (placed). */
  registered_by?: '' | 'supervisor' | 'members'
  /** Made a BIOTech group from the Waiting Area (Create all groups): on the
   *  Groups board since. */
  placed?: boolean
}

// The program's official areas of interest. Keep in step with the backend's
// users/migrations/0023_load_areas_of_interest.py, which loads them.
export const DEFAULT_GROUP_INTERESTS = [
  'Biomedical Innovations',
  'Environmental Sustainability & Climate Tech',
  'Space & Astrobiology',
  'AI & Robotics and Smart Systems',
  'Nanotechnology & Materials Science',
  'Food & Agriculture Technology',
  'Neuroscience & Mental Health Tech',
  'Water & Energy Tech',
  'Ethical & Societal Impacts of Emerging Tech',
]

export type AvailableMentor = {
  id: number
  first_name: string
  last_name: string
  email: string
  group_id?: number | null
  group_name?: string | null
  school_name?: string | null
  interests?: string[]
}

const headers = async (unsafe = false) => {
  if (unsafe) await ensureCsrfCookie(API_BASE_URL)
  return buildSessionHeaders({
    includeCSRF: unsafe,
    headers: { Accept: 'application/json' },
  })
}

const read = async <T>(response: Response): Promise<T> => {
  if (!response.ok) throw await apiErrorFromResponse(response)
  return response.json()
}

export const personName = (person: { first_name?: string; last_name?: string; email?: string }) => {
  const name = `${person.first_name || ''} ${person.last_name || ''}`.trim()
  return name || person.email || '—'
}

export async function fetchSupervisedGroups(): Promise<SupervisedGroup[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-groups/`, {
    method: 'GET',
    credentials: 'include',
    headers: await headers(),
  })
  const groups = await read<SupervisedGroup[]>(response)
  return groups.map((group) => ({ ...group, interests: group.interests || [] }))
}

export async function createSupervisedGroup(interests: string[] = []): Promise<SupervisedGroup> {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-groups/`, {
    method: 'POST',
    credentials: 'include',
    headers: await headers(true),
    body: JSON.stringify({ interests }),
  })
  return read(response)
}

export async function updateSupervisedGroup(
  groupId: number,
  payload: { group_name?: string; interests?: string[] },
): Promise<SupervisedGroup> {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-groups/${groupId}/`, {
    method: 'PATCH',
    credentials: 'include',
    headers: await headers(true),
    body: JSON.stringify(payload),
  })
  return read(response)
}

export async function renameSupervisedGroup(groupId: number, groupName: string): Promise<SupervisedGroup> {
  return updateSupervisedGroup(groupId, { group_name: groupName })
}

export async function fetchInterestCatalog(): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-groups/interests/`, {
    method: 'GET',
    credentials: 'include',
    headers: await headers(),
  })
  const payload = await read<{ interests: string[] }>(response)
  return payload.interests
}

export async function addSupervisedGroupMembers(
  groupId: number,
  userIds: number[],
  role: 'student' | 'mentor' = 'student',
): Promise<SupervisedGroup> {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-groups/${groupId}/members/`, {
    method: 'POST',
    credentials: 'include',
    headers: await headers(true),
    body: JSON.stringify({ user_ids: userIds, role }),
  })
  return read(response)
}

export async function removeSupervisedGroupMembers(
  groupId: number,
  userIds: number[],
): Promise<SupervisedGroup> {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-groups/${groupId}/members/`, {
    method: 'DELETE',
    credentials: 'include',
    headers: await headers(true),
    body: JSON.stringify({ user_ids: userIds }),
  })
  return read(response)
}

/** Save the order the supervisor moved their groups into on My Groups. */
export async function saveSupervisedGroupOrder(groupIds: number[]): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-groups/order/`, {
    method: 'PUT',
    credentials: 'include',
    headers: await headers(true),
    body: JSON.stringify({ group_ids: groupIds }),
  })
  if (!response.ok) throw await apiErrorFromResponse(response)
}

/** How the supervisor's students without a group are matched, asked at the
 *  top of My Groups; "" until they answer. */
export type GroupingPreference = '' | 'school_only' | 'cross_school'

export type GroupingAnswer = {
  grouping_preference: GroupingPreference
  school_name: string
}

export async function fetchGroupingPreference(): Promise<GroupingAnswer> {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-groups/grouping-preference/`, {
    method: 'GET',
    credentials: 'include',
    headers: await headers(),
  })
  return read(response)
}

export async function saveGroupingPreference(
  preference: Exclude<GroupingPreference, ''>,
): Promise<GroupingAnswer> {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-groups/grouping-preference/`, {
    method: 'PUT',
    credentials: 'include',
    headers: await headers(true),
    body: JSON.stringify({ grouping_preference: preference }),
  })
  return read(response)
}

// My Groups' Waiting Area: Create all groups. Every group of that kind
// waiting there becomes a BIOTech group; answers with them.
export async function createAllWaitingGroups(
  registeredBy: 'supervisor' | 'members',
): Promise<SupervisedGroup[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-groups/place/`, {
    method: 'POST',
    credentials: 'include',
    headers: await headers(true),
    body: JSON.stringify({ registered_by: registeredBy }),
  })
  if (!response.ok) throw await apiErrorFromResponse(response)
  return response.json()
}

export async function deleteSupervisedGroup(groupId: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-groups/${groupId}/`, {
    method: 'DELETE',
    credentials: 'include',
    headers: await headers(true),
  })
  if (!response.ok) throw await apiErrorFromResponse(response)
}

export async function fetchAvailableMentors(): Promise<AvailableMentor[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/users/supervised-groups/mentors/`, {
    method: 'GET',
    credentials: 'include',
    headers: await headers(),
  })
  return read(response)
}
