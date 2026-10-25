<template>
  <main class="set-password-page">
    <!-- Under the site's top bar, which shows the logo: laid out as Guardian
         Details is. -->
    <div class="set-password-shell">
      <section class="set-password-card">
        <h1>{{ completingRegistration ? 'Complete your registration' : 'Set your password' }}</h1>

        <!-- The link a registration email gave: checked before the form, which
             asks for their guardian too if we don't have them. -->
        <p v-if="checkingLink" class="page-copy" role="status">Opening your link…</p>

        <template v-else-if="linkError">
          <p class="page-copy" role="alert">{{ linkError }}</p>
          <RouterLink to="/login" class="btn btn-primary primary-action">Go to sign in</RouterLink>
        </template>

        <!-- A mentor's, set straight after registering: they sign in once an
             admin activates their account. -->
        <template v-else-if="mentorPasswordSet">
          <p class="page-copy" role="status">
            Your password is set. You can sign in with it once your account is activated.
          </p>
          <RouterLink to="/login" class="btn btn-primary primary-action">Return to sign in</RouterLink>
        </template>

        <template v-else>
          <!-- A student registered by someone else, without their guardian's
               details: those first, then their password. -->
          <template v-if="needsGuardian">
            <p class="step-label">Step {{ onGuardianStep ? 1 : 2 }} of 2</p>
            <h2>{{ onGuardianStep ? 'Guardian details' : 'Password' }}</h2>
          </template>
          <p class="page-copy">
            {{
              onGuardianStep
                ? "Add your parent or guardian's details. We'll email them the permission form."
                : 'Create a password for your account.'
            }}
          </p>

          <form
            class="password-form"
            novalidate
            @submit.prevent="onGuardianStep ? continueToPassword() : submitPassword()"
          >
            <div v-if="onGuardianStep" class="guardian-fields">
              <div class="field-group">
                <label for="guardian-first-name">First name</label>
                <input
                  id="guardian-first-name"
                  ref="guardianInputRef"
                  v-model="guardian.first_name"
                  class="field-input"
                  :class="{ 'is-error': Boolean(guardianErrors.first_name) }"
                  autocomplete="off"
                  required
                  @input="clearMessages"
                />
              </div>

              <div class="field-group">
                <label for="guardian-last-name">Last name</label>
                <input
                  id="guardian-last-name"
                  v-model="guardian.last_name"
                  class="field-input"
                  :class="{ 'is-error': Boolean(guardianErrors.last_name) }"
                  autocomplete="off"
                  required
                  @input="clearMessages"
                />
              </div>

              <div class="field-group">
                <label for="guardian-email">Email</label>
                <input
                  id="guardian-email"
                  v-model="guardian.email"
                  class="field-input"
                  :class="{ 'is-error': Boolean(guardianErrors.email) }"
                  type="email"
                  autocomplete="off"
                  required
                  @input="clearMessages"
                />
              </div>

              <p v-if="guardianError" class="error-message" role="alert">{{ guardianError }}</p>

              <button type="submit" class="btn btn-primary set-password-submit">Continue</button>
            </div>

            <template v-else>
              <div class="field-group">
                <label for="new-password">New password</label>
                <div class="password-shell" :class="{ 'is-error': Boolean(passwordError) }">
                  <input
                    id="new-password"
                    ref="passwordInputRef"
                    v-model="newPassword"
                    :type="showPassword ? 'text' : 'password'"
                    autocomplete="new-password"
                    minlength="8"
                    required
                    @input="clearMessages"
                  />
                  <button
                    type="button"
                    class="icon-button"
                    :aria-label="showPassword ? 'Hide password' : 'Show password'"
                    @click="showPassword = !showPassword"
                  >
                    <i class="fas" :class="showPassword ? 'fa-eye-slash' : 'fa-eye'"></i>
                  </button>
                </div>
              </div>

              <div class="field-group">
                <label for="confirm-password">Confirm password</label>
                <input
                  id="confirm-password"
                  v-model="confirmPassword"
                  class="field-input"
                  :class="{ 'is-error': Boolean(passwordError) }"
                  :type="showPassword ? 'text' : 'password'"
                  autocomplete="new-password"
                  required
                  @input="clearMessages"
                />
              </div>

              <ul class="password-rules" aria-label="Password requirements">
                <li :class="{ passed: newPassword.length >= 8 }">At least 8 characters</li>
                <li :class="{ passed: passwordsMatch && confirmPassword.length > 0 }">Passwords match</li>
              </ul>

              <!-- Someone registered by others agrees to the BIOTech Futures
                   policies here, as the registration form asks the person
                   filling it in. -->
              <div v-if="needsPolicies" class="policies-agree">
                <label class="policies-agree__check">
                  <input
                    v-model="policiesAgreed"
                    type="checkbox"
                    data-test="policies-agree"
                    :aria-invalid="Boolean(policiesError)"
                    :aria-describedby="policiesError ? 'policies-agree-error' : undefined"
                    @change="policiesError = ''"
                  />
                  <span>
                    I have read and agree to the
                    <a :href="POLICIES_URL" target="_blank" rel="noopener noreferrer">BIOTech Futures policies</a>
                  </span>
                </label>
                <p v-if="policiesError" id="policies-agree-error" class="policies-agree__error" role="alert">
                  {{ policiesError }}
                </p>
              </div>

              <p v-if="passwordError" class="error-message" role="alert">{{ passwordError }}</p>
              <p v-if="statusMessage" class="status-message" aria-live="polite">{{ statusMessage }}</p>

              <button type="submit" class="btn btn-primary set-password-submit" :disabled="submitting">
                <span v-if="submitting" class="button-spinner" aria-hidden="true"></span>
                {{ submitting ? 'Setting password...' : 'Set password' }}
              </button>
              <button
                v-if="needsGuardian"
                type="button"
                class="text-action"
                :disabled="submitting"
                @click="backToGuardian"
              >
                Back to guardian details
              </button>
            </template>
          </form>

          <!-- Not signed in yet, straight after registering. -->
          <button v-if="!registration" type="button" class="text-action" @click="handleLogout">
            Log out
          </button>
        </template>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { POLICIES_URL } from '@/constants/brand'
