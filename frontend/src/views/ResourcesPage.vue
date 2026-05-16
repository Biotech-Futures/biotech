<template>
  <div class="content-area">
    <div class="resource-header">
      <div>
        <h1>Resource Library</h1>
        <p class="resource-subtitle">Browse available files and pages.</p>
      </div>
      <button v-if="isAdmin" class="btn btn-primary">
        <i class="fas fa-upload"></i> Upload Resource
      </button>
    </div>

    <section class="resource-toolbar" aria-label="Resource filters">
      <input
        v-model="searchQuery"
        type="search"
        class="form-control resource-search"
        placeholder="Search by file name..."
      />

      <select v-model="selectedType" class="form-control resource-select" aria-label="Filter by type">
        <option value="">All types</option>
        <option v-for="type in resourceTypes" :key="type.id" :value="type.type_name">
          {{ formatTypeName(type.type_name) }}
        </option>
      </select>

      <select v-model="selectedLabelId" class="form-control resource-select" aria-label="Filter by label">
        <option value="">All labels</option>
        <option v-for="label in labels" :key="label.id" :value="String(label.id)">
          {{ label.name }}{{ typeof label.resource_count === 'number' ? ` (${label.resource_count})` : '' }}
        </option>
      </select>

      <select v-model="sortOrder" class="form-control resource-select" aria-label="Sort resources">
        <option value="newest">Newest first</option>
        <option value="oldest">Oldest first</option>
        <option value="name">Name A-Z</option>
      </select>
    </section>

    <div v-if="loading" class="card resource-state">
      <span class="loading"></span>
      <span>Loading resources...</span>
    </div>

    <div v-else-if="error" class="card resource-state resource-state-error">
      <h3>Error</h3>
      <p>{{ error }}</p>
      <button @click="loadResources" class="btn btn-primary">Retry</button>
    </div>

    <div v-else-if="resources.length === 0" class="card resource-state">
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
<!--            <th>Size</th>-->
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="resource in resources"
            :key="resource.id"
            class="resource-row"
            tabindex="0"
            @click="openResourceDetail(resource.id)"
            @keydown.enter="openResourceDetail(resource.id)"
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
<!--            <td>{{ formatFileSize(resource.file_size) }}</td>-->
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  fetchResources,
  fetchResourceLabels,
  fetchResourceTypes,
  type Resource,
  type ResourceKind,
  type ResourceLabel,
  type ResourceType
} from '../utils/resourcesAPI'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const isAdmin = computed(() => auth.isAdmin)

const resources = ref<Resource[]>([])
const labels = ref<ResourceLabel[]>([])
const resourceTypes = ref<ResourceType[]>([])
const loading = ref(false)
const error = ref('')

const searchQuery = ref('')
const selectedType = ref('')
const selectedLabelId = ref('')
const sortOrder = ref<'newest' | 'oldest' | 'name'>('newest')
let loadSequence = 0

const loadResources = async (): Promise<void> => {
  if (!auth.isAuthenticated) {
    error.value = 'You must be logged in to view resources'
    return
  }

  const sequence = ++loadSequence
  loading.value = true
  error.value = ''
  try {
    const response = await fetchResources({
      search: searchQuery.value.trim() || undefined,
      type: selectedType.value || undefined,
      label_id: selectedLabelId.value ? Number(selectedLabelId.value) : undefined,
      order: sortOrder.value,
      page: 1,
      page_size: 100
    })
    if (sequence === loadSequence) {
      resources.value = response.results
    }
  } catch (err: unknown) {
    if (sequence === loadSequence) {
      error.value = err instanceof Error ? err.message : 'Failed to load resources'
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

let searchTimer: ReturnType<typeof window.setTimeout> | undefined
watch([searchQuery, selectedType, selectedLabelId, sortOrder], () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    loadResources()
  }, 250)
})

onMounted(() => {
  loadResourceLookups()
  loadResources()
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
  grid-template-columns: minmax(260px, 2fr) repeat(3, minmax(130px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.resource-select,
.resource-search {
  min-height: 42px;
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

.resource-list {
  overflow-x: auto;
  padding: 0;
}

.resource-row {
  cursor: pointer;
}

.resource-row:focus-visible {
  outline-offset: -2px;
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
}
</style>
