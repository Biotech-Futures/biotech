<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAnnouncementStore } from '@/stores/announcements'
import { useAuthStore } from '@/stores/auth'

const q = ref('')

const auth = useAuthStore()
const { isAuthenticated, isAdmin, user } = storeToRefs(auth)

const announcementStore = useAnnouncementStore()
const { items, loadingList, listError, creating } = storeToRefs(announcementStore)

const showCreateForm = ref(false)
const formError = ref(null)
const formState = ref({
  title: '',
  summary: '',
  content: '',
  author: '',
  audience: 'all',
  link: '',
})

// 详情模态框
const showDetailModal = ref(false)
const selectedAnnouncement = ref(null)

const audienceOptions = [
  { value: 'all', label: 'All Users' },
  { value: 'student', label: 'Student' },
  { value: 'mentor', label: 'Mentor' },
  { value: 'supervisor', label: 'Supervisor' },
  { value: 'admin', label: 'Admin' },
]

const canCreateAnnouncements = computed(() => isAdmin?.value ?? false)

const filtered = computed(() => {
  const text = q.value.trim().toLowerCase()
  const source = items.value || []
  if (!text) return source
  return source.filter((announcement) =>
    [announcement.title, announcement.summary, announcement.author]
      .some((field) => String(field || '').toLowerCase().includes(text))
  )
})

const errorMessage = computed(() => {
  const error = listError.value
  if (!error) return null
  return error.message || String(error)
})

const resetForm = () => {
  formState.value = {
    title: '',
    summary: '',
    content: '',
    author: user.value?.name || 'Program Team',
    audience: 'all',
    link: '',
  }
  formError.value = null
}

const loadAnnouncements = async (force = false) => {
  if (!isAuthenticated.value) return
  try {
    await announcementStore.fetchAnnouncements({ forceRefresh: force })
  } catch (error) {
    console.error('Failed to load announcements', error)
  }
}

onMounted(() => {
  resetForm()
  loadAnnouncements()
})

watch(isAuthenticated, (loggedIn) => {
  if (loggedIn) {
    loadAnnouncements(true)
  } else {
    announcementStore.reset()
  }
})

watch(
  () => user.value?.name,
  (name) => {
    if (!showCreateForm.value) {
      formState.value.author = name || 'Program Team'
    }
  }
)

const toggleCreateForm = () => {
  showCreateForm.value = !showCreateForm.value
  if (!showCreateForm.value) {
    resetForm()
  }
}

const handleCreate = async () => {
  formError.value = null
  const payload = {
    title: formState.value.title.trim(),
    summary: formState.value.summary.trim(),
    content: formState.value.content.trim(),
    author: formState.value.author.trim() || undefined,
    audience: formState.value.audience,
    link: formState.value.link.trim() || undefined,
  }

  if (!payload.title) {
    formError.value = 'Title is required'
    return
  }
  if (!payload.summary) {
    formError.value = 'Summary is required'
    return
  }

  try {
    await announcementStore.createAnnouncement(payload)
    resetForm()
    showCreateForm.value = false
  } catch (error) {
    formError.value = error?.message || 'Failed to create announcement'
  }
}

const formatDate = (iso) => {
  if (!iso) return '—'
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) return '—'
  return parsed.toLocaleDateString('en-AU', { year: 'numeric', month: 'short', day: 'numeric' })
}

const getAudienceLabel = (audience) => {
  const labels = {
    all: 'All Users',
    student: 'Student',
    mentor: 'Mentor',
    supervisor: 'Supervisor',
    admin: 'Admin',
  }
  return labels[audience] || 'Unknown'
}

const getAudienceClass = (audience) => {
  const classes = {
    all: 'status-active',
    student: 'status-info',
    mentor: 'status-warning',
    supervisor: 'status-pending',
    admin: 'status-danger',
  }
  return classes[audience] || 'status-active'
}

// 打开详情模态框
const openDetail = (announcement) => {
  selectedAnnouncement.value = announcement
  showDetailModal.value = true
}

