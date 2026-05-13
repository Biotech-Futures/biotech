<template>
  <div class="content-area">
    <div class="page-head">
      <h1>Events & Workshops</h1>

      <div class="head-actions">
        <button class="btn btn-outline">
          <i class="fas fa-filter"></i> Filter
        </button>

        <button
          v-if="isAdmin"
          class="btn btn-primary"
          @click="createEvent"
        >
          <i class="fas fa-plus"></i> Create Event
        </button>
      </div>
    </div>

    <div v-if="loading" class="events-skeleton-grid" role="status" aria-live="polite">
      <span class="sr-only">Loading events...</span>
      <article
        v-for="item in 4"
        :key="`event-skeleton-${item}`"
        class="event-card event-skeleton-card"
      >
        <div class="event-skeleton-banner skeleton-block"></div>
        <div class="event-content">
          <div class="event-skeleton-date skeleton-block"></div>
          <div class="event-skeleton-title skeleton-block"></div>
          <div class="event-skeleton-line skeleton-block"></div>
          <div class="event-skeleton-line event-skeleton-line--short skeleton-block"></div>
          <div class="event-skeleton-meta">
            <div class="event-skeleton-chip skeleton-block"></div>
            <div class="event-skeleton-chip skeleton-block"></div>
            <div class="event-skeleton-chip skeleton-block"></div>
          </div>
          <div class="event-skeleton-actions">
            <div class="event-skeleton-button skeleton-block"></div>
            <div class="event-skeleton-button skeleton-block"></div>
          </div>
        </div>
      </article>
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="card"
      style="border-left:4px solid #dc3545;"
    >
      <h3 style="color:#dc3545;">Error</h3>

      <p style="color:#6c757d;">
        {{ error }}
      </p>

      <button
        class="btn btn-primary"
        style="margin-top:1rem;"
        @click="loadEvents"
      >
        Retry
      </button>
    </div>

    <!-- Events -->
    <div v-else-if="events.length" class="events-grid">
      <div
        v-for="ev in events"
        :key="ev.id"
        class="event-card"
      >
        <!-- Banner -->
        <div class="event-banner" :style="bannerStyle(ev)">
          <i
            v-if="!ev.cover"
            class="fas fa-calendar-alt"
          ></i>

          <!-- Admin Change Cover -->
          <button
            v-if="isAdmin"
            type="button"
            class="edit-cover-btn"
            @click="triggerCoverPicker(ev.id)"
            title="Change cover image"
          >
            <i class="fas fa-image"></i>
          </button>

          <!-- Admin Remove Cover -->
          <button
            v-if="isAdmin && ev.cover"
            type="button"
            class="edit-cover-btn"
            style="right:46px;"
            @click="resetCover(ev)"
            title="Remove cover image"
          >
            <i class="fas fa-trash"></i>
          </button>

          <!-- Hidden file picker -->
          <input
            type="file"
            accept="image/*"
            class="hidden-file"
            :ref="el => setCoverInputRef(el, ev.id)"
            @change="onCoverPicked($event, ev)"
          />
        </div>

        <!-- Content -->
        <div class="event-content">
          <span class="event-date">
            {{ formatDate(ev.start_datetime) }}
          </span>

          <h3 class="event-title">
            {{ ev.event_name }}
          </h3>

          <p class="event-description">
            {{
              ev.description ||
              'Join us for this important session as part of the BIOTech Futures program.'
            }}
          </p>

          <div class="event-meta">
            <div class="event-meta-item">
              <i class="fas fa-clock"></i>

              {{ formatTime(ev.start_datetime) }}
            </div>

            <div class="event-meta-item">
              <i class="fas fa-map-marker-alt"></i>

              {{
                ev.is_virtual
                  ? 'Virtual Event'
                  : (ev.location || 'TBA')
              }}
            </div>

            <div class="event-meta-item">
              <i class="fas fa-users"></i>

              {{ prettyType(ev.event_type) }}
            </div>
          </div>

          <!-- CTA -->
          <div class="cta-row">
            <button
              class="btn btn-outline"
              @click="openDetails(ev)"
            >
              View Details
            </button>

            <button
              class="btn btn-primary"
              @click="register(ev)"
            >
              Register Now
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty -->
    <div v-else class="card">
      <h3>No upcoming events</h3>
    </div>

    <!-- Modal -->
    <div
      class="modal"
      :class="{ show: showModal }"
      @click.self="closeDetails"
    >
      <div class="modal-content">
        <div class="modal-header">
          <div class="modal-title">
            {{ selected?.event_name }}
          </div>

          <button
            class="modal-close"
            @click="closeDetails"
          >
            &times;
          </button>
        </div>

        <div class="modal-body">
          <div
            class="detail-banner"
            :style="bannerStyle(selected)"
          >
            <i
              v-if="selected && !selected.cover"
              class="fas fa-calendar-alt"
            ></i>
          </div>

          <p style="color:#6c757d;margin:0.75rem 0;">
            {{ formatDate(selected?.start_datetime) }}
            •
            {{ formatTime(selected?.start_datetime) }}
            •
            {{
              selected?.is_virtual
                ? 'Virtual Event'
                : selected?.location
            }}
            •
            {{ prettyType(selected?.event_type) }}
          </p>

          <p>
            {{
              selected?.description ||
              defaultLong
            }}
          </p>
        </div>

        <div class="modal-footer">
          <button
            class="btn btn-outline"
            @click="closeDetails"
          >
            Close
          </button>

          <button
            class="btn btn-primary"
            @click="register(selected)"
          >
            Register Now
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { fetchEvents } from '../utils/eventsAPI'
import { formatEventDate, formatEventTimeRange } from '../utils/date'

