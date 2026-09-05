<template>
  <FormSheet
    v-model="open"
    :title="isEditing ? 'Edit Announcement' : 'New Announcement'"
    :description="isEditing ? `Update details for announcement #${announcement?.id}` : 'Create a new announcement for students, mentors, or all users.'"
    width="min(100vw, 760px)"
  >
    <form class="admin-ann-form" novalidate @submit.prevent>
      <p v-if="formError" class="admin-ann-form__error" role="alert">
        <i class="fas fa-triangle-exclamation mr-1.5"></i>
        {{ formError }}
      </p>

      <div class="admin-ann-form__grid">
        <!-- Title -->
        <div class="form-field form-field--full">
          <label class="form-label" for="ann-title">
            Title <span class="required-star">*</span>
          </label>
          <input
            id="ann-title"
            v-model.trim="title"
            type="text"
            class="form-input"
            placeholder="Announcement title"
            maxlength="255"
            required
          />
        </div>

        <!-- Body with TipTap RichEditor -->
        <div class="form-field form-field--full">
          <label class="form-label">
            Body <span class="required-star">*</span>
          </label>
          <RichEditor
            :key="editorKey"
            v-model="body"
            placeholder="Write your announcement content…"
          />
        </div>

        <!-- Target Roles -->
        <div class="form-field form-field--full">
          <div class="admin-ann-form__section">
            <span class="font-semibold">Target Roles</span>
            <span class="admin-ann-form__section-note">(leave unselected to target all roles)</span>
          </div>
          <div v-if="loadingMeta" class="admin-ann-form__meta-loading">
            <i class="fas fa-spinner fa-spin mr-1.5"></i> Loading roles…
          </div>
          <fieldset v-else-if="roles.length" class="admin-ann-form__checkbox-grid">
            <legend class="sr-only">Target Roles</legend>
            <label
              v-for="r in roles"
              :key="r.id"
              class="admin-ann-form__checkbox-label"
            >
              <input
                type="checkbox"
                :value="r.id"
                :checked="roleIds.includes(r.id)"
                @change="toggleRole(r.id)"
              />
              <span>{{ r.name }}</span>
            </label>
          </fieldset>
          <p v-if="roleIds.length > 0" class="admin-ann-form__count-note">
            {{ roleIds.length }} role{{ roleIds.length > 1 ? 's' : '' }} selected
          </p>
        </div>

        <!-- Target Groups -->
        <div class="form-field form-field--full">
          <div class="admin-ann-form__section">
            <span class="font-semibold">Target Groups</span>
            <span class="admin-ann-form__section-note">(leave unselected to target all groups)</span>
          </div>
          <div v-if="loadingMeta" class="admin-ann-form__meta-loading">
            <i class="fas fa-spinner fa-spin mr-1.5"></i> Loading groups…
          </div>
          <fieldset v-else-if="groups.length" class="admin-ann-form__checkbox-grid">
            <legend class="sr-only">Target Groups</legend>
            <label
              v-for="g in groups"
              :key="g.id"
              class="admin-ann-form__checkbox-label"
            >
              <input
                type="checkbox"
                :value="g.id"
                :checked="groupIds.includes(g.id)"
                @change="toggleGroup(g.id)"
              />
              <span>{{ g.name }}</span>
            </label>
          </fieldset>
          <p v-if="groupIds.length > 0" class="admin-ann-form__count-note">
            {{ groupIds.length }} group{{ groupIds.length > 1 ? 's' : '' }} selected
          </p>
        </div>

        <!-- Global audience notice -->
        <div v-if="roleIds.length === 0 && groupIds.length === 0" class="admin-ann-form__notice">
          <i class="fas fa-circle-info"></i>
          <span>No roles or groups selected — announcement will be visible to all users (Global).</span>
        </div>
      </div>

      <!-- Footer Actions -->
      <div class="admin-ann-form__footer">
        <button
          v-if="isEditing"
          type="button"
          class="btn btn-danger"
          :disabled="saving || busy"
          @click="emit('delete', announcement!)"
        >
          <i class="fas fa-trash-can" aria-hidden="true"></i>
          <span>Delete</span>
        </button>

        <span v-if="isEditing" class="admin-ann-form__footer-spacer"></span>

        <button
          type="button"
          class="btn btn-outline"
          :disabled="saving || busy"
          @click="onDismiss"
        >
          <span>Cancel</span>
        </button>

        <!-- Create Mode Buttons -->
        <template v-if="!isEditing">
          <button
            type="button"
            class="btn btn-outline"
            :disabled="saving || busy"
            @click="handleSubmit(false)"
          >
            <i v-if="saving && !pendingEmail" class="fas fa-spinner fa-spin"></i>
            <span>Publish</span>
          </button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="saving || busy"
            @click="promptPublishWithEmail"
          >
            <i v-if="saving && pendingEmail" class="fas fa-spinner fa-spin"></i>
            <i v-else class="fas fa-paper-plane"></i>
            <span>Publish & Notify</span>
          </button>
        </template>

        <!-- Edit Mode Buttons -->
        <template v-else>
          <button
            type="button"
            class="btn btn-outline"
            :disabled="saving || busy"
            @click="handleSubmit(false)"
          >
            <i v-if="saving && !pendingEmail" class="fas fa-spinner fa-spin"></i>
            <span>Save</span>
          </button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="saving || busy"
            @click="handleSubmit(true)"
          >
            <i v-if="saving && pendingEmail" class="fas fa-spinner fa-spin"></i>
            <i v-else class="fas fa-paper-plane"></i>
            <span>Save & Re-notify</span>
          </button>
        </template>
      </div>
    </form>
  </FormSheet>

  <!-- Publish & Notify confirmation modal -->
  <ConfirmDialog
    v-model="confirmNotifyOpen"
    title="Publish & Notify Announcement?"
    message="This will immediately publish the announcement to the platform and send an email notification to the selected audience."
    confirm-label="Publish & Notify"
    variant="default"
    @confirm="confirmPublishAndNotify"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import RichEditor from '@/components/admin/announcements/RichEditor.vue'