import { isValidRegistrationEmail } from '@/registration/registration'
import {
  checkRegistrationPassword,
  heldRegistrationPassword,
  releaseRegistrationPassword,
  setRegistrationPassword,
} from '@/registration/registrationPassword'
import { useAuthStore } from '@/stores/auth'
import { apiErrorFromUnknown, logApiError } from '@/utils/apiError'
import { landingPath } from '@/utils/landing'
import { takeReturnTo } from '@/utils/postLoginRedirect'

const props = withDefaults(
  defineProps<{
    /** Straight after registering (/register/password), by the token the
     *  registration gave; otherwise signed in, on first sign-in. */
    registration?: boolean
  }>(),
  { registration: false },
)

const router = useRouter()
const auth = useAuthStore()

const newPassword = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const submitting = ref(false)
const statusMessage = ref('')
const passwordError = ref('')
const passwordInputRef = ref<HTMLInputElement | null>(null)

const passwordsMatch = computed(() => newPassword.value === confirmPassword.value)

// Straight after registering: the registration's token, and a mentor's
// password once set (they wait for their account to be activated).
const held = props.registration ? heldRegistrationPassword() : null
const mentorPasswordSet = ref(false)

// A student someone else registered (a teammate, their supervisor or an
// admin) comes from their registration email, with a token of their own
// (?token=, for 14 days). It's checked first: whether it still works, and
// whether they give their guardian too.
const linkToken = (() => {
  const token = router.currentRoute?.value?.query?.token
  return props.registration && typeof token === 'string' ? token : ''
})()
const registrationToken = linkToken || held?.token || ''
const checkingLink = ref(Boolean(linkToken))
const linkError = ref('')
const linkNeedsGuardian = ref(false)
const linkNeedsPolicies = ref(false)

// A student someone else registered (a supervisor, a teammate or an admin)
// without all their guardian's details: they give them here too, whether
// signed in on first sign-in or from their registration email's link.
const needsGuardian = computed(() => {
  if (props.registration) return linkNeedsGuardian.value
  const user = auth.user
  if (!user || String(user.current_role_name || '').toLowerCase() !== 'student') {
    return false
  }
  return !(user.pg_firstname?.trim() && user.pg_lastname?.trim() && user.pg_email?.trim())
})
const guardian = reactive({
  first_name: auth.user?.pg_firstname || '',
  last_name: auth.user?.pg_lastname || '',
  email: auth.user?.pg_email || '',
})
const guardianError = ref('')
const guardianErrors = reactive<Record<string, string>>({})
const guardianInputRef = ref<HTMLInputElement | null>(null)

