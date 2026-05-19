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
          <dl v-if="!isPageResource" class="detail-file-facts" aria-label="File details">
            <div>
              <dt>File type</dt>
              <dd>{{ fileTypeLabel }}</dd>
            </div>
            <div>
              <dt>File size</dt>
              <dd>{{ fileSizeLabel }}</dd>
            </div>
          </dl>
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
          </div>

          <div v-if="previewLoading" class="preview-empty">
            <span class="loading"></span>
            <span>Preparing preview...</span>
          </div>

          <div v-else-if="previewError" class="preview-empty">
            <i class="fas fa-file-download" aria-hidden="true"></i>
            <p>{{ previewError }}</p>
            <button
              v-if="isPdfResource ? pdfPreviewTarget : downloadTarget"
              type="button"
              class="btn btn-primary"
              @click="isPdfResource ? previewPdfResource() : downloadResource()"
            >
              {{ isPdfResource ? 'Preview' : 'Download file' }}
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

          <article
            v-else-if="previewMode === 'html' && isPageResource"
            class="resource-page-preview"
          >
            <div class="resource-page-body announcement-rich" v-html="htmlPreview"></div>
          </article>

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
  type ResourceAccess
} from '../utils/resourcesAPI'

type PreviewMode = 'none' | 'html' | 'frame' | 'image' | 'video' | 'audio' | 'text'
type ResourceAccessMode =
  | 'inline_html'
  | 'external_page'
  | 'external_file'
  | 'managed_file'
  | 'managed_page'
  | 'unavailable'
  | string

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

const isPageResource = computed(() =>
  (resource.value?.kind || access.value?.kind || '').toLowerCase() === 'page',
)

const isPdfResource = computed(() => mimeType.value.includes('pdf'))

const fileTypeLabel = computed(() =>
  access.value?.file_mime_type || resource.value?.file_mime_type || resourceTypeLabel.value,
)

const fileSizeLabel = computed(() =>
  formatFileSize(access.value?.file_size || resource.value?.file_size),
)

const accessMode = computed<ResourceAccessMode | ''>(() => access.value?.access_mode || '')

const resourceIcon = computed(() => {
  if (resource.value?.kind === 'page') return 'fas fa-globe'
  if (resource.value?.kind === 'attachment') return 'fas fa-paperclip'
  if (mimeType.value.includes('pdf')) return 'fas fa-file-pdf'
  if (mimeType.value.startsWith('image/')) return 'fas fa-file-image'
  if (mimeType.value.startsWith('video/')) return 'fas fa-file-video'
  if (mimeType.value.startsWith('audio/')) return 'fas fa-file-audio'
  return 'fas fa-file-alt'
})

const resourceDownloadEndpoint = computed(() => {
  if (!access.value || access.value.access_mode === 'unavailable') return null
  return access.value.download_url || `/resources/resource-files/${access.value.resource_id}/download/`
})

const downloadTarget = computed(() => {
  if (!access.value || accessError.value) return null

  if (accessMode.value === 'managed_file' || accessMode.value === 'managed_page') {
    return resourceDownloadEndpoint.value ? buildResourceUrl(resourceDownloadEndpoint.value) : null
  }

  if (accessMode.value === 'external_file') {
    const target = resourceDownloadEndpoint.value
    if (!target) return null
    const separator = target.includes('?') ? '&' : '?'
    return buildResourceUrl(`${target}${separator}force=1`)
  }

  return null
})

const pdfPreviewTarget = computed(() => {
  if (!access.value || accessError.value || !isPdfResource.value) return null
  if ((accessMode.value === 'external_file' || accessMode.value === 'external_page') && access.value.external_url) {
    return buildResourceUrl(access.value.external_url)
  }
  return resourceDownloadEndpoint.value ? buildResourceUrl(resourceDownloadEndpoint.value) : null
})

const isTextLike = computed(() => {
  const mime = mimeType.value
  return mime.startsWith('text/') || mime.includes('json') || mime.includes('xml') || mime.includes('csv')
})

