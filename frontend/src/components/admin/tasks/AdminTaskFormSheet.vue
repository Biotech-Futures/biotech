<template>
  <FormSheet
    v-model="open"
    :title="isEditing ? 'Edit Task' : 'Add Task'"
    :description="isEditing ? 'Update the task details below.' : 'Create a group task, or assign one directly to a specific person. For a task assigned by role, use Role Tasks.'"
    width="min(100vw, 680px)"
  >
    <form class="admin-task-form" novalidate @submit.prevent="submitForm">
      <p v-if="displayError" class="admin-task-form__error" role="alert">{{ displayError }}</p>

      <template v-if="!isEditing">
        <div class="admin-task-form__section">Assignment</div>
        <div class="admin-task-form__grid admin-task-form__grid--assignment">
          <div class="form-field">
            <label class="form-label" for="task-type">
              Task type <span class="admin-task-form__required">*</span>
            </label>
            <select id="task-type" v-model="form.task_type" class="form-input" :disabled="busy">
              <option value="group">Group Task</option>
              <option value="individual">Individual Task</option>
            </select>
          </div>

          <div v-if="form.task_type === 'group'" class="form-field">
            <label class="form-label" for="task-group">
              Group <span class="admin-task-form__required">*</span>
            </label>
            <select id="task-group" v-model="form.group" class="form-input" :disabled="busy">
              <option value="">{{ groups.length ? 'Select group' : 'No groups available' }}</option>
              <option v-for="group in groups" :key="group.id" :value="String(group.id)">
                {{ groupLabel(group) }}
              </option>
            </select>
          </div>

          <div v-else class="form-field">
            <label class="form-label" for="task-user">
              User <span class="admin-task-form__required">*</span>
            </label>
            <select id="task-user" v-model="form.assigned_user" class="form-input" :disabled="busy">
              <option value="">{{ users.length ? 'Select user' : 'No users available' }}</option>
              <option v-for="user in users" :key="user.id" :value="String(user.id)">
                {{ userLabel(user) }}
              </option>
            </select>
          </div>
        </div>
      </template>

      <div class="admin-task-form__section">Task details</div>
      <div class="admin-task-form__grid admin-task-form__grid--details">
        <div class="form-field form-field--full">
          <label class="form-label" for="task-name">
            Name <span class="admin-task-form__required">*</span>
          </label>
          <input id="task-name" v-model.trim="form.name" class="form-input" :disabled="busy" placeholder="Task name" />
        </div>

        <div class="form-field form-field--full">
          <label class="form-label" for="task-description">Description</label>
          <textarea
            id="task-description"
            v-model.trim="form.description"
            class="form-input"
            rows="3"
            :disabled="busy"
            placeholder="Optional description"
          ></textarea>
        </div>

        <div class="form-field">
          <label class="form-label" for="task-due-date">Due date</label>
          <input id="task-due-date" v-model="form.due_date" type="date" class="form-input" :disabled="busy" />
        </div>

        <div class="form-field">
          <label class="form-label" for="task-status">Status</label>
          <select id="task-status" v-model="form.status" class="form-input" :disabled="busy">
            <option value="todo">To Do</option>
            <option value="in_progress">In Progress</option>
            <option value="done">Done</option>
            <option value="blocked">Blocked</option>
          </select>
        </div>
      </div>

      <div class="admin-task-form__footer">
        <button type="button" class="btn btn-outline" :disabled="busy" @click="onCancel">
          Cancel
        </button>
        <button type="submit" class="btn btn-primary admin-task-form__submit" :disabled="saveDisabled">
          <span v-if="busy" class="admin-task-form__spinner" aria-hidden="true"></span>
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
  AdminGroup,
  AdminTask,
  AdminTaskStatus,
  AdminTaskType,
  AdminUser,
  CreateAdminTaskPayload,
  UpdateAdminTaskPayload
} from '@/utils/adminAPI'
import { userName } from '@/utils/userFormat'

interface TaskForm {
  task_type: AdminTaskType
  group: string
  assigned_user: string
  name: string
  description: string
  due_date: string
  status: AdminTaskStatus
}

const props = defineProps<{
  modelValue: boolean
  task?: AdminTask | null
  groups: AdminGroup[]
  users: AdminUser[]
  busy?: boolean
  submitError?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'save', value: CreateAdminTaskPayload | UpdateAdminTaskPayload): void
}>()

