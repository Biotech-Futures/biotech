<template>
  <FormSheet
    v-model="open"
    :title="isEditing ? 'Edit Role Task' : 'Add Role Task'"
    :description="isEditing
      ? 'Update the task details below. This changes it for every current and future holder of the role — there is nothing else to edit.'
      : 'Define a task once for a role. Everyone who currently holds it, and anyone who gains it later, picks it up automatically.'"
    width="min(100vw, 680px)"
  >
    <form class="admin-role-task-form" novalidate @submit.prevent="submitForm">
      <p v-if="displayError" class="admin-role-task-form__error" role="alert">{{ displayError }}</p>

      <template v-if="!isEditing">
        <div class="admin-role-task-form__section">Assignment</div>
        <div class="admin-role-task-form__grid">
          <div class="form-field form-field--full">
            <label class="form-label" for="role-task-role">
              Role <span class="admin-role-task-form__required">*</span>
            </label>
            <select id="role-task-role" v-model="form.role" class="form-input" :disabled="busy">
              <option value="">{{ roles.length ? 'Select role' : 'No roles available' }}</option>
              <option
                v-for="(role, index) in roles"
                :key="role.id ?? `${role.roleName}-${index}`"
                :value="role.roleName"
              >
                Everyone with the {{ role.roleName }} role
              </option>
            </select>
            <div v-if="form.role">
              <p v-if="recipientLookupError" class="admin-role-task-form__lookup-error" role="alert">
                <span>{{ recipientLookupError }}</span>
                <button
                  type="button"
                  class="admin-role-task-form__retry"
                  :disabled="busy || recipientCountLoading"
                  @click="retryRecipientLookup"
                >
                  Retry
                </button>
              </p>
              <p v-else class="admin-role-task-form__hint">
                <template v-if="recipientCountLoading">Resolving recipients...</template>
                <template v-else-if="roleRecipientCount === null">
                  Every {{ form.role }} will see this task, now and in the future.
                </template>
                <template v-else-if="roleRecipientCount === 0">
                  No active users currently have this role — the task is still created and
                  will apply automatically to anyone who gains it later.
                </template>
                <template v-else>
                  {{ roleRecipientCount }} active user{{ roleRecipientCount === 1 ? '' : 's' }} currently
                  {{ roleRecipientCount === 1 ? 'has' : 'have' }} this role, and it applies automatically
                  to anyone who gains it later.
                </template>
              </p>
            </div>
          </div>
        </div>
      </template>

      <div class="admin-role-task-form__section">Task details</div>
      <div class="admin-role-task-form__grid">
        <div class="form-field form-field--full">
          <label class="form-label" for="role-task-name">
            Name <span class="admin-role-task-form__required">*</span>
          </label>
          <input id="role-task-name" v-model.trim="form.name" class="form-input" :disabled="busy" placeholder="Task name" />
        </div>

        <div class="form-field form-field--full">
          <label class="form-label" for="role-task-description">Description</label>
          <textarea
            id="role-task-description"
            v-model.trim="form.description"
            class="form-input"
            rows="3"
            :disabled="busy"
            placeholder="Optional description"
          ></textarea>
        </div>

        <div class="form-field">
          <label class="form-label" for="role-task-due-date">Due date</label>
          <input id="role-task-due-date" v-model="form.due_date" type="date" class="form-input" :disabled="busy" />
        </div>
      </div>

      <div class="admin-role-task-form__footer">
        <button type="button" class="btn btn-outline" :disabled="busy" @click="onCancel">
          Cancel
        </button>
        <button type="submit" class="btn btn-primary admin-role-task-form__submit" :disabled="saveDisabled">
          <span v-if="busy" class="admin-role-task-form__spinner" aria-hidden="true"></span>
          {{ busy ? 'Saving...' : 'Save' }}
        </button>
      </div>
    </form>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import type {
  AdminRoleTask,
  AdminRoleTaskMutationResult,
  AdminRoleTaskRecipientsData,
  CreateAdminRoleTaskPayload,
  UpdateAdminRoleTaskPayload
} from '@/utils/adminAPI'
import { fetchRoleTaskRecipients } from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'

interface RoleOption {
  id?: number
  roleName: string
}

interface RoleTaskForm {
  role: string
  name: string
  description: string
  due_date: string
}

const props = defineProps<{
  modelValue: boolean
  roleTask?: AdminRoleTask | null
  roles: RoleOption[]
  busy?: boolean
  submitError?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'save', value: CreateAdminRoleTaskPayload | UpdateAdminRoleTaskPayload): void
}>()

const form = reactive<RoleTaskForm>({
  role: '',
  name: '',
  description: '',
  due_date: ''
})
const formError = ref('')
const roleRecipientCount = ref<number | null>(null)
const recipientCountLoading = ref(false)
const recipientLookupError = ref('')
const recipientRequestId = ref(0)

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value)
})
const isEditing = computed(() => Boolean(props.roleTask))
const displayError = computed(() => formError.value || props.submitError || '')
const hasName = computed(() => Boolean(form.name.trim()))
const hasValidAssignment = computed(() => isEditing.value || Boolean(form.role))
const canSave = computed(() => hasName.value && hasValidAssignment.value)
const saveDisabled = computed(() => Boolean(props.busy) || !canSave.value)

