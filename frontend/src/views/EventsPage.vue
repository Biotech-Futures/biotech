<template>
  <div class="content-area">
    <div class="page-head">
      <h1>Events & Workshops</h1>
      <div class="head-actions">
        <button class="btn btn-outline">
          <i class="fas fa-filter"></i> Filter
        </button>
        <button v-if="isAdmin" class="btn btn-primary" @click="createEvent">
          <i class="fas fa-plus"></i> Create Event
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="card">
      <p>Loading events...</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="card">
      <p>{{ error }}</p>
    </div>

    <!-- Events Grid -->
    <div v-else-if="events.length" class="events-grid">
      <div v-for="ev in events" :key="ev.id" class="event-card">
        <div class="event-banner" :style="bannerStyle(ev)">
          <i v-if="!ev.cover" class="fas fa-calendar-alt"></i>

          <button
            v-if="isAdmin"
            class="edit-cover-btn"
            @click="triggerCoverPicker(ev.id)"
          >
            <i class="fas fa-image"></i>
          </button>

          <button
            v-if="isAdmin && ev.cover"
            class="edit-cover-btn"
            style="right: 46px;"
            @click="resetCover(ev)"
          >
            <i class="fas fa-trash"></i>
          </button>

          <input
            type="file"
            accept="image/*"
            class="hidden-file"
            :ref="el => setCoverInputRef(el, ev.id)"
            @change="onCoverPicked($event, ev)"
          />
        </div>

        <div class="event-content">
          <span class="event-date">{{ formatDate(ev.date) }}</span>
          <h3 class="event-title">{{ ev.title }}</h3>
          <p class="event-description">
            {{ ev.description || defaultLong }}
          </p>

          <div class="event-meta">
            <div class="event-meta-item">
              <i class="fas fa-clock"></i> {{ ev.time }}
            </div>
            <div class="event-meta-item">
              <i class="fas fa-map-marker-alt"></i> {{ ev.location }}
            </div>
            <div class="event-meta-item">
              <i class="fas fa-users"></i> {{ ev.type }}
            </div>
          </div>

          <div class="cta-row">
            <button class="btn btn-outline" @click="openDetails(ev)">View Details</button>
            <button class="btn btn-primary" @click="register(ev)">Register Now</button>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="card">
      <h3>No upcoming events</h3>
    </div>

    <!-- Modal -->
    <div class="modal" :class="{ show: showModal }" @click.self="closeDetails">
      <div class="modal-content">
        <div class="modal-header">
          <div class="modal-title">{{ selected?.title }}</div>
          <button class="modal-close" @click="closeDetails">&times;</button>
        </div>
        <div class="modal-body">
          <div class="detail-banner" :style="bannerStyle(selected)">
            <i v-if="selected && !selected.cover" class="fas fa-calendar-alt"></i>
          </div>
          <p>
            {{ formatDate(selected?.date) }} • {{ selected?.time }} • {{ selected?.location }}
          </p>
          <p>{{ selected?.description || defaultLong }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchEvents } from '../utils/eventsAPI'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

const backendEvents = ref([])
const loading = ref(false)
const error = ref('')

const defaultLong = 'Join this session and explore more insights.'

// ✅ Map backend → frontend
const events = computed(() => {
  return backendEvents.value.map(e => {
    const start = new Date(e.start_datetime)
    const end = new Date(e.ends_datetime)

    return {
      id: e.id,
      title: e.event_name,
      description: e.description,
      date: e.start_datetime,
      time: `${start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} -
             ${end.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`,
      location: e.is_virtual ? 'Online' : (e.location || 'TBA'),
      type: e.event_type || 'event',
      cover: e.event_image || null
    }
  })
})

// ✅ Load from API
onMounted(async () => {
  loading.value = true
  try {
    const res = await fetchEvents()
    backendEvents.value = res.results || res
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
})

// UI helpers
const formatDate = (d) => new Date(d).toLocaleDateString()

const bannerStyle = (ev) => {
  if (!ev?.cover) return 'background: #2d6a4f; height:150px; display:flex; align-items:center; justify-content:center; color:white;'
  return `background:url(${ev.cover}); background-size:cover; height:150px;`
}

// modal
const showModal = ref(false)
const selected = ref(null)

const openDetails = (ev) => {
  selected.value = ev
  showModal.value = true
}
const closeDetails = () => showModal.value = false

// actions
const register = (ev) => alert(`Register: ${ev.title}`)
const createEvent = () => alert('Create Event')

// cover handlers (unchanged)
const coverInputs = new Map()
const setCoverInputRef = (el, id) => el && coverInputs.set(id, el)
const triggerCoverPicker = (id) => coverInputs.get(id)?.click()

const onCoverPicked = (e, ev) => {
  const file = e.target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    ev.cover = reader.result
    localStorage.setItem(`eventCover:${ev.id}`, ev.cover)
  }
  reader.readAsDataURL(file)
}

const resetCover = (ev) => {
  ev.cover = null
  localStorage.removeItem(`eventCover:${ev.id}`)
}
</script>
