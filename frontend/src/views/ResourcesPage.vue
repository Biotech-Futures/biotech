<template>
  <div class="content-area">
    <div class="resource-header">
      <h1>Resource Library</h1>
      <div class="resource-tools">
        <input
          type="text"
          v-model="searchQuery"
          class="form-control resource-search"
          placeholder="Search resources..."
        />
        <button v-if="isAdmin" class="btn btn-primary">
          <i class="fas fa-upload"></i> Upload Resource
        </button>
      </div>
    </div>

    <div class="resource-filters">
      <button
        v-for="f in filters"
        :key="f"
        @click="activeFilter = f"
        :class="['btn', activeFilter === f ? 'btn-primary' : 'btn-outline']"
      >
        {{ f }}
      </button>
    </div>

    <div v-if="loading" class="card" style="margin-top:1.5rem;">
      <p style="text-align:center;color:#6c757d;">Loading resources...</p>
    </div>

    <div v-else-if="error" class="card" style="margin-top:1.5rem;border-left:4px solid #dc3545;">
      <h3 style="color:#dc3545;">Error</h3>
      <p style="color:#6c757d;">{{ error }}</p>
      <button @click="loadResources" class="btn btn-primary" style="margin-top:1rem;">Retry</button>
    </div>

    <div v-else-if="filteredResources.length === 0" class="card" style="margin-top:1.5rem;">
      <h3>No resources found</h3>
      <p style="color:#6c757d;">
        <span v-if="searchQuery || activeFilter !== 'All Resources'">
          Try changing your search keywords or filter.
        </span>
        <span v-else>
          There are no resources available yet. Check back later or contact your administrator.
        </span>
      </p>
    </div>

    <div v-else class="resource-grid">
      <div
        v-for="resource in filteredResources"
        :key="resource.id"
        class="resource-card"
        @click="openResource(resource)"
      >
        <div class="resource-banner" :style="bannerStyle(resource)">
          <i v-if="!resource.cover" :class="getResourceIcon(resource)" class="banner-icon"></i>

          <button
            v-if="isAdmin"
            type="button"
            class="edit-cover-btn"
            title="Change cover image"
            @click.stop="triggerCoverPicker(resource.id)"
          >
            <i class="fas fa-image"></i>
          </button>

          <button
            v-if="isAdmin && resource.cover"
            type="button"
            class="edit-cover-btn remove-cover-btn"
            title="Remove cover image"
            @click.stop="resetCover(resource)"
          >
            <i class="fas fa-trash"></i>
          </button>

          <input
            type="file"
            accept="image/*"
            class="hidden-file"
            :ref="el => setCoverInputRef(el, resource.id)"
            @change="onCoverPicked($event, resource)"
          />
        </div>

        <div class="resource-content">
          <div class="resource-title">{{ resource.title }}</div>
          <p class="resource-description">{{ resource.description }}</p>
          <div class="resource-meta">
            <span class="res-type">{{ prettyType(resource) }}</span>
            <span>{{ resource.updated }}</span>
          </div>
          <div class="resource-footer">
            <span class="status-badge" :class="getStatusClass(resource)">
              {{ getStatusLabel(resource) }}
            </span>
            <div class="resource-actions">
              <button
                type="button"
                class="btn btn-outline resource-action-btn"
                :disabled="isResourceBusy(resource.id)"
                @click.stop="openResource(resource)"
              >
                <i class="fas fa-eye"></i> View
              </button>
              <button
                type="button"
                class="btn btn-primary resource-action-btn"
                :disabled="isResourceBusy(resource.id) || !resource.canDownload"
                @click.stop="downloadResource(resource)"
              >
                <i class="fas fa-download"></i> Download
              </button>
            </div>
          </div>
          <p v-if="actionStatus[resource.id]" class="resource-action-status">
            {{ actionStatus[resource.id] }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, type ComponentPublicInstance } from 'vue'
