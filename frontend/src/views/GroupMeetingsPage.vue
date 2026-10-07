<template>
  <div
    class="meetings-page"
    :class="{ 'meetings-page--embedded': props.embedded }"
  >
    <div
      class="page-header"
      :class="{ 'page-header--embedded': props.embedded }"
    >
      <div>
        <h1>{{ props.embedded ? 'Meetings' : 'Group Meetings' }}</h1>

        <p
          v-if="!props.embedded"
          class="subtitle"
        >
          View upcoming and past meetings for your group.
        </p>
      </div>

      <button
        v-if="auth.isMentor"
        class="primary-button"
        @click="showCreateForm = !showCreateForm"
      >
        {{ showCreateForm ? 'Close' : '+ Schedule Meeting' }}
      </button>
    </div>

    <section
      v-if="showCreateForm && auth.isMentor"
      class="create-form"
    >
    <h2>Schedule Meeting</h2>

      <label>
        <span>Title <span class="required-mark">*</span></span>
        <input
          v-model="newTitle"
          type="text"
          class="form-input"
          :class="{ 'form-input--error': formErrors.title }"
          placeholder="Enter meeting title"
          @input="formErrors.title = ''"
        />

        <span v-if="formErrors.title" class="field-error">
          {{ formErrors.title }}
        </span>
      </label>

      <label>
        <span>Description</span>
        <textarea
          v-model="newDescription"
          class="form-input"
          rows="3"
          placeholder="Enter meeting description"
        ></textarea>
      </label>

      <label>
        <span>Start <span class="required-mark">*</span></span>
        <input
          v-model="newStart"
          type="datetime-local"
          class="form-input"
          :class="{ 'form-input--error': formErrors.start }"
          @input="formErrors.start = ''"
        />
        <span v-if="formErrors.start" class="field-error">
          {{ formErrors.start }}
        </span>
      </label>

    <label>
      <span>Duration <span class="required-mark">*</span></span>
      <input
        v-model="newDuration"
        type="number"
        min="5"
        max="480"
        step="5"
        class="form-input"
        :class="{ 'form-input--error': formErrors.duration }"
        placeholder="Enter duration in minutes"
        @input="formErrors.duration = ''"
      />
      <span v-if="formErrors.duration" class="field-error">
        {{ formErrors.duration }}
      </span>
    </label>

    <label>
        Timezone
        <input
        v-model="newTimezone"
        type="text"
        class="form-input"
        />
    </label>

    <label>
      <span>Join Link <span class="required-mark">*</span></span>

      <input
        v-model="newJoinLink"
        type="url"
        class="form-input"
        :class="{ 'form-input--error': formErrors.joinLink }"
        placeholder="https://..."
        @input="formErrors.joinLink = ''"
      />

      <span v-if="formErrors.joinLink" class="field-error">
        {{ formErrors.joinLink }}
      </span>
    </label>

    <div class="create-actions">
        <button
        class="primary-button"
        :disabled="creatingMeeting"
        @click="submitMeeting"
        >
        {{ creatingMeeting ? 'Scheduling...' : 'Schedule Meeting' }}
        </button>
    </div>
    </section>

    <p v-if="createMessage" class="create-message">
    {{ createMessage }}
    </p>

    <div class="tabs">
      <button
        class="tab-button"
        :class="{ active: selectedWhen === 'upcoming' }"
        @click="changeTab('upcoming')"
      >
        Upcoming
      </button>

      <button
        class="tab-button"
        :class="{ active: selectedWhen === 'past' }"
        @click="changeTab('past')"
      >
        Past
      </button>
    </div>

    <div v-if="isLoading" class="state-message">
      Loading meetings...
    </div>

    <div v-else-if="errorMessage" class="state-message error">
      {{ errorMessage }}
    </div>

    <div v-else-if="meetings.length === 0" class="state-message">
      No {{ selectedWhen }} meetings found.
    </div>

    <div v-else class="meeting-list">
      <article
        v-for="meeting in meetings"
        :key="meeting.id"
        class="meeting-card"
      >
        <div class="meeting-header">
          <div>
            <h2>{{ meeting.title }}</h2>

            <p class="meeting-time">
              {{ formatMeetingDate(meeting.start_datetime) }}
            </p>
          </div>

          <span
            v-if="meeting.can_manage"
            class="manage-badge"
          >
            You can manage
          </span>
        </div>

        <p
          v-if="meeting.description"
          class="description"
        >
          {{ meeting.description }}
        </p>

        <div class="meeting-actions">
          <a
            v-if="meeting.join_link && selectedWhen === 'upcoming'"
            :href="meeting.join_link"
            target="_blank"
            rel="noopener noreferrer"
            class="primary-button"
          >
            <img
              v-if="providerLogo(meeting.provider)"
              :src="providerLogo(meeting.provider)!"
              :alt="`${meeting.provider} logo`"
              class="meeting-provider-icon"
            />

            <i
              v-else
              class="fas fa-video meeting-provider-icon--generic"
              aria-hidden="true"
            ></i>

            Join Meeting
          </a>

          <button
            class="secondary-button"
            @click="viewMeeting(meeting.id)"
          >
            View Details
          </button>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import zoomLogo from '@/assets/meeting-providers/zoom.webp'
