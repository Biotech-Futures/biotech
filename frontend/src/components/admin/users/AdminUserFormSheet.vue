<template>
  <FormSheet
    v-model="open"
    :title="isEditing ? `Edit ${userNoun}` : `Add ${userNoun}`"
    :description="isEditing ? lastEditedLabel || 'Update the account details below.' : 'Manage role, state, and account status without touching other modules.'"
    width="min(100vw, 680px)"
  >
    <form class="admin-users-form" novalidate @submit.prevent="submitForm">

      <div class="admin-users-form__grid">
        <div class="form-field form-field--full">
          <label class="form-label" for="f-email">Email <span class="required-mark" aria-hidden="true">*</span></label>
          <input
            id="f-email"
            v-model.trim="form.email"
            type="email"
            class="form-input app-input"
            :disabled="isEditing && isSupervisorMode"
            :readonly="isEditing && isSupervisorMode"
            :aria-invalid="Boolean(emailProblem('email'))"
            :aria-describedby="isEditing && !isSupervisorMode ? 'f-email-hint' : undefined"
            @blur="checkEmailBox('email')"
          />
          <!-- Checked as it's left: what saving refuses, or a warning to confirm. -->
          <p v-if="emailProblem('email')" class="admin-users-form__field-error" role="alert">
            {{ emailProblem('email') }}
          </p>
          <EmailCheckNote
            :state="emailNote('email')"
          />
          <p v-if="isEditing && !isSupervisorMode" id="f-email-hint" class="admin-users-form__hint">
            Changing this address updates the user's login and future emails. They will need to
            request a new login code or password-reset link if they have one already.
          </p>
        </div>
        <div v-if="!isEditing" class="form-field">
          <label class="form-label" for="f-role">Role <span class="required-mark" aria-hidden="true">*</span></label>
          <AppSelect id="f-role" v-model="form.role" class="form-input app-input" :options="ROLE_OPTIONS" :disabled="!!fixedRole" />
        </div>
        <div v-if="isEditing" class="form-field">
          <label class="form-label" for="f-role-edit">Role</label>
          <AppSelect
            id="f-role-edit"
            v-model="form.role"
            class="form-input app-input"
            :options="ROLE_OPTIONS"
            :disabled="!!fixedRole"
            :aria-describedby="losesSupportAccess ? 'f-role-support-note' : undefined"
          />
        </div>
        <!-- Moving an account off the support role revokes its queue access on
             save (backend services/user.py, the role_moved branch, audited).
             The server is right to do it, but nothing here said so; adminweb
             was silent too (U6 C9). Said at the moment of the change, because
             the save is the action and it cannot be taken back from here.
             Not said for a move to admin, which keeps the queue (see
             losesSupportAccess). aria-describedby is what carries the note to
             a screen reader; aria-live on an element inserted together with
             its text is announced unreliably, so it is only a second chance. -->
        <p
          v-if="losesSupportAccess"
          id="f-role-support-note"
          class="admin-users-form__note admin-users-form__note--support form-field--full"
          aria-live="polite"
        >
          Saving with this role removes their access to the support queue. Tickets they own stay in
          their name until somebody reassigns them.
        </p>
      </div>

      <!-- Country, state and status, as the user panel's Account has them. -->
      <template v-if="form.role !== 'admin' || !isEditing">
        <div class="admin-users-form__section">Account</div>
        <div class="admin-users-form__grid">
          <template v-if="form.role !== 'admin'">
            <div class="form-field">
              <label class="form-label" for="f-country">Country</label>
              <AppSelect
                id="f-country"
                :model-value="form.countryId ?? null"
                class="form-input app-input"
                :options="countryOptions"
                @update:model-value="(value) => (form.countryId = value === null ? undefined : Number(value))"
                @change="onFormCountryChange"
              />
            </div>
            <!-- Picked from the list where the country has one (Australia's),
                 else typed, as registering takes it. -->
            <!-- Beside Country always: greyed out until a country is picked. -->
            <div class="form-field">
              <label class="form-label" for="f-state">State</label>
              <AppSelect
                v-if="formStates.length || form.countryId === undefined"
                id="f-state"
                :model-value="form.stateId ?? null"
                class="form-input app-input"
                :options="stateOptions"
                :searchable="false"
                :disabled="form.countryId === undefined"
                :placeholder="form.countryId === undefined ? 'Choose a country first' : 'Choose a state'"
                @update:model-value="(value) => (form.stateId = value === null ? undefined : Number(value))"
              />
              <input
                v-else
                id="f-state"
                v-model.trim="form.stateName"
                class="form-input app-input"
                data-test="form-state-name"
                maxlength="255"
              />
            </div>
          </template>
          <div v-if="!isEditing" class="form-field">
            <label class="form-label" for="f-status">Status</label>
            <AppSelect
              id="f-status"
              :model-value="form.active ? 'active' : 'inactive'"
              class="form-input app-input"
              data-test="form-status"
              :options="STATUS_OPTIONS"
              :searchable="false"
              @update:model-value="(value) => (form.active = value === 'active')"
            />
          </div>
        </div>
      </template>

      <!-- Their name, then what their role needs, as the user panel's details
           part has them. -->
      <div class="admin-users-form__section">{{ roleLabel(form.role) }} details</div>
      <div class="admin-users-form__grid">
        <div class="form-field">
          <label class="form-label" for="f-first">First name</label>
          <input id="f-first" v-model.trim="form.firstName" class="form-input app-input" />
        </div>
        <div class="form-field">
          <label class="form-label" for="f-last">Last name</label>
          <input id="f-last" v-model.trim="form.lastName" class="form-input app-input" />
        </div>

        <template v-if="form.role === 'student'">
          <div class="form-field">
            <label class="form-label" for="f-school">School</label>
            <input
              id="f-school"
              v-model.trim="form.schoolName"
              class="form-input app-input"
              @blur="checkEmailBox('schoolName')"
            />
            <!-- Checked as it's left too: a university gets a warning to confirm. -->
            <EmailCheckNote
              subject="school"
              :state="emailNote('schoolName')"
            />
          </div>
          <div class="form-field">
            <label class="form-label" for="f-year">Year level</label>
            <AppSelect
              id="f-year"
              :model-value="form.yearLevel ?? null"
              class="form-input app-input"
              :options="YEAR_OPTIONS"
              :searchable="false"
              placeholder="Choose a year"
              @update:model-value="(value) => (form.yearLevel = value === null ? undefined : Number(value))"
            />
          </div>
        </template>

        <template v-if="form.role === 'supervisor'">
          <div class="form-field form-field--full">
            <label class="form-label" for="f-sschool">School</label>
            <input id="f-sschool" v-model.trim="form.supervisorSchoolName" class="form-input app-input" />
          </div>
        </template>

        <!-- Pronouns as the user panel has them: after the name for a mentor or
             admin, after the school for a supervisor. -->
        <template v-if="form.role === 'mentor' || form.role === 'admin' || form.role === 'supervisor'">
          <div class="form-field">
            <label class="form-label" for="f-mpronouns">Pronouns</label>
            <AppSelect
              id="f-mpronouns"
              v-model="form.pronounsChoice"
              class="form-input app-input"
              :options="PRONOUN_SELECT_OPTIONS"
              :placeholder="PRONOUN_PLACEHOLDER"
              clearable
              :searchable="false"
            />
          </div>
          <div v-if="form.pronounsChoice === 'Other'" class="form-field">
            <label class="form-label" for="f-mpronouns-other">Their pronouns</label>
            <input id="f-mpronouns-other" v-model="form.pronounsOther" class="form-input app-input" maxlength="100" />
          </div>
        </template>

        <!-- A mentor's background and where they work or study, as the mentor
             panel's Mentor Details has them. -->
        <template v-if="form.role === 'mentor'">
          <div class="form-field form-field--full">
            <label class="form-label" for="f-mbg">Background</label>
            <AppSelect
              id="f-mbg"
              v-model="form.mentorBackground"
              class="form-input app-input"
              :options="mentorBackgroundOptions"
              :searchable="false"
              placeholder="Choose a background"
            />
          </div>
          <div v-if="form.mentorBackground === 'industry'" class="form-field">
            <label class="form-label" for="f-mcompany">Company</label>
            <input id="f-mcompany" v-model.trim="form.mentorCompany" class="form-input app-input" maxlength="255" />
          </div>
          <div v-else class="form-field">
            <label class="form-label" for="f-minst">Institution</label>
            <input id="f-minst" v-model.trim="form.mentorInstitution" class="form-input app-input" maxlength="255" />
          </div>
          <div v-if="mentorStudying" class="form-field">
            <label class="form-label" for="f-myear">Year of study</label>
            <AppSelect
              id="f-myear"
              v-model="form.mentorUniversityYear"
              class="form-input app-input"
              :options="STUDY_YEAR_OPTIONS"
              :searchable="false"
              placeholder="Choose a year"
            />
          </div>
          <div v-if="form.mentorBackground !== 'industry'" class="form-field">
            <label class="form-label" for="f-mfield">Field of study</label>
            <input id="f-mfield" v-model.trim="form.mentorFieldOfStudy" class="form-input app-input" maxlength="255" />
          </div>
        </template>

        <!-- Interests last in their details, as the user panel has them, the
             heading on the box's line as registering shows it. -->
        <div v-if="roleUsesInterests" class="form-field form-field--full">
          <fieldset class="admin-users-form__interests">
            <legend>{{ form.role === 'mentor' ? 'Expertise' : 'Interests' }}</legend>
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
        </div>

        <!-- A mentor's capacity and hours, after their interests as the panel has them. -->
        <template v-if="form.role === 'mentor'">
          <div class="form-field">
            <label class="form-label" for="f-mcap">Capacity</label>
            <AppSelect
              id="f-mcap"
              :model-value="form.mentorMaxGroupCount ?? null"
              class="form-input app-input"
              :options="capacityOptions"
              :searchable="false"
              placeholder="Choose a capacity"
              @update:model-value="(value) => (form.mentorMaxGroupCount = value === null ? undefined : Number(value))"
            />
          </div>
        </template>

        <!-- A student's pronouns, after their interests as the user panel has them. -->
        <template v-if="form.role === 'student'">
          <div class="form-field">
            <label class="form-label" for="f-pronouns">Pronouns</label>
            <AppSelect
              id="f-pronouns"
              v-model="form.pronounsChoice"
              class="form-input app-input"
              :options="PRONOUN_SELECT_OPTIONS"
              :placeholder="PRONOUN_PLACEHOLDER"
              clearable
              :searchable="false"
            />
          </div>
          <div v-if="form.pronounsChoice === 'Other'" class="form-field">
            <label class="form-label" for="f-pronouns-other">Their pronouns</label>
            <input id="f-pronouns-other" v-model="form.pronounsOther" class="form-input app-input" maxlength="100" />
          </div>
        </template>
      </div>

      <!-- Who supervises them and the group they join, as the user panel's
           Supervisor and Group part has them. -->
      <template v-if="form.role === 'student'">
        <div class="admin-users-form__section">Supervisor and Group</div>
        <div class="admin-users-form__grid">
          <div class="form-field form-field--full">
            <label class="form-label" for="f-supervisor">Supervisor</label>
            <AppSelect
              id="f-supervisor"
              v-model="form.supervisorEmail"
              class="form-input app-input"
              searchable
              :options="supervisorOptions"
              placeholder="Search by name or email"
              empty-text="No supervisor matches"
            />
          </div>
          <div v-if="!isEditing" class="form-field">
            <label class="form-label" for="f-group">Group</label>
            <AppSelect
              id="f-group"
              v-model="form.groupId"
              class="form-input app-input"
              searchable
              :options="groupOptions"
              :loading="groupsLoading"
              placeholder="Search by group name"
              empty-text="No group matches"
            />
          </div>
        </div>
        <p v-if="groupsError" class="admin-users-form__error" role="alert">{{ groupsError }}</p>
      </template>

      <template v-if="form.role === 'student'">
        <div class="admin-users-form__section">Guardian &amp; consent</div>
        <p v-if="pendingGuardian" class="admin-users-form__note" data-test="form-pending-guardian">
          The student asked to change their guardian to
          <strong>{{ pendingGuardian.firstName }} {{ pendingGuardian.lastName }}</strong>
          ({{ pendingGuardian.email || 'no email' }}). They become the guardian once they sign the consent
          form; changing the guardian below discards the request.
        </p>
        <div class="admin-users-form__grid">
          <div class="form-field">
            <label class="form-label" for="f-gfirst">Guardian first name</label>
            <input id="f-gfirst" v-model.trim="form.guardianFirstName" class="form-input app-input" />
          </div>
          <div class="form-field">
            <label class="form-label" for="f-glast">Guardian last name</label>
            <input id="f-glast" v-model.trim="form.guardianLastName" class="form-input app-input" />
          </div>
          <div class="form-field form-field--full">
            <label class="form-label" for="f-gemail">Guardian email</label>
            <input
              id="f-gemail"
              v-model.trim="form.guardianEmail"
              type="email"
              class="form-input app-input"
              :aria-invalid="Boolean(emailProblem('guardianEmail'))"
              @blur="checkEmailBox('guardianEmail')"
            />
            <p v-if="emailProblem('guardianEmail')" class="admin-users-form__field-error" role="alert">
              {{ emailProblem('guardianEmail') }}
            </p>
            <EmailCheckNote
              :state="emailNote('guardianEmail')"
            />
          </div>
          <!-- Ticked when given: ticking records it, unticking records a withdrawal. -->
          <div class="form-field form-field--full admin-users-form__consents" data-test="form-consent">
            <label class="admin-users-form__check">
              <input id="f-consent-given" v-model="form.consentGiven" type="checkbox" />
              Consent to take part
            </label>
            <label class="admin-users-form__check" :class="{ 'is-disabled': !form.consentGiven }">
              <input id="f-media-given" v-model="form.mediaGiven" type="checkbox" :disabled="!form.consentGiven" />
              Media consent
            </label>
            <label v-if="pendingGuardian" class="admin-users-form__check">
              <input id="f-pending-consent" v-model="form.pendingConsentGiven" type="checkbox" />
              {{ pendingGuardian.firstName }} {{ pendingGuardian.lastName }} (new guardian) has given consent
            </label>
          </div>
          <p v-if="consentUnverified" class="admin-users-form__note form-field--full">
            This student is marked as consented, but no signed consent form is on record.
          </p>
        </div>
      </template>

      <template v-if="form.role === 'mentor'">
        <!-- When they're free each week: a day and its times, as many as they like. -->
        <div class="admin-users-form__section">Weekly Availability</div>
        <div
          v-for="(slot, index) in form.mentorAvailability"
          :key="index"
          class="admin-users-form__slot"
          :data-test="`form-mentor-slot-${index}`"
        >
          <AppSelect
            v-model="slot.weekday"
            class="form-input admin-users-form__day"
            :aria-label="`Day ${index + 1}`"
            :options="WEEKDAY_OPTIONS"
            placeholder="Day"
          />
          <AppTimePicker
            v-model="slot.start"
            class="form-input admin-users-form__time"
            :aria-label="`From, time ${index + 1}`"
          />
          <span class="admin-users-form__muted">to</span>
          <AppTimePicker
            v-model="slot.end"
            class="form-input admin-users-form__time"
            :aria-label="`To, time ${index + 1}`"
          />
          <button
            type="button"
            class="admin-users-form__slot-remove"
            :aria-label="`Remove time ${index + 1}`"
            @click="form.mentorAvailability.splice(index, 1)"
          >
            <i class="fas fa-xmark" aria-hidden="true"></i>
          </button>
        </div>
        <p v-if="!form.mentorAvailability.length" class="admin-users-form__hint">No weekly times.</p>
        <button
          v-if="form.mentorAvailability.length < MAX_SLOTS"
          type="button"
          class="btn btn-outline btn-sm admin-users-form__slot-add"
          data-test="form-mentor-add-slot"
          @click="form.mentorAvailability.push(blankSlot())"
        >
          Add a time
        </button>

        <!-- The question registering asks, 150 words at most. -->
        <div class="admin-users-form__section">Application Form</div>
        <div
          v-for="question in APPLICATION_QUESTIONS"
          :key="question.key"
          class="form-field admin-users-form__answer"
        >
          <label class="form-label" :for="`f-${question.key}`">{{ question.label }}</label>
          <textarea
            :id="`f-${question.key}`"
            v-model="form[question.key]"
            v-auto-grow
            class="form-input admin-users-form__textarea"
            rows="5"
          ></textarea>
          <span
            class="admin-users-form__words"
            :class="{ 'is-over': wordCount(form[question.key]) > MAX_ANSWER_WORDS }"
          >
            {{ wordCount(form[question.key]) }}/{{ MAX_ANSWER_WORDS }} words
          </span>
        </div>
      </template>

      <!-- Their photo, last: uploaded once they're added. -->
      <template v-if="!isEditing">
        <div class="admin-users-form__section">Profile Photo</div>
        <div class="admin-users-form__photo">
          <img v-if="photoPreview" class="admin-users-form__photo-img" :src="photoPreview" alt="Profile photo" />
          <label class="btn btn-outline btn-sm">
            Choose photo
            <input
              type="file"
              class="sr-only"
              :accept="PROFILE_PHOTO_ACCEPT"
              data-test="form-photo-input"
              @change="choosePhoto"
            />
          </label>
          <button
            v-if="photoPreview"
            type="button"
            class="btn btn-outline btn-sm"
            data-test="form-photo-remove"
            @click="clearPhoto"
          >
            Remove
          </button>
        </div>
        <p class="admin-users-form__hint">PNG, JPEG or WebP, smaller than 5 MB.</p>
      </template>

      <div class="admin-users-form__footer">
        <!-- What stopped saving: under the line, just above the buttons. -->
        <p v-if="formError" class="admin-users-form__error admin-users-form__error--save" role="alert">
          {{ formError }}
        </p>
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
import AppSelect, { type AppSelectOption } from '@/components/AppSelect.vue'
import AppTimePicker from '@/components/AppTimePicker.vue'
import type { AdminGroupDetail, AdminUser, AdminUserCountry, AdminUserState, CreateUserPayload } from '@/utils/adminAPI'
import EmailCheckNote from '@/components/registration/EmailCheckNote.vue'
import type { EmailBoxState } from '@/registration/emailFieldCheck'
import {
  checkAdminUserEmails,
  confirmStudentAssignments,
  createAdminUser,
  fetchAdminGroupList,
  setAdminUserActive,
  updateAdminUser,
  uploadAdminUserPhoto
} from '@/utils/adminAPI'
import { apiErrorFromUnknown, logApiError } from '@/utils/apiError'
import { DEFAULT_GROUP_MAX_SIZE, studentCount } from '@/utils/groupCapacity'
import { PROFILE_PHOTO_ACCEPT, PROFILE_PHOTO_PROBLEM, isProfilePhoto } from '@/utils/profilePhoto'
import {
  APPLICATION_QUESTIONS,
  MAX_ANSWER_WORDS,
  MAX_SLOTS,
  MENTOR_BACKGROUNDS,
  STUDY_YEAR_OPTIONS,
  WEEKDAY_OPTIONS,
  availabilityTimes,
  blankSlot,
  capacityLabel,
  isStudyingBackground,
  mentorBackgroundCode,
  draftSlot,
  vAutoGrow,
  wordCount,
  type MentorSlot
} from '@/utils/mentorForm'
import { PRONOUN_PLACEHOLDER, PRONOUN_SELECT_OPTIONS, pronounDraft, pronounsToSave } from '@/utils/pronouns'
import { isPlaceholderGuardian } from '@/utils/guardian'
import { formatFullDate, roleLabel, userName } from '@/utils/userFormat'
import { INTEREST_OPTIONS, USER_ROLES, type UserRole } from '@/utils/userOptions'

interface UserForm {
  firstName: string
  lastName: string
  email: string
  role: UserRole
  countryId?: number
  stateId?: number
  /** Typed, for a country with no list of states. */
  stateName: string
  schoolName: string
  yearLevel?: number
  interests: string[]
  supervisorEmail: string
  supervisorSchoolName: string
  mentorBackground: AppSelectOption['value']
  mentorInstitution: string
  mentorCompany: string
  mentorUniversityYear: AppSelectOption['value']
  mentorFieldOfStudy: string
  mentorMaxGroupCount?: number
  mentorAvailability: MentorSlot[]
  mentorReason: string
  guardianFirstName: string
  guardianLastName: string
  guardianEmail: string
  /** Ticked when given: ticking records consent, unticking a withdrawal. */
  consentGiven: boolean
  mediaGiven: boolean
  pendingConsentGiven: boolean
  active: boolean
  /** The group a new student joins once added; null for none. */
  groupId: number | null
  /** A student's pronouns, as registering takes them. */
  pronounsChoice: AppSelectOption['value']
  pronounsOther: string
}

type GuardianFields = Pick<UserForm, 'guardianFirstName' | 'guardianLastName' | 'guardianEmail'>

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
  stateName: '',
  schoolName: '',
  yearLevel: undefined,
  interests: [],
  supervisorEmail: '',
  supervisorSchoolName: '',
  mentorBackground: null,
  mentorInstitution: '',
  mentorCompany: '',
  mentorUniversityYear: null,
  mentorFieldOfStudy: '',
  mentorMaxGroupCount: undefined,
  mentorAvailability: [],
  mentorReason: '',
  guardianFirstName: '',
  guardianLastName: '',
  guardianEmail: '',
  consentGiven: false,
  mediaGiven: false,
  pendingConsentGiven: false,
  active: true,
  groupId: null,
  pronounsChoice: '',
  pronounsOther: ''
})

