<template>
  <div class="content-area">
    <div class="resource-header page-header">
      <div>
        <h1 class="page-title">Resource Library</h1>
        <p class="page-subtitle">Browse available files and pages.</p>
      </div>
      <!-- An admin sees the table students, mentors and supervisors see, and
           back to their own. -->
      <div v-if="isAdmin" class="resource-header__actions">
        <button
          class="btn btn-outline"
          type="button"
          :aria-pressed="othersView"
          data-test="others-view"
          @click="othersView = !othersView"
        >
          <i class="fas" :class="othersView ? 'fa-user-shield' : 'fa-eye'" aria-hidden="true"></i>
          <span>{{ othersView ? 'Show Admin View' : "Show Others' View" }}</span>
        </button>
      </div>
    </div>
    <!-- When each resource reaches students, mentors and supervisors (what
         Management > Challenge Start had, as Release Resources). -->
    <p v-if="adminView" class="resource-release-hint">
      Shown, a resource is open now to everyone it's for. A hidden resource is released automatically at the
      start of its <strong>Release At</strong> date (Sydney time). Without a date, it stays hidden. Admins always
      see every resource. <strong>Last Released</strong> is when it was released last year.
    </p>
    <p v-else-if="isAdmin" class="resource-release-hint" data-test="others-view-note">
      As students, mentors and supervisors see it: the resources released to them now. Each sees only those
      for their role.
    </p>
    <p v-if="releaseError" class="resource-release-error" role="alert">{{ releaseError }}</p>

    <div v-if="error" class="card resource-state resource-state-error">
      <h3>Error</h3>
      <p>{{ error }}</p>
      <button @click="loadResources" class="btn btn-primary">Retry</button>
    </div>

    <!-- Bulk Actions Bar for Admins -->
    <BulkActionsBar
      v-if="adminView && selectedResourceIds.length && !loading"
      :count="selectedResourceIds.length"
      noun="resource"
      :disabled="batchBusy"
      @clear="clearSelection"
    >
      <button
        type="button"
        class="btn btn-sm btn-outline"
        :disabled="batchBusy"
        @click="openBatchAccessModal"
      >
        <i class="fas fa-user-shield" aria-hidden="true"></i>
        <span>Edit Access</span>
      </button>
      <button
        type="button"
        class="btn btn-sm btn-danger"
        :disabled="batchBusy"
        @click="confirmBulkDelete"
      >
        <i class="fas fa-trash-can" aria-hidden="true"></i>
        <span>Delete</span>
      </button>
    </BulkActionsBar>

    <!-- The shared table. The server searches and filters the rows, and the
         table sorts them: latest modified first, or by Name or Modified; an
         admin's by when each was released last year, as Release Resources
         was. Label sits after Search. Each view keeps its own sort. -->
    <AppDataTable
      :key="adminView ? 'admin' : 'others'"
      :columns="adminView ? adminColumns : columns"
      :rows="adminView ? tableRows : othersRows"
      row-key="id"
      :loading="loading"
      :selectable="adminView"
      :selected="selectedResourceIds"
      :default-sort="adminView ? ADMIN_SORT : DEFAULT_SORT"
      :focus-row="focusResource"
      v-model:search="searchQuery"
      search-placeholder="Name or description"
      empty-message="No resources found. Try changing your search or filters."
      clickable-rows
      @update:selected="onSelectedChange"
      @row-click="openResourceDetail(toResource($event).id)"
    >
      <template v-if="adminView" #search-side>
        <button class="btn btn-primary btn-sm" type="button" @click="openCreateResource">
          <i class="fas fa-plus" aria-hidden="true"></i>
          <span>Add Resource</span>
        </button>
      </template>
      <template #filters>
        <label class="table-filter-field">
          <span class="table-filter-label">Label</span>
          <AppSelect v-model="selectedLabelId" class="table-filter" aria-label="Filter by label" :options="labelFilterOptions" />
          <span v-if="getFieldError('label_id')" class="field-error">{{ getFieldError('label_id') }}</span>
        </label>

        <label class="table-filter-field">
          <span class="table-filter-label">Type</span>
          <AppSelect v-model="selectedType" class="table-filter" aria-label="Filter by type" :options="typeFilterOptions" />
        </label>

      </template>

      <!-- The icon's own column, with no heading to see. -->
      <template #head-icon>
        <span class="sr-only">Icon</span>
      </template>
      <template #cell-icon="{ row }">
        <i class="resource-row-icon" :class="getResourceIcon(toResource(row))" aria-hidden="true"></i>
      </template>

      <template #cell-name="{ row }">
        <span class="resource-name-cell" :class="{ 'resource-name-cell--wide': !adminView }">
          {{ toResource(row).name }}
        </span>
      </template>

      <template #cell-labels="{ row }">
        <span v-if="toResource(row).labels?.length" class="label-list">
          <span v-for="label in toResource(row).labels" :key="label.id" class="label-chip">
            {{ label.name }}
          </span>
        </span>
        <span v-else class="muted">None</span>
      </template>

      <!-- An admin's: Edit (Delete is in its panel, or ticked rows' bar),
           then whether it's shown and when it's released. Clicking its name
           opens it. -->
      <template #cell-edit="{ row }">
        <button
          type="button"
          class="btn btn-sm btn-outline"
          :data-test="`resource-edit-${row.id}`"
          @click.stop="openEditResource(toResource(row))"
        >
          Edit
        </button>
      </template>
      <template #cell-shown="{ row }">
        <HideShowSwitch
          v-if="row.release"
          :on="Boolean(toRelease(row).shown)"
          :disabled="savingId === row.id"
          :label="`Show ${row.name}`"
          :data-test="`release-shown-${row.id}`"
          @change="saveRelease(Number(row.id), { shown: $event })"
        />
      </template>
      <template #cell-release="{ row }">
        <AppDatePicker
          v-if="row.release"
          :model-value="toRelease(row).release_on"
          class="app-input app-input--compact resource-release-date"
          :clearable="false"
          :disabled="savingId === row.id"
          placeholder="No date"
          :data-test="`release-date-${row.id}`"
          @update:model-value="saveRelease(Number(row.id), { release_on: $event || null })"
        />
      </template>
    </AppDataTable>

    <!-- Admin Side Panels & Confirm Dialogs -->
    <AdminResourceFormSheet
      v-if="isAdmin"
      v-model="formSheetOpen"
      :resource="formEditResource"
      :busy="busy"
      @saved="onResourceSaved"
      @delete="onFormEditorDelete"
    />

    <AdminResourceBatchAccessModal
      v-if="isAdmin"
      v-model="batchAccessModalOpen"
      :count="selectedResourceIds.length"
      :busy="batchBusy"
      @apply="onApplyBatchAccess"
    />

    <ConfirmDialog
      v-if="isAdmin"
      v-model="deleteConfirm.open"
      title="Delete Resource"
      :message="deleteConfirm.message"
      confirm-label="Delete"
      variant="danger"
      :busy="busy"
      @confirm="runDeleteResource"
    />

    <ConfirmDialog
      v-if="isAdmin"
      v-model="bulkDeleteConfirm.open"
      title="Delete Resources"
      :message="bulkDeleteConfirm.message"
      confirm-label="Delete"
      variant="danger"
      :busy="batchBusy"
      @confirm="runBulkDeleteResources"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppDataTable, { type DataTableColumn, type DataTableSort } from '@/components/AppDataTable.vue'
