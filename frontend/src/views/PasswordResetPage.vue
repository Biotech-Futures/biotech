<template>
  <main class="reset-page">
    <section class="hero-pane legacy-left-pane">
      <div class="legacy-left-inner">
        <div class="legacy-brand">
          <div class="legacy-logo-icon">
            <img :src="logo" :alt="BRAND_NAME" />
          </div>
          <h1 class="legacy-brand-title">{{ BRAND_CONNECT }}</h1>
        </div>

        <div class="legacy-custom-content">
          <h2 class="legacy-info-title">About the {{ BRAND_NAME }} Challenge</h2>
          <p>
            A national innovation and mentorship program connecting high school students with
            leading researchers to solve real-world biotechnology challenges.
          </p>
          <ul class="legacy-info-list">
            <li>Match with mentors from universities and industry</li>
            <li>Develop a biotechnology solution with your team</li>
            <li>Present at showcase events and win awards</li>
          </ul>
        </div>

        <div class="legacy-links">
          <a
            class="legacy-website-button"
            href="https://biotechfutures.org"
            target="_blank"
            rel="noopener noreferrer"
          >
            Visit {{ BRAND_NAME }}
          </a>
        </div>
      </div>
    </section>

    <section class="reset-auth-pane">
      <div class="reset-auth-shell">
        <div class="reset-card">
          <div class="reset-card-glow" aria-hidden="true"></div>
          <div class="reset-card-noise" aria-hidden="true"></div>

          <div class="reset-panel">
            <header class="reset-header">
              <div class="auth-logo auth-logo--small">
                <img :src="logo" :alt="BRAND_NAME" />
              </div>
              <p class="brand-kicker">{{ BRAND_HUB }}</p>
              <h1>{{ hasToken ? 'Set a new password' : 'Reset your password' }}</h1>
              <p class="reset-copy">
                {{
                  hasToken
                    ? 'Choose a new password for your account. This reset link is single-use and expires after 30 minutes.'
                    : 'Enter your account email and we will send a password reset link if the account exists.'
                }}
              </p>
            </header>

            <form
              v-if="hasToken && !resetComplete"
              class="reset-form"
              @submit.prevent="submitNewPassword"
              novalidate
            >
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
                  <button
                    type="button"
                    class="icon-button"
                    :aria-label="showPassword ? 'Hide password' : 'Show password'"
                    @click="showPassword = !showPassword"
                  >
                    <svg
                      v-if="showPassword"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                      focusable="false"
                    >
                      <path
                        d="M3 3l18 18M10.58 10.58a2 2 0 0 0 2.83 2.83M9.88 4.24A9.8 9.8 0 0 1 12 4c5.52 0 9.18 5.14 9.9 6.27a2.9 2.9 0 0 1 0 3.46 18.23 18.23 0 0 1-2.2 2.69M6.4 6.39a17.28 17.28 0 0 0-4.3 3.88 2.9 2.9 0 0 0 0 3.46C2.82 14.86 6.48 20 12 20a9.9 9.9 0 0 0 4.02-.84"
                      />
                    </svg>
                    <svg v-else viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                      <path
                        d="M2.1 10.27C2.82 9.14 6.48 4 12 4s9.18 5.14 9.9 6.27a2.9 2.9 0 0 1 0 3.46C21.18 14.86 17.52 20 12 20S2.82 14.86 2.1 13.73a2.9 2.9 0 0 1 0-3.46Z"
                      />
                      <path d="M12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6Z" />
                    </svg>
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
                <span>{{ submittingPassword ? 'Updating password...' : 'Update password' }}</span>
              </button>
            </form>

            <form
              v-else-if="!resetComplete"
              class="reset-form"
              @submit.prevent="requestResetLink"
              novalidate
            >
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
                <span>{{ requestingLink ? 'Sending link...' : 'Send reset link' }}</span>
              </button>
            </form>

            <div v-else class="success-state" role="status" aria-live="polite">
              <div class="success-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" focusable="false">
                  <path d="M20 6 9 17l-5-5" />
                </svg>
              </div>
              <h2>Password reset successful</h2>
              <p>Please log in with your new password.</p>
              <button type="button" class="secondary-action" @click="goToLogin">
                <span>Back to login</span>
              </button>
            </div>

            <p v-if="statusMessage && !resetComplete" class="status-message" aria-live="polite">
              {{ statusMessage }}
            </p>

            <RouterLink class="login-link" to="/login">Return to login</RouterLink>
          </div>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import logo from '@/assets/btf-logo.png'
