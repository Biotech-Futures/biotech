import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/styles.css' // 你的全局样式（按需）

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)

// 可选：首屏时把本地存储里的登录态恢复
import { useAuthStore } from './stores/auth'
const auth = useAuthStore()
auth.hydrate()

app.mount('#app')
