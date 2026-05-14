<template>
  <div class="content-area events-page">
    <div class="page-head">
      <div>
        <h1>Events & Workshops</h1>
        <p class="page-subtitle">
          {{ auth.roleLabel }} events available to your program access.
        </p>
      </div>
    </div>

    <section class="event-toolbar" aria-label="Event filters">
      <div class="event-tabs" role="tablist" aria-label="Event view">
        <button
          v-for="tab in viewTabs"
          :key="tab.value"
          type="button"
          class="event-tab"
          :class="{ active: viewMode === tab.value }"
          @click="setViewMode(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>

      <form class="event-filters" @submit.prevent="loadEvents()">
        <label class="filter-field filter-field-search">
          <span>Search</span>
          <input
            v-model.trim="filters.search"
            type="search"
            class="form-control"
            placeholder="Title or description"
          />
        </label>

        <label class="filter-field">
          <span>Category</span>
          <select
            v-model="filters.category"
            class="form-control"
          >
            <option value="">All categories</option>
            <option
              v-for="category in eventCategories"
              :key="category.value"
              :value="category.value"
            >
              {{ category.label }}
            </option>
          </select>
        </label>

        <label class="filter-field">
          <span>RSVP</span>
          <select
            v-model="filters.rsvpStatus"
            class="form-control"
          >
            <option value="">Any status</option>
            <option
              v-for="status in rsvpFilterOptions"
              :key="status.value"
              :value="status.value"
            >
              {{ status.label }}
            </option>
          </select>
        </label>

        <div class="filter-actions">
          <button type="submit" class="btn btn-primary">
            <i class="fas fa-search"></i>
            Search
          </button>

          <button type="button" class="btn btn-outline" @click="resetFilters">
            Reset
          </button>
        </div>
      </form>
    </section>

    <Transition name="event-status-fade">
      <p v-if="statusVisible && statusMessage" class="event-status-message" role="status">
        {{ statusMessage }}
      </p>
    </Transition>

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
        @click="loadEvents()"
      >
        Retry
      </button>
    </div>

    <div v-else-if="events.length" class="events-grid">
      <article
        v-for="ev in events"
        :key="ev.id"
        class="event-card"
      >
        <div class="event-banner" :style="bannerStyle(ev)">
          <i
            v-if="!eventCover(ev)"
            class="fas fa-calendar-alt"
          ></i>
        </div>

        <div class="event-content">
          <div class="event-card-topline">
            <span class="event-date">
              {{ formatDate(ev.start_datetime) }}
            </span>

            <span
              v-if="eventStatus(ev)"
              class="rsvp-badge"
              :class="`rsvp-badge-${eventStatus(ev)}`"
            >
              {{ rsvpLabel(eventStatus(ev)) }}
            </span>
          </div>

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
              {{ formatTime(ev.start_datetime, ev.ends_datetime) }}
            </div>

            <div class="event-meta-item">
              <i class="fas fa-map-marker-alt"></i>
              <a
                v-if="eventLink(ev)"
                class="event-link"
                :href="eventLink(ev)"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ eventLinkLabel(ev) }}
              </a>
              <span v-else>
                {{ eventLocationText(ev) }}
              </span>
            </div>

            <div class="event-meta-item">
              <i class="fas fa-users"></i>
              {{ prettyType(ev.event_type) }}
            </div>
          </div>

          <div class="cta-row">
            <button
              class="btn btn-outline"
              type="button"
              @click="openDetails(ev)"
            >
              View Details
            </button>

            <div class="rsvp-actions" aria-label="RSVP status">
              <button
                v-for="choice in rsvpChoices"
                :key="choice.value"
                type="button"
                class="rsvp-choice"
                :class="{ active: eventStatus(ev) === choice.value }"
                :disabled="settingRsvpFor === ev.id || isRsvpClosed(ev)"
                @click="updateRsvp(ev, choice.value)"
              >
                {{ choice.shortLabel }}
              </button>
            </div>
          </div>
        </div>
      </article>
    </div>

    <div v-else class="card empty-state-card">
      <h3>{{ emptyTitle }}</h3>
      <p>{{ emptyMessage }}</p>
    </div>

    <div
      class="modal"
      :class="{ show: showModal }"
      @click.self="closeDetails"
    >
      <div class="modal-content event-modal-content">
        <div class="modal-header">
          <div class="modal-title">
            {{ selected?.event_name }}
          </div>

          <button
            class="modal-close"
            type="button"
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
              v-if="selected && !eventCover(selected)"
              class="fas fa-calendar-alt"
            ></i>
          </div>

          <div class="detail-meta">
            <span>
              <i class="fas fa-calendar-day"></i>
              {{ formatDate(selected?.start_datetime) }}
            </span>
            <span>
              <i class="fas fa-clock"></i>
              {{ formatTime(selected?.start_datetime, selected?.ends_datetime) }}
            </span>
            <span>
              <i class="fas fa-users"></i>
              {{ prettyType(selected?.event_type) }}
            </span>
          </div>

          <div class="detail-location">
            <i class="fas fa-map-marker-alt"></i>
            <a
              v-if="eventLink(selected)"
              class="event-link"
              :href="eventLink(selected)"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ eventLinkLabel(selected) }}
            </a>
            <span v-else>
              {{ eventLocationText(selected) }}
            </span>
          </div>

          <p class="detail-description">
            {{
              selected?.description ||
              defaultLong
            }}
          </p>

          <div v-if="selected" class="detail-rsvp-panel">
            <div>
              <span class="detail-rsvp-label">Your RSVP</span>
              <strong>{{ rsvpLabel(eventStatus(selected)) }}</strong>
            </div>

            <div class="rsvp-actions">
              <button
                v-for="choice in rsvpChoices"
                :key="choice.value"
                type="button"
                class="rsvp-choice"
                :class="{ active: eventStatus(selected) === choice.value }"
                :disabled="settingRsvpFor === selected.id || isRsvpClosed(selected)"
                @click="updateRsvp(selected, choice.value)"
              >
                {{ choice.label }}
              </button>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button
            class="btn btn-outline"
            type="button"
            @click="closeDetails"
          >
            Close
          </button>

          <a
            v-if="eventLink(selected)"
            class="btn btn-primary"
            :href="eventLink(selected)"
            target="_blank"
            rel="noopener noreferrer"
          >
            {{ eventLinkLabel(selected) }}
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import {
  type BackendEvent,
  type EventListParams,
  type EventRsvpStatus,
  fetchEvents,
  fetchMyEventRsvps,
  resolveEventUrl,
  setEventRsvp
} from '../utils/eventsAPI'
import { formatEventDate, formatEventTimeRange } from '../utils/date'

