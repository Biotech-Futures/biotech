<template>
  <!--
  --------------------------------------------------------------------------------------------------------------
   * @file LoginPage.vue
   *
   * @description LoginPage.vue is the unified entry page for the BIOTech Futures mentoring platform.
   It combines password and email-to-OTP authentication, multilingual support,
   and branded platform presentation in one structured login experience.
   *
   * @author Shiqi Fang
   * @author Jiachen Ding
   * @author Qin Chen
   * @version 1.4.0
   *
   * Project: Group Based 5703 Capstone Project
   * Group: CS17-1
   * Team: CS17-1 Frontend Team
   *
   * Component Type: Frontend Page Component
   * File Role: Unified login entry page
   *
   * Purpose: Provide a structured and user-friendly entry point for students, mentors, supervisors,
   and administrators to sign in with email OTP while understanding the platform context before entering the system.
   *
   * Scope: Covers the left information pane, language switching, email submission,
   OTP verification, resend flow, and post-login navigation.
   *
   * Responsibilities:
   * - Display platform branding and overview information
   * - Support multilingual login experience with LTR and RTL layout handling
   * - Handle the full passwordless email-to-OTP authentication flow
   * - Provide reusable login copy for different authentication modes
   * - Keep authentication feedback, loading state, and OTP interaction consistent
   *
   * Dependencies:
   * - Vue 3 Composition API
   * - Vue Router
   * - Pinia auth store
   * - Login language data
   * - Login background data
   * - CSRF header helper
   * - String and storage utilities
   *
   * Revision Summary:
   * - Major revisions: 5
   * - Minor revisions: 5
   *
   * Last Modified: 2026-04-10
   * Modified By: CS17-1 Frontend Team
   *
   -----------------------------------------------------------------------------------------------------------------------------
   -->

  <!-- Page shell and two-column layout. -->
  <div class="login-shell">
    <div class="shell-aurora" aria-hidden="true">
      <span class="shell-aurora-orb shell-aurora-orb--one"></span>
      <span class="shell-aurora-orb shell-aurora-orb--two"></span>
      <span class="shell-aurora-orb shell-aurora-orb--three"></span>
      <span class="shell-mesh"></span>
    </div>
    <!-- Left information pane from the old login page. -->
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
            The {{ BRAND_NAME }} Challenge empowers students to tackle real-world problems through
            innovation, mentorship, and interdisciplinary collaboration.
          </p>
          <ul class="legacy-info-list">
            <li>Learn from mentors across academia &amp; industry</li>
            <li>Develop practical solutions and prototypes</li>
            <li>Present at showcase events and win awards</li>
          </ul>
          <p>Explore key dates, eligibility, submission guidelines, and more on our website.</p>
        </div>

        <div class="legacy-links">
          <a
            class="legacy-website-button"
            href="https://biotechfutures.org"
            target="_blank"
            rel="noopener noreferrer"
          >
            Visit Website
          </a>
        </div>
      </div>
    </section>

    <!-- Right authentication pane. -->
    <section class="auth-pane">
      <div class="auth-shell">
        <!-- Auth card container. -->
        <div class="auth-card">
          <div class="auth-card-glow"></div>
          <div class="auth-card-noise"></div>

          <!-- Two-step progress indicator. -->
          <div
            v-if="currentStep !== 'inactive'"
            class="auth-progress"
            aria-label="Authentication progress"
          >
            <div class="progress-item active current">
              <span class="progress-dot">1</span>
              <span class="progress-label">{{ t('emailStep') }}</span>
            </div>
            <div class="progress-line active"></div>
            <div class="progress-item active">
              <span class="progress-dot">2</span>
              <span class="progress-label">{{ credentialStepLabel }}</span>
            </div>
          </div>

          <!-- Step transition wrapper. -->
          <transition name="content-fade" mode="out-in">
            <!-- Email step panel. -->
            <div v-if="currentStep === 'email'" key="email" class="step-panel">
              <header class="auth-header">
                <div class="auth-logo-wrap">
                  <div class="auth-logo">
                    <img :src="logo" :alt="BRAND_NAME" />
                  </div>

                  <div class="auth-logo-copy">
                    <h2 class="auth-title">{{ authHeading }}</h2>
                  </div>
                </div>

                <p class="auth-subtitle">{{ authSubtitle }}</p>

                <!-- Meta chips for selected identity and auth method. -->
                <!--                <div class="meta-row">-->
                <!--                  <span class="meta-chip meta-chip&#45;&#45;neutral">{{ activeLoginModeLabel }}</span>-->
                <!--                </div>-->
              </header>

              <!-- Email submission form. -->
              <form class="auth-form" @submit.prevent="handleLogin" novalidate>
                <div class="login-mode-switch" role="tablist" :aria-label="t('loginMethod')">
                  <button
                    type="button"
                    class="login-mode-button"
                    :class="{ active: loginMode === 'password' }"
                    role="tab"
                    :aria-selected="loginMode === 'password'"
                    @click="setLoginMode('password')"
                  >
                    {{ t('passwordSignIn') }}
                  </button>
                  <button
                    type="button"
                    class="login-mode-button"
                    :class="{ active: loginMode === 'code' }"
                    role="tab"
                    :aria-selected="loginMode === 'code'"
                    @click="setLoginMode('code')"
                  >
                    {{ t('emailCodeSignIn') }}
                  </button>
                </div>

                <div class="field-block">
                  <label class="field-label" for="login-email">{{ t('emailLabel') }}</label>

                  <!-- Field shell highlights focus and error state at container level. -->
                  <div class="field-shell" :class="{ 'is-error': Boolean(error) }">
                    <input
                      id="login-email"
                      ref="emailInputRef"
                      v-model.trim="email"
                      type="email"
                      class="field-input"
                      :placeholder="t('emailPlaceholder')"
                      :aria-invalid="Boolean(error)"
                      autocomplete="email"
                      required
                    />
                  </div>

                  <!--                  <small class="field-help">{{ emailStepHelper }}</small>-->
                </div>

                <div
                  class="field-block password-field-slot"
                  :class="{ 'is-reserved-hidden': loginMode !== 'password' }"
                  :aria-hidden="loginMode !== 'password'"
                >
                  <label class="field-label" for="login-password">{{ t('passwordLabel') }}</label>

                  <div
                    class="field-shell field-shell--password"
                    :class="{ 'is-error': Boolean(error) }"
                  >
                    <input
                      id="login-password"
                      ref="passwordInputRef"
                      v-model="password"
                      :type="showPassword ? 'text' : 'password'"
                      class="field-input"
                      :placeholder="t('passwordPlaceholder')"
                      :aria-invalid="Boolean(error)"
                      autocomplete="current-password"
                      :disabled="loginMode !== 'password'"
                      :required="loginMode === 'password'"
                    />
                    <button
                      type="button"
                      class="password-toggle"
                      :aria-label="passwordVisibilityLabel"
                      :aria-pressed="showPassword"
                      :title="passwordVisibilityLabel"
                      :disabled="loginMode !== 'password'"
                      @click="togglePasswordVisibility"
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

                  <div class="forgot-password-row">
                    <a href="/#/auth/reset-password" class="forgot-password-link">
                      Forgot password?
                    </a>
                  </div>
                </div>

                <button
                  type="submit"
                  class="primary-button"
                  :disabled="sendingCode || submitBlockedByCooldown"
                >
                  <span v-if="sendingCode && isPasswordLoginMode">{{ t('loadingDashboard') }}</span>
                  <span v-else-if="sendingCode">{{ t('sendingCode') }}</span>
                  <span v-else>{{ loginActionLabel }}</span>
                </button>

                <p class="registration-demo-link">
                  New student?
                  <RouterLink to="/register">Start a registration</RouterLink>
                </p>
              </form>

              <!-- Step feedback messages. -->
              <transition name="message-slide">
                <p v-if="statusMessage" class="status-message" aria-live="polite">
                  {{ statusMessage }}
                </p>
              </transition>

              <transition name="message-slide">
                <p v-if="error" class="error-message" role="alert" aria-live="assertive">
                  {{ error }}
                </p>
              </transition>
            </div>

            <!-- Inactive account panel: replaces the form, since no credential can unblock it. -->
            <div v-else-if="currentStep === 'inactive'" key="inactive" class="step-panel">
              <header class="auth-header">
                <div class="auth-logo-wrap">
                  <div class="auth-logo">
                    <img :src="logo" :alt="BRAND_NAME" />
                  </div>

                  <div class="auth-logo-copy">
                    <h2 class="auth-title">{{ t('accountInactiveTitle') }}</h2>
                  </div>
                </div>

                <p class="auth-subtitle" role="alert">{{ t('accountInactiveBody') }}</p>
              </header>

              <!-- Support row spells out the address: nothing else on this screen can unblock the user. -->
              <div class="support-row">
                <span>{{ t('accountInactiveContact') }}</span>
                <a class="support-email" :href="`mailto:${SUPPORT_EMAIL}`">{{ SUPPORT_EMAIL }}</a>
              </div>

              <button type="button" class="secondary-button" @click="goBackToEmailStep">
                {{ t('backToSignIn') }}
              </button>
            </div>

            <!-- OTP step panel. -->
            <div v-else key="otp" class="step-panel step-panel--otp">
              <header class="auth-header auth-header--compact">
                <div class="auth-logo-wrap">
                  <div class="auth-logo auth-logo--small">
                    <img :src="logo" :alt="BRAND_NAME" />
                  </div>

                  <div class="auth-logo-copy">
                    <span class="auth-kicker">{{ t('secureAccess') }}</span>
                    <h2 class="auth-title">{{ t('verifyHeading') }}</h2>
                  </div>
                </div>

                <p class="auth-subtitle">{{ t('codeSentTo') }} {{ maskedEmail }}</p>

                <!-- Meta row keeps role context visible during OTP verification. -->
                <div class="meta-row meta-row--stack">
                  <button type="button" class="text-link" @click="goBackToEmailStep">
                    {{ t('changeEmail') }}
                  </button>
                </div>
              </header>

              <!-- OTP box. -->
              <!-- Each box binds to one digit, while input, keyboard, focus, and paste are centrally handled in script helpers. -->
              <div
                class="otp-box"
                :class="{
                  'has-error': otpErrorActive,
                  'is-complete': isOtpComplete && !otpErrorActive,
                  shaking: otpShake,
                }"
              >
                <input
                  v-for="(digit, index) in otpDigits"
                  :key="index"
                  :ref="(el) => setOtpRef(el, index)"
                  v-model="otpDigits[index]"
                  type="text"
                  maxlength="1"
                  class="otp-input"
                  :class="{ 'otp-input-error': otpErrorActive, 'otp-input-filled': Boolean(digit) }"
                  inputmode="numeric"
                  autocomplete="one-time-code"
                  :aria-label="`${t('digit')} ${index + 1}`"
                  @input="handleOTPInput($event, index)"
                  @keydown="handleOTPKeydown($event, index)"
                  @keydown.enter.prevent="handleOTPEnter"
                  @focus="handleOTPFocus($event)"
                  @paste="handleOTPPaste($event, index)"
                />
              </div>
              <div class="otp-footer-copy">
                <p v-if="codeSecondsLeft > 0" aria-live="polite">
                  {{ t('codeExpiresIn') }} {{ codeCountdownLabel }}
                </p>
                <p v-else-if="codeExpiredNotice" class="otp-expired-note" role="alert">
                  {{ t('codeExpiredHint') }}
                </p>
                <p>{{ t('codeExpiryHint') }}</p>
                <p v-if="showSpamHint">{{ t('codeSpamHint') }}</p>
              </div>

              <!-- OTP primary and secondary actions. -->
              <div class="otp-action-stack">
                <button
                  type="button"
                  class="primary-button"
                  :disabled="verifyingCode || !isOtpComplete"
                  @click="verifyOTP"
                >
                  <span v-if="verifyingCode">{{ t('loadingDashboard') }}</span>
                  <span v-else>{{ t('verifyCode') }}</span>
                </button>

                <div class="otp-secondary-actions">
                  <button
                    type="button"
                    class="secondary-button"
                    :disabled="resendDisabled"
                    @click="resendCode"
                  >
                    {{
                      resendDisabled && resendCountdown > 0
                        ? `${t('resendIn')} ${formatWait(resendCountdown)}`
                        : t('resendCode')
                    }}
                  </button>
                </div>
              </div>

              <transition name="message-slide">
                <p v-if="statusMessage" class="status-message" aria-live="polite">
                  {{ statusMessage }}
                </p>
              </transition>

              <transition name="message-slide">
                <p v-if="error" class="error-message" role="alert" aria-live="assertive">
                  {{ error }}
                </p>
              </transition>

              <!-- Support link row. -->
              <div class="support-row">
                <span>{{ t('needHelp') }}</span>
                <a :href="`mailto:${SUPPORT_EMAIL}`">{{ t('contactSupport') }}</a>
              </div>
            </div>
          </transition>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
