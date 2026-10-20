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

        <AppSelect
          v-model="statusFilter"
          class="admin-event-rsvps__status-select"
          aria-label="Filter by RSVP status"
          :options="STATUS_OPTIONS"
        />
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
      <AppSimpleTable v-else :columns="rsvpColumns" :rows="rsvpRows">
        <template #cell-user="{ row }">
          <div class="admin-event-rsvps__attendee">
            <div class="admin-event-rsvps__avatar" aria-hidden="true">{{ row.initials }}</div>
            <div class="admin-event-rsvps__attendee-info">
              <span class="admin-event-rsvps__name">
                {{ row.name }}
                <span
                  v-if="row.noMediaConsent"
                  class="admin-event-rsvps__media-flag"
                  title="Their guardian didn't give media consent, which in-person events require."
                  data-test="rsvp-no-media-consent"
                >
                  No media consent
                </span>
              </span>
              <span class="admin-event-rsvps__email">{{ row.email }}</span>
            </div>
          </div>
        </template>
        <template #cell-status="{ row }">
          <span class="rsvp-badge" :class="`rsvp-badge-${row.status}`">{{ row.statusLabel }}</span>
        </template>
        <template #cell-respondedAt="{ value }">
          <span class="admin-event-rsvps__date">{{ value }}</span>
        </template>
      </AppSimpleTable>
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
import AppSelect, { type AppSelectOption } from '@/components/AppSelect.vue'
import AppSimpleTable, { type SimpleTableColumn } from '@/components/AppSimpleTable.vue'
import type { AdminEventRsvpItem, AdminUser } from '@/utils/adminAPI'
import { fetchAdminEventRsvps, fetchAdminUsers, fetchAdminUser } from '@/utils/adminAPI'
import { formatShortDateTime } from '@/utils/date'
import { roleLabel } from '@/utils/userFormat'
import type { BackendEvent } from '@/utils/eventsAPI'

const STATUS_OPTIONS: AppSelectOption[] = [
  { value: '', label: 'All statuses' },
  { value: 'accepted', label: 'Going' },
  { value: 'tentative', label: 'Maybe' },
  { value: 'waitlisted', label: 'Waitlisted' },
  { value: 'declined', label: 'Not going' },
  { value: 'pending', label: 'Pending' }
]

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

    rsvps.value = rsvpData || []

    if (usersData?.items) {
      const nextMap = new Map(usersMap.value)
      for (const u of usersData.items) {
        nextMap.set(u.id, u)
      }
      usersMap.value = nextMap
    }

    // Resolve any remaining attendees whose names were not populated in rsvpData and are missing from usersMap
    const unresolvedUserIds = [
      ...new Set(
        rsvps.value
          .filter((r) => (!r.userName || r.userName.startsWith('User #')) && !usersMap.value.has(r.userId))
          .map((r) => r.userId)
      )
    ]

    if (unresolvedUserIds.length > 0) {
      const userResults = await Promise.allSettled(
        unresolvedUserIds.map((uid) => fetchAdminUser(uid))
      )
      const nextMap = new Map(usersMap.value)
      userResults.forEach((res) => {
        if (res.status === 'fulfilled' && res.value?.id) {
          nextMap.set(res.value.id, res.value)
        }
      })
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

const userName = (target: AdminEventRsvpItem | number) => {
  if (typeof target === 'object' && target) {
    if (target.userName && !target.userName.startsWith('User #')) {
      return target.userName
    }
    const u = usersMap.value.get(target.userId)
    if (u) {
      const name = `${u.firstName || ''} ${u.lastName || ''}`.trim()
      return name || u.email || `User #${target.userId}`
    }
    return target.userName || `User #${target.userId}`
  }
  const u = usersMap.value.get(target)
  if (u) {
    const name = `${u.firstName || ''} ${u.lastName || ''}`.trim()
    return name || u.email || `User #${target}`
  }
  return `User #${target}`
}

const userEmail = (target: AdminEventRsvpItem | number) => {
  if (typeof target === 'object' && target) {
    if (target.userEmail) return target.userEmail
    const u = usersMap.value.get(target.userId)
    return u?.email || ''
  }
  const u = usersMap.value.get(target)
  return u?.email || ''
}

const userRole = (target: AdminEventRsvpItem | number): string => {
  if (typeof target === 'object' && target) {
    if (target.userRole) return target.userRole
    const u = usersMap.value.get(target.userId)
    if (u?.role) return u.role
    if (u?.isAdmin) return 'admin'
    return 'student'
  }
  const u = usersMap.value.get(target)
  if (u?.role) return u.role
  if (u?.isAdmin) return 'admin'
  return 'student'
}

const userInitials = (target: AdminEventRsvpItem | number) => {
  const name = userName(target)
  if (name && !name.startsWith('User #')) {
    const parts = name.split(/\s+/).filter(Boolean)
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    }
    return name.slice(0, 2).toUpperCase()
  }
  const email = userEmail(target)
  if (email) return email.slice(0, 2).toUpperCase()
  return 'U'
}

