<template>
  <div class="content-area events-page">
    <div class="page-head">
      <div>
        <h1>Events &amp; Workshops</h1>
        <p class="page-subtitle">
          {{ auth.roleLabel }} events available to your program access.
        </p>
      </div>
    </div>

    <div class="event-tabs" role="tablist" aria-label="Event view">
      <button
        v-for="tab in viewTabs"
        :key="tab.value"
        type="button"
        role="tab"
        :aria-selected="viewMode === tab.value"
        class="event-tab"
        :class="{ active: viewMode === tab.value }"
        @click="setViewMode(tab.value)"
      >
        {{ tab.label }}
      </button>
    </div>

    <section class="event-filterbar" aria-label="Event filters">
      <form class="filter-form" @submit.prevent="submitSearch">
        <label class="filter-field filter-field-search">
          <span class="filter-label">Search</span>
          <span class="filter-search-input-wrap">
            <i class="fas fa-search filter-search-icon" aria-hidden="true"></i>
            <input
              v-model.trim="filters.search"
              type="search"
              class="filter-input"
              placeholder="Title or description"
              @input="onSearchInput"
            />
            <button
              v-if="filters.search"
              type="button"
              class="filter-search-clear"
              aria-label="Clear search"
              @click="clearSearch"
            >
              &times;
            </button>
          </span>
        </label>

        <label class="filter-field">
          <span class="filter-label">Category</span>
          <select
            v-model="filters.category"
            class="filter-input filter-select"
            @change="loadEvents()"
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
          <span class="filter-label">RSVP</span>
          <select
            v-model="filters.rsvpStatus"
            class="filter-input filter-select"
            @change="loadEvents()"
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
          <button type="submit" class="btn btn-primary filter-submit">
            <i class="fas fa-search" aria-hidden="true"></i>
            <span>Search</span>
          </button>
          <button
            type="button"
            class="btn btn-outline filter-reset"
            @click="resetFilters"
          >
            Reset
          </button>
        </div>
      </form>
    </section>

    <Transition name="event-status-fade">
      <p
        v-if="statusVisible && statusMessage"
        class="event-status-message"
        role="status"
      >
        {{ statusMessage }}
      </p>
    </Transition>

    <Transition name="event-refresh-fade">
      <div
        v-if="refreshing"
        class="event-refresh-bar"
        role="status"
        aria-live="polite"
      >
        <span class="sr-only">Refreshing events...</span>
      </div>
    </Transition>

    <div v-if="loading" class="events-grid" role="status" aria-live="polite">
      <span class="sr-only">Loading events...</span>
      <article
        v-for="item in 4"
        :key="`event-skeleton-${item}`"
        class="event-card event-skeleton-card"
        :class="{ 'event-skeleton-card--featured': item === 1 }"
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
          </div>
          <div class="event-skeleton-actions">
            <div class="event-skeleton-button skeleton-block"></div>
            <div class="event-skeleton-button skeleton-block"></div>
          </div>
        </div>
      </article>
    </div>

    <div v-else-if="error" class="card events-error-card">
      <h3 class="events-error-title">Error</h3>
      <p class="events-error-message">{{ error }}</p>
      <button
        type="button"
        class="btn btn-primary events-error-retry"
        @click="loadEvents()"
      >
        Retry
      </button>
    </div>

    <TransitionGroup
      v-else-if="events.length"
      tag="div"
      name="event-list"
      class="events-grid"
    >
      <article
        v-for="(ev, idx) in events"
        :key="ev.id"
        class="event-card"
        :style="{ '--enter-delay': `${Math.min(idx, 8) * 50}ms` }"
        role="button"
        tabindex="0"
        @click="openDetailsFromCard(ev, $event)"
        @keydown.enter="openDetailsFromCard(ev, $event)"
        @keydown.space="openDetailsFromCard(ev, $event)"
      >
        <div class="event-banner">
          <img
            v-if="eventCover(ev)"
            :src="eventCover(ev)"
            :alt="`${ev.event_name} banner`"
            class="event-banner-img"
            width="640"
            height="220"
            loading="lazy"
            decoding="async"
          />
          <i
            v-else
            class="fas fa-calendar-alt"
            aria-hidden="true"
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

          <div class="event-card-tag-row">
            <span class="event-tag">{{ prettyType(ev.event_type) }}</span>
            <span class="event-tag event-tag-mode">
              <i
                :class="ev.is_virtual ? 'fas fa-video' : 'fas fa-map-marker-alt'"
                aria-hidden="true"
              ></i>
              {{ ev.is_virtual ? 'Virtual' : 'In-person' }}
            </span>
          </div>

          <p class="event-description">
            {{ ev.description || defaultShort }}
          </p>

          <div class="event-meta">
            <div class="event-meta-item">
              <i class="fas fa-clock" aria-hidden="true"></i>
              {{ formatTime(ev.start_datetime, ev.ends_datetime) }}
            </div>

            <div class="event-meta-item">
              <i class="fas fa-map-marker-alt" aria-hidden="true"></i>
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

            <div
              v-if="ev.max_attendees"
              class="event-meta-item event-capacity-row"
            >
              <i class="fas fa-users" aria-hidden="true"></i>
              <span
                class="event-capacity-pill"
                :class="`event-capacity-pill--${capacityVariant(ev)}`"
              >
                {{ capacityLabel(ev) }}
              </span>
              <span
                v-if="(ev.waitlist_count ?? 0) > 0"
                class="event-waitlist-chip"
                :title="`${ev.waitlist_count} on the waitlist`"
              >
                <i class="fas fa-hourglass-half" aria-hidden="true"></i>
                {{ ev.waitlist_count }} waitlisted
              </span>
            </div>
          </div>

          <div class="cta-row">
            <div
              v-if="shouldShowWaitlistAction(ev)"
              class="rsvp-actions"
            >
              <button
                v-if="eventStatus(ev) === 'waitlisted'"
                type="button"
                class="rsvp-choice rsvp-choice-waitlist active"
                :disabled="settingRsvpFor === ev.id || isRsvpClosed(ev)"
                @click="updateRsvp(ev, 'declined')"
              >
                <i class="fas fa-times" aria-hidden="true"></i>
                Leave waitlist
              </button>
              <button
                v-else
                type="button"
                class="rsvp-choice rsvp-choice-waitlist"
                :disabled="settingRsvpFor === ev.id || isRsvpClosed(ev)"
                @click="updateRsvp(ev, 'accepted')"
              >
                <i class="fas fa-hourglass-half" aria-hidden="true"></i>
                Join waitlist
              </button>
            </div>

            <div
              v-else
              class="rsvp-actions"
              aria-label="RSVP status"
            >
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
    </TransitionGroup>

    <div
      v-if="hasMore && !loading && !refreshing && events.length"
      ref="loadMoreSentinel"
      class="event-load-more"
      aria-hidden="true"
    >
      <div v-if="loadingMore" class="event-load-more-status" role="status" aria-live="polite">
        <span class="loading event-load-more-spinner" aria-hidden="true"></span>
        <span>Loading more events...</span>
      </div>
    </div>

    <div v-if="!events.length && !loading && !error" class="card empty-state-card">
      <div class="empty-illustration" aria-hidden="true">
        <span class="empty-ring empty-ring-outer"></span>
        <span class="empty-ring empty-ring-mid"></span>
        <span class="empty-ring empty-ring-inner">
          <i class="fas fa-calendar-alt"></i>
        </span>
      </div>
      <h3 class="empty-title">{{ emptyTitle }}</h3>
      <p class="empty-message">{{ emptyMessage }}</p>
      <button
        v-if="hasActiveFilters"
        type="button"
        class="btn btn-outline empty-action"
        @click="resetFilters"
      >
        Reset filters
      </button>
    </div>

    <div
      class="modal"
      :class="{ show: showModal }"
      role="dialog"
      aria-modal="true"
      aria-labelledby="event-modal-title"
      @click.self="closeDetails"
    >
      <div ref="modalContentRef" class="modal-content event-modal-content">
        <div class="modal-header">
          <div id="event-modal-title" class="modal-title">
            {{ selected?.event_name }}
          </div>

          <button
            ref="modalCloseRef"
            class="modal-close"
            type="button"
            aria-label="Close event details"
            @click="closeDetails"
          >
            &times;
          </button>
        </div>

        <div class="modal-body">
          <div class="detail-banner">
            <img
              v-if="eventCover(selected)"
              :src="eventCover(selected)"
              :alt="`${selected?.event_name} banner`"
              class="event-banner-img"
              width="1280"
              height="320"
              decoding="async"
            />
            <i
              v-else-if="selected"
              class="fas fa-calendar-alt"
              aria-hidden="true"
            ></i>
          </div>

          <div class="detail-meta">
            <span>
              <i class="fas fa-calendar-day" aria-hidden="true"></i>
              {{ formatDate(selected?.start_datetime) }}
            </span>
            <span>
              <i class="fas fa-clock" aria-hidden="true"></i>
              {{ formatTime(selected?.start_datetime, selected?.ends_datetime) }}
            </span>
            <span>
              <i class="fas fa-users" aria-hidden="true"></i>
              {{ prettyType(selected?.event_type) }}
            </span>
          </div>

          <div class="detail-location">
            <i class="fas fa-map-marker-alt" aria-hidden="true"></i>
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

          <div
            v-if="eventStatus(selected) === 'pending' && !isRsvpClosed(selected)"
            class="detail-pending-callout"
            role="note"
          >
            <i class="fas fa-bell" aria-hidden="true"></i>
            <span>
              You've been invited &mdash; please respond so the host can plan.
            </span>
          </div>

          <div
            v-if="eventStatus(selected) === 'waitlisted' && !isRsvpClosed(selected)"
            class="detail-waitlist-callout"
            role="note"
          >
            <i class="fas fa-hourglass-half" aria-hidden="true"></i>
            <span>
              You're on the waitlist &mdash; we'll email you if a spot opens up.
            </span>
          </div>

          <div
            v-else-if="
              isEventFull(selected) &&
              !isRsvpClosed(selected) &&
              eventStatus(selected) !== 'accepted'
            "
            class="detail-waitlist-callout"
            role="note"
          >
            <i class="fas fa-hourglass-half" aria-hidden="true"></i>
            <span>
              Event is at capacity. Tap <strong>Going</strong> to join the
              waitlist &mdash; you'll be auto-promoted if a spot opens.
            </span>
          </div>

          <div
            v-if="selected?.max_attendees"
            class="detail-capacity-row"
          >
            <span class="detail-capacity-label">Capacity</span>
            <span class="detail-capacity-value">
              <span
                class="event-capacity-pill"
                :class="`event-capacity-pill--${capacityVariant(selected)}`"
              >
                {{ capacityLabel(selected) }}
              </span>
            </span>
          </div>

          <p class="detail-description">
            {{ selected?.description || defaultLong }}
          </p>

          <div v-if="selected" class="detail-rsvp-panel">
            <div>
              <span class="detail-rsvp-label">Your RSVP</span>
              <strong>{{ rsvpLabel(eventStatus(selected)) }}</strong>
            </div>

            <div
              v-if="shouldShowWaitlistAction(selected)"
              class="rsvp-actions"
            >
              <button
                v-if="eventStatus(selected) === 'waitlisted'"
                type="button"
                class="rsvp-choice rsvp-choice-waitlist active"
                :disabled="settingRsvpFor === selected.id || isRsvpClosed(selected)"
                @click="updateRsvp(selected, 'declined')"
              >
                <i class="fas fa-times" aria-hidden="true"></i>
                Leave waitlist
              </button>
              <button
                v-else
                type="button"
                class="rsvp-choice rsvp-choice-waitlist"
                :disabled="settingRsvpFor === selected.id || isRsvpClosed(selected)"
                @click="updateRsvp(selected, 'accepted')"
              >
                <i class="fas fa-hourglass-half" aria-hidden="true"></i>
                Join waitlist
              </button>
            </div>

            <div
              v-else
              class="rsvp-actions"
            >
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

          <button
            v-if="selected"
            class="btn btn-outline"
            type="button"
            @click="downloadIcal(selected)"
          >
            <i class="fas fa-calendar-plus" aria-hidden="true"></i>
            <span>Add to calendar</span>
          </button>

          <a
            v-if="eventLink(selected)"
            class="btn btn-primary"
            :href="eventLink(selected)"
            target="_blank"
            rel="noopener noreferrer"
          >
            {{ eventCtaLabel(selected) }}
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import {
  type BackendEvent,
  type EventListParams,
  type EventRsvpStatus,
  downloadEventIcal,
  fetchEventById,
  fetchEvents,
  fetchEventsByUrl,
  fetchMyEventRsvps,
  resolveEventUrl,
  setEventRsvp
} from '../utils/eventsAPI'
import { formatEventDate, formatEventTimeRange } from '../utils/date'