type ViewMode = 'upcoming' | 'mine' | 'past'
type UserRsvpStatus = Exclude<EventRsvpStatus, 'pending'>

const auth = useAuthStore()

const loading = ref(true)
const error = ref('')
const statusMessage = ref('')
const statusVisible = ref(false)
const settingRsvpFor = ref<number | null>(null)
let statusTimer: ReturnType<typeof window.setTimeout> | null = null

const events = ref<BackendEvent[]>([])
const selected = ref<BackendEvent | null>(null)
const showModal = ref(false)
const viewMode = ref<ViewMode>('upcoming')
const rsvpsByEvent = ref<Record<number, EventRsvpStatus>>({})

const filters = ref({
  search: '',
  category: '',
  rsvpStatus: '' as '' | EventRsvpStatus
})

const defaultLong =
  'This session is part of the BIOTech Futures program. Learn, collaborate, and build your project with mentors and peers.'

const viewTabs: Array<{ value: ViewMode; label: string }> = [
  { value: 'upcoming', label: 'Upcoming' },
  { value: 'mine', label: 'My RSVPs' },
  { value: 'past', label: 'Past' }
]

const eventCategories = [
  { value: 'workshop', label: 'Workshop' },
  { value: 'webinar', label: 'Webinar' },
  { value: 'symposium', label: 'Symposium' },
  { value: 'networking', label: 'Networking' },
  { value: 'social', label: 'Social' },
  { value: 'other', label: 'Other' }
]

