<template>
  <FormSheet
    :model-value="open"
    :title="sheetTitle"
    :description="sheetDescription"
    width="min(100vw, 760px)"
    @update:model-value="onDismiss"
    @close="onDismiss"
  >
    <div class="admin-event-rsvps">
      <!-- Summary Counts Bar -->
      <div v-if="!loading && rsvps.length" class="admin-event-rsvps__stats">
        <div class="admin-event-rsvps__stat-pill">
          <span class="admin-event-rsvps__stat-label">Total</span>
          <span class="admin-event-rsvps__stat-val">{{ rsvps.length }}</span>
        </div>
        <div class="admin-event-rsvps__stat-pill admin-event-rsvps__stat-pill--accepted">
          <span class="admin-event-rsvps__stat-label">Going</span>
          <span class="admin-event-rsvps__stat-val">{{ countByStatus('accepted') }}</span>
        </div>
        <div class="admin-event-rsvps__stat-pill admin-event-rsvps__stat-pill--tentative">
          <span class="admin-event-rsvps__stat-label">Maybe</span>
          <span class="admin-event-rsvps__stat-val">{{ countByStatus('tentative') }}</span>
        </div>
        <div class="admin-event-rsvps__stat-pill admin-event-rsvps__stat-pill--waitlisted">
          <span class="admin-event-rsvps__stat-label">Waitlisted</span>
          <span class="admin-event-rsvps__stat-val">{{ countByStatus('waitlisted') }}</span>
        </div>
        <div class="admin-event-rsvps__stat-pill admin-event-rsvps__stat-pill--declined">
          <span class="admin-event-rsvps__stat-label">Not Going</span>
          <span class="admin-event-rsvps__stat-val">{{ countByStatus('declined') }}</span>
        </div>
      </div>

      <!-- Search & Filters -->
      <div v-if="rsvps.length > 0 || searchFilter" class="admin-event-rsvps__toolbar">
        <div class="admin-event-rsvps__search-wrap">
          <i class="fas fa-search admin-event-rsvps__search-icon" aria-hidden="true"></i>
          <input
            v-model.trim="searchFilter"
            type="search"
            class="admin-event-rsvps__search-input"
            placeholder="Search attendees by name or email..."
            aria-label="Search attendees"
          />
          <button
            v-if="searchFilter"
            type="button"
            class="admin-event-rsvps__search-clear"
            aria-label="Clear attendee search"
            @click="searchFilter = ''"
          >
            &times;
          </button>
        </div>

        <select
          v-model="statusFilter"
          class="admin-event-rsvps__status-select"
          aria-label="Filter by RSVP status"
        >
          <option value="">All statuses</option>
          <option value="accepted">Going</option>
          <option value="tentative">Maybe</option>
          <option value="waitlisted">Waitlisted</option>
          <option value="declined">Not going</option>
          <option value="pending">Pending</option>
        </select>
      </div>

      <!-- Error alert -->
      <p v-if="error" class="admin-event-rsvps__error" role="alert">
        {{ error }}
      </p>

      <!-- Loading skeleton -->
      <div v-if="loading" class="admin-event-rsvps__loading" role="status" aria-live="polite">
        <div class="admin-event-rsvps__spinner" aria-hidden="true"></div>
        <span>Loading RSVP attendee list...</span>
      </div>

      <!-- Empty state (no RSVPs or no match) -->
      <div
        v-else-if="!filteredRsvps.length"
        class="admin-event-rsvps__empty"
        role="status"
      >
        <i class="fas fa-users-slash admin-event-rsvps__empty-icon" aria-hidden="true"></i>
        <p class="admin-event-rsvps__empty-title">
          {{ searchFilter || statusFilter ? 'No matching RSVPs found' : 'No RSVPs yet' }}
        </p>
        <p class="admin-event-rsvps__empty-sub">
          {{ searchFilter || statusFilter ? 'Try clearing your search query or status filter.' : 'When students or mentors respond to this event, they will appear here.' }}
        </p>
      </div>

      <!-- RSVP Table -->
      <div v-else class="admin-event-rsvps__table-wrap">
        <table class="admin-event-rsvps__table">
          <thead>
            <tr>
              <th scope="col" class="th-sortable" @click="toggleSort('name')">
                <span>Attendee</span>
                <i :class="sortIcon('name')" aria-hidden="true"></i>
              </th>
              <th scope="col" class="th-sortable" @click="toggleSort('status')">
                <span>Status</span>
                <i :class="sortIcon('status')" aria-hidden="true"></i>
              </th>
              <th scope="col" class="th-sortable" @click="toggleSort('date')">
                <span>Responded At</span>
                <i :class="sortIcon('date')" aria-hidden="true"></i>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="rsvp in sortedRsvps" :key="rsvp.id">
              <td class="admin-event-rsvps__attendee-cell">
                <div class="admin-event-rsvps__avatar" aria-hidden="true">
                  {{ userInitials(rsvp.userId) }}
                </div>
                <div class="admin-event-rsvps__attendee-info">
                  <span class="admin-event-rsvps__name">
                    {{ userName(rsvp.userId) }}
                  </span>
                  <span class="admin-event-rsvps__email">
                    {{ userEmail(rsvp.userId) }}
                  </span>
                </div>
              </td>
              <td>
                <span
                  class="rsvp-badge"
                  :class="`rsvp-badge-${rsvp.rsvpStatus}`"
                >
                  {{ statusLabel(rsvp.rsvpStatus) }}
                </span>
              </td>
              <td class="admin-event-rsvps__date-cell">
                {{ formatDate(rsvp.respondedAt) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <template #footer>
      <button type="button" class="btn btn-outline" @click="onDismiss">
        Close
      </button>
    </template>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import type { AdminEventRsvpItem, AdminUser } from '@/utils/adminAPI'
import { fetchAdminEventRsvps, fetchAdminUsers } from '@/utils/adminAPI'
import type { BackendEvent } from '@/utils/eventsAPI'

const props = defineProps<{
  open: boolean
  event?: BackendEvent | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const loading = ref(false)
const error = ref('')
const rsvps = ref<AdminEventRsvpItem[]>([])
const searchFilter = ref('')
const statusFilter = ref('')

type SortColumn = 'name' | 'status' | 'date'
type SortDir = 'asc' | 'desc'
const sortCol = ref<SortColumn>('date')
const sortDir = ref<SortDir>('desc')

// Cache user details by ID for display
const usersMap = ref<Map<number, AdminUser>>(new Map())

const eventName = computed(() => {
  if (!props.event) return 'Event'
  const raw = props.event as any
  return raw.event_name || raw.eventName || `Event #${props.event.id}`
})

const sheetTitle = computed(() => `RSVPs: ${eventName.value}`)

const sheetDescription = computed(() => {
  if (!props.event?.id) return ''
  const count = rsvps.value.length
  return `Event #${props.event.id} · ${count} ${count === 1 ? 'response' : 'responses'}`
})

const onDismiss = () => {
  emit('close')
}

const countByStatus = (status: string) => {
  return rsvps.value.filter((r) => r.rsvpStatus === status).length
}

const statusLabel = (status: string) => {
  switch (status) {
    case 'accepted':
      return 'Going'
    case 'tentative':
      return 'Maybe'
    case 'declined':
      return 'Not going'
    case 'waitlisted':
      return 'Waitlisted'
    case 'pending':
      return 'Pending'
    default:
      return status
  }
}

const loadData = async (eventId: number) => {
  loading.value = true
  error.value = ''
  searchFilter.value = ''
  statusFilter.value = ''

  try {
    const [rsvpData, usersData] = await Promise.all([
      fetchAdminEventRsvps(eventId),
      usersMap.value.size === 0 ? fetchAdminUsers({ limit: 200 }) : Promise.resolve(null)
    ])

    rsvps.value = rsvpData

    if (usersData?.items) {
      const nextMap = new Map(usersMap.value)
      for (const u of usersData.items) {
        nextMap.set(u.id, u)
      }
      usersMap.value = nextMap
    }
  } catch (err: any) {
    console.error('Failed to load event RSVPs:', err)
    error.value = err?.message || 'Failed to load RSVPs for this event.'
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.event?.id] as const,
  ([isOpen, eventId]) => {
    if (isOpen && eventId) {
      void loadData(Number(eventId))
    }
  }
)

const userName = (userId: number) => {
  const u = usersMap.value.get(userId)
  if (u) {
    const name = `${u.firstName || ''} ${u.lastName || ''}`.trim()
    return name || u.email || `User #${userId}`
  }
  return `User #${userId}`
}

const userEmail = (userId: number) => {
  const u = usersMap.value.get(userId)
  return u?.email || ''
}

const userInitials = (userId: number) => {
  const u = usersMap.value.get(userId)
  if (u) {
    const first = (u.firstName || '')[0] || ''
    const last = (u.lastName || '')[0] || ''
    const res = (first + last).toUpperCase()
    if (res) return res
    if (u.email) return u.email[0].toUpperCase()
  }
  return 'U'
}

const formatDate = (isoStr?: string | null) => {
  if (!isoStr) return '—'
  try {
    return new Intl.DateTimeFormat('en-AU', {
      dateStyle: 'medium',
      timeStyle: 'short'
    }).format(new Date(isoStr))
  } catch {
    return isoStr
  }
}

const toggleSort = (col: SortColumn) => {
  if (sortCol.value === col) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortCol.value = col
    sortDir.value = col === 'date' ? 'desc' : 'asc'
  }
}

const sortIcon = (col: SortColumn) => {
  if (sortCol.value !== col) return 'fas fa-sort sort-neutral'
  return sortDir.value === 'asc' ? 'fas fa-sort-up sort-active' : 'fas fa-sort-down sort-active'
}

const filteredRsvps = computed(() => {
  let list = rsvps.value

  if (statusFilter.value) {
    list = list.filter((r) => r.rsvpStatus === statusFilter.value)
  }

  if (searchFilter.value) {
    const q = searchFilter.value.toLowerCase()
    list = list.filter((r) => {
      const name = userName(r.userId).toLowerCase()
      const email = userEmail(r.userId).toLowerCase()
      return name.includes(q) || email.includes(q) || String(r.userId).includes(q)
    })
  }

  return list
})

const sortedRsvps = computed(() => {
  const list = [...filteredRsvps.value]
  const dir = sortDir.value === 'asc' ? 1 : -1

  list.sort((a, b) => {
    if (sortCol.value === 'name') {
      return dir * userName(a.userId).localeCompare(userName(b.userId))
    }
    if (sortCol.value === 'status') {
      return dir * (a.rsvpStatus || '').localeCompare(b.rsvpStatus || '')
    }
    if (sortCol.value === 'date') {
      const dateA = a.respondedAt ? new Date(a.respondedAt).getTime() : 0
      const dateB = b.respondedAt ? new Date(b.respondedAt).getTime() : 0
      return dir * (dateA - dateB)
    }
    return 0
  })

  return list
})
</script>

<style scoped>
.admin-event-rsvps {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.admin-event-rsvps__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.admin-event-rsvps__stat-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.65rem;
  border-radius: 999px;
  background-color: var(--bg-light);
  border: 1px solid var(--border-light);
  font-size: 0.8rem;
}

.admin-event-rsvps__stat-label {
  color: var(--text-muted);
  font-weight: 600;
}

.admin-event-rsvps__stat-val {
  font-weight: 700;
  color: var(--charcoal);
}

.admin-event-rsvps__stat-pill--accepted {
  background-color: rgba(1, 113, 81, 0.08);
  border-color: rgba(1, 113, 81, 0.25);
}
.admin-event-rsvps__stat-pill--accepted .admin-event-rsvps__stat-val {
  color: var(--dark-green);
}

.admin-event-rsvps__stat-pill--tentative {
  background-color: rgba(241, 229, 166, 0.4);
  border-color: rgba(180, 150, 50, 0.3);
}

.admin-event-rsvps__stat-pill--waitlisted {
  background-color: rgba(57, 104, 123, 0.1);
  border-color: rgba(57, 104, 123, 0.25);
}
.admin-event-rsvps__stat-pill--waitlisted .admin-event-rsvps__stat-val {
  color: #39687b;
}

.admin-event-rsvps__stat-pill--declined {
  background-color: rgba(220, 53, 69, 0.06);
  border-color: rgba(220, 53, 69, 0.2);
}
.admin-event-rsvps__stat-pill--declined .admin-event-rsvps__stat-val {
  color: var(--danger);
}

.admin-event-rsvps__toolbar {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.admin-event-rsvps__search-wrap {
  position: relative;
  flex: 1;
  min-width: 220px;
  display: flex;
  align-items: center;
}

.admin-event-rsvps__search-icon {
  position: absolute;
  left: 0.75rem;
  color: var(--text-muted);
  font-size: 0.85rem;
  pointer-events: none;
}

.admin-event-rsvps__search-input {
  width: 100%;
  padding: 0.5rem 2rem 0.5rem 2.2rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
  font-size: 0.875rem;
}

.admin-event-rsvps__search-input:focus {
  outline: none;
  border-color: var(--dark-green);
  box-shadow: 0 0 0 3px rgba(1, 113, 81, 0.15);
}

.admin-event-rsvps__search-clear {
  position: absolute;
  right: 0.5rem;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.1rem 0.3rem;
  border-radius: 999px;
}

.admin-event-rsvps__status-select {
  padding: 0.5rem 1.8rem 0.5rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
  font-size: 0.875rem;
  appearance: none;
  -webkit-appearance: none;
  background-image: linear-gradient(45deg, transparent 50%, var(--text-muted) 50%),
                    linear-gradient(135deg, var(--text-muted) 50%, transparent 50%);
  background-position: calc(100% - 15px) 50%, calc(100% - 10px) 50%;
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
  cursor: pointer;
}

.admin-event-rsvps__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3rem 1rem;
  color: var(--text-muted);
  font-size: 0.95rem;
}

.admin-event-rsvps__spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border-light);
  border-top-color: var(--dark-green);
  border-radius: 50%;
  animation: admin-spin 0.8s linear infinite;
}

