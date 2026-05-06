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
            <span class="profile-field-label">Account Status:</span>
            <span class="profile-field-value">{{ capitalise(user.accountStatus) }}</span>
          </div>
        </div>

        <div v-if="user.student.hasDetails" class="profile-section">
          <h3 class="profile-section-title">Student Details</h3>
          <div class="profile-field">
            <span class="profile-field-label">School:</span>
            <span class="profile-field-value">{{ user.student.schoolName }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Year Level:</span>
            <span class="profile-field-value">{{ user.student.yearLevel }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Parent/Guardian:</span>
            <span class="profile-field-value">{{ user.student.guardianName }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Join Permission:</span>
            <span class="profile-field-value">{{ user.student.joinPermission }}</span>
          </div>
        </div>

        <div v-if="user.mentor.hasDetails" class="profile-section">
          <h3 class="profile-section-title">Mentor Details</h3>
          <div class="profile-field">
            <span class="profile-field-label">Institution:</span>
            <span class="profile-field-value">{{ user.mentor.institution }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Mentor Reason:</span>
            <span class="profile-field-value">{{ user.mentor.reason }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Max Groups:</span>
            <span class="profile-field-value">{{ user.mentor.maxGroups }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { buildSessionHeaders } from '@/utils/csrf'
import { useAuthStore } from '@/stores/auth'
import { apiErrorFromResponse } from '@/utils/apiError'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const auth = useAuthStore()

const loading = ref(false)
const error = ref('')
const trackById = ref(new Map())

const valueOrFallback = (value, fallback = 'Not provided') => {
  const text = String(value ?? '').trim()
  return text || fallback
}

const user = computed(() => {
  const source = auth.user
  const fullName = `${source?.first_name || ''} ${source?.last_name || ''}`.trim() || source?.email || 'User'
  const roleName = String(source?.current_role_name || auth.roleLabel || 'Member').trim()
  const trackId = Number(source?.track)
  const guardianName = `${source?.pg_firstname || ''} ${source?.pg_lastname || ''}`.trim()
  const hasStudentDetails = [source?.school_name, source?.year_lvl, guardianName].some(Boolean) || source?.join_perm != null
  const hasMentorDetails = [source?.ment_inst, source?.ment_reason, source?.ment_max_groups].some(value => value !== null && value !== undefined && value !== '')

  return {
    name: fullName,
    email: source?.email || 'Unavailable',
    role: roleName || 'Member',
    accountStatus: source?.account_status || 'Unavailable',
    track: trackById.value.get(trackId) || (source?.track ? `Track ${source.track}` : 'Unassigned'),
    student: {
      hasDetails: hasStudentDetails,
      schoolName: valueOrFallback(source?.school_name),
      yearLevel: valueOrFallback(source?.year_lvl),
      guardianName: valueOrFallback(guardianName),
      joinPermission: source?.join_perm === true ? 'Granted' : source?.join_perm === false ? 'Not granted' : 'Not provided'
    },
    mentor: {
      hasDetails: hasMentorDetails,
      institution: valueOrFallback(source?.ment_inst),
      reason: valueOrFallback(source?.ment_reason),
      maxGroups: valueOrFallback(source?.ment_max_groups)
    }
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

  if (!response.ok) {
    throw await apiErrorFromResponse(response)
  }

  const text = await response.text()
  const data = text ? JSON.parse(text) : null

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