/*
  Imports and external modules.
*/
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { buildSessionHeaders, ensureCsrfCookie, resetCsrfToken, setCsrfToken } from '@/utils/csrf'
import { apiErrorFromResponse, apiErrorFromUnknown, logApiError } from '@/utils/apiError'
import { redirectAfterLogin } from '@/utils/postLoginRedirect'
import { isValidEmail, maskEmail } from '@/utils/string'
import {
  LOGIN_SEND_COOLDOWN_KEY,
  safeLocalStorageGet,
  safeLocalStorageRemove,
  safeLocalStorageSet,
} from '@/utils/storage'

import logo from '@/assets/btf-logo.png'
import { BRAND_NAME, BRAND_CONNECT, SUPPORT_EMAIL } from '@/constants/brand'
import { LOGIN_MESSAGES } from '@/data/login_language'

/*
  Page-level instances.
*/
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

/*
  Static configuration.
*/
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const RESEND_SECONDS = 60
// The send is dispatched off-thread server-side, so the response is immediate;
// this only guards a genuinely dead connection.
const REQUEST_TIMEOUT_MS = 30000
// Mirrors the backend LOGIN_OTP_EXPIRY_MINUTES.
const CODE_LIFETIME_SECONDS = 600
const SPAM_HINT_DELAY_SECONDS = 20
// The 5-per-15-min cap can return a retry_after of ~900; never hold the button
// longer than that even if a stored deadline is stale.
const MAX_COOLDOWN_SECONDS = 900

// Magic-link failures arrive as ?error= codes forwarded by the callback view.
const MAGIC_LINK_ERROR_KEYS = {
  invalid_or_expired_code: 'errorMagicLinkExpired',
  too_many_attempts: 'errorMagicLinkThrottled',
  session_load_failed: 'errorUserLoadFailed',
  callback_failed: 'errorMagicLinkFailed',
}