const rsvpFilterOptions: Array<{ value: EventRsvpStatus; label: string }> = [
  { value: 'pending', label: 'Pending invitation' },
  { value: 'accepted', label: 'Going' },
  { value: 'tentative', label: 'Maybe' },
  { value: 'declined', label: 'Declined' }
]

const rsvpChoices: Array<{ value: UserRsvpStatus; label: string; shortLabel: string }> = [
  { value: 'accepted', label: 'Going', shortLabel: 'Going' },
  { value: 'tentative', label: 'Maybe', shortLabel: 'Maybe' },
  { value: 'declined', label: 'Decline', shortLabel: 'Decline' }
]

const emptyTitle = computed(() => {
  if (viewMode.value === 'mine') return 'No RSVP events found'
  if (viewMode.value === 'past') return 'No past events found'
  return 'No upcoming events'
})

const emptyMessage = computed(() => {
  if (filters.value.search || filters.value.category || filters.value.rsvpStatus) {
    return 'Try adjusting the search or filters.'
  }

  if (viewMode.value === 'mine') {
    return 'Events you respond to will appear here.'
  }

  return 'Check back later for new BIOTech Futures sessions.'
})

const requestParams = (): EventListParams => {
  const params: EventListParams = {
    page_size: 100,
    ordering: viewMode.value === 'past' ? '-start_datetime' : 'start_datetime'
  }

  if (viewMode.value === 'past') {
    params.when = 'past'
  } else if (viewMode.value === 'mine') {
    params.when = 'all'
    params.rsvp_status = filters.value.rsvpStatus || ['pending', 'accepted', 'tentative', 'declined']
  } else {
    params.when = 'upcoming'
    if (filters.value.rsvpStatus) {
      params.rsvp_status = filters.value.rsvpStatus
    }
  }

  if (filters.value.search) {
    params.search = filters.value.search
  }

  if (filters.value.category) {
    params.category = filters.value.category
  }

  return params
}

const syncSelectedEvent = () => {
  if (!selected.value) return

  const updated = events.value.find((event) => event.id === selected.value?.id)
  if (updated) {
    selected.value = updated
  }
}

const loadUserRsvps = async () => {
  try {
    const response = await fetchMyEventRsvps()
    const nextMap: Record<number, EventRsvpStatus> = {}

    for (const row of response.results || []) {
      nextMap[row.event] = row.rsvp_status
    }

    rsvpsByEvent.value = nextMap
  } catch (err) {
    console.warn('Failed to load event RSVP status:', err)
    rsvpsByEvent.value = {}
  }
}

const loadEvents = async (silent = false) => {
  if (!silent) {
    loading.value = true
  }

  error.value = ''

  try {
    const [eventResponse] = await Promise.all([
      fetchEvents(requestParams()),
      loadUserRsvps()
    ])

    events.value = eventResponse.results || []
    syncSelectedEvent()
  } catch (err: any) {
    console.error(err)
    error.value = err?.message || 'Failed to load events'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadEvents()
})

onBeforeUnmount(() => {
  if (statusTimer) {
    window.clearTimeout(statusTimer)
  }
})

const showStatusMessage = (message: string) => {
  statusMessage.value = message
  statusVisible.value = true

  if (statusTimer) {
    window.clearTimeout(statusTimer)
  }

  statusTimer = window.setTimeout(() => {
    statusVisible.value = false
  }, 3000)
}

const setViewMode = (mode: ViewMode) => {
  if (viewMode.value === mode) return

  viewMode.value = mode
  statusVisible.value = false
  loadEvents()
}