const blankGuardian = (): GuardianFields => ({
  guardianFirstName: '',
  guardianLastName: '',
  guardianEmail: ''
})

const form = reactive<UserForm>(defaultForm())
const formError = ref('')
const saving = ref(false)
const editingOriginalActive = ref(false)
// What the guardian fields held when the form opened; only changes are sent,
// so saving a student's year level can't discard a pending guardian change
// or revoke consent.
const originalGuardian = ref<GuardianFields>(blankGuardian())

const pendingGuardian = computed(() => (form.role === 'student' ? props.user?.pendingGuardian ?? null : null))
// What's on record, so only the tick boxes that changed are sent.
const consentWas = computed(() => Boolean(isEditing.value && props.user?.joinPermissionReceived))
const mediaWas = computed(() => consentWas.value && props.user?.mediaConsent === true)
// Media consent goes with consent to take part.
watch(
  () => form.consentGiven,
  (given) => {
    if (!given) form.mediaGiven = false
  }
)
const consentUnverified = computed(() =>
  Boolean(props.user?.role === 'student' && props.user.joinPermissionReceived && !props.user.joinpermResponseId)
)
// Who last changed this user, from anywhere: an admin, the user or their supervisor.
const lastEditedLabel = computed(() => {
  const { lastEditedBy, lastEditedAt } = props.user ?? {}
  return lastEditedBy && lastEditedAt ? `Last edited by ${lastEditedBy} · ${formatFullDate(lastEditedAt)}` : ''
})