type ViewMode = 'upcoming' | 'mine' | 'past'
type UserRsvpStatus = 'accepted' | 'tentative' | 'declined'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const statusMessage = ref('')
const statusVisible = ref(false)
const settingRsvpFor = ref<number | null>(null)
let statusTimer: ReturnType<typeof window.setTimeout> | null = null
let searchTimer: ReturnType<typeof window.setTimeout> | null = null
let lastSearchTerm = ''

const events = ref<BackendEvent[]>([])
const selected = ref<BackendEvent | null>(null)
const showModal = ref(false)
const modalCloseRef = ref<HTMLButtonElement | null>(null)
const modalContentRef = ref<HTMLElement | null>(null)
let lastTriggerEl: HTMLElement | null = null

const PAGE_SIZE = 12
const nextCursorUrl = ref<string | null>(null)
const hasMore = computed(() => Boolean(nextCursorUrl.value))
const loadingMore = ref(false)
const loadMoreSentinel = ref<HTMLElement | null>(null)
let loadMoreObserver: IntersectionObserver | null = null
const viewMode = ref<ViewMode>('upcoming')
const rsvpsByEvent = ref<Record<number, EventRsvpStatus>>({})

const filters = ref({
  search: '',
  category: '',
  rsvpStatus: '' as '' | EventRsvpStatus
})