import AppDatePicker from '@/components/AppDatePicker.vue'
import AppSelect, { type AppSelectOption } from '@/components/AppSelect.vue'
import BulkActionsBar from '@/components/admin/BulkActionsBar.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import AdminResourceBatchAccessModal from '@/components/admin/resources/AdminResourceBatchAccessModal.vue'
import AdminResourceFormSheet from '@/components/admin/resources/AdminResourceFormSheet.vue'
import {
  deleteAdminResource,
  updateAdminResource
} from '@/utils/adminAPI'
import {
  fetchResources,
  fetchResourceLabels,
  fetchResourceTypes,
  type Resource,
  type ResourceLabel,
  type ResourceType
} from '../utils/resourcesAPI'
import { ApiError, apiErrorFromUnknown } from '../utils/apiError'
import { formatDayMonth, formatShortDate } from '../utils/date'
import { fetchResourceReleases, saveResourceRelease, type ResourceReleaseRow } from '../utils/managementAPI'
import { resourceFileIcon } from '../utils/resource'
import { useAuthStore } from '../stores/auth'
import HideShowSwitch from './management/HideShowSwitch.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const isAdmin = computed(() => auth.isAdmin)
// An admin's own table, or the one students, mentors and supervisors see.
const othersView = ref(false)
const adminView = computed(() => isAdmin.value && !othersView.value)
// Back from a resource's page, the resource it was: its row brought into
// view, on whichever page of the table has it.
const focusResource = computed(() => (typeof route.query.resource === 'string' ? route.query.resource : undefined))