/*
  Shared page data.
*/
const messages = LOGIN_MESSAGES

/*
  Auth flow state.
*/
const email = ref('')
const password = ref('')
const showPassword = ref(false)
const loginMode = ref('code')
const currentStep = ref('email')
const error = ref('')
const statusMessage = ref('')
const sendingCode = ref(false)
const verifyingCode = ref(false)
const resendingCode = ref(false)
const resendCountdown = ref(0)
const loginCooldownSeconds = ref(0)
const codeSecondsLeft = ref(0)
const codeCountdownStarted = ref(false)

/*
  OTP interaction state.
*/
const otpDigits = ref(['', '', '', '', '', ''])
const otpRefs = ref([])
const otpShake = ref(false)
const otpErrorActive = ref(false)

/*
  DOM refs.
*/
const emailInputRef = ref(null)
const passwordInputRef = ref(null)

/*
  Runtime timer handles.
*/
let resendTimer = null
let loginCooldownTimer = null
let otpErrorTimer = null
let otpAutoSubmitTimer = null
let codeExpiryTimer = null

/*
  Translation accessor.
*/
const t = (key) => messages.en?.[key] || key

/*
  Basic derived values.
*/
const maskedEmail = computed(() => maskEmail(email.value))
const isOtpComplete = computed(() => otpDigits.value.every((digit) => /^\d$/.test(digit)))
const authHeading = computed(() => t('signIn'))

const authSubtitle = computed(() => t('welcomeSubtitle'))

const isPasswordLoginMode = computed(() => loginMode.value === 'password')
const activeLoginModeLabel = computed(() =>
  isPasswordLoginMode.value ? t('passwordSignIn') : t('emailCodeSignIn'),
)
const credentialStepLabel = computed(() =>
  isPasswordLoginMode.value ? t('passwordStep') : t('otpStep'),
)
const passwordVisibilityLabel = computed(() =>
  showPassword.value ? 'Conceal password' : 'Show password',
)
// Tripping the 15-minute send cap yields a retry_after in the hundreds, and
// "Resend in 847s" reads as broken; anything past a minute becomes m:ss.
const formatWait = (totalSeconds) => {
  if (totalSeconds < 60) return `${totalSeconds}s`
  const minutes = Math.floor(totalSeconds / 60)
  return `${minutes}:${String(totalSeconds % 60).padStart(2, '0')}`
}

const loginOnCooldown = computed(() => loginCooldownSeconds.value > 0)
// The OTP throttle only governs code requests; password sign-in is rate-limited separately server-side.
// The resend gap counts here too, or stepping back to the email screen would bypass it.
const sendBlockedSeconds = computed(() =>
  Math.max(loginCooldownSeconds.value, resendCountdown.value),
)
const submitBlockedByCooldown = computed(
  () => sendBlockedSeconds.value > 0 && !isPasswordLoginMode.value,
)
const loginActionLabel = computed(() => {
  if (submitBlockedByCooldown.value)
    return `${t('resendIn')} ${formatWait(sendBlockedSeconds.value)}`
  return isPasswordLoginMode.value ? t('signIn') : t('sendVerificationCode')
})
// Guarded on "did we ever start a countdown": zero also means "not tracking",
// which must not read as expired or it would unlock resend immediately.
const codeExpiredNotice = computed(() => codeCountdownStarted.value && codeSecondsLeft.value <= 0)
const codeCountdownLabel = computed(() => {
  const minutes = Math.floor(codeSecondsLeft.value / 60)
  const seconds = String(codeSecondsLeft.value % 60).padStart(2, '0')
  return `${minutes}:${seconds}`
})
// Once expired the code is useless, so let them re-request even mid-cooldown.
const resendDisabled = computed(
  () => resendingCode.value || (resendCountdown.value > 0 && !codeExpiredNotice.value),
)
const showSpamHint = computed(
  () => codeSecondsLeft.value > 0 && codeSecondsLeft.value < CODE_LIFETIME_SECONDS - SPAM_HINT_DELAY_SECONDS,
)
const emailStepHelper = computed(() =>
  isPasswordLoginMode.value ? t('passwordHelper') : t('emailHelper'),
)

/*
  Message helpers.
*/
const clearMessages = () => {
  error.value = ''
  statusMessage.value = ''
}

/*
  Timer cleanup helpers.
*/
const clearOtpAnimationTimers = () => {
  if (otpErrorTimer) {
    clearTimeout(otpErrorTimer)
    otpErrorTimer = null
  }
}

const clearOtpAutoSubmitTimer = () => {
  if (otpAutoSubmitTimer) {
    clearTimeout(otpAutoSubmitTimer)
    otpAutoSubmitTimer = null
  }
}

const clearLoginCooldownTimer = () => {
  if (loginCooldownTimer) {
    clearInterval(loginCooldownTimer)
    loginCooldownTimer = null
  }
}

/*
  Login mode interaction helpers.
*/
const setLoginMode = async (mode) => {
  if (!['password', 'code'].includes(mode) || loginMode.value === mode) {
    return
  }

  loginMode.value = mode
  currentStep.value = 'email'
  clearMessages()
  clearOtpAutoSubmitTimer()
  otpErrorActive.value = false
  otpShake.value = false

  await nextTick()

  if (mode === 'password') {
    passwordInputRef.value?.focus()
    return
  }

  showPassword.value = false
  emailInputRef.value?.focus()
}

const togglePasswordVisibility = () => {
  showPassword.value = !showPassword.value
  nextTick(() => passwordInputRef.value?.focus())
}

/*
  OTP ref collection.
*/
const setOtpRef = (element, index) => {
  if (element) {
    otpRefs.value[index] = element
  }
}

/*
  OTP state reset.
*/
const resetOtpState = async () => {
  clearOtpAutoSubmitTimer()
  otpDigits.value = ['', '', '', '', '', '']
  otpShake.value = false
  otpErrorActive.value = false
  await nextTick()
  otpRefs.value[0]?.focus()
}

/*
  Fill OTP digits from pasted or merged input text.
*/
const fillOtpFromText = async (value, startIndex = 0) => {
  const digits = value
    .replace(/\D/g, '')
    .slice(0, 6 - startIndex)
    .split('')

  if (!digits.length) {
    return
  }

  digits.forEach((digit, offset) => {
    otpDigits.value[startIndex + offset] = digit
  })

  await nextTick()

  const nextIndex = Math.min(startIndex + digits.length, 5)
  otpRefs.value[nextIndex]?.focus()
}

/*
  OTP input handlers.
*/
const handleOTPInput = async (event, index) => {
  otpErrorActive.value = false
  otpShake.value = false
  clearOtpAnimationTimers()

  const normalizedValue = event.target.value.replace(/\D/g, '')

  if (!normalizedValue) {
    otpDigits.value[index] = ''
    return
  }

  if (normalizedValue.length > 1) {
    otpDigits.value[index] = ''
    await fillOtpFromText(normalizedValue, index)
    return
  }

  otpDigits.value[index] = normalizedValue

  if (index < otpDigits.value.length - 1) {
    otpRefs.value[index + 1]?.focus()
  }
}

