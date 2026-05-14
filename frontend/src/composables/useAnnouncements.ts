import { ref } from 'vue'
import { buildSessionHeaders } from '@/utils/csrf'
import { apiErrorFromResponse, apiErrorFromUnknown, ApiError } from '@/utils/apiError'
import { useGroupsStore } from '@/stores/groups'

export interface AnnouncementImage {
  url: string
  alt?: string
}

export interface Announcement {
  id: number | string
  title: string
  date: string
  author: string
  bodyText: string
  bodyHtml: string
  audience: string
  // Normalized role set (e.g. ['student','mentor']) used by chip filters.
  audienceRoles: string[]
  // True when scope is public or no specific role/track/group audience exists.
  isPublic: boolean
  trackIds: number[]
  // Group ids this announcement is scoped to via audience rules.
  groupIds: number[]
  images: AnnouncementImage[]
  link?: string
  route?: string | null
}

export interface LoadFailure {
  kind: 'auth' | 'network' | 'server' | 'unknown'
  message: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const LIST_ENDPOINT = `${API_BASE_URL}/announcements/v1/?page_size=100`
const DETAIL_ENDPOINT = (id: string | number) => `${API_BASE_URL}/announcements/v1/${id}/`

interface AnnouncementAudience {
  role_name?: string | null
  track_name?: string | null
  track?: number | null
  group?: number | null
  group_name?: string | null
}

interface AnnouncementApiItem {
  id: number | string
  title?: string | null
  body?: string | null
  content?: string | null
  summary?: string | null
  visibility_scope?: string | null
  track?: number | null
  published_at?: string | null
  archived_at?: string | null
  author_email?: string | null
  author?: string | null
  image_url?: string | string[] | null
  image_urls?: unknown[] | null
  images?: unknown[] | null
  attachments?: unknown[] | null
  media?: unknown[] | null
  link?: string | null
  route?: string | null
  audiences?: AnnouncementAudience[]
  [key: string]: unknown
}

interface AnnouncementListResponse {
  results?: AnnouncementApiItem[]
}

const normalizeAudienceValue = (value?: string | null) =>
  String(value || '').trim().toLowerCase().replace(/\s+/g, '_')

const stripHtml = (value?: string | null) => {
  const source = String(value || '')
  if (typeof document !== 'undefined') {
    const template = document.createElement('template')
    template.innerHTML = source
    return (template.content.textContent || '').replace(/\s+/g, ' ').trim()
  }
  return source.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
}

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

const plainTextToHtml = (value: string) =>
  value
    .split(/\n{2,}/)
    .map(p => p.trim())
    .filter(Boolean)
    .map(p => `<p>${escapeHtml(p).replace(/\n/g, '<br>')}</p>`)
    .join('')

const normalizeRichTextUrl = (value?: string | null) => {
  const url = String(value || '').trim()
  if (!url) return ''
  if (/^(https?:|mailto:|tel:|data:image\/|\/(?!\/)|#)/i.test(url)) return url
  return ''
}

const normalizeImageUrl = (value?: unknown) => {
  const url = String(value || '').trim()
  if (!url) return undefined
  if (/^(https?:|data:|blob:|\/\/)/i.test(url)) return url
  try {
    return new URL(url, API_BASE_URL).toString()
  } catch {
    return undefined
  }
}

const ALLOWED_TAGS = new Set([
  'A','B','BLOCKQUOTE','BR','CODE','DIV','EM','FIGCAPTION','FIGURE',
  'H1','H2','H3','H4','H5','H6','HR','I','IMG','LI','OL','P','PRE',
  'S','SPAN','STRONG','TABLE','TBODY','TD','TH','THEAD','TR','U','UL'
])
// Dangerous tags: drop the tag AND its text content (e.g. <script>alert(1)
// </script> must not leave 'alert(1)' visible as text on the page).
const STRIPPED_TAGS = new Set([
  'SCRIPT','STYLE','NOSCRIPT','IFRAME','OBJECT','EMBED','FRAME','FRAMESET',
  'LINK','META','BASE','APPLET','TEMPLATE'
])
const ALLOWED_ATTRS: Record<string, Set<string>> = {
  A: new Set(['href','title','target','rel']),
  IMG: new Set(['src','alt','title','width','height']),
  TD: new Set(['colspan','rowspan']),
  TH: new Set(['colspan','rowspan'])
}

// Announcements are admin-authored; we trust the source HTML and skip
// sanitization. Plain-text bodies still get paragraph-wrapped so they
// render with line breaks instead of one wall of text.
export const renderAnnouncementBody = (value?: string | null) => {
  const source = String(value || '').trim()
  const fallback = '<p>No announcement details are available yet.</p>'
  if (!source) return fallback
  return /<\/?[a-z][\s\S]*>/i.test(source) ? source : plainTextToHtml(source)
}

export const sanitizeRichText = (value?: string | null) => {
  const source = String(value || '').trim()
  const fallback = '<p>No announcement details are available yet.</p>'
  if (!source) return fallback

  const rawHtml = /<\/?[a-z][\s\S]*>/i.test(source) ? source : plainTextToHtml(source)
  if (typeof document === 'undefined') return rawHtml

  const template = document.createElement('template')
  template.innerHTML = rawHtml

  const cleanNode = (node: Node) => {
    if (node.nodeType !== Node.ELEMENT_NODE) return
    const el = node as HTMLElement
    // Dangerous tags drop entirely — children included — so the text
    // inside <script>...</script> doesn't leak onto the page.
    if (STRIPPED_TAGS.has(el.tagName)) {
      el.remove()
      return
    }
    if (!ALLOWED_TAGS.has(el.tagName)) {
      Array.from(el.childNodes).forEach(cleanNode)
      el.replaceWith(...Array.from(el.childNodes))
      return
    }
    for (const attr of Array.from(el.attributes)) {
      const allowed = ALLOWED_ATTRS[el.tagName]?.has(attr.name.toLowerCase()) || false
      if (!allowed) el.removeAttribute(attr.name)
    }
    if (el.tagName === 'A') {
      const href = normalizeRichTextUrl(el.getAttribute('href'))
      if (href) {
        el.setAttribute('href', href)
        el.setAttribute('target', '_blank')
        el.setAttribute('rel', 'noopener noreferrer')
      } else {
        el.removeAttribute('href')
      }
    }
    if (el.tagName === 'IMG') {
      const src = normalizeImageUrl(el.getAttribute('src'))
      if (src) {
        el.setAttribute('src', src)
        el.setAttribute('loading', 'lazy')
      } else {
        el.remove()
        return
      }
    }
    Array.from(el.childNodes).forEach(cleanNode)
  }

  Array.from(template.content.childNodes).forEach(cleanNode)
  return template.innerHTML || fallback
}

const getImageCandidateUrl = (value: unknown) => {
  if (typeof value === 'string') return normalizeImageUrl(value)
  if (!value || typeof value !== 'object') return undefined
  const item = value as Record<string, unknown>
  const mimeType = String(item.mime_type || item.content_type || item.type || '').toLowerCase()
  if (mimeType && !mimeType.startsWith('image/')) return undefined
  return normalizeImageUrl(
    item.url ||
      item.image_url ||
      item.imageUrl ||
      item.src ||
      item.download_url ||
      item.downloadUrl ||
      item.file_url ||
      item.fileUrl
  )
}

const getImageCandidateAlt = (value: unknown) => {
  if (!value || typeof value !== 'object') return undefined
  const item = value as Record<string, unknown>
  const alt = String(item.alt || item.caption || item.title || item.name || '').trim()
  return alt || undefined
}

const extractImages = (a: AnnouncementApiItem): AnnouncementImage[] => {
  const candidates: unknown[] = []
  const append = (value: unknown) => {
    if (Array.isArray(value)) candidates.push(...value)
    else if (value) candidates.push(value)
  }
  append(a?.image_url)
  append(a?.image_urls)
  append(a?.images)
  append(a?.attachments)
  append(a?.media)

  const seen = new Set<string>()
  return candidates.reduce<AnnouncementImage[]>((images, candidate) => {
    const url = getImageCandidateUrl(candidate)
    if (!url || seen.has(url)) return images
    seen.add(url)
    images.push({ url, alt: getImageCandidateAlt(candidate) })
    return images
  }, [])
}

const buildBodyText = (value?: string | null) => {
  const text = stripHtml(value)
  return text || 'No announcement details are available yet.'
}

export const normalizeAnnouncement = (a: AnnouncementApiItem): Announcement => {
  const body = a?.body || a?.content || a?.summary || ''
  const rawRoles = Array.isArray(a?.audiences)
    ? a.audiences.map(r => r?.role_name).filter(Boolean)
    : []
  const trackNames = Array.isArray(a?.audiences)
    ? a.audiences.map(r => r?.track_name).filter(Boolean)
    : []
  const audienceTrackIds = Array.isArray(a?.audiences)
    ? (a.audiences
        .map((r) => (typeof r?.track === 'number' ? r.track : null))
        .filter((v): v is number => v !== null))
    : []
  const directTrackId = typeof (a as { track?: number | null })?.track === 'number'
    ? ((a as { track: number }).track)
    : null
  const trackIds = Array.from(
    new Set([...(directTrackId !== null ? [directTrackId] : []), ...audienceTrackIds]),
  )
  const groupIds = Array.isArray(a?.audiences)
    ? Array.from(
        new Set(
          a.audiences
            .map((r) => (typeof r?.group === 'number' ? r.group : null))
            .filter((v): v is number => v !== null),
        ),
      )
    : []
  const scope = normalizeAudienceValue(a?.visibility_scope)
  // Normalized, deduped role set for chip-filter matching. Plural names
  // collapse so 'Students' and 'student' resolve the same.
  const audienceRoles = Array.from(
    new Set(rawRoles.map((r) => normalizeAudienceValue(r).replace(/s$/, ''))),
  )
  const audience =
    scope === 'public'
      ? 'all'
      : normalizeAudienceValue(rawRoles[0] || trackNames[0] || scope || 'all')

  return {
    id: a?.id,
    title: a?.title || 'Untitled announcement',
    date: a?.published_at || '',
    author: a?.author_email || a?.author || 'Program Team',
    bodyText: buildBodyText(body),
    bodyHtml: renderAnnouncementBody(body),
    audience,
    audienceRoles,
    isPublic:
      scope === 'public' ||
      (audienceRoles.length === 0 && trackIds.length === 0 && groupIds.length === 0),
    trackIds,
    groupIds,
    images: extractImages(a),
    link: normalizeRichTextUrl(a?.link),
    route: typeof a?.route === 'string' ? a.route : null
  }
}

const extractCollection = (data: AnnouncementApiItem[] | AnnouncementListResponse | null) => {
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  return []
}

const failureFromError = (error: unknown): LoadFailure => {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) {
      return { kind: 'auth', message: 'Your session has expired. Please sign in again.' }
    }
    if (error.status && error.status >= 500) {
      return { kind: 'server', message: 'The announcements service is temporarily unavailable.' }
    }
  }
  const apiError = apiErrorFromUnknown(error)
  if (apiError.code === 'network_error') {
    return { kind: 'network', message: 'Network error. Check your connection and try again.' }
  }
  return { kind: 'unknown', message: 'Announcements could not be loaded.' }
}

const compareByDateDesc = (a: Announcement, b: Announcement) => {
  const da = a.date ? new Date(a.date).getTime() : 0
  const db = b.date ? new Date(b.date).getTime() : 0
  return db - da
}

export interface UserGroupOption {
  id: number
  name: string
}

// Fetches the groups the current user is an active member of. Used by the
// announcements page group-filter dropdown. Shares the cached, server-filtered
// list with the sidebar via the Pinia store — no extra bulk fetch.
export async function fetchMyGroups(userId: number | string | null): Promise<UserGroupOption[]> {
  if (!userId) return []
  const store = useGroupsStore()
  await store.ensureLoaded()
  return store.sorted
    .map((g) => ({ id: Number(g.id), name: g.name }))
    .filter((g) => Number.isFinite(g.id) && g.id > 0)
}

export function useAnnouncements() {
  const announcements = ref<Announcement[]>([])
  const isLoading = ref(true)
  const error = ref<LoadFailure | null>(null)

  async function load() {
    isLoading.value = true
    error.value = null
    try {
      const response = await fetch(LIST_ENDPOINT, {
        method: 'GET',
        credentials: 'include',
        headers: buildSessionHeaders({ headers: { Accept: 'application/json' } })
      })
      if (!response.ok) throw await apiErrorFromResponse(response)
      const data = (await response.json()) as AnnouncementApiItem[] | AnnouncementListResponse
      announcements.value = extractCollection(data).map(normalizeAnnouncement).sort(compareByDateDesc)
    } catch (e) {
      console.error('Failed to load announcements:', e)
      announcements.value = []
      error.value = failureFromError(e)
    } finally {
      isLoading.value = false
    }
  }

  return { announcements, isLoading, error, load }
}

export function useAnnouncementDetail() {
  const announcement = ref<Announcement | null>(null)
  const isLoading = ref(true)
  const error = ref<LoadFailure | null>(null)
  const notFound = ref(false)

  async function load(id: string | number) {
    isLoading.value = true
    error.value = null
    notFound.value = false
    try {
      const response = await fetch(DETAIL_ENDPOINT(id), {
        method: 'GET',
        credentials: 'include',
        headers: buildSessionHeaders({ headers: { Accept: 'application/json' } })
      })
      if (response.status === 404) {
        notFound.value = true
        announcement.value = null
        return
      }
      if (!response.ok) throw await apiErrorFromResponse(response)
      const data = (await response.json()) as AnnouncementApiItem
      announcement.value = normalizeAnnouncement(data)
    } catch (e) {
      console.error('Failed to load announcement:', e)
      announcement.value = null
      error.value = failureFromError(e)
    } finally {
      isLoading.value = false
    }
  }

  return { announcement, isLoading, error, notFound, load }
}

// One chip per role group (plus All). Visible chips are filtered by the
// caller's own role in the view layer — a student never sees the Mentor
// or Supervisor chips because announcements targeted to those roles
// aren't in their visible set in the first place.
export const AUDIENCE_FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'student', label: 'Students' },
  { value: 'mentor', label: 'Mentors' },
  { value: 'supervisor', label: 'Supervisors' }
] as const

