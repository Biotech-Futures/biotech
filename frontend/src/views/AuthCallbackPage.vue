<template>
  <div class="callback-container">
    <div class="callback-content">
      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
        <p>Authenticating...</p>
      </div>

      <div v-else-if="error" class="error-state">
        <div class="error-icon">⚠️</div>
        <h2>Authentication Failed</h2>
        <p>{{ error }}</p>
        <button @click="redirectToLogin" class="btn btn-primary">
          Back to Login
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const success = route.query.success
    const email = route.query.email

    if (success !== 'true') {
      error.value = 'Invalid authentication link. Please try logging in again.'
      setTimeout(redirectToLogin, 3000)
      return
    }

    const userData = await auth.fetchUserData()

    if (userData) {
      await router.push('/dashboard')
      return
    }

    error.value = email
      ? `Authentication succeeded for ${email}, but the user session could not be loaded. Please try again.`
      : 'Authentication succeeded, but the user session could not be loaded. Please try again.'

    setTimeout(redirectToLogin, 3000)
  } catch (err) {
    console.error('Authentication callback failed:', err)
    error.value = 'Authentication failed. Please try logging in again.'
    setTimeout(redirectToLogin, 3000)
  } finally {
    loading.value = false
  }
})

const redirectToLogin = () => {
  router.push('/login')
}
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

.error-state {
  padding: 1rem 0;
}

.error-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.error-state h2 {
  color: var(--charcoal);
  margin-bottom: 1rem;
}

.error-state p {
  color: #6c757d;
  margin-bottom: 2rem;
}

.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  text-decoration: none;
  display: inline-block;
}

.btn-primary {
  background: var(--dark-green);
  color: white;
}

.btn-primary:hover {
  background: var(--green);
}
</style>