import googleMeetLogo from '@/assets/meeting-providers/google-meet.webp'
import teamsLogo from '@/assets/meeting-providers/microsoft-teams.webp'

import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

import {
  fetchMeetings,
  createMeeting,
  type GroupMeeting,
  type MeetingWhen,
} from '@/utils/meetingsAPI'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const providerLogo = (provider: GroupMeeting['provider']) => {
  switch (provider) {
    case 'zoom':
      return zoomLogo
    case 'google_meet':
      return googleMeetLogo
    case 'microsoft_teams':
      return teamsLogo
    default:
      return null
  }
}

const props = withDefaults(
  defineProps<{
    embedded?: boolean
  }>(),
  {
    embedded: false,
  }
)

const meetings = ref<GroupMeeting[]>([])
const selectedWhen = ref<MeetingWhen>('upcoming')

const isLoading = ref(false)
const errorMessage = ref('')
const showCreateForm = ref(false)
const creatingMeeting = ref(false)
const createMessage = ref('')

const newTitle = ref('')
const newDescription = ref('')
const newStart = ref('')
const newDuration = ref('')
const newTimezone = ref('Australia/Sydney')
const newJoinLink = ref('')

const formErrors = ref({
  title: '',
  start: '',
  duration: '',
  timezone: '',
  joinLink: '',
})

const getGroupId = (): number | undefined => {
  const rawId = route.params.id

  if (!rawId) return undefined

  const id = Number(rawId)

  return Number.isFinite(id) ? id : undefined
}

const loadMeetings = async () => {
  isLoading.value = true
  errorMessage.value = ''

  try {
    const response = await fetchMeetings({
      group: getGroupId(),
      when: selectedWhen.value,
      page_size: 100,
    })

    meetings.value = response.results ?? []
  } catch (error) {
    console.error('Failed to load meetings:', error)

    errorMessage.value =
      error instanceof Error
        ? error.message
        : 'Failed to load meetings.'

    meetings.value = []
  } finally {
    isLoading.value = false
  }
}

const changeTab = (when: MeetingWhen) => {
  selectedWhen.value = when
}

const viewMeeting = (meetingId: number) => {
  router.push({
    name: 'group-meeting-detail',
    params: {
      id: route.params.id,
      meetingId,
    },
  })
}

