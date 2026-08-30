<template>
  <div class="content-area admin-groups">
    <div class="page-head">
      <div>
        <h1>Groups</h1>
        <p class="page-subtitle">Manage student groups and mentor assignments.</p>
      </div>
      <button type="button" class="btn btn-outline" @click="openCreate">
        <i class="fas fa-plus" aria-hidden="true"></i> New group
      </button>
    </div>

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
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import AdminDataTable, { type AdminColumn, type SortState } from '@/components/admin/AdminDataTable.vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import GroupDetailModal from '@/components/admin/groups/GroupDetailModal.vue'
import {
  fetchAdminGroupList,
  createGroup,
  updateGroup,
  fetchNextGroupName,
  type AdminGroupDetail
} from '@/utils/adminAPI'
import { formatDateAU } from '@/utils/date'

const columns: AdminColumn[] = [
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
    loadGroups()
  }, 300)
})

watch(mentorStatus, () => {
  page.value = 1
  loadGroups()
})

const onSortChange = (next: SortState) => {
  sortState.value = next
  page.value = 1
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