const canFrameMime = computed(() => {
  const mime = mimeType.value
  return mime === 'text/html'
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

  if (accessMode.value === 'unavailable') {
    previewError.value = access.value.detail || 'This resource is unavailable.'
    return
  }

  if (accessMode.value === 'inline_html') {
    if (access.value.body_html) {
      htmlPreview.value = access.value.body_html
      previewMode.value = 'html'
    } else {
      previewError.value = access.value.detail || 'Rich-text content could not be displayed.'
    }
    return
  }

  if (accessMode.value === 'external_page') {
    previewError.value = access.value.external_url
      ? 'Open this resource in a new tab.'
      : access.value.detail || 'This resource does not have an external page URL.'
    return
  }

  if (accessMode.value === 'external_file' && access.value.external_url) {
    if (isPdfResource.value) {
      previewError.value = 'Preview this PDF in a new window.'
      return
    }
    previewUrl.value = buildResourceUrl(access.value.external_url)
    if (mimeType.value.startsWith('image/')) previewMode.value = 'image'
    else if (mimeType.value.startsWith('video/')) previewMode.value = 'video'
    else if (mimeType.value.startsWith('audio/')) previewMode.value = 'audio'
    else if (canFrameMime.value || isTextLike.value) previewMode.value = 'frame'
    else previewError.value = 'This file type cannot be displayed in the browser.'
    return
  }

  if (accessMode.value !== 'managed_file' && accessMode.value !== 'managed_page') {
    previewError.value = access.value.detail || 'This resource cannot be displayed.'
    return
  }

  const target = resourceDownloadEndpoint.value
  if (!target) {
    previewError.value = access.value.detail || 'This resource has no file to preview.'
    return
  }

  if (isPdfResource.value) {
    previewError.value = 'Preview this PDF in a new window.'
    return
  }

  previewError.value = 'Open or download this file to view it.'
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

const previewPdfResource = (): void => {
  if (!pdfPreviewTarget.value || !resource.value) return

  const safeTitle = escapeHtml(resource.value.name || 'PDF preview')
  const safeUrl = escapeHtml(pdfPreviewTarget.value)
  const previewHtml = `
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>${safeTitle}</title>
        <style>
          * { box-sizing: border-box; }
          body {
            margin: 0;
            background: #f8f9fa;
            color: #174243;
            font-family: Arial, sans-serif;
          }
          header {
            align-items: center;
            background: #ffffff;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            gap: 1rem;
            justify-content: space-between;
            min-height: 64px;
            padding: 0.9rem 1rem;
          }
          h1 {
            font-size: 1rem;
            line-height: 1.3;
            margin: 0;
          }
          a {
            color: #017151;
            font-weight: 700;
            text-decoration: none;
            white-space: nowrap;
          }
          main {
            height: calc(100vh - 64px);
          }
          iframe {
            border: 0;
            display: block;
            height: 100%;
            width: 100%;
          }
          .fallback {
            background: #ffffff;
            border-bottom: 1px solid #e0e0e0;
            color: #6c757d;
            font-size: 0.9rem;
            padding: 0.7rem 1rem;
          }
        </style>
      </head>
      <body>
        <header>
          <h1>${safeTitle}</h1>
          <a href="${safeUrl}" target="_self" rel="noopener noreferrer">Download PDF</a>
        </header>
        <div class="fallback">
          If the PDF does not render here, the file is being served as a download by the storage provider.
        </div>
        <main>
          <iframe src="${safeUrl}" title="${safeTitle}"></iframe>
        </main>
      </body>
    </html>
  `
  const previewPageUrl = window.URL.createObjectURL(
    new Blob([previewHtml], { type: 'text/html' }),
  )
  const previewWindow = window.open(previewPageUrl, '_blank', 'noopener,noreferrer')
  if (!previewWindow) {
    window.URL.revokeObjectURL(previewPageUrl)
    return
  }
  window.setTimeout(() => window.URL.revokeObjectURL(previewPageUrl), 60_000)
}

const escapeHtml = (value: string): string =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

const formatTypeName = (value?: string | null): string => {
  if (!value) return 'Resource'
  return value
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
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

.detail-file-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  margin: 0 0 0.85rem;
}

.detail-file-facts div {
  align-items: baseline;
  display: inline-flex;
  gap: 0.4rem;
}

.detail-file-facts dt {
  color: var(--dark-green);
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
}

.detail-file-facts dd {
  color: var(--charcoal);
  font-size: 0.9rem;
  margin: 0;
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
  display: block;
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

.preview-header h2 {
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

.resource-page-preview {
  background: var(--white);
  color: var(--charcoal);
}

.resource-page-body {
  font-size: 1rem;
  line-height: 1.75;
  padding: 1.75rem 2.25rem;
}

.announcement-rich :deep(*) {
  max-width: 100%;
}

.announcement-rich :deep(p),
.announcement-rich :deep(ul),
.announcement-rich :deep(ol),
.announcement-rich :deep(blockquote),
.announcement-rich :deep(pre),
.announcement-rich :deep(table),
.announcement-rich :deep(figure) {
  margin: 0 0 1rem;
}

.announcement-rich :deep(h1),
.announcement-rich :deep(h2),
.announcement-rich :deep(h3),
.announcement-rich :deep(h4),
.announcement-rich :deep(h5),
.announcement-rich :deep(h6) {
  color: var(--dark-green);
  line-height: 1.25;
  margin: 1.25rem 0 0.55rem;
}

.announcement-rich :deep(h1:first-child),
.announcement-rich :deep(h2:first-child),
.announcement-rich :deep(h3:first-child),
.announcement-rich :deep(h4:first-child),
.announcement-rich :deep(h5:first-child),
.announcement-rich :deep(h6:first-child) {
  margin-top: 0;
}

.announcement-rich :deep(ul),
.announcement-rich :deep(ol) {
  padding-left: 1.4rem;
}

.announcement-rich :deep(a) {
  color: var(--dark-green);
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.announcement-rich :deep(blockquote) {
  background: rgba(1, 113, 81, 0.06);
  border-left: 3px solid var(--dark-green);
  border-radius: 0 10px 10px 0;
  padding: 0.85rem 1.1rem;
}

.announcement-rich :deep(pre) {
  background: #f5f7f8;
  border-radius: 10px;
  overflow-x: auto;
  padding: 0.95rem 1.1rem;
}

.announcement-rich :deep(code) {
  background: #f5f7f8;
  border-radius: 4px;
  font-size: 0.92em;
  padding: 0.1rem 0.3rem;
}

.announcement-rich :deep(pre code) {
  background: transparent;
  padding: 0;
}

.announcement-rich :deep(img) {
  background: var(--light-green);
  border-radius: 10px;
  display: block;
  height: auto;
  max-height: 480px;
  object-fit: contain;
  width: 100%;
}

.announcement-rich :deep(table) {
  border-collapse: collapse;
  display: block;
  overflow-x: auto;
  width: 100%;
}

.announcement-rich :deep(th),
.announcement-rich :deep(td) {
  border: 1px solid rgba(1, 113, 81, 0.14);
  padding: 0.6rem 0.7rem;
  text-align: left;
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

  .resource-page-body {
    padding: 1.25rem;
  }
}
</style>
