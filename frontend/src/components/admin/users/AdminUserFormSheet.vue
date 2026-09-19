<template>
  <FormSheet
    v-model="open"
    :title="isEditing ? `Edit ${userNoun}` : `Add ${userNoun}`"
    :description="isEditing ? 'Update the account details below.' : 'Manage role, state, and account status without touching other modules.'"
    width="min(100vw, 680px)"
  >
    <form class="admin-users-form" novalidate @submit.prevent="submitForm">
      <p v-if="formError" class="admin-users-form__error" role="alert">{{ formError }}</p>

      <div class="admin-users-form__grid">
        <div class="form-field">
          <label class="form-label" for="f-first">First name *</label>
          <input id="f-first" v-model.trim="form.firstName" class="form-input" />
        </div>
        <div class="form-field">
          <label class="form-label" for="f-last">Last name *</label>
          <input id="f-last" v-model.trim="form.lastName" class="form-input" />
        </div>
        <div class="form-field" :class="{ 'form-field--full': isEditing }">
          <label class="form-label" for="f-email">Email *</label>
          <input
            id="f-email"
            v-model.trim="form.email"
            type="email"
            class="form-input"
            :disabled="isEditing"
            :readonly="isEditing"
          />
        </div>
        <div v-if="!isEditing" class="form-field">
          <label class="form-label" for="f-role">Role *</label>
          <select id="f-role" v-model="form.role" class="form-input" :disabled="!!fixedRole">
            <option v-for="role in USER_ROLES" :key="role" :value="role">{{ roleLabel(role) }}</option>
          </select>
        </div>
        <div v-if="isEditing" class="form-field">
          <label class="form-label" for="f-role-edit">Role</label>
          <select id="f-role-edit" v-model="form.role" class="form-input" :disabled="!!fixedRole">
            <option v-for="role in USER_ROLES" :key="role" :value="role">{{ roleLabel(role) }}</option>
          </select>
        </div>

        <template v-if="form.role !== 'admin'">
          <div class="form-field">
            <label class="form-label" for="f-country">Country *</label>
            <select id="f-country" v-model="form.countryId" class="form-input" @change="onFormCountryChange">
              <option :value="undefined">Unassigned</option>
              <option v-for="country in countries" :key="country.id" :value="country.id">{{ country.countryName }}</option>
            </select>
          </div>
          <div v-if="formStates.length" class="form-field">
            <label class="form-label" for="f-state">State</label>
            <select id="f-state" v-model="form.stateId" class="form-input">
              <option :value="undefined">None</option>
              <option v-for="state in formStates" :key="state.id" :value="state.id">{{ state.stateName }}</option>
            </select>
          </div>
        </template>
      </div>

      <template v-if="form.role === 'student'">
        <div class="admin-users-form__section">Student details</div>
        <div class="admin-users-form__grid">
          <div class="form-field">
            <label class="form-label" for="f-school">School *</label>
            <input id="f-school" v-model.trim="form.schoolName" class="form-input" />
          </div>
          <div class="form-field">
            <label class="form-label" for="f-year">Year level *</label>
            <input
              id="f-year"
              v-model.number="form.yearLevel"
              type="number"
              min="9"
              max="12"
              class="form-input"
            />
          </div>
          <div class="form-field form-field--full">
            <label class="form-label" for="f-supervisor">Supervisor (optional)</label>
            <input
              id="f-supervisor"
              v-model.trim="form.supervisorEmail"
              list="user-supervisor-datalist"
              class="form-input"
              placeholder="Search by name or email"
            />
            <datalist id="user-supervisor-datalist">
              <option v-for="supervisor in supervisors" :key="supervisor.id" :value="supervisor.email">
                {{ userName(supervisor) }}
              </option>
            </datalist>
          </div>
        </div>
      </template>

      <template v-if="form.role === 'supervisor'">
        <div class="admin-users-form__section">Supervisor details</div>
        <div class="admin-users-form__grid">
          <div class="form-field form-field--full">
            <label class="form-label" for="f-sschool">School (optional)</label>
            <input id="f-sschool" v-model.trim="form.supervisorSchoolName" class="form-input" />
          </div>
        </div>
      </template>

      <template v-if="form.role === 'mentor'">
        <div class="admin-users-form__section">Mentor details</div>
        <div class="admin-users-form__grid">
          <div class="form-field">
            <label class="form-label" for="f-minst">Institution *</label>
            <input id="f-minst" v-model.trim="form.mentorInstitution" class="form-input" />
          </div>
          <div class="form-field">
            <label class="form-label" for="f-mmax">Max groups *</label>
            <input id="f-mmax" v-model.number="form.mentorMaxGroupCount" type="number" min="0" class="form-input" />
          </div>
          <div class="form-field form-field--full">
            <label class="form-label" for="f-mbg">Background</label>
            <input id="f-mbg" v-model.trim="form.mentorBackground" class="form-input" placeholder="e.g. Research" />
          </div>
          <div class="form-field form-field--full">
            <label class="form-label" for="f-mreason">Mentor reason *</label>
            <textarea
              id="f-mreason"
              v-model.trim="form.mentorReason"
              class="form-input"
              rows="2"
              placeholder="Supporting student research projects"
            ></textarea>
          </div>
        </div>
      </template>

      <template v-if="roleUsesInterests">
        <div class="admin-users-form__section">
          {{ form.role === 'mentor' ? 'Interests / Expertise' : 'Interests' }} *
        </div>
        <fieldset class="admin-users-form__interests">
          <legend class="sr-only">Select areas of interest</legend>
          <label v-for="option in INTEREST_OPTIONS" :key="option" class="admin-users-form__interest">
            <input
              type="checkbox"
              :value="option"
              :checked="form.interests.includes(option)"
              @change="onInterestToggle(option, $event)"
            />
            <span>{{ option }}</span>
          </label>
        </fieldset>
      </template>

      <div class="admin-users-form__section">Account</div>
      <div v-if="!isEditing" class="form-field">
        <label class="form-label">
          <input id="f-active" v-model="form.active" type="checkbox" class="form-checkbox" />
          Active (displays in the list immediately)
        </label>
      </div>

      <div class="admin-users-form__footer">
        <button
          v-if="isEditing && !isSupervisorMode"
          type="button"
          class="btn btn-danger"
          :disabled="saving || busy"
          @click="emit('delete')"
        >
          <i class="fas fa-trash-can" aria-hidden="true"></i>
          Delete
        </button>
        <span v-if="isEditing && !isSupervisorMode" class="admin-users-form__footer-spacer"></span>
        <button type="button" class="btn btn-outline" :disabled="saving || busy" @click="onCancel">
          Cancel
        </button>
        <button type="submit" class="btn btn-primary" :disabled="saving || busy">
          <span v-if="saving" class="admin-users-form__spinner" aria-hidden="true"></span>
          {{ isEditing ? 'Save Changes' : 'Create User' }}
        </button>
      </div>
    </form>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import type { AdminUser, AdminUserCountry, AdminUserState, CreateUserPayload } from '@/utils/adminAPI'
