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
        <div class="matched-groups__actions">
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
        </div>
      </div>

      <p v-if="error" class="matched-groups__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ error }}</span>
      </p>

      <p v-if="!groups.length" class="matched-groups__empty">No confirmed mentor assignments yet.</p>

      <div v-else class="matched-groups__table-wrap">
        <table class="matched-groups__table">
          <thead>
            <tr>
              <th class="matched-groups__expand-col"></th>
              <th v-for="col in columns" :key="col.key">
                <button type="button" class="matched-groups__sort-btn" @click="toggleSort(col.key)">
                  <span>{{ col.label }}</span>
                  <i class="fas" :class="sortIconClass(col.key)" aria-hidden="true"></i>
                </button>
              </th>
              <th class="matched-groups__action-col">Action</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="group in sortedGroups" :key="group.membershipId">
              <tr class="matched-groups__row" @click="toggleExpand(group.membershipId)">
                <td class="matched-groups__expand-col">
                  <i
                    class="fas"
                    :class="isExpanded(group.membershipId) ? 'fa-chevron-down' : 'fa-chevron-right'"
                    aria-hidden="true"
                  ></i>
                </td>
                <td class="matched-groups__name">{{ group.groupName }}</td>
                <td><span class="matched-groups__country-badge">{{ group.countryName || 'Unknown' }}</span></td>
                <td>{{ group.studentCount }}</td>
                <td>
                  <div class="matched-groups__mentor-cell">
                    <span>
                      {{ group.mentor.name }}
                      <span v-if="capacityFor(group.mentor.mentorId)" class="matched-groups__capacity">
                        · {{ capacityFor(group.mentor.mentorId) }}
                      </span>
                    </span>
                    <span v-if="group.mentor.institution" class="matched-groups__muted">{{ group.mentor.institution }}</span>
                  </div>
                </td>
                <td @click.stop>
                  <span v-if="group.mentor.isActive" class="matched-groups__status matched-groups__status--active">
                    <i class="fas fa-circle-check" aria-hidden="true"></i> Active
                  </span>
                  <span v-else class="matched-groups__status matched-groups__status--danger">
                    <i class="fas fa-triangle-exclamation" aria-hidden="true"></i> Inactive
                  </span>
                </td>
                <td class="matched-groups__action-col" @click.stop>
                  <div v-if="replacingId === group.membershipId" class="matched-groups__replace-form">
                    <select
                      v-model="selectedMentorId"
                      class="form-input matched-groups__replace-select"
                      :disabled="replaceBusy"
                      :aria-label="`Replacement mentor for ${group.groupName}`"
                    >
                      <option value="">Select action</option>
                      <option :value="UNASSIGN_VALUE">— Unassign (leave unmatched)</option>
                      <option v-for="m in optionsFor(group)" :key="m.mentorId" :value="String(m.mentorId)">
                        {{ m.name }}{{ m.remainingCapacity === 0 ? ' (full)' : '' }}
                      </option>
                    </select>
                    <button
                      type="button"
                      class="btn btn-sm"
                      :disabled="!selectedMentorId || replaceBusy"
                      @click="confirmReplace(group)"
                    >
                      {{ replaceBusy ? 'Working...' : 'Confirm' }}
                    </button>
                    <button type="button" class="btn btn-sm btn-outline" :disabled="replaceBusy" @click="cancelReplace">
                      Cancel
                    </button>
                  </div>
                  <button v-else type="button" class="btn btn-sm btn-outline" @click="startReplace(group.membershipId)">
                    Replace Mentor
                  </button>
                </td>
              </tr>
              <tr v-if="isExpanded(group.membershipId)" class="matched-groups__detail-row">
                <td colspan="7">
                  <div class="matched-groups__detail">
                    <div>
                      <p class="matched-groups__detail-label">Students ({{ group.studentCount }})</p>
                      <p v-if="!group.students.length" class="matched-groups__muted">No student data available.</p>
                      <ul v-else class="matched-groups__student-list">
                        <li v-for="(s, i) in group.students" :key="`${s.name}-${i}`">
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
                        <p class="matched-groups__student-name">{{ group.mentor.name }}</p>
                        <p v-if="group.mentor.institution" class="matched-groups__muted">{{ group.mentor.institution }}</p>
                        <div class="matched-groups__mentor-detail-meta">
                          <span class="matched-groups__country-badge">{{ group.mentor.countryName || 'Unknown' }}</span>
                          <span v-if="group.mentor.isActive" class="matched-groups__status matched-groups__status--active">Active</span>
                          <span v-else class="matched-groups__status matched-groups__status--danger">Inactive</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
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

const columns: Array<{ key: SortKey; label: string }> = [
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

const sortIconClass = (key: SortKey) => {
  if (sortState.value.key !== key) return 'fa-sort'
  return sortState.value.direction === 'asc' ? 'fa-sort-up' : 'fa-sort-down'
}

// --- Row expansion -------------------------------------------------------
const expandedIds = ref<Set<number>>(new Set())
const isExpanded = (id: number) => expandedIds.value.has(id)
const toggleExpand = (id: number) => {
  const next = new Set(expandedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedIds.value = next
}

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
  color: var(--charcoal);
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

.matched-groups__actions {
  display: flex;
  align-items: center;
  gap: 1rem;
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

.matched-groups__empty {
  padding: 2rem;
  text-align: center;
  border: 1px dashed var(--border-light);
  border-radius: 10px;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.matched-groups__table-wrap {
  width: 100%;
  overflow-x: auto;
  background-color: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 10px;
}

.matched-groups__table {
  width: 100%;
  border-collapse: collapse;
}

.matched-groups__table th {
  padding: 0.75rem 1rem;
  text-align: left;
  font-weight: 600;
  color: var(--charcoal);
  background-color: var(--light-green);
  border-bottom: 2px solid var(--border-light);
  white-space: nowrap;
}

.matched-groups__table td {
  padding: 0.75rem 1rem;
  color: var(--charcoal);
  border-bottom: 1px solid var(--border-light);
  vertical-align: middle;
}

.matched-groups__expand-col {
  width: 32px;
  text-align: center;
  color: var(--text-muted);
}

.matched-groups__action-col {
  width: 20rem;
}

.matched-groups__sort-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0;
  border: none;
  background: transparent;
  font: inherit;
  font-weight: 600;
  color: inherit;
  cursor: pointer;
}

.matched-groups__row {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.matched-groups__row:hover {
  background-color: var(--light-green);
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

.matched-groups__detail-row td {
  padding: 0;
  background-color: var(--bg-light);
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
  color: var(--charcoal);
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
