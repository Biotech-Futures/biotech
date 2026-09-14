<template>
  <FormSheet
    v-model="open"
    :title="isEditing ? `Edit Event` : `New Event`"
    :description="isEditing ? `Update details for event #${event?.id}` : 'Add an event to the program calendar.'"
    width="min(100vw, 680px)"
  >
    <form class="admin-event-form" novalidate @submit.prevent="submitForm">
      <p v-if="formError" class="admin-event-form__error" role="alert">
        {{ formError }}
      </p>

      <div class="admin-event-form__grid">
        <!-- Host (read-only) -->
        <div class="form-field form-field--full">
          <label class="form-label" for="ev-host">Host</label>
          <input
            id="ev-host"
            :value="hostDisplayName"
            type="text"
            class="form-input form-input--disabled"
            readonly
            disabled
          />
        </div>

        <!-- Event Name -->
        <div class="form-field form-field--full">
          <label class="form-label" for="ev-name">Event Name *</label>
          <input
            id="ev-name"
            v-model.trim="form.eventName"
            type="text"
            class="form-input"
            placeholder="e.g. Biotech Symposium 2026"
            required
            maxlength="255"
          />
        </div>

        <!-- Description -->
        <div class="form-field form-field--full">
          <label class="form-label" for="ev-desc">Description</label>
          <textarea
            id="ev-desc"
            v-model.trim="form.description"
            class="form-input"
            rows="3"
            placeholder="Event overview, agenda, or prerequisites..."
          ></textarea>
        </div>

        <!-- Event Format -->
        <div class="form-field">
          <label class="form-label" for="ev-format">Event Format *</label>
          <select
            id="ev-format"
            v-model="form.eventFormat"
            class="form-input filter-select"
          >
            <option value="in_person">In-person</option>
            <option value="virtual">Virtual</option>
            <option value="hybrid">Hybrid</option>
          </select>
        </div>

        <!-- Timezone -->
        <div class="form-field">
          <label class="form-label" for="ev-tz">Timezone *</label>
          <select
            id="ev-tz"
            v-model="form.eventTimezone"
            class="form-input filter-select"
          >
            <option
              v-for="tz in timezoneOptions"
              :key="tz.value"
              :value="tz.value"
            >
              {{ tz.label }}
            </option>
          </select>
        </div>

        <!-- Location (if in-person or hybrid) -->
        <div v-if="form.eventFormat !== 'virtual'" class="form-field form-field--full">
          <label class="form-label" for="ev-loc">Location</label>
          <input
            id="ev-loc"
            v-model.trim="form.location"
            type="text"
            class="form-input"
            placeholder="e.g. Room 201, Science Building"
          />
        </div>

        <!-- Meeting link or Maps link -->
        <div class="form-field form-field--full">
          <label class="form-label" for="ev-link">
            {{ form.eventFormat === 'virtual' ? 'Meeting Link' : form.eventFormat === 'hybrid' ? 'Meeting Link (Online Attendees)' : 'Google Maps Link (Optional)' }}
          </label>
          <input
            id="ev-link"
            v-model.trim="form.locationLink"
            type="url"
            class="form-input"
            :placeholder="form.eventFormat === 'in_person' ? 'https://maps.google.com/...' : 'https://zoom.us/j/...'"
          />
        </div>

        <!-- Start Date & Time -->
        <div class="form-field">
          <label class="form-label" for="ev-start">Start Date &amp; Time *</label>
          <input
            id="ev-start"
            v-model="form.startAt"
            type="datetime-local"
            class="form-input"
            required
          />
        </div>

        <!-- End Date & Time -->
        <div class="form-field">
          <label class="form-label" for="ev-end">End Date &amp; Time *</label>
          <input
            id="ev-end"
            v-model="form.endsAt"
            type="datetime-local"
            class="form-input"
            required
          />
        </div>
      </div>

      <!-- Image Upload Section -->
      <div class="admin-event-form__section">Banner Image</div>
      <div class="admin-event-image-upload">
        <div class="admin-event-image-upload__controls">
          <input
            ref="fileInputRef"
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp"
            class="admin-event-file-input"
            @change="onFileChange"
          />
          <button
            type="button"
            class="btn btn-outline btn-sm"
            @click="triggerFileInput"
          >
            <i class="fas fa-image" aria-hidden="true"></i>
            <span>{{ previewUrl || form.eventImage ? 'Change Image' : 'Upload Image' }}</span>
          </button>
          <button
            v-if="previewUrl || form.eventImage"
            type="button"
            class="btn btn-outline btn-sm admin-event-remove-btn"
            @click="clearImage"
          >
            <i class="fas fa-times" aria-hidden="true"></i>
            <span>Remove</span>
          </button>
        </div>

        <!-- Preview Thumbnail -->
        <div v-if="previewUrl || form.eventImage" class="admin-event-image-preview">
          <img
            :src="previewUrl || form.eventImage || ''"
            alt="Event banner preview"
            class="admin-event-image-thumb"
          />
        </div>

        <!-- Image URL manual fallback -->
        <div class="form-field" style="margin-top: 0.5rem;">
          <label class="form-label" for="ev-img-url">Or Image URL</label>
          <input
            id="ev-img-url"
            v-model.trim="form.eventImage"
            type="url"
            class="form-input"
            placeholder="https://example.com/banner.png"
            :disabled="Boolean(selectedFile)"
          />
        </div>
        <p class="admin-event-form__hint">
          Accepted: JPG, PNG, GIF, WEBP &bull; Max 5 MB
        </p>
      </div>

      <!-- Target Groups -->
      <div v-if="groups.length" class="admin-event-form__section">
        Target Groups
        <span class="admin-event-form__section-note">(leave unselected to target all groups)</span>
      </div>
      <fieldset v-if="groups.length" class="admin-event-form__checkbox-grid">
        <legend class="sr-only">Target groups</legend>
        <label
          v-for="g in groups"
          :key="g.id"
          class="admin-event-form__checkbox-label"
        >
          <input
            type="checkbox"
            :value="g.id"
            :checked="form.targetGroupIds.includes(g.id)"
            @change="toggleGroup(g.id)"
          />
          <span>{{ g.groupName }}</span>
        </label>
      </fieldset>

      <!-- Target Roles -->
      <div v-if="roles.length" class="admin-event-form__section">
        Target Roles
        <span class="admin-event-form__section-note">(leave unselected to target all roles)</span>
      </div>
      <fieldset v-if="roles.length" class="admin-event-form__checkbox-grid">
        <legend class="sr-only">Target roles</legend>
        <label
          v-for="r in roles"
          :key="r.id"
          class="admin-event-form__checkbox-label"
        >
          <input
            type="checkbox"
            :value="r.id"
            :checked="form.targetRoleIds.includes(r.id)"
            @change="toggleRole(r.id)"
          />
          <span>{{ r.roleName }}</span>
        </label>
      </fieldset>

      <!-- Footer Actions -->
      <div class="admin-event-form__footer">
        <button
          v-if="isEditing"
          type="button"
          class="btn btn-danger"
          :disabled="saving || busy"
          @click="emit('delete')"
        >
          <i class="fas fa-trash-can" aria-hidden="true"></i>
          Delete
        </button>
        <span v-if="isEditing" class="admin-event-form__footer-spacer"></span>
        <button
          type="button"
          class="btn btn-outline"
          :disabled="saving || busy"
          @click="onCancel"
        >
          Cancel
        </button>
        <button
          type="submit"
          class="btn btn-primary"
          :disabled="saving || busy"
        >
          <span v-if="saving" class="admin-event-form__spinner" aria-hidden="true"></span>
          {{ isEditing ? 'Save Changes' : 'Create Event' }}
        </button>
      </div>
    </form>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import { useAuthStore } from '@/stores/auth'