import { createAdminUser, setAdminUserActive, updateAdminUser } from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import { roleLabel, userName } from '@/utils/userFormat'
import { INTEREST_OPTIONS, USER_ROLES, type UserRole } from '@/utils/userOptions'

interface UserForm {
  firstName: string
  lastName: string
  email: string
  role: UserRole
  countryId?: number
  stateId?: number
  schoolName: string
  yearLevel?: number
  interests: string[]
  supervisorEmail: string
  supervisorSchoolName: string
  mentorBackground: string
  mentorInstitution: string
  mentorReason: string
  mentorMaxGroupCount?: number
  active: boolean
}

const props = defineProps<{
  modelValue: boolean
  userNoun: string
  user?: AdminUser | null
  fixedRole?: string
  isSupervisorMode: boolean
  countries: AdminUserCountry[]
  states: AdminUserState[]
  supervisors: AdminUser[]
  busy?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'close'): void
  (e: 'saved'): void
  (e: 'delete'): void
}>()

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value)
})

const isEditing = computed(() => Boolean(props.user))
const roleUsesInterests = computed(() => form.role === 'student' || form.role === 'mentor')

const defaultForm = (): UserForm => ({
  firstName: '',
  lastName: '',
  email: '',
  role: (props.fixedRole as UserRole) || 'student',
  countryId: undefined,
  stateId: undefined,
  schoolName: '',
  yearLevel: undefined,
  interests: [],
  supervisorEmail: '',
  supervisorSchoolName: '',
  mentorBackground: '',
  mentorInstitution: '',
  mentorReason: '',
  mentorMaxGroupCount: 2,
  active: true
})

