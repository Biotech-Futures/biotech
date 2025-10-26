<template>
  <div class="content-area">
    <div class="page-head">
      <h1>Events & Workshops</h1>
      <div class="head-actions">
        <button class="btn btn-outline" type="button" @click="loadEvents(true)">
          <i class="fas fa-rotate"></i> Refresh
        </button>
        <button v-if="isAdmin" class="btn btn-primary" type="button" @click="openCreateModal">
          <i class="fas fa-plus"></i> Create Event
        </button>
      </div>
    </div>

    <div v-if="loadingList" class="card">
      <h3>Loading events…</h3>
      <p style="color:#6c757d;">Fetching the latest schedule for you.</p>
    </div>

    <div v-else-if="pageError" class="card">
      <h3>Unable to load events</h3>
      <p style="color:#dc3545;">{{ pageError.message || 'An unexpected error occurred.' }}</p>
      <button type="button" class="btn btn-outline" @click="loadEvents(true)">Retry</button>
    </div>

    <!-- 两列网格 -->
    <div class="events-grid" v-else-if="events.length">
      <div v-for="ev in events" :key="ev.id" class="event-card">
        <div class="event-banner" :style="bannerStyle(ev)">
          <i v-if="!ev.coverImage" class="fas fa-calendar-alt"></i>

          <div class="banner-controls" v-if="isAdmin">
            <button
              type="button"
              class="edit-cover-btn"
              :disabled="coverUploading(ev.id)"
              @click.prevent="triggerCoverPicker(ev.id)"
              title="Change cover image"
            >
              <i v-if="coverUploading(ev.id)" class="fas fa-spinner fa-spin"></i>
              <i v-else class="fas fa-image"></i>
            </button>
            <input
              type="file"
              accept="image/*"
              class="hidden-file"
              :ref="el => setCoverInputRef(el, ev.id)"
              @change="onCoverPicked($event, ev)"
            />
            <button
              type="button"
              class="edit-cover-btn danger"
              :disabled="deleting(ev.id)"
              title="Delete event"
              @click.prevent="deleteEvent(ev)"
            >
              <i v-if="deleting(ev.id)" class="fas fa-spinner fa-spin"></i>
              <i v-else class="fas fa-trash"></i>
            </button>
          </div>
        </div>

        <div class="event-content">
          <span class="event-date">{{ formatDate(ev.date) }}</span>
          <h3 class="event-title">{{ ev.title }}</h3>
          <p class="event-description">
            {{ ev.description || defaultLong }}
          </p>

          <div class="event-meta">
            <div class="event-meta-item">
              <i class="fas fa-clock"></i> {{ ev.time || 'TBA' }}
            </div>
            <div class="event-meta-item">
              <i class="fas fa-map-marker-alt"></i> {{ ev.location || 'TBA' }}
            </div>
            <div class="event-meta-item">
              <i class="fas fa-users"></i> {{ formatType(ev.type) }}
            </div>
          </div>

          <div class="cta-row">
            <button class="btn btn-outline" type="button" @click="openDetails(ev)">View Details</button>

            <a
              v-if="ev.registerLink"
              class="btn btn-primary"
              :href="ev.registerLink"
              target="_blank"
              rel="noopener"
            >
              Register Now
            </a>
            <button
              v-else
              class="btn btn-primary"
              type="button"
              :disabled="ev.isRegistered || registering(ev.id)"
              @click="register(ev)"
            >
              <template v-if="ev.isRegistered">
                <i class="fas fa-check-circle"></i> Registered
              </template>
              <template v-else-if="registering(ev.id)">
                <i class="fas fa-spinner fa-spin"></i> Registering…
              </template>
              <template v-else>
                Register Now
              </template>
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="card">
      <h3>No upcoming events</h3>
      <p style="color:#6c757d;">Check back soon for new workshops and sessions.</p>
    </div>

    <!-- 详情弹窗 -->
    <div class="modal" :class="{ show: showModal }" @click.self="closeDetails">
      <div class="modal-content">
        <div class="modal-header">
          <div class="modal-title">{{ selected?.title }}</div>
          <button class="modal-close" @click="closeDetails">&times;</button>
        </div>
        <div class="modal-body">
          <div class="detail-banner" :style="bannerStyle(selected)">
            <i v-if="selected && !selected.coverImage" class="fas fa-calendar-alt"></i>
          </div>
          <p style="color:#6c757d; margin: 0.75rem 0;">
            {{ formatDate(selected?.date) }} • {{ selected?.time }} • {{ selected?.location }} • {{ formatType(selected?.type) }}
          </p>
          <p>{{ selected?.longDescription || selected?.description || defaultLong }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="closeDetails">Close</button>
          <a
            v-if="selected?.registerLink"
            class="btn btn-primary"
            :href="selected.registerLink"
            target="_blank"
            rel="noopener"
          >Register Now</a>
          <button
            v-else
            class="btn btn-primary"
            :disabled="selected?.isRegistered || registering(selected?.id)"
            @click="register(selected)"
          >
            <template v-if="selected?.isRegistered">
              <i class="fas fa-check-circle"></i> Registered
            </template>
            <template v-else-if="registering(selected?.id)">
              <i class="fas fa-spinner fa-spin"></i> Registering…
            </template>
            <template v-else>
              Register Now
            </template>
          </button>
        </div>
      </div>
    </div>

    <!-- 创建活动模态框 -->
    <div v-if="showCreateModal" class="modal-backdrop">
      <div class="modal-container">
        <div class="modal-header">
          <h2>Create Event</h2>
          <button class="modal-close" type="button" @click="closeCreateModal" aria-label="Close">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <form class="modal-body" @submit.prevent="submitCreate">
          <div class="form-group">
            <label for="event-title">Title</label>
            <input
              id="event-title"
              v-model="createForm.title"
              type="text"
              class="form-control"
              placeholder="Enter event title"
              required
            />
          </div>

          <div class="form-group">
            <label for="event-description">Description</label>
            <textarea
              id="event-description"
              v-model="createForm.description"
              class="form-control"
              rows="2"
              placeholder="Short description"
            ></textarea>
          </div>

          <div class="form-group">
            <label for="event-long-description">Long Description</label>
            <textarea
              id="event-long-description"
              v-model="createForm.longDescription"
              class="form-control"
              rows="4"
              placeholder="Full agenda or session details"
            ></textarea>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label for="event-date">Date</label>
              <input
                id="event-date"
                v-model="createForm.date"
                type="date"
                class="form-control"
                required
              />
            </div>
            <div class="form-group">
              <label for="event-time">Time</label>
              <input
                id="event-time"
                v-model="createForm.time"
                type="text"
                class="form-control"
                placeholder="e.g. 3:00 PM"
                required
              />
            </div>
          </div>

          <div class="form-group">
            <label for="event-location">Location</label>
            <input
              id="event-location"
              v-model="createForm.location"
              type="text"
              class="form-control"
              placeholder="Online / Venue details"
              required
            />
          </div>

          <div class="form-row">
            <div class="form-group">
              <label for="event-type">Type</label>
              <select
                id="event-type"
                v-model="createForm.type"
                class="form-control"
              >
                <option value="in-person">In Person</option>
                <option value="virtual">Virtual</option>
              </select>
            </div>
            <div class="form-group">
              <label for="event-capacity">Capacity (optional)</label>
              <input
                id="event-capacity"
                v-model="createForm.capacity"
                type="number"
                min="1"
                class="form-control"
                placeholder="Leave blank if unlimited"
              />
            </div>
          </div>

          <div class="form-group">
            <label for="event-register-link">Registration Link (optional)</label>
            <input
              id="event-register-link"
              v-model="createForm.registerLink"
              type="url"
              class="form-control"
              placeholder="https://example.com/register"
            />
          </div>

          <p v-if="createError" class="form-error">{{ createError }}</p>

          <div class="modal-footer">
            <button type="button" class="btn btn-outline" @click="closeCreateModal" :disabled="creating">
              Cancel
            </button>
            <button type="submit" class="btn btn-primary" :disabled="creating">
              <i v-if="creating" class="fas fa-spinner fa-spin"></i>
              <span v-else>Create Event</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { useEventStore } from '@/stores/events'

const auth = useAuthStore()
const eventStore = useEventStore()

const { items, loadingList } = storeToRefs(eventStore)
const isAdmin = computed(() => auth.isAdmin)

const events = computed(() => items.value || [])
const pageError = ref(null)

const defaultLong =
  'This session is part of the BIOTech Futures program. Learn, collaborate, and build your project with mentors and peers.'

const formatDate = (dateStr) => {
  if (!dateStr) return 'TBA'
  const parsed = new Date(dateStr)
  if (Number.isNaN(parsed.getTime())) return dateStr
  return parsed.toLocaleDateString('en-AU', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}

const formatType = (type) => {
  const map = {
    'in-person': 'In Person',
    'virtual': 'Virtual'
  }
  return map[type] || 'Event'
}

const bannerStyle = (ev) => {
  const base =
    'height: 150px; display:flex; align-items:center; justify-content:center; color: #fff; background: linear-gradient(135deg, var(--dark-green), var(--mint-green));'
  if (!ev) return base
  if (ev.coverImage) {
    return `${base} background-image: url('${ev.coverImage}'); background-size: cover; background-position: center;`
  }
  return base
}

const showModal = ref(false)
const selected = ref(null)
const openDetails = (ev) => {
  selected.value = { ...ev }
  showModal.value = true
}
const closeDetails = () => {
  showModal.value = false
  selected.value = null
}

const coverInputs = new Map()
const setCoverInputRef = (el, id) => {
  if (el) {
    coverInputs.set(id, el)
  } else {
    coverInputs.delete(id)
  }
}
const triggerCoverPicker = (id) => {
  if (!isAdmin.value) return
  coverInputs.get(id)?.click()
}

const coverUploading = (id) => Boolean(eventStore.uploadingCoverIds?.[id])
const registering = (id) => Boolean(eventStore.registeringIds?.[id])
const deleting = (id) => Boolean(eventStore.deletingIds?.[id])

const onCoverPicked = async (event, ev) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return

  try {
    await eventStore.updateCover(ev.id, file)
  } catch (error) {
    console.error(error)
    alert(error.message || 'Failed to update cover.')
  }
}

const register = async (eventObj) => {
  if (!eventObj?.id) return
  if (eventObj.registerLink) {
    window.open(eventObj.registerLink, '_blank', 'noopener')
    return
  }
  try {
    await eventStore.registerEvent(eventObj.id)
    alert('Registered successfully!')
    if (selected.value?.id === eventObj.id) {
      selected.value = {
        ...selected.value,
        isRegistered: true,
        registrationCount: (selected.value.registrationCount || 0) + 1
      }
    }
  } catch (error) {
    console.error(error)
    alert(error.message || 'Registration failed.')
  }
}

const deleteEvent = async (eventObj) => {
  if (!eventObj?.id) return
  const confirmed = window.confirm(`Delete "${eventObj.title}"? This action cannot be undone.`)
  if (!confirmed) return
  try {
    await eventStore.deleteEvent(eventObj.id)
    if (selected.value?.id === eventObj.id) {
      closeDetails()
    }
  } catch (error) {
    console.error(error)
    alert(error.message || 'Deletion failed, please try again later.')
  }
}

const loadEvents = async (force = false) => {
  if (!auth.isAuthenticated) return
  try {
    await eventStore.fetchEvents({ forceRefresh: force })
    pageError.value = null
  } catch (error) {
    console.error(error)
    pageError.value = error
  }
}

onMounted(() => {
  loadEvents()
})

watch(
  () => auth.isAuthenticated,
  (loggedIn) => {
    if (loggedIn) {
      loadEvents(true)
    } else {
      eventStore.reset()
      pageError.value = null
    }
  }
)

watch(
  items,
  (list) => {
    if (!selected.value) return
    const updated = (list || []).find((item) => item.id === selected.value.id)
    if (updated) {
      selected.value = { ...updated }
    }
  },
  { deep: false }
)

// --- 创建活动模态 ---
const showCreateModal = ref(false)
const createError = ref(null)
const createForm = ref({
  title: '',
  description: '',
  longDescription: '',
  date: '',
  time: '',
  location: '',
  type: 'in-person',
  registerLink: '',
  capacity: ''
})

const openCreateModal = () => {
  if (!isAdmin.value) return
  createForm.value = {
    title: '',
    description: '',
    longDescription: '',
    date: '',
    time: '',
    location: '',
    type: 'in-person',
    registerLink: '',
    capacity: ''
  }
  createError.value = null
  showCreateModal.value = true
}

const closeCreateModal = () => {
  showCreateModal.value = false
  createError.value = null
}

const submitCreate = async () => {
  createError.value = null
  const payload = {
    title: createForm.value.title.trim(),
    description: createForm.value.description.trim(),
    longDescription: createForm.value.longDescription.trim(),
    date: createForm.value.date,
    time: createForm.value.time.trim(),
    location: createForm.value.location.trim(),
    type: createForm.value.type,
    registerLink: createForm.value.registerLink.trim(),
    capacity: createForm.value.capacity ? Number(createForm.value.capacity) : null
  }

  if (!payload.title || !payload.date || !payload.time || !payload.location) {
    createError.value = 'Please complete all required fields'
    return
  }

  try {
    await eventStore.createEvent(payload)
    showCreateModal.value = false
    createError.value = null
  } catch (error) {
    console.error(error)
    createError.value = error.message || 'Failed to create event, please try again later'
  }
}

const creating = computed(() => eventStore.creating)
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}
.head-actions {
  display: flex;
  gap: 1rem;
}

