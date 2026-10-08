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

        <div v-if="user.guardian.hasDetails" class="profile-section" data-test="guardian-details">
          <div class="guardian-heading">
            <h3 class="profile-section-title">Guardian Details</h3>
            <button
              v-if="!guardianEditing"
              class="btn btn-outline"
              type="button"
              data-test="guardian-edit"
              @click="startGuardianEdit"
            >
              Edit guardian
            </button>
          </div>

          <form
            v-if="guardianEditing"
            class="guardian-form"
            data-test="guardian-form"
            novalidate
            @submit.prevent="saveGuardian"
          >
            <p v-if="user.guardian.consentReceived" class="consent-hint guardian-form-hint">
              {{ user.guardian.consentingName }} has already given consent and stays on file
              until your new guardian completes the consent form.
            </p>
            <div class="profile-field guardian-form-field">
              <label class="profile-field-label" for="guardian-first-name">First name:</label>
              <div class="guardian-input-wrap">
                <input
                  id="guardian-first-name"
                  v-model.trim="guardianForm.first_name"
                  class="guardian-input"
                  type="text"
                  autocomplete="off"
                  required
                >
                <span v-if="guardianErrors.first_name" class="guardian-error">{{ guardianErrors.first_name }}</span>
              </div>
            </div>
            <div class="profile-field guardian-form-field">
              <label class="profile-field-label" for="guardian-last-name">Last name:</label>
              <div class="guardian-input-wrap">
                <input
                  id="guardian-last-name"
                  v-model.trim="guardianForm.last_name"
                  class="guardian-input"
                  type="text"
                  autocomplete="off"
                  required
                >
                <span v-if="guardianErrors.last_name" class="guardian-error">{{ guardianErrors.last_name }}</span>
              </div>
            </div>
            <div class="profile-field guardian-form-field">
              <label class="profile-field-label" for="guardian-email">Email:</label>
              <div class="guardian-input-wrap">
                <input
                  id="guardian-email"
                  v-model.trim="guardianForm.email"
                  class="guardian-input"
                  type="email"
                  autocomplete="off"
                  required
                >
                <span v-if="guardianErrors.email" class="guardian-error">{{ guardianErrors.email }}</span>
              </div>
            </div>
            <div class="guardian-actions">
              <button class="btn btn-outline" type="button" :disabled="guardianSaving" @click="cancelGuardianEdit">
                Cancel
              </button>
              <button class="btn btn-primary" type="submit" :disabled="guardianSaving" data-test="guardian-save">
                {{ guardianSaving ? 'Saving...' : 'Save guardian' }}
              </button>
            </div>
          </form>

          <div v-if="user.guardian.pending && !guardianEditing" class="guardian-pending" data-test="guardian-pending">
            <p>
              <strong>Change requested:</strong>
              {{ user.guardian.pending.name }} ({{ user.guardian.pending.email }}).
              Waiting for their consent — until then {{ user.guardian.consentingName }} stays on file.
            </p>
            <button
              class="btn btn-outline"
              type="button"
              :disabled="guardianSaving"
              data-test="guardian-withdraw"
              @click="withdrawGuardianChange"
            >
              {{ guardianSaving ? 'Withdrawing...' : 'Withdraw change' }}
            </button>
          </div>

          <div class="profile-field">
            <span class="profile-field-label">Name:</span>
            <span class="profile-field-value" data-test="guardian-name">{{ user.guardian.name }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Email:</span>
            <span class="profile-field-value" data-test="guardian-email">
              <a
                v-if="user.guardian.emailAddress"
                class="profile-link"
                :href="`mailto:${user.guardian.emailAddress}`"
              >
                {{ user.guardian.emailAddress }}
              </a>
              <span v-else>{{ unsetLabel }}</span>
            </span>
          </div>
          <div class="profile-field consent-field">
            <span class="profile-field-label">Consent:</span>
            <span class="profile-field-value">
              <span
                class="consent-status"
                :class="user.guardian.consentReceived ? 'consent-status--received' : 'consent-status--pending'"
                data-test="guardian-consent"
              >
                {{ user.guardian.consentReceived ? 'Received' : 'Not received yet' }}
              </span>
              <span v-if="user.guardian.consentReceivedOn" class="consent-hint" data-test="guardian-consent-date">
                Received on {{ user.guardian.consentReceivedOn }}
              </span>
              <span v-if="!user.guardian.consentReceived" class="consent-hint">
                Your parent or guardian needs to complete the consent form. Ask your supervisor if you're not sure how.
              </span>
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
import { computed, inject, nextTick, onMounted, ref, watch } from 'vue'
import { routeLocationKey } from 'vue-router'

import { buildSessionHeaders } from '@/utils/csrf'
import { useAuthStore } from '@/stores/auth'
import { apiErrorFromResponse } from '@/utils/apiError'
import { isPlaceholderGuardian } from '@/utils/guardian'
import { formatLongDateAU, formatTimeZoneLabel, getBrowserTimeZone, isValidTimeZone } from '@/utils/date'

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
  const consentReceived = source?.join_perm === true
  const guardianName = `${source?.pg_firstname || ''} ${source?.pg_lastname || ''}`.trim()
  const placeholderGuardian = isPlaceholderGuardian(source?.pg_firstname, source?.pg_lastname, source?.first_name, source?.last_name)
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
    guardian: {
      hasDetails: hasStudentDetails,
      name: (!placeholderGuardian && guardianName) || unsetLabel,
      consentingName: (!placeholderGuardian && guardianName) || 'Your current guardian',
      emailAddress: String(source?.pg_email || '').trim(),
      // null when there's no student profile behind the account; treat as not received.
      consentReceived,
      consentReceivedOn: consentReceived && source?.join_perm_granted_at
        ? formatLongDateAU(source.join_perm_granted_at)
        : '',
      pending: source?.pending_guardian
        ? {
          name: `${source.pending_guardian.first_name} ${source.pending_guardian.last_name}`.trim(),
          firstName: source.pending_guardian.first_name,
          lastName: source.pending_guardian.last_name,
          email: source.pending_guardian.email
        }
        : null,
      // Form defaults: blank when the guardian fields only hold the placeholder.
      firstName: placeholderGuardian ? '' : String(source?.pg_firstname || ''),
      lastName: placeholderGuardian ? '' : String(source?.pg_lastname || '')
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

const guardianEditing = ref(false)
const guardianSaving = ref(false)
const guardianForm = ref({ first_name: '', last_name: '', email: '' })
const guardianErrors = ref({})
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const startGuardianEdit = () => {
  const { guardian } = user.value
  // Editing a pending change picks up where the student left off.
  guardianForm.value = guardian.pending
    ? { first_name: guardian.pending.firstName, last_name: guardian.pending.lastName, email: guardian.pending.email }
    : { first_name: guardian.firstName, last_name: guardian.lastName, email: guardian.emailAddress }
  guardianErrors.value = {}
  error.value = ''
  guardianEditing.value = true
}

const cancelGuardianEdit = () => {
  guardianEditing.value = false
  guardianErrors.value = {}
}

const validateGuardianForm = () => {
  const errors = {}
  const form = guardianForm.value
  if (!form.first_name) errors.first_name = 'Enter their first name.'
  if (!form.last_name) errors.last_name = 'Enter their last name.'
  if (!form.email) {
    errors.email = 'Enter their email.'
  } else if (!EMAIL_PATTERN.test(form.email)) {
    errors.email = 'Enter a valid email address.'
  } else if (form.email.toLowerCase() === String(auth.user?.email || '').toLowerCase()) {
    errors.email = "Enter your parent or guardian's email, not your own."
  }
  guardianErrors.value = errors
  return Object.keys(errors).length === 0
}

const showStatus = (message) => {
  clearStatusMessageTimer()
  statusMessage.value = message
  statusMessageTimer = window.setTimeout(() => {
    statusMessage.value = ''
    statusMessageTimer = null
  }, 3200)
}

const saveGuardian = async () => {
  if (!validateGuardianForm()) return

  guardianSaving.value = true
  error.value = ''
  const hadConsent = user.value.guardian.consentReceived

  try {
    await auth.updateGuardian({ ...guardianForm.value })
    guardianEditing.value = false
    showStatus(hadConsent && user.value.guardian.pending
      ? 'Saved. Your new guardian needs to complete the consent form.'
      : 'Your guardian details have been updated.')
  } catch (saveError) {
    const fields = saveError?.fields || {}
    guardianErrors.value = Object.fromEntries(
      Object.entries(fields).map(([key, messages]) => [key, [].concat(messages)[0]])
    )
    if (!Object.keys(guardianErrors.value).length) {
      error.value = saveError instanceof Error
        ? saveError.message
        : 'Your guardian details could not be updated right now.'
    }
  } finally {
    guardianSaving.value = false
  }
}

const withdrawGuardianChange = async () => {
  guardianSaving.value = true
  error.value = ''

  try {
    await auth.withdrawGuardianChange()
    showStatus('The guardian change has been withdrawn.')
  } catch (withdrawError) {
    error.value = withdrawError instanceof Error
      ? withdrawError.message
      : 'The guardian change could not be withdrawn right now.'
  } finally {
    guardianSaving.value = false
  }
}

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

// The route, when the page runs under the router (tests may mount it bare).
const route = inject(routeLocationKey, null)

// The guardian details email links here with ?guardian=edit: open the form.
const openGuardianFromLink = async () => {
  if (route?.query?.guardian !== 'edit' || !user.value?.guardian?.hasDetails) return
  startGuardianEdit()
  await nextTick()
  document.querySelector('[data-test="guardian-details"]')?.scrollIntoView?.({ block: 'start' })
}

onMounted(async () => {
  await loadProfile()
  await openGuardianFromLink()
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

.consent-field {
  align-items: flex-start;
}

.consent-status {
  display: inline-flex;
  align-items: center;
  min-height: 1.75rem;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  font-size: 0.9rem;
  line-height: 1.2;
}

.consent-status--received {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

.consent-status--pending {
  border: 1px solid var(--warning);
  color: var(--charcoal);
}

.consent-hint {
  display: block;
  margin-top: 0.4rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.guardian-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.guardian-heading .btn {
  margin: 0;
}

.guardian-form {
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-light);
}

.guardian-form-hint {
  margin: 0 0 0.75rem;
}

.guardian-form-field {
  align-items: flex-start;
}

.guardian-input-wrap {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 0.3rem;
}

.guardian-input {
  width: min(100%, 360px);
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  color: var(--charcoal);
}

.guardian-error {
  color: var(--danger);
  font-size: 0.9rem;
}

.guardian-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.guardian-actions .btn,
.guardian-pending .btn {
  margin: 0;
}

.guardian-pending {
  margin-bottom: 1rem;
  padding: 0.85rem 1rem;
  border-left: 4px solid var(--warning);
  border-radius: 6px;
  background: var(--accent-green-soft);
}

.guardian-pending p {
  margin: 0 0 0.75rem;
  color: var(--charcoal);
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

  .timezone-actions,
  .guardian-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
