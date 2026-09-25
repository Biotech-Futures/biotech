<template>
  <div class="content-area">
    <div v-if="error" class="card" style="margin-bottom:1rem;border-left:4px solid var(--danger);">
      <p style="margin:0;color:#6c757d;">{{ error }}</p>
    </div>
    <Transition name="status-fade">
      <div v-if="statusMessage" class="card status-card">
        <p>{{ statusMessage }}</p>
      </div>
    </Transition>

    <div v-if="loading" class="profile-loading" role="status" aria-live="polite">
      <span class="sr-only">Loading your profile...</span>
      <div class="profile-loading-header">
        <div class="profile-loading-avatar skeleton-block"></div>
        <div class="profile-loading-title skeleton-block"></div>
        <div class="profile-loading-subtitle skeleton-block"></div>
      </div>
      <div class="profile-loading-content">
        <section
          v-for="section in 3"
          :key="`profile-loading-section-${section}`"
          class="profile-loading-section"
        >
          <div class="profile-loading-heading skeleton-block"></div>
          <div
            v-for="row in 4"
            :key="`profile-loading-row-${section}-${row}`"
            class="profile-loading-row"
          >
            <div class="profile-loading-label skeleton-block"></div>
            <div class="profile-loading-value skeleton-block"></div>
          </div>
        </section>
      </div>
    </div>

    <div v-else-if="auth.user" class="card" style="overflow:hidden;padding:0;">
      <div class="profile-header">
        <div class="profile-avatar-large">{{ getInitials(user.name) }}</div>
        <h2 class="profile-name">{{ user.name }}</h2>
        <p class="profile-role">{{ capitalise(user.role) }} | {{ user.country }}</p>
      </div>

      <div class="profile-content">
        <div class="profile-section">
          <h3 class="profile-section-title">Personal Information</h3>
          <div class="profile-field">
            <span class="profile-field-label">Email:</span>
            <span class="profile-field-value">{{ user.email }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Country:</span>
            <span class="profile-field-value">{{ user.country }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Region:</span>
            <span class="profile-field-value">{{ user.region }}</span>
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

        <div class="profile-section">
          <h3 class="profile-section-title">Timezone</h3>
          <div class="profile-field">
            <span class="profile-field-label">Current timezone:</span>
            <span class="profile-field-value">{{ formatTimeZoneLabel(auth.timeZone) }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">This device:</span>
            <span class="profile-field-value">{{ formatTimeZoneLabel(browserTimeZone) }}</span>
          </div>
          <div class="profile-field timezone-field">
            <label class="profile-field-label" for="timezone-input">Set timezone:</label>
            <div class="timezone-control">
              <select
                id="timezone-input"
                v-model="selectedTimeZone"
                class="timezone-input"
              >
                <option
                  v-for="zone in timeZoneOptions"
                  :key="zone"
                  :value="zone"
                >
                  {{ formatTimeZoneLabel(zone) }}
                </option>
              </select>
              <div class="timezone-actions">
                <button
                  class="btn btn-outline"
                  type="button"
                  @click="useBrowserTimeZone"
                >
                  Use device timezone
                </button>
                <button
                  class="btn btn-primary"
                  type="button"
                  :disabled="timezoneSaving || !timezoneChanged"
                  @click="saveTimeZone"
                >
                  {{ timezoneSaving ? 'Saving...' : 'Save timezone' }}
                </button>
              </div>
            </div>
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
            <span class="profile-field-label">Areas of Interest:</span>
            <span class="profile-field-value">
              <span v-if="user.student.interests.length" class="profile-interest-list">
                <span
                  v-for="interest in user.student.interests"
                  :key="interest"
                  class="profile-interest"
                >
                  {{ interest }}
                </span>
              </span>
              <span v-else>{{ unsetLabel }}</span>
            </span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Supervisor:</span>
            <span class="profile-field-value">{{ user.student.supervisorName }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Supervisor Email:</span>
            <span class="profile-field-value">
              <a
                v-if="user.student.supervisorEmailAddress"
                class="profile-link"
                :href="`mailto:${user.student.supervisorEmailAddress}`"
              >
                {{ user.student.supervisorEmailAddress }}
              </a>
              <span v-else>{{ user.student.supervisorEmail }}</span>
            </span>
          </div>
        </div>

        <div v-if="user.mentor.hasDetails" class="profile-section">
          <h3 class="profile-section-title">Mentor Details</h3>
          <div class="profile-field">
            <span class="profile-field-label">Background:</span>
            <span class="profile-field-value">{{ user.mentor.background }}</span>
          </div>
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

        <div v-if="user.supervisor.hasDetails" class="profile-section">
          <h3 class="profile-section-title">Supervisor Details</h3>
          <div class="profile-field">
            <span class="profile-field-label">School:</span>
            <span class="profile-field-value">{{ user.supervisor.schoolName }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Supervised Students:</span>
            <span class="profile-field-value">{{ user.supervisor.studentSummary }}</span>
          </div>
          <div
            v-for="student in user.supervisor.students"
            :key="student.id"
            class="profile-field"
          >
            <span class="profile-field-label">{{ student.relationship }}:</span>
            <span class="profile-field-value">{{ student.name }} ({{ student.email }})</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import { buildSessionHeaders } from '@/utils/csrf'
import { useAuthStore } from '@/stores/auth'
import { apiErrorFromResponse } from '@/utils/apiError'
import { formatTimeZoneLabel, getBrowserTimeZone, isValidTimeZone } from '@/utils/date'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const auth = useAuthStore()

const loading = ref(true)
const error = ref('')
const statusMessage = ref('')
const timezoneSaving = ref(false)
const browserTimeZone = getBrowserTimeZone()
const selectedTimeZone = ref('UTC')
const unsetLabel = 'Not set'
let statusMessageTimer = null
const commonTimeZones = [
  'UTC',
  'Australia/Sydney',
  'Australia/Melbourne',
  'Australia/Brisbane',
  'Australia/Adelaide',
  'Australia/Darwin',
  'Australia/Perth',
  'Australia/Hobart',
  'Pacific/Auckland',
  'Pacific/Fiji',
  'Asia/Shanghai',
  'Asia/Hong_Kong',
  'Asia/Taipei',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Asia/Seoul',
  'Asia/Bangkok',
  'Asia/Jakarta',
  'Asia/Kolkata',
  'Asia/Dubai',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Europe/Madrid',
  'Europe/Rome',
  'Europe/Amsterdam',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Toronto',
  'America/Vancouver',
  'America/Sao_Paulo',
  'Africa/Johannesburg'
]

const timeZoneOptions = computed(() => {
  return Array.from(new Set([
    auth.timeZone,
    browserTimeZone,
    ...commonTimeZones
  ])).filter(Boolean).sort((a, b) => a.localeCompare(b))
})

const timezoneChanged = computed(() => selectedTimeZone.value !== auth.timeZone)

watch(
  () => auth.timeZone,
  (timezone) => {
    selectedTimeZone.value = timezone
  },
  { immediate: true }
)

const useBrowserTimeZone = () => {
  selectedTimeZone.value = browserTimeZone
  statusMessage.value = ''
  clearStatusMessageTimer()
}

const saveTimeZone = async () => {
  statusMessage.value = ''
  clearStatusMessageTimer()

  if (!isValidTimeZone(selectedTimeZone.value)) {
    error.value = 'Please enter a valid IANA timezone, such as Australia/Sydney.'
    return
  }

  timezoneSaving.value = true
  error.value = ''

  try {
    await auth.updateTimeZone(selectedTimeZone.value)
    statusMessage.value = 'Your timezone has been updated.'
    statusMessageTimer = window.setTimeout(() => {
      statusMessage.value = ''
      statusMessageTimer = null
    }, 3200)
  } catch (saveError) {
    error.value = saveError instanceof Error
      ? saveError.message
      : 'Your timezone could not be updated right now.'
  } finally {
    timezoneSaving.value = false
  }
}

const clearStatusMessageTimer = () => {
  if (!statusMessageTimer) return
  window.clearTimeout(statusMessageTimer)
  statusMessageTimer = null
}

const valueOrFallback = (value, fallback = 'Not provided') => {
  const text = String(value ?? '').trim()
  return text || fallback
}

const listOrEmpty = (value) => {
  if (!Array.isArray(value)) return []

  return value
    .map((item) => String(item ?? '').trim())
    .filter(Boolean)
}

const normaliseRole = (value) => {
  const role = String(value || '').trim().toLowerCase()
  if (role.includes('admin')) return 'admin'
  if (role.includes('mentor') || role === 'teacher') return 'mentor'
  if (role.includes('supervisor')) return 'supervisor'
  if (role.includes('student')) return 'student'
  return 'member'
}

const user = computed(() => {
  const source = auth.user
  const fullName = `${source?.first_name || ''} ${source?.last_name || ''}`.trim() || source?.email || 'User'
  const roleName = String(source?.current_role_name || auth.roleLabel || 'Member').trim()
  const roleKey = normaliseRole(roleName)
  const interests = listOrEmpty(source?.interests)
  const supervisorEmail = valueOrFallback(source?.supervisor_email, unsetLabel)
  const supervisorEmailAddress = String(source?.supervisor_email || '').trim()
  const supervisedStudents = Array.isArray(source?.supervised_students)
    ? source.supervised_students.map((student) => {
      const name = `${student?.first_name || ''} ${student?.last_name || ''}`.trim() || student?.email || 'Student'
      return {
        id: student?.id || student?.email || name,
        name,
        email: valueOrFallback(student?.email),
        relationship: capitalise(student?.relationship_type || 'student')
      }
    })
    : []
  const hasStudentDetails = roleKey === 'student'
  const hasMentorDetails = roleKey === 'mentor' && [source?.ment_bg, source?.ment_inst, source?.ment_reason, source?.ment_max_groups].some(value => value !== null && value !== undefined && value !== '')
  const hasSupervisorDetails = roleKey === 'supervisor' && ([source?.supervisor_school_name].some(Boolean) || supervisedStudents.length > 0)

  return {
    name: fullName,
    email: source?.email || 'Unavailable',
    role: roleName || 'Member',
    accountStatus: source?.account_status || 'Unavailable',
    country: source?.country?.countryName || 'Unassigned',
    // Sub-national only, and blank for most non-Australian users — not a gap to flag.
    region: source?.state?.stateName || unsetLabel,
    student: {
      hasDetails: hasStudentDetails,
      schoolName: valueOrFallback(source?.school_name, unsetLabel),
      yearLevel: valueOrFallback(source?.year_lvl, unsetLabel),
      interests,
      supervisorName: valueOrFallback(source?.supervisor_name, unsetLabel),
      supervisorEmail,
      supervisorEmailAddress
    },
    mentor: {
      hasDetails: hasMentorDetails,
      background: valueOrFallback(source?.ment_bg),
      institution: valueOrFallback(source?.ment_inst),
      reason: valueOrFallback(source?.ment_reason),
      maxGroups: valueOrFallback(source?.ment_max_groups)
    },
    supervisor: {
      hasDetails: hasSupervisorDetails,
      schoolName: valueOrFallback(source?.supervisor_school_name),
      studentSummary: supervisedStudents.length === 1
        ? '1 student'
        : `${supervisedStudents.length} students`,
      students: supervisedStudents
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

async function loadProfile() {
  loading.value = true
  error.value = ''

  try {
    await auth.fetchUserData()

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

<style scoped>
.profile-loading {
  overflow: hidden;
  border-radius: 8px;
  background: var(--white);
  box-shadow: 0 2px 4px var(--shadow);
}

.profile-loading-header {
  display: flex;
  min-height: 180px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.85rem;
  padding: 2rem;
  background: linear-gradient(135deg, var(--dark-green), var(--mint-green));
}

.profile-loading-content {
  padding: 2rem;
}

.profile-loading-section {
  padding: 1.5rem 0;
  border-bottom: 1px solid var(--border-light);
}

.profile-loading-section:first-child {
  padding-top: 0;
}

.profile-loading-section:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.profile-loading-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.5rem 0;
}

.skeleton-block {
  position: relative;
  overflow: hidden;
  border-radius: 6px;
  background: #e9ecef;
}

.profile-loading-avatar {
  width: 82px;
  height: 82px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.35);
}

.profile-loading-title {
  width: min(280px, 68%);
  height: 26px;
  background: rgba(255, 255, 255, 0.55);
}

.profile-loading-subtitle {
  width: min(220px, 58%);
  height: 16px;
  background: rgba(255, 255, 255, 0.42);
}

.profile-loading-heading {
  width: 180px;
  height: 20px;
  margin-bottom: 1rem;
}

.profile-loading-label {
  width: 140px;
  height: 16px;
}

.profile-loading-value {
  width: min(320px, 55%);
  height: 16px;
}

.status-card {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 1000;
  width: min(360px, calc(100vw - 2rem));
  margin-bottom: 0;
  border-left: 4px solid var(--dark-green);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.14);
}

.status-card p {
  margin: 0;
  color: #6c757d;
}

.status-fade-enter-active,
.status-fade-leave-active {
  transition:
    opacity 0.25s ease,
    transform 0.25s ease;
}

.status-fade-enter-from,
.status-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.timezone-field {
  align-items: flex-start;
}

.timezone-control {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 0.75rem;
}

.timezone-input {
  width: min(100%, 360px);
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  color: var(--charcoal);
}

.timezone-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.timezone-actions .btn {
  margin: 0;
}

.profile-interest-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.profile-interest {
  display: inline-flex;
  align-items: center;
  min-height: 1.75rem;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background: var(--accent-green-soft);
  color: var(--dark-green);
  font-size: 0.9rem;
  line-height: 1.2;
}

.profile-link {
  color: var(--dark-green);
  overflow-wrap: anywhere;
}

@media (max-width: 640px) {
  .status-card {
    top: 0.75rem;
    right: 0.75rem;
    width: calc(100vw - 1.5rem);
  }

  .profile-loading-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .profile-loading-value {
    width: 100%;
  }

  :deep(.profile-field) {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.35rem;
  }

  :deep(.profile-field-label) {
    width: auto;
  }

  .timezone-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
