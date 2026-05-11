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

    <div v-if="isLoading" class="card">
      <p style="margin:0;color:#6c757d;">Loading announcements...</p>
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
          :class="{ 'announcement-card--with-image': a.imageUrl }"
        >
          <figure v-if="a.imageUrl" class="announcement-card-media">
            <img
              :src="a.imageUrl"
              :alt="`${a.title} announcement image`"
              loading="lazy"
              @error="handleAnnouncementImageError(a)"
            />
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
            <p class="announcement-card-summary">{{ a.summary }}</p>

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
  visibility_scope?: string | null
  published_at?: string | null
  archived_at?: string | null
  author_email?: string | null
  author?: string | null
  image_url?: string | null
  audiences?: AnnouncementAudience[]
}

interface AnnouncementListResponse {
  results?: AnnouncementApiItem[]
}

interface AnnouncementItem {
  id: number | string
  title: string
  date: string
  author: string
  summary: string
  audience: string
  imageUrl?: string
  link?: string
  route?: string | null
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const ANNOUNCEMENTS_ENDPOINT = `${API_BASE_URL}/announcements/v1/?page_size=100`

const q = ref('')
const announcements = ref<AnnouncementItem[]>([])
const isLoading = ref(false)
const loadError = ref('')

const filtered = computed(() => {
  const text = q.value.trim().toLowerCase()
  if (!text) return announcements.value
  return announcements.value.filter(a =>
    [a.title, a.summary, a.author, getAudienceLabel(a.audience)].some(f =>
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

const truncateText = (value?: string | null, maxLength = 220) => {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  if (!text) return 'No announcement details are available yet.'
  return text.length > maxLength ? `${text.slice(0, maxLength - 1).trim()}...` : text
}

const normalizeImageUrl = (value?: string | null) => {
  const url = String(value || '').trim()
  if (!url) return undefined
  if (/^(https?:|data:|blob:|\/\/)/i.test(url)) return url

  try {
    return new URL(url, API_BASE_URL).toString()
  } catch {
    return undefined
  }
}

const extractCollectionItems = (data: AnnouncementApiItem[] | AnnouncementListResponse | null) => {
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  return []
}

const normalizeAnnouncement = (announcement: AnnouncementApiItem): AnnouncementItem => {
  const body = announcement?.body || ''
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
    summary: truncateText(body),
    audience,
    imageUrl: normalizeImageUrl(announcement?.image_url)
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

const handleAnnouncementImageError = (announcement: AnnouncementItem) => {
  announcement.imageUrl = undefined
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

.announcement-card {
  width: min(100%, 860px);
  background: var(--white);
  border: 1px solid rgba(1, 113, 81, 0.08);
  border-radius: 8px;
  box-shadow: 0 2px 4px var(--shadow);
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

.announcement-card:not(.announcement-card--with-image) {
  padding: 1.5rem;
}

.announcement-card--with-image {
  display: grid;
  grid-template-columns: minmax(280px, 42%) minmax(0, 1fr);
  width: min(100%, 1100px);
  min-height: 260px;
  overflow: hidden;
}

.announcement-card-media {
  min-height: 260px;
  background: var(--light-green);
}

.announcement-card-media img {
  display: block;
  width: 100%;
  height: 100%;
  min-height: 260px;
  object-fit: cover;
}

.announcement-card-content {
  padding: 1.5rem;
}

.announcement-card--with-image .announcement-card-content {
  display: flex;
  flex-direction: column;
  justify-content: center;
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

.announcement-card-summary {
  margin-bottom: 1rem;
  line-height: 1.7;
}

.announcement-card-actions {
  margin-top: auto;
}

@media (max-width: 900px) {
  .announcement-card--with-image {
    grid-template-columns: 1fr;
  }

  .announcement-card-media,
  .announcement-card-media img {
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
}
</style>