const busy = ref(false)
const formSheetOpen = ref(false)
const formEditResource = ref<Resource | null>(null)
const deleteConfirm = ref<{
  open: boolean
  resource: Resource | null
  message: string
}>({
  open: false,
  resource: null,
  message: ''
})

const selectedResourceIds = ref<number[]>([])
const batchBusy = ref(false)
const batchAccessModalOpen = ref(false)
const bulkDeleteConfirm = ref<{
  open: boolean
  message: string
}>({
  open: false,
  message: ''
})

const resources = ref<Resource[]>([])
const labels = ref<ResourceLabel[]>([])
const resourceTypes = ref<ResourceType[]>([])
const loading = ref(false)
const error = ref('')
const fieldErrors = ref<Record<string, string[]>>({})

const searchQuery = ref('')
const selectedType = ref('')
// The Label and Type filters' choices.
const labelFilterOptions = computed<AppSelectOption[]>(() => [
  { value: '', label: 'All labels' },
  ...labels.value.map((label) => ({ value: String(label.id), label: `${label.name} (${label.resource_count ?? 0})` }))
])
const typeFilterOptions = computed<AppSelectOption[]>(() => [
  { value: '', label: 'All types' },
  ...resourceTypes.value.map((type) => ({ value: type.type_name, label: formatTypeName(type.type_name) }))
])
// Seeded from ?label= so another page can link straight to one shelf of the
// library. The Support Centre uses this to send someone to the help articles
// for the topic they clicked, instead of dropping them in the full list to
// find it themselves.
const selectedLabelId = ref(
  typeof route.query.label === 'string' ? route.query.label : ''
)
let loadSequence = 0

const getFieldError = (field: string): string => fieldErrors.value[field]?.[0] || ''

const loadResources = async (): Promise<void> => {
  if (!auth.isAuthenticated) {
    error.value = 'You must be logged in to view resources'
    return
  }

  const sequence = ++loadSequence
  loading.value = true
  error.value = ''
  fieldErrors.value = {}
  try {
    const response = await fetchResources({
      search: searchQuery.value.trim() || undefined,
      type: selectedType.value || undefined,
      label_id: selectedLabelId.value ? Number(selectedLabelId.value) : undefined,
      page: 1,
      page_size: 100
    })
    if (sequence === loadSequence) {
      resources.value = response.results
    }
  } catch (err: unknown) {
    if (sequence === loadSequence) {
      if (err instanceof ApiError && err.fields) {
        fieldErrors.value = err.fields
        error.value = ''
      } else {
        error.value = err instanceof Error ? err.message : 'Failed to load resources'
      }
    }
  } finally {
    if (sequence === loadSequence) {
      loading.value = false
    }
  }
}

const loadResourceLookups = async (): Promise<void> => {
  try {
    const [nextLabels, nextTypes] = await Promise.all([
      fetchResourceLabels(),
      fetchResourceTypes()
    ])
    labels.value = nextLabels
    resourceTypes.value = nextTypes
  } catch {
    labels.value = []
    resourceTypes.value = []
  }
}

// When each resource reaches students, mentors and supervisors, for an
// admin: shown or hidden, its release date, and last year's release.
const releases = ref<Map<number, ResourceReleaseRow>>(new Map())
const releaseError = ref('')
const savingId = ref<number | null>(null)

const loadReleases = async (): Promise<void> => {
  if (!isAdmin.value) return
  try {
    releases.value = new Map((await fetchResourceReleases()).map((row) => [row.id, row]))
  } catch (err) {
    releaseError.value = apiErrorFromUnknown(err, 'When each resource is released could not be loaded.').message
  }
}

// Shown or hidden, or its date, saved as it's changed: its row as the server has it then.
const saveRelease = async (id: number, change: { shown?: boolean; release_on?: string | null }) => {
  savingId.value = id
  releaseError.value = ''
  try {
    const saved = await saveResourceRelease(id, change)
    releases.value = new Map(releases.value).set(saved.id, saved)
  } catch (err) {
    releaseError.value = apiErrorFromUnknown(err, 'The change could not be saved.').message
  } finally {
    savingId.value = null
  }
}

