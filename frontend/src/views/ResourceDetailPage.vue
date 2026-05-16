<template>
  <div class="content-area">
    <button type="button" class="btn btn-outline back-button" @click="router.push({ name: 'resources' })">
      <i class="fas fa-arrow-left" aria-hidden="true"></i> Back to resources
    </button>

    <div v-if="loading" class="card detail-state">
      <span class="loading"></span>
      <span>Loading resource...</span>
    </div>

    <div v-else-if="error" class="card detail-state detail-state-error">
      <h3>Resource unavailable</h3>
      <p>{{ error }}</p>
      <button type="button" class="btn btn-primary" @click="loadResource">Retry</button>
    </div>

    <template v-else-if="resource">
      <header class="detail-header">
        <div>
          <div class="detail-kind">
            <i :class="resourceIcon" aria-hidden="true"></i>
            <span>{{ resourceTypeLabel }}</span>
          </div>
          <h1>{{ resource.name }}</h1>
          <p class="detail-description">{{ resource.description }}</p>
          <div v-if="resource.labels?.length" class="label-list">
            <span v-for="label in resource.labels" :key="label.id" class="label-chip">
              {{ label.name }}
            </span>
          </div>
          <p v-if="accessError" class="detail-warning">
            {{ accessError }}
          </p>
        </div>
        <button
          v-if="downloadTarget"
          type="button"
          class="btn btn-primary"
          @click="downloadResource"
        >
          <i class="fas fa-download" aria-hidden="true"></i> Download
        </button>
      </header>

      <section class="detail-layout">
        <article class="preview-panel">
          <div class="preview-header">
            <h2>Preview</h2>
            <a
              v-if="openTarget"
              class="btn btn-outline btn-sm"
              :href="openTarget"
              target="_blank"
              rel="noopener noreferrer"
            >
              <i class="fas fa-external-link-alt" aria-hidden="true"></i> Open
            </a>
          </div>

          <div v-if="previewLoading" class="preview-empty">
            <span class="loading"></span>
            <span>Preparing preview...</span>
          </div>

          <div v-else-if="previewError" class="preview-empty">
            <i class="fas fa-file-download" aria-hidden="true"></i>
            <p>{{ previewError }}</p>
            <button
              v-if="downloadTarget"
              type="button"
              class="btn btn-primary"
              @click="downloadResource"
            >
              Download file
            </button>
            <button
              v-if="accessError"
              type="button"
              class="btn btn-outline"
              @click="loadAccess"
            >
              Retry preview
            </button>
          </div>

          <iframe
            v-else-if="previewMode === 'html'"
            class="preview-frame"
            title="Resource preview"
            sandbox="allow-popups allow-popups-to-escape-sandbox"
            :srcdoc="htmlPreview"
          ></iframe>

          <iframe
            v-else-if="previewMode === 'frame' && previewUrl"
            class="preview-frame"
            title="Resource preview"
            sandbox="allow-popups allow-popups-to-escape-sandbox"
            :src="previewUrl"
          ></iframe>

          <img
            v-else-if="previewMode === 'image' && previewUrl"
            class="preview-image"
            :src="previewUrl"
            :alt="resource.name"
          />

          <video
            v-else-if="previewMode === 'video' && previewUrl"
            class="preview-media"
            :src="previewUrl"
            controls
          ></video>

          <audio
            v-else-if="previewMode === 'audio' && previewUrl"
            class="preview-audio"
            :src="previewUrl"
            controls
          ></audio>

          <pre v-else-if="previewMode === 'text'" class="preview-text">{{ textPreview }}</pre>

          <div v-else class="preview-empty">
            <i class="fas fa-file-download" aria-hidden="true"></i>
            <p>This file type cannot be displayed in the browser.</p>
            <button
              v-if="downloadTarget"
              type="button"
              class="btn btn-primary"
              @click="downloadResource"
            >
              Download file
            </button>
          </div>
        </article>

        <aside class="metadata-panel card">
          <h2>Details</h2>
          <dl class="metadata-list">
            <div>
              <dt>File name</dt>
              <dd>{{ access?.file_name || resource.file_name || resource.name }}</dd>
            </div>
            <div>
              <dt>Kind</dt>
              <dd>{{ resourceKindLabel }}</dd>
            </div>
            <div>
              <dt>Type</dt>
              <dd>{{ resourceTypeLabel }}</dd>
            </div>
            <div>
              <dt>Modified</dt>
              <dd>{{ formatDateTime(resource.uploaded_at) }}</dd>
            </div>
            <div>
              <dt>Uploaded by</dt>
              <dd>{{ resource.uploader_name || 'Unknown' }}</dd>
            </div>
            <div>
              <dt>Size</dt>
              <dd>{{ formatFileSize(access?.file_size || resource.file_size) }}</dd>
            </div>
            <div>
              <dt>MIME type</dt>
              <dd>{{ access?.file_mime_type || resource.file_mime_type || 'Unknown' }}</dd>
            </div>
            <div>
              <dt>Storage</dt>
              <dd>{{ storageLabel }}</dd>
            </div>
          </dl>
        </aside>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  buildResourceUrl,
  fetchResource,
  fetchResourceAccess,
  type Resource,
  type ResourceAccess,
  type ResourceKind
} from '../utils/resourcesAPI'

