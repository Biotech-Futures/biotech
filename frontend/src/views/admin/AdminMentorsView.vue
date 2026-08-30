<template>
  <div class="admin-mentors">
    <!-- Header -->
    <div class="admin-mentors__header">
      <p class="admin-mentors__count">
        {{ mentors.length }} mentor{{ mentors.length === 1 ? '' : 's' }} registered
      </p>
      <div class="admin-mentors__header-actions">
        <button type="button" class="btn btn-sm btn-outline" title="CSV import coming soon">
          <i class="fas fa-file-arrow-up" aria-hidden="true"></i>
          Import Mentors CSV
        </button>
        <div class="admin-mentors__inactive-days">
          <label for="inactive-days-input" class="admin-mentors__inactive-label">Inactive after</label>
          <input
            id="inactive-days-input"
            type="number"
            min="1"
            :value="inactiveDays"
            class="admin-mentors__inactive-input"
            @change="onInactiveDaysChange"
          />
          <span class="admin-mentors__inactive-label">days</span>
        </div>
        <button
          v-if="inactiveGroups.length > 0"
          type="button"
          class="btn btn-sm btn-outline"
          @click="replaceDialogOpen = true"
        >
          <i class="fas fa-sync-alt" aria-hidden="true"></i>
          Replace Inactive Mentors
          <span class="admin-mentors__badge">{{ inactiveGroups.length }}</span>
        </button>
      </div>
    </div>

    <p v-if="error" class="admin-mentors__error" role="alert">{{ error }}</p>

    <!-- Bulk actions -->
    <BulkActionsBar
      v-if="selectedIds.size > 0"
      :count="selectedIds.size"
      noun="mentor"
      :disabled="statusBusy"
      @clear="selectedIds = new Set()"
    >
      <button type="button" class="btn btn-sm btn-outline" :disabled="statusBusy" @click="openBulk('activate')">
        Activate
      </button>
      <button type="button" class="btn btn-sm btn-outline" :disabled="statusBusy" @click="openBulk('deactivate')">
        Deactivate
      </button>
    </BulkActionsBar>

    <!-- Table -->
    <div
      class="admin-mentors__card"
      :class="{ 'admin-mentors__card--loading': loading && mentors.length > 0 }"
    >
      <template v-if="loading && mentors.length === 0">
        <div class="admin-mentors__state">
          <span class="admin-mentors__spinner" aria-hidden="true"></span>
          <span>Loading mentors...</span>
        </div>
      </template>

      <template v-else-if="sortedMentors.length === 0">
        <div class="admin-mentors__state admin-mentors__state--empty">
          No mentors registered yet.
        </div>
      </template>

      <div v-else class="admin-mentors__scroll">
        <table class="admin-mentors__table">
          <thead>
            <tr>
              <th class="admin-mentors__check">
                <input
                  type="checkbox"
                  :checked="headerChecked === true"
                  :indeterminate.prop="headerChecked === 'indeterminate'"
                  aria-label="Select all mentors"
                  :disabled="loading || mentors.length === 0"
                  @change="toggleAll"
                />
              </th>
              <th class="admin-mentors__expand" aria-hidden="true"></th>
              <th class="admin-mentors__head">
                <button type="button" class="admin-mentors__sort" :class="sortClass('name')" @click="setSort('name')">
                  Name
                </button>
              </th>
              <th class="admin-mentors__head">
                <button type="button" class="admin-mentors__sort" :class="sortClass('country')" @click="setSort('country')">
                  Country
                </button>
              </th>
              <th class="admin-mentors__head">
                <button type="button" class="admin-mentors__sort" :class="sortClass('institution')" @click="setSort('institution')">
                  Institution
                </button>
              </th>
              <th class="admin-mentors__head">
                <button type="button" class="admin-mentors__sort" :class="sortClass('capacity')" @click="setSort('capacity')">
                  Capacity
                </button>
              </th>
              <th class="admin-mentors__head">
                <button type="button" class="admin-mentors__sort" :class="sortClass('lastMessage')" @click="setSort('lastMessage')">
                  Last Message
                </button>
              </th>
              <th class="admin-mentors__head">
                <button type="button" class="admin-mentors__sort" :class="sortClass('status')" @click="setSort('status')">
                  Status
                </button>
              </th>
              <th class="admin-mentors__head">Logged In</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="mentor in sortedMentors" :key="mentor.mentorId">
              <tr
                class="admin-mentors__row"
                :class="{
                  'admin-mentors__row--inactive': isEffectivelyInactive(mentor, inactiveDays),
                  'admin-mentors__row--selected': selectedIds.has(mentor.mentorId)
                }"
                @click="toggleExpand(mentor.mentorId)"
              >
                <td class="admin-mentors__check" @click.stop>
                  <input
                    type="checkbox"
                    :checked="selectedIds.has(mentor.mentorId)"
                    :aria-label="`Select ${mentor.name}`"
                    :disabled="loading"
                    @change="toggleOne(mentor.mentorId)"
                  />
                </td>
                <td class="admin-mentors__expand">
                  <button
                    type="button"
                    class="admin-mentors__chevron"
                    :aria-expanded="expandedIds.has(mentor.mentorId)"
                    :aria-label="expandedIds.has(mentor.mentorId) ? `Collapse ${mentor.name}` : `Expand ${mentor.name}`"
                    @click.stop="toggleExpand(mentor.mentorId)"
                  >
                    <i class="fas" :class="expandedIds.has(mentor.mentorId) ? 'fa-chevron-down' : 'fa-chevron-right'" aria-hidden="true"></i>
                  </button>
                </td>
                <td>
                  <p class="admin-mentors__name">{{ mentor.name }}</p>
                  <p class="admin-mentors__sub">{{ mentor.email }}</p>
                </td>
                <td>
                  <span class="admin-mentors__pill">{{ mentor.countryName ?? 'Unknown' }}</span>
                </td>
                <td class="admin-mentors__muted">{{ mentor.institution ?? '—' }}</td>
                <td>
                  {{ mentor.currentAssignedCount }}/{{ mentor.maxGroupCount }}
                  <span class="admin-mentors__sub">({{ mentor.remainingCapacity }} left)</span>
                </td>
                <td class="admin-mentors__muted">
                  <span v-if="mentor.lastMessageAt" :class="{ 'admin-mentors__danger': lastMessageDays(mentor.lastMessageAt) >= inactiveDays }">
                    {{ relativeDays(mentor.lastMessageAt) }}
                  </span>
                  <span v-else class="admin-mentors__never">
                    <i class="fas fa-comment-slash" aria-hidden="true"></i>
                    Never
                  </span>
                </td>
                <td @click.stop>
                  <div class="admin-mentors__status-cell">
                    <span v-if="mentor.isActive" class="admin-mentors__active-badge">
                      <i class="fas fa-check-circle" aria-hidden="true"></i>
                      Active
                    </span>
                    <span v-else class="admin-mentors__danger">
                      <i class="fas fa-exclamation-triangle" aria-hidden="true"></i>
                      Inactive
                    </span>
                    <button type="button" class="btn btn-sm btn-outline" :disabled="statusBusy" @click="toggleActive(mentor)">
                      {{ mentor.isActive ? 'Deactivate' : 'Activate' }}
                    </button>
                  </div>
                </td>
                <td class="admin-mentors__muted">
                  <span v-if="mentor.hasLoggedIn" class="admin-mentors__logged-in">
                    <span class="admin-mentors__pill admin-mentors__pill--green">Yes</span>
                    <span v-if="mentor.lastLogin" class="admin-mentors__sub" :title="formatLogin(mentor.lastLogin)">
                      {{ loginDate(mentor.lastLogin) }}
                    </span>
                  </span>
                  <span v-else class="admin-mentors__pill">No</span>
                </td>
              </tr>

              <tr v-if="expandedIds.has(mentor.mentorId)" key="detail" class="admin-mentors__detail-row">
                <td :colspan="9" class="admin-mentors__detail">
                  <div class="admin-mentors__detail-grid">
                    <!-- Account info -->
                    <section>
                      <p class="admin-mentors__section-title">Account Info</p>
                      <dl class="admin-mentors__detail-list">
                        <div><dt>User ID:</dt><dd class="admin-mentors__mono">{{ mentor.mentorId }}</dd></div>
                        <div><dt>Email:</dt><dd>{{ mentor.email }}</dd></div>
                        <div><dt>Institution:</dt><dd>{{ mentor.institution ?? '—' }}</dd></div>
                        <div><dt>Max Groups:</dt><dd>{{ mentor.maxGroupCount }}</dd></div>
                        <div><dt>Logged In:</dt><dd>{{ mentor.hasLoggedIn ? `Yes${mentor.lastLogin ? ` (${formatLogin(mentor.lastLogin)})` : ''}` : 'No (Never logged in)' }}</dd></div>
                      </dl>
                    </section>

                    <!-- Interests -->
                    <section>
                      <p class="admin-mentors__section-title">Interests</p>
                      <div v-if="mentor.interests.length" class="admin-mentors__chips">
                        <span v-for="interest in mentor.interests" :key="interest" class="admin-mentors__chip">{{ interest }}</span>
                      </div>
                      <p v-else class="admin-mentors__muted">No interests listed.</p>
                    </section>

                    <!-- Availability -->
                    <section>
                      <p class="admin-mentors__section-title">
                        <i class="fas fa-clock" aria-hidden="true"></i>
                        Availability
                      </p>
                      <div v-if="mentor.availability.length" class="admin-mentors__chips">
                        <span
                          v-for="(slot, index) in sortedAvailability(mentor.availability)"
                          :key="index"
                          class="admin-mentors__availability-slot"
                        >
                          <span class="admin-mentors__slot-day">{{ WEEKDAYS[slot.weekday] }}</span>
                          <span class="admin-mentors__muted">{{ slot.startTime.slice(0, 5) }}–{{ slot.endTime.slice(0, 5) }}</span>
                        </span>
                      </div>
                      <p v-else class="admin-mentors__muted">No availability set.</p>
                    </section>

                    <!-- Certificates -->
                    <section>
                      <p class="admin-mentors__section-title">
                        <i class="fas fa-shield-alt" aria-hidden="true"></i>
                        Certificates
                      </p>
                      <div v-if="mentor.certificates.length" class="admin-mentors__certificates">
                        <div v-for="(cert, index) in mentor.certificates" :key="index" class="admin-mentors__cert">
                          <div>
                            <span class="admin-mentors__cert-name">{{ cert.certificateTypeName }}</span>
                            <span v-if="cert.verifiedAt" class="admin-mentors__verified">
                              <i class="fas fa-shield-alt" aria-hidden="true"></i>
                              Verified
                            </span>
                            <span v-else class="admin-mentors__muted">Unverified</span>
                          </div>
                          <div class="admin-mentors__sub">
                            <template v-if="cert.certificateNumber">No. {{ cert.certificateNumber }}</template>
                            <template v-if="cert.issuedBy">Issued by: {{ cert.issuedBy }}</template>
                            <span>Issued: {{ cert.issuedAt }}</span>
                            <span v-if="cert.expiresAt">Expires: {{ cert.expiresAt }}</span>
                          </div>
                          <a
                            v-if="cert.fileUrl"
                            :href="cert.fileUrl"
                            target="_blank"
                            rel="noopener noreferrer"
                            class="admin-mentors__link"
                          >
                            View file
                          </a>
                        </div>
                      </div>
                      <p v-else class="admin-mentors__muted">No certificates on file.</p>
                    </section>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Bulk status confirm -->
    <ConfirmDialog
      v-model="bulkAction.open"
      :title="bulkTitle"
      :message="bulkMessage"
      :confirm-label="bulkAction.action === 'activate' ? 'Activate' : 'Deactivate'"
      :variant="bulkAction.action === 'activate' ? 'default' : 'warning'"
      :busy="statusBusy"
      @confirm="runBulkStatus"
    />

    <!-- Replace inactive mentors -->
    <MentorReplaceDialog
      v-model:open="replaceDialogOpen"
      :inactive-groups="inactiveGroups"
      :mentors="mentorList"
      @confirmed="onReplaceConfirmed"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import BulkActionsBar from '@/components/admin/BulkActionsBar.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import MentorReplaceDialog from '@/components/admin/MentorReplaceDialog.vue'
