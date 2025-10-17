<template>
  <div class="split-login">
    <!-- 左侧：可自定义信息区 -->
    <section class="left-pane">
      <div class="left-inner">
        <div class="brand">
          <div class="logo-icon"><img :src="logo" alt="BIOTech Futures" /></div>
          <h1 class="brand-title">BIOTech Futures Hub</h1>
        </div>

        <!-- 这块内容完全可改：可以直接写 HTML，或未来从接口拿 -->
        <div class="custom-content" v-html="leftHtml"></div>

        <div class="links">
          <!-- 示例：主站链接（替换成你们的真实网址） -->
          <a
            class="btn btn-secondary"
            href="https://example.org"
            target="_blank"
            rel="noopener"
          >
            Visit Main Website
          </a>
        </div>
      </div>
    </section>

    <!-- 右侧：登录面板（纯色背景） -->
    <section class="right-pane">
      <div class="login-card fade-in">
        <div class="login-logo" style="margin-bottom: 1rem;">
          <div class="login-logo-icon"><img :src="logo" alt="BIOTech Futures" /></div>
          <h2 class="login-title">Sign in</h2>
          <p class="login-subtitle">Welcome! Please sign in to continue.</p>
        </div>

        <form @submit.prevent="handleLogin">
          <div class="form-group">
            <label class="form-label">Email Address</label>
            <input
              type="email"
              v-model="email"
              class="form-control"
              placeholder="Enter your email"
              required
            />
            <small class="form-text">We’ll send you a magic link to sign in</small>
          </div>
          <button type="submit" class="btn btn-primary btn-lg" style="width: 100%;">
            <span v-if="!loading">Send Login Link</span>
            <span v-else class="loading"></span>
          </button>
        </form>

        <div v-if="showOTP" class="otp-section">
          <p style="text-align: center; margin: 1.5rem 0;">
            Click the link in your email to sign in directly, or enter your 6-digit code below
          </p>
          <div class="otp-container">
            <input
              v-for="i in 6"
              :key="i"
              type="text"
              maxlength="1"
              class="otp-input"
              @input="handleOTPInput($event, i)"
            />
          </div>
          <button @click="verifyOTP" class="btn btn-primary" style="width: 100%; margin-top: 1rem;">
            Verify Code
          </button>

          <div style="text-align: center; margin-top: 0.75rem;">
            <button class="linklike" type="button" @click="resendCode">Resend Code</button>
          </div>

          <p v-if="error" style="color:#dc3545; text-align:center; margin-top:0.75rem;">{{ error }}</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import logo from '@/assets/btf-logo.png'

const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const loading = ref(false)
const showOTP = ref(false)
const error = ref('')

/**
 * 左侧介绍区可自定义的 HTML（示例占位）
 * 你可以在这里自由编辑富文本内容（受信源可用 v-html）
 * 若未来从后端/配置拉取，也可以把它换成接口数据
 */
const leftHtml = ref(`
  <h2 class="info-title">About the BIOTech Futures Challenge</h2>
  <p>
    The BIOTech Futures Challenge empowers students to tackle real-world problems
    through innovation, mentorship, and interdisciplinary collaboration.
  </p>
  <ul class="info-list">
    <li>Learn from mentors across academia & industry</li>
    <li>Develop practical solutions and prototypes</li>
    <li>Present at showcase events and win awards</li>
  </ul>
  <p>
    Explore key dates, eligibility, submission guidelines, and more on our website.
  </p>
`)

const handleLogin = () => {
  error.value = ''
  loading.value = true
  setTimeout(() => {
    loading.value = false
    showOTP.value = true
  }, 600)
}

const handleOTPInput = (e, index) => {
  if (e.target.value && index < 6) {
    const inputs = e.target.parentElement.querySelectorAll('input')
    inputs[index]?.focus()
  }
}

// 点击 Verify 时真正“落地登录”
const verifyOTP = () => {
  try {
    auth.loginByEmail(email.value) // 从 mockUsers 里找用户并入库（Pinia + localStorage）
    router.push('/dashboard')
  } catch (e) {
    error.value = e.message || 'Login failed'
  }
}

const resendCode = () => alert('Code resent to your email!')
</script>

<style scoped>
/* 整体为左右分栏布局（无渐变），移动端自动堆叠 */
.split-login {
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 100vh;
  background: var(--bg-light);
}

/* 左侧信息区 */
.left-pane {
  background: var(--white);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
  border-right: 1px solid var(--border-light);
}
.left-inner {
  width: 100%;
  max-width: 560px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}
.brand-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--charcoal);
}
.logo-icon {
  width: 48px;
  height: 48px;
  background-color: var(--white);
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.login-logo-icon img {
  width: 70%;
  height: 70%;
  object-fit: contain;
}

.custom-content :deep(h2.info-title) {
  font-size: 1.75rem;
  margin-bottom: 0.75rem;
  color: var(--charcoal);
}
.custom-content :deep(p) {
  color: #566;
  margin-bottom: 0.75rem;
  line-height: 1.7;
}
.custom-content :deep(ul.info-list) {
  margin: 0.75rem 0 1rem 1.25rem;
  color: var(--charcoal);
}
.links {
  margin-top: 1rem;
}

/* 右侧登录区：纯色背景（无渐变） */
.right-pane {
  background: var(--dark-green); /* 纯色 */
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
}

/* 复用你原来的卡片风格 */
.login-card {
  background-color: var(--white);
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
  width: 100%;
  max-width: 420px;
  padding: 2rem;
}
.login-logo {
  text-align: center;
}
.login-logo-icon {
  width: 72px;
  height: 72px;
  background-color: var(--white);
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0.5rem;
}
.login-title {
  color: var(--charcoal);
  margin-bottom: 0.25rem;
}
.login-subtitle {
  color: #6c757d;
  margin-bottom: 1.25rem;
}

/* 让“Resend Code”看起来像链接但本质是按钮，避免 hash 跳转 */
.linklike {
  background: none;
  border: none;
  color: var(--dark-green);
  cursor: pointer;
  font: inherit;
  padding: 0;
  text-decoration: underline;
}

/* 响应式：小屏改为上下布局，右侧（登录）在上面 */
@media (max-width: 900px) {
  .split-login {
    grid-template-columns: 1fr;
  }
  .right-pane {
    order: -1;
  }
  .left-pane, .right-pane {
    padding: 2rem 1.25rem;
  }
}
</style>