const form = reactive<TaskForm>({
  task_type: 'group',
  group: '',
  assigned_user: '',
  name: '',
  description: '',
  due_date: '',
  status: 'todo'
})
const formError = ref('')

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value)
})
const isEditing = computed(() => Boolean(props.task))
const displayError = computed(() => formError.value || props.submitError || '')
const hasName = computed(() => Boolean(form.name.trim()))
const hasValidAssignment = computed(() => {
  if (isEditing.value) return true
  return form.task_type === 'group' ? Boolean(form.group) : Boolean(form.assigned_user)
})
const canSave = computed(() => hasName.value && hasValidAssignment.value)
const saveDisabled = computed(() => Boolean(props.busy) || !canSave.value)

const toDateInput = (value: string | null | undefined) => value ? value.slice(0, 10) : ''
const toDueDatePayload = (value: string) => value ? `${value}T00:00:00Z` : null
const toEditDueDatePayload = () => {
  const originalDueDate = props.task?.due_date ?? null
  return form.due_date === toDateInput(originalDueDate)
    ? originalDueDate
    : toDueDatePayload(form.due_date)
}

const reset = () => {
  formError.value = ''
  if (props.task) {
    form.task_type = props.task.task_type
    form.group = props.task.group != null ? String(props.task.group) : ''
    form.assigned_user = props.task.assigned_user != null ? String(props.task.assigned_user) : ''
    form.name = props.task.name
    form.description = props.task.description
    form.due_date = toDateInput(props.task.due_date)
    form.status = props.task.status
    return
  }

  form.task_type = 'group'
  form.group = ''
  form.assigned_user = ''
  form.name = ''
  form.description = ''
  form.due_date = ''
  form.status = 'todo'
}

watch(
  () => form.task_type,
  () => {
    formError.value = ''
    if (form.task_type === 'group') form.assigned_user = ''
    else form.group = ''
  }
)

watch(
  () => props.modelValue,
  (next) => {
    if (next) reset()
  }
)

watch(
  () => props.task,
  () => {
    if (props.modelValue) reset()
  }
)

const groupLabel = (group: AdminGroup) =>
  String(group.name ?? group.group_id ?? `Group #${group.id ?? ''}`)

const userLabel = (user: AdminUser) => {
  const name = userName(user)
  return user.email ? `${name} (${user.email})` : name
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
    if (form.task_type === 'group' && !form.group) {
      formError.value = 'Select a group for this task.'
      return
    }
    if (form.task_type === 'individual' && !form.assigned_user) {
      formError.value = 'Select a user for this task.'
      return
    }

    const payload: CreateAdminTaskPayload =
      form.task_type === 'group'
        ? {
            task_type: 'group',
            group: Number(form.group),
            name: form.name.trim(),
            description: form.description.trim(),
            due_date: toDueDatePayload(form.due_date),
            status: form.status,
            parent: null
          }
        : {
            task_type: 'individual',
            assigned_user: Number(form.assigned_user),
            name: form.name.trim(),
            description: form.description.trim(),
            due_date: toDueDatePayload(form.due_date),
            status: form.status,
            parent: null
          }
    emit('save', payload)
    return
  }

  emit('save', {
    name: form.name.trim(),
    description: form.description.trim(),
    due_date: toEditDueDatePayload(),
    status: form.status,
    parent: props.task?.parent ?? null
  })
}
</script>

<style scoped>
.admin-task-form {
  margin: 0;
}

.admin-task-form__grid {
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

.admin-task-form__required {
  color: var(--danger);
  font-weight: 700;
}

.admin-task-form__section {
  margin: 1.4rem 0 0.6rem;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid var(--border-light);
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--dark-green);
}

.admin-task-form__section:first-of-type {
  margin-top: 0;
}

.admin-task-form__hint {
  margin: 0.4rem 0 0;
  color: var(--text-muted);
  font-size: 0.85rem;
  line-height: 1.4;
}

.admin-task-form__error {
  margin: 0 0 1rem;
  padding: 0.7rem 0.9rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
}

.admin-task-form__lookup-error {
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

.admin-task-form__retry {
  flex: 0 0 auto;
  border: 0;
  background: transparent;
  color: var(--dark-green);
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  padding: 0.1rem 0.2rem;
}

.admin-task-form__retry:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.admin-task-form__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-light);
}

.admin-task-form__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.45);
  border-top-color: var(--white);
  border-radius: 50%;
  display: inline-block;
  margin-right: 0.4rem;
  vertical-align: -2px;
  animation: admin-task-form-spin 0.8s linear infinite;
}

.admin-task-form__submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.admin-task-form__submit:disabled:hover {
  transform: none;
  box-shadow: none;
}

@media (max-width: 640px) {
  .admin-task-form__grid {
    grid-template-columns: 1fr;
  }
}

@keyframes admin-task-form-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
