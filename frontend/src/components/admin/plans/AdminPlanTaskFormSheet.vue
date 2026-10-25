<template>
  <FormSheet
    v-model="open"
    :title="isEditing ? 'Edit Task' : 'Add Task'"
    :description="
      isEditing
        ? 'Update this plan task. Audience and mode lock once a group has recorded it.'
        : 'Add a task to a stage. Groups work through stages in order.'
    "
    width="min(100vw, 620px)"
  >
    <form class="admin-plan-task-form" novalidate @submit.prevent="submitForm">
      <p v-if="displayError" class="admin-plan-task-form__error" role="alert">{{ displayError }}</p>

      <div class="form-field form-field--full">
        <label class="form-label" for="plan-task-name">
          Name <span class="admin-plan-task-form__required">*</span>
        </label>
        <input
          id="plan-task-name"
          v-model.trim="form.name"
          class="form-input"
          :disabled="busy"
          placeholder="Task name"
        />
      </div>

      <div class="form-field form-field--full">
        <label class="form-label" for="plan-task-description">Instructions</label>
        <textarea
          id="plan-task-description"
          v-model.trim="form.description"
          class="form-input"
          rows="3"
          :disabled="busy"
          placeholder="Optional instructions"
        ></textarea>
      </div>

      <div class="form-field">
        <label class="form-label" for="plan-task-stage">
          Stage <span class="admin-plan-task-form__required">*</span>
        </label>
        <AppSelect
          id="plan-task-stage"
          v-model="form.stage_id"
          class="form-input"
          :options="stageOptions"
          :placeholder="stages.length ? 'Select stage' : 'No stages yet'"
          :disabled="busy || !stages.length"
        />
      </div>

      <div class="form-field">
        <label class="form-label" for="plan-task-position">Order</label>
        <input
          id="plan-task-position"
          v-model.number="form.position"
          type="number"
          min="0"
          step="1"
          class="form-input"
          :disabled="busy"
        />
      </div>

      <div class="form-field">
        <label class="form-label" for="plan-task-audience">
          Audience <span class="admin-plan-task-form__required">*</span>
        </label>
        <AppSelect
          id="plan-task-audience"
          v-model="form.audience_role"
          class="form-input"
          :options="AUDIENCE_OPTIONS"
          :disabled="busy || lockFields"
        />
        <p v-if="lockFields" class="admin-plan-task-form__hint admin-plan-task-form__hint--locked">
          <i class="fas fa-lock" aria-hidden="true"></i>
          A group has already recorded this task, so its audience is locked.
        </p>
      </div>

      <div class="form-field">
        <label class="form-label" for="plan-task-due-date">Due date</label>
        <input
          id="plan-task-due-date"
          v-model="form.due_date"
          type="date"
          class="form-input"
          :disabled="busy"
        />
      </div>

      <fieldset class="form-field form-field--full admin-plan-task-form__mode">
        <legend class="form-label">
          Completion <span class="admin-plan-task-form__required">*</span>
        </legend>
        <label class="admin-plan-task-form__radio">
          <input
            v-model="form.completion_mode"
            type="radio"
            value="per_person"
            :disabled="busy || lockFields"
          />
          <span>
            Each person ticks their own
            <small>Progress counts completed people over the current audience.</small>
          </span>
        </label>
        <label class="admin-plan-task-form__radio">
          <input
            v-model="form.completion_mode"
            type="radio"
            value="per_group"
            :disabled="busy || lockFields"
          />
          <span>
            Whole group
            <small>One shared tick for the group (0/1 or 1/1).</small>
          </span>
        </label>
        <p v-if="lockFields" class="admin-plan-task-form__hint admin-plan-task-form__hint--locked">
          <i class="fas fa-lock" aria-hidden="true"></i>
          Completion mode is locked once a group has recorded this task.
        </p>
      </fieldset>

      <div class="form-field">
        <label class="form-label" for="plan-task-resource-label">Resource label</label>
        <input
          id="plan-task-resource-label"
          v-model.trim="form.resource_label"
          class="form-input"
          :disabled="busy"
          placeholder="e.g. Read the guide"
        />
      </div>

      <div class="form-field">
        <label class="form-label" for="plan-task-resource-url">Resource link</label>
        <input
          id="plan-task-resource-url"
          v-model.trim="form.resource_url"
          class="form-input"
          :disabled="busy"
          placeholder="https://..."
        />
        <p class="admin-plan-task-form__hint">A label and a link go together, or neither.</p>
      </div>

      <div class="admin-plan-task-form__footer">
        <button type="button" class="btn btn-outline" :disabled="busy" @click="onCancel">
          Cancel
        </button>
        <button type="submit" class="btn btn-primary admin-plan-task-form__submit" :disabled="saveDisabled">
          <span v-if="busy" class="admin-plan-task-form__spinner" aria-hidden="true"></span>
          {{ busy ? 'Saving...' : 'Save' }}
        </button>
      </div>
    </form>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import AppSelect, { type AppSelectOption } from '@/components/AppSelect.vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import type {
  AdminPlanAudienceRole,
  AdminPlanCompletionMode,
  AdminPlanStage,
  AdminPlanTask,
  AdminPlanTaskPayload
} from '@/utils/adminAPI'