const defaultShort = 'Join us for this BIOTech Futures session.'
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
  { value: 'pending', label: 'Pending' },
  { value: 'accepted', label: 'Going' },
  { value: 'tentative', label: 'Maybe' },
  { value: 'declined', label: 'Not going' },
  { value: 'waitlisted', label: 'Waitlisted' }
]

const rsvpChoices: Array<{ value: UserRsvpStatus; label: string; shortLabel: string }> = [
  { value: 'accepted', label: 'Going', shortLabel: 'Going' },
  { value: 'tentative', label: 'Maybe', shortLabel: 'Maybe' },
  { value: 'declined', label: 'Not going', shortLabel: 'Not going' }
]

const hasActiveFilters = computed(() =>
  Boolean(filters.value.search || filters.value.category || filters.value.rsvpStatus)
)

const emptyTitle = computed(() => {
  if (viewMode.value === 'mine') return 'No RSVP events found'
  if (viewMode.value === 'past') return 'No past events found'
  return 'No upcoming events'
})

const emptyMessage = computed(() => {
  if (hasActiveFilters.value) {
    return 'Try adjusting the search or filters.'
  }

  if (viewMode.value === 'mine') {
    return 'Events you respond to will appear here.'
  }

  return 'Check back later for new BIOTech Futures sessions.'
})

