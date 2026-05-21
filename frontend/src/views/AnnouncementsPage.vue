<template>
  <div class="content-area announcements">
    <header class="announcements__hero">
      <div class="announcements__hero-text">
        <p class="announcements__eyebrow">Program updates</p>
        <h1 class="announcements__title">Announcements</h1>
        <p class="announcements__subtitle">
          <template v-if="!isLoading">
            <template v-if="totalCount">
              Showing
              <strong>{{ filtered.length }}</strong>
              of
              <strong>{{ totalCount }}</strong>
              {{ totalCount === 1 ? 'post' : 'posts' }}
            </template>
            <template v-else>No posts yet</template>
          </template>
          <template v-else>Loading the latest updates&hellip;</template>
        </p>
      </div>

      <label class="announcements__search">
        <span class="sr-only">Search announcements</span>
        <input
          v-model="q"
          type="text"
          placeholder="Search by title, body, or audience"
          aria-label="Search announcements"
        />
        <button
          v-if="q"
          type="button"
          class="announcements__search-clear"
          aria-label="Clear search"
          @click="q = ''"
        >
          &times;
        </button>
      </label>
    </header>

    <div
      v-if="visibleAudienceFilters.length || myGroups.length"
      class="announcements__filterbar"
    >
      <div
        v-if="visibleAudienceFilters.length"
        class="announcements__filters"
        role="tablist"
        aria-label="Filter by audience"
      >
        <button
          v-for="option in visibleAudienceFilters"
          :key="option.value"
          type="button"
          role="tab"
          :aria-selected="audienceFilter === option.value"
          class="filter-chip"
          :class="{ 'filter-chip--active': audienceFilter === option.value }"
          @click="toggleAudienceFilter(option.value)"
        >
          {{ option.label }}
        </button>
      </div>

      <label v-if="myGroups.length" class="announcements__group-filter">
        <span class="sr-only">Filter by group</span>
        <select v-model.number="groupFilter" class="announcements__group-select">
          <option :value="0">All groups</option>
          <option v-for="g in myGroups" :key="g.id" :value="g.id">{{ g.name }}</option>
        </select>
      </label>
    </div>

    <div
      v-if="isLoading"
      class="announcements__list"
      role="status"
      aria-live="polite"
    >
      <span class="sr-only">Loading announcements&hellip;</span>
      <AnnouncementSkeleton
        v-for="i in 4"
        :key="`skeleton-${i}`"
        :with-media="i % 2 === 0"
      />
    </div>

    <div v-else-if="error" class="announcements__error card">
      <h2>{{ errorTitle }}</h2>
      <p>{{ error.message }}</p>
      <button class="btn btn-outline btn-sm" type="button" @click="load">Try again</button>
    </div>

    <template v-else>
      <div v-if="filtered.length" class="announcements__list">
        <AnnouncementCard
          v-for="item in filtered"
          :key="item.id"
          :announcement="item"
          @image-error="onImageError"
        />
      </div>

      <div v-else class="announcements__empty card">
        <div class="announcements__empty-icon" aria-hidden="true">&#128276;</div>
        <h2>{{ emptyTitle }}</h2>
        <p>{{ emptyMessage }}</p>
        <button
          v-if="hasActiveFilters"
          type="button"
          class="btn btn-outline btn-sm"
          @click="clearFilters"
        >
          Clear filters
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import AnnouncementCard from '@/components/announcements/AnnouncementCard.vue'
import AnnouncementSkeleton from '@/components/announcements/AnnouncementSkeleton.vue'
import {
  AUDIENCE_FILTERS_FOR_ROLE,
  audienceMatches,
  fetchMyGroups,
  getAudienceLabel,
  type UserGroupOption,
  useAnnouncements
} from '@/composables/useAnnouncements'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const { announcements, isLoading, error, load } = useAnnouncements()

const q = ref('')
const audienceFilter = ref<string>('all')
const groupFilter = ref<number>(0) // 0 = "All groups"
const myGroups = ref<UserGroupOption[]>([])

const callerRole = computed<'admin' | 'mentor' | 'supervisor' | 'student'>(() => {
  if (auth.isAdmin) return 'admin'
  if (auth.isMentor) return 'mentor'
  if (auth.isSupervisor) return 'supervisor'
  return 'student'
})

// Available chips depend on the caller's role. A student never sees the
// Mentor / Supervisor chips because their backend-scoped feed wouldn't
// contain matching announcements anyway.
const roleAudienceFilters = computed(() => AUDIENCE_FILTERS_FOR_ROLE(callerRole.value))
const visibleAudienceFilters = computed(() =>
  roleAudienceFilters.value.filter((option) => !['all', 'student'].includes(option.value))
)

// If the active chip becomes hidden after a role change, snap back to All.
watch(roleAudienceFilters, (chips) => {
  if (!chips.some((c) => c.value === audienceFilter.value)) {
    audienceFilter.value = 'all'
  }
})

const totalCount = computed(() => announcements.value.length)

const filtered = computed(() => {
  const text = q.value.trim().toLowerCase()
  const gid = groupFilter.value
  return announcements.value.filter(item => {
    if (!audienceMatches(item, audienceFilter.value)) return false
    if (gid && !item.groupIds.includes(gid)) return false
    if (!text) return true
    return [item.title, item.bodyText, getAudienceLabel(item.audience)].some(
      field => String(field || '').toLowerCase().includes(text)
    )
  })
})

const hasActiveFilters = computed(() => Boolean(q.value) || audienceFilter.value !== 'all')

const emptyTitle = computed(() => {
  if (totalCount.value === 0) return 'No announcements yet'
  return 'No matches'
})

