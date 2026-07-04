import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/main.css'
import { useAuthStore } from './stores/auth'
import { BRAND_CONNECT } from './constants/brand'

document.title = BRAND_CONNECT

const bootstrap = async () => {
  const app = createApp(App)
  const pinia = createPinia()

  app.use(pinia)

  const auth = useAuthStore()
  await auth.initializeAuth()

  app.use(router)
  await router.isReady()

  app.mount('#app')
}

bootstrap()