const handleOTPKeydown = (event, index) => {
  const key = event.key

  /*
    Allow common system shortcuts such as Ctrl/Cmd + C/V/A/X.
  */
  if (event.ctrlKey || event.metaKey) {
    return
  }

  if (key === 'Backspace') {
    event.preventDefault()

    if (otpDigits.value[index]) {
      otpDigits.value[index] = ''
      return
    }

    if (index > 0) {
      otpDigits.value[index - 1] = ''
      otpRefs.value[index - 1]?.focus()
    }

    return
  }

  if (key === 'ArrowLeft' && index > 0) {
    event.preventDefault()
    otpRefs.value[index - 1]?.focus()
    return
  }

  if (key === 'ArrowRight' && index < otpDigits.value.length - 1) {
    event.preventDefault()
    otpRefs.value[index + 1]?.focus()
    return
  }

  if (key === ' ' || key === 'Spacebar') {
    event.preventDefault()
    return
  }

  if (['Tab', 'Shift', 'Control', 'Meta', 'Alt', 'Enter', 'Delete', 'Home', 'End'].includes(key)) {
    return
  }

  if (!/^\d$/.test(key)) {
    event.preventDefault()
  }
}

const handleOTPFocus = (event) => {
  event.target.select()
}

const handleOTPPaste = async (event, index = 0) => {
  event.preventDefault()
  otpErrorActive.value = false
  otpShake.value = false
  clearOtpAnimationTimers()

  const pastedText = event.clipboardData?.getData('text') || ''
  await fillOtpFromText(pastedText, index)
}

const handleOTPEnter = async () => {
  if (!isOtpComplete.value || verifyingCode.value) {
    return
  }

  await verifyOTP()
}

/*
  Request helpers.
*/
const buildCallbackUrl = () => `${window.location.origin}/#/auth/callback`

const startLoginCooldown = (seconds = 300) => {
  loginCooldownSeconds.value = seconds
  clearLoginCooldownTimer()

  loginCooldownTimer = setInterval(() => {
    if (loginCooldownSeconds.value <= 1) {
      loginCooldownSeconds.value = 0
      clearLoginCooldownTimer()
      return
    }

    loginCooldownSeconds.value -= 1
  }, 1000)
}

const parseApiError = async (response, fallbackText) => {
  const apiError = await apiErrorFromResponse(response, fallbackText)
  logApiError('login', apiError)
  return apiError
}

const loginErrorMessage = (apiError) => {
  return apiError?.message || t('errorNetworkLogin')
}

const parseResponseJson = async (response) => {
  try {
    return await response.json()
  } catch {
    return null
  }
}

/*
  Shared JSON POST request helper.
*/
const postJson = async (path, payload) => {
  const csrfReady = await ensureCsrfCookie(API_BASE_URL)
  if (!csrfReady) {
    throw new Error(t('errorCsrfFailed'))
  }

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    return await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: buildSessionHeaders({
        includeCSRF: true,
      }),
      credentials: 'include',
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
  } finally {
    clearTimeout(timeoutId)
  }
}

/*
  Resend countdown logic.
*/
const cooldownStorageKey = (address) => `${LOGIN_SEND_COOLDOWN_KEY}:${address}`

// Clamped so a stale deadline or a backwards clock change can't disable the
// button for an arbitrary length of time.
const remainingFromDeadline = (address, cap) => {
  const stored = Number(safeLocalStorageGet(cooldownStorageKey(address), '0'))
  if (!Number.isFinite(stored) || stored <= 0) return 0
  return Math.min(cap, Math.max(0, Math.ceil((stored - Date.now()) / 1000)))
}

const runResendCountdown = () => {
  if (resendTimer) clearInterval(resendTimer)

  // Recomputed from the stored deadline rather than decremented: browsers throttle
  // timers in background tabs, so counting down would drift far behind the server.
  resendTimer = setInterval(() => {
    const remaining = remainingFromDeadline(email.value, MAX_COOLDOWN_SECONDS)
    resendCountdown.value = remaining

    if (remaining <= 0) {
      clearInterval(resendTimer)
      resendTimer = null
      safeLocalStorageRemove(cooldownStorageKey(email.value))
    }
  }, 1000)
}

const startResendCountdown = (seconds = RESEND_SECONDS) => {
  const total = Math.min(
    MAX_COOLDOWN_SECONDS,
    Math.max(1, Math.round(Number(seconds) || RESEND_SECONDS)),
  )
  resendCountdown.value = total
  // Persist the deadline, not the remaining count: a refresh must not reset it.
  safeLocalStorageSet(cooldownStorageKey(email.value), String(Date.now() + total * 1000))
  runResendCountdown()
}

const restoreResendCountdown = (address) => {
  const remaining = remainingFromDeadline(address, MAX_COOLDOWN_SECONDS)

  if (remaining <= 0) {
    safeLocalStorageRemove(cooldownStorageKey(address))
    return
  }

  resendCountdown.value = remaining
  runResendCountdown()
}

// The server's retry_after is authoritative; fall back to our own gap if absent.
const cooldownFromError = (apiError) =>
  Number(apiError?.body?.retry_after) || RESEND_SECONDS

const startCodeExpiryCountdown = (seconds = CODE_LIFETIME_SECONDS) => {
  // Anchored to a deadline for the same reason as the resend timer: a throttled
  // background tab would otherwise show time left on a code that already died.
  const deadline = Date.now() + seconds * 1000
  codeSecondsLeft.value = seconds
  codeCountdownStarted.value = true
  if (codeExpiryTimer) clearInterval(codeExpiryTimer)

  codeExpiryTimer = setInterval(() => {
    const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000))
    codeSecondsLeft.value = remaining

    if (remaining <= 0) {
      clearInterval(codeExpiryTimer)
      codeExpiryTimer = null
    }
  }, 1000)
}

/*
  OTP error feedback.
*/
const triggerOtpErrorFeedback = async () => {
  clearOtpAnimationTimers()
  clearOtpAutoSubmitTimer()
  otpErrorActive.value = true
  otpShake.value = false
  otpDigits.value = ['', '', '', '', '', '']

  await nextTick()

  otpShake.value = true
  otpRefs.value[0]?.focus()

  otpErrorTimer = setTimeout(() => {
    otpShake.value = false
  }, 420)
}

/*
  Step navigation helper.
*/
const goBackToEmailStep = async () => {
  // Drop ?error= so a refresh does not drop the user back on the inactive screen.
  if (route.query.error) router.replace({ name: 'login' })
  currentStep.value = 'email'
  clearMessages()
  otpErrorActive.value = false
  otpShake.value = false
  clearOtpAutoSubmitTimer()
  await nextTick()
  emailInputRef.value?.focus()
}