import {
  buildResourceUrl,
  fetchAllResources,
  fetchResourceAccess,
  type Resource,
  type ResourceAccess
} from '../utils/resourcesAPI'
import { safeLocalStorageGet, safeLocalStorageRemove, safeLocalStorageSet } from '../utils/storage'
import { useAuthStore } from '../stores/auth'

type ResourceTypeKey = 'document' | 'video' | 'template' | 'guide' | 'page' | string

interface FrontendResource {
  id: number
  title: string
  description: string
  type: ResourceTypeKey
  kind: string
  mimeType?: string | null
  fileName?: string | null
  fileSize?: number | null
  updated: string
  uploaderName?: string | null
  storageStatus?: string | null
  cover?: string | null
  canDownload: boolean
}

const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

const backendResources = ref<Resource[]>([])
const loading = ref(false)
const error = ref('')
const busyResourceId = ref<number | null>(null)
const actionStatus = ref<Record<number, string>>({})
const coverById = ref<Record<number, string>>({})

const searchQuery = ref('')
const filters = ['All Resources', 'Documents', 'Videos', 'Templates', 'Guides', 'Pages'] as const
type FilterOption = typeof filters[number]
const activeFilter = ref<FilterOption>('All Resources')

const typeMap: Record<FilterOption, ResourceTypeKey | null> = {
  'All Resources': null,
  Documents: 'document',
  Videos: 'video',
  Templates: 'template',
  Guides: 'guide',
  Pages: 'page'
}

const resources = computed<FrontendResource[]>(() => {
  return backendResources.value.map(r => {
    const type = normalizeResourceType(r)
    return {
      id: r.id,
      title: r.name,
      description: r.description,
      type,
      kind: r.kind,
      mimeType: r.file_mime_type,
      fileName: r.file_name,
      fileSize: r.file_size,
      updated: formatDate(r.uploaded_at),
      uploaderName: r.uploader_name,
      storageStatus: r.storage_status,
      cover: coverById.value[r.id] || null,
      canDownload: r.kind === 'file' && Boolean(r.download_url || r.access_url)
    }
  })
})

const filteredResources = computed<FrontendResource[]>(() => {
  let list = resources.value
  const query = searchQuery.value.trim().toLowerCase()
  if (query) {
    list = list.filter(r =>
      [r.title, r.description, r.fileName, r.uploaderName]
        .filter(Boolean)
        .some(value => String(value).toLowerCase().includes(query))
    )
  }
  const selectedType = typeMap[activeFilter.value]
  if (selectedType) {
    list = list.filter(r => r.type === selectedType)
  }
  return list
})

const loadResources = async (): Promise<void> => {
  if (!auth.isAuthenticated) {
    error.value = 'You must be logged in to view resources'
    return
  }

  loading.value = true
  error.value = ''
  try {
    backendResources.value = await fetchAllResources()
    loadSavedCovers()
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : 'Failed to load resources'
    console.error('Error loading resources:', err)
  } finally {
    loading.value = false
  }
}

const normalizeResourceType = (resource: Resource): ResourceTypeKey => {
  const explicitType = resource.type_name || resource.resource_type_detail?.type_name
  const typeName = explicitType?.trim().toLowerCase()
  if (typeName) {
    if (typeName.includes('video')) return 'video'
    if (typeName.includes('template')) return 'template'
    if (typeName.includes('guide')) return 'guide'
    if (typeName.includes('page') || typeName.includes('link')) return 'page'
    return typeName
  }

  if (resource.kind === 'page') return 'page'
  const mimeType = resource.file_mime_type?.toLowerCase() || ''
  if (mimeType.startsWith('video/')) return 'video'
  if (mimeType.includes('spreadsheet') || mimeType.includes('template')) return 'template'
  if (mimeType.includes('pdf') || mimeType.includes('document') || mimeType.includes('text')) return 'document'

  return 'document'
}

const formatDate = (value: string): string => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown date'
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  })
}

