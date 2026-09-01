<template>
  <div class="content-area admin-groups">
    <div class="page-head">
      <div>
        <h1>Groups</h1>
        <p class="page-subtitle">Manage student groups and mentor assignments.</p>
      </div>
      <button v-if="activeTab === 'groups'" type="button" class="btn btn-outline" @click="openCreate">
        <i class="fas fa-plus" aria-hidden="true"></i> New group
      </button>
    </div>

    <div class="admin-groups__tabs" role="tablist">
      <button
        type="button"
        class="admin-groups__tab"
        :class="{ 'admin-groups__tab--active': activeTab === 'groups' }"
        role="tab"
        :aria-selected="activeTab === 'groups'"
        @click="activeTab = 'groups'"
      >
        Groups
      </button>
      <button
        type="button"
        class="admin-groups__tab"
        :class="{ 'admin-groups__tab--active': activeTab === 'matched' }"
        role="tab"
        :aria-selected="activeTab === 'matched'"
        @click="activeTab = 'matched'"
      >
        Matched Groups
      </button>
    </div>

    <MatchedGroupsPanel v-if="activeTab === 'matched'" />

    <template v-else>
    <div class="admin-groups__filters">
      <label class="admin-groups__search">
        <span class="sr-only">Search groups</span>
        <i class="fas fa-search admin-groups__search-icon" aria-hidden="true"></i>
        <input
          v-model="searchInput"
          type="search"
          placeholder="Search by group name..."
        />
      </label>

      <label class="admin-groups__filter-field">
        <span class="admin-groups__filter-label">Mentor status</span>
        <select v-model="mentorStatus">
          <option value="">All</option>
          <option value="matched">Matched</option>
          <option value="unmatched">Unmatched</option>
        </select>
      </label>
    </div>

    <p v-if="error" class="admin-groups__error" role="alert">
      <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
      <span>{{ error }}</span>
    </p>

    <BulkActionsBar
      v-if="bulkCount && !loading"
      :count="bulkCount"
      noun="group"
      :disabled="busy"
      @clear="clearSelection"
    >
      <button type="button" class="btn btn-sm btn-danger" :disabled="busy" @click="confirmBulkDelete">
        <i class="fas fa-trash" aria-hidden="true"></i> Delete
      </button>
    </BulkActionsBar>

    <div v-if="selectionBanner" class="admin-groups__selection-banner" aria-live="polite">
      <template v-if="selectAllMatching">
        <span>
          <i class="fas fa-check-double admin-groups__selection-icon" aria-hidden="true"></i>
          <span v-if="excludedCount > 0">
            {{ effectiveSelectAllCount }} of {{ totalCount }} groups selected.
          </span>
          <span v-else>All {{ totalCount }} groups matching these filters are selected.</span>
        </span>
        <button type="button" class="admin-groups__selection-link" @click="clearSelection">
          Clear selection
        </button>
      </template>
      <template v-else>
        <span>
          <i class="fas fa-circle-info admin-groups__selection-icon" aria-hidden="true"></i>
          <span>All {{ pageRowCount }} groups on this page are selected.</span>
        </span>
        <button type="button" class="admin-groups__selection-link" @click="selectAllMatchingNow">
          Select all {{ totalCount }} groups matching these filters
        </button>
      </template>
    </div>

    <AdminDataTable
      :columns="columns"
      :rows="rows"
      row-key="id"
      :loading="loading"
      :sort-state="sortState"
      :page="page"
      :page-size="limit"
      :total-count="totalCount"
      :page-size-options="[25, 50, 100]"
      empty-message="No groups found."
      pager-label="Groups pagination"
      @update:sort="onSortChange"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #header-select>
        <input
          type="checkbox"
          :checked="allOnPageSelected"
          :indeterminate.prop="somePageSelected && !allOnPageSelected"
          aria-label="Select all groups on this page"
          :disabled="loading || !rows.length"
          @change="toggleSelectAllPage"
        />
      </template>
      <template #cell-select="{ row }">
        <input
          type="checkbox"
          :checked="isRowSelected(toGroup(row).id)"
          :aria-label="`Select ${toGroup(row).name}`"
          :disabled="loading"
          @change="toggleRow(toGroup(row).id)"
        />
      </template>
      <template #cell-name="{ row }">
        <span class="admin-groups__name">{{ toGroup(row).name }}</span>
      </template>
      <template #cell-members="{ row }">
        {{ toGroup(row).members.length }} student{{ toGroup(row).members.length === 1 ? '' : 's' }}
      </template>
      <template #cell-mentor="{ row }">
        <span v-if="toGroup(row).mentor">{{ toGroup(row).mentor!.name }}</span>
        <span v-else class="admin-groups__unmatched">Unassigned</span>
      </template>
      <template #cell-createdAt="{ row }">
        {{ formatDateAU(toGroup(row).createdAt) }}
      </template>
      <template #cell-actions="{ row }">
        <div class="admin-groups__row-actions">
          <button type="button" class="btn btn-sm btn-outline" @click.stop="openDetail(toGroup(row))">
            View
          </button>
          <button type="button" class="btn btn-sm btn-outline" @click.stop="openRename(toGroup(row))">
            Rename
          </button>
        </div>
      </template>
    </AdminDataTable>

    <GroupDetailModal v-model="detailOpen" :group="detailGroup" @changed="onDetailChanged" />

    <!-- Bulk delete confirm (forces the DELETE keyword when select-all / force) -->
    <ConfirmDialog
      v-model="bulkDelete.open"
      title="Delete groups"
      :message="bulkDeleteMessage"
      confirm-label="Delete"
      variant="danger"
      :busy="busy"
      :disabled="deleteConfirmBlocked"
      @confirm="runBulkDelete"
    >
      <p v-if="error" class="admin-groups__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ error }}</span>
      </p>
      <label class="admin-groups__force-toggle">
        <input v-model="bulkForce" type="checkbox" />
        <span>
          Force delete — also permanently delete any hosted workshops linked to these groups.
          Required to remove groups that still have one.
        </span>
      </label>
      <p v-if="bulkForce" class="admin-groups__force-warning">
        This destroys that content too, not just the group, and cannot be undone.
      </p>
      <div class="admin-groups__delete-type">
        <label class="admin-groups__delete-confirm-label" for="bulk-delete-confirm">
          Type <span class="admin-groups__delete-keyword">DELETE</span> to confirm
        </label>
        <input
          id="bulk-delete-confirm"
          v-model="deleteConfirmText"
          class="form-input"
          autocomplete="off"
          placeholder="DELETE"
        />
      </div>
      <p v-if="bulkDeleteProgress" class="admin-groups__delete-progress">
        Deleting... {{ bulkDeleteProgress.done }} of {{ bulkDeleteProgress.total }}
      </p>
    </ConfirmDialog>

    <FormSheet
      v-model="formOpen"
      :title="formMode === 'create' ? 'New group' : 'Rename group'"
      :description="formMode === 'create'
        ? 'Leave the name blank to auto-generate the next group name.'
        : undefined"
    >
      <form class="admin-groups__form" @submit.prevent="submitForm">
        <label class="admin-groups__form-field">
          <span class="admin-groups__filter-label">Group name</span>
          <input
            v-model="formName"
            type="text"
            :placeholder="formMode === 'create' ? nextNamePreview || 'BTF#' : ''"
          />
        </label>
        <p v-if="formError" class="admin-groups__error" role="alert">{{ formError }}</p>
      </form>

      <template #footer>
        <button type="button" class="btn btn-outline" :disabled="busy" @click="formOpen = false">
          Cancel
        </button>
        <button type="button" class="btn" :disabled="busy" @click="submitForm">
          {{ busy ? 'Saving...' : formMode === 'create' ? 'Create' : 'Save' }}
        </button>
      </template>
    </FormSheet>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import AdminDataTable, { type AdminColumn, type SortState } from '@/components/admin/AdminDataTable.vue'