const emptyMessage = computed(() => {
  if (totalCount.value === 0) {
    return 'When new updates are posted, they will appear here.'
  }
  if (q.value && audienceFilter.value !== 'all') {
    return `Nothing matches "${q.value}" in this audience.`
  }
  if (q.value) return `Nothing matches "${q.value}".`
  return 'No announcements match the selected audience.'
})

const errorTitle = computed(() => {
  if (!error.value) return 'Something went wrong'
  if (error.value.kind === 'auth') return 'Session expired'
  if (error.value.kind === 'network') return 'No connection'
  if (error.value.kind === 'server') return 'Service unavailable'
  return 'Could not load announcements'
})

function clearFilters() {
  q.value = ''
  audienceFilter.value = 'all'
  groupFilter.value = 0
}

function toggleAudienceFilter(value: string) {
  audienceFilter.value = audienceFilter.value === value ? 'all' : value
}

function onImageError({ id, url }: { id: number | string; url: string }) {
  const target = announcements.value.find(item => item.id === id)
  if (target) target.images = target.images.filter(image => image.url !== url)
}

onMounted(async () => {
  await load()
  // Group list is non-critical to first paint — fire after the feed loads.
  myGroups.value = await fetchMyGroups(auth.user?.id ?? null)
})
</script>

<style scoped>
.announcements {
  --hero-bg: linear-gradient(135deg, rgba(1, 113, 81, 0.06), rgba(94, 169, 158, 0.08));
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  width: min(100%, 1100px);
  margin: 0 auto;
}

.announcements__hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1.5rem;
  padding: 1.75rem;
  border-radius: 20px;
  background: var(--hero-bg);
  border: 1px solid rgba(1, 113, 81, 0.08);
}

.announcements__hero-text {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
}

.announcements__eyebrow {
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--dark-green);
}

.announcements__title {
  margin: 0;
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--charcoal);
}

.announcements__subtitle {
  margin: 0;
  color: #5e6c66;
  font-size: 0.95rem;
}

.announcements__subtitle strong {
  color: var(--charcoal);
  font-weight: 600;
}

.announcements__search {
  position: relative;
  display: flex;
  align-items: center;
  width: min(360px, 100%);
  background: var(--white);
  border: 1px solid rgba(14, 31, 25, 0.1);
  border-radius: 999px;
  padding: 0.55rem 0.85rem;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.announcements__search:focus-within {
  border-color: var(--dark-green);
  box-shadow: 0 0 0 4px rgba(1, 113, 81, 0.12);
}

.announcements__search-icon {
  font-size: 0.9rem;
  margin-right: 0.5rem;
  opacity: 0.6;
}

.announcements__search input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  font: inherit;
  color: var(--charcoal);
}

.announcements__search input::placeholder {
  color: #95a4a0;
}

.announcements__search-clear {
  appearance: none;
  border: 0;
  background: transparent;
  color: #95a4a0;
  font-size: 1.1rem;
  line-height: 1;
  padding: 0.15rem 0.35rem;
  cursor: pointer;
  border-radius: 999px;
}

.announcements__search-clear:hover {
  background-color: rgba(0, 0, 0, 0.05);
  color: var(--charcoal);
}

.announcements__filterbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.announcements__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.25rem 0.1rem;
}

.announcements__group-filter {
  display: inline-flex;
  align-items: center;
}

.announcements__group-select {
  appearance: none;
  -webkit-appearance: none;
  padding: 0.45rem 2rem 0.45rem 0.85rem;
  border-radius: 999px;
  border: 1px solid var(--border-light, #e0e0e0);
  background: var(--white, #ffffff);
  color: var(--charcoal, #174243);
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  background-image: linear-gradient(45deg, transparent 50%, #6c757d 50%),
                    linear-gradient(135deg, #6c757d 50%, transparent 50%);
  background-position: calc(100% - 16px) 50%, calc(100% - 11px) 50%;
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
}

.announcements__group-select:focus {
  outline: none;
  border-color: var(--dark-green, #017151);
  box-shadow: 0 0 0 3px rgba(1, 113, 81, 0.15);
}

.filter-chip {
  appearance: none;
  border: 1px solid rgba(14, 31, 25, 0.12);
  background: var(--white);
  color: var(--charcoal);
  padding: 0.45rem 0.95rem;
  border-radius: 999px;
  font-size: 0.88rem;
  font-weight: 500;
  cursor: pointer;
  transition:
    background-color 0.18s ease,
    color 0.18s ease,
    border-color 0.18s ease,
    transform 0.1s ease;
}

.filter-chip:hover {
  border-color: rgba(1, 113, 81, 0.35);
  background-color: rgba(1, 113, 81, 0.04);
}

.filter-chip--active {
  background-color: var(--dark-green);
  border-color: var(--dark-green);
  color: var(--white);
}

.filter-chip:active {
  transform: scale(0.98);
}

.announcements__list {
  display: grid;
  gap: 1.1rem;
}

.announcements__empty,
.announcements__error {
  text-align: center;
  padding: 2.5rem 1.5rem;
}

.announcements__empty h2,
.announcements__error h2 {
  margin: 0 0 0.5rem;
  color: var(--charcoal);
}

.announcements__empty p,
.announcements__error p {
  margin: 0 0 1.25rem;
  color: #6c757d;
}

.announcements__empty-icon {
  font-size: 2.2rem;
  margin-bottom: 0.5rem;
  opacity: 0.65;
}

.announcements__error {
  border-left: 4px solid var(--danger);
  text-align: left;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 720px) {
  .announcements__hero {
    flex-direction: column;
    align-items: stretch;
    padding: 1.25rem;
  }

  .announcements__search {
    width: 100%;
  }

  .announcements__title {
    font-size: 1.6rem;
  }
}
</style>
