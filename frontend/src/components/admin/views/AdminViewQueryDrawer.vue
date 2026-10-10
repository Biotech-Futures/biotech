<template>
  <FormSheet
    :model-value="modelValue"
    :title="isEditing ? 'Edit View' : 'Create View'"
    description="Define query conditions, role filters, and visible attributes for custom mini-reports."
    width="min(100vw, 680px)"
    @update:model-value="onClose"
  >
    <form class="view-drawer-form" novalidate @submit.prevent="handleSubmit">
      <div v-if="errorMessage" class="view-drawer-form__error" role="alert">
        {{ errorMessage }}
      </div>

      <!-- SECTION 1: VIEW DETAILS -->
      <div class="view-drawer-form__section">View Details</div>

      <div class="form-field">
        <label class="form-label" for="view-name">View Name *</label>
        <input
          id="view-name"
          v-model.trim="form.name"
          type="text"
          required
          placeholder="e.g. InScience 2026 - Active Participants"
          class="form-input"
        />
      </div>

      <div class="form-field">
        <label class="form-label" for="view-desc">Description</label>
        <textarea
          id="view-desc"
          v-model.trim="form.description"
          rows="2"
          placeholder="Provide a short description for this view cohort..."
          class="form-input form-textarea"
        ></textarea>
      </div>

      <!-- SECTION 2: TARGET ROLES & BASE FILTERS -->
      <div class="view-drawer-form__section">Target Roles & Base Filters</div>

      <div class="form-field">
        <span class="form-label">Include Roles</span>
        <fieldset class="view-drawer-form__checkbox-grid">
          <legend class="sr-only">Target roles</legend>
          <label
            v-for="role in ROLE_CHOICES"
            :key="role.value"
            class="view-drawer-form__checkbox-label"
          >
            <input
              type="checkbox"
              :value="role.value"
              :checked="isRoleSelected(role.value)"
              @change="toggleRole(role.value)"
            />
            <span>{{ role.label }}</span>
          </label>
        </fieldset>
      </div>

      <div class="view-drawer-form__grid-2">
        <div class="form-field">
          <label class="form-label" for="view-status">Account Status</label>
          <select id="view-status" v-model="form.accountStatus" class="form-input form-select">
            <option value="all">All statuses</option>
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
          </select>
        </div>

        <div class="form-field">
          <label class="form-label" for="view-engagement">Engagement / Matching</label>
          <select id="view-engagement" v-model="form.engagementStatus" class="form-input form-select">
            <option value="all">All</option>
            <option value="matched">Matched (in active group)</option>
            <option value="unmatched">Unmatched</option>
            <option value="pending">Pending matching / invited</option>
          </select>
        </div>
      </div>

      <!-- SECTION 3: ADVANCED CONDITIONS -->
      <div class="view-drawer-form__section">Advanced Conditions</div>

      <AdminViewConditionsBuilder v-model="form.advancedConditions" />

      <!-- SECTION 4: VISIBLE FIELDS / COLUMNS TO SHOW -->
      <div class="view-drawer-form__section">Visible Fields / Columns to Show</div>

      <AdminViewColumnSelector v-model="form.visibleColumns" />
    </form>

    <template #footer>
      <div class="view-drawer-footer">
        <button
          type="button"
          class="btn btn-outline"
          :disabled="isSubmitting"
          @click="onClose"
        >
          Cancel
        </button>
        <button
          type="button"
          class="btn btn-primary"
          :disabled="isSubmitting"
          @click="handleSubmit"
        >
          <span v-if="isSubmitting">Saving...</span>
          <span v-else>{{ isEditing ? 'Save Changes' : 'Save & Run View' }}</span>
        </button>
      </div>
    </template>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import AdminViewConditionsBuilder from '@/components/admin/views/AdminViewConditionsBuilder.vue'
import AdminViewColumnSelector from '@/components/admin/views/AdminViewColumnSelector.vue'
import {
  createAdminView,
  updateAdminView,
  type AdminView,
  type ViewCondition,
} from '@/utils/adminAPI'

const ROLE_CHOICES = [
  { value: 'student', label: 'Student' },
  { value: 'mentor', label: 'Mentor' },
  { value: 'supervisor', label: 'Supervisor' },
  { value: 'admin', label: 'Admin' },
]

const DEFAULT_COLUMNS = [
  'name',
  'email',
  'role',
  'school',
  'matched_mentor',
  'status',
]

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    view?: AdminView | null
  }>(),
  {
    view: null,
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'saved', view: AdminView): void
}>()