import { BRAND_NAME, BRAND_CONNECT, BRAND_HUB } from '@/constants/brand'
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
        includeCSRF: true,
      }),
      body: JSON.stringify(payload),
      signal: controller.signal,
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
      new_password: newPassword.value,
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
    applyApiError(
      'password-reset-confirm',
      error,
      'Could not reset your password. Please try again.',
    )
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
      email: normalizedEmail,
    })

    if (!response.ok) {
      const apiError = await apiErrorFromResponse(response, 'Could not send the reset link.')
      applyApiError('password-reset-request', apiError, 'Could not send the reset link.')
      return
    }

    statusMessage.value = 'If an account exists for that email, a reset link has been sent.'
  } catch (error) {
    applyApiError(
      'password-reset-request',
      error,
      'Could not send the reset link. Please try again.',
    )
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
  },
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
  --reset-font-primary: Arial, Helvetica, sans-serif;
  --emerald-700: #1f5d4f;
  --emerald-500: #2fa486;
  --emerald-400: #69c3aa;
  --mint-50: #f5fbf8;
  --stone-900: #10211d;
  --stone-700: #36514a;
  --stone-500: #648178;
  --border-soft: rgba(16, 33, 29, 0.1);
  --shadow-focus: 0 0 0 4px rgba(47, 164, 134, 0.14);
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 100vh;
  min-height: 100dvh;
  font-family: var(--reset-font-primary);
  background:
    radial-gradient(circle at top left, rgba(48, 173, 138, 0.16), transparent 24%),
    radial-gradient(circle at bottom right, rgba(23, 93, 79, 0.08), transparent 28%),
    linear-gradient(180deg, #eef7f2 0%, #e7f3ec 40%, #dcece2 100%);
}

.reset-page,
.reset-page * {
  box-sizing: border-box;
}

.reset-page button,
.reset-page input {
  font-family: var(--reset-font-primary);
  font-style: normal;
}

.hero-pane {
  position: relative;
  overflow: hidden;
  min-height: 100vh;
  min-height: 100dvh;
}

.legacy-left-pane {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
  background: var(--white, #ffffff);
  border-right: 1px solid var(--border-light, rgba(16, 33, 29, 0.1));
}

.legacy-left-inner {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 560px;
}

.legacy-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.legacy-brand-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--charcoal, #212529);
}