const props = defineProps<{
  modelValue: boolean
  task?: AdminPlanTask | null
  stages: AdminPlanStage[]
  /** The stage a new task is added to (the one selected in the builder). */
  defaultStageId?: number | null
  busy?: boolean
  submitError?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'save', value: AdminPlanTaskPayload): void
}>()

const form = reactive<{
  name: string
  description: string
  stage_id: number | null
  position: number
  audience_role: AdminPlanAudienceRole
  completion_mode: AdminPlanCompletionMode
  due_date: string
  resource_label: string
  resource_url: string
}>({
  name: '',
  description: '',
  stage_id: null,
  position: 0,
  audience_role: 'student',
  completion_mode: 'per_person',
  due_date: '',
  resource_label: '',
  resource_url: ''
})
const formError = ref('')

const AUDIENCE_OPTIONS: AppSelectOption[] = [
  { value: 'student', label: 'Students' },
  { value: 'mentor', label: 'Mentors' },
  { value: 'supervisor', label: 'Supervisors' }
]

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value)
})
const isEditing = computed(() => Boolean(props.task))
const lockFields = computed(() => Boolean(props.task?.has_completions))
const displayError = computed(() => formError.value || props.submitError || '')
const stageOptions = computed<AppSelectOption[]>(() =>
  props.stages.map((stage) => ({ value: stage.id, label: stage.name }))
)
const saveDisabled = computed(
  () => Boolean(props.busy) || !form.name.trim() || form.stage_id === null
)

const toDateInput = (value: string | null | undefined) => (value ? value.slice(0, 10) : '')

const reset = () => {
  formError.value = ''
  if (props.task) {
    form.name = props.task.name
    form.description = props.task.description
    form.stage_id = props.task.stage_id
    form.position = props.task.position
    form.audience_role = props.task.audience_role
    form.completion_mode = props.task.completion_mode
    form.due_date = toDateInput(props.task.due_date)
    form.resource_label = props.task.resource_label
    form.resource_url = props.task.resource_url
    return
  }
  form.name = ''
  form.description = ''
  form.stage_id = props.defaultStageId ?? props.stages[0]?.id ?? null
  form.position = 0
  form.audience_role = 'student'
  form.completion_mode = 'per_person'
  form.due_date = ''
  form.resource_label = ''
  form.resource_url = ''
}

watch(
  () => props.modelValue,
  (next) => {
    if (next) reset()
  },
  { immediate: true }
)
watch(
  () => props.task,
  () => {
    if (props.modelValue) reset()
  }
)

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
  if (form.stage_id === null) {
    formError.value = 'Select a stage for this task.'
    return
  }
  if (Boolean(form.resource_label) !== Boolean(form.resource_url)) {
    formError.value = 'A resource needs both a label and a link, or neither.'
    return
  }
  const position = Number.isFinite(form.position) ? Math.max(0, Math.trunc(form.position)) : 0
  emit('save', {
    name: form.name.trim(),
    description: form.description.trim(),
    stage_id: form.stage_id,
    position,
    audience_role: form.audience_role,
    completion_mode: form.completion_mode,
    due_date: form.due_date || null,
    resource_label: form.resource_label.trim(),
    resource_url: form.resource_url.trim()
  })
}
</script>

<style scoped>
.admin-plan-task-form {
  margin: 0;
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
  color: var(--teal);
}

.form-input {
  width: 100%;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--teal);
  font: inherit;
}

.form-input:disabled,
.app-select.form-input.is-disabled {
  background-color: var(--bg-light);
  color: var(--text-muted);
  cursor: not-allowed;
}

.app-select.form-input.is-disabled {
  opacity: 1;
}

.admin-plan-task-form__required {
  color: var(--danger);
  font-weight: 700;
}

.admin-plan-task-form__mode {
  border: 0;
  margin: 0;
  padding: 0;
}

.admin-plan-task-form__radio {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-top: 0.4rem;
  font-size: 0.9rem;
  color: var(--teal);
}

.admin-plan-task-form__radio small {
  display: block;
  color: var(--text-muted);
  font-size: 0.8rem;
  margin-top: 0.1rem;
}

.admin-plan-task-form__hint {
  margin: 0.35rem 0 0;
  color: var(--text-muted);
  font-size: 0.8rem;
}

.admin-plan-task-form__hint--locked {
  color: var(--dark-green);
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.admin-plan-task-form__error {
  grid-column: 1 / -1;
  margin: 0;
  padding: 0.7rem 0.9rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
}

.admin-plan-task-form__footer {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 0.6rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-light);
}

.admin-plan-task-form__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.45);
  border-top-color: var(--white);
  border-radius: 50%;
  display: inline-block;
  margin-right: 0.4rem;
  vertical-align: -2px;
  animation: admin-plan-task-form-spin 0.8s linear infinite;
}

.admin-plan-task-form__submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

@media (max-width: 640px) {
  .admin-plan-task-form {
    grid-template-columns: 1fr;
  }
}

@keyframes admin-plan-task-form-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
