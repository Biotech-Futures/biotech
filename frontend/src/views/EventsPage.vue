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

    <!-- Two-column grid -->
    <div class="events-grid" v-if="events.length">
      <div v-for="ev in events" :key="ev.id" class="event-card">
        <!-- Cover: supports custom image or placeholder background -->
        <div class="event-banner" :style="bannerStyle(ev)">
          <i v-if="!ev.cover" class="fas fa-calendar-alt"></i>

          <!-- Admins can edit the cover -->
          <button
            v-if="isAdmin"
            type="button"
            class="edit-cover-btn"
            @click="triggerCoverPicker(ev.id)"
            title="Change cover image"
          >
            <i class="fas fa-image"></i>
          </button>
          <!-- Optional: reset cover -->
          <button
            v-if="isAdmin && ev.cover"
            type="button"
            class="edit-cover-btn"
            style="right: 46px;"
            @click="resetCover(ev)"
            title="Remove cover image"
          >
            <i class="fas fa-trash"></i>
          </button>
          <!-- Hidden file input -->
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
            {{ ev.description || 'Join us for this important session as part of the BIOTech Futures program.' }}
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

          <!-- CTA area: View Details + Register Now -->
          <div class="cta-row">
            <button class="btn btn-outline" @click="openDetails(ev)">View Details</button>

            <a
              v-if="ev.registerLink"
              class="btn btn-primary"
              :href="ev.registerLink"
              target="_blank"
              rel="noopener"
            >
              Register Now
            </a>
            <button v-else class="btn btn-primary" @click="register(ev)">Register Now</button>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="card">
      <h3>No upcoming events</h3>
    </div>

    <!-- Details modal -->
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
          <p style="color:#6c757d; margin: 0.75rem 0;">
            {{ formatDate(selected?.date) }} • {{ selected?.time }} • {{ selected?.location }} • {{ selected?.type }}
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
          <button v-else class="btn btn-primary" @click="register(selected)">Register Now</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { mockEvents } from '../data/mock.js'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

const events = ref(mockEvents.map(e => ({ ...e })))

const defaultLong =
  'This session is part of the BIOTech Futures program. Learn, collaborate, and build your project with mentors and peers.'

// --- Display and formatting ---
const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-AU', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}

const bannerStyle = (ev) => {
  const base = 'height: 150px; display:flex; align-items:center; justify-content:center; color: #fff;'
  if (!ev) return base
  if (ev.cover) {
    return `${base} background-image: url('${ev.cover}'); background-size: cover; background-position: center;`
  }
  // If no cover, use a brand gradient or solid placeholder
  return `${base} background: linear-gradient(135deg, var(--dark-green), var(--mint-green));`
}

// --- Details modal ---
const showModal = ref(false)
const selected = ref(null)
const openDetails = (ev) => {
  selected.value = ev
  showModal.value = true
}
const closeDetails = () => {
  showModal.value = false
  selected.value = null
}

// --- Registration (placeholder logic; replace with your real flow) ---
const register = (ev) => {
  alert(`Registering for: ${ev?.title || 'Event'}`)
}

// --- Editable cover (admin): file picker, local preview, localStorage persistence ---
const coverInputs = new Map()
const setCoverInputRef = (el, id) => {
  if (el) coverInputs.set(id, el)
}
const triggerCoverPicker = (id) => {
  const input = coverInputs.get(id)
  if (input) input.click()
}
const onCoverPicked = (e, ev) => {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    ev.cover = String(reader.result) // data URL, local preview
      localStorage.setItem(`eventCover:${ev.id}`, ev.cover)
    } catch {}
  }
  reader.readAsDataURL(file)
  // Clear the input so selecting the same file still triggers change
  e.target.value = ''
}
const resetCover = (ev) => {
  try { localStorage.removeItem(`eventCover:${ev.id}`) } catch {}
  ev.cover = null
}

// Initial load: restore persisted covers
onMounted(() => {
  events.value.forEach(ev => {
    try {
      const saved = localStorage.getItem(`eventCover:${ev.id}`)
      if (saved) ev.cover = saved
    } catch {}
  })
})

// Extensible: create event (admin only)
const createEvent = () => {
  alert('Create Event (demo)')
}
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

/* Two-column layout (single column on small screens) */
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

/* Reuse existing card styles with refinements */
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

/* Edit cover button (admins only) */
.edit-cover-btn {
  position: absolute;
  right: 10px;
  bottom: 10px;
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

/* CTA row */
.cta-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

/* Modal banner (matches card style) */
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
</style>
