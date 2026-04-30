<template>
  <div class="content-area">
    <div v-if="error" class="card" style="margin-bottom:1rem;border-left:4px solid var(--danger);">
      <p style="margin:0;color:#6c757d;">{{ error }}</p>
    </div>

    <div class="card" style="overflow:hidden;padding:0;">
      <div class="profile-header">
        <div class="profile-avatar-large">{{ getInitials(user.name) }}</div>
        <h2 class="profile-name">{{ user.name }}</h2>
        <p class="profile-role">{{ capitalise(user.role) }} | {{ user.track }}</p>
      </div>

      <div class="profile-content">
        <div v-if="loading" class="profile-section">
          <p style="margin:0;color:#6c757d;">Loading your profile...</p>
        </div>

        <div class="profile-section">
          <h3 class="profile-section-title">Personal Information</h3>
          <div class="profile-field">
            <span class="profile-field-label">Email:</span>
            <span class="profile-field-value">{{ user.email }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Track/Region:</span>
            <span class="profile-field-value">{{ user.track }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Role:</span>
            <span class="profile-field-value">{{ capitalise(user.role) }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Profile Source:</span>
            <span class="profile-field-value">Live backend session</span>
          </div>
        </div>

        <div class="profile-section">
          <h3 class="profile-section-title">Interests & Expertise</h3>
          <div style="display:flex;flex-wrap:wrap;gap:0.5rem;">
            <span
              v-for="interest in interests"
              :key="interest"
              class="status-badge"
              style="background-color:var(--light-green);color:var(--dark-green);"
            >{{ interest }}</span>

            <div style="display:flex;gap:0.5rem;align-items:center;">
              <input v-model="newInterest" class="form-control" placeholder="Add interest" style="width:220px;" />
              <button class="btn btn-outline btn-sm" @click="addInterest">+ Add</button>
            </div>
          </div>
        </div>

        <div class="profile-section">
          <h3 class="profile-section-title">Contact Preferences</h3>
          <div class="form-group">
            <label class="form-label">Preferred Contact Method</label>
            <select v-model="contactMethod" class="form-control">
              <option>Email</option>
              <option>Platform Messages</option>
              <option>Both</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Availability</label>
            <textarea v-model="availability" class="form-control" rows="3" placeholder="Enter your general availability..."></textarea>
          </div>
          <p style="margin:0.75rem 0 0;color:#6c757d;">
            The profile header now loads from the backend. These editable preference fields are still local-only until a profile update API is available.
          </p>
        </div>

        <div style="display:flex;justify-content:flex-end;gap:1rem;">
          <button class="btn btn-outline" @click="reset">Cancel</button>
          <button class="btn btn-primary" @click="save">Save Changes</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { buildSessionHeaders } from '@/utils/csrf'
import { useAuthStore } from '@/stores/auth'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const auth = useAuthStore()

const loading = ref(false)
const error = ref('')
const trackById = ref(new Map())

const original = {
  contactMethod: 'Both',
  availability: '',
  interests: ['Biotechnology', 'Research', 'Mentoring', 'Innovation']
}

const contactMethod = ref(original.contactMethod)
const availability = ref(original.availability)
const interests = ref([...original.interests])
const newInterest = ref('')

const user = computed(() => {
  const source = auth.user
  const fullName = `${source?.first_name || ''} ${source?.last_name || ''}`.trim() || source?.email || 'User'
  const roleName = String(source?.current_role_name || auth.roleLabel || 'Member').trim()
  const trackId = Number(source?.track)

  return {
    name: fullName,
    email: source?.email || 'Unavailable',
    role: roleName || 'Member',
    track: trackById.value.get(trackId) || (source?.track ? `Track ${source.track}` : 'Unassigned')
  }
})

const getInitials = (name) => String(name || 'U')
  .split(' ')
  .filter(Boolean)
  .map((part) => part[0])
  .join('')
  .toUpperCase()
  .slice(0, 2) || 'U'

const capitalise = (value) => {
  const text = String(value || '').trim()
  if (!text) return 'Member'
  return text
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ')
}

const addInterest = () => {
  const value = newInterest.value.trim()
  if (!value) return
  if (!interests.value.includes(value)) interests.value.push(value)
  newInterest.value = ''
}

const reset = () => {
  contactMethod.value = original.contactMethod
  availability.value = original.availability
  interests.value = [...original.interests]
  newInterest.value = ''
  alert('Local preference changes were discarded.')
}

const save = () => {
  alert('Profile header data is live. Preference editing is not connected to a backend update API yet.')
}

async function loadTracks() {
  const response = await fetch(`${API_BASE_URL}/groups/tracks/?page_size=100`, {
    method: 'GET',
    credentials: 'include',
    headers: buildSessionHeaders({
      headers: {
        Accept: 'application/json'
      }
    })
  })

  const text = await response.text()
  const data = text ? JSON.parse(text) : null

  if (!response.ok) {
    throw new Error(data?.detail || data?.error || `Request failed: ${response.status}`)
  }

  const items = Array.isArray(data?.results) ? data.results : (Array.isArray(data) ? data : [])
  trackById.value = new Map(
    items
      .map((track) => [Number(track?.id), track?.track_name])
      .filter((entry) => entry[0] && entry[1])
  )
}

async function loadProfile() {
  loading.value = true
  error.value = ''

  try {
    await Promise.all([
      auth.fetchUserData(),
      loadTracks()
    ])

    if (!auth.user) {
      throw new Error('Your current user profile could not be loaded.')
    }
  } catch (loadError) {
    error.value = loadError instanceof Error
      ? loadError.message
      : 'Your profile could not be loaded right now.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadProfile()
})
</script>