// Per-role chip visibility. Admin sees everything.
export const AUDIENCE_FILTERS_FOR_ROLE = (
  role: 'admin' | 'mentor' | 'supervisor' | 'student' | string,
) => {
  if (role === 'admin') return AUDIENCE_FILTERS.slice()
  if (role === 'mentor') {
    return AUDIENCE_FILTERS.filter((f) => f.value !== 'supervisor')
  }
  if (role === 'supervisor') {
    return AUDIENCE_FILTERS.filter((f) => f.value !== 'mentor')
  }
  // student (and unknown) — only own role chip alongside All.
  return AUDIENCE_FILTERS.filter((f) => f.value === 'all' || f.value === 'student')
}

const AUDIENCE_LABELS: Record<string, string> = {
  all: 'All Users',
  public: 'All Users',
  student: 'Student',
  students: 'Student',
  mentor: 'Mentor',
  mentors: 'Mentor',
  supervisor: 'Supervisor',
  supervisors: 'Supervisor',
  admin: 'Admin',
  administrator: 'Admin',
  role: 'Role-based',
  track: 'Track-based',
  scoped: 'Scoped'
}

const AUDIENCE_CLASSES: Record<string, string> = {
  all: 'status-active',
  public: 'status-active',
  student: 'status-info',
  students: 'status-info',
  mentor: 'status-warning',
  mentors: 'status-warning',
  supervisor: 'status-pending',
  supervisors: 'status-pending',
  admin: 'status-danger',
  administrator: 'status-danger',
  role: 'status-info',
  track: 'status-pending',
  scoped: 'status-warning'
}