/*
  Authentication flow: send code.
*/
const handleLogin = async () => {
  const normalizedEmail = email.value.trim().toLowerCase()
  const enteredPassword = password.value

  clearMessages()

  if (!normalizedEmail) {
    error.value = t('errorEnterEmail')
    return
  }

  if (!isValidEmail(normalizedEmail)) {
    error.value = t('errorInvalidEmail')
    return
  }

  if (isPasswordLoginMode.value && !enteredPassword) {
    error.value = t('errorEnterPassword')
    await nextTick()
    passwordInputRef.value?.focus()
    return
  }

  email.value = normalizedEmail

  if (sendingCode.value) {
    return
  }

  // A stored cooldown means a code is already in flight, so send them straight to
  // the digit inputs instead of blocking here — silently refusing would strand a
  // user who has a perfectly good code sitting in their inbox.
  if (!isPasswordLoginMode.value && resendCountdown.value === 0) {
    restoreResendCountdown(normalizedEmail)
    if (resendCountdown.value > 0) {
      currentStep.value = 'otp'
      await resetOtpState()
      return
    }
  }

  if (submitBlockedByCooldown.value) {
    currentStep.value = 'otp'
    return
  }

  sendingCode.value = true
  statusMessage.value = ''

  try {
    if (isPasswordLoginMode.value) {
      await auth.loginWithPassword(normalizedEmail, enteredPassword)

      if (!auth.user) {
        error.value = t('errorUserLoadFailed')
        statusMessage.value = ''
        return
      }

      await redirectAfterLogin(auth, router)
      return
    }

    const response = await postJson('/services/send-login-code/', {
      email: normalizedEmail,
      redirect_url: buildCallbackUrl(),
    })

    if (!response.ok) {
      statusMessage.value = ''
      const apiError = await parseApiError(response, t('errorSendLink'))
      if (apiError.code === 'too_many_failed_attempts') startLoginCooldown()
      if (apiError.code === 'login_send_rate_limited') {
        // A code may already be in flight; show the OTP step so they can use it.
        startResendCountdown(cooldownFromError(apiError))
        currentStep.value = 'otp'
      }
      if (apiError.code === 'account_inactive') currentStep.value = 'inactive'
      error.value = loginErrorMessage(apiError)
      return
    }

    statusMessage.value = t('sendingSuccess')
    currentStep.value = 'otp'
    await resetOtpState()
    startResendCountdown()
    startCodeExpiryCountdown()
  } catch (requestError) {
    logApiError('login', requestError)
    statusMessage.value = ''
    const apiError = apiErrorFromUnknown(requestError, t('errorNetworkLogin'))
    if (apiError.code === 'too_many_failed_attempts') startLoginCooldown()
    if (apiError.code === 'account_inactive') currentStep.value = 'inactive'
    else if (!isPasswordLoginMode.value) {
      // The send may well have succeeded before the connection dropped, so hold
      // the button anyway — an immediate retry is what stacks up codes.
      startResendCountdown()
    }
    error.value = loginErrorMessage(apiError)
  } finally {
    sendingCode.value = false
  }
}

/*
  Authentication flow: verify OTP.
*/
const verifyOTP = async () => {
  const code = otpDigits.value.join('')

  if (code.length !== 6) {
    error.value = t('errorCompleteCode')
    statusMessage.value = ''
    return
  }

  const csrfReady = await ensureCsrfCookie(API_BASE_URL)
  if (!csrfReady) {
    error.value = t('errorCsrfFailed')
    statusMessage.value = ''
    return
  }

  clearMessages()
  verifyingCode.value = true
  statusMessage.value = ''

  try {
    const response = await postJson('/services/verify-login-code/', {
      email: email.value,
      code,
    })

    if (!response.ok) {
      statusMessage.value = ''
      const apiError = await parseApiError(response, t('errorInvalidCode'))
      if (apiError.code === 'too_many_failed_attempts') startLoginCooldown()
      error.value = loginErrorMessage(apiError)
      // The OTP was correct — skip the shake/refocus, the inputs are gone.
      if (apiError.code === 'account_inactive') {
        currentStep.value = 'inactive'
        return
      }
      await triggerOtpErrorFeedback()
      return
    }

    const data = await parseResponseJson(response)
    if (!setCsrfToken(data?.csrfToken)) {
      resetCsrfToken()
    }

    await auth.fetchUserData()

    if (!auth.user) {
      error.value = t('errorUserLoadFailed')
      statusMessage.value = ''
      return
    }

    await redirectAfterLogin(auth, router)
  } catch (requestError) {
    logApiError('verify-login-code', requestError)
    statusMessage.value = ''
    error.value = loginErrorMessage(apiErrorFromUnknown(requestError, t('errorNetworkOtp')))
  } finally {
    verifyingCode.value = false
  }
}

/*
  Authentication flow: resend code.
*/
const resendCode = async () => {
  if (!email.value) {
    error.value = t('errorEnterEmailFirst')
    statusMessage.value = ''
    return
  }

  if (resendDisabled.value) {
    return
  }

  clearMessages()
  resendingCode.value = true

  try {
    const response = await postJson('/services/send-login-code/', {
      email: email.value,
      redirect_url: buildCallbackUrl(),
    })

    if (!response.ok) {
      const apiError = await parseApiError(response, t('errorResendFail'))
      if (apiError.code === 'too_many_failed_attempts') startLoginCooldown()
      else if (apiError.code === 'login_send_rate_limited') {
        startResendCountdown(cooldownFromError(apiError))
      } else startResendCountdown()
      if (apiError.code === 'account_inactive') currentStep.value = 'inactive'
      error.value = loginErrorMessage(apiError)
      return
    }

    statusMessage.value = t('resendSuccess')
    // Deliberately NOT clearing the digits: the resent code is the same one, so
    // anything already typed from an earlier email is still correct.
    startResendCountdown()
    startCodeExpiryCountdown()
  } catch (requestError) {
    logApiError('resend-login-code', requestError)
    startResendCountdown()
    error.value = loginErrorMessage(apiErrorFromUnknown(requestError, t('errorNetworkOtp')))
  } finally {
    resendingCode.value = false
  }
}

/*
  Step focus sync.
*/
watch(currentStep, async (step) => {
  await nextTick()

  if (step === 'email') {
    emailInputRef.value?.focus()
  } else {
    otpRefs.value[0]?.focus()
  }
})

watch([isOtpComplete, currentStep], ([complete, step]) => {
  clearOtpAutoSubmitTimer()

  if (step !== 'otp' || !complete || verifyingCode.value || otpErrorActive.value) {
    return
  }

  otpAutoSubmitTimer = setTimeout(() => {
    if (isOtpComplete.value && currentStep.value === 'otp' && !verifyingCode.value) {
      verifyOTP()
    }
  }, 160)
})

/*
  Lifecycle: initial focus.
*/
onMounted(async () => {
  // Magic-link rejections land here as a redirect from the callback view.
  const linkError = Array.isArray(route.query.error) ? route.query.error[0] : route.query.error

  if (linkError === 'account_inactive') {
    currentStep.value = 'inactive'
  } else if (linkError) {
    // A throttled user must wait, not re-request; the cooldown blocks the submit button meanwhile.
    if (linkError === 'too_many_attempts') startLoginCooldown()

    // Guard the lookup: a code like "constructor" would otherwise resolve to an inherited property.
    const messageKey = MAGIC_LINK_ERROR_KEYS[linkError]
    error.value = t(typeof messageKey === 'string' ? messageKey : 'errorMagicLinkFailed')

    // Drop ?error= so a refresh does not replay a stale failure or restart the cooldown.
    router.replace({ name: 'login' })
  }

  ensureCsrfCookie(API_BASE_URL).catch((error) => {
    console.error('Initial CSRF warm-up failed:', error)
  })

  await nextTick()
  emailInputRef.value?.focus()
})

/*
  Lifecycle: cleanup timers.
*/
onBeforeUnmount(() => {
  clearOtpAnimationTimers()
  clearOtpAutoSubmitTimer()
  clearLoginCooldownTimer()

  if (resendTimer) {
    clearInterval(resendTimer)
    resendTimer = null
  }

  if (codeExpiryTimer) {
    clearInterval(codeExpiryTimer)
    codeExpiryTimer = null
  }
})
</script>

<style scoped>
/*
  Module 1: page tokens and global two-column shell.
*/