import {
  fetchAdminAnnouncement,
  createAdminAnnouncement,
  updateAdminAnnouncement,
  fetchAnnouncementRoles,
  fetchAnnouncementGroups,
  type AdminAnnouncement,
  type AdminAnnouncementDetail,
  type AdminAnnouncementRoleOption,
  type AdminAnnouncementGroupOption
} from '@/utils/adminAPI'

interface Props {
  modelValue: boolean
  announcement?: AdminAnnouncement | null
  busy?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: false,
  announcement: null,
  busy: false
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'saved', announcement: AdminAnnouncementDetail): void
  (e: 'delete', announcement: AdminAnnouncement): void
  (e: 'close'): void
}>()

const open = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val)
})

const isEditing = computed(() => Boolean(props.announcement && props.announcement.id))

const title = ref('')
const body = ref('')
const roleIds = ref<number[]>([])
const groupIds = ref<number[]>([])

const roles = ref<AdminAnnouncementRoleOption[]>([])
const groups = ref<AdminAnnouncementGroupOption[]>([])
const loadingMeta = ref(false)

const saving = ref(false)
const pendingEmail = ref(false)
const formError = ref<string | null>(null)
const confirmNotifyOpen = ref(false)

const editorKey = computed(() => {
  return props.announcement ? `edit-${props.announcement.id}` : 'new-announcement'
})

async function loadMeta() {
  if (roles.value.length > 0 && groups.value.length > 0) return
  loadingMeta.value = true
  try {
    const [rolesData, groupsData] = await Promise.all([
      fetchAnnouncementRoles(),
      fetchAnnouncementGroups()
    ])
    roles.value = rolesData || []
    groups.value = groupsData || []
  } catch (err) {
    console.error('Failed to load announcement targeting metadata:', err)
  } finally {
    loadingMeta.value = false
  }
}

async function populateFromAnnouncement(item: AdminAnnouncement) {
  title.value = item.title || ''
  body.value = item.body || ''
  
  if (item.audiences && item.audiences.length > 0) {
    roleIds.value = item.audiences
      .map((a) => a.roleId)
      .filter((id): id is number => id !== null && id !== undefined)
    groupIds.value = item.audiences
      .map((a) => a.groupId)
      .filter((id): id is number => id !== null && id !== undefined)
  } else {
    roleIds.value = []
    groupIds.value = []
  }

  // If body is missing (e.g. from list view), fetch full detail
  if (item.id && !item.body) {
    try {
      const fullDetail = await fetchAdminAnnouncement(item.id)
      if (fullDetail) {
        title.value = fullDetail.title || ''
        body.value = fullDetail.body || ''
        if (fullDetail.audiences) {
          roleIds.value = fullDetail.audiences
            .map((a) => a.roleId)
            .filter((id): id is number => id !== null && id !== undefined)
          groupIds.value = fullDetail.audiences
            .map((a) => a.groupId)
            .filter((id): id is number => id !== null && id !== undefined)
        }
      }
    } catch (err) {
      console.error('Failed to load announcement details:', err)
    }
  }
}

watch(
  () => props.modelValue,
  async (isOpen) => {
    confirmNotifyOpen.value = false
    if (isOpen) {
      formError.value = null
      await loadMeta()
      if (props.announcement) {
        await populateFromAnnouncement(props.announcement)
      } else {
        title.value = ''
        body.value = ''
        roleIds.value = []
        groupIds.value = []
      }
    }
  },
  { immediate: true }
)