export const getAudienceLabel = (audience: string) =>
  AUDIENCE_LABELS[audience] ||
  audience.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

export const getAudienceClass = (audience: string) =>
  AUDIENCE_CLASSES[audience] || 'status-active'

// 'all' shows everything; a role chip matches any announcement whose
// audience targets that role (alone or combined). Public/global
// announcements only show under 'all'.
export const audienceMatches = (
  announcement: Pick<Announcement, 'audienceRoles'>,
  filter: string,
) => {
  if (filter === 'all') return true
  const roles = announcement.audienceRoles || []
  return roles.includes(filter)
}

export function formatRelativeDate(iso: string): string {
  if (!iso) return 'Recently posted'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return 'Recently posted'
  const diffMs = Date.now() - then
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour
  if (diffMs < minute) return 'Just now'
  if (diffMs < hour) {
    const m = Math.floor(diffMs / minute)
    return `${m} minute${m === 1 ? '' : 's'} ago`
  }
  if (diffMs < day) {
    const h = Math.floor(diffMs / hour)
    return `${h} hour${h === 1 ? '' : 's'} ago`
  }
  if (diffMs < 7 * day) {
    const d = Math.floor(diffMs / day)
    return `${d} day${d === 1 ? '' : 's'} ago`
  }
  return new Date(iso).toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  })
}

export function formatFullDate(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('en-AU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

export function authorInitial(author: string): string {
  const trimmed = String(author || '').trim()
  if (!trimmed) return '?'
  return trimmed[0].toUpperCase()
}
