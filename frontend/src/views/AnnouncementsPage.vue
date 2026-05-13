<template>
  <div class="content-area">
    <div class="announcements-toolbar">
      <h1>Recent Announcements</h1>
      <div class="announcements-toolbar-actions">
        <input
          v-model="q"
          type="text"
          class="form-control"
          placeholder="Search announcements..."
        />
      </div>
    </div>

    <div v-if="isLoading" class="announcements-skeleton-list" role="status" aria-live="polite">
      <span class="sr-only">Loading announcements...</span>
      <article
        v-for="item in 4"
        :key="`announcement-skeleton-${item}`"
        class="announcement-card announcement-skeleton-card"
        :class="{ 'announcement-skeleton-card--with-media': item % 2 === 0 }"
      >
        <div v-if="item % 2 === 0" class="announcement-skeleton-media skeleton-block"></div>
        <div class="announcement-card-content announcement-skeleton-content">
          <div class="announcement-skeleton-heading-row">
            <div class="announcement-skeleton-title skeleton-block"></div>
            <div class="announcement-skeleton-badge skeleton-block"></div>
          </div>
          <div class="announcement-skeleton-meta skeleton-block"></div>
          <div class="announcement-skeleton-line skeleton-block"></div>
          <div class="announcement-skeleton-line skeleton-block"></div>
          <div class="announcement-skeleton-line announcement-skeleton-line--short skeleton-block"></div>
        </div>
      </article>
    </div>

    <div v-else-if="loadError" class="card">
      <p style="margin:0 0 1rem;color:#dc3545;">{{ loadError }}</p>
      <button class="btn btn-outline btn-sm" type="button" @click="loadAnnouncements">Try again</button>
    </div>

    <template v-else>
      <div class="announcements-list">
        <article
          v-for="a in filtered"
          :key="a.id"
          class="announcement-card"
          :class="{
            'announcement-card--with-image': a.images.length > 0,
            'announcement-card--gallery': a.images.length > 1
          }"
        >
          <figure
            v-if="a.images.length"
            class="announcement-card-media"
            :class="{ 'announcement-card-media--multiple': a.images.length > 1 }"
          >
            <div class="announcement-card-gallery" :class="getGalleryClass(a.images.length)">
              <div
                v-for="(image, index) in getVisibleImages(a.images)"
                :key="`${a.id}-${image.url}`"
                class="announcement-card-gallery-item"
              >
                <img
                  :src="image.url"
                  :alt="image.alt || `${a.title} announcement image ${index + 1}`"
                  loading="lazy"
                  @error="handleAnnouncementImageError(a, image.url)"
                />
                <span
                  v-if="a.images.length > MAX_VISIBLE_IMAGES && index === MAX_VISIBLE_IMAGES - 1"
                  class="announcement-card-gallery-more"
                >
                  +{{ a.images.length - MAX_VISIBLE_IMAGES }}
                </span>
              </div>
            </div>
          </figure>

          <div class="announcement-card-content">
            <div class="card-header announcement-card-header">
              <div class="announcement-card-heading">
                <h3 class="card-title announcement-card-title">{{ a.title }}</h3>
                <span class="status-badge announcement-card-badge" :class="getAudienceClass(a.audience)">
                  {{ getAudienceLabel(a.audience) }}
                </span>
              </div>
            </div>

            <div class="announcement-card-meta">
              {{ formatDate(a.date) }} by {{ a.author || 'Program Team' }}
            </div>
            <div class="announcement-card-body" v-html="a.bodyHtml"></div>

            <div v-if="a.route || a.link" class="announcement-card-actions">
              <RouterLink v-if="a.route" :to="a.route" class="btn btn-outline btn-sm">Read more</RouterLink>
              <a
                v-else-if="a.link"
                :href="a.link"
                target="_blank"
                rel="noopener"
                class="btn btn-outline btn-sm"
              >
                Open link
              </a>
            </div>
          </div>
        </article>
      </div>
    </template>

    <div v-if="!isLoading && !loadError && filtered.length === 0" class="card">
      <p style="margin:0;color:#6c757d;">No announcements found.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { buildSessionHeaders } from '@/utils/csrf'
import { apiErrorFromResponse } from '@/utils/apiError'

interface AnnouncementAudience {
  role_name?: string | null
  track_name?: string | null
}