const form = reactive<UserForm>(defaultForm())
const formError = ref('')
const saving = ref(false)
const editingOriginalActive = ref(false)

const formStates = computed(() => {
  if (!form.countryId) return []
  const country = props.countries.find((item) => item.id === form.countryId)
  if (!country) return []
  return props.states.filter((state) => state.countryName === country.countryName)
})

const onFormCountryChange = () => {
  form.stateId = undefined
}

const onInterestToggle = (option: string, event: Event) => {
  const checked = (event.target as HTMLInputElement).checked
  const next = new Set(form.interests)
  if (checked) next.add(option)
  else next.delete(option)
  form.interests = [...next]
}

const initForm = (editingUser: AdminUser | null) => {
  formError.value = ''
  if (!editingUser) {
    Object.assign(form, defaultForm())
    editingOriginalActive.value = false
    return
  }
  editingOriginalActive.value = Boolean(editingUser.isActive)
  Object.assign(form, {
    firstName: editingUser.firstName || '',
    lastName: editingUser.lastName || '',
    email: editingUser.email || '',
    role: (editingUser.role as UserRole) || props.fixedRole || 'student',
    countryId: editingUser.country?.id,
    stateId: editingUser.state?.id,
    schoolName: editingUser.role === 'student' ? editingUser.schoolName || '' : '',
    yearLevel: editingUser.role === 'student' ? (editingUser.yearLevel ?? undefined) : undefined,
    interests: (editingUser.interests || []).filter((interest) => INTEREST_OPTIONS.includes(interest)),
    supervisorEmail: editingUser.role === 'student' ? (editingUser.supervisorEmail || '') : '',
    supervisorSchoolName: editingUser.role === 'supervisor' ? editingUser.schoolName || '' : '',
    mentorBackground: editingUser.role === 'mentor' ? (editingUser.mentorBackground || '') : '',
    mentorInstitution: editingUser.role === 'mentor' ? (editingUser.mentorInstitution || '') : '',
    mentorReason: editingUser.role === 'mentor' ? (editingUser.mentorReason || '') : '',
    mentorMaxGroupCount: editingUser.role === 'mentor' ? (editingUser.mentorMaxGroupCount ?? 2) : 2,
    active: editingUser.isActive
  })
}

watch(
  () => props.modelValue,
  (opening) => {
    if (opening) initForm(props.user ?? null)
  }
)

const onCancel = () => {
  open.value = false
}

const isValidEmail = (email: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)

const validateForm = (): boolean => {
  const role = form.role
  if (!form.firstName.trim()) {
    formError.value = 'First name is required.'
    return false
  }
  if (!form.lastName.trim()) {
    formError.value = 'Last name is required.'
    return false
  }
  if (!form.email.trim()) {
    formError.value = 'Email is required.'
    return false
  }
  if (!isValidEmail(form.email.trim())) {
    formError.value = 'Invalid email format.'
    return false
  }
  if (role !== 'admin' && form.countryId === undefined) {
    formError.value = 'Country is required for non-admin users.'
    return false
  }
  if (role === 'student') {
    if (!form.schoolName.trim()) {
      formError.value = 'School is required for student users.'
      return false
    }
    if (!form.yearLevel || form.yearLevel < 9 || form.yearLevel > 12) {
      formError.value = 'Year level must be between 9 and 12.'
      return false
    }
  }
  if (role === 'mentor') {
    if (!form.mentorInstitution.trim()) {
      formError.value = 'Institution is required for mentor users.'
      return false
    }
    if (!form.mentorReason.trim()) {
      formError.value = 'Mentor reason is required for mentor users.'
      return false
    }
    if (form.mentorMaxGroupCount === undefined || form.mentorMaxGroupCount < 0) {
      formError.value = 'Max group count must be 0 or greater.'
      return false
    }
  }
  if (roleUsesInterests.value && form.interests.length === 0) {
    formError.value = `At least one interest is required for ${role} users.`
    return false
  }
  return true
}

