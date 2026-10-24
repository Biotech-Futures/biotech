<template>
  <main class="set-password-page">
    <section class="set-password-panel">
      <div class="brand-row">
        <div class="brand-mark">
          <img :src="logo" :alt="BRAND_NAME" />
        </div>
        <div>
          <p class="brand-kicker">{{ BRAND_CONNECT }}</p>
          <h1>Set your password</h1>
        </div>
      </div>

      <!-- A mentor's, set straight after registering: they sign in once an
           admin activates their account. -->
      <template v-if="mentorPasswordSet">
        <p class="page-copy" role="status">
          Your password is set. You can sign in with it once your account is activated.
        </p>
        <RouterLink to="/login" class="primary-action">Return to sign in</RouterLink>
      </template>

      <template v-else>
        <p class="page-copy">
          {{
            registration
              ? 'Create a password for your account.'
              : 'Create a password for your account before continuing to your dashboard.'
          }}
        </p>

        <form class="password-form" @submit.prevent="submitPassword" novalidate>
          <!-- A student registered by someone else, without their guardian's
               details: those too, before continuing. -->
          <fieldset v-if="needsGuardian" class="guardian-fields">
            <legend>Parent or guardian</legend>
            <p class="guardian-copy">
              Add your parent or guardian's details. We'll email them the permission form.
            </p>

            <div class="field-group">
              <label for="guardian-first-name">First name</label>
              <input
                id="guardian-first-name"
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
          </fieldset>

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
                placeholder="Enter your new password"
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
              placeholder="Re-enter your new password"
              @input="clearMessages"
            />
          </div>

          <ul class="password-rules" aria-label="Password requirements">
            <li :class="{ passed: newPassword.length >= 8 }">At least 8 characters</li>
            <li :class="{ passed: passwordsMatch && confirmPassword.length > 0 }">Passwords match</li>
          </ul>

          <p v-if="passwordError" class="error-message" role="alert">{{ passwordError }}</p>
          <p v-if="statusMessage" class="status-message" aria-live="polite">{{ statusMessage }}</p>

          <button type="submit" class="primary-action" :disabled="submitting">
            <span v-if="submitting" class="button-spinner" aria-hidden="true"></span>
            <i v-else class="fas fa-lock"></i>
            <span>{{ submitting ? 'Setting password...' : 'Set password' }}</span>
          </button>
        </form>

        <!-- Not signed in yet, straight after registering. -->
        <button v-if="!registration" type="button" class="text-action" @click="handleLogout">
          Log out
        </button>
      </template>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import logo from '@/assets/btf-logo.png'
