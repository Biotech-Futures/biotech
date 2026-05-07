<template>
  <main class="reset-page">
    <div class="reset-background" aria-hidden="true"></div>

    <section class="reset-panel">
      <div class="brand-row">
        <div class="brand-mark">
          <img :src="logo" alt="BIOTech Futures" />
        </div>
        <div>
          <p class="brand-kicker">BIOTech Futures Hub</p>
          <h1>{{ hasToken ? 'Set a new password' : 'Reset your password' }}</h1>
        </div>
      </div>

      <p class="reset-copy">
        {{
          hasToken
            ? 'Choose a new password for your account. This reset link is single-use and expires after 30 minutes.'
            : 'Enter your account email and we will send a password reset link if the account exists.'
        }}
      </p>

      <form v-if="hasToken && !resetComplete" class="reset-form" @submit.prevent="submitNewPassword" novalidate>
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
              @input="clearFieldErrors"
            />
            <button type="button" class="icon-button" :aria-label="showPassword ? 'Hide password' : 'Show password'" @click="showPassword = !showPassword">
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
            @input="clearFieldErrors"
          />
        </div>

        <ul class="password-rules" aria-label="Password requirements">
          <li :class="{ passed: newPassword.length >= 8 }">At least 8 characters</li>
          <li :class="{ passed: passwordsMatch && confirmPassword.length > 0 }">Passwords match</li>
        </ul>

        <p v-if="passwordError" class="error-message" role="alert">{{ passwordError }}</p>

        <ul v-if="fieldMessages.length" class="field-errors" role="alert">
          <li v-for="message in fieldMessages" :key="message">{{ message }}</li>
        </ul>

        <button type="submit" class="primary-action" :disabled="submittingPassword">
          <span v-if="submittingPassword" class="button-spinner" aria-hidden="true"></span>
          <i v-else class="fas fa-lock"></i>
          <span>{{ submittingPassword ? 'Updating password...' : 'Update password' }}</span>
        </button>
      </form>

      <form v-else-if="!resetComplete" class="reset-form" @submit.prevent="requestResetLink" novalidate>
        <div class="field-group">
          <label for="reset-email">Email address</label>
          <input
            id="reset-email"
            ref="emailInputRef"
            v-model.trim="email"
            class="field-input"
            type="email"
            autocomplete="email"
            required
            placeholder="name@example.com"
          />
        </div>

        <p v-if="requestError" class="error-message" role="alert">{{ requestError }}</p>

        <button type="submit" class="primary-action" :disabled="requestingLink">
          <span v-if="requestingLink" class="button-spinner" aria-hidden="true"></span>
          <i v-else class="fas fa-envelope"></i>
          <span>{{ requestingLink ? 'Sending link...' : 'Send reset link' }}</span>
        </button>
      </form>

      <div v-else class="success-state" role="status" aria-live="polite">
        <div class="success-icon">
          <i class="fas fa-check"></i>
        </div>
        <h2>Password reset successful</h2>
        <p>Please log in with your new password.</p>
        <button type="button" class="secondary-action" @click="goToLogin">
          <i class="fas fa-arrow-right"></i>
          <span>Back to login</span>
        </button>
      </div>

      <p v-if="statusMessage && !resetComplete" class="status-message" aria-live="polite">
        {{ statusMessage }}
      </p>

      <RouterLink class="login-link" to="/login">Return to login</RouterLink>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import logo from '@/assets/btf-logo.png'
import { clearAuthTokens } from '@/utils/authTokens'
import { apiErrorFromResponse, apiErrorFromUnknown, logApiError } from '@/utils/apiError'
import { buildSessionHeaders, ensureCsrfCookie, resetCsrfToken } from '@/utils/csrf'
import { useAuthStore } from '@/stores/auth'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const REQUEST_TIMEOUT_MS = 15000
const SUCCESS_REDIRECT_MS = 2400

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const submittingPassword = ref(false)
const requestingLink = ref(false)
const resetComplete = ref(false)
const statusMessage = ref('')
const passwordError = ref('')
const requestError = ref('')
const fieldMessages = ref<string[]>([])
const passwordInputRef = ref<HTMLInputElement | null>(null)
const emailInputRef = ref<HTMLInputElement | null>(null)