const auth = useAuthStore()

const isAdmin = computed(() => auth.isAdmin)

const loading = ref(true)
const error = ref('')

const events = ref<any[]>([])

const defaultLong =
  'This session is part of the BIOTech Futures program. Learn, collaborate, and build your project with mentors and peers.'

// Load events from backend
const loadEvents = async () => {
  loading.value = true
  error.value = ''

  try {
    const response = await fetchEvents()

    // DRF paginated response
    events.value = response.results || []

    // restore covers
    events.value.forEach((ev: any) => {
      try {
        const saved = localStorage.getItem(`eventCover:${ev.id}`)

        if (saved) {
          ev.cover = saved
        }
      } catch {}
    })
  } catch (err: any) {
    console.error(err)

    error.value =
      err?.message || 'Failed to load events'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadEvents()
})

// Formatting
const formatDate = (dateStr?: string | null) => formatEventDate(dateStr, auth.timeZone)

const formatTime = (dateStr?: string | null) => formatEventTimeRange(dateStr, null, auth.timeZone)

const prettyType = (type: string) => {
  if (!type) return 'General'

  return (
    type.charAt(0).toUpperCase() +
    type.slice(1)
  )
}

// Banner style
const bannerStyle = (ev: any) => {
  const base =
    'height:150px;display:flex;align-items:center;justify-content:center;color:#fff;'

  if (!ev) return base

  if (ev.cover) {
    return `
      ${base}
      background-image:url('${ev.cover}');
      background-size:cover;
      background-position:center;
    `
  }

  return `
    ${base}
    background-color:var(--dark-green);
  `
}

// Modal
const showModal = ref(false)

const selected = ref<any | null>(null)

const openDetails = (ev: any) => {
  selected.value = ev
  showModal.value = true
}

const closeDetails = () => {
  showModal.value = false
  selected.value = null
}
const register = async (ev: any) => {
  try {

    const csrfToken = document.cookie
      .split('; ')
      .find(row => row.startsWith('csrftoken='))
      ?.split('=')[1]

    const token = localStorage.getItem('access_token')

    const response = await fetch(
      `http://localhost:8000/events/v1/${ev.id}/rsvp/`,
      {
        method: 'POST',

        credentials: 'include',

        headers: {
          'Content-Type': 'application/json',

          'X-CSRFToken': csrfToken || '',

          ...(token
            ? {
                Authorization: `Bearer ${token}`
              }
            : {})
        },

        body: JSON.stringify({
          rsvp_status: 'accepted'
        })
      }
    )

    if (!response.ok) {
      const err = await response.json()
      console.error(err)

      throw new Error(
        err.error || 'Failed to register'
      )
    }

    ev.accepted = true

    alert('Successfully registered!')
  } catch (err) {
    console.error(err)
    alert('Registration failed')
  }
}
// Admin create
const createEvent = () => {
  alert('Create Event')
}