type PreviewMode = 'none' | 'html' | 'frame' | 'image' | 'video' | 'audio' | 'text'

const route = useRoute()
const router = useRouter()

const resource = ref<Resource | null>(null)
const access = ref<ResourceAccess | null>(null)
const loading = ref(false)
const error = ref('')
const accessError = ref('')
const previewLoading = ref(false)
const previewError = ref('')
const previewMode = ref<PreviewMode>('none')
const previewUrl = ref('')
const htmlPreview = ref('')
const textPreview = ref('')
let objectUrl = ''

const resourceId = computed(() => Number(route.params.id))
const mimeType = computed(() =>
  (access.value?.file_mime_type || resource.value?.file_mime_type || '').toLowerCase(),
)

const resourceTypeLabel = computed(() =>
  formatTypeName(resource.value?.type_name || resource.value?.resource_type_detail?.type_name),
)

const resourceKindLabel = computed(() =>
  getResourceKindLabel(resource.value?.kind || access.value?.kind || 'file'),
)

const storageLabel = computed(() => {
  const value = access.value?.storage_status || resource.value?.storage_status
  const labels: Record<string, string> = {
    managed_key: 'Managed storage',
    external_url: 'External URL',
    unavailable: 'Unavailable'
  }
  return value ? labels[value] || formatTypeName(value) : 'Unknown'
})

const resourceIcon = computed(() => {
  if (resource.value?.kind === 'page') return 'fas fa-globe'
  if (resource.value?.kind === 'attachment') return 'fas fa-paperclip'
  if (mimeType.value.includes('pdf')) return 'fas fa-file-pdf'
  if (mimeType.value.startsWith('image/')) return 'fas fa-file-image'
  if (mimeType.value.startsWith('video/')) return 'fas fa-file-video'
  if (mimeType.value.startsWith('audio/')) return 'fas fa-file-audio'
  return 'fas fa-file-alt'
})

const managedDownloadUrl = computed(() => {
  if (access.value) {
    if (access.value.access_mode === 'unavailable') return null
    return access.value.download_url || `/resources/resource-files/${access.value.resource_id}/download/`
  }

  if (!resource.value) return null
  if (resource.value.storage_status === 'unavailable') return null
  return resource.value.download_url || `/resources/resource-files/${resource.value.id}/download/`
})

const downloadTarget = computed(() => {
  const target = access.value?.download_url || access.value?.external_url || managedDownloadUrl.value
  if (!target) return null
  if (access.value?.download_url) {
    const separator = access.value.download_url.includes('?') ? '&' : '?'
    return buildResourceUrl(`${access.value.download_url}${separator}force=1`)
  }
  return buildResourceUrl(target)
})

const openTarget = computed(() => {
  if (!access.value || accessError.value) return null
  const target = access.value.external_url || managedDownloadUrl.value
  return target ? buildResourceUrl(target) : null
})

const isTextLike = computed(() => {
  const mime = mimeType.value
  return mime.startsWith('text/') || mime.includes('json') || mime.includes('xml') || mime.includes('csv')
})

const canFrameMime = computed(() => {
  const mime = mimeType.value
  return mime.includes('pdf') || mime === 'text/html'
})