.legacy-logo-icon {
  width: 48px;
  height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background-color: var(--white, #ffffff);
}

.legacy-logo-icon img {
  width: 70%;
  height: 70%;
  object-fit: contain;
}

.legacy-info-title {
  margin: 0 0 0.75rem;
  font-size: 1.75rem;
  color: var(--charcoal, #212529);
}

.legacy-custom-content p {
  margin: 0 0 0.75rem;
  color: #566;
  line-height: 1.7;
}

.legacy-info-list {
  margin: 0.75rem 0 1rem 1.25rem;
  color: var(--charcoal, #212529);
}

.legacy-info-list li + li {
  margin-top: 0.35rem;
}

.legacy-links {
  margin-top: 1rem;
}

.legacy-website-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 42px;
  padding: 0 1rem;
  border: 2px solid var(--dark-green, #2d5a3d);
  border-radius: 8px;
  color: var(--dark-green, #2d5a3d);
  background-color: var(--white, #ffffff);
  font-weight: 700;
  text-decoration: none;
  transition:
    transform 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease;
}

.legacy-website-button:hover,
.legacy-website-button:focus-visible {
  color: var(--white, #ffffff);
  background-color: var(--dark-green, #2d5a3d);
  transform: translateY(-1px);
}

.reset-auth-pane {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  min-height: 100dvh;
  padding: 3rem 2rem;
}

.reset-auth-shell {
  width: 100%;
  max-width: 420px;
  position: relative;
}

.reset-card {
  position: relative;
  overflow: hidden;
  padding: 2rem;
  border: 1px solid rgba(255, 255, 255, 0.66);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 251, 248, 0.94));
  box-shadow: 0 26px 70px rgba(12, 41, 34, 0.14);
}

.reset-card::after {
  content: '';
  position: absolute;
  inset: 10px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.44);
  pointer-events: none;
}

.reset-card-glow {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(circle at top left, rgba(47, 164, 134, 0.16), transparent 58%);
}

.reset-card-noise {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    radial-gradient(rgba(16, 33, 29, 0.035) 0.8px, transparent 0.8px),
    linear-gradient(180deg, rgba(255, 255, 255, 0.1), transparent 24%);
  background-size:
    18px 18px,
    auto;
  opacity: 0.46;
}

.reset-panel {
  position: relative;
  z-index: 1;
}

.reset-header {
  display: grid;
  justify-items: center;
  gap: 8px;
  margin-bottom: 22px;
  text-align: center;
}

.auth-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 22px;
  background: #ffffff;
  box-shadow: 0 18px 38px rgba(31, 93, 79, 0.12);
}

.auth-logo--small {
  width: 76px;
  height: 76px;
  border-radius: 20px;
}

.auth-logo img {
  width: 76%;
  height: 76%;
  object-fit: contain;
}

.brand-kicker {
  margin: 6px 0 0;
  color: var(--emerald-700);
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  color: var(--stone-900);
  font-size: 1.85rem;
  line-height: 1.16;
}

.reset-copy {
  margin: 0;
  color: var(--stone-700);
  line-height: 1.58;
}

.reset-form {
  display: grid;
  gap: 14px;
}

.field-group {
  display: grid;
  gap: 7px;
}

label {
  color: var(--stone-900);
  font-size: 0.92rem;
  font-weight: 700;
}

.field-input,
.password-shell {
  width: 100%;
  min-height: 50px;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.42);
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.field-input {
  padding: 0 16px;
  color: var(--stone-900);
  font-size: 1rem;
}

.password-shell {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 8px 0 16px;
}

.password-shell input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--stone-900);
  font-size: 1rem;
}

.field-input::placeholder,
.password-shell input::placeholder {
  color: rgba(54, 81, 74, 0.54);
}

.field-input:focus,
.password-shell:focus-within {
  outline: 0;
  border-color: rgba(39, 132, 109, 0.38);
  box-shadow: var(--shadow-focus);
  background: #ffffff;
}

.field-input.is-error,
.password-shell.is-error {
  border-color: rgba(210, 75, 75, 0.34);
}

.icon-button {
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 999px;
  color: var(--stone-700);
  background: rgba(39, 132, 109, 0.08);
  cursor: pointer;
  transition:
    transform 0.22s ease,
    box-shadow 0.22s ease,
    background 0.22s ease,
    color 0.22s ease;
}

.icon-button:hover,
.icon-button:focus-visible {
  color: var(--emerald-700);
  background: rgba(39, 132, 109, 0.14);
  transform: translateY(-1px);
}

.icon-button:focus-visible,
.primary-action:focus-visible,
.secondary-action:focus-visible,
.login-link:focus-visible {
  outline: none;
  box-shadow: var(--shadow-focus);
}

.icon-button svg {
  width: 19px;
  height: 19px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.9;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.password-rules,
.field-errors {
  margin: 0;
  padding: 0;
  display: grid;
  gap: 7px;
  list-style: none;
}

.password-rules li,
.field-errors li {
  color: var(--stone-700);
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
  color: var(--emerald-700);
}

.password-rules li.passed::before {
  background: var(--emerald-700);
}

.field-errors {
  padding: 12px 14px;
  border: 1px solid rgba(210, 75, 75, 0.16);
  border-radius: 8px;
  background: rgba(255, 245, 245, 0.94);
}

.field-errors li {
  color: #9f3030;
}

.primary-action,
.secondary-action {
  min-height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 0;
  border-radius: 18px;
  font-size: 0.98rem;
  font-weight: 800;
  cursor: pointer;
  transition:
    transform 0.22s ease,
    box-shadow 0.22s ease,
    background 0.22s ease,
    color 0.22s ease;
}

.primary-action {
  width: 100%;
  margin-top: 2px;
  color: #ffffff;
  background: linear-gradient(135deg, var(--emerald-700), var(--emerald-500));
  box-shadow: 0 18px 28px rgba(31, 93, 79, 0.2);
}

.secondary-action {
  padding: 0 18px;
  color: var(--stone-700);
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(16, 33, 29, 0.1);
}

.primary-action:hover:not(:disabled),
.secondary-action:hover {
  transform: translateY(-1px);
}

.primary-action:disabled {
  opacity: 0.72;
  cursor: wait;
  transform: none;
  box-shadow: none;
}

.button-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.status-message,
.error-message {
  margin: 14px 0 0;
  padding: 12px 14px;
  border-radius: 8px;
  font-size: 0.92rem;
  line-height: 1.5;
}

.status-message {
  color: var(--emerald-700);
  border: 1px solid rgba(39, 132, 109, 0.18);
  background: rgba(39, 132, 109, 0.08);
}

.error-message {
  color: #9f3030;
  border: 1px solid rgba(210, 75, 75, 0.18);
  background: rgba(255, 245, 245, 0.94);
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
  background: rgba(39, 132, 109, 0.1);
  color: var(--emerald-700);
  font-size: 1.4rem;
  font-weight: 900;
}

.success-icon svg {
  width: 25px;
  height: 25px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.4;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.success-state h2,
.success-state p {
  margin: 0;
}

.success-state h2 {
  color: var(--stone-900);
  font-size: 1.35rem;
}

.success-state p {
  color: var(--stone-700);
}

.login-link {
  display: inline-flex;
  justify-content: center;
  width: 100%;
  margin-top: 18px;
  color: var(--emerald-700);
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

@media (max-width: 900px) {
  .reset-page {
    grid-template-columns: 1fr;
  }

  .hero-pane {
    min-height: auto;
  }

  .legacy-left-pane {
    align-items: flex-start;
    padding: 2rem 1.5rem;
    border-right: 0;
    border-bottom: 1px solid var(--border-soft);
  }

  .reset-auth-pane {
    min-height: auto;
    padding: 32px 18px 40px;
  }
}

@media (max-width: 620px) {
  .reset-card {
    padding: 22px 18px;
  }

  h1 {
    font-size: 1.48rem;
  }
}
</style>