/* 两列布局（小屏 1 列） */
.events-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.5rem;
}
@media (max-width: 900px) {
  .events-grid {
    grid-template-columns: 1fr;
  }
}

/* 复用现有卡片样式，细节增强 */
.event-card {
  background-color: var(--white);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 4px var(--shadow);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.event-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--shadow);
}
.event-banner {
  position: relative;
}
.event-banner i {
  font-size: 2.25rem;
  opacity: 0.9;
}

.banner-controls {
  position: absolute;
  top: 10px;
  left: 10px;
  right: 10px;
  display: flex;
  justify-content: space-between;
  pointer-events: none;
}
.edit-cover-btn {
  pointer-events: auto;
  background: rgba(0,0,0,0.55);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 0.4rem 0.6rem;
  cursor: pointer;
  font-size: 0.875rem;
}
.edit-cover-btn:hover {
  background: rgba(0,0,0,0.7);
}
.edit-cover-btn:disabled,
.edit-cover-btn:disabled:hover {
  background: rgba(0,0,0,0.35);
  cursor: not-allowed;
}
.hidden-file {
  display: none;
}

.event-content {
  padding: 1.5rem;
}
.event-date {
  display: inline-block;
  background-color: var(--light-green);
  color: var(--dark-green);
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-size: 0.875rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}
.event-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--charcoal);
  margin: 0.25rem 0 0.5rem;
}
.event-description {
  color: #6c757d;
  margin-bottom: 1rem;
  line-height: 1.5;
}
.event-meta {
  display: flex;
  gap: 1.5rem;
  font-size: 0.875rem;
  color: #6c757d;
  margin-bottom: 1rem;
}
.event-meta-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

/* CTA 行 */
.cta-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

/* 详情弹窗里的横幅（沿用卡片风格） */
.detail-banner {
  height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  border-radius: 6px;
  margin-bottom: 1rem;
}
.detail-banner i {
  font-size: 2.5rem;
}

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
  width: min(680px, 100%);
  background: var(--white);
  border-radius: 12px;
  box-shadow: 0 20px 48px rgba(21, 30, 24, 0.25);
  overflow: hidden;
}
.modal-header h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
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
