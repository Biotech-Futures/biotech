<template>
  <div class="content-area">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2rem;">
      <h1>Resource Library</h1>
      <div style="display:flex;gap:1rem;">
        <input
          type="text"
          v-model="searchQuery"
          class="form-control"
          placeholder="Search resources..."
          style="width:300px"
        />
        <button
          v-if="isAdmin"
          class="btn btn-primary"
          type="button"
          :disabled="uploading"
          @click="openUploadModal"
        >
          <i class="fas fa-upload"></i>
          <span v-if="uploading"> Uploading…</span>
          <span v-else> Upload Resource</span>
        </button>
      </div>
    </div>

    <div style="display:flex;gap:1rem;margin-bottom:2rem;">
      <button
        v-for="f in filters"
        :key="f"
        @click="activeFilter = f"
        :class="['btn', activeFilter === f ? 'btn-primary' : 'btn-outline']"
      >
        {{ f }}
      </button>
    </div>

    <div v-if="loadingList" class="card" style="margin-top:1.5rem;">
      <h3>Loading resources…</h3>
      <p style="color:#6c757d;">Fetching the latest library for you.</p>
    </div>

    <div v-else-if="pageError" class="card" style="margin-top:1.5rem;">
      <h3>Unable to load resources</h3>
      <p style="color:#dc3545;">{{ pageError.message || 'An unexpected error occurred.' }}</p>
      <button type="button" class="btn btn-outline" @click="loadResources(true)">Retry</button>
    </div>

    <div v-else>
      <div class="resource-grid">
        <div
          v-for="resource in filteredResources"
          :key="resource.id"
          class="resource-card"
          @click="handleCardClick(resource, $event)"
        >
          <!-- 顶部封面（可编辑，admin 可见按钮） -->
          <div class="resource-banner" :style="bannerStyle(resource)">
            <div class="banner-controls">
              <div class="controls-left">
                <button
                  v-if="isAdmin"
                  type="button"
                  class="control-btn"
                  title="Change cover image"
                  :disabled="coverUploading(resource.id)"
                  @click.stop.prevent="triggerCoverPicker(resource.id)"
                >
                  <i v-if="coverUploading(resource.id)" class="fas fa-spinner fa-spin"></i>
                  <i v-else class="fas fa-image"></i>
                </button>
                <!-- 隐藏的文件选择器（仅管理员使用） -->
                <input
                  v-if="isAdmin"
                  type="file"
                  accept="image/*"
                  class="hidden-file"
                  :ref="el => setCoverInputRef(el, resource.id)"
                  @change="onCoverPicked($event, resource)"
                />
              </div>
              <div class="controls-right">
                <button
                  type="button"
                  class="control-btn"
                  title="Download resource"
                  @click.stop.prevent="downloadResource(resource)"
                >
                  <i class="fas fa-download"></i>
                </button>
                <button
                  v-if="isAdmin"
                  type="button"
                  class="control-btn"
                  title="Delete resource"
                  :disabled="deletingResourceId(resource.id)"
                  @click.stop.prevent="deleteResource(resource)"
                >
                  <i
                    v-if="deletingResourceId(resource.id)"
                    class="fas fa-spinner fa-spin"
                  ></i>
                  <i v-else class="fas fa-trash"></i>
                </button>
              </div>
            </div>

            <i
              v-if="!resource.coverImage"
              :class="getResourceIcon(resource.type)"
              class="banner-icon"
            ></i>
          </div>

          <div class="resource-content">
            <div class="resource-title">{{ resource.title }}</div>
            <div class="resource-meta">
              <span class="res-type">{{ prettyType(resource.type) }}</span>
            </div>
            <div style="margin-top:0.5rem;">
              <span class="status-badge" :class="getAudienceClass(resource.role)">
                {{ getAudienceLabel(resource.role) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!filteredResources.length" class="card" style="margin-top:1.5rem;">
        <h3>No results</h3>
        <p style="color:#6c757d;">Try changing your search keywords or filter.</p>
      </div>
    </div>
  </div>

  <!-- 上传资源模态框 -->
  <div v-if="showUploadModal" class="modal-backdrop">
    <div class="modal-container">
      <div class="modal-header">
        <h2>Upload Resource</h2>
        <button type="button" class="modal-close" @click="closeUploadModal" aria-label="Close">
          <i class="fas fa-times"></i>
        </button>
      </div>
      <form class="modal-body" @submit.prevent="submitUpload">
        <div class="form-group">
          <label for="resource-title">Title</label>
          <input
            id="resource-title"
            v-model="uploadForm.title"
            type="text"
            class="form-control"
            placeholder="Enter resource title"
            required
          />
        </div>

        <div class="form-group">
          <label for="resource-description">Description</label>
          <textarea
            id="resource-description"
            v-model="uploadForm.description"
            class="form-control"
            rows="3"
            placeholder="Optional description"
          ></textarea>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="resource-type">Type</label>
            <select
              id="resource-type"
              v-model="uploadForm.type"
              class="form-control"
            >
              <option v-for="option in typeOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label for="resource-role">Audience</label>
            <select
              id="resource-role"
              v-model="uploadForm.role"
              class="form-control"
            >
              <option v-for="option in roleOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>
        </div>

        <div class="form-group">
          <label for="resource-file">File</label>
          <input
            id="resource-file"
            ref="uploadFileInput"
            type="file"
            class="form-control"
            @change="onSelectUploadFile"
            required
          />
          <p v-if="uploadForm.file" class="selected-file">
            Selected: <strong>{{ uploadForm.file.name }}</strong>
          </p>
        </div>

        <p v-if="uploadError" class="form-error">{{ uploadError }}</p>

        <div class="modal-footer">
          <button type="button" class="btn btn-outline" @click="closeUploadModal" :disabled="uploading">
            Cancel
          </button>
          <button type="submit" class="btn btn-primary" :disabled="uploading">
            <i v-if="uploading" class="fas fa-spinner fa-spin"></i>
            <span v-else>Upload</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { useResourceStore } from '@/stores/resources'

const auth = useAuthStore()
const resourceStore = useResourceStore()

const { items, loadingList, uploading, uploadingCoverIds, deletingIds } =
  storeToRefs(resourceStore)
const isAdmin = computed(() => auth.isAdmin)

const searchQuery = ref('')
const filters = ['All Resources', 'Documents', 'Videos', 'Templates', 'Guides']
const activeFilter = ref('All Resources')
const pageError = ref(null)

const typeOptions = [
  { value: 'document', label: 'Document' },
  { value: 'video', label: 'Video' },
  { value: 'template', label: 'Template' },
  { value: 'guide', label: 'Guide' }
]

const roleOptions = [
  { value: 'all', label: 'All Users' },
  { value: 'student', label: 'Student' },
  { value: 'mentor', label: 'Mentor' },
  { value: 'supervisor', label: 'Supervisor' },
  { value: 'admin', label: 'Admin' }
]

const typeMap = {
  'All Resources': null,
  Documents: 'document',
  Videos: 'video',
  Templates: 'template',
  Guides: 'guide'
}

const filteredResources = computed(() => {
  let list = Array.isArray(items.value) ? [...items.value] : []
  const t = typeMap[activeFilter.value]
  if (t) list = list.filter((r) => r.type === t)

  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(
      (r) =>
        r.title.toLowerCase().includes(q) ||
        (r.description || '').toLowerCase().includes(q)
    )
  }
  return list
})

const getResourceIcon = (type) => {
  const icons = {
    document: 'fas fa-file-alt',
    video: 'fas fa-video',
    template: 'fas fa-file-code',
    guide: 'fas fa-book'
  }
  return icons[type] || 'fas fa-file'
}

const prettyType = (type) => {
  const map = { document: 'Document', video: 'Video', template: 'Template', guide: 'Guide' }
  return map[type] || 'Resource'
}

const showUploadModal = ref(false)
const uploadError = ref(null)
const uploadFileInput = ref(null)

const defaultUploadForm = () => ({
  title: '',
  description: '',
  type: 'document',
  role: 'all',
  file: null
})

const uploadForm = ref(defaultUploadForm())

const openUploadModal = () => {
  if (!isAdmin.value) return
  uploadForm.value = defaultUploadForm()
  uploadError.value = null
  showUploadModal.value = true
}

const closeUploadModal = () => {
  showUploadModal.value = false
  uploadError.value = null
  uploadForm.value = defaultUploadForm()
  if (uploadFileInput.value) {
    uploadFileInput.value.value = ''
  }
}

const onSelectUploadFile = (event) => {
  const file = event.target.files?.[0] || null
  uploadForm.value.file = file
  if (file && !uploadForm.value.title) {
    uploadForm.value.title = file.name.replace(/\.[^.]+$/, '') || file.name
  }
}

const submitUpload = async () => {
  uploadError.value = null
  const title = uploadForm.value.title.trim()
  if (!title) {
    uploadError.value = 'Please enter a resource title'
    return
  }
  if (!uploadForm.value.file) {
    uploadError.value = 'Please select a file to upload'
    return
  }

  try {
    await resourceStore.createResource({
      title,
      description: uploadForm.value.description.trim(),
      type: uploadForm.value.type,
      role: uploadForm.value.role,
      file: uploadForm.value.file
    })
    closeUploadModal()
  } catch (error) {
    console.error(error)
    uploadError.value = error.message || 'Failed to upload resource, please try again later'
  }
}

const coverInputs = new Map()
const setCoverInputRef = (el, id) => {
  if (el) {
    coverInputs.set(id, el)
  } else {
    coverInputs.delete(id)
  }
}

const coverUploading = (id) => Boolean(uploadingCoverIds.value?.[id])
const deletingResourceId = (id) => Boolean(deletingIds.value?.[id])

const triggerCoverPicker = (id) => {
  if (!isAdmin.value || coverUploading(id)) return
  coverInputs.get(id)?.click()
}

const onCoverPicked = async (event, resource) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return

  try {
    await resourceStore.updateCover(resource.id, file)
  } catch (error) {
    console.error(error)
    alert(error.message || 'Failed to update cover image.')
  }
}

