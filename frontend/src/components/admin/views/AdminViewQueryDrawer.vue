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
      <fieldset class="view-drawer-section">
        <legend class="view-drawer-section__legend">
          <span class="view-drawer-section__dot"></span>
          <span>View Details</span>
        </legend>

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

        <div class="form-field">
          <label class="form-label" for="view-visibility">Visibility</label>
          <select id="view-visibility" v-model="form.visibility" class="form-input form-select">
            <option value="shared">Admin Shared (Visible to all admins)</option>
            <option value="private">Private (Only visible to me)</option>
          </select>
        </div>
      </fieldset>

      <!-- SECTION 2: TARGET ROLES & BASE FILTERS -->
      <fieldset class="view-drawer-section">
        <legend class="view-drawer-section__legend">
          <span class="view-drawer-section__dot"></span>
          <span>Target Roles & Base Filters</span>
        </legend>

        <div class="form-field">
          <span class="form-label">Include Roles</span>
          <div class="view-drawer-form__roles-row">
            <button
              v-for="role in ROLE_CHOICES"
              :key="role.value"
              type="button"
              class="view-drawer-form__role-pill"
              :class="{ 'view-drawer-form__role-pill--active': isRoleSelected(role.value) }"
              @click="toggleRole(role.value)"
            >
              <i
                v-if="isRoleSelected(role.value)"
                class="fas fa-check view-drawer-form__role-check"
                aria-hidden="true"
              ></i>
              <span>{{ role.label }}</span>
            </button>
          </div>
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
      </fieldset>

      <!-- SECTION 3: ADVANCED CONDITIONS -->
      <fieldset class="view-drawer-section">
        <legend class="view-drawer-section__legend">
          <span class="view-drawer-section__dot"></span>
          <span>Advanced Conditions</span>
        </legend>

        <AdminViewConditionsBuilder v-model="form.advancedConditions" />
      </fieldset>

      <!-- SECTION 4: VISIBLE FIELDS / COLUMNS TO SHOW -->
      <fieldset class="view-drawer-section">
        <legend class="view-drawer-section__legend">
          <span class="view-drawer-section__dot"></span>
          <span>Visible Fields / Columns to Show</span>
        </legend>

        <AdminViewColumnSelector v-model="form.visibleColumns" />
      </fieldset>
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
  visibility: 'system' | 'shared' | 'private'
  targetRoles: string[]
  accountStatus: 'all' | 'active' | 'inactive'
  engagementStatus: 'all' | 'matched' | 'unmatched' | 'pending'
  advancedConditions: ViewCondition[]
  visibleColumns: string[]
}>({
  name: '',
  description: '',
  visibility: 'shared',
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
    form.visibility = props.view.visibility || 'shared'
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
    form.visibility = 'shared'
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
      visibility: form.visibility,
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
  gap: 1.5rem;
}

.view-drawer-form__error {
  padding: 0.65rem 0.85rem;
  background-color: rgba(220, 53, 69, 0.1);
  color: var(--danger);
  border: 1px solid var(--danger);
  border-radius: 6px;
  font-size: 0.9rem;
}

.view-drawer-section {
  border: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.view-drawer-section__legend {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.85rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--charcoal);
  margin-bottom: 0.25rem;
}

.view-drawer-section__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--dark-green);
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
  font-size: 0.9rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background-color: var(--surface-elevated, #ffffff);
  color: var(--charcoal);
  transition: border-color 0.15s ease-in-out;
}

.form-input:focus {
  outline: none;
  border-color: var(--dark-green);
}

.form-textarea {
  resize: vertical;
}

.view-drawer-form__roles-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.view-drawer-form__role-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.75rem;
  font-size: 0.85rem;
  font-weight: 500;
  border-radius: 9999px;
  border: 1px solid var(--border-light);
  background-color: var(--surface-elevated, #ffffff);
  color: var(--charcoal);
  cursor: pointer;
  transition: all 0.15s ease-in-out;
}

.view-drawer-form__role-pill:hover {
  border-color: var(--dark-green);
  background-color: var(--bg-light);
}

.view-drawer-form__role-pill--active {
  background-color: rgba(1, 113, 81, 0.1);
  border-color: var(--dark-green);
  color: var(--dark-green);
  font-weight: 600;
}

.view-drawer-form__role-check {
  font-size: 0.75rem;
}

.view-drawer-form__grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
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