const toDateInput = (value: string | null | undefined) => value ? value.slice(0, 10) : ''
const toDueDatePayload = (value: string) => value ? `${value}T00:00:00Z` : null
const toEditDueDatePayload = () => {
  const originalDueDate = props.roleTask?.due_date ?? null
  return form.due_date === toDateInput(originalDueDate)
    ? originalDueDate
    : toDueDatePayload(form.due_date)
}

const reset = () => {
  formError.value = ''
  roleRecipientCount.value = null
  recipientLookupError.value = ''
  if (props.roleTask) {
    form.role = props.roleTask.role?.roleName ?? ''
    form.name = props.roleTask.name
    form.description = props.roleTask.description
    form.due_date = toDateInput(props.roleTask.due_date)
    return
  }

  form.role = ''
  form.name = ''
  form.description = ''
  form.due_date = ''
}

watch(
  () => props.modelValue,
  (next) => {
    if (next) reset()
  }
)

watch(
  () => props.roleTask,
  () => {
    if (props.modelValue) reset()
  }
)

const loadRecipientCount = async (role = form.role) => {
  roleRecipientCount.value = null
  recipientLookupError.value = ''
  if (!props.modelValue || isEditing.value || !role) return

  const requestId = recipientRequestId.value + 1
  recipientRequestId.value = requestId
  recipientCountLoading.value = true
  try {
    const result: AdminRoleTaskMutationResult<AdminRoleTaskRecipientsData | null> =
      await fetchRoleTaskRecipients(role)
    if (recipientRequestId.value === requestId) {
      roleRecipientCount.value = result.data?.count ?? null
      recipientLookupError.value = ''
    }
  } catch (error) {
    logApiError('admin.role-tasks.role-recipients', error)
    if (recipientRequestId.value === requestId) {
      roleRecipientCount.value = null
      recipientLookupError.value = 'Recipient count could not be loaded. Try again.'
    }
  } finally {
    if (recipientRequestId.value === requestId) recipientCountLoading.value = false
  }
}

watch(
  () => form.role,
  (role) => {
    void loadRecipientCount(role)
  }
)

const retryRecipientLookup = () => {
  void loadRecipientCount()
}

const onCancel = () => {
  if (props.busy) return
  open.value = false
}

const submitForm = () => {
  formError.value = ''
  if (props.busy) return
  if (!form.name.trim()) {
    formError.value = 'Task name is required.'
    return
  }

  if (!isEditing.value) {
    if (!form.role) {
      formError.value = 'Select a role for this task.'
      return
    }

    const payload: CreateAdminRoleTaskPayload = {
      role: form.role,
      name: form.name.trim(),
      description: form.description.trim(),
      due_date: toDueDatePayload(form.due_date)
    }
    emit('save', payload)
    return
  }

  emit('save', {
    name: form.name.trim(),
    description: form.description.trim(),
    due_date: toEditDueDatePayload()
  })
}
</script>

<style scoped>
.admin-role-task-form {
  margin: 0;
}

.admin-role-task-form__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.9rem;
}

.form-field--full {
  grid-column: 1 / -1;
}

.form-label {
  display: block;
  margin-bottom: 0.3rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--charcoal);
}

.form-input {
  width: 100%;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
  font: inherit;
}

.form-input:disabled {
  background-color: var(--bg-light);
  color: var(--text-muted);
  cursor: not-allowed;
}

.admin-role-task-form__required {
  color: var(--danger);
  font-weight: 700;
}

.admin-role-task-form__section {
  margin: 1.4rem 0 0.6rem;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid var(--border-light);
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--dark-green);
}

.admin-role-task-form__section:first-of-type {
  margin-top: 0;
}

.admin-role-task-form__hint {
  margin: 0.4rem 0 0;
  color: var(--text-muted);
  font-size: 0.85rem;
  line-height: 1.4;
}

.admin-role-task-form__error {
  margin: 0 0 1rem;
  padding: 0.7rem 0.9rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
}

.admin-role-task-form__lookup-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  margin: 0.4rem 0 0;
  padding: 0.55rem 0.65rem;
  border-left: 3px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.85rem;
  line-height: 1.4;
}

.admin-role-task-form__retry {
  flex: 0 0 auto;
  border: 0;
  background: transparent;
  color: var(--dark-green);
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  padding: 0.1rem 0.2rem;
}

.admin-role-task-form__retry:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.admin-role-task-form__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-light);
}

.admin-role-task-form__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.45);
  border-top-color: var(--white);
  border-radius: 50%;
  display: inline-block;
  margin-right: 0.4rem;
  vertical-align: -2px;
  animation: admin-role-task-form-spin 0.8s linear infinite;
}

.admin-role-task-form__submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.admin-role-task-form__submit:disabled:hover {
  transform: none;
  box-shadow: none;
}

@media (max-width: 640px) {
  .admin-role-task-form__grid {
    grid-template-columns: 1fr;
  }
}

@keyframes admin-role-task-form-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