.login-shell {
  --login-font-primary: Arial, Helvetica, sans-serif;
  --login-font-accent: Arial, Helvetica, sans-serif;
  --emerald-950: #081714;
  --emerald-900: #0d241f;
  --emerald-850: #123129;
  --emerald-800: #173d33;
  --emerald-700: #1f5d4f;
  --emerald-600: #27846d;
  --emerald-500: #2fa486;
  --emerald-400: #69c3aa;
  --mint-50: #f5fbf8;
  --mint-100: #edf7f2;
  --mint-200: #deefe6;
  --mint-300: #cce6d8;
  --stone-900: #10211d;
  --stone-700: #36514a;
  --stone-500: #648178;
  --stone-300: #b6c9c2;
  --white-soft: rgba(255, 255, 255, 0.74);
  --border-soft: rgba(16, 33, 29, 0.1);
  --border-strong: rgba(255, 255, 255, 0.18);
  --shadow-hero: 0 32px 90px rgba(3, 12, 10, 0.45);
  --shadow-card: 0 26px 70px rgba(12, 41, 34, 0.14);
  --shadow-focus: 0 0 0 4px rgba(47, 164, 134, 0.14);
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 100vh;
  min-height: 100dvh;
  font-family: var(--login-font-primary);
  background:
    radial-gradient(circle at top left, rgba(48, 173, 138, 0.16), transparent 24%),
    radial-gradient(circle at bottom right, rgba(23, 93, 79, 0.08), transparent 28%),
    linear-gradient(180deg, #eef7f2 0%, #e7f3ec 40%, #dcece2 100%);
}

.login-shell,
.login-shell * {
  box-sizing: border-box;
}

.login-shell button,
.login-shell input {
  font-family: var(--login-font-primary);
  font-style: normal;
}

.legacy-info-title,
.legacy-custom-content p,
.legacy-info-list,
.auth-subtitle,
.field-help,
.status-message,
.error-message,
.otp-footer-copy p,
.support-row {
  font-family: var(--login-font-accent);
  font-style: normal;
}

/*
  Module 2: left information pane.
*/
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

/*
  Module 3: hero foreground layout, brand block, and cards.
*/

.auth-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 22px;
  overflow: hidden;
}

.auth-logo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.auth-kicker {
  font-size: 1.2rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.auth-card::before {
  content: '';
  position: absolute;
  inset: 1px;
  border-radius: inherit;
  pointer-events: none;
}

.auth-title {
  margin: 0;
  letter-spacing: -0.02em;
}

.meta-chip,
.top-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 700;
  white-space: nowrap;
}

/*
  Module 4: shared interaction states.
*/

.primary-button:hover,
.primary-button:focus-visible,
.secondary-button:hover,
.secondary-button:focus-visible,
.text-link:hover,
.text-link:focus-visible,
.password-toggle:hover,
.password-toggle:focus-visible {
  transform: translateY(-1px);
}

.field-input:focus-visible,
.primary-button:focus-visible,
.secondary-button:focus-visible,
.text-link:focus-visible,
.otp-input:focus-visible,
.password-toggle:focus-visible {
  outline: none;
  box-shadow: var(--shadow-focus);
}

/*
  Module 5: shared clickable controls.
*/

.primary-button,
.secondary-button,
.text-link,
.password-toggle {
  cursor: pointer;
  transition:
    transform 0.22s ease,
    box-shadow 0.22s ease,
    background 0.22s ease,
    border-color 0.22s ease,
    color 0.22s ease;
}

/*
  Module 6: auth pane shell, top bar, and card container.
*/
.auth-pane {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  min-height: 100dvh;
  padding: 3rem 2rem;
}

.auth-shell {
  position: relative;
  z-index: 1;
  width: min(100%, 420px);
  display: grid;
  justify-items: center;
  gap: 10px;
}

.top-badges {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.top-badge {
  color: var(--emerald-700);
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(31, 93, 79, 0.08);
  box-shadow: 0 8px 24px rgba(12, 41, 34, 0.06);
}

.auth-card {
  position: relative;
  overflow: hidden;
  width: min(100%, 420px);
  border-radius: 26px;
  padding: 2rem;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 251, 248, 0.94));
  border: 1px solid rgba(255, 255, 255, 0.78);
  box-shadow: var(--shadow-card);
}

.auth-card::before {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.76), rgba(255, 255, 255, 0));
}

.auth-card-glow {
  position: absolute;
  inset: 0 auto auto 0;
  width: 100%;
  height: 160px;
  background: radial-gradient(circle at top left, rgba(47, 164, 134, 0.16), transparent 58%);
  pointer-events: none;
}

/*
  Module 7: auth progress and shared header presentation.
*/
.auth-progress {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 14px;
}

.progress-item {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--stone-500);
}

.progress-item.active {
  color: var(--stone-900);
}

.progress-item.current .progress-dot {
  box-shadow: 0 12px 26px rgba(31, 93, 79, 0.18);
}

.progress-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  font-size: 0.9rem;
  font-weight: 800;
  background: rgba(31, 93, 79, 0.08);
  color: inherit;
}

.progress-item.active .progress-dot {
  background: linear-gradient(135deg, var(--emerald-700), var(--emerald-500));
  color: #fff;
}

.progress-label {
  font-size: 0.88rem;
  font-weight: 700;
}

.progress-line {
  flex: 1;
  height: 2px;
  margin: 0 10px;
  border-radius: 999px;
  background: rgba(16, 33, 29, 0.08);
}

.progress-line.active {
  background: linear-gradient(90deg, var(--emerald-700), var(--emerald-400));
}

.step-panel {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 440px;
  margin: 0 auto;
  display: grid;
  gap: 14px;
}

.auth-header {
  display: grid;
  justify-items: center;
  gap: 8px;
  text-align: center;
}

.auth-header--compact {
  gap: 12px;
}

.auth-logo-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.auth-logo {
  width: 52px;
  height: 52px;
  background: linear-gradient(180deg, rgba(39, 132, 109, 0.12), rgba(39, 132, 109, 0.04));
  border: 1px solid rgba(39, 132, 109, 0.1);
}

.auth-logo--small {
  width: 46px;
  height: 46px;
}

.auth-logo-copy {
  display: grid;
  gap: 6px;
}

.auth-kicker {
  color: var(--emerald-700);
}

.auth-title {
  font-size: clamp(1.55rem, 2.6vw, 2rem);
  color: var(--stone-900);
}