import {
  type AdminMentorAvailability,
  type AdminMentorDetail,
  type MatchedGroup,
  type MentorListItem,
  bulkSetUsersActive,
  fetchAdminMentorDetails,
  fetchMatchedGroups,
  fetchMentorMatchMentorList,
  setAdminMentorActive
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

type MentorSortKey = 'name' | 'country' | 'institution' | 'capacity' | 'lastMessage' | 'status'
type SortDirection = 'asc' | 'desc'

const loading = ref(true)
const statusBusy = ref(false)
const error = ref('')

const mentors = ref<AdminMentorDetail[]>([])
const matchedGroups = ref<MatchedGroup[]>([])
const mentorList = ref<MentorListItem[]>([])

const inactiveDays = ref(30)
const expandedIds = ref<Set<number>>(new Set())
const selectedIds = ref<Set<number>>(new Set())
const bulkAction = reactive<{ open: boolean; action: 'activate' | 'deactivate'; count: number }>({
  open: false,
  action: 'activate',
  count: 0
})
const replaceDialogOpen = ref(false)

const sortState = ref<{ key: MentorSortKey; direction: SortDirection }>({
  key: 'name',
  direction: 'asc'
})

// -- Inactive helpers -------------------------------------------------------

function daysSince(dateStr: string | null): number | null {
  if (!dateStr) return null
  const diff = Date.now() - new Date(dateStr).getTime()
  return Math.floor(diff / (1000 * 60 * 60 * 24))
}

function isEffectivelyInactive(mentor: AdminMentorDetail, inactiveDaysValue: number): boolean {
  if (!mentor.isActive) return true
  const days = daysSince(mentor.lastMessageAt)
  if (days === null) return true // never sent a message
  return days >= inactiveDaysValue
}

function lastMessageDays(dateStr: string): number {
  return daysSince(dateStr) ?? 0
}

function relativeDays(dateStr: string): string {
  const days = daysSince(dateStr) ?? 0
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  return `${days} days ago`
}

function formatLogin(dateStr: string): string {
  return new Date(dateStr).toLocaleString()
}

function loginDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString()
}

