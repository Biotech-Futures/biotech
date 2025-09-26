import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// Optional: restore login state from local storage on first load
import { useAuthStore } from './stores/auth'
const auth = useAuthStore()
auth.hydrate()

app.mount('#app')