import BulkActionsBar from '@/components/admin/BulkActionsBar.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import GroupDetailModal from '@/components/admin/groups/GroupDetailModal.vue'
import MatchedGroupsPanel from '@/components/admin/groups/MatchedGroupsPanel.vue'
import {
  fetchAdminGroupList,
  createGroup,
  updateGroup,
  fetchNextGroupName,
  bulkDeleteGroups,
  type AdminGroupDetail,
  type GroupListDetailParams
} from '@/utils/adminAPI'
import { formatDateAU } from '@/utils/date'

// "Groups" (the list built here) and "Matched Groups" (confirmed mentor
// assignments, mentor replace/unassign) are tabs on one page — matching the
// reference app, which nests both under one "Groups & Matching" section
// rather than giving Matched Groups its own top-level admin route.
const activeTab = ref<'groups' | 'matched'>('groups')

const columns: AdminColumn[] = [
  { key: 'select', label: '', width: '42px' },
  { key: 'name', label: 'Name', sortable: true },
  { key: 'members', label: 'Members', sortable: true },
  { key: 'mentor', label: 'Mentor', sortable: true },
  { key: 'createdAt', label: 'Created', sortable: true },
  { key: 'actions', label: '', align: 'right' }
]

const toGroup = (row: Record<string, unknown>) => row as unknown as AdminGroupDetail