interface AnnouncementApiItem {
  id: number | string
  title?: string | null
  body?: string | null
  content?: string | null
  summary?: string | null
  visibility_scope?: string | null
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

interface AnnouncementItem {
  id: number | string
  title: string
  date: string
  author: string
  bodyText: string
  bodyHtml: string
  audience: string
  images: AnnouncementImage[]
  link?: string
  route?: string | null
}

interface AnnouncementImage {
  url: string
  alt?: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const ANNOUNCEMENTS_ENDPOINT = `${API_BASE_URL}/announcements/v1/?page_size=100`
const MAX_VISIBLE_IMAGES = 4

const q = ref('')
const announcements = ref<AnnouncementItem[]>([])
const isLoading = ref(true)
const loadError = ref('')

const filtered = computed(() => {
  const text = q.value.trim().toLowerCase()
  if (!text) return announcements.value
  return announcements.value.filter(a =>
    [a.title, a.bodyText, a.author, getAudienceLabel(a.audience)].some(f =>
      String(f || '').toLowerCase().includes(text)
    )
  )
})

const formatDate = (iso: string) => {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'Recently posted'
  return d.toLocaleDateString('en-AU', { year: 'numeric', month: 'short', day: 'numeric' })
}

const normalizeAudienceValue = (value?: string | null) => {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_')
}

const stripHtml = (value?: string | null) => {
  const source = String(value || '')
  if (typeof document !== 'undefined') {
    const template = document.createElement('template')
    template.innerHTML = source
    return (template.content.textContent || '').replace(/\s+/g, ' ').trim()
  }
  return source.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
}

const escapeHtml = (value: string) => {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const plainTextToHtml = (value: string) => {
  return value
    .split(/\n{2,}/)
    .map(paragraph => paragraph.trim())
    .filter(Boolean)
    .map(paragraph => `<p>${escapeHtml(paragraph).replace(/\n/g, '<br>')}</p>`)
    .join('')
}

const normalizeRichTextUrl = (value?: string | null) => {
  const url = String(value || '').trim()
  if (!url) return ''
  if (/^(https?:|mailto:|tel:|data:image\/|\/(?!\/)|#)/i.test(url)) return url
  return ''
}

const sanitizeRichText = (value?: string | null) => {
  const source = String(value || '').trim()
  const fallbackHtml = '<p>No announcement details are available yet.</p>'
  if (!source) return fallbackHtml

  const rawHtml = /<\/?[a-z][\s\S]*>/i.test(source) ? source : plainTextToHtml(source)
  if (typeof document === 'undefined') return rawHtml

  const allowedTags = new Set([
    'A',
    'B',
    'BLOCKQUOTE',
    'BR',
    'CODE',
    'DIV',
    'EM',
    'FIGCAPTION',
    'FIGURE',
    'H1',
    'H2',
    'H3',
    'H4',
    'H5',
    'H6',
    'HR',
    'I',
    'IMG',
    'LI',
    'OL',
    'P',
    'PRE',
    'S',
    'SPAN',
    'STRONG',
    'TABLE',
    'TBODY',
    'TD',
    'TH',
    'THEAD',
    'TR',
    'U',
    'UL'
  ])
  const allowedAttributes: Record<string, Set<string>> = {
    A: new Set(['href', 'title', 'target', 'rel']),
    IMG: new Set(['src', 'alt', 'title', 'width', 'height']),
    TD: new Set(['colspan', 'rowspan']),
    TH: new Set(['colspan', 'rowspan'])
  }

  const template = document.createElement('template')
  template.innerHTML = rawHtml

  const cleanNode = (node: Node) => {
    if (node.nodeType !== Node.ELEMENT_NODE) return

    const element = node as HTMLElement
    if (!allowedTags.has(element.tagName)) {
      Array.from(element.childNodes).forEach(cleanNode)
      element.replaceWith(...Array.from(element.childNodes))
      return
    }

    for (const attribute of Array.from(element.attributes)) {
      const allowed = allowedAttributes[element.tagName]?.has(attribute.name.toLowerCase()) || false
      if (!allowed) {
        element.removeAttribute(attribute.name)
      }
    }

    if (element.tagName === 'A') {
      const href = normalizeRichTextUrl(element.getAttribute('href'))
      if (href) {
        element.setAttribute('href', href)
        element.setAttribute('target', '_blank')
        element.setAttribute('rel', 'noopener noreferrer')
      } else {
        element.removeAttribute('href')
      }
    }

    if (element.tagName === 'IMG') {
      const src = normalizeImageUrl(element.getAttribute('src'))
      if (src) {
        element.setAttribute('src', src)
        element.setAttribute('loading', 'lazy')
      } else {
        element.remove()
        return
      }
    }

    Array.from(element.childNodes).forEach(cleanNode)
  }

  Array.from(template.content.childNodes).forEach(cleanNode)
  return template.innerHTML || fallbackHtml
}

const getAnnouncementBody = (announcement: AnnouncementApiItem) => {
  return announcement?.body || announcement?.content || announcement?.summary || ''
}

const buildBodyText = (value?: string | null) => {
  const text = stripHtml(value)
  if (!text) return 'No announcement details are available yet.'
  return text
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

const extractAnnouncementImages = (announcement: AnnouncementApiItem): AnnouncementImage[] => {
  const candidates: unknown[] = []
  const append = (value: unknown) => {
    if (Array.isArray(value)) {
      candidates.push(...value)
      return
    }
    if (value) candidates.push(value)
  }

  append(announcement?.image_url)
  append(announcement?.image_urls)
  append(announcement?.images)
  append(announcement?.attachments)
  append(announcement?.media)

  const seen = new Set<string>()
  return candidates.reduce<AnnouncementImage[]>((images, candidate) => {
    const url = getImageCandidateUrl(candidate)
    if (!url || seen.has(url)) return images
    seen.add(url)
    images.push({ url, alt: getImageCandidateAlt(candidate) })
    return images
  }, [])
}

const extractCollectionItems = (data: AnnouncementApiItem[] | AnnouncementListResponse | null) => {
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  return []
}

const normalizeAnnouncement = (announcement: AnnouncementApiItem): AnnouncementItem => {
  const body = getAnnouncementBody(announcement)
  const roleAudiences = Array.isArray(announcement?.audiences)
    ? announcement.audiences.map(rule => rule?.role_name).filter(Boolean)
    : []
  const trackAudiences = Array.isArray(announcement?.audiences)
    ? announcement.audiences.map(rule => rule?.track_name).filter(Boolean)
    : []
  const visibilityScope = normalizeAudienceValue(announcement?.visibility_scope)
  const audience = visibilityScope === 'public'
    ? 'all'
    : normalizeAudienceValue(roleAudiences[0] || trackAudiences[0] || visibilityScope || 'all')

  return {
    id: announcement?.id,
    title: announcement?.title || 'Untitled announcement',
    date: announcement?.published_at || '',
    author: announcement?.author_email || announcement?.author || 'Program Team',
    bodyText: buildBodyText(body),
    bodyHtml: sanitizeRichText(body),
    audience,
    images: extractAnnouncementImages(announcement),
    link: normalizeRichTextUrl(announcement?.link),
    route: typeof announcement?.route === 'string' ? announcement.route : null
  }
}

const getAudienceLabel = (audience: string) => {
  const labels: Record<string, string> = {
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
  return labels[audience] || audience.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase())
}

const getAudienceClass = (audience: string) => {
  const classes: Record<string, string> = {
    all: 'status-active',
    public: 'status-active',
    student: 'status-info',
    students: 'status-info',
    mentor: 'status-warning',
    mentors: 'status-warning',
    supervisor: 'status-pending',
    supervisors: 'status-pending',
    admin: 'status-danger',
    administrator: 'status-danger'
  }
  return classes[audience] || 'status-active'
}

const getVisibleImages = (images: AnnouncementImage[]) => images.slice(0, MAX_VISIBLE_IMAGES)

const getGalleryClass = (count: number) => {
  if (count <= 1) return 'announcement-card-gallery--single'
  if (count === 2) return 'announcement-card-gallery--two'
  if (count === 3) return 'announcement-card-gallery--three'
  return 'announcement-card-gallery--many'
}

const handleAnnouncementImageError = (announcement: AnnouncementItem, imageUrl: string) => {
  announcement.images = announcement.images.filter(image => image.url !== imageUrl)
}

async function loadAnnouncements() {
  isLoading.value = true
  loadError.value = ''

  try {
    const response = await fetch(ANNOUNCEMENTS_ENDPOINT, {
      method: 'GET',
      credentials: 'include',
      headers: buildSessionHeaders({
        headers: {
          Accept: 'application/json'
        }
      })
    })

    if (!response.ok) {
      throw await apiErrorFromResponse(response)
    }

    const data = await response.json() as AnnouncementApiItem[] | AnnouncementListResponse
    announcements.value = extractCollectionItems(data).map(normalizeAnnouncement)
  } catch (error) {
    console.error('Failed to load announcements:', error)
    announcements.value = []
    loadError.value = 'Announcements could not be loaded.'
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadAnnouncements()
})
</script>

<style scoped>
.announcements-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
  margin-bottom: 2rem;
}

.announcements-toolbar h1 {
  margin: 0;
}

.announcements-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: min(320px, 100%);
}

.announcements-list {
  display: grid;
  gap: 1rem;
}

.announcements-skeleton-list {
  display: grid;
  gap: 1rem;
}

.announcement-card {
  width: min(100%, 860px);
  background: var(--white);
  border: 1px solid rgba(1, 113, 81, 0.08);
  border-radius: 8px;
  box-shadow: 0 2px 4px var(--shadow);
  overflow: hidden;
  transition:
    box-shadow 0.3s ease,
    transform 0.3s ease,
    border-color 0.3s ease;
}

.announcement-card:hover {
  border-color: rgba(1, 113, 81, 0.2);
  box-shadow: 0 4px 12px var(--shadow);
  transform: translateY(-1px);
}

.announcement-skeleton-card {
  pointer-events: none;
  transform: none;
}

.announcement-skeleton-card--with-media {
  display: grid;
  grid-template-columns: minmax(300px, 40%) minmax(0, 1fr);
  width: min(100%, 1100px);
  min-height: 260px;
  padding: 0;
}

.announcement-skeleton-content {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.announcement-skeleton-media {
  min-height: 260px;
  border-radius: 0;
}

.announcement-skeleton-heading-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.9rem;
}

.announcement-skeleton-title {
  width: min(420px, 70%);
  height: 24px;
}

.announcement-skeleton-badge {
  width: 96px;
  height: 24px;
}

.announcement-skeleton-meta {
  width: 220px;
  height: 14px;
  margin-bottom: 1.1rem;
}

.announcement-skeleton-line {
  width: 100%;
  height: 14px;
  margin-bottom: 0.7rem;
}

.announcement-skeleton-line--short {
  width: 66%;
  margin-bottom: 0;
}

.skeleton-block {
  position: relative;
  overflow: hidden;
  border-radius: 6px;
  background: #e9ecef;
}

.skeleton-block::after {
  position: absolute;
  inset: 0;
  content: '';
  transform: translateX(-100%);
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.72), transparent);
  animation: announcements-loading-shimmer 1.35s ease-in-out infinite;
}

@keyframes announcements-loading-shimmer {
  100% {
    transform: translateX(100%);
  }
}

.announcement-card:not(.announcement-card--with-image) {
  padding: 1.5rem;
}

.announcement-card--with-image {
  display: grid;
  grid-template-columns: minmax(300px, 40%) minmax(0, 1fr);
  width: min(100%, 1100px);
  min-height: 280px;
}

.announcement-card-media {
  position: relative;
  min-height: 280px;
  margin: 0;
  background: var(--light-green);
}

.announcement-card-gallery {
  display: grid;
  width: 100%;
  height: 100%;
  min-height: 280px;
  gap: 3px;
  background: rgba(1, 113, 81, 0.12);
}

.announcement-card-gallery--single {
  grid-template-columns: 1fr;
}

.announcement-card-gallery--two {
  grid-template-rows: repeat(2, minmax(0, 1fr));
}

.announcement-card-gallery--three,
.announcement-card-gallery--many {
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr);
  grid-template-rows: repeat(2, minmax(0, 1fr));
}

.announcement-card-gallery--three .announcement-card-gallery-item:first-child,
.announcement-card-gallery--many .announcement-card-gallery-item:first-child {
  grid-row: 1 / span 2;
}

.announcement-card-gallery-item {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--white);
}

