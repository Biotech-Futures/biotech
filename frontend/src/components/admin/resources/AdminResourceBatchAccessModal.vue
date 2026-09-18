<template>
  <FormSheet
    v-model="open"
    title="Batch Edit Access"
    :description="sheetDescription"
    width="min(100vw, 560px)"
    @close="onCancel"
  >
    <form class="admin-batch-access-form admin-modal--batch-access" novalidate @submit.prevent="onApply">
      <p v-if="errorMessage" class="admin-batch-access-form__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ errorMessage }}</span>
      </p>

      <div class="admin-batch-access-form__grid">
        <!-- Visibility Scope -->
        <div class="form-field form-field--full">
          <label class="form-label" for="batch-visibility-scope">Visibility Scope *</label>
          <select
            id="batch-visibility-scope"
            v-model="visibilityScope"
            class="form-input filter-select"
            :disabled="busy"
          >
            <option value="global">Global (All Users)</option>
            <option value="role_based">Role-based</option>
          </select>
          <p class="admin-batch-access-form__hint">
            {{ visibilityScope === 'global' ? 'All authenticated students, mentors, and admins will have access.' : 'Restrict visibility to selected user roles.' }}
          </p>
        </div>

        <!-- Target Roles -->
        <div v-if="visibilityScope === 'role_based'" class="form-field form-field--full">
          <label class="form-label">Target Roles *</label>
          <div v-if="loadingRoles" class="batch-access__roles-loading">
            <span class="admin-batch-access-form__spinner" aria-hidden="true"></span>
            <span>Loading roles...</span>
          </div>
          <fieldset v-else class="admin-batch-access-form__checkbox-grid">
            <legend class="sr-only">Select visible roles</legend>
            <label
              v-for="role in availableRoles"
              :key="role.id"
              class="admin-batch-access-form__checkbox-label"
            >
              <input
                type="checkbox"
                :value="role.id"
                :checked="selectedRoleIds.includes(role.id)"
                :disabled="busy"
                @change="toggleRole(role.id)"
              />
              <span>{{ formatRoleName(role) }}</span>
            </label>
          </fieldset>
          <p class="admin-batch-access-form__hint">
            Select at least one role. Only users assigned these roles will be able to view and access these resources.
          </p>
        </div>
      </div>

      <div class="admin-batch-access-form__actions">
        <button
          type="button"
          class="btn btn-outline"
          :disabled="busy"
          @click="onCancel"
        >
          Cancel
        </button>
        <button
          type="submit"
          class="btn btn-primary"
          :disabled="busy"
        >
          <span v-if="busy" class="admin-batch-access-form__spinner" aria-hidden="true"></span>
          <span>{{ busy ? 'Applying...' : 'Apply Access Changes' }}</span>
        </button>
      </div>
    </form>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import type { AdminResourceRoleItem } from '@/utils/adminAPI'
import { fetchAdminResourceRoles } from '@/utils/adminAPI'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    count: number
    busy?: boolean
  }>(),
  {
    busy: false
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'close'): void
  (e: 'apply', payload: { visibilityScope: 'global' | 'role_based'; roleIds: number[] }): void
}>()

const open = computed({
  get: () => props.modelValue,
  set: (val: boolean) => {
    emit('update:modelValue', val)
    if (!val) emit('close')
  }
})

const sheetDescription = computed(() => {
  return `Updating access settings for ${props.count} selected ${props.count === 1 ? 'resource' : 'resources'}.`
})

const visibilityScope = ref<'global' | 'role_based'>('role_based')
const selectedRoleIds = ref<number[]>([])
const availableRoles = ref<AdminResourceRoleItem[]>([])
const loadingRoles = ref(false)
const errorMessage = ref('')

const formatRoleName = (role: AdminResourceRoleItem): string => {
  if (role.type_name) return role.type_name
  if (role.slug) {
    return role.slug
      .split(/[-_]+/)
      .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
      .join(' ')
  }
  return `Role #${role.id}`
}

const toggleRole = (roleId: number) => {
  const idx = selectedRoleIds.value.indexOf(roleId)
  if (idx > -1) {
    selectedRoleIds.value.splice(idx, 1)
  } else {
    selectedRoleIds.value.push(roleId)
  }
}

const loadRoles = async () => {
  if (availableRoles.value.length > 0) return
  loadingRoles.value = true
  try {
    const roles = await fetchAdminResourceRoles()
    // Exclude system admin role from audience targeting
    availableRoles.value = (roles || []).filter((r) => r.slug !== 'admin')
  } catch (err) {
    console.error('Failed to load roles for batch access:', err)
  } finally {
    loadingRoles.value = false
  }
}

watch(
  () => props.modelValue,
  (isOpen) => {
    if (isOpen) {
      errorMessage.value = ''
      visibilityScope.value = 'role_based'
      selectedRoleIds.value = []
      void loadRoles()
    }
  }
)

const onCancel = () => {
  if (props.busy) return
  emit('update:modelValue', false)
  emit('close')
}

const onApply = () => {
  if (visibilityScope.value === 'role_based' && selectedRoleIds.value.length === 0) {
    errorMessage.value = 'Please select at least one role for role-based visibility.'
    return
  }

  errorMessage.value = ''
  emit('apply', {
    visibilityScope: visibilityScope.value,
    roleIds: visibilityScope.value === 'role_based' ? [...selectedRoleIds.value] : []
  })
}
</script>

<style scoped>
.admin-batch-access-form {
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.admin-batch-access-form__error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 0.85rem;
  border-radius: 6px;
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  font-size: 0.85rem;
  margin: 0;
}

.admin-batch-access-form__grid {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-field--full {
  width: 100%;
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

.admin-batch-access-form__hint {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin: 0.35rem 0 0;
}

.batch-access__roles-loading {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.admin-batch-access-form__checkbox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 0.55rem;
  border: none;
  padding: 0;
  margin: 0.25rem 0 0;
}

.admin-batch-access-form__checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--charcoal);
  cursor: pointer;
}

.admin-batch-access-form__checkbox-label input[type='checkbox'] {
  width: 16px;
  height: 16px;
  accent-color: var(--dark-green);
  cursor: pointer;
}

.admin-batch-access-form__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 0.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-light);
}

.admin-batch-access-form__spinner {
  display: inline-block;
  width: 0.85rem;
  height: 0.85rem;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: admin-batch-access-spin 0.6s linear infinite;
}

@keyframes admin-batch-access-spin {
  to { transform: rotate(360deg); }
}
</style>