const clearPreview = (): void => {
  if (objectUrl) {
    window.URL.revokeObjectURL(objectUrl)
    objectUrl = ''
  }
  previewMode.value = 'none'
  previewUrl.value = ''
  htmlPreview.value = ''
  textPreview.value = ''
  previewError.value = ''
}

const preparePreview = async (): Promise<void> => {
  clearPreview()
  if (!resource.value) return
  if (!access.value) {
    previewError.value = accessError.value || 'Preview information could not be loaded.'
    return
  }

  if (access.value.access_mode === 'unavailable') {
    previewError.value = access.value.detail || 'This resource is unavailable.'
    return
  }

  if (access.value.access_mode === 'inline_html') {
    if (access.value.body_html) {
      htmlPreview.value = access.value.body_html
      previewMode.value = 'html'
    } else {
      previewError.value = access.value.detail || 'Rich-text content could not be displayed.'
    }
    return
  }

  if (access.value.access_mode === 'external_page' && access.value.external_url) {
    previewUrl.value = buildResourceUrl(access.value.external_url)
    previewMode.value = 'frame'
    return
  }

  if (access.value.external_url) {
    previewUrl.value = buildResourceUrl(access.value.external_url)
    if (mimeType.value.startsWith('image/')) previewMode.value = 'image'
    else if (mimeType.value.startsWith('video/')) previewMode.value = 'video'
    else if (mimeType.value.startsWith('audio/')) previewMode.value = 'audio'
    else if (canFrameMime.value || isTextLike.value) previewMode.value = 'frame'
    else previewError.value = 'This file type cannot be displayed in the browser.'
    return
  }

  const target = managedDownloadUrl.value
  if (!target) {
    previewError.value = access.value.detail || 'This resource has no file to preview.'
    return
  }

  if (
    !mimeType.value.startsWith('image/') &&
    !mimeType.value.startsWith('video/') &&
    !mimeType.value.startsWith('audio/') &&
    !canFrameMime.value &&
    !isTextLike.value
  ) {
    previewError.value = 'This file type cannot be displayed in the browser.'
    return
  }

  previewLoading.value = true
  try {
    const response = await fetch(buildResourceUrl(target), {
      credentials: 'include'
    })
    if (!response.ok) {
      throw new Error(`Preview could not be loaded. HTTP ${response.status}`)
    }
    const blob = await response.blob()
    if (isTextLike.value && mimeType.value !== 'text/html') {
      textPreview.value = await blob.text()
      previewMode.value = 'text'
      return
    }

    objectUrl = window.URL.createObjectURL(blob)
    previewUrl.value = objectUrl
    if (mimeType.value.startsWith('image/')) previewMode.value = 'image'
    else if (mimeType.value.startsWith('video/')) previewMode.value = 'video'
    else if (mimeType.value.startsWith('audio/')) previewMode.value = 'audio'
    else previewMode.value = 'frame'
  } catch (err: unknown) {
    previewError.value = err instanceof Error ? err.message : 'Preview could not be loaded.'
  } finally {
    previewLoading.value = false
  }
}

const loadResource = async (): Promise<void> => {
  if (!Number.isFinite(resourceId.value) || resourceId.value <= 0) {
    error.value = 'Invalid resource id.'
    return
  }

  loading.value = true
  error.value = ''
  accessError.value = ''
  clearPreview()
  try {
    const resourceData = await fetchResource(resourceId.value)
    resource.value = resourceData
    await loadAccess()
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : 'Resource could not be loaded.'
  } finally {
    loading.value = false
  }
}

const loadAccess = async (): Promise<void> => {
  if (!resource.value) return
  previewLoading.value = true
  accessError.value = ''
  clearPreview()
  try {
    access.value = await fetchResourceAccess(resource.value.id)
    await preparePreview()
  } catch (err: unknown) {
    access.value = null
    const message = err instanceof Error ? err.message : 'Preview information could not be loaded.'
    accessError.value = `The resource metadata loaded, but the preview API failed: ${message}`
    previewError.value = accessError.value
  } finally {
    previewLoading.value = false
  }
}

const downloadResource = (): void => {
  if (!downloadTarget.value || !resource.value) return
  const link = document.createElement('a')
  link.href = downloadTarget.value
  link.rel = 'noopener noreferrer'
  link.download = access.value?.file_name || resource.value.file_name || resource.value.name
  document.body.appendChild(link)
  link.click()
  link.remove()
}