.admin-event-rsvps__empty {
  text-align: center;
  padding: 3rem 1.5rem;
  color: var(--text-muted);
}

.admin-event-rsvps__empty-icon {
  font-size: 2.5rem;
  color: var(--border-light);
  margin-bottom: 0.75rem;
}

.admin-event-rsvps__empty-title {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--charcoal);
  margin: 0 0 0.25rem;
}

.admin-event-rsvps__empty-sub {
  font-size: 0.875rem;
  margin: 0;
}

.admin-event-rsvps__table-wrap {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  overflow: hidden;
}

.admin-event-rsvps__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.admin-event-rsvps__table th {
  background-color: var(--bg-light);
  padding: 0.65rem 0.9rem;
  text-align: left;
  font-weight: 600;
  color: var(--text-muted);
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--border-light);
  user-select: none;
}

.th-sortable {
  cursor: pointer;
}

.th-sortable:hover {
  color: var(--charcoal);
}

.sort-neutral {
  margin-left: 0.35rem;
  color: #ccc;
  font-size: 0.75rem;
}

.sort-active {
  margin-left: 0.35rem;
  color: var(--dark-green);
  font-size: 0.75rem;
}

.admin-event-rsvps__table td {
  padding: 0.75rem 0.9rem;
  border-bottom: 1px solid var(--border-light);
  vertical-align: middle;
}

