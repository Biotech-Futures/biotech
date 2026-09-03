<template>
  <div class="content-area">
    <div class="resource-header">
      <div>
        <h1>Resource Library</h1>
        <p class="resource-subtitle">Browse available files and pages.</p>
      </div>
      <button
        v-if="isAdmin"
        class="btn btn-primary"
        type="button"
        @click="openCreateResource"
      >
        <i class="fas fa-upload"></i> Upload Resource
      </button>
    </div>

    <section class="resource-toolbar" aria-label="Resource filters">
      <label class="filter-field filter-field-search">
        <span class="filter-label">Search</span>
        <input
          v-model="searchQuery"
          type="search"
          class="form-control resource-search"
          placeholder="Search by name or description..."
        />
      </label>

      <label class="filter-field">
        <span class="filter-label">Type</span>
        <select v-model="selectedType" class="form-control resource-select" aria-label="Filter by type">
          <option value="">All types</option>
          <option v-for="type in resourceTypes" :key="type.id" :value="type.type_name">
            {{ formatTypeName(type.type_name) }}
          </option>
        </select>
      </label>

      <label class="filter-field">
        <span class="filter-label">Since</span>
        <input
          v-model="sinceDate"
          type="date"
          class="form-control resource-date"
          aria-label="Filter resources uploaded since"
        />
        <span v-if="getFieldError('since')" class="field-error">{{ getFieldError('since') }}</span>
      </label>

      <label class="filter-field">
        <span class="filter-label">Until</span>
        <input
          v-model="untilDate"
          type="date"
          class="form-control resource-date"
          aria-label="Filter resources uploaded until"
        />
        <span v-if="getFieldError('until')" class="field-error">{{ getFieldError('until') }}</span>
      </label>

      <label class="filter-field">
        <span class="filter-label">Sort</span>
        <select v-model="sortOrder" class="form-control resource-select" aria-label="Sort resources">
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
          <option value="name">Name A-Z</option>
        </select>
        <span v-if="getFieldError('order')" class="field-error">{{ getFieldError('order') }}</span>
      </label>
    </section>

    <div class="resource-layout">
      <aside class="label-sidebar card" aria-label="Resource labels">
        <h2>Labels</h2>
        <button
          type="button"
          :class="['label-filter', !selectedLabelId ? 'label-filter-active' : '']"
          @click="selectedLabelId = ''"
        >
          <span>All labels</span>
        </button>
        <button
          v-for="label in labels"
          :key="label.id"
          type="button"
          :class="['label-filter', selectedLabelId === String(label.id) ? 'label-filter-active' : '']"
          @click="selectedLabelId = String(label.id)"
        >
          <span>{{ label.name }}</span>
          <span class="label-count">{{ label.resource_count ?? 0 }}</span>
        </button>
        <span v-if="getFieldError('label_id')" class="field-error">{{ getFieldError('label_id') }}</span>
      </aside>

      <section class="resource-results">
        <div v-if="loading" class="card resource-state">
          <span class="loading"></span>
          <span>Loading resources...</span>
        </div>

        <div v-else-if="error" class="card resource-state resource-state-error">
          <h3>Error</h3>
          <p>{{ error }}</p>
          <button @click="loadResources" class="btn btn-primary">Retry</button>
        </div>

        <div v-else-if="resources.length === 0" class="card resource-state resource-empty-state">
          <h3>No resources found</h3>
          <p>Try changing your search or filters.</p>
        </div>

        <div v-else class="resource-list card">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Kind</th>
                <th>Labels</th>
                <th>Modified</th>
                <th v-if="isAdmin" class="th-actions">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="resource in resources"
                :key="resource.id"
                class="resource-row"
                :class="{ 'resource-row--menu-open': activeMenuResourceId === resource.id }"
                tabindex="0"
                @click="openResourceDetailFromRow(resource.id, $event)"
                @keydown.enter="openResourceDetailFromRow(resource.id, $event)"
              >
                <td>
                  <div class="resource-name-cell">
                    <i :class="getResourceIcon(resource)" aria-hidden="true"></i>
                    <span>{{ resource.name }}</span>
                  </div>
                </td>
                <td>{{ getResourceTypeLabel(resource) }}</td>
                <td>{{ getResourceKindLabel(resource.kind) }}</td>
                <td>
                  <div v-if="resource.labels?.length" class="label-list">
                    <span v-for="label in resource.labels" :key="label.id" class="label-chip">
                      {{ label.name }}
                    </span>
                  </div>
                  <span v-else class="muted">None</span>
                </td>
                <td>{{ formatDate(resource.uploaded_at) }}</td>
                <td v-if="isAdmin" class="td-actions" @click.stop>
                  <div class="resource-menu">
                    <button
                      type="button"
                      class="resource-more-btn"
                      :class="{ active: activeMenuResourceId === resource.id }"
                      aria-label="More resource actions"
                      aria-haspopup="true"
                      :aria-expanded="activeMenuResourceId === resource.id"
                      @click="toggleResourceMenu(resource.id, $event)"
                    >
                      <i class="fas fa-ellipsis-h" aria-hidden="true"></i>
                    </button>

                    <div
                      v-if="activeMenuResourceId === resource.id"
                      class="resource-dropdown"
                      role="menu"
                    >
                      <button
                        type="button"
                        class="resource-dropdown-item"
                        role="menuitem"
                        @click="onMenuAction(resource, 'view')"
                      >
                        <i class="fas fa-eye" aria-hidden="true"></i>
                        <span>View Details</span>
                      </button>
                      <button
                        type="button"
                        class="resource-dropdown-item"
                        role="menuitem"
                        @click="onMenuAction(resource, 'edit')"
                      >
                        <i class="fas fa-pen" aria-hidden="true"></i>
                        <span>Edit Resource</span>
                      </button>
                      <button
                        v-if="resource.kind !== 'page'"
                        type="button"
                        class="resource-dropdown-item"
                        role="menuitem"
                        @click="onMenuAction(resource, 'download')"
                      >
                        <i class="fas fa-download" aria-hidden="true"></i>
                        <span>Download</span>
                      </button>
                      <div class="resource-dropdown-divider"></div>
                      <button
                        type="button"
                        class="resource-dropdown-item resource-dropdown-item--danger"
                        role="menuitem"
                        @click="onMenuAction(resource, 'delete')"
                      >
                        <i class="fas fa-trash-can" aria-hidden="true"></i>
                        <span>Delete Resource</span>
                      </button>
                    </div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- Admin Side Panels & Confirm Dialogs -->
    <AdminResourceFormSheet
      v-if="isAdmin"
      v-model="formSheetOpen"
      :resource="formEditResource"
      :busy="busy"
      @saved="onResourceSaved"
      @delete="onFormEditorDelete"
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
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import AdminResourceFormSheet from '@/components/admin/resources/AdminResourceFormSheet.vue'
import { deleteAdminResource, downloadAdminResourceFile } from '@/utils/adminAPI'
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
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const isAdmin = computed(() => auth.isAdmin)