const closeDetail = () => {
  showDetailModal.value = false
  selectedAnnouncement.value = null
}
</script>

<template>
  <div class="content-area">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2rem;">
      <h1>Recent Announcements</h1>
      <div style="display:flex;gap:0.75rem;align-items:center;">
        <input
          v-model="q"
          type="text"
          class="form-control"
          placeholder="Search announcements..."
          style="width: 320px;"
        />
        <button
          v-if="canCreateAnnouncements"
          type="button"
          class="btn btn-primary"
          @click="toggleCreateForm"
        >
          {{ showCreateForm ? 'Cancel' : 'New Announcement' }}
        </button>
      </div>
    </div>

    <div v-if="canCreateAnnouncements && showCreateForm" class="card" style="margin-bottom:1.5rem;">
      <form @submit.prevent="handleCreate">
        <div class="form-group">
          <label class="form-label">Title</label>
          <input
            v-model="formState.title"
            type="text"
            class="form-control"
            placeholder="Announcement title"
            required
          />
        </div>

        <div class="form-group" style="margin-top:1rem;">
          <label class="form-label">Summary</label>
          <textarea
            v-model="formState.summary"
            class="form-control"
            rows="2"
            placeholder="Short summary shown in the list"
            required
          />
        </div>

        <div class="form-group" style="margin-top:1rem;">
          <label class="form-label">Content (optional)</label>
          <textarea
            v-model="formState.content"
            class="form-control"
            rows="4"
            placeholder="Full announcement content"
          />
        </div>

        <div class="form-group" style="display:flex;gap:1rem;margin-top:1rem;flex-wrap:wrap;">
          <div style="flex:1;min-width:220px;">
            <label class="form-label">Audience</label>
            <select v-model="formState.audience" class="form-control">
              <option v-for="option in audienceOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>
          <div style="flex:1;min-width:220px;">
            <label class="form-label">Author (optional)</label>
            <input
              v-model="formState.author"
              type="text"
              class="form-control"
              placeholder="Display name for this announcement"
            />
          </div>
        </div>

        <div class="form-group" style="margin-top:1rem;">
          <label class="form-label">Link (optional)</label>
          <input
            v-model="formState.link"
            type="url"
            class="form-control"
            placeholder="https://example.com/more-info"
          />
        </div>

        <p v-if="formError" style="color:#c0392b;margin-top:1rem;">{{ formError }}</p>

        <div style="display:flex;justify-content:flex-end;gap:0.75rem;margin-top:1.5rem;">
          <button type="button" class="btn btn-outline" @click="toggleCreateForm">
            Cancel
          </button>
          <button type="submit" class="btn btn-primary" :disabled="creating">
            {{ creating ? 'Creating…' : 'Create Announcement' }}
          </button>
        </div>
      </form>
    </div>

    <div v-if="loadingList" class="card">
      <p style="margin:0;color:#6c757d;">Loading announcements…</p>
    </div>

    <div v-else-if="errorMessage" class="card">
      <p style="margin:0;color:#c0392b;">{{ errorMessage }}</p>
    </div>

    <template v-else>
      <div class="announcements-grid">
        <div
          v-for="a in filtered"
          :key="a.id"
          class="announcement-card"
          @click="openDetail(a)"
        >
          <div class="announcement-header">
            <h3 class="announcement-title">{{ a.title }}</h3>
            <span class="status-badge" :class="getAudienceClass(a.audience)">
              {{ getAudienceLabel(a.audience) }}
            </span>
          </div>
          <div class="announcement-meta">
            {{ formatDate(a.createdAt || a.date) }} · {{ a.author || 'Program Team' }}
          </div>
          <p class="announcement-summary">{{ a.summary }}</p>
          <div class="announcement-footer">
            <button class="btn btn-outline btn-sm" @click.stop="openDetail(a)">
              Read more
            </button>
          </div>
        </div>
      </div>

      <div v-if="filtered.length === 0" class="card">
        <p style="margin:0;color:#6c757d;">No announcements found.</p>
      </div>
    </template>

    <!-- 详情模态框 -->
    <div v-if="showDetailModal" class="modal-backdrop" @click.self="closeDetail">
      <div class="modal-container">
        <div class="modal-header">
          <div class="modal-header-content">
            <h2>{{ selectedAnnouncement?.title }}</h2>
            <div class="modal-header-meta">
              <span class="status-badge" :class="getAudienceClass(selectedAnnouncement?.audience)">
                {{ getAudienceLabel(selectedAnnouncement?.audience) }}
              </span>
              <span class="meta-text">
                {{ formatDate(selectedAnnouncement?.createdAt || selectedAnnouncement?.date) }} · 
                {{ selectedAnnouncement?.author || 'Program Team' }}
              </span>
            </div>
          </div>
          <button type="button" class="modal-close" @click="closeDetail" aria-label="Close">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div class="modal-body">
          <div v-if="selectedAnnouncement?.content" class="announcement-content">
            {{ selectedAnnouncement.content }}
          </div>
          <div v-else class="announcement-content">
            {{ selectedAnnouncement?.summary }}
          </div>

          <div v-if="selectedAnnouncement?.link" class="announcement-link-section">
            <a
              :href="selectedAnnouncement.link"
              class="btn btn-primary"
              target="_blank"
              rel="noopener"
            >
              <i class="fas fa-external-link-alt"></i>
              Open Link
            </a>
          </div>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn btn-outline" @click="closeDetail">
            Close
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.announcements-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 1.25rem;
}