const rows = ref<AdminGroupDetail[]>([])
const loading = ref(false)
const error = ref('')

const page = ref(1)
const limit = ref(25)
const totalCount = ref(0)

const searchInput = ref('')
const mentorStatus = ref('')
const sortState = ref<SortState>({ key: 'createdAt', direction: 'desc' })

let searchDebounce: ReturnType<typeof setTimeout> | undefined

const loadGroups = async () => {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchAdminGroupList({
      page: page.value,
      limit: limit.value,
      searchGroup: searchInput.value || undefined,
      mentorStatus: mentorStatus.value || undefined,
      sortBy: sortState.value.key,
      sortOrder: sortState.value.direction
    })
    rows.value = data.items
    totalCount.value = data.total
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load groups.'
  } finally {
    loading.value = false
  }
}

onMounted(loadGroups)

watch(searchInput, () => {
  if (searchDebounce) clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => {
    page.value = 1
    clearSelection()
    loadGroups()
  }, 300)
})

watch(mentorStatus, () => {
  page.value = 1
  clearSelection()
  loadGroups()
})

const onSortChange = (next: SortState) => {
  sortState.value = next
  page.value = 1
  clearSelection()
  loadGroups()
}

const onPageChange = (next: number) => {
  page.value = next
  loadGroups()
}

const onPageSizeChange = (size: number) => {
  limit.value = size
  page.value = 1
  loadGroups()
}

// --- Selection -------------------------------------------------------------
// Row selection is owned entirely here, not through AdminDataTable's built-in
// `selectable`/`:selected` mechanism — that path routes every toggle through
// a derived Set the child recomputes from its own props snapshot, emits back
// up, and this page then has to reconcile into its own state. That round trip
// turned out to be unreliable in practice (state silently stopped tracking
// unchecks in testing). A single Set mutated directly by our own toggle
// functions, read directly by our own checkbox bindings, removes that extra
// hop entirely — one source of truth, no reconciliation step to go stale.
const selectedIds = ref<Set<number>>(new Set())
const selectAllMatching = ref(false)
const excludedIds = ref<Set<number>>(new Set())

const pageIds = computed(() => rows.value.map((row) => row.id))
const pageRowCount = computed(() => rows.value.length)

const isRowSelected = (id: number): boolean =>
  selectAllMatching.value ? !excludedIds.value.has(id) : selectedIds.value.has(id)

const excludedCount = computed(() => excludedIds.value.size)
const effectiveSelectAllCount = computed(() => Math.max(0, totalCount.value - excludedCount.value))
const bulkCount = computed(() => (selectAllMatching.value ? effectiveSelectAllCount.value : selectedIds.value.size))

const allOnPageSelected = computed(
  () => pageIds.value.length > 0 && pageIds.value.every((id) => isRowSelected(id))
)
const somePageSelected = computed(() => pageIds.value.some((id) => isRowSelected(id)))

const selectionBanner = computed(
  () => selectAllMatching.value || (allOnPageSelected.value && totalCount.value > pageRowCount.value)
)