const formStates = computed(() => {
  if (!form.countryId) return []
  const country = props.countries.find((item) => item.id === form.countryId)
  if (!country) return []
  return props.states.filter((state) => state.countryName === country.countryName)
})

const onFormCountryChange = () => {
  form.stateId = undefined
  form.stateName = ''
}

// In Australia a state is needed, as registering asks, so no None.
const inAustralia = computed(
  () => props.countries.find((item) => item.id === form.countryId)?.countryName === 'Australia'
)

const ROLE_OPTIONS: AppSelectOption[] = USER_ROLES.map((role) => ({ value: role, label: roleLabel(role) }))
const YEAR_OPTIONS: AppSelectOption[] = [9, 10, 11, 12].map((year) => ({ value: year, label: String(year) }))
// Active users show in the list straight away.
const STATUS_OPTIONS: AppSelectOption[] = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' }
]

// No country or state is null here, undefined on the form.
const countryOptions = computed<AppSelectOption[]>(() => [
  { value: null, label: 'Unassigned' },
  ...props.countries.map((country) => ({ value: country.id, label: country.countryName }))
])

// Nothing until a country is picked, so its box says to pick one first.
const stateOptions = computed<AppSelectOption[]>(() => form.countryId === undefined ? [] : [
  ...(inAustralia.value ? [] : [{ value: null, label: 'None' }]),
  ...formStates.value.map((state) => ({ value: state.id, label: state.stateName }))
])