const requestParams = (): EventListParams => {
  const params: EventListParams = {
    page_size: PAGE_SIZE,
    ordering: viewMode.value === 'past' ? '-start_datetime' : 'start_datetime'
  }

  if (viewMode.value === 'past') {
    params.when = 'past'
  } else if (viewMode.value === 'mine') {
    params.when = 'all'
    // Default to events the user has actually responded to. "pending"
    // now means "pending OR no row" on the backend, so including it in
    // the default would expand My RSVPs to every visible event.
    params.rsvp_status = filters.value.rsvpStatus || ['accepted', 'tentative', 'declined']
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

const loadUserRsvps = async (eventIds?: number[]) => {
  if (eventIds && eventIds.length === 0) {
    rsvpsByEvent.value = {}
    return
  }
  try {
    const response = await fetchMyEventRsvps(
      eventIds ? { eventIds } : { pageSize: 100 }
    )
    const nextMap: Record<number, EventRsvpStatus> = eventIds
      ? { ...rsvpsByEvent.value }
      : {}
    for (const row of response.results || []) {
      nextMap[row.event] = row.rsvp_status
    }
    rsvpsByEvent.value = nextMap
  } catch (err) {
    console.warn('Failed to load event RSVP status:', err)
    if (!eventIds) {
      rsvpsByEvent.value = {}
    }
  }
}

const loadEvents = async (silent = false) => {
  if (silent) {
    // RSVP-triggered refresh: no visible indicator.
  } else if (events.value.length === 0 && !error.value) {
    loading.value = true
  } else {
    refreshing.value = true
  }

  error.value = ''
  nextCursorUrl.value = null

  try {
    const eventResponse = await fetchEvents(requestParams())
    const incoming = eventResponse.results || []
    events.value = incoming
    nextCursorUrl.value = eventResponse.next || null
    await loadUserRsvps(incoming.map((e) => e.id))
    syncSelectedEvent()
  } catch (err: any) {
    console.error(err)
    error.value = err?.message || 'Failed to load events'
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

const loadMore = async () => {
  if (!nextCursorUrl.value || loadingMore.value) return
  loadingMore.value = true
  try {
    const eventResponse = await fetchEventsByUrl(nextCursorUrl.value)
    const incoming = eventResponse.results || []
    // De-dup by id in case items drift between pages.
    const seen = new Set(events.value.map((e) => e.id))
    const fresh = incoming.filter((e) => !seen.has(e.id))
    events.value = [...events.value, ...fresh]
    nextCursorUrl.value = eventResponse.next || null
    await loadUserRsvps(fresh.map((e) => e.id))
  } catch (err: any) {
    console.error(err)
    error.value = err?.message || 'Failed to load more events'
  } finally {
    loadingMore.value = false
  }
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

const onKeyDown = (e: KeyboardEvent) => {
  if (!showModal.value) return
  if (e.key === 'Escape') {
    closeDetails()
    return
  }
  if (e.key !== 'Tab' || !modalContentRef.value) return
  const focusables = Array.from(
    modalContentRef.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter((el) => el.offsetParent !== null)
  if (!focusables.length) return
  const first = focusables[0]
  const last = focusables[focusables.length - 1]
  const active = document.activeElement as HTMLElement | null
  if (e.shiftKey && (active === first || !modalContentRef.value.contains(active))) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && (active === last || !modalContentRef.value.contains(active))) {
    e.preventDefault()
    first.focus()
  }
}

watch(showModal, async (open) => {
  if (open) {
    await nextTick()
    modalCloseRef.value?.focus()
  } else if (lastTriggerEl) {
    lastTriggerEl.focus()
    lastTriggerEl = null
  }
})

onMounted(async () => {
  await loadEvents()
  if (route.params.id) {
    await openDetailsById(route.params.id)
  }
  window.addEventListener('keydown', onKeyDown)

  // Auto-load the next page when the sentinel scrolls into view.
  // rootMargin pre-fetches a bit before the user actually hits the bottom.
  if ('IntersectionObserver' in window) {
    loadMoreObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && hasMore.value && !loadingMore.value) {
            void loadMore()
          }
        }
      },
      { rootMargin: '400px 0px 400px 0px' },
    )
  }
})

watch(loadMoreSentinel, (el, prev) => {
  if (!loadMoreObserver) return
  if (prev) loadMoreObserver.unobserve(prev)
  if (el) loadMoreObserver.observe(el)
})

watch(
  () => route.params.id,
  (id) => {
    if (id) {
      openDetailsById(id)
    } else if (showModal.value) {
      // URL was popped back to /events while the modal was open.
      showModal.value = false
      selected.value = null
    }
  },
)

onBeforeUnmount(() => {
  if (statusTimer) {
    window.clearTimeout(statusTimer)
  }
  if (searchTimer) {
    window.clearTimeout(searchTimer)
  }
  loadMoreObserver?.disconnect()
  loadMoreObserver = null
  window.removeEventListener('keydown', onKeyDown)
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

const clearSearch = () => {
  if (!filters.value.search) return
  filters.value.search = ''
  if (searchTimer) {
    window.clearTimeout(searchTimer)
    searchTimer = null
  }
  lastSearchTerm = ''
  loadEvents()
}

const onSearchInput = () => {
  if (searchTimer) {
    window.clearTimeout(searchTimer)
  }
  searchTimer = window.setTimeout(() => {
    searchTimer = null
    const term = filters.value.search
    if (term === lastSearchTerm) return
    lastSearchTerm = term
    loadEvents()
  }, 350)
}

const submitSearch = () => {
  if (searchTimer) {
    window.clearTimeout(searchTimer)
    searchTimer = null
  }
  lastSearchTerm = filters.value.search
  loadEvents()
}

const resetFilters = () => {
  const hadFilters = hasActiveFilters.value || viewMode.value !== 'upcoming'

  if (searchTimer) {
    window.clearTimeout(searchTimer)
    searchTimer = null
  }
  lastSearchTerm = ''

  filters.value = {
    search: '',
    category: '',
    rsvpStatus: ''
  }
  viewMode.value = 'upcoming'
  statusVisible.value = false

  if (hadFilters) {
    loadEvents()
  }
}

const formatDate = (dateStr?: string | null) => formatEventDate(dateStr, auth.timeZone)

const formatTime = (start?: string | null, end?: string | null) =>
  formatEventTimeRange(start, end, auth.timeZone)

const prettyType = (type?: string | null) => {
  if (!type) return 'General'
  return type.charAt(0).toUpperCase() + type.slice(1)
}

const eventCover = (ev?: BackendEvent | null) => resolveEventUrl(ev?.event_image)

const eventLink = (ev?: BackendEvent | null) => resolveEventUrl(ev?.location_link)

const eventLinkLabel = (ev?: BackendEvent | null) => {
  if (!ev) return ''
  if (ev.is_virtual) return 'Join Online'
  return ev.location || 'Open Map'
}

const eventCtaLabel = (ev?: BackendEvent | null) => {
  if (!ev) return ''
  if (ev.is_virtual) return 'Join Online'
  return 'Open Map'
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
  if (status === 'declined') return 'Not going'
  if (status === 'pending') return 'Pending'
  if (status === 'waitlisted') return 'Waitlisted'
  return 'No response'
}

const slotsLeft = (ev?: BackendEvent | null) => {
  if (!ev?.max_attendees) return null
  return Math.max(0, ev.max_attendees - (ev.accepted_count ?? 0))
}

const isEventFull = (ev?: BackendEvent | null) => slotsLeft(ev) === 0

const shouldShowWaitlistAction = (ev?: BackendEvent | null) => {
  // Show only the waitlist action (and not the three RSVP buttons)
  // when the event is full and the caller doesn't already hold an
  // ACCEPTED slot — i.e. clicking Going would just put them on the
  // waitlist anyway, so let's be explicit about it.
  if (!ev) return false
  return isEventFull(ev) && eventStatus(ev) !== 'accepted'
}

type CapacityVariant = 'none' | 'open' | 'low' | 'full'

const capacityVariant = (ev?: BackendEvent | null): CapacityVariant => {
  const left = slotsLeft(ev)
  if (left === null) return 'none'
  if (left === 0) return 'full'
  if (left < 10) return 'low'
  return 'open'
}

const capacityLabel = (ev?: BackendEvent | null) => {
  const left = slotsLeft(ev)
  if (left === null) return ''
  if (left === 0) return 'Full'
  if (left === 1) return '1 left'
  if (left < 10) return `${left} left`
  return 'Slots available'
}

const capacityDetail = (ev?: BackendEvent | null) => {
  if (!ev || !ev.max_attendees) return ''
  const accepted = ev.accepted_count ?? 0
  const waitlist = ev.waitlist_count ?? 0
  const base = `${accepted}/${ev.max_attendees} going`
  if (waitlist > 0) return `${base} · ${waitlist} on waitlist`
  return base
}

const isRsvpClosed = (ev?: BackendEvent | null) => {
  if (!ev?.ends_datetime) return false
  return new Date(ev.ends_datetime).getTime() < Date.now()
}

const openDetails = (ev: BackendEvent, event?: MouseEvent) => {
  lastTriggerEl = (event?.currentTarget as HTMLElement) || (document.activeElement as HTMLElement)
  selected.value = ev
  showModal.value = true
  if (ev.id && String(route.params.id) !== String(ev.id)) {
    router.push({ name: 'event-detail', params: { id: ev.id } })
  }
}

const shouldIgnoreCardOpen = (event?: Event) => {
  const target = event?.target
  if (!(target instanceof Element)) return false
  return Boolean(target.closest('a, button, input, select, textarea, [data-event-card-ignore]'))
}

const openDetailsFromCard = (ev: BackendEvent, event: MouseEvent | KeyboardEvent) => {
  if (shouldIgnoreCardOpen(event)) return
  event.preventDefault()
  openDetails(ev, event as MouseEvent)
}

const openDetailsById = async (rawId: string | string[] | undefined) => {
  const id = Array.isArray(rawId) ? rawId[0] : rawId
  if (!id) return
  const n = Number(id)
  if (!Number.isFinite(n)) return
  const existing = events.value.find((e) => e.id === n)
  if (existing) {
    selected.value = existing
    showModal.value = true
    return
  }
  try {
    const ev = await fetchEventById(n)
    selected.value = ev
    showModal.value = true
  } catch (err) {
    // Event not visible / not found — drop the modal request silently
    // and snap the URL back to the list so the user isn't stuck.
    console.warn('Deep-linked event not available:', err)
    if (route.name === 'event-detail') {
      router.replace({ name: 'events' })
    }
  }
}

const downloadIcal = async (ev: BackendEvent) => {
  if (!ev?.id) return
  try {
    await downloadEventIcal(ev.id, ev.event_name)
    showStatusMessage('Calendar file downloaded.')
  } catch (err: any) {
    console.error(err)
    error.value = err?.message || 'Failed to download calendar file'
  }
}

const closeDetails = () => {
  showModal.value = false
  selected.value = null
  if (route.name === 'event-detail') {
    router.push({ name: 'events' })
  }
}

const updateRsvp = async (ev: BackendEvent, status: UserRsvpStatus) => {
  if (!ev?.id || isRsvpClosed(ev)) return

  const previousStatus = eventStatus(ev)
  settingRsvpFor.value = ev.id
  statusVisible.value = false

  try {
    const response = await setEventRsvp(ev.id, status)
    rsvpsByEvent.value = {
      ...rsvpsByEvent.value,
      [ev.id]: response.rsvp_status
    }

    ev.accepted = response.rsvp_status === 'accepted'
    if (status === 'accepted' && response.rsvp_status === 'waitlisted') {
      showStatusMessage("Event full — you're on the waitlist.")
    } else if (previousStatus === 'waitlisted' && status === 'declined') {
      showStatusMessage('RSVP updated: Removed from waitlist')
    } else {
      showStatusMessage(`RSVP updated: ${rsvpLabel(response.rsvp_status)}`)
    }
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
.events-page {
  --event-dark-green: #017151;
  --event-light-green: #bad7bb;
  --event-air-force-blue: #39687b;
  --event-mint-green: #5ea99e;
  --event-yellow: #f1e5a6;
  --event-charcoal: #174243;
  --event-soft-green: rgba(186, 215, 187, 0.44);
  --event-soft-mint: rgba(94, 169, 158, 0.18);
  --event-soft-blue: rgba(57, 104, 123, 0.12);
  --event-soft-yellow: rgba(241, 229, 166, 0.78);

  width: 100%;
  min-height: calc(100vh - 64px);
  padding: clamp(1rem, 2vw, 1.5rem);
  background-color: var(--bg-light);
  color: var(--charcoal);
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.25rem;
}

.page-head h1 {
  margin: 0;
  font-size: clamp(1.5rem, 2.2vw, 2rem);
}

.page-subtitle {
  margin: 0.35rem 0 0;
  color: var(--text-muted);
}

/* Segmented pill tabs */
.event-tabs {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  padding: 0.3rem;
  margin-bottom: 1rem;
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 999px;
  box-shadow: 0 1px 2px var(--shadow);
}

.event-tab {
  border: none;
  background: transparent;
  color: var(--text-muted);
  border-radius: 999px;
  padding: 0.5rem 1.1rem;
  font-weight: 600;
  font-size: 0.92rem;
  cursor: pointer;
  transition: color 0.18s ease, background-color 0.18s ease;
}

.event-tab:hover:not(.active) {
  color: var(--event-charcoal);
  background: var(--event-soft-green);
}

.event-tab.active {
  background: var(--event-dark-green);
  color: var(--white);
  box-shadow: 0 1px 3px rgba(1, 113, 81, 0.3);
}

/* Sticky filter bar */
.event-filterbar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  margin: 0 calc(clamp(1rem, 2vw, 1.5rem) * -1) 1.25rem;
  padding: 0.85rem clamp(1rem, 2vw, 1.5rem);
  background: var(--bg-light);
  border-bottom: 1px solid var(--border-light);
}

.filter-form {
  display: grid;
  grid-template-columns: minmax(220px, 1.4fr) minmax(160px, 0.8fr) minmax(160px, 0.8fr) auto;
  gap: 0.75rem;
  align-items: end;
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  min-width: 0;
}

.filter-label {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.filter-search-input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.filter-search-icon {
  position: absolute;
  left: 0.85rem;
  color: var(--text-muted);
  pointer-events: none;
  font-size: 0.85rem;
}

.filter-input {
  width: 100%;
  padding: 0.55rem 0.85rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
  font-size: 0.92rem;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.filter-search-input-wrap .filter-input {
  padding-left: 2.25rem;
  padding-right: 2.25rem;
}

.filter-input:focus {
  outline: none;
  border-color: var(--event-dark-green);
  box-shadow: 0 0 0 3px rgba(1, 113, 81, 0.15);
}

.filter-select {
  appearance: none;
  -webkit-appearance: none;
  background-image: linear-gradient(45deg, transparent 50%, var(--text-muted) 50%),
                    linear-gradient(135deg, var(--text-muted) 50%, transparent 50%);
  background-position: calc(100% - 18px) 50%, calc(100% - 13px) 50%;
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
  padding-right: 2rem;
  cursor: pointer;
}

.filter-search-clear {
  position: absolute;
  right: 0.5rem;
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 1.2rem;
  line-height: 1;
  padding: 0.15rem 0.4rem;
  border-radius: 999px;
  cursor: pointer;
}

.filter-search-clear:hover {
  color: var(--event-charcoal);
  background: var(--event-soft-green);
}

.filter-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.filter-submit,
.filter-reset {
  border-radius: 8px;
  padding: 0.55rem 1rem;
  font-size: 0.9rem;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

/* Status toast (kept) */
.event-status-message {
  position: fixed;
  top: 78px;
  right: clamp(1rem, 3vw, 2rem);
  z-index: 2100;
  max-width: min(420px, calc(100vw - 2rem));
  margin: 0;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  background: var(--event-soft-green);
  color: var(--event-dark-green);
  border: 1px solid var(--event-light-green);
  box-shadow: 0 8px 24px var(--shadow);
  font-weight: 600;
}

.event-status-fade-enter-active,
.event-status-fade-leave-active {
  transition: opacity 0.28s ease, transform 0.28s ease;
}

.event-status-fade-enter-from,
.event-status-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* Refresh progress bar — sits at top of grid during filter/tab reloads */
.event-refresh-bar {
  position: relative;
  height: 3px;
  width: 100%;
  margin-bottom: 0.85rem;
  border-radius: 2px;
  background: var(--border-light);
  overflow: hidden;
}

.event-refresh-bar::after {
  position: absolute;
  inset: 0;
  content: '';
  background: linear-gradient(
    90deg,
    transparent 0%,
    var(--event-dark-green) 40%,
    var(--event-dark-green) 60%,
    transparent 100%
  );
  animation: event-refresh-slide 1.1s linear infinite;
}

@keyframes event-refresh-slide {
  from {
    transform: translateX(-100%);
  }
  to {
    transform: translateX(100%);
  }
}

.event-refresh-fade-enter-active,
.event-refresh-fade-leave-active {
  transition: opacity 0.18s ease;
}

.event-refresh-fade-enter-from,
.event-refresh-fade-leave-to {
  opacity: 0;
}

/* Event grid — denser, auto-fill */
.events-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1rem;
}

/* Card */
.event-card {
  position: relative;
  display: flex;
  flex-direction: column;
  background-color: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 2px var(--shadow);
  cursor: pointer;
  margin-bottom: 0;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
  /* Tells the browser this card's paint and layout are self-contained,
     so unrelated mutations don't trigger a re-layout of the whole grid. */
  contain: layout paint style;
}

.event-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px var(--shadow);
  border-color: var(--event-light-green);
}

.event-banner {
  position: relative;
  height: 110px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--white);
  background: linear-gradient(135deg, var(--event-dark-green), var(--event-mint-green));
  overflow: hidden;
}

.event-banner-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
  display: block;
}

.event-banner i {
  font-size: 1.75rem;
  opacity: 0.9;
  position: relative;
}

.event-content {
  padding: 1rem 1rem 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  flex: 1;
}

.event-card-topline {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.65rem;
  flex-wrap: wrap;
  line-height: 1;
}

.event-date {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  height: 26px;
  min-height: 26px;
  margin: 0;
  background-color: var(--event-soft-green);
  color: var(--event-dark-green);
  padding: 0.2rem 0.65rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0.02em;
}

.rsvp-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  height: 26px;
  min-height: 26px;
  margin: 0;
  border-radius: 999px;
  padding: 0.2rem 0.65rem;
  font-size: 0.72rem;
  font-weight: 700;
  line-height: 1;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  background: var(--border-light);
  color: var(--text-muted);
}

.rsvp-badge-accepted {
  background: var(--event-soft-green);
  color: var(--event-dark-green);
}

.rsvp-badge-tentative {
  background: var(--event-soft-yellow);
  color: var(--event-air-force-blue);
}

.rsvp-badge-pending {
  background: var(--event-soft-blue);
  color: var(--event-air-force-blue);
}

.rsvp-badge-declined {
  background: rgba(248, 113, 113, 0.18);
  color: var(--danger);
}

.rsvp-badge-waitlisted {
  background: var(--event-soft-mint);
  color: var(--event-air-force-blue);
}

.event-capacity-row {
  align-items: center;
}

.event-capacity-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  border: 1px solid transparent;
}

.event-capacity-pill--open {
  background: var(--event-soft-green);
  color: var(--event-dark-green);
  border-color: var(--event-light-green);
}

.event-capacity-pill--low {
  background: var(--event-soft-yellow);
  color: var(--event-air-force-blue);
  border-color: rgba(57, 104, 123, 0.28);
}

.event-capacity-pill--full {
  background: var(--event-soft-blue);
  color: var(--event-air-force-blue);
  border-color: rgba(57, 104, 123, 0.28);
}

.event-title {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--charcoal);
  margin: 0;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.event-card-tag-row {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.event-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: var(--bg-light);
  color: var(--text-muted);
  border: 1px solid var(--border-light);
}

.event-tag-mode i {
  font-size: 0.7rem;
}

.event-description {
  color: var(--text-muted);
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.event-meta {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.82rem;
  color: var(--text-muted);
  margin-top: auto;
}

.event-meta-item {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.event-meta-item i {
  color: var(--event-dark-green);
  font-size: 0.78rem;
  width: 12px;
  text-align: center;
}

.event-link {
  color: var(--event-dark-green);
  font-weight: 600;
  text-decoration: none;
}

.event-link:hover {
  text-decoration: underline;
}

.cta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  flex-wrap: wrap;
  margin-top: 0.4rem;
  padding-top: 0.6rem;
  border-top: 1px solid var(--border-light);
}

.cta-row .btn {
  padding: 0.4rem 0.85rem;
  font-size: 0.85rem;
  border-radius: 999px;
}

.rsvp-actions {
  display: flex;
  gap: 0.3rem;
  flex-wrap: wrap;
}

.rsvp-choice {
  min-height: 32px;
  padding: 0.3rem 0.65rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background: var(--white);
  color: var(--charcoal);
  font-weight: 600;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.rsvp-choice:hover:not(:disabled):not(.active) {
  border-color: var(--event-dark-green);
  background: var(--event-soft-green);
  color: var(--event-dark-green);
}

.rsvp-choice.active {
  border-color: var(--event-dark-green);
  background: var(--event-dark-green);
  color: var(--white);
}

.rsvp-choice:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.rsvp-choice-waitlist {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.85rem;
  border-color: var(--event-mint-green);
  color: var(--event-air-force-blue);
  background: var(--event-soft-mint);
}

.rsvp-choice-waitlist:hover:not(:disabled):not(.active) {
  background: rgba(94, 169, 158, 0.26);
  border-color: var(--event-mint-green);
  color: var(--event-air-force-blue);
}

.rsvp-choice-waitlist.active {
  background: var(--event-air-force-blue);
  border-color: var(--event-air-force-blue);
  color: var(--white);
}

.event-waitlist-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  background: var(--event-soft-mint);
  color: var(--event-air-force-blue);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  border: 1px solid rgba(94, 169, 158, 0.34);
}

.event-waitlist-chip i {
  font-size: 0.7rem;
}

/* Skeletons */
.event-skeleton-card {
  pointer-events: none;
}

.event-skeleton-card:hover {
  transform: none;
  box-shadow: 0 1px 2px var(--shadow);
  border-color: var(--border-light);
}

.event-skeleton-banner {
  height: 110px;
  border-radius: 0;
}

.event-skeleton-card--featured .event-skeleton-banner {
  height: 150px;
}

.event-skeleton-date {
  width: 110px;
  height: 22px;
  margin-bottom: 0.55rem;
}

.event-skeleton-title {
  width: 72%;
  height: 20px;
  margin-bottom: 0.65rem;
}

.event-skeleton-line {
  width: 100%;
  height: 12px;
  margin-bottom: 0.45rem;
}

.event-skeleton-line--short {
  width: 60%;
  margin-bottom: 0.85rem;
}

.event-skeleton-meta,
.event-skeleton-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.event-skeleton-meta {
  margin-bottom: 0.75rem;
}

.event-skeleton-chip {
  width: 90px;
  height: 16px;
}

.event-skeleton-button {
  width: 88px;
  height: 32px;
}

.skeleton-block {
  position: relative;
  overflow: hidden;
  border-radius: 6px;
  background: var(--border-light);
}

.skeleton-block::after {
  position: absolute;
  inset: 0;
  content: '';
  transform: translateX(-100%);
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.55),
    transparent
  );
  animation: events-loading-shimmer 1.1s ease-in-out infinite;
}