// The table's columns; Name and Modified sort, Modified by its time.
const columns: DataTableColumn[] = [
  { key: 'icon', label: '', sortable: false, cellClass: () => 'resource-icon-cell' },
  // Names the row, though the icon comes first.
  { key: 'name', label: 'Name', wrap: true, primary: true },
  { key: 'type', label: 'Type', sortable: false },
  { key: 'labels', label: 'Labels', wrap: true, sortable: false },
  {
    key: 'modified',
    label: 'Modified',
    sortValue: (row) => Date.parse(String((row.resource as Resource).uploaded_at)) || 0,
  },
]
// Latest modified first, until a heading is clicked.
const DEFAULT_SORT: DataTableSort = { key: 'modified', direction: 'desc' }

// Last year's release by its time, those with none last.
const lastReleased = (row: Record<string, unknown>) => {
  const at = (row.release as ResourceReleaseRow | undefined)?.last_released_at
  return at ? Date.parse(at) : Number.MAX_SAFE_INTEGER
}
// An admin's: the same, then Edit and when each is released.
const adminColumns: DataTableColumn[] = [
  ...columns,
  { key: 'edit', label: 'Edit', sortable: false },
  { key: 'shown', label: 'Show/Hide', sortable: false },
  { key: 'release', label: 'Release At', sortable: false },
  { key: 'last', label: 'Last Released', sortValue: lastReleased },
]
// By when each was released last year, so this year's can follow it.
const ADMIN_SORT: DataTableSort = { key: 'last', direction: 'asc' }

const tableRows = computed(() =>
  resources.value.map((resource) => {
    const release = releases.value.get(resource.id)
    return {
      id: resource.id,
      // The first column's text names the row for its tick box.
      icon: resource.name,
      name: resource.name,
      type: getResourceTypeLabel(resource),
      labels: (resource.labels ?? []).map((label) => label.name).join(', '),
      modified: formatDate(resource.uploaded_at),
      last: release?.last_released_at ? formatShortDate(release.last_released_at) : '—',
      release,
      resource,
    }
  }),
)
// What students, mentors and supervisors see: those released to them now
// (an admin's list has every resource; anyone else's only theirs).
const othersRows = computed(() =>
  isAdmin.value ? tableRows.value.filter((row) => row.release?.released !== false) : tableRows.value,
)
const toResource = (row: Record<string, unknown>) => row.resource as Resource
const toRelease = (row: Record<string, unknown>) => row.release as ResourceReleaseRow

const onSelectedChange = (keys: (string | number)[]) => {
  selectedResourceIds.value = keys.map(Number)
}

const openResourceDetail = (id: number): void => {
  router.push({ name: 'resource-detail', params: { id } })
}

// "9 Oct", in the set time.
const formatDate = (value: string): string => formatDayMonth(value) || 'Unknown'

const formatTypeName = (value?: string | null): string => {
  if (!value) return 'Resource'
  return value
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

const getResourceTypeLabel = (resource: Resource): string => {
  return formatTypeName(resource.type_name || resource.resource_type_detail?.type_name)
}

// Its icon, by its kind and a file's type (utils/resource).
const getResourceIcon = (resource: Resource): string => resourceFileIcon(resource)

const formatFileSize = (value?: number | null): string => {
  if (!Number.isFinite(value || 0) || !value || value <= 0) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = value
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

let searchTimer: any
watch([searchQuery, selectedType, selectedLabelId], () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    loadResources()
  }, 250)
})

const openCreateResource = () => {
  formEditResource.value = null
  formSheetOpen.value = true
}

const openEditResource = (resource: Resource) => {
  formEditResource.value = resource
  formSheetOpen.value = true
}

const confirmDeleteResource = (resource: Resource) => {
  deleteConfirm.value = {
    open: true,
    resource,
    message: `Are you sure you want to delete resource "${resource.name}"? This action cannot be undone.`
  }
}

const runDeleteResource = async () => {
  const target = deleteConfirm.value.resource
  if (!target?.id) return

  busy.value = true
  try {
    await deleteAdminResource(target.id)
    deleteConfirm.value.open = false
    deleteConfirm.value.resource = null
    await Promise.all([loadResources(), loadResourceLookups(), loadReleases()])
  } catch (err: any) {
    console.error('Failed to delete resource:', err)
    error.value = err?.message || 'Failed to delete resource.'
  } finally {
    busy.value = false
  }
}

const onResourceSaved = async () => {
  await Promise.all([loadResources(), loadResourceLookups(), loadReleases()])
}

