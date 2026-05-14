import { defineStore } from 'pinia'
import { buildSessionHeaders } from '@/utils/csrf'
import { apiErrorFromResponse, apiErrorFromUnknown } from '@/utils/apiError'

export interface GroupSummary {
  id: string
  name: string
  memberCount: number
  createdAt: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
// Server-filtered list of the caller's groups. Avoids the
// fetch-all-groups + fetch-all-memberships + filter-client-side dance.
const GROUPS_MINE_ENDPOINT = `${API_BASE_URL}/groups/groups/?page_size=100&mine=true`

interface RawGroup {
  id?: unknown
  group_name?: unknown
  name?: unknown
  title?: unknown
  member_count?: unknown
  memberCount?: unknown
  members?: unknown
  created_at?: unknown
  createdAt?: unknown
}

interface ListResponse {
  results?: RawGroup[]
}

const extractCollection = (data: RawGroup[] | ListResponse | null): RawGroup[] => {
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  return []
}

const normalizeGroup = (item: RawGroup): GroupSummary => {
  const rawCount = item.member_count ?? item.memberCount ?? item.members
  const memberCount = typeof rawCount === 'number'
    ? rawCount
    : Number(rawCount ?? 0) || 0
  return {
    id: String(item.id ?? ''),
    name: String(
      item.group_name ?? item.name ?? item.title ?? (item.id ? `Group ${item.id}` : 'Group'),
    ),
    memberCount,
    createdAt: String(item.created_at ?? item.createdAt ?? ''),
  }
}

interface GroupsState {
  groups: GroupSummary[]
  isLoading: boolean
  error: string
  loaded: boolean
  inflight: Promise<GroupSummary[]> | null
}

export const useGroupsStore = defineStore('groups', {
  state: (): GroupsState => ({
    groups: [],
    isLoading: false,
    error: '',
    loaded: false,
    inflight: null,
  }),

  getters: {
    firstGroup: (state): GroupSummary | null => state.groups[0] || null,
    findById: (state) => (id: string | number | null | undefined): GroupSummary | null => {
      if (id === null || id === undefined) return null
      const key = String(id)
      return state.groups.find((group) => group.id === key) || null
    },
    sorted: (state): GroupSummary[] =>
      [...state.groups].sort((a, b) => a.name.localeCompare(b.name)),
  },

  actions: {
    async load(force = false): Promise<GroupSummary[]> {
      // De-dupe concurrent calls (sidebar + detail page mount together) and
      // skip refetch when already populated unless an explicit refresh is asked.
      if (this.inflight) return this.inflight
      if (this.loaded && !force) return this.groups

      this.isLoading = true
      this.error = ''

      const promise = (async () => {
        try {
          const headers = buildSessionHeaders({ headers: { Accept: 'application/json' } })
          const response = await fetch(GROUPS_MINE_ENDPOINT, {
            method: 'GET',
            credentials: 'include',
            headers,
          })
          if (!response.ok) throw await apiErrorFromResponse(response)
          const data = (await response.json()) as RawGroup[] | ListResponse
          const next = extractCollection(data)
            .map(normalizeGroup)
            .filter((group) => group.id)
          this.groups = next
          this.loaded = true
          return next
        } catch (e) {
          const apiError = apiErrorFromUnknown(e)
          this.error = apiError.body.error || 'Group list unavailable'
          this.groups = []
          this.loaded = false
          return []
        } finally {
          this.isLoading = false
          this.inflight = null
        }
      })()

      this.inflight = promise
      return promise
    },

    async ensureLoaded(): Promise<GroupSummary[]> {
      if (this.loaded || this.inflight) return this.load()
      return this.load()
    },

    reset() {
      this.groups = []
      this.isLoading = false
      this.error = ''
      this.loaded = false
      this.inflight = null
    },

    // Patches a single group when the detail page fetches richer info (or the
    // user joins/leaves). Keeps the store fresh without a full refetch.
    upsert(item: RawGroup | GroupSummary) {
      const normalized: GroupSummary =
        'id' in item && typeof item === 'object' && 'memberCount' in item
          ? (item as GroupSummary)
          : normalizeGroup(item as RawGroup)
      if (!normalized.id) return
      const existingIndex = this.groups.findIndex((g) => g.id === normalized.id)
      if (existingIndex >= 0) {
        this.groups.splice(existingIndex, 1, {
          ...this.groups[existingIndex],
          ...normalized,
        })
      } else {
        this.groups.push(normalized)
      }
    },
  },
})