const submitMeeting = async () => {
  const groupId = getGroupId()

  if (!groupId) {
    createMessage.value = 'Unable to determine the group.'
    return
  }

  // Clear previous validation errors
  formErrors.value = {
    title: '',
    start: '',
    duration: '',
    timezone: '',
    joinLink: '',
  }

  // Required fields
  if (!newTitle.value.trim()) {
    formErrors.value.title = 'Title is required.'
  }

  if (!newStart.value) {
    formErrors.value.start = 'Start time is required.'
  }

  if (!newDuration.value) {
    formErrors.value.duration = 'Duration is required.'
  } else {
    const duration = Number(newDuration.value)

    if (!Number.isInteger(duration) || duration < 5 || duration > 480) {
      formErrors.value.duration =
        'Duration must be between 5 and 480 minutes.'
    }
  }

  if (!newTimezone.value.trim()) {
    formErrors.value.timezone = 'Timezone is required.'
  }

  if (!newJoinLink.value.trim()) {
    formErrors.value.joinLink = 'Join link is required.'
  } else {
    try {
      const url = new URL(newJoinLink.value)

      if (url.protocol !== 'http:' && url.protocol !== 'https:') {
        formErrors.value.joinLink = 'Enter a valid URL.'
      }
    } catch {
      formErrors.value.joinLink = 'Enter a valid URL.'
    }
  }

  const hasErrors = Object.values(formErrors.value).some(Boolean)

  if (hasErrors) {
    return
  }

  creatingMeeting.value = true
  createMessage.value = ''

  try {
    await createMeeting({
      group: groupId,
      title: newTitle.value,
      description: newDescription.value,
      start_datetime: new Date(newStart.value).toISOString(),
      duration_minutes: Number(newDuration.value),
      timezone_name: newTimezone.value,
      join_link: newJoinLink.value,
    })

    showCreateForm.value = false

    newTitle.value = ''
    newDescription.value = ''
    newStart.value = ''
    newDuration.value = ''
    newJoinLink.value = ''

    selectedWhen.value = 'upcoming'
    await loadMeetings()

    createMessage.value = 'Meeting scheduled successfully.'
  } catch (error) {
    console.error('Failed to create meeting:', error)

    createMessage.value =
      error instanceof Error
        ? error.message
        : 'Unable to schedule meeting.'
  } finally {
    creatingMeeting.value = false
  }
}

const getMeetingProviderIcon = (provider: GroupMeeting['provider']) => {
  switch (provider) {
    case 'zoom':
      return 'fas fa-video'

    case 'google_meet':
      return 'fab fa-google'

    case 'microsoft_teams':
      return 'fab fa-microsoft'

    default:
      return 'fas fa-video'
  }
}

const formatMeetingDate = (dateString: string) => {
  const date = new Date(dateString)

  if (Number.isNaN(date.getTime())) {
    return dateString
  }

  return new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)
}

watch(
  () => route.params.id,
  () => {
    loadMeetings()
  }
)

watch(selectedWhen, () => {
  loadMeetings()
})

onMounted(() => {
  loadMeetings()
})
</script>

<style scoped>
.required-mark {
  color: #d32f2f;
  font-weight: 700;
}

.form-input--error {
  border: 1px solid #d32f2f !important;
}

.field-error {
  display: block;
  margin-top: 5px;
  color: #d32f2f !important;
}

.field-error {
  display: block;
  margin-top: 5px;
  color: #d32f2f !important;
  font-size: 12px;
  font-weight: 500;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 24px;
}

.page-header h1 {
  margin: 0;
}

.page-header .subtitle {
  margin: 6px 0 0;
  color: #666;
}

.subtitle {
  margin-top: 8px;
  color: #666;
}

.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}

.tab-button {
  border: none;
  background: transparent;
  padding: 10px 18px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 15px;
}

.tab-button.active {
  background: #eeeeee;
  font-weight: 600;
}

.state-message {
  padding: 40px;
  text-align: center;
  color: #666;
}

.state-message.error {
  color: #b42318;
}