const submitForm = async () => {
  formError.value = ''
  if (!validateForm()) return

  const role = form.role
  const resolveCountryName = (id?: number) => {
    if (id === undefined) return undefined
    return props.countries.find((country) => country.id === id)?.countryName
  }
  const resolveStateName = (id?: number) => {
    if (id === undefined) return undefined
    return props.states.find((state) => state.id === id)?.stateName
  }

  saving.value = true
  try {
    if (isEditing.value && props.user) {
      const payload: Record<string, unknown> = {
        firstName: form.firstName,
        lastName: form.lastName,
        role,
        countryId: role === 'admin' ? null : form.countryId,
        stateId: role === 'admin' ? null : form.stateId
      }
      if (role === 'student') {
        payload.schoolName = form.schoolName
        payload.yearLevel = form.yearLevel
        payload.interests = form.interests
        payload.supervisorEmail = form.supervisorEmail || undefined
      } else if (role === 'supervisor') {
        payload.supervisorSchoolName = form.supervisorSchoolName || null
      } else if (role === 'mentor') {
        payload.mentorBackground = form.mentorBackground || null
        payload.mentorInstitution = form.mentorInstitution
        payload.mentorReason = form.mentorReason
        payload.mentorMaxGroupCount = form.mentorMaxGroupCount
        payload.interests = form.interests
      }

      const activeWasChanged = form.active !== editingOriginalActive.value
      await updateAdminUser(props.user.id, payload)
      if (activeWasChanged) {
        await setAdminUserActive(props.user.id, form.active)
      }
    } else {
      const payload: Record<string, unknown> = {
        email: form.email,
        firstName: form.firstName,
        lastName: form.lastName,
        role,
        active: form.active
      }
      const countryName = resolveCountryName(form.countryId)
      const stateName = role === 'admin' ? undefined : resolveStateName(form.stateId)
      if (countryName) payload.country = countryName
      if (stateName) payload.state = stateName

      if (role === 'student') {
        payload.schoolName = form.schoolName
        payload.yearLevel = form.yearLevel
        payload.supervisorEmail = form.supervisorEmail || undefined
        payload.interests = form.interests
      } else if (role === 'supervisor') {
        payload.supervisorSchoolName = form.supervisorSchoolName || null
      } else if (role === 'mentor') {
        payload.mentorInstitution = form.mentorInstitution
        payload.mentorReason = form.mentorReason
        payload.mentorMaxGroupCount = form.mentorMaxGroupCount
        payload.mentorBackground = form.mentorBackground || null
        payload.interests = form.interests
      }

      await createAdminUser(payload as CreateUserPayload)
    }
    open.value = false
    emit('saved')
  } catch (submitError) {
    logApiError('admin.users.save', submitError)
    formError.value =
      submitError instanceof Error ? submitError.message : 'Unable to save the user right now.'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.admin-users-form__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.9rem;
}

.admin-users-form__section {
  margin: 1.4rem 0 0.6rem;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid var(--border-light);
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--dark-green);
}

.admin-users-form__interests {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.45rem;
  border: none;
  padding: 0;
  margin: 0.4rem 0 0;
}

.admin-users-form__interest {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.9rem;
  color: var(--charcoal);
  cursor: pointer;
}

.admin-users-form__interest input {
  margin-top: 0.2rem;
  accent-color: var(--dark-green);
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

.form-checkbox {
  width: 16px;
  height: 16px;
  margin-right: 0.5rem;
  accent-color: var(--dark-green);
  vertical-align: -2px;
}

.admin-users-form__error {
  margin: 0 0 1rem;
  padding: 0.7rem 0.9rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
}

.admin-users-form__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-light);
}

.admin-users-form__footer-spacer {
  flex: 1;
}

.admin-users-form__spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-right: 0.5rem;
  vertical-align: -2px;
  border: 2px solid rgba(255, 255, 255, 0.5);
  border-top-color: var(--white);
  border-radius: 50%;
  animation: admin-users-spin 0.8s linear infinite;
}

@keyframes admin-users-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .admin-users-form__spinner {
    animation: none;
  }
}

@media (max-width: 640px) {
  .admin-users-form__grid {
    grid-template-columns: 1fr;
  }
}
</style>