// Their guardian first, then their password (when the guardian's asked for).
const step = ref<'guardian' | 'password'>('guardian')
const onGuardianStep = computed(() => needsGuardian.value && step.value === 'guardian')
// A student, mentor or supervisor is completing their registration; an admin
// or a support agent is only setting a first password.
const completingRegistration = computed(() => props.registration || (!auth.isAdmin && !auth.isSupportOnly))

// Someone registered by others (a teammate, their supervisor or an admin)
// who hasn't agreed to the BIOTech Futures policies: the registration form
// asks only the person filling it in. The server says who (needs_policies).
const needsPolicies = computed(() =>
  props.registration ? linkNeedsPolicies.value : completingRegistration.value && !auth.user?.policies_agreed_at,
)
const policiesAgreed = ref(false)
const policiesError = ref('')
const POLICIES_NEEDED = 'Agree to the BIOTech Futures policies to continue.'

async function continueToPassword() {
  clearMessages()
  if (!validateGuardian()) return
  step.value = 'password'
  await nextTick()
  passwordInputRef.value?.focus()
}

async function backToGuardian() {
  clearMessages()
  step.value = 'guardian'
  await nextTick()
  guardianInputRef.value?.focus()
}

function clearMessages() {
  passwordError.value = ''
  statusMessage.value = ''
  guardianError.value = ''
  policiesError.value = ''
  Object.keys(guardianErrors).forEach((key) => delete guardianErrors[key])
}

// The policies not agreed to, as the page or the server says.
function policiesRefused(fields: Record<string, string[] | undefined>) {
  const message = fields.policiesAgreed?.[0]
  if (message) policiesError.value = message
  return Boolean(message)
}

function validateGuardian() {
  if (!needsGuardian.value) return true

  if (!guardian.first_name.trim()) guardianErrors.first_name = "Enter your guardian's first name."
  if (!guardian.last_name.trim()) guardianErrors.last_name = "Enter your guardian's last name."
  if (!guardian.email.trim()) guardianErrors.email = "Enter your guardian's email."
  else if (!isValidRegistrationEmail(guardian.email)) guardianErrors.email = 'Enter a valid email for your guardian.'

  const first = Object.values(guardianErrors)[0]
  if (first) guardianError.value = first
  return !first
}

function validatePasswordForm() {
  if (!newPassword.value) {
    passwordError.value = 'Please enter a new password.'
    return false
  }

  if (newPassword.value.length < 8) {
    passwordError.value = 'Password must be at least 8 characters.'
    return false
  }

  if (!confirmPassword.value) {
    passwordError.value = 'Please confirm your new password.'
    return false
  }

  if (!passwordsMatch.value) {
    passwordError.value = 'The two passwords do not match.'
    return false
  }

  return true
}

async function submitPassword() {
  if (submitting.value) return
  clearMessages()
  if (!validateGuardian() || !validatePasswordForm()) return
  if (needsPolicies.value && !policiesAgreed.value) {
    policiesError.value = POLICIES_NEEDED
    return
  }

  submitting.value = true
  statusMessage.value = 'Setting your password...'

  if (props.registration) {
    await submitRegistrationPassword()
    return
  }

  try {
    if (needsGuardian.value && !(await saveGuardian())) return

    const user = await auth.setInitialPassword(newPassword.value, needsPolicies.value && policiesAgreed.value)

    if (user.must_change_password) {
      passwordError.value = 'Password was set, but your account still requires password setup.'
      statusMessage.value = ''
      return
    }

    // A student, mentor or supervisor goes on to their profile, as they do
    // straight after registering. An admin or a support agent goes to the
    // page they asked for before signing in, if any, else their own start
    // page. The store re-read /users/me/ after the password was set, so the
    // flags that tell a support agent from a student are current here.
    const returnTo = takeReturnTo(router)
    const member = !auth.isAdmin && !auth.isSupportOnly
    await router.replace(member ? '/profile' : returnTo || landingPath(auth))
  } catch (error) {
    const apiError = apiErrorFromUnknown(error, 'Could not set your password. Please try again.')
    logApiError('set-initial-password', apiError)
    if (!policiesRefused(apiError.fields ?? {})) passwordError.value = apiError.message
    statusMessage.value = ''
  } finally {
    submitting.value = false
  }
}