// Editing a support agent and picking another role. Case-folded like the
// backend's role_moved check: a stored "Support" re-saved as "support" is not
// a move and revokes nothing, so it must not be warned about either.
//
// Admin is not a loss. The save does delete their SupportScope row, but it
// creates an AdminScope row in the same call, and is_support() is true for
// every admin (backend apps/tickets/permissions.py), so the person keeps the
// queue. Saying otherwise would warn an admin off a promotion that takes
// nothing away.
const losesSupportAccess = computed(() => {
  if (!isEditing.value) return false
  const stored = (props.user?.role ?? '').trim().toLowerCase()
  const next = form.role.trim().toLowerCase()
  return stored === 'support' && next !== 'support' && next !== 'admin'
})

const onInterestToggle = (option: string, event: Event) => {
  const checked = (event.target as HTMLInputElement).checked
  const next = new Set(form.interests)
  if (checked) next.add(option)
  else next.delete(option)
  form.interests = [...next]
}

// The email boxes, checked as each is left (user/email-check/, as the
// registration page's are): a hard problem is refused at saving too; a
// warning (a mailbox that doesn't exist, a likely typo, a guardian address
// with an account) is only shown under the box, and saving goes ahead. A
// student's School too: a university is a warning.
type EmailField = 'email' | 'guardianEmail' | 'schoolName'
interface EmailCheckState {
  email: string
  status: 'checking' | 'ok' | 'hard' | 'soft'
  message: string
}
const emailCheckStates = reactive<Partial<Record<EmailField, EmailCheckState>>>({})
const pendingEmailChecks = new Set<Promise<void>>()
// The state for the address there now, if it's been checked.
const emailCheckFor = (field: EmailField) => {
  const state = emailCheckStates[field]
  return state && state.email === form[field].trim().toLowerCase() ? state : undefined
}
const emailProblem = (field: EmailField) => {
  const state = emailCheckFor(field)
  return state?.status === 'hard' ? state.message : ''
}
// As the registration page's note shows it: checking, or a warning.
const emailNote = (field: EmailField): EmailBoxState | undefined => {
  const state = emailCheckFor(field)
  return state && (state.status === 'checking' || state.status === 'soft')
    ? { email: state.email, status: state.status, message: state.message }
    : undefined
}
const checkEmailBox = (field: EmailField) => {
  const email = form[field].trim().toLowerCase()
  // Unchanged on an edit, or not a student's guardian or school: nothing to check.
  const saved = field === 'email' ? props.user?.email : field === 'schoolName' ? props.user?.schoolName : undefined
  const own = field !== 'guardianEmail' && isEditing.value && email === (saved || '').trim().toLowerCase()
  if (!email || own || (field !== 'email' && form.role !== 'student')) {
    delete emailCheckStates[field]
    return
  }
  if (emailCheckFor(field)) return
  emailCheckStates[field] = { email, status: 'checking', message: '' }
  const job = checkAdminUserEmails([
    field === 'email'
      ? { field, kind: 'account', email, firstName: form.firstName, lastName: form.lastName, userId: props.user?.id }
      : field === 'schoolName'
        ? { field, kind: 'school', email: '', school: form.schoolName }
        : { field, kind: 'guardian', email, accountEmail: form.email },
  ])
    .then((results) => {
      if (emailCheckStates[field]?.email !== email) return
      const result = results[field]
      if (!result) delete emailCheckStates[field]
      else if (result.ok) emailCheckStates[field] = { email, status: 'ok', message: '' }
      else if (result.severity === 'hard')
        emailCheckStates[field] = { email, status: 'hard', message: result.message }
      else
        emailCheckStates[field] = {
          email, status: 'soft', message: result.warnings.map((warning) => warning.message).join(' '),
        }
    })
    // A check that can't be done says nothing: saving still refuses what's wrong.
    .catch(() => {
      if (emailCheckStates[field]?.email === email) delete emailCheckStates[field]
    })
    .finally(() => pendingEmailChecks.delete(job))
  pendingEmailChecks.add(job)
}
// Before saving: the checks under way done (clicking Save leaves a box, which
// starts its check), then none refused. A warning doesn't stop it. Saving
// refuses what's wrong in any case.
const emailChecksBlockSaving = async () => {
  await Promise.allSettled([...pendingEmailChecks])
  for (const field of ['email', 'guardianEmail', 'schoolName'] as const) {
    const state = emailCheckFor(field)
    if (state?.status === 'hard') return state.message
  }
  return ''
}