.announcement-card-gallery-item img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.announcement-card-gallery-more {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(19, 28, 34, 0.54);
  color: var(--white);
  font-size: 1.35rem;
  font-weight: 700;
}

.announcement-card-content {
  padding: 1.5rem;
}

.announcement-card--with-image .announcement-card-content {
  display: flex;
  flex-direction: column;
}

.announcement-card-header {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.announcement-card-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.announcement-card-title {
  flex: 1 1 auto;
  min-width: 0;
  margin: 0;
  line-height: 1.35;
}

.announcement-card-badge {
  flex: 0 0 auto;
  white-space: nowrap;
}

.announcement-card-meta {
  color: #6c757d;
  margin: 0.25rem 0 1rem;
}

.announcement-card-body {
  margin-bottom: 1rem;
  line-height: 1.7;
  color: var(--dark-gray);
  overflow-wrap: anywhere;
}

.announcement-card-body :deep(*) {
  max-width: 100%;
}

.announcement-card-body :deep(p),
.announcement-card-body :deep(ul),
.announcement-card-body :deep(ol),
.announcement-card-body :deep(blockquote),
.announcement-card-body :deep(pre),
.announcement-card-body :deep(table),
.announcement-card-body :deep(figure) {
  margin: 0 0 0.9rem;
}

.announcement-card-body :deep(p:last-child),
.announcement-card-body :deep(ul:last-child),
.announcement-card-body :deep(ol:last-child),
.announcement-card-body :deep(blockquote:last-child),
.announcement-card-body :deep(pre:last-child),
.announcement-card-body :deep(table:last-child),
.announcement-card-body :deep(figure:last-child) {
  margin-bottom: 0;
}

.announcement-card-body :deep(h1),
.announcement-card-body :deep(h2),
.announcement-card-body :deep(h3),
.announcement-card-body :deep(h4),
.announcement-card-body :deep(h5),
.announcement-card-body :deep(h6) {
  margin: 1rem 0 0.45rem;
  color: var(--primary-green);
  line-height: 1.25;
}

.announcement-card-body :deep(h1:first-child),
.announcement-card-body :deep(h2:first-child),
.announcement-card-body :deep(h3:first-child),
.announcement-card-body :deep(h4:first-child),
.announcement-card-body :deep(h5:first-child),
.announcement-card-body :deep(h6:first-child) {
  margin-top: 0;
}

.announcement-card-body :deep(ul),
.announcement-card-body :deep(ol) {
  padding-left: 1.3rem;
}

.announcement-card-body :deep(a) {
  color: var(--primary-green);
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.announcement-card-body :deep(blockquote) {
  padding: 0.75rem 1rem;
  border-left: 3px solid var(--primary-green);
  background: rgba(1, 113, 81, 0.06);
  border-radius: 0 8px 8px 0;
}

.announcement-card-body :deep(pre) {
  max-width: 100%;
  padding: 0.85rem 1rem;
  overflow-x: auto;
  background: #f5f7f8;
  border-radius: 8px;
}

.announcement-card-body :deep(code) {
  padding: 0.1rem 0.3rem;
  background: #f5f7f8;
  border-radius: 4px;
  font-size: 0.92em;
}

.announcement-card-body :deep(pre code) {
  padding: 0;
  background: transparent;
}

.announcement-card-body :deep(img) {
  display: block;
  width: 100%;
  height: auto;
  max-height: 420px;
  object-fit: contain;
  border-radius: 8px;
  background: var(--light-green);
}

.announcement-card-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  display: block;
  overflow-x: auto;
}

.announcement-card-body :deep(th),
.announcement-card-body :deep(td) {
  padding: 0.55rem 0.65rem;
  border: 1px solid rgba(1, 113, 81, 0.14);
  text-align: left;
}

.announcement-card-actions {
  margin-top: auto;
}

@media (max-width: 900px) {
  .announcement-card--with-image,
  .announcement-skeleton-card--with-media {
    grid-template-columns: 1fr;
  }

  .announcement-card-media,
  .announcement-card-gallery,
  .announcement-skeleton-media {
    min-height: 220px;
  }
}

@media (max-width: 640px) {
  .announcements-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .announcements-toolbar-actions {
    width: 100%;
  }

  .announcement-card:not(.announcement-card--with-image),
  .announcement-card-content {
    padding: 1.25rem;
  }

  .announcement-card-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.5rem;
  }

  .announcement-skeleton-heading-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .announcement-skeleton-title,
  .announcement-skeleton-badge,
  .announcement-skeleton-meta {
    width: 100%;
  }
}
</style>