import type {
  AdminEventDetail,
  CreateAdminEventPayload,
  EventTargetGroupItem,
  EventTargetRoleItem,
  UpdateAdminEventPayload
} from '@/utils/adminAPI'
import {
  createAdminEvent,
  fetchAdminEventMetaGroups,
  fetchAdminEventMetaRoles,
  fetchAdminEventTargets,
  updateAdminEvent,
  uploadAdminEventImage
} from '@/utils/adminAPI'
import type { BackendEvent } from '@/utils/eventsAPI'

const props = defineProps<{
  modelValue: boolean
  event?: BackendEvent | AdminEventDetail | null
  busy?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'close'): void
  (e: 'saved'): void
  (e: 'delete'): void
}>()

const auth = useAuthStore()

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value)
})

const isEditing = computed(() => Boolean(props.event?.id))

interface EventFormData {
  eventName: string
  description: string
  eventFormat: 'in_person' | 'virtual' | 'hybrid'
  location: string
  locationLink: string
  eventTimezone: string
  startAt: string
  endsAt: string
  eventImage: string
  targetGroupIds: number[]
  targetRoleIds: number[]
}

const DEFAULT_TZ =
  auth.timeZone ||
  (typeof Intl !== 'undefined' ? Intl.DateTimeFormat().resolvedOptions().timeZone : 'UTC') ||
  'UTC'

