<template>
  <div class="matched-groups">
    <p v-if="loading" class="matched-groups__loading">
      <span class="matched-groups__spinner" aria-hidden="true"></span>
      Loading matched assignments...
    </p>

    <template v-else>
      <div class="matched-groups__header">
        <div class="matched-groups__title">
          <h2>Matched Groups</h2>
          <span class="matched-groups__badge">{{ groups.length }}</span>
          <span v-if="inactiveCount > 0" class="matched-groups__badge matched-groups__badge--danger">
            <i class="fas fa-triangle-exclamation" aria-hidden="true"></i> {{ inactiveCount }} inactive
          </span>
        </div>
      </div>

      <p v-if="error" class="matched-groups__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ error }}</span>
      </p>

      <AppDataTable
        :columns="columns"
        :rows="groupRows"
        row-key="id"
        :selectable="false"
        :sort="sortState"
        :page-size="DATA_TABLE_ALL"
        search-placeholder="Group or mentor"
        two-line-rows
        empty-message="No confirmed mentor assignments yet."
        @update:sort="toggleSort($event.key as SortKey)"
      >
        <template #search-side>
          <label class="matched-groups__toggle">
            <input v-model="showFullMentors" type="checkbox" />
            <span>Show mentors at capacity</span>
          </label>
          <button
            v-if="inactiveCount > 0"
            type="button"
            class="btn btn-sm btn-outline"
            @click="bulkDialogOpen = true"
          >
            <i class="fas fa-rotate" aria-hidden="true"></i> Replace Inactive Mentors
          </button>
        </template>
        <template #cell-group="{ row }">
          <span class="matched-groups__name">{{ groupOf(row).groupName }}</span>
        </template>
        <template #cell-mentor="{ row }">
          <div class="matched-groups__mentor-cell">
            <span>
              {{ groupOf(row).mentor.name }}
              <span v-if="capacityFor(groupOf(row).mentor.mentorId)" class="matched-groups__capacity">
                · {{ capacityFor(groupOf(row).mentor.mentorId) }}
              </span>
            </span>
            <span v-if="groupOf(row).mentor.institution" class="matched-groups__muted">
              {{ groupOf(row).mentor.institution }}
            </span>
          </div>
        </template>
        <template #cell-status="{ row }">
          <span v-if="groupOf(row).mentor.isActive" class="matched-groups__status matched-groups__status--active">
            <i class="fas fa-circle-check" aria-hidden="true"></i> Active
          </span>
          <span v-else class="matched-groups__status matched-groups__status--danger">
            <i class="fas fa-triangle-exclamation" aria-hidden="true"></i> Inactive
          </span>
        </template>
        <template #actions="{ row }">
          <div v-if="replacingId === groupOf(row).membershipId" class="matched-groups__replace-form">
            <select
              v-model="selectedMentorId"
              class="form-input matched-groups__replace-select"
              :disabled="replaceBusy"
              :aria-label="`Replacement mentor for ${groupOf(row).groupName}`"
            >
              <option value="">Select action</option>
              <option :value="UNASSIGN_VALUE">— Unassign (leave unmatched)</option>
              <option v-for="m in optionsFor(groupOf(row))" :key="m.mentorId" :value="String(m.mentorId)">
                {{ m.name }}{{ m.remainingCapacity === 0 ? ' (full)' : '' }}
              </option>
            </select>
            <button
              type="button"
              class="btn btn-sm"
              :disabled="!selectedMentorId || replaceBusy"
              @click="confirmReplace(groupOf(row))"
            >
              {{ replaceBusy ? 'Working...' : 'Confirm' }}
            </button>
            <button type="button" class="btn btn-sm btn-outline" :disabled="replaceBusy" @click="cancelReplace">
              Cancel
            </button>
          </div>
          <button
            v-else
            type="button"
            class="btn btn-sm btn-outline"
            @click="startReplace(groupOf(row).membershipId)"
          >
            Replace Mentor
          </button>
        </template>
        <template #row-detail="{ row }">
          <div class="matched-groups__detail">
            <div>
              <p class="matched-groups__detail-label">Students ({{ groupOf(row).studentCount }})</p>
              <p v-if="!groupOf(row).students.length" class="matched-groups__muted">No student data available.</p>
              <ul v-else class="matched-groups__student-list">
                <li v-for="(s, i) in groupOf(row).students" :key="`${s.name}-${i}`">
                  <span class="matched-groups__student-name">{{ s.name }}</span>
                  <span v-if="!s.hasLoggedIn" class="matched-groups__login-badge" title="This student has never signed in">
                    Never signed in
                  </span>
                  <span v-if="s.interests.length" class="matched-groups__muted">{{ s.interests.join(', ') }}</span>
                </li>
              </ul>
            </div>
            <div>
              <p class="matched-groups__detail-label">Assigned Mentor</p>
              <div class="matched-groups__mentor-detail">
                <p class="matched-groups__student-name">{{ groupOf(row).mentor.name }}</p>
                <p v-if="groupOf(row).mentor.institution" class="matched-groups__muted">
                  {{ groupOf(row).mentor.institution }}
                </p>
                <div class="matched-groups__mentor-detail-meta">
                  <span class="matched-groups__country-badge">{{ groupOf(row).mentor.countryName || 'Unknown' }}</span>
                  <span
                    v-if="groupOf(row).mentor.isActive"
                    class="matched-groups__status matched-groups__status--active"
                  >Active</span>
                  <span v-else class="matched-groups__status matched-groups__status--danger">Inactive</span>
                </div>
              </div>
            </div>
          </div>
        </template>
      </AppDataTable>
    </template>

    <MentorReplaceDialog
      v-model:open="bulkDialogOpen"
      :inactive-groups="inactiveGroups"
      :mentors="mentors"
      @confirmed="onBulkConfirmed"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'