.meeting-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.meeting-card {
  border: 1px solid #dddddd;
  border-radius: 12px;
  padding: 22px;
  background: white;
}

.meeting-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.meeting-header h2 {
  margin: 0 0 8px;
  font-size: 21px;
}

.meeting-time {
  margin: 0;
  color: #666;
}

.manage-badge {
  height: fit-content;
  padding: 6px 10px;
  border-radius: 999px;
  background: #f1f1f1;
  font-size: 13px;
  white-space: nowrap;
}

.description {
  margin-top: 18px;
  line-height: 1.6;
}


.meeting-actions {
  display: flex;
  gap: 10px;
  margin-top: 22px;
}

.primary-button,
.secondary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 0 16px;
  border-radius: 8px;
  font-size: 14px;
  text-decoration: none;
  cursor: pointer;
}

.primary-button {
  border: none;
  background: #222;
  color: white;
}

.secondary-button {
  border: 1px solid #cccccc;
  background: white;
  color: #222;
}

.create-form {
  border: 1px solid #dddddd;
  border-radius: 12px;
  padding: 22px;
  margin-bottom: 24px;
  background: white;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.create-form h2 {
  margin: 0;
}

.create-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-weight: 600;
}

.form-input {
  padding: 10px 12px;
  border: 1px solid #cccccc;
  border-radius: 8px;
  font: inherit;
}

.create-actions {
  display: flex;
  justify-content: flex-end;
}

.create-message {
  margin-bottom: 20px;
  color: #444;
}

/* Compact layout when Meetings is embedded inside GroupDetailPage */
.meetings-page--embedded {
  max-width: none;
  margin: 0;
  padding: 20px 16px;
}

.meetings-page--embedded .page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.meetings-page--embedded .page-header h1 {
  margin: 0;
  font-size: 20px;
  line-height: 1.2;
}

.meetings-page--embedded .primary-button {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 6px;
  font-size: 12px;
}

.meetings-page--embedded .tabs {
  gap: 6px;
  margin-bottom: 14px;
}

.meetings-page--embedded .tab-button {
  padding: 7px 12px;
  border-radius: 6px;
  font-size: 13px;
}

.meetings-page--embedded .state-message {
  padding: 28px 12px;
  font-size: 14px;
}

.meetings-page--embedded .meeting-list {
  gap: 10px;
}

.meetings-page--embedded .meeting-card {
  padding: 14px;
  border-radius: 8px;
}

.meetings-page--embedded .meeting-header {
  gap: 8px;
}

.meetings-page--embedded .meeting-header h2 {
  margin-bottom: 5px;
  font-size: 16px;
}

.meetings-page--embedded .meeting-time {
  font-size: 13px;
}

.meetings-page--embedded .manage-badge {
  padding: 4px 7px;
  font-size: 11px;
}

.meetings-page--embedded .description{
  margin-top: 10px;
  font-size: 13px;
}