const initForm = (editingUser: AdminUser | null) => {
  formError.value = ''
  delete emailCheckStates.email
  delete emailCheckStates.guardianEmail
  delete emailCheckStates.schoolName
  createdUserId.value = null
  clearPhoto()
  if (!editingUser) {
    Object.assign(form, defaultForm())
    editingOriginalActive.value = false
    originalGuardian.value = blankGuardian()
    return
  }
  editingOriginalActive.value = Boolean(editingUser.isActive)
  const isStudent = editingUser.role === 'student'
  const placeholder = isPlaceholderGuardian(
    editingUser.guardianFirstName, editingUser.guardianLastName, editingUser.firstName, editingUser.lastName
  )
  originalGuardian.value = {
    guardianFirstName: isStudent && !placeholder ? editingUser.guardianFirstName || '' : '',
    guardianLastName: isStudent && !placeholder ? editingUser.guardianLastName || '' : '',
    guardianEmail: isStudent ? editingUser.guardianEmail || '' : ''
  }
  Object.assign(form, {
    firstName: editingUser.firstName || '',
    lastName: editingUser.lastName || '',
    email: editingUser.email || '',
    role: (editingUser.role as UserRole) || props.fixedRole || 'student',
    countryId: editingUser.country?.id,
    stateId: editingUser.state?.id,
    stateName: editingUser.state?.stateName || '',
    schoolName: editingUser.role === 'student' ? editingUser.schoolName || '' : '',
    yearLevel: editingUser.role === 'student' ? (editingUser.yearLevel ?? undefined) : undefined,
    interests: (editingUser.interests || []).filter((interest) => INTEREST_OPTIONS.includes(interest)),
    supervisorEmail: editingUser.role === 'student' ? (editingUser.supervisorEmail || '') : '',
    // Their own words, not a listed choice, come back under Other.
    pronounsChoice: pronounDraft(editingUser.pronouns).choice,
    pronounsOther: pronounDraft(editingUser.pronouns).other,
    supervisorSchoolName: editingUser.role === 'supervisor' ? editingUser.schoolName || '' : '',
    ...(editingUser.role === 'mentor'
      ? {
          mentorBackground: mentorBackgroundCode(editingUser.mentorBackground),
          mentorInstitution: editingUser.mentorInstitution || '',
          mentorCompany: editingUser.mentorCompany || '',
          mentorUniversityYear: editingUser.mentorUniversityYear || null,
          mentorFieldOfStudy: editingUser.mentorFieldOfStudy || '',
          mentorMaxGroupCount: editingUser.mentorMaxGroupCount ?? undefined,
          mentorAvailability: (editingUser.mentorAvailability || []).map(draftSlot),
          mentorReason: editingUser.mentorReason || ''
        }
      : {}),
    ...originalGuardian.value,
    consentGiven: isStudent && Boolean(editingUser.joinPermissionReceived),
    mediaGiven: isStudent && Boolean(editingUser.joinPermissionReceived) && editingUser.mediaConsent === true,
    pendingConsentGiven: false,
    active: editingUser.isActive
  })
}