.auth-subtitle {
  margin: 0;
  color: var(--stone-700);
  line-height: 1.45;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.meta-row--stack {
  justify-content: center;
  align-items: center;
}

.meta-chip {
  color: var(--stone-900);
  border: 1px solid rgba(16, 33, 29, 0.08);
  background: rgba(39, 132, 109, 0.08);
}

.meta-chip--neutral {
  background: rgba(16, 33, 29, 0.05);
  color: var(--stone-700);
}

/*
  Module 8: form fields and action buttons.
*/
.auth-form {
  width: 100%;
  display: grid;
  gap: 10px;
}

.login-mode-switch {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  padding: 6px;
  border: 1px solid rgba(16, 33, 29, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.62);
}

.login-mode-button {
  min-height: 38px;
  border: 0;
  border-radius: 14px;
  background: transparent;
  color: var(--stone-700);
  font-size: 0.9rem;
  font-weight: 800;
  cursor: pointer;
  transition:
    background 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease;
}

.login-mode-button.active {
  color: #fff;
  background: linear-gradient(135deg, var(--emerald-700), var(--emerald-500));
  box-shadow: 0 12px 22px rgba(31, 93, 79, 0.18);
}

.login-mode-button:focus-visible {
  outline: 3px solid rgba(72, 165, 140, 0.22);
  outline-offset: 2px;
}

.field-block {
  display: grid;
  gap: 6px;
}

.password-field-slot {
  transition: opacity 0.18s ease;
}

.password-field-slot.is-reserved-hidden {
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
}

.forgot-password-row {
  display: flex;
  justify-content: flex-start;
  margin-top: 4px;
}

.forgot-password-link {
  color: var(--emerald-700);
  font-size: 0.9rem;
  font-weight: 800;
  text-decoration: none;
}

.forgot-password-link:hover,
.forgot-password-link:focus-visible {
  text-decoration: underline;
}

.registration-demo-link {
  margin: 4px 0 0;
  color: var(--stone-500);
  font-size: 0.9rem;
  text-align: center;
}

.registration-demo-link a {
  color: var(--emerald-700);
  font-weight: 800;
  text-decoration: none;
}

.registration-demo-link a:hover,
.registration-demo-link a:focus-visible {
  text-decoration: underline;
  text-underline-offset: 3px;
}

.field-label {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--stone-900);
}

.field-shell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 50px;
  padding: 0 16px;
  border-radius: 18px;
  border: 1px solid var(--border-soft);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.42);
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.field-shell:focus-within {
  border-color: rgba(39, 132, 109, 0.38);
  box-shadow: var(--shadow-focus);
  background: #fff;
}

.field-shell.is-error {
  border-color: rgba(210, 75, 75, 0.34);
}

.field-input {
  flex: 1;
  min-width: 0;
  width: 100%;
  border: 0;
  background: transparent;
  font-size: 1rem;
  color: var(--stone-900);
}

.password-toggle {
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
}

.password-toggle:hover,
.password-toggle:focus-visible {
  color: var(--emerald-700);
  background: rgba(39, 132, 109, 0.14);
}

.password-toggle:disabled {
  cursor: not-allowed;
  opacity: 0.45;
  transform: none;
}

.password-toggle svg {
  width: 19px;
  height: 19px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.9;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.field-input::placeholder {
  color: rgba(54, 81, 74, 0.54);
}

.field-help {
  color: var(--stone-500);
  line-height: 1.35;
}

.primary-button,
.secondary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 48px;
  padding: 0 18px;
  border-radius: 18px;
  font-size: 0.98rem;
  font-weight: 800;
}

.primary-button {
  border: 0;
  color: #fff;
  background: linear-gradient(135deg, var(--emerald-700), var(--emerald-500));
  box-shadow: 0 18px 28px rgba(31, 93, 79, 0.2);
}

.primary-button:disabled,
.secondary-button:disabled,
.text-link:disabled {
  cursor: not-allowed;
  transform: none;
  opacity: 0.6;
  box-shadow: none;
}

.secondary-button {
  border: 1px solid rgba(16, 33, 29, 0.1);
  color: var(--stone-700);
  background: rgba(255, 255, 255, 0.74);
}

.text-link {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--emerald-700);
  font-size: 0.9rem;
  font-weight: 800;
}

.button-spinner {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  animation: spin 0.8s linear infinite;
}

/*
  Module 9: OTP inputs, feedback blocks, and support row.
*/
.otp-footer-copy p,
.support-row {
  margin: 0;
  color: var(--stone-700);
  line-height: 1.68;
}

.otp-footer-copy p + p {
  margin-top: 4px;
}

.otp-expired-note {
  color: #b3261e;
  font-weight: 600;
}

.otp-box {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.otp-input {
  min-width: 0;
  height: 54px;
  border-radius: 18px;
  border: 1px solid rgba(16, 33, 29, 0.1);
  background: rgba(255, 255, 255, 0.92);
  text-align: center;
  font-size: 1.35rem;
  font-weight: 800;
  color: var(--stone-900);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.44);
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.otp-input:focus {
  border-color: rgba(39, 132, 109, 0.38);
  transform: translateY(-1px);
}

.otp-input-error,
.otp-box.has-error .otp-input {
  border-color: rgba(210, 75, 75, 0.34);
  background: rgba(255, 245, 245, 0.94);
}

.otp-box.is-complete .otp-input {
  border-color: rgba(39, 132, 109, 0.22);
  box-shadow:
    0 10px 22px rgba(31, 93, 79, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.44);
}

.otp-box.shaking {
  animation: shake 0.42s ease;
}

.otp-action-stack {
  display: grid;
  gap: 12px;
}

.otp-secondary-actions {
  display: flex;
  justify-content: center;
}

.status-message,
.error-message {
  margin: 0;
  padding: 13px 15px;
  border-radius: 16px;
  font-size: 0.92rem;
  line-height: 1.55;
}

.status-message {
  color: var(--emerald-700);
  border: 1px solid rgba(39, 132, 109, 0.12);
  background: rgba(39, 132, 109, 0.08);
}

.error-message {
  color: #b33d3d;
  border: 1px solid rgba(210, 75, 75, 0.18);
  background: rgba(255, 235, 235, 0.76);
}

.support-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.support-row a {
  color: var(--emerald-700);
  font-weight: 800;
  text-decoration: none;
}

.support-row a:hover,
.support-row a:focus-visible {
  text-decoration: underline;
}

/* Address is long enough to overflow the card on narrow screens. */
.support-email {
  overflow-wrap: anywhere;
}

/*
  Module 10: role theme utilities and transition effects.
*/

.content-fade-enter-active,
.content-fade-leave-active,
.message-slide-enter-active,
.message-slide-leave-active {
  transition:
    opacity 0.24s ease,
    transform 0.24s ease;
}

.content-fade-enter-from,
.content-fade-leave-to,
.message-slide-enter-from,
.message-slide-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes shake {
  0%,
  100% {
    transform: translateX(0);
  }
  25% {
    transform: translateX(-6px);
  }
  50% {
    transform: translateX(6px);
  }
  75% {
    transform: translateX(-4px);
  }
}

/*
  Module 11: responsive behavior.
*/
@media (max-width: 900px) {
  .login-shell {
    grid-template-columns: 1fr;
  }

  .hero-pane {
    min-height: auto;
  }

  .legacy-left-pane {
    border-right: 0;
    border-bottom: 1px solid var(--border-light, rgba(16, 33, 29, 0.1));
  }

  .auth-pane {
    min-height: auto;
    padding-top: 0;
  }
}

@media (min-width: 901px) {
  .login-shell {
    height: 100vh;
    height: 100dvh;
    overflow: hidden;
  }

  .hero-pane,
  .auth-pane {
    min-height: 0;
    height: 100%;
  }
}

@media (max-width: 760px) {
  .legacy-left-pane,
  .auth-pane {
    padding: 20px;
  }

  .meta-row--stack {
    flex-direction: column;
    align-items: center;
  }

  .auth-card {
    padding: 22px 18px;
    border-radius: 24px;
  }

  .otp-box {
    /* grid-template-columns: repeat(3, minmax(0, 1fr)); */
  }
}

/*
  Module 12: reduced-motion accessibility support.
*/
@media (prefers-reduced-motion: reduce) {
  .button-spinner,
  .otp-box.shaking,
  .content-fade-enter-active,
  .content-fade-leave-active,
  .message-slide-enter-active,
  .message-slide-leave-active,
  .primary-button,
  .secondary-button,
  .text-link,
  .otp-input {
    animation: none !important;
    transition: none !important;
  }
}

/*
  Module 13: immersive motion polish and premium interaction upgrades.
*/

.login-shell {
  --pointer-x: 50%;
  --pointer-y: 32%;
  isolation: isolate;
}

.login-shell::before,
.login-shell::after {
  content: '';
  position: fixed;
  inset: auto;
  pointer-events: none;
  z-index: 0;
  border-radius: 50%;
  filter: blur(48px);
  transition:
    transform 0.22s ease,
    opacity 0.22s ease;
}

.login-shell::before {
  top: calc(var(--pointer-y) * 0.18);
  left: calc(var(--pointer-x) * 0.16);
  width: 280px;
  height: 280px;
  background: radial-gradient(circle, rgba(103, 228, 193, 0.24), transparent 72%);
  transform: translate(-50%, -50%);
  opacity: 0;
}

.login-shell::after {
  right: 5%;
  bottom: 4%;
  width: 360px;
  height: 360px;
  background: radial-gradient(circle, rgba(20, 94, 79, 0.16), transparent 72%);
  opacity: 0.5;
}

.auth-card {
  backdrop-filter: none;
}

.auth-shell {
  position: relative;
  z-index: 1;
}

.auth-card {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 251, 248, 0.92)),
    radial-gradient(circle at top left, rgba(115, 232, 193, 0.12), transparent 34%);
}