// Groups whose current mentor is effectively inactive.
const inactiveGroups = computed(() => {
  const inactiveMentorIds = new Set(
    mentors.value
      .filter((m) => isEffectivelyInactive(m, inactiveDays.value))
      .map((m) => m.mentorId)
  )
  return matchedGroups.value.filter((group) => inactiveMentorIds.has(group.mentor.mentorId))
})

// -- Data loading -----------------------------------------------------------

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const [detailData, matchedData] = await Promise.all([
      fetchAdminMentorDetails(),
      fetchMatchedGroups()
    ])
    mentors.value = detailData
    matchedGroups.value = matchedData
    loadMentorPool()
  } catch (loadError) {
    logApiError('admin.mentors.load', loadError)
    error.value = loadError instanceof Error ? loadError.message : 'Unable to load mentors.'
    mentors.value = []
    matchedGroups.value = []
    mentorList.value = []
  } finally {
    loading.value = false
  }
}

// The replacement pool is only needed when the replace dialog opens; don't fail
// the whole tab if it's unavailable.
const loadMentorPool = async () => {
  try {
    mentorList.value = await fetchMentorMatchMentorList()
  } catch (poolError) {
    logApiError('admin.mentors.list', poolError)
    mentorList.value = []
  }
}

// -- Sorting (client-side, matches adminweb) --------------------------------

