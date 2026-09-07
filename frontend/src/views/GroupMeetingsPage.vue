<template>
  <div class="meetings-page">
    <div class="page-header">
      <div>
        <h1>Group Meetings</h1>
        <p class="subtitle">
          View upcoming and past meetings for your group.
        </p>
      </div>

      <button
        class="primary-button"
        @click="showCreateForm = !showCreateForm"
      >
        {{ showCreateForm ? 'Close' : '+ Schedule Meeting' }}
      </button>
    </div>

    <section v-if="showCreateForm" class="create-form">
    <h2>Schedule Meeting</h2>

    <label>
        Title
        <input
        v-model="newTitle"
        type="text"
        class="form-input"
        />
    </label>

    <label>
        Description
        <textarea
        v-model="newDescription"
        class="form-input"
        rows="3"
        ></textarea>
    </label>

    <label>
        Agenda
        <textarea
        v-model="newAgenda"
        class="form-input"
        rows="3"
        ></textarea>
    </label>

    <label>
        Start
        <input
        v-model="newStart"
        type="datetime-local"
        class="form-input"
        />
    </label>

    <label>
        End
        <input
        v-model="newEnd"
        type="datetime-local"
        class="form-input"
        />
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
        Join Link
        <input
        v-model="newJoinLink"
        type="url"
        class="form-input"
        />
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

        <div
          v-if="meeting.agenda"
          class="agenda"
        >
          <strong>Agenda</strong>
          <p>{{ meeting.agenda }}</p>
        </div>

        <div class="meeting-actions">
          <a
            v-if="meeting.join_link && selectedWhen === 'upcoming'"
            :href="meeting.join_link"
            target="_blank"
            rel="noopener noreferrer"
            class="primary-button"
          >
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
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  fetchMeetings,
  createMeeting,
  type GroupMeeting,
  type MeetingWhen,
} from '@/utils/meetingsAPI'

const route = useRoute()
const router = useRouter()

const meetings = ref<GroupMeeting[]>([])
const selectedWhen = ref<MeetingWhen>('upcoming')

const isLoading = ref(false)
const errorMessage = ref('')
const showCreateForm = ref(false)
const creatingMeeting = ref(false)
const createMessage = ref('')

const newTitle = ref('')
const newDescription = ref('')
const newAgenda = ref('')
const newStart = ref('')
const newEnd = ref('')
const newTimezone = ref('Australia/Sydney')
const newJoinLink = ref('')

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

  creatingMeeting.value = true
  createMessage.value = ''

  try {
    await createMeeting({
      group: groupId,
      title: newTitle.value,
      description: newDescription.value,
      agenda: newAgenda.value,
      start_datetime: new Date(newStart.value).toISOString(),
      ends_datetime: new Date(newEnd.value).toISOString(),
      timezone_name: newTimezone.value,
      join_link: newJoinLink.value,
    })

    showCreateForm.value = false

    newTitle.value = ''
    newDescription.value = ''
    newAgenda.value = ''
    newStart.value = ''
    newEnd.value = ''
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
.meetings-page {
  width: 100%;
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px;
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

.agenda {
  margin-top: 18px;
}

.agenda p {
  margin: 6px 0 0;
  line-height: 1.6;
  white-space: pre-wrap;
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
</style>