<template>
  <div class="admin-users-detail">
    <section v-if="user" class="admin-users-detail__section" data-test="admin-account">
      <div class="admin-users-detail__heading">
        <h3>Account</h3>
        <button
          v-if="user.role === 'student' && editable && editing !== 'account'"
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-edit-account"
          @click="startEdit('account')"
        >
          Edit
        </button>
      </div>
      <p v-if="savedPart === 'account'" class="admin-users-detail__saved">Saved.</p>
      <!-- A student's email, country and state; the rest isn't edited here. -->
      <form v-if="editing === 'account'" data-test="admin-account-form" @submit.prevent="save">
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">Email</span>
          <input v-model.trim="form.email" class="admin-users-detail__input" type="email" required maxlength="254" />
        </label>
        <div class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-detail-country">Country</label>
          <AppSelect
            size="large"
            id="admin-detail-country"
            :model-value="form.countryId"
            class="admin-users-detail__input"
            data-test="admin-country-select"
            :options="countryOptions"
            :loading="placesLoading"
            placeholder="Search countries"
            empty-text="No country matches"
            @update:model-value="pickCountry"
          />
        </div>
        <!-- Australia's states to pick; elsewhere, typed. -->
        <label v-if="!inAustralia" class="admin-users-detail__item">
          <span class="admin-users-detail__label">State</span>
          <input
            v-model.trim="form.stateName"
            class="admin-users-detail__input"
            data-test="admin-state-text"
            maxlength="255"
            placeholder="State, province or region"
          />
        </label>
        <div v-else class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-detail-state">State</label>
          <AppSelect
            size="large"
            id="admin-detail-state"
            v-model="form.stateId"
            class="admin-users-detail__input"
            data-test="admin-state-select"
            :options="stateOptions"
            :loading="placesLoading"
            :searchable="false"
          />
        </div>
        <div class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-detail-status">Status</label>
          <AppSelect
            size="large"
            id="admin-detail-status"
            v-model="form.status"
            class="admin-users-detail__input"
            data-test="admin-status-select"
            :options="STATUS_OPTIONS"
            :searchable="false"
          />
        </div>
        <p v-if="placesError" class="admin-users-detail__save-error" role="alert">{{ placesError }}</p>
        <p v-if="saveError" class="admin-users-detail__save-error" role="alert">{{ saveError }}</p>
        <div class="admin-users-detail__actions">
          <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
      <dl v-else class="admin-users-detail__list">
        <div class="admin-users-detail__item">
          <dt>Email</dt>
          <dd>{{ user.email || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Role</dt>
          <dd><span class="admin-users__role-badge">{{ roleLabel(user.role) }}</span></dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Country</dt>
          <dd>{{ labelizeCountry(user.country) }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>State</dt>
          <dd>{{ labelizeState(user.state) }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Status</dt>
          <dd>
            <span class="admin-users__status-badge" :class="{ 'admin-users__status-badge--inactive': !user.isActive }">
              {{ user.isActive ? 'Active' : 'Inactive' }}
            </span>
          </dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Has logged in</dt>
          <dd>
            <span class="admin-users__logged-in-badge" :class="{ 'admin-users__logged-in-badge--yes': user.hasLoggedIn }">
              {{ user.hasLoggedIn ? 'Yes' : 'No' }}
            </span>
          </dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Last login</dt>
          <dd>{{ user.lastLogin ? formatFullDate(user.lastLogin) : 'Never' }}</dd>
        </div>
        <div class="admin-users-detail__item" data-test="admin-last-edited">
          <dt>Last edited</dt>
          <dd>
            {{
              user.lastEditedBy && user.lastEditedAt
                ? `${user.lastEditedBy} · ${formatFullDate(user.lastEditedAt)}`
                : 'No edits on record'
            }}
          </dd>
        </div>
      </dl>
    </section>

    <section v-if="user?.role === 'student'" class="admin-users-detail__section" data-test="admin-supervisor-group">
      <div class="admin-users-detail__heading">
        <h3>Supervisor and Group</h3>
        <button
          v-if="editable && editing !== 'supervisor'"
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-edit-supervisor"
          @click="startEdit('supervisor')"
        >
          Edit
        </button>
      </div>
      <p v-if="savedPart === 'supervisor'" class="admin-users-detail__saved">Saved.</p>
      <!-- Each picked from a list; replacing one they have asks first. -->
      <form v-if="editing === 'supervisor'" data-test="admin-supervisor-form" @submit.prevent="save">
        <div class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-detail-supervisor">Supervisor</label>
          <AppSelect
            size="large"
            id="admin-detail-supervisor"
            v-model="form.supervisorEmail"
            class="admin-users-detail__input"
            data-test="admin-supervisor-select"
            searchable
            :options="supervisorOptions"
            :loading="picksLoading"
            placeholder="Search by name or email"
            empty-text="No supervisor matches"
          />
        </div>
        <div class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-detail-group">Group</label>
          <AppSelect
            size="large"
            id="admin-detail-group"
            v-model="form.groupId"
            class="admin-users-detail__input"
            data-test="admin-group-select"
            searchable
            :options="groupOptions"
            :loading="picksLoading"
            placeholder="Search by group name"
            empty-text="No group matches"
          />
        </div>
        <p v-if="picksError" class="admin-users-detail__save-error" role="alert">{{ picksError }}</p>
        <p v-if="saveError" class="admin-users-detail__save-error" role="alert">{{ saveError }}</p>
        <div class="admin-users-detail__actions">
          <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
      <dl v-else class="admin-users-detail__list">
        <div class="admin-users-detail__item">
          <dt>Supervisor</dt>
          <dd>{{ supervisorLabel(user) }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Group</dt>
          <dd>{{ user.groupName || '—' }}</dd>
        </div>
      </dl>
    </section>

    <!-- A student's parts as their supervisor's panel shows them, each with
         its own Edit beside its heading; the admin's consent parts under
         Guardian Details. -->
    <section v-if="user?.role === 'student'" class="admin-users-detail__section" data-test="admin-student-details">
      <div class="admin-users-detail__heading">
        <h3>Student Details</h3>
        <button
          v-if="editable && editing !== 'details'"
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-edit-details"
          @click="startEdit('details')"
        >
          Edit
        </button>
      </div>
      <p v-if="savedPart === 'details'" class="admin-users-detail__saved">Saved.</p>
      <form v-if="editing === 'details'" data-test="admin-details-form" @submit.prevent="save">
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">First name</span>
          <input v-model.trim="form.firstName" class="admin-users-detail__input" required maxlength="255" />
        </label>
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">Last name</span>
          <input v-model.trim="form.lastName" class="admin-users-detail__input" required maxlength="255" />
        </label>
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">School</span>
          <input v-model.trim="form.schoolName" class="admin-users-detail__input" required maxlength="255" />
        </label>
        <div class="admin-users-detail__item">
          <label class="admin-users-detail__label" for="admin-detail-year">Year Level</label>
          <AppSelect
            size="large"
            id="admin-detail-year"
            v-model="form.yearLevel"
            class="admin-users-detail__input"
            data-test="admin-year-select"
            :options="YEAR_OPTIONS"
            :searchable="false"
            placeholder="Choose a year"
          />
        </div>
        <fieldset class="admin-users-detail__item admin-users-detail__options">
          <legend class="admin-users-detail__label">Interests</legend>
          <label v-for="interest in INTEREST_OPTIONS" :key="interest">
            <input v-model="form.interests" type="checkbox" :value="interest" />
            {{ interest }}
          </label>
        </fieldset>
        <p v-if="saveError" class="admin-users-detail__save-error" role="alert">{{ saveError }}</p>
        <div class="admin-users-detail__actions">
          <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
      <dl v-else class="admin-users-detail__list">
        <div class="admin-users-detail__item">
          <dt>Name</dt>
          <dd>{{ [user.firstName, user.lastName].filter(Boolean).join(' ') || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>School</dt>
          <dd>{{ user.schoolName || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Year Level</dt>
          <dd>{{ user.yearLevel ?? '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Interests</dt>
          <dd>{{ joinInterests(user.interests) }}</dd>
        </div>
      </dl>
    </section>

    <section v-if="user?.role === 'student'" class="admin-users-detail__section" data-test="admin-guardian">
      <div class="admin-users-detail__heading">
        <h3>Guardian Details</h3>
        <button
          v-if="editable && editing !== 'guardian'"
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-edit-guardian"
          @click="startEdit('guardian')"
        >
          Edit
        </button>
      </div>
      <p v-if="savedPart === 'guardian'" class="admin-users-detail__saved">Saved.</p>
      <form v-if="editing === 'guardian'" data-test="admin-guardian-form" @submit.prevent="save">
        <p v-if="user.pendingGuardian" class="admin-users-detail__note">
          The student asked to change their guardian to
          <strong>{{ user.pendingGuardian.firstName }} {{ user.pendingGuardian.lastName }}</strong>
          ({{ user.pendingGuardian.email || 'no email' }}). They become the guardian once they sign the consent
          form; changing the guardian here discards the request.
        </p>
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">First name</span>
          <input v-model.trim="form.guardianFirstName" class="admin-users-detail__input" />
        </label>
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">Last name</span>
          <input v-model.trim="form.guardianLastName" class="admin-users-detail__input" />
        </label>
        <label class="admin-users-detail__item">
          <span class="admin-users-detail__label">Email</span>
          <input v-model.trim="form.guardianEmail" class="admin-users-detail__input" type="email" />
        </label>
        <!-- Ticked when given: ticking records it, unticking records a withdrawal.
             Each on its own line, as the fields above: words left, box right. -->
        <label class="admin-users-detail__item admin-users-detail__check">
          <span class="admin-users-detail__label">Consent to take part</span>
          <input v-model="form.consentGiven" type="checkbox" data-test="admin-consent-given" />
        </label>
        <label class="admin-users-detail__item admin-users-detail__check" :class="{ 'is-disabled': !form.consentGiven }">
          <span class="admin-users-detail__label">Media consent</span>
          <input v-model="form.mediaGiven" type="checkbox" :disabled="!form.consentGiven" />
        </label>
        <label v-if="user.pendingGuardian" class="admin-users-detail__item admin-users-detail__check">
          <span class="admin-users-detail__label">
            {{ user.pendingGuardian.firstName }} {{ user.pendingGuardian.lastName }} (new guardian) has given consent
          </span>
          <input v-model="form.pendingConsentGiven" type="checkbox" />
        </label>
        <p v-if="saveError" class="admin-users-detail__save-error" role="alert">{{ saveError }}</p>
        <div class="admin-users-detail__actions">
          <button type="button" class="btn btn-outline btn-sm" :disabled="saving" @click="cancelEdit">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </form>
      <dl v-else class="admin-users-detail__list">
        <div class="admin-users-detail__item">
          <dt>Name</dt>
          <dd data-test="admin-guardian-name">{{ guardian.name || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Email</dt>
          <dd>{{ user.guardianEmail || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Permission</dt>
          <dd data-test="admin-consent">
            {{ permissionLabel
            }}<span v-if="guardian.consent === 'unverified'" class="admin-users-detail__flag"> (no signed form on record)</span>
          </dd>
        </div>
        <div class="admin-users-detail__item" data-test="admin-media-consent">
          <dt>Media Consent</dt>
          <dd>{{ mediaConsentLabel }}</dd>
        </div>
        <div v-if="user.pendingGuardian" class="admin-users-detail__item" data-test="admin-pending-guardian">
          <dt>Requested change</dt>
          <dd>
            {{ user.pendingGuardian.firstName }} {{ user.pendingGuardian.lastName }}
            ({{ user.pendingGuardian.email || 'no email' }}), waiting for their consent
          </dd>
        </div>
        <div v-if="user.consentRequestSentAt" class="admin-users-detail__item" data-test="admin-consent-request-sent">
          <dt>Consent requested</dt>
          <dd>{{ formatFullDate(user.consentRequestSentAt) }}</dd>
        </div>
      </dl>
      <div v-if="consentRequestTo" class="admin-users-detail__consent-request">
        <button
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-send-consent-request"
          :disabled="sendingRequest"
          @click="sendConsentRequest"
        >
          {{ sendingRequest ? 'Sending…' : user.consentRequestSentAt ? 'Resend consent request' : 'Send consent request' }}
        </button>
        <p
          v-if="requestMessage"
          class="admin-users-detail__consent-message"
          :class="{ 'admin-users-detail__consent-message--error': requestFailed }"
          role="status"
          data-test="admin-consent-request-message"
        >
          {{ requestMessage }}
        </p>
        <p v-else class="admin-users-detail__consent-hint">Emails the consent form to {{ consentRequestTo }}.</p>
      </div>

      <div v-if="user.joinPermissionReceived && signedOnPlatform" class="admin-users-detail__consent-actions">
        <button
          type="button"
          class="btn btn-outline btn-sm"
          data-test="admin-view-consent"
          :disabled="consentsLoading"
          @click="toggleConsents"
        >
          {{ consentsOpen ? 'Hide signed form' : 'View signed form' }}
        </button>
      </div>
      <p
        v-if="consentsMessage"
        class="admin-users-detail__consent-message"
        :class="{ 'admin-users-detail__consent-message--error': consentsFailed }"
        role="status"
        data-test="admin-consent-message"
      >
        {{ consentsMessage }}
      </p>

      <ul v-if="consentsOpen && consents.length" class="admin-users-detail__consents" data-test="admin-signed-consents">
        <li v-for="consent in consents" :key="consent.id" class="admin-users-detail__consent">
          <p class="admin-users-detail__consent-head">
            <strong>{{ consent.reference }}</strong>
            <span v-if="consent.withdrawnAt" class="admin-users-detail__flag">Withdrawn {{ formatFullDate(consent.withdrawnAt) }}</span>
          </p>
          <p>
            Signed by {{ consent.guardianFullName }} ({{ consent.guardianEmail }}) on
            {{ formatFullDate(consent.signedAt) }}, form version {{ consent.consentVersion }}.
          </p>
          <p>
            Media consent: {{ consent.mediaConsent ? 'Yes' : 'No' }}<template v-if="consent.mediaWithdrawnAt">, withdrawn {{ formatFullDate(consent.mediaWithdrawnAt) }}</template>
          </p>
          <img :src="consent.signature" :alt="`Signature of ${consent.guardianFullName}`" class="admin-users-detail__signature" />
          <button
            type="button"
            class="btn btn-outline btn-sm admin-users-detail__record"
            data-test="admin-download-record"
            :disabled="downloadingId === consent.id"
            @click="downloadRecord(consent)"
          >
            {{ downloadingId === consent.id ? 'Downloading…' : 'Download PDF' }}
          </button>
        </li>
      </ul>
    </section>

    <section v-if="user?.role === 'mentor'" class="admin-users-detail__section">
      <h3>Mentor Profile</h3>
      <dl class="admin-users-detail__list">
        <div class="admin-users-detail__item">
          <dt>Interests / Expertise</dt>
          <dd>{{ joinInterests(user.interests) }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Institution</dt>
          <dd>{{ user.mentorInstitution || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Background</dt>
          <dd>{{ user.mentorBackground || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Mentor reason</dt>
          <dd>{{ user.mentorReason || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Max groups</dt>
          <dd>{{ user.mentorMaxGroupCount ?? '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Group</dt>
          <dd>{{ user.groupName || '—' }}</dd>
        </div>
      </dl>
    </section>

    <section v-if="user?.role === 'supervisor'" class="admin-users-detail__section">
      <h3>Supervisor Profile</h3>
      <dl class="admin-users-detail__list">
        <div class="admin-users-detail__item">
          <dt>School</dt>
          <dd>{{ user.schoolName || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Group</dt>
          <dd>{{ user.groupName || '—' }}</dd>
        </div>
        <div class="admin-users-detail__item">
          <dt>Supervisees</dt>
          <dd class="admin-users-detail__supervisees">
            <span v-if="!user.supervisees?.length">—</span>
            <span v-else>{{ superviseesLabel(user) }}</span>
          </dd>
        </div>
      </dl>
    </section>

    <section v-if="user?.role === 'admin'" class="admin-users-detail__section">
      <h3>Admin Profile</h3>
      <dl class="admin-users-detail__list">
        <div class="admin-users-detail__item">
          <dt>Scope</dt>
          <dd>Admin</dd>
        </div>
      </dl>
    </section>

    <ConfirmDialog
      v-model="confirmOpen"
      title="Replace supervisor or group?"
      :message="`${userName(user)} already has one. Saving will:`"
      confirm-label="Save"
      busy-label="Saving…"
      variant="warning"
      :busy="saving"
      @confirm="commitSupervisorAndGroup"
    >
      <ul class="admin-users-detail__replacing" data-test="admin-replacing">
        <li v-for="line in replacing" :key="line">{{ line }}.</li>
      </ul>
    </ConfirmDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import AppSelect, { type AppSelectOption } from '@/components/AppSelect.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import {
  confirmStudentAssignments,
  downloadGuardianConsentRecord,
  fetchAdminCountries,
  fetchAdminGroupList,
  fetchAdminStates,
  fetchAdminUser,
  fetchAdminUsers,
  fetchGuardianConsents,
  removeGroupMember,
  sendGuardianConsentRequest,
  setAdminUserActive,
  updateAdminUser
} from '@/utils/adminAPI'
import type {
  AdminGroupDetail,
  AdminGuardianConsent,
  AdminUser,
  AdminUserCountry,
  AdminUserState
} from '@/utils/adminAPI'
import { DEFAULT_GROUP_MAX_SIZE, studentCount } from '@/utils/groupCapacity'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatShortDateTime } from '@/utils/date'
import { isPlaceholderGuardian } from '@/utils/guardian'
import {
  formatFullDate,
  joinInterests,
  labelizeCountry,
  labelizeState,
  roleLabel,
  superviseesLabel,
  supervisorLabel,
  userName
} from '@/utils/userFormat'
import { INTEREST_OPTIONS } from '@/utils/userOptions'

const props = withDefaults(
  defineProps<{
    user: AdminUser | null
    /** Whether a student's parts each offer Edit (not on Matched Groups). */
    editable?: boolean
  }>(),
  { editable: true }
)

const emit = defineEmits<{
  (e: 'updated', user: AdminUser): void
}>()

const guardian = computed(() => {
  const user = props.user
  const placeholder = isPlaceholderGuardian(user?.guardianFirstName, user?.guardianLastName, user?.firstName, user?.lastName)
  return {
    name: placeholder ? '' : `${user?.guardianFirstName || ''} ${user?.guardianLastName || ''}`.trim(),
    // Consent with no form response on record is what the old admin path
    // granted as a side effect — flag it rather than show it as received.
    consent: !user?.joinPermissionReceived ? 'missing' : user.joinpermResponseId ? 'received' : 'unverified'
  }
})

// An answer and when it was given, as the supervisor's panel shows them:
// "Yes, 14/10/26 21:30".
const answeredAt = (answer: string, at: string | null | undefined) =>
  [answer, formatShortDateTime(at)].filter(Boolean).join(', ')

// Only a given permission is recorded; a guardian never answers no.
const permissionLabel = computed(() =>
  props.user?.joinPermissionReceived ? answeredAt('Yes', props.user.joinPermissionGrantedAt) : '—'
)

// Who a consent request would go to: a requested guardian change first, else
// the guardian on file while consent is still missing. Mirrors the backend.
const consentRequestTo = computed(() => {
  const user = props.user
  if (!user) return null
  if (user.pendingGuardian) return user.pendingGuardian.email
  if (user.joinPermissionReceived) return null
  return user.guardianEmail
})

const sendingRequest = ref(false)
const requestMessage = ref('')
const requestFailed = ref(false)

watch(() => props.user?.id, () => {
  editing.value = null
  savedPart.value = null
  requestMessage.value = ''
  requestFailed.value = false
  consents.value = []
  consentsOpen.value = false
  consentsMessage.value = ''
  consentsFailed.value = false
})

// --- a student's parts, each edited in place ----------------------------------

type Part = 'account' | 'details' | 'guardian' | 'supervisor'

const YEAR_OPTIONS: AppSelectOption[] = [9, 10, 11, 12].map((year) => ({ value: year, label: String(year) }))

const editing = ref<Part | null>(null)
// The part just saved, to say so above it.
const savedPart = ref<Part | null>(null)
const saving = ref(false)
const saveError = ref('')

const STATUS_OPTIONS: AppSelectOption[] = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' }
]

const blankForm = () => ({
  email: '',
  status: 'active' as AppSelectOption['value'],
  countryId: null as number | null,
  stateId: null as number | null,
  stateName: '',
  firstName: '',
  lastName: '',
  schoolName: '',
  yearLevel: null as AppSelectOption['value'],
  interests: [] as string[],
  guardianFirstName: '',
  guardianLastName: '',
  guardianEmail: '',
  consentGiven: false,
  mediaGiven: false,
  pendingConsentGiven: false,
  supervisorEmail: '',
  groupId: null as number | null
})
const form = reactive(blankForm())

const startEdit = (part: Part) => {
  const user = props.user
  if (!user) return
  Object.assign(form, blankForm(), {
    email: user.email || '',
    status: user.isActive ? 'active' : 'inactive',
    countryId: user.country?.id ?? null,
    stateId: user.state?.id ?? null,
    stateName: user.state?.stateName || '',
    firstName: user.firstName || '',
    lastName: user.lastName || '',
    schoolName: user.schoolName || '',
    yearLevel: user.yearLevel ?? null,
    interests: (user.interests || []).filter((interest) => INTEREST_OPTIONS.includes(interest)),
    // A placeholder guardian (the student's own name) is no guardian at all.
    guardianFirstName: guardian.value.name ? user.guardianFirstName || '' : '',
    guardianLastName: guardian.value.name ? user.guardianLastName || '' : '',
    guardianEmail: user.guardianEmail || '',
    consentGiven: Boolean(user.joinPermissionReceived),
    mediaGiven: Boolean(user.joinPermissionReceived) && user.mediaConsent === true,
    supervisorEmail: (user.supervisorEmail || '').toLowerCase(),
    groupId: user.groupId ?? null
  })
  saveError.value = ''
  savedPart.value = null
  editing.value = part
  if (part === 'supervisor') loadPicks()
  if (part === 'account') loadPlaces()
}

const cancelEdit = () => {
  editing.value = null
  saveError.value = ''
}

// What a part's Save sends: only what it changes, so the rest stays as it is.
const payloadFor = (part: Part): Record<string, unknown> | string => {
  const user = props.user!
  if (part === 'account') {
    const email = form.email.toLowerCase()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'Enter a valid email address.'
    const account: Record<string, unknown> = {}
    if (email !== (user.email || '').toLowerCase()) account.email = email
    // The pair goes together, so a new country never keeps the old state:
    // Australia's picked, elsewhere's typed.
    const countryChanged = form.countryId !== (user.country?.id ?? null)
    if (inAustralia.value) {
      if (countryChanged || form.stateId !== (user.state?.id ?? null)) {
        account.countryId = form.countryId
        account.stateId = form.stateId
      }
    } else if (countryChanged || form.stateName !== (user.state?.stateName || '')) {
      account.countryId = form.countryId
      account.stateName = form.stateName
    }
    if ('countryId' in account && form.countryId === null) return 'Choose a country.'
    return account
  }
  if (part === 'details') {
    if (form.yearLevel === null) return 'Choose a year level.'
    if (!form.interests.length) return 'Choose at least one interest.'
    return {
      firstName: form.firstName,
      lastName: form.lastName,
      schoolName: form.schoolName,
      yearLevel: form.yearLevel,
      interests: form.interests
    }
  }
  const payload: Record<string, unknown> = {}
  const wasFirst = guardian.value.name ? user.guardianFirstName || '' : ''
  const wasLast = guardian.value.name ? user.guardianLastName || '' : ''
  if (form.guardianFirstName !== wasFirst || form.guardianLastName !== wasLast) {
    if (!form.guardianFirstName || !form.guardianLastName) return "Enter the guardian's first and last name."
    payload.guardianFirstName = form.guardianFirstName
    payload.guardianLastName = form.guardianLastName
  }
  if (form.guardianEmail !== (user.guardianEmail || '')) payload.guardianEmail = form.guardianEmail
  // As the full form records them: the new guardian's consent, a change to
  // consent, or media consent alone.
  const consentWas = Boolean(user.joinPermissionReceived)
  const mediaWas = consentWas && user.mediaConsent === true
  if (user.pendingGuardian && form.pendingConsentGiven) {
    payload.consentGiven = true
    payload.mediaConsent = form.mediaGiven
  } else if (form.consentGiven !== consentWas) {
    payload.consentGiven = form.consentGiven
    if (form.consentGiven) payload.mediaConsent = form.mediaGiven
  } else if (form.consentGiven && form.mediaGiven !== mediaWas) {
    payload.mediaConsent = form.mediaGiven
  }
  return payload
}

const save = async () => {
  const user = props.user
  const part = editing.value
  if (!user || !part || saving.value) return
  if (part === 'supervisor') {
    saveSupervisorAndGroup()
    return
  }
  const payload = payloadFor(part)
  if (typeof payload === 'string') {
    saveError.value = payload
    return
  }
  // Account's Status is set on its own.
  const active = form.status === 'active'
  const statusChanged = part === 'account' && active !== Boolean(user.isActive)
  if (!Object.keys(payload).length && !statusChanged) {
    cancelEdit()
    return
  }
  saving.value = true
  saveError.value = ''
  let updated: AdminUser | null = null
  try {
    if (Object.keys(payload).length) {
      const result = await updateAdminUser(user.id, payload)
      if (!result.data) {
        saveError.value = result.msg || 'The change could not be saved.'
        return
      }
      updated = result.data
    }
    if (statusChanged) updated = (await setAdminUserActive(user.id, active)).data
    editing.value = null
    savedPart.value = part
  } catch (error) {
    saveError.value = apiErrorFromUnknown(error, 'The change could not be saved.').message
  } finally {
    // What did save shows, even when the status after it didn't.
    if (updated) emit('updated', updated)
    saving.value = false
  }
}

// --- Account: the country and state picked from lists ------------------------

const countryList = ref<AdminUserCountry[]>([])
const stateList = ref<AdminUserState[]>([])
const placesLoading = ref(false)
const placesError = ref('')

// Loaded once: the countries and states hardly change.
const loadPlaces = async () => {
  if (countryList.value.length) return
  placesLoading.value = true
  placesError.value = ''
  try {
    const [countries, states] = await Promise.all([fetchAdminCountries(), fetchAdminStates()])
    countryList.value = countries
    stateList.value = states
  } catch (error) {
    placesError.value = apiErrorFromUnknown(error, 'Could not load the countries and states.').message
  } finally {
    placesLoading.value = false
  }
}

const byLabel = (a: AppSelectOption, b: AppSelectOption) => a.label.localeCompare(b.label)

const countryOptions = computed<AppSelectOption[]>(() =>
  countryList.value.map((country) => ({ value: country.id, label: country.countryName })).sort(byLabel)
)

// The chosen country's name, known before the list loads for their own.
const countryName = computed(
  () =>
    countryList.value.find((country) => country.id === form.countryId)?.countryName ??
    (form.countryId === props.user?.country?.id ? props.user?.country?.countryName : undefined)
)
const inAustralia = computed(() => countryName.value === 'Australia')

// Australia's states, after "No state".
const stateOptions = computed<AppSelectOption[]>(() => {
  const states = stateList.value
    .filter((state) => state.countryName === countryName.value)
    .map((state) => ({ value: state.id, label: state.stateName }))
    .sort(byLabel)
  return [{ value: null, label: 'No state' }, ...states]
})

// A new country clears the state, which belonged to the old one.
const pickCountry = (value: AppSelectOption['value']) => {
  if (value === form.countryId) return
  form.countryId = value as number | null
  form.stateId = null
  form.stateName = ''
}

// --- Supervisor and Group: picked from lists ---------------------------------

const supervisorList = ref<AdminUser[]>([])
const groupList = ref<AdminGroupDetail[]>([])
const picksLoading = ref(false)
const picksError = ref('')

const fetchAllGroups = async () => {
  const groups: AdminGroupDetail[] = []
  for (let page = 1; page <= 20; page += 1) {
    const data = await fetchAdminGroupList({ page, limit: 200 })
    groups.push(...data.items)
    if (!data.has_more) break
  }
  return groups
}

// Every supervisor and group, fresh each time Edit is pressed so the seats
// left are current.
const loadPicks = async () => {
  picksLoading.value = true
  picksError.value = ''
  try {
    const [supervisors, groups] = await Promise.all([
      fetchAdminUsers({ page: 1, limit: 200, role: 'supervisor' }),
      fetchAllGroups()
    ])
    supervisorList.value = supervisors.items
    groupList.value = groups
  } catch (error) {
    picksError.value = apiErrorFromUnknown(error, 'Could not load the supervisors and groups.').message
  } finally {
    picksLoading.value = false
  }
}

// By name, with the email underneath; the one they have stays a choice even
// when it isn't in the list.
const supervisorOptions = computed<AppSelectOption[]>(() => {
  const options = supervisorList.value
    .flatMap((supervisor) => {
      const email = supervisor.email
      return email ? [{ value: email.toLowerCase(), label: userName(supervisor) || email, detail: email }] : []
    })
    .sort((a, b) => a.label.localeCompare(b.label))
  const current = (props.user?.supervisorEmail || '').toLowerCase()
  if (current && !options.some((option) => option.value === current)) {
    options.unshift({ value: current, label: props.user?.supervisorName || current, detail: current })
  }
  return options
})

// "No group" first, then each group with its seats taken; a full one can't
// be picked, unless it's theirs.
const groupOptions = computed<AppSelectOption[]>(() => {
  const currentId = props.user?.groupId ?? null
  const groups: AppSelectOption[] = [...groupList.value]
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))
    .map((group) => {
      const taken = studentCount(group)
      const full = taken >= DEFAULT_GROUP_MAX_SIZE && group.id !== currentId
      return {
        value: group.id,
        label: group.name,
        detail: `${taken}/${DEFAULT_GROUP_MAX_SIZE} students${full ? ' · Full' : ''}`,
        disabled: full
      }
    })
  if (currentId !== null && !groups.some((option) => option.value === currentId)) {
    groups.unshift({ value: currentId, label: props.user?.groupName || 'Their group' })
  }
  return [{ value: null, label: 'No group', detail: 'Not in a group' }, ...groups]
})

const optionLabel = (options: AppSelectOption[], value: AppSelectOption['value']) =>
  options.find((option) => option.value === value)?.label ?? String(value)

const supervisorChanged = computed(
  () => Boolean(form.supervisorEmail) && form.supervisorEmail !== (props.user?.supervisorEmail || '').toLowerCase()
)
const groupChanged = computed(() => form.groupId !== (props.user?.groupId ?? null))

// What Save would replace, for the popup: nothing when they had none.
const replacing = computed(() => {
  const user = props.user
  if (!user) return []
  const lines: string[] = []
  if (supervisorChanged.value && user.supervisorEmail) {
    lines.push(
      `Change supervisor from ${user.supervisorName || user.supervisorEmail} to ` +
        optionLabel(supervisorOptions.value, form.supervisorEmail)
    )
  }
  if (groupChanged.value && user.groupId != null) {
    lines.push(
      form.groupId === null
        ? `Take them out of ${user.groupName || 'their group'}`
        : `Move them from ${user.groupName || 'their group'} to ${optionLabel(groupOptions.value, form.groupId)}`
    )
  }
  return lines
})

const confirmOpen = ref(false)

const saveSupervisorAndGroup = () => {
  if (!supervisorChanged.value && !groupChanged.value) {
    cancelEdit()
    return
  }
  if (replacing.value.length) {
    confirmOpen.value = true
    return
  }
  commitSupervisorAndGroup()
}

// The supervisor first, so the group move brings the right one into it.
const commitSupervisorAndGroup = async () => {
  const user = props.user
  if (!user || saving.value) return
  saving.value = true
  saveError.value = ''
  let updated: AdminUser | null = null
  try {
    if (supervisorChanged.value) {
      const result = await updateAdminUser(user.id, { supervisorEmail: form.supervisorEmail })
      if (!result.data) {
        saveError.value = result.msg || 'The change could not be saved.'
        return
      }
      updated = result.data
    }
    if (groupChanged.value) {
      if (form.groupId === null) await removeGroupMember(user.groupId!, user.id)
      else await confirmStudentAssignments([{ studentId: user.id, groupId: form.groupId }])
      updated = await fetchAdminUser(user.id)
    }
    editing.value = null
    savedPart.value = 'supervisor'
  } catch (error) {
    saveError.value = apiErrorFromUnknown(error, 'The change could not be saved.').message
  } finally {
    // What did save shows, even when the group move after it didn't.
    if (updated) emit('updated', updated)
    saving.value = false
    confirmOpen.value = false
  }
}

const mediaConsentLabel = computed(() => {
  const media = props.user?.mediaConsent
  if (media == null) return '—'
  return answeredAt(media ? 'Yes' : 'No', props.user?.mediaConsentAt)
})

// Consents signed on the platform carry a BTF- reference; old Qualtrics ones don't.
const signedOnPlatform = computed(() => (props.user?.joinpermResponseId || '').startsWith('BTF-'))

const consents = ref<AdminGuardianConsent[]>([])
const consentsOpen = ref(false)
const consentsLoading = ref(false)
// The outcome of loading the signed form or recording a withdrawal.
const consentsMessage = ref('')
const consentsFailed = ref(false)

const showConsentsMessage = (message: string, failed: boolean) => {
  consentsMessage.value = message
  consentsFailed.value = failed
}

const toggleConsents = async () => {
  const user = props.user
  if (!user) return
  if (consentsOpen.value) {
    consentsOpen.value = false
    return
  }
  consentsLoading.value = true
  consentsMessage.value = ''
  try {
    consents.value = await fetchGuardianConsents(user.id)
    consentsOpen.value = true
  } catch (error) {
    showConsentsMessage(apiErrorFromUnknown(error, 'Could not load the signed form.').message, true)
  } finally {
    consentsLoading.value = false
  }
}

const downloadingId = ref<number | null>(null)

const downloadRecord = async (consent: AdminGuardianConsent) => {
  const user = props.user
  if (!user || downloadingId.value !== null) return
  downloadingId.value = consent.id
  try {
    await downloadGuardianConsentRecord(user.id, consent)
  } catch (error) {
    showConsentsMessage(apiErrorFromUnknown(error, 'Could not download the consent record.').message, true)
  } finally {
    downloadingId.value = null
  }
}

const sendConsentRequest = async () => {
  const user = props.user
  if (!user || sendingRequest.value) return
  sendingRequest.value = true
  try {
    const result = await sendGuardianConsentRequest(user.id)
    requestFailed.value = false
    requestMessage.value = result.msg
    if (result.data) emit('updated', result.data)
  } catch (error) {
    requestFailed.value = true
    requestMessage.value = apiErrorFromUnknown(error, 'Could not send the consent request.').message
  } finally {
    sendingRequest.value = false
  }
}
</script>

<style scoped>
/* Role, status and logged in as plain text, as in the People tables;
   inactive and never logged in are greyed. */
.admin-users__role-badge,
.admin-users__status-badge,
.admin-users__logged-in-badge {
  text-transform: capitalize;
}

.admin-users__status-badge--inactive,
.admin-users__logged-in-badge:not(.admin-users__logged-in-badge--yes) {
  color: var(--text-muted);
}

.admin-users-detail__section h3 {
  margin: 0 0 0.4rem;
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--dark-green);
}

/* A part's heading with its Edit beside it, as on the supervisor's panel. */
.admin-users-detail__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.4rem;
}

.admin-users-detail__heading h3 {
  margin: 0;
}

.admin-users-detail__label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-muted);
  flex-shrink: 0;
}

.admin-users-detail__value {
  color: var(--teal);
}

.admin-users-detail__input {
  flex: 1;
  max-width: 320px;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  font: inherit;
  color: var(--teal);
  background: var(--surface-elevated);
}

.admin-users-detail__replacing {
  margin: 0.5rem 0 0;
  padding-left: 1.2rem;
}

.admin-users-detail__item:has(.admin-users-detail__input) {
  align-items: center;
}

/* Interests, or consents, to tick: one per line. */
.admin-users-detail__options {
  flex-direction: column;
  align-items: flex-start;
  margin: 0;
  border: none;
  border-bottom: 1px solid var(--border-light);
  padding: 0.6rem 0;
}

.admin-users-detail__options legend {
  padding: 0;
  margin-bottom: 0.4rem;
}

.admin-users-detail__options label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--teal);
}

.admin-users-detail__options label.is-disabled {
  color: var(--text-muted);
}

/* A consent to tick, a row of its own. */
.admin-users-detail__check {
  align-items: center;
  cursor: pointer;
}

.admin-users-detail__check.is-disabled .admin-users-detail__label {
  opacity: 0.6;
}

.admin-users-detail__check.is-disabled {
  cursor: not-allowed;
}

/* Bigger tick boxes, for consents and interests alike. */
.admin-users-detail__check input,
.admin-users-detail__options input[type='checkbox'] {
  width: 1.1rem;
  height: 1.1rem;
  margin: 0;
  flex-shrink: 0;
  accent-color: var(--dark-green);
  cursor: inherit;
}

.admin-users-detail__note {
  margin: 0 0 0.4rem;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.admin-users-detail__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.admin-users-detail__saved {
  margin: 0 0 0.4rem;
  color: var(--dark-green);
}

.admin-users-detail__save-error {
  margin: 0.5rem 0 0;
  color: var(--danger);
}

.admin-users-detail__section + .admin-users-detail__section {
  margin-top: 1.4rem;
}

.admin-users-detail__list {
  margin: 0;
}

.admin-users-detail__item {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--border-light);
}

.admin-users-detail__item dt {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-muted);
  flex-shrink: 0;
}

.admin-users-detail__item dd {
  margin: 0;
  color: var(--teal);
  text-align: right;
  overflow-wrap: anywhere;
}

.admin-users-detail__consent-request {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.4rem;
  margin-top: 0.75rem;
}

.admin-users-detail__consent-hint,
.admin-users-detail__consent-message {
  margin: 0;
  font-size: 0.8rem;
  color: var(--text-muted);
  text-align: right;
  overflow-wrap: anywhere;
}

.admin-users-detail__consent-message--error {
  color: var(--danger);
}

.admin-users-detail__flag {
  color: var(--danger);
  font-weight: 600;
}

.admin-users-detail__consent-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.admin-users-detail__consents {
  margin: 0.75rem 0 0;
  padding: 0;
  list-style: none;
}

.admin-users-detail__consent {
  padding: 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  font-size: 0.85rem;
  color: var(--teal);
}

.admin-users-detail__consent + .admin-users-detail__consent {
  margin-top: 0.5rem;
}

.admin-users-detail__consent p {
  margin: 0 0 0.35rem;
  overflow-wrap: anywhere;
}

.admin-users-detail__consent-head {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
}

.admin-users-detail__signature {
  display: block;
  max-width: 100%;
  max-height: 120px;
  margin-top: 0.5rem;
  background: var(--white, #ffffff);
  border: 1px solid var(--border-light);
  border-radius: 6px;
}

.admin-users-detail__record {
  margin-top: 0.5rem;
}

.admin-users-detail__supervisees {
  text-align: right;
}
</style>