// Filters/search/sort redefine the matching set, so drop the selection (see
// the watchers/onSortChange above).
const clearSelection = () => {
  selectedIds.value = new Set()
  selectAllMatching.value = false
  excludedIds.value = new Set()
}

const setRowSelected = (id: number, selected: boolean) => {
  if (selectAllMatching.value) {
    const next = new Set(excludedIds.value)
    if (selected) next.delete(id)
    else next.add(id)
    excludedIds.value = next
    return
  }
  const next = new Set(selectedIds.value)
  if (selected) next.add(id)
  else next.delete(id)
  selectedIds.value = next
}

const toggleRow = (id: number) => setRowSelected(id, !isRowSelected(id))

const toggleSelectAllPage = () => {
  const makeSelected = !allOnPageSelected.value
  pageIds.value.forEach((id) => setRowSelected(id, makeSelected))
}

const selectAllMatchingNow = () => {
  selectedIds.value = new Set()
  excludedIds.value = new Set()
  selectAllMatching.value = true
}

// --- Bulk delete -----------------------------------------------------------
// "select all matching" hard-deletes in chunks: each call caps how many
// groups it removes and reports how many are still left, so the browser
// loops (feeding back everything already attempted as excludeIds) instead of
// asking the backend to cascade-delete a huge set in one transaction.
const BULK_DELETE_CHUNK = 25

const bulkFilters = computed<GroupListDetailParams>(() => ({
  searchGroup: searchInput.value || undefined,
  mentorStatus: mentorStatus.value || undefined
}))

const bulkDelete = ref({ open: false })
const bulkForce = ref(false)
const deleteConfirmText = ref('')
const bulkDeleteProgress = ref<{ done: number; total: number } | null>(null)

const bulkDeleteMessage = computed(() => {
  const count = bulkCount.value
  const base = `This permanently removes the selected ${count === 1 ? 'group' : 'groups'} and all related data (chat history, tasks, memberships). This cannot be undone.`
  return selectAllMatching.value
    ? `${base} Every group matching the current filters will be deleted.`
    : base
})

const deleteConfirmBlocked = computed(
  () => (selectAllMatching.value || bulkForce.value) && deleteConfirmText.value !== 'DELETE'
)

const confirmBulkDelete = () => {
  bulkForce.value = false
  deleteConfirmText.value = ''
  error.value = ''
  bulkDelete.value = { open: true }
}

const runBulkDelete = async () => {
  busy.value = true
  try {
    if (selectAllMatching.value) {
      const expectedCount = bulkCount.value
      let excludeIds = [...excludedIds.value].map(Number)
      let done = 0
      bulkDeleteProgress.value = { done: 0, total: expectedCount }

      for (;;) {
        const { data } = await bulkDeleteGroups({
          selectAll: true,
          filters: bulkFilters.value,
          excludeIds,
          expectedCount,
          force: bulkForce.value,
          limit: BULK_DELETE_CHUNK
        })
        if (!data) break
        done += data.deletedIds.length
        excludeIds = [...excludeIds, ...data.deletedIds, ...data.failedIds, ...data.notFoundIds]
        bulkDeleteProgress.value = { done, total: expectedCount }
        if (!data.remaining) break
      }
    } else {
      await bulkDeleteGroups({
        groupIds: [...selectedIds.value],
        force: bulkForce.value
      })
    }
    bulkDelete.value = { open: false }
    clearSelection()
    await loadGroups()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Bulk delete failed.'
  } finally {
    busy.value = false
    bulkDeleteProgress.value = null
  }
}

// --- Detail modal --------------------------------------------------------

const detailOpen = ref(false)
const detailGroup = ref<AdminGroupDetail | null>(null)

const openDetail = (group: AdminGroupDetail) => {
  detailGroup.value = group
  detailOpen.value = true
}

// Member removal changes this group's student count (and the removed
// student's own group membership elsewhere), so refresh the list rather than
// patching the row locally.
const onDetailChanged = () => {
  loadGroups()
}

// --- Create / rename ---------------------------------------------------

const formOpen = ref(false)
const formMode = ref<'create' | 'rename'>('create')
const formName = ref('')
const formGroupId = ref<string | number | null>(null)
const formError = ref('')
const busy = ref(false)
const nextNamePreview = ref('')