const filteredRsvps = computed(() => {
  let list = rsvps.value

  if (statusFilter.value) {
    list = list.filter((r) => r.rsvpStatus === statusFilter.value)
  }

  if (searchFilter.value) {
    const q = searchFilter.value.toLowerCase()
    list = list.filter((r) => {
      const name = userName(r).toLowerCase()
      const email = userEmail(r).toLowerCase()
      const role = userRole(r).toLowerCase()
      return name.includes(q) || email.includes(q) || role.includes(q) || String(r.userId).includes(q)
    })
  }

  return list
})

// Newest response first.
const sortedRsvps = computed(() =>
  [...filteredRsvps.value].sort((a, b) => {
    const dateA = a.respondedAt ? new Date(a.respondedAt).getTime() : 0
    const dateB = b.respondedAt ? new Date(b.respondedAt).getTime() : 0
    return dateB - dateA
  })
)

const rsvpColumns: SimpleTableColumn[] = [
  { key: 'user', label: 'User' },
  { key: 'role', label: 'User Type' },
  { key: 'status', label: 'Status' },
  { key: 'respondedAt', label: 'Responded At' },
]

// What each row shows, worked out once for the table.
const rsvpRows = computed(() =>
  sortedRsvps.value.map((rsvp) => ({
    id: rsvp.id,
    initials: userInitials(rsvp),
    name: userName(rsvp),
    email: userEmail(rsvp),
    noMediaConsent: rsvp.noMediaConsent,
    role: roleLabel(userRole(rsvp)),
    status: rsvp.rsvpStatus,
    statusLabel: statusLabel(rsvp.rsvpStatus),
    respondedAt: rsvp.respondedAt ? formatShortDateTime(rsvp.respondedAt) : '—',
  }))
)
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
  color: var(--teal);
}

.admin-event-rsvps__stat-pill--accepted {
  background-color: rgba(1, 113, 81, 0.08);
  border-color: rgba(1, 113, 81, 0.25);
}
.admin-event-rsvps__stat-pill--accepted .admin-event-rsvps__stat-val {
  color: var(--dark-green);
}

.admin-event-rsvps__stat-pill--tentative {
  background-color: rgba(243, 230, 157, 0.4);
  border-color: rgba(180, 150, 50, 0.3);
}

.admin-event-rsvps__stat-pill--waitlisted {
  background-color: rgba(38, 105, 125, 0.1);
  border-color: rgba(38, 105, 125, 0.25);
}
.admin-event-rsvps__stat-pill--waitlisted .admin-event-rsvps__stat-val {
  color: #26697d;
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
  color: var(--teal);
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
  padding: 0.5rem 0.6rem 0.5rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  color: var(--teal);
  font-size: 0.875rem;
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
  color: var(--teal);
  margin: 0 0 0.25rem;
}

.admin-event-rsvps__empty-sub {
  font-size: 0.875rem;
  margin: 0;
}

/* Avatar beside the name, email under the name. */
.admin-event-rsvps__attendee {
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
  color: var(--teal);
}

.admin-event-rsvps__email {
  font-size: 0.78rem;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-event-rsvps__date {
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
  background: var(--warning, #f3e69d);
  color: var(--teal);
}

.rsvp-badge-waitlisted {
  background: rgba(38, 105, 125, 0.15);
  color: #26697d;
}

.rsvp-badge-declined {
  background: var(--bg-light);
  color: var(--text-muted);
}

.rsvp-badge-pending {
  background: #f0e6f6;
  color: #6a329f;
}

.admin-event-rsvps__media-flag {
  display: inline-block;
  margin-left: 0.4rem;
  padding: 0.1rem 0.45rem;
  border: 1px solid var(--danger);
  border-radius: 999px;
  color: var(--danger);
  font-size: 0.7rem;
  font-weight: 700;
  vertical-align: middle;
  white-space: nowrap;
}

@keyframes admin-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