const getSortValue = (mentor: AdminMentorDetail, key: MentorSortKey): string | number => {
  switch (key) {
    case 'name':
      return `${mentor.name} ${mentor.email ?? ''}`
    case 'country':
      return mentor.countryName ?? ''
    case 'institution':
      return mentor.institution ?? ''
    case 'capacity':
      return mentor.remainingCapacity
    case 'lastMessage':
      return mentor.lastMessageAt ?? ''
    case 'status':
      return isEffectivelyInactive(mentor, inactiveDays.value) ? 'Inactive' : 'Active'
  }
}

const sortedMentors = computed(() => {
  const direction = sortState.value.direction === 'asc' ? 1 : -1
  const comparators: Record<MentorSortKey, (a: AdminMentorDetail, b: AdminMentorDetail) => number> = {
    name: (a, b) => `${a.name} ${a.email ?? ''}`.localeCompare(`${b.name} ${b.email ?? ''}`),
    country: (a, b) => (a.countryName ?? '').localeCompare(b.countryName ?? ''),
    institution: (a, b) => (a.institution ?? '').localeCompare(b.institution ?? ''),
    capacity: (a, b) => a.remainingCapacity - b.remainingCapacity,
    lastMessage: (a, b) => getSortValue(a, 'lastMessage').toString().localeCompare(getSortValue(b, 'lastMessage').toString()),
    status: (a, b) => getSortValue(a, 'status').toString().localeCompare(getSortValue(b, 'status').toString())
  }
  return [...mentors.value].sort((a, b) => comparators[sortState.value.key](a, b) * direction)
})