// Their guardian, saved as their profile saves one: the guardian is emailed
// the permission form. Whether it was saved.
async function saveGuardian() {
  try {
    await auth.updateGuardian({
      first_name: guardian.first_name.trim(),
      last_name: guardian.last_name.trim(),
      email: guardian.email.trim().toLowerCase(),
    })
    return true
  } catch (error) {
    const apiError = apiErrorFromUnknown(error, 'Could not save your guardian details. Please try again.')
    logApiError('set-password-guardian', apiError)
    guardianError.value = Object.values(apiError.fields ?? {})[0]?.[0] || apiError.message
    statusMessage.value = ''
    // Shown with their details, to change them.
    step.value = 'guardian'
    return false
  }
}

// The emailed link: whether it still works, and whether they give their
// guardian too (with what's on file of them). Whether the form can show.
async function checkLink() {
  try {
    const check = await checkRegistrationPassword(linkToken)
    linkNeedsGuardian.value = check.needsGuardian
    linkNeedsPolicies.value = check.needsPolicies
    if (check.guardian) Object.assign(guardian, check.guardian)
    return true
  } catch (error) {
    const apiError = apiErrorFromUnknown(error, 'This link to set your password could not be opened.')
    logApiError('check-registration-password', apiError)
    linkError.value = apiError.message
    return false
  } finally {
    checkingLink.value = false
  }
}

// Straight after registering, or from the registration email's link: set by
// its token (their guardian first, when asked for), then signed in to their
// profile (a mentor waits for their account to be activated).
async function submitRegistrationPassword() {
  try {
    const signedIn = await setRegistrationPassword(
      registrationToken,
      newPassword.value,
      needsGuardian.value
        ? {
            first_name: guardian.first_name.trim(),
            last_name: guardian.last_name.trim(),
            email: guardian.email.trim().toLowerCase(),
          }
        : undefined,
      needsPolicies.value && policiesAgreed.value,
    )
    releaseRegistrationPassword()
    if (!signedIn) {
      mentorPasswordSet.value = true
      return
    }
    await auth.fetchUserData()
    await router.replace('/profile')
  } catch (error) {
    const apiError = apiErrorFromUnknown(error, 'Could not set your password. Please try again.')
    logApiError('set-registration-password', apiError)
    const fields = apiError.fields ?? {}
    statusMessage.value = ''
    // The policies not agreed to: said by the box.
    if (policiesRefused(fields)) return
    // The guardian's details refused (their own email, say): said there.
    const guardianFields = Object.keys(fields).filter((key) => key in guardian)
    if (needsGuardian.value && !fields.password?.[0] && guardianFields.length) {
      guardianFields.forEach((key) => (guardianErrors[key] = fields[key]?.[0] || apiError.message))
      guardianError.value = guardianErrors[guardianFields[0]!] || apiError.message
      step.value = 'guardian'
    } else {
      passwordError.value = fields.password?.[0] || apiError.message
    }
  } finally {
    submitting.value = false
  }
}

async function handleLogout() {
  await auth.logout()
  await router.replace('/login')
}

onMounted(async () => {
  if (props.registration) {
    if (linkToken) {
      // From a registration email: checked first.
      if (!(await checkLink())) return
    } else if (!held) {
      // Otherwise only straight after registering, with its token.
      await router.replace('/login')
      return
    }
  } else if (!auth.mustChangePassword) {
    // landingPath(): a support agent goes to the queue, not a dashboard.
    await router.replace(landingPath(auth))
    return
  }

  await nextTick()
  ;(onGuardianStep.value ? guardianInputRef : passwordInputRef).value?.focus()
})
</script>

<style scoped>
/* As Guardian Details: the platform's card, fields, button and colours, on
   the site's background under its top bar (64px). */
.set-password-page {
  min-height: calc(100vh - 64px);
  min-height: calc(100dvh - 64px);
  padding: 32px 16px 48px;
  color: var(--teal);
  background: var(--bg-light);
}

