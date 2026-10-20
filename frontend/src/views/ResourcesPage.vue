<template>
  <div class="content-area">
    <div class="resource-header page-header">
      <div>
        <h1 class="page-title">Resource Library</h1>
        <p class="page-subtitle">Browse available files and pages.</p>
      </div>
      <div v-if="isAdmin" class="resource-header__actions">
        <button
          class="btn btn-primary"
          type="button"
          @click="openCreateResource"
        >
          <i class="fas fa-plus"></i>
          <span>Add Resource</span>
        </button>
      </div>
    </div>

    <div v-if="error" class="card resource-state resource-state-error">
      <h3>Error</h3>
      <p>{{ error }}</p>
      <button @click="loadResources" class="btn btn-primary">Retry</button>
    </div>

    <!-- Bulk Actions Bar for Admins -->
    <BulkActionsBar
      v-if="isAdmin && selectedResourceIds.length && !loading"
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
         table sorts them: latest modified first, or by Name or Modified.
         Label sits after Search. -->
    <AppDataTable
      :columns="columns"
      :rows="tableRows"
      row-key="id"
      :loading="loading"
      :selectable="isAdmin"
      :selected="selectedResourceIds"
      :default-sort="DEFAULT_SORT"
      v-model:search="searchQuery"
      search-placeholder="Name or description"
      empty-message="No resources found. Try changing your search or filters."
      clickable-rows
      :action-columns="2"
      @update:selected="onSelectedChange"
      @row-click="openResourceDetail(toResource($event).id)"
    >
      <template #filters>
        <label class="resource-filter">
          <span class="resource-filter-label">Label</span>
          <AppSelect v-model="selectedLabelId" aria-label="Filter by label" :options="labelFilterOptions" />
          <span v-if="getFieldError('label_id')" class="field-error">{{ getFieldError('label_id') }}</span>
        </label>

        <label class="resource-filter">
          <span class="resource-filter-label">Type</span>
          <AppSelect v-model="selectedType" aria-label="Filter by type" :options="typeFilterOptions" />
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
        <span class="resource-name-cell">{{ toResource(row).name }}</span>
      </template>

      <template #cell-labels="{ row }">
        <span v-if="toResource(row).labels?.length" class="label-list">
          <span v-for="label in toResource(row).labels" :key="label.id" class="label-chip">
            {{ label.name }}
          </span>
        </span>
        <span v-else class="muted">None</span>
      </template>

      <!-- Edit | Delete, each in its own column, as the other tables do.
           Clicking its name opens it. -->
      <template v-if="isAdmin" #actions="{ row, column }">
        <button
          v-if="column === 0"
          type="button"
          class="btn btn-sm btn-outline"
          @click.stop="openEditResource(toResource(row))"
        >
          Edit
        </button>
        <button
          v-else
          type="button"
          class="btn btn-sm btn-outline"
          @click.stop="confirmDeleteResource(toResource(row))"
        >
          Delete
        </button>
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
import { useRouter } from 'vue-router'
import AppDataTable, { type DataTableColumn, type DataTableSort } from '@/components/AppDataTable.vue'
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
  type ResourceKind,
  type ResourceLabel,
  type ResourceType
} from '../utils/resourcesAPI'
import { ApiError } from '../utils/apiError'
import { formatDayMonth } from '../utils/date'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const isAdmin = computed(() => auth.isAdmin)

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
const selectedLabelId = ref('')
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

// The table's columns; Name and Modified sort, Modified by its time.
const columns: DataTableColumn[] = [
  { key: 'icon', label: '', sortable: false, cellClass: () => 'resource-icon-cell' },
  // Names the row, though the icon comes first.
  { key: 'name', label: 'Name', wrap: true, primary: true },
  { key: 'type', label: 'Type', sortable: false },
  { key: 'kind', label: 'Kind', sortable: false },
  { key: 'labels', label: 'Labels', wrap: true, sortable: false },
  {
    key: 'modified',
    label: 'Modified',
    sortValue: (row) => Date.parse(String((row.resource as Resource).uploaded_at)) || 0,
  },
]
// Latest modified first, until a heading is clicked.
const DEFAULT_SORT: DataTableSort = { key: 'modified', direction: 'desc' }

const tableRows = computed(() =>
  resources.value.map((resource) => ({
    id: resource.id,
    // The first column's text names the row for its tick box.
    icon: resource.name,
    name: resource.name,
    type: getResourceTypeLabel(resource),
    kind: getResourceKindLabel(resource.kind),
    labels: (resource.labels ?? []).map((label) => label.name).join(', '),
    modified: formatDate(resource.uploaded_at),
    resource,
  })),
)
const toResource = (row: Record<string, unknown>) => row.resource as Resource

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

const getResourceKindLabel = (kind: ResourceKind): string => {
  const labelsByKind: Record<string, string> = {
    file: 'File',
    page: 'Page',
    attachment: 'Attachment'
  }
  return labelsByKind[kind] || formatTypeName(kind)
}

const getResourceIcon = (resource: Resource): string => {
  const mimeType = resource.file_mime_type?.toLowerCase() || ''
  if (resource.kind === 'page') return 'fas fa-globe'
  if (resource.kind === 'attachment') return 'fas fa-paperclip'
  if (mimeType.includes('pdf')) return 'fas fa-file-pdf'
  if (mimeType.startsWith('image/')) return 'fas fa-file-image'
  if (mimeType.startsWith('video/')) return 'fas fa-file-video'
  if (mimeType.startsWith('audio/')) return 'fas fa-file-audio'
  return 'fas fa-file-alt'
}

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
    await Promise.all([loadResources(), loadResourceLookups()])
  } catch (err: any) {
    console.error('Failed to delete resource:', err)
    error.value = err?.message || 'Failed to delete resource.'
  } finally {
    busy.value = false
  }
}

const onResourceSaved = async () => {
  await Promise.all([loadResources(), loadResourceLookups()])
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
    await Promise.all([loadResources(), loadResourceLookups()])
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
    await Promise.all([loadResources(), loadResourceLookups()])
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

/* Label and the other filters, in the table's search card, drawn like Search. */
.resource-filter {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.resource-filter-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.resource-filter .app-select {
  min-width: 9rem;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  font-size: 0.9rem;
  font-family: inherit;
  background-color: var(--surface-elevated);
  color: var(--teal);
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