const sortClass = (key: MentorSortKey) => ({
  'admin-mentors__sort--active': sortState.value.key === key
})

const setSort = (key: MentorSortKey) => {
  if (sortState.value.key !== key) {
    sortState.value = { key, direction: 'asc' }
  } else {
    sortState.value = {
      key,
      direction: sortState.value.direction === 'asc' ? 'desc' : 'asc'
    }
  }
}

// -- Expand / select --------------------------------------------------------

const toggleExpand = (mentorId: number) => {
  const next = new Set(expandedIds.value)
  if (next.has(mentorId)) next.delete(mentorId)
  else next.add(mentorId)
  expandedIds.value = next
}

const headerChecked = computed<boolean | 'indeterminate'>(() => {
  if (selectedIds.value.size === 0) return false
  const all = mentors.value.map((m) => m.mentorId)
  return all.length > 0 && all.every((id) => selectedIds.value.has(id)) ? true : 'indeterminate'
})

const toggleAll = () => {
  const all = mentors.value.map((m) => m.mentorId)
  const next = new Set(selectedIds.value)
  if (all.length > 0 && all.every((id) => next.has(id))) {
    all.forEach((id) => next.delete(id))
  } else {
    all.forEach((id) => next.add(id))
  }
  selectedIds.value = next
}

const toggleOne = (mentorId: number) => {
  const next = new Set(selectedIds.value)
  if (next.has(mentorId)) next.delete(mentorId)
  else next.add(mentorId)
  selectedIds.value = next
}

// -- Status ---------------------------------------------------------

const onInactiveDaysChange = (event: Event) => {
  const value = Number((event.target as HTMLInputElement).value)
  inactiveDays.value = Math.max(1, Number.isFinite(value) ? value : 1)
}

