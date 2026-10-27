<template>
  <div id="admin-mentors-table" class="admin-mentors">
    <p v-if="error" class="admin-mentors__error" role="alert">{{ error }}</p>

    <!-- Bulk actions -->
    <BulkActionsBar
      v-if="selectedIds.size > 0"
      :count="selectedIds.size"
      noun="mentor"
      :disabled="statusBusy"
      @clear="clearSelection"
    >
      <button type="button" class="btn btn-sm btn-outline" :disabled="statusBusy" @click="openBulk('activate')">
        Activate
      </button>
      <button type="button" class="btn btn-sm btn-outline" :disabled="statusBusy" @click="openBulk('deactivate')">
        Deactivate
      </button>
    </BulkActionsBar>

    <AppDataTable
      :columns="columns"
      :rows="mentorRows"
      row-key="id"
      :loading="loading"
      empty-message="No mentors registered yet."
      search-placeholder="Name or email"
      two-line-rows
      :page-size="DATA_TABLE_ALL"
      :selected="[...selectedIds]"
      :sort="sortState"
      v-model:search="searchInput"
      :row-class="rowClass"
      @update:selected="onSelected"
      @update:sort="setSort($event.key as MentorSortKey)"
    >
      <template #filters>
        <label class="table-filter-field">
          <span class="table-filter-label">Capacity</span>
          <AppSelect
            v-model="capacityFilter"
            class="table-filter"
            aria-label="Mentor capacity"
            :options="CAPACITY_OPTIONS"
          />
        </label>
      </template>
      <template #stats>
        {{ mentors.length }} mentor{{ mentors.length === 1 ? '' : 's' }} registered
      </template>
      <template #search-side>
        <div class="admin-mentors__inactive-days">
          <label for="inactive-days-input" class="admin-mentors__inactive-label">Idle after</label>
          <input
            id="inactive-days-input"
            type="number"
            min="1"
            :value="inactiveDays"
            class="admin-mentors__inactive-input table-filter"
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
          Replace Idle Mentors
          <span class="admin-mentors__badge">{{ inactiveGroups.length }}</span>
        </button>
      </template>
      <template #cell-name="{ row }">
        <p class="admin-mentors__name">{{ mentorOf(row).name }}</p>
        <p class="admin-mentors__sub">{{ mentorOf(row).email }}</p>
      </template>
      <template #cell-capacity="{ row }">
        {{ mentorOf(row).currentAssignedCount }}/{{ mentorOf(row).maxGroupCount }}
        <span class="admin-mentors__sub">({{ mentorOf(row).remainingCapacity }} left)</span>
      </template>
      <template #cell-lastMessage="{ row }">
        <span
          v-if="mentorOf(row).lastMessageAt"
          :class="{ 'admin-mentors__danger': lastMessageDays(mentorOf(row).lastMessageAt!) >= inactiveDays }"
        >
          {{ relativeDays(mentorOf(row).lastMessageAt!) }}
        </span>
        <span v-else class="admin-mentors__never">
          <i class="fas fa-comment-slash" aria-hidden="true"></i>
          Never
        </span>
      </template>
      <template #cell-loggedIn="{ row }">
        <span v-if="mentorOf(row).hasLoggedIn" class="admin-mentors__logged-in">
          Yes
          <span
            v-if="mentorOf(row).lastLogin"
            class="admin-mentors__sub"
            :title="formatExactTime(mentorOf(row).lastLogin!)"
          >
            {{ formatShortDate(mentorOf(row).lastLogin!) }}
          </span>
        </span>
        <span v-else class="admin-mentors__muted">No</span>
      </template>
      <template #row-detail="{ row }">
        <AdminMentorDetails :mentor="mentorOf(row)" />
      </template>
    </AppDataTable>

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

    <AdminMentorImportSheet
      v-model="mentorImportOpen"
      @imported="onMentorsImported"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'
import AppSelect, { type AppSelectOption } from '@/components/AppSelect.vue'
import BulkActionsBar from '@/components/admin/BulkActionsBar.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import MentorReplaceDialog from '@/components/admin/MentorReplaceDialog.vue'
import AdminMentorImportSheet from '@/components/admin/mentors/AdminMentorImportSheet.vue'
import AdminMentorDetails from '@/components/admin/mentors/AdminMentorDetails.vue'
import { useAdminMentorsView, type MentorSortKey } from '@/composables/admin/useAdminMentorsView'
import type { AdminMentorDetail } from '@/utils/adminAPI'
import { DATA_TABLE_ALL } from '@/utils/dataTable'
import { formatExactTime, formatShortDate } from '@/utils/date'
import {
  mentorConcern,
  lastMessageDays,
  relativeDays
} from '@/utils/mentorFormat'

type CapacityFilter = '' | 'available' | 'full' | 'over'

