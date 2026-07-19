<template>
  <div class="callback-container">
    <div class="callback-content">
      <div class="loading-state">
        <div class="spinner"></div>
        <p>Authenticating...</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import type { LocationQueryValue } from 'vue-router'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { redirectAfterLogin } from '@/utils/postLoginRedirect'
import { resetCsrfToken, setCsrfToken } from '@/utils/csrf'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const firstQueryValue = (value: LocationQueryValue | LocationQueryValue[]) =>
  Array.isArray(value) ? value[0] : value

// Hand every rejection to the login page, which explains it in the user's language.
const failToLogin = (error: string) => router.replace({ name: 'login', query: { error } })

onMounted(async () => {
  try {
    const callbackError = firstQueryValue(route.query.error)

    if (callbackError) {
      await failToLogin(callbackError)
      return
    }

    if (firstQueryValue(route.query.success) !== 'true') {
      await failToLogin('callback_failed')
      return
    }

    if (!setCsrfToken(firstQueryValue(route.query.csrfToken))) {
      resetCsrfToken()
    }

    if (await auth.fetchUserData()) {
      await redirectAfterLogin(auth, router)
      return
    }

    await failToLogin('session_load_failed')
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