const toggleActive = async (mentor: AdminMentorDetail) => {
  statusBusy.value = true
  error.value = ''
  try {
    await setAdminMentorActive(mentor.mentorId, !mentor.isActive)
    await load()
  } catch (toggleError) {
    logApiError('admin.mentors.toggle', toggleError)
    error.value =
      toggleError instanceof Error
        ? toggleError.message
        : 'Unable to update the mentor status.'
  } finally {
    statusBusy.value = false
  }
}

const openBulk = (action: 'activate' | 'deactivate') => {
  bulkAction.action = action
  bulkAction.count = selectedIds.value.size
  bulkAction.open = true
}

const bulkTitle = computed(() => {
  const count = bulkAction.count
  return `${bulkAction.action === 'activate' ? 'Activate' : 'Deactivate'} ${count} ${count === 1 ? 'mentor' : 'mentors'}?`
})

const bulkMessage = computed(() =>
  bulkAction.action === 'activate'
    ? 'The selected mentors will be able to sign in again.'
    : 'The selected mentors will no longer be able to sign in. You can reactivate them at any time.'
)

const runBulkStatus = async () => {
  if (statusBusy.value) return
  const ids = Array.from(selectedIds.value)
  if (ids.length === 0) {
    bulkAction.open = false
    return
  }
  statusBusy.value = true
  error.value = ''
  try {
    await bulkSetUsersActive({
      userIds: ids,
      isActive: bulkAction.action === 'activate'
    })
    bulkAction.open = false
    selectedIds.value = new Set()
    await load()
  } catch (bulkError) {
    logApiError('admin.mentors.bulk-status', bulkError)
    error.value =
      bulkError instanceof Error
        ? bulkError.message
        : 'Unable to update mentor statuses right now.'
  } finally {
    statusBusy.value = false
  }
}

// -- Replace inactive mentors -----------------------------------------------

const onReplaceConfirmed = () => {
  void load()
}

// -- Detail helpers ---------------------------------------------------------

const sortedAvailability = (availability: AdminMentorAvailability[]) =>
  [...availability].sort((a, b) => a.weekday - b.weekday)

load()
</script>

