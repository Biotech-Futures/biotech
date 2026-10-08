<template>
  <FormSheet
    :model-value="open"
    :title="detailTitle"
    description="Account details"
    width="min(100vw, 620px)"
    @update:model-value="onDismiss"
    @close="onDismiss"
  >
    <div class="admin-users-detail">
      <section v-if="user" class="admin-users-detail__section">
        <h3>Account</h3>
        <dl class="admin-users-detail__list">
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
        </dl>
      </section>

      <section v-if="user?.role === 'student'" class="admin-users-detail__section">
        <h3>Student Profile</h3>
        <dl class="admin-users-detail__list">
          <div class="admin-users-detail__item">
            <dt>School</dt>
            <dd>{{ user.schoolName || '—' }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Year level</dt>
            <dd>{{ user.yearLevel ?? '—' }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Interests</dt>
            <dd>{{ joinInterests(user.interests) }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Group</dt>
            <dd>{{ user.groupName || '—' }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Supervisor</dt>
            <dd>{{ supervisorLabel(user) }}</dd>
          </div>
        </dl>
      </section>

      <section v-if="user?.role === 'student'" class="admin-users-detail__section" data-test="admin-guardian">
        <h3>Guardian &amp; Consent</h3>
        <dl class="admin-users-detail__list">
          <div class="admin-users-detail__item">
            <dt>Guardian</dt>
            <dd data-test="admin-guardian-name">{{ guardian.name || '—' }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Guardian email</dt>
            <dd>{{ user.guardianEmail || '—' }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Consent</dt>
            <dd data-test="admin-consent">
              <span
                class="admin-users__consent-badge"
                :class="`admin-users__consent-badge--${guardian.consent}`"
              >
                {{ consentLabel }}
              </span>
            </dd>
          </div>
          <div v-if="user.joinPermissionReceived" class="admin-users-detail__item">
            <dt>Consent response</dt>
            <dd>{{ user.joinpermResponseId || 'None on record' }}</dd>
          </div>
          <div v-if="user.joinPermissionReceived && user.joinPermissionGrantedAt" class="admin-users-detail__item">
            <dt>Recorded</dt>
            <dd>{{ formatFullDate(user.joinPermissionGrantedAt) }}</dd>
          </div>
          <div v-if="user.joinPermissionReceived" class="admin-users-detail__item" data-test="admin-media-consent">
            <dt>Media consent</dt>
            <dd :class="{ 'admin-users-detail__flag': user.mediaConsent === false }">{{ mediaConsentLabel }}</dd>
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

        <div v-if="user.joinPermissionReceived" class="admin-users-detail__consent-actions">
          <button
            v-if="signedOnPlatform"
            type="button"
            class="btn btn-outline btn-sm"
            data-test="admin-view-consent"
            :disabled="consentsLoading"
            @click="toggleConsents"
          >
            {{ consentsOpen ? 'Hide signed form' : 'View signed form' }}
          </button>
          <button
            v-if="user.mediaConsent !== false"
            type="button"
            class="btn btn-outline btn-sm"
            data-test="admin-withdraw-media"
            @click="askWithdraw(true)"
          >
            Record media withdrawal
          </button>
          <button type="button" class="btn btn-outline btn-sm" data-test="admin-withdraw-consent" @click="askWithdraw(false)">
            Record consent withdrawal
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
    </div>

    <ConfirmDialog
      v-model="withdrawDialog.open"
      :title="withdrawDialog.mediaOnly ? 'Record media consent withdrawal?' : 'Record consent withdrawal?'"
      :message="withdrawDialog.mediaOnly
        ? 'Do this when the guardian has asked to withdraw media consent. The student stays consented to take part, but will be flagged on in-person events.'
        : 'Do this when the guardian has asked to withdraw consent. The student will no longer be recorded as consented, and a new consent request can be sent.'"
      :confirm-label="withdrawDialog.mediaOnly ? 'Record media withdrawal' : 'Record withdrawal'"
      busy-label="Saving..."
      variant="danger"
      :busy="withdrawing"
      @confirm="confirmWithdraw"
    />

    <div class="admin-users-detail__footer">
      <button type="button" class="btn btn-outline" @click="onDismiss">Close</button>
      <button v-if="user" type="button" class="btn btn-primary" @click="emit('edit', user)">Edit</button>
    </div>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import { fetchGuardianConsents, sendGuardianConsentRequest, withdrawGuardianConsent } from '@/utils/adminAPI'
import type { AdminGuardianConsent, AdminUser } from '@/utils/adminAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
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

const props = defineProps<{
  open: boolean
  user: AdminUser | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'edit', user: AdminUser): void
  (e: 'updated', user: AdminUser): void
}>()

const detailTitle = computed(() => userName(props.user) || 'User details')

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

const consentLabel = computed(() => ({
  received: 'Received',
  unverified: 'Marked received, no response on record',
  missing: 'Not received'
})[guardian.value.consent])

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
  requestMessage.value = ''
  requestFailed.value = false
  consents.value = []
  consentsOpen.value = false
  consentsMessage.value = ''
  consentsFailed.value = false
})

const mediaConsentLabel = computed(() => {
  const media = props.user?.mediaConsent
  if (media === true) return 'Yes'
  if (media === false) return 'No: not permitted at in-person events'
  return 'Not recorded'
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

const withdrawDialog = ref({ open: false, mediaOnly: false })
const withdrawing = ref(false)

const askWithdraw = (mediaOnly: boolean) => {
  withdrawDialog.value = { open: true, mediaOnly }
}

const confirmWithdraw = async () => {
  const user = props.user
  if (!user || withdrawing.value) return
  withdrawing.value = true
  try {
    const result = await withdrawGuardianConsent(user.id, withdrawDialog.value.mediaOnly)
    withdrawDialog.value.open = false
    consentsOpen.value = false
    showConsentsMessage(result.msg, false)
    if (result.data) emit('updated', result.data)
  } catch (error) {
    withdrawDialog.value.open = false
    showConsentsMessage(apiErrorFromUnknown(error, 'Could not record the withdrawal.').message, true)
  } finally {
    withdrawing.value = false
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

const onDismiss = () => {
  emit('close')
}
</script>

<style scoped>
.admin-users__role-badge,
.admin-users__status-badge {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background-color: var(--light-green);
  color: var(--dark-green);
  text-transform: capitalize;
}

.admin-users__status-badge--inactive {
  background-color: var(--bg-light);
  color: var(--text-muted);
}

.admin-users__logged-in-badge {
  display: inline-block;
  width: fit-content;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background-color: var(--bg-light);
  color: var(--text-muted);
  text-transform: capitalize;
}

.admin-users__logged-in-badge--yes {
  background-color: rgba(16, 185, 129, 0.12);
  color: #047857;
}

.admin-users__consent-badge {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.admin-users__consent-badge--received {
  background-color: var(--light-green);
  color: var(--dark-green);
}

.admin-users__consent-badge--unverified {
  border: 1px solid var(--warning);
  color: var(--charcoal);
}

.admin-users__consent-badge--missing {
  background-color: var(--bg-light);
  color: var(--text-muted);
}

.admin-users-detail__section h3 {
  margin: 0 0 0.4rem;
  font-size: 0.9rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--dark-green);
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
  font-weight: 600;
  color: var(--text-muted);
  flex-shrink: 0;
}

.admin-users-detail__item dd {
  margin: 0;
  color: var(--charcoal);
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
  color: var(--charcoal);
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

.admin-users-detail__supervisees {
  text-align: right;
}

.admin-users-detail__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 1.5rem;
}
</style>