.admin-event-rsvps__table tr:last-child td {
  border-bottom: none;
}

.admin-event-rsvps__table tr:hover td {
  background-color: rgba(1, 113, 81, 0.02);
}

.admin-event-rsvps__attendee-cell {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.admin-event-rsvps__avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background-color: var(--light-green);
  color: var(--dark-green);
  font-weight: 700;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.admin-event-rsvps__attendee-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.admin-event-rsvps__name {
  font-weight: 600;
  color: var(--charcoal);
}

.admin-event-rsvps__email {
  font-size: 0.78rem;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-event-rsvps__date-cell {
  color: var(--text-muted);
  font-size: 0.82rem;
  white-space: nowrap;
}

.admin-event-rsvps__error {
  margin: 0;
  padding: 0.65rem 0.85rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.875rem;
}

/* Status Badges */
.rsvp-badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: capitalize;
}

.rsvp-badge-accepted {
  background: var(--light-green);
  color: var(--dark-green);
}

.rsvp-badge-tentative {
  background: var(--warning, #f1e5a6);
  color: var(--charcoal);
}

.rsvp-badge-waitlisted {
  background: rgba(57, 104, 123, 0.15);
  color: #39687b;
}

.rsvp-badge-declined {
  background: var(--bg-light);
  color: var(--text-muted);
}

.rsvp-badge-pending {
  background: #f0e6f6;
  color: #6a329f;
}

@keyframes admin-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