const resetFilters = () => {
  filters.value = {
    search: '',
    category: '',
    rsvpStatus: ''
  }
  viewMode.value = 'upcoming'
  statusVisible.value = false
  loadEvents()
}

const formatDate = (dateStr?: string | null) => formatEventDate(dateStr, auth.timeZone)

const formatTime = (start?: string | null, end?: string | null) =>
  formatEventTimeRange(start, end, auth.timeZone)

const prettyType = (type?: string | null) => {
  if (!type) return 'General'

  return (
    type.charAt(0).toUpperCase() +
    type.slice(1)
  )
}

const eventCover = (ev?: BackendEvent | null) => resolveEventUrl(ev?.event_image)

const eventLink = (ev?: BackendEvent | null) => resolveEventUrl(ev?.location_link)

const eventLinkLabel = (ev?: BackendEvent | null) => {
  if (!ev) return ''
  if (ev.is_virtual) return 'Join Online'
  return ev.location || 'Open Map'
}

const eventLocationText = (ev?: BackendEvent | null) => {
  if (!ev) return 'TBA'
  if (ev.is_virtual) return 'Virtual Event'
  return ev.location || 'TBA'
}

const eventStatus = (ev?: BackendEvent | null): EventRsvpStatus | null => {
  if (!ev) return null
  return rsvpsByEvent.value[ev.id] || (ev.accepted ? 'accepted' : null)
}

const rsvpLabel = (status?: EventRsvpStatus | null) => {
  if (status === 'accepted') return 'Going'
  if (status === 'tentative') return 'Maybe'
  if (status === 'declined') return 'Declined'
  if (status === 'pending') return 'Pending'
  return 'No response'
}

const isRsvpClosed = (ev?: BackendEvent | null) => {
  if (!ev?.ends_datetime) return false
  return new Date(ev.ends_datetime).getTime() < Date.now()
}

const bannerStyle = (ev?: BackendEvent | null) => {
  const cover = eventCover(ev)

  if (cover) {
    return {
      backgroundImage: `url("${cover.replace(/"/g, '%22')}")`,
      backgroundSize: 'cover',
      backgroundPosition: 'center'
    }
  }

  return {
    backgroundColor: 'var(--dark-green)'
  }
}

const openDetails = (ev: BackendEvent) => {
  selected.value = ev
  showModal.value = true
}

const closeDetails = () => {
  showModal.value = false
  selected.value = null
}

const updateRsvp = async (ev: BackendEvent, status: UserRsvpStatus) => {
  if (!ev?.id || isRsvpClosed(ev)) return

  settingRsvpFor.value = ev.id
  statusVisible.value = false

  try {
    const response = await setEventRsvp(ev.id, status)
    rsvpsByEvent.value = {
      ...rsvpsByEvent.value,
      [ev.id]: response.rsvp_status
    }

    ev.accepted = response.rsvp_status === 'accepted'
    showStatusMessage(`RSVP updated: ${rsvpLabel(response.rsvp_status)}.`)
    await loadEvents(true)
  } catch (err: any) {
    console.error(err)
    error.value = err?.message || 'Failed to update your RSVP'
  } finally {
    settingRsvpFor.value = null
  }
}
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

.events-page {
  width: 100%;
  min-height: calc(100vh - 64px);
  padding: clamp(1rem, 2vw, 1.5rem);
  background-color: var(--bg-light);
}

.page-subtitle {
  margin: 0.35rem 0 0;
  color: #6c757d;
}

.event-toolbar {
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  box-shadow: 0 1px 3px var(--shadow);
}

.event-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.event-tab {
  border: 1px solid var(--border-light);
  background: var(--white);
  color: var(--charcoal);
  border-radius: 4px;
  padding: 0.5rem 0.85rem;
  font-weight: 600;
  cursor: pointer;
}

.event-tab.active {
  background: var(--dark-green);
  border-color: var(--dark-green);
  color: var(--white);
}

