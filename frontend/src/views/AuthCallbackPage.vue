<template>
  <div class="callback-container">
    <div class="callback-content">
      <!--
        The confirm step keeps the magic link safe from email scanners.
        The code is only spent after a real user presses the button.
      -->
      <div v-if="stage === 'confirm'" class="confirm-state">
        <div class="brand">
          <img :src="btfLogo" alt="BIOTech Connect" class="brand-logo" />
          <span class="brand-name">BIOTech Connect</span>
        </div>

        <h1 class="confirm-title">{{ t('confirmTitle') }}</h1>

        <p class="confirm-body">
          {{ t('confirmBody') }}
        </p>

        <div v-if="maskedEmail" class="email-box">
          {{ maskedEmail }}
        </div>

        <button
          type="button"
          class="confirm-button"
          :disabled="submitting"
          @click="completeSignIn"
        >
          {{ submitting ? t('confirmWorking') : t('confirmAction') }}
        </button>

        <p v-if="errorMessage" class="confirm-error" role="alert">
          {{ errorMessage }}
        </p>
      </div>

      <div v-else class="loading-state">
        <div class="spinner"></div>
        <p>{{ t('confirmWorking') }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import btfLogo from '@/assets/btf-logo.png'
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
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  box-sizing: border-box;

  background:
    radial-gradient(circle at 80% 20%, rgba(129, 214, 184, 0.28), transparent 32%),
    radial-gradient(circle at 20% 80%, rgba(195, 235, 202, 0.35), transparent 30%),
    #f3faf6;

  font-family:
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    Roboto,
    Helvetica,
    Arial,
    sans-serif;
}

.callback-content {
  width: 100%;
  max-width: 500px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(0, 114, 83, 0.12);
  border-radius: 24px;
  padding: 3rem;
  box-sizing: border-box;
  box-shadow: 0 20px 50px rgba(20, 79, 59, 0.12);
}

.confirm-state {
  text-align: center;
}

.brand {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.8rem;
  margin-bottom: 2rem;
}

.brand-logo {
  width: 54px;
  height: 54px;
  object-fit: contain;
}

.brand-name {
  color: #164c43;
  font-size: 1.45rem;
  font-weight: 700;
}

.confirm-title {
  margin: 0 0 0.8rem;
  color: #164c43;
  font-size: 2rem;
  line-height: 1.2;
  font-weight: 750;
}

.confirm-body {
  margin: 0 auto 1.25rem;
  max-width: 360px;
  color: #536660;
  font-size: 1rem;
  line-height: 1.65;
}

.email-box {
  margin: 0 0 1.7rem;
  padding: 0.9rem 1rem;
  background: #f4faf7;
  border: 1px solid #d6e8df;
  border-radius: 12px;
  color: #183d35;
  font-weight: 700;
  font-size: 1rem;
}

.confirm-button {
  width: 100%;
  padding: 1rem 1.25rem;
  border: none;
  border-radius: 14px;
  background: linear-gradient(135deg, #17785f, #329b7c);
  color: #ffffff;
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease;
  box-shadow: 0 8px 18px rgba(23, 120, 95, 0.2);
}

.confirm-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(23, 120, 95, 0.26);
}

.confirm-button:disabled {
  opacity: 0.65;
  cursor: default;
  transform: none;
}

.confirm-error {
  margin: 1rem 0 0;
  padding: 0.8rem 1rem;
  border-radius: 10px;
  background: #fff2f1;
  color: #b3261e;
  font-size: 0.9rem;
}

.loading-state {
  text-align: center;
  padding: 2rem 0;
  color: #536660;
}

.spinner {
  width: 46px;
  height: 46px;
  margin: 0 auto 1rem;
  border: 4px solid #dcece5;
  border-top-color: #17785f;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 600px) {
  .callback-container {
    padding: 1rem;
  }

  .callback-content {
    padding: 2rem 1.4rem;
    border-radius: 18px;
  }

  .brand-logo {
    width: 46px;
    height: 46px;
  }

  .brand-name {
    font-size: 1.25rem;
  }

  .confirm-title {
    font-size: 1.65rem;
  }
}
</style>