import MentorReplaceDialog from '@/components/admin/MentorReplaceDialog.vue'
import {
  fetchMatchedGroups,
  fetchMentorMatchMentorList,
  replaceMentor,
  unassignMentors,
  type MatchedGroup,
  type MentorListItem
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import { DATA_TABLE_ALL } from '@/utils/dataTable'

const UNASSIGN_VALUE = '__unassign__'

const groups = ref<MatchedGroup[]>([])
const mentors = ref<MentorListItem[]>([])
const loading = ref(false)
const error = ref('')

// Fetches into state; throws on failure so callers can decide how to report it.
const fetchData = async () => {
  const [groupsData, mentorsData] = await Promise.all([fetchMatchedGroups(), fetchMentorMatchMentorList()])
  groups.value = groupsData
  mentors.value = mentorsData
}

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    await fetchData()
  } catch (err) {
    logApiError('admin.matched-groups.load', err)
    error.value = err instanceof Error ? err.message : 'Matched groups could not be loaded right now.'
  } finally {
    loading.value = false
  }
}

onMounted(load)

const inactiveGroups = computed(() => groups.value.filter((g) => !g.mentor.isActive))
const inactiveCount = computed(() => inactiveGroups.value.length)

const showFullMentors = ref(false)

// matched-groups rows don't carry capacity themselves — it only exists on the
// separately-fetched mentor pool, so look it up by id rather than re-fetching
// per row.
const mentorById = computed(() => new Map(mentors.value.map((m) => [m.mentorId, m])))

const capacityFor = (mentorId: number): string | null => {
  const mentor = mentorById.value.get(mentorId)
  return mentor ? `${mentor.currentAssignedCount}/${mentor.maxGroupCount}` : null
}

// --- Sorting -----------------------------------------------------------
// Client-side only: fetchMatchedGroups() returns the full confirmed set in
// one call, with no server-side pagination/sort params to route through.
type SortKey = 'group' | 'country' | 'students' | 'mentor' | 'status'

const columns: DataTableColumn[] = [
  { key: 'group', label: 'Group' },
  { key: 'country', label: 'Country' },
  { key: 'students', label: 'Students' },
  { key: 'mentor', label: 'Mentor' },
  { key: 'status', label: 'Status' }
]

const sortState = ref<{ key: SortKey; direction: 'asc' | 'desc' }>({ key: 'group', direction: 'asc' })

const sortValue = (group: MatchedGroup, key: SortKey): string | number => {
  switch (key) {
    case 'group':
      return group.groupName
    case 'country':
      return group.countryName ?? ''
    case 'students':
      return group.studentCount
    case 'mentor':
      return `${group.mentor.name} ${group.mentor.institution ?? ''}`
    case 'status':
      return group.mentor.isActive ? 'Active' : 'Inactive'
  }
}

const sortedGroups = computed(() => {
  const { key, direction } = sortState.value
  const sign = direction === 'asc' ? 1 : -1
  return [...groups.value].sort((a, b) => {
    const av = sortValue(a, key)
    const bv = sortValue(b, key)
    if (av < bv) return -1 * sign
    if (av > bv) return 1 * sign
    return 0
  })
})

const toggleSort = (key: SortKey) => {
  sortState.value =
    sortState.value.key === key
      ? { key, direction: sortState.value.direction === 'asc' ? 'desc' : 'asc' }
      : { key, direction: 'asc' }
}

// Each group as a table row: plain text for search, and the group itself for
// the cells drawn here. Sorted above, by this panel's own rules.
const groupRows = computed(() =>
  sortedGroups.value.map((group) => ({
    id: group.membershipId,
    matched: group,
    group: group.groupName,
    country: group.countryName || 'Unknown',
    students: group.studentCount,
    mentor: group.mentor.name,
    status: group.mentor.isActive ? 'Active' : 'Inactive'
  }))
)