.meetings-page--embedded .meeting-actions {
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.meetings-page--embedded .secondary-button {
  min-height: 32px;
  padding: 0 10px;
  font-size: 12px;
}

.meetings-page--embedded .create-form {
  padding: 14px;
  margin-bottom: 16px;
  gap: 12px;
}

.meetings-page--embedded .create-form h2 {
  font-size: 18px;
}

.meetings-page--embedded .form-input {
  padding: 8px 10px;
  font-size: 13px;
}

.meeting-provider-icon {
  width: 20px;
  height: 20px;
  object-fit: contain;
}

.meeting-provider-icon--generic {
  font-size: 18px;
}

/* =========================================================
   Meetings — dark mode
   ========================================================= */

:global(html[data-theme='dark']) .meetings-page {
  color: #e8eeee;
}

/* Upcoming / Past */
:global(html[data-theme='dark']) .tab-button {
  color: #aeb9b6;
  background: transparent;
}

:global(html[data-theme='dark']) .tab-button:hover {
  background: #1c2925;
}

:global(html[data-theme='dark']) .tab-button.active {
  background: #26332f;
  color: #ffffff;
}

/* Meeting cards */
/* =========================================================
   Meetings — dark mode
   ========================================================= */

:global(html[data-theme='dark'] .meetings-page) {
  color: #e8eeee;
}

:global(html[data-theme='dark'] .meeting-card) {
  background: #18231f !important;
  border-color: #34413d !important;
  color: #e8eeee !important;
}

:global(html[data-theme='dark'] .meeting-header h2) {
  color: #e8eeee !important;
}

:global(html[data-theme='dark'] .meeting-time) {
  color: #aeb9b6 !important;
}

:global(html[data-theme='dark'] .description) {
  color: #d4dcda !important;
}

/* You can manage */
:global(html[data-theme='dark'] .manage-badge) {
  background: #26332f !important;
  color: #c8d5d1 !important;
  border: 1px solid #3c4b47 !important;
}

/* Upcoming / Past */
:global(html[data-theme='dark'] .tab-button) {
  background: transparent !important;
  color: #aeb9b6 !important;
}

:global(html[data-theme='dark'] .tab-button:hover) {
  background: #22302c !important;
}

:global(html[data-theme='dark'] .tab-button.active) {
  background: #26332f !important;
  color: #ffffff !important;
}

/* Join Meeting */
:global(html[data-theme='dark'] .primary-button) {
  background: #26332f !important;
  color: #ffffff !important;
  border-color: #45534f !important;
}

/* View Details */
:global(html[data-theme='dark'] .secondary-button) {
  background: #18231f !important;
  color: #e8eeee !important;
  border-color: #53625e !important;
}

:global(html[data-theme='dark'] .secondary-button:hover) {
  background: #26332f !important;
  border-color: #697975 !important;
}

/* Schedule Meeting form */
:global(html[data-theme='dark'] .create-form) {
  background: #18231f !important;
  border-color: #34413d !important;
  color: #e8eeee !important;
}

:global(html[data-theme='dark'] .form-input) {
  background: #111d1a !important;
  color: #e8eeee !important;
  border-color: #45534f !important;
}

:global(html[data-theme='dark'] .form-input::placeholder) {
  color: #899692 !important;
}

/* Meeting title */
:global(html[data-theme='dark']) .meeting-header h2 {
  color: #e8eeee;
}

/* Date / time */
:global(html[data-theme='dark']) .meeting-time {
  color: #aeb9b6;
}

/* Description */
:global(html[data-theme='dark']) .description {
  color: #d4dcda;
}

/* "You can manage" badge */
:global(html[data-theme='dark']) .manage-badge {
  background: #26332f;
  color: #c8d5d1;
  border: 1px solid #3c4b47;
}

/* Join Meeting */
:global(html[data-theme='dark']) .primary-button {
  background: #26332f;
  color: #ffffff;
  border: 1px solid #45534f;
}

:global(html[data-theme='dark']) .primary-button:hover {
  background: #31403b;
}

/* View Details */
:global(html[data-theme='dark']) .secondary-button {
  background: #18231f;
  color: #e8eeee;
  border-color: #53625e;
}

:global(html[data-theme='dark']) .secondary-button:hover {
  background: #26332f;
  border-color: #697975;
}

/* Schedule Meeting form */
:global(html[data-theme='dark']) .create-form {
  background: #18231f;
  border-color: #34413d;
  color: #e8eeee;
}

:global(html[data-theme='dark']) .form-input {
  background: #111d1a;
  color: #e8eeee;
  border-color: #45534f;
}

:global(html[data-theme='dark']) .form-input::placeholder {
  color: #899692;
}

/* Loading / no meetings */
:global(html[data-theme='dark']) .state-message {
  color: #aeb9b6;
}

:global(html[data-theme='dark']) .create-message {
  color: #c8d0ce;
}

</style>