<style scoped>
.admin-mentors {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.admin-mentors__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.admin-mentors__count {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.admin-mentors__header-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.admin-mentors__inactive-days {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.admin-mentors__inactive-label {
  font-size: 0.9rem;
  color: var(--text-muted);
  white-space: nowrap;
}

.admin-mentors__inactive-input {
  width: 4.5rem;
  height: 2rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background-color: var(--white);
  color: var(--charcoal);
  font-size: 0.9rem;
}

.admin-mentors__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.4rem;
  height: 1.4rem;
  padding: 0 0.35rem;
  margin-left: 0.4rem;
  border-radius: 999px;
  background-color: var(--danger);
  border: 1px solid rgba(255, 255, 255, 0.4);
  color: var(--white);
  font-size: 0.75rem;
  font-weight: 600;
}

.admin-mentors__error {
  margin: 0;
  padding: 0.7rem 0.9rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.875rem;
}

.admin-mentors__card {
  background-color: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(7, 17, 15, 0.03);
  overflow: hidden;
}

.admin-mentors__card--loading {
  opacity: 0.6;
  pointer-events: none;
}

.admin-mentors__scroll {
  width: 100%;
  overflow-x: auto;
}

.admin-mentors__table {
  width: 100%;
  border-collapse: collapse;
}

.admin-mentors__check {
  width: 42px;
  padding: 0.75rem 0.5rem;
  text-align: center;
}

.admin-mentors__check input[type='checkbox'] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: var(--dark-green);
}

.admin-mentors__expand {
  width: 34px;
  padding: 0.75rem 0.25rem;
}

.admin-mentors__chevron {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background-color: transparent;
  color: var(--text-muted);
  font-size: 0.8rem;
  cursor: pointer;
}

.admin-mentors__chevron:hover {
  background-color: var(--light-green);
  color: var(--dark-green);
}

.admin-mentors__head {
  padding: 0.85rem 1rem;
  text-align: center;
  font-weight: 600;
  color: var(--charcoal);
  background-color: var(--light-green);
  border-bottom: 2px solid var(--border-light);
  white-space: nowrap;
}

.admin-mentors__sort {
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.admin-mentors__sort:hover,
.admin-mentors__sort--active {
  color: var(--dark-green);
}

.admin-mentors__row {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.admin-mentors__row:hover {
  background-color: var(--light-green);
}

.admin-mentors__row--selected {
  background-color: rgba(1, 113, 81, 0.08);
}

.admin-mentors__row--inactive {
  background-color: rgba(220, 53, 69, 0.04);
}

.admin-mentors__row td {
  padding: 0.75rem 1rem;
  color: var(--charcoal);
  border-bottom: 1px solid var(--border-light);
}

.admin-mentors__name {
  margin: 0;
  font-weight: 600;
}

.admin-mentors__sub {
  margin: 0;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.admin-mentors__muted {
  font-size: 0.9rem;
  color: var(--text-muted);
}

.admin-mentors__danger {
  color: var(--danger);
  font-size: 0.85rem;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

.admin-mentors__never {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.admin-mentors__pill {
  display: inline-block;
  padding: 0.15rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background-color: var(--bg-light);
  font-size: 0.8rem;
  color: var(--charcoal);
  white-space: nowrap;
}

.admin-mentors__pill--green {
  border-color: rgba(25, 135, 84, 0.3);
  background-color: rgba(25, 135, 84, 0.1);
  color: var(--dark-green);
}

.admin-mentors__status-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.admin-mentors__active-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--dark-green);
}

.admin-mentors__logged-in {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
}

.admin-mentors__mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.admin-mentors__detail-row td {
  padding: 0;
  background-color: rgba(1, 113, 81, 0.04);
}

.admin-mentors__detail {
  border-bottom: 1px solid var(--border-light);
}

.admin-mentors__detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.25rem;
  padding: 1.1rem 1.5rem;
}

.admin-mentors__detail-grid section {
  min-width: 0;
}

.admin-mentors__section-title {
  margin: 0 0 0.5rem;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.admin-mentors__section-title i {
  font-size: 0.8rem;
}

.admin-mentors__detail-list {
  margin: 0;
}

.admin-mentors__detail-list div {
  display: flex;
  gap: 0.5rem;
  margin: 0.15rem 0;
  font-size: 0.8rem;
}

.admin-mentors__detail-list dt {
  color: var(--text-muted);
}

.admin-mentors__detail-list dd {
  margin: 0;
}

.admin-mentors__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.admin-mentors__chip {
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background-color: var(--light-green);
  border: 1px solid var(--border-light);
  font-size: 0.8rem;
}

.admin-mentors__availability-slot {
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  font-size: 0.8rem;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.admin-mentors__slot-day {
  font-weight: 600;
}

.admin-mentors__certificates {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.admin-mentors__cert {
  padding: 0.5rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  font-size: 0.8rem;
}

.admin-mentors__cert-name {
  font-weight: 600;
}

.admin-mentors__verified {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  margin-left: 0.5rem;
  color: var(--dark-green);
  font-size: 0.75rem;
}

.admin-mentors__cert > div:nth-child(2) {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
  margin: 0.2rem 0;
}

.admin-mentors__link {
  color: var(--dark-green);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.admin-mentors__link:hover {
  text-decoration: none;
}

.admin-mentors__state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  padding: 2.5rem 1rem;
  color: var(--text-muted);
}

.admin-mentors__state--empty {
  border: 1px dashed var(--border-light);
  border-radius: 10px;
  background-color: var(--bg-light);
}

.admin-mentors__spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border-light);
  border-top-color: var(--dark-green);
  border-radius: 50%;
  animation: admin-mentors-spin 0.8s linear infinite;
}

@keyframes admin-mentors-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .admin-mentors__spinner {
    animation: none;
  }
}
</style>