import { BRAND_NAME, BRAND_CONNECT } from '@/constants/brand'
import { isValidRegistrationEmail } from '@/registration/registration'
import {
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

// A student someone else registered (a supervisor, a teammate or an admin)
// without all their guardian's details: they give them here too.
const needsGuardian = computed(() => {
  const user = auth.user
  if (props.registration || !user || String(user.current_role_name || '').toLowerCase() !== 'student') {
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

function clearMessages() {
  passwordError.value = ''
  statusMessage.value = ''
  guardianError.value = ''
  Object.keys(guardianErrors).forEach((key) => delete guardianErrors[key])
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

  submitting.value = true
  statusMessage.value = 'Setting your password...'

  if (props.registration) {
    await submitRegistrationPassword()
    return
  }

  try {
    if (needsGuardian.value && !(await saveGuardian())) return

    const user = await auth.setInitialPassword(newPassword.value)

    if (user.must_change_password) {
      passwordError.value = 'Password was set, but your account still requires password setup.'
      statusMessage.value = ''
      return
    }

    // The page they asked for before signing in, if any; else their own start
    // page. The store re-read /users/me/ after the password was set, so the
    // flags that tell a support agent from a student are current here.
    await router.replace(takeReturnTo(router) || landingPath(auth))
  } catch (error) {
    const apiError = apiErrorFromUnknown(error, 'Could not set your password. Please try again.')
    logApiError('set-initial-password', apiError)
    passwordError.value = apiError.message
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
    return false
  }
}

// Straight after registering: set by the registration's token, then signed
// in to their profile (a mentor waits for their account to be activated).
async function submitRegistrationPassword() {
  try {
    const signedIn = await setRegistrationPassword(held?.token || '', newPassword.value)
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
    passwordError.value = apiError.fields?.password?.[0] || apiError.message
    statusMessage.value = ''
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
    // Only straight after registering, with its token.
    if (!held) {
      await router.replace('/login')
      return
    }
  } else if (!auth.mustChangePassword) {
    // landingPath(): a support agent goes to the queue, not a dashboard.
    await router.replace(landingPath(auth))
    return
  }

  await nextTick()
  passwordInputRef.value?.focus()
})
</script>

<style scoped>
.set-password-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 32px;
  background: #e8f3ee;
}

.set-password-panel {
  width: min(100%, 520px);
  padding: 32px;
  border: 1px solid rgba(255, 255, 255, 0.56);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 28px 70px rgba(7, 24, 21, 0.32);
  backdrop-filter: blur(20px);
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 18px;
}

.brand-mark {
  width: 64px;
  height: 64px;
  display: grid;
  place-items: center;
  flex: 0 0 64px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 16px 34px rgba(1, 113, 81, 0.18);
}

.brand-mark img {
  width: 46px;
  height: 46px;
  object-fit: contain;
}

.brand-kicker {
  margin: 0 0 4px;
  color: var(--dark-green);
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  color: var(--teal);
  font-size: 1.8rem;
  line-height: 1.2;
}

.page-copy {
  margin: 0 0 24px;
  color: rgba(23, 66, 67, 0.76);
  line-height: 1.6;
}

.password-form {
  display: grid;
  gap: 16px;
}

/* A student's guardian, above their password. */
.guardian-fields {
  min-width: 0;
  margin: 0 0 8px;
  padding: 0 0 20px;
  display: grid;
  gap: 16px;
  border: 0;
  border-bottom: 1px solid rgba(23, 66, 67, 0.14);
}

.guardian-fields legend {
  margin-bottom: 4px;
  padding: 0;
  color: var(--teal);
  font-size: 1.05rem;
  font-weight: 800;
}

.guardian-copy {
  margin: 0;
  color: rgba(23, 66, 67, 0.76);
  line-height: 1.6;
}

.field-group {
  display: grid;
  gap: 8px;
}

label {
  color: var(--teal);
  font-size: 0.92rem;
  font-weight: 700;
}

.field-input,
.password-shell {
  width: 100%;
  min-height: 54px;
  border: 1px solid rgba(23, 66, 67, 0.14);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.field-input {
  padding: 0 15px;
  color: var(--teal);
  font-size: 1rem;
}

.password-shell {
  display: flex;
  align-items: center;
  padding: 0 8px 0 15px;
}

.password-shell input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--teal);
  font-size: 1rem;
}

.field-input:focus,
.password-shell:focus-within {
  outline: 0;
  border-color: rgba(1, 113, 81, 0.48);
  box-shadow: 0 0 0 4px rgba(1, 113, 81, 0.12);
}

.field-input.is-error,
.password-shell.is-error {
  border-color: rgba(220, 53, 69, 0.45);
}

.icon-button {
  width: 38px;
  height: 38px;
  display: inline-grid;
  place-items: center;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--dark-green);
  cursor: pointer;
}

.icon-button:hover,
.icon-button:focus-visible {
  background: rgba(1, 113, 81, 0.08);
}

.password-rules {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 7px;
}

.password-rules li {
  color: rgba(23, 66, 67, 0.72);
  font-size: 0.9rem;
}

.password-rules li::before {
  content: '';
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 8px;
  border-radius: 50%;
  background: rgba(23, 66, 67, 0.26);
}

.password-rules li.passed {
  color: var(--dark-green);
}

.password-rules li.passed::before {
  background: var(--dark-green);
}

.status-message,
.error-message {
  margin: 0;
  padding: 12px 14px;
  border-radius: 8px;
  font-size: 0.92rem;
  line-height: 1.5;
}

.status-message {
  color: var(--dark-green);
  border: 1px solid rgba(1, 113, 81, 0.16);
  background: rgba(1, 113, 81, 0.08);
}

.error-message {
  color: #9f3030;
  border: 1px solid rgba(220, 53, 69, 0.16);
  background: rgba(255, 238, 238, 0.82);
}

.primary-action {
  width: 100%;
  min-height: 54px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 0;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--dark-green), var(--mint-green));
  color: #ffffff;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 16px 34px rgba(1, 113, 81, 0.22);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

/* A mentor's Return to sign in: a link, as the button looks. */
a.primary-action {
  text-decoration: none;
}

.primary-action:hover:not(:disabled) {
  transform: translateY(-1px);
}

.primary-action:disabled {
  opacity: 0.72;
  cursor: wait;
}

.text-action {
  margin-top: 18px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--dark-green);
  font-weight: 800;
  cursor: pointer;
}

.text-action:hover,
.text-action:focus-visible {
  text-decoration: underline;
}

.button-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.42);
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
    padding: 18px;
  }

  .set-password-panel {
    padding: 24px 20px;
  }

  .brand-row {
    align-items: flex-start;
  }

  h1 {
    font-size: 1.45rem;
  }
}
</style>