const formatDateTime = (value?: string | null): string => {
  if (!value) return 'Unknown'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown'
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
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

const getResourceKindLabel = (kind: ResourceKind): string => {
  const labels: Record<string, string> = {
    file: 'File',
    page: 'Page',
    attachment: 'Attachment'
  }
  return labels[kind] || formatTypeName(kind)
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

watch(resourceId, loadResource, { immediate: true })
onBeforeUnmount(clearPreview)
</script>

<style scoped>
.back-button {
  align-items: center;
  display: inline-flex;
  gap: 0.45rem;
  margin-bottom: 1rem;
}

.detail-state {
  align-items: center;
  display: flex;
  gap: 0.75rem;
}

.detail-state-error {
  align-items: flex-start;
  border-left: 4px solid var(--danger);
  flex-direction: column;
}

.detail-header {
  align-items: flex-start;
  display: flex;
  gap: 1.25rem;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.detail-header h1 {
  margin-bottom: 0.35rem;
}

.detail-kind {
  align-items: center;
  color: var(--dark-green);
  display: flex;
  font-weight: 600;
  gap: 0.5rem;
  margin-bottom: 0.4rem;
}

.detail-description {
  color: var(--text-muted);
  margin: 0 0 0.85rem;
  max-width: 760px;
}

.detail-warning {
  background: #fff3cd;
  border: 1px solid rgba(133, 100, 4, 0.2);
  border-radius: 6px;
  color: #856404;
  margin: 0.9rem 0 0;
  max-width: 760px;
  padding: 0.65rem 0.75rem;
}

.detail-layout {
  align-items: start;
  display: grid;
  gap: 1.25rem;
  grid-template-columns: minmax(0, 1fr) 320px;
}

.preview-panel {
  background: var(--white);
  border-radius: 8px;
  box-shadow: 0 2px 4px var(--shadow);
  min-height: 560px;
  overflow: hidden;
}

.preview-header {
  align-items: center;
  border-bottom: 1px solid var(--border-light);
  display: flex;
  justify-content: space-between;
  padding: 1rem 1.25rem;
}

.preview-header h2,
.metadata-panel h2 {
  font-size: 1.25rem;
  margin: 0;
}

.preview-frame {
  border: 0;
  display: block;
  height: 620px;
  width: 100%;
}

.preview-image {
  display: block;
  max-height: 620px;
  max-width: 100%;
  object-fit: contain;
  padding: 1rem;
  width: 100%;
}

.preview-media {
  background: #000;
  display: block;
  max-height: 620px;
  width: 100%;
}

.preview-audio {
  margin: 3rem auto;
  width: min(520px, calc(100% - 2rem));
}

.preview-text {
  color: var(--charcoal);
  font-family: Consolas, 'Courier New', monospace;
  font-size: 0.9rem;
  line-height: 1.5;
  margin: 0;
  max-height: 620px;
  overflow: auto;
  padding: 1.25rem;
  white-space: pre-wrap;
}

.preview-empty {
  align-items: center;
  color: var(--text-muted);
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  min-height: 480px;
  justify-content: center;
  padding: 2rem;
  text-align: center;
}

.preview-empty i {
  color: var(--dark-green);
  font-size: 2rem;
}

.metadata-panel {
  margin: 0;
}

.metadata-list {
  display: grid;
  gap: 1rem;
  margin-top: 1rem;
}

.metadata-list div {
  border-bottom: 1px solid var(--border-light);
  padding-bottom: 0.85rem;
}

.metadata-list div:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.metadata-list dt {
  color: var(--text-muted);
  font-size: 0.82rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
  text-transform: uppercase;
}

.metadata-list dd {
  color: var(--charcoal);
  margin: 0;
  overflow-wrap: anywhere;
}

.label-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.label-chip {
  background: var(--accent-green-soft);
  border: 1px solid rgba(1, 113, 81, 0.18);
  border-radius: 999px;
  color: var(--dark-green);
  display: inline-flex;
  font-size: 0.85rem;
  line-height: 1;
  padding: 0.4rem 0.6rem;
}

@media (max-width: 1000px) {
  .detail-header {
    flex-direction: column;
  }

  .detail-layout {
    grid-template-columns: 1fr;
  }

  .metadata-panel {
    order: -1;
  }
}
</style>