@keyframes events-loading-shimmer {
  100% {
    transform: translateX(100%);
  }
}

/* Load-more row */
.event-load-more {
  display: flex;
  justify-content: center;
  padding: 1.5rem 0 0.5rem;
}

.event-load-more-spinner {
  width: 14px;
  height: 14px;
  border-width: 2px;
}

.event-load-more-status {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.4rem 0.85rem;
  font-size: 0.88rem;
  color: var(--air-force-blue);
}

/* Error card */
.events-error-card {
  border-left: 4px solid var(--danger);
}

.events-error-title {
  color: var(--danger);
  margin-bottom: 0.4rem;
}

.events-error-message {
  color: var(--text-muted);
  margin-bottom: 1rem;
}

.events-error-retry {
  margin-top: 0.25rem;
}

/* Empty state */
.empty-state-card {
  text-align: center;
  padding: 2.5rem 1.5rem;
  background: var(--white);
}

.empty-illustration {
  position: relative;
  width: 96px;
  height: 96px;
  margin: 0 auto 1.25rem;
}

.empty-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-ring-outer {
  background: var(--event-soft-green);
  opacity: 0.45;
}

.empty-ring-mid {
  inset: 14px;
  background: var(--event-light-green);
  opacity: 0.7;
}

.empty-ring-inner {
  inset: 28px;
  background: var(--event-dark-green);
  color: var(--white);
}

