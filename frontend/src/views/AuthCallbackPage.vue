<template>
  <div class="callback-container">
    <div class="callback-content">
      <!--
        The confirm step is what makes the login link safe: mail scanners follow
        the link but never press a button, so the code is only spent by a person.
      -->
      <div v-if="stage === 'confirm'" class="confirm-state">
        <h1 class="confirm-title">{{ t('confirmTitle') }}</h1>
        <p class="confirm-body">{{ t('confirmBody') }}</p>
        <p v-if="maskedEmail" class="confirm-email">{{ maskedEmail }}</p>

        <button
          type="button"
          class="confirm-button"
          :disabled="submitting"
          @click="completeSignIn"
        >
          {{ submitting ? t('confirmWorking') : t('confirmAction') }}
        </button>

        <p v-if="errorMessage" class="confirm-error" role="alert">{{ errorMessage }}</p>
      </div>

      <div v-else class="loading-state">
        <div class="spinner"></div>
        <p>{{ t('confirmWorking') }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { LocationQueryValue } from 'vue-router'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { redirectAfterLogin } from '@/utils/postLoginRedirect'
import { buildSessionHeaders, ensureCsrfCookie, resetCsrfToken, setCsrfToken } from '@/utils/csrf'
import { apiErrorFromResponse, apiErrorFromUnknown, logApiError } from '@/utils/apiError'
import { maskEmail } from '@/utils/string'
import { LOGIN_LANGUAGE_KEY, safeLocalStorageGet } from '@/utils/storage'
import { LOGIN_MESSAGES } from '@/data/login_language'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const stage = ref<'working' | 'confirm'>('working')
const submitting = ref(false)
const errorMessage = ref('')
const email = ref('')
const code = ref('')

const locale = safeLocalStorageGet(LOGIN_LANGUAGE_KEY, 'en') || 'en'
const messages = LOGIN_MESSAGES as unknown as Record<string, Record<string, string>>
const t = (key: string) => messages[locale]?.[key] || messages.en?.[key] || key

const maskedEmail = computed(() => (email.value ? maskEmail(email.value) : ''))

const firstQueryValue = (value: LocationQueryValue | LocationQueryValue[]) =>
  Array.isArray(value) ? value[0] : value

// Hand every rejection to the login page, which explains it in the user's language.
const failToLogin = (error: string) => router.replace({ name: 'login', query: { error } })

const completeSignIn = async () => {
  if (submitting.value) return

  submitting.value = true
  errorMessage.value = ''

  try {
    if (!(await ensureCsrfCookie(API_BASE_URL))) {
      errorMessage.value = t('errorCsrfFailed')
      return
    }

    const response = await fetch(`${API_BASE_URL}/services/verify-login-code/`, {
      method: 'POST',
      headers: buildSessionHeaders({ includeCSRF: true }),
      credentials: 'include',
      body: JSON.stringify({ email: email.value, code: code.value }),
    })

    if (!response.ok) {
      const apiError = await apiErrorFromResponse(response, t('errorInvalidCode'))
      logApiError('magic-link-confirm', apiError)
      await failToLogin(
        apiError.code === 'account_inactive' ? 'account_inactive' : 'invalid_or_expired_code',
      )
      return
    }

    const data = await response.json().catch(() => null)
    if (!setCsrfToken(data?.csrfToken)) {
      resetCsrfToken()
    }

    if (await auth.fetchUserData()) {
      await redirectAfterLogin(auth, router)
      return
    }

    await failToLogin('session_load_failed')
  } catch (err) {
    logApiError('magic-link-confirm', apiErrorFromUnknown(err))
    errorMessage.value = t('errorNetworkOtp')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    const callbackError = firstQueryValue(route.query.error)
    if (callbackError) {
      await failToLogin(callbackError)
      return
    }

    const queryEmail = firstQueryValue(route.query.email)
    const queryCode = firstQueryValue(route.query.code)

    if (queryEmail && queryCode) {
      email.value = queryEmail
      code.value = queryCode
      stage.value = 'confirm'
      return
    }

    // Legacy shape: the backend used to sign the user in before redirecting.
    if (firstQueryValue(route.query.success) === 'true') {
      if (!setCsrfToken(firstQueryValue(route.query.csrfToken))) {
        resetCsrfToken()
      }

      if (await auth.fetchUserData()) {
        await redirectAfterLogin(auth, router)
        return
      }

      await failToLogin('session_load_failed')
      return
    }

    await failToLogin('callback_failed')
  } catch (err) {
    console.error('Authentication callback failed:', err)
    await failToLogin('callback_failed')
  }
})
</script>

<style scoped>
.callback-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--bg-light);
}

.callback-content {
  text-align: center;
  padding: 2rem;
  background: var(--white);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  max-width: 400px;
  width: 100%;
}

.loading-state {
  padding: 2rem 0;
}

.confirm-state {
  padding: 1rem 0;
}

.confirm-title {
  margin: 0 0 0.75rem;
  font-size: 1.35rem;
  color: var(--dark-green, #1a2e23);
}

.confirm-body {
  margin: 0 0 0.5rem;
  color: #3d4b43;
  line-height: 1.6;
}

.confirm-email {
  margin: 0 0 1.25rem;
  font-weight: 600;
  color: #1a2e23;
}

.confirm-button {
  width: 100%;
  padding: 0.85rem 1rem;
  border: 1px solid var(--dark-green, #007253);
  border-radius: 6px;
  background: #c3ebca;
  color: #007253;
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
}

.confirm-button:disabled {
  opacity: 0.65;
  cursor: default;
}

.confirm-error {
  margin: 0.85rem 0 0;
  color: #b3261e;
}

.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid var(--border-light);
  border-top: 4px solid var(--dark-green);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