let successRedirectTimer: ReturnType<typeof setTimeout> | null = null

const token = computed(() => {
  const rawToken = route.query.token
  return Array.isArray(rawToken) ? String(rawToken[0] || '') : String(rawToken || '')
})

const hasToken = computed(() => token.value.trim().length > 0)
const passwordsMatch = computed(() => newPassword.value === confirmPassword.value)

function clearFieldErrors() {
  passwordError.value = ''
  fieldMessages.value = []
}

function validateEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

function validatePasswordForm() {
  clearFieldErrors()

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

async function postJson(path: string, payload: Record<string, unknown>) {
  await ensureCsrfCookie(API_BASE_URL)

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    return await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      credentials: 'include',
      headers: buildSessionHeaders({
        includeCSRF: true
      }),
      body: JSON.stringify(payload),
      signal: controller.signal
    })
  } finally {
    clearTimeout(timeoutId)
  }
}

function applyApiError(context: string, error: unknown, fallback: string) {
  const apiError = apiErrorFromUnknown(error, fallback)
  logApiError(context, apiError)

  if (apiError.code === 'weak_password' || apiError.code === 'WeakPassword') {
    fieldMessages.value = apiError.fields?.new_password || []
    passwordError.value = apiError.message
    return
  }

  if (
    apiError.code === 'invalid_or_expired_reset_token' ||
    apiError.code === 'InvalidOrExpiredResetToken'
  ) {
    passwordError.value = 'This reset link is invalid or has expired. Please request a new link.'
    return
  }

  if (
    apiError.code === 'password_reset_rate_limited' ||
    apiError.code === 'PasswordResetRateLimited'
  ) {
    const message = 'Too many password reset attempts. Please wait a while before trying again.'
    if (hasToken.value) passwordError.value = message
    else requestError.value = message
    return
  }

  if (hasToken.value) {
    passwordError.value = apiError.message
  } else {
    requestError.value = apiError.message
  }
}

async function submitNewPassword() {
  if (submittingPassword.value || !validatePasswordForm()) return

  submittingPassword.value = true
  statusMessage.value = 'Updating your password...'

  try {
    const response = await postJson('/services/password-reset/confirm/', {
      token: token.value,
      new_password: newPassword.value
    })

    if (!response.ok) {
      statusMessage.value = ''
      const apiError = await apiErrorFromResponse(response, 'Password reset failed.')
      applyApiError('password-reset-confirm', apiError, 'Password reset failed.')
      return
    }

    auth.$patch({ user: null, initialized: true })
    clearAuthTokens()
    resetCsrfToken()

    try {
      localStorage.removeItem('auth.user')
    } catch {}

    resetComplete.value = true
    statusMessage.value = ''
    successRedirectTimer = setTimeout(goToLogin, SUCCESS_REDIRECT_MS)
  } catch (error) {
    statusMessage.value = ''
    applyApiError('password-reset-confirm', error, 'Could not reset your password. Please try again.')
  } finally {
    submittingPassword.value = false
  }
}

async function requestResetLink() {
  const normalizedEmail = email.value.trim().toLowerCase()
  requestError.value = ''
  statusMessage.value = ''

  if (!normalizedEmail) {
    requestError.value = 'Please enter your email address.'
    return
  }

  if (!validateEmail(normalizedEmail)) {
    requestError.value = 'Please enter a valid email address.'
    return
  }

  requestingLink.value = true
  email.value = normalizedEmail

  try {
    const response = await postJson('/services/password-reset/request/', {
      email: normalizedEmail
    })

    if (!response.ok) {
      const apiError = await apiErrorFromResponse(response, 'Could not send the reset link.')
      applyApiError('password-reset-request', apiError, 'Could not send the reset link.')
      return
    }

    statusMessage.value = 'If an account exists for that email, a reset link has been sent.'
  } catch (error) {
    applyApiError('password-reset-request', error, 'Could not send the reset link. Please try again.')
  } finally {
    requestingLink.value = false
  }
}

