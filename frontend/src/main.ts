import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/main.css'
import { useAuthStore } from './stores/auth'
import { BRAND_CONNECT } from './constants/brand'
import { configuredRegistrationGateway } from './registration/httpRegistrationGateway'
import { REGISTRATION_GATEWAY_KEY } from './registration/registrationGateway'

document.title = BRAND_CONNECT

const bootstrap = async () => {
  const app = createApp(App)
  const pinia = createPinia()

  app.use(pinia)
  const registrationGateway = configuredRegistrationGateway(
    import.meta.env.VITE_REGISTRATION_API_URL,
  )
  if (registrationGateway) app.provide(REGISTRATION_GATEWAY_KEY, registrationGateway)

  const auth = useAuthStore()
  await auth.initializeAuth()

  app.use(router)
  await router.isReady()

  app.mount('#app')
}

bootstrap()