const getResourceIcon = (resource: FrontendResource): string => {
  if (resource.kind === 'page') return 'fas fa-external-link-alt'
  const iconMap: Record<string, string> = {
    document: 'fas fa-file-alt',
    video: 'fas fa-video',
    template: 'fas fa-file-code',
    guide: 'fas fa-book',
    page: 'fas fa-external-link-alt'
  }
  return iconMap[resource.type] || 'fas fa-file'
}

const prettyType = (resource: FrontendResource): string => {
  const labelMap: Record<string, string> = {
    document: 'Document',
    video: 'Video',
    template: 'Template',
    guide: 'Guide',
    page: 'Page'
  }
  return labelMap[resource.type] || 'Resource'
}

const setResourceStatus = (resourceId: number, message = '') => {
  actionStatus.value = {
    ...actionStatus.value,
    [resourceId]: message
  }
}

const isResourceBusy = (resourceId: number): boolean => busyResourceId.value === resourceId

const resolveAccessTarget = (data: ResourceAccess, mode: 'view' | 'download'): string | null => {
  if (mode === 'download') {
    const target = data.download_url || data.external_url || data.access_url
    if (!target) return null
    if (data.download_url) {
      const separator = data.download_url.includes('?') ? '&' : '?'
      return `${data.download_url}${separator}force=1`
    }
    return target
  }

  return data.external_url || data.download_url || data.access_url
}

const openManagedFilePreview = async (url: string, resource: FrontendResource): Promise<void> => {
  const response = await fetch(buildResourceUrl(url), {
    method: 'GET',
    credentials: 'include'
  })

  if (!response.ok) {
    throw new Error(`Resource could not be opened. HTTP ${response.status}`)
  }

  const contentType = response.headers.get('Content-Type') || resource.mimeType || 'application/octet-stream'
  const blob = new Blob([await response.blob()], { type: contentType })
  const blobUrl = window.URL.createObjectURL(blob)
  window.open(blobUrl, '_blank', 'noopener,noreferrer')
  window.setTimeout(() => window.URL.revokeObjectURL(blobUrl), 60_000)
}

const openResource = async (resource: FrontendResource): Promise<void> => {
  busyResourceId.value = resource.id
  setResourceStatus(resource.id, 'Opening...')
  try {
    const data = await fetchResourceAccess(resource.id)
    const target = resolveAccessTarget(data, 'view')
    if (!target) {
      setResourceStatus(resource.id, data.detail || 'This resource cannot be opened.')
      return
    }
    if (data.external_url) {
      window.open(buildResourceUrl(target), '_blank', 'noopener,noreferrer')
    } else if (data.download_url) {
      await openManagedFilePreview(data.download_url, resource)
    } else {
      window.open(buildResourceUrl(target), '_blank', 'noopener,noreferrer')
    }
    setResourceStatus(resource.id)
  } catch (err: unknown) {
    setResourceStatus(resource.id, err instanceof Error ? err.message : 'Resource could not be opened.')
  } finally {
    busyResourceId.value = null
  }
}

const downloadResource = async (resource: FrontendResource): Promise<void> => {
  busyResourceId.value = resource.id
  setResourceStatus(resource.id, 'Preparing download...')
  try {
    const data = await fetchResourceAccess(resource.id)
    const target = resolveAccessTarget(data, 'download')
    if (!target) {
      setResourceStatus(resource.id, data.detail || 'This resource has no downloadable file.')
      return
    }

    const link = document.createElement('a')
    link.href = buildResourceUrl(target)
    link.rel = 'noopener noreferrer'
    link.download = data.file_name || resource.fileName || resource.title
    document.body.appendChild(link)
    link.click()
    link.remove()
    setResourceStatus(resource.id)
  } catch (err: unknown) {
    setResourceStatus(resource.id, err instanceof Error ? err.message : 'Resource could not be downloaded.')
  } finally {
    busyResourceId.value = null
  }
}

const coverInputs = new Map<number, HTMLInputElement>()
const setCoverInputRef = (el: Element | ComponentPublicInstance | null, id: number) => {
  if (el instanceof HTMLInputElement) {
    coverInputs.set(id, el)
  }
}
const triggerCoverPicker = (id: number) => { coverInputs.get(id)?.click() }

