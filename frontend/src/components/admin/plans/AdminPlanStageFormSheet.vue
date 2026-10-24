<template>
  <FormSheet
    v-model="open"
    :title="isEditing ? 'Edit Stage' : 'Add Stage'"
    :description="
      isEditing
        ? 'Update this stage. It holds the tasks grouped under it.'
        : 'Stages group the plan into an order groups work through.'
    "
    width="min(100vw, 520px)"
  >
    <form class="admin-plan-stage-form" novalidate @submit.prevent="submitForm">
      <p v-if="displayError" class="admin-plan-stage-form__error" role="alert">{{ displayError }}</p>

      <div class="form-field">
        <label class="form-label" for="plan-stage-name">
          Name <span class="admin-plan-stage-form__required">*</span>
        </label>
        <input
          id="plan-stage-name"
          v-model.trim="form.name"
          class="form-input"
          :disabled="busy"
          placeholder="Stage name"
        />
      </div>

      <div class="form-field">
        <label class="form-label" for="plan-stage-description">Description</label>
        <textarea
          id="plan-stage-description"
          v-model.trim="form.description"
          class="form-input"
          rows="3"
          :disabled="busy"
          placeholder="Optional instructions shown above the stage's tasks"
        ></textarea>
      </div>

      <div class="form-field">
        <label class="form-label" for="plan-stage-position">Order</label>
        <input
          id="plan-stage-position"
          v-model.number="form.position"
          type="number"
          min="0"
          step="1"
          class="form-input"
          :disabled="busy"
        />
        <p class="admin-plan-stage-form__hint">Lower numbers come first.</p>
      </div>

      <div class="admin-plan-stage-form__footer">
        <button type="button" class="btn btn-outline" :disabled="busy" @click="onCancel">
          Cancel
        </button>
        <button type="submit" class="btn btn-primary admin-plan-stage-form__submit" :disabled="saveDisabled">
          <span v-if="busy" class="admin-plan-stage-form__spinner" aria-hidden="true"></span>
          {{ busy ? 'Saving...' : 'Save' }}
        </button>
      </div>
    </form>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import type { AdminPlanStage, AdminPlanStagePayload } from '@/utils/adminAPI'

const props = defineProps<{
  modelValue: boolean
  stage?: AdminPlanStage | null
  /** Suggested order for a new stage (the current stage count). */
  nextPosition?: number
  busy?: boolean
  submitError?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'save', value: AdminPlanStagePayload): void
}>()

const form = reactive({
  name: '',
  description: '',
  position: 0
})
const formError = ref('')

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value)
})
const isEditing = computed(() => Boolean(props.stage))
const displayError = computed(() => formError.value || props.submitError || '')
const saveDisabled = computed(() => Boolean(props.busy) || !form.name.trim())

const reset = () => {
  formError.value = ''
  if (props.stage) {
    form.name = props.stage.name
    form.description = props.stage.description
    form.position = props.stage.position
    return
  }
  form.name = ''
  form.description = ''
  form.position = props.nextPosition ?? 0
}

watch(
  () => props.modelValue,
  (next) => {
    if (next) reset()
  },
  { immediate: true }
)
watch(
  () => props.stage,
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
    formError.value = 'Stage name is required.'
    return
  }
  const position = Number.isFinite(form.position) ? Math.max(0, Math.trunc(form.position)) : 0
  emit('save', {
    name: form.name.trim(),
    description: form.description.trim(),
    position
  })
}
</script>

<style scoped>
.admin-plan-stage-form {
  margin: 0;
}

.admin-plan-stage-form .form-field {
  margin-bottom: 1rem;
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

.form-input:disabled {
  background-color: var(--bg-light);
  color: var(--text-muted);
  cursor: not-allowed;
}

.admin-plan-stage-form__required {
  color: var(--danger);
  font-weight: 700;
}

.admin-plan-stage-form__hint {
  margin: 0.35rem 0 0;
  color: var(--text-muted);
  font-size: 0.8rem;
}

.admin-plan-stage-form__error {
  margin: 0 0 1rem;
  padding: 0.7rem 0.9rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
}

.admin-plan-stage-form__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-light);
}

.admin-plan-stage-form__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.45);
  border-top-color: var(--white);
  border-radius: 50%;
  display: inline-block;
  margin-right: 0.4rem;
  vertical-align: -2px;
  animation: admin-plan-stage-form-spin 0.8s linear infinite;
}

.admin-plan-stage-form__submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

@keyframes admin-plan-stage-form-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