watch(
  () => props.modelValue,
  (opening) => {
    if (opening) initForm(props.user ?? null)
  }
)

// --- Supervisor and Group ------------------------------------------------------

// By name, with the email underneath; none first, as it's optional. The one
// they have stays a choice even when it isn't in the list.
const supervisorOptions = computed<AppSelectOption[]>(() => {
  const options = props.supervisors
    .flatMap((supervisor) => {
      const email = supervisor.email
      return email ? [{ value: email.toLowerCase(), label: userName(supervisor) || email, detail: email }] : []
    })
    .sort((a, b) => a.label.localeCompare(b.label))
  const current = form.supervisorEmail.toLowerCase()
  if (current && !options.some((option) => option.value === current)) {
    options.unshift({ value: current, label: current, detail: current })
  }
  return [{ value: '', label: 'No supervisor', detail: '' }, ...options]
})

const groupList = ref<AdminGroupDetail[]>([])
const groupsLoading = ref(false)
const groupsError = ref('')

// Every group, fresh each time a student is being added, so the seats are current.
const loadGroups = async () => {
  groupsLoading.value = true
  groupsError.value = ''
  try {
    const groups: AdminGroupDetail[] = []
    for (let page = 1; page <= 20; page += 1) {
      const data = await fetchAdminGroupList({ page, limit: 200 })
      // The list gives each id as text.
      groups.push(...data.items.map((group) => ({ ...group, id: Number(group.id) })))
      if (!data.has_more) break
    }
    groupList.value = groups
  } catch (error) {
    groupsError.value = apiErrorFromUnknown(error, 'Could not load the groups.').message
  } finally {
    groupsLoading.value = false
  }
}

watch(
  () => [props.modelValue, form.role] as const,
  ([opening, role]) => {
    if (opening && role === 'student' && !isEditing.value) void loadGroups()
  }
)

// "No group" first, then each group with its seats taken; a full one can't
// be picked.
const groupOptions = computed<AppSelectOption[]>(() => [
  { value: null, label: 'No group', detail: 'Not in a group' },
  ...[...groupList.value]
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))
    .map((group) => {
      const taken = studentCount(group)
      const full = taken >= DEFAULT_GROUP_MAX_SIZE
      return {
        value: group.id,
        label: group.name,
        detail: `${taken}/${DEFAULT_GROUP_MAX_SIZE} students${full ? ' · Full' : ''}`,
        disabled: full
      }
    })
])

// --- Profile Photo ---------------------------------------------------------------

const photoFile = ref<File | null>(null)
const photoPreview = ref('')

function clearPhoto() {
  if (photoPreview.value) URL.revokeObjectURL(photoPreview.value)
  photoFile.value = null
  photoPreview.value = ''
}

const choosePhoto = (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  // So choosing the same file again still counts.
  input.value = ''
  if (!file) return
  if (!isProfilePhoto(file)) {
    formError.value = PROFILE_PHOTO_PROBLEM
    return
  }
  clearPhoto()
  formError.value = ''
  photoFile.value = file
  photoPreview.value = URL.createObjectURL(file)
}

// --- A mentor's details, weekly times and application ------------------------

const mentorStudying = computed(() => isStudyingBackground(form.mentorBackground))
// Registering's backgrounds, and one typed before that, as written.
const mentorBackgroundOptions = computed<AppSelectOption[]>(() => {
  const current = form.mentorBackground
  return typeof current === 'string' && current && !MENTOR_BACKGROUNDS.some((option) => option.value === current)
    ? [...MENTOR_BACKGROUNDS, { value: current, label: current }]
    : MENTOR_BACKGROUNDS
})
// 1 to 5 groups as registering offers, and whatever they have now.
const capacityOptions = computed<AppSelectOption[]>(() => {
  const counts = new Set([1, 2, 3, 4, 5])
  if (form.mentorMaxGroupCount !== undefined) counts.add(form.mentorMaxGroupCount)
  return [...counts].sort((a, b) => a - b).map((count) => ({ value: count, label: capacityLabel(count) }))
})

// What's given wrong: anything may be left out, to be filled in later.
const mentorProblem = (): string => {
  const times = availabilityTimes(form.mentorAvailability)
  if (typeof times === 'string') return times
  if (APPLICATION_QUESTIONS.some((question) => wordCount(form[question.key]) > MAX_ANSWER_WORDS)) {
    return `Keep the answer to ${MAX_ANSWER_WORDS} words or fewer.`
  }
  return ''
}

// What their background doesn't ask for is cleared, as registering does.
const mentorPayload = (): Record<string, unknown> => {
  const industry = form.mentorBackground === 'industry'
  const times = availabilityTimes(form.mentorAvailability)
  return {
    mentorBackground: form.mentorBackground,
    mentorCompany: industry ? form.mentorCompany : '',
    mentorInstitution: industry ? '' : form.mentorInstitution,
    mentorUniversityYear: mentorStudying.value ? form.mentorUniversityYear : '',
    mentorFieldOfStudy: industry ? '' : form.mentorFieldOfStudy,
    mentorMaxGroupCount: form.mentorMaxGroupCount,
    mentorAvailability: typeof times === 'string' ? [] : times,
    mentorReason: form.mentorReason.trim()
  }
}