.auth-card-glow {
  height: 240px;
  background:
    radial-gradient(circle at top left, rgba(47, 164, 134, 0.18), transparent 54%),
    radial-gradient(circle at top right, rgba(103, 228, 193, 0.12), transparent 36%);
}

.top-badge {
  backdrop-filter: none;
}

.primary-button::before,
.secondary-button::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(120deg, transparent 18%, rgba(255, 255, 255, 0.28), transparent 72%);
  opacity: 0;
  transition: opacity 0.22s ease;
}

.primary-button:hover::before,
.secondary-button:hover::before {
  opacity: 1;
}

.progress-dot {
  position: relative;
  overflow: hidden;
}

.progress-dot::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.36), transparent 52%);
  opacity: 0.78;
}

.field-shell {
  position: relative;
  overflow: hidden;
}

.field-shell::after {
  content: '';
  position: absolute;
  inset: auto 12px 0 12px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(47, 164, 134, 0.4), transparent);
  opacity: 0;
  transform: translateY(4px);
  transition:
    opacity 0.22s ease,
    transform 0.22s ease;
}

.field-shell:focus-within::after {
  opacity: 1;
  transform: translateY(0);
}

.primary-button,
.secondary-button {
  position: relative;
  overflow: hidden;
}

.primary-button {
  background:
    linear-gradient(135deg, rgba(18, 96, 80, 1), rgba(47, 164, 134, 0.96)),
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.14), transparent 28%);
  box-shadow:
    0 18px 36px rgba(31, 93, 79, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.18);
}

.primary-button:hover,
.primary-button:focus-visible {
  box-shadow:
    0 24px 42px rgba(31, 93, 79, 0.28),
    inset 0 1px 0 rgba(255, 255, 255, 0.18);
}

.secondary-button {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 251, 249, 0.92)),
    radial-gradient(circle at top left, rgba(47, 164, 134, 0.08), transparent 32%);
}

.otp-box {
  position: relative;
}

.otp-input {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(245, 249, 247, 0.96)),
    radial-gradient(circle at top left, rgba(47, 164, 134, 0.08), transparent 34%);
}

.otp-input:hover,
.otp-input:focus-visible {
  transform: translateY(-2px);
  box-shadow:
    0 12px 26px rgba(31, 93, 79, 0.14),
    var(--shadow-focus);
}

.status-message,
.error-message {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  padding: 12px 14px;
}

.status-message::before,
.error-message::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(120deg, transparent, rgba(255, 255, 255, 0.18), transparent);
  opacity: 0.4;
}

.support-row {
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(16, 33, 29, 0.03);
  border: 1px solid rgba(16, 33, 29, 0.05);
}

@keyframes ambientFloatA {
  0%,
  100% {
    transform: translate3d(0, 0, 0);
  }
  50% {
    transform: translate3d(18px, -14px, 0);
  }
}

@keyframes ambientFloatB {
  0%,
  100% {
    transform: translate3d(0, 0, 0);
  }
  50% {
    transform: translate3d(-18px, 16px, 0);
  }
}

.shell-aurora {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}

.shell-aurora-orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(18px);
  opacity: 0.78;
  mix-blend-mode: screen;
}

.shell-aurora-orb--one {
  top: 6%;
  left: -3%;
  width: 320px;
  height: 320px;
  background: radial-gradient(
    circle,
    rgba(126, 255, 223, 0.32),
    rgba(74, 209, 176, 0.08) 58%,
    transparent 76%
  );
}

.shell-aurora-orb--two {
  right: 10%;
  top: 12%;
  width: 260px;
  height: 260px;
  background: radial-gradient(
    circle,
    rgba(193, 224, 255, 0.22),
    rgba(116, 184, 255, 0.06) 54%,
    transparent 76%
  );
}

.shell-aurora-orb--three {
  right: -4%;
  bottom: 2%;
  width: 360px;
  height: 360px;
  background: radial-gradient(
    circle,
    rgba(124, 255, 217, 0.18),
    rgba(32, 124, 103, 0.06) 52%,
    transparent 78%
  );
}

.shell-mesh {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.06) 1px, transparent 1px);
  background-size: 28px 28px;
  mask-image: radial-gradient(circle at center, rgba(0, 0, 0, 0.64), transparent 82%);
  opacity: 0.18;
}

.hero-pane,
.auth-pane {
  position: relative;
  z-index: 1;
}

.auth-card,
.field-shell {
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.auth-card {
  isolation: isolate;
}

.auth-card::after {
  content: '';
  position: absolute;
  inset: 10px;
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.44);
  pointer-events: none;
}

.auth-card-noise {
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

.auth-progress,
.step-panel {
  position: relative;
  z-index: 1;
}

.progress-item {
  transition:
    transform 0.24s ease,
    color 0.24s ease;
}

.progress-item.current {
  transform: translateY(-1px);
}

.field-shell {
  gap: 12px;
  min-height: 50px;
  padding: 0 18px 0 16px;
}

.field-input {
  letter-spacing: 0.01em;
}

.primary-button,
.secondary-button {
  min-height: 48px;
  border-radius: 18px;
}

.primary-button:active,
.secondary-button:active {
  transform: translateY(0) scale(0.99);
}

.otp-input {
  backdrop-filter: none;
}

.otp-input-filled {
  border-color: rgba(39, 132, 109, 0.2);
  box-shadow:
    0 10px 22px rgba(31, 93, 79, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.5);
}

.status-message,
.error-message,
.support-row {
  backdrop-filter: none;
}

.support-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

@media (max-width: 760px) {
  .shell-aurora-orb--one {
    width: 240px;
    height: 240px;
  }

  .shell-aurora-orb--two {
    width: 200px;
    height: 200px;
  }

  .shell-aurora-orb--three {
    width: 260px;
    height: 260px;
  }

  .support-row {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-shell::before,
  .login-shell::after,
  .primary-button::before,
  .secondary-button::before,
  .shell-aurora-orb,
  .auth-card-glow {
    animation: none !important;
    transition: none !important;
    transform: none !important;
  }
}
</style>