const groupOf = (row: Record<string, unknown>) => row.matched as MatchedGroup

// --- Per-row replace -------------------------------------------------------
const replacingId = ref<number | null>(null)
const selectedMentorId = ref('')
const replaceBusy = ref(false)

const startReplace = (membershipId: number) => {
  replacingId.value = membershipId
  selectedMentorId.value = ''
}

const cancelReplace = () => {
  replacingId.value = null
  selectedMentorId.value = ''
}

// Scored suggestions aren't loaded per-row here (that's the bulk dialog's
// job) — this is the plain mentor pool, filtered to those with a free seat,
// plus whichever mentor already has this group (so the select doesn't lose
// its value when reopened), plus everyone once "show mentors at capacity" is on.
const optionsFor = (group: MatchedGroup): MentorListItem[] =>
  mentors.value.filter(
    (m) => showFullMentors.value || m.remainingCapacity > 0 || m.mentorId === group.mentor.mentorId
  )

const confirmReplace = async (group: MatchedGroup) => {
  if (!selectedMentorId.value) return
  replaceBusy.value = true
  error.value = ''
  try {
    if (selectedMentorId.value === UNASSIGN_VALUE) {
      await unassignMentors([group.groupId])
    } else {
      await replaceMentor({
        membershipId: group.membershipId,
        groupId: group.groupId,
        newMentorUserId: Number(selectedMentorId.value)
      })
    }
  } catch (err) {
    logApiError('admin.matched-groups.replace', err)
    error.value = err instanceof Error ? err.message : 'Action failed. Please try again.'
    replaceBusy.value = false
    return
  }

  // The mentor change went through. A failure past this point is a stale list,
  // not a failed replace — report it as its own thing.
  replacingId.value = null
  selectedMentorId.value = ''
  replaceBusy.value = false
  try {
    await fetchData()
  } catch (err) {
    logApiError('admin.matched-groups.load', err)
    error.value = 'Mentor updated, but the list could not be refreshed. Reload the page to see the latest.'
  }
}

// --- Bulk replace inactive mentors -----------------------------------------
const bulkDialogOpen = ref(false)
const onBulkConfirmed = () => {
  load()
}
</script>

<style scoped>
.matched-groups {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.matched-groups__loading {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.matched-groups__spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border-light);
  border-top-color: var(--dark-green);
  border-radius: 50%;
  animation: matched-groups-spin 0.8s linear infinite;
}

@keyframes matched-groups-spin {
  to {
    transform: rotate(360deg);
  }
}

.matched-groups__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.matched-groups__title {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.matched-groups__title h2 {
  margin: 0;
  font-size: 1.05rem;
  color: var(--teal);
}

.matched-groups__badge {
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  background-color: var(--light-green);
  color: var(--dark-green);
  font-size: 0.8rem;
  font-weight: 600;
}

.matched-groups__badge--danger {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background-color: rgba(220, 53, 69, 0.12);
  color: var(--danger);
}

.matched-groups__toggle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: var(--text-muted);
  cursor: pointer;
}

.matched-groups__error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--danger);
  font-size: 0.9rem;
}

.matched-groups__name {
  font-weight: 600;
}

.matched-groups__country-badge {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--border-light);
  font-size: 0.75rem;
  color: var(--text-muted);
}

.matched-groups__mentor-cell {
  display: flex;
  flex-direction: column;
}

.matched-groups__muted {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.matched-groups__capacity {
  color: var(--text-muted);
  font-size: 0.8rem;
  font-weight: 400;
}

.matched-groups__status {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.8rem;
}

.matched-groups__status--active {
  color: #1a7f37;
}

.matched-groups__status--danger {
  color: var(--danger);
}

.matched-groups__replace-form {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.matched-groups__replace-select {
  flex: 1 1 auto;
  min-width: 10rem;
  padding: 0.4rem 0.5rem;
  font-size: 0.8rem;
}

.matched-groups__detail {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  padding: 1rem 1.5rem;
}

@media (max-width: 720px) {
  .matched-groups__detail {
    grid-template-columns: 1fr;
  }
}

.matched-groups__detail-label {
  margin: 0 0 0.5rem;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

.matched-groups__student-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.matched-groups__student-list li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.6rem;
  background-color: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 6px;
  font-size: 0.8rem;
}

.matched-groups__student-name {
  font-weight: 600;
  color: var(--teal);
}

.matched-groups__login-badge {
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  border: 1px solid var(--border-light);
  font-size: 0.7rem;
  color: var(--text-muted);
}

.matched-groups__mentor-detail {
  padding: 0.6rem 0.75rem;
  background-color: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 6px;
}

.matched-groups__mentor-detail p {
  margin: 0 0 0.2rem;
}

.matched-groups__mentor-detail-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.4rem;
}
</style>