const openCreate = async () => {
  formMode.value = 'create'
  formName.value = ''
  formGroupId.value = null
  formError.value = ''
  formOpen.value = true
  // Every open must hit the server; the previewed name is not reserved and
  // goes stale as soon as anyone else creates a group.
  nextNamePreview.value = ''
  try {
    nextNamePreview.value = await fetchNextGroupName()
  } catch {
    // Non-fatal: the create form still works with a blank/auto name, just
    // without a live placeholder.
  }
}

const openRename = (group: AdminGroupDetail) => {
  formMode.value = 'rename'
  formName.value = group.name
  formGroupId.value = group.id
  formError.value = ''
  formOpen.value = true
}

const submitForm = async () => {
  if (formMode.value === 'rename' && !formName.value.trim()) {
    formError.value = 'Group name is required'
    return
  }

  busy.value = true
  formError.value = ''
  try {
    const result =
      formMode.value === 'create'
        ? await createGroup(formName.value.trim() || undefined)
        : await updateGroup(formGroupId.value!, formName.value.trim())

    if (!result.data) {
      formError.value = result.msg || 'Something went wrong.'
      return
    }

    formOpen.value = false
    await loadGroups()
  } catch (err) {
    formError.value = err instanceof Error ? err.message : 'Something went wrong.'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.admin-groups__selection-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
  padding: 0.7rem 1rem;
  margin-bottom: 1rem;
  border: 1px solid rgba(1, 113, 81, 0.25);
  border-radius: 8px;
  background-color: rgba(1, 113, 81, 0.06);
  color: var(--charcoal);
  font-size: 0.875rem;
}

.admin-groups__selection-icon {
  margin-right: 0.4rem;
  color: var(--dark-green);
}

.admin-groups__selection-link {
  border: none;
  background: none;
  padding: 0;
  font: inherit;
  color: var(--dark-green);
  font-weight: 600;
  text-decoration: underline;
  cursor: pointer;
}

.admin-groups__force-toggle {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--charcoal);
}

.admin-groups__force-toggle input {
  margin-top: 0.15rem;
  accent-color: var(--danger);
}

.admin-groups__force-warning {
  margin: 0.5rem 0 0;
  padding: 0.55rem 0.7rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--risk);
  font-size: 0.8rem;
}

.admin-groups__delete-type {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-top: 0.75rem;
}

.admin-groups__delete-confirm-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.admin-groups__delete-keyword {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-weight: 700;
  color: var(--danger);
}

.admin-groups__delete-type input {
  padding: 0.5rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
  font: inherit;
}

.admin-groups__delete-progress {
  margin: 0.75rem 0 0;
  color: var(--text-muted);
  font-size: 0.8rem;
}

.admin-groups__tabs {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1.25rem;
  border-bottom: 1px solid var(--border-light);
}

.admin-groups__tab {
  padding: 0.6rem 1rem;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  font: inherit;
  font-weight: 600;
  color: var(--text-muted);
  cursor: pointer;
}

.admin-groups__tab:hover {
  color: var(--charcoal);
}

.admin-groups__tab--active {
  color: var(--dark-green);
  border-bottom-color: var(--dark-green);
}

.admin-groups__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.admin-groups__search {
  position: relative;
  flex: 1 1 260px;
  max-width: 360px;
}

.admin-groups__search-icon {
  position: absolute;
  top: 50%;
  left: 0.9rem;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 0.85rem;
}

.admin-groups__search input {
  width: 100%;
  padding: 0.55rem 0.75rem 0.55rem 2.25rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  font-size: 0.9rem;
}

.admin-groups__filter-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.admin-groups__filter-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-muted);
}

.admin-groups__filter-field select {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  font-size: 0.9rem;
  background-color: var(--white);
}

.admin-groups__error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
  color: var(--danger);
  font-size: 0.9rem;
}

.admin-groups__row-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.admin-groups__name {
  font-weight: 600;
  color: var(--charcoal);
}

.admin-groups__unmatched {
  color: var(--text-muted);
}

.admin-groups__form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.admin-groups__form-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.admin-groups__form-field input {
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  font-size: 0.9rem;
}
</style>