const busy = ref(false)
const formSheetOpen = ref(false)
const formEditResource = ref<Resource | null>(null)
const activeMenuResourceId = ref<number | null>(null)
const deleteConfirm = ref<{
  open: boolean
  resource: Resource | null
  message: string
}>({
  open: false,
  resource: null,
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
const selectedLabelId = ref('')
const sinceDate = ref('')
const untilDate = ref('')
const sortOrder = ref<'newest' | 'oldest' | 'name'>('newest')
let loadSequence = 0

const getFieldError = (field: string): string => fieldErrors.value[field]?.[0] || ''

const validateFilters = (): boolean => {
  fieldErrors.value = {}
  if (sinceDate.value && untilDate.value && untilDate.value < sinceDate.value) {
    fieldErrors.value = {
      until: ['until must be on or after since.']
    }
    return false
  }
  return true
}

const loadResources = async (): Promise<void> => {
  if (!auth.isAuthenticated) {
    error.value = 'You must be logged in to view resources'
    return
  }

  if (!validateFilters()) {
    error.value = ''
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
      since: sinceDate.value || undefined,
      until: untilDate.value || undefined,
      order: sortOrder.value,
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

const openResourceDetail = (id: number): void => {
  router.push({ name: 'resource-detail', params: { id } })
}

const formatDate = (value: string): string => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown'
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  })
}

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
watch([searchQuery, selectedType, selectedLabelId, sortOrder, sinceDate, untilDate], () => {
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

const toggleResourceMenu = (id: number, event?: Event) => {
  event?.stopPropagation()
  activeMenuResourceId.value = activeMenuResourceId.value === id ? null : id
}

const closeResourceMenu = () => {
  activeMenuResourceId.value = null
}

const onMenuAction = (resource: Resource, action: 'view' | 'edit' | 'download' | 'delete') => {
  closeResourceMenu()
  if (action === 'view') {
    openResourceDetail(resource.id)
  } else if (action === 'edit') {
    openEditResource(resource)
  } else if (action === 'download') {
    void handleDownload(resource)
  } else if (action === 'delete') {
    confirmDeleteResource(resource)
  }
}

const handleDownload = async (resource: Resource) => {
  try {
    await downloadAdminResourceFile(resource.id, resource.file_name || `${resource.name}.bin`)
  } catch (err: any) {
    console.error('Download failed:', err)
    error.value = err?.message || 'Download failed.'
  }
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

const openResourceDetailFromRow = (id: number, event?: Event) => {
  const target = event?.target
  if (target instanceof Element && target.closest('a, button, input, select, textarea, [data-row-ignore]')) {
    return
  }
  openResourceDetail(id)
}

const onDocumentClick = (e: MouseEvent) => {
  if (activeMenuResourceId.value !== null) {
    const target = e.target as HTMLElement | null
    if (!target?.closest('.resource-menu')) {
      activeMenuResourceId.value = null
    }
  }
}

const onKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && activeMenuResourceId.value !== null) {
    activeMenuResourceId.value = null
  }
}

onMounted(() => {
  loadResourceLookups()
  loadResources()
  document.addEventListener('click', onDocumentClick)
  window.addEventListener('keydown', onKeyDown)
})

onBeforeUnmount(() => {
  window.clearTimeout(searchTimer)
  document.removeEventListener('click', onDocumentClick)
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<style scoped>
.resource-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.resource-subtitle {
  color: var(--text-muted);
  margin: -0.5rem 0 0;
}

.resource-toolbar {
  align-items: center;
  display: grid;
  grid-template-columns: minmax(240px, 2fr) minmax(130px, 1fr) minmax(130px, 0.9fr) minmax(130px, 0.9fr) minmax(130px, 1fr);
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.filter-field {
  display: grid;
  gap: 0.3rem;
  min-width: 0;
}

.filter-label {
  color: var(--text-muted);
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
}

.resource-select,
.resource-date,
.resource-search {
  min-height: 42px;
}

.field-error {
  color: var(--danger);
  font-size: 0.82rem;
  line-height: 1.25;
}

.resource-layout {
  align-items: start;
  display: grid;
  gap: 1rem;
  grid-template-columns: 220px minmax(0, 1fr);
}

.label-sidebar {
  margin: 0;
  padding: 1rem;
}

.label-sidebar h2 {
  font-size: 1.1rem;
  margin-bottom: 0.75rem;
}

.label-filter {
  align-items: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  color: var(--charcoal);
  cursor: pointer;
  display: flex;
  font: inherit;
  justify-content: space-between;
  margin-bottom: 0.25rem;
  min-height: 36px;
  padding: 0.45rem 0.55rem;
  text-align: left;
  width: 100%;
}

.label-filter:hover,
.label-filter-active {
  background: var(--accent-green-soft);
  border-color: rgba(1, 113, 81, 0.18);
  color: var(--dark-green);
}

.label-count {
  color: var(--text-muted);
  font-size: 0.82rem;
}

.resource-results {
  min-width: 0;
}

.resource-state {
  align-items: center;
  display: flex;
  gap: 0.75rem;
}

.resource-empty-state {
  flex-direction: column;
  justify-content: center;
  gap: 0.35rem;
  text-align: center;
}

.resource-empty-state h3,
.resource-empty-state p {
  margin: 0;
}

.resource-empty-state p {
  color: var(--text-muted);
}

.resource-state-error {
  align-items: flex-start;
  border-left: 4px solid var(--danger);
  flex-direction: column;
}

.resource-list {
  overflow-x: auto;
  overflow-y: visible;
  padding: 0;
  position: relative;
}

.resource-row {
  cursor: pointer;
}

.resource-row--menu-open {
  position: relative;
  z-index: 10;
}

.resource-row:focus-visible {
  outline-offset: -2px;
}

.th-actions {
  width: 70px;
  text-align: right;
  padding-right: 1.25rem !important;
}

.td-actions {
  text-align: right;
  padding-right: 1rem !important;
  white-space: nowrap;
}

.resource-menu {
  position: relative;
  display: inline-flex;
  justify-content: flex-end;
}

.resource-more-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: 1px solid var(--border-light);
  background-color: var(--white);
  color: var(--text-muted);
  cursor: pointer;
  padding: 0;
  font-size: 0.82rem;
  transition: all 0.18s ease;
}

.resource-more-btn:hover,
.resource-more-btn.active {
  background-color: var(--accent-green-soft);
  color: var(--dark-green);
  border-color: var(--dark-green);
}

.resource-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  min-width: 170px;
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.14);
  padding: 0.35rem 0;
  z-index: 50;
  text-align: left;
  animation: dropdown-pop 0.15s ease-out;
}

@keyframes dropdown-pop {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.resource-dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  width: 100%;
  padding: 0.5rem 0.85rem;
  border: none;
  background: transparent;
  font-size: 0.84rem;
  font-weight: 500;
  color: var(--charcoal);
  cursor: pointer;
  text-align: left;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.resource-dropdown-item i {
  width: 16px;
  text-align: center;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.resource-dropdown-item:hover {
  background-color: var(--bg-light);
  color: var(--dark-green);
}

.resource-dropdown-item:hover i {
  color: var(--dark-green);
}

.resource-dropdown-item--danger {
  color: var(--danger);
}

.resource-dropdown-item--danger i {
  color: var(--danger);
}

.resource-dropdown-item--danger:hover {
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
}

.resource-dropdown-item--danger:hover i {
  color: var(--danger);
}

.resource-dropdown-divider {
  height: 1px;
  background: var(--border-light);
  margin: 0.3rem 0;
}

.resource-name-cell {
  align-items: center;
  display: flex;
  gap: 0.9rem;
  font-weight: 600;
  min-width: 220px;
}

.resource-name-cell i {
  color: var(--dark-green);
  flex: 0 0 22px;
  text-align: center;
  width: 20px;
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

  .resource-toolbar {
    grid-template-columns: 1fr;
  }

  .resource-layout {
    grid-template-columns: 1fr;
  }

  .label-sidebar {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 0.35rem;
  }

  .label-sidebar h2 {
    grid-column: 1 / -1;
  }

  .label-filter {
    margin-bottom: 0;
  }
}
</style>