const isEditing = computed(() => !!props.view?.id)
const isSubmitting = ref(false)
const errorMessage = ref('')

const form = reactive<{
  name: string
  description: string
  targetRoles: string[]
  accountStatus: 'all' | 'active' | 'inactive'
  engagementStatus: 'all' | 'matched' | 'unmatched' | 'pending'
  advancedConditions: ViewCondition[]
  visibleColumns: string[]
}>({
  name: '',
  description: '',
  targetRoles: ['student', 'mentor'],
  accountStatus: 'active',
  engagementStatus: 'all',
  advancedConditions: [],
  visibleColumns: [...DEFAULT_COLUMNS],
})

const resetForm = () => {
  if (props.view) {
    form.name = props.view.name || ''
    form.description = props.view.description || ''
    form.targetRoles = props.view.targetRoles?.length ? [...props.view.targetRoles] : []
    form.accountStatus = props.view.accountStatus || 'all'
    form.engagementStatus = props.view.engagementStatus || 'all'
    form.advancedConditions = props.view.advancedConditions?.length
      ? JSON.parse(JSON.stringify(props.view.advancedConditions))
      : []
    form.visibleColumns = props.view.visibleColumns?.length
      ? [...props.view.visibleColumns]
      : [...DEFAULT_COLUMNS]
  } else {
    form.name = ''
    form.description = ''
    form.targetRoles = ['student', 'mentor']
    form.accountStatus = 'active'
    form.engagementStatus = 'all'
    form.advancedConditions = []
    form.visibleColumns = [...DEFAULT_COLUMNS]
  }
  errorMessage.value = ''
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      resetForm()
    }
  },
  { immediate: true }
)

const onClose = () => {
  emit('update:modelValue', false)
}

const isRoleSelected = (role: string) => {
  return form.targetRoles.includes(role)
}

const toggleRole = (role: string) => {
  const idx = form.targetRoles.indexOf(role)
  if (idx >= 0) {
    form.targetRoles.splice(idx, 1)
  } else {
    form.targetRoles.push(role)
  }
}

const handleSubmit = async () => {
  errorMessage.value = ''

  if (!form.name.trim()) {
    errorMessage.value = 'View Name is required.'
    return
  }

  if (!form.visibleColumns.length) {
    errorMessage.value = 'At least one visible column must be selected.'
    return
  }

  isSubmitting.value = true
  try {
    const payload = {
      name: form.name.trim(),
      description: form.description.trim(),
      targetRoles: form.targetRoles,
      accountStatus: form.accountStatus,
      engagementStatus: form.engagementStatus,
      advancedConditions: form.advancedConditions,
      visibleColumns: form.visibleColumns,
    }

    let savedView: AdminView
    if (isEditing.value && props.view?.id) {
      savedView = await updateAdminView(props.view.id, payload)
    } else {
      savedView = await createAdminView(payload)
    }

    emit('saved', savedView)
    onClose()
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to save view.'
    errorMessage.value = message
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.view-drawer-form {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.view-drawer-form__error {
  margin: 0 0 0.5rem;
  padding: 0.7rem 0.9rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.9rem;
}

.view-drawer-form__section {
  margin: 1.4rem 0 0.2rem;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid var(--border-light);
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--dark-green);
}

.view-drawer-form__section:first-of-type {
  margin-top: 0;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--charcoal);
}

.form-input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  font: inherit;
  font-family: inherit;
  font-size: 0.9rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background-color: var(--surface-elevated, #ffffff);
  color: var(--charcoal);
  transition: border-color 0.15s ease-in-out;
}

.form-input::placeholder,
.form-textarea::placeholder {
  font: inherit;
  font-family: inherit;
  font-size: inherit;
  color: var(--text-muted);
}

.form-input:focus {
  outline: none;
  border-color: var(--dark-green);
}

.form-textarea {
  resize: vertical;
  font: inherit;
  font-family: inherit;
}

.view-drawer-form__checkbox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 0.5rem;
  border: none;
  padding: 0;
  margin: 0.25rem 0 0;
}

.view-drawer-form__checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--charcoal);
  cursor: pointer;
  user-select: none;
}

.view-drawer-form__checkbox-label input {
  accent-color: var(--dark-green);
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.view-drawer-form__grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-top: 0.4rem;
}

.view-drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  width: 100%;
}

@media (max-width: 600px) {
  .view-drawer-form__grid-2 {
    grid-template-columns: 1fr;
  }
}
</style>