const TIMEZONE_OPTIONS = [
  { value: 'Australia/Sydney', label: 'Sydney, Melbourne, Canberra (AEST/AEDT)' },
  { value: 'Australia/Brisbane', label: 'Brisbane (AEST)' },
  { value: 'Australia/Adelaide', label: 'Adelaide (ACST/ACDT)' },
  { value: 'Australia/Perth', label: 'Perth (AWST)' },
  { value: 'Australia/Darwin', label: 'Darwin (ACST)' },
  { value: 'Australia/Hobart', label: 'Hobart (AEST/AEDT)' },
  { value: 'Pacific/Auckland', label: 'Auckland, Wellington (NZST/NZDT)' },
  { value: 'Asia/Singapore', label: 'Singapore, KL, Manila (SGT)' },
  { value: 'Asia/Tokyo', label: 'Tokyo, Seoul (JST/KST)' },
  { value: 'Europe/London', label: 'London, Dublin (GMT/BST)' },
  { value: 'Europe/Paris', label: 'Paris, Berlin, Rome (CET/CEST)' },
  { value: 'America/New_York', label: 'New York, Toronto (EST/EDT)' },
  { value: 'America/Chicago', label: 'Chicago, Dallas (CST/CDT)' },
  { value: 'America/Denver', label: 'Denver, Calgary (MST/MDT)' },
  { value: 'America/Los_Angeles', label: 'Los Angeles, Vancouver (PST/PDT)' },
  { value: 'UTC', label: 'UTC' }
]

const timezoneOptions = computed(() => {
  const current = form.eventTimezone
  if (current && !TIMEZONE_OPTIONS.some((t) => t.value === current)) {
    return [{ value: current, label: current }, ...TIMEZONE_OPTIONS]
  }
  return TIMEZONE_OPTIONS
})

const defaultFormData = (): EventFormData => {
  const now = new Date()
  const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  const startStr = `${tomorrow.getFullYear()}-${pad(tomorrow.getMonth() + 1)}-${pad(tomorrow.getDate())}T10:00`
  const endStr = `${tomorrow.getFullYear()}-${pad(tomorrow.getMonth() + 1)}-${pad(tomorrow.getDate())}T12:00`

  return {
    eventName: '',
    description: '',
    eventFormat: 'in_person',
    location: '',
    locationLink: '',
    eventTimezone: DEFAULT_TZ,
    startAt: startStr,
    endsAt: endStr,
    eventImage: '',
    targetGroupIds: [],
    targetRoleIds: []
  }
}

const form = reactive<EventFormData>(defaultFormData())
const formError = ref('')
const saving = ref(false)

const groups = ref<EventTargetGroupItem[]>([])
const roles = ref<EventTargetRoleItem[]>([])

const fileInputRef = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const previewUrl = ref<string | null>(null)

const hostDisplayName = computed(() => {
  if (isEditing.value && props.event) {
    const raw = props.event as any
    return raw.hostName || raw.hostEmail || auth.displayName || 'Administrator'
  }
  return auth.displayName || auth.user?.email || 'Administrator'
})

/** Convert a UTC ISO string to a datetime-local input string interpreted in target timezone. */
function toDatetimeLocalInTz(utcIso?: string | null, timeZone: string = 'UTC'): string {
  if (!utcIso) return ''
  try {
    const date = new Date(utcIso)
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }).formatToParts(date)
    const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '00'
    const h = get('hour') === '24' ? '00' : get('hour')
    return `${get('year')}-${get('month')}-${get('day')}T${h}:${get('minute')}`
  } catch {
    return utcIso.slice(0, 16)
  }
}