.empty-ring-inner i {
  font-size: 1.1rem;
}

.empty-title {
  margin: 0 0 0.4rem;
  font-size: 1.1rem;
  color: var(--charcoal);
}

.empty-message {
  margin: 0;
  color: var(--text-muted);
}

.empty-action {
  margin-top: 1rem;
  border-radius: 999px;
  padding: 0.5rem 1.2rem;
}

/* Detail modal */
.event-modal-content {
  max-width: 720px;
  background: var(--surface-elevated);
  color: var(--charcoal);
  border: 1px solid var(--border-light);
  /* Replace the global slideIn keyframe for this modal only. */
  animation: events-modal-in 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}

@supports (backdrop-filter: blur(0)) {
  :deep(.modal.show) {
    backdrop-filter: blur(6px);
  }
}

@keyframes events-modal-in {
  from {
    transform: scale(0.96);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

.detail-banner {
  position: relative;
  height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--white);
  background: linear-gradient(135deg, var(--event-dark-green), var(--event-mint-green));
  border-radius: 8px;
  margin-bottom: 1rem;
  overflow: hidden;
}

.detail-banner .event-banner-img {
  border-radius: 8px;
}

.detail-banner i {
  font-size: 2.25rem;
  opacity: 0.9;
}

.detail-meta,
.detail-location {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem 1rem;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
}

.detail-meta span,
.detail-location {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.detail-meta i,
.detail-location i {
  color: var(--event-dark-green);
}

.detail-description {
  color: var(--charcoal);
  line-height: 1.6;
  margin: 1rem 0;
}

.detail-pending-callout,
.detail-waitlist-callout {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.7rem 0.9rem;
  margin: 0.75rem 0 0.5rem;
  border-radius: 10px;
  font-size: 0.9rem;
  font-weight: 600;
}

.detail-pending-callout {
  border: 1px solid rgba(57, 104, 123, 0.28);
  background: var(--event-soft-blue);
  color: var(--event-air-force-blue);
}

.detail-waitlist-callout {
  border: 1px solid rgba(94, 169, 158, 0.34);
  background: var(--event-soft-mint);
  color: var(--event-air-force-blue);
}

.detail-pending-callout i,
.detail-waitlist-callout i {
  font-size: 1rem;
}

.detail-capacity-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.6rem 0.9rem;
  margin: 0.5rem 0;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: var(--bg-light);
  font-size: 0.9rem;
}

.detail-capacity-label {
  color: var(--text-muted);
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  font-size: 0.78rem;
}

.detail-capacity-value {
  color: var(--charcoal);
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}


.detail-rsvp-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 1rem;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: var(--bg-light);
}