watch(
  () => props.announcement,
  async (newAnn) => {
    if (props.modelValue) {
      if (newAnn) {
        await populateFromAnnouncement(newAnn)
      } else {
        title.value = ''
        body.value = ''
        roleIds.value = []
        groupIds.value = []
      }
    }
  }
)

function toggleRole(id: number) {
  if (roleIds.value.includes(id)) {
    roleIds.value = roleIds.value.filter((r) => r !== id)
  } else {
    roleIds.value.push(id)
  }
}

function toggleGroup(id: number) {
  if (groupIds.value.includes(id)) {
    groupIds.value = groupIds.value.filter((g) => g !== id)
  } else {
    groupIds.value.push(id)
  }
}

function onDismiss() {
  confirmNotifyOpen.value = false
  emit('close')
  open.value = false
}

function validateForm(): boolean {
  formError.value = null
  if (!title.value.trim()) {
    formError.value = 'Title is required.'
    return false
  }
  const strippedBody = body.value.replace(/<[^>]*>/g, '').trim()
  if (!strippedBody && !body.value.includes('<img')) {
    formError.value = 'Body content is required.'
    return false
  }
  return true
}

function promptPublishWithEmail() {
  if (!validateForm()) return
  confirmNotifyOpen.value = true
}

async function confirmPublishAndNotify() {
  confirmNotifyOpen.value = false
  await handleSubmit(true)
}

async function handleSubmit(sendEmail: boolean) {
  if (!validateForm()) return

  saving.value = true
  pendingEmail.value = sendEmail
  formError.value = null

  try {
    const payload = {
      title: title.value.trim(),
      body: body.value,
      role_ids: roleIds.value.length > 0 ? roleIds.value : undefined,
      group_ids: groupIds.value.length > 0 ? groupIds.value : undefined,
      send_email: sendEmail
    }

    let result: AdminAnnouncementDetail
    if (isEditing.value && props.announcement?.id) {
      result = await updateAdminAnnouncement(props.announcement.id, payload)
    } else {
      result = await createAdminAnnouncement(payload)
    }

    emit('saved', result)
    confirmNotifyOpen.value = false
    open.value = false
  } catch (err: unknown) {
    console.error('Failed to save announcement:', err)
    formError.value = err instanceof Error ? err.message : 'Failed to save announcement. Please try again.'
  } finally {
    saving.value = false
    pendingEmail.value = false
  }
}
</script>

<style scoped>
.admin-ann-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: 0.25rem 0;
}

.admin-ann-form__error {
  display: flex;
  align-items: center;
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  padding: 0.625rem 0.875rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
}

.admin-ann-form__grid {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.form-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
}

.required-star {
  color: #dc2626;
}

.form-input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  color: #111827;
  background-color: #ffffff;
  transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
}

.form-input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2);
}

.admin-ann-form__section {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #374151;
  margin-bottom: 0.25rem;
}

.admin-ann-form__section-note {
  font-size: 0.75rem;
  color: #6b7280;
}

.admin-ann-form__meta-loading {
  font-size: 0.8125rem;
  color: #6b7280;
  padding: 0.5rem 0;
}

.admin-ann-form__checkbox-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 0.375rem;
  padding: 0.75rem;
  background-color: #f9fafb;
}

@media (max-width: 640px) {
  .admin-ann-form__checkbox-grid {
    grid-template-columns: 1fr;
  }
}

.admin-ann-form__checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #374151;
  cursor: pointer;
  user-select: none;
}

.admin-ann-form__checkbox-label input[type='checkbox'] {
  width: 1rem;
  height: 1rem;
  accent-color: #2563eb;
  cursor: pointer;
}

.admin-ann-form__count-note {
  font-size: 0.75rem;
  color: #6b7280;
  margin-top: 0.25rem;
}

.admin-ann-form__notice {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  font-size: 0.84rem;
  color: #1e40af;
  background-color: #eff6ff;
  border: 1px solid #dbeafe;
  border-radius: 0.375rem;
  padding: 0.625rem 0.875rem;
  line-height: 1.4;
}

.admin-ann-form__notice i {
  font-size: 1rem;
  color: #2563eb;
  flex-shrink: 0;
}

.admin-ann-form__footer {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding-top: 1rem;
  border-top: 1px solid #e5e7eb;
  margin-top: 0.5rem;
}

.admin-ann-form__footer-spacer {
  margin-right: auto;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease-in-out;
  border: 1px solid transparent;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background-color: #2563eb;
  color: #ffffff;
}

.btn-primary:hover:not(:disabled) {
  background-color: #1d4ed8;
}

.btn-outline {
  background-color: #ffffff;
  border-color: #d1d5db;
  color: #374151;
}

.btn-outline:hover:not(:disabled) {
  background-color: #f3f4f6;
  border-color: #9ca3af;
}

.btn-danger {
  background-color: #dc2626;
  color: #ffffff;
}

.btn-danger:hover:not(:disabled) {
  background-color: #b91c1c;
}
</style>