const bannerStyle = (res) => {
  const base = 'height:120px; display:flex; align-items:center; justify-content:center; color:#fff;'
  if (res?.coverImage) {
    return `${base} background-image:url('${res.coverImage}'); background-size:cover; background-position:center;`
  }
  return `${base} background: linear-gradient(135deg, var(--dark-green), var(--eucalypt));`
}

const getAudienceLabel = (role) => {
  const labels = {
    all: 'All Users',
    student: 'Student',
    mentor: 'Mentor',
    supervisor: 'Supervisor',
    admin: 'Admin'
  }
  return labels[role] || 'Unknown'
}

const getAudienceClass = (role) => {
  const classes = {
    all: 'status-active',
    student: 'status-info',
    mentor: 'status-warning',
    supervisor: 'status-pending',
    admin: 'status-danger'
  }
  return classes[role] || 'status-active'
}

const downloadResource = async (resource) => {
  if (!resource?.url) {
    alert('Download link is not available yet.')
    return
  }
  try {
    const response = await fetch(resource.url, { credentials: 'include' })
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`)
    }
    const blob = await response.blob()
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    const extension = resource.url.split('.').pop()?.split('?')[0] || 'download'
    const safeTitle = resource.title?.trim() || 'resource'
    link.download = `${safeTitle}.${extension}`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(downloadUrl)
  } catch (error) {
    console.error('Download failed:', error)
    // 如果跨域或其他原因导致下载失败，退回到打开新标签页
    window.open(resource.url, '_blank', 'noopener')
  }
}

const deleteResource = async (resource) => {
  if (!isAdmin.value || deletingResourceId(resource.id)) return

  const confirmed = window.confirm(`Delete "${resource.title}"? This action cannot be undone.`)
  if (!confirmed) return

  try {
    await resourceStore.deleteResource(resource.id)
    coverInputs.delete(resource.id)
  } catch (error) {
    console.error(error)
    alert(error.message || 'Failed to delete resource.')
  }
}

const handleCardClick = (resource, event) => {
  if (event?.target?.closest('.control-btn')) return
  downloadResource(resource)
}

const loadResources = async (force = false) => {
  if (!auth.isAuthenticated) return
  try {
    await resourceStore.fetchResources({ forceRefresh: force })
    pageError.value = null
  } catch (error) {
    pageError.value = error
    console.error(error)
  }
}

onMounted(() => {
  loadResources()
})

watch(
  () => auth.isAuthenticated,
  (loggedIn) => {
    if (loggedIn) {
      loadResources(true)
    } else {
      resourceStore.reset()
      pageError.value = null
    }
  }
)
</script>

<style scoped>
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

.banner-controls {
  position: absolute;
  top: 10px;
  left: 10px;
  right: 10px;
  display: flex;
  justify-content: space-between;
  pointer-events: auto;
}
.controls-left,
.controls-right {
  display: flex;
  gap: 0.4rem;
}
.control-btn {
  pointer-events: auto;
  background: rgba(0,0,0,0.55);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 0.35rem 0.55rem;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.2s ease;
}
.control-btn:hover {
  background: rgba(0,0,0,0.7);
}
.control-btn:disabled,
.control-btn:disabled:hover {
  background: rgba(0,0,0,0.35);
  cursor: not-allowed;
}
.hidden-file { display: none; }

.resource-content { padding: 1.25rem; }
.resource-title {
  font-weight: 600;
  color: var(--charcoal);
  margin-bottom: 0.35rem;
}
.resource-meta {
  font-size: 0.9rem;
  color: #6c757d;
}
.res-type { text-transform: capitalize; }

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(21, 30, 24, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1050;
  padding: 1.5rem;
}

.modal-container {
  width: min(560px, 100%);
  background: var(--white);
  border-radius: 12px;
  box-shadow: 0 20px 48px rgba(21, 30, 24, 0.25);
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.modal-header h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--charcoal);
}

.modal-close {
  background: none;
  border: none;
  color: #6c757d;
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.25rem;
  line-height: 1;
}
.modal-close:hover {
  color: var(--charcoal);
}

.modal-body {
  padding: 1.5rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-bottom: 1rem;
}

.form-row {
  display: flex;
  gap: 1rem;
}
.form-row .form-group {
  flex: 1;
  margin-bottom: 0;
}

.form-group label {
  font-weight: 600;
  color: var(--charcoal);
}

.form-group .form-control {
  width: 100%;
}

.selected-file {
  margin-top: 0.3rem;
  font-size: 0.85rem;
  color: #495057;
}

.form-error {
  margin: 0 0 1rem;
  color: #d9534f;
  font-weight: 600;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 0 1.5rem 1.5rem;
}

@media (max-width: 640px) {
  .form-row {
    flex-direction: column;
  }
}
</style>