.announcement-card {
  background: var(--white);
  border: 1.5px solid var(--border-lighter);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  box-shadow: var(--shadow-sm);
  transition: var(--transition);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.announcement-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: var(--dark-green);
}

.announcement-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.announcement-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--charcoal);
  margin: 0;
  flex: 1;
  line-height: 1.4;
}

.announcement-meta {
  color: #6c757d;
  font-size: 0.85rem;
  font-weight: 500;
}

.announcement-summary {
  color: var(--charcoal);
  line-height: 1.6;
  margin: 0;
  flex: 1;
}

.announcement-footer {
  display: flex;
  justify-content: flex-start;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border-lighter);
}

/* Modal styles */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(21, 30, 24, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1050;
  padding: 1.5rem;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.modal-container {
  width: min(680px, 100%);
  max-height: 85vh;
  background: var(--white);
  border-radius: 12px;
  box-shadow: 0 20px 48px rgba(21, 30, 24, 0.25);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.5rem;
  padding: 1.5rem 1.75rem;
  border-bottom: 1.5px solid var(--border-lighter);
  background: linear-gradient(135deg, var(--bg-lighter) 0%, var(--white) 100%);
}

.modal-header-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--charcoal);
  line-height: 1.3;
}

.modal-header-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.meta-text {
  color: #6c757d;
  font-size: 0.9rem;
  font-weight: 500;
}

.modal-close {
  background: none;
  border: none;
  color: #6c757d;
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0.25rem;
  line-height: 1;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: var(--transition);
  flex-shrink: 0;
}

.modal-close:hover {
  background: rgba(0, 0, 0, 0.05);
  color: var(--charcoal);
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.75rem;
}

.announcement-content {
  color: var(--charcoal);
  line-height: 1.7;
  font-size: 1rem;
  white-space: pre-wrap;
  word-break: break-word;
}

.announcement-link-section {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1.5px solid var(--border-lighter);
  display: flex;
  justify-content: flex-start;
}

.announcement-link-section .btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.75rem 1.5rem;
  border-top: 1.5px solid var(--border-lighter);
  background: linear-gradient(135deg, var(--white) 0%, var(--bg-lighter) 100%);
}

@media (max-width: 768px) {
  .announcements-grid {
    grid-template-columns: 1fr;
  }

  .modal-header {
    flex-direction: column;
    gap: 1rem;
  }

  .modal-close {
    align-self: flex-end;
  }
}
</style>