/** Convert a datetime-local string (e.g. 2026-09-02T10:00) interpreted in timezone to UTC ISO string. */
function localInTzToUtcIso(value: string, timeZone: string = 'UTC'): string {
  if (!value) return ''
  try {
    const naive = new Date(`${value}:00Z`)
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    }).formatToParts(naive)
    const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '00'
    const h = get('hour') === '24' ? '00' : get('hour')
    const shown = new Date(
      `${get('year')}-${get('month')}-${get('day')}T${h}:${get('minute')}:${get('second')}Z`
    )
    return new Date(2 * naive.getTime() - shown.getTime()).toISOString()
  } catch {
    return new Date(value).toISOString()
  }
}

const loadMeta = async () => {
  try {
    const [groupsData, rolesData] = await Promise.all([
      fetchAdminEventMetaGroups(),
      fetchAdminEventMetaRoles()
    ])
    groups.value = groupsData
    roles.value = rolesData
  } catch (err) {
    console.warn('Failed to load event metadata (groups/roles):', err)
  }
}

const initForm = async (currentEvent?: BackendEvent | AdminEventDetail | null) => {
  formError.value = ''
  selectedFile.value = null
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = null
  }

  await loadMeta()

  if (!currentEvent) {
    Object.assign(form, defaultFormData())
    return
  }

  const raw = currentEvent as any
  const tz = raw.event_timezone || raw.eventTimezone || DEFAULT_TZ
  const startRaw = raw.start_datetime || raw.startDatetime
  const endRaw = raw.ends_datetime || raw.endsDatetime

  Object.assign(form, {
    eventName: raw.event_name || raw.eventName || '',
    description: raw.description || '',
    eventFormat: raw.event_format || raw.eventFormat || 'in_person',
    location: raw.location || '',
    locationLink: raw.location_link || raw.locationLink || '',
    eventTimezone: tz,
    startAt: toDatetimeLocalInTz(startRaw, tz),
    endsAt: toDatetimeLocalInTz(endRaw, tz),
    eventImage: raw.event_image || raw.eventImage || '',
    targetGroupIds: raw.target_groups || [],
    targetRoleIds: raw.target_roles || []
  })

  // Also fetch full targets if editing and event has ID
  if (currentEvent.id) {
    try {
      const targets = await fetchAdminEventTargets(currentEvent.id)
      if (targets) {
        form.targetGroupIds = targets.groupIds || []
        form.targetRoleIds = targets.roleIds || []
      }
    } catch (err) {
      console.warn('Failed to fetch event targets:', err)
    }
  }
}

watch(
  () => props.modelValue,
  (isOpening) => {
    if (isOpening) {
      void initForm(props.event)
    }
  }
)

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const onFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  if (file.size > 5 * 1024 * 1024) {
    formError.value = 'File is too large. Maximum allowed size is 5 MB.'
    return
  }

  selectedFile.value = file
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
  previewUrl.value = URL.createObjectURL(file)
  formError.value = ''
}

const clearImage = () => {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = null
  }
  selectedFile.value = null
  form.eventImage = ''
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

const toggleGroup = (id: number) => {
  const idx = form.targetGroupIds.indexOf(id)
  if (idx > -1) {
    form.targetGroupIds.splice(idx, 1)
  } else {
    form.targetGroupIds.push(id)
  }
}

const toggleRole = (id: number) => {
  const idx = form.targetRoleIds.indexOf(id)
  if (idx > -1) {
    form.targetRoleIds.splice(idx, 1)
  } else {
    form.targetRoleIds.push(id)
  }
}

const onCancel = () => {
  open.value = false
  emit('close')
}

const validateForm = (): boolean => {
  if (!form.eventName.trim()) {
    formError.value = 'Event name is required.'
    return false
  }
  if (!form.startAt) {
    formError.value = 'Start date and time are required.'
    return false
  }
  if (!form.endsAt) {
    formError.value = 'End date and time are required.'
    return false
  }

  const startDate = new Date(form.startAt)
  const endDate = new Date(form.endsAt)

  if (endDate <= startDate) {
    formError.value = 'End time must be after start time.'
    return false
  }

  if (form.eventFormat === 'virtual' && form.location.trim()) {
    formError.value = 'Virtual events must not have a physical location.'
    return false
  }

  return true
}