function goToLogin() {
  router.replace('/login')
}

watch(
  () => route.fullPath,
  async () => {
    statusMessage.value = ''
    passwordError.value = ''
    requestError.value = ''
    fieldMessages.value = []
    resetComplete.value = false
    await nextTick()
    if (hasToken.value) passwordInputRef.value?.focus()
    else emailInputRef.value?.focus()
  }
)

onMounted(async () => {
  await nextTick()
  if (hasToken.value) passwordInputRef.value?.focus()
  else emailInputRef.value?.focus()
})

onBeforeUnmount(() => {
  if (successRedirectTimer) {
    clearTimeout(successRedirectTimer)
  }
})
</script>

<style scoped>
.reset-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 32px;
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(1, 113, 81, 0.96), rgba(57, 104, 123, 0.94)),
    url('@/assets/login/login-bg-2.jpg') center / cover;
}

.reset-background {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.12), transparent 42%),
    radial-gradient(circle at 20% 18%, rgba(241, 229, 166, 0.22), transparent 30%),
    radial-gradient(circle at 82% 86%, rgba(94, 169, 158, 0.28), transparent 34%);
  pointer-events: none;
}

.reset-panel {
  width: min(100%, 520px);
  position: relative;
  z-index: 1;
  padding: 32px;
  border: 1px solid rgba(255, 255, 255, 0.56);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
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
  color: var(--charcoal);
  font-size: 1.8rem;
  line-height: 1.2;
}

.reset-copy {
  margin: 0 0 24px;
  color: rgba(23, 66, 67, 0.76);
  line-height: 1.6;
}

.reset-form {
  display: grid;
  gap: 16px;
}

.field-group {
  display: grid;
  gap: 8px;
}

label {
  color: var(--charcoal);
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
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.field-input {
  padding: 0 15px;
  color: var(--charcoal);
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
  color: var(--charcoal);
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

.password-rules,
.field-errors {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 7px;
}

.password-rules li,
.field-errors li {
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

.field-errors {
  padding: 12px 14px;
  border: 1px solid rgba(220, 53, 69, 0.16);
  border-radius: 8px;
  background: rgba(255, 238, 238, 0.82);
}

.field-errors li {
  color: #9f3030;
}

.primary-action,
.secondary-action {
  min-height: 54px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 0;
  border-radius: 8px;
  font-weight: 800;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.primary-action {
  width: 100%;
  margin-top: 4px;
  background: linear-gradient(135deg, var(--dark-green), var(--mint-green));
  color: #ffffff;
  box-shadow: 0 16px 34px rgba(1, 113, 81, 0.22);
}

.secondary-action {
  padding: 0 20px;
  background: rgba(1, 113, 81, 0.08);
  color: var(--dark-green);
}

.primary-action:hover:not(:disabled),
.secondary-action:hover {
  transform: translateY(-1px);
}

.primary-action:disabled {
  opacity: 0.72;
  cursor: wait;
}

.button-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.42);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
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
  margin-top: 16px;
  color: var(--dark-green);
  border: 1px solid rgba(1, 113, 81, 0.16);
  background: rgba(1, 113, 81, 0.08);
}

.error-message {
  color: #9f3030;
  border: 1px solid rgba(220, 53, 69, 0.16);
  background: rgba(255, 238, 238, 0.82);
}

.success-state {
  display: grid;
  justify-items: center;
  gap: 12px;
  text-align: center;
}

.success-icon {
  width: 58px;
  height: 58px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: rgba(1, 113, 81, 0.1);
  color: var(--dark-green);
  font-size: 1.4rem;
}

.success-state h2,
.success-state p {
  margin: 0;
}

.success-state p {
  color: rgba(23, 66, 67, 0.72);
}

.login-link {
  display: inline-flex;
  margin-top: 18px;
  color: var(--dark-green);
  font-weight: 800;
  text-decoration: none;
}

.login-link:hover,
.login-link:focus-visible {
  text-decoration: underline;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 620px) {
  .reset-page {
    padding: 18px;
  }

  .reset-panel {
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