// A user added whose group or photo didn't take: Create then only retries those.
const createdUserId = ref<number | null>(null)

const finishNewUser = async (userId: number) => {
  createdUserId.value = userId
  if (form.role === 'student' && form.groupId !== null) {
    try {
      await confirmStudentAssignments([{ studentId: userId, groupId: form.groupId }])
    } catch (error) {
      throw new Error(
        `They were added, but not to the group: ${apiErrorFromUnknown(error, 'it could not be joined.').message}`
      )
    }
  }
  if (photoFile.value) {
    try {
      await uploadAdminUserPhoto(userId, photoFile.value)
    } catch (error) {
      throw new Error(
        `They were added, but their photo wasn't saved: ${apiErrorFromUnknown(error, 'it could not be uploaded.').message}`
      )
    }
  }
}

const onCancel = () => {
  open.value = false
}

const isValidEmail = (email: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)

// The pronouns to save: null when Other is chosen with nothing typed.
const chosenPronouns = () =>
  pronounsToSave({ choice: String(form.pronounsChoice ?? ''), other: form.pronounsOther })

const validateForm = (): boolean => {
  const role = form.role
  // Only an email and a role are needed: the rest may come later. What's
  // given wrong is still refused.
  if (!form.email.trim()) {
    formError.value = 'Email is required.'
    return false
  }
  if (!isValidEmail(form.email.trim())) {
    formError.value = 'Invalid email format.'
    return false
  }
  if (role === 'student') {
    // Consent needs a guardian on file: one named, or the student's own name
    // standing in until they are.
    const guardianNamed = Boolean(form.guardianFirstName && form.guardianLastName)
    const studentNamed = Boolean(form.firstName.trim() && form.lastName.trim())
    if (form.consentGiven && !isEditing.value && !guardianNamed && !studentNamed) {
      formError.value = "Enter the guardian's name to record their consent."
      return false
    }
    if (guardianNamesChanged() && (!form.guardianFirstName || !form.guardianLastName)) {
      formError.value = "Enter the guardian's first and last name."
      return false
    }
    if (form.guardianEmail && !isValidEmail(form.guardianEmail)) {
      formError.value = 'Guardian email is not a valid email address.'
      return false
    }
    if (form.guardianEmail && form.guardianEmail.toLowerCase() === form.email.trim().toLowerCase()) {
      formError.value = "Guardian email can't be the student's own email."
      return false
    }
  }
  if (role === 'mentor') {
    const problem = mentorProblem()
    if (problem) {
      formError.value = problem
      return false
    }
  }
  if (form.pronounsChoice === 'Other' && chosenPronouns() === null) {
    formError.value = 'Enter their pronouns.'
    return false
  }
  return true
}

const guardianNamesChanged = () =>
  form.guardianFirstName !== originalGuardian.value.guardianFirstName ||
  form.guardianLastName !== originalGuardian.value.guardianLastName

const guardianPayload = (): Record<string, unknown> => {
  const payload: Record<string, unknown> = {}
  if (guardianNamesChanged()) {
    payload.guardianFirstName = form.guardianFirstName
    payload.guardianLastName = form.guardianLastName
  }
  if (form.guardianEmail !== originalGuardian.value.guardianEmail) {
    payload.guardianEmail = form.guardianEmail
  }
  // Ticking records consent with the media box; unticking records a withdrawal.
  if (pendingGuardian.value && form.pendingConsentGiven) {
    payload.consentGiven = true
    payload.mediaConsent = form.mediaGiven
  } else if (form.consentGiven !== consentWas.value) {
    payload.consentGiven = form.consentGiven
    if (form.consentGiven) payload.mediaConsent = form.mediaGiven
  } else if (form.consentGiven && form.mediaGiven !== mediaWas.value) {
    payload.mediaConsent = form.mediaGiven
  }
  return payload
}

const submitForm = async () => {
  formError.value = ''
  if (!validateForm()) return
  const emailBlock = await emailChecksBlockSaving()
  if (emailBlock) {
    formError.value = emailBlock
    return
  }

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
      // A typed state, for a country with no list of states.
      if (role !== 'admin' && form.countryId !== undefined && !formStates.value.length) {
        delete payload.stateId
        payload.stateName = form.stateName
      }
      if (!props.isSupervisorMode && form.email.trim().toLowerCase() !== (props.user.email || '').trim().toLowerCase()) {
        payload.email = form.email.trim().toLowerCase()
      }
      if (role === 'student') {
        payload.schoolName = form.schoolName
        payload.yearLevel = form.yearLevel
        payload.interests = form.interests
        payload.supervisorEmail = form.supervisorEmail || undefined
        Object.assign(payload, guardianPayload())
      } else if (role === 'supervisor') {
        payload.supervisorSchoolName = form.supervisorSchoolName || null
      } else if (role === 'mentor') {
        Object.assign(payload, mentorPayload())
        payload.interests = form.interests
      }
      payload.pronouns = chosenPronouns()

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
      const stateName =
        role === 'admin'
          ? undefined
          : formStates.value.length
            ? resolveStateName(form.stateId)
            : form.stateName || undefined
      if (countryName) payload.country = countryName
      if (stateName) payload.state = stateName

      if (role === 'student') {
        payload.schoolName = form.schoolName
        payload.yearLevel = form.yearLevel
        payload.supervisorEmail = form.supervisorEmail || undefined
        payload.interests = form.interests
        Object.assign(payload, guardianPayload())
      } else if (role === 'supervisor') {
        payload.supervisorSchoolName = form.supervisorSchoolName || null
      } else if (role === 'mentor') {
        Object.assign(payload, mentorPayload())
        payload.interests = form.interests
      }
      payload.pronouns = chosenPronouns()

      if (createdUserId.value !== null) {
        await finishNewUser(createdUserId.value)
      } else {
        const created = await createAdminUser(payload as CreateUserPayload)
        if (created.data) await finishNewUser(created.data.id)
      }
    }
    open.value = false
    emit('saved')
  } catch (submitError) {
    logApiError('admin.users.save', submitError)
    formError.value =
      submitError instanceof Error ? submitError.message : 'Unable to save the user right now.'
    // Added, though not to their group or without their photo: the list
    // shows them meanwhile.
    if (createdUserId.value !== null) emit('saved')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
/* Two equal columns, whatever a box holds: a long placeholder ("Choose a
   country first") mustn't widen its own. */
.admin-users-form__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
}