const onFormEditorDelete = () => {
  const r = formEditResource.value
  formSheetOpen.value = false
  if (r) {
    confirmDeleteResource(r)
  }
}

const clearSelection = () => {
  selectedResourceIds.value = []
}

const openBatchAccessModal = () => {
  if (!selectedResourceIds.value.length) return
  batchAccessModalOpen.value = true
}

const onApplyBatchAccess = async (payload: { visibilityScope: 'role_based'; roleIds: number[] }) => {
  if (!selectedResourceIds.value.length) return
  batchBusy.value = true
  error.value = ''

  try {
    const ids = [...selectedResourceIds.value]
    const updates = {
      visibility_scope: payload.visibilityScope,
      role_ids: payload.roleIds
    }

    const results = await Promise.allSettled(
      ids.map((id) => updateAdminResource(id, updates))
    )

    const failed = results.filter((r) => r.status === 'rejected')
    if (failed.length > 0) {
      console.warn(`Batch access update partially failed: ${failed.length} of ${ids.length} failed.`)
    }

    batchAccessModalOpen.value = false
    clearSelection()
    await Promise.all([loadResources(), loadResourceLookups(), loadReleases()])
  } catch (err: any) {
    console.error('Batch access update failed:', err)
    error.value = err?.message || 'Failed to update access for selected resources.'
  } finally {
    batchBusy.value = false
  }
}

const confirmBulkDelete = () => {
  const count = selectedResourceIds.value.length
  if (!count) return

  bulkDeleteConfirm.value = {
    open: true,
    message: `Are you sure you want to delete ${count} selected ${count === 1 ? 'resource' : 'resources'}? This action cannot be undone.`
  }
}

const runBulkDeleteResources = async () => {
  const ids = [...selectedResourceIds.value]
  if (!ids.length) return

  batchBusy.value = true
  error.value = ''

  try {
    const results = await Promise.allSettled(
      ids.map((id) => deleteAdminResource(id))
    )

    const failed = results.filter((r) => r.status === 'rejected')
    if (failed.length > 0) {
      console.warn(`Bulk delete partially failed: ${failed.length} of ${ids.length} failed.`)
    }

    bulkDeleteConfirm.value.open = false
    clearSelection()
    await Promise.all([loadResources(), loadResourceLookups(), loadReleases()])
  } catch (err: any) {
    console.error('Failed to bulk delete resources:', err)
    error.value = err?.message || 'Failed to delete selected resources.'
  } finally {
    batchBusy.value = false
  }
}

onMounted(() => {
  loadResourceLookups()
  loadResources()
  loadReleases()
})

onBeforeUnmount(() => {
  window.clearTimeout(searchTimer)
})
</script>

<style scoped>
.resource-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.resource-header__actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.resource-state {
  align-items: center;
  display: flex;
  gap: 0.75rem;
}

.resource-state-error {
  align-items: flex-start;
  border-left: 4px solid var(--danger);
  flex-direction: column;
}

.field-error {
  color: var(--danger);
  font-size: 0.82rem;
  line-height: 1.25;
}

/* Just wide enough for the icon, close to the name after it. */
:deep(.resource-icon-cell) {
  width: 2.5rem;
  padding-right: 0;
}

/* Not .resource-icon: main.css has that as a card's big banner. */
.resource-row-icon {
  display: inline-block;
  width: 20px;
  color: var(--dark-green);
  text-align: center;
}

.resource-name-cell {
  display: block;
  font-weight: 600;
  min-width: 220px;
}

/* Without an admin's columns, the name has the room. */
.resource-name-cell--wide {
  min-width: 360px;
}

/* When each resource is released, said under the title, and its errors. */
.resource-release-hint {
  margin: 0 0 1rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.resource-release-error {
  margin: 0 0 1rem;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
  font-size: 0.9rem;
}

/* A date's width, in the row. */
.resource-release-date {
  width: 11rem;
  max-width: none;
}

.label-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.label-chip {
  background: var(--accent-green-soft);
  border: 1px solid rgba(1, 113, 81, 0.18);
  border-radius: 999px;
  color: var(--dark-green);
  display: inline-flex;
  font-size: 0.8rem;
  line-height: 1;
  padding: 0.35rem 0.55rem;
}

.muted {
  color: var(--text-muted);
}

@media (max-width: 720px) {
  .resource-header {
    flex-direction: column;
  }
}
</style>