const props = withDefaults(defineProps<{
  initialSearch?: string
  initialCapacityFilter?: CapacityFilter
}>(), {
  initialSearch: '',
  initialCapacityFilter: '',
})

const searchInput = ref(props.initialSearch)
const capacityFilter = ref<CapacityFilter>(props.initialCapacityFilter)

watch(() => props.initialSearch, (value) => { searchInput.value = value })
watch(() => props.initialCapacityFilter, (value) => { capacityFilter.value = value })

const CAPACITY_OPTIONS: AppSelectOption[] = [
  { value: '', label: 'All capacities' },
  { value: 'available', label: 'Available capacity' },
  { value: 'full', label: 'At capacity' },
  { value: 'over', label: 'Over capacity' },
]

const {
  loading,
  statusBusy,
  error,
  mentors,
  mentorList,
  inactiveDays,
  selectedIds,
  bulkAction,
  replaceDialogOpen,
  inactiveGroups,
  sortState,
  sortedMentors,
  setSort,
  clearSelection,
  onInactiveDaysChange,
  toggleActive,
  openBulk,
  bulkTitle,
  bulkMessage,
  runBulkStatus,
  onReplaceConfirmed,
  load
} = useAdminMentorsView()

const columns: DataTableColumn[] = [
  { key: 'name', label: 'Name' },
  { key: 'country', label: 'Country' },
  { key: 'institution', label: 'Institution' },
  { key: 'capacity', label: 'Capacity' },
  { key: 'lastMessage', label: 'Last Message' },
  { key: 'loggedIn', label: 'Logged In' }
]

// Each mentor as a table row: plain text for search, copying and export,
// and the mentor itself for the cells drawn here. Sorted by useAdminMentorsView.
const filteredMentors = computed(() => {
  const query = searchInput.value.trim().toLowerCase()
  return sortedMentors.value.filter((mentor) => {
    const matchesCapacity = capacityFilter.value === ''
      || (capacityFilter.value === 'available' && mentor.remainingCapacity > 0)
      || (capacityFilter.value === 'full' && mentor.remainingCapacity === 0)
      || (capacityFilter.value === 'over' && mentor.remainingCapacity < 0)
    const matchesSearch = !query || [
      mentor.name,
      mentor.email,
      mentor.countryName,
      mentor.institution,
      ...mentor.interests,
      mentor.isActive ? 'Active' : 'Inactive',
      `${mentor.currentAssignedCount}/${mentor.maxGroupCount}`,
      `${mentor.remainingCapacity} left`,
      mentor.lastMessageAt ? relativeDays(mentor.lastMessageAt) : 'Never',
      mentor.hasLoggedIn ? 'Yes logged in' : 'No never logged in',
    ].some((value) => value?.toLowerCase().includes(query))
    return matchesCapacity && matchesSearch
  })
})

const mentorRows = computed(() =>
  filteredMentors.value.map((mentor) => ({
    id: mentor.mentorId,
    mentor,
    name: mentor.name,
    email: mentor.email,
    country: mentor.countryName ?? 'Unknown',
    institution: mentor.institution ?? '—',
    capacity: `${mentor.currentAssignedCount}/${mentor.maxGroupCount} (${mentor.remainingCapacity} left)`,
    lastMessage: mentor.lastMessageAt ? relativeDays(mentor.lastMessageAt) : 'Never',
    loggedIn: mentor.hasLoggedIn ? 'Yes' : 'No'
  }))
)

const mentorOf = (row: Record<string, unknown>) => row.mentor as AdminMentorDetail

const onSelected = (ids: Array<string | number>) => {
  selectedIds.value = new Set(ids as number[])
}

const rowClass = (row: Record<string, unknown>) =>
  mentorConcern(mentorOf(row), inactiveDays.value) ? 'admin-mentors__row--inactive' : undefined

const mentorImportOpen = ref(false)

const openMentorImport = () => {
  mentorImportOpen.value = true
}

onMounted(() => {
  void load()
})

const onMentorsImported = () => {
  void load()
}

defineExpose({
  openMentorImport,
  loading
})

</script>

<style scoped>
.admin-mentors {
  display: flex;
  flex-direction: column;
  gap: 1rem;
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

/* The table's filter box, at its own narrow width. */
.admin-mentors__inactive-input {
  width: 4.5rem;
  min-width: 0;
  background-color: var(--white);
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

/* An effectively inactive mentor's row, tinted. */
:deep(.admin-mentors__row--inactive) {
  background-color: rgba(220, 53, 69, 0.04);
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
  color: var(--text-muted);
}

.admin-mentors__danger {
  color: var(--danger);
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

.admin-mentors__never {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--text-muted);
}

.admin-mentors__active-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  color: var(--dark-green);
}

.admin-mentors__logged-in {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
}

.admin-mentors__status-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.admin-mentors__toggle-btn {
  min-width: 5.5rem;
  justify-content: center;
}
</style>