const submitForm = async () => {
  formError.value = ''
  if (!validateForm()) return

  saving.value = true
  try {
    const tz = form.eventTimezone || 'UTC'
    const startIso = localInTzToUtcIso(form.startAt, tz)
    const endsIso = localInTzToUtcIso(form.endsAt, tz)

    const payload: CreateAdminEventPayload | UpdateAdminEventPayload = {
      eventName: form.eventName.trim(),
      description: form.description.trim() || null,
      eventFormat: form.eventFormat,
      location: form.eventFormat !== 'virtual' ? form.location.trim() || null : null,
      locationLink: form.locationLink.trim() || null,
      eventTimezone: tz,
      startAt: startIso,
      endsAt: endsIso,
      targetGroupIds: form.targetGroupIds,
      targetRoleIds: form.targetRoleIds
    }

    if (!selectedFile.value && form.eventImage) {
      payload.eventImage = form.eventImage.trim()
    }

    let savedEventId: number | undefined

    if (isEditing.value && props.event?.id) {
      const res = await updateAdminEvent(props.event.id, payload)
      savedEventId = res.id
    } else {
      const res = await createAdminEvent(payload as CreateAdminEventPayload)
      savedEventId = res.id
    }

    if (selectedFile.value && savedEventId) {
      await uploadAdminEventImage(savedEventId, selectedFile.value)
    }

    open.value = false
    emit('saved')
  } catch (err: any) {
    console.error('Failed to save event:', err)
    formError.value = err?.message || 'Failed to save event. Please check your inputs.'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.admin-event-form {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.admin-event-form__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.9rem;
}

.form-field--full {
  grid-column: 1 / -1;
}

.form-label {
  display: block;
  margin-bottom: 0.35rem;
  font-size: 0.825rem;
  font-weight: 600;
  color: var(--charcoal);
}

.form-input {
  width: 100%;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
  font: inherit;
  font-size: 0.92rem;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.form-input:focus {
  outline: none;
  border-color: var(--dark-green);
  box-shadow: 0 0 0 3px rgba(1, 113, 81, 0.15);
}

.form-input--disabled {
  background-color: var(--bg-light);
  color: var(--text-muted);
  cursor: not-allowed;
}

.filter-select {
  appearance: none;
  -webkit-appearance: none;
  background-image: linear-gradient(45deg, transparent 50%, var(--text-muted) 50%),
                    linear-gradient(135deg, var(--text-muted) 50%, transparent 50%);
  background-position: calc(100% - 18px) 50%, calc(100% - 13px) 50%;
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
  padding-right: 2rem;
  cursor: pointer;
}

.admin-event-form__section {
  margin: 1.25rem 0 0.4rem;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid var(--border-light);
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--dark-green);
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.admin-event-form__section-note {
  font-size: 0.75rem;
  font-weight: normal;
  text-transform: none;
  color: var(--text-muted);
}

.admin-event-form__checkbox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.5rem;
  border: none;
  padding: 0;
  margin: 0.25rem 0 0;
}

.admin-event-form__checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--charcoal);
  cursor: pointer;
}

.admin-event-form__checkbox-label input {
  accent-color: var(--dark-green);
  width: 16px;
  height: 16px;
}

.admin-event-image-upload {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.admin-event-image-upload__controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.admin-event-file-input {
  display: none;
}

.admin-event-image-preview {
  margin-top: 0.35rem;
  max-width: 100%;
}

.admin-event-image-thumb {
  max-height: 140px;
  width: auto;
  border-radius: 8px;
  border: 1px solid var(--border-light);
  object-fit: cover;
}

.admin-event-form__hint {
  margin: 0.25rem 0 0;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.admin-event-form__error {
  margin: 0 0 0.5rem;
  padding: 0.65rem 0.85rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.875rem;
}

.admin-event-form__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.65rem;
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-light);
}

.admin-event-form__footer-spacer {
  flex: 1;
}

.admin-event-form__spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-right: 0.4rem;
  vertical-align: -2px;
  border: 2px solid rgba(255, 255, 255, 0.5);
  border-top-color: var(--white);
  border-radius: 50%;
  animation: admin-spin 0.8s linear infinite;
}

@keyframes admin-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 640px) {
  .admin-event-form__grid {
    grid-template-columns: 1fr;
  }
}
</style>