.detail-rsvp-label {
  display: block;
  color: var(--text-muted);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin-bottom: 0.2rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.65rem;
  padding: 1rem 1.5rem 1.25rem;
  border-top: 1px solid var(--border-light);
  flex-wrap: wrap;
}

/* Grid item enter transition */
.event-list-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.event-list-enter-active {
  transition: opacity 0.28s ease, transform 0.28s ease;
  transition-delay: var(--enter-delay, 0ms);
}

.event-list-leave-active {
  transition: opacity 0.16s ease;
  position: absolute;
}

.event-list-leave-to {
  opacity: 0;
}

/* Reduced-motion: strip non-essential transitions */
@media (prefers-reduced-motion: reduce) {
  .event-tab,
  .filter-input,
  .event-card,
  .rsvp-choice,
  .event-list-enter-active,
  .event-list-leave-active,
  .event-status-fade-enter-active,
  .event-status-fade-leave-active,
  .event-refresh-fade-enter-active,
  .event-refresh-fade-leave-active {
    transition: none !important;
  }

  .event-card:hover {
    transform: none;
  }

  .event-modal-content {
    animation: none;
  }

  .skeleton-block::after,
  .event-refresh-bar::after {
    animation: none;
  }
}

/* Focus visibility */
.event-tab:focus-visible,
.filter-chip:focus-visible,
.filter-search-clear:focus-visible,
.rsvp-choice:focus-visible,
.event-card:focus-within {
  outline: 2px solid var(--event-dark-green);
  outline-offset: 2px;
}

/* Reduced-motion guard for the filter form */
@media (prefers-reduced-motion: reduce) {
  .filter-input {
    transition: none !important;
  }
}

/* Responsive */
@media (max-width: 960px) {
  .filter-form {
    grid-template-columns: 1fr 1fr;
  }

  .filter-field-search,
  .filter-actions {
    grid-column: 1 / -1;
  }
}

@media (max-width: 720px) {
  .events-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .filter-form {
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
</style>