// Cover image handling
const coverInputs = new Map<number, HTMLInputElement>()

const setCoverInputRef = (
  el: any,
  id: number
) => {
  if (el) {
    coverInputs.set(id, el)
  }
}

const triggerCoverPicker = (id: number) => {
  coverInputs.get(id)?.click()
}

const onCoverPicked = (
  e: Event,
  ev: any
) => {
  const input =
    e.target as HTMLInputElement

  const file =
    input.files && input.files[0]

  if (!file) return

  const reader = new FileReader()

  reader.onload = () => {
    ev.cover = String(reader.result)

    try {
      localStorage.setItem(
        `eventCover:${ev.id}`,
        ev.cover
      )
    } catch {}
  }

  reader.readAsDataURL(file)

  input.value = ''
}

const resetCover = (ev: any) => {
  try {
    localStorage.removeItem(
      `eventCover:${ev.id}`
    )
  } catch {}

  ev.cover = null
}
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.head-actions {
  display: flex;
  gap: 1rem;
}

.events-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.5rem;
}

.events-skeleton-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.5rem;
}

@media (max-width: 900px) {
  .events-grid,
  .events-skeleton-grid {
    grid-template-columns: 1fr;
  }
}

.event-card {
  background-color: var(--white);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 4px var(--shadow);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.event-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--shadow);
}

.event-banner {
  position: relative;
}

.event-skeleton-card {
  pointer-events: none;
  transform: none;
}

.event-skeleton-banner {
  height: 150px;
  border-radius: 0;
}

.event-skeleton-date {
  width: 120px;
  height: 26px;
  margin-bottom: 0.9rem;
}

.event-skeleton-title {
  width: 72%;
  height: 24px;
  margin-bottom: 0.9rem;
}

.event-skeleton-line {
  width: 100%;
  height: 14px;
  margin-bottom: 0.55rem;
}

.event-skeleton-line--short {
  width: 68%;
  margin-bottom: 1rem;
}

.event-skeleton-meta,
.event-skeleton-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.event-skeleton-meta {
  margin-bottom: 1rem;
}

.event-skeleton-chip {
  width: 100px;
  height: 18px;
}

.event-skeleton-button {
  width: 112px;
  height: 38px;
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
  animation: events-loading-shimmer 1.35s ease-in-out infinite;
}

@keyframes events-loading-shimmer {
  100% {
    transform: translateX(100%);
  }
}

.event-banner i {
  font-size: 2.25rem;
  opacity: 0.9;
}

.edit-cover-btn {
  position: absolute;
  right: 10px;
  bottom: 10px;
  background: rgba(0,0,0,0.55);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 0.4rem 0.6rem;
  cursor: pointer;
  font-size: 0.875rem;
}

.edit-cover-btn:hover {
  background: rgba(0,0,0,0.7);
}

.hidden-file {
  display: none;
}

.event-content {
  padding: 1.5rem;
}

.event-date {
  display: inline-block;
  background-color: var(--light-green);
  color: var(--dark-green);
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-size: 0.875rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.event-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--charcoal);
  margin: 0.25rem 0 0.5rem;
}

.event-description {
  color: #6c757d;
  margin-bottom: 1rem;
  line-height: 1.5;
}

.event-meta {
  display: flex;
  gap: 1.5rem;
  font-size: 0.875rem;
  color: #6c757d;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.event-meta-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.cta-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.detail-banner {
  height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  border-radius: 6px;
  margin-bottom: 1rem;
}

.detail-banner i {
  font-size: 2.5rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.5rem 1.5rem;
  border-top: 1px solid var(--border-light);
  flex-wrap: wrap;
}
</style>