const coverStorageKey = (id: number) => `resourceCover:${id}`

const loadSavedCovers = () => {
  const nextCovers: Record<number, string> = {}
  backendResources.value.forEach(resource => {
    const saved = safeLocalStorageGet(coverStorageKey(resource.id))
    if (saved) nextCovers[resource.id] = saved
  })
  coverById.value = nextCovers
}

const onCoverPicked = (event: Event, res: FrontendResource) => {
  const input = event.target as HTMLInputElement | null
  if (!input) return
  const file = input.files && input.files[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    const cover = String(reader.result)
    coverById.value = { ...coverById.value, [res.id]: cover }
    safeLocalStorageSet(coverStorageKey(res.id), cover)
  }
  reader.readAsDataURL(file)
  input.value = ''
}

const resetCover = (resource: FrontendResource) => {
  safeLocalStorageRemove(coverStorageKey(resource.id))
  const nextCovers = { ...coverById.value }
  delete nextCovers[resource.id]
  coverById.value = nextCovers
}

onMounted(loadResources)

const bannerStyle = (res: FrontendResource): string => {
  const base = 'height:120px; display:flex; align-items:center; justify-content:center; color:#fff;'
  if (res?.cover) {
    return `${base} background-image:url('${res.cover}'); background-size:cover; background-position:center;`
  }
  return `${base} background: linear-gradient(135deg, var(--dark-green), var(--eucalypt));`
}

const getStatusLabel = (resource: FrontendResource): string => {
  if (resource.storageStatus === 'unavailable') return 'Unavailable'
  if (resource.kind === 'page') return 'Link'
  return resource.fileSize ? formatFileSize(resource.fileSize) : 'File'
}

const getStatusClass = (resource: FrontendResource): string => {
  if (resource.storageStatus === 'unavailable') return 'status-danger'
  if (resource.kind === 'page') return 'status-info'
  return 'status-active'
}

const formatFileSize = (value: number): string => {
  if (!Number.isFinite(value) || value <= 0) return 'File'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = value
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}
</script>

<style scoped>
.resource-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;
}

.resource-tools {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.resource-search {
  width: 300px;
}

.resource-filters {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 2rem;
}

.resource-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
}

.resource-card {
  background-color: var(--white);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 4px var(--shadow);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
}

.resource-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--shadow);
}

.resource-banner {
  position: relative;
}

.banner-icon {
  font-size: 2rem;
  opacity: 0.95;
}

.edit-cover-btn {
  position: absolute;
  right: 10px;
  bottom: 10px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 0.35rem 0.55rem;
  cursor: pointer;
  font-size: 0.85rem;
}

.remove-cover-btn {
  right: 46px;
}

.edit-cover-btn:hover {
  background: rgba(0, 0, 0, 0.7);
}

.hidden-file {
  display: none;
}

.resource-content {
  padding: 1.25rem;
}

.resource-title {
  font-weight: 600;
  color: var(--charcoal);
  margin-bottom: 0.35rem;
}

.resource-description {
  color: #6c757d;
  font-size: 0.9rem;
  line-height: 1.4;
  margin: 0 0 0.75rem;
  min-height: 2.5rem;
}

.resource-meta {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  font-size: 0.9rem;
  color: #6c757d;
}

.res-type {
  text-transform: capitalize;
}

.resource-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.9rem;
}

.resource-actions {
  display: flex;
  gap: 0.5rem;
}

.resource-action-btn {
  padding: 0.4rem 0.65rem;
  font-size: 0.85rem;
}

.resource-action-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.resource-action-status {
  color: #6c757d;
  font-size: 0.85rem;
  margin: 0.75rem 0 0;
}

@media (max-width: 720px) {
  .resource-header,
  .resource-tools,
  .resource-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .resource-search {
    width: 100%;
  }

  .resource-actions {
    width: 100%;
  }

  .resource-action-btn {
    flex: 1;
  }
}
</style>