.event-filters {
  display: grid;
  grid-template-columns: minmax(220px, 1.4fr) minmax(160px, 0.8fr) minmax(160px, 0.8fr) auto;
  gap: 0.75rem;
  align-items: end;
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
  color: #6c757d;
  font-size: 0.875rem;
  font-weight: 600;
}

.filter-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.event-status-message {
  position: fixed;
  top: 78px;
  right: clamp(1rem, 3vw, 2rem);
  z-index: 2100;
  max-width: min(420px, calc(100vw - 2rem));
  margin: 0;
  padding: 0.75rem 1rem;
  border-radius: 6px;
  background: var(--light-green);
  color: var(--dark-green);
  box-shadow: 0 8px 24px rgba(7, 17, 15, 0.14);
  font-weight: 600;
}

.event-status-fade-enter-active,
.event-status-fade-leave-active {
  transition:
    opacity 0.28s ease,
    transform 0.28s ease;
}

.event-status-fade-enter-from,
.event-status-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
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

@media (max-width: 960px) {
  .event-filters {
    grid-template-columns: 1fr 1fr;
  }

  .filter-field-search,
  .filter-actions {
    grid-column: 1 / -1;
  }
}

@media (max-width: 900px) {
  .events-grid,
  .events-skeleton-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .event-filters {
    grid-template-columns: 1fr;
  }

  .filter-field-search,
  .filter-actions {
    grid-column: auto;
  }

  .filter-actions .btn {
    flex: 1;
  }
}

.event-card {
  background-color: var(--white);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 4px var(--shadow);
  margin-bottom: 0;
}

.event-card:hover {
  transform: none;
  box-shadow: 0 2px 4px var(--shadow);
}

.event-banner {
  position: relative;
  height: 150px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--white);
  font-size: inherit;
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

.event-banner i {
  font-size: 2.25rem;
  opacity: 0.9;
}

.event-content {
  padding: 1.5rem;
}

.event-card-topline {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}

.event-date {
  display: inline-block;
  background-color: var(--light-green);
  color: var(--dark-green);
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-size: 0.875rem;
  font-weight: 600;
  margin-bottom: 0;
}

.rsvp-badge {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  border-radius: 4px;
  padding: 0.25rem 0.65rem;
  font-size: 0.8rem;
  font-weight: 700;
  background: #eef2f7;
  color: #495057;
}

.rsvp-badge-accepted {
  background: var(--light-green);
  color: var(--dark-green);
}

.rsvp-badge-tentative,
.rsvp-badge-pending {
  background: #fff3cd;
  color: #856404;
}

.rsvp-badge-declined {
  background: #f8d7da;
  color: #842029;
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
  gap: 1rem 1.5rem;
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

.event-link {
  color: var(--dark-green);
  font-weight: 700;
  text-decoration: none;
}

.event-link:hover {
  text-decoration: underline;
}

.cta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.rsvp-actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.rsvp-choice {
  min-height: 38px;
  padding: 0.45rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  background: var(--white);
  color: var(--charcoal);
  font-weight: 700;
  cursor: pointer;
}

.rsvp-choice:hover:not(:disabled),
.rsvp-choice.active {
  border-color: var(--dark-green);
  background: var(--light-green);
  color: var(--dark-green);
}

.rsvp-choice:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.empty-state-card p {
  margin: 0.5rem 0 0;
  color: #6c757d;
}

.event-modal-content {
  max-width: 620px;
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

.detail-meta,
.detail-location {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1rem;
  color: #6c757d;
  margin-bottom: 0.75rem;
}

.detail-meta span,
.detail-location {
  align-items: center;
}

.detail-meta span,
.detail-location {
  display: inline-flex;
  gap: 0.35rem;
}

.detail-description {
  color: var(--charcoal);
  line-height: 1.6;
  margin: 1rem 0;
}

.detail-rsvp-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 1rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #f8f9fa;
}

.detail-rsvp-label {
  display: block;
  color: #6c757d;
  font-size: 0.85rem;
  font-weight: 700;
  margin-bottom: 0.2rem;
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