.set-password-page,
.set-password-page * {
  box-sizing: border-box;
}

.set-password-shell {
  max-width: 560px;
  margin: 0 auto;
}

.set-password-card {
  padding: 1.5rem;
  border-radius: 8px;
  background: var(--white);
  box-shadow: 0 2px 4px var(--shadow);
}

h1 {
  margin: 0 0 32px;
  font-size: 1.6rem;
  line-height: 1.2;
}

.page-copy {
  margin: 0;
  color: var(--text-muted);
  line-height: 1.6;
}

/* Two steps for a student's guardian, then their password: which one, and
   its title under the page's. */
.step-label {
  margin: 0 0 2px;
  color: var(--text-muted);
  font-size: 0.85rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

h2 {
  margin: 0 0 4px;
  font-size: 1.15rem;
  line-height: 1.3;
}

.field-group {
  display: grid;
  gap: 7px;
  margin-top: 16px;
}

label {
  color: var(--teal);
  font-size: 0.95rem;
  font-weight: 700;
}

.field-input,
.password-shell {
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  background: var(--white);
  transition: border-color 0.3s ease;
}

.field-input,
.password-shell input {
  padding: 0.625rem;
  color: var(--teal);
  font: inherit;
  font-size: 1rem;
}

/* The password and its Show button, in one box. */
.password-shell {
  display: flex;
  align-items: center;
  padding-right: 4px;
}

.password-shell input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
}

.field-input:focus,
.password-shell:focus-within {
  outline: none;
  border-color: var(--dark-green);
  box-shadow: 0 0 0 3px rgba(1, 113, 81, 0.1);
}

.field-input.is-error,
.password-shell.is-error {
  border-color: var(--danger);
}

.icon-button {
  width: 34px;
  height: 34px;
  display: inline-grid;
  place-items: center;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--dark-green);
  cursor: pointer;
}

.icon-button:hover,
.icon-button:focus-visible {
  background: rgba(1, 113, 81, 0.08);
}

.password-rules {
  margin: 14px 0 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 6px;
}

.password-rules li {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.password-rules li::before {
  content: '';
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 8px;
  border-radius: 50%;
  background: var(--border-light);
}

.password-rules li.passed {
  color: var(--dark-green);
}

.password-rules li.passed::before {
  background: var(--dark-green);
}

/* The BIOTech Futures policies: a box and its sentence, as on the form. */
.policies-agree {
  margin-top: 18px;
}

.policies-agree__check {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-weight: 400;
  line-height: 1.5;
  cursor: pointer;
}

.policies-agree__check input {
  flex: none;
  width: 18px;
  height: 18px;
  margin: 2px 0 0;
  accent-color: var(--dark-green);
}

.policies-agree__check a {
  color: var(--dark-green);
  font-weight: 700;
}

.policies-agree__error {
  margin: 8px 0 0 28px;
  color: var(--danger);
  font-size: 0.9rem;
}

.status-message,
.error-message {
  margin: 18px 0 0;
  padding: 12px 14px;
  border-radius: 4px;
}

.status-message {
  border: 1px solid rgba(1, 113, 81, 0.16);
  background: rgba(1, 113, 81, 0.06);
  color: var(--dark-green);
}

.error-message {
  border: 1px solid rgba(220, 53, 69, 0.25);
  background: rgba(220, 53, 69, 0.06);
  color: var(--danger);
}

/* Set password, and a mentor's Return to sign in: the full-width button. */
.set-password-submit,
.primary-action {
  width: 100%;
  margin-top: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

a.primary-action {
  text-decoration: none;
}

.set-password-submit:disabled {
  opacity: 0.72;
  cursor: wait;
}

/* Log out: a quiet line under the button. */
.text-action {
  display: block;
  margin: 14px auto 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--text-muted);
  font: inherit;
  font-size: 0.9rem;
  cursor: pointer;
}

.text-action:hover,
.text-action:focus-visible {
  color: var(--dark-green);
  text-decoration: underline;
}

.button-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 620px) {
  .set-password-page {
    padding: 20px 16px 36px;
  }

  .set-password-card {
    padding: 22px 18px;
  }

  h1 {
    font-size: 1.35rem;
  }
}
</style>
