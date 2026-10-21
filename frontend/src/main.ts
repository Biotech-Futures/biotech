import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/btf-tokens.css'
import './assets/main.css'
import './assets/analytics-theme.css'
import { useAuthStore } from './stores/auth'
import { BRAND_CONNECT } from './constants/brand'
import { REGISTRATION_GATEWAY_KEY } from './registration/registrationGateway'
import { configuredRegistrationGateway } from './registration/httpRegistrationGateway'

document.title = BRAND_CONNECT

const bootstrap = async () => {
  const app = createApp(App)
  const pinia = createPinia()

  app.use(pinia)
  app.provide(
    REGISTRATION_GATEWAY_KEY,
    configuredRegistrationGateway(
      import.meta.env.VITE_REGISTRATION_API_URL,
      // As everywhere else: the backend's own address when none is set (locally).
      import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
    ),
  )

  const auth = useAuthStore()
  await auth.initializeAuth()

  app.use(router)
  await router.isReady()

  app.mount('#app')
}

bootstrap()