.admin-users-form__grid > .form-field {
  min-width: 0;
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

/* In a box, in two columns, as registering and the student dashboard
   show them. */
.admin-users-form__interests {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 30px 16px;
  margin: 0;
  padding: 0.6rem 1rem 1.1rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
}

/* A weekly time: day, from, to, and its ×, as the mentor panel's. */
.admin-users-form__slot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
}

.form-input.admin-users-form__day {
  flex: 1 1 7rem;
  min-width: 7rem;
  width: auto;
}

/* A time (AppTimePicker): as wide as it needs. */
.form-input.admin-users-form__time {
  flex: none;
  width: auto;
  min-width: 0;
}

.admin-users-form__muted {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.admin-users-form__slot-remove {
  padding: 0.25rem 0.4rem;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}

.admin-users-form__slot-add {
  margin: 0.2rem 0 0;
}

.admin-users-form__answer + .admin-users-form__answer {
  margin-top: 0.9rem;
}

/* It grows with what's written rather than scrolling. */
.admin-users-form__textarea {
  resize: vertical;
  min-height: 6rem;
}

.admin-users-form__words {
  align-self: flex-end;
  margin-top: 0.25rem;
  color: var(--text-muted);
  font-size: 0.8rem;
}

.admin-users-form__words.is-over {
  color: var(--danger);
}

/* Its heading on the box's line, in the form's label style. */
.admin-users-form__interests legend {
  padding: 0 6px;
  color: var(--teal);
  font-size: 0.85rem;
  font-weight: 700;
}

/* The photo as the user's dashboard shows it: round, filling its circle. */
.admin-users-form__photo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.admin-users-form__photo-img {
  width: 104px;
  height: 104px;
  border-radius: 50%;
  object-fit: cover;
  object-position: center;
  border: 1px solid var(--border-light);
}

/* Choose photo is a label (for its file box), which would take the page's
   taller line; both buttons take the button's, so they match. */
.admin-users-form__photo .btn {
  margin: 0;
  font-family: inherit;
  line-height: normal;
  cursor: pointer;
}

.admin-users-form__interest {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 0 12px 0 2px;
  font-size: 0.9rem;
  line-height: 1.35;
  color: var(--teal);
  cursor: pointer;
}

/* Centred on the first line of its text, at any text size. */
.admin-users-form__interest input {
  flex: 0 0 auto;
  width: 1.0625rem;
  height: 1.0625rem;
  margin: calc((0.9rem * 1.35 - 1.0625rem) / 2) 0 0;
  accent-color: var(--dark-green);
  cursor: pointer;
}

.admin-users-form__note {
  margin: 0 0 0.6rem;
  padding: 0.6rem 0.8rem;
  border-left: 4px solid var(--warning);
  border-radius: 6px;
  background-color: var(--bg-light);
  color: var(--teal);
  font-size: 0.85rem;
}

/* An email box's check: what saving refuses, under it. */
.admin-users-form__field-error {
  margin: 0.35rem 0 0;
  color: var(--danger);
  font-size: 0.85rem;
}

.admin-users-form__hint {
  margin-top: 0.35rem;
  color: var(--text-muted);
  font-size: 0.85rem;
}

/* Consent to take part and media consent side by side, with large tick
   boxes; a pending guardian's goes on the next line when there's no room. */
.admin-users-form__consents {
  display: flex;
  flex-flow: row wrap;
  align-items: center;
  gap: 0.6rem 2rem;
}

/* The form's usual label text, its larger tick box just after it. */
.admin-users-form__check {
  display: inline-flex;
  flex-direction: row-reverse;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--teal);
  cursor: pointer;
}

.admin-users-form__check input {
  width: 1.25rem;
  height: 1.25rem;
  margin: 0;
  accent-color: var(--dark-green);
  cursor: pointer;
}

.admin-users-form__check.is-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.admin-users-form__check.is-disabled input {
  cursor: not-allowed;
}

.form-field--full {
  grid-column: 1 / -1;
}

/* Text in --teal on the sheet's own --white, both theme tokens that are
   defined as a pair in light and dark (11:1 and 14:1). No tinted background:
   a translucent one would hand the contrast to whatever paints underneath. */
.admin-users-form__note {
  margin: 0;
  padding: 0.55rem 0.8rem;
  border-left: 4px solid var(--warning);
  border-radius: 6px;
  color: var(--teal);
  font-size: 0.85rem;
}

/* The support-role note keeps the pale ground the guardian and consent notes
   brought (the first .admin-users-form__note rule) and loses the bar down its
   left: the client called that side bar an "AI UI" look at the 2026-10-22
   meeting (C-25), and the designer had every one on the support pages go.
   Those two notes are another team's and keep theirs. After both rules, which
   it ties with. */
.admin-users-form__note--support {
  border-left: 0;
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
  background-color: var(--white);
}

/* The weekly times and the application's answers keep their own box; the
   rest are the shared one (app-input). */
.admin-users-form__day,
.admin-users-form__time,
.admin-users-form__textarea {
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  color: var(--teal);
  font: inherit;
}

.form-input:disabled,
.app-select.form-input.is-disabled {
  background-color: var(--bg-light);
  color: var(--text-muted);
  cursor: not-allowed;
}

/* Drawn as the disabled inputs, without the dropdown's own fading. */
.app-select.form-input.is-disabled {
  opacity: 1;
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

/* A row of its own, the buttons under it. */
.admin-users-form__error--save {
  flex: 0 0 100%;
  margin: 0 0 0.4rem;
}

.admin-users-form__footer {
  display: flex;
  flex-wrap: wrap;
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
  .admin-users-form__grid,
  .admin-users-form__interests {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
